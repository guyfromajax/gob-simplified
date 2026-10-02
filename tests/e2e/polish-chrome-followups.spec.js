// @ts-check
/**
 * polish/chrome-followups (2026-10-02): Jamie's answers to the chrome-audio questions.
 *
 * F1 top strip: week 35 reads "Signing Day", week 36 "Offseason" (no week number)
 * F2 champion wording on the Trophy Case, the season review and the Home Base shelf
 * F3 offline: the Coach archetype pop-up is marked seen on this computer
 * F4 "Trim Your Roster": its button is neutral, green is Advance only
 * F5 Training Report: leaving mid-load shows nothing; a real failure is inline
 *
 * FOLLOWUP_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/chrome-followups');
const TAG = process.env.FOLLOWUP_SHOT_TAG || 'after';
const shot = (page, name, opts) => page.screenshot(Object.assign(
  { path: path.join(SHOTS, name + '-' + TAG + '-1280.png') }, opts || {}));

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });
test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

const clone = (value) => JSON.parse(JSON.stringify(value));
const FID = O.FID;
const isGreen = (rgb) => { const m = /rgba?\((\d+), (\d+), (\d+)/.exec(rgb || ''); return !!m && +m[2] > 180 && +m[1] < 120 && +m[3] < 120; };

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

function apiPath(route) {
  let pathname = '';
  try { pathname = new URL(route.request().url()).pathname; } catch (err) { return null; }
  const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
    || pathname === '/teams' || pathname === '/app-config';
  return api ? pathname : null;
}

/* ------------------------------------------------------------------ F1 --- */

for (const [week, label] of [[35, 'Signing Day'], [36, 'Offseason']]) {
  test('F1: week ' + week + ' reads "' + label + '" in the top strip, with no week number', async ({ page }) => {
    const data = clone(week === 35 ? O.STATES.signing_day : O.STATES.regular);
    data.week = week;
    if (week === 36) {
      data.office_digest.next_game = null;
      data.recruiting_wire = { board_saved_week: 0, counts: {}, week_35_orders_submitted: true, week_36_results_seen: true };
    }
    await O.openOffice(page, data);
    await shot(page, 'f1-top-strip-week-' + week, { clip: { x: 0, y: 0, width: 1280, height: 120 } });
    await expect(page.locator('#gob-week-value')).toHaveText(label);
    await expect(page.locator('.top-stats')).not.toContainText(/week/i);
    await expect(page.locator('.top-stats')).not.toContainText(String(week));
    // Not a tournament week: no emblem, no round, plain bar. Only the season sits under it.
    await expect(page.locator('#fcc-header-emblem svg')).toHaveCount(0);
    await expect(page.locator('#gob-week-phase')).toHaveText('Season 1');
    await expect(page.locator('html.gob-shell .top')).not.toHaveClass(/is-tier/);
    // It sits where the week sits: the stat after National Rank, inside the bar.
    const g = await page.evaluate(() => {
      const box = (el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; };
      return { value: box(document.getElementById('gob-week-value')), rank: box(document.getElementById('gob-rank-stat')),
        top: box(document.querySelector('html.gob-shell .top')) };
    });
    expect(g.value.left).toBeGreaterThan(g.rank.right);
    expect(g.value.top).toBeGreaterThanOrEqual(g.top.top);
    expect(g.value.bottom).toBeLessThanOrEqual(g.top.bottom);
  });
}

/* ------------------------------------------------------- F1b: season --- */

