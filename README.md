# Sefaria Dictionary

A small web dictionary for Hebrew and Aramaic words. It serves a single-page UI
and proxies lookups to the [Sefaria](https://www.sefaria.org) Lexicon API
(`GET https://www.sefaria.org/api/words/{word}`), showing entries from Jastrow,
BDB, Strong's, Klein and the other lexicons Sefaria hosts.

Uses only the Python standard library.

## Run

```sh
uv run sefaria                                # http://localhost:8000
uv run sefaria --port 9000 --host 0.0.0.0 --open
```

Without uv: `PYTHONPATH=src python -m sefaria`.

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

- `src/sefaria/app.py`: HTTP server, Sefaria proxy with an in-memory cache, and the embedded HTML/JS page
- `src/sefaria/__init__.py`: exposes `main`, the `sefaria` console script

Dictionary data comes from Sefaria; each lexicon keeps its own license and attribution.
