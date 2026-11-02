# Design — Trip Such-Konfigurationen (speichern / laden / löschen)

## Anforderung
Auf der Trip-Seite soll die aktuelle Suche als benannte Konfiguration gespeichert und
wieder geladen werden können. Gespeichert werden:

- Start-Wochentage (`startWeekdays`)
- End-Wochentage (`endWeekdays`)
- Späteste Abflugzeit ins Ziel (`maxDepToDest`)
- Früheste Rückflug-Abflugzeit (`minRetDep`)
- Kürzeste Trip-Dauer in Tagen (`minTripDays`)
- Längste Trip-Dauer in Tagen (`maxTripDays`)

**Nicht** speicherbar (bleiben bei Laden unverändert):

- Start-/End-Flughafen (`startAirport`/`endAirport`)
- Frühestes Startdatum (`tripStart`)
- Spätestes Endedatum (`tripEnd`)

Jede Konfiguration hat einen Namen. Gespeicherte Konfigurationen können gelöscht
werden. Persistenz: **Local Storage des Browsers** (pro Benutzer/Browser) — ausdrücklich
nicht in der SQLite-DB, d.h. kein Backend-/Schema-Change und keine Migration nötig.

## Bezug zu User Stories / Architektur
- Story 3 (Calculate Turn-arounds): die Trip-Seite ist der Suchbildschirm für Turnarounds;
  Konfigurationen sind wiederverwendbare Presets dieser Suche.
- Architektur: React-Frontend (CRA), Flask-Backend, SQLite. Feature liegt vollständig im
  Frontend (`frontend/src/`); Backend und DB bleiben unangetastet.
- Keine Live-Patches: nur Quellcode + `npm run build` + Image-Deploy + Container-Neustart.

## Design-Entscheidungen
1. **Speicherort:** `localStorage`, Key `skybreak.tripSearchConfigs.v1`.
   Format: JSON-Array von Objekten
   `{ name, startWeekdays[], endWeekdays[], maxDepToDest, minRetDep, minTripDays, maxTripDays }`.
2. **Modulstruktur** (konsequent nach bestehendem Muster `utils/` + `hooks/`):
   - `frontend/src/utils/tripConfigs.js` — reine, framework-freie Funktionen:
     `readTripConfigs(storage)`, `writeTripConfigs(configs, storage)`,
     `upsertTripConfig(configs, config)`, `deleteTripConfig(configs, name)`.
     `storage` wird injiziert (Default `window.localStorage`) → unit-testbar.
   - `frontend/src/hooks/useTripConfigs.js` — React-State + Persistenz-Wrapper.
3. **Namensregeln:** Name ist Pflicht (leer/whitespace → Fehlermeldung). Duplikate
   werden case-insensitive behandelt; Überschreiben erfordert Bestätigung (`confirm()`),
   konsistent mit dem bestehenden `addAllFavorites`.
4. **Validierung beim Speichern:** Start- und End-Wochentage müssen nicht leer sein,
   sonst ist die Konfiguration wertlos → Inline-Fehlermeldung statt speichern.
5. **Laden:** setzt nur die 6 gespeicherten Felder; Flughafen/Daten bleiben aktiv.
   Der bestehende Fetch-`useEffect` in `TripsTab` feuert automatisch neu → neue Suche.
6. **Defensive Dekodierung:** korruptes JSON, nicht-Array-Payloads, falsche Typen oder
   Wochentag-Werte außerhalb 0–6 werden beim Lesen/Laden verworfen bzw. gefiltert —
   der Tab darf nie durch kaputten Local Storage crashen.
7. **UI:** eigener Block "Saved Search Configs" unter dem Suchformular in `TripsTab`:
   - Zeile 1: Name-Input + Button "Save current search"
   - Zeile 2: Select mit gespeicherten Namen + Buttons "Load" / "Delete" (Löschen mit `confirm()`)
   - Kurze Status-/Fehlermeldung unter dem Block.
8. **Tests:** Python-Tests (`tests/test_trip_search_configs.py`) nach bestehendem Muster:
   - Verhaltens-Tests der reinen Storage-Funktionen via Node/ESM (Roundtrip, case-insensitive
     Upsert, Delete, Korrupt-Daten-Toleranz) — keine Mocks, echte Modul-Logik.
   - Verdrahtungs-Tests (TripsTab importiert das Modul; exakt die 6 Felder in `CONFIG_FIELDS`;
     Flughafen/Datum-Felder explizit NICHT dabei; kein Backend/SQLite-Zugriff im Modul).

## Design-Review-Checkliste
- [x] User Stories abgedeckt? — Story 3 (Turnaround-Suche) direkt erweitert, keine Konflikte.
- [x] Architektur konsistent? — reines Frontend-Feature, utils/hook-Muster wie `useAirports`.
- [x] CI/Workflow kompatibel? — `npm ci && npm run build` + `pytest tests/`; neue Tests laufen in bestehendem pytest-Lauf.
- [x] Dokumentation aktualisiert? — dieses Design + Plan; user-stories.md um Story ergänzt.

## Risiken / Open Points
- Local Storage ist pro Browser pro Origin → "pro Benutzer" heißt hier: pro Browser-Profil.
  (Gewünscht, da explizit nicht-DB.)
- Mehrere Tabs desselben Browsers sehen dieselben Konfigurationen; Schreibkonflikte sind
  für dieses Tool vernachlässigbar (last-write-wins).
