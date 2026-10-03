// @ts-check
/** Recruiting hub design tokens — computed styles, not class names. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-recruiting-hub-tokens';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SHOT = process.env.RECRUIT_SHOT || 'after';
const ASSERT = SHOT === 'after';
const OUT = path.join(__dirname, '../../reports/recruiting-hub-tokens');
const FRAMES = path.join(__dirname, '../../_documentation_master/projects');

const GREEN = [52, 236, 39];
const ORANGE = [247, 148, 32];
const NAVY = [39, 64, 142];

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
    saved_orders: week === 35 ? { 'r-lean': { points: 12, promise: false } } : {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: week >= 36 ? {
      signed_players: [{
        player_id: 'p-lean', image_id: 'r-lean', recruit_id: 'r-lean',
        name: 'Ada Lean', pos: 'PG', rt: 88, potential_rt_ratcheted: 92,
        year: 'Junior', team_id: TID, team_name: 'Lancaster',
      }],
    } : {},
    week_35_recruiting_ran: week >= 36,
    week_35_reveal_seen: week >= 36,
    invite_seed_modal_seen: true,
    visit_history: history(week >= 21 ? { 20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } } } : {}),
    current_results_week: null,
    conferences: {
      user_conference: 1, sister_conference: 2, order: [1, 2],
      by_team_id: { [TID]: 1, 'rival-1': 1 },
      user_region: 'C',
      region_by_team_id: { [TID]: 'C', 'rival-1': 'C' },
      region_team_ids: [TID, 'rival-1'],
    },
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
    recruiting_wire: Object.assign({
      board_saved_week: week >= 20 && week <= 26 ? week : 0,
      counts: {},
      week_35_orders_submitted: week >= 35,
    }, wire || {}),
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body == null ? {} : body) });
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

function radiusPx(value) {
  const n = parseFloat(String(value || ''));
  return Number.isFinite(n) ? n : -1;
}

async function shot(page, name) {
  await page.waitForTimeout(160);
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

test('pool computed styles and 1280 / 1920 shots', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 7);
  await page.waitForSelector('#hub-pool');
  const poolTab = page.getByRole('tab', { name: 'Pool', exact: true });
  if (await poolTab.count()) await poolTab.click();
  await page.waitForSelector('#hub-pool tbody tr.rec .pc-av');

  const paint = await page.evaluate(() => {
    const cs = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const s = getComputedStyle(el);
      return { color: s.color, bg: s.backgroundColor, border: s.borderTopColor, radius: s.borderRadius };
    };
    const av = document.querySelector('#hub-pool .pc-av');
    const chip = document.querySelector('#hub-pool .chip.is-active, #hub-pool .chip.is-my-region, #hub-pool .pool-seg button.is-on');
    const you = document.querySelector('.lb-slot.is-you .lb-tok, .tok.is-you');
    const name = document.querySelector('#hub-pool .recruit-name-link, #hub-pool .pc-txt .nm');
    return {
      av: av ? { radius: getComputedStyle(av).borderRadius, w: av.getBoundingClientRect().width, h: av.getBoundingClientRect().height } : null,
      chip: chip ? cs(chip.tagName ? null : '') : null,
      chipPaint: chip ? { bg: getComputedStyle(chip).backgroundColor, color: getComputedStyle(chip).color } : null,
      you: you ? getComputedStyle(you).backgroundColor : null,
      name: name ? name.textContent : '',
      toks: Array.prototype.map.call(document.querySelectorAll('#hub-pool .lb-tok, #hub-pool .tok'), (el) => el.textContent.trim()),
    };
  });

  if (ASSERT) {
    expect(paint.av).toBeTruthy();
    expect(Math.abs(paint.av.w - paint.av.h)).toBeLessThan(1);
    expect(radiusPx(paint.av.radius)).toBeGreaterThanOrEqual(4);
    expect(radiusPx(paint.av.radius)).toBeLessThanOrEqual(8);
    expect(near(parseRgb(paint.chipPaint && paint.chipPaint.bg), GREEN, 40)).toBe(false);
    expect(near(parseRgb(paint.you), NAVY, 40)).toBe(true);
    expect(near(parseRgb(paint.you), GREEN, 40)).toBe(false);
    expect(paint.name).toMatch(/Ada Lean|Bea Other/);
    expect(paint.toks.some((t) => t === 'LAN' || t === 'Lancaster')).toBe(true);
    expect(paint.toks.some((t) => t === 'FAI' || t === 'Fairview')).toBe(true);
  }
  await shot(page, 'pool-1280');

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(200);
  if (ASSERT) {
    const av1920 = await page.evaluate(() => {
      const av = document.querySelector('#hub-pool .pc-av');
      return av ? getComputedStyle(av).borderRadius : '';
    });
    expect(radiusPx(av1920)).toBeGreaterThanOrEqual(4);
    expect(radiusPx(av1920)).toBeLessThanOrEqual(8);
  }
  await shot(page, 'pool-1920');
});

test('leans computed styles at 1280', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 7);
  await page.waitForSelector('#hub-pool');
  const leans = page.getByRole('tab', { name: 'Leans', exact: true });
  if (await leans.count()) await leans.click();
  await page.waitForSelector('#hub-pool tbody tr.rec');
  const paint = await page.evaluate(() => {
    const you = document.querySelector('.lb-slot.is-you .lb-tok, .tok.is-you');
    const other = document.querySelector('.lb-slot:not(.is-you):not(.is-you-list) .lb-tok');
    const av = document.querySelector('#hub-pool .pc-av');
    return {
      you: you ? getComputedStyle(you).backgroundColor : null,
      other: other ? getComputedStyle(other).backgroundColor : null,
      radius: av ? getComputedStyle(av).borderRadius : '',
    };
  });
  if (ASSERT) {
    expect(near(parseRgb(paint.you), NAVY, 40)).toBe(true);
    expect(near(parseRgb(paint.other), GREEN, 40)).toBe(false);
    expect(near(parseRgb(paint.other), ORANGE, 40)).toBe(false);
    expect(radiusPx(paint.radius)).toBeLessThanOrEqual(8);
  }
  await shot(page, 'leans-1280');
});

test('visits calendar and invite dock stay on the colour law', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 7);
  const visits = page.getByRole('tab', { name: 'Visits', exact: true });
  if (await visits.count()) await visits.click();
  await page.waitForSelector('#hub-visits .vcal');
  const preview = await page.evaluate(() => {
    const pending = document.querySelector('.vwk.is-pending, .vwk.is-upcoming');
    const av = document.querySelector('.vwk-av');
    return {
      week: pending ? { bg: getComputedStyle(pending).backgroundColor, border: getComputedStyle(pending).borderTopColor } : null,
      radius: av ? getComputedStyle(av).borderRadius : '',
    };
  });
  if (ASSERT) {
    expect(near(parseRgb(preview.week && preview.week.bg), ORANGE, 30)).toBe(false);
    expect(near(parseRgb(preview.week && preview.week.border), ORANGE, 30)).toBe(false);
    if (preview.radius) expect(radiusPx(preview.radius)).toBeLessThanOrEqual(12);
  }
  await shot(page, 'visits-1280');

  await openHub(page, 21);
  await page.waitForSelector('#hub-board, #hub-pool, .idock, .bpanel');
  const dock = await page.evaluate(() => {
    const save = document.querySelector('.bbtn-save, .idock-save');
    const you = document.querySelector('.lb-slot.is-you .lb-tok, .tok.is-you');
    const av = document.querySelector('.bav, .pc-av');
    const name = document.querySelector('.btxt a, .recruit-name-link');
    return {
      save: save ? getComputedStyle(save).backgroundColor : null,
      you: you ? getComputedStyle(you).backgroundColor : null,
      radius: av ? getComputedStyle(av).borderRadius : '',
      name: name ? name.textContent : '',
    };
  });
  if (ASSERT) {
    expect(near(parseRgb(dock.save), ORANGE, 40)).toBe(true);
    expect(near(parseRgb(dock.save), GREEN, 40)).toBe(false);
    if (dock.you) expect(near(parseRgb(dock.you), NAVY, 40)).toBe(true);
    expect(radiusPx(dock.radius)).toBeLessThanOrEqual(8);
    expect(dock.name).toMatch(/Ada Lean|Bea Other/);
  }
  await shot(page, 'invite-dock-1280');
});

test('signing board save control is orange, not green', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 35);
  await page.waitForSelector('#hub-sign, .rail-submit, .spool');
  const paint = await page.evaluate(() => {
    const submit = document.querySelector('.rail-submit, .ssum-lr');
    const funded = document.querySelector('.prow.funded');
    const stepper = document.querySelector('.stepper button');
    return {
      submit: submit ? getComputedStyle(submit).backgroundColor : null,
      funded: funded ? getComputedStyle(funded).backgroundColor : null,
      stepper: stepper ? getComputedStyle(stepper).backgroundColor : null,
      toks: Array.prototype.map.call(document.querySelectorAll('.lb-tok, .tok, .citem-name .nm'), (el) => el.textContent.trim()),
    };
  });
  if (ASSERT) {
    expect(near(parseRgb(paint.submit), GREEN, 40)).toBe(false);
    if (paint.submit && (parseRgb(paint.submit).r + parseRgb(paint.submit).g + parseRgb(paint.submit).b) > 40) {
      expect(near(parseRgb(paint.submit), ORANGE, 50)).toBe(true);
    }
    expect(near(parseRgb(paint.stepper), ORANGE, 30)).toBe(false);
    expect(paint.toks.some((t) => /Ada Lean|LAN|Lancaster/.test(t))).toBe(true);
  }
  await shot(page, 'signing-1280');
});

test('results week keeps stored team names and square class headshots', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 36);
  await page.waitForSelector('#hub-signings, #hub-phase .pstrip');
  const paint = await page.evaluate(() => {
    const av = document.querySelector('#hub-signings .av, #hub-signings .gob-rec-class .av');
    const names = Array.prototype.map.call(
      document.querySelectorAll('#hub-signings .gob-rec-team-h, #hub-signings .gob-rec-player-link, #hub-signings td.name'),
      (el) => el.textContent.trim()
    );
    return {
      radius: av ? getComputedStyle(av).borderRadius : '',
      square: av ? Math.abs(av.getBoundingClientRect().width - av.getBoundingClientRect().height) < 1 : false,
      names: names,
    };
  });
  if (ASSERT) {
    expect(paint.names.some((t) => /Lancaster|Ada Lean/.test(t))).toBe(true);
    if (paint.radius) {
      expect(radiusPx(paint.radius)).toBeGreaterThanOrEqual(4);
      expect(radiusPx(paint.radius)).toBeLessThanOrEqual(8);
      expect(paint.square).toBe(true);
    }
  }
  await shot(page, 'results-1280');
});

test('deliverable frames load their own CSS', async ({ page }) => {
  const http = require('http');
  const frames = [
    ['Recruiting Hub Deliverables/Recruiting Hub Spine.html', 'frame-spine'],
    ['Recruiting Hub Deliverables/Recruiting Hub Invite Dock.html', 'frame-invite-dock'],
    ['Recruiting Hub Deliverables/Recruiting Hub Signing Board.html', 'frame-signing'],
    ['Recruiting Hub Deliverables/Recruiting Hub Results.html', 'frame-results'],
    ['design_handoff_browse_templates/frames/t2-recruit-pool-1280.html', 'frame-t2-pool'],
  ];
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '');
    const file = path.join(FRAMES, rel);
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
    for (const [rel, name] of frames) {
      const file = path.join(FRAMES, rel);
      expect(fs.existsSync(file)).toBe(true);
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto('http://127.0.0.1:' + port + '/' + rel.split('/').map(encodeURIComponent).join('/'));
      await page.waitForTimeout(1200);
      await page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: true });
    }
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
