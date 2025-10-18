import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/company_financials_report.txt"


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


def build_financials_report(rows: list[dict], report_date: str) -> str:
    from datetime import datetime, timezone

    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S TCT")

    # Column widths
    name_width = max(len("Company Name"), *(len(r["company_name"]) for r in rows))
    days_width = max(len("Days Old"), *(len(str(r.get("days_old", 0))) for r in rows))
    num_width = 14  # width for numeric columns

    # Header
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
        " " * ((len(header) - 32)//2) + "COMPANY DAILY FINANCIALS REPORT",
        f"Report Date: {report_date}",
        f"Generated at: {timestamp}",
        top_line,
        "",
        header,
        "-" * len(header)
    ]

    # Sort rows by days_old descending
    rows_sorted = sorted(rows, key=lambda r: r.get("days_old", 0), reverse=True)

    totals = {"revenue": 0, "stock_cost": 0, "wages": 0, "advertising": 0, "profit": 0}

    for r in rows_sorted:
        name = r["company_name"]
        days_old = r.get("days_old", 0)
        revenue = r.get("revenue") or 0
        stock_cost = r.get("stock_cost") or 0
        wages = r.get("wages") or 0
        advertising = r.get("advertising") or 0
        profit = r.get("profit") or (revenue - stock_cost - wages - advertising)

        totals["revenue"] += revenue
        totals["stock_cost"] += stock_cost
        totals["wages"] += wages
        totals["advertising"] += advertising
        totals["profit"] += profit

        lines.append(
            f"{name:<{name_width}}  "
            f"{days_old:>{days_width}}  "
            f"{format_currency(revenue):>{num_width}}  "
            f"{format_currency(stock_cost):>{num_width}}  "
            f"{format_currency(wages):>{num_width}}  "
            f"{format_currency(advertising):>{num_width}}  "
            f"{format_currency(profit):>{num_width}}"
        )

    # Grand totals
    lines.append("")
    lines.append("=" * len(header))
    lines.append("GRAND TOTALS".center(len(header)))
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
            data = {"content": message or "📊 Daily company financials report attached."}
            response = requests.post(webhook_url, data=data, files=files, timeout=10)

        if response.status_code == 204:
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

    # Step 1: Get the latest capture_date
    try:
        latest_query = (
            supabase.table("company_financials")
            .select("capture_date")
            .order("capture_date", desc=True)
            .limit(1)
            .execute()
        )
        if not latest_query.data:
            print("⚠️ No financial records found.")
            return
        latest_date = latest_query.data[0]["capture_date"]
    except Exception as e:
        print(f"❌ Error fetching latest date: {e}")
        return

    # Step 2: Fetch all financials for that date
    try:
        financials_query = (
            supabase.table("company_financials")
            .select("id, company_id, capture_date, revenue, stock_cost, wages, advertising, profit")
            .eq("capture_date", latest_date)
            .order("company_id")
            .execute()
        )
        financials = financials_query.data
        if not financials:
            print(f"⚠️ No financial records found for {latest_date}")
            return
    except Exception as e:
        print(f"❌ Error fetching financials: {e}")
        return

    # Step 3: Fetch company names + days_old
    try:
        company_ids = [f["company_id"] for f in financials]
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

    # Step 4: Merge company info into financials
    for f in financials:
        c = companies.get(f["company_id"], {})
        f["company_name"] = c.get("company_name", f"Company {f['company_id']}")
        f["days_old"] = c.get("days_old", 0)

    # Step 5: Build report
    report_text = build_financials_report(financials, latest_date)
    save_report_to_file(report_text, REPORT_PATH)

    # Step 6: Send to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 Company Financials Report for {latest_date}"
    )

    print("✅ Daily company financials report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
