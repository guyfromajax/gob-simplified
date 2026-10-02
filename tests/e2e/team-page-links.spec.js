const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * Final scores that open their box score: another team's page (Schedule › Results),
 * League › Rankings (Last Week) and the Office weekly card headline. Every payload is a
 * recorded response of a real offline season: the franchise is at week 4, and the user's
 * week-3 game was played to the final buzzer, which is the game the closed-game guard
 * used to send back to the Office. TPL_SHOTS=1 also writes
 * reports/team-page-links/after-*.png at 1280 and 1920.
 */
test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.TPL_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/team-page-links');
const GAME = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/boxscore-real-game.json'), 'utf8'));
const REAL = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/team-page-real-results.json'), 'utf8'));
const HUB = '/franchise-command-center.html?franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id;
const HEADLINE = 'Lancaster holds off Little York';

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

/**
 * The real responses. `options.detail` replaces the opponent's team page payload,
 * `options.headline` puts a headline on the Office result, `options.holdWeek` keeps
 * last week's schedule back until the returned release() is called.
 */
async function install(page, options) {
  const opts = options || {};
  const center = clone(GAME.command_center);
  center.rankings = REAL.rankings;
  if (opts.headline) center.office_digest.result.headline = opts.headline;
  let release = null;
  const held = opts.holdWeek ? new Promise((resolve) => { release = resolve; }) : null;
  const weeks = [];
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) { return route.continue(); }
    const pathname = url.pathname;
    if (pathname.indexOf('/images/players/') !== -1) return route.fulfill({ status: 404, body: '' });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/command-center/data')) return json(route, center);
    if (pathname.startsWith('/franchise/team-detail')) {
      const own = url.searchParams.get('team_id') === GAME.team_id;
      return json(route, own ? GAME.team_detail : (opts.detail || REAL.team_detail_opponent));
    }
    if (pathname.startsWith('/franchise/schedule/week')) {
      weeks.push(url.searchParams.get('week'));
      if (held) await held;
      return json(route, REAL.schedule_week_3);
    }
    if (pathname.startsWith('/franchise/news')) return json(route, { news: [], dispatches: [] });
    if (pathname === '/api/game/' + GAME.game_id + '/resume-state') return json(route, GAME.resume_state);
    if (pathname === '/api/game/' + GAME.game_id) return json(route, GAME.game);
    if (pathname.startsWith('/roster/')) {
      return json(route, pathname.indexOf(GAME.opponent_id) !== -1 ? GAME.roster_opponent : GAME.roster_user);
    }
    return json(route, {});
  });
  return { weeks, release: () => { if (release) release(); } };
}

async function open(page, query, ready) {
  await page.goto(HUB + query);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready, { timeout: 20000 });
}

/** The box score for the recorded game is on screen and stays there. */
async function expectBoxScore(page) {
  await expect(page).toHaveURL(/\/box-score\.html\?/, { timeout: 15000 });
  await page.waitForSelector('#home-player-stats-body tr', { timeout: 20000 });
  // The bounce took a second or two (two reads, then the jump): give it room to happen.
  await page.waitForTimeout(3500);
  await expect(page).toHaveURL(/\/box-score\.html\?/);
  const here = new URL(page.url());
  expect(here.searchParams.get('game_id')).toBe(GAME.game_id);
  await expect(page.locator('#box-score-container')).toContainText('Lancaster');
  await expect(page.locator('#box-score-container')).toContainText('63');
  await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(0);
  return here;
}

async function shots(page, name, ready) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    if (ready) {
      await page.waitForSelector(ready);
      await page.locator(ready).first().evaluate((node) => {
        (node.closest('section') || node).scrollIntoView({ block: 'end' });
      });
    }
    await page.mouse.move(0, 0);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
}

