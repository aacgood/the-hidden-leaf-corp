# src/discord_bot/_commands/company_info.py
import json
import boto3
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# --- Secrets ---
def get_secrets():
    client = boto3.client("secretsmanager", region_name="ap-southeast-1")

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_APPLICATION_ID": discord_secret.get("DISCORD_APPLICATION_ID"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }

SECRETS = get_secrets()
supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

def handle_company_info(msg):
    """
    Handle /company info command: display all companies in a fixed-width table.
    """
    payload = msg["payload"]

    try:
        resp = supabase.table("company").select(
            "company_acronym, company_name, last_updated"
        ).order("company_acronym", desc=False).execute()
    except Exception as e:
        print(f"⚠️ Supabase query failed: {e}")
        return send_followup(payload, "🚫 Failed to fetch company data.")

    companies = resp.data or []

    if not companies:
        return send_followup(payload, "⚠️ No companies found.")

    # --- Build fixed-width table ---
    header = f"{'Acronym':<8}{'Name':<28}{'Last Updated':<20}"
    lines = [header, "-" * len(header)]

    for c in companies:
        acronym = c.get("company_acronym", "")
        name = c.get("company_name", "")
        updated_raw = c.get("last_updated", "")
        updated = updated_raw.split(".")[0].replace("T", " ") + " TCT"

        lines.append(
            f"{acronym:<8}{name:<28}{updated:<20}"
        )

    timestamp_line = f" ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S TCT')})"

    table_block = "```\n" + "\n".join(lines) + "\n```"

    table_msg = f"**Company Info**{timestamp_line}\n\n{table_block}"

    return send_followup(payload, table_msg)


def send_followup(payload, content: str, edit_original: bool = True) -> str | None:
    token = payload.get("token")
    app_id = SECRETS["DISCORD_APPLICATION_ID"]

    if edit_original:
        url = f"https://discord.com/api/webhooks/{app_id}/{token}/messages/@original"
        method = "patch"
    else:
        url = f"https://discord.com/api/webhooks/{app_id}/{token}"
        method = "post"

    headers = {"Content-Type": "application/json"}
    body = {"content": content}

    try:
        r = requests.request(method, url, headers=headers, json=body)
        if r.status_code in [200, 201]:
            return r.json().get("id")
        else:
            print(f"⚠️ Discord follow-up failed: {r.status_code}, {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ Discord follow-up exception: {e}")
        return None