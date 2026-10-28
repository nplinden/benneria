"""
The notebook's own data: a writable SQLite database, separate from the read-only Bible text
(bhsa.sqlite): the accounts, and for each account which chapter notebooks it has created and the
notes and verb tables written in them.

Location: $BENNERIA_NOTEBOOK_DB, or else $XDG_DATA_HOME/benneria-notebook/notebook.sqlite
(~/.local/share/benneria-notebook/notebook.sqlite by default).
"""

import datetime
import functools
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

# Each statement on its own: the migration below runs them one by one, in its own transaction.
TABLES = {
    # An account. `token` changes with the password, which logs out the account's sessions (each
    # one holds the token it was opened with); `failed` and `locked_until` slow password guessing.
    "users": """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- never reused, so a new account can't inherit data
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password TEXT NOT NULL,     -- werkzeug's salted hash
        token TEXT NOT NULL,
        failed INTEGER NOT NULL DEFAULT 0,      -- wrong passwords in a row
        locked_until TEXT,          -- ISO timestamp, UTC, after too many of them
        created TEXT NOT NULL       -- ISO timestamp, UTC
    )""",
    "chapters": """CREATE TABLE IF NOT EXISTS chapters (
        user_id INTEGER NOT NULL,
        book TEXT NOT NULL,         -- OSIS book code, e.g. 'Isa'
        chapter INTEGER NOT NULL,
        created TEXT NOT NULL,      -- ISO timestamp, UTC
        PRIMARY KEY (user_id, book, chapter)
    )""",
    # A note sits after a verse: verse N's note comes between verses N and N+1. Its text is Markdown.
    "notes": """CREATE TABLE IF NOT EXISTS notes (
        user_id INTEGER NOT NULL,
        book TEXT NOT NULL,
        chapter INTEGER NOT NULL,
        verse INTEGER NOT NULL,
        text TEXT NOT NULL,
        updated TEXT NOT NULL,      -- ISO timestamp, UTC
        PRIMARY KEY (user_id, book, chapter, verse)
    )""",
    # A verse's verb table: its rows as a JSON list of lists of cell texts, one list per row, in the
    # columns' order (see app.TABLE_COLUMNS).
    "tables": """CREATE TABLE IF NOT EXISTS tables (
        user_id INTEGER NOT NULL,
        book TEXT NOT NULL,
        chapter INTEGER NOT NULL,
        verse INTEGER NOT NULL,
        rows TEXT NOT NULL,
        updated TEXT NOT NULL,      -- ISO timestamp, UTC
        PRIMARY KEY (user_id, book, chapter, verse)
    )""",
}
# The columns of the notebook's tables before accounts existed, copied as they were.
V1_COLUMNS = {"chapters": "book, chapter, created",
              "notes": "book, chapter, verse, text, updated",
              "tables": "book, chapter, verse, rows, updated"}
# Whose the notes written before accounts existed become: the first account created.
FIRST_USER = 1

MAX_FAILURES = 5                            # wrong passwords in a row before a lockout
LOCKOUT = datetime.timedelta(minutes=1)


