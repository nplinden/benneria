"""
Hebrew text normalization, shared by the data build and the lookup so both strip characters
the same way. The character ranges match Sefaria's word-form builder, so results line up
when the two backends are compared.
"""

import re
import unicodedata

# Cantillation and other marks that don't change the word: accents (U+0591-05AF), meteg,
# rafe, paseq, upper/lower dots. Vowels, dagesh and shin/sin dots are kept.
CANTILLATION = re.compile("[֑-ֽֿ֯׀ׅׄ]")
# Everything above the consonants: cantillation plus vowels, dagesh, shin/sin dots, qamats qatan.
POINTS = re.compile("[֑-ֽֿ-ׇׅ]")
# morphhb separates prefixes and suffixes with "/".
MORPHEME_SEP = "/"


def _clean(text):
    return unicodedata.normalize("NFC", text or "").replace(MORPHEME_SEP, "").strip()


def pointed(text):
    """The word with vowels, without cantillation."""
    return CANTILLATION.sub("", _clean(text))


def consonantal(text):
    """The word's consonants only."""
    return POINTS.sub("", _clean(text))
