// D6/D12: Responsive FavoriteTripPrices — useMediaQuery (Fix #19),
//        touch targets ≥44px, card view <640px, dialog system.
import React, { useState, useEffect } from 'react';
import ChartModal from './ChartModal';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { useConfirm } from './Dialogs';

export default function FavoriteTripPrices() {
  const isSmallScreen = useMediaQuery('(max-width: 639px)'); // Fix #19: responsive breakpoint
  const { showConfirm, ConfirmDialog } = useConfirm(); // Fix #12: replace window.confirm
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [progress, setProgress] = useState(false);
  const [sortKey, setSortKey] = useState('price_total');
  const [sortDir, setSortDir] = useState('desc');
  const [groupSortKey, setGroupSortKey] = useState('name');
  const [groupSortDir, setGroupSortDir] = useState('asc');
  const [chartOpen, setChartOpen] = useState(false);
  const [chartData, setChartData] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [grpSortKey, setGrpSortKey] = useState({});
  const [grpSortDir, setGrpSortDir] = useState({});
  const [filterStart, setFilterStart] = useState('');
  const [filterEnd, setFilterEnd] = useState('');
  const toggle = (k) => setExpanded(e => ({...e, [k]: !e[k]}));
  const load = () => { setLoading(true); fetch('/api/favorites').then(r => r.json()).then(d => { setPrices(Array.isArray(d) ? d : []); }).catch(() => setPrices([])).finally(() => setLoading(false)); };
  const [pollActive, setPollActive] = useState(false);
  useEffect(() => { load(); let prevRunning = false; const iv = setInterval(() => { if (!pollActive) return; fetch('/api/prices/status').then(r=>r.json()).then(s=>{ if(s.running){setProgress(true); setPollActive(true);}else{setProgress(false); setPollActive(false); if(prevRunning && !s.running){ load(); } } prevRunning = !!s.running; }).catch(()=>{}); }, 1500); return () => clearInterval(iv); }, [pollActive]);
  if (!prices.length) return <p style={{ color: '#94a3b8', fontSize: 13 }}>No favorites yet.</p>;
  const handleUpdate = () => { if (updating || progress) return; setUpdating(true); setProgress(true); setPollActive(true); fetch('/api/prices', {method:'POST'}).then(r => r.json()).then(d => { if(d.updated) { setTimeout(load, 800); } else { setProgress(false); setPollActive(false); } }).catch(() => { setProgress(false); setPollActive(false); }).finally(() => setUpdating(false)); };
  const handleUpdateMissing = () => { if (updating || progress) return; setUpdating(true); setProgress(true); setPollActive(true); fetch('/api/prices/missing', {method:'POST'}).then(r => r.json()).then(d => { if(d.updated) { setTimeout(load, 800); } else { setProgress(false); setPollActive(false); } }).catch(() => { setProgress(false); setPollActive(false); }).finally(() => setUpdating(false)); };
  const openChartFor = (tripId) => {
    const trip = prices.find(p => p.id === tripId || p.id == tripId);
    if (!trip) { setChartData([]); setChartOpen(true); return; }
    // Build minimal array for ChartModal (expects array of points)
    setChartOpen(true);
    fetch(`/api/prices/history?trip_id=${tripId}`).then(r => r.json()).then(data => {
      setChartData(Array.isArray(data) && data.length ? data : [{date: trip.trip_date || '-', outbound_price: trip.price_outbound || 0, return_price: trip.price_return || 0, total_price: trip.price_total || 0}]);
    }).catch(() => {
      setChartData([{date: trip.trip_date || '-', outbound_price: trip.price_outbound || 0, return_price: trip.price_return || 0, total_price: trip.price_total || 0}]);
    });
  };
  const sorted = [...prices].sort((a,b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === 'price_total') {
      const avNull = av == null || av === undefined;
      const bvNull = bv == null || bv === undefined;
      if (avNull && bvNull) return 0;
      if (avNull) return 1; // null immer am Ende
      if (bvNull) return -1;
      const n1 = Number(av), n2 = Number(bv);
      if (n1 < n2) return sortDir === 'asc' ? -1 : 1;
      if (n1 > n2) return sortDir === 'asc' ? 1 : -1;
      return 0;
    }
    if (av == null) av = -Infinity; if (bv == null) bv = -Infinity;
    if (typeof av === 'string') av = av.toLowerCase(); if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return sortDir === 'asc' ? -1 : 1;
    if (av > bv) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });
  const fmtDur = (m) => { if (m == null || m === undefined || m === '') return '—'; return m + ' min'; };
  const fmtTime = (t) => { if (!t) return '—'; if (t.includes('T')) return t.substring(11,16); const parts = String(t).split(' '); return parts.length > 1 ? parts[1].substring(0,5) : t; };
  const headerBtn = (key, label) => (
    <button onClick={() => { if (sortKey === key) { setSortDir(sortDir === 'asc' ? 'desc' : 'asc'); } else { setSortKey(key); setSortDir('asc'); } }} style={{ background:'none', border:'none', color:'#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer', padding:0 }}>
      {label} {sortKey === key ? (sortDir === 'asc' ? '▲' : '▼') : ''}
    </button>
  );
  // Gruppierung nach Ziel (analog turnarounds)
  const groupsObj = {};
  prices.forEach(p => { const key = p.destination_airport || p.dest_city_country || '-'; if (!groupsObj[key]) groupsObj[key] = []; groupsObj[key].push(p); });
  // A→Z sortiert nach Stadtname, nicht nach IATA-Code
  const groupNames = {};
  Object.keys(groupsObj).forEach(k => { groupNames[k] = (groupsObj[k][0]?.dest_city_country || k); });
  const groupKeys = Object.keys(groupsObj).sort((a, b) => {
    if (groupSortKey === 'name') {
      return groupSortDir === 'asc' ? groupNames[a].localeCompare(groupNames[b]) : groupNames[b].localeCompare(groupNames[a]);
    }
    // price_min: cheapest trip in each group first/last, nulls last
    const minA = groupsObj[a].reduce((m, p) => (p.price_total != null && (m == null || p.price_total < m)) ? p.price_total : m, null);
    const minB = groupsObj[b].reduce((m, p) => (p.price_total != null && (m == null || p.price_total < m)) ? p.price_total : m, null);
    if (minA == null && minB == null) return 0;
    if (minA == null) return 1;
    if (minB == null) return -1;
    return groupSortDir === 'asc' ? minA - minB : minB - minA;
  });

  return (
    <div>
        <h4 style={{ margin: '0 0 10px', fontSize: 16, fontWeight: 700, color: '#f8fafc', letterSpacing: 0.2 }}>Favorite Trips</h4>
        <div style={{ display:'flex', gap: 10, flexWrap:'wrap', marginBottom: 10, alignItems:'center' }}>
          <label style={{ color:'#94a3b8', fontSize:12 }}>Filter date range:</label>
          <input type="date" value={filterStart} onChange={e => setFilterStart(e.target.value)} style={{ padding:'5px 8px', borderRadius:6, border:'1px solid rgba(255,255,255,0.15)', background:'rgba(255,255,255,0.06)', color:'#f8fafc', fontSize:12 }} />
          <input type="date" value={filterEnd} onChange={e => setFilterEnd(e.target.value)} style={{ padding:'5px 8px', borderRadius:6, border:'1px solid rgba(255,255,255,0.15)', background:'rgba(255,255,255,0.06)', color:'#f8fafc', fontSize:12 }} />
          <button onClick={() => { setFilterStart(''); setFilterEnd(''); }} style={{ padding:'5px 10px', borderRadius:6, border:'none', background:'#475569', color:'#f8fafc', fontSize:11, cursor:'pointer' }}>Clear</button>
        </div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom: 8, alignItems:'center' }}>
          <label style={{ color:'#94a3b8', fontSize:12, marginRight:4 }}>Sort groups:</label>
          <button onClick={() => { setGroupSortKey('name'); setGroupSortDir('asc'); }} style={{ padding:'5px 10px', borderRadius:6, border:'none', background: groupSortKey==='name' && groupSortDir==='asc' ? '#38bdf8' : '#475569', color: groupSortKey==='name' && groupSortDir==='asc' ? '#0f172a' : '#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer' }}>A→Z</button>
          <button onClick={() => { setGroupSortKey('price_min'); setGroupSortDir('asc'); }} style={{ padding:'5px 10px', borderRadius:6, border:'none', background: groupSortKey==='price_min' && groupSortDir==='asc' ? '#38bdf8' : '#475569', color: groupSortKey==='price_min' && groupSortDir==='asc' ? '#0f172a' : '#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer' }}>Price ↑</button>
          <button onClick={() => { setGroupSortKey('price_min'); setGroupSortDir('desc'); }} style={{ padding:'5px 10px', borderRadius:6, border:'none', background: groupSortKey==='price_min' && groupSortDir==='desc' ? '#38bdf8' : '#475569', color: groupSortKey==='price_min' && groupSortDir==='desc' ? '#0f172a' : '#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer' }}>Price ↓</button>
        </div>
        <button disabled={updating || progress} onClick={handleUpdate} style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: (updating || progress) ? '#475569' : '#f59e0b', color: '#0f172a', fontWeight: 700, fontSize: 12, cursor: (updating || progress) ? 'not-allowed' : 'pointer', marginBottom: 8, marginRight: 10 }}>
          {progress || updating ? 'Updating prices... (running)' : 'Update all prices'}
        </button>
        <button disabled={updating || progress} onClick={handleUpdateMissing} style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: (updating || progress) ? '#475569' : '#38bdf8', color: '#0f172a', fontWeight: 700, fontSize: 12, cursor: (updating || progress) ? 'not-allowed' : 'pointer', marginBottom: 8 }}>
          {progress || updating ? 'Updating prices... (running)' : 'Update missing prices'}
        </button>
        {groupKeys.map(key => {
          let grp = groupsObj[key];
          if (filterStart) grp = grp.filter(p => (p.outbound_trip_date || p.trip_date || '') >= filterStart);
          if (filterEnd) grp = grp.filter(p => (p.outbound_trip_date || p.trip_date || '') <= filterEnd);
          if (!grp.length) return null;
          const isOpen = !!expanded['price_' + key];
          const cheapest = grp.reduce((m, p) => (p.price_total != null && (m == null || p.price_total < m.price_total)) ? p : m, null);
          const cheapestPrice = cheapest && cheapest.price_total != null ? cheapest.price_total + ' €' : '—';
          return (
            <div key={key} style={{ marginBottom: 10, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, overflow: 'hidden' }}>
              <button onClick={() => toggle('price_' + key)} style={{ width: '100%', textAlign: 'left', padding: '10px 14px', background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{(grp[0]?.dest_city_country || key) + ' (' + key + ')'}</span>
                <span style={{ color: '#38bdf8', fontWeight: 600, fontSize: 12, marginLeft: 'auto', marginRight: 8 }}>Cheapest: {cheapestPrice}</span>
                <span style={{ color: '#94a3b8', fontWeight: 500 }}>{isOpen ? '▲' : '▼'}</span>
              </button>
              {isOpen && (
                <div style={{ padding: 8 }}>
                  <button onClick={async () => { const ok = await showConfirm('Delete All', 'Delete all favorites in this group (matching filter)?'); if (!ok) return; for (const p of grp) { await fetch('/api/favorites/'+p.id, {method:'DELETE'}); } load(); }} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: '#ef4444', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', marginBottom: 8, minWidth: 44, minHeight: 44 }}>Delete all in group</button>
                  {isSmallScreen ? (
                      // Mobile card view (<640px)
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {[...grp].sort((a,b) => { const dir = (grpSortDir['grp_' + key] || 'asc'); const sk = (grpSortKey['grp_' + key] || 'cost'); let av=a[sk], bv=b[sk]; if (sk==='cost') { const aNull = a.price_total == null; const bNull = b.price_total == null; if (aNull && bNull) { av = bv = 0; } else if (aNull) { av = Infinity; bv = Number(b.price_total); } else if (bNull) { av = Number(a.price_total); bv = Infinity; } else { av = Number(a.price_total); bv = Number(b.price_total); } } else if (sk==='origin') { av = a.start_city_country||''; bv = b.start_city_country||''; } else if (sk==='outbound') { av = a.outbound_trip_date||a.trip_date||''; bv = b.outbound_trip_date||b.trip_date||''; } else if (sk==='return') { av = a.return_trip_date||a.trip_date||''; bv = b.return_trip_date||b.trip_date||''; } if (sk !== 'cost') { if (av == null) av = ''; if (bv == null) bv = ''; if (typeof av === 'string') av = av.toLowerCase(); if (typeof bv === 'string') bv = bv.toLowerCase(); } if (av < bv) return dir === 'asc' ? -1 : 1; if (av > bv) return dir === 'asc' ? 1 : -1; return 0; }).map(f => (
                          <div key={f.id} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: 12, border: '1px solid rgba(255,255,255,0.06)' }}>
                            <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', marginBottom: 4 }}>{f.start_city_country || '—'} <span style={{ color: '#94a3b8', fontSize: 11 }}>({f.start_airport || ''})</span></div>
                            <div style={{ fontSize: 13, color: '#f8fafc', marginBottom: 4 }}>Out: {f.outbound_trip_date || f.trip_date} {fmtTime(f.outbound_departure)} <span style={{ color: '#94a3b8' }}>({f.outbound_flight || f.outbound_flight_number || '-'})</span></div>
                            <div style={{ fontSize: 13, color: '#f8fafc', marginBottom: 4 }}>Ret: {f.return_trip_date || f.trip_date} {fmtTime(f.return_departure)} <span style={{ color: '#94a3b8' }}>({f.return_flight || f.return_flight_number || '-'})</span></div>
                            <div style={{ fontSize: 14, color: '#38bdf8', fontWeight: 700, marginBottom: 8 }}>Total: {f.price_total != null ? f.price_total + ' €' : 'none / unavailable'}</div>
                            <div style={{ display: 'flex', gap: 8 }}>
                              <button onClick={() => openChartFor(f.id)} style={{ flex: 1, padding: '8px 14px', borderRadius: 6, border: 'none', background: '#38bdf8', color: '#0f172a', fontSize: 12, fontWeight: 700, cursor: 'pointer', minWidth: 44, minHeight: 44 }}>Chart</button>
                              <button onClick={async () => { await fetch('/api/favorites/'+f.id, {method:'DELETE'}); load(); }} style={{ flex: 1, padding: '8px 14px', borderRadius: 6, border: 'none', background: '#ef4444', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', minWidth: 44, minHeight: 44 }}>Delete</button>
                            </div>
                            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 6 }}>Updated: {f.fetched_at ? new Date(f.fetched_at).toLocaleDateString() : '—'} | Out: {f.price_outbound != null ? f.price_outbound + ' €' : '—'} | Ret: {f.price_return != null ? f.price_return + ' €' : '—'}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      // Desktop table view (≥640px)
                      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 4px', fontSize: 12, tableLayout: 'fixed' }}>
                        <thead><tr style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8', whiteSpace: 'nowrap', width: '18%' }}><button onClick={() => { const k = 'grp_' + key; const isSame = grpSortKey[k] === 'origin'; const curDir = grpSortDir[k] || 'asc'; setGrpSortDir({...grpSortDir, [k]: isSame ? (curDir === 'asc' ? 'desc' : 'asc') : 'asc'}); setGrpSortKey({...grpSortKey, [k]: 'origin'}); }} style={{ background:'none', border:'none', color:'#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer', padding:0, textAlign:'left' }}>Origin {grpSortKey['grp_' + key] === 'origin' ? (grpSortDir['grp_' + key] === 'asc' ? '▲' : '▼') : ''}</button></th>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8', whiteSpace: 'nowrap', width: '22%' }}><button onClick={() => { const k = 'grp_' + key; const isSame = grpSortKey[k] === 'outbound'; const curDir = grpSortDir[k] || 'asc'; setGrpSortDir({...grpSortDir, [k]: isSame ? (curDir === 'asc' ? 'desc' : 'asc') : 'asc'}); setGrpSortKey({...grpSortKey, [k]: 'outbound'}); }} style={{ background:'none', border:'none', color:'#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer', padding:0, textAlign:'left' }}>Outbound {grpSortKey['grp_' + key] === 'outbound' ? (grpSortDir['grp_' + key] === 'asc' ? '▲' : '▼') : ''}</button></th>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8', whiteSpace: 'nowrap', width: '22%' }}><button onClick={() => { const k = 'grp_' + key; const isSame = grpSortKey[k] === 'return'; const curDir = grpSortDir[k] || 'asc'; setGrpSortDir({...grpSortDir, [k]: isSame ? (curDir === 'asc' ? 'desc' : 'asc') : 'asc'}); setGrpSortKey({...grpSortKey, [k]: 'return'}); }} style={{ background:'none', border:'none', color:'#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer', padding:0, textAlign:'left' }}>Return {grpSortKey['grp_' + key] === 'return' ? (grpSortDir['grp_' + key] === 'asc' ? '▲' : '▼') : ''}</button></th>
                          <th style={{ textAlign: 'left', padding: '6px 8px', color: '#94a3b8', whiteSpace: 'nowrap', width: '20%' }}><button onClick={() => { const k = 'grp_' + key; const isSame = grpSortKey[k] === 'cost'; const curDir = grpSortDir[k] || 'asc'; setGrpSortDir({...grpSortDir, [k]: isSame ? (curDir === 'asc' ? 'desc' : 'asc') : 'asc'}); setGrpSortKey({...grpSortKey, [k]: 'cost'}); }} style={{ background:'none', border:'none', color:'#f8fafc', fontWeight:700, fontSize:11, cursor:'pointer', padding:0, textAlign:'left' }}>Cost {grpSortKey['grp_' + key] === 'cost' ? (grpSortDir['grp_' + key] === 'asc' ? '▲' : '▼') : ''}</button></th>
                          <th style={{ textAlign: 'center', padding: '6px 8px', color: '#94a3b8', whiteSpace: 'nowrap', width: '18%' }}>Actions</th>
                        </tr></thead>
                        <tbody>
                          {[...grp].sort((a,b) => { const dir = (grpSortDir['grp_' + key] || 'asc'); const sk = (grpSortKey['grp_' + key] || 'cost'); let av=a[sk], bv=b[sk]; if (sk==='cost') { const aNull = a.price_total == null; const bNull = b.price_total == null; if (aNull && bNull) { av = bv = 0; } else if (aNull) { av = Infinity; bv = Number(b.price_total); } else if (bNull) { av = Number(a.price_total); bv = Infinity; } else { av = Number(a.price_total); bv = Number(b.price_total); } } else if (sk==='origin') { av = a.start_city_country||''; bv = b.start_city_country||''; } else if (sk==='outbound') { av = a.outbound_trip_date||a.trip_date||''; bv = b.outbound_trip_date||b.trip_date||''; } else if (sk==='return') { av = a.return_trip_date||a.trip_date||''; bv = b.return_trip_date||b.trip_date||''; } if (sk !== 'cost') { if (av == null) av = ''; if (bv == null) bv = ''; if (typeof av === 'string') av = av.toLowerCase(); if (typeof bv === 'string') bv = bv.toLowerCase(); } if (av < bv) return dir === 'asc' ? -1 : 1; if (av > bv) return dir === 'asc' ? 1 : -1; return 0; }).map(f => (
                            <tr key={f.id} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                              <td style={{ padding: '8px', color: '#f8fafc', fontWeight: 600, fontSize: 11, verticalAlign: 'top', wordBreak: 'break-word' }}>{f.start_city_country || '—'} <span style={{ color: '#94a3b8', fontSize: 10 }}>{f.start_airport || ''}</span></td>
                              <td style={{ padding: '8px', color: '#f8fafc', fontWeight: 600, fontSize: 11, verticalAlign: 'top', wordBreak: 'break-word' }}>
                                <div style={{ whiteSpace: 'nowrap' }}>{f.outbound_trip_date || f.trip_date} {fmtTime(f.outbound_departure)}</div>
                                <div style={{ color: '#cbd5e1', fontSize: 10 }}>{f.outbound_flight || f.outbound_flight_number || '—'}</div>
                              </td>
                              <td style={{ padding: '8px', color: '#f8fafc', fontWeight: 600, fontSize: 11, verticalAlign: 'top', wordBreak: 'break-word' }}>
                                <div style={{ whiteSpace: 'nowrap' }}>{f.return_trip_date || f.trip_date} {fmtTime(f.return_departure)}</div>
                                <div style={{ color: '#cbd5e1', fontSize: 10 }}>{f.return_flight || f.return_flight_number || '—'}</div>
                              </td>
                              <td style={{ padding: '8px', color: '#38bdf8', fontWeight: 700, fontSize: 11, verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                <div>Total: {f.price_total != null ? f.price_total + ' €' : 'none / unavailable'}</div>
                                <div style={{ fontSize: 9, color: '#cbd5e1' }}>{f.price_outbound != null ? 'Outbound: ' + f.price_outbound + ' €' : 'Outbound: —'} | {f.price_return != null ? 'Return: ' + f.price_return + ' €' : 'Return: —'}</div>
                                <div style={{ fontSize: 9, color: '#94a3b8' }}>(updated: {f.fetched_at ? new Date(f.fetched_at).toLocaleDateString() : '—'})</div>
                              </td>
                              <td style={{ padding: '8px', textAlign: 'center', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                                <div style={{ display: 'flex', gap: 6, justifyContent: 'center', flexWrap: 'wrap' }}>
                                  <button onClick={() => openChartFor(f.id)} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: '#38bdf8', color: '#0f172a', fontSize: 12, fontWeight: 700, cursor: 'pointer', minWidth: 44, minHeight: 44 }}>Chart</button>
                                  <button onClick={async () => { await fetch('/api/favorites/'+f.id, {method:'DELETE'}); load(); }} style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: '#ef4444', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', minWidth: 44, minHeight: 44 }}>Delete</button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                </div>
              )}
            </div>
          );
        })}
      <ChartModal open={chartOpen} onClose={() => setChartOpen(false)} data={chartData} />
      <ConfirmDialog />
    </div>
  );
}
