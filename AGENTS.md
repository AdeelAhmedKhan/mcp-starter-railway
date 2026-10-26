# AGENTS.md — working in this repo

Read this before changing anything. The user of this repo is a developer
deploying an MCP server starter on Railway; keep it runnable, minimal,
and honest.

## Stack (pinned — do not bump majors casually)

Python 3.12 + FastAPI 0.162.0 + Uvicorn 0.54.0 + MCP SDK 2.3.0
(spec 2026-07-28) + Pydantic 2.14.1 + python-dotenv 1.2.4 + SQLite
(stdlib). Versions verified on PyPI 2026-10-26; see README
"Stack & versions".

## The one rule that matters

**Never fake a capability.** No auth token means the MCP endpoint is
open and health reports `auth: "disabled"` — the landing page says so
plainly. A missing note returns an error string, never invented data.
The `summarize-notes` prompt only asks the calling model to summarise;
the summary is produced by the model, not by this server. A database
that cannot be opened raises a clear error and health reports
`db: "error"` — nothing in a response is invented.

## Layout

- `app/main.py` — FastAPI app, routes, landing page, bearer-auth
  middleware for `/mcp`. Loads `.env` first (via `app/__init__.py`),
  so `cp .env.example .env` works out of the box. The app boots and
  `/api/health` answers even when the SQLite file cannot be opened.
- `app/settings.py` — env vars only. `config_status()` is the honest
  capability report. `MCP_PROTOCOL_VERSION` is the spec version
  (2026-07-28), not a library version.
- `app/store.py` — stdlib `sqlite3` notes store. `init_db` is
  idempotent (create table + seed 3 demo notes only when empty).
  Search escapes LIKE wildcards in the user query.
- `app/server.py` — the `MCPServer`: 5 tools, 2 resources, 1 prompt.
  Tool/resource/prompt name lists live here as constants and are what
  `/api/health` reports. `mcp_app` is built here with explicit
  transport security from `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`
  (localhost defaults; Railway needs the exact public domain —
  `*.up.railway.app` does not work). Its session manager lifespan is
  entered by `main.py`'s lifespan — Starlette does not propagate
  lifespan to mounted sub-apps, and without it `/mcp` 500s.
- `scripts/seed.py` — idempotent demo-note seed; safe to re-run.
- `tests/test_api.py` — pytest against the REAL server (TestClient
  for HTTP; a live uvicorn subprocess + official MCP client for the
  MCP flow). No mocks.

## Commands

```bash
cp .env.example .env   # optional; defaults work with no .env at all
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/seed.py   # optional; startup seeds automatically
uvicorn app.main:app --reload --port 8000
python -m pytest       # live-server MCP flow included
python -m compileall app scripts   # syntax check after changes
```

## Do / Don't

- DO run `python -m compileall app scripts` + `python -m pytest`
  after changes and fix real errors. Do not claim a test passes if it
  did not. Do not claim a flow works from a status code alone — check
  the response body.
- DO keep `requirements.txt` as the single source of truth for pinned
  versions. If you bump one, verify it on PyPI first and update the
  README version table in the same change.
- DO keep secrets out of the repo. `.env.example` holds placeholders
  only. The only secret is `MCP_AUTH_TOKEN`, and it has no default
  value in code — empty means open, and the app says so.
- DON'T add a feature that needs a new env var without documenting it
  in `.env.example` and README.
- DON'T invent versions. Check `pypi.org/pypi/<pkg>/json` before
  pinning, and check the MCP spec repo before changing
  `MCP_PROTOCOL_VERSION`.
- DON'T generate fake notes, fake summaries, or fake auth. An empty
  database and a `disabled` auth status are honest states.
- DON'T push, deploy, or publish from here. This repo is prepared
  locally; pushing and Railway template creation are separate,
  human-approved steps.
```

## Railway notes

- No extra services needed: the store is a SQLite file. Without a
  Railway Volume mounted at `data/`, the file is ephemeral — notes are
  lost on redeploy. Say so in the README and in health, never hide it.
- No `preDeployCommand` in `railway.toml`: SQLite init happens on
  startup, not before deploy.
