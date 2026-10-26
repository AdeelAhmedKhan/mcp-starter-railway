"""MCP Starter — a production-wired MCP server starter (FastAPI + SQLite).

Importing this package loads ``.env`` (if present) so ``cp .env.example
.env`` works out of the box. Real environment variables always win over
``.env`` values.
"""

from dotenv import load_dotenv

load_dotenv()
