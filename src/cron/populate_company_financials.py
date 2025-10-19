import json
import boto3
import requests
import re
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
    #webhook_url = SECRETS["DISCORD_WEBHOOK_CHANNEL_THLC_BOT"]
    
    # leave this for testing please
    webhook_url = "https://discord.com/api/webhooks/1425300955481636977/jHhYH1mJTjaYQX9H4hUcq-dwWFrDoWPIwLWjXLMpqhc4xZXKsa3Xurj5SJ999Y9wHuWY"

    if not webhook_url:
        print("Discord webhook missing")
        return
    try:
        r = requests.post(webhook_url, json={"content": message}, timeout=5)
        print(f"Discord message sent: {r.status_code}")
    except Exception as e:
        print(f"Error sending Discord message: {e}")


def process_company_financials(supabase: Client, director_torn_id: int, company_id, stock: dict, company_details: dict, employees: dict, news: dict):
    """
    Calculate daily company financials and upsert into Supabase table `company_financials`.
    """

    # --- Revenue from newsfeed ---
    revenue = 0
    if news:
        for entry in news.values():
            news_text = entry.get("news", "")
            match = re.search(r"gross income of \$([\d,\.]+)", news_text)
            if match:
                try:
                    revenue_str = match.group(1)
                    revenue = int(revenue_str.replace(",", "").replace(".", ""))
                    break
                except Exception as e:
                    print(f"[Company Financials] Failed to parse revenue: {e}")

    # --- Stock cost (on_order * cost) ---
    stock_cost = 0
    for item in stock.values():
        cost = item.get("cost", 0)
        on_order = item.get("on_order", 0)
        stock_cost += cost * on_order

    # --- Wages ---
    total_wages = 0
    for emp in employees.values():
        total_wages += emp.get("wage", 0)

    # --- Advertising budget ---
    advertising = company_details.get("advertising_budget", 0)

    # --- Prepare record for upsert (omit profit column, it's generated) ---
    today_str = datetime.now(timezone.utc).date().isoformat()
    record = {
        "company_id": company_id,
        "capture_date": today_str,
        "revenue": revenue,
        "stock_cost": stock_cost,
        "wages": total_wages,
        "advertising": advertising,
    }

    # --- Upsert into Supabase ---
    try:
        resp = supabase.table("company_financials").upsert(
            record, on_conflict="company_id,capture_date"
        ).execute()
        resp_dict = resp.__dict__
        if resp_dict.get("error"):
            print(f"[Company Financials] Error upserting record: {resp_dict['error']}")
        else:
            print(f"[Company Financials] Successfully upserted financials for company {company_id} on {today_str}")
    except Exception as e:
        print(f"[Company Financials] Exception during upsert: {e}")


def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    try:
        directors = supabase.table("directors").select("*").eq("prospective", False).execute().data
    except Exception as e:
        send_discord_message(f"[Company Financials] Error fetching directors: {e}")
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
            resp = requests.get(f"https://api.torn.com/company/?selections=stock,detailed,employees,news&key={api_key}", headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            stock = data.get("company_stock", {})
            company_details= data.get("company_detailed", {})
            employees = data.get("company_employees", {})
            news = data.get("news")

            process_company_financials(supabase, director["torn_user_id"], company_id, stock, company_details, employees, news)
            send_discord_message(f"[Company Financials] Processed for {director.get('director_name')} ({director.get('torn_user_id')})")

        except Exception as e:
            print(f"Error fetching employees for {director.get('torn_user_id')}: {e}")
            send_discord_message(f"[Company Financials] Error fetching education for {director.get('director_name')}: {e}")

    print(f"Cron job completed at {datetime.now(timezone.utc).isoformat()}")
    return {"statusCode": 200, "body": "Cron job executed successfully"}