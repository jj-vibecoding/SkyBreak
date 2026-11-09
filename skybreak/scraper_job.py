import json, logging, subprocess, sys, os
from datetime import datetime, timedelta
from skybreak.airport import fetch_airport_name
from skybreak.db_migrate import apply_migrations
from skybreak.db import connect_db, get_setting
logger = logging.getLogger(__name__)

def _run_kayak(airport, month, delay=None):
    # Baumhöhe: DB-Delayed-Wert (ms) lesen, falls nicht gesetzt Fallback 0.5
    if delay is None:
        try:
            conn = connect_db()
            row = conn.execute("SELECT value FROM settings WHERE key = ?", ("scrape_delay_ms",)).fetchone()
            conn.close()
            delay = float(row[0]) / 1000.0 if row and row[0] else 0.5
        except Exception:
            delay = 0.5
    cmd = [sys.executable, "skybreak/kayak_direct.py", airport, "-m", month, "-d", "both", "--delay", str(delay)]
    env = os.environ.copy(); env["PYTHONPATH"] = "."
    try:
        res = subprocess.run(cmd, stdout=None, stderr=None, timeout=300, env=env)
        logger.info("kayak %s %s finished (returncode %s)", airport, month, res.returncode)
        return res
    except Exception as e:
        logger.warning("subprocess %s %s: %s", airport, month, e)
        return None

def _import_kayak_json(airport):
    path = f"{airport.upper()}_direct.json"
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("flights", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception as e:
        logger.warning("read json %s: %s", path, e)
        return []

def _clear_month(airport, month):
    conn = connect_db()
    conn.execute("DELETE FROM flights WHERE airport_icao = ? AND (month_key = ? OR flight_date LIKE ?)",
                 (airport.upper(), month, month + "-%"))
    conn.commit()
    conn.close()

def _save_kayak(airport, flights, month):
    conn = connect_db()
    airport_name = fetch_airport_name(airport.upper()) or airport.upper()
    for f in flights:
        try:
            date_str = f.get("date") or f.get("flight_date") or ""
            if not date_str: continue
            month_key = str(date_str)[:7] if len(str(date_str)) >= 7 else month
            flight_number = f.get("flight_number") or f.get("flightNumber") or ""
            from_icao = f.get("from") or f.get("from_icao") or airport.upper()
            to_icao = f.get("to") or f.get("to_icao") or ""
            departure_str = f.get("departure") or ""
            arrival_str = f.get("arrival") or ""
            arrival_date = f.get("arrival_date") or f.get("arrivalDate") or date_str
            duration = f.get("duration_min") or f.get("duration_minutes") or f.get("duration")
            try: duration_minutes = int(duration) if duration is not None else None
            except: duration_minutes = None
            direction = "departure" if str(from_icao).upper() == str(airport.upper()).upper() else "arrival"
            dest_icao = to_icao if direction == "departure" else from_icao
            if str(dest_icao or "").upper() == str(airport.upper()).upper(): continue
            from skybreak.airport_lookup import fetch_airport_name as lookup_name
            dest_name = lookup_name(dest_icao) or dest_icao
            conn.execute("INSERT INTO flights (airport_icao, airport_name, destination_icao, destination_name, flight_direction, flight_date, flight_number, from_icao, to_icao, departure, arrival, departure_time, arrival_time, arrival_date, duration_minutes, month_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (airport.upper(), airport_name, dest_icao, dest_name, direction, date_str, flight_number, from_icao, to_icao, departure_str, arrival_str,
                          (date_str + " " + departure_str) if date_str and departure_str else None,
                          (date_str + " " + arrival_str) if date_str and arrival_str else None,
                          arrival_date, duration_minutes, month_key))
        except Exception as e:
            logger.warning("save flight %s: %s", f, e)
    conn.commit()
    conn.close()

