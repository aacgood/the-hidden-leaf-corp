# src/discord_bot/_commands/company_return.py
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

# --- Allowed delegators ---
ROLE_ANBU = 1423550306243055627
ROLE_HOKAGE = 1423558170621640764
ALLOWED_DELEGATORS = {ROLE_ANBU, ROLE_HOKAGE}

def handle_company_return(msg):
    """
    Process /company return slash command, with optional delegate.
    """
    payload = msg["payload"]
    user_roles = {int(r) for r in payload["member"].get("roles", [])}

    # Extract command options
    options = payload.get("data", {}).get("options", [])
    acronym = next((opt["value"].upper() for opt in options if opt["name"] == "acronym"), None)
    amount = next((opt["value"] for opt in options if opt["name"] == "amount"), None)
    note = next((opt["value"] for opt in options if opt["name"] == "note"), None)

    # ✅ Validate amount
    try:
        amount = int(amount)
        if amount <= 0:
            return send_followup(payload, f"🚫 Invalid amount: `{amount}`. Must be greater than 0.")
    except (TypeError, ValueError):
        return send_followup(payload, f"🚫 Invalid amount: `{amount}`. Must be a number.")

    # --- Determine investor (delegate or issuer) ---
    delegate_option = next((opt for opt in options if opt["name"] == "delegate"), None)
    if delegate_option:
        delegate_discord_id = delegate_option["value"]
        delegate_member = payload["data"]["resolved"]["members"].get(delegate_discord_id)
        if not delegate_member:
            return send_followup(payload, f"🚫 Could not resolve delegate <@{delegate_discord_id}>")

        # Check delegator role
        delegate_roles = {int(r) for r in delegate_member.get("roles", [])}
        if not delegate_roles.intersection(ALLOWED_DELEGATORS):
            return send_followup(payload, f"🚫 <@{delegate_discord_id}> is not allowed to be a delegate.")

        delegate_nick = delegate_member.get("nick") or delegate_member["user"]["username"]
        match = re.search(r"\[(\d+)\]", delegate_nick)
        if not match:
            return send_followup(payload, f"🚫 Could not extract Torn ID from delegate {delegate_discord_id}")

        investor_id = int(match.group(1))
        investor_name = delegate_nick
        initiator_id = investor_id  # for transaction initiated_by
    else:
        user_nick = payload["member"].get("nick")
        match = re.search(r"\[(\d+)\]", user_nick or "")
        investor_id = int(match.group(1)) if match else None
        if not investor_id:
            return send_followup(payload, f"⚠️ Could not extract Torn user ID from `{user_nick}`")
        investor_name = user_nick
        initiator_id = investor_id

    print(f"[INFO] {investor_name} ({investor_id}) returning {amount} to {acronym} under note '{note}'")

    # Lookup company by acronym
    try:
        company_resp = (
            supabase.table("company")
            .select("*")
            .eq("company_acronym", acronym)
            .single()
            .execute()
        )
    except Exception:
        return send_followup(payload, f"🚫 `{acronym}` is Invalid / company not found")

    if not company_resp.data:
        return send_followup(payload, f"🚫 `{acronym}` is Invalid / company not found")

    company = company_resp.data
    company_id = company["company_id"]
    company_name = company["company_name"]
    timestamp = datetime.now(timezone.utc).isoformat()

    # 1️⃣ Ensure the investment master record exists (so return has a parent)
    investment_resp = (
        supabase.table("company_investments")
        .select("id, total_invested, total_returned, status")
        .eq("company_id", company_id)
        .eq("investor_id", investor_id)
        .execute()
    )

    if not investment_resp.data or len(investment_resp.data) == 0:
        return send_followup(
            payload,
            f"🚫 No donation record found for `{acronym}` under `{investor_name}`. Cannot record return."
        )

    investment = investment_resp.data[0]
    investment_id = investment["id"]

    # 2️⃣ Insert return transaction (instantly confirmed)
    transaction_payload = {
        "investment_id": investment_id,
        "transaction_type": "return",
        "amount": int(amount),
        "notes": note,
        "initiated_by": str(initiator_id),
        "status": "confirmed",
        "recorded_at": timestamp,
    }

    print("[DEBUG] Inserting company_investment_transactions:", transaction_payload)
    txn_resp = supabase.table("company_investment_transactions").insert(transaction_payload).execute()

    if not txn_resp.data:
        print(f"[ERROR] Failed to insert company_investment_transactions: {txn_resp}")
        return send_followup(payload, "⚠️ Failed to record return transaction.")

    # 3️⃣ Send follow-up message to Discord
    msg_content = f"✅ Return of **${amount}** recorded for **{acronym} ({company_name})** under note *{note}* on behalf of **{investor_name}**."
    discord_msg_id = send_followup(payload, msg_content, edit_original=False)

    return discord_msg_id


def send_followup(payload, content: str, edit_original: bool = True) -> str | None:
    """
    Send a message to Discord after deferred interaction.
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
