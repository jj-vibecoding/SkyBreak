# User Stories - SkyBreak

## Story 1: Basic Airport Entry

**Title:** As a user, I want to enter international airport codes so I can plan trips.

**Description:**
Users can input international airport codes (e.g., "LHR", "JFK", "CDG") to discover destinations.

**Acceptance Criteria:**
- Input field accepts alphanumeric airport codes
- Validation ensures valid IATA codes (3-char regex)
- Code is stored in the system for later use
- Error handling for invalid codes
- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High
**Status:** Implemented

---

## Story 2: Load Departures and Arrivals

**Title:** As a user, I want the system to load flight departures and arrivals from airports.

**Description:**
The system fetches flight schedules via RapidAPI aerodatabox and stores them locally in SQLite.

**Acceptance Criteria:**
- Scraper runs periodically (configured interval) to collect flight data
- Departure and arrival times are parsed and stored
- Data is persisted in the local database
- Invalid or missing data is handled gracefully
- Rate-limit backoff on 429 responses

**Priority:** High
**Status:** Implemented

---

## Story 3: Calculate Turn-arounds

**Title:** As a user, I want to calculate possible turn-arounds from one airport to a destination and back.

**Description:**
The system computes feasible round-trip itineraries (start → destination → return) considering travel time, weekday constraints, and trip duration limits.

**Acceptance Criteria:**
- Algorithm considers flight durations between airports
- Turnaround matching uses SQL-based filtering with in-memory hash join
- Start and end weekdays are configurable via UI
- Min/max trip duration enforced
- Earliest/latest departure/return times configurable
- Resulting itineraries displayed on Trips tab

**Priority:** High
**Status:** Implemented

---

## Story 4: Configure Days Off

**Title:** As a user, I want to configure which days are considered days off for turn-arounds.

**Description:**
Users select which weekdays (0=Monday … 6=Sunday) are valid for outbound and return flights on the Trips search page.

**Acceptance Criteria:**
- Weekday selection via UI component
- Turn-around calculation respects selected weekdays
- Changes take effect immediately on next search

**Priority:** Medium
**Status:** Implemented

---

## Story 5: Select Monitored Trips (Favorites)

**Title:** As a user, I want to save trips as favorites and monitor their prices.

**Description:**
Users can add turn-arounds from the Trips tab to a Favorites list. The system tracks price history for each favorite.

**Acceptance Criteria:**
- List of favorite trips displayed on Favorites tab
- Users can add/remove favorites with confirmation
- Selected trips are tracked for price changes
- Prices fetched periodically via background scheduler

**Priority:** Medium
**Status:** Implemented

---

## Story 6: Flight Price Data Integration

**Title:** As a user, I want the system to fetch real-time flight prices via RapidAPI.

**Description:**
The backend integrates with RapidAPI aerodatabox for flight schedule data and Google Flights (via kayak_direct) for pricing.

**Acceptance Criteria:**
- API key configurable in Settings tab
- Flight schedules fetched on configured interval
- Prices fetched for favorites on configured interval
- Rate-limit handling with backoff on 429 responses

**Priority:** High
**Status:** Implemented

---

## Story 7: Price Monitoring Scheduler

**Title:** As a user, I want the system to automatically check flight prices for favorite trips at a configurable interval.

**Description:**
A background scheduler (apscheduler) runs price checks for all favorites on a configured interval (default 6 hours).

**Acceptance Criteria:**
- Scheduler triggers price checks on configured interval
- Comparison against previous price stored in DB
- New price data saved to `favorite_trip_prices` table
- Interval configurable in Settings tab

**Priority:** High
**Status:** Implemented

---

## Story 8: Price History Chart

**Title:** As a user, I want to view a chart showing price history for each favorite trip.

**Description:**
Visualize the price trends of favorite trips over time using an interactive SVG chart modal.

**Acceptance Criteria:**
- Line chart shows price vs. date for each favorite trip
- Chart displays outbound, return, and total prices
- Responsive SVG with proper scaling on mobile
- Date-based X-axis with collapsible data points
- Trigger manual price updates via button

**Priority:** Medium
**Status:** Implemented

---

## Story 9: Remove Monitoring (Unfavorite)

**Title:** As a user, I want to remove a trip from my favorites and delete its price history.

**Description:**
Removing a favorite deletes the trip entry and all associated price history records.

**Acceptance Criteria:**
- Action removes trip from favorites list
- All price history for the trip is deleted
- Confirmation dialog before deletion
- UI updates immediately

**Priority:** Medium
**Status:** Implemented

---

## Story 10: Remove Entire Airport

**Title:** As a user, I want to remove an entire airport from the system.

**Description:**
Deletion of an airport removes it from the airports table. Related data (flights) retains its records but is no longer associated with the deleted airport code.

**Acceptance Criteria:**
- Confirmation before deletion
- Airport removed from list
- No orphaned references in UI

**Priority:** Medium
**Status:** Implemented

---

## Story 11: Filter by Date

**Title:** As a user, I want to filter potential trips by date range.

**Acceptance Criteria:**
- Date range picker on Trips tab (trip start / trip end dates)
- Only trips within the selected date range are shown
- Applies to both outbound and return flights

**Priority:** Medium
**Status:** Implemented

---

## Story 12: Visible Flight Prices

**Title:** As a user, I want to see trip prices as both single flight prices and combined price.

**Acceptance Criteria:**
- Each favorite shows individual outbound and return prices
- Combined total price shown for the round-trip
- Prices visible in favorites list and detail views
- Price status indicator (up/down/stale)

**Priority:** Medium
**Status:** Implemented

---

## Story 13: Save Trip Search Configurations

**Title:** As a user, I want to save my trip search settings under a name so I can reload them later.

**Description:**
On the Trips page the current search parameters (start/end weekdays, latest departure time, earliest return departure time, min/max trip length) can be saved as a named configuration and reloaded at any time. Saved configurations are stored in the SQLite database through the REST API, so every browser and device shows the same set. Airport selection and the date range are intentionally excluded from a configuration.

**Acceptance Criteria:**
- Only start/end weekdays, departure/return times and min/max trip length are saved
- Airport and earliest start / latest end dates are NOT part of a configuration (kept as-is on load)
- Every configuration has a name; duplicate names require an overwrite confirmation
- Configurations can be loaded and deleted (with confirmation)
- Data is persisted server-side (SQLite, `trip_search_configs`) and is identical in every browser/device
- Configurations saved locally via localStorage are migrated to the database on first sync

**Priority:** Medium
**Status:** Implemented

---

## Story 14: Local UI Persistence

**Title:** As a user, I want my UI preferences (date pickers, sorting, filters) to persist across page refreshes.

**Description:**
UI state on the Trips and Favorites tabs is persisted in browser localStorage so users don't lose their settings when refreshing or navigating away.

**Acceptance Criteria:**
- Airport selections, date ranges, weekday picks persist on Trips tab
- Sorting preferences, date filters persist on Favorites tab
- Preferences restored automatically on page load
- No server round-trips for UI state

**Priority:** Low
**Status:** Implemented

---

## Not Implemented (Future)

### Telegram Notifications
As a user, I want to receive Telegram notifications when a monitored trip becomes cheaper than a predefined maximum price.
