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


def test_api_answers_are_cacheable_and_revalidate(client):
    from benneria.app import API_MAX_AGE, API_VERSION
    for path, params in [("/api/lookup", {"word": "שמר"}), ("/api/entry", {"strong": "1254"})]:
        r = client.get(path, query_string=params)
        assert r.status_code == 200
        assert r.headers["ETag"] == f'"{API_VERSION}"'
        assert r.cache_control.public and r.cache_control.max_age == API_MAX_AGE
        again = client.get(path, query_string=params, headers={"If-None-Match": r.headers["ETag"]})
        assert again.status_code == 304 and again.get_data() == b""
        stale = client.get(path, query_string=params, headers={"If-None-Match": '"old-version"'})
        assert stale.status_code == 200


def test_errors_are_not_cached(client):
    assert client.get("/api/lookup").headers["Cache-Control"] == "no-store"
    assert client.get("/api/entry").headers["Cache-Control"] == "no-store"


def test_static_files_revalidate(client):
    for path in ("/", "/static/app.js"):
        r = client.get(path)
        assert r.headers["Cache-Control"] == "no-cache" and r.headers.get("ETag")
        assert client.get(path, headers={"If-None-Match": r.headers["ETag"]}).status_code == 304


def test_input_too_long(client):
    status, _, body = get(client, "/api/lookup", word=" ".join(["שמר"] * 21))
    assert status == 400 and "Input too long" in json.loads(body)["error"]
    assert get(client, "/api/lookup", word="א" * 301)[0] == 400
    assert get(client, "/api/lookup", word=" ".join(["שמר"] * 20))[0] == 200
