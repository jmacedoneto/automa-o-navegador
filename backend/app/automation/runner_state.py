"""Per-run state via contextvars.

P5 replacement for the module-global `_step_log_writer` so concurrent
runs in the same worker process don't cross-contaminate.

Usage:
    from app.automation.runner_state import step_log_writer_scope, emit_step_log

    with step_log_writer_scope(my_writer):
        # ... within the run ...
        emit_step_log("r-1", "s1", "running", started_at="...")
"""
from contextvars import ContextVar
from typing import Any, Callable


# Public ContextVar. Tests set it via the scope helper.
step_log_writer_var: ContextVar[Callable[[dict], None] | None] = ContextVar(
    "step_log_writer", default=None
)


class step_log_writer_scope:
    """Context manager that sets the writer for the duration of the block.

    Restores the previous value on exit (whether or not an exception was raised).
    """

    def __init__(self, writer: Callable[[dict], None]) -> None:
        self._writer = writer
        self._token = None

    def __enter__(self) -> "step_log_writer_scope":
        self._token = step_log_writer_var.set(self._writer)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            step_log_writer_var.reset(self._token)


def emit_step_log(run_id: str, step_id: str, status: str, **kwargs: Any) -> None:
    """Emit a step-log event if a writer is set in the current context.

    Best-effort: any exception is swallowed so audit never breaks the run.

    The writer is invoked with keyword arguments (matching the original
    `_emit_step_log` contract that pre-P5 callers depend on).
    """
    writer = step_log_writer_var.get()
    if writer is None:
        return
    try:
        writer(
            run_id=run_id,
            step_id=step_id,
            status=status,
            started_at=kwargs.get("started_at"),
            finished_at=kwargs.get("finished_at"),
            error=kwargs.get("error"),
            bindings=kwargs.get("bindings", {}),
            screenshot_keys=kwargs.get("screenshot_keys", []),
            screenshot_urls=kwargs.get("screenshot_urls", {}),
        )
    except Exception:
        # Audit must never fail the run.
        pass