def scrape_single_airport(airport_code):
    """Scrape flight schedule for a single airport (no run-log row)."""
    apply_migrations()
    max_raw = get_setting("fetch_max_months") or get_setting("fetch_max_days") or "3"
    try:
        max_months = int(max_raw)
    except Exception:
        max_months = 3
    max_months = max(1, min(max_months, 12))
    now = datetime.now()
    months = sorted({(now + timedelta(days=30*i)).strftime("%Y-%m") for i in range(max_months)})

    airport = airport_code.upper()
    total_saved = 0
    try:
        for month in months:
            logger.info("Kayak fetch %s %s (single)", airport, month)
            _clear_month(airport, month)
            res = _run_kayak(airport, month)
            flights = _import_kayak_json(airport)
            _save_kayak(airport, flights, month)
            total_saved += len(flights)
            logger.info("Saved %d flights for %s %s", len(flights), airport, month)
    except Exception as e:
        logger.warning("scrape_single_airport %s error: %s", airport, e)
    return total_saved


def scrape_all_airports():
    """Scrape all airports and log the run in ``scrape_runs``."""
    # Schema is owned by the versioned migration; ensure it before scraping.
    apply_migrations()
    conn = connect_db()

    # ── start run-log row ────────────────────────────────────────────────
    try:
        run_id = conn.execute(
            "INSERT INTO scrape_runs (started_at, status) VALUES (?, 'running')",
            (datetime.now().isoformat(),),
        ).lastrowid
        conn.commit()
    except Exception:
        run_id = None  # tables may not exist yet

    rows = conn.execute("SELECT code FROM airports").fetchall()
    conn.close()
    max_raw = get_setting("fetch_max_months") or get_setting("fetch_max_days") or "3"
    try: max_months = int(max_raw)
    except: max_months = 3
    max_months = max(1, min(max_months, 12))
    now = datetime.now()
    months = sorted({(now + timedelta(days=30*i)).strftime("%Y-%m") for i in range(max_months)})

    total_airports = len(rows)
    total_flights_saved = 0
    status = "ok"
    try:
        for (code,) in rows:
            airport = code.upper()
            try:
                for month in months:
                    logger.info("Kayak fetch %s %s", airport, month)
                    _clear_month(airport, month)
                    res = _run_kayak(airport, month)
                    flights = _import_kayak_json(airport)
                    _save_kayak(airport, flights, month)
                    total_flights_saved += len(flights)
                    logger.info("Saved %d flights for %s %s", len(flights), airport, month)
            except Exception as e:
                logger.info("Kayak fetch failed %s: %s", airport, e)
    except Exception as e:
        status = "failed"
        logger.warning("scrape_all_airports error: %s", e)

    # ── finish run-log row ───────────────────────────────────────────────
    if run_id is not None:
        try:
            conn2 = connect_db()
            conn2.execute(
                "UPDATE scrape_runs SET finished_at = ?, status = ?, airports = ?, flights_saved = ? "
                "WHERE id = ?",
                (datetime.now().isoformat(), status, total_airports, total_flights_saved, run_id),
            )
            conn2.commit()
            conn2.close()
        except Exception:
            pass  # logging must not break the scrape

def start_price_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    try: 
        interval = int(get_setting("price_fetch_interval_hours") or "6")
    except Exception as e:
        logger.error("Fehler beim Lesen des Preis-Intervalls: %s", e)
        interval = 6
    if interval <= 0: 
        logger.info("Preis-Scheduler deaktiviert (intervall <= 0)")
        return
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(scrape_favorite_prices, "interval", hours=interval, id="price_scheduler", coalesce=True, max_instances=1)
        scheduler.start()
        logger.info("Preis-Scheduler gestartet: %d Stunden", interval)
    except Exception as e:
        logger.error("Preis-Scheduler konnte nicht gestartet werden: %s", e)


