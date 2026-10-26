"""The MCP server: builds the ``MCPServer`` and its Streamable HTTP app.

Tools, resources, and prompts live in ``app/tools/`` (demo, notes,
external) and are registered here via ``register_all``. The name lists
are re-exported so ``/api/health`` and the landing page keep
reporting the live lists.

Honesty rules for this server:
- Tools read/write a real notes store (SQLite by default, Postgres
  when ``DATABASE_URL`` is set). Nothing is faked.
- A missing note is reported as a plain error string, not invented data.
- ``fetch_json`` returns parsed JSON or a plain error string — never
  invented data.
- The ``summarize-notes`` prompt only *asks* the calling model to
  summarise; the summary itself is produced by the model, not by us.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app import settings
from app.tools import PROMPT_NAMES, RESOURCE_URIS, TOOL_NAMES, register_all

__all__ = ["TOOL_NAMES", "RESOURCE_URIS", "PROMPT_NAMES", "mcp_server", "mcp_app"]

INSTRUCTIONS = (
    "A small notes server with a JSON-fetch helper. Use add_numbers for "
    "arithmetic, echo to test the connection, and create_note / "
    "list_notes / search_notes to work with notes stored in SQLite "
    "(or Postgres when DATABASE_URL is set). Use fetch_json to fetch "
    "and parse JSON from an http(s) URL. The notes://all resource "
    "lists every note; notes://{id} reads one note by id. The "
    "summarize-notes prompt asks you (the calling model) to summarise "
    "the notes — this server never writes summaries itself."
)

mcp_server = MCPServer(
    name=settings.MCP_SERVER_NAME,
    title="MCP Starter",
    description=(
        "Production-wired MCP server starter: FastAPI + swappable "
        "notes store (SQLite or Postgres), Streamable HTTP transport, "
        "optional bearer auth, plus a fetch_json helper."
    ),
    instructions=INSTRUCTIONS,
    version=settings.MCP_SERVER_VERSION,
)

register_all(mcp_server)

# The Streamable HTTP Starlette app, built once and mounted by
# app/main.py. Its lifespan (the session manager) is entered by
# main.py's lifespan handler — Starlette does not propagate lifespan
# to mounted sub-apps, so without that the endpoint 500s.
#
# DNS rebinding protection stays ENABLED, with hosts/origins from
# MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS (defaults: localhost only).
# On Railway you MUST set them to your exact public domain — the SDK
# rejects any other Host with 421. Wildcards only cover ports
# ("host:*"), NOT subdomains, so "*.up.railway.app" does not work.
mcp_app = mcp_server.streamable_http_app(
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.MCP_ALLOWED_HOSTS,
        allowed_origins=settings.MCP_ALLOWED_ORIGINS,
    )
)
