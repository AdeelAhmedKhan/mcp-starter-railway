"""Notes-store interface — the contract every backend must satisfy.

Tools, resources, ``app/main.py`` and ``scripts/seed.py`` only ever talk
to a store through this interface (via ``app.store.get_store()``). No
tool code touches SQLite or Postgres directly, so the backend can be
swapped by setting ``DATABASE_URL`` (Postgres) or leaving it empty
(SQLite at ``DATABASE_PATH``).

A store object holds its own locator (a file path for SQLite, a DSN
for Postgres) and opens a fresh connection per operation — same
pattern the original SQLite store used. ``init_db`` is idempotent:
create the table if missing and seed the demo notes only when the
table is empty.
"""

from typing import Protocol

DEMO_NOTES = [
    (
        "Welcome to MCP Starter",
        "This note was seeded by scripts/seed.py (or on first startup). "
        "It proves the notes store works end to end.",
    ),
    (
        "How the tools work",
        "add_numbers adds two numbers, echo repeats a message, and "
        "create_note / list_notes / search_notes read and write the "
        "notes store through the MCP tools.",
    ),
    (
        "Try the prompt",
        "Ask your MCP client for the summarize-notes prompt. The "
        "summary is produced by the calling model, not by this server.",
    ),
]


class StoreError(RuntimeError):
    """Raised when the store cannot be opened or queried.

    Callers report this as an honest error string; nothing is ever
    invented in its place.
    """


def escape_like(query: str) -> str:
    """Escape LIKE wildcards in a user query so it can never act as a
    pattern. Shared by the SQLite and Postgres backends."""
    return (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


class NoteStore(Protocol):
    """The notes-store interface. ``backend`` is ``"sqlite"`` or
    ``"postgres"`` and is what ``/api/health`` reports."""

    backend: str

    def init_db(self) -> int:
        """Create the notes table if missing; seed demo notes if empty.

        Returns the number of notes seeded (0 when the table already
        had rows). Idempotent — safe to call on every startup.
        """
        ...

    def db_ok(self) -> bool:
        """True when the store opens and answers a query."""
        ...

    def create_note(self, title: str, body: str) -> dict:
        """Insert a note and return it (``id``, ``title``, ``body``,
        ``created_at``)."""
        ...

    def list_notes(self, limit: int = 10) -> list[dict]:
        """Most recent notes, newest first."""
        ...

    def search_notes(self, query: str) -> list[dict]:
        """Substring search over title/body (LIKE wildcards escaped)."""
        ...

    def get_note(self, note_id: int) -> dict | None:
        """One note by id, or ``None`` when it does not exist."""
        ...
