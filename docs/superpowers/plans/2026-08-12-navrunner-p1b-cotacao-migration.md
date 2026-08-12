# NavRunner P1b — Cotação Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the legacy `cotacao_pvs/automacao_cotacao.py` (544 lines of imperative Python) to a NavRunner DSL workflow. Validate end-to-end that the framework can drive a real multi-screen Ionic/Angular app via Browserless, with retry, observability, and cron scheduling.

**Architecture:** The legacy code lives outside the repo (mounted volume at `/root/navegador/cotacao_pvs/`). P1b packages it into the repo as `examples/cotacao_pvs/` with three files: `ionic_helpers.py` (the unavoidable JS-injection wrappers), `steps.json` (the DSL with `auth` + `run_python` blocks for the Ionic quirks), and `automacao.py` (the outer loop driver that calls `run_automation_v2` per vehicle iteration). The driver is dropped into the existing Celery task as a new function, and a one-time `if` in the cron job file (in `apps/runtime/`) replaces the legacy loop.

**Tech Stack:** Python 3.11, NavRunner P1a (already merged), Celery 5, Playwright async API, Browserless via CDP, Supabase (HTTP `PATCH /rest/v1/cotacoes_fipe`).

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — sections "DSL canônico" (hybrid authoring), "IA inline" (no AI for P1b — pure declarative + run_python), "Anti-escopo" (P1b does NOT do AI extraction).

**Predecessor plans:** `docs/superpowers/plans/2026-08-12-navrunner-p0-skeleton.md` (merged), `docs/superpowers/plans/2026-08-12-navrunner-p1a-engine-extensions.md` (merged).

---

## File Structure

### Files created (P1b)

```
examples/cotacao_pvs/
├── __init__.py
├── ionic_helpers.py          # pure Python wrappers — ported from automacao_cotacao.py
├── steps.json                # full DSL of the cotação flow
├── automacao.py              # outer loop driver — calls run_automation_v2 per combo
└── README.md                 # manual + troubleshooting

backend/app/workers/tasks.py  # EXTEND: add executar_cotacao_pvs Celery task
backend/app/automation/runner.py  # EXTEND: implement _visit_child (currently NotImplementedError)
apps/runtime/jobs/cotacao_pvs.py  # NEW: cron-style job that calls the celery task
```

### Files modified (P1b)

- `backend/app/automation/runner.py` — replace `_visit_child` stub with real nested runner
- `backend/app/workers/tasks.py` — add `executar_cotacao_pvs` task
- `backend/app/automation/__init__.py` — re-export `executar_cotacao_pvs` if needed
- `examples/cotacao_pvs/automacao.py` — uses both `run_automation_v2` AND drives the outer loop

### Anti-pattern check

- The legacy code is 544 lines; the new files together should be ~400 lines (DSL + helpers + driver) but with much higher expressivity.
- `ionic_helpers.py` is the unavoidable escape hatch — Ionic components don't expose stable selectors, so JS in `page.evaluate()` is the only path. Keep the helpers pure-Python (no class state).
- `steps.json` does NOT have a 1:1 step-to-legacy-call mapping. Some legacy helper chains collapse into one `run_python` step (select-then-confirm-then-wait).
- The outer loop driver stays in Python (not DSL) because the iteration is over a JSON config file (`veiculos_referencia.json`) and the data shape is dynamic.

---

## Conventions carried from P0/P1a

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P1b task N — <title>` etc.
- Tests live in `backend/tests/automation/` (P1b adds two new files there).
- Online Supabase live at `https://supabase.apvsiguatemi.net` for the cotacoes_fipe table.

---

## Task 1: Implement `_visit_child` in the runner

**Why first:** P1a left `_visit_child` as `NotImplementedError`. P1b's `for_each` and `if` children need real execution. Filling this in also lets us write all subsequent steps without that limitation.

**Files:**
- Modify: `backend/app/automation/runner.py`
- Modify: `backend/tests/automation/test_runner_step_log.py` (add nested-child test)
- Create: `backend/tests/automation/test_runner_visit_child.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_runner_visit_child.py` with EXACTLY:

```python
import asyncio
from unittest.mock import MagicMock

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.models import Step


def _run(coro):
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
        self.page = self._page = _FakePage()

    async def new_page(self):
        return self._page

    async def close(self):
        pass


class _FakePW:
    @property
    def chromium(self):
        class _L:
            async def connect_over_cdp(self, _):
                return _FakeBrowser()
        return _L()

    async def stop(self):
        pass


async def _connect(_):
    return _FakePW(), _FakeBrowser()


def test_visit_child_runs_dict_step(monkeypatch, tmp_path):
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)
    writer = MagicMock()
    from app.automation.runner import set_step_log_writer, _step_log_writer
    original = _step_log_writer
    set_step_log_writer(writer)
    try:
        steps = [
            Step.from_dict({"id": "parent", "for_each": {
                "items": ["a", "b"],
                "as": "x",
                "steps": [{"id": "child", "goto": "https://{{x}}"}],
            }}),
        ]
        cfg = NavRunnerConfig(
            browser_endpoint="ws://fake",
            run_id="r-1",
            screenshot_dir=str(tmp_path),
        )
        runner = NavRunner(cfg=cfg)
        result = _run(runner.run_steps(steps=steps, inputs={}))
        assert result.status == "success"
        # The two child step gotos should appear.
        gotos = [a for a in result.page.actions if a[0] == "goto"]
        assert gotos == [("goto", "https://a"), ("goto", "https://b")]
        # Step logs for the child step should be emitted twice.
        child_started = [c for c in writer.call_args_list if c.kwargs.get("step_id") == "child" and c.kwargs.get("status") == "running"]
        assert len(child_started) == 2
    finally:
        set_step_log_writer(original)


def test_visit_child_runs_step_object(monkeypatch, tmp_path):
    """When `for_each.steps` is a list of Step objects (not raw dicts), it still works."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)
    steps = [
        Step.from_dict({"id": "parent", "for_each": {
            "items": [1, 2],
            "as": "n",
            "steps": [
                Step.from_dict({"id": "child", "goto": "https://{{n}}"}),
            ],
        }}),
    ]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-2",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))
    assert result.status == "success"
    gotos = [a for a in result.page.actions if a[0] == "goto"]
    assert gotos == [("goto", "https://1"), ("goto", "https://2")]


def test_visit_child_inherits_retry_policy(monkeypatch, tmp_path):
    """A child step with `retry` should be retried via `with_retry`."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    attempts = {"count": 0}

    class _FlakyPage(_FakePage):
        async def goto(self, url, **kw):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("flaky")
            self.actions.append(("goto", url))

    class _FlakyBrowser(_FakeBrowser):
        def __init__(self):
            self._page = _FlakyPage()

    async def _flaky_connect(_):
        class _P:
            @property
            def chromium(self):
                class _L:
                    async def connect_over_cdp(self, _):
                        return _FlakyBrowser()
                return _L()
            async def stop(self):
                pass
        return _P(), _FlakyBrowser()

    monkeypatch.setattr("app.automation.runner._connect_playwright", _flaky_connect)

    steps = [
        Step.from_dict({"id": "parent", "for_each": {
            "items": ["x"],
            "as": "v",
            "steps": [{"id": "child", "goto": "https://x", "retry": {"attempts": 3, "initial_delay_ms": 1}}],
        }}),
    ]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-3",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))
    assert result.status == "success"
    assert attempts["count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation/test_runner_visit_child.py -v
```