/** Where a result sits and how it reads, so a link can be compared with plain text. */
function resultBox(locator) {
  return locator.evaluate((node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    const text = range.getBoundingClientRect();
    const row = node.closest('.gob-sch, tr').getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      left: Math.round(text.left * 10) / 10,
      right: Math.round(text.right * 10) / 10,
      top: Math.round(text.top * 10) / 10,
      rowHeight: Math.round(row.height * 100) / 100,
      color: style.color,
      underline: style.textDecorationLine,
      size: style.fontSize,
      weight: style.fontWeight,
    };
  });
}

const TEAM_PAGE = '&tab=team-view&view_team_id=' + GAME.opponent_id;

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('the recorded team page is the real shape: three results, each with its stored game', () => {
  const results = REAL.team_detail_opponent.results;
  expect(results.map((row) => row.week)).toEqual([3, 2, 1]);
  expect(results[0].game_id).toBe(GAME.game_id);
  // Weeks 1 and 2 are games between two CPU teams: they have stored games too.
  results.forEach((row) => expect(String(row.game_id)).toMatch(/^[0-9a-f]{24}$/));
  expect(REAL.team_detail_opponent.upcoming.length).toBeGreaterThan(0);
});

test('another team\'s page: a completed result opens its box score, and Back returns to that team page', async ({ page }) => {
  await install(page);
  await open(page, TEAM_PAGE, '#team-view .gob-team-sched .gob-sch');
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Little York');

  // Every result is a link to its own game; nothing in Upcoming is.
  const links = page.locator('#team-view .gob-team-sched a.gob-sch-res');
  await expect(links).toHaveCount(3);
  const hrefs = await links.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href')));
  REAL.team_detail_opponent.results.forEach((row, index) => {
    const href = new URL(hrefs[index], 'http://x');
    expect(href.pathname).toBe('/box-score.html');
    expect(href.searchParams.get('game_id')).toBe(row.game_id);
    expect(href.searchParams.get('franchise_id')).toBe(GAME.franchise_id);
    expect(href.searchParams.get('team_id')).toBe(GAME.team_id);
  });
  expect(await links.evaluateAll((nodes) => nodes.every((node) => node.hasAttribute('data-return')))).toBe(true);
  const columns = page.locator('#team-view .gob-sch-split > div');
  await expect(columns.nth(1).locator('.gob-sch')).toHaveCount(REAL.team_detail_opponent.upcoming.length);
  await expect(columns.nth(1).locator('a[href*="box-score"]')).toHaveCount(0);
  await expect(columns.nth(1).locator('.gob-sch-res')).toHaveCount(0);
  await shots(page, 'team-page-results', '#team-view .gob-team-sched a.gob-sch-res');

  const result = page.locator('#team-view a.gob-sch-res[href*="' + GAME.game_id + '"]');
  await expect(result).toHaveText('L 58–63');
  await result.click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('tab=team-view');
  expect(here.searchParams.get('return_url')).toContain('view_team_id=' + GAME.opponent_id);
  await shots(page, 'box-score-from-team-page', '#home-player-stats-body tr');

  await page.locator('#locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('team-view');
  expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(GAME.opponent_id);
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Little York', { timeout: 20000 });
});

test('another team\'s page: a linked result sits and reads exactly as the plain one did', async ({ page }) => {
  // The same page with the stored games taken off: the results are plain text.
  const plain = clone(REAL.team_detail_opponent);
  plain.results.forEach((row) => { delete row.game_id; });
  await install(page, { detail: plain });
  await open(page, TEAM_PAGE, '#team-view .gob-team-sched .gob-sch-res');
  await expect(page.locator('#team-view .gob-team-sched a.gob-sch-res')).toHaveCount(0);
  const spans = page.locator('#team-view .gob-team-sched span.gob-sch-res');
  await expect(spans).toHaveCount(3);
  const before = [];
  for (let i = 0; i < 3; i += 1) before.push(await resultBox(spans.nth(i)));
  const texts = await spans.allTextContents();

  await page.unroute('**/*');
  await install(page);
  await page.reload();
  await page.waitForSelector('#team-view .gob-team-sched a.gob-sch-res', { timeout: 20000 });
  const links = page.locator('#team-view .gob-team-sched a.gob-sch-res');
  await expect(links).toHaveCount(3);
  expect(await links.allTextContents()).toEqual(texts);
  for (let i = 0; i < 3; i += 1) {
    const after = await resultBox(links.nth(i));
    expect(after, 'result ' + i).toEqual(before[i]);
    expect(after.underline).toBe('none');
  }
  // The loss keeps its quieter colour; the win does not take it.
  expect(before[0].color).not.toBe(before[2].color);
});

test('Rankings: Last Week opens that game\'s box score, and Back returns to Rankings', async ({ page }) => {
  const net = await install(page, { holdWeek: true });
  await open(page, '&tab=rankings-view', '#rankings-table tbody tr');

  // Until last week's games are read, the results are plain text.
  const cells = page.locator('#rankings-table tbody tr td:nth-child(7)');
  await expect(cells).toHaveCount(25);
  await expect(page.locator('#rankings-view a.gob-res')).toHaveCount(0);
  const mine = page.locator('#rankings-table tbody tr.me td:nth-child(7)');
  await expect(mine).toHaveText(/W\s*@ Little York, 63-58/);
  const before = await resultBox(mine);
  const texts = await cells.allTextContents();

  net.release();
  await expect(page.locator('#rankings-view a.gob-res')).toHaveCount(25, { timeout: 15000 });
  // It asked for the week before the franchise's, once.
  expect(net.weeks).toEqual([String(Number(REAL.week) - 1)]);
  expect(await cells.allTextContents()).toEqual(texts);
  const link = mine.locator('a.gob-res');
  const after = await resultBox(link);
  expect(after).toEqual(before);

  // Each row links to the game that team played last week.
  const byTeam = {};
  REAL.schedule_week_3.games.forEach((game) => {
    byTeam[game.away.team_id] = game.game_id;
    byTeam[game.home.team_id] = game.game_id;
  });
  const rows = await page.locator('#rankings-table tbody tr').evaluateAll((nodes) => nodes.map((node) => ({
    href: node.querySelector('a.gob-res').getAttribute('href'),
    back: node.querySelector('a.gob-res').hasAttribute('data-return'),
  })));
  expect(rows.length).toBe(REAL.rankings.length);
  rows.forEach((row, index) => {
    const team = REAL.rankings[index];
    expect(new URL(row.href, 'http://x').searchParams.get('game_id'), team.team_name).toBe(byTeam[team.team_id]);
    expect(row.back, team.team_name).toBe(true);
  });
  await shots(page, 'rankings-last-week', '#rankings-view a.gob-res');

  await link.click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('tab=rankings-view');
  await page.locator('#locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('rankings-view');
});

test('Rankings: a team with no stored game last week keeps a plain result', async ({ page }) => {
  await install(page);
  await page.route('**/franchise/schedule/week**', (route) => {
    const week = clone(REAL.schedule_week_3);
    week.games.forEach((game) => {
      if (game.away.team_id === GAME.team_id || game.home.team_id === GAME.team_id) delete game.game_id;
    });
    return json(route, week);
  });
  await open(page, '&tab=rankings-view', '#rankings-table tbody tr');
  await expect(page.locator('#rankings-view a.gob-res')).toHaveCount(24, { timeout: 15000 });
  const mine = page.locator('#rankings-table tbody tr.me td:nth-child(7)');
  await expect(mine).toHaveText(/W\s*@ Little York, 63-58/);
  await expect(mine.locator('a')).toHaveCount(0);
});

test('Office: the weekly card headline opens the box score', async ({ page }) => {
  // The real save's result carries no headline (the server only sends one when a news
  // story names the game), so the headline text is added to the recorded payload.
  await install(page, { headline: HEADLINE });
  await open(page, '', '#office-root .wkc a.wkc-hl');
  const headline = page.locator('#office-root .wkc a.wkc-hl');
  await expect(headline).toHaveText(HEADLINE);
  await headline.click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('/franchise-command-center.html');
});
