import json
import boto3
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

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

def get_director_api_key(key_ref: str) -> str | None:
    client = boto3.client("secretsmanager", region_name=REGION)
    try:
        secret_value = client.get_secret_value(SecretId="torn_director_api_keys")
        secret_dict = json.loads(secret_value["SecretString"])
    except Exception as e:
        print(f"Error retrieving Torn API keys: {e}")
        return None

    api_key = secret_dict.get(key_ref)
    if not api_key:
        print(f"Torn API key for {key_ref} not found")
    return api_key

def send_discord_message(message: str):
    webhook_url = SECRETS["DISCORD_WEBHOOK_CHANNEL_THLC_BOT"]
    if not webhook_url:
        print("Discord webhook missing")
        return
    try:
        r = requests.post(webhook_url, json={"content": message}, timeout=5)
        print(f"Discord message sent: {r.status_code}")
    except Exception as e:
        print(f"Error sending Discord message: {e}")

def process_company_stock(supabase, company_id: int, company_stock: dict, snapshot_date):
    """
    Inserts or updates company stock snapshot for the given company_id.
    Calculates estimated_remaining_days in Python before upsert.
    """
    rows_to_insert = []

    for item_name, stock_info in company_stock.items():
        in_stock = stock_info.get("in_stock", 0)
        sold_amount = stock_info.get("sold_amount", 0)

        # Calculate estimated_remaining_days (round down, None if sold_amount is 0)
        if sold_amount > 0:
            estimated_days = in_stock // sold_amount  # integer division
        else:
            estimated_days = None

        rows_to_insert.append({
            "company_id": company_id,
            "item_name": item_name,
            "snapshot_date": str(snapshot_date),
            "cost": stock_info.get("cost", 0),
            "rrp": stock_info.get("rrp", 0),
            "price": stock_info.get("price", 0),
            "in_stock": in_stock,
            "on_order": stock_info.get("on_order", 0),
            "sold_amount": sold_amount,
            "sold_worth": stock_info.get("sold_worth", 0),
            "estimated_remaining_days": estimated_days,
        })

    if not rows_to_insert:
        print(f"[Stock] No valid rows to insert for company_id={company_id}")
        return

    try:
        supabase.table("company_stock_daily").upsert(
            rows_to_insert,
            on_conflict="company_id,item_name,snapshot_date"
        ).execute()

        print(f"[Stock] Inserted {len(rows_to_insert)} records for company_id={company_id}")

    except Exception as e:
        print(f"[Stock] ❌ Error inserting stock records for company_id={company_id}: {e}")

def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])
    utc_today = datetime.now(timezone.utc).date()

    try:
        directors = supabase.table("directors").select("*").execute().data
    except Exception as e:
        send_discord_message(f"[Employees] Error fetching directors: {e}")
        return {"statusCode": 500, "body": "Failed to fetch directors"}

    for director in directors:
        key_ref = director.get("api_key")
        company_id = director.get("company_id")
        
        if not key_ref:
            print(f"No key_ref for director {director.get('torn_user_id')}")
            continue

        api_key = get_director_api_key(key_ref)
        if not api_key:
            print(f"No Torn API key for {key_ref}")
            continue

        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.get(
                f"https://api.torn.com/company/?selections=stock&key={api_key}",
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            print(data)
            company_stock = data.get("company_stock", {})

            if not company_stock:
                print(f"[Stock] No stock data for company_id={company_id}")
                continue

            process_company_stock(supabase, company_id, company_stock, utc_today)

            send_discord_message(f"[Stock] Processed for {director.get('director_name')} ({director.get('torn_user_id')})")

        except Exception as e:
            print(f"Error fetching stock for {director.get('torn_user_id')}: {e}")
            send_discord_message(f"[Stock] Error fetching stock for {director.get('director_name')}: {e}")

    print(f"Cron job completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Cron job executed successfully"}
