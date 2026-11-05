# Design: Health Dashboard + JSON Backup/Export

**Status:** Designed, not implemented
**Date:** 2026-11-05
**Migration number:** none — this feature adds no schema changes (v14/v15 stay free for the other two designs)
**Related:** scraper (`scraper_job`), price scheduler, single-container deployment

## Problem

The whole app lives in one container with one SQLite file on a mounted volume. There is
no way to answer basic operational questions without digging into logs or the DB:

- When did the last flight-schedule scrape run, and did it work?
- How fresh is the data per airport (last departure covered)?
- Is the Google Flights price scraper actually working, or silently failing every cycle?
- Can I back up my data before a container rebuild / image update?

Two findings from code review shape this design:

1. **Flight-schedule scraping is manual-only.** `scrape_all_airports()` is only invoked
   by `POST /api/flights/fetch-now`; the only periodic APScheduler job is the price
   scheduler. The architecture doc's claim of a "scheduled scraper" is stale. The health
   dashboard makes this visible (no last-run timestamp exists today), and an optional
   part 3 adds the missing periodic schedule to match the documented design.
2. **`clean_old_flights()` is dead code** — defined in `scraper_job.py`, never called.

## User Story (add to `doc/user-stories.md` at implementation time)

**As a user**, I want one page showing the health of my data pipelines (scrape freshness
per airport, last price-update results, scraper status) and a one-click backup export,
**so that** I can spot stale or broken data early and protect my database before
rebuilds.

Acceptance criteria:
- A "Status" area (tab or section) shows: per-airport flight count + max covered date;
  last scrape run (time, duration, success/failure); price scheduler state (last run,
  success/fail counts, next expected run).
- The app shows a warning when an airport's data is older than the configured fetch window.
- One-click export downloads a JSON backup of all user data; it can be re-imported into
  a fresh database.
- No secrets in any response or export file.

## Design

### Part 1 — Run-log tables (small migration step)

We need to *record* runs before we can *display* them:

```sql
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running','ok','failed')),
    airports INTEGER,           -- number of airports processed
    flights_saved INTEGER       -- total rows upserted this run
);

CREATE TABLE IF NOT EXISTS price_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running','ok','failed')),
    total INTEGER, success INTEGER, failed INTEGER   -- per-favorite counters
);
```

Wiring (both schedulers already have the data; this is bookkeeping):
- `scrape_all_airports()` (`scraper_job.py`): insert a `running` row at start, update it
  with counts/status before returning or on exception. The manual `fetch-now` endpoint
  and the periodic job (part 3) go through the same function → both are logged for free.
- `scrape_favorite_prices()`: same pattern; it already computes success/fail counts.

### Part 2 — Health endpoint + UI

New route in `app.py`:

```
GET /api/health  →
{
  "db_version": 15,
  "airports": [
    {"code": "FRA", "name": "Frankfurt", "flights": 4123,
     "max_departure": "2026-12-19 18:40:00", "stale": false}
  ],
  "scrape": {"last_run": {...latest scrape_runs row...}, "running": bool},
  "prices": {"last_run": {...latest price_runs row...}, "running": bool,
             "interval_hours": 6, "next_run_eta": "..."},
  "favorites_total": 7, "quotes_cached": 12   // optional context numbers
}
```

- `stale` is computed against the configured `fetch_max_months` window: an airport whose
  max covered departure is earlier than `today + fetch_max_months*30d − grace(7d)` is
  stale (data should reach that far).
- Reuses existing building blocks: `/api/flights/future` already computes per-airport max
  departure — extract that query into a shared helper instead of duplicating it.

Frontend — new **Status tab** (`frontend/src/components/StatusTab.js`, added to the
tab list in `App.js`):
- Airports table: code, name, flight count, max covered date, stale badge (amber).
- Pipeline cards: last scrape (time ago, status icon, flights saved) + "Fetch now"
  button reusing `/api/flights/fetch-now`; last price run (success/failed counts) +
  interval + running indicator.
- Refresh on tab open + manual refresh button; no polling in v1.

