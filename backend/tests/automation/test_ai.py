import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from app.automation.ai import run_ai
from app.automation.models import RunContext
from app.automation.schemas.cotacao_pvs import ResultadoCotacao


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakePage:
    def __init__(self, html="<html><body>R$ 100,00</body></html>"):
        self._html = html

    async def content(self):
        return self._html


def _fake_response(args_dict):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message = MagicMock()
    r.choices[0].message.tool_calls = [MagicMock()]
    r.choices[0].message.tool_calls[0].function.arguments = json.dumps(args_dict)
    return r


def test_run_ai_calls_openai_with_tool_schema(monkeypatch):
    fake_response = _fake_response({
        "valor_total": 100.0,
        "prazo_meses": 12,
        "status": "ok",
    })
    fake_client = MagicMock()
    fake_client.chat = MagicMock()
    fake_client.chat.completions = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("app.automation.ai._get_openai_client", lambda: fake_client)

    page = _FakePage()
    ctx = RunContext()
    params = {
        "schema": "ResultadoCotacao",
        "instruction": "extract the plan details",
        "bind": "resultado",
    }
    _run(run_ai(page, params, ctx))
    assert ctx.bindings["resultado"]["valor_total"] == 100.0
    assert ctx.bindings["resultado"]["status"] == "ok"

    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert "tools" in call_kwargs
    tool = call_kwargs["tools"][0]
    assert tool["function"]["name"] == "extract_ResultadoCotacao"
    schema_props = tool["function"]["parameters"]["properties"]
    assert "valor_total" in schema_props
    assert "prazo_meses" in schema_props


def test_run_ai_validates_against_schema(monkeypatch):
    fake_response = _fake_response({
        "valor_total": "not a number",
        "prazo_meses": 12,
        "status": "ok",
    })
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("app.automation.ai._get_openai_client", lambda: fake_client)

    page = _FakePage()
    ctx = RunContext()
    with __import__("pytest").raises(ValueError, match="valor_total"):
        _run(run_ai(page, {"schema": "ResultadoCotacao", "instruction": "x"}, ctx))


def test_run_ai_handles_no_tool_call(monkeypatch):
    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message = MagicMock()
    fake_response.choices[0].message.tool_calls = None

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("app.automation.ai._get_openai_client", lambda: fake_client)

    page = _FakePage()
    ctx = RunContext()
    with __import__("pytest").raises(RuntimeError, match="no tool call"):
        _run(run_ai(page, {"schema": "ResultadoCotacao", "instruction": "x"}, ctx))


def test_run_ai_unknown_schema_raises(monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr("app.automation.ai._get_openai_client", lambda: fake_client)
    page = _FakePage()
    ctx = RunContext()
    with __import__("pytest").raises(KeyError, match="nope"):
        _run(run_ai(page, {"schema": "nope", "instruction": "x"}, ctx))


def test_run_ai_interpolates_instruction(monkeypatch):
    fake_response = _fake_response({
        "valor_total": 100.0, "prazo_meses": 12, "status": "ok",
    })
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("app.automation.ai._get_openai_client", lambda: fake_client)

    page = _FakePage()
    ctx = RunContext(inputs={"task": "extract value"})
    _run(run_ai(page, {"schema": "ResultadoCotacao", "instruction": "{{input.task}}"}, ctx))
    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert "extract value" in call_kwargs["messages"][1]["content"]
