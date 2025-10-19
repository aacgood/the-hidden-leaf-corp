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
EDUCATION_TAB = "Director Education"
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


    # write the JSON to a temporary file
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

# --- Fetch directors and courses from Supabase ---
def fetch_directors_and_courses(supabase: Client):
    # Directors
    directors_query = (
        supabase.table("directors")
        .select("torn_user_id, director_name, company_id, company:company(company_id, company_name, company_acronym)")
        .eq("prospective", False)
        .execute()
    )
    directors_raw = directors_query.data or []

    directors = []
    for d in directors_raw:
        comp = d.get("company") or {}
        directors.append({
            "torn_user_id": d.get("torn_user_id"),
            "director_name": d.get("director_name"),
            "company_id": comp.get("company_id") or d.get("company_id"),
            "company_name": comp.get("company_name"),
            "company_acronym": comp.get("company_acronym"),
            "completed_courses": []
        })

    # Courses
    courses_query = supabase.table("ref_education").select("course_id, course_code, course_name").execute()
    courses = courses_query.data or []

    # Completed education
    completed_query = supabase.table("director_education").select("torn_user_id, course_id").eq("completed", True).execute()
    completed_rows = completed_query.data or []

    completed_map = {}
    for row in completed_rows:
        completed_map.setdefault(row["torn_user_id"], []).append({"course_id": row["course_id"]})

    for director in directors:
        director["completed_courses"] = completed_map.get(director["torn_user_id"], [])

    return directors, courses

# --- Write data to Google Sheet ---
def write_education_to_sheet(directors, courses):
    client = gsheets_client()
    sheet = client.open(GSHEET_NAME).worksheet(EDUCATION_TAB)

    # Clear existing data
    sheet.clear()

    # Build header row
    header = ["Course Code", "Course Name"] + [d["director_name"] for d in directors]

    # Map completed course IDs for each director
    director_completed_map = {
        d["torn_user_id"]: {c["course_id"] for c in d["completed_courses"]} for d in directors
    }

    # Build all rows in memory
    all_rows = [header]
    for c in sorted(courses, key=lambda x: x["course_code"]):
        row = [c["course_code"], c["course_name"]]
        for d in directors:
            completed_ids = director_completed_map.get(d["torn_user_id"], set())
            status = "✅" if c["course_id"] in completed_ids else "❌"
            row.append(status)
        all_rows.append(row)

    # Determine the range to update
    num_rows = len(all_rows)
    num_cols = len(all_rows[0])
    end_col_letter = chr(64 + num_cols) if num_cols <= 26 else None  # single letters only
    update_range = f"A1:{end_col_letter}{num_rows}" if end_col_letter else "A1"

    # Batch update all rows in one call
    sheet.update(update_range, all_rows)

    # Freeze header row and first two columns
    sheet.freeze(rows=1)
    sheet.freeze(cols=2)


def send_discord_sheet_link(webhook_url: str, sheet_name: str):
    
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return
    
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M TCT")
    content = f"🎓 The Hidden Leaf Corp - Director Education Report is now available online. (Generated: {utc_now})"

    # Build the Google Sheet URL
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit"

    # Embed payload
    embed = {
        "title": sheet_name,
        "url": sheet_url,
        "description": f"{content}",
        "color": 0x00ff00  # optional, green accent
    }

    payload = {
        "username": "THLC Bot",
        "embeds": [embed]
    }

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

    directors, courses = fetch_directors_and_courses(supabase)
    if not directors or not courses:
        print("⚠️ No directors or courses found.")
        return
    write_education_to_sheet(directors, courses)
    
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
    
    send_discord_sheet_link(discord_webhook_url, GSHEET_NAME)
    print(f"✅ Directors education written to Google Sheet '{GSHEET_NAME}' tab '{EDUCATION_TAB}'.")

if __name__ == "__main__":
    lambda_handler()