### Part 3 — Backup export/import

Single-file SQLite → a JSON snapshot is the natural backup unit.

```
GET /api/backup/export → application/json file download (Content-Disposition)
{
  "version": 1,
  "exported_at": "2026-11-05T…",
  "db_version": 15,
  "airports": [...], "favorite_trips": [...], "trip_search_configs": [...],
  "settings": {...}          // EXCLUDING telegram_bot_token (see below)
}
```

Deliberately excluded:
- `flights` — regeneratable by re-scraping; including it makes exports enormous.
- `favorite_trip_prices` — optional second toggle later if wanted (price history is the
  one thing that can't be regenerated). v1 ships without it to keep files small; document
  in README.
- **Secrets:** `telegram_bot_token` (and any future credential key) must not appear in
  the export. Implementation: explicit denylist of secret keys at export time, asserted
  by a test.

```
POST /api/backup/import   body = exported JSON
```
- Validates `version` and required tables; imports inside one transaction (rollback on
  error) using per-table upserts keyed on the natural unique constraints
  (airport code, trip-config name, favorite unique index).
- Import into a fresh DB = restore after container rebuild; import over an existing DB =
  merge (documented behavior).
- Frontend: "Export" button (file download via blob) + "Import" file input with
  confirmation dialog, in the Status tab.

### Part 4 (optional, separate PR) — periodic flight schedule scrape

Closes the gap found in review and matches the documented architecture:
- New setting `scrape_interval_hours` (whitelist entry; default e.g. 24, 0 = disabled).
- APScheduler job in `start_price_scheduler()`'s neighborhood calling
  `scrape_all_airports()` (reuse its scheduler or a second one — implementation detail).
- The run-log table from part 1 makes the new schedule immediately visible in the Status tab.

This is optional because it changes scraper load on the Kayak endpoint; decide at
implementation time whether to include it in this feature or split it off.

## Edge Cases & Risks

| Case | Behavior |
|---|---|
| Fresh DB, no runs yet | Health endpoint returns `last_run: null`; UI shows "never run" |
| Run still in progress | `running` row present → status card shows spinner; next-run ETA suppressed |
| Export while writing | SQLite single-connection writes are short; export opens its own read connection — worst case a mid-write airport list, acceptable for a manual backup. Document: take the backup when no fetch is running for strict consistency |
| Import version mismatch (future schema) | Rejected with 400 + message; never partial-imports |
| Secret leakage via export | Denylist + dedicated test asserting the token key is absent from a populated export |

## Out of Scope

- Automatic scheduled backups to disk/S3.
- Per-row diffs/conflict resolution on import (upsert-by-key is enough for v1).
- Health checks of external endpoints (Kayak/Google reachability) beyond what run logs show.
- Alerting when data goes stale (could reuse the notifications design later).

## Test Plan (tests written first, per workflow)

`tests/test_health_dashboard.py`:
- `scrape_all_airports()` writes a scrape_runs row with ok status + counts (monkeypatched kayak fetch).
- Failing run → status `failed`, finished_at set.
- `GET /api/health` shape: airports array with max_departure, stale flag true/false against the window, last-run objects, db_version.
- `/api/flights/future` and health share the same per-airport query result (no duplication drift).

`tests/test_backup_export.py`:
- Export contains all user tables; `flights` absent; `telegram_bot_token` **absent** even when set.
- Import into fresh DB restores airports + favorites + configs; second import is idempotent (upsert, no duplicates).
- Import of unknown `version` → 400, nothing written.
- Import with a corrupted payload (missing table) → 400, transaction rolled back.

`tests/test_db_migration.py`: bump expected version for the run-log tables.

## Review Checklist

- [x] User story covered (story defined above; add to user-stories.md at implementation)
- [x] Architecture consistent — all DDL via `db_migrate.py`; run logging hooks into existing scraper functions; no new dependencies
- [x] CI/Workflow compatible — pytest only
- [ ] Documentation — README + `doc/architecture.md`: fix the stale "scheduled scraper" claim, add Status tab, routes, tables at implementation time