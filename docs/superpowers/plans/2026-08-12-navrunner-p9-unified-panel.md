# NavRunner P9 — Unified Authoring Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single "create automation" page that gives the user three paths side-by-side (Manual / Record / AI Planner) instead of the current scattered UX where the AI Planner is a card on the list, the ExtensionRecorder is buried in AutomationEditor, and manual editing is the only first-class flow.

**Architecture:** New `src/pages/CreateAutomation.tsx` with a 3-tab layout. Each tab embeds an existing component (`AutomationEditor` for manual, `AIPlannerCard` for AI, the recorder embed for record). Tabs share a "name" field at the top and a single "save" affordance that normalizes the output of the active tab into `steps.json` and persists via `createAutomation`. No backend changes — all tabs already produce NavRunner-shaped drafts.

**Tech Stack:** React + TypeScript + Vite + shadcn/ui + sonner (existing). Pure frontend.

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — section "P9: Single-pane authoring".

**Predecessor plans:** P0–P3 + P5 + P6 merged.

---

## File Structure

### Files created (P9)

```
src/pages/CreateAutomation.tsx              # The new 3-tab page
src/components/automation/CreateTabs.tsx   # Tab strip with shared name field
src/components/automation/RecorderTab.tsx # Embeds the existing Recorder
```

### Files modified (P9)

- `src/components/automation/AutomationList.tsx` — replace the existing "create" link with a button that navigates to `/create` (the new page). Keep `AIPlannerCard` available there.
- `src/App.tsx` (or wherever routes are declared) — register `/create` route pointing to `<CreateAutomation />`.

### Anti-pattern check

- The page is a thin shell — no business logic, just an orchestrator over existing components.
- Recorder plugin + AIPlanner card are reused as-is (no changes to their rendering).
- The "Manual" tab could embed the existing `AutomationForm` if it exists, or render a `Textarea` for raw JSON.

---

## Conventions

- TDD-style for React: render-test the orchestration logic where reasonable.
- Commit messages: `feat(navrunner): P9 task N — <title>` etc.
- No backend changes — this task is purely UI.

---

## Task 1: Survey the existing component API

**Why first:** Before we can orchestrate the tabs, we need to know what props each component accepts, what shape their outputs take, and how they're currently reached from routing.

**Files:** (no changes — read-only)

- [ ] **Step 1: Read the relevant components**

Read at least:
- `src/components/automation/AIPlannerCard.tsx` — already exists, exports `AIPlannerCard`
- `src/components/automation/ExtensionRecorder.tsx` — see how it accepts/returns the recorded `steps`
- `src/components/automation/AutomationList.tsx` — locate the "create automation" button/link
- `src/components/automation/AutomationForm.tsx` (if it exists) — manual editing form

Document:
- For each authoring component, note its props (callback for "onStepsReady" or similar)
- The shape of the final `AutomationCreate` payload

- [ ] **Step 2: Read the router**

Locate `src/App.tsx` or the equivalent router file. Identify:
- Which component renders `/automations/$id` (probably `AutomationEditor`)
- Which component renders `/` (probably `Index` or `Dashboard`)
- Whether there's already a `/create` or `/new` route

## Step 3: Commit (no code change, just docstring if relevant)**

Skip this commit — there's nothing to commit yet.

---

## Task 2: Build the unified page skeleton

**Files:**
- Create: `src/pages/CreateAutomation.tsx`
- Create: `src/components/automation/CreateTabs.tsx`

- [ ] **Step 1: Create `CreateTabs.tsx`**

`/root/navegador/automa-o-navegador/.worktrees/navrunner-p9/src/components/automation/CreateTabs.tsx`:

