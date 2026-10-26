"""Notes tools, resources, and the summarize-notes prompt.

All notes access goes through ``app.store.get_store()`` — the tools
never touch SQLite or Postgres directly, so the backend (SQLite by
default, Postgres when ``DATABASE_URL`` is set) is invisible here.

Honesty rules (unchanged from the original single-file server):
- A missing note is reported as a plain error string, not invented data.
- The ``summarize-notes`` prompt only *asks* the calling model to
  summarise; the summary itself is produced by the model, not by us.
"""

import json

from app.store import get_store


def register(server) -> None:
    """Register the notes tools, resources, and prompt on the server."""

    @server.tool()
    def create_note(title: str, body: str) -> dict:
        """Create a note and return its id and title."""
        note = get_store().create_note(title, body)
        return {"id": note["id"], "title": note["title"]}

    @server.tool()
    def list_notes(limit: int = 10) -> list[dict]:
        """List the most recent notes (default 10, newest first)."""
        return get_store().list_notes(limit=limit)

    @server.tool()
    def search_notes(query: str) -> list[dict]:
        """Search notes by title or body (substring match)."""
        return get_store().search_notes(query)

    @server.resource("notes://all", mime_type="application/json")
    def all_notes() -> str:
        """All notes as JSON."""
        notes = get_store().list_notes(limit=1000)
        return json.dumps(notes)

    @server.resource("notes://{id}", mime_type="application/json")
    def note_by_id(id: str) -> str:
        """One note by id as JSON.

        A missing or non-numeric id is reported as a plain error
        string — no note is ever invented.
        """
        try:
            note_id = int(id)
        except ValueError:
            return json.dumps(
                {"error": f"No note with id {id!r}: id must be an integer."}
            )
        note = get_store().get_note(note_id)
        if note is None:
            return json.dumps({"error": f"No note with id {note_id}."})
        return json.dumps(note)

    @server.prompt("summarize-notes")
    def summarize_notes() -> str:
        """Ask the calling model to summarise all notes.

        This returns an instruction, not a summary: the summary is
        produced by the model that called this prompt, using the
        notes it reads via the list_notes tool or the notes://all
        resource.
        """
        return (
            "Summarise all of the user's notes. First read them with the "
            "list_notes tool (or the notes://all resource), then write a short "
            "summary: one line per note with its title and main point, plus "
            "any themes that appear across several notes. This summary is "
            "produced by you, the calling model — the server only stores the "
            "notes and does not summarise them itself."
        )
