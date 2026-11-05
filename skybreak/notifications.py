"""Price-alert evaluation and Telegram notification dispatch.

Functions:
    send_telegram(token, chat_id, text) -> tuple[bool, str]
    effective_target(favorite_row, dest_airport) -> tuple[float | None, 'trip' | 'destination' | None]
    evaluate_alert(favorite_id) -> dict | None
    last_notifications(limit=50) -> list[dict]
"""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING, Literal

import requests

from skybreak.db import connect_db, get_setting

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ── Telegram dispatch ────────────────────────────────────────────────────────


def send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """POST to the Telegram Bot API *sendMessage* endpoint.

    Returns ``(True, "")`` on success or ``(False, error_detail)`` on any failure.
    Never raises — network and API errors are caught and returned as a tuple.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, ""
        detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        logger.warning("Telegram API error: %s", detail)
        return False, detail
    except Exception as exc:
        msg = str(exc)
        logger.warning("Telegram send failed: %s", msg)
        return False, msg


# ── Target resolution ────────────────────────────────────────────────────────


def effective_target(
    favorite_row: dict | sqlite3.Row, dest_airport: str
) -> tuple[float | None, Literal["trip", "destination"] | None]:
    """Resolve the effective target price and scope for a single favorite.

    Resolution rule (per design doc):
        1. If the trip has ``target_price`` set → use it with scope 'trip'.
        2. Else if there is a destination-level target → use it with scope 'destination'.
        3. Else → no alert (None, None).

    ``favorite_row`` is a dict/Row from the DB containing at least:
        - ``target_price`` (may be NULL)
        - ``destination_airport``
    """
    trip_target = favorite_row.get("target_price")
    if trip_target is not None:
        return float(trip_target), "trip"

    # Fall back to destination target
    conn = connect_db()
    try:
        row = conn.execute(
            "SELECT target_price FROM destination_targets WHERE destination_airport = ?",
            (dest_airport,),
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0]), "destination"
    finally:
        conn.close()

    return None, None


# ── Alert evaluation ────────────────────────────────────────────────────────


def evaluate_alert(favorite_id: int) -> dict | None:
    """Edge-triggered alert check after a successful price fetch.

    Returns a notification dict (to be stored in DB) when an alert fires,
    or ``None`` when there is nothing to do.

    Algorithm (per design doc):
        1. Read favorite + destination target; resolve effective target & scope.
           No effective target → return None.
        2. Read last two favorite_trip_prices rows (newest first).
        3. Fire only if ALL hold:
             new_total is not None and new_total <= target
             previous_total is None or previous_total > target   # re-arm rule
           (previous=None covers the very first price of a favorite already below target)
        4. Compose message, send via Telegram, insert notifications row.
    """
    conn = connect_db()
    try:
        # ── 1. Read favorite + resolve effective target ────────────────────
        fav_row = conn.execute(
            "SELECT id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price "
            "FROM favorite_trips WHERE id = ?",
            (favorite_id,),
        ).fetchone()
        if not fav_row:
            return None

        # fav_row is a sqlite3.Row when Row factory is set, else tuple.
        # Handle both: use dict-like access when available, fallback to index.
        if hasattr(fav_row, 'keys'):
            dest_airport = fav_row["destination_airport"] or ""
            trip_target = fav_row["target_price"]
        else:
            # (id, destination_airport, start_airport, out_date, ret_date, out_fnum, ret_fnum, target_price)
            dest_airport = fav_row[1] or ""
            trip_target = fav_row[7]

        # Resolve effective target from DB directly to avoid extra helper call
        scope: Literal["trip", "destination"] | None = None
        if trip_target is not None:
            target = float(trip_target)
            scope = "trip"
        else:
            dest_row = conn.execute(
                "SELECT target_price FROM destination_targets WHERE destination_airport = ?",
                (dest_airport,),
            ).fetchone()
            if dest_row and dest_row[0] is not None:
                target = float(dest_row[0])
                scope = "destination"
            else:
                return None  # no effective target → nothing to do

        # ── 2. Read last two price rows ────────────────────────────────────
        prices = conn.execute(
            "SELECT price_total FROM favorite_trip_prices "
            "WHERE favorite_id = ? ORDER BY fetched_at DESC LIMIT 2",
            (favorite_id,),
        ).fetchall()

        if not prices:
            return None  # no price data yet

        new_total = prices[0][0] if isinstance(prices[0], tuple) else prices[0]["price_total"]

        # previous row (may not exist → first price ever)
        if len(prices) > 1:
            prev_total = prices[1][0] if isinstance(prices[1], tuple) else prices[1]["price_total"]
        else:
            prev_total = None

        # ── 3. Edge-trigger check ─────────────────────────────────────────
        # new_total must be valid and ≤ target
        if new_total is None or new_total > target:
            return None

        # re-arm rule: previous must be above target or None (first price)
        if prev_total is not None and prev_total <= target:
            return None

        # ── 4. Compose & send ──────────────────────────────────────────────
        message = _compose_message(fav_row, new_total, target, scope)

        token = get_setting("telegram_bot_token") or ""
        chat_id = get_setting("telegram_chat_id") or ""

        if not token or not chat_id:
            # No credentials → silently inactive (per design doc edge case)
            return None

        ok, detail = send_telegram(token, chat_id, message)

        # ── 5. Log notification ────────────────────────────────────────────
        status = "sent" if ok else "failed"
        conn.execute(
            "INSERT INTO notifications "
            "(favorite_id, channel, message, status, target_scope, detail) "
            "VALUES (?, 'telegram', ?, ?, ?, ?)",
            (
                favorite_id,
                message,
                status,
                scope,
                detail if not ok else None,
            ),
        )
        conn.commit()

        return {
            "id": conn.execute("SELECT last_insert_rowid()").fetchone()[0],
            "favorite_id": favorite_id,
            "channel": "telegram",
            "message": message,
            "status": status,
            "target_scope": scope,
            "detail": detail if not ok else None,
        }
    except Exception as exc:
        logger.exception("evaluate_alert(%s) raised: %s", favorite_id, exc)
        return None
    finally:
        conn.close()


def _compose_message(
    fav_row,  # sqlite3.Row or tuple
    new_total: float,
    target: float,
    scope: str | None,
) -> str:
    """Compose the Telegram notification message body (per design doc format)."""
    if hasattr(fav_row, 'keys'):
        start = fav_row["start_airport"] or "?"
        dest = fav_row["destination_airport"] or "?"
        out_fnum = fav_row["outbound_flight_number"] or ""
        ret_fnum = fav_row["return_flight_number"] or ""
        out_date = fav_row["outbound_trip_date"] or "?"
        ret_date = fav_row["return_trip_date"] or "?"
    else:
        # (id, destination_airport, start_airport, out_date, ret_date, out_fnum, ret_fnum, target_price)
        start = fav_row[2] or "?"
        dest = fav_row[1] or "?"
        out_fnum = fav_row[5] or ""
        ret_fnum = fav_row[6] or ""
        out_date = fav_row[3] or "?"
        ret_date = fav_row[4] or "?"

    flights = " / ".join(filter(None, [out_fnum, ret_fnum])) or ""

    lines = [
        f"\U0001f4e9 *SkyBreak price alert*",
        f"{start} \u2192 {dest}\u00b7{flights}".rstrip(),
        f"Out {out_date} \u00b7 Ret {ret_date}",
    ]

    scope_label = ""
    if scope == "trip":
        scope_label = " (trip)"
    elif scope == "destination":
        scope_label = " (destination)"

    lines.append(
        f"Total: *{new_total:.0f} €* (target \u2264 {target:.0f}{scope_label})"
    )

    return "\n".join(lines)


# ── Notification log ────────────────────────────────────────────────────────


def last_notifications(limit: int = 50) -> list[dict]:
    """Return recent notification log entries ordered newest first."""
    conn = connect_db()
    try:
        rows = conn.execute(
            "SELECT id, favorite_id, channel, message, status, target_scope, detail, sent_at "
            "FROM notifications ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        cols = ["id", "favorite_id", "channel", "message", "status", "target_scope", "detail", "sent_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()
