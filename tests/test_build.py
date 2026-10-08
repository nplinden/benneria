"""Unit tests for the helpers in scripts/build_data.py."""

import xml.etree.ElementTree as ET

import pytest

NS = "http://openscriptures.github.com/morphhb/namespace"


@pytest.mark.parametrize("r, osis, title", [
    ("Num.21.30", "Num.21.30", "Numbers 21:30"),
    ("Gen.30.20!a", "Gen.30.20", "Genesis 30:20a"),   # half-verse suffix
    ("Exod24.17", "Exod.24.17", "Exodus 24:17"),      # missing dot
    ("Ezra,6,15", "Ezra.6.15", "Ezra 6:15"),          # commas
    ("Job.37:23", "Job.37.23", "Job 37:23"),          # colon
    ("Exod.3.12-Exod.3.15", "Exod.3.12", "Exodus 3:12"),  # range keeps its start
    ("Jugd.16.26", "Judg.16.26", "Judges 16:26"),     # typo
    ("iKgs.15.18", "1Kgs.15.18", "1 Kings 15:18"),
    ("Ez.19.2", "Ezek.19.2", "Ezekiel 19:2"),         # BDB's abbreviation for Ezekiel
    ("1cHR.2.26", "1Chr.2.26", "1 Chronicles 2:26"),
    ("Ps.33", "Ps.33", "Psalms 33"),
])
def test_normalize_bdb_ref(build_data, r, osis, title):
    assert build_data.normalize_bdb_ref(r) == (osis, title)


@pytest.mark.parametrize("r", ["", None, "Ezra.814", "Luke.1.7", "Matt.15.39"])
def test_normalize_bdb_ref_unreadable(build_data, r):
    assert build_data.normalize_bdb_ref(r) == (None, None)


@pytest.fixture
def bdb_pos(build_data, monkeypatch):
    names = {"vb": "Verb", "n": "Noun", "m": "Masculine", "f": "Feminine", "pl": "Plural",
             "denom": "Denominative", "1pl": "1st Person Plural", **build_data.BDB_POS_FIXES}
    monkeypatch.setattr(build_data, "BDB_POS_NAMES", names)
    return build_data.bdb_pos_title


@pytest.mark.parametrize("abbr, title", [
    ("vb", "Verb"),
    ("n.[m.]pl", "Noun [Masculine] Plural"),
    ("vb. denom", "Verb Denominative"),
    ("n.pr.loc", "Proper Name Location"),
    ("adj.gent", "adj Gentilic"),   # unknown abbreviations are kept as they are
    ("1pl", "1st Person Plural"),   # listed whole in the key
])
def test_bdb_pos_title(bdb_pos, abbr, title):
    assert bdb_pos(abbr) == title


def test_bdb_pos_title_unknown(bdb_pos):
    assert bdb_pos("xyz") is None


def test_render_bdb(build_data, monkeypatch):
    monkeypatch.setattr(build_data, "BDB_POS_NAMES", {"vb": "Verb"})
    el = ET.fromstring(
        f'<entry xmlns="{NS}"><w>אָבַד</w> <pos>vb</pos>. <def>perish</def>'
        f'<sense n="1"><stem>Qal</stem> <ref r="Num.21.30">Nu 21:30</ref> &amp; <w src="a.ae.aa" mod="II">אבה</w></sense>'
        f'<status p="2">done</status></entry>')
    html = build_data.render_bdb(el)
    assert '<span class="he" dir="rtl">אָבַד</span>' in html
    assert '<span class="pos" title="Verb">vb</span>' in html
    assert '<b class="def">perish</b>' in html
    assert '<div class="sense"><span class="n">1.</span> <span class="stem">Qal</span>' in html
    assert '<span class="ref" data-ref="Num.21.30" title="Numbers 21:30">Nu 21:30</span>' in html
    assert '<span class="hom">II</span> <a class="he" dir="rtl" data-bdb="a.ae.aa">אבה</a>' in html
    assert "&amp;" in html and "done" not in html  # text escaped, status dropped


def test_render_strongs(build_data):
    el = ET.fromstring(f'<source xmlns="{NS}">a variation of <w src="H4757">4757</w>; <def>x</def> &lt;</source>')
    assert build_data.render_strongs(el) == (
        'a variation of <a class="he" data-strong="4757">4757</a>; <b class="def">x</b> &lt;')


