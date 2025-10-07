import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone

REGION = "ap-southeast-1"

def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_WEBHOOK_CHANNEL_THLC_BOT": discord_secret.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }

SECRETS = get_secrets()

def send_discord_message(webhook_url: str, message: str):
    if not webhook_url:
        print("Discord webhook missing")
        return
    try:
        resp = requests.post(webhook_url, json={"content": message}, timeout=5)
        print(f"Message sent: {resp.status_code}")
    except Exception as e:
        print(f"Error sending message: {e}")

def shorten(text: str, max_len: int = 9) -> str:
    """Trim text to max_len with ellipsis if needed."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

def build_employee_table(employees: list[dict]) -> str:
    """
    Build a Discord-friendly Markdown table with emoji indicators.
    - ✅ Efficiency >= 100
    - ❌ Efficiency < 80
    - ⚪ Otherwise
    - ❌ Addiction < -5
    - ✅ Addiction >= 0
    - ⚪ Otherwise
    """

    # Timestamp
    utc_now = datetime.now(timezone.utc)


    # Sort by efficiency descending, then addiction ascending
    employees_sorted = sorted(
        employees,
        key=lambda e: (-e.get('effectiveness_total', 0), e.get('addiction', 0))
    )

    header = f"{'Name (Position)':<27}{'Efficiency':<12}{'Addiction':<7}"
    lines = [header, "-" * len(header)]

    for emp in employees_sorted:
        eff = emp.get('effectiveness_total', 0)
        addict = emp.get('addiction', 0)
        name = emp.get('employee_name', '')
        pos = shorten(emp.get('position', ''), 9)

        # Efficiency icon
        if eff >= 100:
            eff_icon = "✅"
        elif eff < 20:
            eff_icon = "❌"
        else:
            eff_icon = "⚪"

        # Addiction icon
        if addict < -5:
            addict_icon = "❌"
        elif addict >= 0:
            addict_icon = "✅"
        else:
            addict_icon = "⚪"

        lines.append(
            f"{name} ({pos})".ljust(27) +
            f"{eff_icon} {eff:<9}" +
            f"{addict_icon} {addict:>2}"
        )

    timestamp_line = f" ({utc_now.strftime('%Y-%m-%d %H:%M:%S TCT')})"
    
    # --- Build the final message ---
    table_block = "```\n" + "\n".join(lines) + "\n```"

    table = (
        "\n\n**Daily Efficiency and Addiction Report**"
        f"{timestamp_line}\n\n"
        f"{table_block}"
    )

    return table

def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    # Query all companies that have a Discord channel
    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"Error fetching discord channels: {e}")
        return

    for ch in channels:
        company_id = ch.get("company_id")
        discord_webhook_url = ch.get("discord_webhook_url")
        if not discord_webhook_url:
            print(f"No webhook for company {company_id}, skipping")
            continue

        # Get all employees for this company
        try:
            employees = supabase.table("employees").select(
                "employee_name, position, effectiveness_total, addiction, allowable_addiction"
            ).eq("company_id", company_id).execute().data
        except Exception as e:
            print(f"Error fetching employees for company {company_id}: {e}")
            continue

        if not employees:
            print(f"No employees found for company {company_id}, skipping")
            continue

        message = build_employee_table(employees)
        send_discord_message(discord_webhook_url, message)
        print(f"Sent employee report for company {company_id}")

    print("Daily employee report job completed.")

if __name__ == "__main__":
    lambda_handler()
