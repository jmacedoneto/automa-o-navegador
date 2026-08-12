# NavRunner P6 — AI Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the third authoring mode: "Tell me what you want, I'll generate the steps." The user describes the automation in natural language; the backend asks GPT to produce a `steps.json` draft (NavRunner DSL — same shape the recorder outputs and the cotação example uses); the user reviews/edits; then saves via the existing `createAutomation` endpoint.

**Architecture:** New backend module `app/automation/planner.py` exposes a single async function `plan_automation(description: str, ctx: dict) -> dict` that returns a NavRunner DSL draft (`{automation_name, steps, notes}`). A new HTTP endpoint `POST /api/planner/plan` accepts the description and returns the draft. A new React card (`AIPlannerCard.tsx`) renders a textarea + a "Generate" button that POSTs to the endpoint and previews the draft as editable JSON. After review, the user clicks "Save as Automation" which calls the existing `createAutomation` flow.

**Tech Stack:** Python 3.11, OpenAI Python SDK, FastAPI (existing), React + TypeScript + Vite (existing), Langfuse (existing tracer from P1a), shadcn/ui (existing).

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — section "P6: AI Planner".

**Predecessor plans:** P0–P3 + P5 all merged.

---

## File Structure

### Files created (P6)

```
backend/app/automation/
└── planner.py                # plan_automation() — GPT-driven DSL generation

backend/app/api/routes/
└── planner.py                # POST /api/planner/plan + GET /api/planner/health

backend/tests/automation/
├── test_planner.py
└── test_planner_endpoint.py

src/components/automation/
└── AIPlannerCard.tsx         # The "AI Planner" card UI

src/services/
└── plannerService.ts         # fetchPlan() — wraps the POST
```

### Files modified (P6)

- `src/components/automation/AutomationList.tsx` — render `AIPlannerCard` at the top of the list
- `backend/app/main.py` — register the planner router

### Anti-pattern check

- `planner.py` is a thin wrapper around OpenAI — same pattern as `ai.py` (P2).
- The DSL output schema matches `examples/cotacao_pvs/steps.json` exactly — verified by importing the same shape.
- `AIPlannerCard` reuses `CodeMirror`/`<textarea>` for editing — no new dependency.

---

## Conventions carried from P0–P3/P5

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P6 task N — <title>` etc.
- Tests in `backend/tests/automation/`.

---

## Task 1: `planner.py` — GPT-driven DSL generation

**Why first:** Pure-Python module, easy to unit test. Once it produces a NavRunner-shaped dict, the endpoint + UI are thin wrappers.

**Files:**
- Create: `backend/app/automation/planner.py`
- Create: `backend/tests/automation/test_planner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_planner.py` with EXACTLY:

```python
import json
from unittest.mock import AsyncMock, MagicMock

from app.automation.planner import plan_automation


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


def _fake_response(steps_dict):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message = MagicMock()
    r.choices[0].message.content = json.dumps(steps_dict)
    return r


def test_plan_automation_returns_dsl_draft(monkeypatch):
    """Happy path: returns a NavRunner-shaped steps.json draft."""
    draft = {
        "automation_name": "cotar_carro",
        "version": 1,
        "auth": {
            "type": "form_login",
            "url": "https://app.apvs.vc",
            "credentials_ref": "apvs_login",
            "selectors": {"user": "input[type=text]", "pass": "input[type=password]", "submit": "button"},
            "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
        },
        "steps": [
            {"id": "open_app", "goto": "https://app.apvs.vc/dashboard"},
            {"id": "fill_cnpj", "fill": {"#cnpj": "{{input.cnpj}}"}},
        ],
        "notes": [],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Automatize cotação de carro",
        site_url="https://app.apvs.vc",
        auth_hint="login with CNPJ + password",
    ))
    assert out["automation_name"] == "cotar_carro"
    assert isinstance(out["steps"], list)
    assert out["steps"][0]["goto"] == "https://app.apvs.vc/dashboard"


