// @ts-check
/**
 * Jamie rulings batch 2 (reports/jamie-decisions-2-2026-10-01.md, all approved).
 * Net rule: orange = "there are unsaved changes" and nothing else.
 *
 *  #1  ▲ green on data chips, ▼ neutral (never red)
 *  #2  W/L in tables: white WIN plate, outlined LOSS
 *  #3a rail count badge neutral      #3b .td-gate / .is-on neutral
 *  #3c Office blocking step neutral  #3d attitude bars: no orange stop
 *  #3e modal accent neutral default  #3f tutorial alert stays neutral
 *  #3g leave-confirm "Stay" neutral primary
 *  #4  no team-colour wash on the weekly / result card (.office-res gone)
 *  #5  red only on irreversible deletes (Home Base delete program)
 *
 * Computed-style guards; each test also writes a 1280 shot at scroll 0.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const OUT = process.env.JRB2_OUT || path.join(__dirname, '../../reports/jamie-rulings-batch-2');
const PREFIX = process.env.JRB2_PREFIX || 'after';
const FID = 'f-e2e-jrb2';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function parse(value) {
  const v = String(value || '');
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4] };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: m[1] * 255, g: m[2] * 255, b: m[3] * 255, a: m[4] == null ? 1 : +m[4] };
  return null;
}
/** Every colour in a computed value (box-shadow, gradients carry several). */
function colours(value) {
  const out = [];
  const re = /rgba?\([^)]*\)|color\(srgb[^)]*\)/gi;
  let m;
  while ((m = re.exec(String(value || '')))) { const p = parse(m[0]); if (p) out.push(p); }
  return out;
}
const isOrange = (p) => p.a > 0.02 && p.r > 200 && p.g > 100 && p.g < 200 && p.b < 110 && p.g - p.b > 40;
const isRed = (p) => p.a > 0.02 && p.r > 200 && p.g < 140 && p.b < 140;
const isGreen = (p) => p.a > 0.02 && p.g > 180 && p.r < 140 && p.b < 140;
const isNeutral = (p) => Math.max(p.r, p.g, p.b) - Math.min(p.r, p.g, p.b) < 24;
const anyOf = (value, fn) => colours(value).some(fn);
const allNeutral = (value) => colours(value).every(isNeutral);

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('.main').forEach((m) => { m.scrollTop = 0; }); });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-1280.png`) });
}

async function css(page, sel, props) {
  return page.locator(sel).first().evaluate((el, p) => {
    const cs = getComputedStyle(el);
    const o = {};
    p.forEach((k) => { o[k] = cs[k]; });
    return o;
  }, props);
}

function digest() {
  return {
    state: 'regular',
    what_moved: {
      national_rank: { now: 14, prev: 17, delta: 3 },
      conference_standing: { now: 2, prev: 3, delta: 1 },
      record: { wins: 16, losses: 5 },
      streak: 'W4',
      attribute_changes: [
        { player_id: 'p-park', name: 'Devin Park', attribute: 'SH', from: 7, to: 8, delta: 1 },
        { player_id: 'p-kerr', name: 'Silas Kerr', attribute: 'ST', from: 6, to: 5, delta: -1 },
      ],
    },
    team_snapshot: {
      state: 'ready',
      chemistry: { value: 18, max: 25 },
      attitude: {
        player_count: 12,
        buckets: [
          { id: 'em_0_19', count: 1 }, { id: 'em_20_39', count: 2 }, { id: 'em_40_59', count: 4 },
          { id: 'em_60_79', count: 3 }, { id: 'em_80_plus', count: 2 },
        ],
      },
      moved_most: [
        // Two of the eight signed-scale attributes: the only ones "Moved most" lists.
        { measure: 'fight', value: 18, delta: 2 },
        { measure: 'discipline', value: 61, delta: -3 },
      ],
    },
    result: {
      result_key: 'jrb2-win', week: 14, user_won: true, site: 'home', user_is_home: true,
      home_team_id: TID, away_team_id: 'opp-team', home_team_name: 'Lawrence', away_team_name: 'Four Corners',
      home_score: 78, away_score: 71, opponent_team_id: 'opp-team', opponent_team_name: 'Four Corners',
      opponent_rank: 21, round_name: null, leader_role: 'potg',
      leader: { player_id: '030d9bd9-125d-4ad5-a49c-12b528d7ae89', name: 'Devin Park', stats: { pts: 24, reb: 9, ast: 5 } },
      headline: 'Park’s 24 carry Lawrence past Four Corners',
      box_score: { path: '/box-score.html', params: { mode: 'franchise', franchise_id: FID, game_id: 'g-1' } },
    },
    next_game: { week: 15, site: 'away', opponent: 'Four Corners', rank: 21, record: { wins: 12, losses: 9 }, conference: 2 },
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [
      { id: 't1', label_key: 'run_training', done: true },
      { id: 't2', label_key: 'assign_practice_squad', done: false, gates_advance: true, route: '/cut-players.html' },
      { id: 't3', label_key: 'play_next_game', done: false, is_advance_action: true },
    ],
    recruiting_wire: {
      status: '',
      events: [
        { recruit_id: 'r1', recruit: 'Ellis Clemons', position: 'SG', direction: 'down', event_detail: 'Interest cooled' },
        { recruit_id: 'r2', recruit: 'Jaylen Moss', position: 'PF', direction: 'up', event_detail: 'Interest rose' },
      ],
      pending_count: 3, urgent: false, unseen_count: 0,
    },
    signing_day: null, season_preview: null, also: null, weekly_card_items: [],
  };
}

const RANKINGS = [
  ['Lawrence', 16, 5, 'W', '78-71 vs Four Corners'],
  ['Four Corners', 15, 6, 'L', '71-78 @ Lawrence'],
  ['Maple Ridge', 15, 6, 'W', '70-64 vs Xavien'],
  ['Xavien', 14, 7, 'L', '64-70 @ Maple Ridge'],
].map(([name, W, L, r, lw], i) => ({
  team_id: i === 0 ? TID : 'team-' + i, team_name: name, natl_rank: i + 1, W, L,
  PF: 1500 - i * 20, PA: 1300 + i * 15, last_week: lw, last_week_result: r, next: 'Week 15',
}));

function cc(extra) {
  return Object.assign({
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lawrence',
    week: 15, season: 3, current_season: 3,
    training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 15, counts: {} },
    office_digest: digest(), rankings: RANKINGS,
    pending_championship_moments: [], moments: [], moments_for_this_visit: [], weekly_card_items: [],
  }, extra || {});
}

const ROSTER = ['Ada Keeper', 'Bea Reserve', 'Cy Bench'].map((name, i) => ({
  _id: '11111111111111111111110' + (i + 1), name,
  position_ratings: { PG: 72 - i * 3, SG: 60, SF: 50, PF: 40, C: 30 },
  attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
  height: 74 + i * 2, weight: 190 + i * 10, year: ['FR', 'SO', 'JR'][i],
}));

async function installApi(page, data) {
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { await route.continue(); return; }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.fallback(); return; }
    const json = (b) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
    if (pathname === '/api/auth/me') return json({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return json({ isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return json([{ name: 'Lawrence', display_name: 'Lawrence', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/command-center/data')) return json(data);
    if (pathname.startsWith('/roster/')) return json({ players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
    return json({});
  });
}

async function openOffice(page, data) {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page, data);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none') && root && root.getAttribute('aria-busy') === 'false';
  });
  await expect(page.locator('#office-root .wkc')).toBeVisible();
  await page.waitForTimeout(2500); // entrance animations settle
}

test('#1 #3a #3c #3d #4 Office: chips, wire, badge, blocking step, attitude, weekly card', async ({ page }) => {
  await openOffice(page, cc());
  await expect(page.locator('.chip.down').first()).toBeVisible();
  await expect(page.locator('.wk-step.gated')).toHaveCount(1);
  await expect(page.locator('#gob-rail-recruiting em.office-rail-count')).toHaveText('3');
  await shot(page, 'office');

  const up = await css(page, '.chip.up', ['color']);
  const down = await css(page, '.chip.down', ['color', 'backgroundColor', 'boxShadow']);
  expect(anyOf(up.color, isGreen), `▲ chip is positive-data green: ${up.color}`).toBe(true);
  expect(allNeutral(down.color + ' ' + down.backgroundColor + ' ' + down.boxShadow), `▼ chip neutral: ${JSON.stringify(down)}`).toBe(true);

  const wireDown = await css(page, '.wr.dn .wr-tag', ['color']);
  const wireUp = await css(page, '.wr.up .wr-tag', ['color']);
  expect(allNeutral(wireDown.color), `wire ▼ neutral: ${wireDown.color}`).toBe(true);
  expect(anyOf(wireUp.color, isGreen), `wire ▲ green: ${wireUp.color}`).toBe(true);

  const badge = await css(page, '#gob-rail-recruiting em.office-rail-count', ['backgroundColor', 'color']);
  expect(allNeutral(badge.backgroundColor) && parse(badge.backgroundColor).r > 200, `badge white plate: ${badge.backgroundColor}`).toBe(true);

  // The strip is a read-only stepper (2026-10-02): the blocking step has no outline or fill.
  // It is the current step, so its label is full white; still neutral, never orange.
  const step = await css(page, '.wk-step.gated', ['boxShadow', 'backgroundColor']);
  expect(step.boxShadow, 'blocking step has no button outline').toBe('none');
  expect(parse(step.backgroundColor).a, 'blocking step has no button fill').toBe(0);
  const stepLabel = await css(page, '.wk-step.gated .td-l', ['color']);
  expect(allNeutral(stepLabel.color) && parse(stepLabel.color).r > 240, `blocking step label white: ${stepLabel.color}`).toBe(true);
  // The BLOCKS ADVANCE tag is gone (2026-10-02).
  expect(await page.locator('.wk-step.gated .td-gate').count()).toBe(0);

  const bars = {};
  for (const id of ['em_0_19', 'em_20_39', 'em_40_59', 'em_60_79', 'em_80_plus']) {
    bars[id] = (await css(page, `.att-col[data-bucket="${id}"] .att-bar i`, ['backgroundColor'])).backgroundColor;
  }
  expect(Object.values(bars).some((c) => anyOf(c, isOrange)), `no orange attitude stop: ${JSON.stringify(bars)}`).toBe(false);
  expect(anyOf(bars.em_0_19, isRed) && anyOf(bars.em_80_plus, isGreen), 'red low, green high').toBe(true);

  await expect(page.locator('.office-res')).toHaveCount(0);
  const wkc = await css(page, '#office-root .wkc', ['backgroundColor', 'backgroundImage', 'borderTopColor']);
  expect(allNeutral(wkc.backgroundColor + ' ' + wkc.backgroundImage + ' ' + wkc.borderTopColor), `weekly card has no team wash: ${JSON.stringify(wkc)}`).toBe(true);
  const wash = await page.evaluate(() => Array.from(document.styleSheets).some((sheet) => {
    try { return Array.from(sheet.cssRules).some((r) => /office-res/.test(r.cssText || '')); } catch (e) { return false; }
  }));
  expect(wash, 'dead .office-res styling is deleted').toBe(false);
});

test('#2 League › Rankings: W plate, L outline, no green/red', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page, cc());
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=rankings-view');
  await expect(page.locator('#rankings-table .gob-wl.up').first()).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(1500);
  await shot(page, 'rankings');
  const w = await css(page, '#rankings-table .gob-wl.up', ['color', 'backgroundColor']);
  const l = await css(page, '#rankings-table .gob-wl.dn', ['color', 'backgroundColor', 'boxShadow']);
  expect(parse(w.backgroundColor).r > 200 && allNeutral(w.backgroundColor), `WIN white plate: ${w.backgroundColor}`).toBe(true);
  expect(parse(w.color).r < 60, `WIN dark ink: ${w.color}`).toBe(true);
  expect(allNeutral(l.color + ' ' + l.boxShadow) && colours(l.boxShadow).length > 0, `LOSS outline: ${JSON.stringify(l)}`).toBe(true);
  expect(parse(l.backgroundColor).a, 'LOSS has no fill').toBeLessThan(0.05);
});

test('#3e functional-modal accent default is neutral (Trim Your Roster)', async ({ page }) => {
  await openOffice(page, cc({ cut_required: true, cut_count: 2 }));
  await expect(page.locator('.fcc-cut-required-modal .gob-modal-accent')).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(800);
  await shot(page, 'modal-accent');
  const accent = await css(page, '.fcc-cut-required-modal .gob-modal-accent', ['backgroundColor']);
  expect(allNeutral(accent.backgroundColor), `accent neutral: ${accent.backgroundColor}`).toBe(true);
});

test('#3g #5 Assign Practice Squad: Stay neutral, accents neutral, Confirm stays the commit', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page, cc({ cut_required: true, cut_count: 2 }));
  await page.goto('/cut-players.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc');
  const boxes = page.locator('#cut-players-table .cut-player-checkbox');
  await expect(boxes.first()).toBeVisible({ timeout: 30000 });
  await boxes.nth(0).check();
  await page.locator('#back-btn').click();
  await expect(page.locator('#cut-modal-title')).toHaveText('Leave Without Assigning?');
  await page.waitForTimeout(600);
  await shot(page, 'stay');
  const stay = await css(page, '#cut-modal-actions .gob-modal-btn-primary', ['backgroundColor', 'color']);
  const accent = await css(page, '#cut-modal-accent', ['backgroundColor']);
  expect(await page.locator('#cut-modal-actions .gob-modal-btn-primary').textContent()).toBe('Stay');
  expect(allNeutral(stay.backgroundColor) && parse(stay.backgroundColor).r > 200, `Stay is a white plate: ${stay.backgroundColor}`).toBe(true);
  expect(allNeutral(accent.backgroundColor), `leave accent neutral: ${accent.backgroundColor}`).toBe(true);

  await page.locator('#cut-modal-actions .gob-modal-btn-primary').click();
  await expect(page.locator('#cut-modal-backdrop.is-visible')).toHaveCount(0);
  await boxes.nth(1).check();
  await page.locator('#submit-btn').click();
  await expect(page.locator('#cut-modal-title')).toHaveText('Confirm Practice Squad');
  await page.waitForTimeout(600);
  await shot(page, 'cut-confirm');
  const confirm = await css(page, '#cut-modal-actions .gob-modal-btn-primary', ['backgroundColor']);
  const accent2 = await css(page, '#cut-modal-accent', ['backgroundColor']);
  expect(allNeutral(accent2.backgroundColor), `confirm accent neutral: ${accent2.backgroundColor}`).toBe(true);
  expect(anyOf(confirm.backgroundColor, isOrange), `Confirm is the commit (orange): ${confirm.backgroundColor}`).toBe(true);
});

const HB_LIST = [1, 2].map((slot) => ({
  franchise_id: 'f' + slot, home_slot: slot, user_team_id: slot === 1 ? 'Bentley-Truman' : 'Ocean City',
  user_team_object_id: 'obj-f' + slot, week: 15 - slot, current_season: 3,
  primary_color: '#27408e', secondary_color: '#15181f', last_played_at: '2026-09-2' + slot + 'T10:00:00Z',
}));

test('#5 Home Base delete program keeps the sanctioned red outline', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  const j = (b) => (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
  await page.route('**/api/auth/me', j({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }));
  await page.route('**/franchise/list', j({ franchises: HB_LIST, count: 2, max: 2, most_recent_franchise_id: 'f2' }));
  await page.route('**/teams', j(HB_LIST.map((f) => ({ object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9 }))));
  await page.route('**/franchise/command-center/data**', j({ current_season: 3, week: 14, rankings: [] }));
  await page.route('**/api/community/around-the-league', j({ slots: [] }));
  await page.route('**/api/auth/leaderboard', j({ top: [], current_user: null, titles_top: [], titles_current_user: null }));
  await page.route('**/franchise/coach-career', j({}));
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await page.click('[data-hb-more][data-slot="1"]');
  const item = await css(page, '.pop [data-hb-delete]', ['color']);
  await page.click('[data-hb-delete]');
  await expect(page.locator('.btn-del')).toHaveText('Delete Program');
  await page.waitForTimeout(600);
  await shot(page, 'delete-program');
  const del = await css(page, '.btn-del', ['color', 'boxShadow']);
  expect(anyOf(item.color, isRed), `menu item red: ${item.color}`).toBe(true);
  expect(anyOf(del.color, isRed) && anyOf(del.boxShadow, isRed), `red-outline confirm: ${JSON.stringify(del)}`).toBe(true);
  await expect(page.locator('[data-hb-cancel]')).toBeFocused();
});

async function openTutorial(page, url) {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page, {});
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

test('#3f tutorial alert stays neutral', async ({ page }) => {
  await openTutorial(page, '/tutorial.html');
  await page.waitForFunction(() => window.GOB && typeof window.GOB.showTip === 'function');
  await page.evaluate(() => {
    window.GOB.showTip({
      alertMode: true, id: 'jrb2-alert', topicLabel: 'Game Plans', title: 'Game Plans',
      body: 'Your game plan tells the team how to play. Two minutes.', href: '/tutorial-game-plans.html',
      lessonIndex: 2, lessonTotal: 7, portrait: '/images/sammy_tutorial.png',
      cta: 'Start lesson', laterLabel: "I'll do this later", onGo() {}, onLater() {},
    });
  });
  await page.locator('.gob-talert').waitFor();
  await page.waitForTimeout(600);
  await shot(page, 'tutorial-alert');
  const found = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.gob-talert, .gob-talert *').forEach((el) => {
      const cs = getComputedStyle(el);
      out.push(cs.color, cs.backgroundColor, cs.backgroundImage, cs.borderTopColor, cs.boxShadow);
    });
    return out.join(' ');
  });
  expect(anyOf(found, isOrange), 'no orange in the tutorial alert').toBe(false);
});

test('#3b advanced-tutorial pick: selected (.is-on) is neutral', async ({ page }) => {
  await openTutorial(page, '/tutorial-advanced-training-by-position.html');
  await expect(page.locator('.fg-pick.is-on').first()).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(600);
  await shot(page, 'advanced-pick');
  const on = await css(page, '.fg-pick.is-on', ['backgroundColor', 'borderTopColor']);
  expect(allNeutral(on.backgroundColor + ' ' + on.borderTopColor), `selected pick neutral: ${JSON.stringify(on)}`).toBe(true);
});

test('#1 #3b #3e #5 sheet guards: box-score / player-view chips, orders tab, remove ×, default accent', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const base = test.info().project.use.baseURL || 'http://localhost:8000';
  await page.goto(base + '/404.html');
  const sheets = ['/css/gob-tokens.css', '/box-score.css', '/css/gob-tables.css', '/recruiting-spine.css',
    '/recruiting-signing.css', '/recruiting-dock.css', '/resource-pages.css'];
  await page.setContent(`<!doctype html><html class="gob"><head><base href="${base}/">
    ${sheets.map((s) => `<link rel="stylesheet" href="${s}">`).join('')}
    <style>body{background:#0b0d14;color:#fff;font:14px Inter,sans-serif;padding:24px;display:grid;gap:18px}
    .row{display:flex;gap:16px;align-items:center}.lbl{width:300px;color:rgba(255,255,255,.6)}
    .islot{position:relative;width:120px;height:44px;border:1px solid rgba(255,255,255,.1);border-radius:8px}
    .islot .islot-remove{opacity:1!important}.box{width:320px;background:#151a26;border-radius:10px;overflow:hidden}</style>
    </head><body class="gob">
    <div class="row"><span class="lbl">Box score attribute chips</span>
      <div class="attr-chips"><div class="attr-chip up"><span class="attr-chip-name">Shooting</span><span class="attr-chip-val up">+1</span></div>
      <div class="attr-chip down"><span class="attr-chip-name">Stamina</span><span class="attr-chip-val down">-1</span></div></div></div>
    <div class="row"><span class="lbl">Player › attribute changes</span>
      <div class="gob-chg-list"><div class="gob-chg is-up"><span>SH</span><i>▲1</i></div><div class="gob-chg is-down"><span>ST</span><i>▼1</i></div></div></div>
    <div class="row"><span class="lbl">Signing › My Orders tab (selected)</span>
      <button class="hub-anchor hub-anchor--orders is-on" style="margin-left:0"><span class="ic">●</span>My Orders</button></div>
    <div class="row"><span class="lbl">Invite dock › remove ×</span><div class="islot queued"><button class="islot-remove">×</button></div></div>
    <div class="row"><span class="lbl">Functional modal accent (default)</span><div class="box"><div class="gob-modal-accent"></div><div style="padding:12px">Modal</div></div></div>
    </body></html>`, { waitUntil: 'load' });
  await page.waitForTimeout(300);
  await shot(page, 'sheet-guards');
  const g = await page.evaluate(() => {
    const s = (sel) => getComputedStyle(document.querySelector(sel));
    return {
      chipDown: s('.attr-chip.down').borderTopColor + ' ' + s('.attr-chip.down').backgroundColor,
      valDown: s('.attr-chip-val.down').color,
      valUp: s('.attr-chip-val.up').color,
      chgDown: s('.gob-chg.is-down i').color,
      orders: s('.hub-anchor--orders.is-on').backgroundColor + ' ' + s('.hub-anchor--orders.is-on').borderTopColor,
      remove: s('.islot-remove').color + ' ' + s('.islot-remove').borderTopColor,
      accent: s('.gob-modal-accent').backgroundColor,
    };
  });
  expect(allNeutral(g.chipDown), `box-score ▼ chip neutral: ${g.chipDown}`).toBe(true);
  expect(allNeutral(g.valDown), `box-score ▼ value neutral: ${g.valDown}`).toBe(true);
  expect(anyOf(g.valUp, isGreen), `box-score ▲ value green: ${g.valUp}`).toBe(true);
  expect(allNeutral(g.chgDown), `player-view ▼ neutral: ${g.chgDown}`).toBe(true);
  expect(allNeutral(g.orders), `orders tab selected neutral: ${g.orders}`).toBe(true);
  expect(allNeutral(g.remove), `remove-invite × neutral: ${g.remove}`).toBe(true);
  expect(allNeutral(g.accent), `default modal accent neutral: ${g.accent}`).toBe(true);
});
