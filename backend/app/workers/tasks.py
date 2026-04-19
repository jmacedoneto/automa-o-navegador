"""
Celery tasks for async execution and delivery.
"""
import asyncio
import json
from datetime import datetime, timezone

from app.workers.celery_app import celery
from app.core.database import get_db, get_setting
from app.core.config import settings
from app.services.browser_executor import execute_automation
from app.services.computer_agent import run_agent
from app.services.integrations.webhook import send_webhook
from app.services.integrations.whatsapp import send_whatsapp
from app.services.integrations.sheets import append_row


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery.task(bind=True, max_retries=2, default_retry_delay=30, time_limit=9000, soft_time_limit=8970)
def run_automation(
    self,
    automation_id: str,
    variables: dict | None = None,
    log_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
):
    variables = variables or {}
    db = get_db()

    # Fetch automation
    res = db.table("automations").select("*").eq("id", automation_id).maybe_single().execute()
    if not res.data:
        raise ValueError(f"Automation {automation_id} not found")

    automation = res.data
    steps = automation.get("steps") or []
    credentials = automation.get("credentials") or {}
    outputs = automation.get("outputs") or []
    erp_url = (automation.get("erp_url") or "").strip()

    # Merge stored credentials into variables
    variables = {**credentials, **variables}

    # Auto-prepend a navigate step when erp_url is set but no step navigates to it.
    # This guarantees at least one screenshot and a real page load.
    has_navigate = any(
        (s.get("action") == "navigate" or s.get("type") == "navigate")
        and (s.get("url") or s.get("value"))
        for s in steps
    )
    if erp_url and not has_navigate:
        steps = [{"action": "navigate", "url": erp_url, "waitTime": 1000}] + steps

    # Fetch runtime settings from DB
    browserless_url = (_run(get_setting("browserless_url")) or settings.BROWSERLESS_URL or "").strip()
    browserless_token = (_run(get_setting("browserless_token")) or settings.BROWSERLESS_TOKEN or "").strip()

    if not browserless_url:
        error_message = (
            "Browserless não configurado. Defina browserless_url nas Settings "
            "ou via variável de ambiente BROWSERLESS_URL."
        )
        db.table("execution_logs").update({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
        }).eq("id", log_id).execute()
        db.table("automations").update({
            "last_execution_at": datetime.now(timezone.utc).isoformat(),
            "last_execution_status": "failed",
        }).eq("id", automation_id).execute()
        raise ValueError(error_message)

    print(f"[run_automation] Browserless URL: {browserless_url}")

    # Use pre-created log if provided, otherwise create a new one
    if log_id:
        db.table("execution_logs").update({
            "status": "running",
            "total_steps": len(steps),
        }).eq("id", log_id).execute()
    else:
        log_res = db.table("execution_logs").insert({
            "automation_id": automation_id,
            "status": "running",
            "total_steps": len(steps),
            "steps_completed": 0,
        }).execute()
        log_id = log_res.data[0]["id"]

    _live_screenshots: list[str] = []

    def _update_run(payload: dict):
        if not run_id:
            return
        try:
            db.table("execution_runs").update(payload).eq("id", run_id).execute()
        except Exception:
            pass

    def _on_step(step_num: int):
        try:
            db.table("execution_logs").update({
                "steps_completed": step_num,
            }).eq("id", log_id).execute()
            _update_run({"steps_completed": step_num})
        except Exception:
            pass

    def _on_screenshot(b64: str):
        try:
            _live_screenshots.append(b64)
            # Persist all accumulated screenshots so live preview shows each step
            db.table("execution_logs").update({
                "screenshots": _live_screenshots,
            }).eq("id", log_id).execute()
            _update_run({"screenshots": list(_live_screenshots)})
        except Exception:
            pass

    if run_id:
        _update_run({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_steps": len(steps),
        })

    try:
        result = _run(execute_automation(steps, variables, browserless_url, browserless_token, _on_step, _on_screenshot))

        final_update: dict = {
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "steps_completed": result["steps_completed"],
            "extracted_data": result["extracted_data"],
        }
        # Prefer explicit screenshot steps; fall back to live screenshots accumulated during execution
        if result["screenshots"]:
            final_update["screenshots"] = result["screenshots"]
        elif _live_screenshots:
            final_update["screenshots"] = _live_screenshots
        db.table("execution_logs").update(final_update).eq("id", log_id).execute()

        db.table("automations").update({
            "last_execution_at": datetime.now(timezone.utc).isoformat(),
            "last_execution_status": "success",
        }).eq("id", automation_id).execute()

        # Deliver outputs — capture any delivery errors
        delivery_errors = _deliver_outputs(outputs, result, automation["name"])
        if delivery_errors:
            db.table("execution_logs").update({
                "error_message": "Entrega falhou: " + "; ".join(delivery_errors),
            }).eq("id", log_id).execute()
            _update_run({"error_message": "Entrega falhou: " + "; ".join(delivery_errors)})

        _update_run({
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "steps_completed": result["steps_completed"],
            "extracted_data": result["extracted_data"],
            "screenshots": result["screenshots"] or list(_live_screenshots),
        })

    except Exception as exc:
        db.table("execution_logs").update({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(exc),
        }).eq("id", log_id).execute()

        db.table("automations").update({
            "last_execution_at": datetime.now(timezone.utc).isoformat(),
            "last_execution_status": "failed",
        }).eq("id", automation_id).execute()

        _update_run({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(exc),
        })

        # ── Agent recovery: if automation has instructions, queue agent to recover ──
        instructions = (automation.get("instructions") or "").strip()
        if instructions and self.request.retries == 0:
            try:
                # Queue agent to recover and regenerate steps
                # Note: do NOT clear steps here — agent will overwrite them on success
                recovery_log = db.table("execution_logs").insert({
                    "automation_id": automation_id,
                    "status": "pending",
                    "total_steps": 0,
                    "steps_completed": 0,
                }).execute()
                recovery_log_id = recovery_log.data[0]["id"]
                run_ai_agent.apply_async(args=[automation_id, instructions, recovery_log_id])
                print(f"[run_automation] Steps failed — queued agent recovery for {automation_id}")
            except Exception as recovery_err:
                print(f"[run_automation] Recovery queue failed: {recovery_err}")
        else:
            raise self.retry(exc=exc)

    return {"log_id": log_id, "status": "success"}


