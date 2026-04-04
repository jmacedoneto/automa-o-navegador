# Runtime Chrome Local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o runtime local (`apps/runtime`) controlar um Chrome real via Playwright `launch_persistent_context`, suportar perfis autenticados, e validar tudo com fixtures E2E.

**Architecture:** O `chrome_manager.py` passa a lançar um Chrome real com `launch_persistent_context()` usando um diretório de perfil configurável (preservando cookies/sessões). O `player.py` executa steps reais no browser. O `client.py` faz polling na API para buscar jobs e reportar status. O `main.py` vira um loop que: poll jobs → abre Chrome → executa steps → reporta resultado. Testes usam mocks do Playwright (sem browser real no CI).

**Tech Stack:** Python, Playwright, httpx, Pydantic, Pytest

---

## File Structure

**Runtime core (modify existing stubs)**

- Modify: `apps/runtime/runtime/config.py`
- Modify: `apps/runtime/runtime/chrome_manager.py`
- Modify: `apps/runtime/runtime/player.py`
- Modify: `apps/runtime/runtime/client.py`
- Modify: `apps/runtime/runtime/recorder.py`
- Modify: `apps/runtime/main.py`

**New files**

- Create: `apps/runtime/runtime/step_executor.py`

**Tests**

- Create: `apps/runtime/tests/test_chrome_manager.py`
- Create: `apps/runtime/tests/test_step_executor.py`
- Create: `apps/runtime/tests/test_client_polling.py`
- Create: `apps/runtime/tests/test_player_loop.py`
- Create: `apps/runtime/tests/test_profile_persistence.py`
- Create: `apps/runtime/tests/test_e2e_scenario.py`

---

## Task 1: Chrome Manager — Launch Real Browser With Persistent Context

**Files:**
- Modify: `apps/runtime/runtime/config.py`
- Modify: `apps/runtime/runtime/chrome_manager.py`
- Create: `apps/runtime/tests/test_chrome_manager.py`

- [ ] **Step 1: Write the failing test**

Create `apps/runtime/tests/test_chrome_manager.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.chrome_manager import ChromeManager
from apps.runtime.runtime.config import RuntimeSettings


def test_launch_creates_persistent_context():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=AsyncMock())
    mock_context.close = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    async def run():
        manager = ChromeManager(settings)
        manager._playwright = mock_playwright
        ctx, page = await manager.launch()
        assert ctx is mock_context
        mock_playwright.chromium.launch_persistent_context.assert_called_once()
        call_kwargs = mock_playwright.chromium.launch_persistent_context.call_args
        assert call_kwargs[0][0] == "/tmp/test-profile"
        assert call_kwargs[1]["headless"] is True
        assert call_kwargs[1]["viewport"] == {"width": 1280, "height": 720}

    asyncio.run(run())


def test_close_shuts_down_context():
    mock_context = AsyncMock()

    async def run():
        settings = RuntimeSettings()
        manager = ChromeManager(settings)
        manager._context = mock_context
        await manager.close()
        mock_context.close.assert_called_once()

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_chrome_manager.py -v`
Expected: FAIL with `ImportError: cannot import name 'ChromeManager'`

- [ ] **Step 3: Update config with chrome settings**

Replace `apps/runtime/runtime/config.py`:

```python
from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    api_base_url: str = "http://localhost:8000"
    max_fallback_attempts: int = 2
    fallback_pause_when_failure: bool = True
    fallback_timeout_seconds: int = 20
    chrome_profile_dir: str = ".runtime-profile"
    chrome_headless: bool = True
    chrome_viewport_width: int = 1280
    chrome_viewport_height: int = 720
    poll_interval_seconds: float = 3.0
```

- [ ] **Step 4: Implement ChromeManager**

Replace `apps/runtime/runtime/chrome_manager.py`:

```python
from pathlib import Path

from apps.runtime.runtime.config import RuntimeSettings


def chrome_user_data_dir(base_dir: str = ".runtime-profile") -> str:
    return str(Path(base_dir).resolve())


class ChromeManager:
    def __init__(self, settings: RuntimeSettings):
        self._settings = settings
        self._playwright = None
        self._context = None
        self._page = None

    async def launch(self):
        profile_dir = chrome_user_data_dir(self._settings.chrome_profile_dir)
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        if self._playwright is None:
            from playwright.async_api import async_playwright
            pw = async_playwright()
            self._playwright = await pw.start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            profile_dir,
            headless=self._settings.chrome_headless,
            viewport={
                "width": self._settings.chrome_viewport_width,
                "height": self._settings.chrome_viewport_height,
            },
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = await self._context.new_page()
        return self._context, self._page

    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None

    @property
    def page(self):
        return self._page
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_chrome_manager.py -v`
Expected: PASS with `2 passed`

