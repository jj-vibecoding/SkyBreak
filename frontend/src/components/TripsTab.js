// D4/D5/D12: Responsive TripsTab — weekday chips (Fix #4),
//        trip cards <640px / table ≥640px (Fix #5), Actions header (Fix #18),
//        toast/confirm dialogs (Fix #12), English UI (Fix #16).
//        On-demand price quotes for candidate trips (Fix #24).
import React, { useState, useEffect, useCallback } from 'react';
import { formatTripDateTime } from '../utils/format';
import { useTripConfigs } from '../hooks/useTripConfigs';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { useConfirm } from './Dialogs';
import { useLocalStorage } from '../hooks/useLocalStorage';

const sectionStyle = {
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 18, padding: 24, boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
};

const fieldStyle = {
  background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 16,
  border: '1px solid rgba(255,255,255,0.06)',
};
const controlStyle = {
  width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)',
  background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontSize: 14,
  boxSizing: 'border-box', maxWidth: '100%',
};
const chipActiveStyle = {
  padding: '8px 14px', borderRadius: 8, border: '1px solid rgba(56,189,248,0.4)',
  background: 'rgba(56,189,248,0.15)', color: '#38bdf8', fontWeight: 700, fontSize: 13,
  cursor: 'pointer', minWidth: 44, minHeight: 44,
};
const chipInactiveStyle = {
  padding: '8px 14px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)',
  background: 'rgba(255,255,255,0.06)', color: '#cbd5e1', fontWeight: 600, fontSize: 13,
  cursor: 'pointer', minWidth: 44, minHeight: 44,
};
const saveButtonStyle = {
  padding: '8px 14px', borderRadius: 8, border: 'none', background: '#10b981',
  color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
};
const loadButtonStyle = {
  padding: '8px 14px', borderRadius: 8, border: 'none', background: '#38bdf8',
  color: '#0f172a', fontWeight: 700, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
};
const deleteButtonStyle = {
  padding: '8px 14px', borderRadius: 8, border: 'none', background: '#ef4444',
  color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
};
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

function payloadFromTurnaround(t, startAirport) {
  return JSON.stringify({
    trip_date: t.hinflug_abflug_zeit ? t.hinflug_abflug_zeit.split(' ')[0] : '',
    outbound_trip_date: t.hinflug_abflug_zeit ? t.hinflug_abflug_zeit.split(' ')[0] : '',
    return_trip_date: t.rueckflug_abflug_zeit ? t.rueckflug_abflug_zeit.split(' ')[0] : '',
    start_time: t.hinflug_abflug_zeit ? t.hinflug_abflug_zeit.split(' ')[1] || '' : '',
    destination_airport: t.destination || t.hinflug_ziel || '',
    outbound_flight_number: t.hinflug_flight_number || '',
    return_flight_number: t.rueckflug_flight_number || '',
    start_airport: startAirport || '',
    return_time: t.rueckflug_abflug_zeit ? t.rueckflug_abflug_zeit.split(' ')[1] || '' : '',
  });
}

