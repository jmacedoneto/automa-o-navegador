import asyncio
from pathlib import Path

from app.automation.extraction import extract_text, extract_table, screenshot
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeTextLocator:
    def __init__(self, text):
        self._text = text

    async def text_content(self):
        return self._text


class _FakeCell:
    def __init__(self, text):
        self._text = text

    async def text_content(self):
        return self._text


class _FakeHeaderRow:
    def __init__(self, cells):
        self._cells = cells

    def query_selector_all(self, sel):
        return [_FakeCell(c) for c in self._cells]


class _FakeDataRow:
    def __init__(self, cells):
        self._cells = cells

    def query_selector_all(self, sel):
        return [_FakeCell(c) for c in self._cells]


class _FakeTable:
    def __init__(self, header, data_rows):
        self._header = header
        self._data_rows = data_rows

    def query_selector_all(self, sel):
        if sel == "tr":
            return [_FakeHeaderRow(self._header)] + [_FakeDataRow(r) for r in self._data_rows]


class _FakePage:
    def __init__(self, *, tables=None, text_results=None):
        self._tables = tables or {}
        self._text_results = text_results or {}
        self.shots = []

    def locator(self, selector):
        text = self._text_results.get(selector, "")

        class _L:
            @property
            def first(self):
                return self

            async def text_content(self):
                return text

        return _L()

    def query_selector(self, selector):
        return self._tables.get(selector)

    async def screenshot(self, **kwargs):
        self.shots.append(kwargs)
        return b"PNG"


def test_extract_text_binds_value():
    page = _FakePage(text_results={".valor": "R$ 100,00"})
    ctx = RunContext()
    _run(extract_text(page, {"selector": ".valor", "bind": "preco"}, ctx))
    assert ctx.bindings["preco"] == "R$ 100,00"


def test_extract_text_without_bind_drops_value():
    page = _FakePage(text_results={".x": "anything"})
    ctx = RunContext()
    _run(extract_text(page, {"selector": ".x"}, ctx))
    assert "preco" not in ctx.bindings


def test_extract_table_to_list_of_dicts():
    page = _FakePage(tables={"table.plans": _FakeTable(
        header=["Plano", "Valor"],
        data_rows=[
            ["Prata", "R$ 100"],
            ["Ouro", "R$ 200"],
            ["Diamante", "R$ 300"],
        ],
    )})
    ctx = RunContext()
    _run(extract_table(page, {"selector": "table.plans", "bind": "plans"}, ctx))
    assert ctx.bindings["plans"] == [
        {"Plano": "Prata", "Valor": "R$ 100"},
        {"Plano": "Ouro", "Valor": "R$ 200"},
        {"Plano": "Diamante", "Valor": "R$ 300"},
    ]


def test_extract_table_raises_when_table_missing():
    page = _FakePage(tables={})  # no tables
    ctx = RunContext()
    with __import__("pytest").raises(ValueError, match="no table"):
        _run(extract_table(page, {"selector": "table.missing", "bind": "x"}, ctx))


def test_extract_table_skips_malformed_rows():
    page = _FakePage(tables={"table.plans": _FakeTable(
        header=["Plano", "Valor"],
        data_rows=[
            ["Prata", "R$ 100"],
            ["Ouro"],  # malformed: only 1 cell
            ["Diamante", "R$ 300"],
        ],
    )})
    ctx = RunContext()
    _run(extract_table(page, {"selector": "table.plans", "bind": "plans"}, ctx))
    # Malformed row is skipped.
    assert len(ctx.bindings["plans"]) == 2


def test_screenshot_writes_to_path(tmp_path):
    page = _FakePage()
    target = tmp_path / "shot.png"
    _run(screenshot(page, {"path": str(target)}, RunContext()))
    assert target.exists()
    assert page.shots and "path" in page.shots[0]


def test_screenshot_creates_parent_dirs(tmp_path):
    page = _FakePage()
    target = tmp_path / "nested" / "deeper" / "shot.png"
    _run(screenshot(page, {"path": str(target)}, RunContext()))
    assert target.exists()
