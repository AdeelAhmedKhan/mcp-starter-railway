# MCP Starter — Deploy on Railway

A production-wired MCP server starter: **Python MCP SDK 2.3.0** (spec
**2026-07-28**) + **FastAPI** + a swappable notes store (**SQLite** by
default, **Postgres** optional), exposed over **Streamable HTTP** at
`/mcp`. One-click deploy on Railway; nothing in here is a demo stub —
the tools read and write a real notes store, the resources serve real
data, and anything not configured tells you so instead of crashing.

**Why this template exists:** Railway already has MCP gateway and
single-purpose templates (an MCP proxy gateway, a Postgres MCP server,
and others) — but no generic Python "build your own MCP server"
starter. Railway's own guide for building one is Node/Express. This
is the Python equivalent: the official MCP SDK, FastAPI, Streamable
HTTP, and a from-scratch server you extend with your own tools.

## Stack & versions (pinned, verified 2026-10-26)

| Piece | Version | Notes |
| --- | --- | --- |
| Python | 3.12 | `requires-python = ">=3.11,<3.14"` |
| MCP SDK (`mcp`) | 2.3.0 | PyPI, MIT, requires Python ≥ 3.10; `MCPServer` + `streamable_http_app()` |
| MCP spec | 2026-07-28 | Current spec version; `LATEST_PROTOCOL_VERSION` in the SDK |
| FastAPI | 0.162.0 | |

