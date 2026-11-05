# Design: On-Demand Price Quotes for Candidate Trips

**Status:** Implemented — PR #80 merged as 3a1b2c4
**Date:** 2026-11-05
**Migration number:** v14
**Related:** price infrastructure (`get_flight_price`, `flight_prices`), TripsTab

## Problem

TripsTab search results show **no prices at all**. The only way to see a price for a
candidate turnaround is to favorite it and wait up to the next price-fetch cycle (default
6 h). Consequences:

- Users cannot compare candidates before committing.
- Favorites become a dumping ground for "maybe" trips, which also wastes Google Flights
  scraper quota on trips that are never booked.

## User Story (add to `doc/user-stories.md` at implementation time)

**As a user**, I want to see the current price of a candidate trip without favoriting it,
**so that** I can compare options before deciding what to monitor.

Acceptance criteria:
- Each turnaround result row has a "show price" action (mobile card + desktop table view).
- Clicking it fetches outbound + return quotes and displays out / ret / total in the row.
- Quotes persist across page refreshes (DB cache, 1 h freshness window).
- Per-row loading and error states; a leg not listed by Google shows "–", not an error.
- Quoting is strictly user-initiated — no automatic mass quoting of search results.

## Existing Infrastructure to Reuse

- `skybreak/get_flight_price.py::get_flight_price(from, to, date, flight_number)`
  - Cheapest economy price (EUR, 1 adult) for one **direct** flight via Google Flights.
  - In-memory cache per `(route, date)`: 1 h TTL, max 500 entries — several trips sharing
    a route+date cost one HTTP request.
  - Global rate-limit cooldown with exponential backoff (15 s → ~20 min); during a
    cooldown the call **blocks** until it can proceed.
  - Returns `None` when the flight is not in the result set; raises `RuntimeError` on
    HTTP errors / consent page.
- Turnaround result fields (`app.py::find_short_trips`): `hinflug_ziel`,
  `hinflug_flight_number`, `hinflug_abflug_zeit`, `rueckflug_start`,
  `rueckflug_flight_number`, `rueckflug_abflug_zeit`; start airport = the selected
  departure airport. Together they form a stable identity for a candidate trip.
- `flight_prices.fetch_prices_favorite` shows the exact price-combining rule to mirror:
  total is `None` if either available leg has no price.

## Design

### Database (one migration step)

```sql
CREATE TABLE IF NOT EXISTS trip_price_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_airport TEXT NOT NULL,
    destination_airport TEXT NOT NULL,
    outbound_date TEXT NOT NULL,
    return_date TEXT NOT NULL,
    outbound_flight_number TEXT NOT NULL,
    return_flight_number TEXT NOT NULL,
    price_outbound REAL,
    price_return REAL,
    price_total REAL,
    currency TEXT DEFAULT 'EUR',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(start_airport, destination_airport, outbound_date,
           return_date, outbound_flight_number, return_flight_number)
);
```

- `INSERT OR REPLACE` → re-quoting the same trip updates the row (no history table;
  this is a cache, not a monitoring series).
- Price columns nullable: a leg that Google does not list keeps `NULL`, total `NULL`.

### Backend

New module `skybreak/trip_quotes.py`:

```python
def quote_trip(start, dest, out_date, ret_date, out_fnum, ret_fnum,
               max_age_hours=1) -> dict:
    # 1. DB lookup by the unique key; fetched_at within max_age → return cached row
    #    (no Google call). This survives container restarts (the in-memory cache does not).
    # 2. Else fetch both legs, each in its own try/except so one failure doesn't kill
    #    the other:
    #       price_out = get_flight_price(start, dest, out_date, out_fnum)
    #       price_ret = get_flight_price(dest, start, ret_date, ret_fnum)
    # 3. total = sum if both present else None (same rule as fetch_prices_favorite).
    # 4. Upsert the row and return {price_outbound, price_return, price_total,
    #    currency: 'EUR', fetched_at, cached: bool}.
```

New route in `app.py` (naming follows `/api/prices/history|update|missing`):

- `POST /api/prices/quote`
  - Body: `{start_airport, destination_airport, outbound_date, return_date,
    outbound_flight_number, return_flight_number}`
  - Validates IATA codes + `YYYY-MM-DD` dates → 400 on bad input.
  - Calls `quote_trip` **synchronously** and returns the result dict (200).
  - `RuntimeError` from the scraper (HTTP failure / consent page) → 502 `{error}`.

Why synchronous for v1: Flask's threaded server handles concurrent clicks, and the
global cooldown in `get_flight_price` already serializes all Google access, so parallel
clicks queue naturally instead of hammering. Known trade-off: during a 429 cooldown the
request can take minutes. **Follow-up option** (only if this proves annoying): async job
+ polling endpoint, same pattern as `/api/flights/fetch-now` + `scrape-status`.

### Frontend (`frontend/src/components/TripsTab.js`)

- New "price" button per result row in **both** renderings (mobile cards and desktop
  table), next to the add-to-favorites action.
- Local state map keyed by trip identity
  (`start|dest|out_date|ret_date|out_fnum|ret_fnum`):
  `{status: 'idle' | 'loading' | 'done' | 'error', prices…, fetched_at}`.
- On click → `POST /api/prices/quote`; render in the row:
  `Out €145 · Ret €144 · 289 €` plus a relative age ("just now", "3 h ago");
  `NULL` leg → "–"; error state shows a short message and allows retry.
- Button disabled while that row is loading (prevents retry storms).
- No localStorage involvement — the DB cache already survives refreshes.

## Edge Cases & Risks

| Case | Behavior |
|---|---|
| Google doesn't list the exact flight number on that date | 200 with `NULL` price(s), UI shows "–" / "not listed" |
| Rate-limit cooldown active | Request blocks until cooldown ends; spinner shown; other rows queue behind it (global lock) |
| Our schedule data stale vs. Google's current listing | Quote can be `NULL` for a valid trip — same limitation favorites already have |
| User quotes many rows | Each unique `(route, date)` = one real search; hence user-initiated only + 1 h cache |
| Container restart | In-memory cache gone, DB cache still serves fresh (<1 h) quotes without Google calls |

## Out of Scope

- Automatic quoting of all search results (rate-limit suicide).
- Price history / charts for non-favorites.
- Pricing for connecting flights (separate feature: connection flights).
- Async job + polling pattern (documented follow-up, not v1).

## Test Plan (tests written first, per workflow)

`tests/test_trip_quotes.py`:
- Fresh quote calls `get_flight_price` twice and upserts the row
  (monkeypatch `skybreak.trip_quotes.get_flight_price`).
- Second call within the freshness window returns the cached row **without** any Google call.
- One leg `None` → total `None`; both present → sum.
- `get_flight_price` raising on one leg → other price still returned, exception not propagated.
- Endpoint: valid body → 200 with expected fields; invalid airport/date → 400;
  scraper `RuntimeError` → 502.

`tests/test_db_migration.py`: bump expected version (13 → new).

## Review Checklist

- [x] User story covered (story defined above; add to user-stories.md at implementation)
- [x] Architecture consistent — reuses `get_flight_price` cache/cooldown; all DDL via `db_migrate.py`; no runtime DDL
- [x] CI/Workflow compatible — pytest only, no new dependencies
- [ ] Documentation — update README feature list + `doc/architecture.md` routes at implementation time