"""Store selection — the single place that decides which backend is active.

- ``DATABASE_URL`` set → :class:`app.store_postgres.PostgresStore`
- otherwise → :class:`app.store_sqlite.SQLiteStore` at ``DATABASE_PATH``

Tools, resources, ``app/main.py`` and ``scripts/seed.py`` must go
through :func:`get_store` — no tool code touches SQLite or Postgres
directly.

The module-level functions below are a thin compatibility shim over
the SQLite store (same signatures as the original ``store.py``);
all real logic lives in ``app/store_sqlite.py``.
"""

from pathlib import Path

from app import settings
from app.store_base import DEMO_NOTES, NoteStore, StoreError
from app.store_postgres import PostgresStore
from app.store_sqlite import SQLiteStore

__all__ = [
    "DEMO_NOTES",
    "NoteStore",
    "PostgresStore",
    "SQLiteStore",
    "StoreError",
    "create_note",
    "db_ok",
    "get_note",
    "get_store",
    "init_db",
    "list_notes",
    "search_notes",
]


def get_store() -> NoteStore:
    """Return the active notes store for the current settings."""
    if settings.DATABASE_URL:
        return PostgresStore(settings.DATABASE_URL)
    return SQLiteStore(settings.DATABASE_PATH)


# ------------------------------------------- compatibility shim (SQLite)


def init_db(path: str | Path) -> int:
    return SQLiteStore(path).init_db()


def db_ok(path: str | Path) -> bool:
    return SQLiteStore(path).db_ok()


def create_note(path: str | Path, title: str, body: str) -> dict:
    return SQLiteStore(path).create_note(title, body)


def list_notes(path: str | Path, limit: int = 10) -> list[dict]:
    return SQLiteStore(path).list_notes(limit=limit)


def search_notes(path: str | Path, query: str) -> list[dict]:
    return SQLiteStore(path).search_notes(query)


def get_note(path: str | Path, note_id: int) -> dict | None:
    return SQLiteStore(path).get_note(note_id)
