"""Smoke tests for the dispatcher wiring. The full celery integration is
exercised by running the actual task against a live worker."""
from app.automation import runner as runner_mod
from app.automation.runner import set_step_log_writer


def test_step_log_writer_is_module_level():
    """The dispatcher uses the module-level hook — verify it exists and is callable."""
    assert callable(set_step_log_writer)
    # Initially None (no run in progress).
    assert runner_mod._step_log_writer is None
    # Idempotent setter.
    def fake_writer(event):
        pass
    set_step_log_writer(fake_writer)
    assert runner_mod._step_log_writer is fake_writer
    set_step_log_writer(None)
    assert runner_mod._step_log_writer is None


def test_imports_required_modules():
    """Smoke test that the dispatcher module imports cleanly."""
    from app.workers.tasks import run_automation_v2  # noqa: F401
    from app.automation.credentials import resolve_credentials  # noqa: F401
    from app.automation.runner import NavRunner, NavRunnerConfig, set_step_log_writer  # noqa: F401
    assert callable(run_automation_v2)
    assert callable(resolve_credentials)
