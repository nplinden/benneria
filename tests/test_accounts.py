"""The notebook's accounts: logging in and out, each account's own notebooks, the lockout, the
migration of a notebook from before accounts, the session key, and the benneria-user command."""

import sqlite3

import pytest

import benneria_notebook.app as notebook_app
from benneria_notebook import users
from benneria_notebook.store import MAX_FAILURES, Store
from benneria_web.app import app as web_app, secret_key


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = Store(tmp_path / "notebook.sqlite")
    monkeypatch.setattr(notebook_app, "_store", store)
    store.add_user("alice", "alice-password")
    store.add_user("bob", "bob-password")
    return store


def login(client, name, password):
    return client.post("/api/login", json={"name": name, "password": password})


def logged_in(name, password):
    client = web_app.test_client()
    assert login(client, name, password).status_code == 200
    return client


def test_logged_out(store):
    client = web_app.test_client()
    r = client.get("/notebook?c=Isa.6")
    assert r.status_code == 302 and r.headers["Location"] == "/login?next=%2Fnotebook%3Fc%3DIsa.6"
    assert client.get("/login").status_code == 200
    assert client.get("/api/notebooks/Isa/6").status_code == 401
    assert client.post("/api/notebooks/Isa/6").status_code == 401
    assert client.put("/api/notebooks/Isa/6/notes/1", json={"text": "x"}).status_code == 401
    assert client.delete("/api/notebooks/Isa/6").status_code == 401
    # The table of contents stays open (BHS reads its book list), with nobody's chapters.
    toc = client.get("/api/toc").json
    assert toc["user"] is None and all(b["created"] == [] for p in toc["parts"] for b in p["books"])


def test_login_and_logout(store):
    client = web_app.test_client()
    r = login(client, "Alice ", "alice-password")  # the name's case and spaces don't matter
    assert r.status_code == 200 and r.json == {"name": "alice"}
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert client.get("/notebook").status_code == 200
    assert client.get("/api/toc").json["user"] == "alice"
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/notebooks/Isa/6").status_code == 401


def test_login_errors(store):
    client = web_app.test_client()
    assert login(client, "alice", "wrong").status_code == 401
    assert login(client, "nobody", "alice-password").status_code == 401
    assert login(client, "alice", "ALICE-PASSWORD").status_code == 401  # passwords are exact
    assert client.post("/api/login", data={"name": "alice", "password": "alice-password"}).status_code == 415
    assert client.post("/api/login", json={"name": "alice"}).status_code == 400


def test_each_account_has_its_own_notebooks(store):
    alice, bob = logged_in("alice", "alice-password"), logged_in("bob", "bob-password")
    alice.post("/api/notebooks/Isa/6")
    alice.put("/api/notebooks/Isa/6/notes/1", json={"text": "la note d'Alice"})
    assert bob.get("/api/notebooks/Isa/6").status_code == 404            # not bob's
    assert bob.put("/api/notebooks/Isa/6/notes/1", json={"text": "x"}).status_code == 404
    assert bob.delete("/api/notebooks/Isa/6").status_code == 404
    bob.post("/api/notebooks/Isa/6")                                       # his own, empty
    assert bob.get("/api/notebooks/Isa/6").json["verses"][0]["note"] == ""
    assert alice.get("/api/notebooks/Isa/6").json["verses"][0]["note"] == "la note d'Alice"
    bob.delete("/api/notebooks/Isa/6")
    assert alice.get("/api/notebooks/Isa/6").status_code == 200           # untouched
    isaiah = lambda c: next(b for p in c.get("/api/toc").json["parts"] for b in p["books"] if b["osis"] == "Isa")
    assert isaiah(alice)["created"] == [6] and isaiah(bob)["created"] == []


def test_lockout(store):
    client = web_app.test_client()
    for _ in range(MAX_FAILURES):
        assert login(client, "alice", "wrong").status_code == 401
    assert login(client, "alice", "alice-password").status_code == 429   # even the right one
    assert login(client, "bob", "bob-password").status_code == 200       # only that account
    store.set_password("alice", "new-password")                          # ends the lockout
    assert login(client, "alice", "new-password").status_code == 200


