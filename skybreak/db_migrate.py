"""Streamlined DB migration: version saved in the db, one step per schema
change, applied at container startup.

Rules:
  * Schema version is stored in the ``db_version`` table.
  * Every schema change is its own migration step and increases the version.
  * Runtime uses only this module (``apply_migrations``); no separate init scripts.
"""
import logging
import sqlite3

from skybreak.db import db_path

logger = logging.getLogger(__name__)

# Settings that are safe to keep across restarts; everything else is purged so
# stale/renamed keys don't linger in the settings table.
SETTINGS_WHITELIST = (
    "scrape_delay_ms",
    "fetch_max_months",
    "fetch_max_days",
    "favorite_max_items",
    "google_consent_cookie",
    "price_fetch_interval_hours",
)

GOOGLE_CONSENT_COOKIE = "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmRlIAEaBgiAo_CmBg"


def get_current_version(conn):
    try:
        row = conn.execute("SELECT version FROM db_version LIMIT 1").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _bump(conn, version):
    conn.execute("DELETE FROM db_version")
    conn.execute("INSERT INTO db_version (version) VALUES (?)", (version,))
    logger.info("Applied migration v%d", version)


def _favorite_cols(conn):
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(favorite_trips)").fetchall()}
    except sqlite3.OperationalError:
        return set()


def _table_cols(conn, table):
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.OperationalError:
        return set()


