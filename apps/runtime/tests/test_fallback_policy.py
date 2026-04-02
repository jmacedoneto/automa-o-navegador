from apps.runtime.runtime.fallback import should_pause_after_failure


def test_should_pause_after_limit():
    assert should_pause_after_failure(attempts=2, max_attempts=2) is True