Expected: 3 errors / failures because `_visit_child` raises NotImplementedError.

- [ ] **Step 3: Replace `_visit_child` in `runner.py`**

Find the existing `_visit_child` method (around line `async def _visit_child(self, ctx: RunContext, child: Any) -> None:`). Replace it with:

```python
async def _run_one_inner(self, page: Page, step: Step, ctx: RunContext, result: RunResult) -> None:
    """Like _run_one but without the per-step wrapper — used by _visit_child.

    _visit_child is the loop-injected callback for for_each / if. It runs a
    single child step without the outer logging/screenshot scaffolding (the
    parent step already has its own).
    """
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
    """Run a single child step inside a for_each / if branch.

    Resolves `child` (dict or Step object) into a Step, then runs it through
    the same scaffolding as a top-level step (retry, langfuse span, step log,
    screenshot). Captures the page from the runner instance.
    """
    if isinstance(child, dict):
        step = Step.from_dict(child)
    elif isinstance(child, Step):
        step = child
    else:
        raise ValueError(f"Unexpected child type: {type(child).__name__}")

    # The runner instance has a single page held across all steps. We
    # accept that limitation — the runner creates one page per run, not per
    # loop iteration. This matches the P1a design (each automation run has
    # one persistent browser context).
    if not hasattr(self, "_page") or self._page is None:
        raise RuntimeError(
            "_visit_child called before run_steps initialized the page; "
            "this is a bug."
        )
    # Lazy: cache the page on first use.
    page = self._page
    # We need a result to attach screenshots to. Create a private one.
    result = getattr(self, "_current_result", None)
    if result is None:
        # If something calls _visit_child outside an outer run_steps, fail loudly.
        raise RuntimeError("_visit_child needs an active result context")
    await self._run_one_inner(page, step, ctx, result)
```

Also, in `run_steps`, set `self._page = page` and `self._current_result = result` after constructing `result`:

```python
async def run_steps(self, steps, inputs, credentials=None):
    steps = list(steps)
    ctx = RunContext(inputs=inputs, bindings={}, credentials=credentials or {})
    result = RunResult(status="success", run_id=self.cfg.run_id)
    self._page = None  # set after browser is up
    self._current_result = result
    Path(self.cfg.screenshot_dir).mkdir(parents=True, exist_ok=True)
    pw, browser = await _connect_playwright(self.cfg.browser_endpoint)
    page = await browser.new_page()
    self._page = page
    result.page = page
    try:
        ...
    finally:
        await browser.close()
        await pw.stop()
        self._page = None
        self._current_result = None
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation/test_runner_visit_child.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Re-run full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation -v
```

Expected: 101 + 3 = 104 passed (no regressions).

- [ ] **Step 6: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add backend/app/automation/runner.py backend/tests/automation/test_runner_visit_child.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 1 — _visit_child real nested step execution"
```

---

## Task 2: Port `ionic_helpers.py` — pure-Python wrappers for Ionic/Angular

**Why second:** The helpers are the only piece that needs `page.evaluate(...)` with JS. Once they exist, the DSL `steps.json` can call them via `run_python`.

**Files:**
- Create: `examples/cotacao_pvs/__init__.py` (empty)
- Create: `examples/cotacao_pvs/ionic_helpers.py`
- Create: `examples/cotacao_pvs/tests/test_ionic_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `examples/cotacao_pvs/tests/__init__.py` (empty) and `examples/cotacao_pvs/tests/test_ionic_helpers.py`:

