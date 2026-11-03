import { useCallback, useEffect, useState } from 'react';
import {
  migrateLegacyConfigs, deleteTripConfig, upsertTripConfig,
} from '../utils/tripConfigs';

const API_URL = '/api/trip-configs';

function postConfig(config) {
  return fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  }).then(r => (r.ok ? r.json() : Promise.reject(new Error(`save failed: ${r.status}`))));
}

// Owns the saved trip search configurations for the Trips tab. They are stored
// in the server-side SQLite DB, so every browser and device sees the same set.
export function useTripConfigs() {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(() => {
    return fetch(API_URL)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`load failed: ${r.status}`))))
      .then(data => {
        setConfigs(Array.isArray(data) ? data : []);
        setError('');
      })
      .catch(() => setError('Could not load the saved configurations from the server.'));
  }, []);

  useEffect(() => {
    let alive = true;
    migrateLegacyConfigs(window.localStorage, postConfig)
      .then(refresh)
      .then(() => { if (alive) setLoading(false); })
      .catch(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [refresh]);

  // Upsert/delete are applied against the local copy only after the server
  // confirms, so the list always reflects what is actually shared everywhere.
  const saveConfig = useCallback((config) => {
    let next;
    try {
      next = upsertTripConfig(configs, config);
    } catch (e) {
      return Promise.resolve({ ok: false, error: e.message });
    }
    return postConfig(config)
      .then(() => {
        setConfigs(next);
        setError('');
        return { ok: true, name: config.name.trim() };
      })
      .catch(() => {
        setError('Could not save the configuration to the server.');
        return { ok: false, error: 'Could not save the configuration to the server.' };
      });
  }, [configs]);

  const removeConfig = useCallback((name) => {
    const next = deleteTripConfig(configs, name);
    return fetch(`/api/trip-configs/${encodeURIComponent(name)}`, { method: 'DELETE' })
      .then(r => (r.ok || r.status === 404 ? r.json() : Promise.reject(new Error(`delete failed: ${r.status}`))))
      .then(() => {
        setConfigs(next);
        setError('');
        return { ok: true };
      })
      .catch(() => {
        setError('Could not delete the configuration on the server.');
        return { ok: false, error: 'Could not delete the configuration on the server.' };
      });
  }, [configs]);

  return { configs, loading, error, saveConfig, removeConfig, refresh };
}
