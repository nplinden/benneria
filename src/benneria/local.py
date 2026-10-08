"""
Local word lookup over data/lexicon.sqlite (built by scripts/build_data.py).

Search follows Sefaria's approach and stops at the first step that finds something:
  1. exact pointed spelling, among the Hebrew Bible's word forms (skipped for unpointed input)
  2. consonants only (also run when always_consonants is set)
  3. consonants only, with the word's prefixes removed
  4. dictionary headwords, consonants only, for words that don't occur in the Bible
  5. for multi-word input, each run of consecutive words, longest first (unless never_split;
     also run when always_split is set)
With a context reference, spellings found in that verse are kept, falling back to all.
Results are ranked by: position in a multi-word input, use in the context verse, Hebrew before
Aramaic, then frequency.

Try it from the command line:
    uv run python -m benneria.local "וַיִּשְׁמְרוּ" [--ref "Ps 59:1"]
"""

import collections
import re
import sqlite3
import threading
from importlib.resources import files

from .hebrew import consonantal, pointed
from .refs import in_ref, to_osis

DB_PATH = files("benneria") / "data" / "lexicon.sqlite"
# Word separators in a typed phrase: spaces, maqaf, sof pasuq, paseq, colon, period.
SPLIT = re.compile(r"[\s:\u05be\u05c3\u05c0.]+")
HAS_POINTS = re.compile("[\u0591-\u05c7]")


