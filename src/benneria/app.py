"""
The web app (Flask): serves the page from static/ and looks words up in data/lexicon.sqlite.

Endpoints:
    /api/lookup?word=...    search (options: lookup_ref, always_consonants, always_split,
                            never_split, strip_prefixes)
    /api/entry?id=|bdb=|strong=...   the entries a cross-reference names

Caching: an API answer depends only on its query, the data and the search code, so it is
cacheable for a day, with an ETag identifying that data and code (API_VERSION). A client
revalidating with that ETag gets 304 Not Modified without the search running. Static files are
revalidated on each use (no-cache plus ETag/Last-Modified), so a changed file is picked up at once.
Errors are not cached.

`app` is a WSGI application, so any WSGI server can run it. For development:
    uv run benneria
"""

import hashlib
import sqlite3
from importlib.resources import files

from flask import Flask, jsonify, request

from .local import DB_PATH, InputTooLong, LocalLexicon
from .refs import RefError

API_MAX_AGE = 86400  # seconds a browser or proxy may reuse an API answer without asking again

app = Flask(__name__, static_folder="static", static_url_path="/static")
# Keep Hebrew readable in responses and the entries' field order as built.
app.json.ensure_ascii = False
app.json.sort_keys = False

# One read-only connection per thread or worker process, opened on first use.
lexicon = LocalLexicon()


def api_version():
    """A short hash of what API answers depend on: the database (its source commits and schema,
    from its meta table) and the search code. A rebuilt database or changed code changes it."""
    h = hashlib.sha256()
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        for key, value in db.execute("SELECT key, value FROM meta ORDER BY key"):
            h.update(f"{key}={value}\n".encode())
    finally:
        db.close()
    for module in ("local.py", "refs.py", "hebrew.py", "app.py"):
        h.update((files("benneria") / module).read_bytes())
    return h.hexdigest()[:16]


API_VERSION = api_version()


def error(message):
    response = jsonify({"error": message})
    response.status_code = 400
    response.headers["Cache-Control"] = "no-store"
    return response


def not_modified():
    """True when the client already holds answers for this API_VERSION."""
    return API_VERSION in request.if_none_match


def api_response(data=None):
    """A cacheable API answer, or 304 Not Modified when the client's copy is current."""
    response = jsonify(data) if data is not None else app.response_class(status=304)
    response.set_etag(API_VERSION)
    response.cache_control.public = True
    response.cache_control.max_age = API_MAX_AGE
    return response


@app.get("/")
@app.get("/index.html")
def index():
    return app.send_static_file("index.html")


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/api/lookup")
def lookup():
    args = request.args
    word = args.get("word", "").strip()
    if not word:
        return error("Missing 'word' parameter")
    if not_modified():
        return api_response()
    flag = lambda k: args.get(k) == "1"
    try:
        result = lexicon.search(
            word, lookup_ref=args.get("lookup_ref") or None, always_consonants=flag("always_consonants"),
            always_split=flag("always_split"), never_split=flag("never_split"),
            strip_prefixes=args.get("strip_prefixes") != "0")
    except (RefError, InputTooLong) as e:
        return error(str(e))
    return api_response(result)


@app.get("/api/entry")
def entry():
    # Cross-references between entries: exactly one of ?id=, ?bdb= or ?strong=.
    keys = {k: request.args[k] for k in ("id", "bdb", "strong") if request.args.get(k)}
    if len(keys) != 1:
        return error("Give one of id, bdb or strong")
    if not_modified():
        return api_response()
    kind, value = keys.popitem()
    return api_response(lexicon.open(**{"entry_id" if kind == "id" else kind: value}))
