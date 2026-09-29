const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 240000 });

const FID = 'f-e2e-polish-rns';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/polish-recruit-news-settings');
const SHOTS = process.env.POLISH_SHOTS === '1';
function cc(week) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 8,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: week, counts: {} },
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 9, losses: 3 },
    rankings: [],
  };
}

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
    Lean: leans ? { 1: TID, 2: null, 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function recruitingData() {
  const names = ['Ada Lean', 'Bea Other', 'Cal Brooks', 'Dev Moreno', 'Eli Hart', 'Finn Walsh'];
  return {
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: 21,
    recruits: names.map((name, i) => recruit('r-' + i, name, i % 2 === 0)),
    board: ['r-0', 'r-2', 'r-4'],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: [20, 21, 22, 23, 24, 25, 26].map((week) => ({
      week: week,
      recruit_id: week === 20 ? 'r-0' : null,
      name: week === 20 ? 'Ada Lean' : null,
      lean: week === 20 ? { 1: TID } : null,
    })),
  };
}

function newsBody() {
  return {
    week: 12,
    news: [
      { story_id: 'w12-upset', week: 12, type: 'upset_report', headline: 'Week 12 Upset Report', lines: ['Lancaster upset Four Corners.'] },
      { story_id: 'w11-wire', week: 11, type: 'recruiting_leans', headline: 'Leans shift in Region C', lines: ['Ada Lean moved to #1.'] },
      { story_id: 'w10-ps', week: 10, type: 'ps_game_results', headline: 'Practice Squad results', lines: ['The reserve side won.'] },
    ],
    dispatches: [
      { week: 12, type: 'game_result', headline: 'Lancaster defeated Four Corners 70-64', target: '/box-score.html?game_id=g1', link_label: 'box score', yours: true },
      { week: 11, type: 'training_report', headline: 'Week 11 training report', target: '/training-report.html?week=11', link_label: 'view', yours: true },
    ],
  };
}

function teams40() {
  const rows = [];
  for (let i = 0; i < 40; i += 1) {
    rows.push({
      team: i === 3 ? 'Lancaster' : ('Club ' + (i + 1)),
      team_id: i === 3 ? TID : ('cstat' + i).padEnd(24, 'd'),
      primary_color: '#1c2a52',
      natl_rank: i + 1,
      conference: 1,
      region: 'C',
      stats: { W: 9, L: 3, PF: 72, PA: 64, FGM: 28, FGA: 60, FG_PCT: 46.7, '3PTM': 8, '3PTA': 22, TP_PCT: 36.4, FTM: 12, FTA: 16, FT_PCT: 75, DREB: 24, OREB: 10, TREB: 34, AST: 14, F: 16, TO: 11, SCR_A: 12, SCR_PCT: 50, STL: 7, BLK: 3, DEF_A: 40, DEF_PCT: 55 },
    });
  }
  return { teams: rows };
}

const ME = {
  user_id: 'e2e-user',
  username: 'e2e',
  email: 'e2e@example.com',
  record: { wins: 12, losses: 5 },
  championships_total: { conf_rs: 1, conf_t: 0, region: 0, national: 2 },
  geek_points: 1200,
  geek_points_by_team: { IDA: 400, BENTLEY_TRUMAN: 300, LANCASTER: 200 },
  archetype_reveal_seen: true,
  archetypes: {
    total: 100,
    authoritarian: 40,
    'systems-coach': 25,
    'player-maximizer': 15,
    'culture-builder': 10,
    tactician: 6,
    motivator: 4,
  },
};

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body == null ? {} : body) });
}

async function installApi(page, week) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) { await route.continue(); return; }
    const pathname = url.pathname;
    if (pathname.indexOf('/images/players/') !== -1 || pathname.indexOf('/images/recruits/') !== -1) {
      await route.fulfill({ status: 404, body: '' });
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, ME); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', object_id: TID, _id: TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, cc(week)); return; }
    if (pathname.startsWith('/franchise/recruiting-data')) { await fulfillJson(route, recruitingData()); return; }
    if (pathname.startsWith('/franchise/news')) { await fulfillJson(route, newsBody()); return; }
    if (pathname.startsWith('/franchise/team-stats')) { await fulfillJson(route, teams40()); return; }
    await fulfillJson(route, {});
  });
}

async function ready(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

async function park(page) {
  const box = await page.locator('html.gob-shell .main, .acct, .settings').first().boundingBox();
  if (box) await page.mouse.move(box.x + 8, box.y + 8);
}

async function shot(page, name, size) {
  if (!SHOTS) return;
  await page.waitForTimeout(120);
  await park(page);
  await page.screenshot({ path: path.join(OUT, name + '-' + size + '.png') });
}

async function assertNoOverflow(page, label) {
  const overflow = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main') || document.scrollingElement;
    const se = document.scrollingElement;
    return { main: main.scrollWidth - main.clientWidth, page: se.scrollWidth - se.clientWidth };
  });
  expect(overflow.main, label + ' main').toBeLessThanOrEqual(1);
  expect(overflow.page, label + ' page').toBeLessThanOrEqual(1);
  if (await page.locator('html.gob-shell .main').count()) await assertOneVerticalScroll(page);
}

test.beforeAll(() => {
  if (SHOTS) fs.mkdirSync(OUT, { recursive: true });
});

