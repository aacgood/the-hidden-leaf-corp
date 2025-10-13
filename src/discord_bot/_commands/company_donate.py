# src/discord_bot/_commands/company_donate.py
import json
import re
import boto3
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# --- Secrets ---
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
supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])


def handle_company_donate(msg):
    """
    Process /company donate slash command
    """
    payload = msg["payload"]
    user_nick = payload["member"].get("nick")

    # Extract Torn user ID from nick, e.g. "pzero [3694180]"
    match = re.search(r"\[(\d+)\]", user_nick or "")
    torn_user_id = int(match.group(1)) if match else None
    if not torn_user_id:
        return send_followup(payload, f"⚠️ Could not extract Torn user ID from `{user_nick}`")

    # Extract command options
    options = payload.get("data", {}).get("options", [])
    acronym = next((opt["value"].upper() for opt in options if opt["name"] == "acronym"), None)
    amount = next((opt["value"] for opt in options if opt["name"] == "amount"), None)
    note = next((opt["value"] for opt in options if opt["name"] == "note"), None)

    print(f"[INFO] {user_nick} ({torn_user_id}) donating {amount} to {acronym} under note '{note}'")

    # Lookup company by acronym
    try:
        company_resp = (
            supabase.table("company")
            .select("*")
            .eq("company_acronym", acronym)
            .single()
            .execute()
        )
    except Exception as e:
        return send_followup(payload, f"⚠️ Failed to query company info: {e}")

    if not company_resp.data:
        return send_followup(payload, f"🚫 Company with acronym `{acronym}` not found.")

    company = company_resp.data
    company_id = company["company_id"]
    company_name = company["company_name"]

    timestamp = datetime.now(timezone.utc).isoformat()

    # 1️⃣ Insert or upsert into company_donations
    donation_payload = {
        "company_id": company_id,
        "donator_id": torn_user_id,
        "donator_name": user_nick,
        "created_at": timestamp
    }
    print("[DEBUG] Upserting company_donations:", donation_payload)

    donation_resp = supabase.table("company_donations") \
        .upsert(donation_payload, on_conflict="company_id,donator_id") \
        .execute()
    print("[DEBUG] donation_resp:", donation_resp)

    if not donation_resp.data:
        print(f"[ERROR] Failed to upsert company_donations: {donation_resp}")
        return send_followup(payload, "⚠️ Failed to record donation master entry.")

    donation_id = donation_resp.data[0]["id"]

    # 2️⃣ Insert transaction - Donator to Director is instantly confirmed
    transaction_payload = {
        "donation_id": donation_id,
        "transaction_type": "donation",
        "amount": int(amount),
        "notes": note,
        "initiated_by": str(torn_user_id),
        "status": "confirmed",
        "recorded_at": timestamp
    }
    print("[DEBUG] Inserting company_donation_transactions:", transaction_payload)

    txn_resp = supabase.table("company_donation_transactions").insert(transaction_payload).execute()
    print("[DEBUG] txn_resp:", txn_resp)

    if not txn_resp.data:
        print(f"[ERROR] Failed to insert company_donation_transactions: {txn_resp}")
        return send_followup(payload, "⚠️ Failed to record donation transaction.")

    transaction_id = txn_resp.data[0]["id"]

    # 3️⃣ Send follow-up message to Discord by editing the original deferred response
    msg_content = f"✅ Donation of **${amount}** recorded for **{acronym} ({company_name})** under note *{note}*."
    discord_msg_id = send_followup(payload, msg_content, edit_original=False)

    # 4️⃣ Update transaction row with Discord message ID
    if discord_msg_id:
        supabase.table("company_donation_transactions").update(
            {"discord_message_id": discord_msg_id}
        ).eq("id", transaction_id).execute()

    return discord_msg_id


def send_followup(payload, content: str, edit_original: bool = True) -> str | None:
    """
    Send a message to Discord after deferred interaction.

    - edit_original=True: edits the original deferred response (PATCH @original)
    - edit_original=False: sends a true follow-up (POST to webhook)
    Returns the Discord message ID if successful.
    """
    token = payload.get("token")
    app_id = SECRETS["DISCORD_APPLICATION_ID"]

    if edit_original:
        url = f"https://discord.com/api/webhooks/{app_id}/{token}/messages/@original"
        method = "patch"
    else:
        url = f"https://discord.com/api/webhooks/{app_id}/{token}"
        method = "post"

    headers = {"Content-Type": "application/json"}
    body = {"content": content}

    try:
        r = requests.request(method, url, headers=headers, json=body)
        if r.status_code in [200, 201]:
            return r.json().get("id")
        else:
            print(f"⚠️ Discord follow-up failed: {r.status_code}, {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ Discord follow-up exception: {e}")
        return None