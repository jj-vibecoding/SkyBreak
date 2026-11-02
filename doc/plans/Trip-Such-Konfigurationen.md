# Plan — Trip Such-Konfigurationen (speichern / laden / löschen)

## Reihenfolge (Tests vor Code)
1. `tests/test_trip_search_configs.py` schreiben (rot):
   - Node/ESM-Verhaltens-Tests für `frontend/src/utils/tripConfigs.js`:
     Roundtrip, Upsert (case-insensitive), Delete, Korrupt-/Fremd-Daten-Toleranz.
   - Verdrahtungs-Tests: TripsTab importiert das Modul; exakt die 6 Felder in
     `CONFIG_FIELDS` (ohne startAirport/endAirport/tripStart/tripEnd); kein
     `fetch(`/api/turnarounds`)`-Ersatz, keine SQLite-/Backend-Kopplung im Modul.
2. `frontend/src/utils/tripConfigs.js` implementieren (grün).
3. `frontend/src/hooks/useTripConfigs.js` implementieren.
4. `TripsTab.js`: Saved-Searches-Block (Name + Save / Select + Load / Delete) einhängen,
   Laden setzt nur die 6 Felder; Status-/Fehlermeldungen.
5. `doc/user-stories.md`: Story für Konfigurationen ergänzen.

## Abhängigkeiten
- Keine neuen Pakete (nur React + window.localStorage).
- Kein DB-Migration/Backend-Change nötig — Persistenz explizit im Local Storage.

## Verifikation
- `python -m pytest tests/test_trip_search_configs.py` (neu) + Gesamtsuite `pytest`.
- `npm run build` in `frontend/` (Build-Gate).
- Browser-Smoke: Konfiguration speichern, laden (nur 6 Felder), löschen; Refresh hält.

## Review-Log
- Plan gegen Design geprüft: Feldliste identisch, Namensregeln & Validierung übernommen.
- Reihenfolge Tests→Code eingehalten; keine fehlenden Abhängigkeiten.
