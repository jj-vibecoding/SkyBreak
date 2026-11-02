import { useState } from 'react';
import { readTripConfigs, writeTripConfigs, upsertTripConfig, deleteTripConfig } from '../utils/tripConfigs';

// Owns the saved trip search configurations for the Trips tab. State is kept
// in React and mirrored to window.localStorage so it survives reloads; all
// persistence stays browser-side (per user/browser), never in the SQLite DB.
export function useTripConfigs() {
  const [configs, setConfigs] = useState(() => readTripConfigs(window.localStorage));

  const saveConfig = (config) => {
    let next;
    try {
      next = upsertTripConfig(configs, config);
    } catch (e) {
      return { ok: false, error: e.message };
    }
    setConfigs(next);
    writeTripConfigs(next, window.localStorage);
    return { ok: true, name: config.name.trim() };
  };

  const removeConfig = (name) => {
    const next = deleteTripConfig(configs, name);
    setConfigs(next);
    writeTripConfigs(next, window.localStorage);
  };

  return { configs, saveConfig, removeConfig };
}
