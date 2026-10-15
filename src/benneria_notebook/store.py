"""
The notebook's own data: a writable SQLite database, separate from the read-only Bible text
(bhsa.sqlite): which chapter notebooks have been created, and the notes and verb tables
written in them.

Location: $BENNERIA_NOTEBOOK_DB, or else $XDG_DATA_HOME/benneria-notebook/notebook.sqlite
(~/.local/share/benneria-notebook/notebook.sqlite by default).
"""

import datetime
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    book TEXT NOT NULL,         -- OSIS book code, e.g. 'Isa'
    chapter INTEGER NOT NULL,
    created TEXT NOT NULL,      -- ISO timestamp, UTC
    PRIMARY KEY (book, chapter)
);

-- A note sits after a verse: verse N's note comes between verses N and N+1. Its text is Markdown.
CREATE TABLE IF NOT EXISTS notes (
    book TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    text TEXT NOT NULL,
    updated TEXT NOT NULL,      -- ISO timestamp, UTC
    PRIMARY KEY (book, chapter, verse)
);

-- A verse's verb table: its rows as a JSON list of lists of cell texts, one list per row, in the
-- columns' order (see app.TABLE_COLUMNS).
CREATE TABLE IF NOT EXISTS tables (
    book TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    rows TEXT NOT NULL,
    updated TEXT NOT NULL,      -- ISO timestamp, UTC
    PRIMARY KEY (book, chapter, verse)
);
"""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def default_path():
    if os.environ.get("BENNERIA_NOTEBOOK_DB"):
        return Path(os.environ["BENNERIA_NOTEBOOK_DB"])
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "benneria-notebook" / "notebook.sqlite"


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
            db.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        """A short-lived connection per call (requests run on several threads): committed on
        success, rolled back on error, and always closed."""
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def created_chapters(self):
        """{book: sorted list of created chapter numbers}."""
        out = {}
        with self._connect() as db:
            for book, chapter in db.execute("SELECT book, chapter FROM chapters ORDER BY book, chapter"):
                out.setdefault(book, []).append(chapter)
        return out

    def is_created(self, book, chapter):
        with self._connect() as db:
            return db.execute("SELECT 1 FROM chapters WHERE book = ? AND chapter = ?",
                              (book, chapter)).fetchone() is not None

    def create(self, book, chapter):
        """Create a chapter's notebook; does nothing if it already exists. Returns True if new."""
        with self._connect() as db:
            cur = db.execute("INSERT OR IGNORE INTO chapters VALUES (?, ?, ?)", (book, chapter, now()))
            return cur.rowcount == 1

    def notes(self, book, chapter):
        """{verse: note text} for a chapter."""
        with self._connect() as db:
            return dict(db.execute("SELECT verse, text FROM notes WHERE book = ? AND chapter = ?",
                                   (book, chapter)))

    def set_note(self, book, chapter, verse, text):
        """Save the note after a verse; an empty (or blank) note is removed. Returns the time saved."""
        stamp = now()
        with self._connect() as db:
            if text.strip():
                db.execute("INSERT INTO notes VALUES (?, ?, ?, ?, ?) ON CONFLICT (book, chapter, verse) "
                           "DO UPDATE SET text = excluded.text, updated = excluded.updated",
                           (book, chapter, verse, text, stamp))
            else:
                db.execute("DELETE FROM notes WHERE book = ? AND chapter = ? AND verse = ?",
                           (book, chapter, verse))
        return stamp

    def tables(self, book, chapter):
        """{verse: rows} for a chapter's verb tables."""
        with self._connect() as db:
            return {verse: json.loads(rows) for verse, rows in db.execute(
                "SELECT verse, rows FROM tables WHERE book = ? AND chapter = ?", (book, chapter))}

    def set_table(self, book, chapter, verse, rows):
        """Save a verse's verb table; a table without rows is removed. Returns the time saved."""
        stamp = now()
        with self._connect() as db:
            if rows:
                db.execute("INSERT INTO tables VALUES (?, ?, ?, ?, ?) ON CONFLICT (book, chapter, verse) "
                           "DO UPDATE SET rows = excluded.rows, updated = excluded.updated",
                           (book, chapter, verse, json.dumps(rows, ensure_ascii=False), stamp))
            else:
                db.execute("DELETE FROM tables WHERE book = ? AND chapter = ? AND verse = ?",
                           (book, chapter, verse))
        return stamp