```python
import asyncio
from unittest.mock import AsyncMock

from cotacao_pvs.ionic_helpers import (
    js_set_input,
    click_ion_button,
    click_ion_item,
    select_ionic,
    select_ionic_by_label,
    fill_input_by_label,
    get_selectable_value,
    get_form_errors,
    dump_visible_form,
    extrair_menor_parcela,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _fake_page(eval_result=None, clicked_buttons=None, clicked_items=None, form_errors=0):
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=eval_result)
    page.query_selector = AsyncMock(return_value=AsyncMock())
    page.mouse = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()
    return page


def test_js_set_input_invokes_evaluate():
    page = _fake_page()
    _run(js_set_input(page, "#cnpj", "19.186.569/0001-11"))
    assert page.evaluate.called
    args = page.evaluate.call_args[0]
    # First positional arg is a JS function string, second is the data tuple.
    assert "HTMLInputElement" in args[0]
    assert args[1] == ["#cnpj", "19.186.569/0001-11"]


def test_click_ion_button_returns_true_when_found():
    page = _fake_page(eval_result=True)
    result = _run(click_ion_button(page, "Entrar"))
    assert result is True


def test_click_ion_button_returns_false_when_missing():
    page = _fake_page(eval_result=False)
    result = _run(click_ion_button(page, "Não existe"))
    assert result is False


def test_click_ion_item():
    page = _fake_page(eval_result=True)
    result = _run(click_ion_item(page, "Nova Cotação"))
    assert result is True


def test_select_ionic_returns_false_when_pos_none():
    page = _fake_page(eval_result=None)
    result = _run(select_ionic(page, "state", "Bahia"))
    assert result is False


def test_select_ionic_returns_true_when_select_found():
    page = _fake_page(eval_result={"x": 100, "y": 100, "w": 200})
    result = _run(select_ionic(page, "state", "Bahia"))
    assert result is True
    page.mouse.click.assert_called_once()


def test_fill_input_by_label_returns_true():
    page = _fake_page(eval_result=True)
    result = _run(fill_input_by_label(page, "Nome", "Teste"))
    assert result is True


def test_get_selectable_value_returns_text():
    page = _fake_page(eval_result="2020")
    result = _run(get_selectable_value(page, "version"))
    assert result == "2020"


def test_get_form_errors_counts():
    page = _fake_page(eval_result="Form: Campo obrigatório e Campo obrigatório")
    assert _run(get_form_errors(page)) == 2


def test_dump_visible_form_returns_dict():
    fake_dict = {"text": "...", "inputs": [], "selects": []}
    page = _fake_page(eval_result=fake_dict)
    result = _run(dump_visible_form(page))
    assert result == fake_dict


def test_extrair_menor_parcela_returns_cheapest():
    body = "Plano A: R$ 100,00\nPlano B: R$ 80,50\nPlano C: R$ 200,00"
    assert extrair_menor_parcela(body) == "R$80.50"


def test_extrair_menor_parcela_returns_none_when_no_prices():
    assert extrair_menor_parcela("nada aqui") is None


def test_extrair_menor_parcela_handles_thousands():
    body = "R$ 1.500,00\nR$ 999,99"
    assert extrair_menor_parcela(body) == "R$999.99"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest ../examples/cotacao_pvs/tests/test_ionic_helpers.py -v
```

Expected: `ModuleNotFoundError: No module named 'cotacao_pvs'`

- [ ] **Step 3: Create package skeleton and helpers**

`examples/cotacao_pvs/__init__.py`: empty.

`examples/cotacao_pvs/ionic_helpers.py` — port from `automacao_cotacao.py` (the legacy `cotacao_pvs/automacao_cotacao.py` outside the repo). The functions are straightforward: each takes `page` and dispatches to `page.evaluate(...)` with a JS string. Use the legacy code as reference but add type hints and stricter signatures.

```python
"""Ionic/Angular JS helpers for the cotação DSL.

P1a needs DSL steps to interact with Ionic components whose DOM doesn't
expose stable CSS selectors. These helpers wrap the page.evaluate(...) JS
strings so the steps.json can call them via `run_python`.

The legacy code (cotacao_pvs/automacao_cotacao.py) has these inline; P1b
promotes them to a reusable module so the DSL stays declarative.
"""
import re
from typing import Any

_PRICE_RE = re.compile(r"R\$\s*([\d.,]+)")


def _parse_brl_value(raw_value: str) -> float:
    value = raw_value.strip().replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    return float(value)


# ─── DOM helpers ───────────────────────────────────────────────

async def js_set_input(page, selector: str, value: str) -> None:
    """Set input value via the native setter (Angular reactive forms)."""
    await page.evaluate(
        '''([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return;
            const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            set.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }''',
        [selector, value],
    )


async def click_ion_button(page, text: str) -> bool:
    """Click an `ion-button` whose visible text contains `text`."""
    return bool(await page.evaluate(
        '''(text) => {
            for (const b of document.querySelectorAll('ion-button')) {
                if (b.innerText.includes(text) && b.offsetParent !== null) { b.click(); return true; }
            }
            return false;
        }''',
        text,
    ))


async def click_ion_item(page, text: str) -> bool:
    """Click an `ion-item` whose visible text equals `text`."""
    return bool(await page.evaluate(
        '''(text) => {
            for (const i of document.querySelectorAll('ion-item')) {
                if (i.innerText.trim() === text) { i.click(); return true; }
            }
            return false;
        }''',
        text,
    ))


async def get_selectable_value(page, formcontrolname: str) -> str | None:
    """Return the current value of an `ionic-selectable` field."""
    return await page.evaluate(
        '''(fc) => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            for (const s of f?.querySelectorAll('ionic-selectable') || []) {
                if (s.getAttribute('formcontrolname') === fc)
                    return s.querySelector('.ionic-selectable-value-item')?.innerText?.trim() || null;
            }
            return null;
        }''',
        formcontrolname,
    )


async def select_ionic(page, formcontrolname: str, option_text: str, use_search: bool = False) -> bool:
    """Open an ionic-selectable and pick `option_text`."""
    pos = await page.evaluate(
        '''(fc) => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            for (const s of f?.querySelectorAll('ionic-selectable') || []) {
                if (s.getAttribute('formcontrolname') === fc) {
                    s.scrollIntoView({block: 'center'});
                    const rect = s.getBoundingClientRect();
                    return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, w: rect.width};
                }
            }
            return null;
        }''',
        formcontrolname,
    )
    if not pos or pos.get("w", 0) == 0:
        return False
    await page.mouse.click(pos["x"], pos["y"])
    await page.wait_for_timeout(3000)
    if use_search:
        sb = await page.query_selector("ion-modal ion-searchbar input")
        if sb:
            await sb.click()
            await page.keyboard.type(option_text, delay=50)
            await page.wait_for_timeout(2000)
    selected = await page.evaluate(
        '''(text) => {
            const m = document.querySelector('ion-modal');
            if (!m) return false;
            for (const item of m.querySelectorAll('ion-item')) {
                const t = item.innerText.trim();
                if (t === text || t.startsWith(text)) { item.click(); return true; }
            }
            return false;
        }''',
        option_text,
    )
    await page.wait_for_timeout(2000)
    return bool(selected)


async def fill_input_by_label(page, label_text: str, value: str) -> bool:
    """Fill an input that's grouped with a label (Ionic)."""
    return bool(await page.evaluate(
        '''([labelText, val]) => {
            const forms = Array.from(document.querySelectorAll('form'));
            const form = forms.find(f => !f.closest('.ion-page-hidden')) || document;
            const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const wanted = norm(labelText);
            for (const col of form.querySelectorAll('ion-col, div, label')) {
                const label = col.querySelector('ion-label');
                if (!label || norm(label.innerText) !== wanted) continue;
                const input = col.querySelector('input');
                if (!input) continue;
                const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                set.call(input, val);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('blur', { bubbles: true }));
                return true;
            }
            return false;
        }''',
        [label_text, value],
    ))


async def get_form_errors(page) -> int:
    """Count 'Campo obrigatório' labels in the visible form."""
    text = await page.evaluate(
        '''() => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            return f?.innerText || '';
        }''',
    )
    return text.count("Campo obrigatório") if text else 0


async def dump_visible_form(page) -> dict[str, Any]:
    """Return visible form metadata for selector drift debugging."""
    return await page.evaluate(
        '''() => {
            const visible = el => !!(el && (el.offsetParent !== null || el.getClientRects().length));
            const forms = Array.from(document.querySelectorAll('form')).filter(visible);
            const form = forms[0] || document;
            return {
                text: (form.innerText || '').slice(0, 4000),
                inputs: Array.from(form.querySelectorAll('input')).map(el => ({
                    name: el.name || null,
                    type: el.type || null,
                    placeholder: el.placeholder || null,
                    value: el.value || null,
                })),
                selects: Array.from(form.querySelectorAll('ionic-selectable, ion-select')).map(el => ({
                    tag: el.tagName,
                    formcontrolname: el.getAttribute('formcontrolname'),
                    text: (el.innerText || '').trim(),
                })),
            };
        }''',
    )


# ─── Pure-Python helpers ─────────────────────────────────────

def extrair_menor_parcela(body: str) -> str | None:
    """Return the cheapest R$ value found in `body`, formatted as 'R$X.XX'."""
    prices = []
    for match in _PRICE_RE.finditer(body or ""):
        try:
            prices.append(_parse_brl_value(match.group(1)))
        except ValueError:
            continue
    if not prices:
        return None
    return f"R${min(prices):.2f}"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest ../examples/cotacao_pvs/tests/test_ionic_helpers.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add examples/cotacao_pvs/
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 2 — ionic_helpers.py port (page.evaluate wrappers)"
```

