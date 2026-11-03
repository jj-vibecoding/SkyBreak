# Implementierungsplan — Trip Such-Konfigurationen in der DB

Umsetzung des Designs `doc/designs/Trip-Such-Konfigurationen-DB-Persistenz.md`.
Reihenfolge: **Tests zuerst**, dann Code.

## 1. Tests zuerst (`tests/`)
- `tests/test_trip_search_configs_db.py` (neu):
  - Migration: frische DB erreicht Version 13, Tabelle `trip_search_configs`
    existiert mit den erwarteten Spalten, Name ist case-insensitive eindeutig.
  - `skybreak/trip_configs.py`: `sanitize_config`, `list_configs`,
    `save_config` (Upsert), `delete_config` direkt gegen die DB.
  - API über `app.test_client()`:
    - `GET /api/trip-configs` → `[]` auf leerer DB
    - `POST` → 200/201, danach in der Liste
    - `POST` gleicher Name in anderer Schreibweise → ersetzt, keine Duplikate
    - `POST` ohne Name / mit ungültigen Werten → 400
    - `DELETE /api/trip-configs/<name>` → 200, danach weg; unbekannter Name → 404
- `tests/test_trip_search_configs.py` (anpassen):
  - `test_hook_persists_via_localstorage` → `test_hook_persists_via_api`
    (Hook nutzt `/api/trip-configs`, kein `localStorage` mehr als Speicher).
  - Reine Helper-Tests bleiben (Validierung ist weiterhin Node-getestet).
- `tests/test_db_migration.py`: Versions-Assertions 12 → 13.

## 2. Schema (`skybreak/db_migrate.py`)
- `migration_v13`: `CREATE TABLE IF NOT EXISTS trip_search_configs` (Spalten wie
  im Design), `name` mit `UNIQUE COLLATE NOCASE`; in `MIGRATIONS`-Liste ergänzen.

## 3. Backend
- `skybreak/trip_configs.py` (neu): `sanitize_config`, `list_configs`,
  `save_config`, `delete_config`; Zugriff nur über `skybreak/db.py`.
- `skybreak/app.py`: drei Routen (`GET`/`POST` `/api/trip-configs`,
  `DELETE /api/trip-configs/<name>`), Response-Felder im Frontend-Format.

## 4. Frontend
- `frontend/src/utils/tripConfigs.js`: bleibt rein validierend;
  `readTripConfigs`/`writeTripConfigs` nur noch für die einmalige Übernahme.
- `frontend/src/hooks/useTripConfigs.js`: lädt per `GET`, speichert per `POST`,
  löscht per `DELETE`; übernimmt einmalig alte localStorage-Einträge und
  entfernt den alten Key; zeigt Status/Fehler an.
- `frontend/src/components/TripsTab.js`: Ladezustand/Fehler der Konfigurationen
  anzeigen, Speichern/Löschen laufen über die API (asynchron).

## 5. Doku
- `doc/user-stories.md` Story 15: Persistenz = SQLite-DB, geräteübergreifend.
- `doc/architecture.md`: Routenliste um `/api/trip-configs` ergänzen.

## 6. Verifikation
- `python -m pytest tests/`
- `npm run build` in `frontend/`
- Deployment nur über `docker build` + Container-Neubau (Migration läuft beim Start).

## Review-Log
- **Plan-Review 1 (gegen Design, User Stories, Architektur, CI):**
  Reihenfolge Tests→Code eingehalten; keine neuen Abhängigkeiten (nur Flask/
  SQLite/React, bereits vorhanden); Migration ersetzt kein bestehendes Schema;
  CI-Stufen unverändert; Doku-Schritte enthalten. Keine Abhängigkeiten fehlen.
  Ergebnis: Plan freigegeben.
