"""Named trip search configurations, stored in SQLite.

A configuration holds exactly the six configurable search fields of the Trips
tab (start/end weekdays, latest outbound departure, earliest return departure,
min/max trip length). Airport selection and the date range are deliberately not
part of it. Because the rows live in the database, every browser and device
talking to this backend sees the same set.

Column names are snake_case in the DB and camelCase on the wire; the mapping is
kept here so the frontend never has to know the schema.
"""
import logging

from skybreak.db import connection

logger = logging.getLogger(__name__)

WEEKDAY_COUNT = 7  # API convention: 0=Monday .. 6=Sunday
MIN_TRIP_DAYS = 1
MAX_TRIP_DAYS = 365

_COLUMNS = (
    "name", "start_weekdays", "end_weekdays", "max_dep_to_dest",
    "min_ret_dep", "min_trip_days", "max_trip_days",
)


def _weekdays(value) -> str:
    """Comma-joined, de-duplicated, sorted weekday numbers; junk is dropped."""
    if not isinstance(value, (list, tuple)):
        return ""
    seen = set()
    for item in value:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= n < WEEKDAY_COUNT:
            seen.add(n)
    return ",".join(str(n) for n in sorted(seen))


def _parse_weekdays(value) -> list[int]:
    if not value:
        return []
    out = []
    for part in str(value).split(","):
        try:
            n = int(part)
        except ValueError:
            continue
        if 0 <= n < WEEKDAY_COUNT:
            out.append(n)
    return out


def _time(value) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if len(text) == 5 and text[2] == ":" and text[:2].isdigit() and text[3:].isdigit():
        hh, mm = int(text[:2]), int(text[3:])
        if hh < 24 and mm < 60:
            return text
    return ""


def _days(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if MIN_TRIP_DAYS <= n <= MAX_TRIP_DAYS:
        return n
    return None


def sanitize_config(raw) -> dict | None:
    """Normalize a raw payload into a storable config, or None if unusable.

    A missing/blank name makes the entry unusable; individual bad field values
    fall back to their empty default so one malformed field never loses the
    whole configuration.
    """
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name:
        return None
    return {
        "name": name,
        "startWeekdays": _parse_weekdays(_weekdays(raw.get("startWeekdays"))),
        "endWeekdays": _parse_weekdays(_weekdays(raw.get("endWeekdays"))),
        "maxDepToDest": _time(raw.get("maxDepToDest")),
        "minRetDep": _time(raw.get("minRetDep")),
        "minTripDays": _days(raw.get("minTripDays")),
        "maxTripDays": _days(raw.get("maxTripDays")),
    }


def _row_to_config(row) -> dict:
    return {
        "name": row[0],
        "startWeekdays": _parse_weekdays(row[1]),
        "endWeekdays": _parse_weekdays(row[2]),
        "maxDepToDest": row[3] or "",
        "minRetDep": row[4] or "",
        "minTripDays": row[5],
        "maxTripDays": row[6],
    }


def list_configs() -> list[dict]:
    """All configurations, alphabetically by name (case-insensitive)."""
    with connection() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM trip_search_configs ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [_row_to_config(r) for r in rows]


def save_config(config) -> dict | None:
    """Insert or replace by name (case-insensitive, last write wins).

    Returns the sanitized configuration, or None if it has no usable name.
    """
    clean = sanitize_config(config)
    if clean is None:
        return None
    params = (
        clean["name"],
        _weekdays(clean["startWeekdays"]),
        _weekdays(clean["endWeekdays"]),
        clean["maxDepToDest"],
        clean["minRetDep"],
        clean["minTripDays"],
        clean["maxTripDays"],
    )
    updates = ", ".join(f"{c} = excluded.{c}" for c in _COLUMNS[1:])
    with connection() as conn:
        conn.execute(
            f"INSERT INTO trip_search_configs ({', '.join(_COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(_COLUMNS))}) "
            "ON CONFLICT(name) DO UPDATE SET "
            # name is reassigned so the saved spelling wins, matching the UI,
            # which lists and deletes configs by their exact stored name.
            f"name = excluded.name, {updates}, updated_at = CURRENT_TIMESTAMP",
            params,
        )
        conn.commit()
    return clean


def delete_config(name: str) -> bool:
    """Delete by name (case-insensitive). True if a row was removed."""
    target = name.strip() if isinstance(name, str) else ""
    if not target:
        return False
    with connection() as conn:
        cur = conn.execute("DELETE FROM trip_search_configs WHERE name = ?", (target,))
        conn.commit()
    return cur.rowcount > 0
