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
INVEST_NOTE_CHOICES = [
    {"name": "Initial Investment", "value": "Initial Investment"},
    {"name": "Top-up Investment", "value": "Top-up Investment"},
    {"name": "Sign-on Bonus", "value": "Sign-on Bonus"},
    {"name": "Giveaways", "value": "Giveaways"},
]

RETURN_NOTE_CHOICES = [
    {"name": "Return", "value": "Return"},
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
                "name": "invest",
                "description": "Record an investment to a company (funds sent from investor to director)",
                "options": [
                    {
                        "name": "acronym",
                        "description": "Company acronym",
                        "type": 3,   # string
                        "required": True
                    },
                    {
                        "name": "amount",
                        "description": "Amount invested (whole dollars only)",
                        "type": 4,  # integer
                        "required": True,
                    },
                    {
                        "name": "note",
                        "description": "Purpose of investment (choose from list)",
                        "type": 3,  # string
                        "required": True,
                        "choices": INVEST_NOTE_CHOICES,
                    },
                    {
                        "name": "delegate",
                        "description": "Optional: On behalf of",
                        "type": 6, # User type
                        "required": False
                    },
                ],
            },
            {
                "type": 1,  # Subcommand
                "name": "return",
                "description": "Record a return from a company (funds returned to investor)",
                "options": [
                    {
                        "name": "acronym",
                        "description": "Company acronym",
                        "type": 3,   # string
                        "required": True
                    },
                    {
                        "name": "amount",
                        "description": "Amount returned (whole dollars only)",
                        "type": 4,  # integer
                        "required": True,
                    },
                    {
                        "name": "note",
                        "description": "Purpose of return (choose from list)",
                        "type": 3,  # string
                        "required": True,
                        "choices": RETURN_NOTE_CHOICES,
                    },
                    {
                        "name": "delegate",
                        "description": "Optional: On behalf of",
                        "type": 6, # User type
                        "required": False
                    },
                ],
            },
            {
                "type": 1,  # Subcommand
                "name": "info",
                "description": "Display current company names and acroymns",
            },
        ],
    },
    {
        "name": "chunin",
        "description": "Chunin related commands",
        "dm_permission": False,
        "options": [
            {
                "type": 1,  # Subcommand
                "name": "register",
                "description": "Register your interest to become a Jonin",
                "options": [
                    {
                        "name": "api_key",
                        "description": "Chunin API Key",
                        "type": 3,  # string
                        "required": True,
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
