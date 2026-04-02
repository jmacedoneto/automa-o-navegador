from __future__ import annotations


def create_recording_payload(automation_id: str | None) -> dict:
    return {
        "automation_id": automation_id,
        "status": "pending",
    }