- [ ] **Step 6: Run all runtime tests for regression**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/ -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/runtime/runtime/config.py apps/runtime/runtime/chrome_manager.py apps/runtime/tests/test_chrome_manager.py
git commit -m "feat: chrome manager with persistent context launch"
```

## Task 2: Step Executor — Execute Automation Steps On A Real Page

**Files:**
- Create: `apps/runtime/runtime/step_executor.py`
- Create: `apps/runtime/tests/test_step_executor.py`

- [ ] **Step 1: Write the failing test**

Create `apps/runtime/tests/test_step_executor.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from apps.runtime.runtime.step_executor import StepExecutor


def _mock_page():
    page = AsyncMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.select_option = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-png")
    page.evaluate = AsyncMock(return_value=None)
    page.wait_for_load_state = AsyncMock()
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    return page


def test_execute_navigate_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "navigate", "url": "https://example.com", "waitTime": 0})
        assert result["success"] is True
        page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded", timeout=30000)

    asyncio.run(run())


def test_execute_click_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "click", "selector": "#btn", "waitTime": 0})
        assert result["success"] is True
        page.click.assert_called_once_with("#btn", timeout=10000)

    asyncio.run(run())


def test_execute_type_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "type", "selector": "#name", "value": "test", "waitTime": 0})
        assert result["success"] is True
        page.fill.assert_called_once_with("#name", "test", timeout=10000)

    asyncio.run(run())


def test_execute_unknown_action_skips():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "unknown_thing", "waitTime": 0})
        assert result["success"] is True
        assert result["skipped"] is True

    asyncio.run(run())


def test_execute_step_captures_error():
    page = _mock_page()
    page.click = AsyncMock(side_effect=Exception("Element not found"))

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "click", "selector": "#gone", "waitTime": 0})
        assert result["success"] is False
        assert "Element not found" in result["error"]

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_step_executor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.runtime.runtime.step_executor'`

- [ ] **Step 3: Implement StepExecutor**

Create `apps/runtime/runtime/step_executor.py`:

```python
import asyncio
import base64
import os
import re
from typing import Any, Callable


def _resolve_vars(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(variables.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: _resolve_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_vars(i, variables) for i in value]
    return value


class StepExecutor:
    def __init__(self, page, variables: dict[str, Any] | None = None, on_screenshot: Callable | None = None):
        self._page = page
        self._variables = variables or {}
        self._on_screenshot = on_screenshot

    async def execute_step(self, raw_step: dict) -> dict:
        step = _resolve_vars(raw_step, self._variables)
        action = step.get("action") or step.get("type", "")
        selector = step.get("selector", "")
        result = {"action": action, "success": True, "skipped": False, "error": ""}

        try:
            if action == "navigate":
                url = step.get("url") or step.get("value", "")
                if url:
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            elif action == "click":
                if selector:
                    await self._page.click(selector, timeout=10000)
                    try:
                        await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass

            elif action == "type":
                if selector:
                    await self._page.fill(selector, step.get("value", ""), timeout=10000)

            elif action == "selectOption":
                if selector:
                    value = step.get("value", "")
                    if step.get("selectBy") == "label":
                        await self._page.select_option(selector, label=value, timeout=10000)
                    else:
                        await self._page.select_option(selector, value=value, timeout=10000)

            elif action == "wait":
                await asyncio.sleep(step.get("duration", 1000) / 1000)

            elif action == "waitForSelector":
                if selector:
                    await self._page.wait_for_selector(selector, timeout=15000)

            elif action == "scroll":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            elif action == "hover":
                if selector:
                    await self._page.hover(selector, timeout=10000)

            elif action == "key":
                await self._page.keyboard.press(step.get("key", step.get("value", "Enter")))

            elif action == "screenshot":
                png = await self._page.screenshot(full_page=step.get("full_page", False))
                if self._on_screenshot:
                    self._on_screenshot(base64.b64encode(png).decode())

            elif action == "extractTable":
                data = await self._page.evaluate("""(sel) => {
                    const table = document.querySelector(sel);
                    if (!table) return [];
                    return Array.from(table.querySelectorAll('tr')).map(r =>
                        Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())
                    );
                }""", selector or "table")
                result["extracted"] = data

            elif action == "extractText":
                if selector:
                    result["extracted"] = await self._page.inner_text(selector)

            else:
                result["skipped"] = True

            wait_ms = step.get("waitTime", 0)
            if wait_ms and wait_ms > 0 and action not in ("wait", "hover"):
                await asyncio.sleep(wait_ms / 1000)

        except Exception as exc:
            result["success"] = False
            result["error"] = str(exc)

        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_step_executor.py -v`
