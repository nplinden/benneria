"""
Compare the local backend with the Sefaria API on a seeded sample of words.

Words are drawn from the local database by category, with a fixed seed so every run uses the
same sample. Each word is looked up both ways with the page's default options (ignore vowels on,
phrase splitting allowed), and the Strong's numbers each backend finds are compared:
  - from Sefaria, the "BDB Augmented Strong" entries' strong_number
  - locally, the entries' Strong's number, without the augmented letter (Sefaria drops it)
The word's own entry (the one it was drawn from) is the expected answer.

Run from the repository root (needs network for Sefaria):
    uv run python scripts/compare_backends.py [--per-category 25] [--seed 2026]

Writes build/compare_backends.md and build/compare_backends.json. After a change to the local
backend, --reuse-sefaria build/compare_backends.json re-runs only the local side, keeping the
Sefaria answers of that earlier run (same seed and sample size).
"""

import argparse
import json
import random
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from benneria.local import DB_PATH, LocalLexicon

ROOT = Path(__file__).resolve().parent.parent
SEFARIA_API = "https://www.sefaria.org/api/words/"  # the app's former data source
OUT = ROOT / "build"

# Each category: (description, SQL returning rows of (word, expected Strong's number)). The
# entries table is aliased e; only entries with a numeric Strong's number can be compared with
# Sefaria, so sample() adds that condition.
CATEGORIES = {
    "common": ("frequent Bible forms (50+ occurrences)",
               "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
               "WHERE f.count >= 50 AND f.variant IS NULL"),
    "rare": ("forms occurring once or twice",
             "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
             "WHERE f.count <= 2 AND f.variant IS NULL"),
    "prefixed": ("forms with a prefix (ו, ה, ב, ל, …)",
                 "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
                 "WHERE f.bare != f.form AND f.variant IS NULL"),
    "aramaic": ("Aramaic forms",
                "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
                "WHERE f.morph LIKE 'A%' AND f.variant IS NULL"),
    "proper_names": ("forms of proper names",
                     "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
                     "WHERE e.pos = 'Np' AND f.variant IS NULL"),
    "homographs": ("forms of augmented a/b homographs",
                   "SELECT f.form, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
                   "WHERE e.aug IS NOT NULL AND f.variant IS NULL"),
    "unpointed": ("Bible forms typed without vowels",
                  "SELECT f.form_c, e.strong FROM forms f JOIN entries e ON e.id = f.entry_id "
                  "WHERE f.variant IS NULL"),
    "headwords": ("dictionary headwords",
                  "SELECT e.headword, e.strong FROM entries e WHERE 1"),
}


def sample(db, per_category, seed):
    rng = random.Random(seed)
    words = []
    for name, (_, sql) in CATEGORIES.items():
        rows = [(w, s) for w, s in db.execute(sql + " AND e.strong GLOB '[0-9]*'") if w]
        rows = sorted(set(rows))  # stable order before sampling
        for word, strong in rng.sample(rows, min(per_category, len(rows))):
            words.append({"category": name, "word": word, "expected": strong})
    return words


def sefaria_strongs(word, retries=2):
    """Strong's numbers of Sefaria's BDB Augmented Strong entries, or None if the API failed."""
    url = (SEFARIA_API + urllib.parse.quote(word, safe="") + "?"
           + urllib.parse.urlencode({"always_consonants": "1", "never_split": "0"}))
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "benneria-compare/1.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            return [e["strong_number"] for e in data
                    if isinstance(e, dict) and e.get("parent_lexicon") == "BDB Augmented Strong"
                    and e.get("strong_number")]
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def local_strongs(lexicon, word):
    results = lexicon.search(word, always_consonants=True)["results"]
    return [e["strong"] for e in results if e["strong"] and e["strong"][:1].isdigit()]


def unique(xs):
    return list(dict.fromkeys(xs))


def compare(words, delay, previous=None):
    lexicon = LocalLexicon()
    for i, w in enumerate(words, 1):
        w["local"] = unique(local_strongs(lexicon, w["word"]))
        if previous is not None:
            w["sefaria"] = previous[(w["category"], w["word"])]
        else:
            w["sefaria"] = sefaria_strongs(w["word"])
            if w["sefaria"] is not None:
                w["sefaria"] = unique(w["sefaria"])
            time.sleep(delay)  # be gentle with the Sefaria API
        print(f"  {i}/{len(words)} {w['category']:12} {w['word']}", flush=True)
    return words


