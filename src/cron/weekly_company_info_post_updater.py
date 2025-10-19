import json
import boto3
import requests
from datetime import datetime
from supabase import create_client, Client

REGION = "ap-southeast-1"
DISCORD_BASE = "https://discord.com/api/v10"


REQUIREMENTS_TEXT = (
    "**Requirements**\n"
    "- Be active\n"
    "- Aim to reach Level 15 within a month of joining\n"
    "- Keep drug addiction above -6 before evaluation day\n"
    "- Weekly rehabilitation required (or twice weekly if addiction is too high)\n"
)

POLICY_TEXT = (
    "**3 Strikes Policy** ❌❌❌\n"
    "Failure to adhere to the direction of the company director, failing to rehab on time or "
    "unexplained absence will result in a strike against you. "
    "3 strikes over a 6 month period will see you ejected from The Hidden Leaf Corp."
)

def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)
    discord_secret = json.loads(client.get_secret_value(SecretId="discord_keys")["SecretString"])
    supabase_secret = json.loads(client.get_secret_value(SecretId="supabase_keys")["SecretString"])
    return {
        "DISCORD_BOT_TOKEN": discord_secret.get("DISCORD_BOT_TOKEN"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }


SECRETS = get_secrets()


def get_company_benefits(company_type: int, rating: int, supabase: Client):
    """Return list of cumulative benefits for a company up to its rating."""
    data = (
        supabase.table("ref_company")
        .select("benefit_description")
        .eq("company_type", company_type)
        .lte("rating", rating)
        .order("rating", desc=False)
        .execute()
        .data
    )
    return [row["benefit_description"] for row in data] if data else []


def load_directors_map(supabase: Client):
    """Return dict mapping torn_user_id -> director_name"""
    try:
        rows = supabase.table("directors").select("torn_user_id,director_name").execute().data
        return {r["torn_user_id"]: r.get("director_name") for r in rows} if rows else {}
    except Exception as e:
        print(f"[DiscordUpdater] Error fetching directors: {e}")
        return {}


def build_company_message(company, director_name, benefits):
    """Builds the Discord message text."""
    stars = "⭐" * company.get("rating", 0)
    director_display = director_name or "Unknown Director"

    msg = f"**Store Name:** {company['company_name']}\n"
    msg += f"**Director:** {director_display}\n"
    msg += f"**Current Level:** {stars or 'Unrated'}\n\n"

    # Custom message section (if provided)
    if company.get("custom_msg_1"):
        msg += f"{company['custom_msg_1'].strip()}\n\n"

    msg += "**Benefits**\n"
    if benefits:
        msg += "\n".join(f"- {b}" for b in benefits)
    else:
        msg += "- None currently available, but we're working towards building our ⭐ goals!"

    #msg += f"\n\n{REQUIREMENTS_TEXT}\n{POLICY_TEXT}"

    msg += "\n```✨ ✦ ✧ ✦ ✨ ✦ ✧ ✦ ✨ ✦ ✧ ✦ ✨ ✦ ✧ ✦ ✨```\n\n"

    return msg


def update_discord_message(channel_id, message_id, content):
    headers = {
        "Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_BASE}/channels/{channel_id}/messages/{message_id}"
    payload = {"content": content}
    r = requests.patch(url, headers=headers, json=payload, timeout=10)
    return r.status_code, r.text


def post_discord_message(channel_id, content):
    headers = {
        "Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_BASE}/channels/{channel_id}/messages"
    payload = {"content": content}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    return r.status_code, r.json() if r.ok else r.text


def lambda_handler(event, context):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    # Preload director names
    directors_map = load_directors_map(supabase)

    try:
        companies = supabase.table("company").select("*").execute().data
    except Exception as e:
        print(f"[DiscordUpdater] Error fetching companies: {e}")
        return {"statusCode": 500, "body": "Failed to fetch companies"}

    for company in companies:
        company_id = company["company_id"]
        print(f"[DiscordUpdater] Processing company {company_id} ({company['company_name']})")

        channel_id = company.get("discord_channel_id")
        if not channel_id:
            print(f"[DiscordUpdater] No Discord channel for {company_id}")
            continue

        director_name = directors_map.get(company.get("torn_user_id"))
        benefits = get_company_benefits(company["company_type"], company.get("rating", 0), supabase)
        content = build_company_message(company, director_name, benefits)

        message_id = company.get("discord_message_id")

        if message_id:
            status, result = update_discord_message(channel_id, message_id, content)
            print(f"[DiscordUpdater] Updated message {message_id}: {status}")
        else:
            status, resp = post_discord_message(channel_id, content)
            if status in (200, 201):
                msg_id = resp["id"]
                supabase.table("company").update({"discord_message_id": msg_id}).eq("company_id", company_id).execute()
                print(f"[DiscordUpdater] Created new message for {company_id}: {msg_id}")
            else:
                print(f"[DiscordUpdater] Failed to post for {company_id}: {resp}")

    print("[DiscordUpdater] Completed successfully.")
    return {"statusCode": 200, "body": "Discord updater completed"}
