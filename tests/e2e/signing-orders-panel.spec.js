// @ts-check
/** Signing Day orders panel — computed styles, not class names. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-signing-orders-panel';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SHOT = process.env.SIGN_SHOT || 'after';
const ASSERT = SHOT === 'after';
const OUT = path.join(__dirname, '../../reports/signing-orders-panel');
const FRAMES = path.join(__dirname, '../../_documentation_master/projects');

const BLUE = [74, 144, 217];
const TIER_BLUE = [107, 164, 224];

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

function dataFor(extra) {
  return Object.assign({
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: 35,
    recruits: [
      recruit('r-ada', 'Ada Lean', true),
      recruit('r-cal', 'Cal Lean', true),
      recruit('r-bea', 'Bea Other', false),
    ],
    board: [],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: [20, 21, 22, 23, 24, 25, 26].map((week) => ({ week: week, recruit_id: null, name: null, lean: null })),
    roster_capacity: { roster_spots: 4, scholarships: 4, roster_cap: 15, roster_used: 11 },
    lean_multipliers: { 1: 5, 2: 3, 3: 2 },
    conferences: {
      user_conference: 1, sister_conference: 2, order: [1, 2],
      by_team_id: { [TID]: 1, 'rival-1': 1 },
      user_region: 'C',
      region_by_team_id: { [TID]: 'C', 'rival-1': 'C' },
      region_team_ids: [TID, 'rival-1'],
    },
  }, extra || {});
}

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 35,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: {
      board_saved_week: 0,
      counts: {},
      week_35_orders_submitted: false,
    },
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body == null ? {} : body) });
}

async function openHub(page) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, dataFor());
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, version: '1.0' });
      return;
    }
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) {
      await fulfillJson(route, pathname === '/teams' ? [] : {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  await page.waitForSelector('#hub-sign');
  await page.waitForSelector('#sign-rail', { state: 'visible', timeout: 15000 });
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

function overlap(a, b) {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

async function shot(page, name) {
  await page.waitForTimeout(180);
  const main = page.locator('html.gob-shell .main').first();
  if (await main.count()) {
    const box = await main.boundingBox();
    if (box) await page.mouse.move(box.x + 80, box.y + 80);
  }
  await page.screenshot({ path: path.join(OUT, SHOT + '-' + name + '.png') });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('signing board before/after at 1280 and 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page);
  await page.waitForSelector('#sign-rail');
  await shot(page, 'signing-1280');
  await page.locator('#sign-rail').screenshot({ path: path.join(OUT, SHOT + '-orders-0-1280.png') });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(200);
  await shot(page, 'signing-1920');
  await page.locator('#sign-rail').screenshot({ path: path.join(OUT, SHOT + '-orders-0-1920.png') });
});

test('orders panel with two committed and one promise', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page);
  await page.waitForSelector('#sign-rows .prow .stepper button[data-step="1"]');
  const plus = page.locator('#sign-rows .prow .stepper button[data-step="1"]');
  await plus.nth(0).click();
  await plus.nth(0).click();
  await plus.nth(1).click();
  await page.locator('#sign-rows .prow .promise-toggle').first().click();
  await page.waitForSelector('#sign-rail .citem');
  await shot(page, 'orders-2-1280');
  await page.locator('#sign-rail').screenshot({ path: path.join(OUT, SHOT + '-orders-2-1280.png') });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(200);
  await shot(page, 'orders-2-1920');
  await page.locator('#sign-rail').screenshot({ path: path.join(OUT, SHOT + '-orders-2-1920.png') });
});

test('computed styles: padding, submit height, no stepper overlap, odds not blue', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page);
  await page.waitForSelector('#sign-rail');

  const paint = await page.evaluate(() => {
    const rail = document.getElementById('sign-rail');
    const submit = document.getElementById('sign-submit');
    const advance = document.querySelector('.advance, .gob .advance');
    const odds = document.querySelector('.stand-mult');
    const pts = document.querySelector('.stepper-pts');
    const promise = document.querySelector('.promise-toggle');
    const box = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, w: r.width, h: r.height };
    };
    const cs = rail ? getComputedStyle(rail) : null;
    const head = rail ? rail.querySelector('.rail-head, .srail-head') : null;
    const headPad = head ? getComputedStyle(head) : null;
    return {
      padL: headPad ? parseFloat(headPad.paddingLeft) : (cs ? parseFloat(cs.paddingLeft) : 0),
      padR: headPad ? parseFloat(headPad.paddingRight) : (cs ? parseFloat(cs.paddingRight) : 0),
      padT: headPad ? parseFloat(headPad.paddingTop) : (cs ? parseFloat(cs.paddingTop) : 0),
      submitH: submit ? submit.getBoundingClientRect().height : 0,
      submitBg: submit ? getComputedStyle(submit).backgroundColor : '',
      advanceH: advance ? advance.getBoundingClientRect().height : 40,
      oddsColor: odds ? getComputedStyle(odds).color : '',
      pts: box(pts),
      promise: box(promise),
    };
  });

  if (ASSERT) {
    expect(paint.padL).toBeGreaterThan(0);
    expect(paint.padR).toBeGreaterThan(0);
    expect(paint.padT).toBeGreaterThan(0);
    expect(paint.submitH).toBeGreaterThanOrEqual(paint.advanceH);
    const bg = parseRgb(paint.submitBg);
    expect(near(bg, [247, 148, 32], 50)).toBe(true);
    expect(overlap(paint.pts, paint.promise)).toBe(false);
    const odds = parseRgb(paint.oddsColor);
    expect(near(odds, BLUE, 36)).toBe(false);
    expect(near(odds, TIER_BLUE, 36)).toBe(false);
  }

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(160);
  const wide = await page.evaluate(() => {
    const pts = document.querySelector('.stepper-pts');
    const promise = document.querySelector('.promise-toggle');
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    return { pts: box(pts), promise: box(promise) };
  });
  if (ASSERT) expect(overlap(wide.pts, wide.promise)).toBe(false);
});

test('deliverable signing frame', async ({ page }) => {
  const rel = 'Recruiting Hub Deliverables/Recruiting Hub Signing Board.html';
  const server = http.createServer((req, res) => {
    const fileRel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '');
    const file = path.join(FRAMES, fileRel);
    if (!file.startsWith(FRAMES) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.statusCode = 404;
      res.end();
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.jsx': 'text/javascript', '.png': 'image/png', '.otf': 'font/otf' };
    res.setHeader('Content-Type', types[ext] || 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('http://127.0.0.1:' + port + '/' + rel.split('/').map(encodeURIComponent).join('/'));
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(OUT, 'frame-signing.png'), fullPage: true });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
