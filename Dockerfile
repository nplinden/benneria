# Benneria in a container, served by gunicorn (settings in gunicorn.conf.py).
#
#   docker build -t benneria .
#   docker run -p 1525:1525 benneria                 # http://localhost:1525
#   docker run -p 1525:1525 -e WEB_CONCURRENCY=8 benneria
#
# The lexicon database is part of the package, so the image needs no network or volume.

# ---------- build: install the app and its locked dependencies into /app/.venv ----------
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so this layer is reused when only the app's code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the app itself, installed as a regular (non-editable) package with its static files and
# database.
COPY README.md LICENSE DATA_LICENSE.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---------- run: the virtual environment and gunicorn's settings, nothing else ----------
FROM python:3.14-slim
# A home directory: gunicorn keeps its control socket there.
RUN useradd --system --create-home --uid 10001 benneria
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY gunicorn.conf.py LICENSE DATA_LICENSE.md ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    BENNERIA_BIND=0.0.0.0:1525 \
    WEB_CONCURRENCY=4
USER benneria
EXPOSE 1525

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1525/api/entry?strong=1', timeout=4)"

# gunicorn reads ./gunicorn.conf.py from the working directory.
CMD ["gunicorn", "benneria.app:app"]
