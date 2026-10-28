"""The BHS reader's web app: the page and its chapter endpoint."""

from contextlib import closing

import pytest

from benneria_notebook import bhsa
from benneria_web.app import app


@pytest.fixture(scope="module")
def client():
    return app.test_client()


def test_page_and_static_files(client):
    for path in ("/bhs", "/static/bhs.js", "/static/bhs-justify.js", "/static/bhs.css", "/static/books.js",
                 "/static/notebook.css", "/static/style.css"):
        assert client.get(path).status_code == 200


def test_chapter(client):
    r = client.get("/api/bhs/Gen/1")
    assert r.status_code == 200
    data = r.json
    assert data["book"] == "Gen" and data["chapter"] == 1
    assert len(data["verses"]) == 31
    v1 = data["verses"][0]
    assert v1["verse"] == 1 and v1["osis"] == "Gen.1.1"
    with closing(bhsa.connect()) as db:
        assert v1["text"] == bhsa.verse_text(db, "Gen.1.1")


def test_chapter_matches_bhsa_directly(client):
    # Reads the same way the notebook does (bhsa.chapter_verses), not its own query.
    with closing(bhsa.connect()) as db:
        expected = bhsa.chapter_verses(db, "Isa", 6)
    verses = client.get("/api/bhs/Isa/6").json["verses"]
    assert [(v["verse"], v["osis"], v["text"]) for v in verses] == expected


def test_errors(client):
    assert client.get("/api/bhs/Gen/51").status_code == 404     # Genesis has 50 chapters
    assert client.get("/api/bhs/Gen/0").status_code == 404
    assert client.get("/api/bhs/Matt/1").status_code == 404     # not in the Hebrew Bible