/** What the week stat shows, how its label is styled, and whether the label moves anything. */
async function weekStat(page) {
  return page.evaluate(() => {
    const box = (el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width }; };
    const style = (el) => { const cs = getComputedStyle(el); return { size: cs.fontSize, weight: cs.fontWeight, transform: cs.textTransform, color: cs.color, family: cs.fontFamily, tracking: cs.letterSpacing }; };
    const value = document.getElementById('gob-week-value');
    const label = document.getElementById('gob-week-phase');
    const stats = document.querySelector('.top-stats');
    const advance = document.querySelector('.adv-wrap');
    const measure = () => ({ stats: box(stats), advance: box(advance), stat: box(document.getElementById('gob-week-stat')) });
    const withLabel = measure();
    const text = label.textContent;
    // The same strip with no season line: nothing may be in a different place.
    label.hidden = true;
    const without = measure();
    label.hidden = false;
    label.textContent = text;
    return {
      value: value.textContent.trim(), label: label.hidden ? null : text.trim(),
      valueBox: box(value), labelBox: box(label), valueSize: parseFloat(getComputedStyle(value).fontSize),
      labelStyle: style(label), recordLabelStyle: style(document.querySelector('#gob-record-stat span')),
      rankLabelStyle: style(document.querySelector('#gob-rank-stat span')),
      withLabel, without, top: box(document.querySelector('html.gob-shell .top')),
      rankLabelBox: box(document.querySelector('#gob-rank-stat span')),
    };
  });
}

function seasonData(week) {
  const base = week >= 27 && week <= 34 ? O.STATES.tournament : (week === 35 ? O.STATES.signing_day : O.STATES.win);
  const data = clone(base);
  data.week = week;
  data.current_season = 3;
  data.season = 3;
  return data;
}

function expectSecondaryAndStill(g, expected) {
  expect(g.label).toBe(expected);
  // Beneath the value, on the same line as the other stats' labels, inside the bar.
  expect(g.labelBox.top).toBeGreaterThanOrEqual(g.valueBox.bottom - 1);
  expect(Math.abs(g.labelBox.top - g.rankLabelBox.top)).toBeLessThanOrEqual(2);
  expect(g.labelBox.bottom).toBeLessThanOrEqual(g.top.bottom);
  expect(Math.abs(g.labelBox.left - g.valueBox.left)).toBeLessThanOrEqual(1);
  // Clearly secondary: the small label type, far smaller than the value.
  expect(g.labelStyle.size).toBe(g.recordLabelStyle.size);
  expect(g.labelStyle.weight).toBe(g.recordLabelStyle.weight);
  expect(g.labelStyle.transform).toBe('uppercase');
  expect(g.labelStyle.tracking).toBe(g.recordLabelStyle.tracking);
  expect(g.labelStyle.family).toBe(g.recordLabelStyle.family);
  expect(parseFloat(g.labelStyle.size)).toBeLessThanOrEqual(g.valueSize * 0.6);
  // It does not widen the strip or move the action button.
  expect(g.withLabel.stats.width).toBe(g.without.stats.width);
  expect(g.withLabel.stat.width).toBe(g.without.stat.width);
  expect(g.withLabel.advance.left).toBe(g.without.advance.left);
  // Nothing sits beside the action button (a focus page has no action button in its bar).
  if (g.withLabel.advance.width > 0) {
    expect(g.withLabel.advance.left - Math.max(g.labelBox.right, g.withLabel.stats.right)).toBeGreaterThan(100);
  }
}

const SEASON_CASES = [
  { week: 2, name: 'regular', value: 'Week 2', label: 'Season 3' },
  { week: 27, name: 'tournament', value: 'Conference Tournament', label: 'First Round · Season 3' },
  { week: 35, name: 'signing-day', value: 'Signing Day', label: 'Season 3' },
];

for (const item of SEASON_CASES) {
  for (const size of [[1280, 720], [1920, 1080]]) {
    test('F1b: ' + item.name + ' week shows the season under "' + item.value + '" at ' + size[0], async ({ page }) => {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await O.openOffice(page, seasonData(item.week));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(SHOTS, 'f1b-season-' + item.name + '-' + TAG + '-' + size[0] + '.png'),
        clip: { x: 0, y: 0, width: size[0], height: 130 } });
      const g = await weekStat(page);
      expect(g.value).toBe(item.value);
      expectSecondaryAndStill(g, item.label);
      if (item.week <= 26 || item.week === 35) {
        // The same quiet label colour as RECORD and NATIONAL RANK.
        expect(g.labelStyle.color).toBe(g.recordLabelStyle.color);
        expect(g.labelStyle.color).toBe(g.rankLabelStyle.color);
      }
    });
  }
}

