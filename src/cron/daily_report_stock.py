import json
import re
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
    """Send a message to a Discord webhook."""
    if not webhook_url:
        print("Discord webhook missing")
        return
    try:
        resp = requests.post(webhook_url, json={"content": message}, timeout=10)
        print(f"Message sent: {resp.status_code}")
    except Exception as e:
        print(f"Error sending message: {e}")


def escape_discord_markdown(text: str) -> str:
    """Escape common Discord markdown characters."""
    if not text:
        return ""
    return re.sub(r'([_*~`>])', r'\\\1', str(text))


def format_generated_timestamp() -> str:
    """Return a UTC (TCT) timestamp string."""
    dt = datetime.now(timezone.utc)
    s = dt.strftime("%B %d, %Y %H:%M TCT")
    return s


def build_stock_report(rows: list[dict], max_stock: int) -> str:
    """
    Build a Discord-ready stock report table.
    """
    if not rows:
        return "📦 Stock Report: No data available for today."

    normalized = []
    for r in rows:
        normalized.append({
            "name": escape_discord_markdown(r.get("item_name") or ""),
            "in_stock": int(r.get("in_stock") or 0),
            "on_order": int(r.get("on_order") or 0),
            "sold_amount": int(r.get("sold_amount") or 0),
            "est_days_remain": int(r["estimated_remaining_days"]) if r.get("estimated_remaining_days") is not None else None
        })

    total_sold = sum(r["sold_amount"] for r in normalized)
    normalized.sort(key=lambda x: (x["est_days_remain"] is None, x["est_days_remain"] or 999999))

    gen_ts = format_generated_timestamp()
    header = f"📦 Stock Report (Generated {gen_ts})\n"

    total_in_stock = 0
    total_on_order = 0

    # Prepare table header
    table_lines = []
    table_lines.append("```")
    table_lines.append(f"{' '} {'Item Name':<18} {'InStock':>6} {'Sold':>6} {'OnOrd':>6} {'Days':>6} {'Optimal':>8}")
    table_lines.append("──────────────────────────────────────────────────────────")

    for r in normalized:
        name = r["name"]
        in_stock = r["in_stock"]
        on_order = r["on_order"]
        sold_amount = r["sold_amount"]
        days = r["est_days_remain"]
        total_in_stock += in_stock
        total_on_order += on_order

        daily_sales_pct = (sold_amount / total_sold) if total_sold > 0 else 0
        optimal = round(daily_sales_pct * max_stock)

        # Icon logic
        icon = "✅"
        if (days is not None) and (days <= 7):
            icon = "‼️"
        elif optimal > 0 and in_stock < optimal * 0.3:
            icon = "🚨"
        elif optimal > 0 and in_stock < optimal * 0.6:
            icon = "⚠️"

        days_display = f"{days}d" if days is not None else "-"
        table_lines.append(f"{icon} {name:<18} {in_stock:>6} {sold_amount:>6} {on_order:>6} {days_display:>6} {optimal:>8}")

    available_to_order = max_stock - (total_in_stock + total_on_order)
    if available_to_order < 0:
        available_to_order = 0

    table_lines.append("```")
    table_lines.append(f"\n📦 There are {available_to_order} items available to order (of {max_stock:,} total capacity).")

    return header + "\n".join(table_lines)


def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"Error fetching discord channels: {e}")
        return

    utc_today = datetime.now(timezone.utc).date().isoformat()

    for ch in channels:
        company_id = ch.get("company_id")
        discord_webhook_url = ch.get("discord_webhook_url")
        company_name = ch.get("company_name") or f"Company {company_id}"

        if not discord_webhook_url:
            print(f"No webhook for company {company_id}, skipping")
            continue

        # Fetch the company's current storage capacity (max_stock)
        try:
            company_info = (
                supabase.table("company")
                .select("storage_space")
                .eq("company_id", company_id)
                .single()
                .execute()
                .data
            )
            max_stock = int(company_info.get("storage_space", 100000)) if company_info else 100000
        except Exception as e:
            print(f"Error fetching storage_space for company {company_id}: {e}")
            max_stock = 100000

        try:
            rows = supabase.table("company_stock_daily").select(
                "item_name,in_stock,on_order,sold_amount,estimated_remaining_days"
            ).eq("company_id", company_id).eq("snapshot_date", utc_today).execute().data
        except Exception as e:
            print(f"Error fetching stock for company {company_id}: {e}")
            continue

        if not rows:
            print(f"No stock rows for company {company_id} on {utc_today}, skipping")
            continue

        message = build_stock_report(rows, max_stock)
        full_message = f"{message}"

        send_discord_message(discord_webhook_url, full_message)
        print(f"Sent stock report for company {company_name} (max_stock={max_stock})")

    print("Daily stock report job completed.")


if __name__ == "__main__":
    lambda_handler()
