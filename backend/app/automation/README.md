# NavRunner

Declarative browser automation framework for the `autonavegador` stack. Replaces
the brittle Python-per-automation pattern (see `cotacao_pvs/automacao_cotacao.py`)
with a JSON DSL, per-step retry, and observability hooks (Langfuse + MinIO).

## Status: P1a (engine extensions)

### Implemented (P0 + P1a)

- DSL parser + data types (`models.py` → `Step`, `RetryPolicy`, `RunContext`)
- Bindings interpolation `{{input.x}}` / `{{binding}}` / `{{cfg.x}}` (`bindings.py`)
- Retry with fixed/linear/exponential backoff (`retry.py`)
- Navigation steps: `goto`, `wait_for` (P0)
- Interaction steps: `click`, `fill` (P0)
- Assertion step: `assert_text` (P0)
- Extraction steps: `extract_text`, `extract_table`, `screenshot` (P1a)
- Code escape hatch: `run_python` (P1a) — **NOT a sandbox in P1a**: code runs as the worker process user with full filesystem and network access via `__import__`. P5 wraps it in RestrictedPython / subprocess / seccomp.
- Control flow: `for_each`, `if` (P1a)
- Auth block: `form_login` (P1a)
- Credentials resolver: `cfg.*` settings + `NAVRUNNER_*` env vars (P1a)
- Interpreter dispatch table (`interpreter.py`)
- MinIO upload (when `MINIO_*` env set; local fallback otherwise) — P1a
- Langfuse tracing (no-op when `LANGFUSE_*` missing; real SDK when set) — P1a
- Runner orchestrator with per-step screenshots + on_fail capture + step-log emission
- Celery dispatcher `run_automation_v2` (writes audit row + step logs + credentials)
- Supabase migrations: `automation_runs`, `automation_versions`, `automation_steps_log`
- Hello-world example + offline e2e test

### Deferred to later phases

- Cotação migration (P1b)
- `run_ai` inline AI step (P2)
- WhatsApp alerts via Evolution (P2)
- Chrome extension record-replay (P3)
- Run detail UI in `painel` (P4)
- Auth strategies: `cookie_reuse`, `otp_via_telegram` (P5)
- RestrictedPython sandbox for `run_python` (P5)
- Per-run step_log_writer (instead of module global) when concurrency > 1 needed (P5)

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
