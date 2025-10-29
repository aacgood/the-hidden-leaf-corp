import json
import boto3

REGION = "ap-southeast-1"

# def get_secrets():
#     client = boto3.client("secretsmanager", region_name=REGION)

#     discord_secret = json.loads(
#         client.get_secret_value(SecretId="discord_keys")["SecretString"]
#     )
#     supabase_secret = json.loads(
#         client.get_secret_value(SecretId="supabase_keys")["SecretString"]
#     )

#     return {
#         "DISCORD_WEBHOOK_CHANNEL_THLC_BOT": discord_secret.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT"),
#         "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
#         "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
#     }



def get_secrets(secret_ids=None): 
    """ 
    Load only the specified AWS Secrets Manager secrets. 
    :param secret_ids: list of secret IDs to fetch. If None, returns empty dict. 
    :return: dict with all secrets merged. 
    """ 
    
    secrets = {} 
    if not secret_ids: 
        return secrets 
    
    client = boto3.client("secretsmanager", region_name=REGION) 
    
    for sid in secret_ids: 
        try: 
            val = json.loads(client.get_secret_value(SecretId=sid)["SecretString"]) 
            secrets.update(val) 
        except client.exceptions.ResourceNotFoundException: 
            print(f"Secret {sid} not found") 
        except client.exceptions.AccessDeniedException: 
            print(f"No permission to read secret {sid}") 
    
    return secrets