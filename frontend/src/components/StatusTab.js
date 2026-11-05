// D10: Status tab — health dashboard + backup export/import.
import React, { useState, useEffect } from 'react';

const cardStyle = {
  background: 'rgba(255,255,255,0.04)',
  borderRadius: 14, padding: 20, border: '1px solid rgba(255,255,255,0.08)',
};

const badgeStyle = (color) => ({
  display: 'inline-block', padding: '3px 10px', borderRadius: 6, fontSize: 12,
  fontWeight: 600, background: `${color}22`, color, border: `1px solid ${color}44`,
});

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr.replace('Z', '+00:00'));
    const now = new Date();
    const diffMs = now - d;
    if (diffMs < 60_000) return 'just now';
    if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`;
    if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`;
    return `${Math.floor(diffMs / 86_400_000)}d ago`;
  } catch { return dateStr; }
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr.replace('Z', '+00:00'));
    return d.toLocaleString();
  } catch { return dateStr; }
}

// ── StatusTab ───────────────────────────────────────────────────────────────

export default function StatusTab() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchHealth = () => {
    setLoading(true);
    fetch('/api/health')
      .then(r => r.json())
      .then(data => { setHealth(data); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchHealth(); }, []);

  const handleExport = () => {
    window.dispatchEvent(new CustomEvent('showToast', {
      detail: { message: 'Preparing backup download…', type: 'info' }
    }));
    fetch('/api/backup/export')
      .then(r => r.json())
      .then(data => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `skybreak-backup-${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        window.dispatchEvent(new CustomEvent('showToast', {
          detail: { message: 'Backup exported', type: 'success' }
        }));
      })
      .catch(e => {
        window.dispatchEvent(new CustomEvent('showToast', {
          detail: { message: `Export failed: ${e.message}`, type: 'error' }
        }));
      });
  };

  const handleImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        fetch('/api/backup/import', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        })
        .then(r => r.json())
        .then(result => {
          if (r.ok) {
            window.dispatchEvent(new CustomEvent('showToast', {
              detail: { message: `Import successful: ${result.message}`, type: 'success' }
            }));
            fetchHealth(); // refresh
          } else {
            window.dispatchEvent(new CustomEvent('showToast', {
              detail: { message: `Import failed: ${result.error}`, type: 'error' }
            }));
          }
        })
        .catch(err => {
          window.dispatchEvent(new CustomEvent('showToast', {
            detail: { message: `Import failed: ${err.message}`, type: 'error' }
          }));
        });
      } catch (parseErr) {
        window.dispatchEvent(new CustomEvent('showToast', {
          detail: { message: 'Invalid JSON file', type: 'error' }
        }));
      }
    };
    reader.readAsText(file);
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>Loading…</div>;
  if (error) return <div style={{ ...cardStyle, color: '#f87171' }}>Error: {error}</div>;
  if (!health) return null;

  const staleCount = health.airports?.filter(a => a.stale).length || 0;

  return (
    <>
      {/* ── Pipeline Health Cards ─────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
        {/* Scrape Card */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>🔍 Flight Scraper</h4>
          {health.last_scrape ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: '#94a3b8' }}>Last run</span>
                <span style={badgeStyle(health.last_scrape.status === 'ok' ? '#34d399' : '#fbbf24')}>
                  {health.last_scrape.status}
                </span>
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
                Started: {formatDateTime(health.last_scrape.started_at)}
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
                Finished: {formatDateTime(health.last_scrape.finished_at)}
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1' }}>
                Airports: {health.last_scrape.airports ?? '—'} · Flights: {health.last_scrape.flights_saved ?? '—'}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Never run</div>
          )}
        </div>

        {/* Price Card */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>💰 Price Updates</h4>
          {health.last_price_run ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: '#94a3b8' }}>Last run</span>
                <span style={badgeStyle(health.last_price_run.status === 'ok' ? '#34d399' : '#fbbf24')}>
                  {health.last_price_run.status}
                </span>
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
                Total: {health.last_price_run.total ?? '—'} · Success: {health.last_price_run.success ?? '—'} · Failed: {health.last_price_run.failed ?? '—'}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Never run</div>
          )}
        </div>

        {/* Context Card */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>📊 Summary</h4>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
            DB Version: <strong>v{health.db_version}</strong>
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
            Flights: <strong>{health.flights_total ?? '—'}</strong>
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
            Favorites: {health.favorites_total}
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 4 }}>
            Cached Quotes: {health.quotes_cached}
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1' }}>
            Fetch Window: {health.fetch_max_months} month(s)
          </div>
        </div>
      </div>

      {/* ── Airport Freshness Table ───────────────────────────────────── */}
      <div style={{ ...cardStyle, marginTop: 16 }}>
        <h4 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>
          ✈️ Airport Data Freshness
          {staleCount > 0 && (
            <span style={{ ...badgeStyle('#fbbf24'), marginLeft: 10 }}>
              {staleCount} stale
            </span>
          )}
        </h4>
        {health.airports?.length === 0 ? (
          <div style={{ fontSize: 13, color: '#94a3b8' }}>No airports configured yet.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8' }}>Code</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8' }}>Name</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8' }}>Max Departure</th>
                  <th style={{ textAlign: 'center', padding: '8px 12px', color: '#94a3b8' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {health.airports.map(a => (
                  <tr key={a.code} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontWeight: 600 }}>{a.code}</td>
                    <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>{a.name}</td>
                    <td style={{ padding: '8px 12px', color: '#94a3b8', fontSize: 13 }}>
                      {a.max_departure ? formatDateTime(a.max_departure) : '—'}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                      {a.stale
                        ? <span style={badgeStyle('#fbbf24')}>Stale</span>
                        : <span style={badgeStyle('#34d399')}>Fresh</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Backup Section ────────────────────────────────────────────── */}
      <div style={{ ...cardStyle, marginTop: 16 }}>
        <h4 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>💾 Backup</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <button onClick={handleExport} style={{
            padding: '10px 18px', borderRadius: 10, border: 'none',
            background: 'linear-gradient(135deg, #34d399, #38bdf8)',
            color: '#0f172a', fontWeight: 700, fontSize: 14, cursor: 'pointer',
          }}>
            📥 Export Backup
          </button>
          <label style={{
            padding: '10px 18px', borderRadius: 10, border: 'none',
            background: 'linear-gradient(135deg, #fbbf24, #f97316)',
            color: '#0f172a', fontWeight: 700, fontSize: 14, cursor: 'pointer',
          }}>
            📤 Import Backup
            <input type="file" accept=".json,application/json" onChange={handleImport} style={{ display: 'none' }} />
          </label>
          <span style={{ fontSize: 12, color: '#64748b', maxWidth: 300 }}>
            Export includes airports, favorites, configs, and settings (no secrets). Import restores to the current database.
          </span>
        </div>
      </div>
    </>
  );
}
