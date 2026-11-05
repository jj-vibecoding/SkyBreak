# Design: Price Alerts with Telegram Notifications

**Status:** Designed, not implemented
**Date:** 2026-11-05 (updated: destination-level targets added)
**Migration number:** v15 if on-demand-price-quotes (v14) ships first — renumber to the next free version if this ships alone
**Related:** price scheduler (`scraper_job.scrape_favorite_prices`, `flight_prices`), Settings tab, Favorites tab

## Problem

Price monitoring exists, but it's passive: prices are fetched every N hours and displayed
on the Favorites tab. If the user is not watching the app, a price drop goes unnoticed —
and flight prices move within days, so "noticed it next weekend" defeats the purpose.

This was already documented as the future story *Telegram Notifications*: get notified
when a monitored trip becomes cheaper than a predefined maximum price.

## Target levels (design decision)

A target can be set at **two levels**, mirroring how the Favorites UI is already
organized (trips are grouped by destination):

| Level | Scope | Stored on |
|---|---|---|
| Destination | All favorite trips to that destination airport | `destination_targets` table |
| Trip | One specific favorite trip | `favorite_trips.target_price` column |

**Resolution rule:** the trip-level target wins when set; otherwise the destination
target applies. A trip with neither inherits nothing (no alert). The UI makes this
explicit: the per-trip input shows "inherit" when empty and a distinct style when it
overrides the group value.

Rationale: users often think in destinations ("CDG under €300") but occasionally want a
tighter or looser goal for one specific flight pair — both must be expressible without
duplicating work across trips to the same destination.

## User Story (add to `doc/user-stories.md` at implementation time)

**As a user**, I want to set a target price per favorite trip *or* per destination, and
receive a Telegram message when the current total price falls to or below the effective
target, **so that** I can book at my desired price even when I'm not looking at the app.

Acceptance criteria:
- Destination targets: one optional value (EUR) per destination group in the Favorites tab; empty = no alert.
- Trip targets: one optional value (EUR) per favorite trip; takes precedence over the destination target when set.
- Alert fires when a price update finds `price_total ≤ effective target` while the previous known total was above it (edge-triggered, not level-triggered).
- Telegram bot token + chat id configurable in Settings; "send test message" button.
- Every sent/failed notification is logged in the DB (including which scope fired) and visible in the UI.
- Without configured credentials the feature is silently inactive (no errors).

## Existing Infrastructure to Reuse

- `scraper_job.scrape_favorite_prices()` — runs every `price_fetch_interval_hours`
  (default 6 h), calls `fetch_prices_favorite(fav_id, force=True)` per favorite and logs
  success/failure counts. **This is the single hook point** where new prices land; alerts
  are evaluated right here, after each successful fetch.
- `favorite_trip_prices` — full price history already stored (`fetched_at`, total), so
  "previous price" = the row before the one just inserted.
- Favorites UI grouping: `FavoriteTripPrices.js` already groups rows by
  `destination_airport` with city-name headers — destination targets slot into the group
  header, no new structure needed.
- Settings key-value store + `/api/settings` (GET/POST). **Important:**
  `apply_migrations()` deletes every settings key not in `SETTINGS_WHITELIST`
  (`db_migrate.py`) — new keys must be added to that tuple in the same migration step.
- Telegram Bot API: plain HTTPS POST, no SDK needed → no new Python dependency.

## Design

### Database (one migration step)

```sql
ALTER TABLE favorite_trips ADD COLUMN target_price REAL;   -- NULL = inherit destination / no alert

CREATE TABLE IF NOT EXISTS destination_targets (
    destination_airport TEXT PRIMARY KEY,   -- IATA code, e.g. 'CDG'
    target_price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    favorite_id INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'telegram',
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('sent','failed')),
    target_scope TEXT CHECK(target_scope IN ('trip','destination')),  -- which target fired
    detail TEXT,                 -- API error text on failure
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notifications_fav ON notifications (favorite_id, sent_at DESC);
```

Settings keys added to `SETTINGS_WHITELIST` in the same step:
`telegram_bot_token`, `telegram_chat_id`.

### Backend

New module `skybreak/notifications.py`:

```python
def send_telegram(token, chat_id, text) -> tuple[bool, str]:
    """POST https://api.telegram.org/bot<token>/sendMessage (requests, timeout=15).
    Returns (ok, detail). Never raises — network/API errors become ('failed', msg)."""

def effective_target(favorite) -> tuple[float | None, 'trip' | 'destination' | None]:
    """Resolve (target_price, scope): trip target if set, else destination target."""

def evaluate_alert(favorite_id) -> dict | None:
    """Edge-triggered alert check, called after a successful price fetch.

    1. Read favorite + its destination target; resolve effective target & scope.
       No effective target → return None (nothing to do).
    2. Read last two favorite_trip_prices rows (newest first).
    3. Fire only if ALL hold:
         new_total is not None and new_total <= target
         previous_total is None or previous_total > target   # re-arm rule
       (previous=None covers the very first price of a favorite that's already below target)
    4. If firing: compose message (noting scope), send via configured channel, insert
       notifications row (status sent/failed, target_scope). Return the notification dict; else None."""

def last_notifications(limit=50) -> list[dict]: ...   # for the UI log
```

Re-arm rule rationale: with level-triggering ("notify while price ≤ target") a user who
misses one message would get the same alert every 6 h forever. Edge-triggering means:
drop below → one message; it stays below → silence; it rises back above and drops again
→ new message. The comparison always uses the *current* effective target, so editing a
target re-arms naturally on the next drop (see edge cases for "target set above current price").

