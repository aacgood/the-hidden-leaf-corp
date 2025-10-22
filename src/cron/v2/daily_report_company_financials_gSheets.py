import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import gspread
from oauth2client.service_account import ServiceAccountCredentials

REGION = "ap-southeast-1"
GSHEET_NAME = "The Hidden Leaf Corp - Reports"
GSHEET_ID = "1MgX93FK1PduIKgtz8RqIcG9U4kZhxRFJoN0kLtrJrVU"
FINANCIALS_TAB = "Company Financials - Daily"
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

    creds_path = GOOGLE_CREDS_FILE
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

# --- Fetch latest financials ---
def fetch_latest_financials(supabase: Client):
    try:
        latest_query = (
            supabase.table("company_financials")
            .select("capture_date")
            .order("capture_date", desc=True)
            .limit(1)
            .execute()
        )
        if not latest_query.data:
            print("⚠️ No financial records found.")
            return []

        latest_date = latest_query.data[0]["capture_date"]

        financials_query = (
            supabase.table("company_financials")
            .select("id, company_id, capture_date, revenue, stock_cost, wages, advertising, profit")
            .eq("capture_date", latest_date)
            .order("company_id")
            .execute()
        )
        financials = financials_query.data or []

        # Fetch company info
        company_ids = [f["company_id"] for f in financials]
        companies_query = (
            supabase.table("company")
            .select("company_id, company_name, days_old")
            .in_("company_id", company_ids)
            .execute()
        )
        companies = {c["company_id"]: c for c in companies_query.data}

        # Merge company info
        for f in financials:
            c = companies.get(f["company_id"], {})
            f["company_name"] = c.get("company_name", f"Company {f['company_id']}")
            f["days_old"] = c.get("days_old", 0)

        return financials, latest_date

    except Exception as e:
        print(f"❌ Error fetching financials: {e}")
        return [], None

# --- Write financials to Google Sheet ---
def write_financials_to_sheet(financials, capture_date: str):
    if not financials:
        print("⚠️ No financials to write.")
        return

    client = gsheets_client()
    sheet = client.open(GSHEET_NAME).worksheet(FINANCIALS_TAB)
    sheet.clear()

    header = [
        "Company Name", "Days Old", "Revenue", "Stock Cost", "Wages",
        "Advertising", "Profit"
    ]
    all_rows = [header]

    def format_currency(value):
        return f"${value:,.0f}" if value is not None else "-"

    totals = {"revenue": 0, "stock_cost": 0, "wages": 0, "advertising": 0, "profit": 0}

    for f in sorted(financials, key=lambda r: r.get("days_old", 0), reverse=True):
        revenue = f.get("revenue") or 0
        stock_cost = f.get("stock_cost") or 0
        wages = f.get("wages") or 0
        advertising = f.get("advertising") or 0
        profit = f.get("profit") or (revenue - stock_cost - wages - advertising)

        totals["revenue"] += revenue
        totals["stock_cost"] += stock_cost
        totals["wages"] += wages
        totals["advertising"] += advertising
        totals["profit"] += profit

        row = [
            f["company_name"],
            f["days_old"],
            format_currency(revenue),
            format_currency(stock_cost),
            format_currency(wages),
            format_currency(advertising),
            format_currency(profit)
        ]
        all_rows.append(row)

    # --- Add GRAND TOTALS row ---
    grand_total_row = [
        "GRAND TOTALS",
        "",
        format_currency(totals["revenue"]),
        format_currency(totals["stock_cost"]),
        format_currency(totals["wages"]),
        format_currency(totals["advertising"]),
        format_currency(totals["profit"])
    ]
    all_rows.append([])
    all_rows.append(grand_total_row)

    # Add timestamp row
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S TCT")
    last_updated_row = [f"Last Updated: {utc_now}"] + [""] * (len(header) - 1)
    all_rows.append(last_updated_row)

    # Determine update range
    num_rows = len(all_rows)
    num_cols = len(header)
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    sheet.update(update_range, all_rows)
    sheet.freeze(rows=1)

    # Format numeric columns as currency
    try:
        sheet.format('C2:G', {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0"}})
        print("✅ Applied currency formatting.")
    except Exception as e:
        print(f"❌ Error formatting sheet: {e}")

    return sheet._properties["sheetId"]

# --- Send Google Sheet link to Discord ---
def send_discord_sheet_link(webhook_url: str, sheet_name: str, gid: int):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"📊 Company Financials Report is available.\n\nGenerated: {utc_now}"
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit#gid={gid}"

    embed = {
        "title": sheet_name,
        "url": sheet_url,
        "description": content,
        "color": 0x00ff00
    }
    payload = {"username": "THLC Bot", "embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            print("✅ Google Sheet link sent to Discord.")
        else:
            print(f"⚠️ Discord returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending Discord message: {e}")

# --- Lambda handler ---
def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    financials, capture_date = fetch_latest_financials(supabase)
    if not financials:
        return

    gid = write_financials_to_sheet(financials, capture_date)

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
    print("✅ Company financials report completed successfully.")

if __name__ == "__main__":
    lambda_handler()
