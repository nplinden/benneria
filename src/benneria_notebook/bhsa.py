"""
Read access to data/bhsa.sqlite (built by scripts/build_bhsa.py from BHSA, CC BY-NC 4.0).

The database stores each word's text (with vowels and accents) and the trailer that follows it,
but not derived forms. They are computed here, with the same normalization the dictionary uses,
so the two apps agree on spellings:
  - a verse's text is its words' text + trailer, in order
  - a word's pointed (no cantillation) and consonantal forms come from benneria.hebrew

Texts are kept exactly as BHSA publishes them, including its own order of combining marks (e.g.
dagesh before sheva), which is not Unicode's NFC. They display the same; compare them after
unicodedata.normalize("NFC", ...). The derived pointed and consonantal forms are already NFC.
"""

import sqlite3
from importlib.resources import files

from benneria.hebrew import consonantal, pointed

DB_PATH = files("benneria_notebook") / "data" / "bhsa.sqlite"


def connect(path=DB_PATH):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def assemble(words, form=None):
    """A verse's text from its words, given as (text, trailer) pairs in order. With form=pointed,
    the text without cantillation."""
    form = form or (lambda text: text)
    return "".join(form(text) + trailer for text, trailer in words).strip()


def verse_words(db, osis):
    """The words of a verse ('Gen.1.1'), in order, with their pointed and consonantal forms."""
    rows = db.execute(
        "SELECT w.* FROM words w JOIN verses v ON v.id = w.verse_id WHERE v.osis = ? ORDER BY w.position",
        (osis,)).fetchall()
    return [{**dict(r), "pointed": pointed(r["text"]), "consonantal": consonantal(r["text"])} for r in rows]


def verse_text(db, osis, form=None):
    """A verse's text ('Gen.1.1'): as in BHSA, or without cantillation with form=pointed."""
    rows = db.execute(
        "SELECT w.text, w.trailer FROM words w JOIN verses v ON v.id = w.verse_id "
        "WHERE v.osis = ? ORDER BY w.position", (osis,)).fetchall()
    return assemble([(r["text"], r["trailer"]) for r in rows], form)


def chapter_verses(db, book_osis, chapter):
    """[(verse, osis, text)] for a chapter ('Gen', 1), in verse order. Shared by the notebook
    and the BHS reader, the two apps that show chapters of text."""
    rows = db.execute(
        "SELECT v.verse, v.osis, w.text, w.trailer FROM verses v "
        "JOIN books b ON b.id = v.book_id JOIN words w ON w.verse_id = v.id "
        "WHERE b.osis = ? AND v.chapter = ? ORDER BY v.verse, w.position", (book_osis, chapter)).fetchall()
    verses = {}
    for r in rows:
        verses.setdefault((r["verse"], r["osis"]), []).append((r["text"], r["trailer"]))
    return [(verse, osis, assemble(words)) for (verse, osis), words in verses.items()]
