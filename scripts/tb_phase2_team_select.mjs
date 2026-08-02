/**
 * Team Builder Phase 2 — team select acceptance checks (offline helpers).
 */
import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import vm from 'vm';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pickerPath = path.join(__dirname, '../FrontEnd/static/js/shared/teamPicker.js');
const src = fs.readFileSync(pickerPath, 'utf8');

const sandbox = { window: {}, globalThis: {}, console };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.runInNewContext(src, sandbox);
const TP = sandbox.TeamPicker;

// Helpers return arrays from a vm sandbox realm; coerce before deepEqual.
function fromSandbox(value) {
  return JSON.parse(JSON.stringify(value));
}

const geos = fromSandbox(TP.distinctGeographies());
assert.strictEqual(geos.length, 56, 'geography filter must offer exactly 56 options');
assert.deepStrictEqual(fromSandbox(TP.conferencesForGeography('Texas')), [11, 12]);
assert.deepStrictEqual(fromSandbox(TP.conferencesForGeography('California')), [15, 16]);

// Synthetic 128 teams with tied prestige to force rank/tie-break banding.
const teams = [];
for (let i = 0; i < 128; i++) {
  teams.push({
    object_id: String(i).padStart(24, 'a'),
    team_id: 'T' + String(i).padStart(3, '0'),
    name: 'Team ' + i,
    conference: (i % 16) + 1,
    region: String.fromCharCode(65 + Math.floor((i % 16) / 2)),
    // Many ties on prestige — naive thresholds would fail.
    prestige: 500 - Math.floor(i / 8),
    total_player_attrs: 6000 - i * 3,
  });
}

const talent = fromSandbox(TP.assignRankBands(teams, 'total_player_attrs'));
const prestige = fromSandbox(TP.assignRankBands(teams, 'prestige'));
const tHist = fromSandbox(TP.bandSizeHistogram(talent));
const pHist = fromSandbox(TP.bandSizeHistogram(prestige));
assert.deepStrictEqual(
  [tHist[1], tHist[2], tHist[3], tHist[4], tHist[5]],
  [26, 25, 26, 25, 26],
  'talent band sizes'
);
assert.deepStrictEqual(
  [pHist[1], pHist[2], pHist[3], pHist[4], pHist[5]],
  [26, 25, 26, 25, 26],
  'prestige band sizes'
);

const talentBands = new Set(Object.values(talent));
const prestigeBands = new Set(Object.values(prestige));
assert.strictEqual(Object.keys(talent).length, 128);
assert.strictEqual(Object.keys(prestige).length, 128);
assert.deepStrictEqual([...talentBands].sort(), [1, 2, 3, 4, 5]);
assert.deepStrictEqual([...prestigeBands].sort(), [1, 2, 3, 4, 5]);

// region helper untouched
assert.strictEqual(TP.regionFromConference(1), 'A');
assert.strictEqual(TP.regionFromConference(16), 'H');

console.log('PASS geography count', geos.length);
console.log('PASS Texas →', TP.conferencesForGeography('Texas'));
console.log('PASS California →', TP.conferencesForGeography('California'));
console.log('PASS talent bands', tHist);
console.log('PASS prestige bands', pHist);
console.log('--- summary ---');
console.log('passed');
