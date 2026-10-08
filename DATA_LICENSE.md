# Data license

This notice covers `src/benneria/data/lexicon.sqlite`, the lexicon database the app's local
backend uses. It does not cover the app's code.

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
[LICENSE.md](https://github.com/openscriptures/morphhb/blob/master/LICENSE.md) asks for. The app
shows both in its footer when it runs with the local backend, and the database records them in its
`meta` table.

## Changes made

The source XML is transformed, not redistributed as is:

- converted to SQLite tables and joined: Lexical Index entries are linked to their BDB, Strong's
  and augmented Strong's records
- BDB and Strong's entries rendered from XML to HTML; BDB's Bible reference codes normalized
  (typos and irregular forms fixed) and given verse tooltips; BDB's part-of-speech abbreviations
  given tooltips from `BDBPartsOfSpeech.xml`, with three of its entries corrected (`gent`,
  `patr`, `Haph`)
- the morphhb Bible reduced to a spelling index: each distinct word form with its entry, parse,
  occurrence count and verses; cantillation removed, and consonant-only and prefix-less forms
  added

No endorsement by the Open Scriptures Hebrew Bible Project is implied.
