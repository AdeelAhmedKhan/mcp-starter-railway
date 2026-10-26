"""Tool, resource, and prompt registration for the MCP server.

Each module under ``app/tools/`` owns one group and exposes a
``register(server)`` function; :func:`register_all` wires them all
onto the ``MCPServer`` built in ``app/server.py``. The name lists
below are the single source of truth for what the server offers —
``/api/health`` and the landing page report them verbatim.
"""

from app.tools import demo, external, notes

TOOL_NAMES = [
    "add_numbers",
    "echo",
    "create_note",
    "list_notes",
    "search_notes",
    "fetch_json",
]
RESOURCE_URIS = ["notes://all", "notes://{id}"]
PROMPT_NAMES = ["summarize-notes"]


def register_all(server) -> None:
    """Register every tool, resource, and prompt on ``server``."""
    demo.register(server)
    notes.register(server)
    external.register(server)


__all__ = [
    "TOOL_NAMES",
    "RESOURCE_URIS",
    "PROMPT_NAMES",
    "register_all",
]
