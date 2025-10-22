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
EMPLOYEES_TAB = "All Employees"
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

# --- Fetch all employees from Supabase ---
def fetch_employees(supabase: Client):
    try:
        employees_query = (
            supabase.table("employees")
            .select(
                "employee_name, torn_user_id, company_id, position, wage, working_stats, "
                "effectiveness_total, allowable_addiction, manual_labor, intelligence, endurance, "
                "addiction, inactivity, days_in_company, company:company_id(company_name)"
            )
            .execute()
        )
        employees = employees_query.data or []

        for e in employees:
            e["manual_labor"] = e.get("manual_labor") or 0
            e["intelligence"] = e.get("intelligence") or 0
            e["endurance"] = e.get("endurance") or 0
            e["working_stats"] = e.get("working_stats") or 0
            e["effectiveness_total"] = e.get("effectiveness_total") or 0
            e["allowable_addiction"] = e.get("allowable_addiction") or 0
            e["wage"] = e.get("wage") or 0
            e["addiction"] = e.get("addiction") or 0
            e["inactivity"] = e.get("inactivity") or 0
            e["days_in_company"] = e.get("days_in_company") or 0

        return employees
    except Exception as e:
        print(f"❌ Error fetching employees: {e}")
        return []

# --- Write employee data to Google Sheet ---
def write_employees_to_sheet(employees):
    if not employees:
        print("⚠️ No employees to write to Google Sheet.")
        return

    client = gsheets_client()
    sheet = client.open(GSHEET_NAME).worksheet(EMPLOYEES_TAB)

    # Clear existing data
    sheet.clear()

    # Header
    header = [
        "Employee Name", "Torn ID", "Company Name", "Position", "Days in Company",
        "Wage", "Manual Labor", "Intelligence", "Endurance",
        "Working Stats", "Effectiveness", "Allowable Addiction",
        "Current Addiction", "Inactivity"
    ]
    all_rows = [header]

    # Rows
    for e in sorted(employees, key=lambda r: r.get("working_stats", 0), reverse=True):
        company_name = (e.get("company") or {}).get("company_name") or f"Company {e['company_id']}"
        row = [
            e["employee_name"],
            e["torn_user_id"],
            company_name,
            e.get("position") or "-",
            e["days_in_company"],
            e["wage"],
            e["manual_labor"],
            e["intelligence"],
            e["endurance"],
            e["working_stats"],
            e["effectiveness_total"],
            e["allowable_addiction"],
            e["addiction"],
            e["inactivity"],
        ]
        all_rows.append(row)

    # Add timestamp row
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S TCT")
    last_updated_row = [f"Last Updated: {utc_now}"] + [""] * (len(header) - 1)
    all_rows.append(last_updated_row)

    num_rows = len(all_rows)
    num_cols = len(all_rows[0])
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    sheet.update(update_range, all_rows)
    sheet.freeze(rows=1)

    # Apply currency format to Wage column
    try:
        sheet.format('F2:F', {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "$#,##0"
            }
        })
        print("✅ Applied currency format to Wage column (F).")
    except Exception as e:
        print(f"❌ Error applying format: {e}")

    print(f"✅ Written {len(employees)} employees to Google Sheet tab '{EMPLOYEES_TAB}'.")

    # Return gid for the Discord link
    return sheet._properties['sheetId']

# --- Send Google Sheet link to Discord ---
def send_discord_sheet_link(webhook_url: str, sheet_name: str, gid: int):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"📊 Employees Report is available.\n\nGenerated: {utc_now}"
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
    employees = fetch_employees(supabase)
    if not employees:
        return

    gid = write_employees_to_sheet(employees)

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
