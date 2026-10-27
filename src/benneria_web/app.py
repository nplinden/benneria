"""
The combined web app (Flask): the landing page at /, the dictionary at /lexicon, the notebook at
/notebook, the BHS reader at /bhs, and verb-form statistics at /stats, with each app's own API
under /api/ (no path overlaps between them: see benneria.app, benneria_notebook.app,
benneria_bhs.app and benneria_stats.app).

Static files are served from all four apps' static/ directories under one /static/ (their file
names don't collide), plus this package's own static/index.html for the landing page.

`app` is a WSGI application, so any WSGI server can run it. For development:
    uv run benneria
"""

from importlib.resources import files

from flask import Flask, send_file, send_from_directory
from werkzeug.exceptions import NotFound

from benneria.app import bp as lexicon_bp
from benneria_bhs.app import bp as bhs_bp
from benneria_notebook.app import bp as notebook_bp
from benneria_stats.app import bp as stats_bp

app = Flask(__name__, static_folder=None)  # replaced below by a route covering all apps' static/
# Keep Hebrew readable in responses and the entries' field order as built.
app.json.ensure_ascii = False
app.json.sort_keys = False

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
