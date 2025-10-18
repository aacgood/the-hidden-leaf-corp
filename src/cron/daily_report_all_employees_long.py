import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/all_employees_report.txt"


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


def build_employees_report(rows: list[dict]) -> str:
    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S TCT")
    snapshot_date = utc_now.strftime("%Y-%m-%d")

    if not rows:
        return f"No employee data found.\nGenerated at: {timestamp}"

    # Determine column widths
    name_width = max(len("Employee Name"), *(len(r["employee_name"]) for r in rows))
    company_width = max(len("Company Name"), *(len(r["company"]["company_name"]) if r.get("company") else 12 for r in rows))
    position_width = max(len("Position"), *(len(r["position"]) if r.get("position") else 8 for r in rows))
    num_width = 14  # for numeric columns

    # Header
    header = (
        f"{'Employee Name':<{name_width}}  "
        f"{'Torn ID':>10}  "
        f"{'Company Name':<{company_width}}  "
        f"{'Position':<{position_width}}  "
        f"{'Wage':>{num_width}}  "
        f"{'Working Stats':>{num_width}}  "
        f"{'Effectiveness':>{num_width}}  "
        f"{'Allowable Addiction':>{num_width}}"
    )

    top_line = "=" * len(header)
    lines = [
        top_line,
        " " * max(0, (len(header) - 35)//2) + "EMPLOYEES SNAPSHOT REPORT",
        f"Snapshot Date: {snapshot_date}",
        f"Generated at: {timestamp}",
        top_line,
        "",
        header,
        "-" * len(header)
    ]

    total_wage = 0
    total_working = 0
    total_effectiveness = 0
    total_addiction = 0

    # Sort by company name then employee_name
    rows_sorted = sorted(rows, key=lambda r: r.get("working_stats", 0), reverse=True)


    for r in rows_sorted:
        employee = r["employee_name"]
        torn_id = r["torn_user_id"]
        company_name = r.get("company", {}).get("company_name", f"Company {r['company_id']}")
        position = r.get("position", "-")
        wage = r.get("wage") or 0
        working_stats = r.get("working_stats") or 0
        effectiveness = r.get("effectiveness_total") or 0
        allowable_addiction = r.get("allowable_addiction") or 0

        total_wage += wage
        total_working += working_stats
        total_effectiveness += effectiveness
        total_addiction += allowable_addiction

        lines.append(
            f"{employee:<{name_width}}  "
            f"{torn_id:>10}  "
            f"{company_name:<{company_width}}  "
            f"{position:<{position_width}}  "
            f"${wage:>{num_width-1},}  "
            f"{working_stats:>{num_width}}  "
            f"{effectiveness:>{num_width}}  "
            f"{allowable_addiction:>{num_width}}"
        )


    return "\n".join(lines)


def save_report_to_file(report_text: str, file_path: str):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"✅ Report written to {file_path}")
    except Exception as e:
        print(f"❌ Error writing report: {e}")


def send_discord_file(webhook_url: str, file_path: str, message: str = None):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"content": message or "📊 Employees snapshot report attached."}
            response = requests.post(webhook_url, data=data, files=files, timeout=30)

        if response.status_code in (200, 204):
            print("✅ Report successfully sent to Discord.")
        else:
            print(f"⚠️ Discord returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")


def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    # Query all companies that have a Discord channel
    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"❌ Error fetching discord channels: {e}")
        return

    for ch in channels:
        company_id = 0  # Special ID for group ops
        discord_webhook_url = ch.get("discord_webhook_url")
        if not discord_webhook_url:
            print(f"No webhook for company {company_id}, skipping")
            continue

    # Fetch all employee snapshots
    try:
        employees_query = (
            supabase.table("employees")
            .select(
                "employee_name, torn_user_id, company_id, position, wage, working_stats, effectiveness_total, allowable_addiction, company:company_id(company_name)"
            )
            .execute()
        )
        
        employees = employees_query.data or []

        # Ensure working_stats exists and is an int
        for e in employees:
            if e.get("working_stats") is None:
                e["working_stats"] = 0

    except Exception as e:
        print(f"❌ Error fetching employees: {e}")
        return

    if not employees:
        print("⚠️ No employee data found.")
        return

    # Build report
    report_text = build_employees_report(employees)
    save_report_to_file(report_text, REPORT_PATH)

    # Send report to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 Employees Snapshot Report ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    )

    print("✅ Employees snapshot report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
