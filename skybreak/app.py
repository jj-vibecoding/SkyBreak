import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from datetime import datetime, timedelta, timezone
import os
import threading
from zoneinfo import ZoneInfo

# Standard + third-party
import airportsdata
_AIRPORTS = airportsdata.load('IATA')
from flask import Flask, request, jsonify, send_from_directory

# Project modules
from skybreak.airport import add_airport, delete_airport, validate_iata
from skybreak.airport_lookup import fetch_airport_name, fetch_city_country
from skybreak.db import connect_db, get_setting, set_setting
from skybreak.db_migrate import apply_migrations
from skybreak import trip_configs

# Configurable paths for testing vs production
FRONTEND_BUILD_DIR = os.environ.get("FRONTEND_BUILD_DIR", "/app/frontend/build")

# Cache state (lazily warmed by _preload_airport_cache after migrations)
_airport_lookup_cache: dict[str, str] = {}
_city_lookup_cache: dict[str, str] = {}


def _preload_airport_cache() -> None:
    """Warm the airport-name cache from the DB. Safe to call even if empty."""
    try:
        conn = connect_db(timeout=5.0)
        for row in conn.execute("SELECT code, name FROM airports").fetchall():
            _airport_lookup_cache[row[0]] = row[1] or row[0]
        conn.close()
    except Exception:
        pass


_preload_airport_cache()

app = Flask(__name__, static_folder=os.path.join(FRONTEND_BUILD_DIR, "static"), static_url_path="/static")


# Cached wrappers (Option 1 + 3)
def _cached_fetch_airport_name(code):
    if code not in _airport_lookup_cache:
        _airport_lookup_cache[code] = fetch_airport_name(code)
    return _airport_lookup_cache[code]

def _cached_fetch_city_country(code):
    if code not in _city_lookup_cache:
        # Derive from the name cache (populated from DB + external fallback)
        full = _cached_fetch_airport_name(code)
        start = full.rfind('(')
        end = full.rfind(')')
        if start != -1 and end != -1 and end > start:
            _city_lookup_cache[code] = full[start+1:end]
        else:
            _city_lookup_cache[code] = code or ""
    return _city_lookup_cache[code]

def _tz_for(code, airports):
    """Timezone for an airport code, or None if unknown."""
    a = airports.get(code)
    return ZoneInfo(a["tz"]) if a and a.get("tz") else None

_scrape_lock = threading.Lock()
_scrape_in_progress = False
_price_lock = threading.Lock()
_price_in_progress = False

# Ensure schema exists before serving requests. The earlier _preload_airport_cache
# call is harmless on a fresh DB (it catches the "no table yet" case and the
# lookup caches fill lazily afterward).
apply_migrations()

@app.route("/api/airports", methods=["GET"])
def list_airports():
    conn = connect_db()
    rows = conn.execute("SELECT code, name FROM airports").fetchall()
    conn.close()
    return jsonify([{"code": r[0], "name": r[1] or ""} for r in rows])
@app.route("/api/airports", methods=["POST"])
def create_airport():
    data = request.get_json(force=True)
    code = data.get("code", "").strip().upper()
    if not validate_iata(code):
        return jsonify({"error": "Invalid IATA"}), 400
    add_airport(code)
    return jsonify({"added": code})

@app.route("/api/airports/<code>", methods=["DELETE"])
def remove_airport(code):
    code = code.strip().upper()
    if not validate_iata(code):
        return jsonify({"error": "Invalid IATA"}), 400
    delete_airport(code)
    return jsonify({"deleted": code})

@app.route("/")
@app.route("/<path:path>")
def index(path=""):
    return send_from_directory(FRONTEND_BUILD_DIR, "index.html")

@app.route("/api/flights", methods=["GET"])
def list_flights():
    airport = request.args.get("airport", "").strip().upper()
    conn = connect_db()
    sql = "SELECT airport_icao, airport_name, destination_icao, destination_name, flight_direction, departure_time, arrival_time, duration_minutes, flight_number FROM flights WHERE departure_time >= datetime('now','utc') AND departure_time <= datetime('now', '+365 days')"
    params = []
    if airport:
        sql += " AND airport_icao = ?"
        params.append(airport)
    if request.args.get('date'):
        date_filter = request.args.get('date').strip()
        sql += " AND date(departure_time) = ?"
        params.append(date_filter)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        airport_icao = r[0]
        destination_icao = r[2]
        airport_name = _cached_fetch_airport_name(airport_icao) or r[1] or ""
        destination_name = _cached_fetch_airport_name(destination_icao) or r[3] or ""
        result.append({
            "airport_icao": airport_icao,
            "airport_name": airport_name,
            "destination_icao": destination_icao,
            "destination_name": destination_name,
            "direction": r[4],
            "from_icao": destination_icao if r[4] == 'arrival' else airport_icao,
            "from_airport_name": (_cached_fetch_airport_name(destination_icao) or r[3] or "") if r[4] == 'arrival' else airport_name,
            "to_icao": airport_icao if r[4] == 'arrival' else destination_icao,
            "to_airport_name": airport_name if r[4] == 'arrival' else destination_name,
            "departure_time": r[5] + ("Z" if r[5] and not r[5].endswith("Z") and "+" not in r[5][-6:] else ""),
            "arrival_time": (r[6] + "Z" if r[6] and not r[6].endswith("Z") and "+" not in r[6][-6:] else r[6]) if len(r) > 6 and r[6] else None,
            "duration_minutes": r[7] if len(r) > 7 and r[7] is not None else None,
            "flight_number": r[8] or r[6] or "" if len(r) > 8 else (r[6] or "")
        })
    return jsonify(result)



