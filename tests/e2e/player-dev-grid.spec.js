// @ts-check
/**
 * Player Development grid (polish/player-dev-grid, 2026-10-02).
 *
 * 1. Prep > Player Training draws the same grid the weekly Training page does: cards,
 *    four across (three rows for twelve players). One component, one layout.
 * 2. On both pages the cards are ordered by the RT each card shows, highest first, reading
 *    left to right and then top to bottom. Ties keep the order they arrived in.
 * A roster longer than twelve (camp, before cuts) adds a row.
 *
 * PDG_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const SHOTS = path.join(__dirname, '../../reports/player-dev-grid');
const TAG = process.env.PDG_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/images/players/generic_headshot.png'));

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));

/** Camp (week 1): the fifteen-player roster, before cuts. */
function campState() {
  return { cc: clone(FIXTURE.cc), points: clone(FIXTURE.trainingPoints) };
}

/** In season (week 12): the twelve active players. */
function seasonState() {
  const cc = clone(FIXTURE.cc);
  cc.week = 12;
  cc.session_type = 'in-season';
  cc.training_completed = false;
  cc.training_disabled_for_postseason = false;
  cc.training_disabled_for_eos = false;
  const points = clone(FIXTURE.trainingPoints);
  points.week = 12;
  points.is_camp_week = false;
  points.is_first_training = false;
  points.training_points = 24;
  points.training_unavailable = false;
  points.custom_focus_roster = points.custom_focus_roster.slice(0, 12);
  return { cc, points };
}

/** The same players, sent in an order that is NOT RT order (the server does not sort). */
function shuffled(state) {
  const roster = state.points.custom_focus_roster;
  const out = [];
  // Odd indexes first, then even: keeps tied players in their relative order, so the
  // expected result is still unique.
  roster.forEach((row, i) => { if (i % 2) out.push(row); });
  roster.forEach((row, i) => { if (!(i % 2)) out.push(row); });
  state.points.custom_focus_roster = out;
  return state;
}

/** The RT a card shows: the rating at the training position. */
function shownRt(row) {
  const pos = row.resolved_training_position || row.training_position;
  const ratings = row.position_ratings || {};
  const value = pos && ratings[pos] != null ? ratings[pos] : Math.max.apply(null, Object.values(ratings).map(Number));
  return Math.round(Number(value));
}

