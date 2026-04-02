from __future__ import annotations


def create_job_payload(
    automation_id: str,
    trigger_type: str,
    mode: str,
    incoming_payload: dict,
) -> dict:
    return {
        "automation_id": automation_id,
        "trigger_type": trigger_type,
        "mode": mode,
        "payload": incoming_payload,
        "status": "queued",
    }
