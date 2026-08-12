# NavRunner

Declarative browser automation framework for the `autonavegador` stack. Replaces
the brittle Python-per-automation pattern (see `cotacao_pvs/automacao_cotacao.py`)
with a JSON DSL, per-step retry, and observability hooks (Langfuse + MinIO).

## Status: P0 (skeleton)

### Implemented

- DSL parser + data types (`models.py` → `Step`, `RetryPolicy`, `RunContext`)
- Bindings interpolation `{{input.x}}` / `{{binding}}` / `{{cfg.x}}` (`bindings.py`)
- Retry with fixed/linear/exponential backoff (`retry.py`)
- Step handlers: `goto`, `wait_for`, `click`, `fill`, `assert_text`
  (`app/automation/steps/*`)
- Interpreter dispatch table (`interpreter.py`) — adding a new step type is one line
- MinIO key builder + URL formatter (`storage.py`) — actual upload deferred to P1
- Langfuse noop span (`tracing.py`) — real SDK integration deferred to P1
- Runner orchestrator (`runner.py`) with per-step screenshots + on_fail capture
- Celery dispatcher `run_automation_v2` (writes audit row to `automation_runs`)
- Supabase migration `automation_runs` (in `supabase/migrations/`)
- Hello world example (`examples/hello_world/steps.json`) + offline e2e test

### Deferred to later phases

- `automation_versions`, `automation_steps_log` tables (P1)
- `for_each`, `if`, `run_python`, `run_ai`, `extract_*` (P1/P2)
- MinIO upload + screenshots in UI (P1)
- Real Langfuse SDK + alert WhatsApp via Evolution (P2)
- Chrome extension record-replay (P3)
- Run detail UI in `painel` (P4)

## Tests

```bash
cd backend
python3 -m pytest tests/automation -v
```

40 tests, all passing.

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
