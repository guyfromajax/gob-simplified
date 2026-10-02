// @ts-check
/**
 * CH is a hidden attribute: never displayed, on any screen (UX_System, "CH is hidden").
 *
 * The server no longer sends it (tests/test_hidden_attrs.py). This spec is the display
 * half of the guard: it hands the main screens payloads that DO still carry CH, the way
 * a leaking route or a stale cache would, and fails if a CH column, chip or label is drawn.
 *
 * CH_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const SHOTS = path.join(__dirname, '../../reports/chrome-followups-2');
const TAG = process.env.CH_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/images/players/generic_headshot.png'));

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));
const shotPath = (name, width) => path.join(SHOTS, name + '-' + TAG + '-' + width + '.png');

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

/** Put CH back into every attribute dict of a payload: what a leaking server would send. */
function leak(value) {
  if (Array.isArray(value)) return value.map(leak);
  if (!value || typeof value !== 'object') return value;
  const out = {};
  Object.keys(value).forEach((key) => { out[key] = leak(value[key]); });
  ['attributes', 'attrs'].forEach((key) => {
    if (out[key] && typeof out[key] === 'object' && !Array.isArray(out[key]) && 'SC' in out[key]) {
      out[key].CH = 77;
      out[key].anchor_CH = 77;
    }
  });
  return out;
}

/** Every visible place the page names the hidden attribute. Empty when it is hidden. */
function chOnScreen(page) {
  return page.evaluate(() => {
    const visible = (el) => {
      const cs = getComputedStyle(el);
      return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0;
    };
    const found = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent.trim();
      const host = node.parentElement;
      if (!text || !host || !visible(host) || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(host.tagName)) continue;
      // A column header, chip or label that is the attribute's code, or copy that uses its name.
      if (text === 'CH' || /^CH\s*[+−–-]?\s*\d/.test(text) || /^[+−-]?\d+\s*CH$/.test(text) || /\bClutch\b/.test(text)) {
        found.push(host.tagName.toLowerCase() + (host.className ? '.' + String(host.className).split(' ')[0] : '') + ': ' + text.slice(0, 40));
      }
    }
    document.querySelectorAll('[data-attr="CH"], [data-key="CH"], [data-attribute="CH"], [data-sort="CH"], option[value="CH"]').forEach((el) => {
      if (visible(el) || el.tagName === 'OPTION') found.push(el.tagName.toLowerCase() + '[data CH]');
    });
    document.querySelectorAll('[title], [aria-label], [data-tooltip]').forEach((el) => {
      const tip = [el.getAttribute('title'), el.getAttribute('aria-label'), el.getAttribute('data-tooltip')].join(' ');
      if (/\bClutch\b/.test(tip)) found.push(el.tagName.toLowerCase() + ' tooltip: ' + tip.trim().slice(0, 40));
    });
    return found;
  });
}

/* ------------------------------------------------ Office "Since last week" --- */

function officeWithChMovement() {
  const data = clone(O.STATES.loss); // no score count-up: the card is settled when it is shot
  const moved = data.office_digest.what_moved;
  // Two players trained this week; the leaking payload also carries their CH movement.
  moved.attribute_changes = [
    { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'SC', from: 6, to: 7 },
    { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'CH', from: 5, to: 7 },
    { player_id: 'p-noah', name: 'Noah Peck', attribute: 'CH', from: 4, to: 6 },
    { player_id: 'p-noah', name: 'Noah Peck', attribute: 'RB', from: 7, to: 8 },
  ];
  return data;
}

for (const [width, height] of SIZES) {
  test('Office "Since last week": no CH chip, even when the payload has CH movement (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    await O.openOffice(page, officeWithChMovement());
    const card = page.locator('#office-root .wkc-tr');
    await expect(card).toBeVisible({ timeout: 15000 });
    await expect(card).toContainText('Jalen Carter');
    // The card's rows arrive on a short stagger; shoot once they have landed.
    await page.waitForTimeout(2500);
    await page.screenshot({ path: shotPath('ch-office-since-last-week', width) });
    // The visible movement is still there; only CH is gone.
    await expect(card).toContainText('Jalen Carter');
    await expect(card).toContainText('SC');
    await expect(card).toContainText('RB');
    expect(await chOnScreen(page)).toEqual([]);
  });
}

