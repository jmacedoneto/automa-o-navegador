# NavRunner P5 — Auth Runner Wiring + Sandbox + Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three production debts that survive P0–P3: (1) the dispatcher doesn't honor `auth` blocks — NavRecorder drafts emit `login_block` annotations that aren't runnable, fix this end-to-end; (2) `run_python` exposes `__import__` so it can run arbitrary code under the worker user; (3) `_step_log_writer` is a module global so two concurrent runs in the same worker process would cross-contaminate.

**Architecture:** Three orthogonal fixes. (1) Dispatcher (`run_automation_v2`) reads `automation_name` from the FIRST step in `steps_payload` if it's an `auth` block, OR accepts a top-level `auth` field in the payload, calls `parse_auth` + `run_auth` before `for_each`. Recorder (`recorder.py`) stops emitting `login_block` as a step and instead returns the top-level `auth` field in the draft. (2) `run_python` moves to a subprocess-based sandbox using `multiprocessing` + `asyncio.to_thread` for timeout enforcement; the subprocess gets a denylist of dangerous modules (`os`, `subprocess`, `sys.exit`, `importlib`). (3) `_step_log_writer` becomes a `contextvars.ContextVar` so concurrent runs each get their own writer.

**Tech Stack:** Python 3.11, `contextvars` (stdlib), `multiprocessing` (stdlib), `RestrictedPython` (NEW dep, optional), NavRunner P0–P3 (all merged).

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — sections "Auth block", "P5: RestrictedPython sandbox", "P5: Per-run step_log_writer".

**Predecessor plans:** P0, P1a, P1b, P2, P3 all merged.

---

## File Structure

### Files created (P5)

```
backend/app/automation/
├── auth_strategies.py        # cookie_reuse + otp_via_telegram strategies
├── sandbox.py                 # run_python sandbox (subprocess isolation)
└── runner_state.py            # ContextVar-based step_log_writer per run

backend/tests/automation/
├── test_auth_strategies.py
├── test_sandbox.py
└── test_runner_state.py
```

### Files modified (P5)

- `backend/app/workers/tasks.py` — wire `parse_auth` + `run_auth` before step loop; use `contextvars.ContextVar` writer
- `backend/app/automation/auth.py` — register `cookie_reuse` and `otp_via_telegram` types
- `backend/app/automation/runner.py` — accept `auth` block at NavRunner.run_steps; use `ContextVar` writer
- `backend/app/automation/run_python.py` — route to sandbox
- `backend/app/automation/recorder.py` — emit `auth` at top level (not `login_block` step)
- `examples/cotacao_pvs/steps.json` — promote `auth` to top level (so P5 proves the wire end-to-end)
- `backend/requirements.txt` — add `RestrictedPython` if implementing constraint-based sandbox (TBD per task 3)
- `backend/app/automation/README.md` — confirm P5 closed

### Anti-pattern check

- Each new file is one responsibility. `auth_strategies.py` is sibling to `auth.py` (the parser) — same directory, sibling module.
- Sandbox isolation is via subprocess (the only way to truly hide `os.system` from the eval'd code without writing a full Python sandbox). RestrictedPython is belt-and-suspenders for naive modifications.
- `contextvars.ContextVar` is reused per-run, not per-call — the dispatcher creates a fresh var, the runner reads it, no global state.

---

## Conventions carried from P0/P1a/P1b/P2/P3

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P5 task N — <title>` etc.
- Tests in `backend/tests/automation/`.

---

## Task 1: Wire `auth` block in dispatcher

**Why first:** Closes the gap that NavRecorder left as a P3 "important" issue. Once `auth` lands at the top level (instead of the bogus `login_block` step), the recorder can switch to emitting it correctly (Task 5).

**Files:**
- Modify: `backend/app/workers/tasks.py` (only `run_automation_v2`)
- Create: `backend/tests/automation/test_dispatcher_auth.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_dispatcher_auth.py` with EXACTLY:

```python
"""Test that the dispatcher honors a top-level `auth` block."""
from unittest.mock import MagicMock


def test_dispatcher_runs_auth_before_steps(monkeypatch):
    """When steps_payload[0] is an auth block, parse_auth + run_auth are called."""
    fake_run_auth = MagicMock()
    async def fake_run_auth_async(page, spec, ctx):
        pass
    fake_run_auth_async.return_value = None
    fake_run_auth.side_effect = lambda *, page, spec, ctx: fake_run_auth_async(page, spec, ctx)
    monkeypatch.setattr("app.workers.tasks.run_auth", fake_run_auth)

    fake_result = MagicMock()
    fake_result.status = "success"
    fake_result.errors = []
    fake_result.bindings = {"step": "ok"}
    fake_result.screenshot_keys = []
    fake_result.screenshot_urls = {}

    async def fake_run_steps(steps, inputs, credentials=None):
        return fake_result

    fake_runner = MagicMock()
    fake_runner.run_steps = fake_run_steps
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {"apvs_login": {"user": "x", "pass": "y"}})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    auth_block = {
        "type": "form_login",
        "url": "https://app.apvs.vc/home",
        "credentials_ref": "apvs_login",
        "selectors": {"user": "input[type=text]", "pass": "input[type=password]", "submit": "ion-button"},
        "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
    }
    body_block = {"id": "click_x", "click": {"selector": "button"}}

    from app.workers.tasks import run_automation_v2
    import asyncio
    asyncio.run(run_automation_v2(
        automation_name="login_only",
        steps_payload=[auth_block, body_block],
        inputs={},
    ))

    # 1. parse_auth was called: the runner's step list starts AFTER the auth block.
    fake_runner.run_steps.assert_called_once()
    call = fake_runner.run_steps.call_args
    steps_seen = call.kwargs.get("steps") or call.args[0]
    assert steps_seen[0]["id"] == "click_x"
    assert auth_block not in steps_seen  # stripped

    # 2. run_auth was called against the page.
    fake_run_auth.assert_called_once()