// Trip turnaround finder: date-range / weekday form plus grouped results, with
// add-to-favorites. `list`/`airportNames` are the shared airport data.
export default function TripsTab({ list, airportNames }) {
  const isSmallScreen = useMediaQuery('(max-width: 639px)'); // Fix #5: cards below 640px
  const { showConfirm, ConfirmDialog } = useConfirm(); // Fix #12: replace window.confirm
  
  // Persist UI state in localStorage
  const [startAirport, setStartAirport] = useLocalStorage('trips.startAirport', '');
  const [endAirport, setEndAirport] = useLocalStorage('trips.endAirport', '');
  const [tripStart, setTripStart] = useLocalStorage('trips.tripStart', new Date().toISOString().split('T')[0]);
  const [tripEnd, setTripEnd] = useLocalStorage('trips.tripEnd', new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0]);
  const [startWeekdays, setStartWeekdays] = useLocalStorage('trips.startWeekdays', [4]);
  const [endWeekdays, setEndWeekdays] = useLocalStorage('trips.endWeekdays', [6]);
  const [maxDepToDest, setMaxDepToDest] = useLocalStorage('trips.maxDepToDest', '18:00');
  const [minRetDep, setMinRetDep] = useLocalStorage('trips.minRetDep', '10:00');
  const [maxTripDays, setMaxTripDays] = useLocalStorage('trips.maxTripDays', 5);
  const [minTripDays, setMinTripDays] = useLocalStorage('trips.minTripDays', 1);
  
  const [turnarounds, setTurnarounds] = useState([]);
  const [expanded, setExpanded] = useState({});
  const toggle = (k) => setExpanded(e => ({ ...e, [k]: !e[k] }));

  // On-demand price quote state: key → {status, prices, fetched_at}
  // Key = 'start|dest|out_date|ret_date|out_fnum|ret_fnum'
  const [quotes, setQuotes] = useState({});
  const quoteKey = (t) => `${startAirport || ''}|${t.hinflug_ziel || t.destination || ''}|${(t.hinflug_abflug_zeit || '').split(' ')[0]}|${(t.rueckflug_abflug_zeit || '').split(' ')[0]}|${t.hinflug_flight_number || ''}|${t.rueckflug_flight_number || ''}`;

  const fetchQuote = useCallback(async (t) => {
    const key = quoteKey(t);
    setQuotes(prev => ({ ...prev, [key]: { status: 'loading' } }));
    try {
      const res = await fetch('/api/prices/quote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_airport: startAirport || '',
          destination_airport: t.hinflug_ziel || t.destination || '',
          outbound_date: (t.hinflug_abflug_zeit || '').split(' ')[0] || '',
          return_date: (t.rueckflug_abflug_zeit || '').split(' ')[0] || '',
          outbound_flight_number: t.hinflug_flight_number || '',
          return_flight_number: t.rueckflug_flight_number || '',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setQuotes(prev => ({ ...prev, [key]: { status: 'error', error: err.error || `HTTP ${res.status}` } }));
        return;
      }
      const data = await res.json();
      setQuotes(prev => ({ ...prev, [key]: { status: 'done', ...data } }));
    } catch (e) {
      setQuotes(prev => ({ ...prev, [key]: { status: 'error', error: e.message } }));
    }
  }, [startAirport]);

  function formatPrice(v) { return v != null ? `€${Math.round(v)}` : '–'; }
  function relativeAge(ts) {
    if (!ts) return '';
    try {
      const diff = (Date.now() - new Date(ts + 'Z').getTime()) / 60000; // minutes
      if (diff < 1) return 'just now';
      if (diff < 60) return `${Math.round(diff)}m ago`;
      return `${Math.round(diff / 60)}h ago`;
    } catch { return ''; }
  }

  // Saved search configs live in the server DB (shared by every browser);
  // they never include the airport selection or the date range.
  const { configs: savedConfigs, loading: configsLoading, error: configsError, saveConfig, removeConfig } = useTripConfigs();
  const [configName, setConfigName] = useState('');
  const [selectedConfig, setSelectedConfig] = useState('');
  const [configMessage, setConfigMessage] = useState('');

  const currentSearch = {
    startWeekdays, endWeekdays, maxDepToDest, minRetDep, minTripDays, maxTripDays,
  };

  const handleSaveConfig = async () => {
    if (!configName.trim()) { setConfigMessage('Please enter a name for the configuration.'); return; }
    if (startWeekdays.length === 0 || endWeekdays.length === 0) {
      setConfigMessage('Select at least one start and one end weekday before saving.');
      return;
    }
    const existing = savedConfigs.find(c => c.name.toLowerCase() === configName.trim().toLowerCase());
    if (existing) {
      const ok = await showConfirm('Overwrite Configuration?', `Configuration "${configName.trim()}" already exists. Overwrite it?`);
      if (!ok) {
        setConfigMessage('Overwrite cancelled — nothing was saved.');
        return;
      }
    }
    const result = await saveConfig({ name: configName.trim(), ...currentSearch });
    if (result.ok) {
      setSelectedConfig(result.name);
      setConfigName('');
      setConfigMessage(`Configuration "${result.name}" saved — visible in every browser.`);
    } else {
      setConfigMessage(result.error || 'Could not save the configuration.');
    }
  };

  const handleLoadConfig = () => {
    const config = savedConfigs.find(c => c.name === selectedConfig);
    if (!config) { setConfigMessage('Select a configuration to load.'); return; }
    setStartWeekdays(config.startWeekdays);
    setEndWeekdays(config.endWeekdays);
    if (config.maxDepToDest) setMaxDepToDest(config.maxDepToDest);
    if (config.minRetDep) setMinRetDep(config.minRetDep);
    if (config.minTripDays) setMinTripDays(config.minTripDays);
    if (config.maxTripDays) setMaxTripDays(config.maxTripDays);
    // Airport and date range are intentionally NOT part of a configuration.
    setConfigMessage(`Loaded "${config.name}" — airport and dates kept as they were.`);
  };

  const handleDeleteConfig = async () => {
    if (!selectedConfig) { setConfigMessage('Select a configuration to delete.'); return; }
    const ok = await showConfirm('Delete Configuration', `Delete configuration "${selectedConfig}"?`);
    if (!ok) { setConfigMessage('Delete cancelled.'); return; }
    const result = await removeConfig(selectedConfig);
    setSelectedConfig('');
    setConfigMessage(result.ok
      ? `Configuration "${selectedConfig}" deleted.`
      : (result.error || 'Could not delete the configuration.'));
  };

  useEffect(() => {
    if (tripStart && tripEnd && startWeekdays.length > 0 && endWeekdays.length > 0 && maxDepToDest && minRetDep) {
      const params = new URLSearchParams({
        start: tripStart, end: tripEnd,
        start_days: startWeekdays.join(','), end_days: endWeekdays.join(','),
        max_dep_dest: maxDepToDest, min_ret_dep: minRetDep,
        max_trip_days: maxTripDays || 30, min_trip_days: minTripDays || 1,
      });
      if (startAirport) params.append('start_airport', startAirport);
      if (endAirport) params.append('end_airport', endAirport);
      fetch('/api/turnarounds?' + params.toString())
        .then(r => r.json())
        .then(data => setTurnarounds(data.turnarounds || data.results || []))
        .catch(() => setTurnarounds([]));
    }
  }, [tripStart, tripEnd, startWeekdays, endWeekdays, maxDepToDest, minRetDep, startAirport, endAirport, maxTripDays, minTripDays]);

  const addFavorite = async (t) => {
    const res = await fetch('/api/favorites', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: payloadFromTurnaround(t, startAirport),
    });
    if (res.ok) {
      const idx = turnarounds.indexOf(t);
      if (idx >= 0) {
        const copy = [...turnarounds];
        copy[idx] = { ...copy[idx], is_favorite: true };
        setTurnarounds(copy);
      }
    }
  };

  const addAllFavorites = async (group) => {
    const ok = await showConfirm('Add to Favorites', 'Add all trips in this group to favorites?');
    if (!ok) return;
    for (const t of group) await addFavorite(t);
  };

  const groups = {};
  turnarounds.forEach(t => { const key = t.hinflug_ziel || t.destination || '-'; if (!groups[key]) groups[key] = []; groups[key].push(t); });
  const groupKeys = Object.keys(groups).sort();

  // Fix #4: Weekday chips replacing <select multiple>
  const renderChips = (label, value, onChange) => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {WEEKDAYS.map((day, i) => {
        const isActive = value.includes(i);
        return (
          <button key={i} onClick={() => onChange(isActive ? value.filter(v => v !== i) : [...value, i])}
            style={isActive ? chipActiveStyle : chipInactiveStyle} aria-pressed={isActive}>
            {day.slice(0, 3)}
          </button>
        );
      })}
    </div>
  );

  // On mobile: completely flat layout — no borderRadius anywhere.
  // iOS Safari clips rendering of nested border-radius values causing visual bleed.
  // Removing all rounded corners on mobile eliminates the artifact entirely.
  const sectionStyleFlat = isSmallScreen
    ? { ...sectionStyle, borderRadius: 0 }
    : sectionStyle;

  const fieldBoxStyle = (p) => ({
    background: 'rgba(255,255,255,0.03)',
    borderRadius: 0,
    padding: p != null ? p : (isSmallScreen ? 12 : 16),
    border: isSmallScreen ? 'none' : '1px solid rgba(255,255,255,0.06)',
  });

  return (
    <section style={{ ...sectionStyleFlat, padding: isSmallScreen ? 14 : 24 }}>
      <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 18 }}>Find possible trip combinations based on date ranges and weekday preferences.</p>
      <div style={{ display: 'grid', gridTemplateColumns: isSmallScreen ? '1fr' : 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 18 }}>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Airport (Start & End)</label>
          <select value={startAirport} onChange={e => { setStartAirport(e.target.value); setEndAirport(e.target.value); }}
            style={{ ...controlStyle, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            <option value="">Select airport</option>
            {list.map(c => <option key={c} value={c} style={{ color: '#0f172a', background: '#f8fafc' }}>{c}{airportNames[c] ? ' — ' + airportNames[c] : ''}</option>)}
          </select>
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Earliest Trip Start Date</label>
          <input type="date" value={tripStart} onChange={e => setTripStart(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Latest Trip End Date</label>
          <input type="date" value={tripEnd} onChange={e => setTripEnd(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Start Weekdays</label>
          {renderChips('start', startWeekdays, setStartWeekdays)}
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>End Weekdays</label>
          {renderChips('end', endWeekdays, setEndWeekdays)}
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Latest Departure to Destination</label>
          <input type="time" value={maxDepToDest} onChange={e => setMaxDepToDest(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Earliest Return Departure</label>
          <input type="time" value={minRetDep} onChange={e => setMinRetDep(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Min Trip Length (days)</label>
          <input type="number" min={1} max={30} value={minTripDays === '' ? '' : minTripDays}
            onChange={e => setMinTripDays(e.target.value === '' ? '' : parseInt(e.target.value, 10) || '')}
            onBlur={e => { const v = parseInt(e.target.value, 10); if (isNaN(v) || v < 1) setMinTripDays(1); }}
            style={controlStyle} />
        </div>
        <div style={fieldBoxStyle()}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Max Trip Length (days)</label>
          <input type="number" min={1} max={30} value={maxTripDays === '' ? '' : maxTripDays}
            onChange={e => setMaxTripDays(e.target.value === '' ? '' : parseInt(e.target.value, 10) || '')}
            onBlur={e => { const v = parseInt(e.target.value, 10); if (isNaN(v) || v < 1) setMaxTripDays(1); }}
            style={controlStyle} />
        </div>
      </div>

      <div style={{ ...fieldBoxStyle(), marginBottom: 18 }}>
        <h4 style={{ margin: '0 0 6px', fontSize: 15, fontWeight: 700, color: '#f8fafc' }}>Saved Search Configs</h4>
        <p style={{ color: '#94a3b8', fontSize: 12, margin: '0 0 12px' }}>
          Save the current weekdays, times and trip length under a name. Airport and date range are not saved; they stay as set when loading. Stored on the server, so every browser shows the same configs.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <input type="text" value={configName} onChange={e => setConfigName(e.target.value)} placeholder="Configuration name"
            style={{ ...controlStyle, maxWidth: 260 }} />
          <button onClick={handleSaveConfig} style={saveButtonStyle}>Save current search</button>
          <select value={selectedConfig} onChange={e => setSelectedConfig(e.target.value)} style={{ ...controlStyle, maxWidth: 220 }}>
            <option value="">{configsLoading ? 'Loading saved configs…' : 'Select saved config…'}</option>
            {savedConfigs.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
          <button onClick={handleLoadConfig} style={loadButtonStyle}>Load</button>
          <button onClick={handleDeleteConfig} style={deleteButtonStyle}>Delete</button>
        </div>
        {configsError && (
          <p style={{ color: '#ef4444', fontSize: 12, margin: '10px 0 0' }}>{configsError}</p>
        )}
        {configMessage && (
          <p style={{ color: '#fbbf24', fontSize: 12, margin: '10px 0 0' }}>{configMessage}</p>
        )}
      </div>

      {/* Fix #5/D18: Responsive cards (<640px) or table (≥640px) with Actions header */}
      {turnarounds.length > 0 && (
        <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 16, border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#f8fafc' }}>Possible Turnarounds</h4>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>{turnarounds.length} result{turnarounds.length !== 1 ? 's' : ''}</span>
          </div>
          {groupKeys.map(key => {
            const group = groups[key];
            const isOpen = !!expanded['trip_' + key];
            return (
              <div key={key} style={{ marginBottom: 10, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, overflow: 'hidden' }}>
                <button onClick={() => toggle('trip_' + key)} style={{ width: '100%', textAlign: 'left', padding: '10px 14px', background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <span style={{ minWidth: 0 }}>{(group[0]?.hinflug_ziel_name || airportNames[key] ? (group[0]?.hinflug_ziel_name || airportNames[key] || key) + ' ' : '') + '(' + key + ')'}</span>
                  <span style={{ color: '#94a3b8', fontWeight: 500, flexShrink: 0 }}>{isOpen ? '▲' : '▼'}</span>
                </button>
                {isOpen && (
                  <div style={{ padding: 8 }}>
                    <button onClick={() => addAllFavorites(group)} style={{ padding: '6px 12px', borderRadius: 6, border: 'none', background: '#10b981', color: '#fff', fontWeight: 700, fontSize: 12, cursor: 'pointer', marginBottom: 8, whiteSpace: 'nowrap', minWidth: 44, minHeight: 32 }}>Add all favorites</button>
                    {isSmallScreen ? (
                      // Cards view for mobile (<640px)
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {group.map((t, i) => {
                          const key = quoteKey(t);
                          const q = quotes[key];
                          return (
                            <div key={i} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: 12, border: '1px solid rgba(255,255,255,0.06)' }}>
                              <div style={{ fontSize: 13, color: '#f8fafc', fontWeight: 600, marginBottom: 6 }}>
                                <span style={{ color: '#38bdf8' }}>Out:</span> {formatTripDateTime(t.hinflug_abflug_zeit)} <span style={{ color: '#94a3b8' }}>({t.hinflug_flight_number || '-'})</span>
                              </div>
                              <div style={{ fontSize: 13, color: '#f8fafc', fontWeight: 600, marginBottom: 6 }}>
                                <span style={{ color: '#38bdf8' }}>Ret:</span> {formatTripDateTime(t.rueckflug_abflug_zeit)} <span style={{ color: '#94a3b8' }}>({t.rueckflug_flight_number || '-'})</span>
                              </div>
                              <div style={{ fontSize: 13, color: '#38bdf8', fontWeight: 600, marginBottom: 8 }}>
                                Dauer: {(t.dauer_tage !== undefined ? t.dauer_tage + 'd' : (t.days ? t.days + 'd' : '-'))}
                              </div>
                              {q && q.status === 'done' && (
                                <div style={{ fontSize: 12, color: '#38bdf8', fontWeight: 600, marginBottom: 6 }}>
                                  {formatPrice(q.price_outbound)} · {formatPrice(q.price_return)} · {formatPrice(q.price_total)}{' '}
                                  <span style={{ color: '#94a3b8', fontWeight: 400 }}>({relativeAge(q.fetched_at)})</span>
                                </div>
                              )}
                              {q && q.status === 'error' && (
                                <div style={{ fontSize: 12, color: '#ef4444', marginBottom: 6 }}>
                                  {q.error}{' '}
                                  <button onClick={() => fetchQuote(t)} style={{ background: 'none', border: 'none', color: '#38bdf8', cursor: 'pointer', padding: 0 }}>Retry</button>
                                </div>
                              )}
                              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                <button onClick={() => fetchQuote(t)} disabled={q && (q.status === 'loading' || q.status === 'done')}
                                  style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: q?.status === 'loading' ? '#64748b' : '#0ea5e9', color: '#fff', fontWeight: 600, fontSize: 12, cursor: q?.status === 'loading' || q?.status === 'done' ? 'not-allowed' : 'pointer', minWidth: 44, minHeight: 44, flex: 1 }}>
                                  {q?.status === 'loading' ? '…fetching' : (q?.status === 'done' ? '✓ quoted' : 'Show price')}
                                </button>
                                <button onClick={() => addFavorite(t)} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: t.is_favorite ? '#38bdf8' : '#1e293b', color: '#fff', fontWeight: 600, fontSize: 12, cursor: 'pointer', minWidth: 44, minHeight: 44 }}>
                                  {t.is_favorite ? '★ Favorited' : '+ Add'}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      // Table view for desktop (≥640px)
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, tableLayout: 'fixed' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
                            <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Outbound Flight</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Return Flight</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Trip Duration</th>
                            <th style={{ textAlign: 'right', padding: '6px 8px', color: '#94a3b8' }}>Price</th>
                            <th style={{ textAlign: 'right', padding: '6px 8px', color: '#94a3b8' }}>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.map((t, i) => {
                            const key = quoteKey(t);
                            const q = quotes[key];
                            return (
                              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{formatTripDateTime(t.hinflug_abflug_zeit) + ' | ' + (t.hinflug_flight_number || '-')}</td>
                                <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{formatTripDateTime(t.rueckflug_abflug_zeit) + ' | ' + (t.rueckflug_flight_number || '-')}</td>
                                <td style={{ padding: '6px 8px', color: '#38bdf8' }}>{(t.dauer_tage !== undefined ? t.dauer_tage + 'd' : (t.days ? t.days + 'd' : '-'))}</td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', minWidth: 120 }}>
                                  {q && q.status === 'done' && (
                                    <div style={{ color: '#38bdf8', fontWeight: 600, whiteSpace: 'nowrap' }}>
                                      {formatPrice(q.price_outbound)} · {formatPrice(q.price_return)} · {formatPrice(q.price_total)}
                                      <span style={{ color: '#94a3b8', fontWeight: 400, fontSize: 10, marginLeft: 4 }}>({relativeAge(q.fetched_at)})</span>
                                    </div>
                                  )}
                                  {q && q.status === 'error' && (
                                    <div style={{ color: '#ef4444', fontSize: 11 }}>
                                      {q.error}{' '}
                                      <button onClick={() => fetchQuote(t)} style={{ background: 'none', border: 'none', color: '#38bdf8', cursor: 'pointer', padding: 0, fontSize: 11 }}>Retry</button>
                                    </div>
                                  )}
                                </td>
                                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                                  <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                                    <button onClick={() => fetchQuote(t)} disabled={q && (q.status === 'loading' || q.status === 'done')}
                                      style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: q?.status === 'loading' ? '#64748b' : '#0ea5e9', color: '#fff', fontWeight: 600, fontSize: 11, cursor: q?.status === 'loading' || q?.status === 'done' ? 'not-allowed' : 'pointer', minWidth: 32, minHeight: 28 }}>
                                      {q?.status === 'loading' ? '…' : (q?.status === 'done' ? '✓' : '€')}
                                    </button>
                                    <button onClick={() => addFavorite(t)} style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: t.is_favorite ? '#38bdf8' : '#1e293b', color: '#fff', fontWeight: 600, fontSize: 11, cursor: 'pointer', minWidth: 32, minHeight: 28 }}>
                                      {t.is_favorite ? '★' : '+ Add'}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <ConfirmDialog />
    </section>
  );
}
