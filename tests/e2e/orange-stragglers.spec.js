// @ts-check
/**
 * Orange stragglers (Jamie, 2026-10-01): the "not obviously unsaved changes"
 * orange list from reports/jamie-rulings-batch-2-2026-10-01.md.
 *
 *   toasts (.hub-toast, training-playbooks .toast)      → neutral
 *   Training Report stat toggle (.tsr-toggle .active)    → neutral (choice control)
 *   on-your-board marks (.on-board, .pool-rankbadge, .citem), My Orders dot → navy
 *   .prow.flash, .ssum-lr, .ssum-nm b                    → stay orange (just committed)
 *   .gob-btn--action as CONTINUE (username, Game Plan tutorial) → neutral plate;
 *   Assign Practice Squad stays the orange save.
 *
 * OS_PREFIX=before skips the guards and writes before-*.png.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const OUT = process.env.OS_OUT || path.join(__dirname, '../../reports/orange-stragglers');
const PREFIX = process.env.OS_PREFIX || 'after';
const ASSERT = PREFIX === 'after';
const FID = 'f-e2e-orange-stragglers';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const PLAN = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));

function parse(value) {
  const v = String(value || '');
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4] };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: m[1] * 255, g: m[2] * 255, b: m[3] * 255, a: m[4] == null ? 1 : +m[4] };
  return null;
}
function colours(value) {
  const out = [];
  const re = /rgba?\([^)]*\)|color\(srgb[^)]*\)/gi;
  let m;
  while ((m = re.exec(String(value || '')))) { const p = parse(m[0]); if (p) out.push(p); }
  return out;
}
const isOrange = (p) => p.a > 0.02 && p.r > 200 && p.g > 100 && p.g < 200 && p.b < 110 && p.g - p.b > 40;
const isNavy = (p) => p.a > 0.02 && p.b > p.r + 30 && p.b > p.g + 15;
const isNeutral = (p) => Math.max(p.r, p.g, p.b) - Math.min(p.r, p.g, p.b) < 24;
const anyOf = (value, fn) => colours(value).some(fn);
const allNeutral = (value) => colours(value).every(isNeutral);
const whitePlate = (value) => { const p = parse(value); return !!p && isNeutral(p) && p.r > 200 && p.a > 0.8; };

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

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body == null ? {} : body) });

// ── Recruiting hub (board weeks 20–26, signing week 35) ────────────────────
function recruit(id, name, mine) {
  return {
    recruit_id: id, image_id: id, name, archetype: 'Slasher', 'Home Region': 'C', year: 'Junior',
    height: 76, weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: mine ? { 1: TID, 2: 'rival-1', 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function hubData(week) {
  return {
    team: 'Lancaster', team_id: TID, team_region: 'C', week,
    recruits: [recruit('r-lean', 'Ada Lean', true), recruit('r-other', 'Bea Other', false)],
    board: week >= 20 && week <= 26 ? ['r-lean'] : [],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: week === 35 ? { 'r-lean': { points: 12, promise: false } } : {},
    watchlist: [], new_lean_recruit_ids: [], week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    week_35_reveal_seen: false, invite_seed_modal_seen: true, visit_history: [], current_results_week: null,
    conferences: {
      user_conference: 1, sister_conference: 2, order: [1, 2], by_team_id: { [TID]: 1, 'rival-1': 1 },
      user_region: 'C', region_by_team_id: { [TID]: 'C', 'rival-1': 'C' }, region_team_ids: [TID, 'rival-1'],
    },
  };
}

function hubCc(week) {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week, rank: 14, season: 1,
    current_season: 1, training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 0, counts: {}, week_35_orders_submitted: false },
    user_conference: 1, user_region: 'C', team_record: { wins: 4, losses: 1 },
  };
}

async function openHub(page, week) {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname.startsWith('/franchise/recruiting-data')) return json(route, hubData(week));
    if (pathname.startsWith('/franchise/command-center/data')) return json(route, hubCc(week));
    if (pathname.startsWith('/franchise/recruiting-results')) return json(route, { regions: [] });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) {
      return json(route, pathname === '/teams' ? [] : {});
    }
    return route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
}

test('on-your-board pool marks are navy', async ({ page }) => {
  await openHub(page, 21);
  const poolTab = page.getByRole('tab', { name: 'Pool', exact: true });
  if (await poolTab.count()) await poolTab.click();
  await expect(page.locator('#hub-pool tbody tr.rec.on-board .pool-rankbadge')).toBeVisible({ timeout: 30000 });
  await shot(page, 'pool-board');
  // The pool sits under the Invite Board; a second, labelled shot scrolled to the row.
  await page.locator('#hub-pool tbody tr.rec.on-board').first().scrollIntoViewIfNeeded();
  await page.mouse.move(0, 0);
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-pool-board-rows-scrolled-1280.png`) });
  if (!ASSERT) return;
  const badge = await css(page, '#hub-pool .pool-rankbadge', ['backgroundColor', 'color']);
  const row = await css(page, '#hub-pool tbody tr.rec.on-board td', ['backgroundColor']);
  expect(anyOf(badge.backgroundColor, isNavy) && !anyOf(badge.backgroundColor, isOrange), `rank badge navy: ${badge.backgroundColor}`).toBe(true);
  expect(anyOf(row.backgroundColor, isNavy) && !anyOf(row.backgroundColor, isOrange), `on-board row navy: ${row.backgroundColor}`).toBe(true);
});

test('signing: committed items and My Orders dot navy; toast neutral; just-committed flash stays orange', async ({ page }) => {
  await openHub(page, 35);
  // Commit points locally (no save): the recruit joins the Your Orders rail.
  const plus = page.locator('button[data-step="1"][data-id="r-lean"]');
  await plus.waitFor({ timeout: 30000 });
  for (let i = 0; i < 3; i += 1) await plus.click();
  await expect(page.locator('.citem').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('.hub-anchor--orders .ic')).toBeVisible();
  await shot(page, 'signing');
  // The hub's own toast, with the markup hub saves use (show it without a save).
  await page.evaluate(() => {
    const t = document.createElement('div');
    t.className = 'hub-toast show';
    t.innerHTML = '<span class="ti">✓</span><div><div class="tt1">Orders saved</div><div class="tt2">12 points on 1 recruit</div></div>';
    document.body.appendChild(t);
  });
  await page.waitForTimeout(400);
  await shot(page, 'hub-toast');
  if (!ASSERT) return;
  const item = await css(page, '.citem', ['backgroundColor', 'borderTopColor']);
  const dot = await css(page, '.hub-anchor--orders .ic', ['color']);
  const toast = await css(page, '.hub-toast', ['borderLeftColor', 'borderTopColor']);
  const ti = await css(page, '.hub-toast .ti', ['color', 'backgroundColor', 'borderTopColor']);
  expect(anyOf(item.backgroundColor + ' ' + item.borderTopColor, isNavy), `committed item navy: ${JSON.stringify(item)}`).toBe(true);
  expect(anyOf(item.backgroundColor + ' ' + item.borderTopColor, isOrange), 'committed item not orange').toBe(false);
  expect(anyOf(dot.color, isOrange), `My Orders dot not orange: ${dot.color}`).toBe(false);
  expect(parse(dot.color).b > parse(dot.color).r, `My Orders dot navy-tinted (--you-ink): ${dot.color}`).toBe(true);
  expect(allNeutral(toast.borderLeftColor + ' ' + toast.borderTopColor), `hub toast neutral: ${JSON.stringify(toast)}`).toBe(true);
  expect(allNeutral(ti.color + ' ' + ti.backgroundColor + ' ' + ti.borderTopColor), `hub toast icon neutral: ${JSON.stringify(ti)}`).toBe(true);
  // Kept: the just-committed flash and the signing summary.
  const kept = await page.evaluate(() => {
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:-9999px';
    host.innerHTML = '<div class="prow flash">x</div><div class="ssum-nm">Ada<b>+12</b></div><button class="ssum-lr">Lock</button>';
    document.body.appendChild(host);
    const s = (sel) => getComputedStyle(host.querySelector(sel));
    return { flash: s('.prow.flash').boxShadow, nm: s('.ssum-nm b').color, lr: s('.ssum-lr').backgroundImage + ' ' + s('.ssum-lr').borderTopColor };
  });
  expect(anyOf(kept.flash, isOrange), `.prow.flash stays orange: ${kept.flash}`).toBe(true);
  expect(anyOf(kept.nm, isOrange), `.ssum-nm b stays orange: ${kept.nm}`).toBe(true);
  expect(anyOf(kept.lr, isOrange), `.ssum-lr stays orange: ${kept.lr}`).toBe(true);
});

// ── Training playbook toast ────────────────────────────────────────────────
test('training playbook "Saved" toast is neutral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const req = route.request();
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (err) { return route.continue(); }
    if (/googletagmanager|sentry|google-analytics/.test(req.url())) return route.fulfill({ status: 204, body: '' });
    if (pathname === '/api/playbooks' && req.method() === 'GET') return json(route, PLAN.playbooks);
    if (pathname === '/api/playbooks') return json(route, { success: true });
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e', fte_v2_complete: true });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0', sentryDsn: null });
    return route.continue();
  });
  await page.goto(`/training-playbooks.html?franchise_id=${PLAN.franchise_id}&team_id=${PLAN.cc.team_id}&mode=franchise`);
  await page.locator('.tp-card').first().waitFor({ timeout: 30000 });
  // The markup showToast() writes (training-playbooks.js).
  await page.evaluate(() => {
    const t = document.getElementById('toast');
    t.innerHTML = '<div class="toast-icon" aria-hidden="true"></div><div class="toast-copy"><div class="toast-title">Playbooks Saved</div>'
      + '<div class="toast-subline">Your training playbook is set.</div></div><button type="button" class="toast-dismiss" aria-label="Dismiss">×</button>';
    t.hidden = false;
    t.classList.add('visible');
  });
  await page.waitForTimeout(500);
  await shot(page, 'tp-toast');
  if (!ASSERT) return;
  const t = await css(page, '#toast', ['borderLeftColor', 'borderTopColor', 'backgroundColor']);
  expect(allNeutral(t.borderLeftColor + ' ' + t.borderTopColor), `training toast neutral: ${JSON.stringify(t)}`).toBe(true);
});

// ── Training Report stat toggle ────────────────────────────────────────────
test('Training Report stat toggle: selected is neutral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname.startsWith('/franchise/training-squad-reports')) {
      return json(route, {
        attr_keys: ['SC', 'SH', 'ID', 'OD'],
        reports: [{
          week: 8,
          players: [
            { player_id: 'p1', name: 'Ada Keeper', pos: 'PG', baseline: { SC: 50, SH: 48, ID: 40, OD: 44 }, current: { SC: 56, SH: 51, ID: 40, OD: 46 } },
            { player_id: 'p2', name: 'Bea Reserve', pos: 'SF', baseline: { SC: 42, SH: 39, ID: 45, OD: 47 }, current: { SC: 45, SH: 41, ID: 49, OD: 47 } },
          ],
        }],
      });
    }
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json(route, pathname === '/teams' ? [] : {});
    return route.continue();
  });
  await page.goto('/training-squad-report.html?franchise_id=' + FID + '&team_id=' + TID);
  await expect(page.locator('.tsr-toggle .toggle-btn.active')).toBeVisible({ timeout: 30000 });
  await shot(page, 'tsr-toggle');
  if (!ASSERT) return;
  const on = await css(page, '.tsr-toggle .toggle-btn.active', ['backgroundColor', 'color']);
  expect(allNeutral(on.backgroundColor + ' ' + on.color) && !anyOf(on.backgroundColor, isOrange), `selected toggle neutral: ${JSON.stringify(on)}`).toBe(true);
  expect(parse(on.backgroundColor).a, 'selected is a brighter neutral fill').toBeGreaterThan(0.05);
});

// ── CONTINUE buttons that only continue ────────────────────────────────────
test('username modal CONTINUE is the neutral plate', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e', fte_v2_complete: true });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json(route, {});
    return route.continue();
  });
  await page.goto('/tutorial.html', { waitUntil: 'load' });
  await page.evaluate(async () => {
    const m = await import('/js/shared/usernameModal.js');
    m.openUsernameModal({ onSuccess() {} });
  });
  await page.locator('#username-modal-cta').waitFor();
  await page.waitForTimeout(500);
  await shot(page, 'username');
  if (!ASSERT) return;
  const cta = await css(page, '#username-modal-cta', ['backgroundColor', 'color']);
  expect(whitePlate(cta.backgroundColor), `CONTINUE white plate: ${cta.backgroundColor}`).toBe(true);
  expect(anyOf(cta.backgroundColor, isOrange)).toBe(false);
});

test('Game Plan tutorial PLAY NOW is the neutral plate', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') {
      return json(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com', tutorial_state: { game_id: 'g-tut', step: 'situation' } });
    }
    if (pathname === '/franchise/command-center/data') return json(route, PLAN.cc);
    if (pathname === '/franchise/team-data') return json(route, PLAN.teamData);
    if (pathname === '/teams') return json(route, PLAN.teams);
    if (pathname.startsWith('/roster/')) return json(route, PLAN.roster);
    if (pathname === '/api/gameplan') return json(route, PLAN.gameplan);
    return json(route, {});
  });
  const q = new URLSearchParams({
    franchise_id: PLAN.franchise_id, team_id: 'Lancaster', user_team_id: 'Lancaster', home: 'Lancaster',
    away: 'Four-Corners', my_team: 'home', mode: 'tutorial', game_id: 'g-tut', from: 'lineup',
  });
  await page.goto('/game-plan.html?' + q.toString());
  await expect(page.locator('#btn-tutorial-gameplan-continue')).toBeVisible({ timeout: 30000 });
  // The Sammy intro modal may sit over the page; close it so the button shows.
  const sammy = page.locator('.sammy-modal-backdrop.open .sammy-modal-btn-primary');
  if (await sammy.count()) await sammy.first().click();
  await page.waitForTimeout(600);
  await shot(page, 'gameplan-tutorial');
  if (!ASSERT) return;
  const cta = await css(page, '#btn-tutorial-gameplan-continue', ['backgroundColor']);
  expect(whitePlate(cta.backgroundColor), `PLAY NOW white plate: ${cta.backgroundColor}`).toBe(true);
});

test('Assign Practice Squad stays the orange save', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  const roster = ['Ada Keeper', 'Bea Reserve'].map((name, i) => ({
    _id: '11111111111111111111110' + (i + 1), name,
    position_ratings: { PG: 70, SG: 60, SF: 50, PF: 40, C: 30 },
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    height: 74, weight: 190, year: 'FR',
  }));
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json(route, { franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 12, season: 1, current_season: 1, cut_required: true, cut_count: 1, recruiting_wire: {} });
    }
    if (pathname.startsWith('/roster/')) return json(route, { players: roster, conference: 1, region: 'A', team_chemistry: 15 });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json(route, pathname === '/teams' ? [] : {});
    return route.continue();
  });
  await page.goto('/cut-players.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc');
  await page.locator('#cut-players-table .cut-player-checkbox').first().check({ timeout: 30000 });
  await expect(page.locator('#submit-btn')).toBeEnabled();
  await page.waitForTimeout(400);
  await shot(page, 'cut-submit');
  if (!ASSERT) return;
  const btn = await css(page, '#submit-btn', ['backgroundColor']);
  expect(anyOf(btn.backgroundColor, isOrange), `Assign Practice Squad is the orange save: ${btn.backgroundColor}`).toBe(true);
});
