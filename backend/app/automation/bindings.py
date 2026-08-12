"""Template interpolation for NavRunner step params.

Resolves {{input.x}}, {{cfg.x}}, {{binding}}, {{binding.sub}} against
RunContext. Only walks into dicts, lists, and strings; everything else
passes through. Delegate the lookup to ``RunContext.get`` so this module
stays a thin wrapper.
"""
import re
from typing import Any

from app.automation.models import RunContext

_PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def interpolate(value: Any, ctx: RunContext, missing_marker: str | None = None) -> Any:
    """Walk a JSON-like value, substituting `{{...}}` strings via ``ctx.get``.

    - str   -> substitute each match; unresolved marker kept as the original
               ``{{key}}`` text unless ``missing_marker`` is provided.
    - dict  -> recurse into values.
    - list  -> recurse into items.
    - other -> returned as-is.
    """
    if isinstance(value, str):
        def replace(m: re.Match) -> str:
            key = m.group(1)
            resolved = ctx.get(key, default=None)
            if resolved is None:
                return missing_marker if missing_marker is not None else m.group(0)
            return str(resolved)
        return _PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: interpolate(v, ctx, missing_marker) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(i, ctx, missing_marker) for i in value]
    return value
