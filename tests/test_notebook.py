"""Benneria Notebook's web app: table of contents, creating and opening chapter notebooks."""

import json

import pytest

import benneria_notebook.app as notebook_app
from benneria_notebook.store import Store
from benneria_web.app import app as web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # A fresh notes database for each test, never the real one.
    monkeypatch.setattr(notebook_app, "_store", Store(tmp_path / "notebook.sqlite"))
    return web_app.test_client()


def test_page_and_styles(client):
    for path in ("/notebook", "/static/notebook.js", "/static/books.js", "/static/notebook.css"):
        assert client.get(path).status_code == 200
    css = client.get("/static/style.css")
    assert css.status_code == 200 and b"--accent" in css.data  # the dictionary's stylesheet,
    # shared with the notebook rather than duplicated


def test_toc_parts(client):
    parts = client.get("/api/toc").json["parts"]
    assert [p["id"] for p in parts] == ["torah", "neviim", "ketuvim"]
    assert [len(p["books"]) for p in parts] == [5, 21, 13]
    isaiah = next(b for p in parts for b in p["books"] if b["osis"] == "Isa")
    assert isaiah == {"osis": "Isa", "chapters": 66, "created": []}


def test_create_then_open(client):
    assert client.get("/api/notebooks/Isa/6").status_code == 404  # not created yet
    created = client.post("/api/notebooks/Isa/6")
    assert created.status_code == 201
    verses = created.json["verses"]
    assert len(verses) == 13 and verses[5]["osis"] == "Isa.6.6"
    assert client.post("/api/notebooks/Isa/6").status_code == 200  # already exists: nothing new
    opened = client.get("/api/notebooks/Isa/6")
    assert opened.status_code == 200 and opened.json == created.json
    isaiah = next(b for p in client.get("/api/toc").json["parts"] for b in p["books"] if b["osis"] == "Isa")
    assert isaiah["created"] == [6]


def test_invalid_chapters(client):
    assert client.get("/api/notebooks/Isa/67").status_code == 404
    assert client.post("/api/notebooks/Isa/0").status_code == 404
    assert client.post("/api/notebooks/Matt/1").status_code == 404


def test_api_answers_are_not_cached(client):
    assert client.get("/api/toc").headers["Cache-Control"] == "no-store"


def test_store_persists(tmp_path):
    path = tmp_path / "notes.sqlite"
    assert Store(path).create("Gen", 1) is True
    assert Store(path).create("Gen", 1) is False  # a second process sees the first one's write
    assert Store(path).created_chapters() == {"Gen": [1]}


def test_store_location(tmp_path, monkeypatch):
    monkeypatch.setenv("BENNERIA_NOTEBOOK_DB", str(tmp_path / "x.sqlite"))
    assert Store().path == tmp_path / "x.sqlite"
    monkeypatch.delenv("BENNERIA_NOTEBOOK_DB")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert Store().path == tmp_path / "data" / "benneria-notebook" / "notebook.sqlite"


def put_note(client, book, chapter, verse, text, **kw):
    return client.put(f"/api/notebooks/{book}/{chapter}/notes/{verse}", json={"text": text}, **kw)


def test_notes_save_and_load(client):
    client.post("/api/notebooks/Isa/6")
    note = "Il vola vers moi depuis les *séraphins*, une pierre chaude dans sa main."
    r = put_note(client, "Isa", 6, 6, note)
    assert r.status_code == 200 and r.json["verse"] == 6 and r.json["saved"]
    verses = client.get("/api/notebooks/Isa/6").json["verses"]
    assert verses[5]["note"] == note and verses[4]["note"] == ""
    put_note(client, "Isa", 6, 6, note + " (révisé)")  # saving again replaces it
    assert client.get("/api/notebooks/Isa/6").json["verses"][5]["note"].endswith("(révisé)")


def test_empty_note_is_removed(client):
    client.post("/api/notebooks/Gen/1")
    put_note(client, "Gen", 1, 1, "au commencement")
    assert put_note(client, "Gen", 1, 1, "   \n").status_code == 200
    assert client.get("/api/notebooks/Gen/1").json["verses"][0]["note"] == ""
    assert notebook_app.store().notes("Gen", 1) == {}


def test_note_errors(client):
    assert put_note(client, "Isa", 6, 6, "x").status_code == 404           # notebook not created
    client.post("/api/notebooks/Isa/6")
    assert put_note(client, "Isa", 6, 14, "x").status_code == 404          # Isaiah 6 has 13 verses
    assert put_note(client, "Isa", 6, 0, "x").status_code == 404
    assert client.put("/api/notebooks/Isa/6/notes/1", data="text=x").status_code == 415  # not JSON
    assert client.put("/api/notebooks/Isa/6/notes/1", json={"txt": "x"}).status_code == 400
    assert put_note(client, "Isa", 6, 1, "x" * (notebook_app.MAX_NOTE + 1)).status_code == 413


