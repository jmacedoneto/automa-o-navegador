def build_run_summary(steps_completed: int, total_steps: int, status: str) -> dict:
    return {
        "steps_completed": steps_completed,
        "total_steps": total_steps,
        "status": status,
    }
