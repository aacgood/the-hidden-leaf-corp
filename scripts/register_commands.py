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

COMMANDS = [
    {
        "name": "ping",
        "description": "replies with pong!",
        "default_member_permissions": None,  # everyone can see
        "dm_permission": False
    },
    {
        "name": "register",
        "description": "Register a company director API key",
        "default_member_permissions": None,  # visible to everyone, Lambda will enforce role/channel
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
        "description": "link a Torn company ID to this Discord channel",
        "default_member_permissions": None,  # visible to everyone
        "dm_permission": False,
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

# Guild only
GUILD_ID = "1419520053971517633"
URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/guilds/{GUILD_ID}/commands"

# Global
#URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/commands"

headers = {
    "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.put(URL, headers=headers, json=COMMANDS)
if response.status_code in [200, 201]:
    print("successfully registered commands")

    for cmd in response.json():
        print(f"- {cmd['name']}: {cmd['id']}")

else:
    print(f"Error registering commands: {response.status_code}")
    