"""
Build the Hebrew Bible database for Benneria Notebook from BHSA, the ETCBC's annotated edition of
the Biblia Hebraica Stuttgartensia (https://github.com/ETCBC/bhsa), read with Text-Fabric.

BHSA is licensed CC BY-NC 4.0 (non-commercial; see DATA_LICENSE.md), so it gets its own database,
separate from the dictionary's lexicon.sqlite.

Run from the repository root:
    uv run --group build python scripts/build_bhsa.py

The first run downloads the corpus (about 270 MB) into ~/text-fabric-data; later runs reuse it.
Writes src/benneria_notebook/data/bhsa.sqlite.
"""

import argparse
import os
import sqlite3
from pathlib import Path

from tf.app import use

from benneria.refs import BOOKS, book_osis

BHSA_VERSION = "2021"
SCHEMA_VERSION = "1"

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "src" / "benneria_notebook" / "data" / "bhsa.sqlite"
BOOK_TITLES = dict(BOOKS)

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE books (
    id INTEGER PRIMARY KEY,     -- order in BHSA (Hebrew canon: Genesis ... 2 Chronicles)
    bhsa TEXT NOT NULL,         -- BHSA's name, e.g. '1_Samuel'
    osis TEXT NOT NULL UNIQUE,  -- e.g. '1Sam', as in Benneria's references
    title TEXT NOT NULL         -- e.g. '1 Samuel'
);

CREATE TABLE verses (
    id INTEGER PRIMARY KEY,     -- BHSA verse node
    book_id INTEGER NOT NULL REFERENCES books (id),
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    osis TEXT NOT NULL UNIQUE,  -- e.g. 'Gen.1.1', as in Benneria's context verses
    first_word INTEGER NOT NULL,
    last_word INTEGER NOT NULL
);

CREATE TABLE lexemes (
    id INTEGER PRIMARY KEY,     -- BHSA lex node
    lexeme TEXT NOT NULL,       -- consonantal, e.g. 'ברא'
    pointed TEXT,               -- vocalised, e.g. 'בָּרָא'
    gloss TEXT,                 -- BHSA's English gloss
    language TEXT NOT NULL      -- 'Hebrew' or 'Aramaic'
);

-- BHSA words are morphemes as written: a prefix such as בְּ is its own word. "unit" numbers the
-- written words of a verse (בְּרֵאשִׁית is one unit made of two words), split at spaces, maqaf
-- and sof pasuq.
-- Derived forms are not stored: a verse's text is its words' text + trailer, in order, and a
-- word's pointed and consonantal forms come from benneria.hebrew (see benneria_notebook.bhsa).
CREATE TABLE words (
    id INTEGER PRIMARY KEY,     -- BHSA word node
    verse_id INTEGER NOT NULL REFERENCES verses (id),
    position INTEGER NOT NULL,  -- 1-based, within the verse
    unit INTEGER NOT NULL,      -- 1-based written word, within the verse
    text TEXT NOT NULL,         -- with vowels and accents
    trailer TEXT NOT NULL,      -- what follows: '', ' ', '־', '׃ ', '׃ פ ', ...
    lexeme_id INTEGER NOT NULL REFERENCES lexemes (id),
    sp TEXT,                    -- part of speech: subs, verb, prep, art, conj, ...
    vs TEXT,                    -- verbal stem: qal, piel, hif, ...
    vt TEXT,                    -- verbal tense: perf, impf, wayq, impv, infa, infc, ptca, ptcp
    ps TEXT,                    -- person: p1, p2, p3
    gn TEXT,                    -- gender: m, f
    nu TEXT,                    -- number: sg, du, pl
    st TEXT                     -- state: a (absolute), c (construct), e (emphatic)
);
CREATE INDEX words_verse ON words (verse_id, position);
CREATE INDEX words_lexeme ON words (lexeme_id);
CREATE INDEX verses_book ON verses (book_id, chapter, verse);
"""


def value(feature, node):
    """A BHSA feature value, with its "not applicable" marker stored as NULL."""
    v = feature.v(node)
    return None if v in (None, "NA") else v


def build(output):
    A = use(f"ETCBC/bhsa:{BHSA_VERSION}", version=BHSA_VERSION, silent="deep")
    api = A.api
    F, L, T = api.F, api.L, api.T

    books, verses, words, lexemes = [], [], [], {}
    for book_id, book in enumerate(F.otype.s("book"), 1):
        bhsa = T.sectionFromNode(book)[0]
        osis = book_osis(bhsa)
        books.append((book_id, bhsa, osis, BOOK_TITLES[osis]))
        for verse in L.d(book, otype="verse"):
            _, chapter, number = T.sectionFromNode(verse)
            ws = L.d(verse, otype="word")
            unit = 1
            for position, w in enumerate(ws, 1):
                lex = L.u(w, otype="lex")[0]
                if lex not in lexemes:
                    lexemes[lex] = (lex, F.lex_utf8.v(lex), value(F.voc_lex_utf8, lex),
                                    value(F.gloss, lex), F.language.v(w))
                surface, trailer = F.g_word_utf8.v(w) or "", F.trailer_utf8.v(w) or ""
                words.append((w, verse, position, unit, surface, trailer, lex, value(F.sp, w),
                              value(F.vs, w), value(F.vt, w), value(F.ps, w), value(F.gn, w),
                              value(F.nu, w), value(F.st, w)))
                if trailer:  # a space, maqaf or sof pasuq ends the written word
                    unit += 1
            verses.append((verse, book_id, chapter, number, f"{osis}.{chapter}.{number}", ws[0], ws[-1]))

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO books VALUES (?,?,?,?)", books)
    db.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?,?)", verses)
    db.executemany("INSERT INTO lexemes VALUES (?,?,?,?,?)", sorted(lexemes.values()))
    db.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", words)

    checks = {
        "books": len(books),
        "verses": len(verses),
        "words": len(words),
        "lexemes": len(lexemes),
        "written words": sum(1 for w in words if w[5]),  # each written word ends with a trailer
    }
    meta = {
        "schema_version": SCHEMA_VERSION,
        "source": "ETCBC/bhsa",
        "bhsa_version": BHSA_VERSION,
        "license": "CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/); "
                   "commercial use needs the consent of the German Bible Society",
        "attribution": "BHSA (Biblia Hebraica Stuttgartensia Amstelodamensis), Eep Talstra Centre for "
                       "Bible and Computer; doi:10.17026/dans-z6y-skyh",
    }
    meta.update({f"check: {k}": str(v) for k, v in checks.items()})
    db.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
    db.commit()
    db.execute("VACUUM")
    db.close()
    os.replace(tmp, output)

    print(f"Wrote {output} ({output.stat().st_size / 1e6:.1f} MB)")
    for k, v in checks.items():
        print(f"  {k}: {v}")


def main():
    ap = argparse.ArgumentParser(description="Build Benneria Notebook's BHSA database")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build(ap.parse_args().output)


if __name__ == "__main__":
    main()
