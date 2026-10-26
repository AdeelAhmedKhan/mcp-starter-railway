"""fetch_json — the "wrap my API" example tool.

Fetches JSON from an http(s) URL and returns the parsed value. Every
failure is reported as a plain error string — never invented data:
non-200 status, timeout, invalid JSON, an over-large response, or a
non-http(s) URL. Only http:// and https:// are fetched (``file://``
and friends are rejected outright).
"""

import json
from urllib.parse import urlparse

import httpx

MAX_RESPONSE_BYTES = 1_000_000  # 1 MB
TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 5


def fetch_json(url: str):
    """Fetch JSON from an http(s) URL and return the parsed value.

    Returns the parsed JSON (dict, list, str, number, bool, or None)
    on success. Errors — non-200 status, timeout, invalid JSON,
    a response over 1 MB, a non-http(s) URL — are returned as plain
    error strings, never invented data.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return (
            "Error: only http:// and https:// URLs can be fetched, "
            f"got {url!r}."
        )
    try:
        with httpx.Client(
            trust_env=False,  # this VM exports proxy env vars that break
            # httpx's env-proxy parsing for localhost URLs
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return (
                        f"Error: {url} returned HTTP "
                        f"{response.status_code}."
                    )
                declared = response.headers.get("content-length")
                if declared is not None:
                    try:
                        if int(declared) > MAX_RESPONSE_BYTES:
                            return (
                                "Error: response from "
                                f"{url} exceeds the 1 MB limit "
                                f"(Content-Length: {declared} bytes)."
                            )
                    except ValueError:
                        pass  # unparseable header: enforce by counting
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        return (
                            "Error: response from "
                            f"{url} exceeds the 1 MB limit."
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)
    except httpx.TimeoutException:
        return (
            f"Error: request to {url} timed out after "
            f"{TIMEOUT_SECONDS:g} seconds."
        )
    except httpx.HTTPError as exc:
        return f"Error: request to {url} failed: {exc}."
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return f"Error: response from {url} is not valid JSON: {exc}."


def register(server) -> None:
    """Register fetch_json on the given MCP server."""
    server.tool()(fetch_json)
