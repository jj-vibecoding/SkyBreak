# Plan: Frontend Responsive Optimierung

Referenz: `doc/designs/Frontend-Responsive-Optimierung.md`. Alle Änderungen liegen in
`frontend/src` + `frontend/public/index.html`; kein Backend-/API-/DB-Change.

## Arbeitsschritte (in Reihenfolge)

### Schritt 0 — Tests ZUERST (TDD)
Neue/guardierte Tests vor der Implementation, im Stil der bestehenden Infrastruktur:
- `tests/test_frontend_responsive.py` (pytest, Node-basiert wie die tripConfigs-Tests):
  - `useMediaQuery`: liefert bei simulierten Viewports korrekte Breakpoints, reagiert auf Changes.
  - Wochentage-Chips: Multi-Select-Semantik identisch zum alten `<select multiple>`
    (Index-Array), Toggle per Tap, State round-trip mit Saved Configs.
  - Trips-Karten-Ansicht <640px: alle Trip-Felder (Rückflug-Zeit, Turnaround, Preis, Aktionen)
    vorhanden; ≥640px Tabelle wie bisher.
  - Tabellen-Container: `.scroll-x`-Klasse + min-width gesetzt (DOM-Assertion).
  - ChartModal: Tooltip-Rect-Klemmung `[5,595]`, Tick-Verdünnung (max. 8 Labels inkl. erstem/letztem),
    Legendenposition (<480px unter Chart).
  - Sidebar-Drawer: ein einziger State, Backdrop schließt, ESC schließt, Body-Scroll-Lock.
  - Trips-Tabelle: Header-Zellenzahl == Body-Zellenzahl (4/4, Actions-Spalte mit Kopf) → Fix #18.
  - `index.html`: `<html lang="en">`; keine deutschen UI-Strings mehr in Komponenten (Regex-Guard) → Fix #16.
  - AirportsTab-Feedback: `tone`-Feld steuert Farbe (success ≠ error), unabhängig vom Text → Fix #19.
- Playwright (`tests/test_frontend_visual.py`, guardiert wie `test_price_chart_playwright.py`):
  Screenshots/Sanity-Checks bei 375×812 (iPhone), 768×1024 (Tablet), 1440×900 (Desktop)
  für alle 5 Tabs: **kein horizontaler Seitendoc-Overflow**
  (`document.documentElement.scrollWidth <= clientWidth + 1`) und keine unsichtbare Navigation.
- Bestehende Tests dürfen ohne Semantik-Änderung weiterlaufen; `test_db_migration.py` etc. unberührt.

### Schritt 1 — Fundament (global)
- `src/styles/global.css` anlegen + import in `src/index.js`:
  Tokens (Farben/Radien/Spacing/Touch-Größe), Box-Model-Reset, `color-scheme: dark`,
  `focus-visible`, Scrollbars, Utilities `.scroll-x` / `.tap`.
- `public/index.html`: `<meta name="theme-color" content="#0f172a">`, `description`,
  Apple-Mobile-Metas; `'Inter'` aus dem Font-Stack entfernen (reiner System-Stack);
  `<html lang="en">` (statt `de`) → Fix #16.
- `src/hooks/useMediaQuery.js` neu (matchMedia, SSR-safe, Listener-Cleanup).

### Schritt 2 — Shell (Sidebar + Header + Spacing)
- `App.js`: Sidebar-State vereinheitlichen (einziger Source of Truth), Resize-Listener
  via `useMediaQuery('lg')` statt innerWidth-Check → Fix #3.
- `CollapsibleSidebar.jsx`: <1024px Off-Canvas-Drawer (Transform, Backdrop, ESC,
  Safe-Area, Scroll-Lock); ≥1024px statisch wie heute → Fix #2.
- `App.js`-Header: kompakter Tab-Header mit Titel/Untertitel pro Tab; Brand bleibt in Sidebar → Fix #8.
- Spacing-Skalen lg/md/sm + `max-width: 1400px`-Content-Wrapper (zentriert) → Fix #9.
- `<a><button>`-Nesting korrigieren (Button mit onClick/Navigate oder Link-Style) → Fix #13.

### Schritt 3 — Tabs & Komponenten
- `TripsTab.js`:
  - Wochentage-Chips (7 Toggle-Buttons, `aria-pressed`) ersetzen `<select multiple>` → Fix #4.
  - Turnarounds: `<640px` gestapelte Karten, `≥640px` Tabelle in `.scroll-x` (min-width 640px) → Fix #5.
  - Fehlenden „Actions“-Spaltenkopf ergänzen (3→4 `<th>`, Body-Konsistenz) → Fix #18.
  - „Loaded until …“-Text + Button: `flex-wrap: wrap` → Fix #17.
  - Save-Config-Feedback als Toast; Bestätigungen als In-App-Dialog → Fix #12.
