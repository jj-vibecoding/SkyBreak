// D6/D12: Responsive AirportsTab — touch targets ≥44px (Fix #6), 
//        explicit { text, tone } feedback state (Fix #19), English UI (Fix #16).
import React, { useState } from 'react';

export default function AirportsTab({ list, setList }) {
  const [code, setCode] = useState('');
  // Fix #19: Explicit tone field instead of text-matching for color
  const [feedback, setFeedback] = useState({ text: '', tone: 'default' });

  const submit = async (e) => {
    e.preventDefault();
    const raw = code.trim().toUpperCase();
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
      setCode('');
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

  const FEEDBACK_COLORS = {
    default: '#94a3b8',
    success: '#4ade80',
    error: '#f87171',
    info: '#38bdf8',
  };

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <h4 style={{ margin: '0 0 14px', fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>Add Airport</h4>
        <form onSubmit={submit} style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input id="codeInput" value={code} maxLength={3} placeholder="LHR"
            onChange={e => setCode(e.target.value.toUpperCase())}
            style={{
              flex: '1 1 120px', padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.15)',
              background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontSize: 15, outline: 'none'
            }} />
          <button type="submit" className="tap" style={{
            padding: '10px 18px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
            color: '#0f172a', fontWeight: 700, fontSize: 15, cursor: 'pointer', boxShadow: '0 4px 14px rgba(56,189,248,0.35)'
          }}>Save</button>
        </form>
        {/* Fix #19: Use tone field to determine color, not text matching */}
        <p style={{ margin: '12px 0 0', minHeight: 24, color: FEEDBACK_COLORS[feedback.tone], fontSize: 13, fontWeight: 500 }}>
          {feedback.text}
        </p>
      </div>

      <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
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
      </div>
    </>
  );
}
