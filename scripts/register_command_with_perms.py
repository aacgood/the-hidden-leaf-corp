import os
import sys
import boto3
import requests
import json

AWS_REGION = "ap-southeast-1"

secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)
secrets = secrets_client.get_secret_value(SecretId='discord_keys')

DISCORD_BOT_TOKEN = json.loads(secrets['SecretString'])['DISCORD_BOT_TOKEN']
DISCORD_APPLICATION_ID = json.loads(secrets['SecretString'])['DISCORD_APPLICATION_ID']

# === Add your role IDs here ===
# The @everyone role is always the same as the guild_id
GUILD_ID = "1419520053971517633"
EVERYONE_ROLE_ID = GUILD_ID

# role IDs
MUSIC_STORE_ADMIN = "1419803622631543046"
AN_STORE_ADMIN = "1424612035555098716"
SERVER_ADMIN = "1419804995532099624"
JONIN = "1419589117938761839"
ANBU = "1423550306243055627"
HOCKAGE = "1423558170621640764"

DIRECTOR_ROLE_ID = "123456789012345678"
STAFF_ROLE_ID = "234567890123456789"

COMMANDS = [
    {
        "name": "ping",
        "description": "replies with pong!"
    },
    {
        "name": "register",
        "description": "Register a company director API key (with optional webhook)",
        "options": [
            {
                "name": "api_key",
                "description": "Company API Key",
                "type": 3,  # string
                "required": True,
            },
        ],
    },
    {
        "name": "link",
        "description": "link a Torn company to this Discord channel",
        "options": [
            {
                "name": "company_id",
                "description": "Company ID to link",
                "type": 4,  # integer
                "required": True
            },
            {
                "name": "webhook_url",
                "description": "Discord webhook URL for this channel",
                "type": 3,  # string
                "required": True,
            },
        ]
    }
]

# Guild-only command registration
URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/guilds/{GUILD_ID}/commands"

headers = {
    "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.put(URL, headers=headers, json=COMMANDS)
if response.status_code in [200, 201]:
    print("successfully registered commands")

    commands = response.json()
    for cmd in commands:
        print(f"- {cmd['name']}: {cmd['id']}")

        # === Apply role-based permissions here ===
        # Example: block @everyone, allow Director + Staff roles
        perms_url = f"{URL}/{cmd['id']}/permissions"

        if cmd["name"] in ["register", "link"]:  # restrict these
            permissions = {
                "permissions": [
                    {"id": EVERYONE_ROLE_ID, "type": 1, "permission": False},
                    {"id": MUSIC_STORE_ADMIN, "type": 1, "permission": True},
                    {"id": AN_STORE_ADMIN, "type": 1, "permission": True},
                    {"id": SERVER_ADMIN, "type": 1, "permission": True},
                    {"id": JONIN, "type": 1, "permission": True},
                    {"id": ANBU, "type": 1, "permission": True},
                    {"id": HOCKAGE, "type": 1, "permission": True},                    
                ]
            }
        else:
            # ping is open to everyone
            permissions = {
                "permissions": [
                    {"id": EVERYONE_ROLE_ID, "type": 1, "permission": True}
                ]
            }

        perm_resp = requests.put(perms_url, headers=headers, json=permissions)
        if perm_resp.status_code in [200, 201]:
            print(f"  → Permissions applied for {cmd['name']}")
        else:
            print(f"  → Failed to set permissions for {cmd['name']}: {perm_resp.status_code} {perm_resp.text}")

else:
    print(f"Error registering commands: {response.status_code} {response.text}")