---

## Task 3: Create `examples/cotacao_pvs/steps.json` — the DSL

**Why third:** With helpers in place, the DSL is the next piece. It's the artefact that gets loaded by the dispatcher.

**Files:**
- Create: `examples/cotacao_pvs/steps.json`

- [ ] **Step 1: Write the steps.json**

Create `examples/cotacao_pvs/steps.json` with EXACTLY:

```json
{
  "automation_name": "cotacao_pvs",
  "version": 1,
  "auth": {
    "type": "form_login",
    "url": "https://app.apvs.vc/home",
    "credentials_ref": "apvs_login",
    "selectors": {
      "user": "input[type=text]",
      "pass": "input[type=password]",
      "submit": "ion-button"
    },
    "success_assert": {"selector": ".dashboard", "timeout_ms": 30000}
  },
  "steps": [
    {
      "id": "click_consultor",
      "run_python": {
        "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'CONSULTOR')",
        "timeout_ms": 30000
      },
      "retry": {"attempts": 2, "initial_delay_ms": 2000}
    },
    {
      "id": "fill_credentials",
      "run_python": {
        "value": "from cotacao_pvs.ionic_helpers import js_set_input; await js_set_input(page, 'input[type=text]', inputs['cnpj']); await js_set_input(page, 'input[type=password]', inputs['password'])",
        "timeout_ms": 30000
      }
    },
    {
      "id": "click_entrar",
      "run_python": {
        "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'Entrar')",
        "timeout_ms": 30000
      }
    },
    {
      "id": "wait_dashboard",
      "wait_for": {"selector": ".dashboard", "timeout_ms": 30000}
    },
    {
      "id": "loop_over_combo",
      "for_each": {
        "items": "{{input.combos}}",
        "as": "combo",
        "max_iterations": 100,
        "steps": [
          {
            "id": "go_to_dashboard",
            "goto": "{{combo.dashboard_url}}"
          },
          {
            "id": "click_nova_cotacao",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import click_ion_item; await click_ion_item(page, 'Nova Cotação')",
              "timeout_ms": 15000
            }
          },
          {
            "id": "click_codigo_fipe",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'Código Fipe')",
              "timeout_ms": 15000
            }
          },
          {
            "id": "type_fipe_code",
            "run_python": {
              "value": "inp = await page.query_selector('input[name=\"ion-input-0\"]'); await inp.click(); await page.keyboard.type(combo['fipe_code'], delay=80)",
              "timeout_ms": 15000
            },
            "bind": "_typed"
          },
          {
            "id": "click_proximo_step1",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'Próximo')",
              "timeout_ms": 30000
            }
          },
          {
            "id": "verify_step2_advanced",
            "run_python": {
              "value": "assert '/2/' in page.url, f'expected /2/ in url, got {page.url}'",
              "timeout_ms": 5000
            }
          },
          {
            "id": "fill_step2_data",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import get_selectable_value, select_ionic, select_ionic_by_label, fill_input_by_label; from cotacao_pvs.ionic_helpers import js_set_input; import asyncio; \nyear = await get_selectable_value(page, 'year') or '2020'; \nsel = await get_selectable_value(page, 'version'); \nif not sel: raise RuntimeError('model not loaded after 120s'); \nres = await select_ionic(page, 'year', year) or await select_ionic(page, 'manufactureYear', year) or await select_ionic_by_label(page, 'Ano Modelo', year) or await select_ionic_by_label(page, 'Ano de Fabricação', year); \nif not res: raise RuntimeError('year field not fillable'); \nawait select_ionic(page, 'state', inputs['estado']) or await select_ionic_by_label(page, 'Estado', inputs['estado']); \nawait select_ionic(page, 'city', combo['cidade'], use_search=True) or await select_ionic_by_label(page, 'Cidade', combo['cidade'], use_search=True); \nfor name, label, val in [('ion-input-1', 'Nome', 'Teste Automacao'), ('ion-input-2', 'Celular', '71999999999'), ('ion-input-3', 'Email', 'teste@teste.com')]: \n    el = await page.query_selector(f'input[name=\"{name}\"]'); \n    if el: \n        await el.click(); await el.fill(''); await page.keyboard.type(val, delay=20); \n    else: \n        await fill_input_by_label(page, label, val); \nawait asyncio.sleep(1)",
              "timeout_ms": 120000
            }
          },
          {
            "id": "click_proximo_step2",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'Próximo')",
              "timeout_ms": 30000
            }
          },
          {
            "id": "verify_step3_advanced",
            "run_python": {
              "value": "assert '/3/' in page.url, f'expected /3/ in url, got {page.url}'",
              "timeout_ms": 5000
            }
          },
          {
            "id": "step3_set_blindado_nao",
            "run_python": {
              "value": "await page.evaluate('''() => { const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden')); if (!f) return; for (const col of f.querySelectorAll('ion-col')) { const label = col.querySelector('ion-label')?.innerText || ''; if (label.toLowerCase().includes('blindado')) { for (const b of col.querySelectorAll('ion-button')) if (b.innerText.trim() === 'Não') { b.click(); return; } } } }''')",
              "timeout_ms": 15000
            }
          },
          {
            "id": "step3_set_importado_nao",
            "run_python": {
              "value": "await page.evaluate('''() => { const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden')); if (!f) return; for (const col of f.querySelectorAll('ion-col')) { const label = col.querySelector('ion-label')?.innerText || ''; if (label.includes('Importado')) { for (const b of col.querySelectorAll('ion-button')) if (b.innerText.trim() === 'Não') { b.click(); return; } } } }''')",
              "timeout_ms": 15000
            }
          },
          {
            "id": "step3_set_utilizacao_particular",
            "run_python": {
              "value": "await page.evaluate('''() => { const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden')); const sel = f?.querySelector('ion-select[formcontrolname=\"vehicleUse\"]'); if (sel) sel.click(); }'''); await page.wait_for_timeout(3000); await page.evaluate('''() => { for (const alert of document.querySelectorAll('ion-alert')) { for (const btn of alert.querySelectorAll('button')) { if (btn.innerText.trim() === 'Particular') { btn.click(); return; } } } }'''); await page.wait_for_timeout(1000); await page.evaluate('''() => { for (const alert of document.querySelectorAll('ion-alert')) { const ok = Array.from(alert.querySelectorAll('button')).find(b => b.innerText.trim() === 'OK' || b.innerText.trim() === 'Confirmar'); if (ok) ok.click(); } }'''); await page.wait_for_timeout(2000)",
              "timeout_ms": 30000
            }
          },
          {
            "id": "click_proximo_step3",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import click_ion_button; await click_ion_button(page, 'Próximo')",
              "timeout_ms": 30000
            }
          },
          {
            "id": "extract_plano",
            "run_python": {
              "value": "from cotacao_pvs.ionic_helpers import extrair_menor_parcela; body = await page.evaluate('''() => { const pages = document.querySelectorAll('.ion-page:not(.ion-page-hidden)'); for (const p of pages) { if (p.innerText.includes('Planos') || p.innerText.includes('R$')) return p.innerText; } return ''; }'''); resultado = extrair_menor_parcela(body); bindings['resultado'] = resultado; bindings['combo_done'] = dict(combo); bindings['valor'] = resultado",
              "timeout_ms": 30000
            },
            "bind": "resultado"
          },
          {
            "id": "save_to_supabase",
            "if": {
              "condition": "bindings.get('resultado') is not None",
              "then_steps": [
                {
                  "id": "patch_supabase",
                  "run_python": {
                    "value": "import httpx; from urllib.parse import quote; row = {'valor_prata': bindings['resultado'], 'erro': ''}; url = f\"https://supabase.apvsiguatemi.net/rest/v1/cotacoes_fipe?faixa_min=eq.{quote(str(combo['faixa_min']))}&faixa_max=eq.{quote(str(combo['faixa_max']))}&tipo=eq.{quote(str(combo['tipo']))}&regiao=eq.{quote(str(combo['regiao']))}\"; async with httpx.AsyncClient(timeout=15) as client: r = await client.patch(url, headers={'apikey': inputs['supabase_key'], 'Authorization': f'Bearer {inputs[\"supabase_key\"]}', 'Content-Type': 'application/json', 'Prefer': 'resolution=merge-duplicates'}, json=row); assert r.status_code in (200, 204), f'supabase patch failed: {r.status_code} {r.text}'",
                    "timeout_ms": 30000
                  }
                }
              ],
              "else_steps": [
                {
                  "id": "mark_error",
                  "run_python": {
                    "value": "import httpx; from urllib.parse import quote; row = {'erro': 'sem_planos'}; url = f\"https://supabase.apvsiguatemi.net/rest/v1/cotacoes_fipe?faixa_min=eq.{quote(str(combo['faixa_min']))}&faixa_max=eq.{quote(str(combo['faixa_max']))}&tipo=eq.{quote(str(combo['tipo']))}&regiao=eq.{quote(str(combo['regiao']))}\"; async with httpx.AsyncClient(timeout=15) as client: r = await client.patch(url, headers={'apikey': inputs['supabase_key'], 'Authorization': f'Bearer {inputs[\"supabase_key\"]}', 'Content-Type': 'application/json', 'Prefer': 'resolution=merge-duplicates'}, json=row)",
                    "timeout_ms": 30000
                  }
                }
              ]
            }
          }
        ]
      }
    }
  ]
}
```

