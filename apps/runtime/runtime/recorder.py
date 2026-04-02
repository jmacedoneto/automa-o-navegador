EVENT_FIELDS = (
    "selector",
    "value",
    "url",
    "waitTime",
    "duration",
    "key",
    "options",
    "downloadPath",
    "uploadPath",
    "metadata",
)


def normalize_event(event: dict) -> dict:
    normalized = {
        "action": event["type"],
        "waitTime": event.get("waitTime", 500),
    }

    for field in EVENT_FIELDS:
        if field in event and event[field] is not None:
            normalized[field] = event[field]

    normalized.setdefault("selector", "")
    normalized.setdefault("value", "")
    return normalized