@app.route("/api/flights/future", methods=["GET"])
def future_flights_info():
    conn = connect_db()
    # For each airport shown in flights page, compute max departure_time from DB
    rows = conn.execute("SELECT airport_icao, MAX(departure_time) FROM flights WHERE departure_time >= datetime('now','utc') GROUP BY airport_icao").fetchall()
    conn.close()
    result = {}
    max_day = None
    for airport_icao, max_time_str in rows:
        if max_time_str:
            try:
                max_time = datetime.fromisoformat(max_time_str.replace('Z', '+00:00'))
                if max_time.tzinfo is None:
                    max_time = max_time.replace(tzinfo=timezone.utc)
                result[airport_icao] = {
                    "max_departure_time": max_time_str,
                    "max_departure_day": max_time.strftime('%Y-%m-%d')
                }
                if max_day is None or max_time > max_day:
                    max_day = max_time
            except Exception:
                result[airport_icao] = {"max_departure_time": max_time_str, "max_departure_day": None}
        else:
            result[airport_icao] = {"max_departure_time": None, "max_departure_day": None}
    result['_max_loaded_day'] = max_day.strftime('%Y-%m-%d') if max_day else None
    return jsonify(result)

@app.route("/api/prices/history", methods=["GET"])
def price_history():
    favorite_id = request.args.get("trip_id") or request.args.get("favorite_id")
    if not favorite_id:
        return jsonify({"error": "missing trip_id"}), 400
    try:
        favorite_id = int(favorite_id)
    except Exception:
        return jsonify({"error": "invalid trip_id"}), 400
    conn = connect_db()
    rows = conn.execute(
    "SELECT date(fetched_at) AS date, price_outbound, price_return, price_total FROM favorite_trip_prices WHERE favorite_id = ? ORDER BY fetched_at ASC",
    (favorite_id,)
    ).fetchall()
    conn.close()
    return jsonify([
    {"date": r[0], "outbound_price": r[1], "return_price": r[2], "total_price": r[3]}
    for r in rows
    ])


@app.route("/api/prices/quote", methods=["POST"])
def quote_trip_endpoint():
    """On-demand price quote for a candidate turnaround trip.

    Body: {start_airport, destination_airport, outbound_date, return_date,
           outbound_flight_number, return_flight_number}
    """
    data = request.get_json(force=True)
    start = (data.get("start_airport") or "").strip().upper()
    dest = (data.get("destination_airport") or "").strip().upper()
    out_date = (data.get("outbound_date") or "").strip()
    ret_date = (data.get("return_date") or "").strip()
    out_fnum = (data.get("outbound_flight_number") or "").strip()
    ret_fnum = (data.get("return_flight_number") or "").strip()

    # Validate IATA codes
    for code, label in [(start, "start_airport"), (dest, "destination_airport")]:
        if not validate_iata(code):
            return jsonify({"error": f"Invalid {label}: {code!r}"}), 400

    # Validate dates (YYYY-MM-DD)
    for date_str, label in [(out_date, "outbound_date"), (ret_date, "return_date")]:
        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return jsonify({"error": f"Invalid {label}: {date_str!r} (expected YYYY-MM-DD)"}), 400

    try:
        from skybreak.trip_quotes import quote_trip as _quote_trip
        result = _quote_trip(start, dest, out_date, ret_date, out_fnum, ret_fnum)
        return jsonify(result), 200
    except RuntimeError as e:
        # Scraper HTTP error / consent page → 502
        logger.error("Quote scraper error: %s", e)
        return jsonify({"error": str(e)}), 502


@app.route("/api/flights/fetch-now", methods=["POST"])
def fetch_now():
    global _scrape_in_progress
    with _scrape_lock:
        if _scrape_in_progress:
            return jsonify({"fetched": False, "message": "Fetch already in progress"}), 409
        _scrape_in_progress = True
    from skybreak.scraper_job import scrape_all_airports
    def _run():
        global _scrape_in_progress
        try:
            scrape_all_airports()
        finally:
            with _scrape_lock:
                _scrape_in_progress = False
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"fetched": True})

@app.route("/api/flights/scrape-status", methods=["GET"])
def scrape_status():
    global _scrape_in_progress
    with _scrape_lock:
        running = _scrape_in_progress
    return jsonify({"running": running})

@app.route("/api/settings/check", methods=["GET"])
def settings_check():
    max_m = get_setting("fetch_max_months") or get_setting("fetch_max_days") or ""
    return jsonify({"fetch_max_months_set": bool(max_m and max_m.strip()), "value": max_m or None})

@app.route("/api/settings/delay-ms", methods=["GET", "POST"])
def settings_delay_ms():
    if request.method == "POST":
        data = request.get_json(force=True)
        val = data.get("delay_ms")
        if val is not None:
            val_int = int(val)
            set_setting("scrape_delay_ms", str(val_int))
            return jsonify({"updated": True, "value": val_int})
        return jsonify({"updated": False, "error": "missing delay_ms"}), 400
    else:
        val_str = get_setting("scrape_delay_ms") or "500"
        return jsonify({"delay_ms": int(val_str)})

@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        data = request.get_json(force=True)
        for k, v in data.items():
            if k == "scrape_delay_ms":
                set_setting("scrape_delay_ms", str(int(v) if v is not None else 500))
            else:
                set_setting(str(k), str(v))
        return jsonify({"updated": True})
    else:
        conn = connect_db()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        return jsonify({r[0]: r[1] for r in rows})


