"""
Build Benneria's lexicon database from OpenScriptures data.

Sources, pinned to a commit so builds are reproducible:
  - HebrewLexicon (https://github.com/openscriptures/HebrewLexicon): Lexical Index, BDB,
    Strong's Hebrew dictionary and the augmented Strong's index. CC BY 4.0; the BDB and
    Strong's text is public domain.
  - morphhb (https://github.com/openscriptures/morphhb): the morphologically tagged Hebrew
    Bible, used for the spelling index. CC BY 4.0, "Original work of the Open Scriptures
    Hebrew Bible available at https://github.com/openscriptures/morphhb".

Run from the repository root:
    uv run python scripts/build_data.py

Downloads the sources into build/sources/ (reused on later runs) and writes
src/benneria/data/lexicon.sqlite.
"""

import argparse
import collections
import html
import os
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from benneria.hebrew import consonantal, pointed

HEBREWLEXICON_COMMIT = "21c9add13bc727d3a951361778e97e3ff7afd1ce"
MORPHHB_COMMIT = "3d15126fb1ef74867fc1434be1942e837932691f"
HEBREWLEXICON_FILES = ["LexicalIndex.xml", "BrownDriverBriggs.xml", "HebrewStrong.xml", "AugIndex.xml"]
MORPHHB_BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs",
    "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer",
    "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph",
    "Hag", "Zech", "Mal",
]
SCHEMA_VERSION = "1"

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = ROOT / "build" / "sources"
DEFAULT_OUTPUT = ROOT / "src" / "benneria" / "data" / "lexicon.sqlite"

LEX_NS = "{http://openscriptures.github.com/morphhb/namespace}"
OSIS_NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- One row per Lexical Index entry: the table that links BDB, Strong's and TWOT.
CREATE TABLE entries (
    id TEXT PRIMARY KEY,        -- Lexical Index id, e.g. 'aaf'
    seq INTEGER NOT NULL,       -- document order, for previous/next navigation
    lang TEXT NOT NULL,         -- 'heb' or 'arc'
    headword TEXT NOT NULL,     -- pointed
    headword_c TEXT NOT NULL,   -- consonants only
    xlit TEXT,
    pos TEXT,                   -- Lexical Index part of speech: N, V, Np, ...
    gloss TEXT,
    bdb_id TEXT,
    strong TEXT,                -- Strong's number ('6'), or a prefix letter code ('l')
    aug TEXT,                   -- augmented Strong's letter ('a', 'b', ...)
    twot TEXT,
    etym_type TEXT,             -- 'main', 'sub' or 'single'
    etym_root TEXT
);
CREATE INDEX entries_headword_c ON entries (headword_c);
CREATE INDEX entries_strong ON entries (strong);
CREATE INDEX entries_bdb ON entries (bdb_id);

-- Root/derivative links from the Lexical Index etym element.
CREATE TABLE related (
    entry_id TEXT NOT NULL,
    related_id TEXT NOT NULL,
    relation TEXT NOT NULL,     -- 'derivative' (from a main entry) or 'origin' (from a sub entry)
    PRIMARY KEY (entry_id, related_id)
);

-- Brown-Driver-Briggs entries, pre-rendered to HTML.
CREATE TABLE bdb (
    id TEXT PRIMARY KEY,        -- e.g. 'a.ac.aa'
    lang TEXT NOT NULL,
    page INTEGER,               -- BDB page the entry starts on
    is_root INTEGER NOT NULL,
    homonym TEXT,               -- 'I', 'II', ... (mod attribute)
    status TEXT,                -- editing stage: base, ref, made, done, new, added
    html TEXT NOT NULL
);

-- Strong's Hebrew dictionary.
CREATE TABLE strongs (
    number TEXT PRIMARY KEY,    -- '1254' (from id 'H1254')
    lang TEXT,                  -- 'heb', 'arc' or 'x-pn' (proper name)
    pos TEXT,                   -- Strong's part-of-speech code, e.g. 'n-pr-m'
    headword TEXT,
    pron TEXT,
    xlit TEXT,
    source_html TEXT,
    meaning_html TEXT,
    usage_html TEXT,
    note_html TEXT
);

-- Augmented Strong's numbers ('1254a') to Lexical Index entries.
CREATE TABLE aug (aug TEXT PRIMARY KEY, entry_id TEXT NOT NULL);