def _deliver_outputs(outputs: list[dict], result: dict, automation_name: str) -> list[str]:
    """Deliver outputs and return a list of error strings (empty = all succeeded)."""
    payload = {
        "automation": automation_name,
        "extracted_data": result.get("extracted_data", {}),
        "steps_completed": result.get("steps_completed"),
        "screenshots_count": len(result.get("screenshots", [])),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    errors: list[str] = []

    for output in outputs:
        kind = output.get("type")
        try:
            if kind == "webhook":
                _run(send_webhook(
                    url=output["url"],
                    payload=payload,
                    headers=output.get("headers"),
                ))

            elif kind == "whatsapp":
                message_tpl = output.get("message", "Automação '{name}' concluída.")
                message = message_tpl.replace("{name}", automation_name)
                file_path = None
                extracted = result.get("extracted_data", {})
                file_keys = [k for k, v in extracted.items() if isinstance(v, str) and v.startswith("/tmp/")]
                if file_keys:
                    file_path = extracted[file_keys[0]]
                _run(send_whatsapp(config=output, text=message, file_path=file_path))

            elif kind == "sheets":
                service_account_raw = _run(get_setting("google_service_account")) or ""
                if not service_account_raw:
                    errors.append("Google Sheets: google_service_account não configurado")
                    continue
                service_account = json.loads(service_account_raw)
                extracted = result.get("extracted_data", {})
                row = list(extracted.values()) if extracted else [json.dumps(payload)]
                _run(append_row(
                    service_account_json=service_account,
                    spreadsheet_id=output["spreadsheet_id"],
                    sheet=output.get("sheet", "Sheet1"),
                    row=row,
                ))

        except Exception as e:
            err_msg = f"{kind} → {output.get('url', output.get('instance', ''))}: {e}"
            print(f"[delivery] {err_msg}")
            errors.append(err_msg)

    return errors


# ── AI Agent helpers ──────────────────────────────────────────────────────────

async def _generate_automation_steps(api_key: str, model: str, task: str, steps_done: list[dict]) -> list[dict]:
    """Ask GPT to convert agent execution log into clean, reproducible automation steps."""
    if not steps_done or not api_key:
        return []
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)

        steps_text = json.dumps(steps_done, ensure_ascii=False)
        prompt = f"""A browser automation task was completed successfully.

Task: "{task}"

All actions executed (may include failed retries):
{steps_text}

Create a CLEAN, MINIMAL step sequence that reliably reproduces only the SUCCESSFUL path.
Rules:
- Remove failed attempts and retries
- Keep only necessary steps in the correct order
- For navigate: include the URL
- For click: use selector if available, otherwise keep x/y coordinates from the step
- For type/selectOption: use the selector and value from the original step
- For key press: keep the key value

Return JSON: {{"steps": [...]}}

Step formats:
{{"action":"navigate","url":"https://...","description":"...","waitTime":1000}}
{{"action":"click","selector":"#btn","description":"...","waitTime":500}}
{{"action":"click","selector":"","x":640,"y":360,"description":"...","waitTime":500}}
{{"action":"type","selector":"#input","value":"text","description":"...","waitTime":500}}
{{"action":"selectOption","selector":"#select","value":"Option","selectBy":"label","description":"...","waitTime":500}}
{{"action":"key","value":"Enter","description":"...","waitTime":300}}
{{"action":"wait","duration":2000,"description":"...","waitTime":2000}}"""

        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
            temperature=0,
        )
        result = json.loads(resp.choices[0].message.content or "{}")
        steps = result.get("steps", [])
        for i, s in enumerate(steps):
            s["order"] = i + 1
        return steps
    except Exception as e:
        print(f"[step_generation] Error: {e}")
        return []


