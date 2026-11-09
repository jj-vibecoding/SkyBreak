// D2/D3: Responsive shell with single-state sidebar (drawer on mobile, static on desktop).
// D10: Toast provider + confirm dialog integration (replaces alert/confirm).
import React, { useEffect, useState } from 'react';
import { useMediaQuery, useIsLargeOrAbove } from './hooks/useMediaQuery';
import { ToastProvider, useConfirm } from './components/Dialogs';
import FlightsTab from './components/FlightsTab';
import TripsTab from './components/TripsTab';
import FavoriteTripPrices from './components/FavoriteTripPrices';
import SettingsTab from './components/SettingsTab';
import StatusTab from './components/StatusTab';
import { useActiveTab } from './hooks/useActiveTab';
import { useAirports } from './hooks/useAirports';

const NAV = [
  { key: 'favorites', label: 'Favorites', icon: '⭐' },
  { key: 'trips', label: 'Search Trips', icon: '🧳' },
  { key: 'flights', label: 'Flights', icon: '🛫' },
  { key: 'settings', label: 'Settings', icon: '⚙️' },
  { key: 'status', label: 'Status', icon: '📊' },
];

// Tab-specific header subtitles for compact mobile header (Fix #8)
const TAB_SUBTITLES = {
  favorites: 'Cheapest routes at a glance',
  flights: 'View & manage flight schedules',
  settings: 'Configure your dashboard',
  status: 'Health dashboard & backups',
};

