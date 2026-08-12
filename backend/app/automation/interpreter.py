"""Maps a Step to its handler and invokes it with retry.

A thin dispatch: adding a new step type is one line in _HANDLERS (handlers
themselves live in app.automation.steps.*). Retry is wrapped here so
handlers stay pure and don't need to know about RetryPolicy.

Note: handlers internally call `interpolate` on their params, so the
interpreter does NOT interpolate before dispatch — handlers do it. This
lets handlers control which fields interpolate (e.g., fill iterates dict
items where keys are selectors).
"""
from typing import Awaitable, Callable
from playwright.async_api import Page

from app.automation.models import RunContext, Step
from app.automation.retry import with_retry
from app.automation.steps import navigation, interaction, assertion

Handler = Callable[[Page, dict, RunContext], Awaitable]

_HANDLERS: dict[str, Handler] = {
    "goto": navigation.goto,
    "wait_for": navigation.wait_for,
    "click": interaction.click,
    "fill": interaction.fill,
    "assert": assertion.assert_text,
}


async def execute_step(page: Page, step: Step, ctx: RunContext) -> None:
    handler = _HANDLERS.get(step.action)
    if handler is None:
        raise NotImplementedError(
            f"Step action {step.action!r} not implemented in P0 "
            f"(supported: {sorted(_HANDLERS)})"
        )

    async def _run_once():
        await handler(page, step.params, ctx)

    await with_retry(_run_once, step.retry)
