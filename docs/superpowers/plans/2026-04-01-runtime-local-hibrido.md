# Runtime Local Hibrido Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reestruturar o produto para usar painel web + API de orquestracao + runtime local com Chrome real, entregando gravacao funcional e execucao hibrida com webhook, agenda e outputs.

**Architecture:** O repositório passa a ser um workspace com `apps/web`, `apps/api`, `apps/runtime` e `packages/shared`. A API deixa de controlar browser via screenshot e passa a publicar jobs/runs, enquanto o runtime local abre o Chrome real, grava passos, executa Playwright e aplica fallback de IA com limite. A migracao acontece por fatias, preservando o codigo legado enquanto os novos fluxos entram em operacao.

**Tech Stack:** React + Vite + TypeScript, FastAPI + Pydantic, Playwright, OpenAI, Supabase, npm workspaces, Vitest, Pytest

---

## File Structure

**Workspace root**

- Modify: `package.json`
- Create: `apps/web/package.json`
- Create: `apps/api/requirements.txt`
- Create: `apps/runtime/requirements.txt`
- Create: `packages/shared/package.json`
- Create: `packages/shared/src/contracts.ts`
- Create: `packages/shared/src/index.ts`
- Create: `vitest.config.ts`

**Web app**

- Create: `apps/web/src/app/router.tsx`
- Create: `apps/web/src/domains/automations/api.ts`
- Create: `apps/web/src/domains/recordings/api.ts`
- Create: `apps/web/src/domains/executions/api.ts`
- Create: `apps/web/src/pages/AutomationEditorPage.tsx`
- Create: `apps/web/src/pages/ExecutionRunsPage.tsx`
- Create: `apps/web/src/pages/RecordingSessionPage.tsx`
- Modify: `src/pages/AutomationEditor.tsx`
- Modify: `src/services/automationService.ts`
- Modify: `src/types/automation.ts`

**API app**

- Create: `apps/api/main.py`
- Create: `apps/api/app/models/contracts.py`
- Create: `apps/api/app/models/execution.py`
- Create: `apps/api/app/services/job_service.py`
- Create: `apps/api/app/services/recording_service.py`
- Create: `apps/api/app/api/routes/recordings.py`
- Create: `apps/api/app/api/routes/jobs.py`
- Create: `apps/api/app/api/routes/runs.py`
- Modify: `backend/main.py`
- Modify: `backend/app/api/routes/recording.py`
- Modify: `backend/app/api/routes/executions.py`

**Runtime app**

- Create: `apps/runtime/main.py`
- Create: `apps/runtime/runtime/config.py`
- Create: `apps/runtime/runtime/chrome_manager.py`
- Create: `apps/runtime/runtime/recorder.py`
- Create: `apps/runtime/runtime/player.py`
- Create: `apps/runtime/runtime/fallback.py`
- Create: `apps/runtime/runtime/client.py`
- Create: `apps/runtime/tests/test_step_normalizer.py`
- Create: `apps/runtime/tests/test_fallback_policy.py`

**Database / migrations**

- Create: `supabase/migrations/202604010001_runtime_sessions_and_jobs.sql`
- Create: `supabase/migrations/202604010002_runtime_runs_and_outputs.sql`

**Tests**

- Create: `apps/web/src/domains/recordings/api.test.ts`
- Create: `apps/api/tests/test_jobs_api.py`
- Create: `apps/api/tests/test_recordings_api.py`
- Create: `apps/runtime/tests/test_player_contract.py`

## Task 1: Create The New Workspace Skeleton

**Files:**
- Modify: `package.json`
- Create: `apps/web/package.json`
- Create: `apps/api/requirements.txt`
- Create: `apps/runtime/requirements.txt`
- Create: `packages/shared/package.json`
- Test: `package.json`

- [ ] **Step 1: Write the failing workspace validation check**

Create a root validation command entry that will fail until the workspace folders exist:

