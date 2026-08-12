"""NavRunner — orchestrates Playwright + interpreter + storage + tracing."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from playwright.async_api import async_playwright, Page

from app.automation.interpreter import execute_step
from app.automation.models import RunContext, Step
from app.automation.storage import build_screenshot_key
from app.automation.tracing import langfuse_span


@dataclass
class NavRunnerConfig:
    browser_endpoint: str             # Browserless WebSocket URL (ws://...)
    run_id: str
    screenshot_dir: str = ""          # empty => defaults to OS temp /navrunner-shots
    minio_endpoint: str = ""          # P1 — empty in P0
    capture_screenshot_per_step: bool = True


@dataclass
class RunResult:
    status: str                       # "success" | "failed" | "partial"
    run_id: str
    bindings: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    screenshot_keys: list[str] = field(default_factory=list)
    page: Any = None                  # exposed for tests; do not use in production code
    trace_id: str | None = None


async def _connect_playwright(endpoint: str):
    """Returns (playwright_instance, browser). Imported lazily in run_steps so
    tests can monkeypatch this hook without spinning up real Chrome."""
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(endpoint)
    return pw, browser


class NavRunner:
    def __init__(self, cfg: NavRunnerConfig) -> None:
        self.cfg = cfg
        if cfg.screenshot_dir == "":
            cfg.screenshot_dir = os.path.join(tempfile.gettempdir(), "navrunner-shots")

    async def run_steps(
        self,
        steps: Iterable[Step],
        inputs: dict[str, Any],
    ) -> RunResult:
        """P0 entry point: walk steps, capture per-step screenshots, return RunResult.

        P0 deliberately does NOT touch Supabase, the real Langfuse SDK, or MinIO
        upload — those land in P1.
        """
        steps = list(steps)
        ctx = RunContext(inputs=inputs, bindings={})
        result = RunResult(status="success", run_id=self.cfg.run_id)
        Path(self.cfg.screenshot_dir).mkdir(parents=True, exist_ok=True)

        pw, browser = await _connect_playwright(self.cfg.browser_endpoint)
        page = await browser.new_page()
        result.page = page
        try:
            with langfuse_span("navrunner.run", run_id=self.cfg.run_id, steps=len(steps)):
                for step in steps:
                    try:
                        await self._run_one(page, step, ctx, result)
                    except Exception:
                        # P0 default: on_fail=abort — stop on first failure.
                        # Future: honor step.retry.on_fail (skip_continue, alert, ...).
                        break
            # P0 honors only `on_fail=abort`. The "partial" branch lands in P1
            # once RetryPolicy.on_fail actually drives step-level continue/stop.
            result.status = "success" if not result.errors else "failed"
        finally:
            await browser.close()
            await pw.stop()
        return result

    async def _run_one(self, page: Page, step: Step, ctx: RunContext, result: RunResult) -> None:
        with langfuse_span("navrunner.step", step_id=step.id, action=step.action):
            try:
                await execute_step(page, step, ctx)
                if self.cfg.capture_screenshot_per_step:
                    key = build_screenshot_key(self.cfg.run_id, step.id, "after")
                    local = Path(self.cfg.screenshot_dir) / Path(key).name
                    await page.screenshot(path=str(local))
                    result.screenshot_keys.append(key)
            except Exception as e:
                err = f"{step.id}: {type(e).__name__}: {e}"
                result.errors.append(err)
                # Always capture on_fail screenshot, best-effort.
                try:
                    fail_key = build_screenshot_key(self.cfg.run_id, step.id, "on_fail")
                    local = Path(self.cfg.screenshot_dir) / Path(fail_key).name
                    await page.screenshot(path=str(local))
                    result.screenshot_keys.append(fail_key)
                except Exception:
                    pass
                raise