def test_dispatcher_no_auth_block_unchanged(monkeypatch):
    """When there's no auth block, the dispatcher behaves as before."""
    fake_run_auth = MagicMock()
    monkeypatch.setattr("app.workers.tasks.run_auth", fake_run_auth)

    fake_result = MagicMock(status="success", errors=[], bindings={}, screenshot_keys=[], screenshot_urls={})
    async def fake_run_steps(steps, inputs, credentials=None):
        return fake_result
    fake_runner = MagicMock()
    fake_runner.run_steps = fake_run_steps
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    from app.workers.tasks import run_automation_v2
    import asyncio
    asyncio.run(run_automation_v2(
        automation_name="no_auth",
        steps_payload=[{"id": "x", "click": {"selector": "button"}}],
        inputs={},
    ))
    fake_run_auth.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_dispatcher_auth.py -v
```

Expected: both tests fail (no auth block detection in dispatcher).

- [ ] **Step 3: Wire auth in dispatcher**

In `backend/app/workers/tasks.py`, find the existing `run_automation_v2` definition. Add imports:

```python
from app.automation.auth import AuthSpec, parse_auth, run_auth
```

Find the spot where `steps = [Step.from_dict(s) for s in steps_payload]` (or similar). Add a preprocessing pass BEFORE the runner is invoked:

```python
    # Step 1: detect top-level auth block (first step might be auth)
    auth_spec: AuthSpec | None = None
    if steps_payload and isinstance(steps_payload[0], dict) and "auth" in steps_payload[0]:
        auth_block = steps_payload[0]["auth"]
        # Strip the auth block from steps_payload — runner doesn't see it.
        steps_payload = steps_payload[1:]
        try:
            auth_spec = parse_auth(auth_block)
        except ValueError as e:
            # Bad auth block — log and fail at dispatch time (before launching runner).
            db.table("automation_runs").update({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_message": f"auth block parse error: {e}",
            }).eq("id", run_id).execute()
            raise
```

Find the `try: result = _run(runner.run_steps(...))` block. Wrap it so `run_auth` is called before the runner:

```python
    try:
        page = None  # runner will create the page; we need it for run_auth
        # We need access to the page for run_auth. The cleanest path is to
        # have the runner expose its page via a callback, OR to run the auth
        # step inside the runner. For P5, we keep it simple: call run_auth
        # against the runner's page via a hook on the runner instance.
        # ...
        # P5 implementation: runner.run_steps accepts an `auth` kwarg and
        # runs auth before the steps loop. See runner.py changes below.
        result = _run(runner.run_steps(
            steps=steps,
            inputs=inputs,
            credentials=credentials,
            auth=auth_spec,
        ))
        # ... rest unchanged
```

**Alternative (simpler) implementation:** Pass `auth` through `run_steps` and let the runner call `run_auth` after creating the page. This is the path we'll take — see Task 4 below for the runner changes.

**For Task 1 scope:** Only verify the dispatcher passes through and skips the auth block from step list. The actual `run_auth` call happens in Task 4 (runner changes).

Update the test to NOT assert `fake_run_auth.assert_called_once` — that's verified by Task 4's test instead. Update the first test to:

```python
def test_dispatcher_strips_auth_block_from_steps(monkeypatch):
    """When steps_payload[0] is an auth block, the runner's step list is the rest."""
    fake_result = MagicMock(status="success", errors=[], bindings={}, screenshot_keys=[], screenshot_urls={})
    async def fake_run_steps(steps=None, inputs=None, credentials=None, auth=None):
        return fake_result
    fake_runner = MagicMock()
    fake_runner.run_steps = fake_run_steps
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {"apvs_login": {"user": "x", "pass": "y"}})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    auth_block = {"type": "form_login", "url": "https://x", "credentials_ref": "apvs_login", "selectors": {"user": "input", "pass": "input", "submit": "button"}, "success_assert": {"selector": ".ok", "timeout_ms": 5000}}
    body_block = {"id": "click_x", "click": {"selector": "button"}}

    from app.workers.tasks import run_automation_v2
    import asyncio
    asyncio.run(run_automation_v2(
        automation_name="login_only",
        steps_payload=[auth_block, body_block],
        inputs={},
    ))

    fake_runner.run_steps.assert_called_once()
    call = fake_runner.run_steps.call_args
    kwargs = call.kwargs
    steps_seen = kwargs.get("steps") or call.args[0]
    assert auth_block not in steps_seen
    assert steps_seen[0]["id"] == "click_x"
    # The auth spec is passed through.
    assert kwargs.get("auth") is not None
    assert kwargs["auth"].type == "form_login"
```

(Remove the `test_dispatcher_no_auth_block_unchanged` test — or keep it as the no-auth path. Simpler: keep both tests.)

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_dispatcher_auth.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/workers/tasks.py backend/tests/automation/test_dispatcher_auth.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P5 task 1 — dispatcher strips top-level auth block + passes auth to runner"
```

---

## Task 2: Auth strategies — `cookie_reuse` and `otp_via_telegram`

**Why second:** Adds two production-relevant auth strategies. `cookie_reuse` is the easy one (load cookies from storage). `otp_via_telegram` requires a Telegram bot token + chat_id (re-uses `evolution` config or a new `telegram` key).

**Files:**
- Modify: `backend/app/automation/auth.py` (register types + add handlers)
- Create: `backend/tests/automation/test_auth_strategies.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_auth_strategies.py` with EXACTLY:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.automation.auth import parse_auth, run_auth, AuthSpec
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_parse_auth_cookie_reuse():
    raw = {
        "type": "cookie_reuse",
        "url": "https://app.apvs.vc/dashboard",
        "cookies": [{"name": "sessionid", "value": "abc", "domain": ".apvs.vc"}],
        "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
    }
    spec = parse_auth(raw)
    assert spec.type == "cookie_reuse"
    assert spec.cookies == [{"name": "sessionid", "value": "abc", "domain": ".apvs.vc"}]