```json
{
  "name": "autopilot-platform",
  "private": true,
  "workspaces": [
    "apps/web",
    "packages/shared"
  ],
  "scripts": {
    "lint:web": "npm --workspace apps/web run lint",
    "test:web": "npm --workspace apps/web run test",
    "test:api": "cd apps/api && pytest",
    "test:runtime": "cd apps/runtime && pytest",
    "check:workspace": "test -f apps/web/package.json && test -f packages/shared/package.json"
  }
}
```

- [ ] **Step 2: Run validation to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && npm run check:workspace`
Expected: FAIL with `apps/web/package.json: No such file or directory`

- [ ] **Step 3: Create the minimal workspace manifests**

Create `apps/web/package.json`:

```json
{
  "name": "@autopilot/web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint src --ext .ts,.tsx",
    "test": "vitest run"
  }
}
```

Create `packages/shared/package.json`:

```json
{
  "name": "@autopilot/shared",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "main": "./src/index.ts"
}
```

Create `apps/api/requirements.txt`:

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
supabase==2.7.4
httpx==0.27.2
pydantic==2.9.2
pydantic-settings==2.5.2
pytest==8.3.3
```

Create `apps/runtime/requirements.txt`:

```txt
playwright==1.47.0
openai==1.51.0
httpx==0.27.2
pydantic==2.9.2
pydantic-settings==2.5.2
pytest==8.3.3
```

- [ ] **Step 4: Run validation to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && npm run check:workspace`
Expected: PASS with no output

- [ ] **Step 5: Commit**

```bash
git add package.json apps/web/package.json apps/api/requirements.txt apps/runtime/requirements.txt packages/shared/package.json
git commit -m "chore: scaffold runtime workspace layout"
```

## Task 2: Define Shared Contracts Before Moving Code

**Files:**
- Create: `packages/shared/src/contracts.ts`
- Create: `packages/shared/src/index.ts`
- Create: `apps/web/src/domains/recordings/api.test.ts`
- Modify: `src/types/automation.ts`
- Test: `apps/web/src/domains/recordings/api.test.ts`

- [ ] **Step 1: Write the failing contract test**

Create `apps/web/src/domains/recordings/api.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AutomationMode, FallbackPolicy } from "@autopilot/shared";

