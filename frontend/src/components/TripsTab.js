import React, { useState, useEffect } from 'react';
import { formatTripDateTime } from '../utils/format';
import { useTripConfigs } from '../hooks/useTripConfigs';

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
  const [startAirport, setStartAirport] = useState('');
  const [endAirport, setEndAirport] = useState('');
  const [tripStart, setTripStart] = useState(new Date().toISOString().split('T')[0]);
  const [tripEnd, setTripEnd] = useState(new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0]);
  const [startWeekdays, setStartWeekdays] = useState([4]);
  const [endWeekdays, setEndWeekdays] = useState([6]);
  const [maxDepToDest, setMaxDepToDest] = useState('18:00');
  const [minRetDep, setMinRetDep] = useState('10:00');
  const [maxTripDays, setMaxTripDays] = useState(5);
  const [minTripDays, setMinTripDays] = useState(1);
  const [turnarounds, setTurnarounds] = useState([]);
  const [expanded, setExpanded] = useState({});
  const toggle = (k) => setExpanded(e => ({ ...e, [k]: !e[k] }));

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
    if (existing && !confirm(`Configuration "${configName.trim()}" already exists. Overwrite it?`)) {
      setConfigMessage('Overwrite cancelled — nothing was saved.');
      return;
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
    if (!confirm(`Delete configuration "${selectedConfig}"?`)) { setConfigMessage('Delete cancelled.'); return; }
    const result = await removeConfig(selectedConfig);
    setSelectedConfig('');
    setConfigMessage(result.ok
      ? `Configuration "${selectedConfig}" deleted.`
      : (result.error || 'Could not delete the configuration.'));
  };

  useEffect(() => {
    if (tripStart && tripEnd && startWeekdays.length > 0 && endWeekdays.length > 0 && maxDepToDest && minRetDep && maxTripDays && minTripDays) {
      const params = new URLSearchParams({
        start: tripStart, end: tripEnd,
        start_days: startWeekdays.join(','), end_days: endWeekdays.join(','),
        max_dep_dest: maxDepToDest, min_ret_dep: minRetDep,
        max_trip_days: maxTripDays, min_trip_days: minTripDays,
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
    if (!confirm('Add all trips in this group to favorites?')) return;
    for (const t of group) await addFavorite(t);
  };

  const groups = {};
  turnarounds.forEach(t => { const key = t.hinflug_ziel || t.destination || '-'; if (!groups[key]) groups[key] = []; groups[key].push(t); });
  const groupKeys = Object.keys(groups).sort();

  const selectWeekdays = (value, onChange) => (
    <select multiple value={value.map(String)}
      onChange={e => onChange([...e.target.options].filter(o => o.selected).map(o => parseInt(o.value)))}
      style={{ ...controlStyle, height: 160, overflow: 'auto' }}>
      {WEEKDAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
    </select>
  );

  return (
    <section style={sectionStyle}>
      <h3 style={{ margin: '0 0 14px', fontSize: 18, fontWeight: 700, color: '#f8fafc' }}>Trip Turnaround Finder</h3>
      <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 18 }}>Find possible trip combinations based on date ranges and weekday preferences.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 18, marginBottom: 18 }}>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Airport (Start & End)</label>
          <select value={startAirport} onChange={e => { setStartAirport(e.target.value); setEndAirport(e.target.value); }}
            style={{ ...controlStyle, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            <option value="">Select airport</option>
            {list.map(c => <option key={c} value={c} style={{ color: '#0f172a', background: '#f8fafc' }}>{c}{airportNames[c] ? ' — ' + airportNames[c] : ''}</option>)}
          </select>
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Earliest Trip Start Date</label>
          <input type="date" value={tripStart} onChange={e => setTripStart(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Latest Trip End Date</label>
          <input type="date" value={tripEnd} onChange={e => setTripEnd(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Start Weekdays</label>
          {selectWeekdays(startWeekdays, setStartWeekdays)}
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>End Weekdays</label>
          {selectWeekdays(endWeekdays, setEndWeekdays)}
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Latest Departure to Destination</label>
          <input type="time" value={maxDepToDest} onChange={e => setMaxDepToDest(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Earliest Return Departure</label>
          <input type="time" value={minRetDep} onChange={e => setMinRetDep(e.target.value)} style={controlStyle} />
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Min Trip Length (days)</label>
          <input type="number" min={1} max={30} value={minTripDays} onChange={e => setMinTripDays(parseInt(e.target.value) || 1)} style={controlStyle} />
        </div>
        <div style={fieldStyle}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#f8fafc', display: 'block', marginBottom: 6 }}>Max Trip Length (days)</label>
          <input type="number" min={1} max={30} value={maxTripDays} onChange={e => setMaxTripDays(parseInt(e.target.value) || 1)} style={controlStyle} />
        </div>
      </div>

      <div style={{ ...fieldStyle, marginBottom: 18 }}>
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

      {turnarounds.length > 0 && (
        <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 16, border: '1px solid rgba(255,255,255,0.08)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 700, color: '#f8fafc' }}>Possible Turnarounds</h4>
          {groupKeys.map(key => {
            const group = groups[key];
            const isOpen = !!expanded['trip_' + key];
            return (
              <div key={key} style={{ marginBottom: 10, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, overflow: 'hidden' }}>
                <button onClick={() => toggle('trip_' + key)} style={{ width: '100%', textAlign: 'left', padding: '10px 14px', background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{(group[0]?.hinflug_ziel_name || airportNames[key] ? (group[0]?.hinflug_ziel_name || airportNames[key] || key) + ' ' : '') + '(' + key + ')'}</span>
                  <span style={{ color: '#94a3b8', fontWeight: 500 }}>{isOpen ? '▲' : '▼'}</span>
                </button>
                {isOpen && (
                  <div style={{ padding: 8 }}>
                    <button onClick={() => addAllFavorites(group)} style={{ padding: '6px 12px', borderRadius: 6, border: 'none', background: '#10b981', color: '#fff', fontWeight: 700, fontSize: 12, cursor: 'pointer', marginBottom: 8, whiteSpace: 'nowrap' }}>Add all favorites</button>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, tableLayout: 'fixed' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Outbound Flight</th>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Return Flight</th>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8' }}>Trip Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.map((t, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{formatTripDateTime(t.hinflug_abflug_zeit) + ' | ' + (t.hinflug_flight_number || '-')}</td>
                            <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{formatTripDateTime(t.rueckflug_abflug_zeit) + ' | ' + (t.rueckflug_flight_number || '-')}</td>
                            <td style={{ padding: '6px 8px', color: '#38bdf8' }}>{(t.dauer_tage !== undefined ? t.dauer_tage + 'd' : (t.days ? t.days + 'd' : '-'))}</td>
                            <td style={{ padding: '6px 8px' }}>
                              <button onClick={() => addFavorite(t)} style={{ padding: '4px 8px', borderRadius: 6, border: 'none', background: t.is_favorite ? '#38bdf8' : '#1e293b', color: '#fff', fontWeight: 600, fontSize: 12, cursor: 'pointer', minWidth: 110 }}>
                                {t.is_favorite ? '★ Favorited' : '+ Add to favorites'}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
