import json
import os
import boto3
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from _commands.ping import handle_ping
#from _commands.company_channels import handle_link_company

DISCORD_API_BASE = "https://discord.com/api/v10/interactions"

SLASH_COMMAND_QUEUE_URL = os.environ.get("SLASH_COMMAND_QUEUE_URL")

# Roles
ROLE_AN_STORE_ADMIN = 1424612035555098716
ROLE_MUSIC_STORE_ADMIN = 1419803622631543046
ROLE_ZERODB_STORE_ADMIN = 1427104006617960489
ROLE_SERVER_ADMIN = 1419804995532099624
ROLE_JONIN = 1419589117938761839
ROLE_ANBU = 1423550306243055627
ROLE_HOKAGE = 1423558170621640764

# Channels
CHANNEL_AN_STORE_REPORTS = 1424626226349346918
CHANNEL_AN_STORE_ADMIN = 1424625414722293790
CHANNEL_MUSIC_STORE_REPORTS = 1419804361248215131
CHANNEL_MUSIC_STORE_ADMIN = 1419803970649722992
CHANNEL_ZERODB_STORE_ADMIN = 1427104434613256312
CHANNEL_ZERODB_STORE_REPORTS = 1427104495787049156
CHANNEL_THLC_BOT_COMMANDS = 1428303850322001921

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
    import json
    body = event.get("body", "")
    headers = event.get("headers", {})

    # --- Verify Discord request ---
    signature = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519")
    timestamp = headers.get("x-signature-timestamp") or headers.get("X-Signature-Timestamp")
    if not signature or not timestamp:
        return {"statusCode": 401, "body": "Missing signature"}
    if not verify_discord_request(signature, timestamp, body):
        return {"statusCode": 401, "body": "Invalid request signature"}

    payload = json.loads(body)

    # --- Handle PING ---
    if payload["type"] == 1:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"type": 1})
        }

    # --- Slash commands ---
    if payload["type"] == 2:
        data = payload.get("data", {})
        command_name = data.get("name")

        # --- Early rejection checks ---
        user_roles = {int(r) for r in payload["member"]["roles"]}
        channel_id = int(payload["channel"]["id"])

        if command_name == "register":
            ALLOWED_ROLES = {ROLE_SERVER_ADMIN, ROLE_AN_STORE_ADMIN, ROLE_MUSIC_STORE_ADMIN, ROLE_ZERODB_STORE_ADMIN}
            ALLOWED_CHANNELS = {CHANNEL_AN_STORE_ADMIN, CHANNEL_MUSIC_STORE_ADMIN, CHANNEL_ZERODB_STORE_ADMIN}
            if not user_roles.intersection(ALLOWED_ROLES):
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 You don’t have permission to use `/register`.", "flags": 64}
                    })
                }
            if channel_id not in ALLOWED_CHANNELS:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 `/register` cannot be used in this channel.", "flags": 64}
                    })
                }

        elif command_name == "link":
            ALLOWED_ROLES = {ROLE_SERVER_ADMIN}
            ALLOWED_CHANNELS = {CHANNEL_AN_STORE_REPORTS, CHANNEL_MUSIC_STORE_REPORTS, CHANNEL_ZERODB_STORE_REPORTS}
            if not user_roles.intersection(ALLOWED_ROLES):
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 You don’t have permission to use `/link`.", "flags": 64}
                    })
                }
            if channel_id not in ALLOWED_CHANNELS:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 `/link` cannot be used in this channel.", "flags": 64}
                    })
                }

        elif command_name == "company":
            ALLOWED_ROLES = {ROLE_HOKAGE, ROLE_ANBU}
            ALLOWED_CHANNELS = {CHANNEL_THLC_BOT_COMMANDS}
            if not user_roles.intersection(ALLOWED_ROLES):
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 You don’t have permission to use `/company`.", "flags": 64}
                    })
                }
            if channel_id not in ALLOWED_CHANNELS:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "type": 4,
                        "data": {"content": "🚫 `/company` cannot be used in this channel. Use thlc-bot-commands", "flags": 64}
                    })
                }

        # --- Normalize company subcommands ---
        if command_name == "company":
            options = data.get("options", [])
            normalized_parts = [command_name]
            normalized_options = None
            while options:
                first_option = options[0]
                opt_type = first_option.get("type")
                if opt_type in (1, 2):
                    sub_name = first_option.get("name")
                    normalized_parts.append(sub_name)
                    options = first_option.get("options", [])
                    normalized_options = options
                else:
                    normalized_options = options
                    break
            command_name = "_".join(normalized_parts)
            payload["data"]["options"] = normalized_options or []

        # --- Immediately defer response ---
        defer_response = {"type": 5}
        response = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(defer_response)
        }

        # --- Push to SQS synchronously (fast) ---
        try:
            sqs_client.send_message(
                QueueUrl=SLASH_COMMAND_QUEUE_URL,
                MessageBody=json.dumps({
                    "command_name": command_name,
                    "payload": payload,
                    "initiator_id": payload["member"]["user"]["id"]
                })
            )
        except Exception as e:
            print(f"Error pushing {command_name} payload to SQS:", e)

        return response

    # Unknown interaction
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"type": 4, "data": {"content": "Unknown interaction"}})
    }