test('F1b: a double-digit season under the shortest value still moves nothing', async ({ page }) => {
  const data = seasonData(2);
  data.current_season = 12;
  await O.openOffice(page, data);
  const g = await weekStat(page);
  expect(g.value).toBe('Week 2');
  expectSecondaryAndStill(g, 'Season 12');
});

/** A recruiting page (browse, or focus when the invite board is the week's task) over a given Office payload. */
async function openRecruiting(page, data, focus) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    if (pathname.startsWith('/franchise/command-center/data')) {
      const body = clone(data);
      body.recruiting_wire = { board_saved_week: focus ? 0 : body.week, counts: {} };
      await fulfillJson(route, body);
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, { week: data.week, team_id: O.TID, team: 'Lancaster', team_region: 'A', recruits: [], team_name_map: {} });
      return;
    }
    await fulfillJson(route, {});
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + O.TID + '&from=fcc');
  await expect(page.locator('#gob-week-value')).toHaveText('Week ' + data.week, { timeout: 15000 });
}

for (const mode of ['browse', 'focus']) {
  const week = mode === 'browse' ? 5 : 22;
  test('F1b: the season shows on a ' + mode + ' page too (recruiting, week ' + week + ')', async ({ page }) => {
    // Week 22 with the invite board not saved yet: recruiting is the week's task, so the page is focus.
    await openRecruiting(page, seasonData(week), mode === 'focus');
    await expect(page.locator('#gob-week-phase')).toHaveText('Season 3');
    if (mode === 'focus') await expect(page.locator('html')).toHaveClass(/gob-focus/);
    const g = await weekStat(page);
    expectSecondaryAndStill(g, 'Season 3');
  });
}

test('F1b: a payload that names no season shows no season line (never a guess)', async ({ page }) => {
  const data = seasonData(5);
  delete data.current_season;
  delete data.season;
  await openRecruiting(page, data, false);
  await expect(page.locator('#gob-week-phase')).toBeHidden();
});

/* ------------------------------------------------------------------ F2 --- */

const NEW_LABELS = ['National Champions', 'Region Champions', 'Conference Tournament Champions', 'Regular Season Conference Champions'];
const OLD_WORDING = /Conference Champions\b|Regular-Season|regular-season #1|Conference champions\b/;

function trophy(kind, season) {
  return { kind, season, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' };
}

function career() {
  return {
    user_id: 'e2e-user', username: 'Coach Demo',
    record: { wins: 73, losses: 22, total_games: 95, win_rate: 77 },
    championships_total: { conf_rs: 1, conf_t: 1, region: 1, national: 1 },
    titles_total: 4, win_pct_display: '.770', geek_points: 4060, seasons_completed: 4, programs: 1,
    trophies: [
      trophy('national', 2), trophy('region', 2), trophy('conf_t', 2), trophy('conf_rs', 2),
      { kind: 'season_record', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1',
        detail: { wins: 31, losses: 5, national_rank: 1, conf_finish: 1, best_players: [], class_signed: [] } },
    ],
    // The finish line is the server's string (career_data.finish_label).
    top_seasons: [
      { franchise_id: 'f1', team_name: 'Lawrence Eagles', team_slug: 'lawrence', season: 1, wins: 22, losses: 10,
        finish: 'Conference tournament champions', finish_is_title: true, season_gp: 1120, in_progress: false, week: null },
      { franchise_id: 'f1', team_name: 'Lawrence Eagles', team_slug: 'lawrence', season: 2, wins: 24, losses: 8,
        finish: 'Regular season conference champions', finish_is_title: true, season_gp: 980, in_progress: false, week: null },
    ],
  };
}

async function installCareerApi(page) {
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    if (pathname === '/franchise/coach-career') { await fulfillJson(route, career()); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' }); return; }
    if (pathname === '/franchise/list') { await fulfillJson(route, { franchises: [], count: 0, max: 2, most_recent_franchise_id: null }); return; }
    if (pathname === '/teams') { await fulfillJson(route, []); return; }
    await fulfillJson(route, {});
  });
}

