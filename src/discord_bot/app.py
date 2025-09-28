import json
import os
import boto3
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from _commands.ping import handle_ping

DISCORD_API_BASE = "https://discord.com/api/v10/interactions"

REGISTER_QUEUE_URL = os.environ.get("REGISTER_QUEUE_URL")
sqs_client = boto3.client("sqs")

def get_secrets():
    """
    Load both Discord and Supabase secrets from AWS Secrets Manager
    """
    client = boto3.client("secretsmanager", region_name="ap-southeast-1")

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_PUBLIC_KEY": discord_secret.get("DISCORD_PUBLIC_KEY"),
        "DISCORD_APPLICATION_ID": discord_secret.get("DISCORD_APPLICATION_ID"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }

SECRETS = get_secrets()

def verify_discord_request(signature, timestamp, body):
    if not SECRETS['DISCORD_PUBLIC_KEY']:
        print("Warning: DISCORD_PUBLIC_KEY not set")
        return True
    try:
        verify_key = VerifyKey(bytes.fromhex(SECRETS['DISCORD_PUBLIC_KEY']))
        verify_key.verify((timestamp + body).encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False

def lambda_handler(event, context):
    body = event.get("body", "")
    headers = event.get("headers", {})

    # Discord request verification (optional: keep from your previous code)
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
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response),
        }

    # Slash commands
    if payload["type"] == 2:
        command_name = payload["data"]["name"]

        if command_name == "ping":
            response = handle_ping(payload)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(response)
            }

        elif command_name == "register":
            # --- Immediately defer response ---
            defer_response = {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

            # --- Push payload to SQS for worker Lambda ---
            try:
                sqs_client.send_message(
                    QueueUrl=REGISTER_QUEUE_URL,
                    MessageBody=json.dumps(payload)
                )
                print("Payload pushed to SQS")
            except Exception as e:
                print("Error pushing to SQS:", e)

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(defer_response)
            }

    # Unknown interaction
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"type": 4, "data": {"content": "Unknown interaction"}})
    }
