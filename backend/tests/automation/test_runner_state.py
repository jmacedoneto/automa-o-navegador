import asyncio
from contextvars import copy_context
from unittest.mock import MagicMock

from app.automation.runner_state import (
    step_log_writer_var,
    step_log_writer_scope,
    emit_step_log,
)


def test_context_var_default_is_none():
    assert step_log_writer_var.get() is None


def test_step_log_writer_scope_sets_writer():
    writer = MagicMock()
    with step_log_writer_scope(writer):
        assert step_log_writer_var.get() is writer
        emit_step_log("r-1", "s1", "running", started_at="2026-08-12T00:00:00")
        writer.assert_called_once()
    assert step_log_writer_var.get() is None


def test_outside_scope_writes_are_silent():
    writer = MagicMock()
    emit_step_log("r-1", "s1", "running")
    writer.assert_not_called()


def test_concurrent_scopes_are_isolated():
    """Two contexts with different writers see different writers."""
    writer_a = MagicMock()
    writer_b = MagicMock()

    results = {}

    def run_a():
        with step_log_writer_scope(writer_a):
            emit_step_log("r-a", "s1", "running")
            results["a"] = step_log_writer_var.get()

    def run_b():
        with step_log_writer_scope(writer_b):
            emit_step_log("r-b", "s1", "running")
            results["b"] = step_log_writer_var.get()

    run_a()
    run_b()
    assert results["a"] is writer_a
    assert results["b"] is writer_b
    assert writer_a.call_args.kwargs["run_id"] == "r-a"
    assert writer_b.call_args.kwargs["run_id"] == "r-b"