// App shell: routing, responsive sidebar, and the shared airport list that the
// per-tab components consume. Each tab owns its own data + interactions.
// Fix #2/#3: Single state for sidebar visibility via useMediaQuery.
// Fix #12: Replaced all alert()/confirm() with toast/confirm dialogs.
// Fix #8: Compact tab header with title/subtitle.
// Fix #9: Responsive spacing + max-width content wrapper (D8).
export default function App() {
  const [tab, setTab] = useActiveTab(NAV);
  const isLarge = useIsLargeOrAbove(); // ≥1024px → desktop (static sidebar)
  const isMediumOrAbove = useMediaQuery('(min-width: 768px)');
  
  // Single source of truth: drawerOpen (only relevant when NOT large)
  const [drawerOpen, setDrawerOpen] = useState(false);
  
  const { list, setList, airportNames } = useAirports();
  const [scrapeRunning, setScrapeRunning] = useState(false);
  const { ConfirmDialog, showConfirm } = useConfirm();

  // Update drawer state when breakpoint changes (Fix #3: no more resize bug)
  useEffect(() => {
    if (isLarge) {
      setDrawerOpen(false); // Desktop: sidebar always visible
    }
    // Mobile: keep user's last choice (default closed)
  }, [isLarge]);

  // --- D3: ESC closes drawer + body scroll lock + safe-area-inset ---
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && !isLarge && drawerOpen) {
        setDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isLarge, drawerOpen]);

  useEffect(() => {
    if (!isLarge && drawerOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isLarge, drawerOpen]);

  // Poll the scraper status while it runs; stop once it finishes.
  useEffect(() => {
    const check = () => {
      fetch('/api/flights/scrape-status')
        .then(r => r.json())
        .then(d => {
          setScrapeRunning(!!d.running);
          if (d.running) setTimeout(check, 2000);
        })
        .catch(() => setScrapeRunning(false));
    };
    check();
  }, []);

  const handleFetchNow = async () => {
    try {
      const res = await fetch('/api/flights/fetch-now', { method: 'POST' });
      if (res.ok) {
        // Use toast instead of alert (Fix #12)
        window.dispatchEvent(new CustomEvent('showToast', { 
          detail: { message: 'Fetch started', type: 'info' } 
        }));
      }
    } catch {
      window.dispatchEvent(new CustomEvent('showToast', { 
        detail: { message: 'Failed to start fetch', type: 'error' } 
      }));
    }
  };

  const selectTab = (n) => {
    setTab(n.key);
    // Close drawer on mobile after navigation (Fix #2)
    if (!isLarge) setDrawerOpen(false);
    window.history.pushState({}, '', '/' + n.key);
  };

  // --- Render sidebar ---
  const renderSidebar = () => {
    // Desktop: fixed width 220. Mobile: expands when drawer is open.
    const sidebarWidth = isLarge ? 220 : (drawerOpen ? 270 : 0);
    return (
    <aside style={{
      flexShrink: 0,
      background: 'rgba(15,23,42,0.85)',
      backdropFilter: 'blur(12px)',
      borderRight: isLarge ? '1px solid rgba(255,255,255,0.06)' : (drawerOpen ? '1px solid rgba(255,255,255,0.08)' : 'none'),
      padding: '18px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      boxShadow: isLarge ? '4px 0 30px rgba(0,0,0,0.25)' : (drawerOpen ? '4px 0 30px rgba(0,0,0,0.4)' : 'none'),
      transition: 'width 0.3s ease, opacity 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease',
      opacity: isLarge ? 1 : (drawerOpen ? 1 : 0),
      overflow: 'hidden',
      zIndex: 999, // Above backdrop (998)
      position: 'fixed', // Never scroll with content — always fixed at viewport edge
      width: sidebarWidth,
      top: `calc(env(safe-area-inset-top, 0px))`,
      left: 0,
      height: '100dvh',
      // D3: Safe area inset for iPhone X+ notch/home bar
      paddingTop: isLarge ? 18 : `calc(18px + env(safe-area-inset-top, 0px))`,
      paddingBottom: isLarge ? 18 : `calc(18px + env(safe-area-inset-bottom, 0px))`,
      paddingLeft: isLarge ? 14 : `calc(14px + env(safe-area-inset-left, 0px))`,
      paddingRight: isLarge ? 14 : `calc(14px + env(safe-area-inset-right, 0px))`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28 }}>
        <div style={{
          width: 48, height: 48, borderRadius: 14,
          background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, boxShadow: '0 4px 15px rgba(56,189,248,0.35)'
        }}>✈️</div>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, letterSpacing: '-0.5px', fontWeight: 800, color: '#f8fafc' }}>SkyBreak</h1>
          <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>Travel Dashboard</span>
        </div>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {NAV.map(n => (
          <button key={n.key} onClick={() => selectTab(n)} style={{
            width: '100%', textAlign: 'left', padding: '12px 14px', borderRadius: 12, border: 'none',
            background: tab === n.key ? 'rgba(56,189,248,0.15)' : 'transparent',
            color: tab === n.key ? '#38bdf8' : '#cbd5e1', fontWeight: 600, fontSize: 15,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
            transition: 'all 0.2s ease', boxShadow: tab === n.key ? 'inset 0 0 0 1px rgba(56,189,248,0.35)' : 'none'
          }}>
            <span style={{ fontSize: 18 }}>{n.icon}</span>
            {n.label}
          </button>
        ))}
      </nav>

      <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
          SkyBreak v1.0 — Modern travel analytics
        </div>
      </div>
      </aside>
    );
  };

  // --- Render mobile drawer toggle button (Fix #2) ---
  const renderDrawerToggle = () => {
    if (isLarge) return null;
    // Hide when drawer is open so it doesn't overlap the logo area
    if (drawerOpen) return null;
    return (
      <button onClick={() => setDrawerOpen(o => !o)} aria-label="Toggle navigation" style={{
        position: 'fixed',
        top: 12,
        left: 12,
        zIndex: 1000,
        width: 44,
        height: 44,
        borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(15,23,42,0.9)',
        backdropFilter: 'blur(8px)',
        color: '#f8fafc',
        fontSize: 20,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        ☰
      </button>
    );
  };

  // --- Render mobile back-drop (Fix #2) ---
  const renderBackdrop = () => {
    if (isLarge || !drawerOpen) return null;
    return (
      <div onClick={() => setDrawerOpen(false)} style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        zIndex: 998,
      }} />
    );
  };

  return (
    <ToastProvider>
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        minHeight: '100dvh',
        fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        color: '#f1f5f9'
      }}>
        {renderDrawerToggle()}
        {renderSidebar()}
        {renderBackdrop()}

        {/* D8: Content wrapper with max-width */}
        <main style={{
          flex: 1,
          padding: isLarge ? 36 : (isMediumOrAbove ? 24 : 16),
          overflow: 'auto',
          maxWidth: '100%',
          zIndex: 1, // Must be above backdrop (998) on mobile
          marginLeft: isLarge ? 220 : 0, // Offset for fixed sidebar on desktop
        }}>
          <div style={{
            display: 'grid',
            gap: 24,
            gridTemplateColumns: '1fr',
            alignItems: 'start',
            maxWidth: isLarge ? '1400px' : '100%',
            margin: isLarge ? '0 auto' : '0',
          }}>
            {/* Compact header per tab (Fix #8) */}
            <div style={{ marginBottom: 8, marginLeft: isLarge ? 0 : 60 }}>
              <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#f8fafc' }}>
                {NAV.find(n => n.key === tab)?.label || ''}
              </h2>
              <span style={{ fontSize: 13, color: '#94a3b8' }}>
                {TAB_SUBTITLES[tab] || ''}
              </span>
            </div>

            {tab === 'trips' && <TripsTab list={list} airportNames={airportNames} />}

            {tab === 'favorites' && <FavoriteTripPrices />}

            {tab === 'flights' && (
              <FlightsTab list={list} setList={setList} onFetchNow={handleFetchNow} fetchRunning={scrapeRunning} />
            )}

            {tab === 'settings' && <SettingsTab />}

            {tab === 'status' && <StatusTab />}
          </div>
        </main>

        {/* D10: Confirm dialog rendered at app level */}
        <ConfirmDialog />
      </div>
    </ToastProvider>
  );
}
