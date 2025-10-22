import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Config ---
REGION = "ap-southeast-1"
GSHEET_NAME = "The Hidden Leaf Corp - Reports"
GSHEET_ID = "1MgX93FK1PduIKgtz8RqIcG9U4kZhxRFJoN0kLtrJrVU"
FINANCIALS_TAB = "Company Financials - Weekly"
GOOGLE_CREDS_FILE = "/tmp/gCreds.json"

# --- Fetch secrets from AWS Secrets Manager ---
def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )
    google_secret = json.loads(
        client.get_secret_value(SecretId="google_service_account")["SecretString"]
    )

    creds_path = "/tmp/gCreds.json"
    with open(creds_path, "w") as f:
        json.dump(google_secret, f)

    return {
        "DISCORD_WEBHOOK_CHANNEL_THLC_BOT": discord_secret.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
        "GOOGLE_CREDS_JSON": creds_path
    }

SECRETS = get_secrets()

# --- Google Sheets client ---
def gsheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(SECRETS["GOOGLE_CREDS_JSON"], scope)
    client = gspread.authorize(creds)
    return client

# --- Format currency ---
def format_currency(value: int | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.0f}"

# --- Build 7-day financials report for Google Sheet ---
def build_financials_sheet_rows(aggregated_rows: list[dict]) -> list[list]:
    if not aggregated_rows:
        return []

    # Header
    header = [
        "Company Name", "Days Old", "Revenue", "Stock Cost",
        "Wages", "Advertising", "Profit"
    ]
    all_rows = [header]

    totals = {"revenue": 0, "stock_cost": 0, "wages": 0, "advertising": 0, "profit": 0}

    # Rows
    for r in sorted(aggregated_rows, key=lambda x: x["days_old"], reverse=True):
        row = [
            r["company_name"],
            r["days_old"],
            r["revenue"],
            r["stock_cost"],
            r["wages"],
            r["advertising"],
            r["profit"]
        ]
        all_rows.append(row)

        totals["revenue"] += r["revenue"]
        totals["stock_cost"] += r["stock_cost"]
        totals["wages"] += r["wages"]
        totals["advertising"] += r["advertising"]
        totals["profit"] += r["profit"]

    # Empty separator row
    all_rows.append([""] * len(header))

    # Totals row
    totals_row = ["GRAND TOTALS"] + [""] + [
        totals["revenue"],
        totals["stock_cost"],
        totals["wages"],
        totals["advertising"],
        totals["profit"]
    ]
    all_rows.append(totals_row)

    # Add timestamp row
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S TCT")
    last_updated_row = [f"Last Updated: {utc_now}"] + [""] * (len(header) - 1)
    all_rows.append(last_updated_row)

    return all_rows

# --- Write to Google Sheet ---
def write_financials_to_sheet(aggregated_rows):
    if not aggregated_rows:
        print("⚠️ No financials to write to Google Sheet.")
        return

    client = gsheets_client()
    sheet = client.open(GSHEET_NAME).worksheet(FINANCIALS_TAB)

    sheet.clear()

    all_rows = build_financials_sheet_rows(aggregated_rows)

    # Update range
    num_rows = len(all_rows)
    num_cols = len(all_rows[0])
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    sheet.update(update_range, all_rows)
    sheet.freeze(rows=1)

    # Apply currency format to numeric columns (Revenue → Profit)
    try:
        sheet.format('C2:G', {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "$#,##0"
            }
        })
        print("✅ Applied currency format to numeric columns (C → G).")
    except Exception as e:
        print(f"❌ Error applying format: {e}")

    return sheet._properties['sheetId']

# --- Send Google Sheet link to Discord ---
def send_discord_sheet_link(webhook_url: str, sheet_name: str, gid: int):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"📊 7-Day Aggregated Company Financials Report is now available.\n\nGenerated: {utc_now}"
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit#gid={gid}"

    embed = {
        "title": sheet_name,
        "url": sheet_url,
        "description": content,
        "color": 0x00ff00
    }
    payload = {"username": "THLC Bot", "embeds": [embed]}

    try:
        response = requests.post(url=webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            print("✅ Google Sheet link sent to Discord (embed).")
        else:
            print(f"⚠️ Discord returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending Discord message: {e}")

# --- Lambda handler ---
def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    # Step 1: Fetch all records in the last 7 days
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)

    try:
        financials_query = (
            supabase.table("company_financials")
            .select("company_id, revenue, stock_cost, wages, advertising, profit")
            .gte("capture_date", str(start_date))
            .lte("capture_date", str(end_date))
            .execute()
        )
        financials = financials_query.data or []
    except Exception as e:
        print(f"❌ Error fetching financials: {e}")
        return

    if not financials:
        print("⚠️ No financial data found for the 7-day period.")
        return

    # Step 2: Aggregate by company_id
    aggregates = {}
    for row in financials:
        cid = row["company_id"]
        if cid not in aggregates:
            aggregates[cid] = {
                "company_id": cid,
                "revenue": 0,
                "stock_cost": 0,
                "wages": 0,
                "advertising": 0,
                "profit": 0,
            }
        aggregates[cid]["revenue"] += row.get("revenue", 0) or 0
        aggregates[cid]["stock_cost"] += row.get("stock_cost", 0) or 0
        aggregates[cid]["wages"] += row.get("wages", 0) or 0
        aggregates[cid]["advertising"] += row.get("advertising", 0) or 0
        aggregates[cid]["profit"] += row.get("profit", 0) or 0

    # Step 3: Fetch company info
    try:
        company_ids = list(aggregates.keys())
        companies_query = (
            supabase.table("company")
            .select("company_id, company_name, days_old")
            .in_("company_id", company_ids)
            .execute()
        )
        companies = {c["company_id"]: c for c in companies_query.data}
    except Exception as e:
        print(f"❌ Error fetching company info: {e}")
        return

    # Step 4: Merge into final list
    merged = []
    for cid, data in aggregates.items():
        c = companies.get(cid, {})
        merged.append({
            "company_id": cid,
            "company_name": c.get("company_name", f"Company {cid}"),
            "days_old": c.get("days_old", 0),
            **data,
        })

    # Step 5: Write to Google Sheet
    gid = write_financials_to_sheet(merged)

    # Step 6: Send Discord link
    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"❌ Error fetching discord channels: {e}")
        return

    discord_webhook_url = next(
        (ch.get("discord_webhook_url") for ch in channels if ch.get("company_id", 0) == 0),
        None
    )

    send_discord_sheet_link(discord_webhook_url, GSHEET_NAME, gid)

    print("✅ 7-day aggregated financials report completed successfully.")

if __name__ == "__main__":
    lambda_handler()
