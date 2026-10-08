# Benneria

A small web dictionary for Hebrew and Aramaic words. It serves a single-page UI
and proxies lookups to the [Sefaria](https://www.sefaria.org) Lexicon API
(`GET https://www.sefaria.org/api/words/{word}`), showing entries from Jastrow,
BDB, Strong's, Klein and the other lexicons Sefaria hosts.

Uses only the Python standard library.

## Run

```sh
uv run benneria                                # http://localhost:8000
uv run benneria --port 9000 --host 0.0.0.0 --open
```

Without uv: `PYTHONPATH=src python -m benneria`.

Options:

| Flag     | Default     | Description                    |
| -------- | ----------- | ------------------------------ |
| `--host` | `127.0.0.1` | Interface to bind              |
| `--port` | `8000`      | Port to listen on              |
| `--open` | off         | Open the browser on start      |

Binding to `0.0.0.0` lets anyone on your network use the server as a proxy to Sefaria.

## Features

- Results grouped by lexicon, with a per-lexicon filter
- Nested senses, grammar, Strong's/TWOT/GK numbers, source references and
  previous/next headword navigation
- Links between dictionary entries open as in-app lookups
- Search options passed through to Sefaria: `lookup_ref`, `always_consonants`,
  `always_split`, `never_split`
- Recent-search history, back/forward navigation, on-screen Hebrew keyboard,
  dark mode

## Layout

- `src/benneria/lookup.py`: word lookup, a proxy to the Sefaria API with an in-memory cache
- `src/benneria/server.py`: HTTP server and command-line options; serves `static/` and `/api/lookup`
- `src/benneria/static/`: the frontend
  - `index.html`: page markup
  - `style.css`: styles, including dark mode
  - `labels.js`: display names for morphology and language codes
  - `app.js`: rendering, filters, search, history and the Hebrew keyboard
- `src/benneria/__init__.py`: exposes `main`, the `benneria` console script

Dictionary data comes from Sefaria; each lexicon keeps its own license and attribution.
