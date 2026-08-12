"""NavRunner — orchestrates Playwright + interpreter + storage + tracing."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from playwright.async_api import async_playwright, Page

from app.automation.auth import AuthSpec, run_auth
from app.automation.interpreter import execute_step
from app.automation.models import RunContext, Step
from app.automation.storage import build_screenshot_key, upload_to_minio
from app.automation.tracing import langfuse_span
from app.automation.runner_state import (
    emit_step_log as _emit_step_log,
    step_log_writer_var,
)


# Backward-compat shim — pre-P5 callers (and existing tests) import
# `set_step_log_writer` / `_step_log_writer` from this module. Internally,
# writes go through a `contextvars.ContextVar` so concurrent runs in the
# same worker process are isolated. Production code should use
# `step_log_writer_scope` from runner_state directly.
_step_log_writer: Callable[[dict], None] | None = None


def set_step_log_writer(writer: Callable[[dict], None] | None) -> None:
    """Wire (or clear) the step-log writer. Idempotent within a context.

    DEPRECATED: prefer `step_log_writer_scope` from `runner_state`. This
    shim remains so legacy imports keep working, and synchronizes both the
    module global and the ContextVar for the current context.
    """
    global _step_log_writer
    _step_log_writer = writer
    if writer is None:
        step_log_writer_var.set(None)
    else:
        step_log_writer_var.set(writer)


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
    screenshot_urls: dict[str, str] = field(default_factory=dict)  # phase -> presigned URL
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
        credentials: dict[str, Any] | None = None,
        auth: "AuthSpec | None" = None,
    ) -> RunResult:
        """P0 entry point: walk steps, capture per-step screenshots, return RunResult.

        `credentials` populates `RunContext.credentials` so the auth step can
        resolve `credentials_ref` lookups. None (default) leaves it empty.
        """
        steps = list(steps)
        ctx = RunContext(inputs=inputs, bindings={}, credentials=credentials or {})
        result = RunResult(status="success", run_id=self.cfg.run_id)
        self._page = None
        self._current_result = result
        Path(self.cfg.screenshot_dir).mkdir(parents=True, exist_ok=True)

        pw, browser = await _connect_playwright(self.cfg.browser_endpoint)
        page = await browser.new_page()
        self._page = page
        result.page = page
        if auth is not None:
            await run_auth(page, spec=auth, ctx=ctx)
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
            self._page = None
            self._current_result = None
        return result

    async def _capture_screenshot(
        self,
        page: Page,
        step_id: str,
        phase: str,
        result: RunResult,
    ) -> None:
        """Write screenshot to local disk; upload to MinIO when configured.

        Failures anywhere are non-fatal — the on-disk file is the fallback.
        """
        key = build_screenshot_key(self.cfg.run_id, step_id, phase)
        local = Path(self.cfg.screenshot_dir) / Path(key).name
        try:
            await page.screenshot(path=str(local))
        except Exception:
            return
        result.screenshot_keys.append(key)
        try:
            url = upload_to_minio(local, self.cfg.run_id, step_id, phase)
            if url:
                result.screenshot_urls[phase] = url
        except Exception:
            pass

    async def _run_one_inner(self, page: Page, step: Step, ctx: RunContext, result: RunResult) -> None:
        """Like _run_one but without the per-step wrapper — used by _visit_child."""
        started_at = datetime.now(timezone.utc)
        _emit_step_log(
            self.cfg.run_id, step.id, "running",
            started_at=started_at.isoformat(),
        )
        with langfuse_span("navrunner.step", step_id=step.id, action=step.action):
            try:
                await execute_step(page, step, ctx, on_visit_child=self._visit_child)
                await self._capture_screenshot(page, step.id, "after", result)
                _emit_step_log(
                    self.cfg.run_id, step.id, "ok",
                    started_at=started_at.isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    bindings=dict(ctx.bindings),
                    screenshot_keys=list(result.screenshot_keys),
                    screenshot_urls=dict(result.screenshot_urls),
                )
            except Exception as e:
                err = f"{step.id}: {type(e).__name__}: {e}"
                result.errors.append(err)
                _emit_step_log(
                    self.cfg.run_id, step.id, "failed",
                    started_at=started_at.isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=err,
                    bindings=dict(ctx.bindings),
                    screenshot_keys=list(result.screenshot_keys),
                    screenshot_urls=dict(result.screenshot_urls),
                )
                await self._capture_screenshot(page, step.id, "on_fail", result)
                raise

    async def _visit_child(self, ctx: RunContext, child: Any) -> None:
        """Run a single child step inside a for_each / if branch."""
        if isinstance(child, dict):
            step = Step.from_dict(child)
        elif isinstance(child, Step):
            step = child
        else:
            raise ValueError(f"Unexpected child type: {type(child).__name__}")

        page = getattr(self, "_page", None)
        if page is None:
            raise RuntimeError(
                "_visit_child called before run_steps initialized the page; "
                "this is a bug."
            )
        result = getattr(self, "_current_result", None)
        if result is None:
            raise RuntimeError("_visit_child needs an active result context")
        await self._run_one_inner(page, step, ctx, result)

    async def _run_one(self, page: Page, step: Step, ctx: RunContext, result: RunResult) -> None:
        started_at = datetime.now(timezone.utc)
        _emit_step_log(
            self.cfg.run_id, step.id, "running",
            started_at=started_at.isoformat(),
        )
        with langfuse_span("navrunner.step", step_id=step.id, action=step.action):
            try:
                await execute_step(page, step, ctx, on_visit_child=self._visit_child)
                await self._capture_screenshot(page, step.id, "after", result)
                _emit_step_log(
                    self.cfg.run_id, step.id, "ok",
                    started_at=started_at.isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    bindings=dict(ctx.bindings),
                    screenshot_keys=list(result.screenshot_keys),
                    screenshot_urls=dict(result.screenshot_urls),
                )
            except Exception as e:
                err = f"{step.id}: {type(e).__name__}: {e}"
                result.errors.append(err)
                _emit_step_log(
                    self.cfg.run_id, step.id, "failed",
                    started_at=started_at.isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=err,
                    bindings=dict(ctx.bindings),
                    screenshot_keys=list(result.screenshot_keys),
                    screenshot_urls=dict(result.screenshot_urls),
                )
                await self._capture_screenshot(page, step.id, "on_fail", result)
                raise
