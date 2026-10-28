import importlib.util
import os
import sqlite3
from pathlib import Path

import pytest

from benneria.local import DB_PATH, LocalLexicon

ROOT = Path(__file__).resolve().parent.parent

# Sessions are signed with this rather than a key file made next to the real notebook database.
os.environ.setdefault("BENNERIA_SECRET_KEY", "tests")


@pytest.fixture(scope="session")
def build_data():
    """scripts/build_data.py as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("build_data", ROOT / "scripts" / "build_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def lexicon():
    return LocalLexicon()
