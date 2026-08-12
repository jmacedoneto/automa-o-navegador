import csv
import re
import uuid
from io import StringIO
from fastapi import APIRouter, HTTPException
from app.models.schemas import AutomationCreate, AutomationUpdate, AutomationResponse
from app.core.database import get_db

router = APIRouter(prefix="/automations", tags=["automations"])

# ── In-memory recording sessions (extensão Chrome) ──────────────────────────
_ext_sessions: dict[str, list[dict]] = {}


@router.post("/ext-session/create")
async def create_ext_session():
    """Cria sessão temporária para a extensão Chrome enviar passos."""
    session_id = str(uuid.uuid4())
    _ext_sessions[session_id] = []
    return {"session_id": session_id}


@router.post("/ext-session/{session_id}/step")
async def push_ext_step(session_id: str, step: dict):
    """Extensão Chrome envia um passo em tempo real."""
    if session_id not in _ext_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    _ext_sessions[session_id].append(step)
    return {"count": len(_ext_sessions[session_id])}


@router.get("/ext-session/{session_id}/steps")
async def get_ext_steps(session_id: str):
    """Frontend faz polling para ver os passos gravados."""
    if session_id not in _ext_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"steps": _ext_sessions[session_id]}


@router.put("/ext-session/{session_id}/steps")
async def update_ext_steps(session_id: str, steps: list[dict]):
    if session_id not in _ext_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    _ext_sessions[session_id] = steps
    return {"count": len(steps)}


@router.delete("/ext-session/{session_id}")
async def delete_ext_session(session_id: str):
    _ext_sessions.pop(session_id, None)
    return {"ok": True}


@router.get("", response_model=list[AutomationResponse])
async def list_automations():
    db = get_db()
    res = db.table("automations").select("*").order("created_at", desc=True).execute()
    return res.data or []


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(automation_id: str):
    db = get_db()
    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")
    return res.data[0]


@router.post("", response_model=AutomationResponse, status_code=201)
async def create_automation(payload: AutomationCreate):
    db = get_db()
    data = payload.model_dump()
    res = db.table("automations").insert(data).execute()
    return res.data[0]


@router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation(automation_id: str, payload: AutomationUpdate):
    db = get_db()
    data = payload.model_dump()
    res = db.table("automations").update(data).eq("id", automation_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")
    return res.data[0]


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(automation_id: str):
    db = get_db()
    db.table("automations").delete().eq("id", automation_id).execute()


@router.post("/{automation_id}/import-steps")
async def import_steps(automation_id: str, steps: list[dict]):
    """Receive steps recorded by the Chrome extension."""
    db = get_db()
    res = db.table("automations").update({"steps": steps}).eq("id", automation_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")
    return {"imported": len(steps)}


@router.post("/{automation_id}/clone", response_model=AutomationResponse, status_code=201)
async def clone_automation(automation_id: str):
    """Duplicate an automation with '(Cópia)' appended to the name."""
    db = get_db()
    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    src = res.data[0]
    clone = {
        "name": f"{src['name']} (Cópia)",
        "description": src.get("description", ""),
        "erp_url": src.get("erp_url", ""),
        "instructions": src.get("instructions", ""),
        "steps": src.get("steps", []),
        "credentials": src.get("credentials", {}),
        "outputs": src.get("outputs", []),
        "is_active": False,  # start inactive so user can review before running
    }
    new_res = db.table("automations").insert(clone).execute()
    return new_res.data[0]


@router.post("/{automation_id}/execute", status_code=202)
async def execute_automation(automation_id: str, payload: dict = {}):
    """Queue automation execution. If no steps but has instructions → uses AI agent automatically."""
    from app.workers.tasks import run_automation, run_ai_agent
    db = get_db()

    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    automation = res.data[0]
    steps = automation.get("steps") or []
    instructions = (automation.get("instructions") or "").strip()

    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "pending",
        "total_steps": len(steps),
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]

    # Auto-select mode: no steps but has instructions → AI agent
    if not steps and instructions:
        task = run_ai_agent.delay(automation_id, instructions, log_id)
    else:
        variables = payload.get("variables") or {}
        task = run_automation.delay(automation_id, variables, log_id)

    return {"task_id": task.id, "status": "queued", "execution_id": log_id}


@router.post("/{automation_id}/run-agent", status_code=202)
async def run_agent_endpoint(automation_id: str, payload: dict = {}):
    """Execute automation using GPT-4o vision agent. Just provide a prompt."""
    from app.workers.tasks import run_ai_agent
    db = get_db()

    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Campo 'prompt' é obrigatório")

    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "pending",
        "total_steps": 0,
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]

    task = run_ai_agent.delay(automation_id, prompt, log_id)
    return {"task_id": task.id, "status": "queued", "execution_id": log_id}


