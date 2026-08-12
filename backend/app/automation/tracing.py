"""Langfuse span helper.

P0: noop path. P1a: activates the real Langfuse SDK when LANGFUSE_PUBLIC_KEY,
LANGFUSE_SECRET_KEY, and LANGFUSE_HOST are all set. Otherwise stays noop so
the worker can run without tracing.
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


class _LangfuseSpan:
    """Thin wrapper around the Langfuse SDK span so the call site matches
    NoopSpan's interface (update(**kwargs), end())."""
    def __init__(self, sdk_span: Any) -> None:
        self._sdk_span = sdk_span

    def update(self, **kwargs: Any) -> None:
        # The real SDK method name varies by version. Try the most common.
        for method_name in ("update", "set_output", "set_input"):
            fn = getattr(self._sdk_span, method_name, None)
            if callable(fn):
                try:
                    if method_name == "update":
                        fn(**kwargs)
                    else:
                        fn(kwargs)
                    return
                except Exception:
                    continue

    def end(self) -> None:
        try:
            self._sdk_span.end()
        except Exception:
            pass


def _langfuse_configured() -> bool:
    return all([
        os.environ.get("LANGFUSE_PUBLIC_KEY"),
        os.environ.get("LANGFUSE_SECRET_KEY"),
        os.environ.get("LANGFUSE_HOST"),
    ])


@contextmanager
def langfuse_span(name: str, **attrs: Any):
    """Returns a context manager yielding a span.

    Real Langfuse SDK when LANGFUSE_* env vars are all set; otherwise NoopSpan.
    Falls back to NoopSpan if the SDK import or init fails.
    """
    if not _langfuse_configured():
        with _noop(name, attrs) as span:
            yield span
        return

    try:
        from langfuse import Langfuse
        client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
        )
        with client.span(name=name, **attrs) as sdk_span:
            yield _LangfuseSpan(sdk_span)
    except Exception:
        # Fail closed to noop rather than crash the run.
        with _noop(name, attrs) as span:
            yield span


@contextmanager
def _noop(name: str, attrs: dict[str, Any]):
    span = NoopSpan()
    try:
        yield span
    finally:
        span.end()
