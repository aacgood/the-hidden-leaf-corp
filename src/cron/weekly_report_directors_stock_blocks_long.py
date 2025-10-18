import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/directors_stock_report.txt"


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


def build_directors_report(rows: list[dict]) -> str:
    """Builds a directors snapshot report, grouped by director."""
    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S TCT")

    if not rows:
        return f"No director data found.\nGenerated at: {timestamp}"

    # Column widths
    stock_code_width = max(len("Code"), *(len(r.get("stock_acronym", "")) for r in rows))
    stock_name_width = max(len("Stock Name"), *(len(r.get("stock_name", "")) for r in rows)) + 10
    shares_width = 12
    completed_width = 9  # enough space for emoji + padding

    lines = [
        "=" * 80,
        " " * 10 + "DIRECTORS SNAPSHOT REPORT",
        f"Generated at: {timestamp}",
        "=" * 80,
        ""
    ]

    # Group by director
    directors_map = {}
    for r in rows:
        key = r["torn_user_id"]
        directors_map.setdefault(key, []).append(r)

    for director_id, items in directors_map.items():
        lines.append("")  # blank line after director header
        lines.append("")  # blank line after director header
        
        director = items[0]
        header = f"Director: {director['director_name']} [{director['torn_user_id']}]: {director.get('company_name', f'Company {director.get('company_id')}')} [{director.get('company_id')}]"
        lines.append(header)
        lines.append("")  # blank line after director header

        # Table header
        table_header = (
            f"{'Code':<{stock_code_width}}  "
            f"{'Stock Name':<{stock_name_width}}  "
            f"{'Shares Held':>{shares_width}}  "
            f"{'Ready':^{completed_width}}"
        )
        lines.append(table_header)
        lines.append("-" * len(table_header))

        # Table rows
        for r in items:
            code = r.get("stock_acronym", "")
            stock_name = r.get("stock_name", "")
            shares = r.get("shares_held", 0)
            completed = "✅" if r.get("completed") else "⚪"
            lines.append(
                f"{code:<{stock_code_width}}  "
                f"{stock_name:<{stock_name_width}}  "
                f"{shares:>{shares_width},}  "
                f"{completed:^{completed_width}}"
            )

        lines.append("")  # blank line between directors

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
            data = {"content": message or "📊 Directors stock report attached."}
            response = requests.post(data=data, files=files, url=webhook_url, timeout=30)

        if response.status_code in (200, 204):
            print("✅ Report successfully sent to Discord.")
        else:
            print(f"⚠️ Discord returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")


def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

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

    # Fetch director stock data
    try:
        directors_query = (
            supabase.table("director_stock_blocks")
            .select(
                "torn_user_id, shares_held, has_block, "
                "director:directors(torn_user_id, director_name, company_id, company:company(company_id, company_name, company_acronym)), "
                "stock:ref_stocks(stock_name, stock_acronym)"
            )
            .execute()
        )
        directors = directors_query.data or []

        # Flatten nested structures
        flattened = []
        for r in directors:
            director = r.get("director", {})
            stock = r.get("stock", {})
            company = director.get("company", {})

            flattened.append({
                "torn_user_id": r.get("torn_user_id"),
                "director_name": director.get("director_name"),
                "company_id": company.get("company_id"),
                "company_name": company.get("company_name"),
                "company_acronym": company.get("company_acronym"),
                "stock_name": stock.get("stock_name"),
                "stock_acronym": stock.get("stock_acronym"),
                "shares_held": r.get("shares_held"),
                "completed": r.get("has_block", False)
            })

    except Exception as e:
        print(f"❌ Error fetching directors: {e}")
        return

    if not flattened:
        print("⚠️ No director stock data found.")
        return

    # Build report
    report_text = build_directors_report(flattened)
    save_report_to_file(report_text, REPORT_PATH)

    # Send report to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 Directors Stock Holdings Report ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    )

    print("✅ Directors stock report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
