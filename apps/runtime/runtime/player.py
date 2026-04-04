from typing import Literal

from apps.runtime.runtime.config import RuntimeSettings
from apps.runtime.runtime.step_executor import StepExecutor
from apps.runtime.runtime.fallback import should_pause_after_failure


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


async def play_job(job: dict, page, client, settings: RuntimeSettings) -> dict:
    run_id = job.get("run_id", "")
    steps = job.get("steps", [])
    variables = job.get("variables", {})
    total = len(steps)

    await client.report_run_status(run_id, status="running", steps_completed=0, total_steps=total)

    executor = StepExecutor(page, variables=variables)
    completed = 0
    fallback_attempts = 0
    extracted_data = {}

    for i, step in enumerate(steps):
        result = await executor.execute_step(step)

        if result["success"]:
            completed += 1
            if "extracted" in result:
                extracted_data[f"step_{i}"] = result["extracted"]
            await client.report_run_status(run_id, status="running", steps_completed=completed, total_steps=total)
        else:
            fallback_attempts += 1
            if should_pause_after_failure(fallback_attempts, settings.max_fallback_attempts, settings.fallback_pause_when_failure):
                await client.report_run_status(
                    run_id,
                    status="failed",
                    steps_completed=completed,
                    total_steps=total,
                    error=result["error"],
                )
                return {"status": "failed", "steps_completed": completed, "error": result["error"]}

    await client.report_run_status(
        run_id,
        status="success",
        steps_completed=completed,
        total_steps=total,
        extracted_data=extracted_data,
    )
    return {"status": "success", "steps_completed": completed, "extracted_data": extracted_data}