def _safe_downloads(downloads: dict) -> dict:
    """Trim download data to at most 200 rows per file so webhook payloads stay reasonable."""
    result = {}
    for filename, data in downloads.items():
        if isinstance(data, list):
            result[filename] = data[:200]
            if len(data) > 200:
                result[f"{filename}__truncated"] = f"{len(data)} rows total, showing first 200"
        else:
            result[filename] = data
    return result


def _save_agent_memory(db, automation_id: str, credentials: dict, prompt: str, summary: str, success: bool):
    """Append a one-line memory entry to automation credentials._agent_memory."""
    try:
        from datetime import date
        today = date.today().isoformat()
        status_label = "SUCESSO" if success else "FALHA"
        # Trim summary to keep memory compact
        short = (summary or "")[:300].replace("\n", " ")
        new_entry = f"[{today}] {status_label}: {short}"

        existing = (credentials.get("_agent_memory") or "").strip()
        entries = [e for e in existing.split("\n---\n") if e.strip()]
        # Keep last 4 entries max
        entries = entries[-4:]
        entries.append(new_entry)
        new_memory = "\n---\n".join(entries)

        updated_creds = {**credentials, "_agent_memory": new_memory}
        db.table("automations").update({"credentials": updated_creds}).eq("id", automation_id).execute()
    except Exception:
        pass  # memory is best-effort, never block execution


# ── AI Agent task ─────────────────────────────────────────────────────────────

