"""The MCP server: tools, resources, and prompts.

Built on the official Python MCP SDK (``mcp`` 2.3.0, spec 2026-07-28)
via ``MCPServer`` and exposed over Streamable HTTP by ``app/main.py``.

Honesty rules for this server:
- Tools read/write a real SQLite database. Nothing is faked.
- A missing note is reported as a plain error string, not invented data.
- The ``summarize-notes`` prompt only *asks* the calling model to
  summarise; the summary itself is produced by the model, not by us.
"""

import json

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app import settings
from app import store

TOOL_NAMES = ["add_numbers", "echo", "create_note", "list_notes", "search_notes"]
RESOURCE_URIS = ["notes://all", "notes://{id}"]
PROMPT_NAMES = ["summarize-notes"]

INSTRUCTIONS = (
    "A small notes server. Use add_numbers for arithmetic, echo to test "
    "the connection, and create_note / list_notes / search_notes to work "
    "with notes stored in SQLite. The notes://all resource lists every "
    "note; notes://{id} reads one note by id. The summarize-notes prompt "
    "asks you (the calling model) to summarise the notes — this server "
    "never writes summaries itself."
)

mcp_server = MCPServer(
    name=settings.MCP_SERVER_NAME,
    title="MCP Starter",
    description=(
        "Production-wired MCP server starter: FastAPI + SQLite notes, "
        "Streamable HTTP transport, optional bearer auth."
    ),
    instructions=INSTRUCTIONS,
    version=settings.MCP_SERVER_VERSION,
)

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


# ---------------------------------------------------------------- tools


@mcp_server.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@mcp_server.tool()
def echo(message: str) -> str:
    """Return the message unchanged (connectivity check)."""
    return message


@mcp_server.tool()
def create_note(title: str, body: str) -> dict:
    """Create a note in SQLite and return its id and title."""
    note = store.create_note(settings.DATABASE_PATH, title, body)
    return {"id": note["id"], "title": note["title"]}


@mcp_server.tool()
def list_notes(limit: int = 10) -> list[dict]:
    """List the most recent notes (default 10, newest first)."""
    return store.list_notes(settings.DATABASE_PATH, limit=limit)


@mcp_server.tool()
def search_notes(query: str) -> list[dict]:
    """Search notes by title or body (substring match)."""
    return store.search_notes(settings.DATABASE_PATH, query)


# ------------------------------------------------------------ resources


@mcp_server.resource("notes://all", mime_type="application/json")
def all_notes() -> str:
    """All notes as JSON."""
    notes = store.list_notes(settings.DATABASE_PATH, limit=1000)
    return json.dumps(notes)


@mcp_server.resource("notes://{id}", mime_type="application/json")
def note_by_id(id: str) -> str:
    """One note by id as JSON.

    A missing or non-numeric id is reported as a plain error string —
    no note is ever invented.
    """
    try:
        note_id = int(id)
    except ValueError:
        return json.dumps({"error": f"No note with id {id!r}: id must be an integer."})
    note = store.get_note(settings.DATABASE_PATH, note_id)
    if note is None:
        return json.dumps({"error": f"No note with id {note_id}."})
    return json.dumps(note)


# -------------------------------------------------------------- prompts


@mcp_server.prompt("summarize-notes")
def summarize_notes() -> str:
    """Ask the calling model to summarise all notes.

    This returns an instruction, not a summary: the summary is produced
    by the model that called this prompt, using the notes it reads via
    the list_notes tool or the notes://all resource.
    """
    return (
        "Summarise all of the user's notes. First read them with the "
        "list_notes tool (or the notes://all resource), then write a short "
        "summary: one line per note with its title and main point, plus "
        "any themes that appear across several notes. This summary is "
        "produced by you, the calling model — the server only stores the "
        "notes and does not summarise them itself."
    )
