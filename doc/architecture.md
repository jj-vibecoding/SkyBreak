# SkyBreak - Architecture Overview

## High-Level Design

### Core Components

1. **Web Frontend** (React)
   - Single-page application built with React and `react-scripts`
   - Dashboard with tabs: Trips, Favorites, Airports, Flights, Settings
   - Airport code entry with IATA validation
   - Flight schedule browsing with date filtering
   - Turnaround search with configurable parameters (weekdays, times, duration)
   - Favorite trips management with price history chart modal
   - API key configuration for flight data access
   - Responsive layout (desktop sidebar / mobile drawer)

2. **Backend Service** (Python/Flask)
   - REST API built with Flask serving static frontend build and JSON endpoints
   - Routes:
     - `/api/airports` — CRUD for airports (GET/POST/DELETE)
     - `/api/flights` — Flight schedule queries with filters (airport, date)
     - `/api/flights/future` — Per-airport max departure info
     - `/api/flights/fetch-now` — Trigger immediate flight data fetch
     - `/api/flights/scrape-status` — Scraper status polling
     - `/api/prices/history` — Price history for a favorite trip
     - `/api/prices/update` — Trigger price update for favorites
     - `/api/prices/missing` — Fetch prices for favorites with missing data
     - `/api/settings` — Settings CRUD (key-value store)
     - `/api/trip-configs` — Trip search configuration CRUD
     - `/api/turnarounds` — Turnaround calculation endpoint
   - Local SQLite database for airports, flights, settings, favorites, prices, and trip configs
   - Integration with RapidAPI aerodatabox for flight schedule data

3. **Scheduled Scraper** (Background Job)
   - `apscheduler`-based background scheduler running periodic scrapes
   - Fetches 6-hour windows continuously until configured range covered
   - Rate-limit backoff: starts at configured delay, doubles on each 429
   - Cleans old flights (`departure_time < now`) on each interval

4. **Price Scheduler** (Background Job)
   - `apscheduler`-based scheduler running periodic price checks for favorite trips
   - Fetches prices via Google Flights scraper (kayak_direct)
   - Stores price history in `favorite_trip_prices` table
   - Configurable interval (default 6 hours)

5. **Database** (SQLite)
   - Tables: `airports`, `flights`, `settings`, `favorite_trips`, `favorite_trip_prices`, `trip_search_configs`, `db_version`
   - `airports`: code, name, created_at
   - `flights`: airport_icao, airport_name, destination_icao, destination_name, flight_direction, departure_time, arrival_time, duration_minutes, flight_number, from_icao, to_icao, month_key, flight_date, arrival_date, departure, arrival, created_at
   - `settings`: key-value store for API key, fetch intervals, max days, price interval, etc.
   - `favorite_trips`: destination_airport, outbound_flight_number, return_flight_number, start_airport, outbound_trip_date, return_trip_date
   - `favorite_trip_prices`: favorite_id (FK), price_outbound, price_return, price_total, currency, fetched_at
   - `trip_search_configs`: id, name (UNIQUE COLLATE NOCASE), start_weekdays, end_weekdays, max_dep_to_dest, min_ret_dep, min_trip_days, max_trip_days, created_at, updated_at
   - **Access layer** — `skybreak/db.py`: every module opens the DB through
     `connect_db()` / the `connection()` context manager. The path is read from
     `DB_FILE` at call time so the test harness can point it at a temp file.
     `get_setting`/`set_setting` also live here (the `settings` table's home).
   - **Schema** — `skybreak/db_migrate.py` owns the full schema and applies
     versioned migrations (`db_version`) at startup, including fresh-DB creation
     and upgrades of older files. No module performs runtime DDL.

6. **Containerization** (Docker + docker-compose)
   - Multi-stage Dockerfile: builder (Python + Node) → final (Python runtime)
   - Frontend built with `npm ci && npm run build` during build
   - Single container serving both API and static frontend on port 80
   - DB persisted via mounted volume

## Data Flow

1. User enters airport code in the React UI
2. Frontend POSTs to `/api/airports`; Flask validates IATA and stores in SQLite
3. `add_airport()` triggers `trigger_fetch_for_airport()` which calls `fetch_flights()` in 6-hour windows
4. Fetched flights are saved to SQLite via `save_flights()` (deduplication applied)
5. Frontend GETs `/api/flights` with optional `airport` and `date` query params
6. `/api/flights/future` returns per-airport max departure time and days-ahead
7. User searches turnarounds on Trips tab → POST to `/api/turnarounds` with search params
8. Turnaround algorithm queries flights via SQL filtering + in-memory hash join
9. User adds a turnaround as favorite → stored in `favorite_trips` table
10. `apscheduler` runs flight scraper and price scheduler on configured intervals
11. Favorites tab shows saved trips with prices; clicking chart opens SVG price history modal
12. Settings page POSTs to `/api/settings` to store API key and fetch parameters
13. User saves trip search configs → POST/GET/DELETE to `/api/trip-configs`

## Technology Stack

- **Frontend:** React 18, `react-scripts` 5.0.1
- **Backend:** Python 3.13, Flask, sqlite3
- **Database:** SQLite (lightweight, local)
- **Containerization:** Docker multi-stage build, docker-compose
- **Flight Data API:** RapidAPI aerodatabox (`requests` library)
- **Price Scraper:** Google Flights via kayak_direct (`playwright`)
- **Scheduler:** `apscheduler` (BackgroundScheduler)
- **HTTP Client:** `requests` for API calls
- **Caching:** In-memory `_airport_lookup_cache` and `_city_lookup_cache` dicts

## Key Requirements Mapping

| Requirement | Component |
|---|---|
| No paid APIs | RapidAPI aerodatabox (freemium) + local SQLite caching |
| Web frontend | React + `react-scripts` build |
| Docker/hosted | Multi-stage Dockerfile + docker-compose |
| International airport codes | `validate_iata()` (3-char IATA regex) + `fetch_airport_name()` |
| Load departures/arrivals | RapidAPI fetch + local DB storage |
| Calculate turn-arounds | SQL filtering + in-memory hash join (`/api/turnarounds`) |
| Configurable days off | Weekday selection on Trips tab (start/end weekdays) |
| Favorites / monitored trips | `favorite_trips` table + `/api/favorites` routes |
| Price checking | `apscheduler` price scheduler (configurable interval) |
| Price history chart | SVG ChartModal with date-based X-axis (`/api/prices/history`) |
| Remove monitoring | DELETE favorite route + cascade delete prices |
| Remove airport | `DELETE /api/airports/<code>` + cleanup |
| Trip search configs | `trip_search_configs` table + `/api/trip-configs` routes |
| Local UI persistence | Browser localStorage via `useLocalStorage` hook |