def test_new_password_or_removed_account_ends_sessions(store):
    alice, bob = logged_in("alice", "alice-password"), logged_in("bob", "bob-password")
    store.set_password("alice", "new-password")
    assert alice.get("/api/toc").json["user"] is None
    assert alice.get("/api/notebooks/Isa/6").status_code == 401
    store.remove_user("bob")
    assert bob.get("/api/notebooks/Isa/6").status_code == 401


def test_remove_user(store):
    bob = logged_in("bob", "bob-password")
    bob.post("/api/notebooks/Isa/6")
    bob.put("/api/notebooks/Isa/6/notes/2", json={"text": "x"})
    assert store.remove_user("bob") == {"chapters": 1, "notes": 1, "tables": 0}
    assert store.remove_user("bob") is None
    # A new account never gets a removed one's id, so never its data.
    assert store.add_user("bob", "bob-password-2") == 3
    with pytest.raises(ValueError):
        store.add_user("BOB", "whatever-password")


def test_migration_from_before_accounts(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as db:  # the notebook's schema before accounts
        db.executescript("""
            CREATE TABLE chapters (book TEXT NOT NULL, chapter INTEGER NOT NULL, created TEXT NOT NULL,
                PRIMARY KEY (book, chapter));
            CREATE TABLE notes (book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
                text TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY (book, chapter, verse));
            CREATE TABLE tables (book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL,
                rows TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY (book, chapter, verse));
            INSERT INTO chapters VALUES ('Isa', 6, '2026-01-01T00:00:00+00:00');
            INSERT INTO notes VALUES ('Isa', 6, 1, 'une note', '2026-01-01T00:00:00+00:00');
            INSERT INTO tables VALUES ('Isa', 6, 3, '[["a","b","c","d","e","f"]]', '2026-01-01T00:00:00+00:00');
        """)
    db.close()
    store = Store(path)
    Store(path)  # a second process starting: nothing more to migrate
    first = store.add_user("nicolas", "a-password")
    assert first == 1
    assert store.created_chapters(first) == {"Isa": [6]}
    assert store.notes(first, "Isa", 6) == {1: "une note"}
    assert store.tables(first, "Isa", 6) == {3: [["a", "b", "c", "d", "e", "f"]]}
    second = store.add_user("other", "a-password")
    assert store.created_chapters(second) == {}


def test_secret_key_file(tmp_path, monkeypatch):
    monkeypatch.delenv("BENNERIA_SECRET_KEY")
    monkeypatch.setenv("BENNERIA_NOTEBOOK_DB", str(tmp_path / "data" / "notebook.sqlite"))
    key = secret_key()
    path = tmp_path / "data" / "secret_key"
    assert len(key) == 64 and path.read_text() == key
    assert path.stat().st_mode & 0o777 == 0o600
    assert secret_key() == key                      # kept: the same after a restart
    assert [p.name for p in path.parent.iterdir()] == ["secret_key"]  # no temporary file left
    monkeypatch.setenv("BENNERIA_SECRET_KEY", "from-the-environment")
    assert secret_key() == "from-the-environment"


def test_user_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BENNERIA_NOTEBOOK_DB", str(tmp_path / "notebook.sqlite"))
    monkeypatch.setattr(users.getpass, "getpass", lambda prompt: "a-good-password")
    users.main(["add", "nicolas"])
    assert "created" in capsys.readouterr().out
    assert Store().login("nicolas", "a-good-password") is not None
    with pytest.raises(SystemExit):
        users.main(["add", "Nicolas"])               # taken, whatever the case
    users.main(["list"])
    assert capsys.readouterr().out.startswith("nicolas\t0 notebooks")
    monkeypatch.setattr(users.getpass, "getpass", lambda prompt: "short")
    with pytest.raises(SystemExit):
        users.main(["passwd", "nicolas"])            # too short: unchanged
    users.main(["remove", "nicolas", "--yes"])
    assert Store().users() == []