Expected: PASS with `5 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/runtime/runtime/step_executor.py apps/runtime/tests/test_step_executor.py
git commit -m "feat: step executor for runtime browser actions"
```

## Task 3: API Client — Poll Jobs And Report Status

**Files:**
- Modify: `apps/runtime/runtime/client.py`
- Create: `apps/runtime/tests/test_client_polling.py`

- [ ] **Step 1: Write the failing test**

Create `apps/runtime/tests/test_client_polling.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from apps.runtime.runtime.client import ApiClient


def test_poll_next_job_returns_job_when_available():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "id": "job-1",
        "automation_id": "auto-1",
        "trigger_type": "manual",
        "mode": "hibrido",
        "payload": {},
        "steps": [{"action": "navigate", "url": "https://example.com"}],
    })
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            job = await client.poll_next_job()
            assert job is not None
            assert job["id"] == "job-1"
            instance.get.assert_called_once_with(f"{client.base_url}/api/jobs/next")

    asyncio.run(run())


def test_poll_next_job_returns_none_when_empty():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 204
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            job = await client.poll_next_job()
            assert job is None

    asyncio.run(run())


def test_report_run_status():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.patch = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await client.report_run_status("run-1", status="running", steps_completed=2)
            instance.patch.assert_called_once()
            call_kwargs = instance.patch.call_args
            assert "run-1" in call_kwargs[0][0]
            assert call_kwargs[1]["json"]["status"] == "running"

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_client_polling.py -v`
Expected: FAIL with `AttributeError: 'ApiClient' object has no attribute 'poll_next_job'`

- [ ] **Step 3: Implement the full ApiClient**

Replace `apps/runtime/runtime/client.py`:

```python
import httpx


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def runs_url(self, run_id: str) -> str:
        return f"{self.base_url}/api/runs/{run_id}"

    async def poll_next_job(self) -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{self.base_url}/api/jobs/next")
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return resp.json()

    async def report_run_status(
        self,
        run_id: str,
        status: str,
        steps_completed: int = 0,
        total_steps: int = 0,
        error: str = "",
        extracted_data: dict | None = None,
    ) -> None:
        payload: dict = {
            "status": status,
            "steps_completed": steps_completed,
            "total_steps": total_steps,
        }
        if error:
            payload["error_message"] = error
        if extracted_data:
            payload["extracted_data"] = extracted_data
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.patch(self.runs_url(run_id), json=payload)
            resp.raise_for_status()

    async def ack_job(self, job_id: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(f"{self.base_url}/api/jobs/{job_id}/ack")
            resp.raise_for_status()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_client_polling.py -v`
Expected: PASS with `3 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/runtime/runtime/client.py apps/runtime/tests/test_client_polling.py
git commit -m "feat: api client with job polling and status reporting"
```

## Task 4: Player Loop — Orchestrate Chrome + Steps + Reporting

**Files:**
- Modify: `apps/runtime/runtime/player.py`
- Create: `apps/runtime/tests/test_player_loop.py`

- [ ] **Step 1: Write the failing test**

Create `apps/runtime/tests/test_player_loop.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.player import play_job
from apps.runtime.runtime.config import RuntimeSettings


def test_play_job_executes_steps_and_reports_success():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")

    job = {
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://example.com", "waitTime": 0},
            {"action": "click", "selector": "#btn", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.fill = AsyncMock()
    mock_page.keyboard = AsyncMock()
    mock_page.mouse = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_page.inner_text = AsyncMock(return_value="")

    async def run():
        result = await play_job(job=job, page=mock_page, client=mock_client, settings=settings)
        assert result["status"] == "success"
        assert result["steps_completed"] == 2
        # Should have reported running then success
        assert mock_client.report_run_status.call_count >= 2

    asyncio.run(run())


def test_play_job_reports_failure_on_step_error():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")

    job = {
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [
            {"action": "click", "selector": "#missing", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_page = AsyncMock()
    mock_page.click = AsyncMock(side_effect=Exception("Timeout"))
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")

    async def run():
        result = await play_job(job=job, page=mock_page, client=mock_client, settings=settings)
        assert result["status"] == "failed"
        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "failed"

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_player_loop.py -v`
Expected: FAIL with `ImportError: cannot import name 'play_job'`