```tsx
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sparkles, MousePointerClick, PencilLine } from "lucide-react";
import { AIPlannerCard } from "./AIPlannerCard";
import { ExtensionRecorder } from "./ExtensionRecorder";
import { Textarea } from "@/components/ui/textarea";
import { AutomationStep } from "@/types/automation";

interface CreateTabsProps {
  automationName: string;
  onAutomationNameChange: (n: string) => void;
  steps: AutomationStep[];
  onStepsChange: (s: AutomationStep[]) => void;
  onAuth?: unknown;
  onSave: () => Promise<void>;
  saving: boolean;
}

/**
 * 3-tab authoring strip — the heart of P9. Each tab writes into the parent's
 * `steps` / `onAuth` slots, and a single Save button persists via the
 * existing createAutomation flow.
 */
export function CreateTabs({
  automationName,
  onAutomationNameChange,
  steps,
  onStepsChange,
  onSave,
  saving,
}: CreateTabsProps) {
  const [tab, setTab] = useState<"manual" | "record" | "ai">("manual");

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Nova automação</CardTitle>
          <CardDescription>Dá um nome pra ela — pode renomear depois.</CardDescription>
        </CardHeader>
        <CardContent>
          <Label htmlFor="automation-name">Nome</Label>
          <Input
            id="automation-name"
            value={automationName}
            onChange={(e) => onAutomationNameChange(e.target.value)}
            placeholder="Ex: Cotação FIPE - APVS"
          />
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(v as "manual" | "record" | "ai")}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="manual"><PencilLine className="h-4 w-4 mr-2" /> Manual</TabsTrigger>
          <TabsTrigger value="record"><MousePointerClick className="h-4 w-4 mr-2" /> Gravar</TabsTrigger>
          <TabsTrigger value="ai"><Sparkles className="h-4 w-4 mr-2" /> AI Planner</TabsTrigger>
        </TabsList>

        <TabsContent value="manual">
          <Card>
            <CardHeader>
              <CardTitle>Steps (JSON)</CardTitle>
              <CardDescription>Edite o NavRunner DSL à mão, ou cole um draft.</CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={JSON.stringify(steps, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    if (Array.isArray(parsed)) onStepsChange(parsed);
                  } catch {
                    /* invalid JSON — leave steps unchanged */
                  }
                }}
                rows={20}
                className="font-mono text-xs"
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="record">
          <Card>
            <CardHeader>
              <CardTitle>Gravar do navegador</CardTitle>
              <CardDescription>
                Usa a extensão Chrome NavRecorder (carregue como unpacked em <code>chrome://extensions</code>).
                Ela grava tua sessão real e converte pra NavRunner DSL.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ExtensionRecorder
                isOpen={true}
                onClose={() => setTab("manual")}
                onStepsReady={(s) => onStepsChange(s)}
                initialUrl={undefined}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai">
          <AIPlannerCard />
        </TabsContent>
      </Tabs>

      <div className="flex items-center gap-2">
        <Button onClick={onSave} disabled={saving || !automationName.trim() || steps.length === 0}>
          {saving ? "Salvando..." : "Salvar automação"}
        </Button>
        <span className="text-xs text-muted-foreground">
          {steps.length} step{steps.length === 1 ? "" : "s"} prontos
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `CreateAutomation.tsx`**

`/root/navegador/automa-o-navegador/.worktrees/navrunner-p9/src/pages/CreateAutomation.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CreateTabs } from "@/components/automation/CreateTabs";
import { AutomationStep } from "@/types/automation";
import { createAutomation } from "@/services/automationService";

/**
 * Single-pane authoring page (P9). Three authoring modes share a name +
 * a save action. Combines AI Planner, manual editing, and the recorder.
 */
