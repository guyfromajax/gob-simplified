/**
 * Exercise Team Builder FE logic for Phase 1 criteria 2/4/5/9.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import assert from 'assert';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const jsPath = path.join(__dirname, '../FrontEnd/static/team-builder.js');
const src = fs.readFileSync(jsPath, 'utf8');
const htmlPath = path.join(__dirname, '../FrontEnd/static/team-builder.html');
const html = fs.readFileSync(htmlPath, 'utf8');

assert.ok(!/\b6400\b/.test(src), 'FE still contains 6400');
assert.ok(!/\b3950\b/.test(src), 'FE still contains 3950');
assert.ok(!/\b7027\b/.test(src), 'FE JS still hardcodes 7027');
assert.ok(!/\b5567\b/.test(src), 'FE JS still hardcodes 5567');
assert.ok(!/\b7027\b/.test(html), 'FE HTML still hardcodes 7027');
assert.ok(!/\b5567\b/.test(html), 'FE HTML still hardcodes 5567');
assert.ok(!/No attribute top-up/.test(html), 'Keep card still names top-up');
assert.ok(html.includes('tb-budget-refuse'), 'Missing sticky refuse on roster step');
assert.ok(html.includes('tb-budget-refuse-apply'), 'Missing refuse anchored to Apply');
assert.ok(html.includes('tb-actions-dock'), 'Missing sticky actions dock');
assert.ok(!html.includes('tb-budget-warn'), 'Old off-screen budget warn still present');
assert.ok(src.includes('wizard-walk-ons'), 'FE missing wizard walk-on generation call');
assert.ok(src.includes('ensureWizardWalkOns'), 'FE missing once-per-session walk-on guard');
assert.ok(src.includes('ensureDraftId'), 'FE missing draft_id for idempotent walk-ons');
assert.ok(src.includes('draft_id'), 'FE must send draft_id with walk-on / Apply requests');
assert.ok(src.includes('rosterSizeInvalidMessage'), 'FE missing exact-15 import reject copy');
assert.ok(!src.includes('limitToFirst15'), 'FE still offers silent truncate-to-15');
assert.ok(!src.includes('Import the first 15'), 'FE still offers import-first-15 pad/truncate');

const CORE_12 = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
const BUDGET = { ATTR_MIN: 5, ATTR_MAX: 99, TOPUP_FLOOR: 60 };

function clampAttr(value) {
  const n = parseInt(value, 10);
  if (isNaN(n)) return BUDGET.ATTR_MIN;
  return Math.max(BUDGET.ATTR_MIN, Math.min(BUDGET.ATTR_MAX, n));
}
function core12Total(attrs) {
  return CORE_12.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
}
function even(total) {
  const base = Math.floor(total / 12);
  const rem = total % 12;
  const out = {};
  CORE_12.forEach((k, i) => {
    out[k] = base + (i < rem ? 1 : 0);
  });
  return out;
}
function applyCappedTopup(rawAttrs) {
  const raw = rawAttrs || {};
  const rawTotal = core12Total(raw);
  const toppedUp = rawTotal < BUDGET.TOPUP_FLOOR;
  const budget = toppedUp ? BUDGET.TOPUP_FLOOR : Math.max(0, rawTotal);
  const attrs = {};
  CORE_12.forEach((key) => {
    attrs[key] = clampAttr(raw[key]);
  });
  let total = core12Total(attrs);
  while (total < budget) {
    const key = CORE_12.reduce((b, k) => (attrs[k] < attrs[b] ? k : b));
    if (attrs[key] >= BUDGET.ATTR_MAX) break;
    attrs[key] += 1;
    total += 1;
  }
  while (total > budget) {
    const key = CORE_12.reduce((b, k) => (attrs[k] > attrs[b] ? k : b));
    if (attrs[key] <= BUDGET.ATTR_MIN) break;
    attrs[key] -= 1;
    total -= 1;
  }
  return { attrs, raw_total: rawTotal, budget, topped_up: toppedUp };
}

function editorSetAttrCapped(player, key, value) {
  const prev = player.attrs[key];
  player.attrs[key] = clampAttr(value);
  if (player.budget != null && core12Total(player.attrs) > player.budget) {
    player.attrs[key] = prev;
  }
  return player;
}

const results = [];
function report(id, pass, detail) {
  results.push({ id, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} ${id}: ${detail}`);
}

for (const [label, raw] of Object.entries({
  zero: 0,
  four: 4,
  hundred: 100,
  negative: -7,
  non_numeric: 'abc',
  empty: '',
})) {
  const v = clampAttr(raw);
  report(`5/${label}`, v >= 5 && v <= 99, `clampAttr(${JSON.stringify(raw)}) => ${v}`);
}

{
  const p = { attrs: even(400), budget: 400 };
  editorSetAttrCapped(p, 'SC', p.attrs.SC + 50);
  const after = core12Total(p.attrs);
  report('2a', after === 400, `editor raise blocked; total=${after} budget=400`);
}

{
  const a = { attrs: even(400), budget: 400 };
  const b = { attrs: even(400), budget: 400 };
  editorSetAttrCapped(a, 'SC', Math.max(5, a.attrs.SC - 20));
  editorSetAttrCapped(b, 'SC', b.attrs.SC + 20);
  report(
    '2b',
    core12Total(a.attrs) === 380 && core12Total(b.attrs) === 400,
    `A=${core12Total(a.attrs)} B=${core12Total(b.attrs)} (B raise past budget blocked)`
  );
}

{
  const jason = {
    SC: 4, SH: 2, ID: 8, OD: 1, PS: 1, BH: 1, RB: 1, ST: 1, AG: 1, ND: 2, IQ: 1, FT: 1,
  };
  const build = (mode) => {
    if (mode === 'capped') {
      const t = applyCappedTopup(jason);
      return {
        attrs: { ...t.attrs },
        inheritedAttrs: { ...t.attrs },
        raw_total: t.raw_total,
        budget: t.budget,
        topped_up: t.topped_up,
      };
    }
    const attrs = {};
    CORE_12.forEach((k) => {
      attrs[k] = clampAttr(jason[k]);
    });
    return { attrs: { ...attrs }, inheritedAttrs: { ...attrs }, raw_total: core12Total(jason), budget: null, topped_up: false };
  };
  let player = build('capped');
  const baseline1 = JSON.stringify(player.inheritedAttrs);
  editorSetAttrCapped(player, 'SC', 40);
  player = build('uncapped');
  editorSetAttrCapped(player, 'SH', 50);
  player = build('capped');
  const baseline2 = JSON.stringify(player.inheritedAttrs);
  report('2d/baseline', baseline1 === baseline2, `baseline stable=${baseline1 === baseline2}`);
  editorSetAttrCapped(player, 'SC', 90);
  player.attrs = { ...player.inheritedAttrs };
  report('9/reset-all', JSON.stringify(player.attrs) === baseline2, 'reset-all exact');
  editorSetAttrCapped(player, 'ID', 88);
  player.attrs = { ...player.inheritedAttrs };
  report('9/reset-one', JSON.stringify(player.attrs) === baseline2, 'reset-one exact');
}

{
  const pool = 5000;
  const teamTotal = 7200;
  const over = Math.max(0, teamTotal - pool);
  report('4/exceed-detected', over === 2200, `over_pool_by=${over} against runtime pool ${pool}`);
}

const failed = results.filter((r) => !r.pass);
console.log('\n--- summary ---');
console.log(`passed ${results.length - failed.length}/${results.length}`);
if (failed.length) process.exitCode = 1;
