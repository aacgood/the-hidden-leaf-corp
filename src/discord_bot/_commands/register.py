import re
import requests

DISCORD_API_BASE = "https://discord.com/api/v10/interactions"

def handle_register(payload):
    """
    Handles /register command using the synchronous deferred response pattern.
    Returns a deferred response immediately and posts the final message after processing.
    """

    # --- Extract API key and Discord user info ---
    api_key = payload["data"]["options"][0]["value"]
    user_nick = payload["member"].get("nick") or payload["member"]["user"]["username"]

    # Extract Torn user ID from the discord username
    match = re.search(r"\[(\d+)\]", user_nick)
    torn_user_id = int(match.group(1)) if match else None

    interaction_id = payload["id"]
    interaction_token = payload["token"]

    # --- Step 1: Immediately defer response ---
    defer_response = {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    # --- Step 2: Process the command ---
    content = _process_register(api_key, torn_user_id)

    # --- Step 3: Send the final message back to Discord ---
    callback_url = f"{DISCORD_API_BASE}/{interaction_id}/{interaction_token}/callback"

    try:
        r = requests.post(
            callback_url,
            json={
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {"content": content}
            },
            timeout=5
        )
        print("Callback status:", r.status_code)
        print("Callback response:", r.text)
    except Exception as e:
        print("Error sending callback to Discord:", e)

    # --- Step 4: Return deferred response immediately ---
    return defer_response


def _process_register(api_key, torn_user_id):
    """
    Validates the API key against Torn API and prepares a concise response message.
    """
    
    API_URL = f"https://api.torn.com/company/?selections=profile&key={api_key}"
    
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()

        # Check if Torn returned an error because of a bad key
        if "error" in data:
            return f"Invalid API key provided.  Please check and retry."

        # Otherwise, extract director
        director_id = data.get("company", {}).get("director")
        
        if director_id == torn_user_id:
            return f"Company director: {director_id}, torn_user_id(requestor): {torn_user_id}"
        
        else:

            # If someone is using a directors API key, the director wont match the requestor so reject
            return f"You are not a company director"

    except Exception as e:
        return f"Exception validating API key: {e}"