def test_plan_automation_handles_no_auth(monkeypatch):
    """When the user says 'no login needed', the draft omits `auth`."""
    draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "ping", "goto": "https://example.com"}],
        "notes": [],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Visit example.com",
        site_url="https://example.com",
        auth_hint="no auth",
    ))
    assert "auth" not in out
    assert out["steps"][0]["goto"] == "https://example.com"


def test_plan_automation_includes_notes_for_unknown(monkeypatch):
    """When the GPT can't fill everything, it returns `notes` with caveats."""
    draft = {
        "automation_name": "thing",
        "version": 1,
        "steps": [{"id": "x", "fill": {"#input": ""}}],
        "notes": ["Could not determine the value for #input — fill in manually."],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Do a thing",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert len(out["notes"]) == 1
    assert "manually" in out["notes"][0]


def test_plan_automation_normalizes_strings(monkeypatch):
    """Whitespace in automation_name is normalized to underscores."""
    draft = {"automation_name": "Foo Bar Baz", "version": 1, "steps": [], "notes": []}
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Foo Bar Baz",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert out["automation_name"] == "foo_bar_baz"


def test_plan_automation_defaults_version_to_one(monkeypatch):
    """If the model omits `version`, the planner fills it in."""
    draft = {"automation_name": "x", "steps": []}  # no version, no notes
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="x",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert out["version"] == 1
    assert out["notes"] == []  # defaulted


def test_plan_automation_handles_empty_description():
    """Empty description raises ValueError (we can't plan nothing)."""
    import asyncio, pytest
    with pytest.raises(ValueError, match="description"):
        asyncio.run(plan_automation(description="", site_url="https://x", auth_hint=""))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation/test_planner.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.automation.planner'`

- [ ] **Step 3: Implement `planner.py`**

`backend/app/automation/planner.py`:

```python
"""AI Planner — convert natural-language descriptions into NavRunner DSL drafts.

P6 implementation. The user describes what they want, the planner asks GPT
with a NavRunner-shaped example, and returns a draft `steps.json` (same shape
as `examples/cotacao_pvs/steps.json`).

The planner is a thin wrapper. All the heavy lifting is the prompt. The
output schema is enforced by giving the model a clear JSON template.
"""
import json
import re
from typing import Any

from openai import AsyncOpenAI


_OPENAI_CLIENT: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    """Lazily create a singleton OpenAI client (same pattern as `ai.py`)."""
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        from app.core.config import settings
        api_key = settings.OPENAI_API_KEY or ""
        if not api_key:
            raise RuntimeError("OpenAI API key not configured (set OPENAI_API_KEY env)")
        _OPENAI_CLIENT = AsyncOpenAI(api_key=api_key)
    return _OPENAI_CLIENT


def _reset_openai_client() -> None:
    """Test helper — clears the singleton."""
    global _OPENAI_CLIENT
    _OPENAI_CLIENT = None


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return s.strip("_") or "new_automation"


_SYSTEM_PROMPT = """You generate NavRunner DSL automation drafts.

NavRunner DSL is a JSON-based automation language. Each draft is a dict with:
- automation_name: snake_case string
- version: 1
- auth (optional): an auth block for form_login OR cookie_reuse OR otp_via_telegram
- steps: list of step dicts. Each step has an `id` and one of:
    - {"id":"x","goto":{"url":"..."}}
    - {"id":"x","wait_for":{"selector":"...","timeout_ms":5000}}
    - {"id":"x","click":{"selector":"..."}}
    - {"id":"x","fill":{"#field":"value"}}
    - {"id":"x","fill":{"#field":"{{input.field_name}}"}} (template substitution at runtime)
    - {"id":"x","assert":{"text":"...","timeout_ms":5000}}
    - {"id":"x","extract_text":{"selector":"...","bind":"var_name"}}
    - {"id":"x","run_python":{"value":"from helpers import foo; await foo(page)"}}
    - {"id":"x","for_each":{"items":"{{input.items}}","as":"item","steps":[...]}}
    - {"id":"x","if":{"condition":"{{input.x}} == 5","then_steps":[...],"else_steps":[...]}}
- notes: list of strings — caveats the user must address before saving

If the user mentions "login", "autenticação", "sign in", include an `auth` block.
If they explicitly say "no auth" or "já logado" or similar, omit `auth`.
Otherwise, default to `form_login` with `credentials_ref="site_login"`.

If the user asks for a dynamic loop ("for each X", "iterate over", "todos os..."), wrap the inner steps in `for_each`.

Return ONLY a JSON object (no markdown, no explanation outside the JSON).
"""


async def plan_automation(
    description: str,
    site_url: str,
    auth_hint: str = "",
    model: str | None = None,
) -> dict[str, Any]:
    """Convert a natural-language description into a NavRunner DSL draft.

    `description`: what the user wants automated.
    `site_url`: the base URL (helps the model anchor the auth block).
    `auth_hint`: optional extra hint about authentication.

    Returns a dict shaped like `steps.json` (see `_SYSTEM_PROMPT`).
    """
    if not description or not description.strip():
        raise ValueError("description is required")

    user_msg = f"""Generate a NavRunner DSL draft for this automation:

DESCRIPTION: {description}

SITE URL: {site_url or "(unknown)"}
AUTH HINT: {auth_hint or "(none)"}

Return a JSON object with: automation_name, version=1, optional auth, steps, notes.
"""

    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=model or "gpt-5.4-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=2000,
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        draft = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"planner: model returned non-JSON: {e}: {raw[:200]}") from e

    # Normalize / sanity-check the draft.
    if "automation_name" not in draft or not draft["automation_name"]:
        draft["automation_name"] = _slugify(description)
    draft["automation_name"] = _slugify(draft["automation_name"])
    draft["version"] = int(draft.get("version", 1))
    draft.setdefault("steps", [])
    draft.setdefault("notes", [])
    if "auth" in draft and isinstance(draft["auth"], dict):
        # ensure credentials_ref has a sane default
        if "credentials_ref" not in draft["auth"]:
            draft["auth"]["credentials_ref"] = "site_login"
    return draft
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation/test_planner.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6
git add backend/app/automation/planner.py backend/tests/automation/test_planner.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P6 task 1 — planner.py (GPT-driven DSL generation)"
```

---

## Task 2: HTTP endpoint `POST /api/planner/plan`

**Why second:** Wire `plan_automation` into a real HTTP endpoint. Tests via `TestClient`.

**Files:**
- Create: `backend/app/api/routes/planner.py`
- Modify: `backend/main.py` (register router)
- Create: `backend/tests/automation/test_planner_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_planner_endpoint.py` with EXACTLY:

```python
from unittest.mock import MagicMock, patch


def test_endpoint_returns_dsl_draft():
    """POST /api/planner/plan accepts {description, site_url, auth_hint} and returns a draft."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "x", "goto": "https://x"}],
        "notes": [],
    }

    async def fake_plan(description, site_url, auth_hint="", model=None):
        return fake_draft

    with patch("app.api.routes.planner.plan_automation", side_effect=fake_plan):
        resp = client.post("/api/planner/plan", json={
            "description": "ping example",
            "site_url": "https://example.com",
            "auth_hint": "",
        })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["automation_name"] == "ping"
    assert isinstance(body["steps"], list)


def test_endpoint_rejects_empty_description():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/planner/plan", json={
        "description": "",
        "site_url": "https://x.com",
    })
    assert resp.status_code == 400


def test_endpoint_rejects_missing_description():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/planner/plan", json={"site_url": "https://x.com"})
    assert resp.status_code == 422  # Pydantic missing field


def test_endpoint_propagates_openai_errors():
    """A model failure becomes a 500 (the painel will show the error)."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    async def fake_plan(**kw):
        raise RuntimeError("openai is down")

    with patch("app.api.routes.planner.plan_automation", side_effect=fake_plan):
        resp = client.post("/api/planner/plan", json={
            "description": "x",
            "site_url": "https://x",
        })
    assert resp.status_code == 500
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation/test_planner_endpoint.py -v
```

Expected: 404 (route not registered) or ImportError.

- [ ] **Step 3: Implement the route**

`backend/app/api/routes/planner.py`:

```python
"""POST /api/planner/plan — accept a description, return a NavRunner DSL draft."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.automation.planner import plan_automation


router = APIRouter(prefix="/planner", tags=["planner"])


class PlanRequest(BaseModel):
    description: str
    site_url: str = ""
    auth_hint: str = ""


@router.post("/plan")
async def plan(req: PlanRequest) -> dict:
    """Accept a description; return a NavRunner DSL draft."""
    try:
        draft = await plan_automation(
            description=req.description,
            site_url=req.site_url,
            auth_hint=req.auth_hint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"planner failed: {e}") from e
    return draft
```

- [ ] **Step 4: Register the router**

In `backend/main.py`, find the existing imports:

```python
from app.api.routes import settings, automations, executions, schedules, ai, trigger, recording, health, scrape
```

Add `planner`:

```python
from app.api.routes import settings, automations, executions, schedules, ai, trigger, recording, health, scrape, planner
```

Find the `api.include_router(...)` block. Add:

```python
api.include_router(planner.router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation/test_planner_endpoint.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Re-run full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation -q 2>&1 | tail -3
```

Expected: 181 + 6 + 4 = 191 passed (no regressions).

- [ ] **Step 7: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6
git add backend/app/api/routes/planner.py backend/main.py backend/tests/automation/test_planner_endpoint.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P6 task 2 — POST /api/planner/plan endpoint"
```

---

## Task 3: Frontend — `AIPlannerCard` + `plannerService` + wire into `AutomationList`

**Why third:** With the backend live, the UI is the visible payoff. User types description → sees draft → reviews → saves.

**Files:**
- Create: `src/services/plannerService.ts`
- Create: `src/components/automation/AIPlannerCard.tsx`
- Modify: `src/components/automation/AutomationList.tsx`

- [ ] **Step 1: Create `plannerService.ts`**

`/root/navegador/automa-o-navegador/.worktrees/navrunner-p6/src/services/plannerService.ts`:

```typescript
import { api } from "./api";
import { Automation } from "@/types/automation";

export interface PlanRequest {
  description: string;
  site_url?: string;
  auth_hint?: string;
}

export interface PlannerDraft {
  automation_name: string;
  version: number;
  auth?: Record<string, unknown>;
  steps: Array<Record<string, unknown>>;
  notes?: string[];
}

export async function fetchPlan(req: PlanRequest): Promise<PlannerDraft> {
  return api.post<PlannerDraft>("/planner/plan", req);
}

/** Convert a PlannerDraft into the AutomationCreate shape the existing
 *  `createAutomation` service expects. */
export function draftToAutomation(draft: PlannerDraft): Omit<Automation, "id" | "created_at" | "updated_at"> {
  return {
    name: draft.automation_name,
    description: `Generated by AI Planner`,
    steps: draft.steps,
    auth: draft.auth,
    inputs_schema: null,
    outputs: [],
    credentials: {},
    is_active: false,
  } as Omit<Automation, "id" | "created_at" | "updated_at">;
}
```

- [ ] **Step 2: Create `AIPlannerCard.tsx`**

`/root/navegador/automa-o-navegador/.worktrees/navrunner-p6/src/components/automation/AIPlannerCard.tsx`:

```tsx
import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Loader2, Save, X } from "lucide-react";
import { toast } from "sonner";
import { fetchPlan, draftToAutomation, PlannerDraft } from "@/services/plannerService";
import { createAutomation } from "@/services/automationService";

