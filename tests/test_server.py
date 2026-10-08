"""HTTP endpoints, through Flask's test client."""

import json

import pytest

from benneria.app import app


@pytest.fixture(scope="module")
def client():
    return app.test_client()


def get(client, path, **params):
    resp = client.get(path, query_string=params)
    return resp.status_code, resp.headers.get("Content-Type"), resp.get_data()


def test_page_and_static_files(client):
    for path in ("/", "/static/app.js", "/static/labels.js", "/static/style.css"):
        assert get(client, path)[0] == 200


def test_only_static_files_are_served(client):
    assert get(client, "/static/../server.py")[0] == 404
    assert get(client, "/static/index.htm")[0] == 404


def test_lookup(client):
    status, ctype, body = get(client, "/api/lookup", word="וַיִּשְׁמְרוּ", always_consonants="1")
    data = json.loads(body)
    assert status == 200 and ctype.startswith("application/json")
    assert data["results"][0]["strong"] == "8104"
    assert "שָׁמַר".encode() in body  # Hebrew sent as is, not as \u escapes


def test_lookup_errors(client):
    assert get(client, "/api/lookup")[0] == 400
    status, _, body = get(client, "/api/lookup", word="בָּרָא", lookup_ref="Matthew 1:1")
    assert status == 400 and "Unknown book" in json.loads(body)["error"]


def test_entry(client):
    data = json.loads(get(client, "/api/entry", strong="1254")[2])
    assert {e["gloss"] for e in data["results"]} == {"shape", "be fat"}
    assert get(client, "/api/entry")[0] == 400
    assert get(client, "/api/entry", id="nbf", bdb="x")[0] == 400


def test_responses_are_not_cached(client):
    assert client.get("/api/lookup", query_string={"word": "שמר"}).headers["Cache-Control"] == "no-store"
    assert client.get("/static/app.js").headers["Cache-Control"] == "no-store"
