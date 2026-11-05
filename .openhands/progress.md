# Goal
Complete code review and documentation cleanup (2026-11-05).

## Done
- Removed all obsolete design docs from `doc/designs/` (all from merged PRs)
- Removed all obsolete plan docs from `doc/plans/` (all from merged PRs)
- Deleted stale standalone docs: IMPLEMENTATION_SUMMARY.md, PERSISTENCE_DEMO.md, doc/updates.md, CI-CONFIG.md
- Rewrote `doc/user-stories.md`: removed copy-paste errors, removed Telegram story (not implemented), added Status fields to all stories, cleaned up acceptance criteria
- Updated `doc/architecture.md`: fixed tab list (no "Costs" tab), marked all features as implemented, added missing routes/tables, updated tech stack (Python 3.13, playwright scraper)
- Cleaned `AGENTS.md`: removed outdated session learnings, kept workflow rules + DB migration + container config
- Updated `README.md`: expanded features list to match actual implementation

## Verification
- All 130 tests passing (2 skipped), 0 failures
- Remaining docs: AGENTS.md, README.md, doc/user-stories.md, doc/architecture.md
- Empty directories preserved for future use: doc/designs/, doc/plans/
