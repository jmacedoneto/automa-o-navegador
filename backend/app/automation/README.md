# NavRunner

Declarative browser automation framework for the `autonavegador` stack. Replaces
the brittle Python-per-automation pattern (see `cotacao_pvs/automacao_cotacao.py`)
with a JSON DSL, per-step retry, and observability hooks (Langfuse + MinIO).

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
- Code escape hatch: `run_python` (P5 subprocess sandbox — blocks `os`, `subprocess`, `importlib`, `ctypes`, `socket`, `sys`, `builtins`, etc.; **best-effort** — see Threat Model in `app/automation/sandbox.py`)
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

## Tests

```bash
cd backend
python3 -m pytest tests/automation -v
```

101 tests, all passing.

## Quick start

The hello-world automation opens example.com, waits for `h1`, asserts the
title is "Example Domain". It's an offline e2e test (uses a fake Playwright).

```bash
cd backend
python3 -m pytest tests/automation/test_hello_world_e2e.py -v
```

To run against a real Browserless instance, set `BROWSERLESS_URL` to the
endpoint (e.g. `ws://autopilot_browser:3000`) and use `NavRunner` directly:

```python
from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.models import Step
import asyncio, json

steps_payload = json.load(open("examples/hello_world/steps.json"))["steps"]
steps = [Step.from_dict(s) for s in steps_payload]
cfg = NavRunnerConfig(
    browser_endpoint="ws://autopilot_browser:3000",
    run_id="hello-1",
    screenshot_dir="/tmp/hello-shots",
)
runner = NavRunner(cfg=cfg)
result = asyncio.run(runner.run_steps(steps=steps, inputs={}))
print(result.status, result.errors, result.screenshot_keys)
```

## Record-Replay (NavRecorder)

Install the Chrome extension from `chrome-extension/` (load unpacked in developer mode). Open the target site, click "Start Recording", perform the flow manually, click "Stop", then "Exportar Trace". Upload the trace file to the painel — the recorder heuristic generates a `steps.json` draft for review.

The recorder is conservative: it detects login blocks automatically, groups consecutive fills, and skips screenshots (the runner already captures them). The user reviews the draft, adds `credentials_ref`, `inputs`, and `outputs`, then saves.

### Backend endpoint

```bash
curl -X POST http://localhost:8000/api/automation/import-trace \
  -F "trace_file=@navrunner-trace.json"
```

Returns a JSON body shaped like `steps.json`. Errors:

- 422: missing `trace_file` field
- 400: trace is invalid JSON or has wrong shape

## Architecture

```
app/automation/
  models.py          data types — Step (action + params + retry + bind),
                                RunContext (inputs/bindings/credentials),
                                RetryPolicy
  bindings.py        {{...}} interpolation across str/dict/list/scalar
  retry.py           with_retry(coro, policy) with three backoff strategies
  interpreter.py     dispatch table (step.action → handler); wraps with_retry
  steps/             one file per category (navigation, interaction, assertion)
  storage.py         MinIO key + URL formatters (upload deferred)
  tracing.py         langfuse_span context manager (no-op until LANGFUSE_* set)
  runner.py          orchestrates Playwright + interpreter + tracing + storage;
                     captures per-step screenshots + on_fail screenshot
  __init__.py        re-exports the public types
```

Adding a new step type:

1. Add an entry to `_ACTIONS` in `models.py`
2. Create a handler in `steps/<category>.py`
3. Register it in `_HANDLERS` in `interpreter.py`

## Conventions

- DSL shape: `{"id": "...", "<action>": <payload>, "retry": {...}?}`
- Bindings: `{{input.x.y}}` for inputs, `{{cfg.x}}` for credentials, bare
  `{{name}}` for bindings (inputs checked first, then bindings).
- Handlers always re-raise exceptions; the runner catches and decides whether
  to continue or stop based on the per-step `retry.on_fail`.
- Screenshots are written to local disk in P0; P1 will add MinIO upload.
- Langfuse spans are no-ops until `LANGFUSE_*` env vars are all set.
