# Local Storage Persistence Implementation

This document describes the local storage persistence feature that keeps UI state across page refreshes and browser sessions.

## Overview

The implementation adds browser-local persistence for UI preferences on the Trips and Favorites pages. Unlike the existing `useTripConfigs` hook (which stores search configurations on the server), this feature keeps UI state local to each browser.

## What Gets Persisted

### Trips Page (`TripsTab.js`)
- **Airport selections**: `startAirport`, `endAirport`
- **Date range**: `tripStart`, `tripEnd`
- **Weekday selections**: `startWeekdays`, `endWeekdays`
- **Search parameters**: `maxDepToDest`, `minRetDep`, `minTripDays`, `maxTripDays`

### Favorites Page (`FavoriteTripPrices.js`)
- **Filter dates**: `filterStart`, `filterEnd`
- **Sorting preferences**: `sortKey`, `sortDir`, `groupSortKey`, `groupSortDir`

## Implementation Details

### New Hook: `useLocalStorage`

Location: `frontend/src/hooks/useLocalStorage.js`

```javascript
export function useLocalStorage(key, defaultValue) {
  // Returns [storedValue, setValue] - works exactly like useState
  // but persists the value to localStorage automatically
}
```

### Key Features

1. **Namespace Prefix**: All keys are prefixed with `skybreak.` to prevent collisions
2. **Error Handling**: Gracefully handles localStorage errors
3. **Function Updaters**: Supports function updaters like `useState`
4. **JSON Serialization**: Automatically serializes/deserializes values

### Usage Pattern

```javascript
// Before (temporary state)
const [value, setValue] = useState(defaultValue);

// After (persistent state)
const [value, setValue] = useLocalStorage('component.value', defaultValue);
```

## Benefits

1. **User Experience**: Users don't lose their preferences when refreshing or navigating
2. **Performance**: No server round-trips for simple UI state
3. **Privacy**: Data stays in the browser, not on the server
4. **Compatibility**: Works offline and with multiple browser tabs

## Testing

Run the persistence tests:
```bash
pytest tests/test_local_storage_persistence.py -v
pytest tests/test_persistence_integration.py -v
```

## Migration Path

This implementation is backward compatible:
- If no value exists in localStorage, the default value is used
- Existing functionality remains unchanged
- No database migrations required

## Future Enhancements

Potential improvements:
1. Add TTL (time-to-live) for persisted values
2. Add encryption for sensitive data
3. Add size limits and cleanup mechanisms
4. Add sync between browser tabs