@app.route("/api/trip-configs", methods=["GET"])
def list_trip_configs():
    return jsonify(trip_configs.list_configs())


@app.route("/api/trip-configs", methods=["POST"])
def save_trip_config():
    data = request.get_json(silent=True)
    saved = trip_configs.save_config(data)
    if saved is None:
        return jsonify({"error": "A configuration needs a name."}), 400
    return jsonify(saved), 200


@app.route("/api/trip-configs/<name>", methods=["DELETE"])
def delete_trip_config(name):
    if not trip_configs.delete_config(name):
        return jsonify({"error": "Configuration not found.", "name": name}), 404
    return jsonify({"deleted": True, "name": name})


@app.route("/api/favorites", methods=["POST"])
def create_favorite():
    data = request.get_json() or {}
    conn = connect_db()
    conn.execute("INSERT OR IGNORE INTO favorite_trips (destination_airport, outbound_flight_number, return_flight_number, start_airport, outbound_trip_date, return_trip_date) VALUES (?, ?, ?, ?, ?, ?)", (
        data.get("destination_airport") or "",
        data.get("outbound_flight_number") or "",
        data.get("return_flight_number") or "",
        data.get("start_airport") or "",
        data.get("trip_date") or data.get("outbound_trip_date") or "",
        data.get("return_trip_date") or ""
    ))
    conn.commit()
    conn.close()
    return jsonify({"created": True}), 201


