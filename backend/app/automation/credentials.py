"""Resolve credentials for the auth block.

Sources (in order, later overrides earlier):
1. Supabase `settings` table — wide-format rows where `value` is JSON.
2. Env vars with prefix `NAVRUNNER_<KEY>_<FIELD>` (e.g. NAVRUNNER_APP_LOGIN_USER).

The dispatcher calls `resolve_credentials()` once per run and stuffs the
result into `RunContext.credentials`. Auth blocks look up by `credentials_ref`.
"""
import json
import os
from typing import Any


def _load_settings() -> dict[str, Any]:
    """Pull all rows from the `settings` table and parse `value` as JSON.

    Returns a flat dict (key -> parsed value). Imported lazily so module import
    doesn't require a live Supabase connection.
    """
    try:
        from app.core.database import get_db
        db = get_db()
        rows = db.table("settings").select("key,value").execute().data or []
    except Exception:
        # No DB available (e.g. test env). Return empty.
        return {}
    out: dict[str, Any] = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except (json.JSONDecodeError, TypeError, ValueError):
            out[r["key"]] = r["value"]
    return _flatten_settings(out)


def _flatten_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate that values are JSON-serializable primitives or dicts."""
    for k, v in settings.items():
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Unsupported setting value for {k!r}: {type(v).__name__} ({e})")
    return settings


def _env_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    """Layer env vars on top of the settings dict.

    Convention: `NAVRUNNER_<KEY>` overrides `out["key"]` flat.
    For nested overrides, use double underscore: `NAVRUNNER_APP_LOGIN__USER`
    writes to `out["app_login"]["user"]`. Single underscore within the key
    is preserved (`NAVRUNNER_EVOLUTION_API_KEY` → `out["evolution_api_key"]`).
    """
    out = dict(settings)
    for env_key, env_value in os.environ.items():
        if not env_key.startswith("NAVRUNNER_"):
            continue
        raw = env_key[len("NAVRUNNER_"):].lower()
        if "__" in raw:
            top, sub = raw.split("__", 1)
            existing = out.get(top)
            if not isinstance(existing, dict):
                existing = {}
            existing = {**existing, sub: env_value}
            out[top] = existing
        else:
            out[raw] = env_value
    return out


def resolve_credentials() -> dict[str, Any]:
    """Load credentials from settings + env overrides."""
    return _env_overrides(_load_settings())