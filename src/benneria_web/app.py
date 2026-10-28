"""
The combined web app (Flask): the landing page at /, the dictionary at /lexicon, the notebook at
/notebook, the BHS reader at /bhs, and verb-form statistics at /stats, with each app's own API
under /api/ (no path overlaps between them: see benneria.app, benneria_notebook.app,
benneria_bhs.app and benneria_stats.app).

Static files are served from all four apps' static/ directories under one /static/ (their file
names don't collide), plus this package's own static/index.html for the landing page.

Logins (the notebook's) are Flask's signed session cookies. Settings, from the environment:
    BENNERIA_SECRET_KEY      the key signing them; by default a random one is made on first use
                             and kept next to the notebook's database (see secret_key)
    BENNERIA_SECURE_COOKIES  1: send the session cookie over HTTPS only. Set it when the site is
                             served over HTTPS, as it should be wherever passwords cross a network

`app` is a WSGI application, so any WSGI server can run it. For development:
    uv run benneria
"""

import datetime
import os
from importlib.resources import files

from flask import Flask, send_file, send_from_directory
from flask.sessions import SecureCookieSessionInterface
from werkzeug.exceptions import NotFound

from benneria.app import bp as lexicon_bp
from benneria_bhs.app import bp as bhs_bp
from benneria_notebook.app import bp as notebook_bp
from benneria_notebook.store import default_path
from benneria_stats.app import bp as stats_bp


def secret_key():
    """$BENNERIA_SECRET_KEY, or else the key in a file next to the notebook's database, made the
    first time (random, readable by its owner only). Kept, so logins survive a restart, and the
    same for every server process, so any of them can read a session another one signed."""
    if os.environ.get("BENNERIA_SECRET_KEY"):
        return os.environ["BENNERIA_SECRET_KEY"]
    path = default_path().parent / "secret_key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written in full under another name, then linked into place: a process starting at the
        # same moment either finds no file or the complete one, never a half-written one.
        tmp = path.with_name(f".secret_key.{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(os.urandom(32).hex())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # another process made it first: use theirs
        finally:
            os.unlink(tmp)
    return path.read_text().strip()


class Sessions(SecureCookieSessionInterface):
    """Flask's signed-cookie sessions, with the key loaded when first needed rather than when the
    app is imported (importing it creates no files)."""

    def get_signing_serializer(self, app):
        if not app.secret_key:
            app.secret_key = secret_key()
        return super().get_signing_serializer(app)


app = Flask(__name__, static_folder=None)  # replaced below by a route covering all apps' static/
# Keep Hebrew readable in responses and the entries' field order as built.
app.json.ensure_ascii = False
app.json.sort_keys = False

app.session_interface = Sessions()
app.config.update(
    SESSION_COOKIE_NAME="benneria_session",
    SESSION_COOKIE_HTTPONLY=True,       # out of reach of the pages' scripts
    SESSION_COOKIE_SAMESITE="Lax",      # not sent with other sites' requests: no cross-site writes
    SESSION_COOKIE_SECURE=os.environ.get("BENNERIA_SECURE_COOKIES") == "1",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),  # from the last visit
)

app.register_blueprint(lexicon_bp)
app.register_blueprint(notebook_bp)
app.register_blueprint(bhs_bp)
app.register_blueprint(stats_bp)

# Directories searched, in order, for a /static/<path> request (no file names collide).
STATIC_DIRS = [files("benneria") / "static", files("benneria_notebook") / "static",
               files("benneria_bhs") / "static", files("benneria_stats") / "static"]


@app.get("/")
def home():
    return send_file(files("benneria_web") / "static" / "index.html")


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/static/<path:filename>")
def static_files(filename):
    for directory in STATIC_DIRS:
        try:
            return send_from_directory(directory, filename)
        except NotFound:
            continue
    raise NotFound()