# Batch helper (weiter optimieren)
@app.route("/api/favorites", methods=["GET"])
def list_favorites():
    conn = connect_db()
    # Pre-load all destination targets in one query (before iterating favorites)
    dest_targets = {}
    for r in conn.execute("SELECT destination_airport, target_price FROM destination_targets").fetchall():
        dest_targets[r[0]] = r[1]

    rows = conn.execute(
        "SELECT id, destination_airport, outbound_flight_number, return_flight_number, "
        "start_airport, created_at, outbound_trip_date, return_trip_date, target_price "
        "FROM favorite_trips ORDER BY created_at DESC"
    ).fetchall()

    # --- Batch fetch latest prices for ALL favorites in one query ----------
    fav_ids = [r[0] for r in rows]
    price_map: dict[int, dict] = {}
    if fav_ids:
        placeholders = ",".join("?" for _ in fav_ids)
        for row in conn.execute(
            f"SELECT p.favorite_id, p.price_outbound, p.price_return, p.price_total, p.currency, p.fetched_at "
            f"FROM favorite_trip_prices p "
            f"WHERE p.favorite_id IN ({placeholders}) "
            f"AND p.fetched_at = (SELECT MAX(fetched_at) FROM favorite_trip_prices WHERE favorite_id = p.favorite_id)",
            fav_ids,
        ).fetchall():
            price_map[row[0]] = {
                "price_outbound": row[1], "price_return": row[2],
                "price_total": row[3], "currency": row[4], "fetched_at": row[5],
            }

    # --- Batch fetch flight details for ALL outbound/return flights ---------
    out_keys: list[tuple[str, str]] = []   # (flight_number, date)
    ret_keys: list[tuple[str, str]] = []
    for r in rows:
        if r[6] and r[4] and r[1] and r[2]:  # out_trip_date, start_airport, dest_airport, out_fnum
            out_keys.append((r[2], r[6]))
        if r[7] and r[4] and r[1] and r[3]:  # ret_trip_date, start_airport, dest_airport, ret_fnum
            ret_keys.append((r[3], r[7]))

    def _batch_fetch(keys: list[tuple[str, str]], existing_map: dict) -> dict:
        """Fetch flight details in chunks to avoid SQLite expression-tree limit."""
        chunk_size = 100
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i:i + chunk_size]
            where_clause = " OR ".join(
                f"(flight_number = ? AND date(departure_time) = ?)" for _ in chunk
            )
            params = [item for pair in chunk for item in pair]
            for row in conn.execute(
                f"SELECT flight_number, date(departure_time), airport_icao, destination_icao, flight_number, departure_time, arrival_time "
                f"FROM flights WHERE {where_clause}",
                params,
            ).fetchall():
                key = (row[0], row[1])  # (flight_number, date)
                if key not in existing_map:
                    existing_map[key] = (row[2], row[3], row[4], row[5], row[6])
        return existing_map

    flight_map: dict[tuple[str, str], tuple] = {}
    if out_keys:
        flight_map = _batch_fetch(out_keys, flight_map)

    ret_flight_map: dict[tuple[str, str], tuple] = {}
    if ret_keys:
        ret_flight_map = _batch_fetch(ret_keys, ret_flight_map)

    result = []
    for r in rows:
        prices = price_map.get(r[0]) or {}
        dest_airport = r[1] or ''
        out_fnum = r[2] or ''
        ret_fnum = r[3] or ''
        start_airport = r[4] or ''
        created_at = r[5]
        out_trip_date = r[6] or ''
        ret_trip_date = r[7] or ''
        trip_target = r[8]  # may be None

        # Look up pre-fetched flight details
        out_dep = out_arr = out_flight = None
        if out_trip_date and start_airport and dest_airport and out_fnum:
            fr = flight_map.get((out_fnum, out_trip_date))
            if fr:
                out_dep = fr[3]; out_arr = fr[4]; out_flight = fr[2]

        ret_dep = ret_arr = ret_flight = None
        if ret_trip_date and start_airport and dest_airport and ret_fnum:
            fr = ret_flight_map.get((ret_fnum, ret_trip_date))
            if fr:
                ret_dep = fr[3]; ret_arr = fr[4]; ret_flight = fr[2]

        start_city_country = _cached_fetch_city_country(start_airport)
        dest_city_country = _cached_fetch_city_country(dest_airport)
        # Dauer berechnen (Hinflug) mit Zeitzonen
        duration_out = None
        if out_dep and out_arr:
            try:
                dep_str = str(out_dep)
                arr_str = str(out_arr)
                # Datum und Zeit extrahieren
                dep_date = dep_str[:10] if len(dep_str) >= 10 else dep_str.split()[0] if " " in dep_str else None
                arr_date = arr_str[:10] if len(arr_str) >= 10 else arr_str.split()[0] if " " in arr_str else None
                dep_t_str = dep_str[11:16] if len(dep_str) >= 16 else dep_str.split()[1] if " " in dep_str else "00:00"
                arr_t_str = arr_str[11:16] if len(arr_str) >= 16 else arr_str.split()[1] if " " in arr_str else "00:00"
                dep_t = datetime.strptime(dep_t_str, "%H:%M").time()
                arr_t = datetime.strptime(arr_t_str, "%H:%M").time()
                # Zeitzonen
                tz_start = _tz_for(start_airport, _AIRPORTS) if start_airport else None
                tz_dest = _tz_for(dest_airport, _AIRPORTS) if dest_airport else None
                if dep_date and arr_date and (tz_start or tz_dest):
                    dep_date_obj = datetime.strptime(dep_date, "%Y-%m-%d").date()
                    arr_date_obj = datetime.strptime(arr_date, "%Y-%m-%d").date()
                    dep = datetime.combine(dep_date_obj, dep_t, tz_start) if tz_start else datetime.combine(dep_date_obj, dep_t)
                    arr = datetime.combine(arr_date_obj, arr_t, tz_dest) if tz_dest else datetime.combine(arr_date_obj, arr_t)
                    if dep.tzinfo and arr.tzinfo:
                        duration_out = int(round((arr - dep).total_seconds() / 60))
                    else:
                        duration_out = int(round((arr - dep).total_seconds() / 60))
                else:
                    # Fallback: direkte Differenz wie bisher
                    d1 = datetime.fromisoformat(str(dep_str).replace("Z","+00:00"))
                    d2 = datetime.fromisoformat(str(arr_str).replace("Z","+00:00"))
                    duration_out = int(round((d2 - d1).total_seconds() / 60))
            except Exception:
                pass
        duration_ret = None
        if ret_dep and ret_arr:
            try:
                # Rückflug: Start = dest_airport, Ziel = start_airport
                dep_str = str(ret_dep)
                arr_str = str(ret_arr)
                dep_date = dep_str[:10] if len(dep_str) >= 10 else dep_str.split()[0] if " " in dep_str else None
                arr_date = arr_str[:10] if len(arr_str) >= 10 else arr_str.split()[0] if " " in arr_str else None
                dep_t_str = dep_str[11:16] if len(dep_str) >= 16 else dep_str.split()[1] if " " in dep_str else "00:00"
                arr_t_str = arr_str[11:16] if len(arr_str) >= 16 else arr_str.split()[1] if " " in arr_str else "00:00"
                dep_t = datetime.strptime(dep_t_str, "%H:%M").time()
                arr_t = datetime.strptime(arr_t_str, "%H:%M").time()
                tz_start = _tz_for(dest_airport, _AIRPORTS) if dest_airport else None
                tz_dest = _tz_for(start_airport, _AIRPORTS) if start_airport else None
                if dep_date and arr_date and (tz_start or tz_dest):
                    dep_date_obj = datetime.strptime(dep_date, "%Y-%m-%d").date()
                    arr_date_obj = datetime.strptime(arr_date, "%Y-%m-%d").date()
                    dep = datetime.combine(dep_date_obj, dep_t, tz_start) if tz_start else datetime.combine(dep_date_obj, dep_t)
                    arr = datetime.combine(arr_date_obj, arr_t, tz_dest) if tz_dest else datetime.combine(arr_date_obj, arr_t)
                    duration_ret = int(round((arr - dep).total_seconds() / 60))
                else:
                    d1 = datetime.fromisoformat(str(dep_str).replace("Z","+00:00"))
                    d2 = datetime.fromisoformat(str(arr_str).replace("Z","+00:00"))
                    duration_ret = int(round((d2 - d1).total_seconds() / 60))
            except Exception:
                pass
        start_name = _cached_fetch_airport_name(start_airport) or start_airport or ""
        dest_name = _cached_fetch_airport_name(dest_airport) or dest_airport or ""
        # Destination-level target for this trip's destination airport
        dest_target = dest_targets.get(dest_airport)
        result.append({"id": r[0], "destination_airport": r[1], "outbound_flight_number": r[2],
                       "return_flight_number": r[3], "start_airport": r[4], "created_at": r[5],
                                                "outbound_trip_date": r[6], "return_trip_date": r[7],
                       "target_price": trip_target,
                       "destination_target_price": dest_target,
                       "price_outbound": prices.get("price_outbound"), "price_return": prices.get("price_return"),
                       "price_total": prices.get("price_total"), "currency": prices.get("currency"), "fetched_at": prices.get("fetched_at"),
                       "outbound_departure": out_dep, "outbound_arrival": out_arr, "outbound_flight": out_flight,
                       "return_departure": ret_dep, "return_arrival": ret_arr, "return_flight": ret_flight,
                       "start_airport_name": start_name, "destination_airport_name": dest_name,
                       "start_city_country": start_city_country, "dest_city_country": dest_city_country,
                       "duration_outbound_minutes": duration_out, "duration_return_minutes": duration_ret})
    return jsonify(result)