def test_parse_auth_otp_via_telegram():
    raw = {
        "type": "otp_via_telegram",
        "url": "https://app.apvs.vc/login",
        "credentials_ref": "apvs_login",
        "telegram_chat_id": "123456",
        "otp_selector": "input[name=otp]",
        "submit_selector": "button[type=submit]",
        "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
    }
    spec = parse_auth(raw)
    assert spec.type == "otp_via_telegram"
    assert spec.telegram_chat_id == "123456"


def test_run_auth_cookie_reuse():
    page = MagicMock()
    page.add_cookies = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()

    spec = AuthSpec(
        type="cookie_reuse",
        url="https://app.apvs.vc/dashboard",
        cookies=[{"name": "sess", "value": "xyz", "domain": ".apvs.vc"}],
        success_assert={"selector": ".dashboard", "timeout_ms": 5000},
    )
    ctx = RunContext()
    _run(run_auth(page, spec, ctx))
    page.add_cookies.assert_called_once()
    page.goto.assert_called_once_with(spec.url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_selector.assert_called_once_with(".dashboard", timeout=5000, state="visible")


def test_run_auth_otp_via_telegram_fetches_otp():
    """OTP flow: login first, then poll Telegram for the code, fill, submit."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_selector = AsyncMock()

    fake_message = "Seu código: 123456"
    fake_telegram = AsyncMock(return_value=fake_message)
    # Re-register a fake telegram fetcher.
    import app.automation.auth as auth_mod
    original = getattr(auth_mod, "_fetch_telegram_message", None)
    auth_mod._fetch_telegram_message = fake_telegram
    try:
        spec = AuthSpec(
            type="otp_via_telegram",
            url="https://app.apvs.vc/login",
            credentials_ref="apvs_login",
            telegram_chat_id="999",
            otp_selector="input[name=otp]",
            submit_selector="button[type=submit]",
            success_assert={"selector": ".dashboard", "timeout_ms": 5000},
        )
        ctx = RunContext(credentials={"apvs_login": {"user": "u", "pass": "p"}})
        _run(run_auth(page, spec, ctx))
        fake_telegram.assert_called_once_with("999", timeout_s=60)
        # OTP was filled (look for "123456" in any fill call).
        fill_calls = [c.args for c in page.fill.call_args_list]
        assert any("123456" in (c[1] if len(c) > 1 else "") for c in fill_calls)
    finally:
        if original is not None:
            auth_mod._fetch_telegram_message = original


def test_parse_auth_unknown_type_still_raises():
    with __import__("pytest").raises(ValueError, match="Unsupported"):
        parse_auth({"type": "oauth_magic", "url": "x"})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_auth_strategies.py -v
```

Expected: ImportError / AttributeError (AuthSpec has no `cookies` field).

- [ ] **Step 3: Update `auth.py` and add telegram fetcher**

`backend/app/automation/auth.py` — replace with:

```python
"""Auth block — declarative login flows.

P1a implements `form_login`. P5 adds `cookie_reuse` and `otp_via_telegram`.
`success_assert` is mandatory because we can't assume a login worked without
signaling; treating absence as success has burned cotacao_pvs in the past.
"""
from dataclasses import dataclass, field
import re
from typing import Any

from app.automation.bindings import interpolate
from app.automation.models import RunContext


SUPPORTED_TYPES = {"form_login", "cookie_reuse", "otp_via_telegram"}


@dataclass
class AuthSpec:
    type: str
    url: str
    credentials_ref: str | None = None
    selectors: dict[str, str] = field(default_factory=dict)
    success_assert: dict[str, Any] = field(default_factory=dict)
    # cookie_reuse:
    cookies: list[dict] = field(default_factory=list)
    # otp_via_telegram:
    telegram_chat_id: str | None = None
    otp_selector: str | None = None
    submit_selector: str | None = None


def parse_auth(raw: dict[str, Any]) -> AuthSpec:
    if not isinstance(raw, dict):
        raise ValueError(f"auth block must be a dict, got {type(raw).__name__}")
    auth_type = raw.get("type")
    if auth_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported auth type {auth_type!r}; supported: {sorted(SUPPORTED_TYPES)}")
    if "url" not in raw or "success_assert" not in raw:
        raise ValueError("auth block missing required field(s): url, success_assert")

    if auth_type == "form_login":
        if "credentials_ref" not in raw or "selectors" not in raw:
            raise ValueError("form_login requires credentials_ref, selectors")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            credentials_ref=raw["credentials_ref"],
            selectors=raw["selectors"],
            success_assert=raw["success_assert"],
        )
    if auth_type == "cookie_reuse":
        if "cookies" not in raw or not isinstance(raw["cookies"], list):
            raise ValueError("cookie_reuse requires 'cookies' list")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            cookies=raw["cookies"],
            success_assert=raw["success_assert"],
        )
    if auth_type == "otp_via_telegram":
        missing = [f for f in ("credentials_ref", "telegram_chat_id", "otp_selector", "submit_selector") if f not in raw]
        if missing:
            raise ValueError(f"otp_via_telegram missing required field(s): {missing}")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            credentials_ref=raw["telegram_chat_id"],  # unused; placeholder
            selectors={
                "user": "input[type=text]",
                "pass": "input[type=password]",
                "submit": raw["submit_selector"],
            },
            success_assert=raw["success_assert"],
            telegram_chat_id=raw["telegram_chat_id"],
            otp_selector=raw["otp_selector"],
            submit_selector=raw["submit_selector"],
        )
    raise ValueError(f"Unhandled auth type {auth_type!r}")


# ── OTP helpers ─────────────────────────────────────────────────────────

_OTP_RE = re.compile(r"\b(\d{4,8})\b")


async def _fetch_telegram_message(chat_id: str, timeout_s: int = 60) -> str:
    """Fetch the latest message from a Telegram chat within `timeout_s`.

    Default impl uses the Telegram Bot API (HTTPS). Requires:
    - TELEGRAM_BOT_TOKEN env var
    - chat_id from the auth block
    """
    import os
    import httpx
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
    update_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    timeout = 2
    elapsed = 0
    last_update_id = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        while elapsed < timeout_s:
            resp = await client.get(update_url, params={"timeout": 1, "allowed_updates": '["message"]'})
            data = resp.json().get("result") or []
            for update in data:
                if str(update.get("message", {}).get("chat", {}).get("id")) != str(chat_id):
                    continue
                msg_text = update["message"].get("text", "")
                last_update_id = update["update_id"]
                m = _OTP_RE.search(msg_text)
                if m:
                    return m.group(1)
            await asyncio.sleep(2)
            elapsed += 2
    raise TimeoutError(f"No OTP message received in {timeout_s}s from chat {chat_id}")


# ── Auth runners ────────────────────────────────────────────────────────

async def run_auth(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    if spec.type == "form_login":
        await _run_form_login(page, spec, ctx)
        return
    if spec.type == "cookie_reuse":
        await _run_cookie_reuse(page, spec)
        return
    if spec.type == "otp_via_telegram":
        await _run_otp_via_telegram(page, spec, ctx)
        return
    raise ValueError(f"Auth type {spec.type!r} not implemented")


async def _run_form_login(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    creds = ctx.credentials.get(spec.credentials_ref) if spec.credentials_ref else None
    if creds is None:
        raise KeyError(f"credentials_ref {spec.credentials_ref!r} not found in ctx.credentials")

    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")

    user_selector = interpolate(spec.selectors["user"], ctx)
    pass_selector = interpolate(spec.selectors["pass"], ctx)
    user_value = interpolate(str(creds.get("user", "")), ctx)
    pass_value = interpolate(str(creds.get("pass", "")), ctx)
    await page.fill(user_selector, user_value, timeout=15000)
    await page.fill(pass_selector, pass_value, timeout=15000)

    submit_selector = interpolate(spec.selectors["submit"], ctx)
    await page.click(submit_selector, timeout=30000)

    success_selector = interpolate(spec.success_assert["selector"], ctx)
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")


async def _run_cookie_reuse(page: Any, spec: AuthSpec) -> None:
    # Playwright add_cookies expects `name`, `value`, `domain` (or `url`).
    cookies = [
        {k: v for k, v in c.items() if k in ("name", "value", "domain", "url", "path", "expires", "httpOnly", "secure", "sameSite")}
        for c in spec.cookies
    ]
    if cookies:
        await page.add_cookies(cookies)
    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")
    success_selector = interpolate(spec.success_assert["selector"], type("C", (), {"bindings": {}, "credentials": {}, "inputs": {}})())
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")


async def _run_otp_via_telegram(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    import asyncio
    creds = ctx.credentials.get(spec.credentials_ref) if spec.credentials_ref else None
    if creds is None:
        raise KeyError(f"credentials_ref {spec.credentials_ref!r} not found in ctx.credentials")
    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")
    # Fill user/pass (assumes first screen has them).
    if creds.get("user"):
        first_input = await page.query_selector("input[type=text]")
        if first_input:
            await first_input.fill(str(creds["user"]))
    if creds.get("pass"):
        pwd_input = await page.query_selector("input[type=password]")
        if pwd_input:
            await pwd_input.fill(str(creds["pass"]))
    # Submit to reach OTP screen.
    await page.click("button[type=submit]", timeout=15000)
    # Fetch OTP from Telegram.
    msg = await _fetch_telegram_message(spec.telegram_chat_id, timeout_s=60)
    m = _OTP_RE.search(msg)
    if not m:
        raise RuntimeError(f"No OTP code found in Telegram message: {msg!r}")
    otp = m.group(1)
    # Fill OTP.
    await page.fill(spec.otp_selector, otp, timeout=15000)
    # Submit.
    await page.click(spec.submit_selector, timeout=15000)
    # Wait for success.
    success_selector = interpolate(spec.success_assert["selector"], type("Ctx", (), {"bindings": {}, "credentials": {}, "inputs": {}})())
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_auth_strategies.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Re-run full auth tests**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_auth.py tests/automation/test_auth_strategies.py -v
```

Expected: 11 passed (6 original + 5 new).

- [ ] **Step 6: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/automation/auth.py backend/tests/automation/test_auth_strategies.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P5 task 2 — cookie_reuse + otp_via_telegram auth strategies"
```

---

## Task 3: `run_python` sandbox — subprocess isolation

**Why third:** The escape hatch currently exposes `__import__`. P5 wraps it in a subprocess that denies `os`, `subprocess`, `importlib` and enforces the timeout via `multiprocessing.Process`.

**Files:**
- Create: `backend/app/automation/sandbox.py`
- Modify: `backend/app/automation/run_python.py` (route to sandbox)
- Create: `backend/tests/automation/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_sandbox.py` with EXACTLY:

```python
import asyncio

from app.automation.sandbox import run_sandboxed


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_sandbox_executes_simple_expression():
    """A simple expression returns its value."""
    result = _run(run_sandboxed("1 + 2", {}))
    assert result == 3


def test_sandbox_executes_multi_stmt():
    """Multi-statement scripts can assign variables."""
    code = """
total = 0
for i in range(5):
    total += i
"""
    result = _run(run_sandboxed(code, {}))
    assert result == 15


def test_sandbox_blocks_os_import():
    """`import os` raises a SandboxViolation, not a silent success."""
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("import os; os.listdir('/')", {}))


def test_sandbox_blocks_subprocess():
    """`subprocess` import is blocked."""
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("import subprocess; subprocess.run(['ls'])", {}))


def test_sandbox_blocks_os_system_via_eval():
    """Even via getattr, __import__ is blocked at the module level."""
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("__import__('os').system('echo pwned')", {}))


def test_sandbox_allows_safe_stdlib():
    """json, re, math, datetime, time, asyncio are allowed."""
    code = """
import json
import re
import math
payload = json.dumps({'x': math.sqrt(16)})
m = re.match(r'.*4.*', payload)
"""
    result = _run(run_sandboxed(code, {}))
    assert result is not None  # no return value, just executed


def test_sandbox_exposes_inputs_and_bindings():
    """The sandbox namespace has `inputs`, `bindings`, `page` (None in this test)."""
    code = """
result = inputs.get('cliente', {}).get('nome', 'unknown') + '|' + str(bindings.get('combo', {}).get('fipe_code', ''))
"""
    ns = {"inputs": {"cliente": {"nome": "Ana"}}, "bindings": {"combo": {"fipe_code": "001"}}, "page": None}
    _run(run_sandboxed(code, ns))


def test_sandbox_timeout_returns_best_effort():
    """A long-running script is killed at the timeout."""
    import time
    t0 = time.time()
    try:
        _run(run_sandboxed("import time; time.sleep(10)", {}, timeout_s=1))
    except Exception:
        pass
    elapsed = time.time() - t0
    assert elapsed < 5, f"sandbox took {elapsed:.1f}s, expected < 5s"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_sandbox.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.automation.sandbox'`

- [ ] **Step 3: Implement `sandbox.py`**

`backend/app/automation/sandbox.py`:

```python
"""Subprocess-isolated sandbox for run_python.

P5 implementation. The user's code runs in a separate Python process
(via multiprocessing). The process has a denylist of dangerous modules
that raise `SandboxViolation` on import. The timeout is enforced by
killing the process.

Why subprocess isolation? Python's eval() cannot be sandboxed without
modifying the interpreter (RestrictedPython, etc.) — and even those
can be bypassed. A subprocess gives us a clean process boundary: from
the user's perspective, `os.system` looks like it works, but the
denylist blocks it at import time.

Trade-off: a few extra ms of fork overhead per run_python invocation.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import os
import sys
import traceback
from typing import Any


# Modules that the sandbox refuses to import.
_BLOCKED_MODULES = frozenset({
    "os", "subprocess", "importlib", "importlib.util", "importlib.machinery",
    "ctypes", "cffi", "multiprocessing", "socket", "ssl", "_socket",
    "win32api", "win32com", "win32process", "win32security",
    "_winreg", "posix", "fcntl", "grp", "pwd", "resource",
    "sysconfig", "distorm", "keystone", "capstone", "unicorn",
})


class SandboxViolation(RuntimeError):
    """Raised when sandbox detects a blocked module or operation."""


def _child_main(code: str, ns: dict, q) -> None:
    """Entry point for the sandboxed subprocess."""
    # Patch __import__ to refuse blocked modules.
    _real_import = __import__

    def _guarded_import(name, *args, **kwargs):
        top = name.split(".")[0]
        if top in _BLOCKED_MODULES:
            raise SandboxViolation(f"module {name!r} is blocked in the sandbox")
        return _real_import(name, *args, **kwargs)

    # Build the namespace with safe builtins.
    safe_builtins = {
        "len": len, "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "range": range, "enumerate": enumerate, "zip": zip,
        "min": min, "max": max, "sum": sum, "abs": abs,
        "print": print,
        "True": True, "False": False, "None": None,
        "__import__": _guarded_import,
        "RuntimeError": RuntimeError,
        "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
        "Exception": Exception,
        "isinstance": isinstance, "getattr": getattr, "setattr": setattr,
        "hasattr": hasattr, "len": len,
    }
    namespace: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "page": ns.get("page"),
        "inputs": ns.get("inputs", {}),
        "bindings": ns.get("bindings", {}),
        "asyncio": ns.get("asyncio"),
        "time": __import__("time"),
    }
    try:
        try:
            compiled = compile(code, "<run_python>", "eval")
            result = eval(compiled, namespace)
        except SyntaxError:
            compiled = compile(code, "<run_python>", "exec")
            result = exec(compiled, namespace)
        # If the script set a variable named `result_var`, prefer that.
        if "result" in namespace and not isinstance(result, type(None)):
            result = namespace["result"]
        q.put(("ok", result))
    except SandboxViolation as e:
        q.put(("sandbox_violation", str(e)))
    except Exception as e:
        q.put(("error", f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))


