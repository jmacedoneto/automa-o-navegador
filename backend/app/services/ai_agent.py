"""
OpenAI agent with two modes:
  1. generate_steps  — converts text instructions into automation steps
  2. fill_variables  — resolves {{placeholders}} from context data
"""
from typing import Any
from openai import AsyncOpenAI
from app.core.model_config import DEFAULT_OPENAI_MODEL, normalize_openai_model

STEP_SCHEMA = {
    "name": "create_steps",
    "description": "Create a list of browser automation steps from the user instructions.",
    "parameters": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": [
                            "navigate", "click", "type", "selectOption",
                            "wait", "waitForSelector", "screenshot",
                            "extractTable", "extractText", "extractImages",
                            "download", "scroll", "evaluate"
                        ]},
                        "selector": {"type": "string"},
                        "url": {"type": "string"},
                        "value": {"type": "string"},
                        "duration": {"type": "integer"},
                        "key": {"type": "string"},
                        "limit": {"type": "integer"},
                        "description": {"type": "string"},
                    },
                    "required": ["type"],
                },
            }
        },
        "required": ["steps"],
    },
}

FILL_SCHEMA = {
    "name": "fill_variables",
    "description": "Resolve all {{placeholder}} variables from available context data.",
    "parameters": {
        "type": "object",
        "properties": {
            "resolved": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Map of variable_name → resolved_value",
            }
        },
        "required": ["resolved"],
    },
}


async def generate_steps(
    instructions: str,
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    context: str = "",
) -> list[dict[str, Any]]:
    client = AsyncOpenAI(api_key=api_key)

    system = (
        "You are a browser automation expert. "
        "Convert the user instructions into precise Playwright automation steps. "
        "Use CSS selectors that are robust (prefer id, data-*, aria-label over positional classes). "
        "Always add a screenshot step at the end."
    )

    messages = [{"role": "system", "content": system}]
    if context:
        messages.append({"role": "user", "content": f"Context about the target website:\n{context}"})
    messages.append({"role": "user", "content": instructions})

    response = await client.chat.completions.create(
        model=normalize_openai_model(model),
        messages=messages,
        tools=[{"type": "function", "function": STEP_SCHEMA}],
        tool_choice={"type": "function", "function": {"name": "create_steps"}},
    )

    args = response.choices[0].message.tool_calls[0].function.arguments
    import json
    return json.loads(args).get("steps", [])


async def fill_variables(
    placeholders: list[str],
    context_data: dict[str, Any],
    instructions: str,
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
) -> dict[str, str]:
    """
    Given a list of {{placeholder}} names and available context data,
    ask the AI to resolve each placeholder to a concrete value.
    """
    import json
    client = AsyncOpenAI(api_key=api_key)

    system = (
        "You are an intelligent form-filling assistant. "
        "Given context data and a list of variable names, "
        "map each variable to the most appropriate value from the context. "
        "If a value cannot be determined, leave it empty."
    )

    user_message = (
        f"Variables to resolve: {placeholders}\n\n"
        f"Context data:\n{json.dumps(context_data, ensure_ascii=False, indent=2)}\n\n"
        f"Additional instructions: {instructions}"
    )

    response = await client.chat.completions.create(
        model=normalize_openai_model(model),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        tools=[{"type": "function", "function": FILL_SCHEMA}],
        tool_choice={"type": "function", "function": {"name": "fill_variables"}},
    )

    args = response.choices[0].message.tool_calls[0].function.arguments
    return json.loads(args).get("resolved", {})
