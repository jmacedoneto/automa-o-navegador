"""NavRunner — orchestrates Playwright + interpreter + storage + tracing."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from playwright.async_api import async_playwright, Page

from app.automation.interpreter import execute_step
from app.automation.models import RunContext, Step
from app.automation.storage import build_screenshot_key, upload_to_minio
from app.automation.tracing import langfuse_span


# Module-level hook; the dispatcher sets this before a run to receive step events.
# It is a plain function so we can keep the runner simple (no class hierarchy).
_step_log_writer: Callable[[dict], None] | None = None


def set_step_log_writer(writer: Callable[[dict], None] | None) -> None:
    """Wire (or clear) the step-log writer. Idempotent."""
    global _step_log_writer
    _step_log_writer = writer


def _emit_step_log(run_id: str, step_id: str, status: str, **kwargs) -> None:
    """Emit a step-log event if a writer is wired. Best-effort: never raises."""
    if _step_log_writer is None:
        return
    try:
        _step_log_writer(
            run_id=run_id,
            step_id=step_id,
            status=status,
            started_at=kwargs.get("started_at"),
            finished_at=kwargs.get("finished_at"),
            error=kwargs.get("error"),
            bindings=kwargs.get("bindings", {}),
            screenshot_keys=kwargs.get("screenshot_keys", []),
            screenshot_urls=kwargs.get("screenshot_urls", {}),
        )
    except Exception:
        # Audit must never fail the run.
        pass


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

    async def _visit_child(self, ctx: RunContext, child: Any) -> None:
        """Run a single child step (control flow).

        P1a wires the hook so the dispatcher can plug a writer. P1b implements
        the actual nested execution (currently raises NotImplementedError for child
        steps since the recursive page reference needs an executor strategy).
        """
        if isinstance(child, dict):
            step = Step.from_dict(child)
        elif isinstance(child, Step):
            step = child
        else:
            raise ValueError(f"Unexpected child type: {type(child).__name__}")
        raise NotImplementedError(
            "Nested step execution (for_each/if children) lands in P1b — "
            "this hook is only exercised by unit tests in P1a."
        )

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
