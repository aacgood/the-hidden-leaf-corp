import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Config ---
REGION = "ap-southeast-1"
GSHEET_NAME = "The Hidden Leaf Corp - Reports"
GSHEET_ID = "1MgX93FK1PduIKgtz8RqIcG9U4kZhxRFJoN0kLtrJrVU"
INVESTMENTS_TAB = "Investments"
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

# --- Fetch all investments from Supabase ---
def fetch_investments(supabase: Client):
    try:
        investments_query = (
            supabase.table("company_investments")
            .select("company_id, investor_name, total_invested, total_returned, company:company_id(company_name)")
            .eq("status", "active")
            .execute()
        )
        investments = investments_query.data or []

        for inv in investments:
            inv["total_invested"] = inv.get("total_invested") or 0
            inv["total_returned"] = inv.get("total_returned") or 0

        return investments
    except Exception as e:
        print(f"❌ Error fetching investments: {e}")
        return []

# --- Write investment data to Google Sheet ---
def write_investments_to_sheet(investments):
    if not investments:
        print("⚠️ No investments to write to Google Sheet.")
        return

    client = gsheets_client()
    sheet = client.open(GSHEET_NAME).worksheet(INVESTMENTS_TAB)

    # Clear existing data
    sheet.clear()

    # Header
    header = ["Investor Name", "Company Name", "Total Invested", "Total Returned"]
    all_rows = [header]

    total_invested = 0
    total_returned = 0

    # Sort by investor name then company
    for inv in sorted(investments, key=lambda x: (x["investor_name"], (x.get("company") or {}).get("company_name", ""))):
        company_name = (inv.get("company") or {}).get("company_name") or f"Company {inv['company_id']}"
        row = [
            inv["investor_name"],
            company_name,
            inv["total_invested"],
            inv["total_returned"],
        ]
        all_rows.append(row)
        total_invested += inv["total_invested"]
        total_returned += inv["total_returned"]

    # Totals row
    all_rows.append(["", "TOTAL", total_invested, total_returned])

    # Timestamp footer
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S TCT")
    all_rows.append([f"Last Updated: {utc_now}"] + [""] * (len(header) - 1))

    # Write to sheet
    num_rows = len(all_rows)
    num_cols = len(all_rows[0])
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    sheet.update(update_range, all_rows)
    sheet.freeze(rows=1)

    # Apply currency format to columns C and D
    try:
        sheet.format('C2:D', {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "$#,##0"
            }
        })
        print("✅ Applied currency format to columns C and D.")
    except Exception as e:
        print(f"❌ Error applying format: {e}")

    print(f"✅ Written {len(investments)} investments to Google Sheet tab '{INVESTMENTS_TAB}'.")

    # Return gid for the Discord link
    return sheet._properties['sheetId']

# --- Send Google Sheet link to Discord ---
def send_discord_sheet_link(webhook_url: str, sheet_name: str, gid: int):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"💰 Company Investments (Total) Report is available.\n\nGenerated: {utc_now}"
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit#gid={gid}"

    embed = {
        "title": sheet_name,
        "url": sheet_url,
        "description": content,
        "color": 0x2ecc71
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
    investments = fetch_investments(supabase)
    if not investments:
        return

    gid = write_investments_to_sheet(investments)

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

if __name__ == "__main__":
    lambda_handler()