class LocalLexicon:
    def __init__(self, path=DB_PATH):
        self.uri = f"file:{path}?mode=ro"
        self._local = threading.local()  # one connection per server thread

    @property
    def db(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = sqlite3.connect(self.uri, uri=True)
            conn.row_factory = sqlite3.Row
        return conn

    # ---------- search ----------

    def search(self, word, lookup_ref=None, always_consonants=False, always_split=False,
               never_split=False, strip_prefixes=True):
        """Returns {"query", "ref", "steps", "results"}; results are ranked entries.
        strip_prefixes=False skips step 3 (matching a word without its prefixes)."""
        word = re.sub(r"\s+", " ", word or "").strip()
        ref = to_osis(lookup_ref) if lookup_ref else None
        opts = (always_consonants, strip_prefixes)
        matches, steps = self._single(word, ref, *opts)
        words = [w for w in SPLIT.split(word) if w]
        if len(words) > 1 and not never_split and (not matches or always_split):
            for gram in _ngrams(words):
                found, gram_steps = self._single(gram, ref, *opts)
                if found:
                    # Remember which piece of the phrase matched, so results keep the phrase's order.
                    matches += [{**m, "piece": len(steps)} for m in found]
                    steps.append({"input": gram, "steps": gram_steps})
        return {"query": word, "ref": ref, "steps": steps, "results": self._entries(matches, ref)}

    def _single(self, word, ref, always_consonants, strip_prefixes):
        """Steps 1-4 for one word or phrase. Returns (match rows, names of the steps that matched)."""
        rows, steps = [], []
        if HAS_POINTS.search(word):
            rows = self._forms("form", pointed(word), ref)
            if rows:
                steps.append("exact")
        if not rows or always_consonants:
            found = self._forms("form_c", consonantal(word), ref)
            if found:
                rows += [r for r in found if r not in rows]
                steps.append("consonantal")
        if not rows and strip_prefixes:
            rows = self._forms("bare_c", consonantal(word), ref)
            if rows:
                steps.append("without prefixes")
        if not rows:
            rows = [{"entry_id": r["id"], "form": None, "morph": None, "variant": None, "count": 0,
                     "refs": "", "in_ref": False}
                    for r in self.db.execute("SELECT id FROM entries WHERE headword_c = ?",
                                             (consonantal(word),))]
            if rows:
                steps.append("headword")
        return rows, steps

    def _forms(self, column, value, ref):
        if not value:
            return []
        rows = [dict(r) for r in self.db.execute(
            f"SELECT entry_id, form, morph, variant, count, refs FROM forms "
            f"WHERE {column} = ? AND entry_id IS NOT NULL", (value,))]
        for r in rows:
            r["in_ref"] = bool(ref) and any(in_ref(v, ref) for v in r["refs"].split())
        if ref and any(r["in_ref"] for r in rows):
            rows = [r for r in rows if r["in_ref"]]
        return rows

    def open(self, entry_id=None, bdb=None, strong=None):
        """Entries by id, BDB id or Strong's number ('1254' gives 1254a and 1254b), for
        cross-references. Same shape as search(), with no matched forms."""
        if entry_id:
            sql, value = "SELECT id FROM entries WHERE id = ?", entry_id
        elif bdb:
            sql, value = "SELECT id FROM entries WHERE bdb_id = ? ORDER BY seq", bdb
        else:
            sql, value = "SELECT id FROM entries WHERE strong = ? ORDER BY seq", strong
        ids = [r["id"] for r in self.db.execute(sql, (value,))]
        results = [{**self.entry(i), "matches": [], "count": 0, "in_ref": False} for i in ids]
        return {"query": value, "ref": None, "steps": ["open"], "results": results}

    # ---------- results ----------

    def _entries(self, matches, ref):
        by_entry = collections.OrderedDict()
        for m in matches:
            by_entry.setdefault(m["entry_id"], []).append(m)
        results = []
        for entry_id, ms in by_entry.items():
            e = self.entry(entry_id)
            ms.sort(key=lambda m: (-m["in_ref"], -m["count"]))
            e["matches"] = [{
                "form": m["form"], "morph": m["morph"], "variant": m["variant"], "count": m["count"],
                "in_ref": m["in_ref"],
                # Verses in the context reference, else the first few, to show where the form occurs.
                "refs": [v for v in m["refs"].split() if in_ref(v, ref)][:5] if m["in_ref"]
                        else m["refs"].split()[:5],
            } for m in ms if m["form"]]
            e["count"] = sum(m["count"] for m in ms)
            e["in_ref"] = any(m["in_ref"] for m in ms)
            e["piece"] = min(m.get("piece", 0) for m in ms)
            results.append(e)
        # Phrase order first, then entries used in the context verse, then Hebrew before Aramaic
        # (98% of the Bible's words are Hebrew), then the most frequent.
        results.sort(key=lambda e: (e["piece"], -e["in_ref"], e["lang"] != "heb", -e["count"]))
        for e in results:
            del e["piece"]
        return results

    def entry(self, entry_id):
        db = self.db
        e = dict(db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone())
        strongs = None
        if e["strong"] and e["strong"].isdigit():
            row = db.execute("SELECT * FROM strongs WHERE number = ?", (e["strong"],)).fetchone()
            strongs = dict(row) if row else None
        bdb = db.execute("SELECT id, page, homonym, status, html FROM bdb WHERE id = ?",
                         (e["bdb_id"],)).fetchone() if e["bdb_id"] else None
        related = [dict(r) for r in db.execute(
            "SELECT e.id, e.headword, e.gloss, r.relation FROM related r JOIN entries e ON e.id = r.related_id "
            "WHERE r.entry_id = ? ORDER BY e.seq", (entry_id,))]
        nav = {k: dict(r) if r else None for k, r in (
            ("prev", db.execute("SELECT id, headword FROM entries WHERE seq = ?", (e["seq"] - 1,)).fetchone()),
            ("next", db.execute("SELECT id, headword FROM entries WHERE seq = ?", (e["seq"] + 1,)).fetchone()),
        )}
        del e["seq"], e["headword_c"]
        return {**e, "strongs": strongs, "bdb": dict(bdb) if bdb else None, "related": related, **nav}


def _ngrams(words):
    """Runs of consecutive words, longest first, excluding the whole input."""
    seen = []
    for n in range(len(words) - 1, 0, -1):
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i:i + n])
            if gram not in seen:
                seen.append(gram)
    return seen


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Search the local lexicon")
    ap.add_argument("word")
    ap.add_argument("--ref", help="context verse, e.g. 'Gen 1:1'")
    ap.add_argument("--always-consonants", action="store_true")
    ap.add_argument("--always-split", action="store_true")
    ap.add_argument("--never-split", action="store_true")
    a = ap.parse_args()
    out = LocalLexicon().search(a.word, a.ref, a.always_consonants, a.always_split, a.never_split)
    print(f"steps: {out['steps']}  ref: {out['ref']}")
    for e in out["results"]:
        forms = ", ".join(f"{m['form']} {m['morph']} ×{m['count']}" for m in e["matches"][:3])
        print(f"  {e['headword']}  {e['gloss'] or ''}  [{e['id']}, Strong's {e['strong'] or '-'}"
              f"{e['aug'] or ''}, {e['lang']}]  ×{e['count']}  {forms}")
