# Data licenses

This repository contains two databases, under different licenses. Neither notice covers the code,
which is under the MIT License (see `LICENSE`).

| Database | Used by | Built by | License |
|---|---|---|---|
| `src/benneria/data/lexicon.sqlite` | The dictionary (`/lexicon`) | `scripts/build_data.py` | CC BY 4.0 |
| `src/benneria_notebook/data/bhsa.sqlite` | The notebook (`/notebook`) | `scripts/build_bhsa.py` | **CC BY-NC 4.0: non-commercial** |

# lexicon.sqlite

## Sources

The database is built by `scripts/build_data.py` from two projects of the
[Open Scriptures Hebrew Bible Project](https://hb.openscriptures.org/), at these commits:

| Source | Files used | Commit |
|---|---|---|
| [openscriptures/HebrewLexicon](https://github.com/openscriptures/HebrewLexicon) | `LexicalIndex.xml`, `BrownDriverBriggs.xml`, `HebrewStrong.xml`, `AugIndex.xml`, `BDBPartsOfSpeech.xml` | `21c9add13bc727d3a951361778e97e3ff7afd1ce` |
| [openscriptures/morphhb](https://github.com/openscriptures/morphhb) | `wlc/*.xml` (the 39 books of the Hebrew Bible) | `3d15126fb1ef74867fc1434be1942e837932691f` |

## License

Both sources are released under the
[Creative Commons Attribution 4.0 International license (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/),
and so is the database derived from them.

- The text of Brown-Driver-Briggs and of Strong's Hebrew dictionary is in the public domain.
- morphhb is based on the Westminster Leningrad Codex, which is in the public domain.

## Attribution

- Lexical data from the Open Scriptures Hebrew Bible Project
  (https://github.com/openscriptures/HebrewLexicon), CC BY 4.0.
- Original work of the Open Scriptures Hebrew Bible available at
  https://github.com/openscriptures/morphhb

The second line is the wording morphhb's
[LICENSE.md](https://github.com/openscriptures/morphhb/blob/master/LICENSE.md) asks for. The
dictionary shows both in its footer, and the database records them in its `meta` table.

## Changes made

The source XML is transformed, not redistributed as is:

- converted to SQLite tables and joined: Lexical Index entries are linked to their BDB, Strong's
  and augmented Strong's records
- BDB and Strong's entries rendered from XML to HTML; BDB's Bible reference codes normalized
  (typos and irregular forms fixed) and given verse tooltips; BDB's part-of-speech abbreviations
  given tooltips from `BDBPartsOfSpeech.xml`, with three of its entries corrected (`gent`,
  `patr`, `Haph`); untagged parts of speech after a headword tagged; abbreviations in BDB's
  prose given tooltips
- the morphhb Bible reduced to a spelling index: each distinct word form with its entry, parse,
  occurrence count and verses; cantillation removed, and consonant-only and prefix-less forms
  added

No endorsement by the Open Scriptures Hebrew Bible Project is implied.

# bhsa.sqlite

## Source

The database is built by `scripts/build_bhsa.py` from
[BHSA](https://github.com/ETCBC/bhsa), version 2021: the Biblia Hebraica Stuttgartensia
Amstelodamensis, the Eep Talstra Centre for Bible and Computer's linguistically annotated edition
of the Biblia Hebraica Stuttgartensia, read with [Text-Fabric](https://github.com/annotation/text-fabric).

## License

BHSA is released under the
[Creative Commons Attribution-NonCommercial 4.0 International license (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/),
and so is the database derived from it. In BHSA's own words: do not use the data for commercial
applications without consent; for any commercial use, contact the German Bible Society
(Deutsche Bibelgesellschaft).

This makes the notebook (`/notebook`) non-commercial, whatever the license of its code. The
dictionary's search and data (`/lexicon`, `src/benneria/`) do not use this database and remain
CC BY 4.0, even though both are served by the same app and image.

## Attribution

BHSA asks that publications of the data or results cite its persistent identifier:

- BHSA (Biblia Hebraica Stuttgartensia Amstelodamensis), Eep Talstra Centre for Bible and
  Computer, version 2021. https://doi.org/10.17026/dans-z6y-skyh

The database records this in its `meta` table.

## Changes made

- Selected from the corpus: the books, verses and words, each word's text (vowels and accents),
  the text following it, its lexeme with the lexeme's vocalised form, gloss and language, and
  its part of speech, verbal stem and tense, person, gender, number and state.
- Converted to SQLite tables. Verses get OSIS identifiers (`Gen.1.1`) and words a written-word
  number within the verse (prefixes such as בְּ are separate BHSA words).
- Not stored: phrases, clauses, sentences and BHSA's other features.

No endorsement by the Eep Talstra Centre for Bible and Computer or the German Bible Society is
implied.
