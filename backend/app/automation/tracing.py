"""Langfuse span helper.

P0 implements the no-op path so the runner can run before tracing is wired
up. When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` + `LANGFUSE_HOST`
are all set, the real SDK branch (deferred to P1) would activate.
"""
import os
from contextlib import contextmanager
from typing import Any


class NoopSpan:
    """Span-like object that absorbs all calls without side-effects."""

    def update(self, **kwargs: Any) -> None:
        return None

    def end(self) -> None:
        return None


@contextmanager
def langfuse_span(name: str, **attrs: Any):
    """Returns a context manager yielding a span.

    P0: always yields a NoopSpan. Real Langfuse SDK integration lands in P1.
    """
    with _noop(name, attrs) as span:
        yield span


@contextmanager
def _noop(name: str, attrs: dict[str, Any]):
    span = NoopSpan()
    try:
        yield span
    finally:
        span.end()