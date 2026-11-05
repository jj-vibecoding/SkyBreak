"""Portable test harness.

Tests must not touch a real ``/data`` volume. This module runs before any
``skybreak`` import (pytest imports ``conftest`` first), so it configures the
environment the way the container does, but on an isolated temp database and a
placeholder frontend build.
"""
import os
import pathlib
import sqlite3
import tempfile

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# --- environment defaults, set BEFORE any skybreak import ------------------
_TMP = pathlib.Path(tempfile.gettempdir()) / "skybreak-test"
_TMP.mkdir(parents=True, exist_ok=True)
_DB_FILE = _TMP / "skybreak.db"
# Always use a writable, isolated DB for tests.
os.environ["DB_FILE"] = str(_DB_FILE)

_BUILD_DIR = _REPO_ROOT / "frontend" / "build"
if not (_BUILD_DIR / "index.html").exists():
    # Placeholder so index-route tests don't 404 when npm hasn't been run.
    _placeholder = _TMP / "build"
    _placeholder.mkdir(parents=True, exist_ok=True)
    (_placeholder / "index.html").write_text(
        "<html><body>skybreak test placeholder</body></html>"
    )
    os.environ["FRONTEND_BUILD_DIR"] = str(_placeholder)
else:
    os.environ.setdefault("FRONTEND_BUILD_DIR", str(_BUILD_DIR))


def _reset_data_tables():
    conn = sqlite3.connect(str(_DB_FILE), timeout=30.0)
    for table in ("flights", "airports", "favorite_trips", "favorite_trip_prices",
                  "trip_search_configs", "trip_price_quotes",
                  "scrape_runs", "price_runs", "settings"):
        try:
            conn.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _migrated_db():
    """Ensure the schema exists for the whole session; clean data between tests."""
    from skybreak.db_migrate import apply_migrations

    apply_migrations()
    _reset_data_tables()
    yield
    # best-effort cleanup
    try:
        _DB_FILE.unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture()
def clean_db():
    """Give a test an empty data set (tables already exist via the session fixture)."""
    _reset_data_tables()
    yield
    _reset_data_tables()