const cleanText = (texts) => texts.map((t) => t.replace(/\s+/g, ' ').trim());

test('F2: the Trophy Case and its season review use the new champion wording', async ({ page }) => {
  await stubAuth(page);
  await installCareerApi(page);
  await page.goto('/trophy-case.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.tc-head h1')).toContainText('Trophy Case');
  await shot(page, 'f2-trophy-case');
  const shelf = cleanText(await page.locator('.tc .med.gold').locator('xpath=following-sibling::div[1]/b').allTextContents());
  expect(shelf.slice().sort()).toEqual(NEW_LABELS.slice().sort());
  await expect(page.locator('.tc')).not.toContainText(OLD_WORDING);

  await page.locator('[data-tc-review]').first().click();
  const review = page.locator('.rv.is-open');
  await expect(review).toBeVisible({ timeout: 15000 });
  await page.waitForTimeout(1200);
  await shot(page, 'f2-season-review');
  const medallions = cleanText(await review.locator('.rv-t .tro b').allTextContents());
  // The two conference titles are named by which title they are, not by "Conference X Champions".
  expect(medallions).toContain('Conference Tournament Champions');
  expect(medallions).toContain('Regular Season Conference Champions');
  expect(medallions).toContain('National Champions');
  expect(medallions.filter((label) => /^Region( \S+)? Champions$/.test(label))).toHaveLength(1);
  await expect(review).not.toContainText(OLD_WORDING);
});

test('F2: the offline Home Base shelf uses the new champion wording', async ({ page }) => {
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await installCareerApi(page);
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  const shelf = page.locator('.cr .shelf');
  await expect(shelf).toBeVisible({ timeout: 15000 });
  await shot(page, 'f2-home-base-offline');
  const text = (await page.locator('.cr').innerText()).replace(/\s+/g, ' ');
  expect(text).toMatch(/Conference tournament champions/i);
  expect(text).toMatch(/Regular season conference champions/i);
  expect(text).not.toMatch(/regular-season #1/i);
  expect(text).not.toMatch(/(^|[^n] )Conference champions/i);
  // The longer finish lines read in full in Top Seasons (they used to fit "Conference champions").
  const finishes = await page.locator('.tsn .tsn-f').evaluateAll((nodes) => nodes
    .filter((n) => n.textContent.trim())
    .map((n) => ({ text: n.textContent.trim(), clipped: n.scrollWidth > n.clientWidth })));
  expect(finishes).toEqual([
    { text: 'Conference tournament champions', clipped: false },
    { text: 'Regular season conference champions', clipped: false },
  ]);
});

/* ------------------------------------------------------------------ F3 --- */

function archetypeVisit(state) {
  const data = clone(O.STATES.regular);
  delete data.franchise_id; // the real payload has no franchise_id
  const item = { id: 'first_archetype', kind: 'first_archetype', tier: 'MILESTONE', priority: 70, payload_ref: 'first_archetype',
    seen_key: 'archetype_reveal_seen', title: 'Coaching archetype', line: 'Your coaching archetype is established.',
    style: 'gold', sting: 'STING_MILESTONE', duration: 'short' };
  data.lead_archetype = 'defensive_rebounding';
  data.archetype_reveal_seen = !!state.seen;
  data.first_archetype = state.seen ? null : { eligible: true, archetype: 'defensive_rebounding' };
  data.moments = state.seen ? [] : [item];
  data.moments_for_this_visit = state.seen ? [] : [item];
  return data;
}

async function installArchetypeApi(page, state, writes) {
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    const request = route.request();
    if (request.method() !== 'GET') {
      let body = {};
      try { body = JSON.parse(request.postData() || '{}'); } catch (err) { body = {}; }
      writes.push({ path: pathname, method: request.method(), body });
    }
    if (pathname === '/api/auth/archetype-reveal-seen') {
      // Always remote: the offline build cannot reach it.
      if (state.desktop) { await route.abort(); return; }
      state.seen = true;
      await fulfillJson(route, { archetype_reveal_seen: true });
      return;
    }
    if (pathname === '/franchise/archetype-reveal-seen') {
      const body = writes[writes.length - 1].body;
      if (body.franchise_id === FID) state.seen = true;
      await fulfillJson(route, { archetype_reveal_seen: true });
      return;
    }
    if (pathname === '/api/auth/me') {
      if (state.desktop) { await route.abort(); return; }
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', lead_archetype: 'defensive_rebounding', archetype_reveal_seen: !!state.seen });
      return;
    }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: O.TID, _id: O.TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, archetypeVisit(state)); return; }
    await fulfillJson(route, {});
  });
}

