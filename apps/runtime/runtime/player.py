from typing import Literal


RunStatus = Literal["queued", "running", "paused", "success", "failed"]


def build_run_summary(steps_completed: int, total_steps: int, status: RunStatus) -> dict:
    return {
        "stepsCompleted": steps_completed,
        "totalSteps": total_steps,
        "status": status,
    }


def build_delivery_payload(run_id: str, destination: str, extracted_data: dict) -> dict:
    return {
        "run_id": run_id,
        "destination": destination,
        "payload": extracted_data,
    }
