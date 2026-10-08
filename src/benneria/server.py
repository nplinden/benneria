"""
Development server: `uv run benneria` runs the Flask app (app.py) with Flask's built-in server.

Run:
    uv run benneria                           # http://127.0.0.1:8000
    uv run benneria --port 9000 --host 0.0.0.0 --open
"""

import argparse
import threading
import webbrowser

from .app import app


def main():
    ap = argparse.ArgumentParser(description="Benneria: a Hebrew and Aramaic dictionary web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser on start")
    args = ap.parse_args()

    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}/"
    print(f"Benneria running at {url}  (Ctrl+C to stop)")
    if args.open:
        threading.Timer(1, webbrowser.open, (url,)).start()  # once the server is listening
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
