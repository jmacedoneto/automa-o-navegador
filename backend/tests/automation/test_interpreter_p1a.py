import asyncio

from app.automation.interpreter import execute_step
from app.automation.models import Step, RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_interpreter_dispatches_extract_text():
    page = type("P", (), {})()
    captured = {}
    class _Loc:
        @property
        def first(self):
            return self
        async def text_content(self):
            captured["text"] = "R$ 100"
            return "R$ 100"
    page.locator = lambda sel: _Loc()
    step = Step.from_dict({"id": "x", "extract_text": {"selector": ".v", "bind": "preco"}})
    ctx = RunContext()
    _run(execute_step(page, step, ctx))
    assert captured["text"] == "R$ 100"
    assert ctx.bindings["preco"] == "R$ 100"


def test_interpreter_dispatches_run_python():
    page = object()
    step = Step.from_dict({"id": "calc", "run_python": {"value": "1 + 2", "bind": "sum"}})
    ctx = RunContext()
    _run(execute_step(page, step, ctx))
    assert ctx.bindings["sum"] == 3


def test_interpreter_dispatches_screenshot(tmp_path):
    target = tmp_path / "shot.png"
    page = type("P", (), {})()
    async def screenshot(**kw):
        Path_ = type("Path", (), {"write_bytes": lambda self, data: open(self.path, "wb").write(data) and True or True})()
        # Custom fake: write the path with a mock bytes via the impl reading kwargs["path"]
        # The impl will call await page.screenshot(path=path). Our fake just opens the file.
        return open(kw["path"], "wb").write(b"PNG")
    # Make Path_ usable — actually a simpler fake:
    class _P:
        async def screenshot(self, **kw):
            open(kw["path"], "wb").write(b"PNG")
            return b"PNG"
    page = _P()
    step = Step.from_dict({"id": "shot", "screenshot": {"path": str(target)}})
    _run(execute_step(page, step, RunContext()))
    assert target.exists()


def test_step_from_dict_for_each():
    raw = {
        "id": "loop",
        "for_each": {
            "items": [1, 2, 3],
            "as": "n",
            "steps": [{"id": "visit", "run_python": {"value": "pass"}}],
        },
    }
    step = Step.from_dict(raw)
    assert step.action == "for_each"
    assert step.params["items"] == [1, 2, 3]
    assert step.params["as"] == "n"


def test_step_from_dict_if():
    raw = {
        "id": "branch",
        "if": {
            "condition": "{{input.x}} == 5",
            "then_steps": [{"id": "t", "run_python": {"value": "pass"}}],
            "else_steps": [],
        },
    }
    step = Step.from_dict(raw)
    assert step.action == "if"
    assert step.params["condition"] == "{{input.x}} == 5"


def test_interpreter_for_each_invokes_visit_callback():
    page = object()
    step = Step.from_dict({"id": "loop", "for_each": {"items": [1, 2], "as": "x", "steps": [{"id": "child"}]}})
    visited = []
    async def visit(ctx, child):
        visited.append(ctx.bindings["x"])
    ctx = RunContext()
    _run(execute_step(page, step, ctx, on_visit_child=visit))
    assert visited == [1, 2]


def test_interpreter_for_each_without_visit_callback_raises():
    page = object()
    step = Step.from_dict({"id": "loop", "for_each": {"items": [1], "as": "x", "steps": []}})
    ctx = RunContext()
    with __import__("pytest").raises(ValueError, match="for_each"):
        _run(execute_step(page, step, ctx))


def test_interpreter_if_invokes_then_callback():
    page = object()
    step = Step.from_dict({"id": "branch", "if": {"condition": "1 == 1", "then_steps": [{"id": "t"}]}})
    then_calls = []
    async def visit(ctx, item):
        then_calls.append(item)
    ctx = RunContext()
    _run(execute_step(page, step, ctx, on_visit_child=visit))
    assert len(then_calls) == 1


def test_interpreter_unknown_action_raises():
    page = object()
    step = Step(id="s1", action="frobnicate", params={})
    with __import__("pytest").raises(NotImplementedError, match="frobnicate"):
        _run(execute_step(page, step, RunContext()))