/* ------------------------------------------------- Practice Squad report --- */

const PS_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

function practiceSquadReports() {
  const snapshot = (base) => {
    const out = {};
    PS_KEYS.forEach((key, i) => { out[key] = base + (i % 4); });
    out.CH = base + 9; // the leak
    return out;
  };
  const player = (id, name, pos, base) => ({ player_id: id, name, pos, baseline: snapshot(base), current: snapshot(base + 2) });
  return {
    // What the route sent before CH was hidden: a thirteenth key.
    attr_keys: PS_KEYS.concat(['CH']),
    reports: [
      { week: 11, players: [player('ps1', 'Cal Riser', 'PG', 30), player('ps2', 'Dee Marsh', 'C', 24), player('ps3', 'Ian Foley', 'SF', 27)] },
      { week: 6, players: [player('ps1', 'Cal Riser', 'PG', 28), player('ps2', 'Dee Marsh', 'C', 22)] },
    ],
  };
}

async function installPracticeSquadApi(page) {
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { await route.continue(); return; }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/franchise/training-squad-reports') return fulfillJson(route, practiceSquadReports());
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, FIXTURE.cc);
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    return fulfillJson(route, {});
  });
}

for (const [width, height] of SIZES) {
  test('Practice Squad report: twelve attribute columns, no CH, in Changes and Absolute (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    await stubAuth(page);
    await installPracticeSquadApi(page);
    await page.goto('/training-squad-report.html?franchise_id=' + FID + '&team_id=' + TEAM);
    const report = page.locator('.tsr-report').first();
    await expect(report).toBeVisible({ timeout: 20000 });
    const headers = () => report.locator('thead tr').first().locator('th, td').allTextContents()
      .then((texts) => texts.map((t) => t.trim()).filter((t) => /^[A-Z]{2}$/.test(t)));
    for (const view of ['changes', 'absolute']) {
      if (view === 'absolute') await report.locator('.toggle-btn', { hasText: /Absolute/i }).click();
      await page.mouse.move(0, 0);
      await page.screenshot({ path: shotPath('ch-practice-squad-report-' + view, width) });
      const codes = await headers();
      expect(codes.slice().sort()).toEqual(PS_KEYS.slice().sort());
      expect(codes).toHaveLength(12);
      expect(await chOnScreen(page)).toEqual([]);
    }
  });
}

/* ---------------------------------------------------- the main screens --- */

function trainingReport() {
  const roster = FIXTURE.trainingPoints.custom_focus_roster.slice(0, 12);
  const players = roster.map((row) => ({
    player_id: row.player_id, id: row.player_id, name: row.name, jersey: row.jersey, year: 'JR', pos: row.pos,
    position: row.pos, position_ratings: row.position_ratings, attributes: row.attrs, attrs: row.attrs, season_stats: {},
  }));
  const player_changes = {};
  const movements = {};
  players.slice(0, 4).forEach((p, i) => {
    player_changes[p.name] = { SC: 2 - i, CH: 3 };
    movements[String(p.id)] = { name: p.name, CH: { from: 5, to: 6 }, SC: { from: 4, to: 5 } };
  });
  return {
    week: 12, upcoming_opponent: 'Four Corners',
    coaching_focus: { archetype: 'systems-coach', sub_option: 'systems-coach-offense', leaf_display_name: 'Offense' },
    players, player_changes, player_attribute_display_movements: movements,
    exceptional_gains: [{ name: players[0].name, attribute: 'CH' }],
    team_attributes: { shot_threshold: 0, rebound_modifier: 1, offensive_efficiency: 4, defensive_efficiency: 2,
      fb_efficiency: 1, pt_efficiency: 6, fight: 2, discipline: 3, team_chemistry: 8, fb_opp_modifier: -2, pt_opp_modifier: -1 },
    team_changes: { offensive_efficiency: 2 },
    plays_data: clone(FIXTURE.teamData.plays_data), scouting_data: clone(FIXTURE.teamData.scouting_data),
    plays_effectiveness_changes: {}, defenses_effectiveness_changes: {}, projected_starting_five: [],
    training_notes: [{ title: 'Practice Player Of The Week', body: players[0].name }],
  };
}