def _parse_selenium_csv(csv_text: str) -> list[dict]:
    """Convert Selenium IDE CSV export to AutoPilot steps."""
    # Fix Mojibake encoding (UTF-8 bytes interpreted as Latin-1 by Selenium IDE exporter)
    try:
        csv_text = csv_text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # already proper UTF-8

    # Selenium IDE prepends a metadata line (OS, browser, timestamp) before the header.
    # Find the real header row — the line that contains the column "#" and "Step".
    lines = csv_text.splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip().strip('"')
        if stripped.startswith("#") and "Step" in line:
            start_idx = i
            break
    csv_body = "\n".join(lines[start_idx:])

    steps = []
    reader = csv.DictReader(StringIO(csv_body))
    for i, row in enumerate(reader):
        step_text = (row.get("Step") or "").strip()
        data      = (row.get("Data") or "").strip()
        xpath     = (row.get("XPath") or "").strip()
        css       = (row.get("cssSelector") or "").strip()

        if not step_text or step_text == "#":
            continue

        # Prefer simple #id CSS selector; fall back to XPath, then full CSS
        if re.match(r"^#[\w-]+$", css):
            selector = css
        elif xpath:
            selector = xpath
        else:
            selector = css

        lower = step_text.lower()

        def base(action: str, **kwargs) -> dict:
            return {
                "order": i + 1,
                "action": action,
                "selector": kwargs.get("selector", ""),
                "value": kwargs.get("value", ""),
                "description": "",
                "waitTime": 1000,
                **{k: v for k, v in kwargs.items() if k not in ("selector", "value")},
            }

        # Open website → navigate
        if lower.startswith("open website"):
            url = data
            if not url:
                m = re.search(r"https?://\S+", step_text)
                url = m.group(0) if m else ""
            steps.append(base("navigate", value=url))

        # Click on → click
        elif lower.startswith("click on") or lower.startswith("click "):
            steps.append(base("click", selector=selector))

        # Enter X into Y → type
        elif lower.startswith("enter ") and " into " in lower:
            value = data
            is_pwd = (
                value == "******"
                or "senha" in lower
                or "password" in lower
                or "nm_senha" in selector
            )
            if is_pwd:
                value = "{{password}}"
            steps.append(base("type", selector=selector, value=value))

        # select X from Y → selectOption
        elif lower.startswith("select "):
            value = data
            select_by = "value"

            if value.startswith("label=regexp:"):
                pattern = value[len("label=regexp:"):]
                human = re.sub(r"\\s\+$", "", pattern)
                human = re.sub(r"\\s\+", " ", human)
                human = re.sub(r"\\s-\\s", " - ", human)
                human = re.sub(r"\\s", " ", human)
                value = human.strip()
                select_by = "label"
            elif value.startswith("label="):
                value = value[6:]
                select_by = "label"

            steps.append(base("selectOption", selector=selector, value=value, selectBy=select_by))

    return steps


@router.post("/parse-selenium")
async def parse_selenium(payload: dict):
    """
    Convert a Selenium IDE CSV export into AutoPilot steps.
    Body: { "csv": "<csv text>" }
    Returns: { "steps": [...], "count": N }
    """
    csv_text = payload.get("csv", "")
    if not csv_text:
        raise HTTPException(status_code=400, detail="Field 'csv' is required")
    steps = _parse_selenium_csv(csv_text)
    return {"steps": steps, "count": len(steps)}


# ── Chrome DevTools Recorder importer ────────────────────────────────────────

