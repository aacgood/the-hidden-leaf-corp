import os
import boto3
import requests
import json

AWS_REGION = "ap-southeast-1"

# --- Load Secrets ---
secrets_client = boto3.client("secretsmanager", region_name=AWS_REGION)
secrets = secrets_client.get_secret_value(SecretId="discord_keys")

DISCORD_BOT_TOKEN = json.loads(secrets["SecretString"])["DISCORD_BOT_TOKEN"]
DISCORD_APPLICATION_ID = json.loads(secrets["SecretString"])["DISCORD_APPLICATION_ID"]

# --- Common Valid Notes ---
DONATE_NOTE_CHOICES = [
    {"name": "Initial Funding", "value": "Initial Funding"},
    {"name": "Top-up Funding", "value": "Top-up Funding"}
]

REPAY_NOTE_CHOICES = [
    {"name": "Repayment", "value": "Repayment"},
]

# --- Slash Commands ---
COMMANDS = [
    {
        "name": "ping",
        "description": "Replies with pong!",
        "default_member_permissions": None,
        "dm_permission": False,
    },
    {
        "name": "register",
        "description": "Register a company director API key",
        "default_member_permissions": None,
        "dm_permission": False,
        "options": [
            {
                "name": "api_key",
                "description": "Director API Key",
                "type": 3,  # string
                "required": True,
            },
        ],
    },
    {
        "name": "link",
        "description": "Link a Torn company ID to this Discord channel",
        "default_member_permissions": None,
        "dm_permission": False,
        "options": [
            {
                "name": "company_id",
                "description": "Company ID to link",
                "type": 4,  # integer
                "required": True,
            },
            {
                "name": "webhook_url",
                "description": "Discord webhook URL for this channel",
                "type": 3,  # string
                "required": True,
            },
        ],
    },
    {
        "name": "company",
        "description": "Company-related financial actions",
        "dm_permission": False,
        "options": [
            {
                "type": 1,  # Subcommand
                "name": "donate",
                "description": "Record a donation to a company (funds sent from donator to director)",
                "options": [
                    {
                    "name": "acronym",
                    "description": "company acronym",
                    "type": 3,   # string
                    "required": True
                    },
                    {
                        "name": "amount",
                        "description": "Amount donated (whole dollars only)",
                        "type": 4,  # integer
                        "required": True,
                    },
                    {
                        "name": "note",
                        "description": "Purpose of donation (must choose from list)",
                        "type": 3,  # string
                        "required": True,
                        "choices": DONATE_NOTE_CHOICES,
                    },
                ],
            },
            {
                "type": 1,  # Subcommand
                "name": "repay",
                "description": "Record a repayment from a company (funds returned to donator)",
                "options": [
                    {
                        "name": "acronym",
                        "description": "company acronym",
                        "type": 3,   # string
                        "required": True
                    },
                    {
                        "name": "amount",
                        "description": "Amount repaid (whole dollars only)",
                        "type": 4,  # integer
                        "required": True,
                    },
                    {
                        "name": "note",
                        "description": "Purpose of repayment (must choose from list)",
                        "type": 3,  # string
                        "required": True,
                        "choices": REPAY_NOTE_CHOICES,
                    },
                ],
            },
        ],
    },
]

# --- Guild only ---
GUILD_ID = "1419520053971517633"
URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/guilds/{GUILD_ID}/commands"

# --- Global (if needed) ---
# URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/commands"

headers = {
    "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}

response = requests.put(URL, headers=headers, json=COMMANDS)
if response.status_code in [200, 201]:
    print("✅ Successfully registered commands:\n")
    for cmd in response.json():
        print(f"- {cmd['name']}: {cmd['id']}")
else:
    print(f"❌ Error registering commands: {response.status_code}")
    print(response.text)
