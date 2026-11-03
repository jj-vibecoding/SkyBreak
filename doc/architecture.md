# SkyBreak - Architecture Overview

## High-Level Design

### Core Components

1. **Web Frontend** (React)
   - Single-page application built with React and `react-scripts`
   - Dashboard with tabs: Airports, Flights, Trips, Costs, Settings
   - Airport code entry with IATA validation
   - Flight schedule browsing with date filtering
   - API key configuration for flight data access

2. **Backend Service** (Python/Flask)
   - REST API built with Flask serving static frontend build and JSON endpoints
   - Routes: `/api/airports`, `/api/flights`, `/api/flights/future`, `/api/settings`, `/api/trip-configs`
   - Local SQLite database for airports, flights, and settings
   - Integration with RapidAPI aerodatabox for flight data

3. **Scheduled Scraper** (Background Job)
   - `apscheduler`-based background scheduler running periodic scrapes
   - Fetches 6-hour windows continuously until 365-day range covered
   - Rate-limit backoff: starts at 30 min, doubles on each 429
   - Cleans old flights (`departure_time < now`) on each interval

4. **Database** (SQLite)
   - Tables: `airports`, `flights`, `settings`, `trip_search_configs`
   - `airports`: code, name, created_at
   - `flights`: airport_icao, airport_name, destination_icao, destination_name, flight_direction, departure_time, flight_number, year_ahead
   - `settings`: key-value store for API key, fetch intervals, max days
   - `trip_search_configs`: named trip search settings (six search fields, unique
     case-insensitive name) shared by all browsers via `/api/trip-configs`
   - **Access layer** — `skybreak/db.py`: every module opens the DB through
     `connect_db()` / the `connection()` context manager. The path is read from
     `DB_FILE` at call time so the test harness can point it at a temp file.
     `get_setting`/`set_setting` also live here (the `settings` table's home).
   - **Schema** — `skybreak/db_migrate.py` owns the full schema and applies
     versioned migrations (`db_version`) at startup, including fresh-DB creation
     and upgrades of older files. No module performs runtime DDL.

5. **Containerization** (Docker + docker-compose)
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
7. `apscheduler` runs `scrape_all_airports()` on configured interval (default 30 min)
8. Old flights (departure_time < now) are deleted by `clean_old_flights()`
9. Settings page POSTs to `/api/settings` to store API key and fetch parameters

## Technology Stack

- **Frontend:** React 18, `react-scripts` 5.0.1
- **Backend:** Python 3.11, Flask, sqlite3
- **Database:** SQLite (lightweight, local)
- **Containerization:** Docker multi-stage build, docker-compose
- **Scraping:** RapidAPI aerodatabox (`requests` library)
- **Scheduler:** `apscheduler` (BackgroundScheduler)
- **HTTP Client:** `requests` for RapidAPI calls
- **Caching:** In-memory `_airport_cache` dict for airport name lookups

## Key Requirements Mapping

| Requirement | Component |
|---|---|
| No paid APIs | RapidAPI aerodatabox (freemium) + local SQLite caching |
| Web frontend | React + `react-scripts` build |
| Docker/hosted | Multi-stage Dockerfile + docker-compose |
| International airport codes | `validate_iata()` (3-char IATA regex) + `fetch_airport_name()` |
| Load departures/arrivals | RapidAPI fetch + local DB storage |
| Calculate turn-arounds | Backend logic in scraper windows |
| Configurable days off | Settings via `/api/settings` |
| Select monitored trips | Future feature (trips tab placeholder) |
| Price checking every 24h | `apscheduler` cron interval |
| Price history | Stored in `flights` table (future feature) |
| Remove monitoring | Future feature |
| Remove airport | `DELETE /api/airports/<code>` + cleanup |

## Implementation Order (Incremental)

1. **Architecture Setup** - Dockerfile + docker-compose
2. **Airport Management** - CRUD for airports (`/api/airports` GET/POST/DELETE)
3. **Flight Scraper Integration** - RapidAPI fetch + `save_flights()`
4. **Turnaround Calculation** - Flight window logic
5. **Monitoring System** - `apscheduler` + `scrape_all_airports()`
6. **Price Tracking** - Daily price checks
7. **Visualization** - Price history charts (future)
8. **Configuration** - Settings API (`/api/settings`)
9. **Frontend** - React dashboard (airports, flights, settings tabs)

Each component can be developed and tested independently.