@app.route("/api/favorites/<int:fav_id>", methods=["PUT"])
def update_favorite_target(fav_id):
    """Set or clear the trip-level target price."""
    data = request.get_json() or {}
    tp = data.get("target_price")
    if tp is not None:
        try:
            tp = float(tp)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid target_price"}), 400
        if tp < 0:
            return jsonify({"error": "target_price must be non-negative"}), 400
    conn = connect_db()
    try:
        exists = conn.execute(
            "SELECT id FROM favorite_trips WHERE id = ?", (fav_id,)
        ).fetchone()
        if not exists:
            conn.close()
            return jsonify({"error": "Favorite not found"}), 404
        conn.execute(
            "UPDATE favorite_trips SET target_price = ? WHERE id = ?",
            (tp, fav_id),
        )
        conn.commit()
        # Read back the updated row
        row = conn.execute(
            "SELECT id, destination_airport, outbound_flight_number, return_flight_number, "
            "start_airport, created_at, outbound_trip_date, return_trip_date, target_price "
            "FROM favorite_trips WHERE id = ?",
            (fav_id,),
        ).fetchone()
    finally:
        conn.close()
    return jsonify({
        "id": row[0],
        "target_price": row[8],
        "destination_airport": row[1],
    })


@app.route("/api/favorites/<int:fav_id>", methods=["DELETE"])
def delete_favorite(fav_id):
    conn = connect_db()
    conn.execute("DELETE FROM favorite_trips WHERE id = ?", (fav_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": fav_id})


@app.route("/api/favorites/<int:fav_id>/prices", methods=["POST"])
def favorite_prices(fav_id):
    from skybreak.flight_prices import fetch_prices_favorite
    result = fetch_prices_favorite(fav_id)
    return jsonify({"updated": True, "result": result})


# ── Destination Targets ──────────────────────────────────────────────────────


@app.route("/api/destination-targets/<airport>", methods=["PUT"])
def upsert_destination_target(airport):
    """Set or clear a destination-level target price."""
    airport = airport.strip().upper()
    if not validate_iata(airport):
        return jsonify({"error": "Invalid IATA code"}), 400
    data = request.get_json() or {}
    tp = data.get("target_price")
    if tp is None:
        # null → delete the row (clear target)
        conn = connect_db()
        try:
            conn.execute("DELETE FROM destination_targets WHERE destination_airport = ?", (airport,))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"deleted": airport})
    try:
        tp = float(tp)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid target_price"}), 400
    if tp < 0:
        return jsonify({"error": "target_price must be non-negative"}), 400
    conn = connect_db()
    conn.execute(
        "INSERT OR REPLACE INTO destination_targets (destination_airport, target_price) VALUES (?, ?)",
        (airport, tp),
    )
    conn.commit()
    conn.close()
    return jsonify({"destination_airport": airport, "target_price": tp})


# ── Notifications ────────────────────────────────────────────────────────────


