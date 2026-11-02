# Plan: Sort Favorite Trip Groups by Alphabetical or Price

## Current State (Bug / Gap)

The `FavoriteTripPrices` component already has top-level sort state (`sortKey`, `sortDir`) and computes a sorted array (line 36–54), but **this sorted array is never used for rendering**. The groups are always built from the raw `prices` array and displayed in alphabetical order by destination name (`Object.keys(groupsObj).sort()` on line 65). This means:

- The top-level sort controls (▲/▼ headers) have no effect on group ordering
- Groups can only appear alphabetically — there is no "sort by price" for the groups themselves
- The `sorted` variable at line 36–54 is dead code

## Goal

Allow the user to sort destination groups in the Favorite view either:
1. **Alphabetically** (by destination name) — current default behavior
2. **By price** — by cheapest trip within each group (ascending/descending)

## Implementation Plan

### 1. Backend (No changes needed)
The `/api/favorites` endpoint already returns the full list of favorite trips with all necessary fields (`destination_airport`, `dest_city_country`, `price_total`, etc.). No API changes required.

### 2. Frontend — FavoriteTripPrices.js

#### 2a. Add group sort state (lines ~9–10)
```js
const [groupSortKey, setGroupSortKey] = useState('name'); // 'name' | 'price_min' | 'price_avg'
const [groupSortDir, setGroupSortDir] = useState('asc');
```

#### 2b. Build groups respecting the sort order

Replace line 63–65:
```js
const groupsObj = {};
prices.forEach(p => { ... });
const groupKeys = Object.keys(groupsObj).sort();
```

With logic that:
1. Builds the same `groupsObj`
2. Converts keys to an array
3. Sorts by `groupSortKey` / `groupSortDir`:
   - `'name'` → alphabetical (current behavior)
   - `'price_min'` → cheapest trip in each group, nulls last
   - `'price_avg'` → average price per group, nulls last

#### 2c. Add a sort selector UI near the existing filter controls (line ~70)

Add a small control group:
```
[▼ Sort groups by] [Alphabetical | Price ↓ | Price ↑]
```

Or three buttons styled as a segmented control:
- "A→Z" (alphabetical asc)
- "Price ↑" (cheapest first)
- "Price ↓" (most expensive first)

This is simpler than a dropdown and fits the existing UI style.

#### 2d. Wire group sort into group rendering

Each group's `groupKeys.map(key => ...)` already renders correctly once `groupKeys` is sorted differently — no changes needed there.

### 3. Tests

Add an integration test in `tests/test_app_integration.py`:
- Verify the FavoriteTripPrices component accepts `groupSortKey` / `groupSortDir` props (or tests via DOM interaction)
- Verify that clicking sort buttons changes group order
- If no frontend testing framework exists (per memory: "Frontend has NO test framework"), add a manual smoke-test checklist instead

### 4. Files Modified

| File | Change |
|------|--------|
| `frontend/src/components/FavoriteTripPrices.js` | Add group sort state, compute sorted group keys, add UI controls |
| `tests/test_app_integration.py` | (optional) Add DOM-based or component test for group sorting |

### 5. Acceptance Criteria

- [ ] Groups default to alphabetical order (no behavior change for existing users)
- [ ] Clicking "Price ↑" reorders groups by cheapest trip ascending
- [ ] Clicking "Price ↓" reorders groups by cheapest trip descending
- [ ] Within-group sorting (origin, outbound, return, cost) continues to work independently
- [ ] Date filtering still works after group reordering
- [ ] No console errors or React warnings

## Implementation Order

1. **Frontend state** — add `groupSortKey` / `groupSortDir`
2. **Group sorting logic** — replace `Object.keys(groupsObj).sort()` with sorted-by-criteria logic
3. **UI controls** — add the sort selector buttons
4. **Verification** — `npm run build` passes, manual browser test

## Risks & Notes

- The existing `sorted` variable (line 36–54) is dead code and can be removed or repurposed. Recommend removing to avoid confusion.
- Group sort and within-group sort are independent concerns and should remain so (e.g., groups sorted by price, but within each group trips sorted alphabetically by origin).