- [ ] **Step 3: Implement play_job**

Replace `apps/runtime/runtime/player.py`:

```python
from typing import Literal

from apps.runtime.runtime.config import RuntimeSettings
from apps.runtime.runtime.step_executor import StepExecutor
from apps.runtime.runtime.fallback import should_pause_after_failure


RunStatus = Literal["queued", "running", "paused", "success", "failed"]


def build_run_summary(steps_completed: int, total_steps: int, status: RunStatus) -> dict:
    return {
        "stepsCompleted": steps_completed,
        "totalSteps": total_steps,
        "status": status,
    }


def build_delivery_payload(run_id: str, destination: str, extracted_data: dict) -> dict:
    return {
        "run_id": run_id,
        "destination": destination,
        "payload": extracted_data,
    }


async def play_job(job: dict, page, client, settings: RuntimeSettings) -> dict:
    run_id = job.get("run_id", "")
    steps = job.get("steps", [])
    variables = job.get("variables", {})
    total = len(steps)

    await client.report_run_status(run_id, status="running", steps_completed=0, total_steps=total)

    executor = StepExecutor(page, variables=variables)
    completed = 0
    fallback_attempts = 0
    extracted_data = {}

    for i, step in enumerate(steps):
        result = await executor.execute_step(step)

        if result["success"]:
            completed += 1
            if "extracted" in result:
                extracted_data[f"step_{i}"] = result["extracted"]
            await client.report_run_status(run_id, status="running", steps_completed=completed, total_steps=total)
        else:
            fallback_attempts += 1
            if should_pause_after_failure(fallback_attempts, settings.max_fallback_attempts, settings.fallback_pause_when_failure):
                await client.report_run_status(
                    run_id,
                    status="failed",
                    steps_completed=completed,
                    total_steps=total,
                    error=result["error"],
                )
                return {"status": "failed", "steps_completed": completed, "error": result["error"]}

    await client.report_run_status(
        run_id,
        status="success",
        steps_completed=completed,
        total_steps=total,
        extracted_data=extracted_data,
    )
    return {"status": "success", "steps_completed": completed, "extracted_data": extracted_data}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_player_loop.py -v`
Expected: PASS with `2 passed`

- [ ] **Step 5: Run all runtime tests for regression**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add apps/runtime/runtime/player.py apps/runtime/tests/test_player_loop.py
git commit -m "feat: player loop orchestrates steps and reports status"
```

## Task 5: Main Runtime Loop — Poll, Launch Chrome, Execute, Report

**Files:**
- Modify: `apps/runtime/main.py`
- Modify: `apps/runtime/tests/test_player_contract.py`

- [ ] **Step 1: Write the failing test**

Replace `apps/runtime/tests/test_player_contract.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.player import build_run_summary
from apps.runtime.main import run_once
from apps.runtime.runtime.config import RuntimeSettings


def test_build_run_summary():
    summary = build_run_summary(steps_completed=3, total_steps=4, status="running")
    assert summary["stepsCompleted"] == 3
    assert summary["status"] == "running"


def test_run_once_executes_job_when_available():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")
    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value={
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [{"action": "navigate", "url": "https://example.com", "waitTime": 0}],
        "variables": {},
    })
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")

    mock_manager = AsyncMock()
    mock_manager.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_manager.close = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_manager, settings=settings)
        assert executed is True
        mock_client.ack_job.assert_called_once_with("job-1")

    asyncio.run(run())


def test_run_once_skips_when_no_job():
    settings = RuntimeSettings()
    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=None)
    mock_manager = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_manager, settings=settings)
        assert executed is False
        mock_manager.launch.assert_not_called()

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_player_contract.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_once'`

- [ ] **Step 3: Implement main with run_once**

Replace `apps/runtime/main.py`:

