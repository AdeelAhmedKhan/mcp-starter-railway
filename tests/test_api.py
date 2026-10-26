"""Tests against the REAL server — no mocks.

- ``/api/health`` and ``/`` via FastAPI TestClient.
- The full MCP flow (initialize, list/call tools, read resources, list
  prompts, unknown-tool error) against a live uvicorn process on an
  ephemeral port, using the official ``streamable_http_client`` +
  ``ClientSession``.

Run: ``python -m pytest``
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

# Env must be set BEFORE importing the app (settings read at import).
TEST_DB = Path(__file__).resolve().parents[1] / "data" / "test-notes.db"
os.environ.setdefault("DATABASE_PATH", str(TEST_DB))
os.environ.pop("MCP_AUTH_TOKEN", None)  # tests run with auth disabled

from app.main import app  # noqa: E402

TOOL_NAMES = ["add_numbers", "echo", "create_note", "list_notes", "search_notes"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _text_content(result) -> str:
    """First text block of a CallToolResult."""
    assert result.content, "tool result had no content"
    return result.content[0].text


def _tool_value(result):
    """The tool's return value, preferring structured content.

    FastMCP 2.3.0 serialises a list return as one TextContent block
    PER ITEM (plus structured_content={"result": [...]}), so reading
    only the first text block would silently drop items. Structured
    content is the complete value; fall back to parsing the text.
    """
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    texts = [c.text for c in result.content]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return texts[0]
    return [json.loads(t) for t in texts]


# ------------------------------------------------------- HTTP endpoints
# One shared TestClient for the whole module: the FastAPI lifespan
# enters the MCP session manager's run(), which can only be called
# once per manager instance (one lifespan per process). A second
# TestClient context in the same process would raise on entry.


@pytest.fixture(scope="module")
def http_client():
    with TestClient(app) as client:
        yield client


def test_health_full_body(http_client):
    resp = http_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["db"] in ("ok", "error")
    assert body["mcp"]["server"] == "mcp-starter"
    assert body["mcp"]["protocol_version"] == "2026-07-28"
    assert body["mcp"]["tools"] == TOOL_NAMES
    assert body["mcp"]["resources"] == ["notes://all", "notes://{id}"]
    assert body["mcp"]["prompts"] == ["summarize-notes"]
    assert body["auth"] == "disabled"


def test_landing_page(http_client):
    resp = http_client.get("/")
    assert resp.status_code == 200
    assert "MCP" in resp.text
    assert "/mcp" in resp.text
    assert "add_numbers" in resp.text
    assert "notes://all" in resp.text
    assert "summarize-notes" in resp.text
    assert "No auth configured" in resp.text


# ------------------------------------------------------------- MCP flow


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """Start the real server in a subprocess on an ephemeral port."""
    db_path = tmp_path_factory.mktemp("mcp-live") / "notes.db"
    port = _free_port()
    env = dict(os.environ)
    env["DATABASE_PATH"] = str(db_path)
    env["PORT"] = str(port)
    env.pop("MCP_AUTH_TOKEN", None)
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=root,
        env={**env, "PYTHONPATH": str(root)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 30
        # trust_env=False: this VM exports ALL_PROXY/no_proxy env vars and
        # httpx trips over them when parsing env proxies for a localhost
        # URL. The test server is local; no proxy is wanted or needed.
        with httpx.Client(trust_env=False) as client:
            while time.time() < deadline:
                try:
                    r = client.get(f"{url}/api/health", timeout=2)
                    if r.status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("live server did not become healthy in 30s")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _run_mcp_flow(base_url: str) -> dict:
    """Drive the whole MCP flow with the official client. Returns evidence."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def flow():
        evidence = {}
        # trust_env=False: see live_server fixture — the VM's proxy env
        # vars break httpx's env-proxy parsing for localhost URLs.
        http_client = httpx.AsyncClient(trust_env=False)
        async with streamable_http_client(
            f"{base_url}/mcp", http_client=http_client
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                evidence["tools"] = sorted(t.name for t in tools.tools)
                result = await session.call_tool("add_numbers", {"a": 2, "b": 3})
                evidence["add_numbers"] = _tool_value(result)
                result = await session.call_tool(
                    "echo", {"message": "hello mcp"})
                evidence["echo"] = _text_content(result)
                result = await session.call_tool(
                    "create_note",
                    {"title": "MCP flow note", "body": "created by the test suite"},
                )
                evidence["create_note"] = _tool_value(result)
                result = await session.call_tool("list_notes", {"limit": 10})
                evidence["list_notes"] = _tool_value(result)
                result = await session.call_tool(
                    "search_notes", {"query": "MCP flow"})
                evidence["search_notes"] = _tool_value(result)
                resources = await session.list_resources()
                evidence["resources"] = sorted(r.uri for r in resources.resources)
                templates = await session.list_resource_templates()
                evidence["resource_templates"] = sorted(
                    t.uri_template for t in templates.resource_templates)
                read_result = await session.read_resource("notes://all")
                evidence["notes_all"] = json.loads(read_result.contents[0].text)
                note_id = evidence["create_note"]["id"]
                read_result = await session.read_resource(f"notes://{note_id}")
                evidence["note_by_id"] = json.loads(read_result.contents[0].text)
                prompts = await session.list_prompts()
                evidence["prompts"] = sorted(p.name for p in prompts.prompts)
                prompt = await session.get_prompt("summarize-notes")
                evidence["prompt_text"] = prompt.messages[0].content.text
                # Unknown tool returns a proper MCP error result
                # (is_error=True), not a crash and not an exception.
                result = await session.call_tool("does_not_exist", {})
                assert result.is_error is True
                evidence["unknown_tool_error"] = _text_content(result)
        return evidence

    return asyncio.run(flow())


def test_mcp_flow_live(live_server):
    ev = _run_mcp_flow(live_server)
    assert ev["tools"] == sorted(TOOL_NAMES)
    assert ev["add_numbers"] == 5.0
    assert ev["echo"] == "hello mcp"
    assert ev["create_note"]["title"] == "MCP flow note"
    created_id = ev["create_note"]["id"]
    listed_ids = [n["id"] for n in ev["list_notes"]]
    assert created_id in listed_ids
    assert len(ev["list_notes"]) >= 4  # 3 seeded + at least the created one
    assert any(n["id"] == created_id for n in ev["search_notes"])
    assert "notes://all" in ev["resources"]
    assert "notes://{id}" in ev["resource_templates"]
    assert any(n["id"] == created_id for n in ev["notes_all"])
    assert ev["note_by_id"]["id"] == created_id
    assert ev["note_by_id"]["title"] == "MCP flow note"
    assert ev["prompts"] == ["summarize-notes"]
    assert "calling model" in ev["prompt_text"]
    assert "does_not_exist" in ev["unknown_tool_error"]


def test_resource_missing_note_live(live_server):
    """Reading a missing note returns an honest error string, not fake data."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def flow():
        http_client = httpx.AsyncClient(trust_env=False)
        async with streamable_http_client(
            f"{live_server}/mcp", http_client=http_client
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource("notes://999999")
                return json.loads(result.contents[0].text)

    body = asyncio.run(flow())
    assert "error" in body