/** The app's payloads with CH put back in every attribute dict. */
async function installLeakingApi(page) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { await route.continue(); return; }
    if (pathname.startsWith('/images/players/')) return route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, leak(FIXTURE.cc));
    if (pathname === '/franchise/team-data') return fulfillJson(route, leak(FIXTURE.teamData));
    if (pathname === '/franchise/training-points') return fulfillJson(route, leak(FIXTURE.trainingPoints));
    if (pathname === '/franchise/training-report') return fulfillJson(route, leak(trainingReport()));
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, leak(FIXTURE.roster));
    if (pathname === '/api/gameplan') return fulfillJson(route, FIXTURE.gameplan);
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') return fulfillJson(route, FIXTURE.playbooks);
    return fulfillJson(route, {});
  });
}

function query(extra) {
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, mode: 'franchise' });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

test.describe('main screens, fed payloads that still carry CH', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await stubAuth(page);
    await installLeakingApi(page);
  });

  test('the leak helper really puts CH in the payloads (so the checks below mean something)', async () => {
    expect(leak(FIXTURE.roster).players[0].attributes.CH).toBe(77);
    expect(leak(FIXTURE.trainingPoints).custom_focus_roster[0].attrs.CH).toBe(77);
    expect(leak(trainingReport()).players[0].attributes.CH).toBe(77);
  });

  test('Roster', async ({ page }) => {
    await page.goto('/franchise-command-center.html?' + query({ tab: 'team-view', from: 'command_center' }));
    await waitOverlay(page);
    await expect(page.locator('#team-view')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('#team-view')).toContainText('Roger Henrich', { timeout: 30000 });
    expect(await chOnScreen(page)).toEqual([]);
  });

  test('Player Training', async ({ page }) => {
    await page.goto('/franchise-command-center.html?' + query({ tab: 'training-view', from: 'command_center' }));
    await waitOverlay(page);
    await expect(page.locator('#training-view .pdg-grid')).toBeVisible({ timeout: 30000 });
    expect(await chOnScreen(page)).toEqual([]);
  });

  test('Training page', async ({ page }) => {
    await page.goto('/training.html?' + query({ from: 'locker-room', session_type: 'in-season' }));
    await waitOverlay(page);
    await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
    expect(await chOnScreen(page)).toEqual([]);
  });

  test('Training Report: Team Report, Training Changes, Attributes, notes', async ({ page }) => {
    await page.goto('/training-report.html?' + query({ week: '12', from: 'training', origin: 'prep' }));
    await expect(page.locator('#week-number')).toHaveText('12', { timeout: 15000 });
    await waitOverlay(page);
    await expect(page.locator('#players-tbody tr').first()).toBeVisible();
    // Training Changes: the changed-attribute columns come from the payload's keys.
    const changeHeads = (await page.locator('#players-thead th').allTextContents()).map((t) => t.trim());
    expect(changeHeads).toContain('SC');
    expect(changeHeads).not.toContain('CH');
    expect(await chOnScreen(page)).toEqual([]);
    await page.locator('.players-section .toggle-btn[data-view="attributes"]').click();
    const attrHeads = (await page.locator('#players-thead th').allTextContents()).map((t) => t.trim());
    expect(attrHeads).toContain('IQ');
    expect(attrHeads).not.toContain('CH');
    expect(await chOnScreen(page)).toEqual([]);
  });

  test('Set Lineup', async ({ page }) => {
    await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
    await page.locator('#play-now').waitFor({ timeout: 20000 });
    await page.waitForTimeout(800);
    expect(await chOnScreen(page)).toEqual([]);
  });
});

/* -------------------------------------------------------------- the court --- */

test('court: the side panels never show CH (the game payload still carries it)', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.goto(courtUrl());
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.player-stats-panel.away', { state: 'attached', timeout: 20000 });
  expect(await chOnScreen(page)).toEqual([]);
  // Every stat tab of both panels.
  for (const side of ['away', 'home']) {
    for (const tab of ['S2', 'S3', 'S1']) {
      await page.locator('.team-toggle-btn[data-team="' + side + '"][data-tab="' + tab + '"]').evaluate((el) => el.click());
      expect(await chOnScreen(page)).toEqual([]);
    }
  }
  const toggles = page.locator('.player-stats-panel .toggle-btn');
  for (let i = 0; i < await toggles.count(); i += 1) {
    await toggles.nth(i).evaluate((el) => el.click());
    expect(await chOnScreen(page)).toEqual([]);
  }
});