class LockedOut(Exception):
    """Too many wrong passwords in a row: no login for this account until the lockout ends."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def default_path():
    if os.environ.get("BENNERIA_NOTEBOOK_DB"):
        return Path(os.environ["BENNERIA_NOTEBOOK_DB"])
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "benneria-notebook" / "notebook.sqlite"


@functools.cache
def _dummy_hash():
    # Checked against for an unknown name, so it takes as long as a wrong password would.
    return generate_password_hash(secrets.token_hex())


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
            # One transaction, taken before looking: several server processes start at once, and
            # only the first may migrate.
            conn.execute("BEGIN IMMEDIATE")
            columns = [row[1] for row in conn.execute("PRAGMA table_info(chapters)")]
            if columns and "user_id" not in columns:
                self._migrate_v1(conn)
            for statement in TABLES.values():
                conn.execute(statement)
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    @staticmethod
    def _migrate_v1(conn):
        """The notebook from before accounts: its rows move, unchanged, to FIRST_USER. SQLite
        can't change a table's primary key, so each table is rebuilt."""
        for name, columns in V1_COLUMNS.items():
            conn.execute(f"ALTER TABLE {name} RENAME TO {name}_v1")
            conn.execute(TABLES[name])
            conn.execute(f"INSERT INTO {name} (user_id, {columns}) SELECT ?, {columns} FROM {name}_v1",
                         (FIRST_USER,))
            conn.execute(f"DROP TABLE {name}_v1")

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

    # ---------- accounts ----------

    def add_user(self, name, password):
        """Create an account; returns its id. Raises ValueError if the name is taken (whatever
        its case)."""
        try:
            with self._connect() as db:
                return db.execute(
                    "INSERT INTO users (name, password, token, created) VALUES (?, ?, ?, ?)",
                    (name, generate_password_hash(password), secrets.token_urlsafe(), now())).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"An account named {name!r} already exists") from None

    def set_password(self, name, password):
        """Change an account's password, logging out its sessions and ending any lockout.
        Returns False if there is no such account."""
        with self._connect() as db:
            return db.execute(
                "UPDATE users SET password = ?, token = ?, failed = 0, locked_until = NULL WHERE name = ?",
                (generate_password_hash(password), secrets.token_urlsafe(), name)).rowcount == 1

    def remove_user(self, name):
        """Delete an account with all its notebooks, in one transaction. Returns
        {"chapters": n, "notes": n, "tables": n} removed, or None if there is no such account."""
        with self._connect() as db:
            row = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            if row is None:
                return None
            removed = {kind: db.execute(f"DELETE FROM {kind} WHERE user_id = ?", row).rowcount
                       for kind in ("chapters", "notes", "tables")}
            db.execute("DELETE FROM users WHERE id = ?", row)
        return removed

    def users(self):
        """[(name, created, number of chapter notebooks)], by name."""
        with self._connect() as db:
            return db.execute(
                "SELECT u.name, u.created, COUNT(c.chapter) FROM users u "
                "LEFT JOIN chapters c ON c.user_id = u.id GROUP BY u.id ORDER BY u.name").fetchall()

    def login(self, name, password):
        """Check a name and password: (id, name as created, session token), or None if wrong.
        Raises LockedOut after MAX_FAILURES wrong passwords in a row, for LOCKOUT, without
        checking the password meanwhile."""
        with self._connect() as db:
            row = db.execute("SELECT id, name, password, token, failed, locked_until FROM users "
                             "WHERE name = ?", (name,)).fetchone()
            if row is None:
                check_password_hash(_dummy_hash(), password)
                return None
            uid, real_name, hashed, token, failed, locked_until = row
            if locked_until and locked_until > now():
                raise LockedOut()
            if check_password_hash(hashed, password):
                db.execute("UPDATE users SET failed = 0, locked_until = NULL WHERE id = ?", (uid,))
                return uid, real_name, token
            if failed + 1 >= MAX_FAILURES:
                until = (datetime.datetime.now(datetime.timezone.utc) + LOCKOUT).isoformat(timespec="seconds")
                db.execute("UPDATE users SET failed = 0, locked_until = ? WHERE id = ?", (until, uid))
            else:
                db.execute("UPDATE users SET failed = ? WHERE id = ?", (failed + 1, uid))
            return None

    def session_user(self, uid, token):
        """The name of the account a session belongs to, or None if it no longer exists or its
        password changed since the session was opened."""
        with self._connect() as db:
            row = db.execute("SELECT name FROM users WHERE id = ? AND token = ?", (uid, token)).fetchone()
        return row[0] if row else None

    # ---------- one account's notebooks ----------

    def created_chapters(self, uid):
        """{book: sorted list of created chapter numbers}."""
        out = {}
        with self._connect() as db:
            for book, chapter in db.execute(
                    "SELECT book, chapter FROM chapters WHERE user_id = ? ORDER BY book, chapter", (uid,)):
                out.setdefault(book, []).append(chapter)
        return out

    def is_created(self, uid, book, chapter):
        with self._connect() as db:
            return db.execute("SELECT 1 FROM chapters WHERE user_id = ? AND book = ? AND chapter = ?",
                              (uid, book, chapter)).fetchone() is not None

    def create(self, uid, book, chapter):
        """Create a chapter's notebook; does nothing if it already exists. Returns True if new."""
        with self._connect() as db:
            cur = db.execute("INSERT OR IGNORE INTO chapters VALUES (?, ?, ?, ?)", (uid, book, chapter, now()))
            return cur.rowcount == 1

    def notes(self, uid, book, chapter):
        """{verse: note text} for a chapter."""
        with self._connect() as db:
            return dict(db.execute("SELECT verse, text FROM notes WHERE user_id = ? AND book = ? AND chapter = ?",
                                   (uid, book, chapter)))

    def set_note(self, uid, book, chapter, verse, text):
        """Save the note after a verse; an empty (or blank) note is removed. Returns the time saved."""
        stamp = now()
        with self._connect() as db:
            if text.strip():
                db.execute("INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, book, chapter, verse) "
                           "DO UPDATE SET text = excluded.text, updated = excluded.updated",
                           (uid, book, chapter, verse, text, stamp))
            else:
                db.execute("DELETE FROM notes WHERE user_id = ? AND book = ? AND chapter = ? AND verse = ?",
                           (uid, book, chapter, verse))
        return stamp

    def tables(self, uid, book, chapter):
        """{verse: rows} for a chapter's verb tables."""
        with self._connect() as db:
            return {verse: json.loads(rows) for verse, rows in db.execute(
                "SELECT verse, rows FROM tables WHERE user_id = ? AND book = ? AND chapter = ?",
                (uid, book, chapter))}

    def set_table(self, uid, book, chapter, verse, rows):
        """Save a verse's verb table; a table without rows is removed. Returns the time saved."""
        stamp = now()
        with self._connect() as db:
            if rows:
                db.execute("INSERT INTO tables VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, book, chapter, verse) "
                           "DO UPDATE SET rows = excluded.rows, updated = excluded.updated",
                           (uid, book, chapter, verse, json.dumps(rows, ensure_ascii=False), stamp))
            else:
                db.execute("DELETE FROM tables WHERE user_id = ? AND book = ? AND chapter = ? AND verse = ?",
                           (uid, book, chapter, verse))
        return stamp

    def delete(self, uid, book, chapter):
        """Delete a chapter's notebook with all its notes and tables, in one transaction.
        Returns {"notes": n, "tables": n} removed, or None if the chapter had no notebook."""
        with self._connect() as db:
            if not db.execute("DELETE FROM chapters WHERE user_id = ? AND book = ? AND chapter = ?",
                              (uid, book, chapter)).rowcount:
                return None
            removed = {kind: db.execute(f"DELETE FROM {kind} WHERE user_id = ? AND book = ? AND chapter = ?",
                                        (uid, book, chapter)).rowcount for kind in ("notes", "tables")}
        return removed
