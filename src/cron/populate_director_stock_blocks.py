import json
import boto3
import requests
from utils.secrets import get_secrets  # type: ignore
from datetime import datetime, timezone
from supabase import create_client, Client

REGION = "ap-southeast-1"
TARGET_STOCKS = [3,8,11,13,23,25]

# Fetch shared secrets once
SECRETS = get_secrets(["discord_keys", "supabase_keys"])
DISCORD_WEBHOOK_CHANNEL_THLC_BOT = SECRETS.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT") 
SUPABASE_URL = SECRETS.get("SUPABASE_URL") 
SUPABASE_KEY = SECRETS.get("SUPABASE_KEY")

# def get_secrets():
#     client = boto3.client("secretsmanager", region_name=REGION)

#     discord_secret = json.loads(
#         client.get_secret_value(SecretId="discord_keys")["SecretString"]
#     )
#     supabase_secret = json.loads(
#         client.get_secret_value(SecretId="supabase_keys")["SecretString"]
#     )

#     return {
#         "DISCORD_WEBHOOK_CHANNEL_THLC_BOT": discord_secret.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT"),
#         "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
#         "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
#     }

# SECRETS = get_secrets()

def get_director_api_key(key_ref: str) -> str | None:
    """
    Fetch a single director API key using the shared get_secrets() function.
    Keeps the code simple by fetching only the 'torn_director_api_keys' secret
    each time this function is called.
    """
    secrets = get_secrets(["torn_director_api_keys"])
    api_key = secrets.get(key_ref)
    if not api_key:
        print(f"Torn API key for {key_ref} not found")
    return api_key

def send_discord_message(message: str):
    webhook_url = DISCORD_WEBHOOK_CHANNEL_THLC_BOT
    if not webhook_url:
        print("Discord webhook missing")
        return
    try:
        r = requests.post(webhook_url, json={"content": message}, timeout=5)
        print(f"Discord message sent: {r.status_code}")
    except Exception as e:
        print(f"Error sending Discord message: {e}")

def process_director_stock_blocks_raw(supabase: Client, torn_user_id: int, stock_blocks: dict):
    now = datetime.utcnow().isoformat()

    # Build all records for bulk upsert
    records = []
    for sid, details in stock_blocks.items():
        stock_id = int(sid)
        if stock_id not in TARGET_STOCKS:
            continue

        shares_held = details.get("total_shares", 0)
        benefit = details.get("benefit", {})
        has_block = benefit.get("ready", 0) >= 1

        records.append(
            {
                "torn_user_id": torn_user_id,
                "stock_id": stock_id,
                "shares_held": shares_held,
                "has_block": has_block,
                "updated_at": now,
            }
        )

    if not records:
        return

    try:
        supabase.table("director_stock_blocks").upsert(
            records,
            on_conflict="torn_user_id,stock_id",
        ).execute()
    except Exception as e:
        print(f"Error upserting stock blocks for user {torn_user_id}: {e}")


def lambda_handler(event, context):
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        # This will also get prospective directors
        directors = supabase.table("directors").select("*").execute().data
    except Exception as e:
        send_discord_message(f"[Director Stock Blocks] Error fetching directors: {e}")
        return {"statusCode": 500, "body": "Failed to fetch directors"}

    for director in directors:
        key_ref = director.get("api_key")
        if not key_ref:
            print(f"No key_ref for director {director.get('torn_user_id')}")
            continue

        api_key = get_director_api_key(key_ref)
        if not api_key:
            print(f"No Torn API key for {key_ref}")
            continue

        try:
            resp = requests.get(f"https://api.torn.com/user/?selections=stocks&key={api_key}", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            stock_blocks = data.get("stocks", {})

            filtered_stock_blocks = {
                sid: details
                for sid, details in stock_blocks.items()
                if int(sid) in TARGET_STOCKS
            }

            process_director_stock_blocks_raw(supabase, director["torn_user_id"], filtered_stock_blocks)
            send_discord_message(f"[Director Stock Blocks] Processed for {director.get('director_name')} ({director.get('torn_user_id')})")

        except Exception as e:
            print(f"Error fetching education for {director.get('torn_user_id')}: {e}")
            send_discord_message(f"[Director Stock Blocks] Error fetching education for {director.get('director_name')}: {e}")

    print(f"Cron job completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Cron job executed successfully"}