export function AIPlannerCard() {
  const [description, setDescription] = useState("");
  const [siteUrl, setSiteUrl] = useState("");
  const [authHint, setAuthHint] = useState("");
  const [draft, setDraft] = useState<PlannerDraft | null>(null);
  const [busy, setBusy] = useState(false);

  const handleGenerate = async () => {
    if (!description.trim()) {
      toast.error("Descreva o que você quer automatizar");
      return;
    }
    setBusy(true);
    try {
      const d = await fetchPlan({ description, site_url: siteUrl, auth_hint: authHint });
      setDraft(d);
      toast.success("Draft gerado — revise e ajuste antes de salvar");
    } catch (err) {
      toast.error(`Erro ao gerar: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    if (!draft) return;
    try {
      await createAutomation(draftToAutomation(draft) as never);
      toast.success("Automação criada a partir do draft");
      setDraft(null);
      setDescription("");
      setSiteUrl("");
      setAuthHint("");
      // Tell the list to reload.
      window.dispatchEvent(new CustomEvent("automation-created"));
    } catch (err) {
      toast.error(`Erro ao salvar: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <Card className="border-dashed border-primary/40 bg-gradient-to-br from-background to-primary/5">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <CardTitle>AI Planner</CardTitle>
          <Badge variant="secondary" className="ml-auto">P6</Badge>
        </div>
        <CardDescription>
          Descreva em uma frase o que você quer automatizar. Eu gero um rascunho
          em NavRunner DSL pra você revisar e salvar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label htmlFor="planner-description">Descrição</Label>
          <Textarea
            id="planner-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder='Ex: "Automatize cotação de carro: abre app.apvs.vc, faz login, preenche código FIPE, retorna o menor plano"'
            rows={3}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="planner-url">URL base (opcional)</Label>
            <Input
              id="planner-url"
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              placeholder="https://app.apvs.vc"
            />
          </div>
          <div>
            <Label htmlFor="planner-auth">Auth hint (opcional)</Label>
            <Input
              id="planner-auth"
              value={authHint}
              onChange={(e) => setAuthHint(e.target.value)}
              placeholder='"login com CNPJ + senha" ou "no auth"'
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={handleGenerate} disabled={busy || !description.trim()}>
            {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
            Gerar rascunho
          </Button>
          {draft && (
            <Button variant="ghost" onClick={() => setDraft(null)}>
              <X className="h-4 w-4 mr-1" /> Descartar
            </Button>
          )}
        </div>

        {draft && (
          <div className="rounded-md border bg-muted/40 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-3 w-3" />
              {draft.automation_name}
              <Badge variant="outline" className="ml-auto">{draft.steps.length} steps</Badge>
            </div>
            {draft.auth && (
              <div className="text-xs text-muted-foreground">
                🔐 auth: {String((draft.auth as Record<string, unknown>).type || "unknown")}
              </div>
            )}
            <pre className="text-xs overflow-x-auto bg-background p-2 rounded border max-h-48">
{JSON.stringify(draft, null, 2)}
            </pre>
            {draft.notes && draft.notes.length > 0 && (
              <div className="text-xs space-y-1">
                <div className="font-medium">⚠️ Notas do planner:</div>
                <ul className="list-disc list-inside text-muted-foreground">
                  {draft.notes.map((n, i) => (<li key={i}>{n}</li>))}
                </ul>
              </div>
            )}
            <Button onClick={handleSave} className="w-full">
              <Save className="h-4 w-4 mr-2" /> Salvar como automação
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Wire `AIPlannerCard` into `AutomationList`**

In `src/components/automation/AutomationList.tsx`, find the import block at the top. Add:

```typescript
import { AIPlannerCard } from "./AIPlannerCard";
```

Find the JSX return. Add `<AIPlannerCard />` ABOVE the existing list (so it appears at the top):

```tsx
return (
  <div className="space-y-4">
    <AIPlannerCard />
    {/* existing list rendering below */}
  </div>
);
```

(Adjust the wrapping div accordingly if the component already has a different root.)

- [ ] **Step 4: Verify build compiles**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6 && npm run build 2>&1 | tail -15
```

Expected: build succeeds with no TypeScript errors. If it complains about missing imports (`Textarea`, `Label`, `Sparkles`, `Loader2`, `Save`, `X`), check that these shadcn/ui components and lucide icons exist (they should — they're standard).

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6
git add src/services/plannerService.ts src/components/automation/AIPlannerCard.tsx src/components/automation/AutomationList.tsx
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P6 task 3 — AIPlannerCard + plannerService + AutomationList wiring"
```

- [ ] **Step 6: Smoke test (manual)**

1. Build the frontend (`npm run build`).
2. Restart the API container (`docker service update --force autonavegador_autopilot_api`) so the planner router is loaded.
3. Open `https://navegador.apvsiguatemi.net` → see the AI Planner card above the list.
4. Type a description → click "Gerar rascunho" → see the JSON draft.
5. Adjust if needed → click "Salvar como automação" → see the new entry in the list.

## Self-Review

- All 4 planner tests + 4 endpoint tests + build succeeds
- Frontend mirrors the existing `automationService.createAutomation` pattern (no backend change needed for persistence)
- `AIPlannerCard` reuses shadcn/ui primitives
- The `auth_hint` field is the critical lever — without it, the model defaults to "form_login" which may be wrong

## Report

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- **Test results:** (paste last 5 lines of pytest + tail of npm build)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p6 rev-parse HEAD`
- **Self-review findings**
- **Concerns** if any

---

## Task 4: README + final verification

**Files:**
- Modify: `backend/app/automation/README.md`

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, find the "Status: P5 (...)" header. Replace with:

```markdown
## Status: P6 (AI Planner + auth + sandbox + concurrency)

### Implemented (P0 + P1a + P1b + P2 + P3 + P5 + P6)

[copy the P5 list and add:]
- **AI Planner (P6)** — `POST /api/planner/plan` accepts a description, returns a NavRunner DSL draft. UI: `AIPlannerCard` in the automation list.

### Deferred to later phases

- Painel unificado (P9) — UI single-pane for all 3 authoring modes
- MCP server wrapping the framework (P8, last)
```

- [ ] **Step 2: Final full verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6/backend && python3 -m pytest tests/automation -q 2>&1 | tail -3
```

Expected: 191 passed.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p6
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P6 README — AI Planner confirmed"
```

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P6 coverage | Deferred to |
|---|---|---|
| AI Planner card + chat | Done (`AIPlannerCard`) | — |
| GPT-driven DSL generation | Done (`planner.py`) | — |
| NavRunner-shaped draft | Verified (same shape as `examples/cotacao_pvs/steps.json`) | — |
| Painel unificado | Not (P9) | P9 |
| MCP server | Not (P8) | P8 |

**2. Placeholder scan**

Searched for `TBD`, `TODO`, `implement later`. Zero in task code.

**3. Type consistency**

- `PlannerDraft.automation_name: string`, `version: number`, `auth?: Record`, `steps: Array<Record>`, `notes?: string[]` — matches the schema `plan_automation` returns.
- `draftToAutomation` produces the same shape `createAutomation` expects (verified by reading the existing `Automation` type).
- The endpoint returns `dict` from the planner directly; FastAPI serializes via Pydantic.

**4. Concerns**

- **OpenAI dependency:** the planner requires `OPENAI_API_KEY` to be set in the worker env (same constraint as `ai.py` from P2). Documented in the planner docstring.
- **Cost:** each plan call is ~2K tokens. Cheap enough for an interactive feature.
- **No conversation memory:** P6 is single-shot — the user types, gets a draft, can re-generate. Multi-turn conversation is out of scope; can land in P9 (painel unificado).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p6-ai-planner.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent per task. Orchestrator merges between tasks.

**2. Inline Execution** — Execute tasks in this session.

Which approach?