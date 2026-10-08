"""
HTTP server: serves the web UI from static/ and looks words up in data/lexicon.sqlite.

Endpoints:
    /api/lookup?word=...    search (options: lookup_ref, always_consonants, always_split,
                            never_split, strip_prefixes)
    /api/entry?id=|bdb=|strong=...   the entries a cross-reference names

Run:
    uv run benneria                           # http://127.0.0.1:8000
    uv run benneria --port 9000 --host 0.0.0.0 --open
"""

import argparse
import json
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from .local import LocalLexicon
from .refs import RefError

STATIC = files("benneria") / "static"
# Only these files are served, so request paths never reach the filesystem directly.
STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "labels.js": "text/javascript; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
JSON = "application/json; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    """Expects the server to have a `lexicon` attribute (a LocalLexicon)."""

    server_version = "Benneria/1.0"

    def _send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, data):
        return self._send(status, json.dumps(data, ensure_ascii=False).encode(), JSON)

    def _send_static(self, name):
        return self._send(200, (STATIC / name).read_bytes(), STATIC_TYPES[name])

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        if parsed.path in ("/", "/index.html"):
            return self._send_static("index.html")
        if parsed.path.startswith("/static/") and parsed.path[len("/static/"):] in STATIC_TYPES:
            return self._send_static(parsed.path[len("/static/"):])
        if parsed.path == "/api/lookup":
            return self._lookup(qs)
        if parsed.path == "/api/entry":
            return self._entry(qs)
        if parsed.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        self._send(404, b"Not found", "text/plain")

    def _lookup(self, qs):
        word = qs.get("word", "").strip()
        if not word:
            return self._send_json(400, {"error": "Missing 'word' parameter"})
        flag = lambda k: qs.get(k) == "1"
        try:
            result = self.server.lexicon.search(
                word, lookup_ref=qs.get("lookup_ref") or None, always_consonants=flag("always_consonants"),
                always_split=flag("always_split"), never_split=flag("never_split"),
                strip_prefixes=qs.get("strip_prefixes") != "0")
        except RefError as e:
            return self._send_json(400, {"error": str(e)})
        return self._send_json(200, result)

    def _entry(self, qs):
        # Cross-references between entries: exactly one of ?id=, ?bdb= or ?strong=.
        keys = {k: qs[k] for k in ("id", "bdb", "strong") if qs.get(k)}
        if len(keys) != 1:
            return self._send_json(400, {"error": "Give one of id, bdb or strong"})
        kind, value = keys.popitem()
        return self._send_json(200, self.server.lexicon.open(**{"entry_id" if kind == "id" else kind: value}))

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser(description="Benneria: a Hebrew and Aramaic dictionary web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser on start")
    args = ap.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.lexicon = LocalLexicon()
    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}/"
    print(f"Benneria running at {url}  (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.server_close()


if __name__ == "__main__":
    main()
