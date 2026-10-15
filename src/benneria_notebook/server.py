"""
Development server: `uv run benneria-notebook` runs the notebook app (app.py) with Flask's built-in
server.

Run:
    uv run benneria-notebook                  # http://127.0.0.1:1526
    uv run benneria-notebook --port 9001 --open
"""

import argparse
import threading
import webbrowser

from .app import app


def main():
    ap = argparse.ArgumentParser(description="Benneria Notebook: notes on Biblical verses")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1526)
    ap.add_argument("--open", action="store_true", help="open the browser on start")
    args = ap.parse_args()

    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}/"
    print(f"Benneria Notebook running at {url}  (Ctrl+C to stop)")
    if args.open:
        threading.Timer(1, webbrowser.open, (url,)).start()
    app.run(host=args.host, port=args.port, threaded=True)
