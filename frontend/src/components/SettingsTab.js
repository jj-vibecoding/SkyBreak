// D6/D10: Responsive SettingsTab — toast for save feedback (Fix #12), 
//        touch targets ≥44px (Fix #6), English UI (Fix #16).
import React, { useState, useEffect } from 'react';

const inputStyle = {
  padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.15)',
  background: 'rgba(255,255,255,0.06)', color: '#f8fafc', fontSize: 15, outline: 'none', width: '100%',
};

const SOCS_DEFAULT = 'CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmRlIAEaBgiAo_CmBg';

// Self-contained settings form: loads on mount, saves on submit.
export default function SettingsTab() {
  const [settings, setSettings] = useState({
    fetch_max_months: '1', scrape_delay_ms: '500',
    price_fetch_interval_hours: '6', refresh_interval_days: '7',
    google_consent_cookie: SOCS_DEFAULT,
  });
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [testSending, setTestSending] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(data => {
      setSettings({
        fetch_max_months: data.fetch_max_months || data.fetch_max_days || '1',
        scrape_delay_ms: data.scrape_delay_ms || '500',
        price_fetch_interval_hours: data.price_fetch_interval_hours || '6',
        refresh_interval_days: data.refresh_interval_days || '7',
        google_consent_cookie: data.google_consent_cookie || SOCS_DEFAULT,
      });
      setTelegramToken(data.telegram_bot_token || '');
      setTelegramChatId(data.telegram_chat_id || '');
    }).catch(() => {});
  }, []);

  const testNotification = async () => {
    setTestSending(true);
    try {
      const res = await fetch('/api/notifications/test', { method: 'POST' });
      const data = await res.json();
      if (data.sent) {
        showToast('Test notification sent successfully!', 'success');
      } else {
        showToast(`Failed: ${data.detail || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error');
    }
    setTestSending(false);
  };

  const showToast = (message, type) => {
    window.dispatchEvent(new CustomEvent('showToast', { 
      detail: { message, type: type || 'info' } 
    }));
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const body = {
      fetch_max_months: settings.fetch_max_months,
      scrape_delay_ms: settings.scrape_delay_ms,
      price_fetch_interval_hours: settings.price_fetch_interval_hours,
      refresh_interval_days: settings.refresh_interval_days,
      google_consent_cookie: settings.google_consent_cookie,
      telegram_bot_token: telegramToken || undefined,
      telegram_chat_id: telegramChatId || undefined,
    };
    const res = await fetch('/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    if (res.ok) {
      // Fix #12: Use toast instead of alert
      showToast('Settings saved successfully', 'success');
      setSettings(body);
    } else {
      showToast('Failed to save settings', 'error');
    }
    setSaving(false);
  };

  const handleSaveTelegram = async () => {
    const res = await fetch('/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_bot_token: telegramToken || undefined, telegram_chat_id: telegramChatId || undefined }),
    });
    if (res.ok) showToast('Telegram settings saved', 'success');
    else showToast('Failed to save Telegram settings', 'error');
  };

  return (
    <>
      <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 16 }}>Configure max fetch months and scrape delay.</p>
      <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="fetchMaxMonths" style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>Max Fetch Months (1-12)</label>
          <input id="fetchMaxMonths" type="number" min="1" max="12" value={settings.fetch_max_months || '1'}
            onChange={e => setSettings(s => ({ ...s, fetch_max_months: e.target.value }))} placeholder="Months"
            style={{ ...inputStyle, maxWidth: 420 }} />
          <span style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5, maxWidth: 360 }}>
            The parameter <code>fetch_max_months</code> controls how many months ahead flight data is fetched. It is globally shared between all airports.
          </span>
        </div>
        <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>Price Update Interval (Hours)</h4>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>How often favorite prices are updated automatically. Default 6h.</p>
          <input id="priceIntervalHours" type="number" min="1" max="168" value={settings.price_fetch_interval_hours || '6'}
            onChange={e => setSettings(s => ({ ...s, price_fetch_interval_hours: e.target.value }))} placeholder="Hours"
            style={{ ...inputStyle, width: 140, fontSize: 14 }} />
        </div>
        <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>Flight Schedule Refresh (Days)</h4>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>How often flight schedules are refreshed automatically. Set to 0 to disable. Default 7 days.</p>
          <input id="refreshIntervalDays" type="number" min="0" max="365" value={settings.refresh_interval_days || '7'}
            onChange={e => setSettings(s => ({ ...s, refresh_interval_days: e.target.value }))} placeholder="Days"
            style={{ ...inputStyle, width: 140, fontSize: 14 }} />
        </div>
        <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>Scrape Delay (ms)</h4>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>Delay between kayak requests in milliseconds.</p>
          <input id="delayMs" type="number" min="0" max="5000" value={settings.scrape_delay_ms || '500'}
            onChange={e => setSettings(s => ({ ...s, scrape_delay_ms: e.target.value }))} placeholder="ms"
            style={{ ...inputStyle, width: 140, fontSize: 14 }} />
        </div>
        <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>Google Consent Cookie (SOCS)</h4>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>Cookie value for EU consent (Decline all).</p>
          <input id="consentCookie" type="text" value={settings.google_consent_cookie || SOCS_DEFAULT}
            onChange={e => setSettings(s => ({ ...s, google_consent_cookie: e.target.value }))} placeholder="SOCS Cookie Value"
            style={{ ...inputStyle, maxWidth: 520, fontSize: 14 }} />
        </div>
        <button type="submit" className="tap" style={{
          marginTop: 8, padding: '10px 18px', borderRadius: 10, border: 'none',
          background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
          color: '#0f172a', fontWeight: 700, fontSize: 15, cursor: saving ? 'not-allowed' : 'pointer',
          alignSelf: 'flex-start', opacity: saving ? 0.6 : 1
        }}>{saving ? 'Saving…' : 'Save'}</button>

        {/* Notifications Card */}
        <div style={{ marginTop: 24, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>📩 Notifications (Telegram)</h4>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 12 }}>Configure Telegram bot credentials to receive price alerts when monitored trips hit your target prices.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <label htmlFor="telegramBotToken" style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>Bot Token</label>
              <input id="telegramBotToken" type="password" value={telegramToken}
                onChange={e => setTelegramToken(e.target.value)} placeholder="123456:ABC-DEF..."
                style={{ ...inputStyle, maxWidth: 420, fontSize: 14 }} />
            </div>
            <div>
              <label htmlFor="telegramChatId" style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>Chat ID</label>
              <input id="telegramChatId" type="text" value={telegramChatId}
                onChange={e => setTelegramChatId(e.target.value)} placeholder="-1001234567890"
                style={{ ...inputStyle, maxWidth: 220, fontSize: 14 }} />
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 4 }}>
              <button onClick={handleSaveTelegram} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#38bdf8', color: '#0f172a', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                Save Telegram Settings
              </button>
              <button onClick={testNotification} disabled={testSending || !telegramToken || !telegramChatId}
                style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: testSending ? '#475569' : '#f59e0b', color: '#0f172a', fontWeight: 700, fontSize: 13, cursor: testSending || !telegramToken || !telegramChatId ? 'not-allowed' : 'pointer', opacity: testSending || !telegramToken || !telegramChatId ? 0.6 : 1 }}>
                {testSending ? 'Sending...' : 'Send Test Message'}
              </button>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}
