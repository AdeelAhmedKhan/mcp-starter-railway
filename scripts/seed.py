"""Idempotent seed: creates the notes table and seeds the demo notes
if the table is empty. Safe to re-run — it never duplicates notes.

Uses the active store: Postgres when DATABASE_URL is set, otherwise
the SQLite file at DATABASE_PATH.

Usage:
    python scripts/seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import settings, store  # noqa: E402


def main() -> None:
    active_store = store.get_store()
    seeded = active_store.init_db()
    if active_store.backend == "postgres":
        print("Store: Postgres (DATABASE_URL is set)")
    else:
        print(f"Store: SQLite at {settings.DATABASE_PATH}")
    print(f"Seeded {seeded} demo notes." if seeded else "Notes already present — nothing seeded.")


if __name__ == "__main__":
    main()