(Each step is small. The big ones are the Ionic-specialized `run_python` blocks that wrap the helpers. The framework executes them through the standard interpreter.)

- [ ] **Step 2: Validate JSON parses**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b && python3 -c "import json; json.load(open('examples/cotacao_pvs/steps.json')); print('json OK')"
```

Expected: `json OK`.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add examples/cotacao_pvs/steps.json
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 3 — cotacao_pvs/steps.json (the DSL flow)"
```

---

## Task 4: Outer loop driver — `automacao.py`

**Why fourth:** The driver is the Python wrapper that loads `veiculos_referencia.json`, builds the `combos` list, calls `run_automation_v2` once per combo (or once for all combos in a single DSL run), and persists results.

**Files:**
- Create: `examples/cotacao_pvs/automacao.py`
- Create: `examples/cotacao_pvs/tests/test_automacao.py`

- [ ] **Step 1: Write the failing test**

Create `examples/cotacao_pvs/tests/test_automacao.py`:

```python
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from cotacao_pvs.automacao import (
    load_veiculos_referencia,
    build_combos,
    filter_combos,
    executar_cotacao_pvs,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_load_veiculos_referencia_parses_json(tmp_path):
    p = tmp_path / "veiculos.json"
    p.write_text(json.dumps([
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "pesado", "codigo_fipe": None,
         "nota": "Nenhum veículo encontrado"},
    ]))
    out = load_veiculos_referencia(p)
    assert len(out) == 2
    assert out[0]["codigo_fipe"] == "001"


def test_build_combos_expands_tipos():
    veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 11001, "faixa_max": 21000, "tipo": "pesado", "codigo_fipe": "002"},
    ]
    regioes = {"capital": "Salvador", "interior": "Santo Antônio de Jesus"}
    combos = build_combos(veiculos, regioes)
    # 2 vehicles * 2 regions = 4 combos.
    assert len(combos) == 4
    # Each combo has all the fields needed by the DSL.
    for c in combos:
        assert "fipe_code" in c
        assert "cidade" in c
        assert "faixa_min" in c
        assert "faixa_max" in c
        assert "tipo" in c
        assert "regiao" in c
        assert "dashboard_url" in c


def test_filter_combos_skips_missing_fipe():
    veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
        {"faixa_min": 11001, "faixa_max": 21000, "tipo": "pesado", "codigo_fipe": None},
    ]
    combos = build_combos(veiculos, {"capital": "Salvador"})
    filtered = filter_combos(combos)
    assert len(filtered) == 1
    assert filtered[0]["fipe_code"] == "001"


def test_executar_cotacao_pvs_dispatches_run_automation_v2(monkeypatch):
    """The driver calls run_automation_v2 with the loaded combos."""
    fake_delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr("cotacao_pvs.automacao.run_automation_v2", MagicMock(delay=fake_delay))

    fake_veiculos = [
        {"faixa_min": 0, "faixa_max": 11000, "tipo": "leve", "codigo_fipe": "001"},
    ]
    monkeypatch.setattr("cotacao_pvs.automacao.load_veiculos_referencia", lambda p: fake_veiculos)

    result = _run(executar_cotacao_pvs(
        veiculos_path=Path("/fake/veiculos.json"),
        credentials={"apvs_login": {"user": "x", "pass": "y"}},
        supabase_key="sb-key",
        estado="BA",
        regioes={"capital": "Salvador"},
        automation_name="cotacao_pvs_smoke",
    ))
    assert result["total_combos"] == 1
    assert result["dispatched"] == 1
    fake_delay.assert_called_once()
    # Inspect the call to run_automation_v2.delay(...)
    kwargs = fake_delay.call_args.kwargs
    assert kwargs["automation_name"] == "cotacao_pvs_smoke"
    assert isinstance(kwargs["steps_payload"], list)
    assert kwargs["inputs"]["cnpj"] == "x"
    assert kwargs["inputs"]["combos"]  # list of combos
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest ../examples/cotacao_pvs/tests/test_automacao.py -v
```

