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

def calculate_allowable_addiction(merits: int) -> int:
    base_limit = -6
    raw_limit = base_limit - merits
    # cap at -10
    allowable = max(raw_limit, -10)
    return allowable

def process_employees(supabase: Client, director_torn_id: int, company_id, employees: dict):
  
    # Delete existing entries for the company_id as this is a state table not a historical one.
    supabase.table("employees").delete().eq("company_id", company_id).execute()

    # Insert employees found for the director
    records = []
    
    for emp_id, emp in employees.items():
        records.append({
            "torn_user_id": int(emp_id),
            "employee_name": emp.get("name", ""),
            "company_id": company_id,
            "position": emp.get("position", ""),
            "days_in_company": emp.get("days_in_company", 0),
            "wage": emp.get("wage", 0),
            "manual_labor": emp.get("manual_labor", 0),
            "intelligence": emp.get("intelligence", 0),
            "endurance": emp.get("endurance", 0),
            "effectiveness_total": emp["effectiveness"].get("total", 0),
            "working_stats": emp["effectiveness"].get("working_stats", 0),
            "settled_in": emp["effectiveness"].get("settled_in", 0),
            "merits": emp["effectiveness"].get("merits", 0),
            "director_education": emp["effectiveness"].get("director_education", 0),
            "management": emp["effectiveness"].get("management", 0),
            "addiction": emp["effectiveness"].get("addiction", 0),
            "inactivity": emp["effectiveness"].get("inactivity", 0),
            "allowable_addiction": calculate_allowable_addiction(emp["effectiveness"].get("merits", 0))
        })


    if records:
        resp = supabase.table("employees").insert(records).execute()
        # Proper error handling for latest Supabase client
        try:
            resp_dict = resp.__dict__  # inspect underlying dict
            if resp_dict.get("error"):
                print(f"[Employees] Error inserting employees: {resp_dict['error']}")
            else:
                print(f"[Employees] Inserted {len(records)} employees successfully")
        except Exception as e:
            print(f"[Employees] Unexpected response structure: {resp}, error: {e}")
    else:
        print("[Employees] No employee records to insert")


def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    try:
        directors = supabase.table("directors").select("*").eq("prospective", False).execute().data
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
            resp = requests.get(f"https://api.torn.com/company/?selections=employees&key={api_key}", headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            employees = data.get("company_employees", {})

            process_employees(supabase, director["torn_user_id"], company_id, employees)
            send_discord_message(f"[Employees] Processed for {director.get('director_name')} ({director.get('torn_user_id')})")

        except Exception as e:
            print(f"Error fetching employees for {director.get('torn_user_id')}: {e}")
            send_discord_message(f"[Employees] Error fetching education for {director.get('director_name')}: {e}")

    print(f"Cron job completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Cron job executed successfully"}