def _pick_selector(selectors: list) -> str:
    """Pick the best Playwright-compatible selector from Chrome DevTools Recorder selectors array."""
    if not selectors:
        return ""
    # Each item in selectors is a list (frame chain); take last element of each
    candidates = []
    for group in selectors:
        if isinstance(group, list) and group:
            candidates.append(group[-1])
        elif isinstance(group, str):
            candidates.append(group)
    if not candidates:
        return ""

    # Priority 1: CSS ID selector
    for s in candidates:
        if isinstance(s, str) and re.match(r"^#[\w-]+$", s):
            return s

    # Priority 2: any CSS selector (not aria, not xpath)
    for s in candidates:
        if isinstance(s, str) and not s.startswith("aria/") and not s.startswith("xpath/"):
            return s

    # Priority 3: aria → convert to :has-text
    for s in candidates:
        if isinstance(s, str) and s.startswith("aria/"):
            label = s[5:]
            label = re.sub(r'\[role=["\']?\w+["\']?\]', '', label).strip()
            if label:
                return f':has-text("{label}")'

    # Priority 4: xpath → strip prefix
    for s in candidates:
        if isinstance(s, str) and s.startswith("xpath/"):
            return s[6:]

    return candidates[0] if candidates else ""


def _convert_chrome_recording(recording: dict) -> list[dict]:
    """Convert Chrome DevTools Recorder JSON to AutoPilot steps."""
    steps = []
    for i, raw in enumerate(recording.get("steps", [])):
        kind = raw.get("type", "")

        if kind in ("setViewport", "emulateNetworkConditions", "keyUp", "mousedown", "mouseup"):
            continue

        elif kind == "navigate":
            url = raw.get("url", "")
            if url:
                steps.append({"action": "navigate", "url": url,
                               "description": f"Navegar para {url}", "waitTime": 1500})

        elif kind == "click":
            sel = _pick_selector(raw.get("selectors", []))
            if sel:
                steps.append({"action": "click", "selector": sel,
                               "description": f"Clique em {sel}", "waitTime": 800})

        elif kind == "change":
            sel = _pick_selector(raw.get("selectors", []))
            value = raw.get("value", "")
            if sel:
                # Heuristic: looks like a select element?
                if re.search(r"select|listbox|combobox", sel, re.I):
                    steps.append({"action": "selectOption", "selector": sel, "value": value,
                                   "description": f'Selecionar "{value}" em {sel}', "waitTime": 500})
                else:
                    steps.append({"action": "type", "selector": sel, "value": value,
                                   "description": f'Digitar "{value}" em {sel}', "waitTime": 500})

        elif kind == "hover":
            sel = _pick_selector(raw.get("selectors", []))
            if sel:
                steps.append({"action": "hover", "selector": sel,
                               "description": f"Hover em {sel}", "waitTime": 800})

        elif kind == "scroll":
            steps.append({"action": "scroll", "description": "Rolar página", "waitTime": 300})

        elif kind == "keyDown":
            key = raw.get("key", "")
            if key in ("Enter", "Return", "Tab"):
                steps.append({"action": "wait", "duration": 800,
                               "description": f"Aguardar após tecla {key}"})

        elif kind == "waitForElement":
            sel = _pick_selector(raw.get("selectors", []))
            if sel:
                steps.append({"action": "waitForSelector", "selector": sel,
                               "description": f"Aguardar {sel}", "waitTime": 0})

    return steps


@router.post("/import-chrome-recorder")
async def import_chrome_recorder(payload: dict):
    """
    Converte um JSON exportado pelo Chrome DevTools Recorder em passos AutoPilot.
    Body: { "recording": <objeto JSON do Chrome> }
    Returns: { "steps": [...], "count": N }
    """
    recording = payload.get("recording")
    if not recording or not isinstance(recording, dict):
        raise HTTPException(status_code=400, detail="Campo 'recording' inválido ou ausente")
    steps = _convert_chrome_recording(recording)
    if not steps:
        raise HTTPException(status_code=422, detail="Nenhum passo convertido. Verifique se o JSON é de uma gravação do Chrome DevTools Recorder.")
    return {"steps": steps, "count": len(steps)}
