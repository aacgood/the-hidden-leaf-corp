# weekly_report_directors_stocks_gsheets.py
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
GSHEET_NAME = "The Hidden Leaf Corp - Prospective Directors"
GSHEET_ID = "1yRjH7WdwALSioFgVtJxS-n-rOrLzfn7pDTFn44qpeAA"
STOCKS_TAB = "Director Stocks"
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

    # write the JSON to a temporary file (gspread / oauth2client expects a file)
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

# --- Fetch directors and stocks from Supabase ---
def fetch_director_stock_data(supabase: Client):
    try:
        directors_query = (
            supabase.table("director_stock_blocks")
            .select(
                "torn_user_id, shares_held, has_block, "
                "director:directors(torn_user_id, director_name, prospective, company_id, company:company(company_id, company_name)), "
                "stock:ref_stocks(stock_id, stock_name, stock_acronym)"
            )
            .execute()
        )
        rows = directors_query.data or []

        # Keep only rows where director.prospective is True
        rows = [r for r in rows if (r.get("director") or {}).get("prospective")]

    except Exception as e:
        print(f"❌ Error fetching director stock data: {e}")
        return [], [], []

    # Flatten structure into usable rows with safe defaults
    flattened = []
    for r in rows:
        director = r.get("director") or {}
        stock = r.get("stock") or {}
        company = director.get("company") or {}

        director_name = director.get("director_name") or "Unknown Director"
        company_name = company.get("company_name") or "Unknown Company"
        stock_acronym = stock.get("stock_acronym") or "UNKNOWN"

        flattened.append({
            "torn_user_id": director.get("torn_user_id"),
            "director_name": director_name,
            "company_id": company.get("company_id") or director.get("company_id"),
            "company_name": company_name,
            "stock_id": stock.get("stock_id"),
            "stock_name": stock.get("stock_name"),
            "stock_acronym": stock_acronym,
            "completed": r.get("has_block", False),
            "shares_held": r.get("shares_held", 0)
        })

    if not flattened:
        return [], [], []

    # Unique directors in display format "Director / Company"
    directors_set = {f"{d['director_name']}" for d in flattened}
    directors_list = sorted(directors_set)

    # Fetch all stock acronyms from ref_stocks (even if no director has it)
    try:
        stocks_query = supabase.table("ref_stocks").select("stock_acronym").execute()
        stocks_data = stocks_query.data or []
        stocks_list = sorted({s.get("stock_acronym") or "UNKNOWN" for s in stocks_data})
    except Exception as e:
        print(f"❌ Error fetching stock acronyms: {e}")
        # fallback: use any found in flattened
        stocks_list = sorted({d["stock_acronym"] for d in flattened if d.get("stock_acronym")})

    return flattened, directors_list, stocks_list

# --- Build matrix rows for Google Sheet ---
def build_stocks_sheet_rows(flattened, directors_list, stocks_list):
    header = ["Prospective Director"] + stocks_list
    all_rows = [header]

    # Create a lookup map for quick matching
    lookup = {}
    for r in flattened:
        director_key = f"{r['director_name']}"
        stock_key = r['stock_acronym']
        lookup.setdefault(director_key, {})[stock_key] = r

    for director in directors_list:
        row = [director]
        director_map = lookup.get(director, {})
        for stock in stocks_list:
            entry = director_map.get(stock)
            if entry is None:
                row.append("❌")
            else:
                row.append("✅" if entry.get("completed") else "⚪")
        all_rows.append(row)

    # Empty separator row
    all_rows.append([""] * len(header))

    # Last Updated row (first column label with timestamp in second column)
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S TCT")
    last_row = [f"Last Updated: {utc_now}"] + [""] * (len(header) - 1)
    all_rows.append(last_row)

    return all_rows

# --- Write matrix to Google Sheet ---
def write_stocks_to_sheet(all_rows):
    client = gsheets_client()

    try:
        sheet = client.open(GSHEET_NAME).worksheet(STOCKS_TAB)
    except gspread.SpreadsheetNotFound:
        # If the spreadsheet doesn't exist, create it and then add the tab
        spreadsheet = client.create(GSHEET_NAME)
        sheet = spreadsheet.sheet1
        sheet.update_title(STOCKS_TAB)

    # Clear existing data
    sheet.clear()

    # Determine update range
    num_rows = len(all_rows)
    num_cols = len(all_rows[0]) if all_rows else 1
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    # Batch update
    sheet.update(update_range, all_rows)

    # Freeze header row and first column
    sheet.freeze(rows=1)
    sheet.freeze(cols=1)

    return sheet._properties.get("sheetId")

# --- Send Google Sheet link to Discord ---
def send_discord_sheet_link(webhook_url: str, sheet_name: str, gid: int):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"📊 Prospective Director Stocks Report is available.\n\nGenerated: {utc_now}"
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

    flattened, directors_list, stocks_list = fetch_director_stock_data(supabase)
    if not flattened:
        print("⚠️ No director stock data found.")
        return

    all_rows = build_stocks_sheet_rows(flattened, directors_list, stocks_list)
    gid = write_stocks_to_sheet(all_rows)

    # Fetch discord channel for group ops
    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"❌ Error fetching discord channels: {e}")
        return

    discord_webhook_url = None
    for ch in channels:
        if ch.get("company_id", 0) == 0:
            discord_webhook_url = ch.get("discord_webhook_url")
            break

    if not discord_webhook_url:
        print("⚠️ No group ops discord webhook found.")
        return

    send_discord_sheet_link(discord_webhook_url, GSHEET_NAME, gid)
    print(f"✅ Directors stock matrix written to Google Sheet '{GSHEET_NAME}' tab '{STOCKS_TAB}'.")

if __name__ == "__main__":
    lambda_handler()
