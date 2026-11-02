// Trip search configuration helpers — browser-side only, persisted in the
// user's localStorage (never in the SQLite DB). A saved configuration holds
// exactly the six configurable search fields below; airport selection and the
// date range are intentionally not part of a configuration.

export const CONFIG_STORAGE_KEY = 'skybreak.tripSearchConfigs.v1';

export const CONFIG_FIELDS = ['startWeekdays', 'endWeekdays', 'maxDepToDest', 'minRetDep', 'minTripDays', 'maxTripDays'];

const WEEKDAY_COUNT = 7; // same convention as the API: 0=Monday .. 6=Sunday

function toWeekdays(value) {
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  for (const v of value) {
    const n = Number(v);
    if (Number.isInteger(n) && n >= 0 && n < WEEKDAY_COUNT) seen.add(n);
  }
  return [...seen].sort((a, b) => a - b);
}

function toTime(value) {
  return typeof value === 'string' && /^\d{2}:\d{2}$/.test(value.trim()) ? value.trim() : '';
}

function toDays(value) {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 ? n : null;
}

// Normalizes one raw entry into a valid configuration, or null if it is not
// usable (wrong shape, empty name). Corrupt localStorage must never crash the tab.
function sanitizeConfig(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const name = typeof raw.name === 'string' ? raw.name.trim() : '';
  if (!name) return null;
  const config = { name };
  for (const field of CONFIG_FIELDS) {
    if (field === 'startWeekdays' || field === 'endWeekdays') config[field] = toWeekdays(raw[field]);
    else if (field === 'maxDepToDest' || field === 'minRetDep') config[field] = toTime(raw[field]);
    else config[field] = toDays(raw[field]);
  }
  return config;
}

export function readTripConfigs(storage) {
  try {
    const raw = storage.getItem(CONFIG_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(sanitizeConfig).filter(Boolean);
  } catch (e) {
    return [];
  }
}

export function writeTripConfigs(configs, storage) {
  storage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(configs));
}

// Adds or replaces a configuration; names compare case-insensitively.
export function upsertTripConfig(configs, config) {
  const name = typeof config.name === 'string' ? config.name.trim() : '';
  if (!name) throw new Error('Configuration needs a name');
  const clean = sanitizeConfig({ ...config, name });
  const rest = configs.filter(c => c.name.toLowerCase() !== name.toLowerCase());
  return [...rest, clean];
}

export function deleteTripConfig(configs, name) {
  const target = typeof name === 'string' ? name.trim().toLowerCase() : '';
  if (!target) return configs;
  return configs.filter(c => c.name.toLowerCase() !== target);
}