@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Return recent notification log entries."""
    limit = request.args.get("limit", 50)
    try:
        limit = min(int(limit), 200)
    except (TypeError, ValueError):
        limit = 50
    from skybreak.notifications import last_notifications as _last
    return jsonify(_last(limit))


@app.route("/api/notifications/test", methods=["POST"])
def test_notification():
    """Send a test Telegram message with configured credentials."""
    token = get_setting("telegram_bot_token") or ""
    chat_id = get_setting("telegram_chat_id") or ""
    if not token or not chat_id:
        return jsonify({"sent": False, "detail": "Telegram credentials not configured"})
    try:
        from skybreak.notifications import send_telegram as _send
        ok, detail = _send(token, chat_id, "*SkyBreak* — Telegram notification test \u2705")
        if ok:
            return jsonify({"sent": True})
        return jsonify({"sent": False, "detail": detail})
    except Exception as exc:
        return jsonify({"sent": False, "detail": str(exc)})


@app.route("/api/prices", methods=["POST"])
def update_prices():
    global _price_in_progress
    with _price_lock:
        if _price_in_progress:
            return jsonify({"updated": False, "message": "Preisaktualisierung bereits aktiv", "running": True}), 409
        _price_in_progress = True
    from skybreak.flight_prices import fetch_prices_favorite
    def _run_prices():
        global _price_in_progress
        try:
            conn = connect_db()
            rows = conn.execute("SELECT id FROM favorite_trips").fetchall()
            conn.close()
            for (fav_id,) in rows:
                try:
                    fetch_prices_favorite(fav_id, force=True)
                except Exception:
                    pass
        finally:
            with _price_lock:
                _price_in_progress = False
    threading.Thread(target=_run_prices, daemon=True).start()
    return jsonify({"updated": True, "running": True})

@app.route("/api/prices/status", methods=["GET"])
def price_status():
    global _price_in_progress
    with _price_lock:
        running = _price_in_progress
    return jsonify({"running": running})

def _safe_weekdays(values: list[int]) -> list[int]:
    """Keep only valid weekday ints (0=Mon .. 6=Sun)."""
    return [v for v in values if isinstance(v, int) and 0 <= v <= 6]


@app.route("/api/turnarounds", methods=["GET"])
def find_short_trips():
    """Find outbound/return flight combinations within the user's date & weekday prefs."""
    start_str = request.args.get('start', '')
    end_str = request.args.get('end', '')
    start_days_raw = _safe_weekdays(
        [int(x) for x in request.args.get('start_days', '').split(',') if x != ''],
    )
    end_days_raw = _safe_weekdays(
        [int(x) for x in request.args.get('end_days', '').split(',') if x != ''],
    )
    # Fall back to hard-coded defaults if the lists are still empty after filtering.
    start_days = start_days_raw or [4]   # Friday by default
    end_days = end_days_raw or [1]      # Monday by default
    max_dep_str = request.args.get('max_dep_dest', '23:59')
    min_ret_str = request.args.get('min_ret_dep', '00:00')
    start_airport = request.args.get('start_airport', '').strip().upper() or None
    max_trip_days_str = request.args.get('max_trip_days', '')
    max_trip_days = int(max_trip_days_str) if max_trip_days_str and max_trip_days_str.strip().isdigit() else None
    min_trip_days_str = request.args.get('min_trip_days', '')
    min_trip_days = int(min_trip_days_str) if min_trip_days_str and min_trip_days_str.strip().isdigit() else 1
    max_dep_hour, max_dep_min = 23, 59
    try:
        max_dep = max_dep_str.split(':')
        max_dep_hour = int(max_dep[0]) if len(max_dep) > 0 else 23
        max_dep_min = int(max_dep[1]) if len(max_dep) > 1 else 59
    except Exception:
        pass
    min_ret_hour, min_ret_min = 0, 0
    try:
        min_ret = min_ret_str.split(':')
        min_ret_hour = int(min_ret[0]) if len(min_ret) > 0 else 0
        min_ret_min = int(min_ret[1]) if len(min_ret) > 1 else 0
    except Exception:
        pass

    try:
        zeitraum_von = datetime.strptime(start_str, '%Y-%m-%d').strftime('%Y-%m-%d') if start_str else datetime.now().strftime('%Y-%m-%d')
        zeitraum_bis = datetime.strptime(end_str, '%Y-%m-%d').strftime('%Y-%m-%d') if end_str else (datetime.strptime(zeitraum_von, '%Y-%m-%d') + timedelta(days=14)).strftime('%Y-%m-%d')
    except Exception:
        zeitraum_von = datetime.now().strftime('%Y-%m-%d')
        zeitraum_bis = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

    flughafen = start_airport
    max_dauer_tage = max_trip_days if max_trip_days is not None else 7
    min_dauer_tage = min_trip_days if min_trip_days is not None else 1
    spaeteste_hinzeit = f"{max_dep_hour:02d}:{max_dep_min:02d}:00"
    frueheste_rueckzeit = f"{min_ret_hour:02d}:{min_ret_min:02d}:00"

    start_days_str = ','.join(str(d) for d in start_days)
    end_days_str = ','.join(str(d) for d in end_days)

    # 1. SQL-Abfrage Hinflüge (Abflüge vom Startflughafen)
    conn = connect_db()
    sql_hin = f"""SELECT id, to_icao AS ziel, flight_number, departure_time AS abflug_zeit
                   FROM flights
                   WHERE airport_icao = ?
                     AND departure_time >= ?
                     AND departure_time <= ?
                     AND ((CAST(strftime('%w', departure_time) AS INTEGER) + 6) % 7) IN ({start_days_str})
                     AND time(departure_time) <= ?
                   ORDER BY to_icao, departure_time"""
    hinfluege_rows = conn.execute(sql_hin, (flughafen or '', zeitraum_von + ' 00:00:00', zeitraum_bis + ' 23:59:59', spaeteste_hinzeit)).fetchall()

    # 2. SQL-Abfrage Rückflüge (von Ziel zurück zum Startflughafen)
    zeitraum_bis_dt = datetime.strptime(zeitraum_bis, '%Y-%m-%d')  # end gilt auch für Rückflug
    zeitraum_bis_rueck_str = zeitraum_bis_dt.strftime('%Y-%m-%d')
    sql_rueck = f"""SELECT id, from_icao AS start_flughafen, flight_number, departure_time AS abflug_zeit
                     FROM flights
                     WHERE to_icao = ?
                       AND departure_time >= ?
                       AND departure_time <= ?
                       AND ((CAST(strftime('%w', departure_time) AS INTEGER) + 6) % 7) IN ({end_days_str})
                       AND time(departure_time) >= ?
                     ORDER BY from_icao, departure_time"""
    rueckfluege_rows = conn.execute(sql_rueck, (flughafen or '', zeitraum_von + ' 00:00:00', zeitraum_bis_rueck_str + ' 23:59:59', frueheste_rueckzeit)).fetchall()
    conn.close()

    # 3. In-Memory Hash-Join (Gruppierung Rückflüge nach Destination)
    rueckfluege_by_destination = {}
    for flug in rueckfluege_rows:
        ziel_key = flug[1]
        if ziel_key not in rueckfluege_by_destination:
            rueckfluege_by_destination[ziel_key] = []
        rueckfluege_by_destination[ziel_key].append({
            "id": flug[0],
            "start_flughafen": flug[1],
            "flight_number": flug[2],
            "abflug_zeit": flug[3]
        })

    # 4. Lineares Matching (Two-Pointer-Prinzip mit Break bei zu später Rückflugzeit)
    ergebnisse = []
    for hin in hinfluege_rows:
        ziel = hin[1]
        if ziel not in rueckfluege_by_destination:
            continue
        moegliche_rueck = rueckfluege_by_destination[ziel]
        for rueck in moegliche_rueck:
            try:
                hin_zeit = datetime.fromisoformat(str(hin[3]).replace('Z', '+00:00'))
                rueck_zeit = datetime.fromisoformat(str(rueck["abflug_zeit"]).replace('Z', '+00:00'))
                dauer_stunden = (rueck_zeit - hin_zeit).total_seconds() / 3600.0
            except Exception:
                continue
            if dauer_stunden < 0:
                continue  # Rückflug vor Hinflug
            if min_dauer_tage is not None and dauer_stunden < (min_dauer_tage * 24):
                continue  # Unter Mindestlänge
            if max_dauer_tage is not None and dauer_stunden > (max_dauer_tage * 24):
                break  # Weitere Rückflüge für dieses Ziel zu spät (sortiert)
            ergebnisse.append({
                "destination": ziel,
                "hinflug_id": hin[0],
                "hinflug_ziel": ziel,
                "hinflug_flight_number": hin[2] or "",
                "hinflug_ziel_name": _cached_fetch_airport_name(ziel) or ziel,
                "hinflug_abflug_zeit": hin[3],
                "rueckflug_id": rueck["id"],
                "rueckflug_start": rueck["start_flughafen"],
                "rueckflug_start_name": _cached_fetch_airport_name(rueck["start_flughafen"]) or rueck["start_flughafen"],
                "rueckflug_abflug_zeit": rueck["abflug_zeit"],
                "rueckflug_flight_number": rueck.get("flight_number") or "",
                "dauer_tage": round(dauer_stunden / 24.0, 2)
            })
    ergebnisse.sort(key=lambda x: x.get("hinflug_abflug_zeit", ""))
    # Favoriten-Status ergänzen
    conn = connect_db()
    fav_rows = conn.execute("SELECT outbound_trip_date, destination_airport, outbound_flight_number, return_flight_number, return_trip_date FROM favorite_trips").fetchall()
    conn.close()
    # Each favorite keyed by (out_date, dest, out_f, ret_f, ret_date). The old
    # tuple duplicated the return flight number in place of the return date and
    # the match only compared the first four fields, so a favorite with a
    # concrete return date flagged turnarounds returning on any other day.
    fav_set = {
        (r[0] or '', r[1] or '', r[2] or '', r[3] or '', r[4] or '')
        for r in fav_rows
    }
    for item in ergebnisse:
        trip_date = str(item.get("hinflug_abflug_zeit", "")).split()[0] if item.get("hinflug_abflug_zeit") else ""
        turn_ret_date = str(item.get("rueckflug_abflug_zeit", "")).split()[0] if item.get("rueckflug_abflug_zeit") else ""
        dest = item.get("hinflug_ziel") or item.get("destination") or ""
        out_f = item.get("hinflug_flight_number") or ""
        ret_f = item.get("rueckflug_flight_number") or ""
        # Match is exact on dest / outbound / return flight; an empty favorite
        # return date stays permissive, otherwise the turnaround must return on
        # the day the favorite expects.
        item["is_favorite"] = any(
            (fav[0] == trip_date or trip_date == '') and
            (fav[1] == dest) and
            (fav[2] == out_f) and
            (fav[3] == ret_f) and
            (fav[4] == '' or turn_ret_date == fav[4])
            for fav in fav_set
        )
    return jsonify({"turnarounds": ergebnisse, "count": len(ergebnisse), "algorithm": "sql_filter_hash_join"})

