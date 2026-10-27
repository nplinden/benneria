"""
Verb-form statistics over the whole Hebrew Bible, reproducing hegram's statistics page
(https://github.com/nplinden/hegram): how often each root occurs in each common binyan, and the
binyan/tense breakdown for a root or the whole corpus.

Computed from the same corpus as the notebook and BHS (BHSA, via benneria_notebook.bhsa), in
plain Python rather than hegram's own dataframe pipeline, since nothing here is large enough to
need it: about 74,000 verb occurrences, loaded once when this module is imported.
"""

from collections import Counter
from contextlib import closing

from benneria_notebook import bhsa

# BHSA's verbal-stem codes (the words table's "vs" column) for the binyanim covered here, mapped
# to display names, in the order shown in the table and the chart. BHSA has about 20 binyanim in
# all; the rarer ones aren't part of this feature, matching hegram's own statistics page.
BINYAN_CODES = {"qal": "Paal", "piel": "Piel", "hif": "Hifil", "hit": "Hitpael",
                "hof": "Hofal", "pual": "Pual", "nif": "Nifal"}
BINYANIM = list(BINYAN_CODES.values())

# BHSA's verbal-tense codes ("vt"), in a fixed display order: the chart's stacking order.
TENSE_CODES = {"perf": "Qatal", "impf": "Yiqtol", "wayq": "Wayyiqtol", "impv": "Imperative",
               "infa": "Infinitive (absolute)", "infc": "Infinitive (construct)",
               "ptca": "Participle", "ptcp": "Participle (passive)"}
TENSES = list(TENSE_CODES.values())


def _load_verbs():
    """Every verb occurrence in a common binyan, as (root, binyan, tense). The corpus never
    changes while the app runs, so this runs once, not on every request."""
    with closing(bhsa.connect()) as db:
        rows = db.execute(
            "SELECT l.lexeme, w.vs, w.vt FROM words w JOIN lexemes l ON l.id = w.lexeme_id "
            "WHERE w.sp = 'verb' AND w.vs IN ({})".format(",".join("?" * len(BINYAN_CODES))),
            list(BINYAN_CODES)).fetchall()
    return [(root, BINYAN_CODES[vs], TENSE_CODES.get(vt, vt)) for root, vs, vt in rows]


def _root_binyan_counts():
    """Every root's occurrences in each common binyan, plus its total, most frequent first:
    [{"root": ..., "total": ..., <binyan>: count, ...}]."""
    counts = {}
    for root, binyan, _tense in VERBS:
        counts.setdefault(root, dict.fromkeys(BINYANIM, 0))[binyan] += 1
    rows = [{"root": root, "total": sum(row.values()), **row} for root, row in counts.items()]
    rows.sort(key=lambda r: -r["total"])
    return rows


def binyan_tense_counts(roots=None):
    """Occurrences of each tense per common binyan, as chart data: one row per binyan, in a
    fixed order, with every tense as a column (0 where it doesn't occur).

    Args:
        roots: restrict the count to these roots; every root when empty or None.
    """
    if not roots:
        return ALL_ROOTS_BINYAN_TENSE_COUNTS
    return _binyan_tense_counts(roots)


def _binyan_tense_counts(roots=None):
    roots = set(roots) if roots else None
    counts = {b: Counter() for b in BINYANIM}
    for root, binyan, tense in VERBS:
        if roots is None or root in roots:
            counts[binyan][tense] += 1
    return [{"binyan": b, **{t: counts[b][t] for t in TENSES}} for b in BINYANIM]


# The corpus never changes while the app runs, so the tables that don't depend on a selection are
# computed once. Callers must not modify them.
VERBS = _load_verbs()
ROOT_BINYAN_COUNTS = _root_binyan_counts()
# The binyan/tense chart over every root, the statistics page's default chart.
ALL_ROOTS_BINYAN_TENSE_COUNTS = _binyan_tense_counts()
