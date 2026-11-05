"""DB migration tests: the latest version must be reached and persisted, the stale
favorite columns dropped, unique index recreated, idempotency, and a clean
script run. v13 adds trip_search_configs; v14 adds trip_price_quotes for
on-demand price quotes in TripsTab.
"""
import os
import pathlib
import sqlite3
import subprocess
import sys

import skybreak.db_migrate as m


def _fresh_db(tmp_path):
    db = str(tmp_path / "mig.db")
    if pathlib.Path(db).exists():
        pathlib.Path(db).unlink()
    return db


def _cols(db, table="favorite_trips"):
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    conn.close()
    return cols


def _version(db):
    conn = sqlite3.connect(db)
    (v,) = conn.execute("SELECT version FROM db_version").fetchone()
    conn.close()
    return v


def test_fresh_db_reaches_latest(tmp_path):
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    assert _version(db) == 14


def test_v11_drops_stale_columns(tmp_path):
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    cols = _cols(db)
    for c in ("start_time", "return_time", "trip_date"):
        assert c not in cols, f"{c} should have been dropped by v11"


def test_v11_recreates_unique_index(tmp_path):
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    conn = sqlite3.connect(db)
    idx = {r[1] for r in conn.execute("PRAGMA index_list(favorite_trips)")}
    conn.close()
    assert "idx_favorite_unique" in idx


def test_fresh_db_has_full_flights_schema(tmp_path):
    # Schema is owned by db_migrate, not by runtime mutation in the scraper:
    # the scraper-era columns must already exist on a fresh DB.
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    cols = _cols(db, "flights")
    for c in ("from_icao", "to_icao", "flight_date", "arrival_date",
              "departure", "arrival", "month_key"):
        assert c in cols, f"{c} should be part of the migrated flights schema"
    conn = sqlite3.connect(db)
    idx = {r[1] for r in conn.execute("PRAGMA index_list(flights)")}
    conn.close()
    assert "idx_flights_airport_month" in idx


def test_partial_v11_db_upgraded_to_latest(tmp_path):
    # An existing DB that reached v11 (e.g. before the unification) must be
    # upgraded to v12 by adding the missing columns, without data loss.
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    # Simulate an older DB that stops at v11.
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM db_version")
    conn.execute("INSERT INTO db_version (version) VALUES (11)")
    conn.commit()
    conn.close()
    m.apply_migrations(db)
    assert _version(db) == 14
    cols = _cols(db, "flights")
    for c in ("flight_date", "arrival_date", "departure", "arrival", "month_key"):
        assert c in cols, f"{c} should be added by v12"


def test_v13_db_upgraded_to_v14(tmp_path):
    # An existing DB at v12 (the deployed schema before trip search configs)
    # must gain the trip_search_configs table without losing anything.
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt"))
    conn.execute("DELETE FROM db_version")
    conn.execute("INSERT INTO db_version (version) VALUES (12)")
    conn.commit()
    conn.close()
    m.apply_migrations(db)
    assert _version(db) == 14
    cols = _cols(db, "trip_search_configs")
    assert {"id", "name", "start_weekdays", "max_trip_days"} <= cols
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT name FROM airports WHERE code='FRA'").fetchone()[0] == "Frankfurt"
    conn.close()


def test_v14_creates_trip_price_quotes_table(tmp_path):
    # An existing DB at v13 must gain trip_price_quotes without data loss.
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt"))
    conn.execute("DELETE FROM db_version")
    conn.execute("INSERT INTO db_version (version) VALUES (13)")
    conn.commit()
    conn.close()
    m.apply_migrations(db)
    assert _version(db) == 14
    # Verify the new table exists with expected columns
    cols = _cols(db, "trip_price_quotes")
    for c in ("start_airport", "destination_airport", "outbound_date",
              "return_date", "outbound_flight_number", "return_flight_number",
              "price_outbound", "price_return", "price_total", "fetched_at"):
        assert c in cols, f"{c} should be in trip_price_quotes"
    # Existing data preserved
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT name FROM airports WHERE code='FRA'").fetchone()[0] == "Frankfurt"
    conn.close()


def test_migration_is_idempotent(tmp_path):
    db = _fresh_db(tmp_path)
    m.apply_migrations(db)
    m.apply_migrations(db)  # must not raise on a second run
    assert _version(db) == 14


def test_migrate_runs_as_script(tmp_path):
    db = _fresh_db(tmp_path)
    env = dict(os.environ)
    env["DB_FILE"] = db
    res = subprocess.run(
        [sys.executable, "-m", "skybreak.db_migrate"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path.cwd()),
    )
    assert res.returncode == 0, f"stderr: {res.stderr}"
    assert _version(db) == 14
