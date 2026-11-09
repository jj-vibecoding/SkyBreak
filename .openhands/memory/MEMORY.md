# Project Memory - SkyBreak (vacation)
- Stack: React frontend, Flask backend, SQLite DB at /data/skybreak.db
- Docker: socket at /var/run/docker.sock (sudo needed); image skybreak-local
- Design docs: doc/designs/ and doc/plans/ deleted per user; architecture.md updated
- DB init: container handles (not Dockerfile); init_db creates schema + migrates
- Cleanup protocol: rm -rf test containers/volumes; keep production image

# DB Access Layer (2026-10-29)
- skybreak/db.py is the single DB entry point: db_path() (call-time DB_FILE read), connect_db(timeout=30.0), connection() ctx-mgr, get_setting/set_setting.
- All source modules (app, airport, scraper_job, flight_prices, get_flight_price, db_migrate) open via db.py — NO raw sqlite3.connect / module-level DB_FILE constant outside db.py.
- db_migrate.apply_migrations(path=None): path defaults to db_path(); pass explicit path to migrate a specific file without env mutation (used by migration tests).
- get_setting/set_setting live in db.py (the settings table's home), not airport.py.
- Schema fully owned by db_migrate migration_v1..v12 (version-tracked in db_version table); no runtime DDL in data path.
- Tests set DB_FILE via conftest BEFORE import (call-time read is required; import-time capture breaks the harness).
- Dead-import sweep: AST check of skybreak/*.py + tests/*.py should report 0 unused imports.

# Frontend Structure (2026-11-09)
- App.js is a thin shell: routing + responsive sidebar + shared airport list + scrape-status poll.
- Nav tabs: Favorites, Search Trips, Flights, Settings, Status (Airports removed — merged into Flights).
- Per-tab components (frontend/src/components/): FlightsTab (owns flightData + airport management: add/remove/refresh), TripsTab, SettingsTab, FavoriteTripPrices (owns ChartModal).
- AirportsTab.js exists as dead file; no longer imported anywhere. Airport management is in FlightsTab with add form, remove buttons, and per-airport refresh button.
- Hooks (frontend/src/hooks/): useActiveTab(NAV) = tab routing, useAirports() = shared list + airportNames.
- utils/format.js: formatTime + formatTripDateTime (deduped the repeated IIFEs).
- Dead code removed: FavoriteTrips() def, checkScrape helper, `import Layout` (Layout was imported but NEVER used — pre-existing dead import).
- ORPHAN: frontend/src/components/Layout.jsx is now fully unused (zero imports). Left in place awaiting user call to delete.
- Build gate: `npm run build` in frontend/ (node_modules present; frontend/build is gitignored, served by Flask /app/frontend/build).
- tests/test_app_integration.py enforces the new wiring (asserts tab imports in App.js, ChartModal in FavoriteTripPrices, NO `import Layout`).
- Frontend has NO test framework (no jest/RTL) — verification is `npm run build` + browser smoke test only.
- CI on main PRs: .github/workflows/ci.yml runs `npm ci && npm run build` + `python -m pytest tests/`.
- Refactor landed as commit 92db11c (branch feature/refactor-db-app-frontend), PR #74 to main; CI passed (2m27s).
# WICHTIG — NIE LIVE PATCHEN
- DB-/Container-Patche sind VERBOTEN.
- Jede Migration, jede Settings-Änderung, jede Schema-Fix muss im Quellcode (init_db.py, scraper_job.py, app.py) stehen und durch Image-Deploy + Container-Neustart wirken.
- Wenn fetch_max_months / DB-Setting fehlt: im Code ergänzen, nicht via sqlite3 im laufenden Container.
- Wenn API 404 / DB leer: Code prüfen (route, query, Migration), nicht Container-Daten händisch editieren.
- Nach jedem Code-Change: docker build + docker rm + docker run (neues Image, neuer Container).
- Agents.md / MEMORY.md muss diese Regel enthalten, damit nicht wiederholt wird.

- NIE LIVE PATCHEN (DB/Container-Edits verboten).
- Migrationen/Schema-Fixes NUR im Code (init_db.py/scraper_job.py/app.py), dann docker build + redeploy.
- fetch_max_months = 1 muss als DB-Setting (init_db/settings) + Env-Var gesetzt sein.
- API 404 (scrape-status): Route in app.py ergänzen, nicht Container editieren.
- Insert-Konflikte: INSERT statt INSERT OR IGNORE, wenn DB leer / keine Konflikte erwartet.

# GitHub Auth Token
GITHUB_PERSONAL_ACCESS_TOKEN set for GitHub API access (gh / curl).
Use GH_TOKEN=\$GITHUB_TOKEN for gh CLI operations.
Token masked in output; never commit raw value.

# Container Config (2026-09-25)
- Port: 8088 (mapped to container 80)
- Mount: /opt/skybreak (DB_FILE=/opt/skybreak/skybreak.db)
- Container name: flightbreak
- Image: skybreak-local

# Repo Cleanup (2026-11-02)
- GitHub user renamed Julian-VibeCoder -> jj-vibecoding; origin remote + README clone URL + docker-compose.yml.example GHCR ref updated, pushed to main. CI workflows use ${github.repository} dynamically so no hard refs.
- Cleanup commit on branch chore/repo-cleanup-2026-11 (pushed to origin): removed root memory.md (stale schema-v1 doc), untracked TST_direct.json + gitignored *_direct.json/flights.json, CI frontend build now hard-fails (removed || echo swallow), README Quick Start fixed to docker compose, removed dead tests/frontend/*.jsx stubs.
- Local state cleaned: 72 stale remote-tracking refs pruned (remote only ever had main), 12 local branches deleted (all content in main via squash merges), all 6 stashes dropped. Kept main + work branch only.

# Favorites Sort Fix (2026-11-02)
- PR #77 merged to main (d12d399): FavoriteTripPrices A→Z group sort uses dest_city_country (city name), not IATA code; fallback to IATA if no city data.
- Takes effect only after docker image rebuild + container restart (no live patching).

# GHCR Cleanup Fix (2026-11-02)
- Root cause of 404: GitHub container-package API is NAMESPACE-scoped (/users/{owner} or /orgs/{org}/packages/container/<pkg>), NOT repo-scoped (/repos/{o}/{r}/... returns 404). Package name must be lowercase (ghcr stores 'skybreak' for repo SkyBreak).
- Fix in .github/workflows/ghcr-cleanup.yml: detect owner type via /repos/{repo} owner.type, build API base accordingly, lowercase PKG. Pushed direct to main as 0e48fa2; verified via workflow_dispatch run (deleted 8 stale versions, kept 'main').

# Trip Search Configs (2026-11-02)
- Feature branch feature/trip-search-configs, commit 9cfa48b: named save/load/delete of trip search on Trips tab.
- Persisted in browser localStorage key `skybreak.tripSearchConfigs.v1` — NOT SQLite (user requirement). No backend/DB change.
- Saved fields exactly: startWeekdays, endWeekdays, maxDepToDest, minRetDep, minTripDays, maxTripDays. Airport + date range EXCLUDED by design (stays as-is on load).
- Files: frontend/src/utils/tripConfigs.js (pure helpers, storage injected), hooks/useTripConfigs.js, TripsTab "Saved Search Configs" block; tests/test_trip_search_configs.py runs the real module via Node ESM against in-memory localStorage.
- Names compare case-insensitively (upsert/delete); corrupt JSON tolerated (returns []). Deploy = npm build + image rebuild + container restart (no live patch).

# Trip Search Configs — Merged (2026-11-02)
- PR #78 squash-merged to main as fc72032; CI green (test job 2m44s, frontend build + pytest). Feature branch deleted.
- Takes effect in the running app only after docker image rebuild + container restart (no live patching).

# Trip Search Configs — DB Persistenz (2026-11-03)
- Branch feature/trip-search-configs-db, commit 0d03019 (lokal, noch kein PR/Push).
- localStorage -> SQLite: Tabelle trip_search_configs (Migration v13, name UNIQUE COLLATE NOCASE).
- Backend: skybreak/trip_configs.py (sanitize_config/list_configs/save_config/delete_config),
  Routen GET+POST /api/trip-configs, DELETE /api/trip-configs/<name> in app.py.
- save_config gibt None zurück (kein Exception) -> Route mappt auf 400. Upsert uebernimmt
  auch die Name-Schreibweise (name = excluded.name), damit UI-Load/Delete (exakter Name) passt.
- Frontend: utils/tripConfigs.js bleibt rein (kein fetch) - migrateLegacyConfigs(storage, post)
  ist dort, Fetch wird vom Hook injiziert -> Node-Tests testen die echte Uebernahme.
  writeTripConfigs entfernt (tot). Hook liefert jetzt loading/error und async save/remove.
- Uebernahme: alte localStorage-Eintraege werden einmalig POSTet, Key dann entfernt; bei
  Fetch-Fehler bleibt der Key (Retry).
- Tests: tests/test_trip_search_configs_db.py (neu, 27), test_trip_search_configs.py nutzt
  seed()-Helper statt writeTripConfigs, test_db_migration.py Version 12 -> 13.
- Node-Tests in pytest: Top-Level-await erlaubt, Top-Level-return NICHT.
- 85 passed, 2 skipped (docker daemon / playwright server - vorbestehend). npm build gruen.
- PR #79 SQUASH-MERGED to main as 7dfca1a (async merge API, sha-pinned). CI green: frontend "Compiled
  successfully", pytest 86 passed / 1 skipped (CI hat Docker-Daemon, nur Playwright-Skip).
  Feature branch geloescht (remote + lokal); main lokal = origin/main; 85 passed/2 skipped lokal.
- gh CLI braucht hier explizit GH_TOKEN=... vor dem Befehl (GITHUB_TOKEN reicht nicht automatisch).

# Responsive Frontend Fix (2026-11-05)
- Symptom "nur dunkelblauer Hintergrund am iPhone" = veraltetes Bundle im Container, NICHT ein Disk-Bug: `useEffect`-Import war auf Disk schon gefixt. Root Cause immer erst per neuem Build + Container-Recreate verifizieren.
- useConfirm/ToastProvider (Dialogs.js): Jede Komponente, die showConfirm() nutzt, MUSS ihr eigenes <ConfirmDialog/> im Root rendern — sonst löst das Promise nie auf (UI friert). ToastProvider hört auf window CustomEvent "showToast".
- ChartModal: SVG viewBox muss responsive sein (getChartWidth = min(innerWidth-48,720)); Punkte/Tooltip-Clamp/Legende skalieren damit; Legende < 480px unter den Chart.
- Container skybreak-skybreak-1 wurde mit plain `docker run` gestartet (kein Compose-Label). Identische Config: -p 8088:80 -v /opt/skybreak/:/data/ -e DB_FILE=/data/skybreak.db, image skybreak-local, cmd python -m skybreak.app.
