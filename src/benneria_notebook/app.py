"""
Benneria Notebook's part of the web app: notes on Biblical verses, chapter by chapter.
Registered as a blueprint on the combined app (see benneria_web.app); not runnable on its own.

Endpoints:
    /api/toc                          books by part (Torah, Nevi'im, Ketuvim), with their chapter
                                      counts and which chapters have a notebook
    /api/notebooks/<book>/<chapter>   GET: the chapter's notebook, its verses and their notes
                                      (404 if not created yet)
                                      POST: create it, then return it
                                      DELETE: delete it, with its notes and tables
    /api/notebooks/<book>/<chapter>/notes/<verse>
                                      PUT {"text": "..."}: save the note after that verse
                                      (Markdown; empty text removes it)
    /api/notebooks/<book>/<chapter>/tables/<verse>
                                      PUT {"rows": [[cell, ...], ...]}: save that verse's verb
                                      table, one list of TABLE_COLUMNS cells per row (no rows
                                      removes it)

Bible text from bhsa.sqlite (read-only, CC BY-NC 4.0); the notebook's own data in a writable
database (store.py).
"""

from contextlib import closing
from importlib.resources import files

from flask import Blueprint, jsonify, request, send_file

from . import bhsa
from .store import Store

bp = Blueprint("notebook", __name__)

MAX_NOTE = 100_000  # characters in one note
# A verse's verb table: these columns (their headers are shown by the page), a few hundred rows.
TABLE_COLUMNS = ["verb", "root", "binyan", "tense", "person", "translation"]
MAX_ROWS = 200
MAX_CELL = 1_000

# The three parts of the Hebrew Bible, by their first book in BHSA's (canonical) order.
PARTS = [("torah", "Gen"), ("neviim", "Josh"), ("ketuvim", "Ps")]

_store = None


def store():
    """The notes database, opened on first use (so importing the app doesn't create files)."""
    global _store
    if _store is None:
        _store = Store()
    return _store


def books():
    """[(osis, number of chapters)] in canonical order."""
    with closing(bhsa.connect()) as db:
        return [(r["osis"], r["chapters"]) for r in db.execute(
            "SELECT b.osis, MAX(v.chapter) AS chapters FROM books b JOIN verses v ON v.book_id = b.id "
            "GROUP BY b.id ORDER BY b.id")]


BOOKS = books()
CHAPTERS = dict(BOOKS)


def error(status, message):
    response = jsonify({"error": message})
    response.status_code = status
    return response


def not_found(message):
    return error(404, message)


@bp.after_request
def no_store(response):
    # The notebook changes as you write in it; API answers must always be fresh.
    if response.mimetype == "application/json":
        response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/notebook")
def index():
    return send_file(files("benneria_notebook") / "static" / "index.html")


@bp.get("/api/toc")
def toc():
    created = store().created_chapters()
    starts = {first: part for part, first in PARTS}
    parts = []
    for osis, chapters in BOOKS:
        if osis in starts:
            parts.append({"id": starts[osis], "books": []})
        parts[-1]["books"].append({"osis": osis, "chapters": chapters, "created": created.get(osis, [])})
    return jsonify({"parts": parts})


def notebook(book, chapter):
    with closing(bhsa.connect()) as db:
        rows = bhsa.chapter_verses(db, book, chapter)
    notes = store().notes(book, chapter)
    tables = store().tables(book, chapter)
    return {"book": book, "chapter": chapter, "columns": TABLE_COLUMNS,
            "verses": [{"verse": v, "osis": osis, "text": text,
                        "note": notes.get(v, ""), "table": tables.get(v, [])}
                       for v, osis, text in rows]}


def verse_count(book, chapter):
    with closing(bhsa.connect()) as db:
        return db.execute("SELECT MAX(v.verse) FROM verses v JOIN books b ON b.id = v.book_id "
                          "WHERE b.osis = ? AND v.chapter = ?", (book, chapter)).fetchone()[0]


def check_chapter(book, chapter):
    if book not in CHAPTERS or not 1 <= chapter <= CHAPTERS[book]:
        return not_found(f"No such chapter: {book} {chapter}")
    return None


@bp.get("/api/notebooks/<book>/<int:chapter>")
def get_notebook(book, chapter):
    if (bad := check_chapter(book, chapter)) is not None:
        return bad
    if not store().is_created(book, chapter):
        return not_found("This chapter has no notebook yet")
    return jsonify(notebook(book, chapter))


@bp.post("/api/notebooks/<book>/<int:chapter>")
def create_notebook(book, chapter):
    if (bad := check_chapter(book, chapter)) is not None:
        return bad
    new = store().create(book, chapter)
    return jsonify(notebook(book, chapter)), (201 if new else 200)


def check_verse(book, chapter, verse):
    """An error response unless the verse exists, its chapter has a notebook, and the request is
    JSON (which a cross-site form can't send, so other sites can't write to the notebook)."""
    if (bad := check_chapter(book, chapter)) is not None:
        return bad
    if not store().is_created(book, chapter):
        return not_found("This chapter has no notebook yet")
    if not 1 <= verse <= verse_count(book, chapter):
        return not_found(f"No such verse: {book} {chapter}:{verse}")
    if not request.is_json:
        return error(415, "Send JSON")
    return None


@bp.put("/api/notebooks/<book>/<int:chapter>/notes/<int:verse>")
def save_note(book, chapter, verse):
    if (bad := check_verse(book, chapter, verse)) is not None:
        return bad
    text = (request.get_json(silent=True) or {}).get("text")
    if not isinstance(text, str):
        return error(400, "Missing 'text'")
    if len(text) > MAX_NOTE:
        return error(413, f"Note too long: at most {MAX_NOTE} characters")
    return jsonify({"verse": verse, "saved": store().set_note(book, chapter, verse, text)})


@bp.put("/api/notebooks/<book>/<int:chapter>/tables/<int:verse>")
def save_table(book, chapter, verse):
    if (bad := check_verse(book, chapter, verse)) is not None:
        return bad
    rows = (request.get_json(silent=True) or {}).get("rows")
    width = len(TABLE_COLUMNS)
    if not (isinstance(rows, list) and all(
            isinstance(row, list) and len(row) == width and all(isinstance(c, str) for c in row)
            for row in rows)):
        return error(400, f"'rows' must be a list of rows of {width} texts")
    if len(rows) > MAX_ROWS or any(len(c) > MAX_CELL for row in rows for c in row):
        return error(413, f"Table too large: at most {MAX_ROWS} rows of {MAX_CELL} characters per cell")
    return jsonify({"verse": verse, "saved": store().set_table(book, chapter, verse, rows)})


@bp.delete("/api/notebooks/<book>/<int:chapter>")
def delete_notebook(book, chapter):
    # DELETE can't be sent by a cross-site form or a plain link, so other sites can't trigger it.
    if (bad := check_chapter(book, chapter)) is not None:
        return bad
    removed = store().delete(book, chapter)
    if removed is None:
        return not_found("This chapter has no notebook")
    return jsonify({"book": book, "chapter": chapter, "deleted": removed})
