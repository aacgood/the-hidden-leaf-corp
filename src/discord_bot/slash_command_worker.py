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

        elif command == "company_invest":
            print("company_invest")
            try:
                from _commands.company_invest import handle_company_invest
                handle_company_invest(msg)
            except Exception as e:
                print(f"❌ Error processing company_invest: {e}")

        elif command == "company_return":
            print("company_return")
            try:
                from _commands.company_return import handle_company_return
                handle_company_return(msg)
            except Exception as e:
                print(f"❌ Error processing company_return {e}")

        elif command == "company_info":
            print("company_invest")
            try:
                from _commands.company_info import handle_company_info
                handle_company_info(msg)
            except Exception as e:
                print(f"❌ Error processing company_invest: {e}")
        else:
            print(f"⚠️ Unhandled command: {command}")


    return {"statusCode": 200}
