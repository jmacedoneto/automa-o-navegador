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
- steps: list of step dicts. Each step has an `id` and one of:
    - {"id":"auth","auth":{"type":"form_login","url":"...","credentials_ref":"site_login","selectors":{...},"success_assert":{...}}}
        (only when login is required; auth must be the FIRST step)
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

CRITICAL: If the user mentions "login", "autenticação", "sign in", the FIRST element of `steps` MUST be {"id":"auth","auth":{...}}. The runner strips it from the step list at runtime and uses it to authenticate before any other step.
If the user explicitly says "no auth" or "já logado" or similar, do NOT include an auth step.
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

    if "automation_name" not in draft or not draft["automation_name"]:
        draft["automation_name"] = _slugify(description)
    draft["automation_name"] = _slugify(draft["automation_name"])
    draft["version"] = int(draft.get("version", 1))
    draft.setdefault("steps", [])
    draft.setdefault("notes", [])
    if "auth" in draft and isinstance(draft["auth"], dict):
        if "credentials_ref" not in draft["auth"]:
            draft["auth"]["credentials_ref"] = "site_login"
    return draft