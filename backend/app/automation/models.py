"""Core data types for NavRunner DSL."""
from dataclasses import dataclass, field
from typing import Any, Optional


# When a step's action is given a bare string, wrap it under a semantic key.
# Example: `{"goto": "https://x"}` -> params = {"url": "https://x"}.
_BARE_STRING_KEYS: dict[str, str] = {
    "goto": "url",
    "click": "selector",
    "wait_for": "selector",
    "assert": "text",
}


@dataclass
class RetryPolicy:
    attempts: int = 1
    backoff: str = "fixed"
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    on_fail: str = "abort"
    retry_if: str = "any_error"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Optional["RetryPolicy"]:
        if d is None:
            return None
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


@dataclass
class Step:
    id: str
    action: str
    params: dict[str, Any]
    retry: Optional[RetryPolicy] = None
    bind: Optional[str] = None
    timeout_ms: int = 30000

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Step":
        ACTION_KEYS = {"goto", "click", "fill", "wait_for", "assert", "run_ai",
                       "run_python", "for_each", "if", "reload", "go_back",
                       "extract_text", "extract_table", "screenshot"}
        META_KEYS = {"id", "retry", "bind", "timeout_ms", "pre_hook", "post_hook"}
        meta = {k: raw[k] for k in META_KEYS if k in raw}
        action_keys = [k for k in raw if k in ACTION_KEYS]
        if len(action_keys) != 1:
            raise ValueError(f"Step must have exactly one action key, got {action_keys} in {raw}")
        action = action_keys[0]
        params = raw[action]
        if not isinstance(params, dict):
            key = _BARE_STRING_KEYS.get(action, "value")
            params = {key: params}
        if "retry" in raw:
            meta["retry"] = RetryPolicy.from_dict(raw["retry"])
        return cls(action=action, params=params, **meta)


@dataclass
class RunContext:
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
        return _walk(self.bindings, [head, *rest], default)


def _walk(obj: Any, path: list[str], default: Any) -> Any:
    cur: Any = obj
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur
