# Goal
Fix N+1 query performance issue on the favorites page (`GET /api/favorites`).

## Done
- Identified root cause in `skybreak/app.py` `list_favorites()`: for each of N favorites, 1 price query + up to 2 flight detail queries = 3N+1 queries total.
- Replaced per-row queries with batch IN-clause queries:
  - 1 batch query for all favorites' latest prices (correlated MAX subquery)
  - 2 batch queries for outbound/return flight details (unique flight_number+date pairs)
- Total reduced from O(N) to O(1) queries regardless of favorites count.
- All 195 pytest tests pass, 2 skipped; frontend `npm run build` clean.

## Open
- Delivered feature proposals to user; user picked features 1, 2, 6 (rejected 3, 4, 5, 7).
- Wrote 3 design docs in doc/designs/: on-demand-price-quotes.md, price-alerts-telegram.md, health-dashboard-backup.md. User will implement later in separate sessions (each: plan doc → tests first).
- Design 2 updated per user request: targets at BOTH levels — destination_targets table (per destination group) + favorite_trips.target_price (per trip); trip wins when set; UI slots into existing destination grouping in FavoriteTripPrices.js.
- Key facts baked into designs: migration v14/v15 numbering depends on ship order; settings keys need SETTINGS_WHITELIST entry in same migration step; flight scrape is manual-only today (no periodic job) — health design part 4 optionally adds it; clean_old_flights() is dead code.
