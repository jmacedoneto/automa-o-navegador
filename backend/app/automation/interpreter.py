"""Maps a Step to its handler and invokes it with retry.

A thin dispatch: adding a new step type is one line in _HANDLERS (handlers
themselves live in app.automation.steps.*). Retry is wrapped here so
handlers stay pure and don't need to know about RetryPolicy.

Note: handlers internally call `interpolate` on their params, so the
interpreter does NOT interpolate before dispatch — handlers do it.
"""
from typing import Any, Awaitable, Callable
from playwright.async_api import Page

from app.automation.models import RunContext, Step
from app.automation.retry import with_retry
from app.automation.steps import navigation, interaction, assertion
from app.automation import control, extraction, run_python

Handler = Callable[[Page, dict, RunContext], Awaitable]

_HANDLERS: dict[str, Handler] = {
    "goto": navigation.goto,
    "wait_for": navigation.wait_for,
    "click": interaction.click,
    "fill": interaction.fill,
    "assert": assertion.assert_text,
    "extract_text": extraction.extract_text,
    "extract_table": extraction.extract_table,
    "screenshot": extraction.screenshot,
    "run_python": run_python.run_python,
    # for_each / if need a visitor callback — handled separately below.
}


async def execute_step(
    page: Page,
    step: Step,
    ctx: RunContext,
    on_visit_child: Callable[[RunContext, Any], Any] | None = None,
) -> None:
    """Dispatch a step to its handler.

    For control flow (for_each / if), supply `on_visit_child` — a callable
    that runs a single child step. The control handlers manage the loop /
    branch selection and call back into this callable per child.
    """
    if step.action == "for_each":
        if on_visit_child is None:
            raise ValueError("for_each requires the runner to pass on_visit_child")
        await control.run_for_each(page, step.params, ctx, _visit=on_visit_child)
        return
    if step.action == "if":
        if on_visit_child is None:
            raise ValueError("if requires the runner to pass on_visit_child")
        await control.run_if(
            page, step.params, ctx,
            _then=on_visit_child,
            _else=on_visit_child,
        )
        return

    handler = _HANDLERS.get(step.action)
    if handler is None:
        raise NotImplementedError(
            f"Step action {step.action!r} not implemented in P1a "
            f"(supported: {sorted(list(_HANDLERS) + ['for_each', 'if'])})"
        )

    async def _run_once():
        await handler(page, step.params, ctx)

    await with_retry(_run_once, step.retry)
