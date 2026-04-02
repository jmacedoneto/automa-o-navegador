def should_pause_after_failure(
    attempts: int,
    max_attempts: int,
    pause_when_failure: bool = True,
) -> bool:
    return pause_when_failure and attempts >= max_attempts
