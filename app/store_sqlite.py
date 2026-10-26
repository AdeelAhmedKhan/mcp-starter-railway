"""SQLite notes store — stdlib ``sqlite3`` only, no ORM, no fake data.

This is the default backend (used when ``DATABASE_URL`` is empty).
Implements :class:`app.store_base.NoteStore`. If the database file
cannot be opened, every method raises a clear ``StoreError`` instead
of returning invented notes.
"""

import sqlite3
from pathlib import Path

from app.store_base import DEMO_NOTES, StoreError, escape_like


class SQLiteStore:
    """Notes backed by a SQLite file at ``path``."""

    backend = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        try:
            if self.path.parent != Path("."):
                self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise StoreError(
                f"Cannot open SQLite database at {self.path}: {exc}. "
                "Check DATABASE_PATH and that the directory is writable."
            ) from exc

    def init_db(self) -> int:
        conn = self._connect()
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
            raise StoreError(
                f"Cannot initialise database at {self.path}: {exc}"
            ) from exc
        finally:
            conn.close()

    def db_ok(self) -> bool:
        try:
            conn = self._connect()
            try:
                conn.execute("SELECT 1").fetchone()
                return True
            finally:
                conn.close()
        except StoreError:
            return False

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "body": row["body"],
            "created_at": row["created_at"],
        }

    def create_note(self, title: str, body: str) -> dict:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO notes (title, body, created_at) "
                "VALUES (?, ?, datetime('now'))",
                (title, body),
            )
            conn.commit()
            note_id = cursor.lastrowid
        except sqlite3.Error as exc:
            raise StoreError(
                f"Cannot create note in {self.path}: {exc}"
            ) from exc
        finally:
            conn.close()
        return self.get_note(note_id)

    def list_notes(self, limit: int = 10) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, title, body, created_at FROM notes "
                "ORDER BY id DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
            return [self._row_to_note(r) for r in rows]
        except sqlite3.Error as exc:
            raise StoreError(
                f"Cannot list notes from {self.path}: {exc}"
            ) from exc
        finally:
            conn.close()

    def search_notes(self, query: str) -> list[dict]:
        """LIKE search over title/body. Wildcards in the query are
        escaped, so a user query can never act as a pattern."""
        pattern = f"%{escape_like(query)}%"
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, title, body, created_at FROM notes "
                "WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' "
                "ORDER BY id DESC",
                (pattern, pattern),
            ).fetchall()
            return [self._row_to_note(r) for r in rows]
        except sqlite3.Error as exc:
            raise StoreError(
                f"Cannot search notes in {self.path}: {exc}"
            ) from exc
        finally:
            conn.close()

    def get_note(self, note_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, title, body, created_at FROM notes WHERE id = ?",
                (note_id,),
            ).fetchone()
            return self._row_to_note(row) if row is not None else None
        except sqlite3.Error as exc:
            raise StoreError(
                f"Cannot read note {note_id} from {self.path}: {exc}"
            ) from exc
        finally:
            conn.close()