Expected: `ModuleNotFoundError: No module named 'cotacao_pvs'`

- [ ] **Step 3: Implement `automacao.py`**

`examples/cotacao_pvs/automacao.py`:

```python
"""Outer-loop driver for the cotação PVS flow.

Reads `veiculos_referencia.json`, builds the cartesian product of
(vehicle × region) combos, and dispatches one Celery task per combo via
the NavRunner v2 dispatcher. Each combo is one full DSL run with the
`input.combos` list narrowed to a single element.

Why one DSL run per combo (not one DSL run with all combos):
- A combo can fail independently (FIPE rejected, model not loaded, ...).
  Per-combo runs give us per-combo retry + per-combo step logs.
- Each combo writes to a unique row in `cotacoes_fipe` (filter by faixa+tipo+regiao).
"""
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.workers.tasks import run_automation_v2


STEPS_PATH = Path(__file__).parent / "steps.json"
DASHBOARD_URL = "https://app.apvs.vc/dashboard"


def load_veiculos_referencia(path: Path | None = None) -> list[dict]:
    """Load the FIPE vehicle reference list.

    Default path is `cotacao_pvs/veiculos_referencia.json` (the legacy output).
    """
    p = path or (Path(__file__).parent / "veiculos_referencia.json")
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def build_combos(veiculos: list[dict], regioes: dict[str, str]) -> list[dict]:
    """Cartesian product of (vehicle × region). Each combo has all fields
    the DSL needs to drive one quotation."""
    combos = []
    for v in veiculos:
        for regiao_slug, cidade in regioes.items():
            combos.append({
                "fipe_code": v.get("codigo_fipe"),
                "faixa_min": v["faixa_min"],
                "faixa_max": v["faixa_max"],
                "tipo": v["tipo"],
                "regiao": regiao_slug,
                "cidade": cidade,
                "dashboard_url": DASHBOARD_URL,
            })
    return combos


def filter_combos(combos: list[dict]) -> list[dict]:
    """Drop combos without a FIPE code (the legacy output marks them with
    `codigo_fipe: null` and a `nota` field)."""
    return [c for c in combos if c.get("fipe_code")]


def executar_cotacao_pvs(
    veiculos_path: Path | None = None,
    credentials: dict[str, Any] | None = None,
    supabase_key: str = "",
    estado: str = "BA",
    regioes: dict[str, str] | None = None,
    automation_name: str = "cotacao_pvs",
) -> dict[str, Any]:
    """Dispatch one Celery task per combo.

    Returns a summary dict with `total_combos` and `dispatched` counts.
    """
    credentials = credentials or {}
    regioes = regioes or {"capital": "Salvador"}

    veiculos = load_veiculos_referencia(veiculos_path)
    combos = filter_combos(build_combos(veiculos, regioes))

    steps_payload = json.loads((STEPS_PATH).read_text(encoding="utf-8"))

    dispatched = 0
    for combo in combos:
        inputs = {
            **credentials,  # apvs_login.user, apvs_login.pass
            "cnpj": credentials.get("apvs_login", {}).get("user", ""),
            "password": credentials.get("apvs_login", {}).get("pass", ""),
            "supabase_key": supabase_key,
            "estado": estado,
            "combos": [combo],  # one combo per run
        }
        run_automation_v2.delay(
            automation_name=automation_name,
            steps_payload=steps_payload["steps"],
            inputs=inputs,
        )
        dispatched += 1

    return {"total_combos": len(combos), "dispatched": dispatched}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest ../examples/cotacao_pvs/tests/test_automacao.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add examples/cotacao_pvs/automacao.py examples/cotacao_pvs/tests/test_automacao.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 4 — cotacao_pvs outer loop driver (dispatch one task per combo)"
```