export function CreateAutomationPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim() || steps.length === 0) {
      toast.error("Precisa de nome e pelo menos 1 step");
      return;
    }
    setSaving(true);
    try {
      const created = await createAutomation({
        name,
        description: `Created via unified authoring (P9)`,
        erp_url: "",
        instructions: "",
        steps,
        credentials: {},
        outputs: [],
        is_active: false,
      } as never);
      toast.success("Automação criada!");
      window.dispatchEvent(new CustomEvent("automation-created"));
      navigate(`/automations/${created.id}`);
    } catch (err) {
      toast.error(`Erro: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <CreateTabs
        automationName={name}
        onAutomationNameChange={setName}
        steps={steps}
        onStepsChange={setSteps}
        onSave={handleSave}
        saving={saving}
      />
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 && npm run build 2>&1 | tail -10
```

Expected: build succeeds with no TypeScript errors. If `AutomationStep` type doesn't match the JSON you want, loosen the typing (e.g., `Array<Record<string, unknown>>`).

- [ ] **Step 4: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9
git add src/pages/CreateAutomation.tsx src/components/automation/CreateTabs.tsx
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P9 task 2 — CreateTabs 3-tab strip + CreateAutomation page"
```

## Report

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- **Build output:** (paste last 10 lines of `npm run build`)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 rev-parse HEAD`
- **Concerns** if any

---

## Task 3: Wire the route + navigation

**Files:**
- Modify: `src/App.tsx` (or equivalent — find where routes live)
- Modify: `src/components/automation/AutomationList.tsx` — replace inline AI card with a link/button

- [ ] **Step 1: Find the router**

```bash
grep -rn "Routes\|Route\|BrowserRouter" /root/navegador/automa-o-navegador/.worktrees/navrunner-p9/src/*.tsx 2>&1 | head -10
```

Note the file + import style.

- [ ] **Step 2: Register the new route**

Add (next to existing `<Route path="/automations" ... />`):

```tsx
<Route path="/create" element={<CreateAutomationPage />} />
```

And import at the top:

```tsx
import { CreateAutomationPage } from "./pages/CreateAutomation";
```

- [ ] **Step 3: Update `AutomationList` — replace inline card with link**

In `src/components/automation/AutomationList.tsx`:

a) Remove the `<AIPlannerCard />` from inside the rendered list (it's now inside `/create`):
   - Find the line `<AIPlannerCard />` and delete it.

b) Add a button at the top of the list that navigates to `/create`:

```tsx
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

// Inside the component:
const navigate = useNavigate();

// Inside the JSX, at the top of the rendered tree:
<div className="flex justify-end">
  <Button onClick={() => navigate("/create")}>
    <Plus className="h-4 w-4 mr-2" /> Nova automação
  </Button>
</div>
```

- [ ] **Step 4: Verify build + manual smoke**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 && npm run build 2>&1 | tail -5
```

Manual smoke (if backend is running locally):
1. Open `https://navegador.apvsiguatemi.net`
2. Click "Nova automação" → navigates to `/create`
3. Tab "Manual" → edit JSON → Save
4. Refresh → automation in the list

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9
git add src/App.tsx src/components/automation/AutomationList.tsx
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P9 task 3 — /create route + AutomationList 'Nova automação' button"
```

## Report

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- **Build output:** (paste tail)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 rev-parse HEAD`
- **Concerns** if any

---

## Task 4: README + final verification

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, find the "Status: P6" header. Change to:

```markdown
## Status: P9 (single-pane authoring + AI Planner + auth + sandbox + concurrency)

### Implemented (P0 + ... + P9)

[copy P6 list and add:]
- **Single-pane authoring (P9)** — `/create` page with 3 tabs (Manual / Record / AI Planner). Users pick the mode that fits the task.
```

- [ ] **Step 2: Final verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9/backend && python3 -m pytest tests/automation -q 2>&1 | tail -3
```

Expected: 172 still passing (no regressions from a UI-only change).

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 && npm run build 2>&1 | tail -5
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p9
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P9 README — single-pane authoring confirmed"
```

## Report

- **Status:** DONE
- **Test results:** (paste last 3 lines)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p9 rev-parse HEAD`

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P9 coverage |
|---|---|
| Single-pane authoring for all 3 modes | Done (`/create` page) |
| Tabs: Manual / Record / AI Planner | Done (3-tab layout) |
| Shared name + save | Done (`CreateTabs` props) |

**2. Placeholder scan**

Searched for `TBD`/`TODO` in task code. Zero.

**3. Type consistency**

- `AutomationStep[]` matches `AutomationCreate.steps` (existing).
- `CreateTabs` is a controlled component — parent owns state.

**4. Concerns**

- **Recorder embed may need prop tuning** — if `ExtensionRecorder` expects a real `isOpen` toggle (e.g., a modal), embedding it as always-open may not work. If so, fall back to a "Open Recorder" button that opens it as a modal.
- **`AutomationStep` shape** — the JSON textarea parses as `Array<AutomationStep>`. If the model is strict, use `Array<Record<string, unknown>>` for the field and cast at save time.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p9-unified-panel.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent per task. Orchestrator merges.

**2. Inline Execution** — Execute tasks in this session.

Which approach?
