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

def process_company(supabase: Client, director: dict, company: dict, company_details: dict):
    company_id = company.get("ID")
    if not company_id:
        print(f"[Company] Missing ID for director {director.get('torn_user_id')}")
        return None

    record = {
        "company_id": company_id,
        "rating": company.get("rating"),
        "torn_user_id": director["torn_user_id"],
        "company_name": company.get("name"),
        "company_type": company.get("company_type"),
        "popularity": company_details.get("popularity"),
        "efficiency": company_details.get("efficiency"),
        "environment": company_details.get("environment"),
        "employees_hired": company.get("employees_hired"),
        "employees_capacity": company.get("employees_capacity"),
        "storage_space": company_details.get("upgrades", {}).get("storage_space"),
        "value": company_details.get("value"),
        "days_old": company.get("days_old"),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    try:
        supabase.table("company").upsert(record, on_conflict="company_id").execute()
        print(f"[Company] Upserted company {company_id} ({record['company_name']})")
        return True
    except Exception as e:
        print(f"[Company] Error upserting company {company_id}: {e}")
        return False

def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    success_list = []
    fail_list = []

    try:
        directors = supabase.table("directors").select("*").execute().data
    except Exception as e:
        send_discord_message(f"[Company] ❌ Error fetching directors: {e}")
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
            resp = requests.get(
                f"https://api.torn.com/company/?selections=detailed,profile&key={api_key}",
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            #print(data)

            company = data.get("company", {})
            company_details = data.get("company_detailed", {})

            if company and company_details:
                ok = process_company(supabase, director, company, company_details)
                if ok:
                    success_list.append(f"{company.get('name')} ({director.get('torn_user_id')})")
                else:
                    fail_list.append(f"{company.get('name')} ({director.get('torn_user_id')})")
            else:
                fail_list.append(f"{director.get('torn_user_id')} (no company data)")
        except Exception as e:
            print(f"Error fetching company for {director.get('torn_user_id')}: {e}")
            fail_list.append(f"{director.get('torn_user_id')} (API error)")

    # Summary message
    summary = "**[Company Cron Summary]**\n"
    summary += f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    summary += f"✅ Updated: {len(success_list)}\n❌ Failed: {len(fail_list)}\n\n"

    if success_list:
        summary += "**Success:**\n" + "\n".join(success_list[:10])
        if len(success_list) > 10:
            summary += f"\n(+{len(success_list)-10} more)"
        summary += "\n\n"

    if fail_list:
        summary += "**Failed:**\n" + "\n".join(fail_list[:10])
        if len(fail_list) > 10:
            summary += f"\n(+{len(fail_list)-10} more)"

    send_discord_message(summary)

    print(f"[Company Cron] Completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Company cron executed successfully"}
