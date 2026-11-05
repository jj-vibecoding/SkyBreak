def _read(path):
    with open(path) as f:
        return f.read()


def test_app_js_wires_decomposition():
    app = _read("frontend/src/App.js")
    # App is now a thin shell: it composes the per-tab components + hooks instead
    # of holding all state itself. CollapsibleSidebar was replaced by the
    # responsive drawer (D3) implemented directly in App.js.
    for name in ["AirportsTab", "FlightsTab",
                 "TripsTab", "FavoriteTripPrices", "SettingsTab", "StatusTab"]:
        assert f"import {name}" in app, f"App.js must import {name}"
    assert "from './hooks/useActiveTab'" in app
    assert "from './hooks/useAirports'" in app
    # Layout may be imported as a wrapper component (responsive optimization);
    # verify it's used correctly per-tab rather than dead code.
    if "import Layout" in app:
        assert 'Layout title=' in app or "Layout title=" in app, \
            "Layout must be used as per-tab wrapper, not unused dead code"


def test_chartmodal_lives_with_favorites():
    # ChartModal moved into the Favorites tab component during the decomposition.
    fav = _read("frontend/src/components/FavoriteTripPrices.js")
    assert "import ChartModal" in fav