@celery.task(bind=True, max_retries=0, time_limit=900, soft_time_limit=870)
def run_ai_agent(
    self,
    automation_id: str,
    prompt: str,
    log_id: str | None = None,
):
    """Run the GPT-4o vision agent for the given automation + prompt."""
    from playwright.sync_api import sync_playwright

    db = get_db()

    res = db.table("automations").select("*").eq("id", automation_id).maybe_single().execute()
    if not res.data:
        raise ValueError(f"Automation {automation_id} not found")

    automation = res.data
    erp_url = (automation.get("erp_url") or "").strip()
    credentials = automation.get("credentials") or {}
    outputs = automation.get("outputs") or []

    browserless_url = (_run(get_setting("browserless_url")) or settings.BROWSERLESS_URL or "").strip()
    browserless_token = (_run(get_setting("browserless_token")) or settings.BROWSERLESS_TOKEN or "").strip()
    api_key = _run(get_setting("openai_api_key")) or settings.OPENAI_API_KEY or ""
    from app.core.model_config import normalize_openai_model
    model = normalize_openai_model(_run(get_setting("openai_model")))

    if not browserless_url:
        raise ValueError("Browserless não configurado")
    if not api_key:
        raise ValueError("OpenAI API key não configurada em Configurações")

    # Build full prompt including URL and credentials context
    _hidden = ("password", "senha", "pass", "_agent_memory")
    creds_hint = ""
    if credentials:
        visible = {k: v for k, v in credentials.items() if k not in _hidden}
        if visible:
            creds_hint = "\nCredenciais disponíveis: " + ", ".join(f"{k}={v}" for k, v in visible.items())
        has_pwd = any(k in ("password", "senha", "pass") for k in credentials)
        if has_pwd:
            creds_hint += " (senha disponível)"

    full_prompt = prompt
    if erp_url:
        full_prompt = f"Acesse {erp_url}{creds_hint}\n\nTarefa: {prompt}"

    # Inject memory from previous runs of this same prompt
    agent_memory = (credentials.get("_agent_memory") or "").strip()
    if agent_memory:
        full_prompt += (
            "\n\n━━━ MEMÓRIA DE EXECUÇÕES ANTERIORES ━━━\n"
            + agent_memory
            + "\n\nUse estas informações: siga o caminho que funcionou, evite o que falhou."
        )

    # Create execution log
    if log_id:
        db.table("execution_logs").update({
            "status": "running",
        }).eq("id", log_id).execute()
    else:
        log_res = db.table("execution_logs").insert({
            "automation_id": automation_id,
            "status": "running",
            "total_steps": 0,
            "steps_completed": 0,
        }).execute()
        log_id = log_res.data[0]["id"]

    screenshots: list[str] = []
    steps_done: list[dict] = []
    result_summary = ""
    downloads_captured: dict = {}

    async def _run_async():
        nonlocal result_summary

        cdp_url = browserless_url.rstrip("/")
        if cdp_url.startswith("https://"):
            cdp_url = cdp_url.replace("https://", "wss://")
        elif cdp_url.startswith("http://"):
            cdp_url = cdp_url.replace("http://", "ws://")
        if browserless_token:
            cdp_url = f"{cdp_url}?token={browserless_token}"

        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            page = await browser.new_page()
            page.set_default_timeout(15000)

            async def _on_screenshot(b64):
                screenshots.append(b64)
                try:
                    db.table("execution_logs").update({"screenshots": screenshots}).eq("id", log_id).execute()
                except Exception:
                    pass

            cancelled = False

            async def _is_cancelled() -> bool:
                try:
                    r = db.table("execution_logs").select("status").eq("id", log_id).maybe_single().execute()
                    return (r.data or {}).get("status") == "cancelled"
                except Exception:
                    return False

            async def _on_action(action):
                nonlocal cancelled
                if await _is_cancelled():
                    cancelled = True
                    raise Exception("Cancelado pelo usuário")

            async def _on_step(step):
                steps_done.append(step)
                try:
                    db.table("execution_logs").update({
                        "steps_completed": len(steps_done),
                        "total_steps": len(steps_done),
                    }).eq("id", log_id).execute()
                except Exception:
                    pass

            async def _on_done(success=True, message="", downloads=None):
                nonlocal result_summary
                result_summary = message
                if downloads:
                    downloads_captured.update(downloads)
                    try:
                        db.table("execution_logs").update({
                            "extracted_data": {"summary": message, "downloads": _safe_downloads(downloads)},
                        }).eq("id", log_id).execute()
                    except Exception:
                        pass

            await run_agent(
                page=page,
                instruction=full_prompt,
                api_key=api_key,
                model=model,
                on_screenshot=_on_screenshot,
                on_action=_on_action,
                on_step=_on_step,
                on_done=_on_done,
                max_steps=50,
            )
            await browser.close()

    execution_success = True
    execution_error = None
    try:
        _run(_run_async())

        extracted = {"summary": result_summary}
        if downloads_captured:
            extracted["downloads"] = _safe_downloads(downloads_captured)

        db.table("execution_logs").update({
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "steps_completed": len(steps_done),
            "total_steps": len(steps_done),
            "extracted_data": extracted,
            "screenshots": screenshots,
        }).eq("id", log_id).execute()
        db.table("automations").update({
            "last_execution_at": datetime.now(timezone.utc).isoformat(),
            "last_execution_status": "success",
        }).eq("id", automation_id).execute()

        # Deliver via outputs (includes downloaded file data)
        if outputs:
            _deliver_outputs(
                outputs,
                {"extracted_data": extracted, "steps_completed": len(steps_done), "screenshots": screenshots},
                automation.get("name", ""),
            )

        # Store memory of what worked for future runs
        _save_agent_memory(db, automation_id, credentials, prompt, result_summary, success=True)

        # ── Generate and save clean automation steps from this successful run ──
        # Next executions will use these steps directly (no AI needed)
        agent_succeeded = result_summary and "Maximum steps" not in result_summary
        if agent_succeeded and steps_done:
            try:
                clean_steps = _run(_generate_automation_steps(api_key, model, prompt, steps_done))
                if clean_steps:
                    db.table("automations").update({"steps": clean_steps}).eq("id", automation_id).execute()
                    print(f"[run_ai_agent] Saved {len(clean_steps)} clean steps to automation {automation_id}")
            except Exception as gen_err:
                print(f"[run_ai_agent] Step generation failed (non-critical): {gen_err}")

    except Exception as exc:
        execution_success = False
        execution_error = exc
        db.table("execution_logs").update({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(exc),
            "screenshots": screenshots,
        }).eq("id", log_id).execute()
        db.table("automations").update({
            "last_execution_at": datetime.now(timezone.utc).isoformat(),
            "last_execution_status": "failed",
        }).eq("id", automation_id).execute()

        # Store memory of failure too
        _save_agent_memory(db, automation_id, credentials, prompt, str(exc), success=False)
        raise

    return {"log_id": log_id, "status": "success"}
