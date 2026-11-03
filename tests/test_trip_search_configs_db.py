"""Trip search configurations persisted in the SQLite DB.

The configurations moved out of browser localStorage into the database so every
browser/device sees the same set. These tests cover the three layers that make
that happen: the versioned migration that owns the table, the data-access module
``skybreak.trip_configs``, and the REST routes in ``skybreak.app``.
"""
import pathlib
import sqlite3

import pytest

import skybreak.db_migrate as m
from skybreak.app import app
from skybreak.trip_configs import delete_config, list_configs, sanitize_config, save_config

TABLE = "trip_search_configs"

SAMPLE = {
    "name": "Wochenende",
    "startWeekdays": [4],
    "endWeekdays": [6],
    "maxDepToDest": "18:00",
    "minRetDep": "10:00",
    "minTripDays": 2,
    "maxTripDays": 5,
}


@pytest.fixture(autouse=True)
def _empty_configs():
    with sqlite3.connect(m.db_path(), timeout=10.0) as conn:
        conn.execute(f"DELETE FROM {TABLE}")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _fresh_db(tmp_path):
    db = str(tmp_path / "configs.db")
    if pathlib.Path(db).exists():
        pathlib.Path(db).unlink()
    m.apply_migrations(db)
    return db


def _cols(db, table=TABLE):
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    conn.close()
    return cols


def _tables(db):
    conn = sqlite3.connect(db)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    return names


def _version(db):
    conn = sqlite3.connect(db)
    (v,) = conn.execute("SELECT version FROM db_version").fetchone()
    conn.close()
    return v


# --- schema / migration ----------------------------------------------------

def test_fresh_db_has_trip_search_configs_table(tmp_path):
    db = _fresh_db(tmp_path)
    assert TABLE in _tables(db)


def test_migration_creates_expected_columns(tmp_path):
    db = _fresh_db(tmp_path)
    expected = {
        "id", "name", "start_weekdays", "end_weekdays", "max_dep_to_dest",
        "min_ret_dep", "min_trip_days", "max_trip_days", "created_at", "updated_at",
    }
    assert expected <= _cols(db), f"missing: {expected - _cols(db)}"


def test_name_is_unique_case_insensitive(tmp_path):
    db = _fresh_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(f"INSERT INTO {TABLE} (name) VALUES (?)", ("Wochenende",))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"INSERT INTO {TABLE} (name) VALUES (?)", ("wochenende",))
        conn.commit()
    conn.close()


# --- data access module ----------------------------------------------------

def test_list_configs_empty():
    assert list_configs() == []


def test_save_and_list_roundtrip_maps_to_frontend_fields():
    saved = save_config(SAMPLE)
    rows = list_configs()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Wochenende"
    assert row["startWeekdays"] == [4]
    assert row["endWeekdays"] == [6]
    assert row["maxDepToDest"] == "18:00"
    assert row["minRetDep"] == "10:00"
    assert row["minTripDays"] == 2
    assert row["maxTripDays"] == 5
    assert saved["name"] == "Wochenende"


def test_save_upserts_case_insensitively():
    save_config(SAMPLE)
    save_config({**SAMPLE, "name": "WOCHENENDE", "maxDepToDest": "17:00"})
    rows = list_configs()
    assert len(rows) == 1
    assert rows[0]["name"] == "WOCHENENDE"
    assert rows[0]["maxDepToDest"] == "17:00"


def test_list_sorted_by_name():
    save_config({**SAMPLE, "name": "Zurich"})
    save_config({**SAMPLE, "name": "Alicante"})
    save_config({**SAMPLE, "name": "Mallorca"})
    assert [c["name"] for c in list_configs()] == ["Alicante", "Mallorca", "Zurich"]


def test_delete_config_reports_whether_it_removed():
    save_config(SAMPLE)
    assert delete_config("wochenende") is True
    assert list_configs() == []
    assert delete_config("wochenende") is False


def test_save_config_rejects_a_missing_name():
    # Contract: None (not an exception) for an unusable payload; the route maps
    # that to HTTP 400.
    assert save_config({**SAMPLE, "name": "   "}) is None
    assert save_config(None) is None
    assert list_configs() == []


def test_sanitize_config_normalizes_values():
    clean = sanitize_config({
        "name": "  Test  ",
        "startWeekdays": ["x", 9, 4, 4, 2],
        "endWeekdays": None,
        "maxDepToDest": " 18:00 ",
        "minRetDep": "half past ten",
        "minTripDays": "3",
        "maxTripDays": 0,
    })
    assert clean["name"] == "Test"
    assert clean["startWeekdays"] == [2, 4]
    assert clean["endWeekdays"] == []
    assert clean["maxDepToDest"] == "18:00"
    assert clean["minRetDep"] == ""
    assert clean["minTripDays"] == 3
    assert clean["maxTripDays"] is None


def test_sanitize_config_rejects_unusable_input():
    for bad in (None, "text", 42, [], {"name": ""}, {"name": "  "}):
        assert sanitize_config(bad) is None


# --- REST API --------------------------------------------------------------

def test_get_returns_empty_list(client):
    resp = client.get("/api/trip-configs")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_post_creates_and_get_returns_it(client):
    resp = client.post("/api/trip-configs", json=SAMPLE)
    assert resp.status_code in (200, 201)
    data = client.get("/api/trip-configs").get_json()
    assert len(data) == 1
    assert data[0]["name"] == "Wochenende"
    assert data[0]["maxTripDays"] == 5


def test_post_upserts_same_name_case_insensitively(client):
    client.post("/api/trip-configs", json=SAMPLE)
    client.post("/api/trip-configs", json={**SAMPLE, "name": "wochenende", "minTripDays": 4})
    data = client.get("/api/trip-configs").get_json()
    assert len(data) == 1
    assert data[0]["minTripDays"] == 4


def test_post_rejects_missing_name(client):
    resp = client.post("/api/trip-configs", json={k: v for k, v in SAMPLE.items() if k != "name"})
    assert resp.status_code == 400


def test_post_rejects_invalid_payload(client):
    resp = client.post("/api/trip-configs", json={"name": "   "})
    assert resp.status_code == 400
    resp = client.post("/api/trip-configs", json=None)
    assert resp.status_code == 400


def test_delete_removes_config(client):
    client.post("/api/trip-configs", json=SAMPLE)
    resp = client.delete("/api/trip-configs/WOCHENENDE")
    assert resp.status_code == 200
    assert client.get("/api/trip-configs").get_json() == []


def test_delete_unknown_name_is_404(client):
    resp = client.delete("/api/trip-configs/nope")
    assert resp.status_code == 404


def test_configs_are_shared_across_requests(client):
    """The point of the change: a second client (another browser) sees them too."""
    client.post("/api/trip-configs", json=SAMPLE)
    with app.test_client() as other:
        data = other.get("/api/trip-configs").get_json()
    assert len(data) == 1
    assert data[0]["name"] == "Wochenende"
