from app.automation.models import Step, RetryPolicy, RunContext


def test_step_parses_minimal_goto():
    step = Step.from_dict({"id": "open", "goto": "https://example.com"})
    assert step.id == "open"
    assert step.action == "goto"
    assert step.params == {"url": "https://example.com"}
    assert step.retry is None


def test_step_parses_with_retry():
    step = Step.from_dict({
        "id": "submit",
        "click": {"selector": "button#ok"},
        "retry": {"attempts": 3, "on_fail": "skip_continue"}
    })
    assert step.action == "click"
    assert step.retry is not None
    assert step.retry.attempts == 3
    assert step.retry.on_fail == "skip_continue"


def test_run_context_stores_bindings():
    ctx = RunContext(inputs={"x": 1}, bindings={})
    ctx.set_binding("y", 42)
    assert ctx.bindings == {"y": 42}
    assert ctx.get("input.x") == 1
    assert ctx.get("y") == 42
    assert ctx.get("missing", default="d") == "d"


def test_run_context_nested_get():
    ctx = RunContext(inputs={"cliente": {"nome": "Ana"}}, bindings={"r": {"valor": 100}})
    assert ctx.get("input.cliente.nome") == "Ana"
    assert ctx.get("r.valor") == 100


def test_run_context_bare_name_falls_back_to_inputs():
    """Bare `{{name}}` resolves to inputs first, then bindings."""
    ctx = RunContext(inputs={"a": 1}, bindings={"b": 2})
    assert ctx.get("a") == 1      # inputs
    assert ctx.get("b") == 2      # bindings
    assert ctx.get("missing") is None  # default


def test_run_context_bare_name_inputs_wins_over_bindings():
    """If the same key exists in both inputs and bindings, inputs wins."""
    ctx = RunContext(inputs={"x": "from-inputs"}, bindings={"x": "from-bindings"})
    assert ctx.get("x") == "from-inputs"