def summarize(words):
    rows = []
    ok = [w for w in words if w["sefaria"] is not None]
    for name, (desc, _) in list(CATEGORIES.items()) + [("all", ("all categories", None))]:
        ws = [w for w in ok if name == "all" or w["category"] == name]
        if not ws:
            continue
        n = len(ws)
        local_hit = sum(w["expected"] in w["local"] for w in ws)
        sef_hit = sum(w["expected"] in w["sefaria"] for w in ws)
        local_top = sum(bool(w["local"]) and w["local"][0] == w["expected"] for w in ws)
        sef_top = sum(bool(w["sefaria"]) and w["sefaria"][0] == w["expected"] for w in ws)
        same = sum(set(w["local"]) == set(w["sefaria"]) for w in ws)
        rows.append({"category": name, "description": desc, "words": n,
                     "local_found": local_hit, "sefaria_found": sef_hit,
                     "local_first": local_top, "sefaria_first": sef_top, "same_set": same})
    return rows


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def write_report(words, rows, seed, per_category):
    failed = [w for w in words if w["sefaria"] is None]
    lines = [
        "# Backend comparison: local vs Sefaria", "",
        f"Seed {seed}, {per_category} words per category, {len(words)} words; "
        f"Sefaria failed for {len(failed)}.", "",
        "*found*: the word's own Strong's number is among the results. *first*: it is the first "
        "result. *same set*: both backends return the same Strong's numbers.", "",
        "| Category | Words | Local found | Sefaria found | Local first | Sefaria first | Same set |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['category']} ({r['description']}) | {r['words']} | "
                     f"{pct(r['local_found'], r['words'])} | {pct(r['sefaria_found'], r['words'])} | "
                     f"{pct(r['local_first'], r['words'])} | {pct(r['sefaria_first'], r['words'])} | "
                     f"{pct(r['same_set'], r['words'])} |")
    misses = [w for w in words if w["sefaria"] is not None and w["expected"] not in w["local"]]
    lines += ["", f"## Words whose own entry the local backend misses ({len(misses)})", ""]
    lines += [f"- {w['category']}: `{w['word']}` expected {w['expected']}, local {w['local']}, "
              f"Sefaria {w['sefaria']}" for w in misses] or ["None."]
    sef_misses = [w for w in words if w["sefaria"] is not None and w["expected"] not in w["sefaria"]
                  and w["expected"] in w["local"]]
    lines += ["", f"## Found locally but not by Sefaria ({len(sef_misses)})", ""]
    lines += [f"- {w['category']}: `{w['word']}` expected {w['expected']}, Sefaria {w['sefaria']}"
              for w in sef_misses] or ["None."]
    if failed:
        lines += ["", "## Sefaria failures", ""] + [f"- `{w['word']}`" for w in failed]
    OUT.mkdir(exist_ok=True)
    (OUT / "compare_backends.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "compare_backends.json").write_text(
        json.dumps({"seed": seed, "per_category": per_category, "summary": rows, "words": words},
                   ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Compare the local backend with the Sefaria API")
    ap.add_argument("--per-category", type=int, default=25)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between Sefaria requests")
    ap.add_argument("--reuse-sefaria", type=Path, metavar="JSON",
                    help="take Sefaria's answers from an earlier run's JSON instead of the API")
    args = ap.parse_args()
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    words = sample(db, args.per_category, args.seed)
    previous = None
    if args.reuse_sefaria:
        old = json.loads(args.reuse_sefaria.read_text(encoding="utf-8"))
        previous = {(w["category"], w["word"]): w["sefaria"] for w in old["words"]}
        missing = [w for w in words if (w["category"], w["word"]) not in previous]
        if missing:
            raise SystemExit(f"{len(missing)} sampled words are not in {args.reuse_sefaria}; "
                             "use the same --seed and --per-category")
    print(f"Comparing {len(words)} words", flush=True)
    words = compare(words, args.delay, previous)
    rows = summarize(words)
    write_report(words, rows, args.seed, args.per_category)
    for r in rows:
        print(f"  {r['category']:12} local {pct(r['local_found'], r['words']):14} "
              f"sefaria {pct(r['sefaria_found'], r['words']):14} same {pct(r['same_set'], r['words'])}")
    print(f"Wrote {OUT / 'compare_backends.md'}")


if __name__ == "__main__":
    main()
