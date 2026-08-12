import re
from collections.abc import Iterable


DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"

# Free-tier mini models (2.5 million tokens/day)
_MINI_TIER: tuple[str, ...] = (
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.1-codex-mini",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o-mini",
    "o1-mini",
    "o3-mini",
    "o4-mini",
    "codex-mini-latest",
)

# Free-tier standard models (250 thousand tokens/day)
_STANDARD_TIER: tuple[str, ...] = (
    "gpt-5.4",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5",
    "gpt-5-codex",
    "gpt-5-chat-latest",
    "gpt-4.1",
    "gpt-4o",
    "o1",
    "o3",
)

ALLOWED_OPENAI_MODELS: tuple[str, ...] = _MINI_TIER + _STANDARD_TIER


def canonicalize_openai_model(model: str | None) -> str:
    """Normalize any model name variant to its clean base alias.

    Handles:
    - Underscore separators:  gpt-5_4-mini  →  gpt-5.4-mini
    - Dated snapshots:        gpt-5.4-mini-2026-03-17  →  gpt-5.4-mini
    """
    normalized = (model or "").strip()
    if not normalized:
        return DEFAULT_OPENAI_MODEL
    # gpt-X_Y  →  gpt-X.Y  (any version, e.g. gpt-5_4, gpt-4_1, gpt-4_o)
    normalized = re.sub(r"(gpt-\d+)_(\d+)", r"\1.\2", normalized)
    # strip dated snapshot suffix  -YYYY-MM-DD
    normalized = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", normalized)
    return normalized


def is_allowed_openai_model(model: str | None) -> bool:
    return canonicalize_openai_model(model) in ALLOWED_OPENAI_MODELS


def coerce_openai_model(model: str | None) -> str:
    normalized = canonicalize_openai_model(model)
    if normalized in ALLOWED_OPENAI_MODELS:
        return normalized
    return DEFAULT_OPENAI_MODEL


def normalize_openai_model(model: str | None) -> str:
    return coerce_openai_model(model)


def filter_allowed_openai_models(models: Iterable[str]) -> list[str]:
    available = {canonicalize_openai_model(m) for m in models}
    return [m for m in ALLOWED_OPENAI_MODELS if m in available]
