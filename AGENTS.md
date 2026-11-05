# KI / Agent Anweisungen — Workflow

## Pflicht-Regeln (für alle Änderungen)
1. Feature-Branch erstellen wenn angemessen (`git checkout -b ...`) — nicht für jeden Hotfix erforderlich
2. Erst Design-Dokument (`doc/designs/<Feature>.md`) — bei Features und signifikanten Änderungen
3. Design-Review gegen User Stories (`doc/user-stories.md`) + Architektur (`doc/architecture.md`)
4. Iteriere Design + Review bis Kompatibilität bestätigt
5. Konkreter Implementierungsplan (`doc/plans/<Feature>.md`)
6. Plan-Review gegen restliche Doku + User Stories
7. Iteriere Plan + Review bis alles passt
8. Tests ZUERST schreiben (`tests/test_...`)
9. Feature implementieren
10. Tests ausführen (`python -m pytest`)
11. PR erstellen (`create_pull_request`) — nur wenn erforderlich (Feature/Release); direkte Push nur bei expliziter Zustimmung
12. GitHub Actions validieren (Workflow prüfen / `gh run`) — bei PRs oder nach direktem Push
13. PR mergen wenn ok / bei direktem Push auf Main: sofortige Validierung

## Design-Review-Checkliste
- [ ] User Stories abgedeckt?
- [ ] Architektur konsistent?
- [ ] CI/Workflow kompatibel?
- [ ] Dokumentation aktualisiert?

## Implementierungsplan-Checkliste
- [ ] Reihenfolge korrekt (Tests vor Code)?
- [ ] Keine fehlenden Abhängigkeiten?
- [ ] Review-Log aktualisiert?

## Database Migration Requirement
The container must handle an empty/missing database file.
The container must migrate an existing db on its own to the latest schema.

## DB Migration Rules
1. Schema version saved in DB table `db_version`.
2. Every schema change needs own migration step increasing version; apply at startup via `skybreak/db_migrate.py`.
3. Remove unused DB/init scripts; runtime must use only `db_migrate.apply_migrations()`.
4. Future migrations: add `migration_v*` in `db_migrate.py`, update version, deploy via image rebuild.
5. Never live-patch DB/container; changes only through source + docker build + redeploy.

## Container Config
- Port: 8088 (mapped to container 80, App: flightbreak)
- Mount: /opt/skybreak (DB_FILE=/opt/skybreak/skybreak.db)
- Container name: flightbreak
- Image: skybreak-local
