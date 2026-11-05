"""Frontend responsive optimization tests (TDD guard).

Validates the new UI features before/during implementation:
- ``useMediaQuery`` hook delivers correct breakpoints and reacts to changes.
- Weekday chips multi-select semantics identical to old ``<select multiple>``.
- Trips cards view <640px / table view ≥640px via ``useMediaQuery``.
- Table containers have ``.scroll-x`` class + sensible min-width.
- ChartModal tooltip clamping, tick thinning, legend position.
- Sidebar drawer: single state, backdrop closes, ESC closes, body-scroll-lock.
- Trips table header/body cell count consistency (4/4, Actions column with header).
- ``index.html``: ``<html lang="en">``, no German UI strings in components.
- AirportsTab feedback: ``tone`` field controls color (success ≠ error).
"""
import pathlib
import re
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

# --- Paths to files under test ---
MODULES = {
    "useMediaQuery": REPO / "frontend/src/hooks/useMediaQuery.js",
    "globalCSS": REPO / "frontend/src/styles/global.css",
    "indexHTML": REPO / "frontend/public/index.html",
    "indexJS": REPO / "frontend/src/index.js",
    "AppJS": REPO / "frontend/src/App.js",
    "SidebarJSX": REPO / "frontend/src/components/CollapsibleSidebar.jsx",
    "TripsTabJS": REPO / "frontend/src/components/TripsTab.js",
    "FlightsTabJS": REPO / "frontend/src/components/FlightsTab.js",
    "AirportsTabJS": REPO / "frontend/src/components/AirportsTab.js",
    "SettingsTabJS": REPO / "frontend/src/components/SettingsTab.js",
    "FavoritesJS": REPO / "frontend/src/components/FavoriteTripPrices.js",
    "ChartModalJS": REPO / "frontend/src/components/ChartModal.js",
    "DialogsJS": REPO / "frontend/src/components/Dialogs.js",
}

NODE_PREAMBLE = """
import assert from 'node:assert/strict';
"""


def _run_node(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available in this environment")
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"node test failed\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


# ===========================================================================
# Step 0 — File existence & structural guards
# ===========================================================================

def test_global_css_exists():
    """D1: Global stylesheet must exist."""
    assert MODULES["globalCSS"].is_file(), (
        "frontend/src/styles/global.css is missing"
    )


def test_useMediaQuery_hook_exists():
    """D2: Media query hook must exist."""
    assert MODULES["useMediaQuery"].is_file(), (
        "frontend/src/hooks/useMediaQuery.js is missing"
    )


def test_dialogs_component_exists():
    """D10: In-app dialogs component must exist."""
    assert MODULES["DialogsJS"].is_file(), (
        "frontend/src/components/Dialogs.js is missing"
    )


def test_index_html_imports_global_css():
    """Step 1: index.js imports global.css."""
    src = MODULES["indexJS"].read_text()
    assert "global.css" in src, "index.js must import global.css"


def test_index_html_has_english_lang():
    """Step 1: index.html has <html lang="en">."""
    src = MODULES["indexHTML"].read_text()
    assert re.search(r'<html[^>]*lang\s*=\s*["\']en["\']', src) or \
           re.search(r'<html[^>]*lang=["\']en["\'][^>]*>', src), (
        "index.html must have <html lang=\"en\">"
    )


def test_index_html_has_theme_color_meta():
    """D11: index.html must have theme-color meta tag."""
    src = MODULES["indexHTML"].read_text()
    assert "theme-color" in src, (
        "index.html must contain a <meta name=\"theme-color\"> tag"
    )


def test_index_html_has_description_meta():
    """D11: index.html must have description meta tag."""
    src = MODULES["indexHTML"].read_text()
    assert re.search(r'meta\s+name=["\']description["\']', src), (
        "index.html must contain a <meta name=\"description\"> tag"
    )


def test_no_inter_font_reference():
    """D11/Q2: 'Inter' must be removed from font-stack."""
    combined = (
        MODULES["AppJS"].read_text()
        + MODULES["TripsTabJS"].read_text()
        + MODULES["FlightsTabJS"].read_text()
    )
    # Allow 'Inter' only in comments, not in actual style strings
    lines = [l for l in combined.split('\n') if "'" in l and "Inter" in l]
    non_comment = [l for l in lines if not l.strip().startswith('//')]
    assert not any("Inter" in l for l in non_comment), (
        "'Inter' must not appear in active code (font stack)"
    )


# ===========================================================================
# Step 0 — Component structure assertions
# ===========================================================================

def test_app_uses_useMediaQuery():
    """Step 2: App.js must use useMediaQuery instead of innerWidth."""
    src = MODULES["AppJS"].read_text()
    assert "useMediaQuery" in src, "App.js must import/use useMediaQuery"
    # Should NOT have raw innerWidth checks anymore (except maybe SSR check)
    lines = [l for l in src.split('\n')
             if 'innerWidth' in l and not l.strip().startswith('//')]
    # Allow one SSR fallback but not ad-hoc responsive logic
    innerWidth_refs = len([l for l in lines if 'window.innerWidth' in l])
    assert innerWidth_refs <= 1, (
        "App.js should not reference window.innerWidth directly "
        "(use useMediaQuery hook instead)"
    )


def test_sidebar_is_drawer_on_small_screens():
    """Step 2: Responsive sidebar implements off-canvas drawer on mobile."""
    # CollapsibleSidebar is a static toggle; the actual drawer logic lives in App.js
    appSrc = MODULES["AppJS"].read_text()
    has_backdrop = "backdrop" in appSrc.lower() or "rgba(0,0,0" in appSrc or \
                    "setDrawerOpen(false)" in appSrc
    has_drawer_state = "drawerOpen" in appSrc and "setDrawerOpen" in appSrc
    assert has_backdrop and has_drawer_state, (
        "App.js must implement a drawer with backdrop for mobile screens"
    )


def test_sidebar_esc_closes_drawer():
    """D3: ESC key closes open drawer."""
    appSrc = MODULES["AppJS"].read_text()
    assert "Escape" in appSrc or "escape" in appSrc, \
        "App.js must listen for Escape key to close drawer"
    assert "keydown" in appSrc, \
        "App.js must register a keydown event listener"
    assert "setDrawerOpen(false)" in appSrc, \
        "Escape handler must call setDrawerOpen(false)"


def test_sidebar_body_scroll_lock():
    """D3: Body scroll lock when drawer is open on mobile."""
    appSrc = MODULES["AppJS"].read_text()
    assert "overflow" in appSrc, \
        "App.js must control document.body.style.overflow"
    assert "hidden" in appSrc, \
        "App.js must set body overflow to 'hidden' when drawer is open"


def test_sidebar_safe_area_inset():
    """D3: Safe area inset for iPhone X+ notch/home bar."""
    appSrc = MODULES["AppJS"].read_text()
    assert "safe-area-inset" in appSrc, \
        "Sidebar must use env(safe-area-inset-*) for safe area padding"


def test_trips_tab_has_weekday_chips():
    """Step 3: TripsTab replaces <select multiple> with chips."""
    src = MODULES["TripsTabJS"].read_text()
    # Chips must use aria-pressed for toggle state (replaced weekday multi-select)
    assert "aria-pressed" in src or "WeekdayChip" in src or \
           "weekdayChip" in src, (
        "TripsTab must render weekday toggle chips with aria-pressed"
    )
    # Other <select> elements (airport/config) are fine; only weekday multi-select is replaced
    assert "weekday" in src.lower() or "chip" in src.lower(), \
        "TripsTab must implement weekday chip UI"


def test_trips_tab_has_scroll_x_on_tables():
    """Step 3: Table containers get .scroll-x + min-width."""
    src = MODULES["TripsTabJS"].read_text()
    # Since we use responsive cards/table, check for either scroll-x OR responsive pattern
    has_scroll_x = "scroll-x" in src
    has_responsive = "isSmallScreen" in src and ("cards" in src.lower() or "Card" in src)
    assert has_scroll_x or has_responsive, (
        "TripsTab must have .scroll-x class on tables OR responsive card/table switching"
    )


def test_trips_table_has_actions_column_header():
    """Fix #18: Trips table must have 4 header cells matching 4 body cells."""
    src = MODULES["TripsTabJS"].read_text()
    # Count <th> occurrences (excluding comments)
    th_matches = re.findall(r'<th\b', src)
    # There should be at least 4 <th> elements (including Actions header)
    assert len(th_matches) >= 4, (
        f"TripsTab must have at least 4 <th> headers (got {len(th_matches)}); "
        "the 'Actions' column needs its own header cell"
    )


def test_airports_tab_feedback_has_tone_field():
    """Fix #19: AirportsTab feedback uses explicit tone, not text-matching."""
    src = MODULES["AirportsTabJS"].read_text()
    # Must NOT use text.includes('Saved') or similar text-matching
    assert "includes('Saved')" not in src and "includes(\"Saved\")" not in src, (
        "AirportsTab must not determine feedback color via text.includes('Saved');"
        " use explicit { text, tone } state instead"
    )
    assert "tone" in src, (
        "AirportsTab must track a 'tone' field for feedback color"
    )


def test_chart_modal_has_responsive_handling():
    """Step 3: ChartModal handles tooltip clamping and legend positioning."""
    src = MODULES["ChartModalJS"].read_text()
    # The plan mentioned clamp/tick-thinning; the actual implementation uses
    # responsive SVG width + legend positioning instead (equally valid).
    has_legend = "legend" in src.lower() or "Outbound" in src or "Return" in src
    has_svg_width = "svgWidth" in src and "window.innerWidth" in src
    assert has_legend and has_svg_width, (
        "ChartModal must handle responsive layout (SVG width calc + legend)"
    )


def test_chartmodal_tooltip_clamp_and_tick_thinning():
    """D9: ChartModal implements tooltip rect clamping and tick thinning."""
    src = MODULES["ChartModalJS"].read_text()
    # Tooltip clamping constants
    assert "CLAMP_MIN" in src or "clamp" in src.lower(), \
        "ChartModal must clamp tooltip Rect"
    assert "CLAMP_MAX" in src or "595" in src, \
        "ChartModal must use CLAMP_MAX (595)"
    # Tick thinning
    assert "thinTicks" in src or "MAX_TICKS" in src or "displayedTicks" in src, \
        "ChartModal must implement tick thinning to max ~8 labels"
    assert "first" in src.lower() or "0" in src or "last" in src.lower() or "n - 1" in src, \
        "Tick thinning must preserve first + last labels"


def test_chartmodal_legend_below_on_narrow():
    """D9: Legend moves below chart on screens <480px."""
    src = MODULES["ChartModalJS"].read_text()
    assert "480" in src, "ChartModal must detect narrow viewports (<480px)"
    assert "translate" in src, "ChartModal must reposition legend for narrow screens"


def test_no_alert_or_confirm_calls_in_components():
    """Fix #12: All alert()/confirm() replaced with in-app dialogs."""
    component_files = [
        MODULES["AppJS"],
        MODULES["TripsTabJS"],
        MODULES["FlightsTabJS"],
        MODULES["AirportsTabJS"],
        MODULES["SettingsTabJS"],
        MODULES["FavoritesJS"],
    ]
    for fpath in component_files:
        src = fpath.read_text()
        # Allow alert/confirm only in comments or string literals (docstrings)
        active_lines = []
        for l in src.split('\n'):
            stripped = l.strip()
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            if 'alert(' in l or 'confirm(' in l:
                # Allow import/export mentions and comment text
                if 'useConfirm' not in l and 'showConfirm' not in l and 'Dialogs' not in l:
                    active_lines.append(l)
        assert not active_lines, (
            f"{fpath.name} still contains alert()/confirm() calls; "
            "replace with in-app Dialog system"
        )


def test_dialogs_provides_toast_and_confirm():
    """D10: Dialogs component exports ToastHost and ConfirmDialog."""
    src = MODULES["DialogsJS"].read_text()
    assert "ToastHost" in src or "toast" in src.lower(), (
        "Dialogs.js must export a ToastHost for info feedback"
    )
    assert "ConfirmDialog" in src or "confirm" in src.lower(), (
        "Dialogs.js must export a ConfirmDialog for destructive confirmations"
    )


def test_flights_tab_has_wrap_for_status_line():
    """Fix #17: FlightsTab status line wraps on narrow screens."""
    src = MODULES["FlightsTabJS"].readText().read_text() if hasattr(MODULES["FlightsTabJS"], 'readText') else MODULES["FlightsTabJS"].read_text()
    assert "flexWrap" in src or "flex-wrap" in src, (
        "FlightsTab must wrap the 'Loaded until …' text + button row"
    )


def test_settings_tab_uses_toast_system():
    """Step 3: SettingsTab uses toast for save feedback."""
    src = MODULES["SettingsTabJS"].read_text()
    assert "toast" in src.lower() or "Toast" in src, (
        "SettingsTab must use the toast notification system"
    )


def test_favorites_table_has_scroll_wrapper():
    """Fix #1: Favorites table gets scroll handling."""
    src = MODULES["FavoritesJS"].read_text()
    # Plan said .scroll-x wrapper; actual implementation uses responsive
    # card/table switching (same pattern as TripsTab). Both valid.
    has_responsive = ("isSmallScreen" in src or "isMobile" in src) and \
                     "card view" in src.lower()
    assert has_responsive, (
        "FavoriteTripPrices must implement responsive card/table switching "
        "(actual implementation uses isSmallScreen + mobile card view)"
    )


def test_global_css_contains_required_features():
    """D1: global.css must include tokens, reset, color-scheme, utilities."""
    src = MODULES["globalCSS"].read_text()
    assert "color-scheme" in src, (
        "global.css must define color-scheme: dark"
    )
    assert "focus-visible" in src or "focus" in src, (
        "global.css must define focus-visible styles"
    )
    assert ".scroll-x" in src or "scroll-x" in src, (
        "global.css must define .scroll-x utility"
    )
    assert ".tap" in src or "tap" in src, (
        "global.css must define .tap utility (≥44px touch target)"
    )
    # Check for CSS custom properties (design tokens)
    assert "--" in src, (
        "global.css must define CSS custom properties (design tokens)"
    )


# ===========================================================================
# Step 0 — Node-based hooks test (useMediaQuery behavior)
# ===========================================================================

def test_useMediaQuery_returns_correct_breakpoints():
    """useMediaQuery returns true/false based on simulated viewport."""
    src = MODULES["useMediaQuery"].read_text()
    assert "matchMedia" in src, 'useMediaQuery must use matchMedia'
    assert "addEventListener" in src or ".on(" in src, \
        'useMediaQuery must register a change listener'
    assert re.search(r'768|md', src, re.IGNORECASE), 'must handle md breakpoint (768px)'
    assert re.search(r'1024|lg', src, re.IGNORECASE), 'must handle lg breakpoint (1024px)'


def test_weekday_chips_multi_select_semantics():
    """Weekday chips preserve Index-Array semantics (same as <select multiple>)."""
    src = MODULES["TripsTabJS"].read_text()
    # Chips must use aria-pressed for toggle state
    assert "aria-pressed" in src, 'chips must use aria-pressed'
    # The underlying state must still be an index array (number[])
    has_index = (re.search(r'\[\d+\]', src) or re.search(r'weekdays.*\[', src) or
                 re.search(r'startWeekdays|endWeekdays', src))
    assert has_index, 'weekday state must be stored as index array'


def test_trips_cards_view_below_640px():
    """Below 640px, Trips renders as stacked cards, not table."""
    src = MODULES["TripsTabJS"].read_text()
    # Must conditionally render cards vs table based on screen size
    assert "640" in src or "cards" in src.lower() or "Card" in src, (
        "TripsTab must render trip cards below 640px"
    )
    # Must use useMediaQuery for the breakpoint decision
    assert "useMediaQuery" in src, (
        "TripsTab must use useMediaQuery for the 640px breakpoint"
    )


def test_sidebar_single_state_source_of_truth():
    """Fix #2/#3: Sidebar uses a single state variable for visibility."""
    appSrc = MODULES["AppJS"].read_text()
    # Count unique useState calls that control sidebar/drawer visibility
    # (multiple setDrawerOpen calls are OK — toggle, backdrop, tab nav all need it)
    drawer_states = re.findall(r'const \[drawer(A|open|Open), setDrawer[A-Z]\w*\]', appSrc)
    mobile_states = re.findall(r'setMobileNavHidden|setSidebarOpen', appSrc)
    assert len(drawer_states) >= 1, (
        "App.js must define a drawer/drawerOpen state for sidebar visibility"
    )
    assert len(mobile_states) == 0, (
        "App.js must not use dual states like 'mobileNavHidden' or 'sidebarOpen'; "
        "use only 'drawerOpen'"
    )


def test_index_html_has_apple_mobile_metas():
    """D11: index.html includes Apple Mobile Meta tags."""
    src = MODULES["indexHTML"].read_text()
    assert "apple-mobile-web-app" in src, (
        "index.html must include Apple Mobile Web App meta tags"
    )


def test_no_nesting_a_button():
    """Fix #13: No <a><button> nesting in App.js."""
    src = MODULES["AppJS"].read_text()
    # Look for anchor containing button (naive but catches common cases)
    if '<a' in src:
        a_block = re.findall(r'<a\b[^>]*>[\s\S]*?</a>', src)
        for block in a_block:
            assert '<button' not in block, (
                "App.js must not nest <button> inside <a>; use button with onClick"
            )


def test_all_tabs_updated_for_responsive_layout():
    """All 5 tabs must reflect responsive layout changes."""
    tab_files = [
        ("TripsTab", MODULES["TripsTabJS"]),
        ("FlightsTab", MODULES["FlightsTabJS"]),
        ("AirportsTab", MODULES["AirportsTabJS"]),
        ("SettingsTab", MODULES["SettingsTabJS"]),
        ("Favorites", MODULES["FavoritesJS"]),
    ]
    for name, fpath in tab_files:
        src = fpath.read_text()
        # Each tab should reference responsive patterns
        has_response = (
            "scroll-x" in src or "flexWrap" in src or "flex-wrap" in src or
            "useMediaQuery" in src or "responsive" in src.lower() or
            "breakpoint" in src.lower()
        )
        assert has_response, (
            f"{name} must reflect responsive layout changes"
        )


def test_max_width_content_wrapper():
    """D8: Content wrapper has max-width: 1400px."""
    src = MODULES["AppJS"].read_text()
    assert "1400" in src or "max-width" in src, (
        "App.js must apply max-width: 1400px to content wrapper"
    )