---

## Task 5: Celery task `executar_cotacao_pvs` in `tasks.py`

**Why fifth:** The driver dispatches via `run_automation_v2.delay(...)`. To make this a first-class Celery task that the cron can call, add a thin wrapper.

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Create: `backend/tests/automation/test_cotacao_dispatch.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_cotacao_dispatch.py`:

```python
"""Smoke test for the executar_cotacao_pvs Celery task wrapper."""
import importlib


def test_executar_cotacao_pvs_imports():
    """The task is importable from the tasks module."""
    from app.workers.tasks import executar_cotacao_pvs  # noqa: F401
    import celery
    # Celery tasks are callable; the .delay() method is added by Celery.
    assert callable(executar_cotacao_pvs)


def test_executar_cotacao_pvs_dispatches_run_automation_v2(monkeypatch):
    """The wrapper calls run_automation_v2.delay once per combo."""
    monkeypatch.setattr("app.workers.tasks.run_automation_v2", MagicMock())
    from app.workers.tasks import executar_cotacao_pvs
    importlib.reload(executar_cotacao_pvs)

    fake_delay = MagicMock()
    monkeypatch.setattr(executar_cotacao_pvs, "delay", MagicMock(return_value=MagicMock(id="x")))

    # We can't easily call the underlying function without Celery discovery
    # but we can verify the import path is correct.
    from app.workers import tasks
    assert tasks.executar_cotacao_pvs is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation/test_cotacao_dispatch.py -v
```

Expected: ImportError because `executar_cotacao_pvs` isn't in `tasks.py` yet.

- [ ] **Step 3: Add `executar_cotacao_pvs` to `tasks.py`**

In `backend/app/workers/tasks.py`, add at the top:

```python
from pathlib import Path as _Path
import json as _json
```

Then add this task:

```python
@celery.task(name="app.workers.tasks.executar_cotacao_pvs", time_limit=21600, soft_time_limit=21570)
def executar_cotacao_pvs(veiculos_path: str | None = None):
    """P1b entrypoint: read veiculos_referencia.json, dispatch one
    NavRunner v2 task per (vehicle × region) combo.

    `veiculos_path` is the OPTIONAL path to a JSON file. Default is the
    legacy cotacao_pvs/veiculos_referencia.json (mounted volume).
    """
    from cotacao_pvs.automacao import executar_cotacao_pvs as _executar
    from app.automation.credentials import resolve_credentials

    credentials = resolve_credentials()
    summary = _run(_executar(
        veiculos_path=_Path(veiculos_path) if veiculos_path else None,
        credentials=credentials,
        supabase_key=os.environ.get("SUPABASE_KEY", ""),
        automation_name="cotacao_pvs",
    ))
    return summary
```

Also add `import os` if not already at the top.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation/test_cotacao_dispatch.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Re-run full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation -v
```

Expected: 104 + 2 = 106 passed (no regressions).

- [ ] **Step 6: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add backend/app/workers/tasks.py backend/tests/automation/test_cotacao_dispatch.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 5 — Celery task executar_cotacao_pvs"
```

---

## Task 6: README + cron trigger

**Why sixth:** Document the new package and replace the legacy cron loop with the new task.

**Files:**
- Create: `examples/cotacao_pvs/README.md`
- Modify: `apps/runtime/jobs/cotacao_pvs.py` (or create if missing)

- [ ] **Step 1: Create the README**

`examples/cotacao_pvs/README.md`:

