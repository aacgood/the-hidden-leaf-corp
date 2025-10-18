import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/company_investments_report_weekly.txt"


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


def format_currency(value: int | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.0f}"


def build_investments_report(investments: list[dict]) -> str:
    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S TCT")
    snapshot_date = utc_now.strftime("%Y-%m-%d")

    if not investments:
        return f"No active investments found.\nGenerated at: {timestamp}"

    # Determine column widths
    investor_width = max(len("Investor Name"), *(len(i["investor_name"]) for i in investments))
    company_width = max(len("Company Name"), *(len(i["company"]["company_name"]) if i.get("company") else 12 for i in investments))
    num_width = 16  # width for Invested and Returned

    # Build header line
    header = (
        f"{'Investor Name':<{investor_width}}  "
        f"{'Company Name':<{company_width}}  "
        f"{'Invested':>{num_width}}  "
        f"{'Returned':>{num_width}}"
    )

    top_line = "=" * len(header)
    lines = [
        top_line,
        " " * max(0, (len(header) - 41)//2) + "WEEKLY COMPANY INVESTMENTS SNAPSHOT",
        f"Snapshot Date: {snapshot_date}",
        f"Generated at: {timestamp}",
        top_line,
        "",
        header,
        "-" * len(header)
    ]

    total_invested = 0
    total_returned = 0

    # Sort by investor name
    investments.sort(key=lambda x: x["investor_name"])
    current_investor = None

    for inv in investments:
        investor = inv["investor_name"]
        company_name = inv["company"]["company_name"] if inv.get("company") else f"Company {inv['company_id']}"
        invested = inv.get("total_invested", 0) or 0
        returned = inv.get("total_returned", 0) or 0

        total_invested += invested
        total_returned += returned

        if investor != current_investor:
            lines.append("")  # spacing between investors
            current_investor = investor

        lines.append(
            f"{investor:<{investor_width}}  "
            f"{company_name:<{company_width}}  "
            f"{format_currency(invested):>{num_width}}  "
            f"{format_currency(returned):>{num_width}}"
        )

    # Totals block aligned with numeric columns
    lines.append("")
    lines.append("=" * len(header))
    lines.append("GRAND TOTALS".center(len(header)))
    lines.append("=" * len(header))
    lines.append(
        f"{'':<{investor_width}}  "
        f"{'':<{company_width}}  "
        f"{format_currency(total_invested):>{num_width}}  "
        f"{format_currency(total_returned):>{num_width}}"
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
            data = {"content": message or "📊 Weekly company investments snapshot attached."}
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
        print(f"Error fetching discord channels: {e}")
        return

    for ch in channels:
        company_id = 0 # Special ID for group ops
        discord_webhook_url = ch.get("discord_webhook_url")
        if not discord_webhook_url:
            print(f"No webhook for company {company_id}, skipping")
            continue

    # Fetch all active investments
    try:
        investments_query = (
            supabase.table("company_investments")
            .select("company_id, investor_name, total_invested, total_returned, company:company_id(company_name)")
            .eq("status", "active")
            .execute()
        )
        investments = investments_query.data or []
    except Exception as e:
        print(f"❌ Error fetching investments: {e}")
        return

    if not investments:
        print("⚠️ No active investments found.")
        return

    # Build and save report
    report_text = build_investments_report(investments)
    save_report_to_file(report_text, REPORT_PATH)

    # Send report to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 Weekly Company Investments Snapshot ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    )

    print("✅ Weekly company investments report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