async function openOfficeFor(page) {
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + O.TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none') && root && root.getAttribute('aria-busy') === 'false';
  });
}

const seenWrites = (writes, pathname) => writes.filter((w) => w.path === pathname);

test('F3: offline, the Coach archetype pop-up is saved as seen locally and shows once', async ({ page }) => {
  const writes = [];
  const state = { seen: false, desktop: true };
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await installArchetypeApi(page, state, writes);

  await openOfficeFor(page);
  await expect(page.locator('.mm-scrim.is-open[data-kind="first_archetype"]')).toBeVisible({ timeout: 15000 });
  await page.waitForTimeout(600);
  await shot(page, 'f3-archetype-first-visit');
  // Marked seen as it is shown, on this computer, with the franchise the Office is on.
  await expect.poll(() => seenWrites(writes, '/franchise/archetype-reveal-seen').length).toBe(1);
  expect(seenWrites(writes, '/franchise/archetype-reveal-seen')[0]).toMatchObject({ method: 'PATCH', body: { franchise_id: FID } });
  expect(seenWrites(writes, '/api/auth/archetype-reveal-seen')).toHaveLength(0);

  // Every later Office visit: no pop-up.
  for (let visit = 0; visit < 2; visit += 1) {
    await openOfficeFor(page);
    await page.waitForTimeout(1200);
    await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  }
  await shot(page, 'f3-archetype-next-visit');
  expect(seenWrites(writes, '/franchise/archetype-reveal-seen')).toHaveLength(1);
});

test('F3: online, the seen flag still goes to the account route', async ({ page }) => {
  const writes = [];
  const state = { seen: false, desktop: false };
  await stubAuth(page);
  await installArchetypeApi(page, state, writes);
  await openOfficeFor(page);
  await expect(page.locator('.mm-scrim.is-open[data-kind="first_archetype"]')).toBeVisible({ timeout: 15000 });
  await expect.poll(() => seenWrites(writes, '/api/auth/archetype-reveal-seen').length).toBe(1);
  expect(seenWrites(writes, '/franchise/archetype-reveal-seen')).toHaveLength(0);
});

/* ------------------------------------------------------------------ F4 --- */

