"""
Bible references: "Leviticus 19:3", "Lev 19.3", "I Samuel 3", "Gen.1.1" to OSIS ids ("Lev.19.3"),
the form morphhb uses for verses.
"""

import re

# OSIS code and English name of each book, in Hebrew Bible order as morphhb lists them.
BOOKS = [
    ("Gen", "Genesis"), ("Exod", "Exodus"), ("Lev", "Leviticus"), ("Num", "Numbers"),
    ("Deut", "Deuteronomy"), ("Josh", "Joshua"), ("Judg", "Judges"), ("Ruth", "Ruth"),
    ("1Sam", "1 Samuel"), ("2Sam", "2 Samuel"), ("1Kgs", "1 Kings"), ("2Kgs", "2 Kings"),
    ("1Chr", "1 Chronicles"), ("2Chr", "2 Chronicles"), ("Ezra", "Ezra"), ("Neh", "Nehemiah"),
    ("Esth", "Esther"), ("Job", "Job"), ("Ps", "Psalms"), ("Prov", "Proverbs"),
    ("Eccl", "Ecclesiastes"), ("Song", "Song of Songs"), ("Isa", "Isaiah"), ("Jer", "Jeremiah"),
    ("Lam", "Lamentations"), ("Ezek", "Ezekiel"), ("Dan", "Daniel"), ("Hos", "Hosea"),
    ("Joel", "Joel"), ("Amos", "Amos"), ("Obad", "Obadiah"), ("Jonah", "Jonah"), ("Mic", "Micah"),
    ("Nah", "Nahum"), ("Hab", "Habakkuk"), ("Zeph", "Zephaniah"), ("Hag", "Haggai"),
    ("Zech", "Zechariah"), ("Mal", "Malachi"),
]
EXTRA_NAMES = {"psalm": "Ps", "songofsolomon": "Song", "canticles": "Song", "qohelet": "Eccl"}


def _key(name):
    name = name.lower().replace("_", " ")
    name = re.sub(r"^(iii|ii|i)\s+", lambda m: str(len(m.group(1))) + " ", name)
    return re.sub(r"[\s.]", "", name)


_EXACT = {}
for _osis, _name in BOOKS:
    _EXACT[_key(_osis)] = _osis
    _EXACT[_key(_name)] = _osis
for _name, _osis in EXTRA_NAMES.items():
    _EXACT[_name] = _osis
_NAMES = [(_key(name), osis) for osis, name in BOOKS]

_REF = re.compile(r"^\s*(.*?[^\d\s.:_])[\s._]*(\d+)?(?:\s*[.:_]\s*(\d+))?(?:\s*-.*)?\s*$")


class RefError(ValueError):
    pass


def book_osis(name):
    key = _key(name)
    if key in _EXACT:
        return _EXACT[key]
    # A unique prefix of an English name: "Levit", "Eccles", "Zeph".
    matches = {osis for full, osis in _NAMES if len(key) >= 2 and full.startswith(key)}
    if len(matches) == 1:
        return matches.pop()
    raise RefError(f"Unknown book: {name!r}" if not matches else f"Ambiguous book: {name!r}")


def to_osis(ref):
    """'Leviticus 19:3' -> 'Lev.19.3'; 'Gen 1' -> 'Gen.1'; 'Ruth' -> 'Ruth'. A range keeps its start."""
    m = _REF.match(ref or "")
    if not m:
        raise RefError(f"Not a Bible reference: {ref!r}")
    book, chapter, verse = m.groups()
    return ".".join(p for p in (book_osis(book), chapter, verse) if p)


def in_ref(verse_id, osis_ref):
    """Whether a verse id ('Lev.19.3') falls within a book, chapter or verse reference."""
    return verse_id == osis_ref or verse_id.startswith(osis_ref + ".")
