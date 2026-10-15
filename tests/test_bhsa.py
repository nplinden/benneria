"""Benneria Notebook's BHSA database (src/benneria_notebook/data/bhsa.sqlite) and its reader."""

import unicodedata

import pytest

from benneria.hebrew import consonantal, pointed
from benneria.refs import to_osis
from benneria_notebook import bhsa

GEN_1_1 = "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"


def nfc(s):
    # BHSA keeps its own order of combining marks (e.g. dagesh before sheva), not Unicode's NFC.
    return unicodedata.normalize("NFC", s)


@pytest.fixture(scope="module")
def db():
    conn = bhsa.connect()
    yield conn
    conn.close()


def test_counts_and_source(db):
    meta = dict(db.execute("SELECT key, value FROM meta"))
    assert meta["source"] == "ETCBC/bhsa" and meta["bhsa_version"] == "2021"
    assert "CC BY-NC 4.0" in meta["license"] and "10.17026/dans-z6y-skyh" in meta["attribution"]
    assert (meta["check: books"], meta["check: verses"], meta["check: words"]) == ("39", "23213", "426590")


def test_verse_text(db):
    assert nfc(bhsa.verse_text(db, "Gen.1.1")) == nfc(GEN_1_1)
    assert bhsa.verse_text(db, "Gen.1.1", pointed) == pointed(GEN_1_1)  # derived forms are NFC


def test_words_and_written_units(db):
    words = bhsa.verse_words(db, "Gen.1.1")
    assert len(words) == 11  # prefixes are words of their own in BHSA
    first = [w for w in words if w["unit"] == 1]
    assert [nfc(w["text"]) for w in first] == [nfc("בְּ"), nfc("רֵאשִׁ֖ית")]  # one written word, two BHSA words
    assert max(w["unit"] for w in words) == 7
    verb = words[2]
    assert (verb["consonantal"], verb["sp"], verb["vs"], verb["vt"]) == ("ברא", "verb", "qal", "perf")
    assert verb["pointed"] == pointed(verb["text"]) and verb["consonantal"] == consonantal(verb["text"])


def test_lexemes(db):
    row = db.execute("""SELECT l.lexeme, l.pointed, l.gloss, l.language FROM words w
                        JOIN lexemes l ON l.id = w.lexeme_id JOIN verses v ON v.id = w.verse_id
                        WHERE v.osis = 'Gen.1.1' AND w.position = 3""").fetchone()
    assert tuple(row) == ("ברא", "ברא", "create", "Hebrew")
    aramaic = db.execute("""SELECT COUNT(*) FROM words w JOIN lexemes l ON l.id = w.lexeme_id
                            JOIN verses v ON v.id = w.verse_id
                            WHERE v.osis LIKE 'Dan.2.%' AND l.language = 'Aramaic'""").fetchone()[0]
    assert aramaic > 0  # Daniel 2:4b onward is Aramaic


def test_references_match_the_dictionary(db):
    # Every verse id is one Benneria's reference parser produces for the same verse.
    for osis, title, chapter, verse in db.execute(
            "SELECT v.osis, b.title, v.chapter, v.verse FROM verses v JOIN books b ON b.id = v.book_id"):
        assert to_osis(f"{title} {chapter}:{verse}") == osis


def test_every_verse_has_words_in_order(db):
    gaps = db.execute("""SELECT COUNT(*) FROM verses v WHERE
                         (SELECT COUNT(*) FROM words w WHERE w.verse_id = v.id) != v.last_word - v.first_word + 1
                         OR (SELECT MAX(position) FROM words w WHERE w.verse_id = v.id) != v.last_word - v.first_word + 1""").fetchone()[0]
    assert gaps == 0
