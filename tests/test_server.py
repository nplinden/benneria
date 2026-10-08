"""HTTP endpoints, with the server running in a thread."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from benneria.local import LocalLexicon
from benneria.server import Handler


@pytest.fixture(scope="module")
def base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.lexicon = LocalLexicon()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def get(base_url, path, **params):
    url = base_url + path + ("?" + urllib.parse.urlencode(params) if params else "")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def test_page_and_static_files(base_url):
    for path in ("/", "/static/app.js", "/static/labels.js", "/static/style.css"):
        assert get(base_url, path)[0] == 200


def test_only_listed_static_files_are_served(base_url):
    assert get(base_url, "/static/../server.py")[0] == 404
    assert get(base_url, "/static/index.htm")[0] == 404


def test_lookup(base_url):
    status, ctype, body = get(base_url, "/api/lookup", word="וַיִּשְׁמְרוּ", always_consonants="1")
    data = json.loads(body)
    assert status == 200 and ctype.startswith("application/json")
    assert data["results"][0]["strong"] == "8104"


def test_lookup_errors(base_url):
    assert get(base_url, "/api/lookup")[0] == 400
    status, _, body = get(base_url, "/api/lookup", word="בָּרָא", lookup_ref="Matthew 1:1")
    assert status == 400 and "Unknown book" in json.loads(body)["error"]


def test_entry(base_url):
    data = json.loads(get(base_url, "/api/entry", strong="1254")[2])
    assert {e["gloss"] for e in data["results"]} == {"shape", "be fat"}
    assert get(base_url, "/api/entry")[0] == 400
    assert get(base_url, "/api/entry", id="nbf", bdb="x")[0] == 400
