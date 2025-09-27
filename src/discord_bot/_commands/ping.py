def handle_ping(payload):
    print(f"payload: {payload}")
    return {
        "type": 4,
        "data": {
            "content": "Hello from local Lambda Discord bot!"
        }
    }
