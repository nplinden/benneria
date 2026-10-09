# Benneria

A small web dictionary for Biblical Hebrew and Aramaic. Type a word as it appears in the Bible,
with or without vowels and prefixes, and Benneria finds its dictionary entries in
Brown-Driver-Briggs and Strong's. It works offline: the data
is a local database built from the Open Scriptures Hebrew Bible Project.

Built with [Flask](https://flask.palletsprojects.com/); the data build and search use only the Python standard library.

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
uv run gunicorn benneria.app:app                         # http://127.0.0.1:1525, 4 workers
WEB_CONCURRENCY=8 uv run gunicorn benneria.app:app --bind 0.0.0.0:1525
```

It runs several worker processes, queues up to 2048 waiting connections, restarts a worker
stuck on a request for over 30 s, and keeps connections alive between requests. On this
development machine, 4 workers served about 3,000 lookups a second with 32 to 128 simultaneous
clients, at a few tens of milliseconds each, with memory steady at about 190 MB in total. The
app is a standard WSGI application, `benneria.app:app`, so other WSGI servers (e.g. waitress on
Windows) can run it too.

### With Docker

```sh
docker build -t benneria .
docker run -p 1525:1525 benneria                        # http://localhost:1525
docker run -p 1525:1525 -e WEB_CONCURRENCY=8 benneria   # more workers
```

The image (about 150 MB) runs gunicorn with `gunicorn.conf.py` as an unprivileged user, on
Python 3.14 with the dependencies pinned in `uv.lock`. The lexicon database is inside the
package, so it needs no volume or network, and it has a health check on the API.

`compose.yaml` is a sample Docker Compose setup: `docker compose up -d` builds the image and
starts it on port 1525 (or `BENNERIA_PORT`), restarting it automatically, with a read-only
filesystem.

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

- `src/benneria/local.py`: search over `data/lexicon.sqlite`, and opening entries by id, BDB id or Strong's number
- `src/benneria/refs.py`: Bible references ("Lev 19:3", "I Samuel 3") to OSIS ids ("Lev.19.3")
- `src/benneria/hebrew.py`: Hebrew normalization (cantillation and vowel stripping), shared by the data build and search
- `src/benneria/app.py`: the Flask app: serves `static/`, `/api/lookup` and `/api/entry`
- `src/benneria/server.py`: the `benneria` command: runs the app on Flask's development server
- `gunicorn.conf.py`: production server settings (workers, connection queue, timeouts)
- `src/benneria/static/`: the frontend
  - `index.html`: page markup
  - `style.css`: styles, including dark mode
  - `labels.js`: display names for parses, parts of speech and languages
  - `app.js`: rendering, filters, search and the options dialog
- `src/benneria/data/lexicon.sqlite`: the lexicon database, generated by `scripts/build_data.py`
- `src/benneria/__init__.py`: exposes `main`, the `benneria` console script
- `scripts/build_data.py`: builds the database
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

The app's own code is released under the [MIT License](LICENSE). The lexicon database keeps its
own license, CC BY 4.0, described above and in [DATA_LICENSE.md](DATA_LICENSE.md).