@app.route("/api/prices/missing", methods=["POST"])
def update_missing_prices():
    global _price_in_progress
    with _price_lock:
        if _price_in_progress:
            return jsonify({"updated": False, "message": "Preisaktualisierung bereits aktiv", "running": True}), 409
        _price_in_progress = True
    from skybreak.flight_prices import fetch_prices_favorite
    def _run_missing():
        global _price_in_progress
        try:
            conn = connect_db()
            rows = conn.execute("SELECT DISTINCT ft.id FROM favorite_trips ft LEFT JOIN favorite_trip_prices ftp ON ft.id = ftp.favorite_id WHERE ftp.favorite_id IS NULL OR ftp.price_outbound IS NULL OR ftp.price_return IS NULL").fetchall()
            conn.close()
            for (fav_id,) in rows:
                try:
                    fetch_prices_favorite(fav_id, force=True)
                except Exception:
                    pass
        finally:
            with _price_lock:
                _price_in_progress = False
    threading.Thread(target=_run_missing, daemon=True).start()
    return jsonify({"updated": True, "running": True})


# ── Health Dashboard ────────────────────────────────────────────────────────

# Secret keys that must never appear in backup exports.
_SECRET_KEYS = frozenset(("telegram_bot_token",))


@app.route("/api/health")
def health():
    """Health dashboard data: run logs, airport freshness, context counts."""
    conn = connect_db()

    # DB version
    try:
        db_version = conn.execute("SELECT version FROM db_version LIMIT 1").fetchone()[0]
    except Exception:
        db_version = 0

    # Airports with max departure and stale flag
    fetch_max_months_raw = get_setting("fetch_max_months") or "3"
    try:
        fetch_max_months = int(fetch_max_months_raw)
    except Exception:
        fetch_max_months = 3
    fetch_max_months = max(1, min(fetch_max_months, 12))

    # Window = today + fetch_max_months * 30 days, minus 7 day grace
    now_dt = datetime.now(timezone.utc)
    window_end = (now_dt + timedelta(days=fetch_max_months * 30 - 7)).isoformat()

    airports_rows = conn.execute(
        "SELECT a.code, COALESCE(a.name, ''), MAX(f.departure_time) AS max_dep "
        "FROM airports a LEFT JOIN flights f ON f.airport_icao = a.code "
        "GROUP BY a.code"
    ).fetchall()
    airports = []
    for code, name, max_dep in airports_rows:
        stale = False
        if max_dep:
            try:
                dep_str = str(max_dep).replace("Z", "+00:00")
                dep_dt = datetime.fromisoformat(dep_str)
                if dep_dt.tzinfo is None:
                    dep_dt = dep_dt.replace(tzinfo=timezone.utc)
                stale = dep_dt < datetime.fromisoformat(window_end)
            except Exception:
                stale = True
        airports.append({
            "code": code,
            "name": name or code,
            "max_departure": max_dep,
            "stale": stale,
        })

    # Last scrape run
    try:
        sr = conn.execute(
            "SELECT started_at, finished_at, status, airports, flights_saved "
            "FROM scrape_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_scrape = {
            "started_at": sr[0],
            "finished_at": sr[1],
            "status": sr[2],
            "airports": sr[3],
            "flights_saved": sr[4],
        } if sr else None
    except Exception:
        last_scrape = None

    # Last price run
    try:
        pr = conn.execute(
            "SELECT started_at, finished_at, status, total, success, failed "
            "FROM price_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_price_run = {
            "started_at": pr[0],
            "finished_at": pr[1],
            "status": pr[2],
            "total": pr[3],
            "success": pr[4],
            "failed": pr[5],
        } if pr else None
    except Exception:
        last_price_run = None

    # Context counts
    try:
        flights_total = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    except Exception:
        flights_total = 0
    try:
        favorites_total = conn.execute("SELECT COUNT(*) FROM favorite_trips").fetchone()[0]
    except Exception:
        favorites_total = 0
    try:
        quotes_cached = conn.execute("SELECT COUNT(*) FROM trip_price_quotes").fetchone()[0]
    except Exception:
        quotes_cached = 0

    conn.close()

    return jsonify({
        "db_version": db_version,
        "airports": airports,
        "last_scrape": last_scrape,
        "last_price_run": last_price_run,
        "flights_total": flights_total,
        "favorites_total": favorites_total,
        "quotes_cached": quotes_cached,
        "fetch_max_months": fetch_max_months,
    })


