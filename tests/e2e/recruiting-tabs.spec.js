// @ts-check
/** Pool · Leans · Visits on the recruiting underline row. */
const { test, expect } = require('@playwright/test');

test.describe.configure({ timeout: 120000 });
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-recruiting-tabs';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/recruiting-tabs');

function recruit(id, name, leans) {
  return {
    recruit_id: id,
    name: name,
    archetype: 'Slasher',
    'Home Region': 'C',
    year: 'Junior',
    height: 76,
    weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: leans ? { 1: TID, 2: null, 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function history(rows) {
  return [20, 21, 22, 23, 24, 25, 26].map((week) => {
    const row = rows[week] || {};
    return { week: week, recruit_id: row.id || null, name: row.name || null, lean: row.lean || null };
  });
}

function dataFor(week, extra) {
  const body = Object.assign({
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: week,
    recruits: [recruit('r-lean', 'Ada Lean', true), recruit('r-other', 'Bea Other', false)],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: history({}),
    current_results_week: week === 22 ? 22 : null,
    conferences: { order: [], by_team_id: {} },
  }, extra || {});
  return body;
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
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openHub(page, week, extra, wire) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, dataFor(week, extra));
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc(week, wire));
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-results')) {
      await fulfillJson(route, { regions: [] });
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/app-config' || pathname === '/teams') {
      await fulfillJson(route, pathname === '/app-config' ? { isAlpha: false, version: '1.0' } : {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForSelector('#hub-root .spine-h');
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
}

function tab(page, label) {
  return page.getByRole('tab', { name: label, exact: true });
}

async function park(page) {
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + Math.min(320, box.width / 2), box.y + Math.min(280, box.height - 24));
}

async function shot(page, name) {
  await park(page);
  await page.screenshot({ path: path.join(OUT, name) });
}

test('invite weeks keep the stack on pool and leans, and visits is the calendar', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 22, {
    visit_history: history({ 20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } } }),
  });
  await expect(tab(page, 'Leans')).toHaveAttribute('aria-selected', 'true');
  expect(page.url()).toContain('hub=leans');
  await expect(page.locator('.pool-view[data-view="leans"]')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs .gob-search')).toHaveAttribute('placeholder', 'Search name…');
  await expect(page.locator('#hub-visits .vcal')).toBeVisible();
  await expect(page.locator('#hub-board')).toBeVisible();
  await expect(page.locator('#hub-pool')).toBeVisible();
  await expect(page.locator('#hub-weekly')).toBeVisible();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(1);

  const before = await page.evaluate(() => history.length);
  await tab(page, 'Pool').click();
  await expect(tab(page, 'Pool')).toHaveAttribute('aria-selected', 'true');
  expect(page.url()).toContain('hub=pool');
  expect(await page.evaluate(() => history.length)).toBe(before);
  await expect(page.locator('#hub-visits')).toBeVisible();
  await expect(page.locator('#hub-board')).toBeVisible();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(2);
  await expect(page.locator('#hub-weekly')).toBeVisible();
  await shot(page, 'pool-w22-1280.png');

  await tab(page, 'Leans').click();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(1);
  await expect(page.locator('#hub-board')).toBeVisible();
  await shot(page, 'leans-w22-1280.png');

  await tab(page, 'Visits').click();
  expect(page.url()).toContain('hub=visits');
  await expect(page.locator('#hub-visits .vcal')).toBeVisible();
  await expect(page.locator('#hub-weekly')).toBeVisible();
  await expect(page.locator('#hub-board')).toHaveCount(0);
  await expect(page.locator('#hub-pool')).toHaveCount(0);
  await shot(page, 'visits-w22-1280.png');

  await page.evaluate(() => {
    const url = new URL(location.href);
    url.searchParams.set('hub', 'pool');
    history.pushState(history.state, '', url.pathname + url.search);
  });
  await page.goBack();
  await expect(tab(page, 'Visits')).toHaveAttribute('aria-selected', 'true');
  expect(page.url()).toContain('hub=visits');

  await page.setViewportSize({ width: 1920, height: 1080 });
  await tab(page, 'Pool').click();
  await shot(page, 'pool-w22-1920.png');
  await tab(page, 'Leans').click();
  await shot(page, 'leans-w22-1920.png');
  await tab(page, 'Visits').click();
  await shot(page, 'visits-w22-1920.png');
});

test('passive and tournament visits use the existing calendar tiles', async ({ page }) => {
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 7);
    await tab(page, 'Visits').click();
    await expect(page.locator('.vcal-title')).toHaveText('Invite window opens Week 20');
    await expect(page.locator('#hub-visits .vwk.is-upcoming')).toHaveCount(7);
    await expect(page.locator('#hub-pool')).toHaveCount(0);
    await shot(page, 'visits-w7-' + size[2] + '.png');
  }

  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 30, {
      visit_history: history({
        20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } },
        21: { id: 'r-other', name: 'Bea Other', lean: { 1: 'rival-1' } },
      }),
    });
    await tab(page, 'Visits').click();
    await expect(page.locator('.vcal-title')).toHaveText('Invite Visits');
    await expect(page.locator('#hub-visits .vwk.is-filled')).toHaveCount(2);
    await expect(page.locator('#hub-visits .vwk.is-missed')).toHaveCount(5);
    await expect(page.locator('#hub-pool')).toHaveCount(0);
    await shot(page, 'visits-w30-' + size[2] + '.png');
  }
});

test('signing day and results hide the tab row', async ({ page }) => {
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 35);
    await expect(page.locator('#hub-sign')).toBeVisible();
    await expect(page.locator('#gob-subtabs')).toBeHidden();
    await expect(page.locator('#gob-subtabs .gob-search')).toHaveCount(0);
    await shot(page, 'signing-w35-' + size[2] + '.png');
  }
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 36);
    await expect(page.locator('#hub-signings')).toBeVisible();
    await expect(page.locator('#gob-subtabs')).toBeHidden();
    await shot(page, 'results-w36-' + size[2] + '.png');
  }
});

test('focus mode still hides the head during an unsaved invite week', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 22, {}, { board_saved_week: 0 });
  await expect(page.locator('html.gob-shell.gob-focus .pg-head')).toBeHidden();
  await expect(page.locator('#hub-board')).toBeVisible();
});
