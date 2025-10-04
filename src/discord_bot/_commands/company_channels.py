# src/discord_bot/_commands/company_channels.py
import json
import requests
import boto3
from supabase import create_client, Client
from datetime import datetime, timezone

DISCORD_API_BASE = "https://discord.com/api/v10/webhooks"

def get_secrets():
    client = boto3.client("secretsmanager", region_name="ap-southeast-1")

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_APPLICATION_ID": discord_secret.get("DISCORD_APPLICATION_ID"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }

SECRETS = get_secrets()


def handle_link_company(msg: dict):
    """
    msg: the SQS message body dict created in app.py. Expected keys:
      - company_id
      - discord_channel_id
      - channel_name (optional)
      - payload (optional) -> full Discord interaction payload (recommended)
    This function upserts the mapping and sends a Discord follow-up using the interaction token
    (extracted from msg['payload']['token'] if present, otherwise msg['interaction_token']).
    """
    # try to extract payload and token
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else None
    interaction_token = None
    if payload:
        interaction_token = payload.get("token")
    if not interaction_token:
        # support explicit token if app.py included it separately
        interaction_token = msg.get("interaction_token") or msg.get("token")

    # company_id: prefer explicit field, fall back to payload options
    company_id = msg.get("company_id")
    if not company_id and payload:
        options = payload.get("data", {}).get("options", [])
        company_id = next((opt["value"] for opt in options if opt.get("name") in ("company", "company_id")), None)

    # channel id & name
    channel_id = msg.get("discord_channel_id") or (payload.get("channel_id") if payload else None) or (payload.get("channel", {}).get("id") if payload else None)
    channel_name = msg.get("channel_name") or (payload.get("channel", {}).get("name") if payload else None) or f"channel_{channel_id}"

    # basic validation
    if not company_id or not channel_id:
        err = f"Missing company_id or channel_id (company_id={company_id}, channel_id={channel_id})"
        print("❌", err)
        if interaction_token:
            send_followup(interaction_token, f"❌ {err}")
        return

    # Upsert into Supabase
    try:
        supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

        row = {
            "company_id": int(company_id),
            "channel_name": channel_name,
            "discord_channel_id": int(channel_id),
        }

        # on_conflict matches your UNIQUE(company_id, channel_name)
        supabase.table("discord_company_channels").upsert(row, on_conflict="company_id,channel_name").execute()

        success_msg = f"✅ Linked company `{company_id}` to channel <#{channel_id}>"
        print(success_msg)

        if interaction_token:
            send_followup(interaction_token, success_msg)
        else:
            # should not normally happen — prefer the token path
            print("No interaction token available; cannot send follow-up to Discord.")

    except Exception as e:
        err_msg = f"❌ Error linking company: {e}"
        print(err_msg)
        if interaction_token:
            send_followup(interaction_token, err_msg)


def send_followup(interaction_token: str, content: str):
    """
    Send a follow-up using the interaction token (webhook URL).
    """
    if not SECRETS.get("DISCORD_APPLICATION_ID"):
        print("DISCORD_APPLICATION_ID missing; cannot send follow-up.")
        return

    try:
        webhook_url = f"{DISCORD_API_BASE}/{SECRETS['DISCORD_APPLICATION_ID']}/{interaction_token}"
        r = requests.post(webhook_url, json={"content": content}, timeout=5)
        print("Follow-up message sent:", r.status_code, r.content)
    except Exception as e:
        print("Error sending follow-up to Discord:", e)
