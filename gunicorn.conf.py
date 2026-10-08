"""
gunicorn settings for running Benneria in production:

    uv run gunicorn benneria.app:app

Settings can be overridden on the command line (e.g. --bind 0.0.0.0:8000) or, for the worker
count, with the WEB_CONCURRENCY environment variable.
"""

import os

bind = os.environ.get("BENNERIA_BIND", "127.0.0.1:8000")

# Separate processes, so lookups use several cores instead of being limited by Python's GIL.
# Each worker opens its own read-only connection to the database, which the OS caches once for all.
workers = int(os.environ.get("WEB_CONCURRENCY", 4))
worker_class = "sync"  # lookups are short, blocking SQLite work

# Pending connections the OS queues while all workers are busy (the built-in server allowed 5).
backlog = 2048
# Restart a worker stuck on one request for longer than this many seconds.
timeout = 30
# Let a browser reuse its connection for a few seconds instead of opening one per request.
keepalive = 5

accesslog = "-"  # request log to stdout
