# User Stories - SkyBreak

## Story 1: Basic Airport Entry

**Title:** As a user, I want to enter international airport codes so I can plan trips.

**Description:**
Users can input international airport codes (e.g., "LHR", "JFK", "CDG") to discover destinations.

**Acceptance Criteria:**
- Input field accepts alphanumeric airport codes
- Validation ensures valid IATA codes
- Code is stored in the system for later use
- Error handling for invalid codes
- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High

## Story 2: Load Departures and Arrivals

**Title:** As a user, I want the system to load flight departures and arrivals from airports.

**Description:**
The system should fetch flight schedules from the integrated Google Flight Scraper and store them locally.

**Acceptance Criteria:**
- Scraper runs periodically to collect flight data
- Departure and arrival times are parsed and stored
- Data is persisted in the local database
- Invalid or missing data is handled gracefully

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High

## Story 3: Calculate Turn-arounds

**Title:** As a user, I want to calculate possible turn-arounds from one airport to a destination and back.

**Description:**
The system should compute feasible round-trip itineraries (start → destination → return) considering travel time.

**Acceptance Criteria:**
- Algorithm considers flight durations between airports
- Turns are calculated excluding weekends (Sat/Sun not counted as days off)
- Start and end times are configurable
- Resulting itinerary is stored in the system

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High

## Story 4: Configure Days Off

**Title:** As a user, I want to configure which days are considered days off for turn-arounds.

**Description:**
Users can set which days (e.g., Saturday and Sunday) should not count as working days in turn-around calculations.

**Acceptance Criteria:**
- Days off are configurable per user or globally
- Turn-around calculation excludes configured days
- Changes take effect immediately

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Medium

## Story 5: Select Monitored Trips

**Title:** As a user, I want to select trips to monitor for price changes.

**Description:**
Users can choose which computed turn-arounds they want to track for price monitoring.

**Acceptance Criteria:**
- List of monitored trips is displayed in the UI
- Users can enable/disable monitoring per trip
- Selected trips are tracked for price changes

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Medium

## Story 6: Integrate Google Flight Scraper

**Title:** As a user, I want the system to use an open-source Google Flight Scraper to get real-time flight prices.

**Description:**
Implement integration with a maintained open-source scraper to fetch current flight prices.

**Acceptance Criteria:**
- Scraper runs daily (or configured interval)
- Flight prices are extracted and stored
- Scraper handles rate limits and errors gracefully
- Fallback mechanism if scraper fails

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High

## Story 7: Price Check Every 24 Hours

**Title:** As a user, I want the system to check flight prices for monitored trips every 24 hours.

**Description:**
Automated price monitoring runs daily to compare current prices with historical data.

**Acceptance Criteria:**
- Scheduler triggers price check daily
- Comparison against previous price stored in DB
- New price data is saved

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** High

## Story 8: Price History Chart

**Title:** As a user, I want to view a chart showing price history for each monitored trip.

**Description:**
Visualize the price trends of monitored turn-arounds over time.

**Acceptance Criteria:**
- Line chart shows price vs. date for each monitored trip
- Chart updates when new price data is available
- Clear visualization of price fluctuations

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Medium

## Story 9: Telegram Notifications

**Title:** As a user, I want to receive Telegram notifications when a monitored trip becomes cheaper than a predefined maximum price.

**Description:**
Integrate Telegram Bot API to send alerts when prices drop.

**Acceptance Criteria:**
- User sets maximum price threshold per trip
- Notification sent via Telegram when price falls below threshold
- Notification includes trip details and new price

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Low (optional feature)

## Story 10: Remove Monitoring

**Title:** As a user, I want to disable monitoring for a trip and remove its notification and price history.

**Description:**
Ability to unmonitor a trip, removing associated notifications and historical data.

**Acceptance Criteria:**
- Action removes trip from monitoring list
- Associated Telegram notifications are stopped
- Price history for the trip is cleared

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Medium

## Story 11: Remove Entire Airport

**Title:** As a user, I want to remove an entire airport from the system.

**Description:**
Deletion of an airport should remove all associated data (flights, trips, etc.).

**Acceptance Criteria:**
- Confirmation before deletion
- All related records are cleaned up
- No orphaned data remains

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Medium

## Story 12: Architecture Documentation

**Title:** As a developer, I want clear architectural documentation to guide implementation.

**Description:**
Create comprehensive architecture docs covering components, data flow, and technology choices.

**Acceptance Criteria:**
- Document describes all system components
- Data flow between components is clear
- Technology stack is specified
- Implementation roadmap is outlined

- Frontend input form validates and submits to backend API
- Backend stores validated code and returns confirmation to UI
- UI displays stored airport list with feedback

**Priority:** Low (foundational)

---

## Implementation Order (Recommended)

1. **Architecture Setup** - Docker compose, basic project structure
2. **Airport Management** - CRUD for airports
3. **Flight Scraper Integration** - Connect to Google Flight Scraper
4. **Turnaround Calculation** - Core algorithm for round trips
5. **Monitoring System** - Track and store trips
6. **Price Tracking** - Daily price checks
7. **Visualization** - Price charts
8. **Telegram Notifications** - Alert system
9. **Configuration** - Days off, thresholds, etc.
10. **Frontend** - UI for all features

Each story can be developed and tested independently, allowing incremental delivery.Test-Update: Filter, Next-Year-Only, TDD, REST-API (free), Google-Flight=prices only
## Story 13: Filter by Date

**Title:** As a user, I want to filter potential trips by date.

**Acceptance Criteria:**
- Date picker or date-range filter
- Only trips matching selected date shown

---

## Story 14: Visible Flight Prices

**Title:** As a user, I want to see trip prices as both single flight prices and combined price.

**Acceptance Criteria:**
- Each flight leg shows individual price
- Combined total price shown for turn-around
- Both prices visible in list and details

---

## Story 15: Save Trip Search Configurations

**Title:** As a user, I want to save my trip search settings under a name so I can reload them later.

**Description:**
On the Trips page the current search (start/end weekdays, latest departure time, earliest return departure time, min/max trip length) can be saved as a named configuration and reloaded at any time. Saved configurations are stored in the browser's local storage — not in the SQLite database. Airport selection and the date range are intentionally excluded from a configuration.

**Acceptance Criteria:**
- Only start/end weekdays, departure/return times and min/max trip length are saved
- Airport and earliest start / latest end dates are NOT part of a configuration (kept as-is on load)
- Every configuration has a name; duplicate names require an overwrite confirmation
- Configurations can be loaded and deleted (with confirmation)
- Data persists across page reloads in the same browser (localStorage), no backend/DB change

**Priority:** Medium
