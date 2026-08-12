"""run_ai step — extract structured data from the current page via OpenAI
tool-calling.

P2 implements the one-shot extraction path. The agent-loop path
(`run_ai_agent` in `tasks.py`) is separate and not used here.

Flow:
1. Resolve schema name -> Pydantic class via `get_schema`.
2. Build a tool definition with the schema's JSON schema.
3. Page content + instruction -> OpenAI chat completions.
4. OpenAI returns a tool call with the parsed JSON.
5. Validate against the Pydantic class.
6. Optionally bind to `ctx.bindings[bind]`.
"""
from typing import Any

from openai import AsyncOpenAI

from app.automation.bindings import interpolate
from app.automation.models import RunContext
from app.automation.schemas import get_schema
from app.core.model_config import normalize_openai_model

# Cap on the HTML we ship to the model. Full DOMs routinely exceed the
# context window, and the tail of a page is rarely where the data lives.
_MAX_HTML_CHARS = 50_000

_OPENAI_CLIENT: AsyncOpenAI | None = None


def _reset_openai_client() -> None:
    """Test helper — clears the singleton so the next call rebuilds it."""
    global _OPENAI_CLIENT
    _OPENAI_CLIENT = None


def _get_openai_client() -> AsyncOpenAI:
    """Lazily create a singleton OpenAI client."""
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        from app.core.config import settings

        api_key = settings.OPENAI_API_KEY or ""
        if not api_key:
            raise RuntimeError("OpenAI API key not configured (set OPENAI_API_KEY env)")
        _OPENAI_CLIENT = AsyncOpenAI(api_key=api_key)
    return _OPENAI_CLIENT


async def run_ai(page: Any, params: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Extract structured data from `page.content()` via OpenAI tool-calling.

    `params`:
      schema:        string name of a registered Pydantic class (e.g. "ResultadoCotacao")
      instruction:   what to extract from the page
      bind:          optional name to bind the result dict
      model:         optional override, coerced to the model_config whitelist
      max_tokens:    default 800

    Raises `SchemaNotFoundError` (a `KeyError`) for an unknown schema name,
    `RuntimeError` when the model declines to call the tool, and
    `pydantic.ValidationError` (a `ValueError`) when the returned JSON does
    not satisfy the schema.
    """
    schema_name = params["schema"]
    # Resolve the schema first: a bad name is a DSL authoring error and
    # should fail before we spend a page serialization or an API call.
    schema_cls = get_schema(schema_name)

    instruction = interpolate(params["instruction"], ctx)
    max_tokens = int(params.get("max_tokens", 800))
    model = normalize_openai_model(params.get("model"))
    bind = params.get("bind")

    page_html = await page.content()
    truncated = page_html[:_MAX_HTML_CHARS]

    tool_name = f"extract_{schema_name}"
    tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": f"Extract structured data conforming to {schema_name}",
            "parameters": schema_cls.model_json_schema(),
        },
    }

    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured data from HTML pages. "
                    "Use the tool function to return the parsed value. "
                    "Match the schema EXACTLY — all required fields, correct types."
                ),
            },
            {
                "role": "user",
                "content": f"Page HTML:\n```html\n{truncated}\n```\n\nTask: {instruction}",
            },
        ],
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": f"extract_{schema_name}"}},
        max_completion_tokens=max_tokens,
    )

    msg = response.choices[0].message
    if not msg.tool_calls:
        raise RuntimeError(
            f"run_ai: OpenAI returned no tool call for schema {schema_name!r}. "
            f"Response: {msg.content}"
        )

    raw_args = msg.tool_calls[0].function.arguments
    parsed = schema_cls.model_validate_json(raw_args)

    result = parsed.model_dump()
    if bind:
        ctx.bindings[bind] = result
    return result
