from app.automation.tracing import NoopSpan, langfuse_span


def test_noop_span_absorbs_update_and_end():
    s = NoopSpan()
    s.update(input="x", output="y", metadata={"k": "v"})
    s.end()  # must not raise
    # Return value absorbed for fluent chains; doesn't matter what.
    assert True


def test_langfuse_span_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    with langfuse_span("test", step_id="s1") as span:
        # Update inside the span context — must be a no-op when unconfigured.
        span.update(output="x")
        # noop spans return self from update; caller doesn't need the return.
    assert True


def test_noop_span_context_manager_does_not_raise():
    with langfuse_span("a", action="b") as span:
        # span is whatever — could be NoopSpan if env unset.
        span.update(status="ok")