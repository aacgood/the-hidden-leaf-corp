# src/discord_bot/slash_command_worker.py
import json
import boto3
from register_worker import process_register


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

        if not command:
            print("⚠️ Missing command_name in message, skipping")
            continue

        if command == "register":
            try:    
                import register_worker  # or from _commands.register_worker import process_register
                register_worker.process_register(payload)
            except Exception as e:
                print(f"❌ Error processing register: {e}")

        elif command == "link":
            try:
                from _commands.company_channels import handle_link_company
                handle_link_company(msg)
            except Exception as e:
                print(f"❌ Error processing link: {e}")

        elif command == "company_donate":
            print("company_donate")
            try:
                from _commands.company_donate import handle_company_donate
                handle_company_donate(msg)
            except Exception as e:
                print(f"❌ Error processing company_donate: {e}")

        elif command == "company_repay":
            print("company_repay")
            try:
                from _commands.company_repay import handle_company_repay
                handle_company_repay(msg)
            except Exception as e:
                print(f"❌ Error processing company_donate: {e}")

        else:
            print(f"⚠️ Unhandled command: {command}")


    return {"statusCode": 200}
