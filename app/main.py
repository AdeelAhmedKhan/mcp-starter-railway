"""FastAPI app: mounts the MCP server on Streamable HTTP at /mcp.

- ``GET /`` — landing page documenting the server and how to connect.
- ``GET /api/health`` — always HTTP 200; the body says honestly whether
  the DB is up and whether auth is configured (``status`` is
  ``"degraded"`` when the DB is down).
- ``/mcp`` — the MCP endpoint (Streamable HTTP). If ``MCP_AUTH_TOKEN``
  is set, a bearer token is required; without it the endpoint is open
  and the landing page says so plainly.

The notes store (SQLite by default, Postgres when DATABASE_URL is
set) is initialised (create + seed if empty) on startup.
If that fails, the app still boots and ``/api/health`` reports
``db: "error"`` instead of crashing — a missing database is an honest
state, not a reason to refuse the healthcheck.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app import settings, store
from app.server import (
    PROMPT_NAMES,
    RESOURCE_URIS,
    TOOL_NAMES,
    mcp_app,
    mcp_server,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    active_store = store.get_store()
    try:
        seeded = active_store.init_db()
        logger.info(
            "%s store ready (seeded %d notes)",
            active_store.backend, seeded,
        )
    except store.StoreError as exc:
        # Boot anyway; /api/health reports db: "error" honestly.
        logger.warning("%s store unavailable at startup: %s", active_store.backend, exc)
    # The MCP session manager's lifespan. Starlette does not propagate
    # lifespan to mounted sub-apps, so it must be entered here —
    # without it, /mcp 500s with "Task group is not initialized".
    # run() can only be called once per manager instance; there is one
    # lifespan per process, so that is fine.
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title=settings.MCP_SERVER_NAME,
    version=settings.MCP_SERVER_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def bearer_auth_middleware(request: Request, call_next):
    """Optional bearer auth on /mcp only.

    ``/`` and ``/api/health`` stay public so the server can be checked
    without a token. When no token is configured, /mcp is open.
    """
    if request.url.path.startswith("/mcp") and settings.auth_enabled():
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {settings.MCP_AUTH_TOKEN}":
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "detail": "This MCP endpoint requires "
                    "Authorization: Bearer <MCP_AUTH_TOKEN>.",
                },
            )
    return await call_next(request)


@app.get("/api/health")
def health() -> JSONResponse:
    active_store = store.get_store()
    db_ok = active_store.db_ok()
    status = settings.config_status()
    return JSONResponse(
        content={
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
            "backend": active_store.backend,
            "mcp": {
                "server": settings.MCP_SERVER_NAME,
                "protocol_version": settings.MCP_PROTOCOL_VERSION,
                "tools": TOOL_NAMES,
                "resources": RESOURCE_URIS,
                "prompts": PROMPT_NAMES,
            },
            "auth": "enabled" if settings.auth_enabled() else "disabled",
            "auth_note": status["auth_note"],
        }
    )


def _landing_html(base_url: str) -> str:
    mcp_url = f"{base_url}/mcp"
    backend = store.get_store().backend
    storage_line = (
        "backed by a real Postgres notes store (DATABASE_URL is set)."
        if backend == "postgres"
        else "backed by a real SQLite notes store."
    )
    auth_warning = (
        '<p><strong>Auth is enabled.</strong> Clients must send '
        '<code>Authorization: Bearer &lt;MCP_AUTH_TOKEN&gt;</code>.</p>'
        if settings.auth_enabled()
        else '<p><strong>No auth configured — set MCP_AUTH_TOKEN before '
        "exposing publicly.</strong> Anyone with this URL can currently "
        "call the MCP tools and read/write notes.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{settings.MCP_SERVER_NAME} — MCP Starter</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.5}}code,pre{{background:#f4f4f4;padding:.15em .4em;border-radius:4px}}pre{{padding:1em;overflow:auto}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.4em .8em;text-align:left}}</style>
</head>
<body>
<h1>{settings.MCP_SERVER_NAME} — MCP Starter</h1>
<p>A production-wired MCP server (spec <strong>{settings.MCP_PROTOCOL_VERSION}</strong>,
Python SDK 2.3.0) over Streamable HTTP, {storage_line}
Endpoint: <code>{mcp_url}</code></p>
{auth_warning}
<h2>Tools</h2>
<table><tr><th>Tool</th><th>What it does</th></tr>
<tr><td><code>add_numbers(a, b)</code></td><td>Add two numbers.</td></tr>
<tr><td><code>echo(message)</code></td><td>Return the message unchanged.</td></tr>
<tr><td><code>create_note(title, body)</code></td><td>Create a note in the notes store.</td></tr>
<tr><td><code>list_notes(limit=10)</code></td><td>List recent notes, newest first.</td></tr>
<tr><td><code>search_notes(query)</code></td><td>Substring search over title/body.</td></tr>
<tr><td><code>fetch_json(url)</code></td><td>Fetch JSON from an http(s) URL and return the parsed value (errors returned as plain text).</td></tr>
</table>
<h2>Resources</h2>
<table><tr><th>URI</th><th>What it returns</th></tr>
<tr><td><code>notes://all</code></td><td>All notes as JSON.</td></tr>
<tr><td><code>notes://{{id}}</code></td><td>One note by id as JSON (error text if missing).</td></tr>
</table>
<h2>Prompts</h2>
<table><tr><th>Prompt</th><th>What it does</th></tr>
<tr><td><code>summarize-notes</code></td><td>Asks the calling model to summarise all notes. The summary is produced by the model, not by this server.</td></tr>
</table>
<h2>Connect</h2>
<p>Point any MCP client at the remote endpoint <code>{mcp_url}</code> using
Streamable HTTP transport.</p>
<h3>Claude Desktop / Cursor (remote MCP server)</h3>
<pre>{{
  "mcpServers": {{
    "{settings.MCP_SERVER_NAME}": {{
      "url": "{mcp_url}"
    }}
  }}
}}</pre>
<h3>Claude Code</h3>
<pre>claude mcp add --transport http {settings.MCP_SERVER_NAME} {mcp_url}</pre>
<p>Health: <a href="/api/health"><code>/api/health</code></a> — returns the
live DB and auth status. Source: the <code>mcp-starter</code> template.</p>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    base_url = str(request.base_url).rstrip("/")
    return HTMLResponse(content=_landing_html(base_url))


# Mount the MCP Streamable HTTP app last so / and /api/health keep
# their own routes. The mount is at "/" (not "/mcp"): a Mount at
# "/mcp" 307-redirects POST /mcp to /mcp/ and MCP clients do not
# follow it, and the default streamable_http_path "/mcp" inside a
# "/mcp" mount would double up to /mcp/mcp. Mounted at "/" with the
# default path, the endpoint is exactly /mcp. (app/server.py builds
# the app; its lifespan is entered by the lifespan handler above.)
app.mount("/", mcp_app)