/** Highest shown RT first; ties in the order they were sent. */
function expectedOrder(roster) {
  return roster.map((row, index) => ({ row, index, rt: shownRt(row) }))
    .sort((a, b) => (b.rt - a.rt) || (a.index - b.index))
    .map((entry) => entry.row.name);
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, state, saves) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { await route.continue(); return; }
    if (pathname.startsWith('/images/players/')) return route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, state.cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, state.points);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/api/gameplan') return fulfillJson(route, FIXTURE.gameplan);
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') return fulfillJson(route, FIXTURE.playbooks);
    if (pathname === '/franchise/player/development-focus' && request.method() === 'POST') {
      const body = request.postDataJSON() || {};
      if (saves) saves.push(body);
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
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

/** The two hosts of the grid. */
const HOSTS = {
  // The weekly Training page (the Advance focus page).
  training: async (page, state) => {
    await page.goto('/training.html?' + query({ from: 'locker-room', session_type: state.cc.session_type || 'preseason' }));
    await waitOverlay(page);
  },
  // Prep > Player Training > Player Development.
  prep: async (page) => {
    await page.goto('/franchise-command-center.html?' + query({ tab: 'training-view', from: 'command_center' }));
    await waitOverlay(page);
  },
};

async function open(page, host, state, saves) {
  await stubAuth(page);
  await installApi(page, state, saves);
  await HOSTS[host](page, state);
  await expect(page.locator('#player-dev-section .pdg-card').first()).toBeVisible({ timeout: 30000 });
}

/** Each card: its name, its place, and what it is made of. */
function cards(page) {
  return page.evaluate(() => {
    const section = document.getElementById('player-dev-section');
    const grid = section.querySelector('.pdg-grid');
    return {
      classes: section.className,
      flow: getComputedStyle(grid).gridAutoFlow,
      columns: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
      tables: section.querySelectorAll('table').length,
      cards: [...section.querySelectorAll('.pdg-card')].map((el) => {
        const r = el.getBoundingClientRect();
        return {
          name: el.querySelector('.pdg-name').textContent.trim(),
          x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width),
          rt: el.querySelector('[data-pdg-rt]').textContent.trim(),
          pot: (el.querySelector('.pdg-rt b.pot') || { textContent: '' }).textContent.trim(),
          lockup: [...el.querySelector('.pdg-rt').children].map((n) => n.textContent.trim()).join(' '),
          arrow: el.querySelectorAll('.pdg-rt i').length,
          portraits: el.querySelectorAll('img').length,
          selects: el.querySelectorAll('select').length,
        };
      }),
      wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}

/** Four across, row by row, in the expected order. */
function expectGrid(got, names, label) {
  expect(got.cards.map((c) => c.name), label).toEqual(names);
  const xs = [...new Set(got.cards.map((c) => c.x))].sort((a, b) => a - b);
  const ys = [...new Set(got.cards.map((c) => c.y))].sort((a, b) => a - b);
  expect(xs.length, label + ' columns').toBe(4);
  expect(ys.length, label + ' rows').toBe(Math.ceil(names.length / 4));
  got.cards.forEach((card, i) => {
    expect(card.x, label + ' ' + card.name).toBe(xs[i % 4]);
    expect(card.y, label + ' ' + card.name).toBe(ys[Math.floor(i / 4)]);
    expect(card.selects, label + ' ' + card.name).toBe(2);
  });
  // One layout: the cards, no table; filled row by row.
  expect(got.classes, label).toMatch(/pdg-layout-cards/);
  expect(got.classes, label).not.toMatch(/pdg-layout-table/);
  expect(got.tables, label).toBe(0);
  expect(got.flow, label).toMatch(/^row/);
  expect(got.columns, label).toBe(4);
  expect(new Set(got.cards.map((c) => c.w)).size, label + ' equal widths').toBe(1);
  expect(got.wide, label).toBeLessThanOrEqual(0);
}

for (const host of ['prep', 'training']) {
  for (const [period, build, count] of [['in season', seasonState, 12], ['camp', campState, 15]]) {
    test(host + ', ' + period + ': four across in RT order, reading left to right then down', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 720 });
      const state = shuffled(build());
      const sent = state.points.custom_focus_roster.map((row) => row.name);
      const want = expectedOrder(state.points.custom_focus_roster);
      expect(want).toHaveLength(count);
      expect(want, 'the payload is not already in RT order').not.toEqual(sent);
      await open(page, host, state);
      const got = await cards(page);
      expectGrid(got, want, host + ' ' + period);
      // Twelve are three rows of four; fifteen add a row, with three in it.
      const lastRow = got.cards.filter((c) => c.y === Math.max(...got.cards.map((k) => k.y)));
      expect(lastRow).toHaveLength(count === 12 ? 4 : 3);
    });
  }
}

/** The grade the page shows for a rating (its own display function). */
function grade(page, rt) {
  return page.evaluate((value) => window.formatRtDisplay(value), rt);
}

for (const host of ['prep', 'training']) {
  test(host + ': every card reads "current → potential"; the order is on the current', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const state = shuffled(seasonState());
    const roster = state.points.custom_focus_roster;
    // One player whose potential is below his current (a ceiling already reached), one with
    // no potential on the wire, and one whose potential would put him first if it counted.
    const byName = Object.fromEntries(roster.map((row) => [row.name, row]));
    byName['Stuart Marconi'].potential_rt_ratcheted = 55;
    byName['Norris Khan'].potential_rt_ratcheted = null;
    byName['Damon Martin'].potential_rt_ratcheted = 120;
    await open(page, host, state);
    const got = await cards(page);
    expect(got.cards.map((c) => c.name), 'ordered by the current, not the potential').toEqual(expectedOrder(roster));
    for (const card of got.cards) {
      const row = byName[card.name];
      const current = await grade(page, shownRt(row));
      expect(card.rt, card.name).toBe(current);
      expect(card.portraits, card.name + ' has no portrait').toBe(0);
      expect(card.lockup, card.name).not.toMatch(/#|\bNo\b\s*\d/); // no jersey number
      if (row.potential_rt_ratcheted == null) {
        expect(card.pot, card.name + ' has no potential').toBe('');
        expect(card.arrow, card.name).toBe(0);
        expect(card.lockup, card.name).toBe(current);
      } else {
        const potential = await grade(page, row.potential_rt_ratcheted);
        expect(card.arrow, card.name).toBe(1);
        expect(card.lockup, card.name).toBe(current + ' \u2192 ' + potential);
      }
    }
    expect(got.cards.find((c) => c.name === 'Roger Henrich').lockup).toBe('A+ \u2192 A++');
  });
}

