import React, { useState, useEffect } from 'react';

function getMonday(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
}

function formatDate(date) {
  return date.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' });
}

export default function WeekPicker({ value, onChange }) {
  const [weekStart, setWeekStart] = useState(() => getMonday(value || new Date()));

  useEffect(() => {
    if (value) setWeekStart(getMonday(value));
  }, [value]);

  const shiftWeek = (delta) => {
    const newStart = new Date(weekStart.getTime() + delta * 7 * 86400000);
    setWeekStart(newStart);
    const monday = getMonday(newStart);
    onChange(monday.toISOString().split('T')[0]);
  };

  const days = [];
  for (let i = 0; i < 7; i++) {
    const day = new Date(weekStart.getTime() + i * 86400000);
    days.push(day);
  }

  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
      <button onClick={() => shiftWeek(-1)} style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#6366f1,#4f46e5)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}>◀ Previous Week</button>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {days.map((day, idx) => (
          <button key={idx} onClick={() => { setWeekStart(getMonday(day)); onChange(day.toISOString().split('T')[0]); }} style={{ padding: '8px 12px', borderRadius: 8, border: 'none', background: value && day.toISOString().split('T')[0] === value ? 'linear-gradient(135deg,#38bdf8,#818cf8)' : 'rgba(255,255,255,0.06)', color: value && day.toISOString().split('T')[0] === value ? '#0f172a' : '#cbd5e1', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>
            {formatDate(day)}
          </button>
        ))}
      </div>
      <button onClick={() => shiftWeek(1)} style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#6366f1,#4f46e5)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}>Next Week ▶</button>
    </div>
  );
}