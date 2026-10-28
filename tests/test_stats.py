"""The statistics app's web app: the page, the root/binyan table, and the chart data."""

import pytest

from benneria_stats import stats
from benneria_web.app import app


@pytest.fixture(scope="module")
def client():
    return app.test_client()


def test_page_and_static_files(client):
    for path in ("/stats", "/static/stats.js", "/static/stats.css", "/static/entry-card.js",
                 "/static/labels.js", "/static/style.css"):
        assert client.get(path).status_code == 200


def test_roots_table(client):
    data = client.get("/api/stats/roots").json
    assert data["binyanim"] == ["Paal", "Piel", "Hifil", "Hitpael", "Hofal", "Pual", "Nifal"]
    roots = data["roots"]
    assert len(roots) == len(stats.ROOT_BINYAN_COUNTS) > 1000
    # Most frequent root first; every row has a total and every binyan column.
    assert roots[0]["total"] >= roots[1]["total"] >= roots[-1]["total"]
    assert set(roots[0]) == {"root", "total", "classes"} | set(data["binyanim"])
    assert roots[0]["total"] == sum(roots[0][b] for b in data["binyanim"])


def test_verb_classes(client):
    data = client.get("/api/stats/roots").json
    assert data["classes"] == stats.VERB_CLASSES
    classes = {r["root"]: r["classes"] for r in data["roots"]}
    assert classes["שׁמר"] == classes["כתב"] == ["strong"]
    assert classes["אמר"] == ["pe-guttural", "pe-aleph"]      # its aleph goes quiet: יֹאמַר
    assert classes["אסף"] == ["pe-guttural"]                  # a guttural, not quiescent
    assert classes["נשׂא"] == ["pe-nun", "lamed-aleph"]       # doubly weak
    assert classes["לקח"] == ["pe-nun", "lamed-guttural"]     # takes after pe-nun: יִקַּח
    assert classes["ישׁב"] == ["pe-yod"] and "pe-yod" in classes["הלך"]
    assert classes["קום"] == ["ayin-vav-yod"] and classes["שׂים"] == ["ayin-vav-yod"]
    assert classes["היה"] == ["pe-guttural", "lamed-he"]      # a consonantal yod: not hollow
    assert classes["סבב"] == ["ayin-ayin"]
    assert classes["שׁמע"] == ["lamed-guttural"] and classes["בנה"] == ["lamed-he"]
    assert classes["תרגם"] == []                               # four letters: no class
    assert all(c in stats.VERB_CLASSES for cs in classes.values() for c in cs)


def test_chart_default_is_every_root(client):
    data = client.get("/api/stats/chart").json
    assert data["tenses"] == ["Qatal", "Yiqtol", "Wayyiqtol", "Imperative",
                               "Infinitive (absolute)", "Infinitive (construct)",
                               "Participle", "Participle (passive)"]
    rows = data["data"]
    assert [r["binyan"] for r in rows] == ["Paal", "Piel", "Hifil", "Hitpael", "Hofal", "Pual", "Nifal"]
    # Every occurrence counted in the table also shows up in the chart, for each binyan.
    totals = {r["root"]: r for r in stats.ROOT_BINYAN_COUNTS}
    for row in rows:
        expected = sum(r[row["binyan"]] for r in totals.values())
        assert sum(row[t] for t in data["tenses"]) == expected


def test_chart_restricted_to_a_root(client):
    all_roots = client.get("/api/stats/chart").json["data"]
    one_root = client.get("/api/stats/chart", query_string=[("root", "ברא")]).json["data"]
    total_all = sum(sum(r[t] for t in stats.TENSES) for r in all_roots)
    total_one = sum(sum(r[t] for t in stats.TENSES) for r in one_root)
    assert 0 < total_one < total_all

    # Several roots: the union of what each contributes alone (no double counting across roots).
    other = client.get("/api/stats/chart", query_string=[("root", "שמר")]).json["data"]
    total_other = sum(sum(r[t] for t in stats.TENSES) for r in other)
    combined = client.get("/api/stats/chart", query_string=[("root", "ברא"), ("root", "שמר")]).json["data"]
    total_combined = sum(sum(r[t] for t in stats.TENSES) for r in combined)
    assert total_combined == total_one + total_other


def test_chart_over_the_filtered_roots(client):
    def total(**params):
        rows = client.get("/api/stats/chart", query_string=params).json["data"]
        return sum(r[t] for r in rows for t in stats.TENSES)
    by_root = {r["root"]: r["total"] for r in stats.ROOT_BINYAN_COUNTS}
    pe_nun = [r for r in by_root if "pe-nun" in stats.verb_classes(r)]
    assert total(**{"class": "pe-nun"}) == sum(by_root[r] for r in pe_nun)
    assert total(contains="שׁ", **{"class": "pe-nun"}) == sum(by_root[r] for r in pe_nun if "שׁ" in r)
    assert total(contains="שׁמר") == by_root["שׁמר"]
    assert total(contains="xyz") == 0                       # nothing matches: an empty chart
    assert total(root="ברא", contains="xyz") == by_root["ברא"]  # a selection overrides filters


def test_chart_unknown_root_is_empty(client):
    data = client.get("/api/stats/chart", query_string=[("root", "xyz")]).json["data"]
    assert all(sum(r[t] for t in stats.TENSES) == 0 for r in data)


def test_definition_reuses_the_dictionary(client):
    # The same endpoint and shape as a normal dictionary lookup, just an exact headword match.
    data = client.get("/api/entry", query_string={"root": "ברא"}).json
    assert {e["gloss"] for e in data["results"]} == {"shape", "be fat"}
    assert client.get("/api/entry", query_string={"root": "xyz"}).json["results"] == []
    assert client.get("/api/entry").status_code == 400


def test_definition_is_verb_entries_only(client):
    # שמר also names a noun, two proper names and an uncertain entry sharing its consonants;
    # the root lookup keeps only the verb ("keep"), unlike a normal dictionary search.
    data = client.get("/api/entry", query_string={"root": "שמר"}).json
    assert [e["gloss"] for e in data["results"]] == ["keep"]
    assert all(e["pos"] == "V" for e in data["results"])
