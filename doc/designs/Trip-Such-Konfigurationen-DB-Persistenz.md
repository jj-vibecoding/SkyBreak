# Design — Trip Such-Konfigurationen: Persistenz in der SQLite-DB

## Anforderung
Die auf der Trips-Seite gespeicherten Such-Konfigurationen lagen bisher im
`localStorage` des Browsers. Damit sehen **alle Browser bzw. Geräte dieselben
Konfigurationen**, werden sie künftig in der SQLite-Datenbank persistiert.

Gespeichert werden weiterhin exakt die sechs konfigurierbaren Suchfelder:

- Start-Wochentage (`startWeekdays`)
- End-Wochentage (`endWeekdays`)
- Späteste Abflugzeit ins Ziel (`maxDepToDest`)
- Früheste Rückflug-Abflugzeit (`minRetDep`)
- Kürzeste Trip-Dauer in Tagen (`minTripDays`)
- Längste Trip-Dauer in Tagen (`maxTripDays`)

**Nicht** gespeichert (bewusst ausgeschlossen, bleibt beim Laden unverändert):

- Start-/End-Flughafen (`startAirport`/`endAirport`)
- Frühestes Startdatum (`tripStart`)
- Spätestes Endedatum (`tripEnd`)

## Bezug zu User Stories / Architektur
- **Story 15** (Save Trip Search Configurations): Persistenz-Änderung von
  "browser local storage" auf "serverseitige DB, geräteübergreifend sichtbar".
- **Architektur**: React-Frontend → Flask-REST-API → SQLite. Die Konfigurationen
  folgen dem bestehenden Muster: Schema in `skybreak/db_migrate.py`
  (versionierte Migration), Datenzugriff über `skybreak/db.py`
  (`connect_db()` / `connection()`), Routen in `skybreak/app.py`.
- **Keine Live-Patches**: Schema-Change ausschließlich als Migration im Quellcode,
  wirksam durch `docker build` + Container-Neustart.

## Design-Entscheidungen

### 1. Schema (Migration v13)
Neue Tabelle `trip_search_configs`:

| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | technischer Schlüssel |
| `name` | TEXT NOT NULL UNIQUE (NOCASE) | Konfigurationsname, case-insensitive eindeutig |
| `start_weekdays` | TEXT NOT NULL DEFAULT '' | kommagetrennt, z. B. `4,6` |
| `end_weekdays` | TEXT NOT NULL DEFAULT '' | kommagetrennt |
| `max_dep_to_dest` | TEXT NOT NULL DEFAULT '' | `HH:MM` |
| `min_ret_dep` | TEXT NOT NULL DEFAULT '' | `HH:MM` |
| `min_trip_days` | INTEGER | 1–30 |
| `max_trip_days` | INTEGER | 1–30 |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | bei Upsert aktualisiert |

Warum normalisierte Spalten statt eines JSON-Blobs: die Felder sind stabil,
validierbar und direkt in SQL filterbar; ein JSON-Blob würde Validierung und
Debugging unnötig erschweren. `UNIQUE ... COLLATE NOCASE` setzt die bestehende
Regel "Duplikate sind case-insensitive" direkt in der DB durch.

### 2. Backend
Neues Modul `skybreak/trip_configs.py` als einzige Heimat der Logik:

- `sanitize_config(raw)` — Normalisierung/Validierung (Wochentage 0–6,
  `HH:MM`-Zeiten, ganzzahlige Tage 1–30, Name Pflicht).
- `list_configs()` — alle Konfigurationen, sortiert nach Name (A→Z).
- `save_config(config)` — Upsert case-insensitive über den Namen;
  `ON CONFLICT(name) DO UPDATE` + `updated_at = CURRENT_TIMESTAMP`.
- `delete_config(name)` — löscht case-insensitive, gibt `deleted` zurück.

Routen in `skybreak/app.py`:

