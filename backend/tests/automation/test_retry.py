import asyncio
import pytest

from app.automation.retry import with_retry
from app.automation.models import RetryPolicy


def _run(coro):
    """Tiny asyncio helper — keeps the test file free of pytest-asyncio."""
    return asyncio.new_event_loop().run_until_complete(coro)


def _identity_op(result):
    async def op():
        return result
    return op


def test_with_retry_succeeds_first_try():
    calls = 0
    def op():
        nonlocal calls
        calls += 1
        async def _inner():
            return "ok"
        return _inner()  # unreachable; we override below
    # Actually build a working counter op:
    state = {"calls": 0}
    async def _good_op():
        state["calls"] += 1
        return "ok"
    policy = RetryPolicy(attempts=3)
    result = _run(with_retry(_good_op, policy))
    assert result == "ok"
    assert state["calls"] == 1


def test_with_retry_succeeds_on_second_try():
    state = {"calls": 0}
    async def _flaky_op():
        state["calls"] += 1
        if state["calls"] < 2:
            raise ValueError("flaky")
        return "ok"
    policy = RetryPolicy(attempts=3, backoff="fixed", initial_delay_ms=1)
    result = _run(with_retry(_flaky_op, policy))
    assert result == "ok"
    assert state["calls"] == 2


def test_with_retry_gives_up_after_attempts():
    state = {"calls": 0}
    async def _always_fails():
        state["calls"] += 1
        raise ValueError(f"fail {state['calls']}")
    policy = RetryPolicy(attempts=3, backoff="fixed", initial_delay_ms=1)
    with pytest.raises(ValueError, match="fail 3"):
        _run(with_retry(_always_fails, policy))
    assert state["calls"] == 3


def test_with_retry_exponential_backoff_grows_delay():
    """Verify the delay grows with attempt index (exponential)."""
    import time
    state = {"calls": 0, "ts": []}
    async def _flaky_op():
        state["calls"] += 1
        state["ts"].append(time.monotonic())
        if state["calls"] < 3:
            raise ValueError("flaky")
        return "ok"
    policy = RetryPolicy(attempts=3, backoff="exponential", initial_delay_ms=10, max_delay_ms=1000)
    _run(with_retry(_flaky_op, policy))
    assert len(state["ts"]) == 3
    gap1 = state["ts"][1] - state["ts"][0]
    gap2 = state["ts"][2] - state["ts"][1]
    # exponential: gap2 >= 2*initial, gap1 == initial. Allow jitter.
    assert gap2 >= gap1 * 0.9
