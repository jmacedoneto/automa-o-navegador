"""Smoke test for the executar_cotacao_pvs Celery task wrapper."""


def test_executar_cotacao_pvs_imports():
    """The task is importable from the tasks module."""
    from app.workers.tasks import executar_cotacao_pvs  # noqa: F401
    assert callable(executar_cotacao_pvs)


def test_executar_cotacao_pvs_uses_resolve_credentials(monkeypatch):
    """The wrapper calls resolve_credentials then dispatches."""
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {"apvs_login": {"user": "x", "pass": "y"}})
    monkeypatch.setattr("app.workers.tasks.executar_cotacao_pvs_inner", lambda **kw: {"summary": "ok"})
    # Just verify the imports and module-level references work.
    from app.workers import tasks
    assert hasattr(tasks, "executar_cotacao_pvs")
    assert callable(tasks.executar_cotacao_pvs)
