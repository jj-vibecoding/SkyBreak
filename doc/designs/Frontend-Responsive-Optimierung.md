# Design: Frontend Responsive Optimierung (Mobile + Desktop)

## Ziel
Das SkyBreak-Frontend auf mobilen UND Desktop-Browsern gleichermaßen gut nutzbar machen:
keine abgeschnittenen/überlappenden Bereiche, bedienbare Touch-Ziele, saubere Darstellung
von 320px (Handy) bis 2560px (Ultra-Wide). Ohne Änderungen an Backend, API oder Feature-Logik.

## Status quo

- React 18 (CRA / react-scripts), **alle Styles sind inline** (JS-Objekte), keine CSS-Dateien,
  **keine Media Queries**, kein globales CSS-Reset.
- Einziger responsiver Mechanismus: Sidebar-Collapse bei `window.innerWidth < 1024` —
  implementiert als **zwei parallele States** (`App.mobileNavHidden` + `CollapsibleSidebar.innerCollapsed`).
- `public/index.html`: viewport-Tag vorhanden, aber kein `theme-color`, kein `description`,
  kein `color-scheme` — native Picker (Date/Time/Number) rendern im Light-Theme.
- `'Inter'` wird im Font-Stack referenziert, aber nirgends geladen (stiller Fallback).

## Befunde (nach Schweregrad)

### P0 — bricht die Mobile-UX
| # | Problem | Wo |
|---|---------|----|
| 1 | Favorites-Tabelle `minWidth: 720px` **ohne** Scroll-Wrapper → seitlicher Überlauf der ganzen Seite / Clipping unter 720px | FavoriteTripPrices.js |
| 2 | Sidebar: Content wird `display:none` statt Drawer → Navigation komplett unsichtbar; Toggle-Button (`right: -22px` an 0-breitem Container) liegt halb außerhalb des Viewports; beim Expanden quetscht die feste 220px-Sidebar den Content auf ~119px (375px-Gerät) | CollapsibleSidebar.jsx / App.js |
| 3 | Resize-Bug: `handleResize` setzt bei <1024 **immer** `true`, nie zurück → nach Rotation/Resize bleibt die Sidebar auch auf Desktop dauerhaft weg; doppelter State kann aus dem Takt laufen | App.js / CollapsibleSidebar.jsx |
| 4 | Wochentage-Auswahl via `<select multiple>` (Ctrl/Cmd-Klick nötig) → auf Touch-Geräten faktisch unbedienbar; zentrale Suchkriterien der Trips-Suche damit nicht setzbar | TripsTab.js |
| 5 | Turnaround-Tabelle: 4 Spalten, `tableLayout: fixed`, `width: 100%`, kein Scroll-Wrapper, kein `word-break` → Inhalte überlappen/kürzen auf schmalen Screens | TripsTab.js |

### P1 — deutlich suboptimal
| # | Problem | Wo |
|---|---------|----|
| 6 | Touch-Ziele: Buttons mit 5–8px Padding / 11–12px Font (< 44px), Sort-Header-Buttons `padding: 0`, ×-Buttons 2×6px | alle Tabs |
| 7 | Kein `color-scheme: dark` + kein `body`-Hintergrund → weiße Overscroll-Flashes, helle native Kalender-/Zeit-Popover auf dunklem UI | global |
| 8 | Identischer großer Marken-Header (28px + 34px-Emoji) auf jedem Tab, keine Tab-Titel → verschwendet Mobile-Platz | App.js |
| 9 | Feste Maße (main-Padding 36, Section-Padding 24, Gaps 24) werden nicht für Mobile skaliert; gleichzeitig **keine Max-Breite** auf Ultra-Wide (Content streckt sich bis 2560px) | App.js |
| 10 | ChartModal: Legende fest bei `translate(380,10)` (kollidiert mit Daten auf schmalen Screens), Single-Point-Tooltip läuft am rechten Rand aus dem viewBox (x=560 → Rect bis 615), Datums-Ticks überlappen / werden bei ~320px-Renderwinde winzig | ChartModal.js |
| 11 | Gruppen-Header: langer Stadtname + „Cheapest: …“ + Pfeil ohne Truncation → Kollisionen | FavoriteTripPrices.js / TripsTab.js |
| 18 | Trips-Tabelle: 3 `<th>`-Header-Zellen, aber 4 Body-Zellen → Actions-Spalte („+ Add to favorites“) ohne Spaltenkopf | TripsTab.js |

