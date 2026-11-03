"""Trip search configurations (save / load / delete).

Validation and the one-off localStorage takeover live as pure helper functions
in ``frontend/src/utils/tripConfigs.js``; the React hook turns them into REST
calls against the SQLite-backed API. The behaviour tests execute the real module
with Node (ESM) against an in-memory storage that implements the same interface
as ``window.localStorage``, with the network call injected — no mocks of the
logic under test. The remaining tests pin the wiring: exactly the six
configurable fields are part of a configuration, airport/date fields stay out,
and the hook talks to the API instead of localStorage.
"""
import pathlib
import re
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
MODULE = REPO / "frontend/src/utils/tripConfigs.js"
TRIPTAB = REPO / "frontend/src/components/TripsTab.js"
HOOK = REPO / "frontend/src/hooks/useTripConfigs.js"

STORAGE_KEY = "skybreak.tripSearchConfigs.v1"

# The six fields a saved configuration may contain — and nothing else.
CONFIG_FIELDS = [
    "startWeekdays",
    "endWeekdays",
    "maxDepToDest",
    "minRetDep",
    "minTripDays",
    "maxTripDays",
]
# Explicitly NOT persistable per requirement.
EXCLUDED_FIELDS = ["startAirport", "endAirport", "tripStart", "tripEnd"]

NODE_PREAMBLE = """
import assert from 'node:assert/strict';
import { readTripConfigs, upsertTripConfig, deleteTripConfig, migrateLegacyConfigs } from '__MODULE_URI__';

const KEY = '__STORAGE_KEY__';
function memStorage(initial) {
  const data = initial || {};
  return {
    getItem(k) { return Object.prototype.hasOwnProperty.call(data, k) ? data[k] : null; },
    setItem(k, v) { data[k] = String(v); },
    removeItem(k) { delete data[k]; },
  };
}
function seed(st, configs) { st.setItem(KEY, JSON.stringify(configs)); return st; }
const sample = {
  name: 'Wochenende',
  startWeekdays: [4],
  endWeekdays: [6],
  maxDepToDest: '18:00',
  minRetDep: '10:00',
  minTripDays: 2,
  maxTripDays: 5,
};
"""


