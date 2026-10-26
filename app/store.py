"""SQLite notes store — stdlib ``sqlite3`` only, no ORM, no fake data.

If the database file cannot be opened, every function raises a clear
``StoreError`` instead of returning invented notes. ``init_db`` is
idempotent: it creates the table if missing and seeds three demo notes
only when the table is empty.
"""

import sqlite3
from pathlib import Path

DEMO_NOTES = [
    (
        "Welcome to MCP Starter",
        "This note was seeded by scripts/seed.py (or on first startup). "
        "It proves the SQLite store works end to end.",
    ),
    (
        "How the tools work",
        "add_numbers adds two numbers, echo repeats a message, and "
        "create_note / list_notes / search_notes read and write this "
        "SQLite database through the MCP tools.",
    ),
    (
        "Try the prompt",
        "Ask your MCP client for the summarize-notes prompt. The "
        "summary is produced by the calling model, not by this server.",
    ),
]


class StoreError(RuntimeError):
    """Raised when the SQLite file cannot be opened or queried."""


def _connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    try:
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        raise StoreError(
            f"Cannot open SQLite database at {path}: {exc}. "
            "Check DATABASE_PATH and that the directory is writable."
        ) from exc


def init_db(path: str | Path) -> int:
    """Create the notes table if missing; seed demo notes if empty.

    Returns the number of notes seeded (0 when the table already had
    rows). Idempotent — safe to call on every startup and re-run.
    """
    conn = _connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS notes ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT NOT NULL, "
            "body TEXT NOT NULL, "
            "created_at TEXT NOT NULL"
            ")"
        )
        count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        if count > 0:
            return 0
        conn.executemany(
            "INSERT INTO notes (title, body, created_at) "
            "VALUES (?, ?, datetime('now'))",
            DEMO_NOTES,
        )
        conn.commit()
        return len(DEMO_NOTES)
    except sqlite3.Error as exc:
        raise StoreError(f"Cannot initialise database at {path}: {exc}") from exc
    finally:
        conn.close()


def db_ok(path: str | Path) -> bool:
    """True when the database file opens and answers a query."""
    try:
        conn = _connect(path)
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        finally:
            conn.close()
    except StoreError:
        return False


def _row_to_note(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "created_at": row["created_at"],
    }


def create_note(path: str | Path, title: str, body: str) -> dict:
    conn = _connect(path)
    try:
        cursor = conn.execute(
            "INSERT INTO notes (title, body, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (title, body),
        )
        conn.commit()
        return get_note(path, cursor.lastrowid)
    except sqlite3.Error as exc:
        raise StoreError(f"Cannot create note in {path}: {exc}") from exc
    finally:
        conn.close()


def list_notes(path: str | Path, limit: int = 10) -> list[dict]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT id, title, body, created_at FROM notes "
            "ORDER BY id DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
        return [_row_to_note(r) for r in rows]
    except sqlite3.Error as exc:
        raise StoreError(f"Cannot list notes from {path}: {exc}") from exc
    finally:
        conn.close()


def search_notes(path: str | Path, query: str) -> list[dict]:
    """LIKE search over title/body. Wildcards in the query are escaped,
    so a user query can never act as a pattern."""
    escaped = (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT id, title, body, created_at FROM notes "
            "WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' "
            "ORDER BY id DESC",
            (pattern, pattern),
        ).fetchall()
        return [_row_to_note(r) for r in rows]
    except sqlite3.Error as exc:
        raise StoreError(f"Cannot search notes in {path}: {exc}") from exc
    finally:
        conn.close()


def get_note(path: str | Path, note_id: int) -> dict | None:
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT id, title, body, created_at FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
        return _row_to_note(row) if row is not None else None
    except sqlite3.Error as exc:
        raise StoreError(f"Cannot read note {note_id} from {path}: {exc}") from exc
    finally:
        conn.close()
