import asyncio

from app.automation.steps.interaction import click, fill
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeLocator:
    def __init__(self, selector):
        self.selector = selector
        self.clicks = 0
        self.fills = []

    # Mimics Playwright's Locator.first (returns self when single match).
    @property
    def first(self):
        return self

    async def click(self, **kwargs):
        self.clicks += 1

    async def fill(self, value, **kwargs):
        self.fills.append((value, kwargs))


class _FakePage:
    def __init__(self):
        self._locators: dict[str, _FakeLocator] = {}

    def locator(self, selector):
        if selector not in self._locators:
            self._locators[selector] = _FakeLocator(selector)
        return self._locators[selector]


def test_click_resolves_selector():
    page = _FakePage()
    ctx = RunContext(inputs={"btn": "button#ok"})
    _run(click(page, {"selector": "{{input.btn}}"}, ctx))
    assert page._locators["button#ok"].clicks == 1


def test_click_with_custom_timeout():
    page = _FakePage()
    ctx = RunContext()
    _run(click(page, {"selector": "a", "timeout_ms": 5000}, ctx))
    # timeout_ms is consumed by the handler — not asserted via the fake locator.
    assert page._locators["a"].clicks == 1


def test_fill_multiple_fields():
    page = _FakePage()
    ctx = RunContext(inputs={"nome": "Ana", "doc": "123"})
    _run(fill(page, {"#nome": "{{input.nome}}", "#doc": "{{input.doc}}"}, ctx))
    assert page._locators["#nome"].fills == [("Ana", {})]
    assert page._locators["#doc"].fills == [("123", {})]