### P2 — Polish / Accessibility
| # | Problem | Wo |
|---|---------|----|
| 12 | `alert()`/`confirm()` als Feedback (Fetch started, Settings saved, Config-Overwrite, Delete-all) — blockierend, unstylbar | App.js, SettingsTab.js, TripsTab.js, FavoriteTripPrices.js |
| 13 | Ungültiges Nesting `<a><button>` in der Sidebar-Navigation | App.js |
| 14 | Keine `focus-visible`-Styles, Collapsible-Buttons ohne `aria-expanded`, Tabellen ohne `scope`/`caption` | diverse |
| 15 | Fehlende Meta-Tags (`theme-color`, `description`), Phantom-Font 'Inter' | public/index.html, App.js |
| 16 | Sprachmix DE/EN in UI-Texten („Gespeichert:“ vs. „No favorites yet“); `<html lang="de">` bleibt trotz englischer UI inkonsistent | diverse, public/index.html |
| 17 | FlightsTab: „Loaded until …“-Text neben Button ohne `flex-wrap` → Überlauf auf schmalen Screens | FlightsTab.js |
| 19 | AirportsTab-Feedback-Farbe: Check `feedback.includes('Saved')` trifft nie, da der Text „Gespeichert“ heißt → Erfolgs-Zeile zeigt immer Grau statt Grün; Fehler-Erkennung über deutsche Teilstrings bricht bei EN-Umstellung | AirportsTab.js |

## Design-Entscheidungen

- **D1 — Globales Stylesheet:** Neues `frontend/src/styles/global.css` (import in `index.js`):
  CSS-Custom-Properties als Design-Tokens (Farben, Radien, Spacing-Skalen, Touch-Größe),
  Box-Model-Reset, `color-scheme: dark`, `focus-visible`-Outline, gedämpfte Scrollbars,
  Utilities `.scroll-x` (horizontaler Momentum-Scroll) und `.tap` (≥44px-Ziel).
  Inline-Styles bleiben primär; **breakpoint-abhängige Werte** kommen über D2/D3.
- **D2 — `useMediaQuery`-Hook:** `matchMedia`-basiert (SSR-safe, Change-Listener).
  Ersetzt alle Ad-hoc-`innerWidth`-Checks. Schwellenwerte: `md = 768px`, `lg = 1024px`,
  Rechnerwerte (Padding/Gaps) über Token-Skalen.
- **D3 — Responsive Shell:** ≥1024px: statische 220px-Sidebar wie heute. <1024px:
  **Off-Canvas-Drawer** (Transform-Animation, dunkler Backdrop, Schließen per Backdrop-Klick /
  ESC / Tab-Wechsel, `safe-area-inset`-Padding, Body-Scroll-Lock während offen).
  **Ein einziger State** in `App`; `CollapsibleSidebar` wird schlanker Wrapper. Fixt #2/#3.
