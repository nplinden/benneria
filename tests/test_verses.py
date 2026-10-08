"""Every word of a seeded sample of verses, searched with its verse as context, finds the entry
morphhb assigns it, ranked first."""

import random

import pytest

from benneria.refs import in_ref

SEED = 2026
VERSES = 40


def sample_verses(db):
    verses = sorted({v for (refs,) in db.execute("SELECT refs FROM forms") for v in refs.split()})
    return random.Random(SEED).sample(verses, VERSES)


def words_in(db, verse):
    """Spelling -> entry ids, for the words of one verse."""
    words = {}
    rows = db.execute("SELECT form, entry_id, refs FROM forms WHERE refs LIKE ?", (f"%{verse}%",))
    for form, entry_id, refs in rows:
        if any(v == verse for v in refs.split()):
            words.setdefault(form, set()).add(entry_id)
    return words


def test_each_word_of_sampled_verses_finds_its_entry(db, lexicon):
    failures, checked = [], 0
    for verse in sample_verses(db):
        for form, expected in words_in(db, verse).items():
            checked += 1
            results = lexicon.search(form, lookup_ref=verse, always_consonants=True)["results"]
            if not results or results[0]["id"] not in expected:
                failures.append((verse, form, expected, [e["id"] for e in results[:3]]))
    assert checked > 300
    assert not failures, f"{len(failures)} of {checked} words: {failures[:10]}"
