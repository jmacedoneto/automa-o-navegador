"""Stdin/stdout entry point for the NavRunner MCP server.

Run it via:
    python -m backend.scripts.mcp_server_stdio

Or in a Claude Desktop config:
    {
      "mcpServers": {
        "navrunner": {
          "command": "python",
          "args": ["-m", "backend.scripts.mcp_server_stdio"],
          "cwd": "/root/navegador/automa-o-navegador/backend"
        }
      }
    }
"""
from app.mcp_server import build_server


def main() -> None:
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
