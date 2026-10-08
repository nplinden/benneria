"""Integrity checks on the committed database, src/benneria/data/lexicon.sqlite."""

import pytest


def scalar(db, sql):
    return db.execute(sql).fetchone()[0]


def test_build_checks_recorded_in_meta_pass(db):
    checks = dict(db.execute("SELECT key, value FROM meta WHERE key LIKE 'check: %'"))
    must_be_zero = [
        "check: bible words unresolved",
        "check: entries whose bdb id is missing from BDB",
        "check: entries whose strong number is missing from Strong's",
        "check: aug numbers pointing to unknown entries",
        "check: related links to unknown entries",
    ]
    for key in must_be_zero:
        assert checks[key] == "0", key
    assert int(checks["check: bible words"]) == 306785


def test_meta_records_sources_and_attribution(db):
    meta = dict(db.execute("SELECT key, value FROM meta"))
    assert len(meta["hebrewlexicon_commit"]) == 40 and len(meta["morphhb_commit"]) == 40
    assert "https://github.com/openscriptures/morphhb" in meta["attribution"]


@pytest.mark.parametrize("sql", [
    # every entry's BDB id and Strong's number resolve
    "SELECT COUNT(*) FROM entries e WHERE e.bdb_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM bdb b WHERE b.id = e.bdb_id)",
    "SELECT COUNT(*) FROM entries e WHERE e.strong GLOB '[0-9]*' AND NOT EXISTS (SELECT 1 FROM strongs s WHERE s.number = e.strong)",
    # every augmented number, related link and spelling points to a real entry
    "SELECT COUNT(*) FROM aug a WHERE NOT EXISTS (SELECT 1 FROM entries e WHERE e.id = a.entry_id)",
    "SELECT COUNT(*) FROM related r WHERE NOT EXISTS (SELECT 1 FROM entries e WHERE e.id = r.related_id)",
    "SELECT COUNT(*) FROM forms f WHERE f.entry_id IS NULL OR NOT EXISTS (SELECT 1 FROM entries e WHERE e.id = f.entry_id)",
    # every BDB entry has a page and some text
    "SELECT COUNT(*) FROM bdb WHERE page IS NULL OR html = ''",
])
def test_no_dangling_references(db, sql):
    assert scalar(db, sql) == 0


def test_occurrence_counts_add_up(db):
    # Every Bible word is counted once, except the 24 with several candidate entries,
    # which are counted once per candidate.
    total = scalar(db, "SELECT SUM(count) FROM forms")
    assert 306785 <= total <= 306785 + 24 * 3


def test_prefix_letters_map_to_entries(db):
    letters = {r[0] for r in db.execute("SELECT strong FROM entries WHERE strong GLOB '[a-z]'")}
    assert letters == set("bcdiklms")