# ── Backup Export / Import ──────────────────────────────────────────────────

_USER_TABLES = [
    "airports",
    "favorite_trips",
    "trip_search_configs",
    "destination_targets",
    "notifications",
    "settings",
]


@app.route("/api/backup/export")
def backup_export():
    """Export user data as JSON (no flights, no secrets)."""
    conn = connect_db()

    try:
        db_version_row = conn.execute("SELECT version FROM db_version LIMIT 1").fetchone()
        db_version = db_version_row[0] if db_version_row else 0
    except Exception:
        db_version = 0

    result = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "db_version": db_version,
    }

    for table in _USER_TABLES:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
            desc = [d[1] for d in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            result[table] = [dict(zip(desc, r)) for r in rows]
        except Exception:
            result[table] = []

    # Filter secrets from settings
    if "settings" in result:
        result["settings"] = [
            s for s in result["settings"] if s.get("key") not in _SECRET_KEYS
        ]

    conn.close()
    return jsonify(result)


@app.route("/api/backup/import", methods=["POST"])
def backup_import():
    """Import user data from JSON (upsert by natural keys, transactional)."""
    data = request.get_json(force=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload: expected object"}), 400

    export_version = data.get("version")
    if export_version is None or export_version != 1:
        return jsonify({"error": f"Unsupported export version: {export_version}"}), 400

    required_tables = {"airports", "favorite_trips", "trip_search_configs", "settings"}
    missing = required_tables - set(data.keys())
    if missing:
        return jsonify({"error": f"Missing tables: {', '.join(sorted(missing))}"}), 400

    conn = connect_db()
    try:
        imported = {}
        for table in _USER_TABLES:
            items = data.get(table, [])
            if not isinstance(items, list):
                continue
            count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                keys = list(item.keys())
                values = [item[k] for k in keys]
                placeholders = ", ".join("?" * len(keys))
                col_list = ", ".join(keys)
                try:
                    conn.execute(
                        f"INSERT OR REPLACE INTO {table} ({col_list}) "
                        f"VALUES ({placeholders})",
                        values,
                    )
                    count += 1
                except Exception:
                    pass  # skip malformed rows
            imported[table] = count

        conn.commit()
        return jsonify({
            "imported_tables": imported,
            "message": f"Imported {sum(imported.values())} total rows",
        })
    except Exception as e:
        conn.rollback()
        logger.error("Backup import failed: %s", e)
        return jsonify({"error": f"Import failed: {e}"}), 500


# ── Refresh-status endpoint ──────────────────────────────────────────────────


@app.route("/api/refresh-status", methods=["GET"])
def refresh_status():
    """Return the current refresh scheduler configuration and enabled state."""
    try:
        interval = int(get_setting("refresh_interval_days") or "7")
    except Exception:
        interval = 7
    return jsonify({
        "interval_days": interval,
        "enabled": interval > 0,
    })


if __name__ == "__main__":
    # Migrations already applied at module load (line 65); start schedulers and serve.
    from skybreak.scraper_job import start_price_scheduler, start_refresh_scheduler

    start_price_scheduler()
    start_refresh_scheduler()
    app.run(host="0.0.0.0", port=80)

# Batch restructuring implemented
