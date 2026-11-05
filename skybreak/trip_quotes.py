"""On-demand price quotes for candidate trips (TripsTab).

When a user clicks "show price" on a turnaround result, this module fetches
outbound + return quotes via ``get_flight_price``, caches the result in the
DB (1 h freshness window), and returns the combined pricing.  A leg that
Google does not list keeps ``None``; total is ``None`` if either available
leg has no price (same rule as ``fetch_prices_favorite``).
"""
import logging
from datetime import datetime, timezone

from skybreak.db import connect_db
from skybreak.get_flight_price import get_flight_price

logger = logging.getLogger(__name__)


def quote_trip(start, dest, out_date, ret_date, out_fnum, ret_fnum,
               max_age_hours=1) -> dict:
    """Quote a candidate turnaround trip.

    1. DB lookup by the unique key; fetched_at within *max_age_hours* → return
       cached row (no Google call).
    2. Else fetch both legs via ``get_flight_price``, each in its own
       try/except so one failure doesn't kill the other.
    3. total = sum if both present else None.
    4. Upsert the row and return the result dict.

    Parameters
    ----------
    start, dest : str
        Departure / destination IATA codes (will be uppercased).
    out_date, ret_date : str
        Dates in ``YYYY-MM-DD`` format.
    out_fnum, ret_fnum : str
        Flight numbers for the outbound and return legs.
    max_age_hours : int | float
        Maximum age of a cached quote in hours (default 1).

    Returns
    -------
    dict
        {price_outbound, price_return, price_total, currency, fetched_at,
         cached: bool}
    """
    start = str(start).upper()
    dest = str(dest).upper()
    out_fnum = str(out_fnum)
    ret_fnum = str(ret_fnum)

    conn = connect_db()
    try:
        # 1. Try cached row
        row = conn.execute(
            """SELECT price_outbound, price_return, price_total, currency, fetched_at
               FROM trip_price_quotes
               WHERE start_airport = ? AND destination_airport = ?
                 AND outbound_date = ? AND return_date = ?
                 AND outbound_flight_number = ? AND return_flight_number = ?""",
            (start, dest, out_date, ret_date, out_fnum, ret_fnum),
        ).fetchone()

        if row:
            price_out, price_ret, price_total, currency, fetched_at_str = row
            # Check freshness
            fetched_at = datetime.fromisoformat(fetched_at_str.replace('Z', '+00:00'))
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600.0
            if age <= max_age_hours:
                logger.debug("Cache hit for %s→%s out=%s ret=%s (age=%.1fh)",
                             start, dest, out_date, ret_date, age)
                return {
                    "price_outbound": price_out,
                    "price_return": price_ret,
                    "price_total": price_total,
                    "currency": currency or "EUR",
                    "fetched_at": fetched_at_str,
                    "cached": True,
                }

        # 2. Fetch both legs independently — each in its own try/except so one
        # failure doesn't kill the other. All exceptions (including RuntimeError
        # from scraper HTTP failures) are treated as "leg not listed" → None.
        price_out = None
        price_ret = None

        if out_date and out_fnum:
            try:
                price_out = get_flight_price(start, dest, out_date, out_fnum)
            except Exception as e:
                logger.warning("Outbound quote failed for %s→%s %s: %s",
                               start, dest, out_date, e)

        if ret_date and ret_fnum:
            try:
                price_ret = get_flight_price(dest, start, ret_date, ret_fnum)
            except Exception as e:
                logger.warning("Return quote failed for %s→%s %s: %s",
                               dest, start, ret_date, e)

        # 3. Combine: total is None if either available leg has no price
        out_available = bool(out_date and out_fnum)
        ret_available = bool(ret_date and ret_fnum)
        out_has_price = price_out is not None
        ret_has_price = price_ret is not None

        if (out_available and not out_has_price) or (ret_available and not ret_has_price):
            total = None
        else:
            total = (price_out or 0) + (price_ret or 0) \
                if (price_out is not None or price_ret is not None) else None

        # 4. Upsert
        fetched_at_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT OR REPLACE INTO trip_price_quotes
               (start_airport, destination_airport, outbound_date, return_date,
                outbound_flight_number, return_flight_number,
                price_outbound, price_return, price_total, currency, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'EUR', ?)""",
            (start, dest, out_date, ret_date, out_fnum, ret_fnum,
             price_out, price_ret, total, fetched_at_now),
        )
        conn.commit()

        return {
            "price_outbound": price_out,
            "price_return": price_ret,
            "price_total": total,
            "currency": "EUR",
            "fetched_at": fetched_at_now,
            "cached": False,
        }
    finally:
        conn.close()
