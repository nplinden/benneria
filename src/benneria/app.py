"""
The web app (Flask): serves the page from static/ and looks words up in data/lexicon.sqlite.

Endpoints:
    /api/lookup?word=...    search (options: lookup_ref, always_consonants, always_split,
                            never_split, strip_prefixes)
    /api/entry?id=|bdb=|strong=...   the entries a cross-reference names

`app` is a WSGI application, so any WSGI server can run it. For development:
    uv run benneria
"""

from flask import Flask, jsonify, request

from .local import LocalLexicon
from .refs import RefError

app = Flask(__name__, static_folder="static", static_url_path="/static")
# Keep Hebrew readable in responses and the entries' field order as built.
app.json.ensure_ascii = False
app.json.sort_keys = False

# One read-only connection per thread or worker process, opened on first use.
lexicon = LocalLexicon()


def error(message):
    return jsonify({"error": message}), 400


@app.after_request
def no_store(response):
    # Nothing is cached yet (as with the previous server); caching is a separate change.
    response.headers["Cache-Control"] = "no-store"
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
    flag = lambda k: args.get(k) == "1"
    try:
        result = lexicon.search(
            word, lookup_ref=args.get("lookup_ref") or None, always_consonants=flag("always_consonants"),
            always_split=flag("always_split"), never_split=flag("never_split"),
            strip_prefixes=args.get("strip_prefixes") != "0")
    except RefError as e:
        return error(str(e))
    return jsonify(result)


@app.get("/api/entry")
def entry():
    # Cross-references between entries: exactly one of ?id=, ?bdb= or ?strong=.
    keys = {k: request.args[k] for k in ("id", "bdb", "strong") if request.args.get(k)}
    if len(keys) != 1:
        return error("Give one of id, bdb or strong")
    kind, value = keys.popitem()
    return jsonify(lexicon.open(**{"entry_id" if kind == "id" else kind: value}))
