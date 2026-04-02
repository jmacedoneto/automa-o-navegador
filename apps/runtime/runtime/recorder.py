def normalize_event(event: dict) -> dict:
    return {
        "action": event["type"],
        "selector": event.get("selector", ""),
        "value": event.get("value", ""),
        "waitTime": event.get("waitTime", 500),
    }
