import re
import requests
import json
import boto3
from datetime import datetime, timezone
from supabase import create_client, Client

DISCORD_API_BASE = "https://discord.com/api/v10/interactions"

def get_supabase_key():
    # --- Load Supabase secrets from AWS Secrets Manager ---
    SECRET_NAME = "supabase_keys"
    REGION_NAME = "ap-southeast-1"

    client = boto3.client("secretsmanager", region_name=REGION_NAME)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])

    SUPABASE_URL = secret["SUPABASE_URL"]
    SUPABASE_KEY = secret["SUPABASE_KEY"]

    return {"SUPABASE_URL": SUPABASE_URL, "SUPABASE_KEY": SUPABASE_KEY}


def handle_register(payload):
    """
    Handles /register command using the synchronous deferred response pattern.
    Returns a deferred response immediately and posts the final message after processing.
    """

    # --- Extract API key and Discord user info ---
    api_key = payload["data"]["options"][0]["value"]
    user_nick = payload["member"].get("nick") or payload["member"]["user"]["username"]

    # Extract Torn user ID from the discord username
    match = re.search(r"\[(\d+)\]", user_nick)
    torn_user_id = int(match.group(1)) if match else None

    interaction_id = payload["id"]
    interaction_token = payload["token"]

    # --- Step 1: Immediately defer response ---
    defer_response = {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    # --- Step 2: Process the command ---
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
            timeout=5
        )
        print("Callback status:", r.status_code)
        print("Callback response:", r.text)
    except Exception as e:
        print("Error sending callback to Discord:", e)

    # --- Step 4: Return deferred response immediately ---
    return defer_response


def _process_register(torn_api_key, torn_user_id):
    """
    Validates the API key against Torn API and prepares a concise response message.
    """
    API_URL = f"https://api.torn.com/company/?selections=profile&key={torn_api_key}"
    now = datetime.now(timezone.utc).isoformat()    
    
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()

        # --- Check if Torn returned an error because of a bad api key ---
        if "error" in data:
            return f"Invalid API key provided.  Please check and retry."
        
        # --- Initialize Supabase client ---
        supabase_keys = get_supabase_key()
        supabase: Client = create_client(supabase_keys['SUPABASE_URL'], supabase_keys['SUPABASE_KEY'])

        # --- No error, extract values ---
        director_id = data.get("company", {}).get("director")
        director_name = data.get("company", {}).get("employees", {}).get(str(director_id), {}).get("name", {})
        company_id = data.get("company", {}).get("ID")
        
        # --- Construct directors record ---
        director_data = {
            "torn_user_id": torn_user_id,
            "director_name": director_name,
            "company_id": company_id,
            "api_key": torn_api_key,
            "updated_at": now
        }

        
        # Needs to flip to ==
        if director_id != torn_user_id:

            director_response = supabase.table("directors").upsert(
                director_data, on_conflict="torn_user_id"
            ).execute()
            print("Directors upsert:", director_response)

            # torn_user_id BIGINT PRIMARY KEY,
            # director_name TEXT NOT NULL,
            # company_id BIGINT,
            # api_key TEXT,
            # equity NUMERIC,
            # voting_pct NUMERIC,
            # created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            # updated_at TIMESTAMP WITH TIME ZONE
            return f"Company director: {director_data}"
        
        
        
        else:

            # If someone is using a directors API key or they are not actually a directors, reject
            return f"You are not a company director"

    except Exception as e:
        return f"Exception validating API key: {e}"