test('F4: the Trim Your Roster button is neutral; green is the Advance button only', async ({ page }) => {
  const data = clone(O.STATES.win);
  data.cut_required = true;
  data.cut_count = 3;
  await O.openOffice(page, data);
  const modal = page.locator('.fcc-cut-required-modal');
  await expect(modal).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(700);
  await shot(page, 'f4-trim-your-roster');
  const button = modal.locator('#fcc-cut-required-close');
  await expect(button).toHaveText('Assign Practice Squad');
  await expect(button).toBeFocused();
  const paint = await page.evaluate(() => {
    const read = (el) => { const cs = getComputedStyle(el); return { bg: cs.backgroundColor, color: cs.color, border: cs.borderTopColor }; };
    const btn = document.getElementById('fcc-cut-required-close');
    const box = btn.getBoundingClientRect();
    const actions = btn.parentElement.getBoundingClientRect();
    return { modal: read(btn), advance: read(document.getElementById('play-now')), fills: box.width >= actions.width - 60 };
  });
  expect(isGreen(paint.modal.bg), 'modal button is not green: ' + paint.modal.bg).toBe(false);
  expect(isGreen(paint.modal.color)).toBe(false);
  expect(isGreen(paint.modal.border)).toBe(false);
  expect(isGreen(paint.advance.bg), 'Advance is still green: ' + paint.advance.bg).toBe(true);
  expect(paint.fills, 'a single action spans the modal').toBe(true);
  // Same job as before: it leaves for the assignment screen.
  await page.evaluate(() => { window.__nav = []; window.GOBNav.go = (url) => { window.__nav.push(url); }; });
  await button.click();
  await expect.poll(() => page.evaluate(() => window.__nav.length)).toBe(1);
  expect(await page.evaluate(() => window.__nav[0])).toContain('/cut-players.html');
});

/* ------------------------------------------------------------------ F5 --- */

async function installReportApi(page, respond) {
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: O.TID, _id: O.TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, { team_id: O.TID, user_team_id: O.TID, team: 'Lancaster', week: 12, rank: 14, current_season: 1,
        training_completed: true, session_type: 'in-season', cut_required: false, rankings: [] });
      return;
    }
    if (pathname.startsWith('/franchise/training-report')) { await respond(route); return; }
    await fulfillJson(route, {});
  });
}

function reportUrl() {
  return '/training-report.html?' + new URLSearchParams({ franchise_id: FID, team_id: O.TID, mode: 'franchise', week: '12', from: 'office' });
}

test('F5: a Training Report that fails to load shows the inline card, not a browser alert', async ({ page }) => {
  const dialogs = [];
  page.on('dialog', (dialog) => { dialogs.push(dialog.message()); dialog.dismiss().catch(() => {}); });
  await stubAuth(page);
  await installReportApi(page, (route) => fulfillJson(route, { detail: 'boom' }, 500));
  await page.goto(reportUrl());
  const status = page.locator('#training-report-view .report-load-status');
  await expect(status).toBeVisible({ timeout: 15000 });
  await expect(status).toHaveText('The training report did not load.');
  await expect(page.locator('#training-report-view')).toHaveClass(/is-load-failed/);
  await page.waitForTimeout(500);
  await shot(page, 'f5-report-load-failed');
  expect(dialogs).toEqual([]);
  // The way out is still there.
  await expect(page.locator('#locker-room-btn')).toBeVisible();
});

test('F5: leaving the Training Report before it loads shows nothing', async ({ page }) => {
  const dialogs = [];
  page.on('dialog', (dialog) => { dialogs.push(dialog.message()); dialog.dismiss().catch(() => {}); });
  await stubAuth(page);
  let asked = 0;
  // The report is still on its way when the player leaves.
  await installReportApi(page, async (route) => {
    asked += 1;
    await new Promise((resolve) => setTimeout(resolve, 4000));
    await fulfillJson(route, {}).catch(() => {});
  });
  await page.goto(reportUrl());
  await expect.poll(() => asked).toBeGreaterThan(0);
  await expect(page.locator('#training-report-view')).toHaveClass(/is-loading/);
  await page.goto('/faqs.html');
  await page.waitForTimeout(1500);
  expect(dialogs).toEqual([]);
  await expect(page).toHaveURL(/faqs\.html/);
});
