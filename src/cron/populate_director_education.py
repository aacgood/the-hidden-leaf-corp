import json
import boto3
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

REGION = "ap-southeast-1"
TARGET_COURSES = [1,2,3,4,5,6,7,8,9,10,11,12,13,22,28,88,100]

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

def process_director_education_raw(supabase: Client, torn_user_id: int, completed_courses: list[int]):
    now = datetime.utcnow().isoformat()
    
    # Build all records for bulk upsert
    records = [
        {
            "torn_user_id": torn_user_id,
            "course_id": course_id,
            "completed": True,
            "updated_at": now
        }
        for course_id in completed_courses
        if course_id in TARGET_COURSES
    ]
    
    if not records:
        return
    
    try:
        supabase.table("director_education").upsert(
            records,
            on_conflict="torn_user_id,course_id"
        ).execute()
    except Exception as e:
        print(f"Error upserting courses for user {torn_user_id}: {e}")

def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    try:
        directors = supabase.table("directors").select("*").execute().data
    except Exception as e:
        send_discord_message(f"[Director Education] Error fetching directors: {e}")
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

        headers = {"Content-Type": "application/json", "Authorization": f"ApiKey {api_key}"}
        try:
            resp = requests.get("https://api.torn.com/v2/user/education", headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            completed_courses = data.get("education", {}).get("complete", [])

            process_director_education_raw(supabase, director["torn_user_id"], completed_courses)
            send_discord_message(f"[Director Education] Processed for {director.get('director_name')} ({director.get('torn_user_id')})")

        except Exception as e:
            print(f"Error fetching education for {director.get('torn_user_id')}: {e}")
            send_discord_message(f"[Director Education] Error fetching education for {director.get('director_name')}: {e}")

    print(f"Cron job completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Cron job executed successfully"}
