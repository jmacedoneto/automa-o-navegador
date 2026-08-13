"""MCP server wrapper for the NavRunner framework.

Exposes NavRunner as Model Context Protocol tools so any MCP client
(Claude Desktop, Cursor, OpenCode, etc.) can list/create/run automations.
"""
from app.mcp_server.server import build_server

__all__ = ["build_server"]
