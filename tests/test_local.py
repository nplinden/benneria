"""Search behaviour of the local backend, on the committed database."""

import pytest

from benneria.refs import RefError


def first(result):
    return result["results"][0]


def test_exact_pointed_spelling(lexicon):
    out = lexicon.search("וַיִּשְׁמְרוּ")
    assert out["steps"] == ["exact"]
    e = first(out)
    assert (e["headword"], e["strong"]) == ("שָׁמַר", "8104")
    assert e["matches"][0]["morph"] == "HC/Vqw3mp"


def test_unpointed_input_matches_consonants(lexicon):
    out = lexicon.search("וישמרו")
    assert out["steps"] == ["consonantal"]
    assert {m["form"] for m in first(out)["matches"]} >= {"וַיִּשְׁמְרוּ", "וְיִשְׁמְרוּ"}


def test_always_consonants_adds_consonant_matches(lexicon):
    assert lexicon.search("וַיִּשְׁמְרוּ", always_consonants=True)["steps"] == ["exact", "consonantal"]


def test_match_without_prefixes(lexicon):
    # A word that only occurs with a prefix in the Bible.
    word = "ישמרו"
    out = lexicon.search(word)
    assert out["results"] and out["results"][0]["strong"] == "8104"


def test_strip_prefixes_off_skips_that_step(lexicon, db):
    # Find a bare spelling that never occurs on its own, so only step 3 can match it.
    row = db.execute("""SELECT bare_c FROM forms f WHERE bare_c != form_c
                        AND NOT EXISTS (SELECT 1 FROM forms g WHERE g.form_c = f.bare_c)
                        AND NOT EXISTS (SELECT 1 FROM entries e WHERE e.headword_c = f.bare_c)
                        LIMIT 1""").fetchone()
    assert lexicon.search(row[0])["steps"] == ["without prefixes"]
    assert lexicon.search(row[0], strip_prefixes=False)["results"] == []


def test_headword_fallback(lexicon, db):
    # A headword whose consonants never occur as a Bible spelling.
    row = db.execute("""SELECT headword FROM entries e WHERE e.headword_c != ''
                        AND NOT EXISTS (SELECT 1 FROM forms f WHERE f.form_c = e.headword_c OR f.bare_c = e.headword_c)
                        LIMIT 1""").fetchone()
    assert lexicon.search(row[0])["steps"] == ["headword"]


def test_prefix_only_word(lexicon):
    e = first(lexicon.search("לָהֶם"))
    assert (e["headword"], e["strong"]) == ("לְ", "l")


def test_hebrew_before_aramaic_without_context(lexicon):
    langs = [e["lang"] for e in lexicon.search("בָּרָא")["results"]]
    assert "arc" in langs and langs == sorted(langs, key=lambda lang: lang != "heb")


def test_all_steps_merge_unpointed(lexicon):
    # Unpointed תורה: Bible forms give 8451 "law", the headwords add 8452 "custom".
    out = lexicon.search("תורה")
    assert [e["strong"] for e in out["results"]][:2] == ["8451", "8452"]
    assert out["steps"][0] == "consonantal" and "headword" in out["steps"]


def test_pointed_input_without_ignore_vowels_stays_strict(lexicon):
    # Without always_consonants, a pointed word that matches exactly doesn't add looser matches.
    out = lexicon.search("וַיִּשְׁמְרוּ")
    assert out["steps"] == ["exact"]


def test_exact_headword_shares_spelling_with_another_entry(lexicon):
    # תּוֹרָה occurs in the Bible only as 8451 "law"; 8452 "custom" has the same headword.
    out = lexicon.search("תּוֹרָה")
    assert {e["strong"] for e in out["results"]} == {"8451", "8452"}
    assert out["results"][0]["strong"] == "8451"  # the Bible spelling ranks first


@pytest.mark.parametrize("ref, gloss", [("Gen 1:1", "shape"), ("Dan 2:38", "field")])
def test_context_verse_picks_the_entry_used_there(lexicon, ref, gloss):
    results = lexicon.search("בָּרָא", lookup_ref=ref)["results"]
    assert results[0]["gloss"] == gloss and results[0]["in_ref"]


def test_phrase_keeps_word_order(lexicon):
    out = lexicon.search("בְּרֵאשִׁית בָּרָא אֱלֹהִים")
    glosses = [e["gloss"] for e in out["results"]]
    assert glosses.index("beginning") < glosses.index("shape") < glosses.index("gods")


def test_never_split(lexicon):
    assert lexicon.search("בְּרֵאשִׁית בָּרָא אֱלֹהִים", never_split=True)["results"] == []


def test_unknown_book(lexicon):
    with pytest.raises(RefError):
        lexicon.search("בָּרָא", lookup_ref="Matthew 1:1")


def test_open_by_strong_returns_homographs(lexicon):
    glosses = {e["gloss"] for e in lexicon.open(strong="1254")["results"]}
    assert glosses == {"shape", "be fat"}


def test_open_by_id_and_bdb(lexicon):
    e = first(lexicon.open(entry_id="nbf"))
    assert e["headword"] == "שָׁמַר" and e["bdb"]["page"] == 1036
    assert [x["id"] for x in lexicon.open(bdb=e["bdb_id"])["results"]] == ["nbf"]


def test_entry_links(lexicon):
    e = first(lexicon.open(entry_id="nbf"))
    assert e["prev"]["id"] == "nbe" and e["next"]["id"] == "nbg"
    assert {r["relation"] for r in e["related"]} == {"derivative"}
