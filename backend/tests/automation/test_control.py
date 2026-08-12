import asyncio
import pytest

from app.automation.control import run_for_each, run_if, _eval_condition
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_for_each_iterates_items_calls_visit():
    page = object()
    visited = []
    async def visit(ctx, item):
        visited.append(item)
    ctx = RunContext()
    spec = {"items": [1, 2, 3], "as": "n", "steps": []}
    _run(run_for_each(page, spec, ctx, _visit=visit))
    assert visited == [1, 2, 3]


def test_for_each_binds_item_in_context():
    page = object()
    seen_items = []
    async def visit(ctx, item):
        seen_items.append(ctx.bindings["x"])
    ctx = RunContext()
    spec = {"items": ["a", "b"], "as": "x", "steps": []}
    _run(run_for_each(page, spec, ctx, _visit=visit))
    assert seen_items == ["a", "b"]


def test_for_each_provides_loop_index():
    page = object()
    seen_indices = []
    async def visit(ctx, item):
        seen_indices.append(ctx.bindings.get("loop", {}).get("index"))
    ctx = RunContext()
    spec = {"items": ["a", "b", "c"], "as": "x", "steps": []}
    _run(run_for_each(page, spec, ctx, _visit=visit))
    assert seen_indices == [1, 2, 3]


def test_for_each_max_iterations_cap():
    page = object()
    visited = []
    async def visit(ctx, item):
        visited.append(item)
    ctx = RunContext()
    spec = {"items": list(range(100)), "as": "x", "max_iterations": 5, "steps": []}
    with pytest.raises(ValueError, match="cap is 5"):
        _run(run_for_each(page, spec, ctx, _visit=visit))


def test_for_each_missing_keys_raises():
    page = object()
    ctx = RunContext()
    with pytest.raises(ValueError, match="requires"):
        _run(run_for_each(page, {"items": []}, ctx, _visit=lambda c, i: None))


def test_for_each_interpolates_string_items():
    """String items in `items` go through interpolate() before iteration."""
    page = object()
    seen = []
    async def visit(ctx, item):
        seen.append(item)
    ctx = RunContext(inputs={"faixas": [100, 200, 300]})
    spec = {"items": "{{input.faixas}}", "as": "f", "steps": []}
    _run(run_for_each(page, spec, ctx, _visit=visit))
    assert seen == [100, 200, 300]


def test_if_then_runs_when_equal():
    page = object()
    then_calls = []
    else_calls = []
    async def then_step(ctx, step):
        then_calls.append(step)
    async def else_step(ctx, step):
        else_calls.append(step)
    ctx = RunContext(inputs={"x": 5})
    spec = {"condition": "{{input.x}} == 5", "then_steps": [{"id": "t"}], "else_steps": [{"id": "e"}]}
    _run(run_if(page, spec, ctx, _then=then_step, _else=else_step))
    assert len(then_calls) == 1
    assert len(else_calls) == 0


def test_if_else_runs_when_not_equal():
    page = object()
    then_calls = []
    else_calls = []
    async def then_step(ctx, step):
        then_calls.append(step)
    async def else_step(ctx, step):
        else_calls.append(step)
    ctx = RunContext(inputs={"x": 5})
    spec = {"condition": "{{input.x}} != 5", "then_steps": [{"id": "t"}], "else_steps": [{"id": "e"}]}
    _run(run_if(page, spec, ctx, _then=then_step, _else=else_step))
    assert len(then_calls) == 0
    assert len(else_calls) == 1


def test_if_comparison_operators():
    assert _eval_condition("5 == 5") is True
    assert _eval_condition("5 != 6") is True
    assert _eval_condition("5 < 6") is True
    assert _eval_condition("5 <= 5") is True
    assert _eval_condition("5 > 4") is True
    assert _eval_condition("5 >= 5") is True
    assert _eval_condition("5 == 6") is False


def test_if_bool_operators():
    assert _eval_condition("True and True") is True
    assert _eval_condition("True and False") is False
    assert _eval_condition("False or True") is True
    assert _eval_condition("not True") is False
    assert _eval_condition("not False") is True


def test_if_invalid_expression_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        _eval_condition("1 ** 2")
    with pytest.raises(ValueError, match="Unsupported"):
        _eval_condition("foo.bar()")
