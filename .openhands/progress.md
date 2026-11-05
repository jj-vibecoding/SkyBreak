# Goal
Frontend responsive-Umbauten (uncommitted) zeigen auf dem iPhone nur dunkelblauen Hintergrund; alle Frontend-Fehler finden/beheben, Container mit neuem Build starten (Config unverändert).

## Done
- `Dialogs.js`: `useConfirm` State erweitert um title/message; `ToastProvider` hört auf `window` CustomEvent `showToast`; `<ConfirmDialog/>` pro Komponente gerendert.
- `TripsTab.js` + `FavoriteTripPrices.js`: `ConfirmDialog` destruktiert UND im Root gerendert (vorher: showConfirm-Promises liefen ins Leere).
- `ChartModal.js`: Chart-Punkte skalieren jetzt mit dynamischer viewBox-Breite (`getChartWidth()` = min(innerWidth-48, 720)); Tooltip-Clamp + Legende responsive (Legende unter Chart < 480px, svgHeight wächst); Effekt rechnet bei Breitenänderung neu.
- `App.js`: tote `CollapsibleSidebar`-Import entfernt (Drawer in App ersetzt es).
- `FlightsTab.js`: "Today"-Button neben WeekPicker wiederhergestellt (Funktionsverlust durch Responsive-Umbau).
- `tests/test_app_integration.py`: CollapsibleSidebar-Anforderung entfernt (passend zur neuen Architektur).
- Tests: 119 passed, 2 skipped. `npm run build`: Compiled successfully.
- Container: Image `skybreak-local` neu gebaut; `skybreak-skybreak-1` mit IDENTISCHER Config neu gestartet (docker run -d --name skybreak-skybreak-1 --restart unless-stopped -p 8088:80 -v /opt/skybreak/:/data/ -e DB_FILE=/data/skybreak.db skybreak-local python -m skybreak.app).
- Verifiziert: Container liefert NEUES Bundle main.4c9164a0.js mit showToast/ConfirmDialog; /api/airports 200; DB intakt (alle Tabellen, 155MB).

## Ruled out
- `useEffect is not defined` auf Disk: Import war schon gefixt — Ursache war ausschließlich das veraltete Bundle im Container.

## Open
- User testet erneut am iPhone (http://<host>:8088), hartes Refresh / Cache leeren falls nötig.