test('a position change moves only the current grade; the potential and the card stay', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const saves = [];
  const state = seasonState();
  await open(page, 'prep', state, saves);
  const before = await cards(page);
  const card = page.locator('#player-dev-section .pdg-card', { hasText: 'Wilbert Struthers' });
  const was = before.cards.find((c) => c.name === 'Wilbert Struthers');
  const row = state.points.custom_focus_roster.find((r) => r.name === 'Wilbert Struthers');
  await card.locator('select').nth(0).selectOption('C');
  await expect.poll(() => saves.length).toBe(1);
  const after = await cards(page);
  const now = after.cards.find((c) => c.name === 'Wilbert Struthers');
  expect(now.rt).toBe(await grade(page, Math.round(row.position_ratings.C)));
  expect(now.rt).not.toBe(was.rt);
  expect(now.pot).toBe(was.pot);
  expect(after.cards.map((c) => c.name)).toEqual(before.cards.map((c) => c.name));
});

test('ties keep the order they arrived in', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const state = seasonState();
  // Three players tied at 54 and three at 50 in the fixture: reverse the whole roster, so
  // the tied players arrive in the opposite order and must stay in it.
  state.points.custom_focus_roster.reverse();
  const roster = state.points.custom_focus_roster;
  await open(page, 'prep', state);
  const got = await cards(page);
  const want = expectedOrder(roster);
  expect(got.cards.map((c) => c.name)).toEqual(want);
  const tied = roster.filter((row) => shownRt(row) === 54).map((row) => row.name);
  expect(tied).toHaveLength(3);
  expect(got.cards.map((c) => c.name).filter((name) => tied.includes(name))).toEqual(tied);
});

test('Prep: the position and training selectors work in every cell, and a change does not move the card', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const saves = [];
  const state = seasonState();
  await open(page, 'prep', state, saves);
  const before = (await cards(page)).cards.map((c) => c.name);
  const all = page.locator('#player-dev-section .pdg-card');
  await expect(all).toHaveCount(12);
  for (let i = 0; i < 12; i += 1) {
    const card = all.nth(i);
    const name = (await card.locator('.pdg-name').textContent()).trim();
    const id = await card.getAttribute('data-pdg-player');
    await card.locator('select').nth(1).selectOption('defensive');
    await expect.poll(() => saves.length, name + ' focus').toBe(i * 2 + 1);
    expect(saves[i * 2]).toMatchObject({ player_id: id, training_focus: 'defensive' });
    await card.locator('select').nth(0).selectOption(i % 2 ? 'PG' : 'C');
    await expect.poll(() => saves.length, name + ' position').toBe(i * 2 + 2);
    expect(saves[i * 2 + 1]).toMatchObject({ player_id: id, training_position: i % 2 ? 'PG' : 'C' });
  }
  // The shown RT follows the new position, but no card moved while it was being edited.
  expect((await cards(page)).cards.map((c) => c.name)).toEqual(before);
});

test('both pages draw the same cards', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const markup = {};
  for (const host of ['prep', 'training']) {
    await open(page, host, seasonState());
    markup[host] = await page.evaluate(() => [...document.querySelectorAll('#player-dev-section .pdg-card')]
      .map((el) => el.outerHTML.replace(/\s+/g, ' ')));
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
  expect(markup.prep).toEqual(markup.training);
});

for (const [width, height] of SIZES) {
  test('shots at ' + width, async ({ page }) => {
    for (const host of ['prep', 'training']) {
      for (const [period, build] of [['in-season', seasonState], ['camp', campState]]) {
        await page.setViewportSize({ width, height });
        await open(page, host, build());
        const section = page.locator('#player-dev-section');
        await section.scrollIntoViewIfNeeded();
        await page.mouse.move(0, 0);
        await page.waitForTimeout(400);
        const name = (host === 'prep' ? 'player-development' : 'training-page') + '-' + period;
        await page.screenshot({ path: path.join(SHOTS, name + '-' + TAG + '-' + width + '.png') });
        await section.screenshot({ path: path.join(SHOTS, name + '-grid-' + TAG + '-' + width + '.png') });
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    }
  });
}
