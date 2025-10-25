import json
import requests
import boto3

REGION = "ap-southeast-1"

# --------------------------------------
# Permission name → bitfield mapping
# (based on Discord developer documentation)
# --------------------------------------
PERMISSIONS = {
    # Classic (0–30)
    "CREATE_INSTANT_INVITE":        1 << 0,
    "KICK_MEMBERS":                 1 << 1,
    "BAN_MEMBERS":                  1 << 2,
    "ADMINISTRATOR":                1 << 3,
    "MANAGE_CHANNELS":              1 << 4,
    "MANAGE_GUILD":                 1 << 5,
    "ADD_REACTIONS":                1 << 6,
    "VIEW_AUDIT_LOG":               1 << 7,
    "PRIORITY_SPEAKER":             1 << 8,
    "STREAM":                       1 << 9,
    "VIEW_CHANNEL":                 1 << 10,
    "SEND_MESSAGES":                1 << 11,
    "SEND_TTS_MESSAGES":            1 << 12,
    "MANAGE_MESSAGES":              1 << 13,
    "EMBED_LINKS":                  1 << 14,
    "ATTACH_FILES":                 1 << 15,
    "READ_MESSAGE_HISTORY":         1 << 16,
    "MENTION_EVERYONE":             1 << 17,
    "USE_EXTERNAL_EMOJIS":          1 << 18,
    "VIEW_GUILD_INSIGHTS":          1 << 19,
    "CONNECT":                      1 << 20,
    "SPEAK":                        1 << 21,
    "MUTE_MEMBERS":                 1 << 22,
    "DEAFEN_MEMBERS":               1 << 23,
    "MOVE_MEMBERS":                 1 << 24,
    "USE_VAD":                      1 << 25,
    "CHANGE_NICKNAME":              1 << 26,
    "MANAGE_NICKNAMES":             1 << 27,
    "MANAGE_ROLES":                 1 << 28,
    "MANAGE_WEBHOOKS":              1 << 29,
    "MANAGE_GUILD_EXPRESSIONS":     1 << 30,

    # Extended / newer permissions (31+)
    "USE_APPLICATION_COMMANDS":     1 << 31,
    "REQUEST_TO_SPEAK":             1 << 32,
    "MANAGE_EVENTS":                1 << 33,
    "MANAGE_THREADS":               1 << 34,
    "CREATE_PUBLIC_THREADS":        1 << 35,
    "CREATE_PRIVATE_THREADS":       1 << 36,
    "USE_EXTERNAL_STICKERS":        1 << 37,
    "SEND_MESSAGES_IN_THREADS":     1 << 38,
    "USE_EMBEDDED_ACTIVITIES":      1 << 39,
    "MODERATE_MEMBERS":             1 << 40,
    "VIEW_CREATOR_MONETIZATION_ANALYTICS": 1 << 41,
    "USE_SOUNDBOARD":               1 << 42,
    "CREATE_GUILD_EXPRESSIONS":     1 << 43,
    "CREATE_EVENTS":                1 << 44,
    "USE_EXTERNAL_SOUNDS":          1 << 45,
    "SEND_VOICE_MESSAGES":          1 << 46,
    "SEND_POLLS":                   1 << 49,
    "USE_EXTERNAL_APPS":            1 << 50,
    "PIN_MESSAGES":                 1 << 51
}


# --------------------------------------
# Helper function to calculate bitfield
# --------------------------------------
def calculate_bitfield(permission_list):
    bitfield = 0
    perms = set(perm.upper() for perm in permission_list)

    for perm in perms:
        if perm not in PERMISSIONS:
            print(f"⚠ Warning: Unknown permission '{perm}'")
        else:
            bitfield |= PERMISSIONS[perm]

    # ---------- Dependent Permissions ----------
    # External emojis/stickers require VIEW_CHANNEL + SEND_MESSAGES
    if "USE_EXTERNAL_EMOJIS" in perms or "USE_EXTERNAL_STICKERS" in perms:
        bitfield |= PERMISSIONS["VIEW_CHANNEL"]
        bitfield |= PERMISSIONS["SEND_MESSAGES"]

    # Thread permissions require VIEW_CHANNEL
    thread_perms = {"SEND_MESSAGES_IN_THREADS", "CREATE_PUBLIC_THREADS", "CREATE_PRIVATE_THREADS"}
    if perms & thread_perms:
        bitfield |= PERMISSIONS["VIEW_CHANNEL"]

    # Sending messages in threads also requires SEND_MESSAGES
    if "SEND_MESSAGES_IN_THREADS" in perms:
        bitfield |= PERMISSIONS["SEND_MESSAGES"]

    return bitfield


# --------------------------------------
# Load secrets from AWS Secrets Manager
# --------------------------------------
def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)
    discord_secret = json.loads(client.get_secret_value(SecretId="discord_keys")["SecretString"])
    return {
        "DISCORD_BOT_TOKEN": discord_secret.get("DISCORD_BOT_TOKEN")
    }


# --------------------------------------
# Main script
# --------------------------------------
def main():
    SECRETS = get_secrets()

    with open("permissions_config.json") as f:
        configs = json.load(f)

    headers = {
        "Authorization": f"Bot {SECRETS['DISCORD_BOT_TOKEN']}",
        "Content-Type": "application/json"
    }

    for entry in configs:
        # Allow single or multiple channel IDs
        channel_ids = entry["channel_id"]
        if isinstance(channel_ids, str):
            channel_ids = [channel_ids]

        overwrite_id = entry["overwrite_id"]
        overwrite_type = 0 if entry["type"].lower() == "role" else 1
        note = entry.get("note", "")

        allow_bit = calculate_bitfield(entry.get("allow", []))
        deny_bit = calculate_bitfield(entry.get("deny", []))

        for channel_id in channel_ids:
            url = f"https://discord.com/api/v10/channels/{channel_id}/permissions/{overwrite_id}"
            data = {
                "type": overwrite_type,
                "allow": str(allow_bit),
                "deny": str(deny_bit)
            }

            resp = requests.put(url, headers=headers, json=data)
            if resp.status_code == 204:
                print(f"✅ Updated permissions for {overwrite_id} in {channel_id} — {note}")
            else:
                print(f"❌ Failed ({resp.status_code}): {resp.text} — {note}")


if __name__ == "__main__":
    main()
