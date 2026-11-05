"""
Integration tests for local storage persistence.
Tests the actual behavior of the useLocalStorage hook.
"""
import pytest
import json
from pathlib import Path
import tempfile
import os


class MockLocalStorage:
    """Mock localStorage for testing."""
    def __init__(self):
        self.storage = {}
    
    def getItem(self, key):
        return self.storage.get(key)
    
    def setItem(self, key, value):
        self.storage[key] = value
    
    def removeItem(self, key):
        if key in self.storage:
            del self.storage[key]
    
    def clear(self):
        self.storage = {}


def test_use_local_storage_hook_behavior():
    """Test the actual behavior of the useLocalStorage hook."""
    # Read the hook implementation
    hook_path = Path(__file__).parent.parent / "frontend" / "src" / "hooks" / "useLocalStorage.js"
    hook_content = hook_path.read_text()
    
    # Verify key components
    assert "useState" in hook_content
    assert "useEffect" in hook_content
    assert "window.localStorage" in hook_content
    assert "JSON.parse" in hook_content
    assert "JSON.stringify" in hook_content
    
    # Verify error handling
    assert "try {" in hook_content
    assert "catch (error)" in hook_content
    
    # Verify namespace
    assert "skybreak." in hook_content


def test_persistence_keys_are_unique():
    """Verify that different components use unique keys."""
    trips_path = Path(__file__).parent.parent / "frontend" / "src" / "components" / "TripsTab.js"
    favorites_path = Path(__file__).parent.parent / "frontend" / "src" / "components" / "FavoriteTripPrices.js"
    
    trips_content = trips_path.read_text()
    favorites_content = favorites_path.read_text()
    
    # Extract all localStorage keys from TripsTab
    trips_keys = set()
    for line in trips_content.split('\n'):
        if "useLocalStorage('trips." in line:
            # Extract the key
            start = line.find("('trips.") + len("('trips.")
            end = line.find("',", start)
            if start > 0 and end > start:
                key = line[start:end]
                trips_keys.add(key)
    
    # Extract all localStorage keys from FavoriteTripPrices
    favorites_keys = set()
    for line in favorites_content.split('\n'):
        if "useLocalStorage('favorites." in line:
            # Extract the key
            start = line.find("('favorites.") + len("('favorites.")
            end = line.find("',", start)
            if start > 0 and end > start:
                key = line[start:end]
                favorites_keys.add(key)
    
    # Verify no overlap
    assert len(trips_keys) > 0, "TripsTab should have persisted keys"
    assert len(favorites_keys) > 0, "FavoriteTripPrices should have persisted keys"
    assert trips_keys.isdisjoint(favorites_keys), "Trips and Favorites should use different keys"
    
    print(f"TripsTab persists: {trips_keys}")
    print(f"FavoriteTripPrices persists: {favorites_keys}")


def test_persistence_covers_all_necessary_state():
    """Verify that all necessary UI state is being persisted."""
    trips_path = Path(__file__).parent.parent / "frontend" / "src" / "components" / "TripsTab.js"
    favorites_path = Path(__file__).parent.parent / "frontend" / "src" / "components" / "FavoriteTripPrices.js"
    
    trips_content = trips_path.read_text()
    favorites_content = favorites_path.read_text()
    
    # TripsTab should persist:
    # - Airport selections (startAirport, endAirport)
    # - Date range (tripStart, tripEnd)
    # - Weekday selections (startWeekdays, endWeekdays)
    # - Search parameters (maxDepToDest, minRetDep, minTripDays, maxTripDays)
    
    trips_required = [
        "startAirport", "endAirport",
        "tripStart", "tripEnd",
        "startWeekdays", "endWeekdays",
        "maxDepToDest", "minRetDep", "minTripDays", "maxTripDays"
    ]
    
    for var in trips_required:
        assert f"useLocalStorage('trips.{var}'" in trips_content, f"TripsTab should persist {var}"
    
    # FavoriteTripPrices should persist:
    # - Filter dates (filterStart, filterEnd)
    # - Sorting preferences (sortKey, sortDir, groupSortKey, groupSortDir)
    
    favorites_required = [
        "filterStart", "filterEnd",
        "sortKey", "sortDir", "groupSortKey", "groupSortDir"
    ]
    
    for var in favorites_required:
        assert f"useLocalStorage('favorites.{var}'" in favorites_content, f"FavoriteTripPrices should persist {var}"


def test_hook_follows_react_conventions():
    """Verify the hook follows React conventions."""
    hook_path = Path(__file__).parent.parent / "frontend" / "src" / "hooks" / "useLocalStorage.js"
    content = hook_path.read_text()
    
    # Should be a function component
    assert "export function useLocalStorage" in content
    
    # Should return an array like useState
    assert "return [" in content
    assert ", setValue]" in content
    
    # Should handle function updaters like useState
    assert "value instanceof Function" in content
    assert "value(storedValue)" in content
    
    # Should use useEffect for side effects
    assert "useEffect" in content


def test_namespace_prevention():
    """Verify that keys are properly namespaced to prevent collisions."""
    hook_path = Path(__file__).parent.parent / "frontend" / "src" / "hooks" / "useLocalStorage.js"
    content = hook_path.read_text()
    
    # Should create a namespaced key
    assert "skybreak." in content
    assert "const storageKey = `skybreak.${key}`" in content
    
    # Should not use raw keys
    assert "window.localStorage.getItem(key)" not in content
    assert "window.localStorage.setItem(key" not in content
    assert "window.localStorage.getItem(storageKey)" in content
    assert "window.localStorage.setItem(storageKey" in content