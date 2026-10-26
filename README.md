# MCP Starter — Deploy on Railway

A production-wired MCP server starter: **Python MCP SDK 2.3.0** (spec
**2026-07-28**) + **FastAPI** + **SQLite**, exposed over **Streamable
HTTP** at `/mcp`. One-click deploy on Railway; nothing in here is a
demo stub — the tools read and write a real SQLite database, the
resources serve real data, and anything not configured tells you so
instead of crashing.

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
| SQLite | stdlib | Notes store; no extra service needed |
| httpx | 0.28.1 | Dev/test only |

Sources: [PyPI `mcp` 2.3.0](https://pypi.org/project/mcp/2.3.0/),
[PyPI `python-dotenv` 1.2.4](https://pypi.org/project/python-dotenv/1.2.4/),
MCP spec repo `schema/2026-07-28/`.

## What you get

| Kind | Name | What it does |
| --- | --- | --- |
| Tool | `add_numbers(a, b)` | Add two numbers. |
| Tool | `echo(message)` | Return the message unchanged (connectivity check). |
| Tool | `create_note(title, body)` | Create a note in SQLite; returns id + title. |
| Tool | `list_notes(limit=10)` | List recent notes, newest first. |
| Tool | `search_notes(query)` | Substring search over title/body (LIKE wildcards escaped). |
| Resource | `notes://all` | All notes as JSON. |
| Resource | `notes://{id}` | One note by id as JSON; honest error text if missing. |
| Prompt | `summarize-notes` | Asks the calling model to summarise all notes. The summary is produced by the model, not by this server. |

Plus:

- **Healthcheck** — `GET /api/health` returns HTTP 200 with the live
  DB status, the MCP server/protocol version, the tool/resource/prompt
  lists, and the auth status; Railway uses it as the deploy
  healthcheck (`railway.toml`). When the DB is down it reports
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

## Deploy on Railway (exact steps)

1. Deploy this repo from GitHub (or from the Railway marketplace
   template once published).
2. No extra services are needed — the notes store is a SQLite file.
3. Optional, recommended: add a **Volume** mounted at `/app/data` so
   the SQLite file survives redeploys. Without it, notes are lost on
   redeploy (the app says so in `/api/health`).
4. Optional, recommended before exposing publicly: set
   `MCP_AUTH_TOKEN` to a long random token as a service variable.
5. **Required for the public domain to work:** set
   `MCP_ALLOWED_HOSTS` to your exact Railway domain (e.g.
   `myapp.up.railway.app`) and `MCP_ALLOWED_ORIGINS` to its https
   origin (e.g. `https://myapp.up.railway.app`). The MCP SDK's DNS
   rebinding protection rejects any Host not on the list (HTTP 421),
   and wildcards only cover ports — `*.up.railway.app` does NOT work.
   The defaults are localhost-only, for local dev.
6. Generate a public domain (Networking → Generate Domain).
7. Deploy. Railway healthchecks `GET /api/health` — it must answer 200.

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
add one (small; grows with the SQLite file). There is no database
service to pay for and no LLM cost — this server calls no model
itself; the calling client's model does the summarising. Verify
against [Railway's pricing page](https://railway.com/pricing) before
promising a number to anyone; Railway's prices change.

## How to back up

- **Notes** — the whole store is one SQLite file (`data/notes.db` by
  default, or `DATABASE_PATH`). Copy it off the server on a schedule
  you control: `cp data/notes.db backup-$(date +%F).db` and store it
  somewhere other than Railway. Test a restore at least once — an
  untested backup is not a backup.
- **Code + config** — the repo is the backup for code. Service
  variables are not in the repo by design; keep a copy of the variable
  *names* (not values) in `.env.example` and the values in Railway.

## Hardening before real users

- **Set `MCP_AUTH_TOKEN`** before exposing the endpoint publicly —
  without it anyone with the URL can call the tools and read/write
  notes. The landing page and `/api/health` warn you while it is unset.
- **Set `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`** to your exact
  Railway domain (see Deploy step 5) — otherwise the SDK's DNS
  rebinding protection rejects the public host with HTTP 421 and no
  MCP client can connect at all.
- **Add a Volume** (see Deploy step 3) or your notes vanish on
  redeploy.
- Add rate limiting on `/mcp` if the endpoint is public.
- Do not store sensitive user input in notes without a policy — notes
  are stored in plain text in SQLite.
- Rotate the token if it ever leaks: change the Railway variable and
  redeploy.

## Project layout

```
app/
  __init__.py       loads .env at package import
  main.py           FastAPI app + routes + landing page + bearer auth
  settings.py       env vars + honest config_status()
  store.py          stdlib sqlite3 notes store (init/seed/CRUD/search)
  server.py         MCPServer: 5 tools, 2 resources, 1 prompt
scripts/
  seed.py           idempotent demo-note seed
tests/
  test_api.py       pytest vs the REAL server (live uvicorn + MCP client)
railway.toml        build/start/healthcheck config (no pre-deploy step)
requirements.txt    pinned runtime dependencies (source of truth)
```

See `AGENTS.md` for the rules AI agents should follow in this repo.

## License

MIT — see `LICENSE`.
