"""Retry policy executor with backoff strategies."""
import asyncio
from typing import Awaitable, Callable, TypeVar

from app.automation.models import RetryPolicy

T = TypeVar("T")


def _compute_delay_ms(attempt_idx: int, policy: RetryPolicy) -> int:
    """`attempt_idx` is 1-based for the NEXT retry (the delay before attempt N+1)."""
    base = policy.initial_delay_ms
    if policy.backoff == "fixed":
        return base
    if policy.backoff == "linear":
        return min(base * attempt_idx, policy.max_delay_ms)
    if policy.backoff == "exponential":
        return min(base * (2 ** (attempt_idx - 1)), policy.max_delay_ms)
    return base


async def with_retry(op: Callable[[], Awaitable[T]], policy: RetryPolicy | None) -> T:
    """Call op() up to policy.attempts times with backoff. Raise last exception on giveup.

    When `policy` is None the operation runs exactly once (no retry).
    """
    attempts = policy.attempts if policy else 1
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return await op()
        except Exception as e:
            last_exc = e
            if i == attempts:
                break
            delay_ms = _compute_delay_ms(i, policy) if policy else 0
            await asyncio.sleep(delay_ms / 1000.0)
    assert last_exc is not None
    raise last_exc