def start_refresh_scheduler():
    """Start a background scheduler that refreshes all flight schedules.

    Reads ``refresh_interval_days`` from settings (default 7).
    Interval <= 0 disables the scheduler and returns None.
    Returns the BackgroundScheduler instance when started, or None when disabled.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    try:
        interval = int(get_setting("refresh_interval_days") or "7")
    except Exception as e:
        logger.error("Fehler beim Lesen des Refresh-Intervalls: %s", e)
        interval = 7
    if interval <= 0:
        logger.info("Refresh-Scheduler deaktiviert (intervall <= 0)")
        return None
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            scrape_all_airports,
            "interval",
            days=interval,
            id="refresh_scheduler",
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info("Refresh-Scheduler gestartet: alle %d Tage", interval)
        return scheduler
    except Exception as e:
        logger.error("Refresh-Scheduler konnte nicht gestartet werden: %s", e)
        return None


def scrape_favorite_prices():
    """Preise aller favorisierten Trips abfragen und in ``price_runs`` loggen."""
    logger.info("Starting automatic price update for all favorites")

    # ── start run-log row ────────────────────────────────────────────────
    try:
        conn_start = connect_db()
        run_id = conn_start.execute(
            "INSERT INTO price_runs (started_at, status) VALUES (?, 'running')",
            (datetime.now().isoformat(),),
        ).lastrowid
        conn_start.commit()
        conn_start.close()
    except Exception:
        run_id = None

    try:
        conn = connect_db()
        rows = conn.execute("SELECT id FROM favorite_trips").fetchall()
        conn.close()
        logger.info("Found %d favorite trips to update", len(rows))
        if not rows:
            logger.info("No favorite trips found, skipping price update")

        from skybreak.flight_prices import fetch_prices_favorite
        success_count = 0
        fail_count = 0
        for (fav_id,) in rows:
            try:
                result = fetch_prices_favorite(fav_id, force=True)
                if "error" in result:
                    logger.warning("Preis-Update Favorit %s fehlgeschlagen: %s", fav_id, result.get("error"))
                    fail_count += 1
                else:
                    logger.debug("Preis-Update Favorit %s erfolgreich: %s", fav_id, result.get("price_total"))
                    success_count += 1
                    # Evaluate alert after successful fetch (must not break the loop)
                    try:
                        from skybreak.notifications import evaluate_alert
                        evaluate_alert(fav_id)
                    except Exception:
                        pass  # alert failure must never break price loop
            except Exception as e:
                logger.warning("Preis-Update Favorit %s fehlgeschlagen: %s", fav_id, e)
                fail_count += 1
        logger.info("Preis-Update abgeschlossen: %d erfolgreich, %d fehlgeschlagen", success_count, fail_count)
        status = "ok" if fail_count == 0 else "failed"
    except Exception as e:
        logger.warning("Preis-Scheduler Fehler: %s", e)
        status = "failed"

    # ── finish run-log row ───────────────────────────────────────────────
    if run_id is not None:
        try:
            conn2 = connect_db()
            conn2.execute(
                "UPDATE price_runs SET finished_at = ?, status = ?, total = ?, success = ?, failed = ? "
                "WHERE id = ?",
                (
                    datetime.now().isoformat(),
                    status,
                    success_count + fail_count,
                    success_count,
                    fail_count,
                    run_id,
                ),
            )
            conn2.commit()
            conn2.close()
        except Exception:
            pass  # logging must not break the price update

def save_flights(airport, flights, month=None):
    # Handle nested API-style flight objects (departure/arrival with scheduledTime/airport)
    parsed = []
    for f in flights if isinstance(flights, list) else [flights]:
        if isinstance(f, dict) and ("departure" in f or "arrival" in f):
            dep = f.get("departure") or {}
            arr = f.get("arrival") or {}
            dep_airport = dep.get("airport") or {}
            arr_airport = arr.get("airport") or {}
            dep_time_raw = dep.get("scheduledTime")
            arr_time_raw = arr.get("scheduledTime")
            if isinstance(dep_time_raw, dict):
                dep_time_raw = dep_time_raw.get("utc", "")
            if isinstance(arr_time_raw, dict):
                arr_time_raw = arr_time_raw.get("utc", "")
            dep_time = str(dep_time_raw) if dep_time_raw else ""
            arr_time = str(arr_time_raw) if arr_time_raw else ""
            parsed.append({
                "from": dep_airport.get("icao") or airport.upper(),
                "to": arr_airport.get("icao") or "",
                "date": dep_time[:10] if dep_time else (arr_time[:10] if arr_time else ""),
                "departure": dep_time[11:16] if len(dep_time) >= 16 else (dep_time if dep_time else ""),
                "arrival": arr_time[11:16] if len(arr_time) >= 16 else (arr_time if arr_time else ""),
                "flight_number": f.get("number") or f.get("flightNumber") or "",
                "duration_minutes": None,
            })
        else:
            parsed.append(f)
    return _save_kayak(airport, parsed, month or "")

def clean_old_flights():
    conn = connect_db(timeout=5)
    conn.execute("DELETE FROM flights WHERE flight_date < date('now') OR (flight_date IS NULL AND departure < datetime('now'))")
    conn.commit(); conn.close()
