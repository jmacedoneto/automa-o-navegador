"""MinIO screenshot helpers.

P0 implements ONLY the key builder + URL formatter. Actual upload lands in
P1 when the worker integration goes in. Tests here lock in the key shape
so future test runs can assert on it without spinning MinIO.
"""
from typing import Literal

Phase = Literal["before", "after", "on_fail"]


def _flatten(s: str) -> str:
    """Replace path separators with underscores so a single key never spans >1 MinIO dir."""
    return s.replace("/", "_")


def build_screenshot_key(
    run_id: str,
    step_id: str,
    phase: Phase | str = "after",
) -> str:
    """Returns the MinIO object key for a step screenshot.

    Pattern: automation-screenshots/<run_id>/<step_id>_<phase>.png
    """
    return f"automation-screenshots/{_flatten(run_id)}/{_flatten(step_id)}_{phase}.png"


def build_screenshot_url(bucket_endpoint: str, key: str) -> str:
    """Concatenate endpoint + key, trimming trailing slash on endpoint."""
    return f"{bucket_endpoint.rstrip('/')}/{key}"