def _run_node(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available in this environment")
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"node test failed\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


def _script(body):
    return (NODE_PREAMBLE + body).replace(
        "__MODULE_URI__", MODULE.as_uri()
    ).replace("__STORAGE_KEY__", STORAGE_KEY)


def test_module_exists():
    assert MODULE.is_file(), "frontend/src/utils/tripConfigs.js is missing"


def test_reads_stored_configs():
    _run_node(_script("""
let st = memStorage();
assert.deepEqual(readTripConfigs(st), []);
seed(st, [sample]);
assert.deepEqual(readTripConfigs(st), [sample]);
"""))


def test_upsert_replaces_case_insensitive_and_appends_new():
    _run_node(_script("""
let st = seed(memStorage(), [sample]);
const updated = { ...sample, name: 'wochenende', maxDepToDest: '17:00' };
let cfgs = upsertTripConfig(readTripConfigs(st), updated);
assert.equal(cfgs.length, 1);
assert.equal(cfgs[0].name, 'wochenende');
assert.equal(cfgs[0].maxDepToDest, '17:00');

const second = { ...sample, name: 'Langtrip', minTripDays: 5 };
cfgs = upsertTripConfig(cfgs, second);
assert.equal(cfgs.length, 2);
assert.equal(cfgs[1].name, 'Langtrip');
"""))


def test_delete_removes_case_insensitively():
    _run_node(_script("""
let st = seed(memStorage(), [sample, { ...sample, name: 'Langtrip' }]);
let cfgs = deleteTripConfig(readTripConfigs(st), 'LANGTRIP');
assert.equal(cfgs.length, 1);
assert.equal(cfgs[0].name, 'Wochenende');
cfgs = deleteTripConfig(cfgs, 'does-not-exist');
assert.equal(cfgs.length, 1);
"""))


def test_corrupt_or_foreign_data_is_tolerated():
    _run_node(_script("""
let st = memStorage({ [KEY]: '{ not json' });
assert.deepEqual(readTripConfigs(st), []);

st = memStorage({ [KEY]: '{"a":1}' });
assert.deepEqual(readTripConfigs(st), []);

st = memStorage({ [KEY]: JSON.stringify([
  { name: 'bad', startWeekdays: ['x', 9, 4], endWeekdays: null },
  'junk',
  42,
])});
let r = readTripConfigs(st);
assert.equal(r.length, 1);
assert.equal(r[0].name, 'bad');
assert.deepEqual(r[0].startWeekdays, [4]);
assert.deepEqual(r[0].endWeekdays, []);
"""))


def test_upsert_requires_a_name():
    _run_node(_script("""
let st = memStorage();
for (const bad of [{ name: '  ' }, {}]) {
  assert.throws(() => upsertTripConfig(readTripConfigs(st), bad));
}
"""))


def test_legacy_localstorage_is_pushed_to_the_backend_once():
    _run_node(_script("""
const posted = [];
const st = seed(memStorage(), [sample, { ...sample, name: 'Langtrip' }]);
const post = c => { posted.push(c); return Promise.resolve(c); };
const migrated = await migrateLegacyConfigs(st, post);
assert.equal(posted.length, 2);
assert.equal(posted[0].name, 'Wochenende');
assert.equal(migrated.length, 2);
// key removed so the takeover never repeats on the next load
assert.equal(st.getItem(KEY), null);
// second run has nothing left to push
await migrateLegacyConfigs(st, post);
assert.equal(posted.length, 2);
"""))


def test_legacy_migration_keeps_key_when_push_fails():
    _run_node(_script("""
const st = seed(memStorage(), [sample]);
await migrateLegacyConfigs(st, () => Promise.reject(new Error('offline')));
// entries must survive a failed push so a later load can retry
assert.notEqual(st.getItem(KEY), null);
assert.equal(readTripConfigs(st).length, 1);
"""))


def test_legacy_migration_on_empty_storage_is_a_noop():
    _run_node(_script("""
const st = memStorage();
let calls = 0;
const migrated = await migrateLegacyConfigs(st, () => { calls++; return Promise.resolve(); });
assert.equal(calls, 0);
assert.deepEqual(migrated, []);
"""))


def test_triptab_wires_config_controls():
    src = TRIPTAB.read_text()
    assert "from '../hooks/useTripConfigs'" in src, (
        "TripsTab must use the useTripConfigs hook"
    )
    for label in ("Save current search", "Load", "Delete"):
        assert label in src, f"TripsTab must render the '{label}' control"


def test_hook_persists_via_api():
    src = HOOK.read_text()
    assert "/api/trip-configs" in src, "the hook must persist through the backend API"
    assert "from '../utils/tripConfigs'" in src
    # localStorage is no longer the store; it is only read once to migrate the
    # old browser-side configurations into the DB.
    assert "writeTripConfigs" not in src


def test_hook_migrates_legacy_localstorage():
    src = HOOK.read_text()
    assert "migrateLegacyConfigs" in src, (
        "the hook must push existing localStorage configs to the DB once"
    )


def test_config_fields_are_exactly_the_six_search_fields():
    src = MODULE.read_text()
    match = re.search(r"CONFIG_FIELDS\s*=\s*\[([^\]]*)\]", src)
    assert match, "tripConfigs.js must export a CONFIG_FIELDS list"
    fields = re.findall(r"['\"](\w+)['\"]", match.group(1))
    assert sorted(fields) == sorted(CONFIG_FIELDS), (
        f"CONFIG_FIELDS must be exactly {CONFIG_FIELDS}, got {fields}"
    )


def test_excluded_fields_stay_out_of_the_module():
    src = MODULE.read_text()
    for field in EXCLUDED_FIELDS:
        assert field not in src, (
            f"'{field}' must not be part of a saved trip search configuration"
        )
    # The module is pure, self-contained browser-side storage logic: no imports,
    # no backend calls, no database access.
    assert "import " not in src
    assert "fetch(" not in src
    assert "sqlite3" not in src.lower()
