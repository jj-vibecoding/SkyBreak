// D4/D7: Responsive FlightsTab — flex-wrap for status line (Fix #17), 
//        scroll-x for tables, touch targets ≥44px (Fix #6).
// Merged AirportsTab: add/remove airports + per-airport refresh at bottom.
import React, { useState, useEffect } from 'react';
import { formatTime } from '../utils/format';
import { useMediaQuery } from '../hooks/useMediaQuery';

const thStyle = { textAlign: 'left', padding: '4px 8px', color: '#94a3b8' };
const tdStyle = { padding: '4px 8px' };

function FlightTable({ title, rows, empty, firstCol, firstLabel }) {
  return (
    <div className="table-responsive">
      <strong style={{ color: title.includes('Arrival') ? '#4ade80' : '#38bdf8', fontSize: 13 }}>{title}</strong>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 560 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <th style={thStyle}>{firstLabel}</th>
            <th style={thStyle}>Flight</th>
            <th style={thStyle}>Departure</th>
            <th style={thStyle}>Arrival</th>
            <th style={thStyle}>Duration</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan="5" style={{ ...tdStyle, color: '#94a3b8' }}>{empty}</td></tr>}
          {rows.map(f => (
            <tr key={f.id || f.destination_icao + f.departure_time} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <td style={tdStyle}>{firstCol(f)}</td>
              <td style={{ ...tdStyle, fontWeight: 600 }}>{f.flight_number || '-'}</td>
              <td style={{ ...tdStyle, color: '#38bdf8' }}>{formatTime(f.departure_time)}</td>
              <td style={{ ...tdStyle, color: '#4ade80' }}>{formatTime(f.arrival_time)}</td>
              <td style={{ ...tdStyle, color: '#818cf8' }}>{f.duration_minutes ? f.duration_minutes + ' min' : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Flight schedule for a saved airport, per date. Owns its own date/flight data.
export default function FlightsTab({ list, setList, onFetchNow, fetchRunning }) {
  const isSmallScreen = useMediaQuery('(max-width: 767px)'); // mobile/tablet
  
  const [flightDate, setFlightDate] = useState(new Date().toISOString().split('T')[0]);
  const [flights, setFlights] = useState([]);
  const [futureInfo, setFutureInfo] = useState({});
  const [expanded, setExpanded] = useState({});
  const toggle = (c) => setExpanded(e => ({ ...e, [c]: !e[c] }));

  // Airport management state
  const [newCode, setNewCode] = useState('');
  const [feedback, setFeedback] = useState({ text: '', tone: 'default' });
  const [refreshingAirports, setRefreshingAirports] = useState({});

  useEffect(() => {
    fetch('/api/flights?date=' + flightDate)
      .then(r => r.json())
      .then(data => {
        setFlights(data);
        fetch('/api/flights/future').then(f => f.json()).then(setFutureInfo).catch(() => setFutureInfo({}));
      })
      .catch(() => setFlights([]));
  }, [flightDate]);

  // --- Airport management ---
  const FEEDBACK_COLORS = { default: '#94a3b8', success: '#4ade80', error: '#f87171', info: '#38bdf8' };

  const submitAirport = async (e) => {
    e.preventDefault();
    const raw = newCode.trim().toUpperCase();
    if (!/^[A-Z0-9]{3}$/.test(raw)) {
      setFeedback({ text: 'Invalid IATA code', tone: 'error' });
      return;
    }
    const res = await fetch('/api/airports', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: raw })
    });
    if (res.ok) {
      setFeedback({ text: `Saved: ${raw}`, tone: 'success' });
      setNewCode('');
      setList([...list, raw]);
      window.dispatchEvent(new CustomEvent('showToast', { 
        detail: { message: `Saved: ${raw}`, type: 'success' } 
      }));
    } else {
      setFeedback({ text: 'Server error', tone: 'error' });
    }
  };

  const removeAirport = async (c) => {
    const res = await fetch('/api/airports/' + c, { method: 'DELETE' });
    if (res.ok) {
      setList(list.filter(x => x !== c));
      setFeedback({ text: `Removed: ${c}`, tone: 'info' });
      window.dispatchEvent(new CustomEvent('showToast', { 
        detail: { message: `Removed: ${c}`, type: 'warning' } 
      }));
    } else {
      setFeedback({ text: 'Error removing airport', tone: 'error' });
    }
  };

  const refreshAirport = async (code) => {
    setRefreshingAirports(prev => ({ ...prev, [code]: true }));
    try {
      const res = await fetch(`/api/airports/${code}/refresh`, { method: 'POST' });
      if (res.ok) {
        window.dispatchEvent(new CustomEvent('showToast', { 
          detail: { message: `Refreshing ${code}…`, type: 'info' } 
        }));
      } else {
        const data = await res.json();
        window.dispatchEvent(new CustomEvent('showToast', { 
          detail: { message: data.error || 'Refresh failed', type: 'error' } 
        }));
      }
    } catch {
      window.dispatchEvent(new CustomEvent('showToast', { 
        detail: { message: `Failed to refresh ${code}`, type: 'error' } 
      }));
    }
    setRefreshingAirports(prev => ({ ...prev, [code]: false }));
  };

  return (
    <>
      {/* Date picker + global fetch */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <input type="date" value={flightDate} onChange={e => setFlightDate(e.target.value)}
          className="tap"
          style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontSize: 13, cursor: 'pointer' }} />
        <button onClick={() => setFlightDate(new Date().toISOString().split('T')[0])} className="tap"
          style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#f59e0b,#d97706)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}>
          Today
        </button>
        <button disabled={fetchRunning} onClick={onFetchNow}
          style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: fetchRunning ? '#475569' : '#10b981', color: '#fff', fontWeight: 700, cursor: fetchRunning ? 'not-allowed' : 'pointer', fontSize: 13 }}>
          {fetchRunning ? 'Fetching...' : 'Fetch Now'}
        </button>
      </div>

      {/* Flight schedule per airport */}
      {list.map(airport => {
        const arr = flights.filter(f => f.airport_icao === airport && f.direction === 'arrival');
        const dep = flights.filter(f => f.airport_icao === airport && f.direction === 'departure');
        return (
          <div key={airport} style={{ marginBottom: 16 }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              width: '100%',
              flexWrap: isSmallScreen ? 'wrap' : 'nowrap',
              gap: 8,
            }}>
              <button onClick={() => toggle(airport)} style={{ 
                flex: 1, 
                textAlign: 'left', 
                padding: '12px 16px', 
                borderRadius: 10, 
                border: '1px solid rgba(255,255,255,0.08)', 
                background: 'rgba(255,255,255,0.06)', 
                color: '#f8fafc', 
                fontWeight: 700, 
                fontSize: 16, 
                cursor: 'pointer', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                minWidth: 44,
                minHeight: 44,
              }}>
                {airport} <span style={{ color: '#94a3b8', fontWeight: 500 }}>✈️</span>
              </button>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <button onClick={() => refreshAirport(airport)} className="tap" disabled={!!refreshingAirports[airport]}
                  style={{ 
                    padding: '6px 12px', borderRadius: 8, border: 'none', 
                    background: refreshingAirports[airport] ? '#475569' : '#6366f1', 
                    color: '#fff', fontWeight: 600, cursor: refreshingAirports[airport] ? 'not-allowed' : 'pointer', fontSize: 12,
                  }}
                  title={`Refresh flights for ${airport}`}>
                  {refreshingAirports[airport] ? '⟳ Refreshing…' : '⟳'}
                </button>
              </div>
              <span style={{ 
                marginLeft: isSmallScreen ? 0 : 10, 
                fontSize: 12, 
                color: '#38bdf8', 
                fontWeight: 600,
                whiteSpace: isSmallScreen ? 'normal' : 'nowrap',
              }}>
                {futureInfo[airport] ? (futureInfo[airport].max_departure_day ? `Loaded until ${futureInfo[airport].max_departure_day}` : 'No future data') : '...'}
              </span>
            </div>
            <div style={{ marginTop: 8, padding: 8 }}>
              {expanded[airport] ? (
                <div>
                  <FlightTable
                    title={`Arrivals (${arr.length})`}
                    rows={arr} empty="No arrivals" firstLabel="From"
                    firstCol={a => a.from_icao ? (a.from_airport_name ? a.from_airport_name + ' (' + a.from_icao + ')' : (a.from_icao || a.airport_icao || airport)) : (a.airport_icao || airport)}
                  />
                  <div style={{ marginTop: 10 }}>
                    <FlightTable
                      title={`Departures (${dep.length})`}
                      rows={dep} empty="No departures" firstLabel="To"
                      firstCol={d => d.destination_name ? d.destination_name + ' (' + d.destination_icao + ')' : d.destination_icao}
                    />
                  </div>
                </div>
              ) : <span style={{ color: '#94a3b8', fontSize: 13 }}>Click to expand</span>}
            </div>
          </div>
        );
      })}
      {!list.length && <div style={{ color: '#94a3b8', fontSize: 14 }}>No airports saved yet. Add one below.</div>}

      {/* ── Saved Airports + Add Airport (merged from AirportsTab) ── */}
      <div style={{ marginTop: 24, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
        <h4 style={{ margin: '0 0 14px', fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>Saved Airports</h4>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {list.map(c => (
            <li key={c} style={{
              background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 10, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 10
            }}>
              <span style={{ fontWeight: 700, color: '#38bdf8', letterSpacing: '0.5px' }}>{c}</span>
              <button onClick={() => removeAirport(c)} className="tap" style={{
                background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: 6, color: '#f87171',
                fontSize: 14, cursor: 'pointer', padding: '4px 10px', lineHeight: 1
              }} title="Remove">×</button>
            </li>
          ))}
          {!list.length && <li style={{ color: '#94a3b8', fontSize: 14 }}>No airports saved yet.</li>}
        </ul>

        {/* Add Airport form */}
        <div style={{ marginTop: 16 }}>
          <form onSubmit={submitAirport} style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input value={newCode} maxLength={3} placeholder="LHR"
              onChange={e => setNewCode(e.target.value.toUpperCase())}
              style={{
                flex: '1 1 120px', padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.15)',
                background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontSize: 15, outline: 'none'
              }} />
            <button type="submit" className="tap" style={{
              padding: '10px 18px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
              color: '#0f172a', fontWeight: 700, fontSize: 15, cursor: 'pointer', boxShadow: '0 4px 14px rgba(56,189,248,0.35)'
            }}>Save</button>
          </form>
          <p style={{ margin: '10px 0 0', minHeight: 24, color: FEEDBACK_COLORS[feedback.tone], fontSize: 13, fontWeight: 500 }}>
            {feedback.text}
          </p>
        </div>
      </div>
    </>
  );
}
