# Goal
Review SkyBreak project and propose next features (advisory only, no code changes).

## Done
- Reviewed README, doc/architecture.md, doc/user-stories.md (14 stories implemented; "Telegram Notifications" was listed as future but removed in last cleanup).
- Reviewed backend: app.py routes (airports, flights, prices, favorites, settings, trip-configs, turnarounds), db_migrate.py at v13.
- Reviewed frontend components/hooks; confirmed TripsTab results show NO prices (only favorites get price tracking) — real UX gap.
- No notification code exists yet (no telegram/smtp anywhere).

## Open
- Delivered feature proposals to user; user picked features 1, 2, 6 (rejected 3, 4, 5, 7).
- Wrote 3 design docs in doc/designs/: on-demand-price-quotes.md, price-alerts-telegram.md, health-dashboard-backup.md. User will implement later in separate sessions (each: plan doc → tests first).
- Design 2 updated per user request: targets at BOTH levels — destination_targets table (per destination group) + favorite_trips.target_price (per trip); trip wins when set; UI slots into existing destination grouping in FavoriteTripPrices.js.
- Key facts baked into designs: migration v14/v15 numbering depends on ship order; settings keys need SETTINGS_WHITELIST entry in same migration step; flight scrape is manual-only today (no periodic job) — health design part 4 optionally adds it; clean_old_flights() is dead code.