def _drop_indexes_referencing(conn, table, columns):
    """Drop every index on `table` that references any of `columns`."""
    import re
    try:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (table,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for idx_name, idx_sql in rows:
        sql = idx_sql or ""
        if any(re.search(rf"\b{re.escape(col)}\b", sql) for col in columns):
            conn.execute(f"DROP INDEX IF EXISTS {idx_name}")



def migration_v1(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS airports (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    # Rebuild the flights table if it has a partial/legacy schema.
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(flights)").fetchall()}
    except sqlite3.OperationalError:
        cols = set()
    full = {"id", "airport_icao", "airport_name", "destination_icao", "destination_name",
            "flight_direction", "departure_time", "arrival_time", "duration_minutes",
            "flight_number", "from_icao", "to_icao", "created_at",
            "flight_date", "arrival_date", "departure", "arrival", "month_key"}
    flights_ddl = ("CREATE TABLE flights (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "airport_icao TEXT, airport_name TEXT, destination_icao TEXT, "
                   "destination_name TEXT, flight_direction TEXT, departure_time TEXT, "
                   "arrival_time TEXT, duration_minutes INTEGER, flight_number TEXT, "
                   "from_icao TEXT, to_icao TEXT, flight_date TEXT, arrival_date TEXT, "
                   "departure TEXT, arrival TEXT, month_key TEXT, "
                   "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    if cols and not full.issubset(cols):
        conn.execute("ALTER TABLE flights RENAME TO flights_old")
        conn.execute(flights_ddl)
        try:
            common = [c for c in
                     ("airport_icao", "airport_name", "destination_icao", "destination_name",
                      "flight_direction", "departure_time", "arrival_time", "duration_minutes",
                      "flight_number", "from_icao", "to_icao", "month_key", "flight_date",
                      "arrival_date", "departure", "arrival")
                     if c in cols]
            common_str = ", ".join(common) if common else "airport_icao"
            conn.execute(
                f"INSERT INTO flights ({common_str}, created_at) "
                f"SELECT {common_str}, CURRENT_TIMESTAMP FROM flights_old")
        except sqlite3.Error:
            pass
        conn.execute("DROP TABLE flights_old")
    else:
        conn.execute(flights_ddl.replace("CREATE TABLE flights", "CREATE TABLE IF NOT EXISTS flights"))
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_airport ON flights (airport_icao, departure_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fluege_matching ON flights (airport_icao, to_icao, departure_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_airport_month ON flights (airport_icao, month_key)")
    conn.execute("CREATE TABLE IF NOT EXISTS db_version (version INTEGER PRIMARY KEY)")
    _bump(conn, 1)


def migration_v2(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS favorite_trips (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_date TEXT, start_time TEXT, destination_airport TEXT, outbound_flight_number TEXT, return_flight_number TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, start_airport TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite_trips_date ON favorite_trips (trip_date)")
    _bump(conn, 2)


def migration_v3(conn):
    cols = _favorite_cols(conn)
    for col in ("outbound_trip_date", "return_trip_date", "start_airport"):
        if col not in cols:
            conn.execute(f"ALTER TABLE favorite_trips ADD COLUMN {col} TEXT")
    _bump(conn, 3)


def migration_v4(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS favorite_trip_prices (favorite_id INTEGER, price_outbound REAL, price_return REAL, price_total REAL, currency TEXT, fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite_prices ON favorite_trip_prices (favorite_id, fetched_at)")
    _bump(conn, 4)


def migration_v5(conn):
    cols = _favorite_cols(conn)
    if "outbound_trip_date" not in cols:
        conn.execute("ALTER TABLE favorite_trips ADD COLUMN outbound_trip_date TEXT")
    if "return_trip_date" not in cols:
        conn.execute("ALTER TABLE favorite_trips ADD COLUMN return_trip_date TEXT")
    _bump(conn, 5)


def migration_v6(conn):
    cols = _favorite_cols(conn)
    if "return_time" not in cols:
        conn.execute("ALTER TABLE favorite_trips ADD COLUMN return_time TEXT")
    _bump(conn, 6)


def migration_v7(conn):
    cols = _favorite_cols(conn)
    needed = ["trip_date", "start_time", "destination_airport", "outbound_flight_number",
              "return_flight_number", "start_airport", "outbound_trip_date",
              "return_trip_date", "return_time"]
    if all(c in cols for c in needed):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_unique ON favorite_trips "
            "(trip_date, start_time, destination_airport, outbound_flight_number, "
            "return_flight_number, start_airport, outbound_trip_date, return_trip_date, return_time)"
        )
    _bump(conn, 7)


def migration_v8(conn):
    conn.execute("DROP TABLE IF EXISTS price_history")
    _bump(conn, 8)


def migration_v9(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite_prices_fav_fetched_asc ON favorite_trip_prices (favorite_id, fetched_at ASC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite_prices_fav_fetched_desc ON favorite_trip_prices (favorite_id, fetched_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite_trips_id ON favorite_trips (id)")
    _bump(conn, 9)


def migration_v10(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_fnum_date ON flights (flight_number, date(departure_time))")
    _bump(conn, 10)


def migration_v11(conn):
    """Drop the legacy per-trip time/date columns that are no longer used.

    SQLite cannot drop a column that is part of an index, so drop every index on
    ``favorite_trips`` that references those columns first, drop the columns, then
    rebuild the unique index on the surviving columns. Wrapped so a partial/older
    state never leaves a half-migrated table.
    """
    cols = _favorite_cols(conn)
    if not cols:
        _bump(conn, 11)
        return
    try:
        to_drop = ("start_time", "return_time", "trip_date")
        _drop_indexes_referencing(conn, "favorite_trips", to_drop)
        for col in to_drop:
            if col in cols:
                conn.execute(f"ALTER TABLE favorite_trips DROP COLUMN {col}")
        # Rebuild the unique index on the columns that still exist.
        remaining = [c for c in
                     ("destination_airport", "outbound_flight_number", "return_flight_number",
                      "start_airport", "outbound_trip_date", "return_trip_date")
                     if c in cols]
        if remaining:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_unique ON favorite_trips "
                f"({', '.join(remaining)})"
            )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.warning("Migration v11 partially applied, retrying next start: %s", e)
        raise
    _bump(conn, 11)


def migration_v12(conn):
    """Give `flights` the full scraper-era schema, version-tracked.

    The Kayak scraper previously added these columns (and the month index) at
    runtime inside the data path. Owning them here removes that runtime mutation
    and makes the schema identical for a fresh DB and an existing one. Existing
    rows keep their values (columns are added, not dropped).
    """
    cols = _table_cols(conn, "flights")
    if not cols:
        # Fresh/absent table: migration_v1 already created the canonical DDL,
        # which now includes these columns. Nothing more to do.
        _bump(conn, 12)
        return
    for col, col_type in (
        ("flight_date", "TEXT"),
        ("arrival_date", "TEXT"),
        ("departure", "TEXT"),
        ("arrival", "TEXT"),
        ("month_key", "TEXT"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE flights ADD COLUMN {col} {col_type}")
            logger.info("Migration v12: added column %s to flights", col)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_airport_month ON flights (airport_icao, month_key)")
    _bump(conn, 12)


def migration_v13(conn):
    """Named trip search configurations, shared by every browser.

    They used to live in browser localStorage, so each device had its own set.
    The six configurable search fields get one column each (stable, validatable,
    queryable) instead of a JSON blob. ``name`` is unique case-insensitively,
    which is the same duplicate rule the UI already applies.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trip_search_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            start_weekdays TEXT NOT NULL DEFAULT '',
            end_weekdays TEXT NOT NULL DEFAULT '',
            max_dep_to_dest TEXT NOT NULL DEFAULT '',
            min_ret_dep TEXT NOT NULL DEFAULT '',
            min_trip_days INTEGER,
            max_trip_days INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _bump(conn, 13)


MIGRATIONS = [
    migration_v1, migration_v2, migration_v3, migration_v4, migration_v5,
    migration_v6, migration_v7, migration_v8, migration_v9, migration_v10,
    migration_v11, migration_v12, migration_v13,
]


def apply_migrations(path: str | None = None):
    """Apply pending migrations to the configured database.

    ``path`` defaults to the shared ``db_path()`` (call-time ``DB_FILE``); pass
    an explicit path to migrate a specific file without touching the environment.
    """
    db_path_ = path or db_path()
    conn = sqlite3.connect(db_path_, timeout=30.0)
    try:
        current = get_current_version(conn)
        for step_no, migrate in enumerate(MIGRATIONS, start=1):
            if current < step_no:
                migrate(conn)
                # Commit each step so a failure in a later step cannot undo the
                # schema created by earlier steps.
                conn.commit()
                current = get_current_version(conn)
        placeholders = ", ".join("?" * len(SETTINGS_WHITELIST))
        conn.execute(
            f"DELETE FROM settings WHERE key NOT IN ({placeholders})",
            SETTINGS_WHITELIST,
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("google_consent_cookie", GOOGLE_CONSENT_COOKIE),
        )
        # Seed the defaults the price scheduler and scraper read on first run.
        for key, default in (("price_fetch_interval_hours", "6"), ("fetch_max_months", "3")):
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, default))
        conn.commit()
    finally:
        conn.close()
    logger.info("DB at version %d", get_current_version(sqlite3.connect(db_path_, timeout=30.0)))


if __name__ == "__main__":
    apply_migrations()
