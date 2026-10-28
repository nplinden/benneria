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

# The traditional verb classes, from a root's consonants (radicals R1, R2, R3), in display order.
# A root can be in several (נשׂא is pe-nun and lamed-aleph); "strong" is a triliteral root in
# none of the others. BHSA writes pe-vav roots with their yod (ישׁב) and lamed-he roots with
# their he (בנה), as the dictionaries do.
VERB_CLASSES = ["strong", "pe-guttural", "pe-aleph", "pe-nun", "pe-yod", "ayin-guttural",
                "ayin-vav-yod", "ayin-ayin", "lamed-guttural", "lamed-aleph", "lamed-he"]
# Pe-aleph in the grammars' sense: the few verbs whose aleph goes quiet (יֹאמַר, יֹאכַל). Other
# aleph-initial roots behave as gutturals, so are pe-guttural, as are these.
PE_ALEPH = {"אבד", "אבה", "אחז", "אכל", "אמר", "אפה"}
GUTTURALS = set("אהחע")


def verb_classes(root):
    """A root's verb classes (ids from VERB_CLASSES); none for a root of four or more letters."""
    r = root.replace("ׁ", "").replace("ׂ", "")  # shin and sin dots
    if len(r) != 3:
        return []
    r1, r2, r3 = r
    classes = []
    if r1 in GUTTURALS:
        classes.append("pe-guttural")
    if r in PE_ALEPH:
        classes.append("pe-aleph")
    if r1 == "נ" or r == "לקח":                 # לקח loses its lamed like a nun: יִקַּח
        classes.append("pe-nun")
    if r1 == "י" or r == "הלך":                 # הלך conjugates like a pe-vav: יֵלֵךְ
        classes.append("pe-yod")
    if r2 in GUTTURALS | {"ר"}:
        classes.append("ayin-guttural")
    if r2 in "וי" and r3 != "ה":                # not היה, צוה: their vav/yod is a consonant
        classes.append("ayin-vav-yod")
    if r2 == r3 and r3 != "ה":                  # כהה is lamed-he
        classes.append("ayin-ayin")
    if r3 in "חע":
        classes.append("lamed-guttural")
    if r3 == "א":
        classes.append("lamed-aleph")
    if r3 == "ה":
        classes.append("lamed-he")
    return classes or ["strong"]


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
    """Every root's occurrences in each common binyan, plus its total and verb classes, most
    frequent first: [{"root": ..., "total": ..., <binyan>: count, ..., "classes": [...]}]."""
    counts = {}
    for root, binyan, _tense in VERBS:
        counts.setdefault(root, dict.fromkeys(BINYANIM, 0))[binyan] += 1
    rows = [{"root": root, "total": sum(row.values()), **row, "classes": verb_classes(root)}
            for root, row in counts.items()]
    rows.sort(key=lambda r: -r["total"])
    return rows


def binyan_tense_counts(roots=None):
    """Occurrences of each tense per common binyan, as chart data: one row per binyan, in a
    fixed order, with every tense as a column (0 where it doesn't occur).

    Args:
        roots: restrict the count to these roots (none at all when empty); every root when None.
    """
    if roots is None:
        return ALL_ROOTS_BINYAN_TENSE_COUNTS
    return _binyan_tense_counts(roots)


def matching_roots(contains="", verb_class=""):
    """The roots the statistics page's filters accept, as its table shows them: those whose
    consonants contain `contains`, and in `verb_class` (an id from VERB_CLASSES) if given."""
    return [r["root"] for r in ROOT_BINYAN_COUNTS
            if contains in r["root"] and (not verb_class or verb_class in r["classes"])]


def _binyan_tense_counts(roots=None):
    roots = set(roots) if roots is not None else None
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
