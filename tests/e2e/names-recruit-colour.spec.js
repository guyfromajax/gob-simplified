// @ts-check
/** Account stored team names + recruiting colour law. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-names-colour';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/names-recruit-colour');

const ME = {
  user_id: 'e2e-user',
  username: 'e2e',
  email: 'e2e@example.com',
  record: { wins: 12, losses: 5 },
  championships_total: { conf_rs: 1, conf_t: 0, region: 0, national: 2 },
  geek_points: 900,
  geek_points_by_team: { IDA: 400, BENTLEY_TRUMAN: 300, SEATTLE_AAA: 200 },
  geek_points_teams: [
    { team_id: 'IDA', display_name: 'IDA', points: 400 },
    { team_id: 'BENTLEY_TRUMAN', display_name: 'Bentley-Truman', points: 300 },
    { team_id: 'SEATTLE_AAA', display_name: 'Seattle AAA', points: 200 },
  ],
  archetype_reveal_seen: true,
  archetypes: { total: 10, authoritarian: 10 },
};

function recruit(id, name, leans) {
  return {
    recruit_id: id,
    image_id: id,
    name: name,
    archetype: 'Slasher',
    'Home Region': 'C',
    year: 'Junior',
    height: 76,
    weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: leans ? { 1: TID, 2: 'rival-1', 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function history(rows) {
  return [20, 21, 22, 23, 24, 25, 26].map((week) => {
    const row = rows[week] || {};
    return { week: week, recruit_id: row.id || null, name: row.name || null, lean: row.lean || null };
  });
}

function dataFor(week, extra) {
  return Object.assign({
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: week,
    recruits: [recruit('r-lean', 'Ada Lean', true), recruit('r-other', 'Bea Other', false)],
    board: week >= 20 && week <= 26 ? ['r-lean'] : [],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: history(week >= 21 ? { 20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } } } : {}),
    current_results_week: null,
    conferences: { order: [], by_team_id: {} },
  }, extra || {});
}

function cc(week, wire) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: Object.assign({ board_saved_week: week, counts: {}, week_35_orders_submitted: week >= 35 }, wire || {}),
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body == null ? {} : body) });
}

async function installApi(page, week, extra, wire) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') { await fulfillJson(route, ME); return; }
    if (pathname.startsWith('/franchise/recruiting-data')) { await fulfillJson(route, dataFor(week, extra)); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, cc(week, wire)); return; }
    if (pathname.startsWith('/franchise/recruiting-results')) { await fulfillJson(route, { regions: [] }); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, version: '1.0' }); return; }
    if (pathname === '/teams') {
      await fulfillJson(route, [
        { team_id: 'IDA', name: 'IDA', object_id: 'ida' },
        { team_id: 'BENTLEY_TRUMAN', name: 'Bentley-Truman', object_id: 'bt' },
        { team_id: 'SEATTLE_AAA', name: 'Seattle AAA', object_id: 'sea' },
      ]);
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) {
      await fulfillJson(route, {});
      return;
    }
    await route.continue();
  });
}

function parseRgb(value) {
  const m = String(value || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return null;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]) };
}

function near(c, target, slop) {
  if (!c) return false;
  return Math.abs(c.r - target[0]) <= slop && Math.abs(c.g - target[1]) <= slop && Math.abs(c.b - target[2]) <= slop;
}

const GREEN = [52, 236, 39];
const ORANGE = [247, 148, 32];
const NAVY = [39, 64, 142];

async function shot(page, name) {
  await page.waitForTimeout(120);
  await page.screenshot({ path: path.join(OUT, name + '.png') });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('account geek points show stored names and no audio switch', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 12);
  await page.goto('/account.html');
  await page.waitForSelector('#gp-by-team .gp-team-name');
  const names = await page.locator('#gp-by-team .gp-team-name').allTextContents();
  expect(names).toEqual(['IDA', 'Bentley-Truman', 'Seattle AAA']);
  // Audio is set in Settings (Music, Sound) and on the court, nowhere else.
  await expect(page.locator('#acct-ambience-switch')).toHaveCount(0);
  await shot(page, 'account-geek-points');
});

test('recruiting week 21 follows colour law', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 21);
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForSelector('#hub-phase .pstrip');
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));

  const colours = await page.evaluate(() => {
    const cs = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const s = getComputedStyle(el);
      return { color: s.color, bg: s.backgroundColor, border: s.borderTopColor };
    };
    const save = document.querySelector('.bbtn-save');
    const youTok = document.querySelector('.lb-slot.is-you .lb-tok, .tok.is-you');
    const otherTok = document.querySelector('.lb-slot:not(.is-you):not(.is-you-list) .lb-tok, .tok:not(.is-you)');
    const pending = document.querySelector('.vwk.is-pending');
    const advance = document.querySelector('#play-now, .advance');
    return {
      name: cs('.pstrip-name'),
      dot: cs('.pstrip-phase-dot'),
      count: cs('.pstrip-counter .n b'),
      save: save ? getComputedStyle(save).backgroundColor : null,
      you: youTok ? getComputedStyle(youTok).backgroundColor : null,
      other: otherTok ? getComputedStyle(otherTok).backgroundColor : null,
      week: pending ? { bg: getComputedStyle(pending).backgroundColor, border: getComputedStyle(pending).borderTopColor } : null,
      advance: advance ? getComputedStyle(advance).backgroundColor : null,
    };
  });

  expect(near(parseRgb(colours.name && colours.name.color), GREEN, 40)).toBe(false);
  expect(near(parseRgb(colours.dot && colours.dot.bg), GREEN, 40)).toBe(false);
  expect(near(parseRgb(colours.count && colours.count.color), ORANGE, 30)).toBe(false);
  expect(near(parseRgb(colours.save), ORANGE, 40)).toBe(true);
  expect(near(parseRgb(colours.save), GREEN, 40)).toBe(false);
  expect(near(parseRgb(colours.you), NAVY, 35)).toBe(true);
  expect(near(parseRgb(colours.you), GREEN, 40)).toBe(false);
  expect(near(parseRgb(colours.other), GREEN, 40)).toBe(false);
  expect(near(parseRgb(colours.week && colours.week.bg), ORANGE, 30)).toBe(false);
  expect(near(parseRgb(colours.week && colours.week.border), ORANGE, 30)).toBe(false);
  const adv = parseRgb(colours.advance);
  if (adv && (adv.r + adv.g + adv.b) > 30) expect(near(adv, GREEN, 60)).toBe(true);

  await shot(page, 'recruiting-week21');
});

test('recruiting pool filters stay neutral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 7);
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForSelector('#hub-pool');
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  const chip = page.locator('#hub-pool .chip.is-active, #hub-pool .chip.is-my-region').first();
  if (await chip.count()) {
    const bg = parseRgb(await chip.evaluate((el) => getComputedStyle(el).backgroundColor));
    expect(near(bg, GREEN, 40)).toBe(false);
  }
  await shot(page, 'recruiting-pool');
});

test('signing day hub is reachable', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 35);
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForSelector('#hub-sign, #hub-phase .pstrip');
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  if (await page.locator('#hub-sign').count()) {
    const submit = page.locator('.rail-submit, .ssum-lr').first();
    if (await submit.count()) {
      const bg = parseRgb(await submit.evaluate((el) => getComputedStyle(el).backgroundColor));
      expect(near(bg, GREEN, 40)).toBe(false);
    }
    await shot(page, 'signing-day');
  }
});