| Methode | Pfad | Verhalten |
|---|---|---|
| GET | `/api/trip-configs` | Liste aller Konfigurationen |
| POST | `/api/trip-configs` | Upsert; 400 wenn Name fehlt/ungültig |
| DELETE | `/api/trip-configs/<name>` | Löschen; 404 wenn nicht vorhanden |

Response-Format identisch zum bisherigen Frontend-Format
(`name`, `startWeekdays`, `endWeekdays`, `maxDepToDest`, `minRetDep`,
`minTripDays`, `maxTripDays`) — DB-Spalten werden beim Lesen gemappt, damit
das Frontend keine DB-Interna kennen muss.

### 3. Frontend
- `frontend/src/utils/tripConfigs.js` bleibt die **rein validierende,
  framework-freie** Schicht (keine Storage-/Fetch-Zugriffe): `CONFIG_FIELDS`,
  `sanitizeConfig`, `upsertTripConfig`, `deleteTripConfig`. Dadurch bleiben die
  Node-Verhaltenstests erhalten.
- `frontend/src/hooks/useTripConfigs.js` ersetzt localStorage durch die API:
  - `GET /api/trip-configs` beim Mounten
  - `saveConfig()` → `POST`, `removeConfig()` → `DELETE`
  - Status-/Fehlermeldung, damit ein fehlgeschlagener Schreibvorgang nicht
    stillschweigend verloren geht.
- **Einmalige Übernahme bestehender Browser-Konfigurationen:** beim ersten Laden
  werden Inhalte des alten localStorage-Keys `skybreak.tripSearchConfigs.v1`
  POSTet und der Key anschließend entfernt. Bestehende Konfigurationen gehen
  dadurch nicht verloren, ohne dass ein Backend-Skript nötig ist.

### 4. Konsistenz / Race-Bedingungen
Mehrere Browser schreiben dieselbe Tabelle. Upsert ist idempotent
(last-write-wins), Löschen ist idempotent. Für dieses Tool ist kein
Per-User-Ownership nötig — die Konfigurationen sind explizit global geteilt.

## Design-Review-Checkliste
- [x] User Stories abgedeckt? — Story 15 angepasst; Story 3 (Turnaround-Suche)
      bleibt unverändert, Presets funktionieren wie bisher.
- [x] Architektur konsistent? — Schema nur in `db_migrate.py`, Zugriff nur über
      `db.py`, Routen in `app.py`; keine Runtime-DDL.
- [x] CI/Workflow kompatibel? — CI führt `npm ci && npm run build` + `pytest tests/`
      aus; neue Tests nutzen den bestehenden pytest-Harness (`conftest` setzt
      `DB_FILE` vor dem Import).
- [x] Dokumentation aktualisiert? — dieses Design, Plan, Story 15 in
      `doc/user-stories.md`.

## Risiken / Open Points
- Konfigurationen sind mandantenübergreifend sichtbar (gewünscht: "alle Browser
  sehen dieselben Einstellungen"). Eine Benutzerauthentifizierung existiert
  nicht und ist nicht Teil dieser Anforderung.
- Der localStorage-Key wird nach der Übernahme gelöscht; wer den Browser-Cache
  bereits geleert hat, hat ohnehin keine lokalen Konfigurationen.

## Review-Log
- **Review 1 (gegen `doc/user-stories.md` Story 15 + `doc/architecture.md`):**
  konsistent. Aktuelle Schema-Version ist v12 → neue Migration wird v13.
  Schema-Zuständigkeit liegt ausschließlich bei `db_migrate.py` (Regel aus
  `AGENTS.md`: keine Runtime-DDL, keine Live-Patches). Story 15 muss in den
  Akzeptanzkriterien von "localStorage" auf "serverseitige DB" umgestellt werden.
  CI (`npm ci && npm run build` + `pytest tests/`) bleibt unverändert kompatibel.
  Ergebnis: keine Design-Änderung nötig, Umsetzung freigegeben.