```python
import asyncio
import signal

from apps.runtime.runtime.config import RuntimeSettings
from apps.runtime.runtime.chrome_manager import ChromeManager
from apps.runtime.runtime.client import ApiClient
from apps.runtime.runtime.player import play_job


async def run_once(client: ApiClient, chrome: ChromeManager, settings: RuntimeSettings) -> bool:
    job = await client.poll_next_job()
    if job is None:
        return False

    await client.ack_job(job["id"])

    _ctx, page = await chrome.launch()
    try:
        await play_job(job=job, page=page, client=client, settings=settings)
    finally:
        await chrome.close()

    return True


async def run_loop(settings: RuntimeSettings | None = None):
    settings = settings or RuntimeSettings()
    client = ApiClient(base_url=settings.api_base_url)
    chrome = ChromeManager(settings)

    stop = asyncio.Event()

    def _handle_signal():
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    print(f"[runtime] polling {settings.api_base_url} every {settings.poll_interval_seconds}s")

    while not stop.is_set():
        try:
            executed = await run_once(client=client, chrome=chrome, settings=settings)
            if not executed:
                await asyncio.sleep(settings.poll_interval_seconds)
        except Exception as exc:
            print(f"[runtime] error: {exc}")
            await asyncio.sleep(settings.poll_interval_seconds)

    print("[runtime] shutting down")


def main():
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_player_contract.py -v`
Expected: PASS with `3 passed`

- [ ] **Step 5: Run all runtime tests for regression**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add apps/runtime/main.py apps/runtime/tests/test_player_contract.py
git commit -m "feat: runtime main loop with polling and chrome lifecycle"
```

## Task 6: Profile Persistence — Verify Cookies/Sessions Survive Restarts

**Files:**
- Create: `apps/runtime/tests/test_profile_persistence.py`

- [ ] **Step 1: Write the test**

Create `apps/runtime/tests/test_profile_persistence.py`:

```python
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from apps.runtime.runtime.chrome_manager import ChromeManager, chrome_user_data_dir
from apps.runtime.runtime.config import RuntimeSettings


def test_chrome_user_data_dir_resolves_path():
    result = chrome_user_data_dir("/tmp/my-profile")
    assert result == "/tmp/my-profile"


def test_chrome_user_data_dir_relative_resolves_to_absolute():
    result = chrome_user_data_dir(".my-profile")
    assert Path(result).is_absolute()


def test_profile_dir_created_on_launch():
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = f"{tmp}/new-profile"
        settings = RuntimeSettings(chrome_profile_dir=profile_path)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=AsyncMock())

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        async def run():
            manager = ChromeManager(settings)
            manager._playwright = mock_playwright
            await manager.launch()
            assert Path(profile_path).exists()

        asyncio.run(run())


def test_persistent_context_uses_same_dir_across_calls():
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = f"{tmp}/stable-profile"
        settings = RuntimeSettings(chrome_profile_dir=profile_path)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=AsyncMock())
        mock_context.close = AsyncMock()

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        async def run():
            manager = ChromeManager(settings)
            manager._playwright = mock_playwright

            await manager.launch()
            call1 = mock_playwright.chromium.launch_persistent_context.call_args[0][0]
            await manager.close()

            await manager.launch()
            call2 = mock_playwright.chromium.launch_persistent_context.call_args[0][0]

            assert call1 == call2
            assert call1 == profile_path

        asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_profile_persistence.py -v`
Expected: PASS with `4 passed`

- [ ] **Step 3: Commit**

```bash
git add apps/runtime/tests/test_profile_persistence.py
git commit -m "test: profile persistence across chrome restarts"
```

## Task 7: API — Add Job Polling Endpoint (GET /api/jobs/next and POST /api/jobs/:id/ack)

**Files:**
- Modify: `apps/api/app/api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_jobs_api.py`:

```python
def test_poll_next_job_returns_204_when_empty():
    response = client.get("/api/jobs/next")
    assert response.status_code == 204


def test_ack_job_returns_200():
    response = client.post("/api/jobs/fake-job-id/ack")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/api/tests/test_jobs_api.py -v`
Expected: FAIL with `404` or `405`

- [ ] **Step 3: Add the polling endpoints**

Replace `apps/api/app/api/routes/jobs.py`:

```python
from uuid import uuid4

from fastapi import APIRouter, Response, status

from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": str(uuid4()),
        "automation_id": str(payload.automation_id),
        "status": "queued",
    }