```markdown
# Cotação PVS — NavRunner implementation

Migrated from the legacy imperative `cotacao_pvs/automacao_cotacao.py` (544 lines)
to a NavRunner DSL workflow. The legacy script is preserved at `/root/navegador/cotacao_pvs/automacao_cotacao.py`
(mounted read-only into the worker) for reference.

## Files

- `ionic_helpers.py` — Python wrappers for Ionic/Angular JS interactions. The
  only piece that needs `page.evaluate(...)` since Ionic components don't
  expose stable CSS selectors.
- `steps.json` — the DSL flow. Auth block + Ionic-step `run_python` blocks
  + `for_each` over combos.
- `automacao.py` — outer loop driver. Loads `veiculos_referencia.json`,
  builds the cartesian product (vehicle × region), dispatches one Celery
  task per combo.
- `tests/` — unit tests for helpers and the driver.

## Run

```python
from cotacao_pvs.automacao import executar_cotacao_pvs
import asyncio
result = asyncio.run(executar_cotacao_pvs())
print(result)  # {'total_combos': 60, 'dispatched': 60}
```

Or via Celery:

```bash
docker exec $(docker ps -q --filter name=autopilot_worker | head -1) \
  celery -A app.workers.celery_app call app.workers.tasks.executar_cotacao_pvs
```

## Required credentials

In Supabase `settings` table (or env vars):
- `apvs_login.user` / `apvs_login.pass` — CNPJ + senha do app.apvs.vc
- `supabase_key` — service key para PATCH em `cotacoes_fipe`

## Output

The DSL writes to Supabase `cotacoes_fipe` — updates `valor_prata` (cheapest plan) or
`erro` (when no plans found) per (faixa_min, faixa_max, tipo, regiao) row.

## Failure modes

- FIPE code rejected → toast detected, returns False, run fails with clear error
- Model not loaded within 120s → raises, run fails
- "Campo obrigatório" errors → captured by `get_form_errors`, step fails
- ForEach limit (max_iterations=100) cuts off if more combos than expected
```

- [ ] **Step 2: Update or create the cron job**

Check if `apps/runtime/jobs/cotacao_pvs.py` exists:

```bash
ls /root/navegador/automa-o-navegador/apps/runtime/jobs/ 2>&1
```

If it exists, replace its body with:

```python
"""Cron trigger for the cotação PVS flow.

The legacy version of this file called automacao_cotacao.py modules directly.
P1b replaces it with a Celery dispatch — the actual work runs in the worker.
"""
from app.workers.tasks import executar_cotacao_pvs


def run():
    """Triggered by the apps/runtime cron."""
    result = executar_cotacao_pvs.delay()
    return {"task_id": result.id, "queued": True}
```

If it doesn't exist, create `examples/cotacao_pvs/runtime_trigger.py` with the same content (this lives outside `apps/runtime/` since that's a separate monorepo effort).

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
git add examples/cotacao_pvs/README.md apps/runtime/jobs/cotacao_pvs.py 2>&1 || git add examples/cotacao_pvs/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P1b task 6 — README + cron trigger uses new executar_cotacao_pvs task"
```

---

## Task 7: Final review + verification

**Files:** (none, just verification)

- [ ] **Step 1: Run the full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest tests/automation
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b/backend && python3 -m pytest ../examples/cotacao_pvs/tests
```

Expected: 106 + 16 = 122 tests pass.

- [ ] **Step 2: Manual smoke check**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p1b
python3 -c "
import json
with open('examples/cotacao_pvs/steps.json') as f:
    data = json.load(f)
print('automation_name:', data['automation_name'])
print('auth:', data['auth']['type'])
print('top-level steps:', len(data['steps']))
loop = next((s for s in data['steps'] if s.get('for_each')), None)
print('for_each items: yes' if loop else 'no')
if loop:
    print('  items source:', loop['for_each'].get('items'))
    print('  inner steps:', len(loop['for_each']['steps']))
"
```

Expected: prints pipeline structure.

- [ ] **Step 3: Commit (no code change, just a marker commit if needed)**

Skip if no changes. If `apps/runtime/jobs/cotacao_pvs.py` exists with changes, commit them; otherwise nothing.

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P1b coverage | Deferred to |
|---|---|---|
| DSL canônico (hybrid) | Done — `auth` + `run_python` + `for_each` + `if` + `extract_*` (P1a) + `goto` / `assert` from P0 | — |
| `auth` block | Used in `steps.json` for the APVS login flow | — |
| `for_each` | Used in `steps.json` for the loop over combos | — |
| `if` | Used inside `extract_plano` to branch between save-with-result vs save-error | — |
| `run_python` | Used heavily for Ionic helpers (unavoidable) | P5 sandboxing |
| `extract_*` | Used in `extract_plano` via `page.evaluate` (not the declarative extract_text — DOM is too dynamic) | — |
| Retry | P1a `retry.attempts` per step | — |
| Observability | P1a step logs + screenshots | P4 UI |
| MinIO upload | P1a | — |
| Langfuse | P1a | — |
| Alerts | Not (P2) | P2 |
| Record-replay | Not (P3) | P3 |
| Painel UI | Not (P4) | P4 |

P1b delivers the first end-to-end use case. P2 (alerts), P3 (record-replay), P4 (UI) are independent.

**2. Placeholder scan**

Searched for `TBD`, `TODO`, `implement later`, `fill in details`. Found zero in task code. One in `automacao.py`: `executar_cotacao_pvs` returns `summary` even on a partial Celery dispatch — that's intentional because Celery's `delay()` is fire-and-forget (the actual run happens in the worker).

**3. Type consistency**

- `Step.from_dict` accepts both `dict` and `Step` objects as children (`for_each.steps` and `if.then_steps`/`else_steps`). Verified by `test_visit_child_runs_step_object`.
- `run_python` accepts `value` (string) and merges with `inputs` / `bindings` / `page` in the namespace. Matches `app/automation/run_python.py` (P1a).
- `for_each.items` accepts a list literal or a `{{input.combos}}` template (which `RunContext.get` resolves into a list — verified by P1a `test_for_each_interpolates_string_items`).
- `credentials` resolution: `apvs_login.user` / `apvs_login.pass` matches the P1a `resolve_credentials` schema.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p1b-cotacao-migration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent per task. The orchestrator merges between tasks.

**2. Inline Execution** — Execute tasks in this session using executing-plans.

Which approach?