def test_notes_are_per_chapter(client):
    client.post("/api/notebooks/Isa/6")
    client.post("/api/notebooks/Isa/7")
    put_note(client, "Isa", 6, 1, "six")
    put_note(client, "Isa", 7, 1, "sept")
    assert client.get("/api/notebooks/Isa/6").json["verses"][0]["note"] == "six"
    assert client.get("/api/notebooks/Isa/7").json["verses"][0]["note"] == "sept"


def put_table(client, book, chapter, verse, rows):
    return client.put(f"/api/notebooks/{book}/{chapter}/tables/{verse}", json={"rows": rows})


def test_tables_save_and_load(client):
    created = client.post("/api/notebooks/Isa/6").json
    assert created["columns"] == ["verb", "root", "binyan", "tense", "person", "translation"]
    assert all(v["table"] == [] for v in created["verses"])
    rows = [["וְקָרָא", "קרא", "Paal", "Accompli inversif", "3MS", "Il appellera"],
            ["וְאָמַר", "אמר", "Paal", "Accompli inversif", "3MS", "Il dira"]]
    r = put_table(client, "Isa", 6, 3, rows)
    assert r.status_code == 200 and r.json["verse"] == 3
    verses = client.get("/api/notebooks/Isa/6").json["verses"]
    assert verses[2]["table"] == rows and verses[1]["table"] == []
    put_table(client, "Isa", 6, 3, rows[:1])  # a row removed
    assert client.get("/api/notebooks/Isa/6").json["verses"][2]["table"] == rows[:1]
    put_table(client, "Isa", 6, 3, [])         # the last row removed: no table
    assert notebook_app.store().tables("Isa", 6) == {}


def test_table_errors(client):
    row = [""] * 6
    assert put_table(client, "Isa", 6, 1, [row]).status_code == 404      # notebook not created
    client.post("/api/notebooks/Isa/6")
    assert put_table(client, "Isa", 6, 14, [row]).status_code == 404     # no such verse
    assert put_table(client, "Isa", 6, 1, [[""] * 5]).status_code == 400  # wrong number of cells
    assert put_table(client, "Isa", 6, 1, [[1, 2, 3, 4, 5, 6]]).status_code == 400
    assert put_table(client, "Isa", 6, 1, "rows").status_code == 400
    assert put_table(client, "Isa", 6, 1, [row] * (notebook_app.MAX_ROWS + 1)).status_code == 413
    assert put_table(client, "Isa", 6, 1, [["x" * (notebook_app.MAX_CELL + 1)] + [""] * 5]).status_code == 413
    assert client.put("/api/notebooks/Isa/6/tables/1", data="rows=x").status_code == 415


def test_tables_and_notes_are_independent(client):
    client.post("/api/notebooks/Isa/6")
    put_note(client, "Isa", 6, 1, "une note")
    put_table(client, "Isa", 6, 1, [["a"] * 6])
    v1 = client.get("/api/notebooks/Isa/6").json["verses"][0]
    assert v1["note"] == "une note" and v1["table"] == [["a"] * 6]
    put_table(client, "Isa", 6, 1, [])
    assert client.get("/api/notebooks/Isa/6").json["verses"][0]["note"] == "une note"


def test_delete_notebook(client):
    client.post("/api/notebooks/Isa/6")
    client.post("/api/notebooks/Isa/7")
    put_note(client, "Isa", 6, 1, "une note")
    put_note(client, "Isa", 6, 2, "une autre")
    put_table(client, "Isa", 6, 3, [["a"] * 6])
    put_note(client, "Isa", 7, 1, "à garder")
    r = client.delete("/api/notebooks/Isa/6")
    assert r.status_code == 200 and r.json["deleted"] == {"notes": 2, "tables": 1}
    assert client.get("/api/notebooks/Isa/6").status_code == 404           # gone
    assert notebook_app.store().notes("Isa", 6) == {} and notebook_app.store().tables("Isa", 6) == {}
    isaiah = next(b for p in client.get("/api/toc").json["parts"] for b in p["books"] if b["osis"] == "Isa")
    assert isaiah["created"] == [7]                                        # greyed again; 7 untouched
    assert client.get("/api/notebooks/Isa/7").json["verses"][0]["note"] == "à garder"
    recreated = client.post("/api/notebooks/Isa/6")                        # a fresh, empty notebook
    assert recreated.status_code == 201
    assert all(v["note"] == "" and v["table"] == [] for v in recreated.json["verses"])


def test_delete_errors(client):
    assert client.delete("/api/notebooks/Isa/6").status_code == 404   # no notebook
    assert client.delete("/api/notebooks/Isa/99").status_code == 404  # no such chapter