@router.get("/next")
def poll_next_job(response: Response):
    # Placeholder: in production this queries execution_jobs WHERE status='queued' ORDER BY created_at LIMIT 1
    # For now returns 204 (no jobs) — the real implementation will query Supabase
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.post("/{job_id}/ack")
def ack_job(job_id: str):
    # Placeholder: in production this sets status='running' on the job
    return {"id": job_id, "status": "running"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/api/tests/test_jobs_api.py -v`
Expected: PASS with `5 passed`

- [ ] **Step 5: Run all API tests for regression**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/api/tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat: job polling and ack endpoints for runtime"
```

## Task 8: E2E Scenario Fixture — Full Cycle Without Real Browser

**Files:**
- Create: `apps/runtime/tests/test_e2e_scenario.py`

- [ ] **Step 1: Write the E2E integration test**

Create `apps/runtime/tests/test_e2e_scenario.py`:

```python
"""
End-to-end scenario: simulates the full runtime cycle.
1. Client polls a job
2. Chrome manager launches (mocked)
3. Player executes steps (mocked page)
4. Client reports success

No real browser. Validates the full wiring between components.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.main import run_once
from apps.runtime.runtime.config import RuntimeSettings


def _mock_page():
    page = AsyncMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.select_option = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-png")
    page.evaluate = AsyncMock(return_value=None)
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.inner_text = AsyncMock(return_value="text")
    page.hover = AsyncMock()
    return page


def test_full_e2e_navigate_click_type():
    """Simulate a 3-step automation: navigate → click → type."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-test")

    job = {
        "id": "job-e2e",
        "automation_id": "auto-e2e",
        "run_id": "run-e2e",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://erp.example.com/login", "waitTime": 0},
            {"action": "type", "selector": "#user", "value": "admin", "waitTime": 0},
            {"action": "click", "selector": "#submit", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_chrome, settings=settings)
        assert executed is True

        # Verify ack was called
        mock_client.ack_job.assert_called_once_with("job-e2e")

        # Verify page interactions
        mock_page.goto.assert_called_once_with(
            "https://erp.example.com/login",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        mock_page.fill.assert_called_once_with("#user", "admin", timeout=10000)
        mock_page.click.assert_called_once_with("#submit", timeout=10000)

        # Verify final status report was success
        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "success"
        assert last_call[1]["steps_completed"] == 3

    asyncio.run(run())


def test_full_e2e_with_variables():
    """Simulate automation with {{variable}} substitution."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-vars")

    job = {
        "id": "job-vars",
        "automation_id": "auto-vars",
        "run_id": "run-vars",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://erp.example.com", "waitTime": 0},
            {"action": "type", "selector": "#user", "value": "{{username}}", "waitTime": 0},
            {"action": "type", "selector": "#pass", "value": "{{password}}", "waitTime": 0},
        ],
        "variables": {"username": "admin", "password": "secret123"},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        await run_once(client=mock_client, chrome=mock_chrome, settings=settings)

        calls = mock_page.fill.call_args_list
        assert calls[0][0] == ("#user", "admin")
        assert calls[1][0] == ("#pass", "secret123")

    asyncio.run(run())


def test_full_e2e_failure_reports_error():
    """When a step fails past fallback limit, run reports failed."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-fail", max_fallback_attempts=1)

    job = {
        "id": "job-fail",
        "automation_id": "auto-fail",
        "run_id": "run-fail",
        "mode": "gravado",
        "steps": [
            {"action": "click", "selector": "#nonexistent", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_page.click = AsyncMock(side_effect=Exception("Element not found"))

    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        await run_once(client=mock_client, chrome=mock_chrome, settings=settings)

        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "failed"
        assert "Element not found" in last_call[1]["error"]

    asyncio.run(run())


def test_no_job_does_nothing():
    """When no job is available, run_once returns False without launching Chrome."""
    settings = RuntimeSettings()

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=None)

    mock_chrome = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_chrome, settings=settings)
        assert executed is False
        mock_chrome.launch.assert_not_called()

    asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/test_e2e_scenario.py -v`
Expected: PASS with `5 passed`

- [ ] **Step 3: Run full verification suite**

Run: `cd /root/navegador/automa-o-navegador && python3 -m pytest apps/runtime/tests/ -v && python3 -m pytest apps/api/tests/ -v && npm run test:web`
Expected: All suites green

- [ ] **Step 4: Commit**

```bash
git add apps/runtime/tests/test_e2e_scenario.py
git commit -m "test: e2e scenario fixtures for full runtime cycle"
```

## Notes For Execution

- All runtime tests use mocked Playwright — no real browser needed in CI.
- The `chrome_profile_dir` setting allows each user/environment to point at their own Chrome profile directory (preserving cookies, localStorage, sessions).
- The `GET /api/jobs/next` and `POST /api/jobs/:id/ack` are placeholders that return empty/OK. The real Supabase integration comes in the next plan cycle.
- After this plan, the next step is wiring the real Supabase queries into the job endpoints and running the runtime against a live API + browser.
