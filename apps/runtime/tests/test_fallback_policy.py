from apps.runtime.runtime.fallback import should_pause_after_failure


def test_should_pause_after_limit():
    assert should_pause_after_failure(attempts=2, max_attempts=2) is True


def test_should_not_pause_when_policy_disables_pause():
    assert should_pause_after_failure(attempts=2, max_attempts=2, pause_when_failure=False) is False
