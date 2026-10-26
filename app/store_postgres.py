"""Postgres notes store — ``psycopg`` 3 (binary wheel, no compiler).

This is the backend used when ``DATABASE_URL`` is set. It implements
exactly the same interface as the SQLite store
(:class:`app.store_base.NoteStore`): same notes table, same idempotent
seeding, same LIKE-wildcard escaping. The only deliberate difference
is ``created_at``: Postgres returns a ``datetime``, which is converted
to an ISO-8601 string so tool/resource responses match the SQLite
shape (plain strings, JSON-safe).

``psycopg`` is imported lazily-guarded: if it is not installed, the
store raises a clear ``StoreError`` instead of failing at import
time, and ``db_ok()`` honestly reports ``False``.
"""

from datetime import datetime

from app.store_base import DEMO_NOTES, StoreError, escape_like

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised only without psycopg
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


class PostgresStore:
    """Notes backed by a Postgres database at ``dsn`` (a DATABASE_URL
    connection string, e.g. ``postgresql://user:password@host:5432/db``)."""

    backend = "postgres"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _connect(self):
        if psycopg is None:
            raise StoreError(
                "Postgres store selected (DATABASE_URL is set) but "
                "psycopg is not installed. Install the dependencies "
                "from requirements.txt."
            )
        try:
            return psycopg.connect(self.dsn, row_factory=dict_row)
        except psycopg.Error as exc:
            raise StoreError(
                "Cannot connect to Postgres via DATABASE_URL: "
                f"{exc}. Check DATABASE_URL and that the database "
                "is reachable."
            ) from exc

    def init_db(self) -> int:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS notes ("
                    "id SERIAL PRIMARY KEY, "
                    "title TEXT NOT NULL, "
                    "body TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                    ")"
                )
                count = cur.execute("SELECT COUNT(*) FROM notes").fetchone()["count"]
                if count > 0:
                    conn.commit()
                    return 0
                cur.executemany(
                    "INSERT INTO notes (title, body) VALUES (%s, %s)",
                    DEMO_NOTES,
                )
            conn.commit()
            return len(DEMO_NOTES)
        except psycopg.Error as exc:
            conn.rollback()
            raise StoreError(
                f"Cannot initialise Postgres notes table: {exc}"
            ) from exc
        finally:
            conn.close()

    def db_ok(self) -> bool:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1").fetchone()
                return True
            finally:
                conn.close()
        except StoreError:
            return False

    @staticmethod
    def _row_to_note(row: dict) -> dict:
        created_at = row["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        return {
            "id": row["id"],
            "title": row["title"],
            "body": row["body"],
            "created_at": created_at,
        }

    def create_note(self, title: str, body: str) -> dict:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO notes (title, body) VALUES (%s, %s) "
                    "RETURNING id",
                    (title, body),
                )
                note_id = cur.fetchone()["id"]
            conn.commit()
        except psycopg.Error as exc:
            conn.rollback()
            raise StoreError(f"Cannot create note in Postgres: {exc}") from exc
        finally:
            conn.close()
        return self.get_note(note_id)

    def list_notes(self, limit: int = 10) -> list[dict]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                rows = cur.execute(
                    "SELECT id, title, body, created_at FROM notes "
                    "ORDER BY id DESC LIMIT %s",
                    (max(1, limit),),
                ).fetchall()
            return [self._row_to_note(r) for r in rows]
        except psycopg.Error as exc:
            raise StoreError(
                f"Cannot list notes from Postgres: {exc}"
            ) from exc
        finally:
            conn.close()

    def search_notes(self, query: str) -> list[dict]:
        """LIKE search over title/body. Wildcards in the query are
        escaped, so a user query can never act as a pattern."""
        pattern = f"%{escape_like(query)}%"
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                rows = cur.execute(
                    "SELECT id, title, body, created_at FROM notes "
                    "WHERE title LIKE %s ESCAPE '\\' "
                    "OR body LIKE %s ESCAPE '\\' "
                    "ORDER BY id DESC",
                    (pattern, pattern),
                ).fetchall()
            return [self._row_to_note(r) for r in rows]
        except psycopg.Error as exc:
            raise StoreError(
                f"Cannot search notes in Postgres: {exc}"
            ) from exc
        finally:
            conn.close()

    def get_note(self, note_id: int) -> dict | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                row = cur.execute(
                    "SELECT id, title, body, created_at FROM notes "
                    "WHERE id = %s",
                    (note_id,),
                ).fetchone()
            return self._row_to_note(row) if row is not None else None
        except psycopg.Error as exc:
            raise StoreError(
                f"Cannot read note {note_id} from Postgres: {exc}"
            ) from exc
        finally:
            conn.close()
