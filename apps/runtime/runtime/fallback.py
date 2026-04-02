def should_pause_after_failure(attempts: int, max_attempts: int) -> bool:
    return attempts >= max_attempts
