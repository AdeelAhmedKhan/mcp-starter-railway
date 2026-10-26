"""Idempotent seed: creates the notes table and seeds the demo notes
if the table is empty. Safe to re-run — it never duplicates notes.

Usage:
    python scripts/seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import settings, store  # noqa: E402


def main() -> None:
    seeded = store.init_db(settings.DATABASE_PATH)
    print(f"Database: {settings.DATABASE_PATH}")
    print(f"Seeded {seeded} demo notes." if seeded else "Notes already present — nothing seeded.")


if __name__ == "__main__":
    main()
