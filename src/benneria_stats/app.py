"""
The statistics app's part of the combined web app: the page at /stats. Registered as a
blueprint on the combined app (see benneria_web.app); not runnable on its own.

Endpoints:
    /api/stats/roots            every verb root's occurrences per common binyan, and its total
    /api/stats/chart?root=...   the binyan/tense breakdown; repeat ?root= to restrict the count
                                 to several roots, omit it for every root

A root's dictionary definition isn't served here: the page looks it up the same way the
dictionary does, through /api/entry?root=... (see benneria.app and benneria.local.LocalLexicon.open).
"""

from importlib.resources import files

from flask import Blueprint, jsonify, request, send_file

from . import stats

bp = Blueprint("stats", __name__)


@bp.get("/stats")
def index():
    return send_file(files("benneria_stats") / "static" / "index.html")


@bp.get("/api/stats/roots")
def roots():
    return jsonify({"binyanim": stats.BINYANIM, "roots": stats.ROOT_BINYAN_COUNTS})


@bp.get("/api/stats/chart")
def chart():
    return jsonify({"tenses": stats.TENSES,
                     "data": stats.binyan_tense_counts(request.args.getlist("root"))})