-- Spelling index from morphhb: one row per spelling, entry, parse and variant.
CREATE TABLE forms (
    form TEXT NOT NULL,         -- pointed, no cantillation
    form_c TEXT NOT NULL,       -- consonants only
    bare TEXT NOT NULL,         -- pointed, prefixes removed (same as form when there are none)
    bare_c TEXT NOT NULL,
    entry_id TEXT,              -- NULL when the lemma could not be resolved
    lemma TEXT NOT NULL,        -- morphhb lemma, e.g. 'c/d/776'
    morph TEXT NOT NULL,        -- morphhb parse, e.g. 'HC/Td/Ncbsa'
    variant TEXT,               -- 'ketiv', 'qere' or NULL
    count INTEGER NOT NULL,
    refs TEXT NOT NULL          -- space-separated OSIS verse ids, e.g. 'Gen.1.1 Gen.1.2'
);
CREATE INDEX forms_form ON forms (form);
CREATE INDEX forms_form_c ON forms (form_c);
CREATE INDEX forms_bare_c ON forms (bare_c);
"""


# ---------- sources ----------

def fetch_sources(sources, offline):
    files = [(f"HebrewLexicon/{name}",
              f"https://raw.githubusercontent.com/openscriptures/HebrewLexicon/{HEBREWLEXICON_COMMIT}/{name}")
             for name in HEBREWLEXICON_FILES]
    files += [(f"morphhb/{book}.xml",
               f"https://raw.githubusercontent.com/openscriptures/morphhb/{MORPHHB_COMMIT}/wlc/{book}.xml")
              for book in MORPHHB_BOOKS]
    # Sources are cached per commit, so changing a pinned commit downloads fresh files.
    base = sources / f"{HEBREWLEXICON_COMMIT[:12]}-{MORPHHB_COMMIT[:12]}"
    for rel, url in files:
        path = base / rel
        if path.exists():
            continue
        if offline:
            sys.exit(f"Missing {path} and --offline was given")
        print(f"  downloading {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as out:
            out.write(resp.read())
        tmp.rename(path)
    return base


# ---------- XML to HTML ----------

def local(tag):
    return tag.split("}")[-1]


def xml_text(s):
    # Collapse the XML's indentation; whitespace is not significant in the rendered HTML.
    return html.escape(re.sub(r"\s+", " ", s or ""), quote=False)


def render_children(el, render_el):
    parts = [xml_text(el.text)]
    for child in el:
        parts.append(render_el(child))
        parts.append(xml_text(child.tail))
    return "".join(parts)


def attr(value):
    return html.escape(value, quote=True)


def render_bdb(el):
    """BDB XML element to HTML. Bible references keep their OSIS id in data-ref; Phase 3
    decides where they link."""
    tag = local(el.tag)
    inner = render_children(el, render_bdb)
    if tag == "w":
        hom = f'<span class="hom">{attr(el.get("mod"))}</span> ' if el.get("mod") else ""
        if el.get("src"):
            return f'{hom}<a class="he" dir="rtl" data-bdb="{attr(el.get("src"))}">{inner}</a>'
        return f'{hom}<span class="he" dir="rtl">{inner}</span>'
    if tag == "def":
        return f'<b class="def">{inner}</b>'
    if tag == "pos":
        return f'<span class="pos">{inner}</span>'
    if tag == "stem":
        return f'<span class="stem">{inner}</span>'
    if tag == "asp":
        return f'<i class="asp">{inner}</i>'
    if tag == "em":
        return f"<em>{inner}</em>"
    if tag == "ref":
        r = el.get("r")
        return f'<a class="ref" data-ref="{attr(r)}">{inner}</a>' if r else inner
    if tag == "foreign":
        return f'<span class="foreign" lang="{attr(el.get(XML_LANG) or "")}">{inner}</span>'
    if tag == "sense":
        n = f'<span class="n">{attr(el.get("n"))}.</span> ' if el.get("n") else ""
        return f'<div class="sense">{n}{inner}</div>'
    if tag in ("status", "page"):
        return ""
    return inner


def render_strongs(el):
    tag = local(el.tag)
    inner = render_children(el, render_strongs)
    if tag == "def":
        return f'<b class="def">{inner}</b>'
    if tag == "w":
        src = el.get("src") or ""
        if src.startswith("H"):
            return f'<a class="he" data-strong="{attr(src[1:])}">{inner}</a>'
        return f'<span class="he" dir="rtl">{inner}</span>'
    if tag == "note":
        return f'<span class="note">{inner}</span>'
    return inner


# ---------- parsers ----------

def parse_lexical_index(path):
    entries, related = [], []
    root = ET.parse(path).getroot()
    seq = 0
    for part in root.iter(LEX_NS + "part"):
        lang = part.get(XML_LANG)
        for e in part.iter(LEX_NS + "entry"):
            seq += 1
            w = e.find(LEX_NS + "w")
            x = e.find(LEX_NS + "xref")
            etym = e.find(LEX_NS + "etym")
            head = w.text or ""
            entries.append({
                "id": e.get("id"), "seq": seq, "lang": lang,
                "headword": pointed(head), "headword_c": consonantal(head), "xlit": w.get("xlit"),
                "pos": (e.findtext(LEX_NS + "pos") or None), "gloss": (e.findtext(LEX_NS + "def") or None),
                "bdb_id": x.get("bdb"), "strong": x.get("strong"), "aug": x.get("aug"), "twot": x.get("twot"),
                "etym_type": etym.get("type") if etym is not None else None,
                "etym_root": etym.get("root") if etym is not None else None,
            })
            if etym is not None and etym.text:
                relation = {"main": "derivative", "sub": "origin"}.get(etym.get("type"))
                for rid in re.split(r"[,\s]+", etym.text.strip()):
                    if rid and relation:
                        related.append((e.get("id"), rid, relation))
    return entries, related


def parse_bdb(path):
    rows = []
    root = ET.parse(path).getroot()
    for part in root.iter(LEX_NS + "part"):
        lang = part.get(XML_LANG)
        for entry in part.iter(LEX_NS + "entry"):
            # Every entry's <status p="..."> gives its BDB page; <page> markers are sparse.
            status = entry.find(LEX_NS + "status")
            p = status.get("p") if status is not None else None
            rows.append((entry.get("id"), lang, int(p) if (p or "").isdigit() else None,
                         int(entry.get("type") == "root"), entry.get("mod"),
                         status.text if status is not None else None, render_bdb(entry).strip()))
    return rows


def parse_strongs(path):
    rows = []
    root = ET.parse(path).getroot()
    for e in root.iter(LEX_NS + "entry"):
        w = e.find(LEX_NS + "w")

        def part(name):
            el = e.find(LEX_NS + name)
            return render_strongs(el).strip() if el is not None else None

        rows.append((e.get("id")[1:], w.get(XML_LANG), w.get("pos"), pointed(w.text), w.get("pron"),
                     w.get("xlit"), part("source"), part("meaning"), part("usage"), part("note")))
    return rows


def parse_aug(path):
    root = ET.parse(path).getroot()
    return [(w.get("aug"), w.text) for w in root.iter(LEX_NS + "w")]


# ---------- spelling index ----------

class LemmaResolver:
    """morphhb lemma ('c/d/776', '1254 a', 'l', '1008+') to Lexical Index entry ids."""

    def __init__(self, entries, aug):
        self.aug = dict(aug)
        self.by_strong = collections.defaultdict(list)
        for e in entries:
            if e["strong"]:
                self.by_strong[e["strong"]].append(e)
        # Prefix-only lemmas (a preposition carrying a suffix, e.g. 'l' for לָהֶם). The Lexical
        # Index gives the Hebrew prefix entries the letter code as their Strong's value. The
        # Aramaic ones have no code, so they are matched by headword instead.
        self.prefix = {code: [e["id"] for e in es] for code, es in self.by_strong.items() if code.isalpha()}
        arc_heads = {"b": "ב", "k": "כ", "l": "ל", "m": "מן"}
        self.arc_prefix = {}
        for code, head in arc_heads.items():
            ids = [e["id"] for e in entries if e["lang"] == "arc" and e["headword_c"] == head]
            if ids:
                self.arc_prefix[code] = ids[:1]

    def resolve(self, lemma, lang):
        parts = [p.strip() for p in lemma.split("/")]
        numbers = [p for p in parts if p[:1].isdigit()]
        prefixes = [p for p in parts if p and not p[:1].isdigit()]
        if not numbers:
            code = prefixes[-1] if prefixes else ""
            if lang == "arc" and code in self.arc_prefix:
                return self.arc_prefix[code], prefixes[:-1]
            return self.prefix.get(code, []), prefixes[:-1]
        key = numbers[-1].replace(" ", "").rstrip("+")
        if key in self.aug:
            return [self.aug[key]], prefixes
        # A plain number where only lettered variants exist (e.g. 7451 vs 7451a/b/c): keep all.
        base = re.match(r"\d+", key).group(0)
        return [e["id"] for e in self.by_strong.get(base, [])], prefixes


def parse_morphhb(book_paths, resolver, stats):
    groups = {}
    for path in book_paths:
        root = ET.parse(path).getroot()
        for verse in root.iter(OSIS_NS + "verse"):
            ref = verse.get("osisID")
            qere = {w.get("id") for rdg in verse.iter(OSIS_NS + "rdg") for w in rdg.iter(OSIS_NS + "w")}
            for w in verse.iter(OSIS_NS + "w"):
                stats["words"] += 1
                text, lemma, morph = w.text or "", w.get("lemma") or "", w.get("morph") or ""
                lang = "arc" if morph.startswith("A") else "heb"
                variant = "qere" if w.get("id") in qere else ("ketiv" if w.get("type") == "x-ketiv" else None)
                ids, prefixes = resolver.resolve(lemma, lang)
                segs = text.split("/")
                # Leading text segments correspond to the lemma's prefix codes.
                if prefixes and len(segs) > len(prefixes):
                    bare_text = "".join(segs[len(prefixes):])
                else:
                    bare_text = text
                    if prefixes and ids:
                        stats["prefix segments not matched"] += 1
                form, bare = pointed(text), pointed(bare_text)
                if not ids:
                    stats["words unresolved"] += 1
                    ids = [None]
                elif len(ids) > 1:
                    stats["words with several candidate entries"] += 1
                for entry_id in ids:
                    key = (form, bare, entry_id, lemma, morph, variant)
                    g = groups.get(key)
                    if g is None:
                        g = groups[key] = [0, []]
                    g[0] += 1
                    if not g[1] or g[1][-1] != ref:
                        g[1].append(ref)
    for (form, bare, entry_id, lemma, morph, variant), (count, refs) in groups.items():
        yield (form, consonantal(form), bare, consonantal(bare), entry_id, lemma, morph, variant,
               count, " ".join(refs))


# ---------- build ----------

def build(sources, output):
    lex = sources / "HebrewLexicon"
    print("Parsing HebrewLexicon")
    entries, related = parse_lexical_index(lex / "LexicalIndex.xml")
    bdb = parse_bdb(lex / "BrownDriverBriggs.xml")
    strongs = parse_strongs(lex / "HebrewStrong.xml")
    aug = parse_aug(lex / "AugIndex.xml")

    print("Parsing morphhb")
    stats = collections.Counter()
    resolver = LemmaResolver(entries, aug)
    forms = list(parse_morphhb([sources / "morphhb" / f"{b}.xml" for b in MORPHHB_BOOKS], resolver, stats))

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    cols = list(entries[0].keys())
    db.executemany(f"INSERT INTO entries ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                   [tuple(e[c] for c in cols) for e in entries])
    db.executemany("INSERT OR IGNORE INTO related VALUES (?,?,?)", related)
    db.executemany("INSERT INTO bdb VALUES (?,?,?,?,?,?,?)", bdb)
    db.executemany("INSERT INTO strongs VALUES (?,?,?,?,?,?,?,?,?,?)", strongs)
    db.executemany("INSERT INTO aug VALUES (?,?)", aug)
    db.executemany("INSERT INTO forms VALUES (?,?,?,?,?,?,?,?,?,?)", forms)

    entry_ids = {e["id"] for e in entries}
    bdb_ids = {r[0] for r in bdb}
    strong_numbers = {r[0] for r in strongs}
    checks = {
        "entries": len(entries),
        "bdb entries": len(bdb),
        "strongs entries": len(strongs),
        "aug numbers": len(aug),
        "spelling rows": len(forms),
        "bible words": stats["words"],
        "bible words unresolved": stats["words unresolved"],
        "bible words with several candidate entries": stats["words with several candidate entries"],
        "bible words whose prefixes could not be split off": stats["prefix segments not matched"],
        "entries whose bdb id is missing from BDB": sum(1 for e in entries if e["bdb_id"] and e["bdb_id"] not in bdb_ids),
        "entries whose strong number is missing from Strong's": sum(
            1 for e in entries if e["strong"] and e["strong"].isdigit() and e["strong"] not in strong_numbers),
        "aug numbers pointing to unknown entries": sum(1 for _, eid in aug if eid not in entry_ids),
        "related links to unknown entries": sum(1 for _, rid, _ in related if rid not in entry_ids),
    }
    meta = {
        "schema_version": SCHEMA_VERSION,
        "hebrewlexicon_commit": HEBREWLEXICON_COMMIT,
        "morphhb_commit": MORPHHB_COMMIT,
        "attribution": "Lexical data from the Open Scriptures Hebrew Bible Project (CC BY 4.0); "
                       "BDB and Strong's text are public domain. Original work of the Open Scriptures "
                       "Hebrew Bible available at https://github.com/openscriptures/morphhb",
    }
    meta.update({f"check: {k}": str(v) for k, v in checks.items()})
    db.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
    db.commit()
    db.execute("VACUUM")
    db.close()
    os.replace(tmp, output)

    print(f"\nWrote {output} ({output.stat().st_size / 1e6:.1f} MB)")
    for k, v in checks.items():
        print(f"  {k}: {v}")


def main():
    ap = argparse.ArgumentParser(description="Build Benneria's lexicon database")
    ap.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="download cache directory")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--offline", action="store_true", help="fail instead of downloading missing sources")
    args = ap.parse_args()
    build(fetch_sources(args.sources, args.offline), args.output)


if __name__ == "__main__":
    main()