@pytest.fixture
def resolver(build_data):
    entries = [
        {"id": "bxy", "lang": "heb", "strong": "1254", "headword_c": "ברא"},
        {"id": "bxx", "lang": "heb", "strong": "1254", "headword_c": "ברא"},
        {"id": "lzv", "lang": "heb", "strong": "7451", "headword_c": "רע"},
        {"id": "lzu", "lang": "heb", "strong": "7451", "headword_c": "רע"},
        {"id": "gau", "lang": "heb", "strong": "l", "headword_c": "ל"},
        {"id": "one", "lang": "arc", "strong": None, "headword_c": "ל"},
        {"id": "bep", "lang": "heb", "strong": "776", "headword_c": "ארץ"},
    ]
    aug = [("1254a", "bxy"), ("1254b", "bxx"), ("7451a", "lzv"), ("7451b", "lzu"), ("776", "bep")]
    return build_data.LemmaResolver(entries, aug)


@pytest.mark.parametrize("lemma, lang, ids, prefixes", [
    ("1254 a", "heb", ["bxy"], []),            # augmented number written with a space
    ("c/d/776", "heb", ["bep"], ["c", "d"]),   # prefixes before the number
    ("776+", "heb", ["bep"], []),              # trailing '+'
    ("7451", "heb", ["lzv", "lzu"], []),       # plain number where only lettered variants exist
    ("l", "heb", ["gau"], []),                 # prefix-only lemma: a preposition with a suffix
    ("c/l", "heb", ["gau"], ["c"]),
    ("l", "arc", ["one"], []),                 # Aramaic prefix matched by headword
])
def test_lemma_resolver(resolver, lemma, lang, ids, prefixes):
    assert resolver.resolve(lemma, lang) == (ids, prefixes)


def test_tag_head_pos(build_data):
    import re
    pattern = re.compile(r"^([\]\s,\d]*)(n\.\[m\.\]|prep|conj|du)(?=[.,;:\s)]|$)")

    def tagged(xml):
        el = ET.fromstring(f'<entry xmlns="{NS}">{xml}</entry>')
        changed = build_data.tag_head_pos(el, pattern)
        return changed, [(c.tag.split("}")[1], c.text, c.tail) for c in el]

    # Untagged right after the headword: wrapped in <pos>, the rest of the text kept.
    changed, kids = tagged("<w>שְׁפַתַּיִם</w> n.[m.] <pos>du</pos>.: prob.")
    assert changed and kids[:2] == [("w", "שְׁפַתַּיִם", " "), ("pos", "n.[m.]", " ")]
    # After a bracketed headword and an occurrence count.
    changed, kids = tagged("[<w>קֳדָם</w>] 42 prep. <def>before</def>")
    assert changed and kids[1] == ("pos", "prep", ". ")
    # Already tagged, or the abbreviation is elsewhere in prose: left alone.
    assert not tagged("<w>אֹפֶס</w> <pos>n.[m.]</pos> only in the <pos>du</pos>.")[0]
    assert not tagged("<w>א</w> (√ of foll.; Thes conj. orig. mng.)")[0]


def test_bdb_abbreviation_tooltips(build_data):
    text = build_data.bdb_text
    assert text("prob. = x, infr., q.v.;") == (
        '<abbr title="probably">prob.</abbr> = x, '
        '<abbr title="infra: below, later in the lexicon">infr.</abbr>, '
        '<abbr title="quod vide: which see">q.v.</abbr>;')
    assert '<abbr title="times (after a number)">t.</abbr>' in text("+ 2t.; + 40 t.")
    assert text("+ 40 t.").count("<abbr") == 1
    # Ambiguous abbreviations, parts of longer words and plain words are left alone.
    assert "<abbr" not in text("v. also; acc. to; Thes conj.; ad loc.; the art of")
    assert text("c. art.") == 'c. <abbr title="article">art.</abbr>'  # "c." is ambiguous, "art." is not
    assert "<abbr" not in text("probably, cfx.")


def test_bdb_abbreviations_skip_hebrew_refs_and_pos(build_data):
    el = ET.fromstring(
        f'<entry xmlns="{NS}"><w>prob.</w> <pos>pl</pos>. <ref r="Gen.1.1">cf. 1:1</ref> see cf. here</entry>')
    html = build_data.render_bdb(el)
    assert html.count("<abbr") == 1 and 'see <abbr title="confer: compare">cf.</abbr> here' in html