describe("shared contracts", () => {
  it("exposes the automation modes used by the web app", () => {
    const modes: AutomationMode[] = ["gravado", "hibrido", "livre_ai"];
    expect(modes).toHaveLength(3);
  });

  it("requires bounded fallback policy values", () => {
    const policy: FallbackPolicy = {
      maxTentativasIa: 2,
      timeoutTotalSegundos: 20,
      pausaQuandoFalhar: true,
    };

    expect(policy.maxTentativasIa).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && npm run test:web`
Expected: FAIL with `Cannot find module '@autopilot/shared'`

- [ ] **Step 3: Create the shared contract package**

Create `packages/shared/src/contracts.ts`:

```ts
export type AutomationMode = "gravado" | "hibrido" | "livre_ai";

export interface FallbackPolicy {
  maxTentativasIa: number;
  timeoutTotalSegundos: number;
  pausaQuandoFalhar: boolean;
}

export interface RecordingSession {
  id: string;
  automationId?: string;
  status: "pending" | "running" | "completed" | "failed";
  runtimeId?: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface ExecutionJob {
  id: string;
  automationId: string;
  triggerType: "manual" | "webhook" | "schedule";
  mode: AutomationMode;
  payload: Record<string, unknown>;
}

export interface ExecutionRun {
  id: string;
  jobId: string;
  status: "queued" | "running" | "paused" | "success" | "failed";
  stepsCompleted: number;
  totalSteps: number;
}
```

Create `packages/shared/src/index.ts`:

```ts
export * from "./contracts";
```

Update `src/types/automation.ts` to consume the new contracts:

```ts
import type { AutomationMode, FallbackPolicy } from "@autopilot/shared";

export interface Automation {
  id: string;
  name: string;
  description: string;
  erp_url: string;
  instructions: string;
  mode: AutomationMode;
  fallback_policy: FallbackPolicy;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && npm run test:web`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/shared/src/contracts.ts packages/shared/src/index.ts src/types/automation.ts apps/web/src/domains/recordings/api.test.ts
git commit -m "feat: add shared runtime contracts"
```

## Task 3: Introduce API Jobs, Runs, And Recording Sessions

**Files:**
- Create: `apps/api/app/models/contracts.py`
- Create: `apps/api/app/models/execution.py`
- Create: `apps/api/app/services/job_service.py`
- Create: `apps/api/app/services/recording_service.py`
- Create: `apps/api/app/api/routes/recordings.py`
- Create: `apps/api/app/api/routes/jobs.py`
- Create: `apps/api/app/api/routes/runs.py`
- Create: `apps/api/tests/test_jobs_api.py`
- Create: `apps/api/tests/test_recordings_api.py`
- Create: `supabase/migrations/202604010001_runtime_sessions_and_jobs.sql`
- Create: `supabase/migrations/202604010002_runtime_runs_and_outputs.sql`
- Test: `apps/api/tests/test_jobs_api.py`
- Test: `apps/api/tests/test_recordings_api.py`

- [ ] **Step 1: Write the failing API tests**

Create `apps/api/tests/test_jobs_api.py`:

```python
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_create_execution_job_returns_202():
    response = client.post(
        "/api/jobs",
        json={
            "automation_id": "auto-1",
            "trigger_type": "manual",
            "mode": "hibrido",
            "payload": {"lead_id": "123"},
        },
    )
    assert response.status_code == 202
```

Create `apps/api/tests/test_recordings_api.py`:

```python
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_create_recording_session_returns_201():
    response = client.post("/api/recordings", json={"automation_id": "auto-1"})
    assert response.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /root/navegador/automa-o-navegador/apps/api && pytest`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.api.main'`

- [ ] **Step 3: Create the minimal API app and contracts**

Create `apps/api/app/models/contracts.py`:

```python
from pydantic import BaseModel


class FallbackPolicy(BaseModel):
    max_tentativas_ia: int = 2
    timeout_total_segundos: int = 20
    pausa_quando_falhar: bool = True
```

Create `apps/api/app/models/execution.py`:

```python
from pydantic import BaseModel


class CreateExecutionJob(BaseModel):
    automation_id: str
    trigger_type: str
    mode: str
    payload: dict


class CreateRecordingSession(BaseModel):
    automation_id: str | None = None
```

Create `apps/api/main.py`:

```python
from fastapi import FastAPI
from apps.api.app.api.routes.jobs import router as jobs_router
from apps.api.app.api.routes.recordings import router as recordings_router
from apps.api.app.api.routes.runs import router as runs_router

app = FastAPI(title="AutoPilot Orchestrator")
app.include_router(jobs_router, prefix="/api")
app.include_router(recordings_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
```

- [ ] **Step 4: Implement minimal route handlers and migrations**

Create `apps/api/app/api/routes/jobs.py`:

```python
from fastapi import APIRouter, status
from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": "job-local-1",
        "automation_id": payload.automation_id,
        "status": "queued",
    }
```

Create `apps/api/app/api/routes/recordings.py`:

```python
from fastapi import APIRouter, status
from apps.api.app.models.execution import CreateRecordingSession

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recording_session(payload: CreateRecordingSession):
    return {
        "id": "rec-local-1",
        "automation_id": payload.automation_id,
        "status": "pending",
    }
```

Create `apps/api/app/api/routes/runs.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: str):
    return {"id": run_id, "status": "queued"}
```

Create `supabase/migrations/202604010001_runtime_sessions_and_jobs.sql`:

```sql
create table if not exists recording_sessions (
  id uuid primary key default gen_random_uuid(),
  automation_id uuid null references automations(id) on delete set null,
  status text not null default 'pending',
  runtime_id text null,
  started_at timestamptz null,
  finished_at timestamptz null,
  created_at timestamptz not null default now()
);

create table if not exists execution_jobs (
  id uuid primary key default gen_random_uuid(),
  automation_id uuid not null references automations(id) on delete cascade,
  trigger_type text not null,
  mode text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  created_at timestamptz not null default now()
);
```

Create `supabase/migrations/202604010002_runtime_runs_and_outputs.sql`:

```sql
create table if not exists execution_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references execution_jobs(id) on delete cascade,
  status text not null default 'queued',
  steps_completed integer not null default 0,
  total_steps integer not null default 0,
  fallback_attempts integer not null default 0,
  screenshots jsonb not null default '[]'::jsonb,
  extracted_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists output_deliveries (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references execution_runs(id) on delete cascade,
  destination text not null,
  status text not null default 'pending',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /root/navegador/automa-o-navegador/apps/api && pytest`
Expected: PASS with `2 passed`

- [ ] **Step 6: Commit**

```bash
git add apps/api/main.py apps/api/app/models/contracts.py apps/api/app/models/execution.py apps/api/app/api/routes/jobs.py apps/api/app/api/routes/recordings.py apps/api/app/api/routes/runs.py apps/api/tests/test_jobs_api.py apps/api/tests/test_recordings_api.py supabase/migrations/202604010001_runtime_sessions_and_jobs.sql supabase/migrations/202604010002_runtime_runs_and_outputs.sql
git commit -m "feat: add orchestration jobs and recording sessions"
```

## Task 4: Build The Runtime Local Recorder And Fallback Shell

**Files:**
- Create: `apps/runtime/runtime/config.py`
- Create: `apps/runtime/runtime/chrome_manager.py`
- Create: `apps/runtime/runtime/recorder.py`
- Create: `apps/runtime/runtime/player.py`
- Create: `apps/runtime/runtime/fallback.py`
- Create: `apps/runtime/runtime/client.py`
- Create: `apps/runtime/main.py`
- Create: `apps/runtime/tests/test_step_normalizer.py`
- Create: `apps/runtime/tests/test_fallback_policy.py`
- Create: `apps/runtime/tests/test_player_contract.py`
- Test: `apps/runtime/tests/test_step_normalizer.py`
- Test: `apps/runtime/tests/test_fallback_policy.py`
- Test: `apps/runtime/tests/test_player_contract.py`

- [ ] **Step 1: Write the failing runtime tests**

Create `apps/runtime/tests/test_step_normalizer.py`:

```python
from apps.runtime.runtime.recorder import normalize_event


def test_normalize_click_event():
    step = normalize_event({"type": "click", "selector": "#submit"})
    assert step["action"] == "click"
    assert step["selector"] == "#submit"
```

Create `apps/runtime/tests/test_fallback_policy.py`:

```python
from apps.runtime.runtime.fallback import should_pause_after_failure


def test_should_pause_after_limit():
    assert should_pause_after_failure(attempts=2, max_attempts=2) is True
```

Create `apps/runtime/tests/test_player_contract.py`:

```python
from apps.runtime.runtime.player import build_run_summary


def test_build_run_summary():
    summary = build_run_summary(steps_completed=3, total_steps=4, status="running")
    assert summary["steps_completed"] == 3
    assert summary["status"] == "running"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /root/navegador/automa-o-navegador/apps/runtime && pytest`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.runtime.runtime'`

- [ ] **Step 3: Create the runtime core modules**

Create `apps/runtime/runtime/recorder.py`:

```python
def normalize_event(event: dict) -> dict:
    return {
        "action": event["type"],
        "selector": event.get("selector", ""),
        "value": event.get("value", ""),
        "waitTime": event.get("waitTime", 500),
    }
```

Create `apps/runtime/runtime/fallback.py`:

```python
def should_pause_after_failure(attempts: int, max_attempts: int) -> bool:
    return attempts >= max_attempts
```

Create `apps/runtime/runtime/player.py`:

```python
def build_run_summary(steps_completed: int, total_steps: int, status: str) -> dict:
    return {
      "steps_completed": steps_completed,
      "total_steps": total_steps,
      "status": status,
    }
```

Create `apps/runtime/runtime/chrome_manager.py`:

```python
from pathlib import Path


def chrome_user_data_dir(base_dir: str = ".runtime-profile") -> str:
    return str(Path(base_dir).resolve())
```

Create `apps/runtime/runtime/client.py`:

```python
class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
```

Create `apps/runtime/runtime/config.py`:

```python
from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    api_base_url: str = "http://localhost:8000"
    max_fallback_attempts: int = 2
```

Create `apps/runtime/main.py`:

```python
from apps.runtime.runtime.config import RuntimeSettings


def main() -> RuntimeSettings:
    return RuntimeSettings()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /root/navegador/automa-o-navegador/apps/runtime && pytest`
Expected: PASS with `3 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/runtime/main.py apps/runtime/runtime/config.py apps/runtime/runtime/chrome_manager.py apps/runtime/runtime/recorder.py apps/runtime/runtime/player.py apps/runtime/runtime/fallback.py apps/runtime/runtime/client.py apps/runtime/tests/test_step_normalizer.py apps/runtime/tests/test_fallback_policy.py apps/runtime/tests/test_player_contract.py
git commit -m "feat: scaffold runtime recorder and fallback shell"
```

## Task 5: Connect The Web App To Recording Sessions And Runs

**Files:**
- Create: `apps/web/src/domains/automations/api.ts`
- Create: `apps/web/src/domains/recordings/api.ts`
- Create: `apps/web/src/domains/executions/api.ts`
- Create: `apps/web/src/app/router.tsx`
- Create: `apps/web/src/pages/AutomationEditorPage.tsx`
- Create: `apps/web/src/pages/RecordingSessionPage.tsx`
- Create: `apps/web/src/pages/ExecutionRunsPage.tsx`
- Modify: `src/services/automationService.ts`
- Modify: `src/pages/AutomationEditor.tsx`
- Test: `apps/web/src/domains/recordings/api.test.ts`

- [ ] **Step 1: Write the failing recording API test**

Replace `apps/web/src/domains/recordings/api.test.ts` with:

```ts
import { describe, expect, it } from "vitest";
import { buildRecordingSessionRequest } from "./api";

describe("recording api", () => {
  it("creates the payload expected by the orchestration api", () => {
    expect(buildRecordingSessionRequest("auto-1")).toEqual({
      automation_id: "auto-1",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /root/navegador/automa-o-navegador && npm run test:web`
Expected: FAIL with `Cannot find module './api'`

- [ ] **Step 3: Create the new domain APIs**

Create `apps/web/src/domains/recordings/api.ts`:

```ts
export function buildRecordingSessionRequest(automationId: string) {
  return { automation_id: automationId };
}
```

Create `apps/web/src/domains/executions/api.ts`:

```ts
export function buildExecutionJobRequest(automationId: string) {
  return {
    automation_id: automationId,
    trigger_type: "manual",
    mode: "hibrido",
    payload: {},
  };
}
```

Create `apps/web/src/domains/automations/api.ts`:

```ts
export function automationRoute(id: string) {
  return `/automations/${id}`;
}
```

- [ ] **Step 4: Add the new page wrappers and router**

Create `apps/web/src/pages/AutomationEditorPage.tsx`:

```tsx
import AutomationEditor from "../../../../src/pages/AutomationEditor";

export default function AutomationEditorPage() {
  return <AutomationEditor />;
}
```

Create `apps/web/src/pages/RecordingSessionPage.tsx`:

```tsx
export default function RecordingSessionPage() {
  return <div>Recording session in progress</div>;
}
```

Create `apps/web/src/pages/ExecutionRunsPage.tsx`:

```tsx
export default function ExecutionRunsPage() {
  return <div>Execution runs</div>;
}
```

Create `apps/web/src/app/router.tsx`:

```tsx
import { createBrowserRouter } from "react-router-dom";
import AutomationEditorPage from "../pages/AutomationEditorPage";
import RecordingSessionPage from "../pages/RecordingSessionPage";
import ExecutionRunsPage from "../pages/ExecutionRunsPage";

export const router = createBrowserRouter([
  { path: "/automations/:id", element: <AutomationEditorPage /> },
  { path: "/recordings/:id", element: <RecordingSessionPage /> },
  { path: "/runs", element: <ExecutionRunsPage /> },
]);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /root/navegador/automa-o-navegador && npm run test:web`
Expected: PASS with `1 passed`

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/domains/automations/api.ts apps/web/src/domains/recordings/api.ts apps/web/src/domains/executions/api.ts apps/web/src/app/router.tsx apps/web/src/pages/AutomationEditorPage.tsx apps/web/src/pages/RecordingSessionPage.tsx apps/web/src/pages/ExecutionRunsPage.tsx apps/web/src/domains/recordings/api.test.ts
git commit -m "feat: wire web app to recording sessions and runs"
```

## Task 6: Move Existing Backend And UI Flows Onto The New Contracts

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/app/api/routes/recording.py`
- Modify: `backend/app/api/routes/executions.py`
- Modify: `src/services/automationService.ts`
- Modify: `src/pages/AutomationEditor.tsx`
- Modify: `src/services/executionService.ts`
- Create: `apps/api/app/services/job_service.py`
- Create: `apps/api/app/services/recording_service.py`
- Test: `apps/api/tests/test_jobs_api.py`
- Test: `apps/web/src/domains/recordings/api.test.ts`

- [ ] **Step 1: Write the failing service-level API test**

Extend `apps/api/tests/test_jobs_api.py` with:

```python
def test_job_service_returns_runtime_queue_shape():
    from apps.api.app.services.job_service import create_job_payload

    payload = create_job_payload(
        automation_id="auto-1",
        trigger_type="manual",
        mode="hibrido",
        incoming_payload={"lead_id": "1"},
    )

    assert payload["mode"] == "hibrido"
    assert payload["payload"]["lead_id"] == "1"
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `cd /root/navegador/automa-o-navegador/apps/api && pytest tests/test_jobs_api.py -v`
Expected: FAIL with `ModuleNotFoundError` for `job_service`

- [ ] **Step 3: Add the orchestration service layer**

Create `apps/api/app/services/job_service.py`:

```python
def create_job_payload(automation_id: str, trigger_type: str, mode: str, incoming_payload: dict) -> dict:
    return {
        "automation_id": automation_id,
        "trigger_type": trigger_type,
        "mode": mode,
        "payload": incoming_payload,
        "status": "queued",
    }
```

Create `apps/api/app/services/recording_service.py`:

```python
def create_recording_payload(automation_id: str | None) -> dict:
    return {
        "automation_id": automation_id,
        "status": "pending",
    }
```

- [ ] **Step 4: Repoint the legacy routes to the new services**

Update `backend/app/api/routes/executions.py`:

```python
from apps.api.app.services.job_service import create_job_payload

payload = create_job_payload(
    automation_id=automation_id,
    trigger_type="manual",
    mode="hibrido",
    incoming_payload=payload.variables,
)
```

Update `backend/app/api/routes/recording.py`:

```python
from apps.api.app.services.recording_service import create_recording_payload

session_payload = create_recording_payload(msg.get("automation_id"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /root/navegador/automa-o-navegador/apps/api && pytest tests/test_jobs_api.py -v`
Expected: PASS with `2 passed`

Run: `cd /root/navegador/automa-o-navegador && npm run test:web`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/job_service.py apps/api/app/services/recording_service.py backend/app/api/routes/executions.py backend/app/api/routes/recording.py
git commit -m "refactor: route legacy flows through orchestration services"
```

## Task 7: Finish The Vertical Slice With Outputs, Runtime Polling, And Verification

**Files:**
- Modify: `apps/runtime/runtime/client.py`
- Modify: `apps/runtime/runtime/player.py`
- Modify: `apps/api/app/api/routes/runs.py`
- Modify: `apps/web/src/pages/ExecutionRunsPage.tsx`
- Create: `apps/runtime/tests/test_output_delivery.py`
- Create: `apps/api/tests/test_runs_api.py`
- Test: `apps/runtime/tests/test_output_delivery.py`
- Test: `apps/api/tests/test_runs_api.py`

- [ ] **Step 1: Write the failing output and run tests**

Create `apps/runtime/tests/test_output_delivery.py`:

```python
from apps.runtime.runtime.player import build_delivery_payload


def test_build_delivery_payload():
    payload = build_delivery_payload(run_id="run-1", destination="webhook", extracted_data={"rows": 2})
    assert payload["destination"] == "webhook"
    assert payload["run_id"] == "run-1"
```

Create `apps/api/tests/test_runs_api.py`:

```python
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_get_run_returns_status_payload():
    response = client.get("/api/runs/run-1")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /root/navegador/automa-o-navegador/apps/runtime && pytest tests/test_output_delivery.py -v`
Expected: FAIL with `cannot import name 'build_delivery_payload'`

- [ ] **Step 3: Add the final vertical slice helpers**

Update `apps/runtime/runtime/player.py`:

```python
def build_delivery_payload(run_id: str, destination: str, extracted_data: dict) -> dict:
    return {
        "run_id": run_id,
        "destination": destination,
        "payload": extracted_data,
    }
```

Update `apps/runtime/runtime/client.py`:

```python
class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def runs_url(self, run_id: str) -> str:
        return f"{self.base_url}/api/runs/{run_id}"
```

Update `apps/api/app/api/routes/runs.py`:

```python
@router.get("/{run_id}")
def get_run(run_id: str):
    return {
        "id": run_id,
        "status": "queued",
        "outputs": [],
    }
```

Update `apps/web/src/pages/ExecutionRunsPage.tsx`:

```tsx
export default function ExecutionRunsPage() {
  return (
    <section>
      <h1>Execution runs</h1>
      <p>Statuses, outputs and intervention points appear here.</p>
    </section>
  );
}
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `cd /root/navegador/automa-o-navegador/apps/runtime && pytest tests/test_output_delivery.py -v`
Expected: PASS with `1 passed`

Run: `cd /root/navegador/automa-o-navegador/apps/api && pytest tests/test_runs_api.py -v`
Expected: PASS with `1 passed`

- [ ] **Step 5: Run the full verification suite**

Run: `cd /root/navegador/automa-o-navegador && npm run test:web && cd apps/api && pytest && cd ../runtime && pytest`
Expected: PASS with web, api and runtime suites green

- [ ] **Step 6: Commit**

```bash
git add apps/runtime/runtime/client.py apps/runtime/runtime/player.py apps/runtime/tests/test_output_delivery.py apps/api/app/api/routes/runs.py apps/api/tests/test_runs_api.py apps/web/src/pages/ExecutionRunsPage.tsx
git commit -m "feat: complete runtime vertical slice verification"
```

## Notes For Execution

- Execute this plan incrementally. Do not delete the legacy `backend/` and `src/` trees until the new `apps/` flows are proven end-to-end.
- Keep the current recorder path available only as fallback during migration; the target is to remove it after the runtime local path is stable.
- Prefer adapting existing files into thin compatibility layers instead of duplicating business rules.
- After Task 7, the next spec/plan cycle should cover real Chrome process control, authenticated profile handling, and the first end-to-end scenario fixtures.
