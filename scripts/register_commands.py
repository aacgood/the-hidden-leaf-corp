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
        "description": "replies with pong!"
    },
    {
        "name": "register",
        "description": "register Company Director API Key",
        "options": [
            {
                "name": "api_key",
                "description": "Company API Key",
                "type": 3, #string
                "required": True
            }
        ]
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
            }
        ]
    }
]

URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/commands"

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
    