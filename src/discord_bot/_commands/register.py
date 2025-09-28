import re
import requests
import json
import boto3
from datetime import datetime, timezone
from supabase import create_client, Client

DISCORD_API_BASE = "https://discord.com/api/v10/interactions"

def load_supabase_keys():
    SECRET_NAME = "supabase_keys"
    REGION_NAME = "ap-southeast-1"

    client = boto3.client("secretsmanager", region_name=REGION_NAME)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])

    return {
        "SUPABASE_URL": secret["SUPABASE_URL"],
        "SUPABASE_KEY": secret["SUPABASE_KEY"]
    }

def handle_register(payload):
    """
    Handles /register command using the synchronous deferred response pattern.
    Immediately returns defer response, then processes and sends follow-up.
    """

    # --- Step 1: Immediately defer response ---
    defer_response = {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    # --- Extract API key and Discord user info ---
    api_key = payload["data"]["options"][0]["value"]
    user_nick = payload["member"].get("nick") or payload["member"]["user"]["username"]
    match = re.search(r"\[(\d+)\]", user_nick)
    torn_user_id = int(match.group(1)) if match else None

    interaction_id = payload["id"]
    interaction_token = payload["token"]

    # --- Step 2: Process registration synchronously ---
    content = _process_register(api_key, torn_user_id)

    # --- Step 3: Send the final message back to Discord ---
    callback_url = f"{DISCORD_API_BASE}/{interaction_id}/{interaction_token}/callback"
    try:
        r = requests.post(
            callback_url,
            json={
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {"content": content}
            },
            timeout=10  # ensure enough time for Torn API + Supabase
        )
        print("Deferred message updated:", r.status_code, r.content)
    except Exception as e:
        print("Error sending callback to Discord:", e)

    # --- Step 4: Return deferred response immediately ---
    return defer_response

def _process_register(torn_api_key, torn_user_id):
    """
    Validates the API key against Torn API and updates Supabase.
    """
    API_URL = f"https://api.torn.com/company/?selections=profile&key={torn_api_key}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()

        if "error" in data:
            return "Invalid API key provided. Please check and retry."

        # --- Initialize Supabase client ---
        supabase_keys = load_supabase_keys()
        supabase: Client = create_client(supabase_keys['SUPABASE_URL'], supabase_keys['SUPABASE_KEY'])

        # --- Extract director info ---
        director_id = data.get("company", {}).get("director")
        director_name = data.get("company", {}).get("employees", {}).get(str(director_id), {}).get("name", {})
        company_id = data.get("company", {}).get("ID")

        director_data = {
            "torn_user_id": torn_user_id,
            "director_name": director_name,
            "company_id": company_id,
            "api_key": torn_api_key,
            "updated_at": now
        }

        if director_id != torn_user_id:
            director_response = supabase.table("directors").upsert(
                director_data, on_conflict="torn_user_id"
            ).execute()
            print("Directors upsert:", director_response)

            return f"Company director: {director_data}"

        else:
            return "You are not a company director"

    except Exception as e:
        return f"Exception validating API key: {e}"