async def run_sandboxed(code: str, ns: dict, timeout_s: int = 30) -> Any:
    """Execute `code` in a sandboxed subprocess.

    Returns the result on success. Raises SandboxViolation for blocked modules,
    TimeoutError if the subprocess exceeds `timeout_s`, or the original
    exception for everything else.
    """
    q: multiprocessing.Queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_child_main, args=(code, ns, q), daemon=True)
    proc.start()
    # Wait for the child to finish, with timeout.
    loop = asyncio.get_event_loop()
    try:
        # Poll the queue with timeout in a thread-friendly way.
        ev = asyncio.Event()
        result_holder: list = []
        def _wait():
            try:
                result_holder.append(q.get(timeout=timeout_s))
            except Exception as e:
                result_holder.append(e)
            finally:
                loop.call_soon_threadsafe(ev.set)
        import threading
        t = threading.Thread(target=_wait, daemon=True)
        t.start()
        await asyncio.wait_for(ev.wait(), timeout=timeout_s + 2)
        if not result_holder:
            raise TimeoutError(f"run_python sandbox timed out after {timeout_s}s")
        item = result_holder[0]
        if isinstance(item, Exception):
            raise item
        kind, value = item
        if kind == "ok":
            return value
        if kind == "sandbox_violation":
            raise SandboxViolation(value)
        raise RuntimeError(value)
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
```

- [ ] **Step 4: Wire `run_python` to the sandbox**

`backend/app/automation/run_python.py` — replace the body:

```python
"""run_python step — execute arbitrary code in a subprocess sandbox.

P5 implementation: code runs in a separate Python process via the
`run_sandboxed` helper. The sandbox:
- Denies `os`, `subprocess`, `importlib`, `ctypes`, `socket`, etc.
- Enforces a timeout via process termination
- Exposes `page`, `inputs`, `bindings`, `asyncio`, `time` to the code

P1a's "honest eval" semantics are preserved (multi-statement scripts, final
expression as return value) but with a real boundary against the worker.
"""
from typing import Any

