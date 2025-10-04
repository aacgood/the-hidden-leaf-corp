# src/discord_bot/slash_command_worker.py
import json
import boto3
from register_worker import process_register
# from company_channels import process_link_company   # (future extension)

def lambda_handler(event, context):
    """
    Worker Lambda triggered by SQS. 
    Routes incoming messages to the correct command processor.
    """
    for record in event.get("Records", []):
        msg = json.loads(record["body"])
        command = msg.get("command_name")
        payload = msg.get("payload")

        print(f"Router received command: {command}")

        if command == "register":
            import register_worker  # or from _commands.register_worker import process_register
            register_worker.process_register(payload)

        elif command == "link":
            from _commands.company_channels import handle_link_company
            handle_link_company(msg)

        else:
            print(f"⚠️ Unhandled command: {command}")


    return {"statusCode": 200}