- `FavoriteTripPrices.js`: Table-Wrapper `.scroll-x` (min-width 720px) → Fix #1;
  Gruppen-Header mit Truncation (`min-width:0`, ellipsis) → Fix #11.
- `FlightsTab.js`: Table-Wrapper `.scroll-x` (min-width 560px); Statuszeile wrappable.
- `AirportsTab.js`: Touch-Ziele vergrößern (`.tap`), Eingabe/Buttons konsistent;
  Feedback-State explizit als `{ text, tone }` statt Text-Matching → Farbe sprachunabhängig → Fix #19.
- `SettingsTab.js`: Sections/Inputs mobil skalierbar, Save-Toast + In-App-Dialog.
- `ChartModal.js`: Tooltip-Klemmung, Tick-Verdünnung, Legende responsiv → Fix #10.
- Globale Passes: `aria-expanded`/`scope` ergänzen, Sort-Header-Buttons ≥44px → Fix #6/#14;
  **alle** `alert()`/`confirm()` durch das In-App-Dialog-System ersetzen → Fix #12.
- UI-Texte auf Englisch vereinheitlichen (inkl. AirportsTab-/SettingsTab-German Strings) → Fix #16.

### Schritt 4 — Verifikation
- `npm run build` (muss grün sein; CI baut das Frontend hart).
- `python -m pytest` lokal (Docker-Daemon-/Playwright-guards wie bisher skippen sich sauber).
- Manuell/Playwright: 375px, 768px, 1024px, 1440px, 2560px über alle 5 Tabs;
  Rotation Mobile↔Desktop (Resize-Bug #3 explizit retesten).
- Docker-Deploy nach Freigabe: `docker build` + `rm` + `run` (kein Live-Patch!).

## Abhängigkeiten
Schritt 1 → 2 → 3 (alle bauen auf global.css/useMediaQuery auf); Schritt 0 läuft parallel
vor/bei 1–3. Kein Backend-Change, keine Migration.

## Rollback
Reines Frontend: Revert des Commits + Image-Rebuild reicht; DB/Daten bleiben unangetastet.

## Plan-Review-Checkliste
- [x] Reihenfolge korrekt (Tests vor Code)?
- [x] Keine fehlenden Abhängigkeiten?
- [x] Review-Log aktualisiert?

## Review-Log
- **2026-11-04 — Initial:** Schritte 0–4 gegen Design abgeglichen; Abhängigkeitskette
  1→2→3 bestätigt; Rollback als reiner Frontend-Revert + Rebuild dokumentiert.
- **2026-11-04 — Re-Review:** Neue Befunde #18/#19 aus dem Design-Review aufgenommen:
  Schritt 1 (`lang="en"`), Schritt 3 (Actions-Header, Feedback-Tone) und Schritt 0
  (drei zusätzliche Test-Guards) ergänzt. Bestehende Tests referenzieren keine deutschen
  UI-Strings → EN-Umstellung bricht keine Tests. Reihenfolge und Abhängigkeiten bleiben gültig.

## Erwartete Dateien
| Datei | Änderung |
|-------|----------|
| `frontend/src/styles/global.css` | neu |
| `frontend/src/components/Dialogs.js` | neu: Toast-Host + Confirm-Dialog (ersetzt alert/confirm) |
| `frontend/src/hooks/useMediaQuery.js` | neu |
| `frontend/src/index.js` | CSS-Import |
| `frontend/public/index.html` | Meta-Tags, Font-Stack |
| `frontend/src/App.js` | Sidebar-State, Drawer, Header, Spacing, Toasts |
| `frontend/src/components/CollapsibleSidebar.jsx` | schlanker Wrapper um Drawer/Statik |
| `frontend/src/components/TripsTab.js` | Chips, Karten/Table, Wrap, Toasts |
| `frontend/src/components/FavoriteTripPrices.js` | Scroll-Wrapper, Truncation |
| `frontend/src/components/FlightsTab.js` | Scroll-Wrapper, Wrap |
| `frontend/src/components/AirportsTab.js` | Touch-Ziele |
| `frontend/src/components/SettingsTab.js` | Skalierung, Toast |
| `frontend/src/components/ChartModal.js` | Tooltip/Ticks/Legende |
| `tests/test_frontend_responsive.py` | neu (Node-Tests) |
| `tests/test_frontend_visual.py` | neu (Playwright, guardiert) |