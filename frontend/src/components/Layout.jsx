import React from 'react';

const sectionStyle = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 18,
  padding: 24,
  boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
};

export default function Layout({ title, children, actions }) {
  return (
    <section style={sectionStyle}>
      {(title || actions) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          {title && <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#f8fafc' }}>{title}</h3>}
          {actions && <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}