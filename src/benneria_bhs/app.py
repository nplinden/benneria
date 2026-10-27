"""
The BHS reader's part of the combined web app: the page at /bhs, showing one chapter of the
Hebrew Bible text at a time, nothing else (no notes, no verb tables, no need for a notebook to
exist there). Registered as a blueprint on the combined app (see benneria_web.app); not runnable
on its own.

Endpoint:
    /api/bhs/<book>/<chapter>   that chapter's verses, in order

Bible text from bhsa.sqlite (read-only, CC BY-NC 4.0), the same source and book list as the
notebook (benneria_notebook): its /api/toc already lists every book with its chapter count, so
this app's page fetches that instead of repeating it here.
"""

from contextlib import closing
from importlib.resources import files

from flask import Blueprint, jsonify, send_file

from benneria_notebook import bhsa
from benneria_notebook.app import CHAPTERS

bp = Blueprint("bhs", __name__)


def not_found(message):
    response = jsonify({"error": message})
    response.status_code = 404
    return response


@bp.get("/bhs")
def index():
    return send_file(files("benneria_bhs") / "static" / "index.html")


@bp.get("/api/bhs/<book>/<int:chapter>")
def chapter(book, chapter):
    if book not in CHAPTERS or not 1 <= chapter <= CHAPTERS[book]:
        return not_found(f"No such chapter: {book} {chapter}")
    with closing(bhsa.connect()) as db:
        rows = bhsa.chapter_verses(db, book, chapter)
    return jsonify({"book": book, "chapter": chapter,
                    "verses": [{"verse": v, "osis": osis, "text": text} for v, osis, text in rows]})
