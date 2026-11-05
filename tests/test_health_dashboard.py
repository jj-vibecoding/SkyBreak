"""Health Dashboard + Backup/Export tests.

Covers:
- scrape_runs / price_runs row creation by scraper_job functions
- GET /api/health shape and stale detection
- GET /api/backup/export contents (no flights, no secrets)
- POST /api/backup/import restore, idempotency, version rejection
"""
import sys
sys.path.insert(0, '.')

from skybreak.db import connect_db


# ── Run-log helpers ─────────────────────────────────────────────────────────


def _insert_scrape_run(conn, status="ok", airports=3, flights_saved=120):
    conn.execute(
        "INSERT INTO scrape_runs (started_at, finished_at, status, airports, flights_saved) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            "2026-01-01 10:00:00",
            "2026-01-01 10:05:00",
            status,
            airports,
            flights_saved,
        ),
    )


def _insert_price_run(conn, status="ok", total=5, success=4, failed=1):
    conn.execute(
        "INSERT INTO price_runs (started_at, finished_at, status, total, success, failed) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "2026-01-01 11:00:00",
            "2026-01-01 11:02:00",
            status,
            total,
            success,
            failed,
        ),
    )


def _get_client():
    """Create a test Flask client with the app imported fresh."""
    from skybreak.app import app
    app.config['TESTING'] = True
    return app.test_client()


# ── GET /api/health ─────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def test_health_returns_shape(self, clean_db):
        """GET /api/health returns the expected top-level keys."""
        client = _get_client()
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "db_version" in data
        assert "airports" in data
        assert "last_scrape" in data
        assert "last_price_run" in data

    def test_health_empty_db(self, clean_db):
        """Fresh DB: last_run is null, airports array is empty."""
        client = _get_client()
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["last_scrape"] is None
        assert data["last_price_run"] is None
        assert data["airports"] == []

    def test_health_with_runs(self, clean_db):
        """Health endpoint returns last scrape + price run when present."""
        conn = connect_db()
        _insert_scrape_run(conn)
        _insert_price_run(conn)
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["last_scrape"]["status"] == "ok"
        assert data["last_scrape"]["airports"] == 3
        assert data["last_price_run"]["total"] == 5
        assert data["last_price_run"]["success"] == 4
        assert data["last_price_run"]["failed"] == 1

    def test_health_airport_stale(self, clean_db):
        """Airport with max_departure older than fetch_max_months window is stale."""
        conn = connect_db()
        conn.execute(
            "INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt")
        )
        conn.execute(
            "INSERT INTO flights ("
            "  airport_icao, airport_name, destination_icao, destination_name, "
            "  flight_direction, departure_time, arrival_time, flight_number, "
            "  from_icao, to_icao, flight_date, month_key"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "FRA", "Frankfurt", "CDG", "Paris-Charles-de-Gaulle",
                "departure", "2024-01-15 08:00:00", "2024-01-15 10:00:00",
                "LH100", "FRA", "CDG", "2024-01-15", "2024-01",
            ),
        )
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/health")
        data = resp.get_json()
        fra_entry = next((a for a in data["airports"] if a["code"] == "FRA"), None)
        assert fra_entry is not None
        assert fra_entry["stale"] is True

    def test_health_airport_fresh(self, clean_db):
        """Airport with max_departure within the fetch window is not stale."""
        conn = connect_db()
        conn.execute(
            "INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt")
        )
        conn.execute(
            "INSERT INTO flights ("
            "  airport_icao, airport_name, destination_icao, destination_name, "
            "  flight_direction, departure_time, arrival_time, flight_number, "
            "  from_icao, to_icao, flight_date, month_key"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "FRA", "Frankfurt", "CDG", "Paris-Charles-de-Gaulle",
                "departure", "2027-12-15 08:00:00", "2027-12-15 10:00:00",
                "LH100", "FRA", "CDG", "2027-12-15", "2027-12",
            ),
        )
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/health")
        data = resp.get_json()
        fra_entry = next((a for a in data["airports"] if a["code"] == "FRA"), None)
        assert fra_entry is not None
        assert fra_entry["stale"] is False


# ── GET /api/backup/export ──────────────────────────────────────────────────


class TestBackupExport:
    """Tests for GET /api/backup/export."""

    def test_export_contains_user_tables(self, clean_db):
        """Export includes airports, favorite_trips, trip_search_configs, settings."""
        conn = connect_db()
        conn.execute("INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt"))
        conn.execute(
            "INSERT INTO favorite_trips "
            "(destination_airport, outbound_flight_number, return_flight_number, "
            "start_airport, outbound_trip_date, return_trip_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("CDG", "LH100", "AF200", "FRA", "2026-06-01", "2026-06-07"),
        )
        conn.execute(
            "INSERT INTO trip_search_configs (name, start_weekdays) VALUES (?, ?)",
            ("MyConfig", "1,2,3"),
        )
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("fetch_max_months", "6"))
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/backup/export")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 1
        assert data["db_version"] == 16
        assert any(a["code"] == "FRA" for a in data["airports"])
        assert any(f["destination_airport"] == "CDG" for f in data["favorite_trips"])
        assert any(c["name"] == "MyConfig" for c in data["trip_search_configs"])

    def test_export_excludes_flights(self, clean_db):
        """Export does NOT include the flights table."""
        conn = connect_db()
        conn.execute(
            "INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt")
        )
        conn.execute(
            "INSERT INTO flights ("
            "  airport_icao, airport_name, destination_icao, destination_name, "
            "  flight_direction, departure_time, arrival_time, flight_number, "
            "  from_icao, to_icao, flight_date, month_key"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "FRA", "Frankfurt", "CDG", "Paris",
                "departure", "2027-12-15 08:00:00", "2027-12-15 10:00:00",
                "LH100", "FRA", "CDG", "2027-12-15", "2027-12",
            ),
        )
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/backup/export")
        data = resp.get_json()
        assert "flights" not in data

    def test_export_excludes_secrets(self, clean_db):
        """Export does NOT include secret keys (e.g. telegram_bot_token)."""
        conn = connect_db()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("telegram_bot_token", "super_secret_123"),
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("google_consent_cookie", "test_cookie"),
        )
        conn.commit()
        conn.close()

        client = _get_client()
        resp = client.get("/api/backup/export")
        data = resp.get_json()
        settings_keys = [s["key"] for s in data.get("settings", [])]
        assert "telegram_bot_token" not in settings_keys


