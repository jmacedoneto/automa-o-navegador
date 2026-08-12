"""Control flow handlers — for_each, if."""
import ast
from typing import Any, Callable

from app.automation.bindings import interpolate
from app.automation.models import RunContext


def _resolve_items(items_spec: Any, ctx: RunContext) -> list[Any]:
    """Return a list to iterate. Accepts a list literal or a template string.

    For template strings, we bypass `interpolate`'s stringification: a marker
    that resolves to a list should stay a list. This keeps `bindings.py`
    untouched (other handlers rely on stringification for selectors).
    """
    if isinstance(items_spec, list):
        return items_spec
    if isinstance(items_spec, str):
        # Look for a single {{...}} marker and resolve it directly.
        import re
        m = re.fullmatch(r"\{\{\s*([\w.]+)\s*\}\}", items_spec)
        if m:
            resolved = ctx.get(m.group(1), default=None)
            if isinstance(resolved, list):
                return resolved
            if resolved is None:
                return []
            return [resolved]
        # Mixed-text template — fall back to interpolate and wrap.
        resolved = interpolate(items_spec, ctx)
        if isinstance(resolved, list):
            return resolved
        return [resolved]
    raise ValueError(f"for_each items must be a list or string, got {type(items_spec).__name__}")


def _max_iterations(spec: dict[str, Any]) -> int:
    return int(spec.get("max_iterations", 50))


_ALLOWED_BINOPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


def _eval_condition(expr: str) -> bool:
    """Evaluate a tiny expression DSL: ==, !=, <, <=, >, >=, and, or, not, literals."""
    if not isinstance(expr, str):
        raise ValueError(f"condition must be a string, got {type(expr).__name__}")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid condition expression {expr!r}: {e}")
    return bool(_eval_node(tree.body))


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        raise ValueError(f"Unsupported name in condition: {node.id!r}")
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise ValueError("Chained comparisons not allowed in condition")
        if type(node.ops[0]) not in _ALLOWED_BINOPS:
            raise ValueError(f"Unsupported operator: {type(node.ops[0]).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.comparators[0])
        return _ALLOWED_BINOPS[type(node.ops[0])](left, right)
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


async def run_for_each(
    page: Any,
    spec: dict[str, Any],
    ctx: RunContext,
    _visit: Callable[[RunContext, Any], Any],
) -> None:
    """Iterate over `items`, calling _visit per item with the iteration value bound.

    The dispatcher passes `_visit` (a callable that runs a single child step
    with the current item bound). `for_each` itself only manages the loop,
    the bindings (`as` + `loop`), and the max_iterations safety cap.
    """
    if not isinstance(spec, dict) or "items" not in spec or "as" not in spec:
        raise ValueError("for_each spec requires 'items' and 'as' keys")
    items = _resolve_items(spec["items"], ctx)
    binding_name = spec["as"]
    cap = _max_iterations(spec)
    if len(items) > cap:
        raise ValueError(f"for_each would iterate {len(items)} items, cap is {cap}")
    for idx, item in enumerate(items, start=1):
        ctx.bindings[binding_name] = item
        ctx.bindings["loop"] = {"index": idx, "total": len(items)}
        try:
            for child in spec.get("steps", []):
                await _visit(ctx, child)
        finally:
            ctx.bindings.pop(binding_name, None)
            ctx.bindings.pop("loop", None)


async def run_if(
    page: Any,
    spec: dict[str, Any],
    ctx: RunContext,
    _then: Callable[[RunContext, Any], Any],
    _else: Callable[[RunContext, Any], Any] | None = None,
) -> None:
    """Run then_steps if condition is true, else_steps otherwise."""
    if "condition" not in spec:
        raise ValueError("if spec requires 'condition' key")
    cond_raw = interpolate(spec["condition"], ctx)
    if not isinstance(cond_raw, str):
        raise ValueError(f"if condition must interpolate to a string, got {type(cond_raw).__name__}")
    cond = _eval_condition(cond_raw)
    if cond:
        for step in spec.get("then_steps", []):
            await _then(ctx, step)
    elif _else is not None:
        for step in spec.get("else_steps", []):
            await _else(ctx, step)
