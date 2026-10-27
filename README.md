# Benneria

A small web app for reading the Hebrew Bible, with four parts:

- **The dictionary** (`/lexicon`): type a word as it appears in the Bible, with or without
  vowels and prefixes, and Benneria finds its dictionary entries in Brown-Driver-Briggs and
  Strong's.
- **The notebook** (`/notebook`): take notes on Bible verses, chapter by chapter, with verb
  tables alongside the text. See [Benneria Notebook](#benneria-notebook) below.
- **BHS** (`/bhs`): read a chapter of the Hebrew Bible text, picking the book and chapter from
  two dropdowns. Nothing else; no notes.
- **Statistics** (`/stats`): how often each verb root occurs in each binyan across the whole
  Hebrew Bible, with a binyan/tense chart and the dictionary's own definitions. See
  [Statistics](#statistics) below.

The root page (`/`) links to all four. It works offline: the data is local databases built from
the Open Scriptures Hebrew Bible Project and BHSA (see [Lexicon data](#lexicon-data) and
[Benneria Notebook](#benneria-notebook); BHS and Statistics read the notebook's own
`bhsa.sqlite`, not a database of their own).

Built with [Flask](https://flask.palletsprojects.com/); the dictionary's data build and search
use only the Python standard library.

## Run

```sh
uv run benneria                                # http://localhost:1525
uv run benneria --port 9000 --host 0.0.0.0 --open
```

Without uv: install the package (`pip install .`), then run `benneria`.

`uv run benneria` uses Flask's development server, for local use.

### In production

Run the app under [gunicorn](https://gunicorn.org/) (Linux and macOS), with the settings in
`gunicorn.conf.py`:

```sh
uv run gunicorn benneria_web.app:app                         # http://127.0.0.1:1525, 4 workers
WEB_CONCURRENCY=8 uv run gunicorn benneria_web.app:app --bind 0.0.0.0:1525
```

It runs several worker processes, queues up to 2048 waiting connections, restarts a worker
stuck on a request for over 30 s, and keeps connections alive between requests. On this
development machine, 4 workers served about 3,000 lookups a second with 32 to 128 simultaneous
clients, at a few tens of milliseconds each, with memory steady at about 190 MB in total. The
app is a standard WSGI application, `benneria_web.app:app`, so other WSGI servers (e.g. waitress
on Windows) can run it too.

### With Docker

```sh
docker build -t benneria .
docker run -p 1525:1525 benneria                        # http://localhost:1525
docker run -p 1525:1525 -e WEB_CONCURRENCY=8 benneria   # more workers
```

The image (about 150 MB) runs gunicorn with `gunicorn.conf.py` as an unprivileged user, on
Python 3.14 with the dependencies pinned in `uv.lock`. Both databases are inside the package, so
the image needs no network, and it has a health check on the API. The notebook's notes and
tables need a writable volume at `/data` to survive a restart (see `compose.yaml`); without one
they are lost when the container stops, since everything else in the image is read-only.

CI publishes the image as `ghcr.io/nplinden/benneria` (`latest` follows the main branch):

```sh
docker run -p 1525:1525 -v benneria-notebook-data:/data ghcr.io/nplinden/benneria:latest
```

`compose.yaml` is a sample Docker Compose setup for that image: `docker compose up -d` starts it
on port 1525 (or `BENNERIA_PORT`), restarting it automatically, with a read-only filesystem apart
from that `/data` volume. `docker compose pull` fetches a newer published image.

Limits and caching:

- A lookup is limited to 20 words and 300 characters (`MAX_WORDS`, `MAX_CHARS` in `local.py`);
  longer input gets a 400. The slowest lookup allowed takes about 25 ms.
- API answers are cacheable for a day (`Cache-Control: public, max-age=86400`), with an ETag
  that changes whenever the database or the search code changes. A request sent with the
  current ETag gets `304 Not Modified` without the search running. So after a deploy, browsers
  may keep showing their cached answer to a lookup for up to a day.
- The page and its static files are revalidated on every load (`no-cache` with an ETag), so
  changes to them show immediately. Errors are never cached.

Options:

| Flag     | Default     | Description                    |
| -------- | ----------- | ------------------------------ |
| `--host` | `127.0.0.1` | Interface to bind              |
| `--port` | `1525`      | Port to listen on              |
| `--open` | off         | Open the browser on start      |

Binding to `0.0.0.0` lets anyone on your network use the server.

Search from the command line:

```sh
uv run python -m benneria.local "וַיִּשְׁמְרוּ"
uv run python -m benneria.local "בָּרָא" --ref "Gen 1:1"
```

## Features

- Finds inflected and prefixed forms through a spelling index of every word in the Hebrew Bible,
  e.g. `וַיִּשְׁמְרוּ` → שָׁמַר "keep"
- Search runs every step and merges the results, closest matches first: exact spelling (Bible
  forms and dictionary headwords), consonants only, without prefixes, headwords by consonants,
  then each word of a phrase. A word with several entries finds them all: `תורה` gives both
  8451 "law" and 8452 "custom"
- A context verse ("Gen 1:1", "Lev 19.3", "I Samuel 3") picks the entry the word has there
- Results ranked by phrase order, context verse, exact spelling, Hebrew before Aramaic, then
  frequency
- One card per dictionary entry, showing both Strong's definition and the full BDB entry (with
  tooltips naming verses and parts of speech)
- Related entries and BDB and Strong's cross-references open the entry
  they point to; each opened entry has its own URL
- Filters by language and part of speech
- Back/forward navigation, dark mode

## Layout

Five packages: `benneria` (the dictionary), `benneria_notebook` (the notebook), `benneria_bhs`
(BHS) and `benneria_stats` (Statistics) each define their routes as a Flask
[`Blueprint`](https://flask.palletsprojects.com/en/stable/blueprints/), with no dependency on
being run on their own; `benneria_web` combines them into the one app that actually runs, adding
the root page and the shared `/static/`.

- `src/benneria_web/`: the combined app
  - `app.py`: the Flask app: registers the four blueprints, serves `/`, and serves `/static/`
    from all four apps' `static/` directories (their file names don't collide)
  - `server.py`: the `benneria` command: runs the app on Flask's development server
  - `static/index.html`: the root page, linking to `/lexicon`, `/notebook`, `/bhs` and `/stats`
- `gunicorn.conf.py`: production server settings (workers, connection queue, timeouts)
- `src/benneria/`: the dictionary
  - `local.py`: search over `data/lexicon.sqlite`, and opening entries by id, BDB id, Strong's
    number or a verb root's exact consonants (`/api/entry?root=`, used by Statistics)
  - `refs.py`: Bible references ("Lev 19:3", "I Samuel 3") to OSIS ids ("Lev.19.3")
  - `hebrew.py`: Hebrew normalization (cantillation and vowel stripping), shared by the data build and search
  - `app.py`: the blueprint: the page at `/lexicon`, `/api/lookup` and `/api/entry`
  - `static/`: the frontend
    - `index.html`: page markup
    - `style.css`: styles, shared with the notebook, BHS and Statistics
    - `labels.js`: display names for parses, parts of speech and languages
    - `entry-card.js`: renders one dictionary entry; shared with Statistics
    - `app.js`: rendering, filters, search and the options dialog
  - `data/lexicon.sqlite`: the lexicon database, generated by `scripts/build_data.py`
- `src/benneria_notebook/`: the notebook (see [Benneria Notebook](#benneria-notebook) below)
  - `app.py`: the blueprint: the page at `/notebook`, and its API
  - `store.py`: the notes database; `bhsa.py`: the Bible text, shared with `benneria_bhs` and `benneria_stats`
  - `static/`: page, styles, book names, Markdown renderer
- `src/benneria_bhs/`: BHS, a chapter of Bible text and nothing else
  - `app.py`: the blueprint: the page at `/bhs`, and `/api/bhs/<book>/<chapter>`
  - `static/`: page, its top bar's styles, and the book/chapter dropdowns' logic
- `src/benneria_stats/`: Statistics (see [Statistics](#statistics) below)
  - `stats.py`: the root/binyan and binyan/tense counts, computed once from `bhsa.sqlite`
  - `app.py`: the blueprint: the page at `/stats`, `/api/stats/roots` and `/api/stats/chart`
  - `static/`: page, the table/chart styles, and their sorting, paging and selection logic
- `scripts/build_data.py`: builds the lexicon database
- `scripts/build_bhsa.py`: builds the notebook's (and BHS's and Statistics') Bible-text database
- `scripts/compare_backends.py`: compares search results with the Sefaria API, the app's former data source
- `tests/`: the test suite

## Tests

```sh
uv run pytest
```

The tests cover normalization, reference parsing, the data build's helpers, the database's
integrity, search behaviour, every word of a seeded sample of verses (each must find its own
entry, ranked first, with its verse as context), and the HTTP endpoints.

`scripts/compare_backends.py` checks search quality against Sefaria's Lexicon API on a seeded
sample of 200 words, writing `build/compare_backends.md`. It needs network access;
`--reuse-sefaria build/compare_backends.json` re-runs only the local side of an earlier run.

## Lexicon data

`src/benneria/data/lexicon.sqlite` is built from two OpenScriptures projects, pinned to a commit
in the script:

```sh
uv run python scripts/build_data.py            # downloads sources into build/sources/
uv run python scripts/build_data.py --offline  # rebuild from the cached sources only
```

It holds the Lexical Index (linking BDB, Strong's and TWOT), BDB and Strong's entries
pre-rendered to HTML, the augmented Strong's index, and a spelling index of every word form in
the Hebrew Bible. The `meta` table records the source commits and the build's consistency
checks. The build is deterministic: the same sources produce a byte-identical file.

Attribution:

- Lexical data from the [Open Scriptures Hebrew Bible Project](https://github.com/openscriptures/HebrewLexicon),
  [CC BY 4.0](http://creativecommons.org/licenses/by/4.0/). The text of Brown-Driver-Briggs and
  Strong's Hebrew dictionary is in the public domain.
- Original work of the Open Scriptures Hebrew Bible available at
  https://github.com/openscriptures/morphhb ([CC BY 4.0](http://creativecommons.org/licenses/by/4.0/)),
  based on the public-domain Westminster Leningrad Codex.

Both are transformed here: converted from XML to SQLite, joined, and rendered to HTML. See
[DATA_LICENSE.md](DATA_LICENSE.md) for the full notice, the source commits and the list of
changes. The app's footer shows this attribution.

## Benneria Notebook

The notebook, in `src/benneria_notebook/`, served at `/notebook`, is for taking notes on
Biblical verses, chapter by chapter (first draft).

- The sidebar lists the books of the Hebrew Bible by part (Torah, Nevi'im, Ketuvim), each with its
  chapters. Book names are in French by default, or in English or Hebrew (a setting kept in the
  browser).
- Double-clicking a chapter opens its notebook. A greyed chapter has none yet; double-clicking it
  creates one. "Supprimer ce carnet", next to the chapter's title, deletes a notebook with its
  notes and tables after confirmation; the chapter is greyed again.
- A chapter's notebook shows each verse in a box, with a note after each one (between it and
  the next verse). Click a note to edit it; it's written in Markdown (*italic*, **bold**, lists,
  quotes, links) and shown formatted once you leave it. Notes save automatically shortly after
  you stop typing; an emptied note is removed.
- Each verse can also have a verb table (Verbe, Racine, Binyan, Temps, Personne, Traduction), between
  the verse and its note: "+ Tableau des verbes" adds one, "+ Ligne" adds rows, × removes one
  (the table goes away with its last row), and Enter moves down a row. Cells are free text, saved
  automatically like notes.

The notebook keeps its own data in a writable SQLite database, `$BENNERIA_NOTEBOOK_DB` or else
`~/.local/share/benneria-notebook/notebook.sqlite` (in the Docker image, `/data/notebook.sqlite`,
on the `/data` volume). It uses the dictionary's stylesheet, so the two apps look alike.

### Bible text

Its Bible text (shared with [BHS](#bhs) below) comes from [BHSA](https://github.com/ETCBC/bhsa),
the ETCBC's annotated edition of the Biblia Hebraica Stuttgartensia, in a separate database,
`src/benneria_notebook/data/bhsa.sqlite`:

```sh
uv run --group build python scripts/build_bhsa.py   # downloads BHSA (about 270 MB) on first run
```

It holds the 39 books, 23,213 verses (with ids such as `Gen.1.1`, matching the dictionary's
verse numbering exactly), and 426,590 words with their lexeme, gloss and parse. BHSA counts a
prefix such as בְּ as a word of its own, so each word also records which written word it belongs
to. Verse texts and the words' forms without cantillation or vowels are not stored but computed by
`benneria_notebook/bhsa.py`; a check during development confirmed this reproduces every verse
exactly. The build needs Text-Fabric, in the `build` dependency group, which the app does not
install.

BHSA's license is **CC BY-NC 4.0: no commercial use** without the German Bible Society's
consent, and its citation is https://doi.org/10.17026/dans-z6y-skyh. The dictionary's code and
data are independent of it, even though all three apps now run in the same process and image.
See [DATA_LICENSE.md](DATA_LICENSE.md).

## BHS

BHS, in `src/benneria_bhs/`, served at `/bhs`, shows one chapter of the Hebrew Bible text at a
time: pick the book and chapter from the two dropdowns at the top of the page. Nothing else —
no notes, no verb tables, and no notebook needs to exist for a chapter to show.

It reads the same `bhsa.sqlite` as the notebook (above), through the same `benneria_notebook.bhsa`
module, so there is nothing of its own to build. It gets the list of books and their chapter
counts from the notebook's `/api/toc`, rather than repeating that lookup.

## Statistics

Statistics, in `src/benneria_stats/`, served at `/stats`, reproduces the verb-form analysis from
[hegram](https://github.com/nplinden/hegram)'s own statistics page, over the same `bhsa.sqlite`
(not hegram's own data build, and not polars — nothing here is large enough to need it: about
74,000 verb occurrences, read once with plain SQL when the app starts).

- A table of every verb root and how often it occurs in each of the seven common binyanim
  (Paal, Piel, Hifil, Hitpael, Hofal, Pual, Nifal), with a Total column, most frequent root
  first. Click a column header to sort by it.
- A bar chart of the same counts, one bar per binyan, each in that binyan's own color (matching
  the author's existing Anki color-coding for the binyanim, so a color means the same binyan in
  both places). Hover a bar for its breakdown across the eight tenses (Qatal, Yiqtol, Wayyiqtol,
  Imperative, the two infinitives, and the two participles).
- Click a row anywhere to restrict the chart to that root (click it again to go back to every
  root). Ctrl/Cmd+click adds a root to the selection, and Shift+click adds every root between it
  and the last one clicked. With one root selected, the chart's title links to its dictionary
  entry at `/lexicon?word=`; with several, it just reads "N roots".

## Licenses

The code is released under the [MIT License](LICENSE). The two databases keep their own
licenses, described in [DATA_LICENSE.md](DATA_LICENSE.md): CC BY 4.0 for the dictionary's
`lexicon.sqlite`, and CC BY-NC 4.0 (non-commercial) for `bhsa.sqlite`, used by the notebook, by
BHS, and by Statistics.
