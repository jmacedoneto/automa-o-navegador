"""Tests for the real Langfuse SDK path. The noop path is covered by test_tracing.py."""
import sys
from unittest.mock import MagicMock

from app.automation.tracing import langfuse_span


def test_langfuse_uses_real_sdk_when_env_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    fake_span = MagicMock()
    fake_span.__enter__ = MagicMock(return_value=fake_span)
    fake_span.__exit__ = MagicMock(return_value=False)
    fake_client = MagicMock()
    fake_client.span = MagicMock(return_value=fake_span)

    fake_langfuse_module = MagicMock()
    fake_langfuse_module.Langfuse = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse_module)

    with langfuse_span("run", automation_id="x") as span:
        pass

    fake_client.span.assert_called_once()
    fake_langfuse_module.Langfuse.assert_called_once()


def test_langfuse_noop_when_env_missing(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    with langfuse_span("run") as span:
        span.update(output="noop")


def test_langfuse_partial_env_falls_back_to_noop(monkeypatch):
    """Only some env vars set → still noop (no half-configured SDK call)."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    with langfuse_span("run") as span:
        span.update(output="noop")


def test_langfuse_sdk_error_falls_back_to_noop(monkeypatch):
    """If the SDK raises on init, the run still completes via noop."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")

    fake_module = MagicMock()
    fake_module.Langfuse = MagicMock(side_effect=RuntimeError("sdk broken"))
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)

    with langfuse_span("run") as span:
        span.update(output="noop")