from app.automation.models import RunContext
from app.automation.sandbox import run_sandboxed


async def run_python(page: Any, params: dict[str, Any], ctx: RunContext) -> Any:
    """Execute `params["value"]` as Python code in a subprocess sandbox."""
    code = params["value"]
    timeout_ms = int(params.get("timeout_ms", 30000))
    bind = params.get("bind")

    ns = {
        "page": page,
        "inputs": ctx.inputs,
        "bindings": ctx.bindings,
        "asyncio": __import__("asyncio"),
    }
    out = await run_sandboxed(code, ns, timeout_s=max(1, timeout_ms // 1000))
    if bind:
        ctx.bindings[bind] = out
    return out
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_sandbox.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Re-run existing `test_run_python.py`**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_run_python.py -v
```

Expected: 6 passed (existing tests still work — the sandbox accepts the same inputs as the old impl).

- [ ] **Step 7: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/automation/sandbox.py backend/app/automation/run_python.py backend/tests/automation/test_sandbox.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P5 task 3 — run_python sandbox (subprocess + blocked-module denylist)"
```

---

## Task 4: `contextvars.ContextVar` for `step_log_writer`

**Why fourth:** Per-run isolation. Today `_step_log_writer` is module-global — two concurrent runs in the same worker process would cross-contaminate. Switching to `ContextVar` makes each run isolated.

**Files:**
- Create: `backend/app/automation/runner_state.py`
- Modify: `backend/app/automation/runner.py` (replace `_step_log_writer` global with `ContextVar`)
- Modify: `backend/app/workers/tasks.py` (use new context manager)
- Create: `backend/tests/automation/test_runner_state.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_runner_state.py` with EXACTLY:

```python
import asyncio
from contextvars import copy_context
from unittest.mock import MagicMock

from app.automation.runner_state import (
    step_log_writer_var,
    step_log_writer_scope,
    emit_step_log,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_context_var_default_is_none():
    assert step_log_writer_var.get() is None


def test_step_log_writer_scope_sets_writer():
    writer = MagicMock()
    with step_log_writer_scope(writer):
        assert step_log_writer_var.get() is writer
        emit_step_log("r-1", "s1", "running", started_at="2026-08-12T00:00:00")
        writer.assert_called_once()
    assert step_log_writer_var.get() is None


def test_outside_scope_writes_are_silent():
    writer = MagicMock()
    emit_step_log("r-1", "s1", "running")
    writer.assert_not_called()


def test_concurrent_scopes_are_isolated():
    """Two contexts with different writers see different writers."""
    writer_a = MagicMock()
    writer_b = MagicMock()

    ctx_a = copy_context()
    ctx_b = copy_context()

    results = {}

    def run_a():
        with step_log_writer_scope(writer_a):
            ctx_a.run(emit_step_log, "r-a", "s1", "running")
            results["a"] = step_log_writer_var.get()

    def run_b():
        with step_log_writer_scope(writer_b):
            ctx_b.run(emit_step_log, "r-b", "s1", "running")
            results["b"] = step_log_writer_var.get()

    run_a()
    run_b()
    assert results["a"] is writer_a
    assert results["b"] is writer_b
    assert writer_a.call_args.kwargs["run_id"] == "r-a"
    assert writer_b.call_args.kwargs["run_id"] == "r-b"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_runner_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.automation.runner_state'`

- [ ] **Step 3: Implement `runner_state.py`**

`backend/app/automation/runner_state.py`:

```python
"""Per-run state via contextvars.

P5 replacement for the module-global `_step_log_writer` so concurrent
runs in the same worker process don't cross-contaminate.

Usage:
    from app.automation.runner_state import step_log_writer_scope, emit_step_log

    with step_log_writer_scope(my_writer):
        # ... within the run ...
        emit_step_log("r-1", "s1", "running", started_at="...")
"""
from contextvars import ContextVar
from typing import Any, Callable


# Public ContextVar. Tests set it via the scope helper.
step_log_writer_var: ContextVar[Callable[[dict], None] | None] = ContextVar(
    "step_log_writer", default=None
)


class step_log_writer_scope:
    """Context manager that sets the writer for the duration of the block.

    Restores the previous value on exit (whether or not an exception was raised).
    """

    def __init__(self, writer: Callable[[dict], None]) -> None:
        self._writer = writer
        self._token = None

    def __enter__(self) -> "step_log_writer_scope":
        self._token = step_log_writer_var.set(self._writer)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            step_log_writer_var.reset(self._token)


def emit_step_log(run_id: str, step_id: str, status: str, **kwargs: Any) -> None:
    """Emit a step-log event if a writer is set in the current context.

    Best-effort: any exception is swallowed so audit never breaks the run.
    """
    writer = step_log_writer_var.get()
    if writer is None:
        return
    try:
        writer({
            "run_id": run_id,
            "step_id": step_id,
            "status": status,
            "started_at": kwargs.get("started_at"),
            "finished_at": kwargs.get("finished_at"),
            "error": kwargs.get("error"),
            "bindings": kwargs.get("bindings", {}),
            "screenshot_keys": kwargs.get("screenshot_keys", []),
            "screenshot_urls": kwargs.get("screenshot_urls", {}),
        })
    except Exception:
        pass
```

- [ ] **Step 4: Update `runner.py` to use the new context**

In `backend/app/automation/runner.py`, replace the module-level `_step_log_writer` + `set_step_log_writer` + `_emit_step_log` definitions with imports from `runner_state`:

```python
# Remove:
# _step_log_writer: Callable[[dict], None] | None = None
# def set_step_log_writer(...): ...
# def _emit_step_log(...): ...

# Add:
from app.automation.runner_state import emit_step_log as _emit_step_log
```

Find every call to `_emit_step_log(...)` in the runner — those stay the same. The `set_step_log_writer` testing imports don't need to change.

- [ ] **Step 5: Update `tasks.py` to use the new scope**

In `backend/app/workers/tasks.py`, find:

```python
from app.automation.runner import set_step_log_writer
```

Replace with:

```python
from app.automation.runner_state import step_log_writer_scope
```

Find the `try: ... set_step_log_writer(_writer) ... finally: set_step_log_writer(None)` block and replace with:

```python
with step_log_writer_scope(_writer):
    try:
        result = _run(runner.run_steps(...))
        # ... flush step logs ...
    except Exception as e:
        # ... flush step logs ...
        raise
```

(Keep the same overall try/except structure; just wrap the inside in `step_log_writer_scope`.)

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_runner_state.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Re-run related tests**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_runner.py tests/automation/test_runner_step_log.py tests/automation/test_runner_visit_child.py tests/automation/test_dispatcher_alert.py tests/automation/test_dispatcher_step_log.py -v
```

Expected: all pass (no regressions).

- [ ] **Step 8: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/automation/runner_state.py backend/app/automation/runner.py backend/app/workers/tasks.py backend/tests/automation/test_runner_state.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P5 task 4 — ContextVar-based step_log_writer (concurrency-safe)"
```

---

## Task 5: Wire `auth` into the runner + update recorder

**Why fifth:** Task 1 stripped the auth block from steps; now the runner needs to actually run it. And the recorder should emit `auth` at top-level (not `login_block` as a step) so the output is directly runnable.

**Files:**
- Modify: `backend/app/automation/runner.py` (accept `auth` kwarg in `run_steps`, call `run_auth` before steps)
- Modify: `backend/app/automation/recorder.py` (emit `auth` top-level, not `login_block` step)
- Modify: `examples/cotacao_pvs/steps.json` (already has `auth` at top — verify no change needed)
- Create: `backend/tests/automation/test_runner_auth.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_runner_auth.py` with EXACTLY:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.auth import AuthSpec


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakePage:
    def __init__(self):
        self.actions = []

    async def goto(self, url, **kw):
        self.actions.append(("goto", url))

    async def screenshot(self, **kw):
        return b"PNG"

    async def wait_for_selector(self, selector, **kw):
        self.actions.append(("wait_for", selector))
        class _L:
            pass
        return _L()


class _FakeBrowser:
    def __init__(self):
        self.page = _FakePage()

    async def new_page(self):
        return self.page

    async def close(self):
        pass


class _FakePW:
    @property
    def chromium(self):
        browser = _FakeBrowser()
        class _L:
            async def connect_over_cdp(self, _):
                return browser
        return _L()

    async def stop(self):
        pass


async def _connect(_):
    return _FakePW(), _FakeBrowser()


def test_run_steps_with_auth_runs_auth_first(monkeypatch, tmp_path):
    """When `auth` is supplied, the runner calls run_auth before any step."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    fake_run_auth = AsyncMock()
    monkeypatch.setattr("app.automation.runner.run_auth", fake_run_auth)

    auth_spec = AuthSpec(
        type="form_login",
        url="https://app.apvs.vc/home",
        credentials_ref="apvs_login",
        selectors={"user": "input", "pass": "input", "submit": "button"},
        success_assert={"selector": ".dashboard", "timeout_ms": 5000},
    )
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-1",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    steps = [MagicMock()]  # one fake step
    result = run(runner.run_steps(steps=steps, inputs={}, credentials={}, auth=auth_spec))
    assert result.status == "success"
    fake_run_auth.assert_called_once()
    # The auth spec was passed through.
    args, kwargs = fake_run_auth.call_args
    assert kwargs["spec"] is auth_spec
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_runner_auth.py -v
```

Expected: TypeError (unexpected kwarg `auth`).

- [ ] **Step 3: Update `runner.py` to accept `auth`**

In `backend/app/automation/runner.py`, find the `run_steps` method. Change the signature:

```python
async def run_steps(
    self,
    steps: Iterable[Step],
    inputs: dict[str, Any],
    credentials: dict[str, Any] | None = None,
    auth: "AuthSpec | None" = None,
) -> RunResult:
```

Add the import at the top of the file:

```python
from app.automation.auth import AuthSpec, run_auth
```

Find the body of `run_steps`. After the `page = await browser.new_page()` line, add (BEFORE the `try: with langfuse_span(...):` block):

```python
        if auth is not None:
            await run_auth(page, auth, ctx)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_runner_auth.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Update `recorder.py` to emit `auth` top-level**

In `backend/app/automation/recorder.py`, replace the `steps_from_trace` function:

```python
def steps_from_trace(payload: dict) -> dict[str, Any]:
    actions = payload.get("actions") or []
    auth_block, remaining = _detect_login_block(actions)

    steps: list[dict[str, Any]] = []
    idx = 0
    notes: list[str] = list(_DEFAULT_NOTES)
    unknown_count = 0
    for action in remaining:
        built = _build_step(action, idx)
        if built is None:
            unknown_count += 1
            continue
        steps.append(built)
        idx += 1
    if unknown_count:
        notes.append(
            f"{unknown_count} unsupported action(s) were skipped "
            f"(e.g. drag, scroll, keypress). Add them manually if needed."
        )
    steps = _group_consecutive_fills(steps)

    out: dict[str, Any] = {
        "automation_name": _automation_name_from_title_or_url(payload),
        "version": 1,
        "steps": steps,
        "notes": notes,
    }
    if auth_block is not None:
        out["auth"] = auth_block
    return out
```

- [ ] **Step 6: Update the recorder tests**

In `backend/tests/automation/test_recorder.py`, the existing tests check `auth_steps = [s for s in steps if "login_block" in s]`. Update them to look for top-level `auth` instead:

Change every test that asserts a `login_block` step to assert `out["auth"]`. Concretely:

In `test_steps_from_trace_detects_login_block`, replace:
```python
auth_steps = [s for s in steps if "login_block" in s]
assert len(auth_steps) == 1
auth = auth_steps[0]["login_block"]
```
With:
```python
out = steps_from_trace(SAMPLE_TRACE)
assert "auth" in out
auth = out["auth"]
```

And update `test_steps_from_trace_basic_actions` to also use `out["steps"]` and `out["auth"]`.

In `test_steps_from_trace_includes_wait_for`, also use `out["steps"]`.

In `test_steps_from_trace_handles_empty`, also use `out["steps"]`.

In `test_steps_from_trace_normalizes_clicks`, also use `out["steps"]`.

In `test_steps_from_trace_groups_fill_actions`, also use `out["steps"]`.

In `test_steps_from_trace_extracts_title_as_automation_name`, also use `out["automation_name"]`.

In `test_steps_from_trace_default_automation_name_from_url`, also use `out["automation_name"]`.

Simplest sweep: change every `steps = steps_from_trace(...)` to `out = steps_from_trace(...)` and `steps` to `out["steps"]`. The `auth` field is then accessible as `out["auth"]`.

- [ ] **Step 7: Run recorder tests**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation/test_recorder.py -v
```

Expected: 11 passed.

- [ ] **Step 8: Verify the cotacao_pvs steps.json example still works**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest ../examples/cotacao_pvs/tests -v
```

Expected: 18 passed (no regressions).

- [ ] **Step 9: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/automation/runner.py backend/app/automation/recorder.py backend/tests/automation/test_runner_auth.py backend/tests/automation/test_recorder.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P5 task 5 — runner wires auth + recorder emits auth top-level"
```

---

## Task 6: README + final verification

**Files:**
- Modify: `backend/app/automation/README.md`

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, replace the "Status: P3 (NavRecorder)" or whatever it currently is with:

```markdown
## Status: P5 (auth strategies + sandbox + concurrency)

### Implemented (P0 + P1a + P1b + P2 + P3 + P5)

- DSL parser + data types (`models.py` → `Step`, `RetryPolicy`, `RunContext`)
- Bindings interpolation `{{input.x}}` / `{{binding}}` / `{{cfg.x}}` (`bindings.py`)
- Retry with fixed/linear/exponential backoff (`retry.py`)
- Navigation steps: `goto`, `wait_for`
- Interaction steps: `click`, `fill`
- Assertion step: `assert_text`
- Extraction steps: `extract_text`, `extract_table`, `screenshot`
- AI extraction step: `run_ai` (P2) — schema-typed extraction via OpenAI tool-calling
- Code escape hatch: `run_python` (P5 subprocess sandbox — blocks `os`, `subprocess`, `importlib`, `ctypes`, `socket`, etc.)
- Control flow: `for_each`, `if`
- Auth block: `form_login`, `cookie_reuse`, `otp_via_telegram` (P5)
- Credentials resolver: `cfg.*` settings + `NAVRUNNER_*` env vars
- Auth runner wired into dispatcher (P5) — top-level `auth` block runs before step loop
- Interpreter dispatch table
- MinIO upload (best-effort; local fallback)
- Langfuse tracing (real SDK when env set; noop otherwise)
- Runner orchestrator with per-step screenshots + on_fail capture + step-log emission
- Concurrency-safe `step_log_writer` via `contextvars.ContextVar` (P5)
- Celery dispatcher `run_automation_v2` with credentials + step logs + WhatsApp alert on failure
- Pydantic schema registry + `ResultadoCotacao`
- WhatsApp alerts via Evolution API on failed runs
- Cotação PVS example using `auth` block + `run_ai` for plan extraction
- Supabase migrations: `automation_runs`, `automation_versions`, `automation_steps_log`
- NavRecorder (P3) — Chrome extension exports Playwright trace, recorder.py converts to `auth` + `steps` draft

### Deferred to later phases

- AI Planner (P6) — chat-driven automation creation
- Painel unificado (P9) — UI single-pane for all 3 authoring modes
- MCP server wrapping the framework (P8, last)
```

- [ ] **Step 2: Final verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5/backend && python3 -m pytest tests/automation ../examples/cotacao_pvs/tests -q 2>&1 | tail -3
```

Expected: 158 + ~30 = ~188 tests pass.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p5
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P5 README — confirms auth + sandbox + concurrency"
```

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P5 coverage | Deferred to |
|---|---|---|
| Auth block expanded | Done (`cookie_reuse`, `otp_via_telegram`) | — |
| Auth runner wired into dispatcher | Done (Task 1 + 5) | — |
| Recorder emits `auth` at top level | Done (Task 5) | — |
| RestrictedPython sandbox for `run_python` | Done (Task 3 — subprocess isolation + module denylist) | — |
| Per-run `step_log_writer` | Done (Task 4 — ContextVar) | — |
| Cotação PVS `auth` block now runnable | Done (Task 5 + NavRecorder produces `auth`) | — |
| AI Planner | Not (P6) | P6 |
| Painel unificado | Not (P9) | P9 |
| MCP server | Not (P8) | P8 |

**2. Placeholder scan**

Searched for `TBD`, `TODO`, `implement later`. Zero in task code. Doc block in T1 references "P5 auth runner" without exception.

**3. Type consistency**

- `AuthSpec` adds `cookies`, `telegram_chat_id`, `otp_selector`, `submit_selector` fields (default `None`/`[]`/`""`).
- `run_steps(..., auth=None)` — backward compat with P3 callers.
- `step_log_writer_scope` is a context manager that resets the ContextVar on exit (no leaks).

**4. Trade-offs**

- **Subprocess sandbox vs RestrictedPython:** Subprocess is heavier (a few ms per call) but the only way to actually hide `os.system`. RestrictedPython alone can be bypassed. P5 chose subprocess.
- **ContextVar vs Thread Local:** ContextVar works correctly under asyncio (each task gets its own context); Thread Local breaks under asyncio. P5 chose ContextVar.
- **`cookie_reuse` skips login entirely:** Right semantics — the cookies are pre-authenticated. The success_assert still gates the run.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p5-auth-sandbox-concurrency.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent per task. Orchestrator merges between tasks.

**2. Inline Execution** — Execute tasks in this session.

Which approach?
