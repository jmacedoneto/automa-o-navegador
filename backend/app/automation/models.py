"""Core data types for NavRunner DSL.

Step actions live in a single registry (`_ACTIONS`). Each entry maps the
action name to the canonical param key for bare-string payloads. Actions
whose `default_key` is None MUST receive a dict payload (e.g. `for_each`,
`if`, `run_python`, `run_ai`).
"""
from dataclasses import dataclass, field
from typing import Any


# Single source of truth for step actions.
# Value = canonical param key when a bare string is given. None = dict required.
_ACTIONS: dict[str, str | None] = {
    "goto": "url",
    "click": "selector",
    "wait_for": "selector",
    "assert": "text",
    "fill": None,                    # fill requires {selector: value, ...} (dict)
    "extract_text": "selector",
    "extract_table": "selector",
    "screenshot": None,
    "reload": None,
    "go_back": None,
    "run_ai": None,
    "run_python": None,
    "for_each": None,
    "if": None,
}

_META_KEYS = {"id", "retry", "bind", "timeout_ms", "pre_hook", "post_hook"}


@dataclass
class RetryPolicy:
    """Per-step retry configuration.

    - ``attempts``: total tries (1 = no retry).
    - ``backoff``: "fixed" | "linear" | "exponential".
    - ``on_fail``: "abort" | "skip_continue" | "alert" | "run_block:<id>".
    - ``retry_if``: "selector_missing" | "timeout" | "any_error".
    """
    attempts: int = 1
    backoff: str = "fixed"
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    on_fail: str = "abort"
    retry_if: str = "any_error"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "RetryPolicy | None":
        if d is None:
            return None
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


@dataclass
class Step:
    """A single declarative step parsed from `steps.json`.

    `bind` (when set) names the slot in `RunContext.bindings` where the
    step's extracted value is stored.
    """
    id: str
    action: str
    params: dict[str, Any]
    retry: RetryPolicy | None = None
    bind: str | None = None
    timeout_ms: int = 30000
    # Forward-compat stubs. P0 ignores them; P1 will run them around the action.
    pre_hook: Any = None
    post_hook: Any = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Step":
        if raw.get("id") is None:
            raise ValueError(f"Step missing required 'id' key: {raw}")
        meta = {k: raw[k] for k in _META_KEYS if k in raw}
        action_keys = [k for k in raw if k in _ACTIONS]
        if len(action_keys) != 1:
            raise ValueError(f"Step must have exactly one action key, got {action_keys} in {raw}")
        action = action_keys[0]
        params = raw[action]
        default_key = _ACTIONS[action]
        if default_key is None and not isinstance(params, dict):
            raise ValueError(
                f"Action {action!r} requires a dict payload, got {type(params).__name__}"
            )
        if default_key is not None and not isinstance(params, dict):
            params = {default_key: params}
        if "retry" in raw:
            meta["retry"] = RetryPolicy.from_dict(raw["retry"])
        return cls(action=action, params=params, **meta)


@dataclass
class RunContext:
    """Runtime context for an automation run.

    Three scopes resolved by `get(dotted)`:
    - ``input.X``         -> ``inputs``
    - ``cfg.X``           -> ``credentials``  (DSL head is "cfg" to match user-facing markup)
    - bare ``name`` / ``name.sub`` -> ``inputs`` first, then ``bindings``
      (so a constant passed via `inputs={"a": 1}` is reachable as `{{a}}`
      without forcing callers to namespace every reference).
    """
    inputs: dict[str, Any] = field(default_factory=dict)
    bindings: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)

    def set_binding(self, name: str, value: Any) -> None:
        self.bindings[name] = value

    def get(self, dotted: str, default: Any = None) -> Any:
        parts = dotted.split(".")
        head, rest = parts[0], parts[1:]
        if head == "input":
            return _walk(self.inputs, rest, default)
        if head == "cfg":
            return _walk(self.credentials, rest, default)
        # Bare name: try inputs first, then bindings.
        if head in self.inputs:
            v = _walk(self.inputs, [head, *rest], None)
            if v is not None:
                return v
        return _walk(self.bindings, [head, *rest], default)


def _walk(obj: Any, path: list[str], default: Any) -> Any:
    cur: Any = obj
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur
