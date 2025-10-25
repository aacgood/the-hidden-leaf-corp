import json
import re
import time
import boto3
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# ---------- CONFIG ----------
REGION = "ap-southeast-1"
DISCORD_BASE = "https://discord.com/api/v10"
GUILD_ID = "1419520053971517633"
CHUNIN_ROLE_ID = "1420160564306513930"
DRY_RUN = False  # ⬅️ Toggle this to False to go live

# ---------- Secrets ----------
def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)
    discord_secret = json.loads(client.get_secret_value(SecretId="discord_keys")["SecretString"])
    supabase_secret = json.loads(client.get_secret_value(SecretId="supabase_keys")["SecretString"])
    return {
        "DISCORD_BOT_TOKEN": discord_secret.get("DISCORD_BOT_TOKEN"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
        "DISCORD_WEBHOOK": discord_secret.get("DISCORD_WEBHOOK"),  # optional
    }

SECRETS = get_secrets()

# ---------- Supabase ----------
def get_employees():
    print("[INFO] Fetching employees from Supabase...")
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])
    data = supabase.table("employees").select("torn_user_id, employee_name").execute().data
    employees = {str(emp["torn_user_id"]) for emp in data}
    print(f"[INFO] Retrieved {len(employees)} employees.")
    return employees

# ---------- Discord ----------
def get_discord_members():
    print("[INFO] Fetching Discord members...")
    headers = {"Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}"}
    members = []
    after = None
    while True:
        url = f"{DISCORD_BASE}/guilds/{GUILD_ID}/members?limit=1000"
        if after:
            url += f"&after={after}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"[ERROR] Discord API error: {resp.status_code} - {resp.text}")
            break
        batch = resp.json()
        if not batch:
            break
        members.extend(batch)
        after = batch[-1]["user"]["id"]
        if len(batch) < 1000:
            break
    print(f"[INFO] Retrieved {len(members)} Discord members.")
    return members

# ---------- Role Management ----------
def add_role(user_id):
    headers = {
        "Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_BASE}/guilds/{GUILD_ID}/members/{user_id}/roles/{CHUNIN_ROLE_ID}"
    resp = requests.put(url, headers=headers)
    if resp.status_code in [204, 200]:
        print(f"[SUCCESS] Added Chunin role to {user_id}")
    else:
        print(f"[ERROR] Failed to add Chunin role to {user_id}: {resp.status_code} - {resp.text}")

def remove_role(user_id):
    headers = {
        "Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_BASE}/guilds/{GUILD_ID}/members/{user_id}/roles/{CHUNIN_ROLE_ID}"
    resp = requests.delete(url, headers=headers)
    if resp.status_code in [204, 200]:
        print(f"[SUCCESS] Removed Chunin role from {user_id}")
    else:
        print(f"[ERROR] Failed to remove Chunin role from {user_id}: {resp.status_code} - {resp.text}")

# ---------- Main Logic ----------
def lambda_handler(event=None, context=None):
    print("=" * 60)
    run_mode = "DRY-RUN" if DRY_RUN else "LIVE"
    print(f"[START] {run_mode} Chunin Role Sync @ {datetime.now(timezone.utc)} UTC")
    print("=" * 60)

    employees = get_employees()
    members = get_discord_members()

    to_add = []
    to_remove = []

    for m in members:
        user_id = m["user"]["id"]
        username = m["user"].get("username", "")
        nick = m.get("nick") or username
        roles = m.get("roles", [])
        has_chunin = CHUNIN_ROLE_ID in roles
        torn_match = re.search(r"\[(\d+)\]", str(nick))

        if not torn_match:
            if has_chunin:
                print(f"[REMOVE] {username} ({user_id}) is unverified → removing Chunin role")
                to_remove.append(user_id)
            else:
                print(f"[SKIP] {username} ({user_id}) is unverified → no role to remove")
            continue

        torn_id = torn_match.group(1)

        if torn_id in employees:
            if not has_chunin:
                print(f"[ADD] {nick} ({user_id}) → Needs Chunin role")
                to_add.append(user_id)
            else:
                print(f"[OK] {nick} ({user_id}) already has Chunin role")
        else:
            if has_chunin:
                print(f"[REMOVE] {nick} ({user_id}) → Should not have Chunin role")
                to_remove.append(user_id)
            else:
                print(f"[OK] {nick} ({user_id}) correctly without Chunin role")

    print("-" * 60)
    print(f"[SUMMARY] ADD role to: {len(to_add)} members")
    print(f"[SUMMARY] REMOVE role from: {len(to_remove)} members")
    print(f"[MODE] {'Dry-run only — no changes made.' if DRY_RUN else 'Live mode — applying changes now!'}")
    print("-" * 60)

    # Execute changes if not dry-run
    if not DRY_RUN:
        for user_id in to_add:
            add_role(user_id)
            time.sleep(1)  # avoid rate limits

        for user_id in to_remove:
            remove_role(user_id)
            time.sleep(1)

    summary = {
        "time": datetime.now(timezone.utc).isoformat(),
        "mode": run_mode,
        "add_count": len(to_add),
        "remove_count": len(to_remove),
    }

    # Optional webhook summary
    if SECRETS.get("DISCORD_WEBHOOK"):
        try:
            payload = {
                "content": (
                    f"📋 **Chunin Role Sync ({run_mode})**\n"
                    f"🕒 `{summary['time']}` UTC\n"
                    f"✅ ADD: {summary['add_count']}\n"
                    f"❌ REMOVE: {summary['remove_count']}"
                )
            }
            requests.post(SECRETS["DISCORD_WEBHOOK"], json=payload, timeout=10)
        except Exception as e:
            print(f"[WARN] Failed to post webhook summary: {e}")

    print(f"[END] {run_mode} complete.")
    print("=" * 60)
    return {"status": run_mode.lower(), "adds": len(to_add), "removes": len(to_remove)}