- **D4 — Tabellen:** Jeder Table-Container erhält `.scroll-x` + sinnvolles `min-width`
  (Favorites 720px, Flights 560px, Trips 640px). Zusätzlich: Trips-Tabelle rendert
  **<640px als gestapelte Trip-Karten** (eine Karte pro Trip, Felder label:value),
  ≥640px als Tabelle — via `useMediaQuery`. Gruppen-Header bekommen `min-width:0` +
  `text-overflow: ellipsis` (Fixt #1/#5/#11). Die Trips-Tabelle bekommt den fehlenden
  „Actions“-Spaltenkopf (`<th>` ergänzt, 4/4-Zellen-Konsistenz) → Fixt #18.
- **D5 — Wochentage-Chips:** 7 Toggle-Buttons (`aria-pressed`, min. 44px, Multi-Select per
  Tap) ersetzen `<select multiple>`; State-Semantik (Index-Array) bleibt identisch →
  Saved-Configs und API-Logik unverändert. Fixt #4.
- **D6 — Touch-Ziele:** Alle interaktiven Elemente auf ≥44×44px (via `.tap`-Token);
  Sort-Header-, ×- und Aktions-Buttons vergrößert; dezenter `:active`-Tap-Effekt. Fixt #6.
- **D7 — Header & Spacing:** Kompakter Tab-Header (Titel + Untertitel je Tab, Brand bleibt
  in der Sidebar); Spacing-Skalen: main-Padding 36/24/16 (lg/md/sm), Section 24/16,
  Gaps 24/16. Fixt #8/#9.
- **D8 — Ultra-Wide:** Content-Wrapper `max-width: 1400px`, zentriert (relevant ≥1600px). Fixt #9.
- **D9 — ChartModal:** Legende wandert unter das Chart bei <480px; Tooltip-Rect wird in
  `[5, 595]` geklemmt; Datums-Ticks werden verdünnt (max. ~8 Labels, erste + letzte immer);
  viewBox/Skalierbarkeit bleibt. Fixt #10.
- **D10 — Feedback & Dialoge:** Leichtgewichtiges in-App-System ersetzt **alle**
  `alert()`/`confirm()`-Aufrufe: Info-Feedback als Toasts, Bestätigungen (inkl.
  destruktiver) als Modal-Dialog mit Abbrechen/Bestätigen. Fixt #12.
- **D11 — Meta & Font:** `theme-color: #0f172a`, `description`, Apple-Mobile-Metas in
  `index.html`; `'Inter'` aus dem Font-Stack entfernen → reiner System-Stack. Fixt #7/#15.
- **D12 — Sprache:** Alle UI-Texte werden auf **Englisch** vereinheitlicht; `<html lang="en">`
  in `index.html`. Der AirportsTab-Feedback-Zustand wird **explizit** statt über Text-Matching
  gehalten (z.B. `{ text, tone }`) → Farbe unabhängig von der Sprachwahl korrekt → Fixt #16/#19.

## Abgrenzung
- **Kein** Backend-/API-Change, **keine** DB-Migration, **keine** Änderung der
  Feature-Logik (Suche, Favoriten, Preise, Charts, Scraper bleiben funktional identisch).
- Bestehende Tests (pytest + Node-Tests) müssen weiter grün bleiben; `npm run build` grün.

## Entscheidungen (abgeschlossen 2026-11-04, Nutzerfreigabe)
- **Q1 → Englisch:** Alle UI-Texte werden auf Englisch vereinheitlicht.
- **Q2 → System-Stack:** 'Inter' aus dem Font-Stack entfernen (kein Self-Hosting).
- **Q3 → In-App-Dialoge:** Auch alle destruktiven `confirm()`-Dialoge werden durch
  eigene in-App-Dialoge ersetzt (kein natives `window.alert`/`window.confirm` mehr).

## Design-Review-Checkliste
- [x] User Stories abgedeckt? (alle 5 Tabs voll funktional, mobile + desktop)
- [x] Architektur konsistent? (React/Flask/SQLite; reine Präsentations-Schicht)
- [x] CI/Workflow kompatibel? (npm build; neue Playwright-Tests guardiert wie die bestehenden)
- [x] Dokumentation aktualisiert? (dieses Design + Plan)

## Review-Log
- **2026-11-04 — Initial:** Vollständiger Frontend-Scan (App.js, alle 5 Tabs, ChartModal,
  index.html). P0/P1/P2-Befunde #1–#17 dokumentiert; D1–D12 festgelegt. Nutzerfreigabe Q1–Q3
  (Englisch, System-Font-Stack, In-App-Dialoge statt Browser-Dialoge).
- **2026-11-04 — Re-Review nach Code-Verifikation:** Drei neue Befunde ergänzt:
  - **#18** Trips-Tabelle mit 3 Header-/4 Body-Zellen (Actions-Spalte ohne Kopf) → Fix in D4/Schritt 3.
  - **#19** AirportsTab-Feedback-Farbe über Text-Matching (`includes('Saved')`) gebrochen → expliziter `{ text, tone }`-State in D12/Schritt 3.
  - **#16 erweitert** `<html lang="de">` trotz englischer UI → `lang="en"` in Schritt 1.
  - Test-Guards für #16/#18/#19 in Plan Schritt 0 ergänzt.
  - Verifiziert: User Stories 1–5 bleiben funktional identisch (nur Präsentation); Architektur
    React/Flask/SQLite unverändert; CI-kompatibel (Node-ESM-Testmuster wie tripConfigs,
    Playwright guardiert); bestehende Tests referenzieren nur eigene Config-Namen („Wochenende“),
    keine deutschen UI-Strings → EN-Umstellung testseitig sicher.
  - Ergebnis: Design + Plan konsistent, Kompatibilität bestätigt.