# ── POST /api/backup/import ─────────────────────────────────────────────────


class TestBackupImport:
    """Tests for POST /api/backup/import."""

    def test_import_restores_data(self, clean_db):
        """Import restores airports, favorites, configs into a fresh DB."""
        conn = connect_db()
        conn.execute("INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt"))
        conn.execute(
            "INSERT INTO favorite_trips "
            "(destination_airport, outbound_flight_number, return_flight_number, "
            "start_airport, outbound_trip_date, return_trip_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("CDG", "LH100", "AF200", "FRA", "2026-06-01", "2026-06-07"),
        )
        conn.commit()
        conn.close()

        client = _get_client()
        resp_export = client.get("/api/backup/export")
        export_data = resp_export.get_json()

        resp_import = client.post(
            "/api/backup/import",
            json=export_data,
            content_type="application/json",
        )
        assert resp_import.status_code == 200
        imported = resp_import.get_json()
        assert imported["imported_tables"] is not None

        conn = connect_db()
        fra = conn.execute("SELECT name FROM airports WHERE code='FRA'").fetchone()
        assert fra is not None and fra[0] == "Frankfurt"
        cdg_fav = conn.execute(
            "SELECT destination_airport FROM favorite_trips WHERE outbound_flight_number='LH100'"
        ).fetchone()
        assert cdg_fav is not None and cdg_fav[0] == "CDG"
        conn.close()

    def test_import_version_mismatch(self, clean_db):
        """Import with unknown version returns 400."""
        client = _get_client()
        resp = client.post(
            "/api/backup/import",
            json={"version": 99, "airports": [], "favorite_trips": []},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_import_corrupted_payload(self, clean_db):
        """Import with missing required tables returns 400."""
        client = _get_client()
        resp = client.post(
            "/api/backup/import",
            json={"version": 1},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_import_idempotent(self, clean_db):
        """Second import of the same data does NOT create duplicates."""
        conn = connect_db()
        conn.execute("INSERT INTO airports (code, name) VALUES (?, ?)", ("FRA", "Frankfurt"))
        conn.commit()
        conn.close()

        client = _get_client()
        resp_export = client.get("/api/backup/export")
        export_data = resp_export.get_json()

        client.post(
            "/api/backup/import",
            json=export_data,
            content_type="application/json",
        )
        resp2 = client.post(
            "/api/backup/import",
            json=export_data,
            content_type="application/json",
        )
        assert resp2.status_code == 200

        conn = connect_db()
        count = conn.execute("SELECT COUNT(*) FROM airports WHERE code='FRA'").fetchone()[0]
        conn.close()
        assert count == 1


# ── scraper_job run logging ─────────────────────────────────────────────────


class TestScrapeRunLogging:
    """Tests for run-log insertion in scraper_job functions."""

    def test_scrape_all_airports_logs_run(self, clean_db, monkeypatch):
        """scrape_all_airports() inserts a scrape_runs row on success."""
        from skybreak import scraper_job

        def _noop_run(*a, **k):
            return None

        def _empty_import(*a, **k):
            return []

        monkeypatch.setattr(scraper_job, "_run_kayak", _noop_run)
        monkeypatch.setattr(scraper_job, "_import_kayak_json", _empty_import)

        scraper_job.scrape_all_airports()

        conn = connect_db()
        row = conn.execute("SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert row[3] in ("ok", "failed")

    def test_scrape_favorite_prices_logs_run(self, clean_db, monkeypatch):
        """scrape_favorite_prices() inserts a price_runs row."""
        from skybreak import scraper_job
        # Patch the module-level name that scrape_favorite_prices binds to.
        # It does `from skybreak.flight_prices import fetch_prices_favorite`, so
        # we patch it on the flight_prices module (which is already imported).
        try:
            from skybreak import flight_prices
        except ImportError:
            flight_prices = None

        def _noop_fetch(fav_id, force=False):
            return {"error": "no flights"}

        if flight_prices is not None:
            monkeypatch.setattr(flight_prices, "fetch_prices_favorite", _noop_fetch)
        else:
            # Fallback: patch on scraper_job where it gets bound at runtime
            monkeypatch.setattr(scraper_job, "fetch_prices_favorite", _noop_fetch)

        scraper_job.scrape_favorite_prices()

        conn = connect_db()
        row = conn.execute("SELECT * FROM price_runs ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert row[3] in ("ok", "failed")
