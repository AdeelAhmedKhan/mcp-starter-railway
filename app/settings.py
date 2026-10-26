"""Environment-only settings.

Every value comes from the environment (or ``.env`` via ``app/__init__``).
There are no secrets with defaults here: ``MCP_AUTH_TOKEN`` is empty by
default, which means the server is OPEN — ``config_status()`` and
``/api/health`` say so plainly.
"""

import os
from pathlib import Path

# MCP protocol version this starter implements. The spec is versioned by
# date; 2026-07-28 is the current version per the MCP spec repo
# (schema/2026-07-28/) and the Python SDK's LATEST_PROTOCOL_VERSION.
# Verified 2026-10-26. Do not bump without checking the spec repo.
MCP_PROTOCOL_VERSION = "2026-07-28"


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


MCP_SERVER_NAME: str = _env("MCP_SERVER_NAME", "mcp-starter")
MCP_SERVER_VERSION: str = _env("MCP_SERVER_VERSION", "0.1.0")
DATABASE_PATH: str = _env("DATABASE_PATH", "data/notes.db")
MCP_AUTH_TOKEN: str = os.environ.get("MCP_AUTH_TOKEN", "")
PORT: int = int(_env("PORT", "8000"))

# --- MCP transport security (DNS rebinding protection) ---
# The SDK rejects requests whose Host/Origin is not allowlisted. The
# defaults are the SDK's localhost sets. On Railway you MUST set these
# to your EXACT public domain (e.g. myapp.up.railway.app) — wildcards
# only cover ports ("host:*"), NOT subdomains, so "*.up.railway.app"
# does NOT work. Comma-separated.
MCP_ALLOWED_HOSTS: list[str] = [
    h.strip()
    for h in _env(
        "MCP_ALLOWED_HOSTS", "127.0.0.1:*,localhost:*,[::1]:*"
    ).split(",")
    if h.strip()
]
MCP_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in _env(
        "MCP_ALLOWED_ORIGINS",
        "http://127.0.0.1:*,http://localhost:*,http://[::1]:*",
    ).split(",")
    if o.strip()
]


def auth_enabled() -> bool:
    """True only when a bearer token is configured."""
    return bool(MCP_AUTH_TOKEN)


def config_status() -> dict:
    """Honest capability report — no capability is ever faked."""
    return {
        "server": MCP_SERVER_NAME,
        "version": MCP_SERVER_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "database_path": DATABASE_PATH,
        "auth": "enabled" if auth_enabled() else "disabled",
        "auth_note": (
            "Bearer token required on /mcp."
            if auth_enabled()
            else "No auth configured — the MCP endpoint is open. "
            "Set MCP_AUTH_TOKEN before exposing publicly."
        ),
        "storage_note": (
            "SQLite file at DATABASE_PATH. Without a Railway Volume "
            "mounted at data/, the file is ephemeral and is lost on "
            "redeploy."
        ),
        "allowed_hosts": MCP_ALLOWED_HOSTS,
        "allowed_origins": MCP_ALLOWED_ORIGINS,
    }


def database_path() -> Path:
    return Path(DATABASE_PATH)