for (const size of [[1280, 720], [1920, 1080]]) {
  const tag = String(size[0]);

  test('recruit news settings polish at ' + tag, async ({ page }) => {
    await installApi(page, 21);
    await stubAuth(page);
    await page.setViewportSize({ width: size[0], height: size[1] });

    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-stats-view');
    await ready(page);
    await page.waitForSelector('#teamstats-body tr');
    await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 1400; });
    await page.waitForTimeout(80);
    const ghost = await page.evaluate(() => {
      const headEl = document.querySelector('html.gob-shell .pg-head');
      const thEl = document.querySelector('#team-stats-view thead th');
      const head = headEl.getBoundingClientRect();
      const th = thEl.getBoundingClientRect();
      const headFill = getComputedStyle(headEl).backgroundColor;
      const thFill = getComputedStyle(thEl).backgroundColor;
      return {
        gap: th.top - head.bottom,
        headFill: headFill,
        thFill: thFill,
        headAlpha: headFill.indexOf('rgba') === 0 && /,\s*0(\.\d+)?\)/.test(headFill),
        thAlpha: thFill.indexOf('rgba') === 0 && /,\s*0(\.\d+)?\)/.test(thFill)
      };
    });
    expect(ghost.gap, 'gap under page head').toBeLessThanOrEqual(1);
    expect(ghost.headAlpha, 'page head opaque').toBe(false);
    expect(ghost.thAlpha, 'pinned header opaque').toBe(false);
    await shot(page, 'team-stats-scrolled', tag);

    await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
    await page.waitForSelector('#hub-pool tbody tr.rec');
    await expect(page.getByRole('tab', { name: 'Pool', exact: true })).toHaveCount(0);
    await expect(page.getByRole('tab', { name: 'Leans', exact: true })).toHaveCount(0);
    await expect(page.getByRole('tab', { name: 'Visits', exact: true })).toHaveCount(0);
    await expect(page.locator('#hub-board')).toBeVisible();
    await expect(page.locator('#hub-visits .vcal')).toBeVisible();
    const shots = page.locator('#hub-pool .pc-av, #hub-board .bav, #hub-visits .vwk-av');
    await expect(shots.first()).toBeVisible();
    const square = await shots.evaluateAll(function (nodes) {
      return nodes.slice(0, 8).map(function (node) {
        const box = node.getBoundingClientRect();
        const radius = parseFloat(getComputedStyle(node).borderTopLeftRadius) || 0;
        return { w: Math.round(box.width), h: Math.round(box.height), r: radius };
      });
    });
    square.forEach(function (box) {
      expect(Math.abs(box.w - box.h), 'square headshot').toBeLessThanOrEqual(1);
      expect(box.r).toBeGreaterThan(0);
      expect(box.r).toBeLessThan(box.w / 2);
    });
    await shot(page, 'recruiting-week21', tag);

    const callout = page.locator('.hub-more');
    await expect(callout).toBeVisible();
    const beforeScroll = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main ? main.scrollTop : 0;
    });
    await callout.click();
    await page.waitForFunction((prev) => {
      const pool = document.getElementById('hub-pool');
      const main = document.querySelector('html.gob-shell .main');
      const head = document.querySelector('html.gob-shell .pg-head');
      if (!pool || !main) return false;
      const top = pool.getBoundingClientRect().top;
      const band = head ? head.getBoundingClientRect().bottom + 72 : 160;
      return main.scrollTop > prev + 8 || top <= band;
    }, beforeScroll, { timeout: 8000 });
    await shot(page, 'recruiting-callout', tag);
    await assertNoOverflow(page, 'recruiting ' + tag);

    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=news-view');
    await ready(page);
    await page.waitForSelector('#news-view .gob-news-card');
    const hero = page.locator('#news-view .gob-news-card.is-hero');
    await expect(hero).toContainText('(Box Score)');
    await expect(hero).toHaveAttribute('href', /box-score\.html/);
    await expect(page.locator('#news-view a.lnk')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'View', exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Box Score', exact: true })).toHaveCount(0);
    const cols = await page.evaluate(() => {
      const grid = document.querySelector('#news-view .gob-news-grid');
      return getComputedStyle(grid).gridTemplateColumns.split(' ').length;
    });
    expect(cols).toBe(size[0] >= 1680 ? 3 : 2);
    await assertNoOverflow(page, 'news ' + tag);
    await shot(page, 'news', tag);

    await page.locator('#gob-rail-settings').click();
    const panel = page.locator('#gob-settings-host .settings');
    await expect(panel).toBeVisible();
    const rec = panel.locator('.cs-rec b');
    await expect(rec).toContainText('12');
    await expect(rec).toContainText('5');
    const recBox = await rec.evaluate(function (el) {
      const nums = Array.from(el.querySelectorAll('em')).map(function (n) { return n.getBoundingClientRect(); });
      return { oneLine: nums.length === 2 && Math.abs(nums[0].top - nums[1].top) < 2 };
    });
    expect(recBox.oneLine).toBe(true);
    await shot(page, 'settings', tag);
    await page.locator('[data-settings-close]').click();

    await page.goto('/account.html');
    await page.waitForSelector('#gp-by-team .gp-team-name');
    const names = await page.locator('#gp-by-team .gp-team-name').allTextContents();
    expect(names).toContain('IDA');
    expect(names.join(' ')).toMatch(/Bentley Truman/);
    expect(names.join(' ')).not.toMatch(/BENTLEY_TRUMAN/);
    const order = await page.locator('.arch-cell .arch-aname').allTextContents();
    expect(order.length).toBeGreaterThan(3);
    const flow = await page.locator('.arch-board-grid').evaluate(function (grid) {
      return getComputedStyle(grid).gridAutoFlow;
    });
    expect(flow).toMatch(/column/);
    await page.locator('.arch-board-grid').scrollIntoViewIfNeeded();
    await shot(page, 'settings-archetypes', tag);
  });
}
