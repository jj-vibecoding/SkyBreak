// D6/D9: Responsive ChartModal — touch targets ≥44px, tooltip clamp, tick thinning (Fix #6, #10).
import React, { useState, useEffect } from 'react';

// Current chart viewBox width (responsive to viewport, capped at 720px)
function getChartWidth() {
  return typeof window !== 'undefined' ? Math.min(window.innerWidth - 48, 720) : 720;
}

function ChartModal({ open, onClose, data }) {
  const [chartPoints, setChartPoints] = useState([]);
  const [dataPointsOpen, setDataPointsOpen] = useState(false);

  const parseDate = (s) => {
    if (!s) return null;
    const str = String(s).trim();
    if (str.includes('-')) {
      const [y, m, d] = str.split('-').map(Number);
      if (y && m && d) return new Date(y, m - 1, d).getTime();
    }
    if (str.includes('.')) {
      const parts = str.split('.');
      if (parts.length === 3) {
        const [d, m, y] = parts.map(Number);
        if (y && m && d) return new Date(y, m - 1, d).getTime();
      }
    }
    return null;
  };

  useEffect(() => {
    if (!open) return;
    const safeData = Array.isArray(data) ? data : [];
    const maxVal = safeData.length > 0
      ? Math.max(...safeData.map(d => Math.max(d.total_price || 0, d.outbound_price || 0, d.return_price || 0))) || 1
      : 1;
    const times = safeData.map(d => parseDate(d.date));
    const validTimes = times.filter(t => t != null);
    const minT = validTimes.length ? Math.min(...validTimes) : 0;
    const maxT = validTimes.length ? Math.max(...validTimes) : 0;
    const range = Math.max(1, maxT - minT);
    const w = getChartWidth();
    const pts = safeData.map((d, i) => {
      const t = times[i] != null ? times[i] : minT + (i / Math.max(1, safeData.length - 1)) * range;
      // x-coordinates scale with the current viewBox width so the chart fills it on any screen
      const nx = safeData.length <= 1 ? (w + 20) / 2 : 60 + ((t - minT) / range) * (w - 140);
      return {
        x: nx,
        out: 30 + 150 - ((d.outbound_price || 0) / maxVal) * 130,
        ret: 30 + 150 - ((d.return_price || 0) / maxVal) * 130,
        tot: 30 + 150 - ((d.total_price || 0) / maxVal) * 130,
        d
      };
    });
    setChartPoints(pts);
  }, [open, data, getChartWidth()]);

  if (!open) return null;
  const safeData = Array.isArray(data) ? data : [];
  const maxVal = safeData.length > 0
    ? Math.max(...safeData.map(d => Math.max(d.total_price || 0, d.outbound_price || 0, d.return_price || 0))) || 1
    : 1;
  const ticks = [0, Math.round(maxVal / 4), Math.round(maxVal / 2), Math.round(3 * maxVal / 4), maxVal];
  const isSingle = safeData.length === 1 || (safeData.length > 0 && chartPoints.length === 1);

  // SVG dimensions responsive to viewport
  const svgWidth = typeof window !== 'undefined' ? Math.min(window.innerWidth - 48, 720) : 720;
  // On narrow screens the legend moves below the chart → taller viewBox
  const legendBelow = svgWidth < 480;
  const svgHeight = isSingle ? (legendBelow ? 310 : 180) : (legendBelow ? 290 : 260);

  // --- D9: Tooltip Rect clamped to the responsive viewBox width ---
  const CLAMP_MIN = 5;
  const CLAMP_MAX = Math.max(CLAMP_MIN, svgWidth - 5);
  const clampedX = (x) => Math.max(CLAMP_MIN, Math.min(CLAMP_MAX, x));

  // --- D9: Tick thinning — max ~8 date labels, first + last always shown ---
  const MAX_TICKS = 8;
  const thinTicks = () => {
    const n = chartPoints.length;
    if (n <= MAX_TICKS) return chartPoints.map((p, i) => ({ ...p, idx: i }));
    const step = Math.floor(n / MAX_TICKS);
    const indices = new Set();
    for (let i = 0; i < n; i += step) indices.add(i);
    indices.add(0);
    indices.add(n - 1);
    return chartPoints.map((p, i) => ({ ...p, idx: i })).filter(p => indices.has(p.idx));
  };
  const displayedTicks = thinTicks();

  return (
    <div
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(2,6,23,0.88)', zIndex: 999,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#0b1121', padding: 24,
          borderRadius: 16, maxWidth: svgWidth > 600 ? 760 : '96%', width: svgWidth > 600 ? '94%' : '98%',
          maxHeight: '88vh', overflow: 'auto',
          border: '1px solid rgba(148,163,184,0.15)',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.7)'
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <h3 style={{ color: '#f1f5f9', margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: 0.3 }}>Price Trend</h3>
          <button
            onClick={e => { e.stopPropagation(); onClose(); }} className="tap"
            style={{ 
              padding: '10px 16px', borderRadius: 10, 
              border: 'none', background: '#334155', color: '#e2e8f0', 
              fontWeight: 600, fontSize: 14, cursor: 'pointer',
              minWidth: 44, minHeight: 44,
            }}
          >
            Close
          </button>
        </div>

        <div style={{ background: '#111827', borderRadius: 12, padding: 16, border: '1px solid rgba(148,163,184,0.12)' }}>
          <svg
            width="100%"
            height={svgHeight}
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ display: 'block' }}
          >
            <rect x="0" y="0" width={svgWidth} height={svgHeight} fill="#0b1220" rx="8" />
            {ticks.map((t, i) => {
              const y = 30 + 150 - (t / maxVal) * 130;
              const labelX = 50;
              return (
                <g key={"grid"+i}>
                  <line x1="60" y1={y} x2={svgWidth - 40} y2={y} stroke="#1e293b" strokeWidth="1" />
                  <text x={labelX} y={y + 4} textAnchor="end" fill="#94a3b8" fontSize="10">{t}</text>
                </g>
              );
            })}
            <line x1="60" y1="30" x2="60" y2="180" stroke="#334155" strokeWidth="1.5" />
            <line x1="60" y1="180" x2={svgWidth - 40} y2="180" stroke="#334155" strokeWidth="1.5" />
            <text x={svgWidth / 2} y="205" textAnchor="middle" fill="#cbd5e1" fontSize="11" fontWeight="600">Date →</text>
            <text x="18" y="110" textAnchor="middle" fill="#cbd5e1" fontSize="11" fontWeight="600" transform="rotate(-90 18 110)">Price (€) ↑</text>

            {chartPoints.map((p, i) => (
              <g key={"pt"+i}>
                <circle cx={p.x} cy={p.out} r="4" fill="#38bdf8" stroke="#0f172a" strokeWidth="1.5" />
                <circle cx={p.x} cy={p.ret} r="4" fill="#f97316" stroke="#0f172a" strokeWidth="1.5" />
                <circle cx={p.x} cy={p.tot} r="5" fill="#10b981" stroke="#0f172a" strokeWidth="1.5" />
                {isSingle && (
                  <g>
                    <rect x={clampedX(p.x) - 55} y={p.tot - 45} width="110" height="34" rx="6" fill="#1e293b" stroke="#334155" strokeWidth="1" />
                    <text x={clampedX(p.x)} y={p.tot - 28} textAnchor="middle" fill="#f8fafc" fontSize="10" fontWeight="600">{p.d.date || '-'}</text>
                    <text x={clampedX(p.x)} y={p.tot - 14} textAnchor="middle" fill="#38bdf8" fontSize="9">Out {p.d.outbound_price ?? '—'} €</text>
                  </g>
                )}
              </g>
            ))}

            {chartPoints.length > 1 && (
              <>
                <polyline points={chartPoints.map(p => `${p.x},${p.out}`).join(' ')} fill="none" stroke="#38bdf8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points={chartPoints.map(p => `${p.x},${p.ret}`).join(' ')} fill="none" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points={chartPoints.map(p => `${p.x},${p.tot}`).join(' ')} fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </>
            )}

            {isSingle && chartPoints.length === 1 && (
              <text x={svgWidth / 2} y={legendBelow ? 302 : 245} textAnchor="middle" fill="#94a3b8" fontSize="10">Only one price entry available</text>
            )}

            {/* D9: Thin date labels — max ~8, first + last always shown */}
            {displayedTicks.map((p) => (
              <text key={"x"+p.idx} x={p.x} y={isSingle ? 165 : 245} textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="500">
                {p.d.date ? String(p.d.date).split("-")[2] + ".." + String(p.d.date).split("-")[1] : '-'}
              </text>
            ))}

            {/* D9: Responsive legend — moves below chart on narrow screens */}
            {legendBelow ? (
              /* Legend below chart for narrow viewports */
              <g>
                <rect x="60" y={isSingle ? 205 : 258} width="170" height="50" rx="6" fill="#0b1220" stroke="#334155" strokeWidth="1" />
                <line x1="70" y1={isSingle ? 218 : 271} x2="88" y2={isSingle ? 218 : 271} stroke="#38bdf8" strokeWidth="3" />
                <circle cx="79" cy={isSingle ? 218 : 271} r="2.5" fill="#38bdf8" />
                <text x="96" y={isSingle ? 222 : 275} fill="#e2e8f0" fontSize="10" fontWeight="600">Outbound</text>
                <line x1="70" y1={isSingle ? 232 : 285} x2="88" y2={isSingle ? 232 : 285} stroke="#f97316" strokeWidth="3" />
                <circle cx="79" cy={isSingle ? 232 : 285} r="2.5" fill="#f97316" />
                <text x="96" y={isSingle ? 236 : 289} fill="#e2e8f0" fontSize="10" fontWeight="600">Return</text>
                <line x1="70" y1={isSingle ? 246 : 299} x2="88" y2={isSingle ? 246 : 299} stroke="#10b981" strokeWidth="3" />
                <circle cx="79" cy={isSingle ? 246 : 299} r="2.5" fill="#10b981" />
                <text x="96" y={isSingle ? 250 : 303} fill="#e2e8f0" fontSize="10" fontWeight="600">Total</text>
              </g>
            ) : (
              /* Original legend position for wider screens */
              <g transform={`translate(${svgWidth - 180}, 10)`}>
                <rect x="0" y="-2" width="170" height="42" rx="6" fill="#0b1220" stroke="#334155" strokeWidth="1" />
                <line x1="10" y1="10" x2="28" y2="10" stroke="#38bdf8" strokeWidth="3" />
                <circle cx="19" cy="10" r="2.5" fill="#38bdf8" />
                <text x="36" y="14" fill="#e2e8f0" fontSize="10" fontWeight="600">Outbound</text>
                <line x1="10" y1="22" x2="28" y2="22" stroke="#f97316" strokeWidth="3" />
                <circle cx="19" cy="22" r="2.5" fill="#f97316" />
                <text x="36" y="26" fill="#e2e8f0" fontSize="10" fontWeight="600">Return</text>
                <line x1="10" y1="34" x2="28" y2="34" stroke="#10b981" strokeWidth="3" />
                <circle cx="19" cy="34" r="2.5" fill="#10b981" />
                <text x="36" y="38" fill="#e2e8f0" fontSize="10" fontWeight="600">Total</text>
              </g>
            )}
          </svg>
        </div>

        <div style={{ marginTop: 14, background: '#111827', padding: 12, borderRadius: 10, border: '1px solid rgba(148,163,184,0.1)' }}>
          <button onClick={() => setDataPointsOpen(o => !o)} className="tap" style={{ 
            width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
            background: 'none', border: 'none', padding: '12px 16px', 
            cursor: 'pointer', minWidth: 44, minHeight: 44
          }}>
            <h4 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>Data Points</h4>
            <span style={{ color: '#94a3b8', fontSize: 14, fontWeight: 700 }}>{dataPointsOpen ? '−' : '+'}</span>
          </button>
          {dataPointsOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
              {safeData.map((d, idx) => (
                <div key={d.date + '-' + idx} style={{ background: '#0b1220', padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(148,163,184,0.08)' }}>
                  <div style={{ color: '#cbd5e1', fontWeight: 600, fontSize: 12 }}>{d.date ? String(d.date) : '—'}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                    Outbound <span style={{ color: '#38bdf8', fontWeight: 600 }}>{d.outbound_price ?? '—'} €</span> · Return <span style={{ color: '#f97316', fontWeight: 600 }}>{d.return_price ?? '—'} €</span> · Total <span style={{ color: '#10b981', fontWeight: 700 }}>{d.total_price ?? '—'} €</span>
                  </div>
                </div>
              ))}
              {safeData.length === 0 && (
                <div style={{ color: '#94a3b8', fontSize: 12, padding: 10 }}>No price history available for this trip.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChartModal;
