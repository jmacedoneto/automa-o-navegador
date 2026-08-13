"""MCP server factory — wraps the tools as an MCP server."""
from app.mcp_server.tools import (
    create_automation,
    get_automation,
    get_run_status,
    list_automations,
    list_runs,
    plan_automation,
    run_automation_now,
    trigger_webhook,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore[assignment]


def build_server():
    if FastMCP is None:
        raise RuntimeError("mcp package not installed — run `pip install mcp==2.0.0`")
    mcp = FastMCP("navrunner")

    mcp.add_tool(
        list_automations,
        name="list_automations",
        description="List all automations registered in NavRunner. Returns id, name, description, is_active, created_at.",
    )
    mcp.add_tool(
        get_automation,
        name="get_automation",
        description="Fetch a single automation by id, including its steps and auth block.",
    )
    mcp.add_tool(
        list_runs,
        name="list_runs",
        description="List recent automation runs (most recent first).",
    )
    mcp.add_tool(
        get_run_status,
        name="get_run_status",
        description="Fetch a single run by id, including status, error_message, screenshot_urls, bindings.",
    )
    mcp.add_tool(
        run_automation_now,
        name="run_automation_now",
        description="Dispatch an automation immediately (Celery task). Returns task_id.",
    )
    mcp.add_tool(
        create_automation,
        name="create_automation",
        description="Persist a new automation with name + steps array. `auth` is a sibling dict (not a step).",
    )
    mcp.add_tool(
        plan_automation,
        name="plan_automation",
        description="Ask GPT to convert a natural-language description into a NavRunner DSL draft.",
    )
    mcp.add_tool(
        trigger_webhook,
        name="trigger_webhook",
        description="Trigger the legacy webhook path. Returns execution_id and task_id.",
    )

    return mcp