Note on versions: SDK 2.3.0 keeps two version tracks. `2026-07-28`
is the current spec version (the SDK's `MODERN_PROTOCOL_VERSIONS`),
negotiated via the newer `discover` mechanism. The classic
`initialize` handshake negotiates only legacy versions (latest
`2025-11-25`) — so a plain `ClientSession.initialize()` reports
`protocolVersion: "2025-11-25"` in the live session. That is the
handshake version, not the spec version: `/api/health` reports the
implemented spec version, `2026-07-28`.
| Uvicorn | 0.54.0 | Production server |
| Pydantic | 2.14.1 | Request validation |
| python-dotenv | 1.2.4 | Loads `.env` at import (PyPI, verified 2026-10-26) |
| SQLite | stdlib | Default notes store; no extra service needed |
| Postgres (`psycopg[binary]`) | 3.3.6 | Optional notes store; only used when `DATABASE_URL` is set |
| httpx | 0.28.1 | Runtime dependency: `fetch_json` (10 s timeout, 1 MB limit) |

Sources: [PyPI `mcp` 2.3.0](https://pypi.org/project/mcp/2.3.0/),
[PyPI `python-dotenv` 1.2.4](https://pypi.org/project/python-dotenv/1.2.4/),
MCP spec repo `schema/2026-07-28/`.

## What you get

| Kind | Name | What it does |
| --- | --- | --- |
| Tool | `add_numbers(a, b)` | Add two numbers. |
| Tool | `echo(message)` | Return the message unchanged (connectivity check). |
| Tool | `create_note(title, body)` | Create a note in the notes store; returns id + title. |
| Tool | `list_notes(limit=10)` | List recent notes, newest first. |
| Tool | `search_notes(query)` | Substring search over title/body (LIKE wildcards escaped). |
| Tool | `fetch_json(url)` | Fetch JSON from an http(s) URL; errors returned as plain text, never invented data. |
| Resource | `notes://all` | All notes as JSON. |
| Resource | `notes://{id}` | One note by id as JSON; honest error text if missing. |
| Prompt | `summarize-notes` | Asks the calling model to summarise all notes. The summary is produced by the model, not by this server. |

Plus:

- **Healthcheck** — `GET /api/health` returns HTTP 200 with the live
  DB status, the active store backend (`sqlite` or `postgres`), the
  MCP server/protocol version, the tool/resource/prompt lists, and the
  auth status; Railway uses it as the deploy healthcheck
  (`railway.toml`). When the DB is down it reports
  `status: "degraded"` instead of crashing.
- **Landing page** — `GET /` documents the server, its tools,
  resources and prompts, and shows the exact config snippet to
  connect. It says plainly when no auth is configured.
- **Optional bearer auth** — set `MCP_AUTH_TOKEN` and `/mcp` requires
  `Authorization: Bearer <token>` (401 otherwise). `/` and
  `/api/health` stay public either way. Without a token the endpoint
  is open and the app says so — set the token before exposing it
  publicly.
- **DNS rebinding protection is on** — the MCP SDK allowlists Host /
  Origin headers via `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`
  (defaults: localhost only). On Railway you must set them to your
  exact public domain, or the public host is rejected (HTTP 421);
  `*.up.railway.app` does not work — the SDK has no subdomain
  wildcards, only port wildcards (`host:*`).
- **Idempotent seeding** — 3 demo notes are created on first startup
  (or via `python scripts/seed.py`); re-running never duplicates them.

## Make it yours

This template is a starting point, not a finished server. Everything
below is a copy-paste change — no framework knowledge needed beyond
the snippet shown.

### Add a tool

Tools live in `app/tools/`, one group per file. Each file exposes a
`register(server)` function, and `app/tools/__init__.py` wires them
all up in `register_all()`. To add a tool:

1. Create a file, e.g. `app/tools/my_tools.py`:

```python
# app/tools/my_tools.py
def register(server) -> None:
    @server.tool()
    def shout(text: str) -> str:
        """Return the text in upper case."""
        return text.upper()
```

2. Register it in `app/tools/__init__.py` — add the import and one
   line in `register_all()`:

```python
from app.tools import demo, external, my_tools, notes

def register_all(server) -> None:
    demo.register(server)
    notes.register(server)
    external.register(server)
    my_tools.register(server)
```

3. Add the tool's name to the `TOOL_NAMES` list in the same file:

```python
TOOL_NAMES = [
    "add_numbers",
    "echo",
    "create_note",
    "list_notes",
    "search_notes",
    "fetch_json",
    "shout",
]
```

That's it. Restart the server and the tool appears to every MCP
client automatically (clients discover tools via `tools/list`).
`/api/health` and the landing page read `TOOL_NAMES`, which is why
step 3 matters — without it the tool works but is not listed there.
The function's docstring becomes the tool description clients see,
and its type hints become the input schema, so write both plainly.
(If the function already exists elsewhere, you can register it
without a decorator instead: `server.tool()(my_function)` — that is
how `fetch_json` is registered in `app/tools/external.py`.)

### Add a resource

Resources are read-only URIs, registered the same way — a URI pattern
plus a `mime_type`. Add this inside a `register(server)` function
(following the same pattern as `app/tools/notes.py`):

```python
@server.resource("greeting://{name}", mime_type="text/plain")
def greeting(name: str) -> str:
    """Greet one person by name."""
    return f"Hello, {name}!"
```

The `{name}` part of the URI becomes the function's argument. Add
the URI to `RESOURCE_URIS` in `app/tools/__init__.py` so
`/api/health` and the landing page list it. A missing or invalid
value should return a plain error string, never invented data — see
`note_by_id` in `app/tools/notes.py` for the pattern.

### Add a prompt

A prompt returns an instruction string for the calling model — the
server never produces the answer itself. Same pattern again:

```python
@server.prompt("my-prompt")
def my_prompt() -> str:
    """Ask the calling model to do one thing with the notes."""
    return (
        "Read all notes with the list_notes tool, then write a "
        "one-paragraph summary of the most important one."
    )
```

Add `"my-prompt"` to `PROMPT_NAMES` in `app/tools/__init__.py` so
`/api/health` and the landing page list it.

### Wrap your own API with `fetch_json`

`fetch_json(url)` in `app/tools/external.py` is the pattern for
wrapping an external JSON API as a tool: fetch, parse, return the
data — or return a plain error string. Copy the file's pattern and
change the URL and the parsing:

```python
# app/tools/weather.py
from app.tools.external import fetch_json

def fetch_weather(city: str) -> dict:
    """Current weather for a city, from a JSON API."""
    data = fetch_json(f"https://api.example.com/weather?city={city}")
    if isinstance(data, str):
        # fetch_json returns an error STRING on failure, never
        # invented data — surface it, don't invent a fallback.
        return {"error": data}
    return {"temp_c": data["temp_c"], "condition": data["condition"]}

def register(server) -> None:
    server.tool()(fetch_weather)
```

Then register `weather` in `app/tools/__init__.py` exactly as in
"Add a tool" above. The honest-error rules are built into
`fetch_json` and apply to your wrapper for free:

- **Timeout** — 10 seconds (`TIMEOUT_SECONDS` in
  `app/tools/external.py`); a slow API returns
  `"Error: request to <url> timed out after 10 seconds."`
- **Non-200 status** — returns `"Error: <url> returned HTTP <status>."`
- **Invalid JSON** — returns `"Error: response from <url> is not valid JSON: ..."`.
- **Oversized response** — over 1 MB (`MAX_RESPONSE_BYTES`) returns
  `"Error: response from <url> exceeds the 1 MB limit."`
- **Non-http(s) URL** — `file://` and friends are rejected outright.
- **Redirects** — followed, up to 5 (`MAX_REDIRECTS`).

If the API you wrap needs an API key, keep the key in an env var
(never in code) and add it to `.env.example` as a placeholder — the
same rule as `MCP_AUTH_TOKEN`.

### Swap the store: SQLite by default, Postgres when you need it

Notes live behind a small interface, the `NoteStore` Protocol in
`app/store_base.py`: `backend`, `init_db()`, `db_ok()`,
`create_note(title, body)`, `list_notes(limit=10)`,
`search_notes(query)`, `get_note(note_id)`. No tool code touches
SQLite or Postgres directly — tools call `get_store()` and the
backend is invisible to them.

- **Default: SQLite.** Leave `DATABASE_URL` empty and notes live in
  the file at `DATABASE_PATH` (default `data/notes.db`). No extra
  service needed.
- **Postgres:** set `DATABASE_URL` to a Postgres connection string
  (e.g. `postgresql://user:password@host:5432/dbname`) and
  `get_store()` in `app/store.py` returns a `PostgresStore`
  (`app/store_postgres.py`) instead. Same notes table, same
  idempotent seeding, same LIKE-wildcard escaping; `created_at` is
  converted to an ISO-8601 string so responses match the SQLite
  shape. `/api/health` reports `"backend": "postgres"` so you can
  confirm which store is live.

**On Railway:** add a Postgres service to the project, then on the
app service set `DATABASE_URL` as a reference variable to the
Postgres service's connection string:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

(Railway fills in the real value at deploy time; the name before the
dot is the Postgres service's name — change it if yours is named
differently.) No Volume is needed for Postgres — notes persist as
long as the database does — but you still need `MCP_ALLOWED_HOSTS` /
`MCP_ALLOWED_ORIGINS` set to your public domain (see Deploy step 6).

> **Honest note — Postgres is implemented but not yet live-tested.**
> The Postgres store (`app/store_postgres.py`) is fully implemented
> and its failure paths are in the code (an unreachable database
> raises a clear `StoreError` and `/api/health` reports
> `db: "error"` instead of crashing), but it has **not yet been
> tested against a live Postgres server** — no live round-trip test
> (create/list/search a note through Postgres) has been run. If you
> switch to Postgres, run `python scripts/seed.py` and
> `curl localhost:8000/api/health` first and check
> `"backend": "postgres"` and `"db": "ok"` before relying on it.
> The tests in `tests/test_api.py` run against SQLite only.

**Add a third backend:** implement the `NoteStore` Protocol
(`app/store_base.py`) in a new file — the six methods above, plus a
`backend` string — then register it in `get_store()` in
`app/store.py` (the one place that decides which backend is active).
Keep the new backend's failure mode honest: raise `StoreError` with
a clear message when it cannot be opened or queried, and make
`db_ok()` return `False` instead of raising.

## Run it locally

```bash
cp .env.example .env   # optional; defaults work with no .env at all
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/seed.py   # optional; startup seeds automatically
uvicorn app.main:app --reload --port 8000
```

Try it:

```bash
curl localhost:8000/api/health
curl localhost:8000/   # landing page with connect instructions
```

Then connect any MCP client to `http://localhost:8000/mcp` (see
"Connect" below) and call `add_numbers(2, 3)` or `list_notes`.

To try the Postgres store locally, set
`DATABASE_URL=postgresql://user:password@localhost:5432/dbname` in
`.env` — see "Swap the store" above, including the note that the
Postgres path is implemented but its live round-trip test is still
pending.

## Deploy on Railway (exact steps)

1. Deploy this repo from GitHub (or from the Railway marketplace
   template once published).
2. No extra services are needed by default — the notes store is a
   SQLite file.
3. Optional: use **Postgres** instead of SQLite. Add a Postgres
   service to the project, then on the app service set
   `DATABASE_URL=${{Postgres.DATABASE_URL}}` (a reference variable —
   Railway fills in the real connection string). Skip the Volume in
   step 4 if you do this: notes persist in Postgres, not in a file.
   See "Swap the store" above — and note the Postgres path is
   implemented but its live round-trip test is still pending.
4. Optional, recommended with SQLite: add a **Volume** mounted at
   `/app/data` so the SQLite file survives redeploys. Without it,
   notes are lost on redeploy (the app says so in `/api/health`).
   Not needed if you use Postgres (step 3).
5. Optional, recommended before exposing publicly: set
   `MCP_AUTH_TOKEN` to a long random token as a service variable.
6. **Required for the public domain to work:** set
   `MCP_ALLOWED_HOSTS` to your exact Railway domain (e.g.
   `myapp.up.railway.app`) and `MCP_ALLOWED_ORIGINS` to its https
   origin (e.g. `https://myapp.up.railway.app`). The MCP SDK's DNS
   rebinding protection rejects any Host not on the list (HTTP 421),
   and wildcards only cover ports — `*.up.railway.app` does NOT work.
   The defaults are localhost-only, for local dev.
7. Generate a public domain (Networking → Generate Domain).
8. Deploy. Railway healthchecks `GET /api/health` — it must answer 200.

## Connect from Claude Desktop / Cursor / Claude Code

All three use the remote endpoint `<your-base-url>/mcp` over
Streamable HTTP. Replace `https://<your-domain>` with your Railway
domain (or `http://localhost:8000` locally).

**Claude Desktop / Cursor** — add a remote MCP server (in
`claude_desktop_config.json` / Cursor settings):

```json
{
  "mcpServers": {
    "mcp-starter": {
      "url": "https://<your-domain>/mcp"
    }
  }
}
```

If you set `MCP_AUTH_TOKEN`, add the header (Cursor supports
`headers`; Claude Desktop remote servers accept a `headers` block in
newer versions):

```json
{
  "mcpServers": {
    "mcp-starter": {
      "url": "https://<your-domain>/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_AUTH_TOKEN>"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add --transport http mcp-starter https://<your-domain>/mcp
# with auth:
claude mcp add --transport http mcp-starter https://<your-domain>/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

## What it costs

Railway charges for what the service actually uses — there is no fixed
price for this template. A realistic small deployment is a single app
service (1 vCPU, ~512 MB), roughly **~$5–10/mo**, plus a Volume if you
add one (small; grows with the SQLite file). With the default SQLite
store there is no database service to pay for; if you add a Postgres
service (see Deploy step 3), Railway charges for that too. There is no
LLM cost — this server calls no model itself; the calling client's
model does the summarising. Verify against [Railway's pricing
page](https://railway.com/pricing) before promising a number to
anyone; Railway's prices change.

## How to back up

- **Notes (SQLite, the default)** — the whole store is one SQLite
  file (`data/notes.db` by default, or `DATABASE_PATH`). Copy it off
  the server on a schedule you control:
  `cp data/notes.db backup-$(date +%F).db` and store it somewhere
  other than Railway. Test a restore at least once — an untested
  backup is not a backup.
- **Notes (Postgres, when `DATABASE_URL` is set)** — back up the
  database, not a file: `pg_dump "$DATABASE_URL" > backup-$(date
  +%F).sql` on a schedule you control, stored somewhere other than
  Railway. Railway's own Postgres backups (if enabled on the service)
  also cover this. Same rule: test a restore at least once.
- **Code + config** — the repo is the backup for code. Service
  variables are not in the repo by design; keep a copy of the variable
  *names* (not values) in `.env.example` and the values in Railway.

## Hardening before real users

- **Set `MCP_AUTH_TOKEN`** before exposing the endpoint publicly —
  without it anyone with the URL can call the tools and read/write
  notes. The landing page and `/api/health` warn you while it is unset.
- **Set `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`** to your exact
  Railway domain (see Deploy step 6) — otherwise the SDK's DNS
  rebinding protection rejects the public host with HTTP 421 and no
  MCP client can connect at all.
- **Add a Volume** (see Deploy step 4) if you use the default SQLite
  store, or your notes vanish on redeploy. Not needed with Postgres
  (Deploy step 3).
- Add rate limiting on `/mcp` if the endpoint is public.
- Do not store sensitive user input in notes without a policy — notes
  are stored in plain text in the notes store (SQLite file or
  Postgres table).
- Rotate the token if it ever leaks: change the Railway variable and
  redeploy.

## Project layout

```
app/
  __init__.py       loads .env at package import
  main.py           FastAPI app + routes + landing page + bearer auth
  settings.py       env vars + honest config_status()
  store.py          backend selection: get_store() (+ SQLite compat shim)
  store_base.py     NoteStore Protocol + StoreError + demo notes + LIKE escaping
  store_sqlite.py   SQLite notes store (default backend)
  store_postgres.py Postgres notes store (used when DATABASE_URL is set)
  server.py         MCPServer: thin — builds the server, calls register_all()
  tools/
    __init__.py     register_all() + TOOL_NAMES / RESOURCE_URIS / PROMPT_NAMES
    demo.py         add_numbers, echo
    notes.py        create_note, list_notes, search_notes + resources + prompt
    external.py     fetch_json (httpx, 10 s timeout, 1 MB limit)
scripts/
  seed.py           idempotent demo-note seed (uses the active store)
tests/
  test_api.py       pytest vs the REAL server (live uvicorn + MCP client)
railway.toml        build/start/healthcheck config (no pre-deploy step)
requirements.txt    pinned runtime dependencies (source of truth)
```

See `AGENTS.md` for the rules AI agents should follow in this repo.

## License

MIT — see `LICENSE`.
