"""
HTTP server: serves the web UI from static/ and the /api/lookup endpoint.

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

from .lookup import fetch_words

STATIC = files("benneria") / "static"
# Only these files are served, so request paths never reach the filesystem directly.
STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "labels.js": "text/javascript; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "Benneria/1.0"

    def _send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name):
        return self._send(200, (STATIC / name).read_bytes(), STATIC_TYPES[name])

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send_static("index.html")
        if parsed.path.startswith("/static/") and parsed.path[len("/static/"):] in STATIC_TYPES:
            return self._send_static(parsed.path[len("/static/"):])
        if parsed.path == "/api/lookup":
            qs = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            word = qs.pop("word", "").strip()
            if not word:
                body = json.dumps({"error": "Missing 'word' parameter"}).encode()
                return self._send(400, body, "application/json")
            status, body = fetch_words(word, qs)
            return self._send(status, body, "application/json; charset=utf-8")
        if parsed.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        self._send(404, b"Not found", "text/plain")

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser(description="Benneria: a Hebrew and Aramaic dictionary web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser on start")
    args = ap.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
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
