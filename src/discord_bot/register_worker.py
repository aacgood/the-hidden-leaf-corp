# src/discord_bot/register_worker.py
import json
import re
import requests
import boto3
from datetime import datetime, timezone
from supabase import create_client, Client

DISCORD_API_BASE = "https://discord.com/api/v10/webhooks"  # follow-up endpoint
SECRET_NAME = "torn_director_api_keys"
REGION = "ap-southeast-1"

def get_secrets():
    """
    Load both Discord and Supabase secrets from AWS Secrets Manager
    """
    client = boto3.client("secretsmanager", region_name="ap-southeast-1")

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_PUBLIC_KEY": discord_secret.get("DISCORD_PUBLIC_KEY"),
        "DISCORD_APPLICATION_ID": discord_secret.get("DISCORD_APPLICATION_ID"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }

SECRETS = get_secrets()


def upsert_director_api_key(director_name: str, director_id: int, api_key: str) -> str:
    """
    Create or update a director's API key inside the shared JSON secret.
    - Creates the secret if it doesn't exist.
    - Updates only the calling director's entry if it does.
    - Keeps other directors' keys intact.
    Returns the key reference string stored in Supabase.
    """
    client = boto3.client("secretsmanager", region_name=REGION)
    key_ref = f"{director_name}_{director_id}"

    try:
        # Load existing JSON from the secret
        secret_value = client.get_secret_value(SecretId=SECRET_NAME)
        secret_dict = json.loads(secret_value["SecretString"])
    except client.exceptions.ResourceNotFoundException:
        # Secret does not exist yet → create from scratch
        secret_dict = {}

    # Upsert this director's entry
    secret_dict[key_ref] = api_key
    secret_string = json.dumps(secret_dict)

    try:
        # Create fresh if missing
        client.create_secret(
            Name=SECRET_NAME,
            SecretString=secret_string,
            Description="Torn director API keys",
            AddReplicaRegions=[{"Region": "ap-southeast-2"}],
        )
        print(f"Secret {SECRET_NAME} created with {key_ref}")
    except client.exceptions.ResourceExistsException:
        # Update if it already exists
        client.update_secret(
            SecretId=SECRET_NAME,
            SecretString=secret_string,
        )
        print(f"Secret {SECRET_NAME} updated with {key_ref}")

    return key_ref



def process_register(payload):
    """
    Performs Torn API lookup, Supabase upsert, and sends final Discord follow-up message
    """

    api_key = payload["data"]["options"][0]["value"]
    user_nick = payload["member"].get("nick") #or payload["member"]["user"]["username"]
    interaction_token = payload["token"]

    # Extract Torn user ID
    match = re.search(r"\[(\d+)\]", user_nick)
    torn_user_id = int(match.group(1)) if match else None

    content = ""
    try:
        # --- Call Torn API ---
        response = requests.get(
            f"https://api.torn.com/company/?selections=profile&key={api_key}",
            timeout=5
        )
        data = response.json()
        if "error" in data:
            content = "Invalid API key provided. Please check and retry."
        else:
            director_id = data.get("company", {}).get("director")
            director_name = data.get("company", {}).get("employees", {}).get(str(director_id), {}).get("name")
            company_id = data.get("company", {}).get("ID")

            # Write the directors API Key to AWS Secrets Manager
            key_ref = upsert_director_api_key(
            director_name=director_name,
            director_id=director_id,
            api_key=api_key
            )

            # --- Initialize Supabase client ---
            supabase: Client = create_client(SECRETS['SUPABASE_URL'], SECRETS['SUPABASE_KEY'])
            director_data = {
                "torn_user_id": torn_user_id,
                "director_name": director_name,
                "company_id": company_id,
                "api_key": key_ref,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            # THIS NEEDS TO BE FLIPPED TO == WHEN READY
            if director_id == torn_user_id:
                supabase.table("directors").upsert(director_data, on_conflict="torn_user_id").execute()
                content = f"Company director: {director_data}"
            else:
                content = "You are not a company director"

    except Exception as e:
        content = f"Exception validating API key: {e}"

    # --- Send final follow-up message to Discord ---
    if SECRETS["DISCORD_APPLICATION_ID"]:
        webhook_url = f"{DISCORD_API_BASE}/{SECRETS['DISCORD_APPLICATION_ID']}/{interaction_token}"
        try:
            r = requests.post(webhook_url, json={"content": content}, timeout=5)
            print("Follow-up message sent:", r.status_code, r.content)
        except Exception as e:
            print("Error sending follow-up to Discord:", e)
    else:
        print("DISCORD_APPLICATION_ID missing, cannot send follow-up")
