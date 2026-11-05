"""
Test local storage persistence for Trips and Favorites pages.
"""
import pytest
import json
from pathlib import Path


@pytest.fixture
def frontend_dir():
    """Path to the frontend directory."""
    return Path(__file__).parent.parent / "frontend"


def test_use_local_storage_hook_exists(frontend_dir):
    """Verify the useLocalStorage hook file exists."""
    hook_path = frontend_dir / "src" / "hooks" / "useLocalStorage.js"
    assert hook_path.exists(), "useLocalStorage.js hook should exist"
    
    content = hook_path.read_text()
    assert "useLocalStorage" in content
    assert "localStorage" in content
    assert "JSON.parse" in content
    assert "JSON.stringify" in content


def test_trips_tab_uses_local_storage(frontend_dir):
    """Verify TripsTab component uses local storage for persistence."""
    trips_path = frontend_dir / "src" / "components" / "TripsTab.js"
    content = trips_path.read_text()
    
    # Check imports
    assert "useLocalStorage" in content
    
    # Check that key state variables are persisted
    persisted_vars = [
        "startAirport",
        "endAirport", 
        "tripStart",
        "tripEnd",
        "startWeekdays",
        "endWeekdays",
        "maxDepToDest",
        "minRetDep",
        "maxTripDays",
        "minTripDays"
    ]
    
    for var in persisted_vars:
        assert f"useLocalStorage('trips.{var}'" in content, f"{var} should be persisted in localStorage"


def test_favorites_tab_uses_local_storage(frontend_dir):
    """Verify FavoriteTripPrices component uses local storage for persistence."""
    favorites_path = frontend_dir / "src" / "components" / "FavoriteTripPrices.js"
    content = favorites_path.read_text()
    
    # Check imports
    assert "useLocalStorage" in content
    
    # Check that key state variables are persisted
    persisted_vars = [
        "sortKey",
        "sortDir",
        "groupSortKey",
        "groupSortDir",
        "filterStart",
        "filterEnd"
    ]
    
    for var in persisted_vars:
        assert f"useLocalStorage('favorites.{var}'" in content, f"{var} should be persisted in localStorage"


def test_local_storage_hook_api(frontend_dir):
    """Test the API of the useLocalStorage hook."""
    hook_path = frontend_dir / "src" / "hooks" / "useLocalStorage.js"
    content = hook_path.read_text()
    
    # Check export
    assert "export function useLocalStorage" in content
    
    # Check it returns an array like useState
    assert "return [storedValue, setValue]" in content
    
    # Check it handles functions like useState
    assert "value instanceof Function" in content
    
    # Check error handling
    assert "try {" in content
    assert "catch (error)" in content
    assert "console.error" in content


def test_local_storage_key_namespace(frontend_dir):
    """Verify that local storage keys are properly namespaced."""
    hook_path = frontend_dir / "src" / "hooks" / "useLocalStorage.js"
    content = hook_path.read_text()
    
    # Check namespace prefix
    assert "skybreak." in content
    assert "const storageKey = `skybreak.${key}`" in content


def test_helper_function_exists(frontend_dir):
    """Verify the helper function for objects exists."""
    hook_path = frontend_dir / "src" / "hooks" / "useLocalStorage.js"
    content = hook_path.read_text()
    
    assert "useLocalStorageObject" in content
    assert "setObjectValue" in content
    assert "...prev || {}" in content  # Spread operator for merging objects