Wiring in `scraper_job.scrape_favorite_prices()`: after each successful
`fetch_prices_favorite`, call `evaluate_alert(fav_id)` inside the same try/except (an
alert failure must never break the price loop). Also call it from the manual update paths
(`POST /api/prices` and `/api/prices/missing`) so a user-triggered refresh can fire alerts too.

New routes in `app.py`:

- `PUT /api/favorites/<int:fav_id>` — body `{target_price: number | null}` → sets/clears
  the trip-level target, returns the favorite. (No update endpoint exists today; POST creates, DELETE removes.)
- `PUT /api/destination-targets/<airport>` — body `{target_price: number | null}` →
  upserts or deletes the destination row (null = delete). Validates IATA code → 400.
- `GET /api/favorites` — extended response: each row gains `target_price` and
  `destination_target_price` so the UI can render both inputs and the effective-target badge without extra round-trips.
- `GET /api/notifications` — recent notification log (limit param).
- `POST /api/notifications/test` — sends a test message with configured credentials;
  returns `{sent: true}` or `{sent: false, detail: "…"}`. Not logged to `notifications`.

### Frontend

**Favorites tab** (`FavoriteTripPrices.js`) — fits the existing group structure:
- **Group header** (per destination): target input next to the city name, persisted via
  `PUT /api/destination-targets/<code>` on change. Placeholder "Target €".
- **Per-trip row**: small target input; empty = inherits the group value (shown as a
  subtle hint, e.g. placeholder "≤ €300 (dest)"), filled = overrides (visually distinct).
  Persisted via `PUT /api/favorites/<id>`.
- Badge states per trip: no effective target → nothing; armed → "⚡ ≤ €X" (with a small
  "trip"/"dest" marker when the trip value overrides); achieved → green highlight
  "€Y ≤ €X".
- Small notification log section at the bottom (last ~20 entries with status icon and scope).

**Settings tab** (`SettingsTab.js`):
- New "Notifications" card: bot token (password-style input), chat id, and a
  "Send test message" button wired to `POST /api/notifications/test` with toast feedback.
- Values saved through the existing generic `/api/settings` POST (whitelist updated).

Message format (Telegram):

```
📉 SkyBreak price alert
FRA → CDG · LH1032 / AF1765
Out 2026-12-04 · Ret 2026-12-08
Total: €289 (target ≤ €300, destination)
```

The scope suffix `(trip)` / `(destination)` is omitted when only one level exists for that trip.

## Edge Cases & Risks

| Case | Behavior |
|---|---|
| No credentials configured | `evaluate_alert` returns early; nothing logged, no errors |
| Price fetch failed for a favorite | No evaluation at all (no price to compare) |
| Total is NULL (a leg unlisted) | No alert — cannot judge total against target |
| Favorite created already below target | First successful price fires the alert (previous=None rule) |
| Target set **above** the current price | No immediate message (edge rule compares price history, not the act of setting). UI shows the "achieved" state immediately, so the user sees it anyway. Documented behavior; an instant confirmation ping is a possible follow-up |
| Trip target and destination target both set | Trip wins; notification logged with `target_scope='trip'` |
| Destination target edited while trips are below it | No re-alert until a price rises above the new target and drops again (re-arm rule) |
| Telegram API down / bad token | Notification stored with status `failed` + detail; user sees it in the log; test button surfaces the same error proactively |
| Token leaked via DB backup | Documented risk of the single-file DB; mitigation: rotate bot token. UI never echoes the token back (mask on GET is out of scope — settings endpoint returns all keys today) |

## Out of Scope

- Other channels (webhook/Email/Push) — `channel` column + provider function shape already
  allow adding one later without schema change.
- Per-leg target prices (outbound-only alerts).
- Destination targets for destinations with *no* favorites yet (table is only meaningful
  where trips exist; creating a target via API for an empty destination is allowed but inert).
- Instant "target set above current price" confirmation message (documented edge case).
- Alert history beyond the log table (no charting of alert events).

## Test Plan (tests written first, per workflow)

`tests/test_price_alerts.py`:
- `effective_target`: trip set → ('trip'); only destination set → ('destination'); neither → None.
- Edge-trigger matrix: (prev, new, effective target) → fires / not fires for the 5 key combinations.
- Trip target overrides destination target in evaluation and in `target_scope` logging.
- Setting target above current price does NOT fire (previous ≤ target).
- `send_telegram` success and failure paths (monkeypatched `requests.post`).
- No credentials → no call attempted, nothing logged.
- Failed send stored with status `failed`.
- Endpoints: PUT trip target updates row; null clears it; invalid value → 400.
  PUT destination target upserts/deletes; invalid IATA → 400.
  GET /api/favorites rows include both target fields.
  Test endpoint returns `{sent: false, detail}` when token is empty.

`tests/test_db_migration.py`: bump expected version.

## Review Checklist

- [x] User story covered (story defined above; add to user-stories.md at implementation)
- [x] Architecture consistent — single hook in the existing scheduler loop; DDL via `db_migrate.py`; new settings keys whitelisted in the same migration step; UI reuses existing destination grouping
- [x] CI/Workflow compatible — pytest only, no new dependencies (requests already used)
- [ ] Documentation — update README + `doc/architecture.md` (routes, tables, settings) at implementation time