import json
import boto3
from _commands.ping import handle_ping
from _commands.register import handle_register
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


# Fetch Discord public key from Secrets Manager
def get_discord_public_key():
    SECRET_NAME = "discord_keys"
    REGION_NAME = "ap-southeast-1"
    
    client = boto3.client("secretsmanager", region_name=REGION_NAME)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])
    
    return secret["DISCORD_PUBLIC_KEY"]

DISCORD_PUBLIC_KEY = get_discord_public_key()


def verify_discord_request(signature, timestamp, body):
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify((timestamp + body).encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False

def lambda_handler(event, context):
    body = event.get("body", "")
    headers = event.get("headers", {})
    
    signature = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519")
    timestamp = headers.get("x-signature-timestamp") or headers.get("X-Signature-Timestamp")

    if not signature or not timestamp:
        return {"statusCode": 401, "body": "Missing signature"}

    if not verify_discord_request(signature, timestamp, body):
        return {"statusCode": 401, "body": "Invalid request signature"}

    payload = json.loads(body)

    # Handle PING (Discord verification)
    if payload["type"] == 1:
        response = {"type":1}

    # Slash commands
    elif payload["type"] == 2:
        command_name = payload["data"]["name"]

        if command_name == "ping":
            response = handle_ping(payload)
        elif command_name == "register":
            response = handle_register(payload)

    else:
        response = {"type": 4, "data": {"content": "Unknown interaction"}}

    # Lambda Proxy requires statusCode + body
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response)
    }