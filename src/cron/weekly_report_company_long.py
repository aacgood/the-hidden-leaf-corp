import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/company_financials_report_7d.txt"


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


def build_financials_report(aggregated_rows: list[dict], start_date: str, end_date: str) -> str:
    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")

    if not aggregated_rows:
        return f"No data\nReport Range: {start_date} → {end_date}\nGenerated at: {timestamp}"

    # Column widths
    name_width = max(len("Company Name"), *(len(r["company_name"]) for r in aggregated_rows))
    days_width = max(len("Days Old"), *(len(str(r["days_old"])) for r in aggregated_rows))
    num_width = 14  # numeric column width

    # Header text
    header = (
        f"{'Company Name':<{name_width}}  "
        f"{'Days Old':>{days_width}}  "
        f"{'Revenue':>{num_width}}  "
        f"{'Stock Cost':>{num_width}}  "
        f"{'Wages':>{num_width}}  "
        f"{'Advertising':>{num_width}}  "
        f"{'Profit':>{num_width}}"
    )

    top_line = "=" * len(header)

    lines = [
        top_line,
        " " * max(0, (len(header) - 36)//2) + "COMPANY 7-DAY AGGREGATED FINANCIALS REPORT",
        f"Report Range: {start_date} → {end_date}",
        f"Generated at: {timestamp}",
        top_line,
        "",
        header,
        "-" * len(header)
    ]

    totals = {"revenue": 0, "stock_cost": 0, "wages": 0, "advertising": 0, "profit": 0}

    for r in sorted(aggregated_rows, key=lambda x: x["days_old"], reverse=True):
        lines.append(
            f"{r['company_name']:<{name_width}}  "
            f"{r['days_old']:>{days_width}}  "
            f"{format_currency(r['revenue']):>{num_width}}  "
            f"{format_currency(r['stock_cost']):>{num_width}}  "
            f"{format_currency(r['wages']):>{num_width}}  "
            f"{format_currency(r['advertising']):>{num_width}}  "
            f"{format_currency(r['profit']):>{num_width}}"
        )

        totals["revenue"] += r["revenue"]
        totals["stock_cost"] += r["stock_cost"]
        totals["wages"] += r["wages"]
        totals["advertising"] += r["advertising"]
        totals["profit"] += r["profit"]

    # Totals block
    lines.append("")
    lines.append("=" * len(header))
    lines.append("GRAND TOTALS (7 DAYS)".center(len(header)))
    lines.append("=" * len(header))
    lines.append(
        f"{'':<{name_width}}  "
        f"{'':>{days_width}}  "
        f"{format_currency(totals['revenue']):>{num_width}}  "
        f"{format_currency(totals['stock_cost']):>{num_width}}  "
        f"{format_currency(totals['wages']):>{num_width}}  "
        f"{format_currency(totals['advertising']):>{num_width}}  "
        f"{format_currency(totals['profit']):>{num_width}}"
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
            data = {"content": message or "📊 7-day aggregated company financials report attached."}
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

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)

    # Fetch all records in the 7-day range
    try:
        financials_query = (
            supabase.table("company_financials")
            .select("company_id, revenue, stock_cost, wages, advertising, profit, capture_date")
            .gte("capture_date", str(start_date))
            .lte("capture_date", str(end_date))
            .execute()
        )
        financials = financials_query.data or []
    except Exception as e:
        print(f"❌ Error fetching financials: {e}")
        return

    if not financials:
        print("⚠️ No financial data found for the 7-day period.")
        return

    # Aggregate by company_id
    aggregates = {}
    for row in financials:
        cid = row["company_id"]
        if cid not in aggregates:
            aggregates[cid] = {
                "company_id": cid,
                "revenue": 0,
                "stock_cost": 0,
                "wages": 0,
                "advertising": 0,
                "profit": 0,
            }
        aggregates[cid]["revenue"] += row.get("revenue", 0) or 0
        aggregates[cid]["stock_cost"] += row.get("stock_cost", 0) or 0
        aggregates[cid]["wages"] += row.get("wages", 0) or 0
        aggregates[cid]["advertising"] += row.get("advertising", 0) or 0
        aggregates[cid]["profit"] += row.get("profit", 0) or 0

    # Fetch company info
    try:
        company_ids = list(aggregates.keys())
        companies_query = (
            supabase.table("company")
            .select("company_id, company_name, days_old")
            .in_("company_id", company_ids)
            .execute()
        )
        companies = {c["company_id"]: c for c in companies_query.data}
    except Exception as e:
        print(f"❌ Error fetching company info: {e}")
        return

    # Merge into final list
    merged = []
    for cid, data in aggregates.items():
        c = companies.get(cid, {})
        merged.append({
            "company_id": cid,
            "company_name": c.get("company_name", f"Company {cid}"),
            "days_old": c.get("days_old", 0),
            **data,
        })

    # Build report
    report_text = build_financials_report(merged, str(start_date), str(end_date))
    save_report_to_file(report_text, REPORT_PATH)

    # Step 6: Send to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 7-Day Aggregated Company Financials Report ({start_date} → {end_date})"
    )

    print("✅ 7-day aggregated financials report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
