const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-t1';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/t1-tables');

function etag(kind, week) {
  return 'W/"' + FID + ':1:' + week + ':0:t1' + kind + ':1"';
}

function standings(week) {
  const rows = [];
  const regions = ['A', 'A', 'B', 'C'];
  const conferences = [1, 2, 1, 1];
  regions.forEach(function (region, card) {
    for (let i = 0; i < 12; i += 1) {
      const mine = card === 0 && i === 0;
      const id = mine ? TID : ('c' + card + 't' + i).padEnd(24, 'b');
      rows.push({
        team_id: id,
        name: mine ? 'Lancaster' : ('Club ' + region + conferences[card] + '-' + (i + 1)),
        display_name: mine ? 'Lancaster' : ('Club ' + region + conferences[card] + '-' + (i + 1)),
        region: region,
        conference: conferences[card],
        W: mine ? (week === 1 ? 10 : 11) : 8 - (i % 3),
        L: mine ? 2 : 1 + (i % 3),
        pct: mine ? 0.833 : 0.5,
        PF: 80,
        PA: 70,
        differential: mine ? 48 : 10 - i,
        streak: mine ? (week === 1 ? 'W3' : 'W4') : 'L1',
        natl_rank: i + 1,
        next_opponent_id: 'opp-lancaster',
        next_opponent_name: 'Four Corners',
        next_week: week,
        next_site: 'vs',
      });
    }
  });
  return {
    standings: rows,
    user_conference: 1,
    user_region: 'A',
  };
}

function leaders(week, limit) {
  const count = limit >= 50 ? 30 : 5;
  const totals = { '3PTM': 1, BLK: 1, STL: 1 };
  const rates = { 'FG%': 1, 'DEF%': 1 };
  const body = {};
  ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'].forEach(function (stat) {
    const rows = [];
    for (let i = 0; i < count; i += 1) {
      const mine = i === 2;
      let value = 20 - i;
      if (totals[stat]) value = 40 - i;
      if (rates[stat]) value = i === 0 ? 75 : (70 - i);
      const row = {
        player_id: stat === 'AST' ? '' : (stat + '-p' + i),
        name: (week === 1 ? 'Alpha ' : 'Beta ') + stat + ' ' + (i + 1),
        team: mine ? 'Lancaster' : ('Club ' + (i + 1)),
        team_id: mine ? TID : ('bbbbbbbbbbbbbbbbbbbbbbb' + (i % 10)),
        position: 'G',
        year: 'JR',
        value: value,
      };
      if (stat === 'FG%') row.qualification_caption = 'min 5 FGA per team game';
      if (stat === 'DEF%') row.qualification_caption = 'min 6 DEF_A per team game';
      rows.push(row);
    }
    body[stat] = rows;
  });
  return body;
}

function teamStats(week) {
  const teams = [];
  for (let i = 0; i < 40; i += 1) {
    const mine = i === 3;
    teams.push({
      team: mine ? 'Lancaster' : ('Club ' + (i + 1)),
      team_id: mine ? TID : ('cstat' + i).padEnd(24, 'd'),
      primary_color: i === 0 ? '#112233' : (i === 1 ? '#445566' : '#1c2a52'),
      natl_rank: i + 1,
      conference: (i % 4) + 1,
      region: 'A',
      stats: {
        W: 10, L: 2, PF: week === 1 ? 70 : 88, PA: 64,
        FGM: 28, FGA: 60, FG_PCT: 46.7,
        '3PTM': 8, '3PTA': 22, TP_PCT: 36.4,
        FTM: 12, FTA: 16, FT_PCT: 75,
        DREB: 24, OREB: 10, TREB: 34,
        AST: 14, F: 16, TO: 11, SCR_A: 12, SCR_PCT: 50,
        STL: 7, BLK: 3, DEF_A: 40, DEF_PCT: 55,
      },
    });
  }
  return { teams: teams };
}

function payload(week) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    user_team_object_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 4,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: week, counts: {} },
    user_conference: 1,
    user_region: 'A',
    team_record: { wins: week === 1 ? 10 : 11, losses: 2 },
    rankings: [],
  };
}

async function fulfillJson(route, body, status, headers) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    headers: headers || {},
    body: body == null ? '' : JSON.stringify(body),
  });
}

async function installApi(page, state) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    let search = '';
    try {
      const url = new URL(request.url());
      pathname = url.pathname;
      search = url.searchParams;
    } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.indexOf('/images/players/') !== -1) {
      if (pathname.indexOf('3PTM') !== -1) {
        await route.fulfill({ status: 404, body: '' });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64'),
      });
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (request.method() === 'POST' && pathname.indexOf('/franchise/complete-week') !== -1) {
      state.week = 2;
      await fulfillJson(route, { ok: true, week: 2 });
      return;
    }
    const liveWeek = state.week;
    function cached(kind, body) {
      const tag = etag(kind, liveWeek);
      if ((request.headers()['if-none-match'] || '') === tag) {
        return route.fulfill({ status: 304, headers: { ETag: tag } });
      }
      return route.fulfill({
        status: 200,
        headers: { ETag: tag, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await cached('cc', payload(liveWeek));
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await cached('standings', standings(liveWeek));
      return;
    }
    if (pathname.startsWith('/franchise/leaders')) {
      if (search.has('basis')) throw new Error('leaders request sent basis');
      const limit = Number(search.get('limit') || '5');
      await cached('leaders' + limit, leaders(liveWeek, limit));
      return;
    }
    if (pathname.startsWith('/franchise/team-stats')) {
      await cached('teamstats', teamStats(liveWeek));
      return;
    }
    if (pathname.startsWith('/franchise/team-data') || pathname.startsWith('/roster/')) {
      await fulfillJson(route, { team_attributes: { team_chemistry: 10 }, players: [], name: 'Lancaster' });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page) {
  await stubAuth(page);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
  await page.evaluate(() => {
    ['gob-view-standings-scope', 'gob-view-leaders-scope', 'gob-view-leaders-basis'].forEach(function (key) {
      sessionStorage.removeItem(key);
    });
  });
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

function stab(page, label) {
  return page.getByRole('tab', { name: label, exact: true });
}

async function docStamp(page) {
  return page.evaluate(() => {
    if (!window.__docStamp) window.__docStamp = String(Math.random());
    return { stamp: window.__docStamp, nav: performance.getEntriesByType('navigation').length };
  });
}

async function assertNoMainOverflow(page) {
  const overflow = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const se = document.scrollingElement;
    return {
      main: main.scrollWidth - main.clientWidth,
      page: se.scrollWidth - se.clientWidth,
    };
  });
  expect(overflow.main).toBeLessThanOrEqual(1);
  expect(overflow.page).toBeLessThanOrEqual(1);
  await assertOneVerticalScroll(page);
}

async function parkPointer(page) {
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + Math.min(320, box.width / 2), box.y + 88);
}

async function assertCollapsedRail(page) {
  if (page.viewportSize().width >= 1680) return;
  await parkPointer(page);
  const leaked = await page.evaluate(() => {
    const face = document.querySelector('html.gob-shell .rail-face');
    if (!face) return ['missing rail'];
    const railRight = face.getBoundingClientRect().right;
    return Array.from(document.querySelectorAll('.rail-l')).filter(function (el) {
      const box = el.getBoundingClientRect();
      const opacity = Number(getComputedStyle(el).opacity);
      return opacity > 0.05 && box.width > 1 && box.right > railRight + 0.5;
    }).map(function (el) { return el.textContent.trim(); });
  });
  expect(leaked).toEqual([]);
}

async function clickStab(page, label) {
  await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    if (main) main.scrollTop = 0;
  });
  await stab(page, label).click();
}

async function timedOpen(page, label, ready) {
  const t0 = Date.now();
  await clickStab(page, label);
  await page.waitForSelector(ready);
  return Date.now() - t0;
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('standings, leaders, and team stats open in place', async ({ page }) => {
  const state = { week: 1 };
  const notes = [];
  await installApi(page, state);
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page);
    const before = await docStamp(page);
    const standingsOpened = Date.now();
    await mouseClick(page, '[data-gob-section="league"]');
    await page.waitForSelector('#standings-view .gob-tbl tbody tr');
    const standingsFirst = Date.now() - standingsOpened;
    const leagueIdx = await page.evaluate(() => history.state && history.state.gobIdx);
    expect(page.url()).toContain('tab=standings-view');
    expect((await docStamp(page)).stamp).toBe(before.stamp);
    await expect(page.locator('#standings-view tr.is-user')).toHaveCount(1);
    await expect(page.locator('#standings-view tr.is-user')).toContainText('Lancaster');
    await expect(page.locator('#standings-view tr.is-user')).toContainText('W3');
    await expect(page.locator('#standings-view .gob-next').first()).toContainText('W1');
    await expect(page.locator('#standings-view tr.is-user')).toContainText('.833');
    await parkPointer(page);
    await assertCollapsedRail(page);
    await expect(page.locator('#standings-view')).not.toContainText(/Mon|Tue|Wed|Thu|Fri|Sat|Sun|\d{1,2}:\d{2}/);
    const labels = await page.locator('#gob-subtabs .tabs > .tb .tb-l').allTextContents();
    expect(labels.map(function (text) { return text.trim(); }).filter(Boolean)).toEqual([
      'Standings', 'Rankings', 'Leaders', 'Team Stats', 'Schedule', 'Practice Squad', 'Tournament',
    ]);
    await clickStab(page, 'Rankings');
    const standingsSecond = await timedOpen(page, 'Standings', '#standings-view .gob-tbl tbody tr');
    expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
    await assertNoMainOverflow(page);

    const leadersFirst = await timedOpen(page, 'Leaders', '#leaders-view .gob-ldb');
    expect(page.url()).toContain('tab=leaders-view');
    expect((await docStamp(page)).stamp).toBe(before.stamp);
    expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
    await expect(page.locator('#leaders-view .gob-ldb')).toHaveCount(8);
    await expect(page.locator('#leaders-view .is-user').first()).toBeVisible();
    await expect(page.locator('#gob-subtabs .pg-tools')).not.toContainText('Per game');
    await expect(page.locator('#gob-subtabs .pg-tools')).not.toContainText('Totals');
    const cards = page.locator('#leaders-view .gob-ldb');
    await expect(cards.nth(0).locator('.meta')).toHaveText('per game');
    await expect(cards.nth(1).locator('.meta')).toHaveText('total');
    await expect(cards.nth(2).locator('.meta')).toHaveText('per game');
    await expect(cards.nth(3).locator('.meta')).toHaveText('total');
    await expect(cards.nth(5).locator('.meta')).toHaveText('per game');
    await expect(cards.nth(6).locator('.meta')).toHaveText('total');
    await expect(cards.nth(4).locator('.card-h .meta')).toHaveCount(0);
    await expect(cards.nth(7).locator('.card-h .meta')).toHaveCount(0);
    await expect(cards.nth(0).locator('.ldb-v')).toContainText('20.0');
    await expect(cards.nth(0).locator('.ldb-v')).toContainText('PPG');
    await expect(cards.nth(1).locator('.ldb-v')).toHaveText('40');
    await expect(cards.nth(4).locator('.ldb-v')).toContainText('75.0');
    await expect(cards.nth(4).locator('.ldb-v')).toContainText('%');
    await expect(page.locator('#leaders-view .cap')).toHaveCount(0);
    await expect(cards.nth(0).locator('.av img')).toBeVisible();
    await expect(cards.nth(1).locator('.av img')).toHaveCount(0);
    await expect(cards.nth(1).locator('.av')).toContainText('A3');
    await expect(cards.nth(2).locator('.av img')).toHaveCount(0);
    await expect(cards.nth(2).locator('.av')).toContainText('AA');
    await expect(page.locator('#leaders-view .spinner, #leaders-view [class*="spinner"]')).toHaveCount(0);
    await clickStab(page, 'Rankings');
    const leadersSecond = await timedOpen(page, 'Leaders', '#leaders-view .gob-ldb');
    await assertNoMainOverflow(page);
    await parkPointer(page);
    await assertCollapsedRail(page);
    await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveCount(1);
    await page.screenshot({ path: path.join(OUT, 'leaders-' + size[2] + '.png') });

    const statsFirst = await timedOpen(page, 'Team Stats', '#teamstats-body tr');
    expect(page.url()).toContain('tab=team-stats-view');
    expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
    await expect(page.locator('#team-stats-view tr.gob-rep')).toHaveCount(2);
    const scrollable = await page.evaluate(() => {
      const card = document.querySelector('#team-stats-view .gob-xs');
      const header = document.querySelector('#team-stats-view .gob-xs thead th');
      return {
        wide: card.scrollWidth > card.clientWidth + 1,
        sticky: getComputedStyle(header).position,
      };
    });
    expect(scrollable.wide).toBe(true);
    expect(scrollable.sticky).toBe('static');
    await expect(page.locator('#team-stats-view thead th[data-sort="natl_rank"]')).toHaveClass(/asc/);
    await expect(page.locator('#team-stats-view')).toContainText('75.0');
    await expect(page.locator('#team-stats-view')).toContainText('46.7');
    await expect(page.locator('#team-stats-view')).toContainText('50.0');
    await assertNoMainOverflow(page);
    await parkPointer(page);
    await assertCollapsedRail(page);
    await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveCount(1);
    await page.screenshot({ path: path.join(OUT, 'team-stats-' + size[2] + '.png') });
    await page.evaluate(() => {
      const card = document.querySelector('#team-stats-view .gob-xs');
      card.scrollLeft = card.scrollWidth;
    });
    await page.screenshot({ path: path.join(OUT, 'team-stats-scrolled-' + size[2] + '.png') });
    await clickStab(page, 'Rankings');
    const statsSecond = await timedOpen(page, 'Team Stats', '#teamstats-body tr');

    await clickStab(page, 'Standings');
    await page.waitForSelector('#standings-view .gob-tcard');
    await parkPointer(page);
    await assertCollapsedRail(page);
    await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveCount(1);
    await page.screenshot({ path: path.join(OUT, 'standings-' + size[2] + '.png') });
    await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
    await page.getByRole('button', { name: 'National', exact: true }).click();
    await expect(page.locator('#standings-view .gob-tcard')).toHaveCount(4);
    if (size[0] >= 1680) {
      const columns = await page.evaluate(() => getComputedStyle(document.querySelector('#standings-view .gob-tgrid')).gridTemplateColumns);
      expect(columns.split(' ').length).toBe(2);
    }
    await parkPointer(page);
    await page.screenshot({ path: path.join(OUT, 'standings-national-' + size[2] + '.png') });
    await assertNoMainOverflow(page);

    notes.push([
      size[2],
      'standings', standingsFirst, standingsSecond,
      'leaders', leadersFirst, leadersSecond,
      'team-stats', statsFirst, statsSecond,
    ].join(' '));
  }
  fs.writeFileSync(path.join(OUT, 'timings.txt'), notes.join('\n') + '\n');

  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view .gob-tbl tbody tr');
  const leagueIdx = await page.evaluate(() => history.state && history.state.gobIdx);
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
  await page.getByRole('button', { name: 'National', exact: true }).click();
  await page.waitForSelector('#standings-view .gob-tcard:nth-child(4)');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 520; });
  const saved = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(saved).toBeGreaterThan(200);
  const link = page.locator('#standings-view .gob-team').nth(8);
  await link.scrollIntoViewIfNeeded();
  await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const head = document.querySelector('html.gob-shell .pg-head');
    const header = document.querySelector('#standings-view .gob-tbl thead th');
    const a = document.querySelectorAll('#standings-view .gob-team')[8];
    const limit = Math.max(head.getBoundingClientRect().bottom, header ? header.getBoundingClientRect().bottom : 0) + 16;
    if (a.getBoundingClientRect().top < limit) main.scrollTop -= (limit - a.getBoundingClientRect().top);
  });
  const scrollBefore = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  await link.evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=team-view/, { timeout: 15000 });
  await page.goBack();
  await page.waitForURL(/tab=standings-view/);
  await page.waitForSelector('#standings-view .gob-tbl tbody tr');
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, scrollBefore, { timeout: 8000 });
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toBeVisible();
});

test('first open shows a skeleton and a failed module retries', async ({ page }) => {
  const views = [
    ['standingsView.js', 'Standings', '#standings-view', '#standings-view .gob-tbl tbody tr'],
    ['leadersView.js', 'Leaders', '#leaders-view', '#leaders-view .gob-ldb'],
    ['teamStatsView.js', 'Team Stats', '#team-stats-view', '#teamstats-body tr'],
  ];
  for (const view of views) {
    const state = { week: 1 };
    let release;
    const gate = new Promise(function (resolve) { release = resolve; });
    await installApi(page, state);
    await page.route('**/js/shared/views/' + view[0], async (route) => {
      if (route.request().url().indexOf('retry=') !== -1) {
        await route.fallback();
        return;
      }
      await gate;
      await route.fallback();
    });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page);
    await mouseClick(page, '[data-gob-section="league"]');
    if (view[1] !== 'Standings') await clickStab(page, view[1]);
    await expect(page.locator(view[2] + ' .gob-view-skel')).toBeVisible();
    await expect(page.locator(view[2] + ' .spinner, ' + view[2] + ' [class*="spinner"]')).toHaveCount(0);
    release();
    await page.waitForSelector(view[3]);
    await page.unroute('**/js/shared/views/' + view[0]);
  }
});

test('a failed module shows a retry card', async ({ page }) => {
  const views = [
    ['standingsView.js', 'Standings', '#standings-view', '#standings-view .gob-tbl tbody tr'],
    ['leadersView.js', 'Leaders', '#leaders-view', '#leaders-view .gob-ldb'],
    ['teamStatsView.js', 'Team Stats', '#team-stats-view', '#teamstats-body tr'],
  ];
  for (const view of views) {
    const state = { week: 1 };
    await installApi(page, state);
    await page.route('**/js/shared/views/' + view[0] + '*', async (route) => {
      if (route.request().url().indexOf('retry=') !== -1) {
        await route.fallback();
        return;
      }
      await route.fulfill({ status: 500, body: 'nope' });
    });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page);
    await mouseClick(page, '[data-gob-section="league"]');
    if (view[1] !== 'Standings') await clickStab(page, view[1]);
    await expect(page.locator(view[2] + ' .gob-view-error')).toBeVisible();
    await expect(page.locator(view[2] + ' .gob-view-retry')).toBeVisible();
    await mouseClick(page, view[2] + ' .gob-view-retry');
    await page.waitForSelector(view[3]);
    await page.unroute('**/js/shared/views/' + view[0] + '*');
  }
});

test('old standings, leaders, and team stats urls redirect', async ({ page }) => {
  const state = { week: 1 };
  await installApi(page, state);
  await stubAuth(page);
  const files = [
    ['/standings.html', 'standings-view'],
    ['/leaders.html', 'leaders-view'],
    ['/team-stats.html', 'team-stats-view'],
  ];
  for (const file of files) {
    const ret = '/schedule.html?franchise_id=' + FID;
    await page.goto(file[0] + '?franchise_id=' + FID + '&team_id=' + TID + '&return_url=' + encodeURIComponent(ret));
    await page.waitForURL(/franchise-command-center\.html/);
    const landed = new URL(page.url());
    expect(landed.searchParams.get('tab')).toBe(file[1]);
    expect(landed.searchParams.get('franchise_id')).toBe(FID);
    expect(landed.searchParams.get('team_id')).toBe(TID);
    expect(landed.searchParams.get('return_url')).toBe(ret);
    await page.waitForSelector('#' + file[1] + '.tab-content.active');
  }
});

test('a week advance refreshes the three views', async ({ page }) => {
  const state = { week: 1 };
  await installApi(page, state);
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view tr.is-user');
  await expect(page.locator('#standings-view tr.is-user')).toContainText('W3');
  await page.evaluate(async (fid) => {
    const res = await fetch('/franchise/complete-week', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
    if (!res.ok) throw new Error('advance failed');
  }, FID);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=standings-view');
  await page.waitForSelector('#standings-view tr.is-user');
  await expect(page.locator('#standings-view tr.is-user')).toContainText('W4');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=leaders-view');
  await page.waitForSelector('#leaders-view .gob-ldb');
  await expect(page.locator('#leaders-view')).toContainText('Beta PTS');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-stats-view');
  await page.waitForSelector('#team-stats-view tr.is-user');
  await expect(page.locator('#team-stats-view tr.is-user')).toContainText('88');
});

test('leaders full list replaces in place and per-game values keep a decimal', async ({ page }) => {
  const state = { week: 1 };
  await installApi(page, state);
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view .gob-tbl tbody tr');
  const leagueIdx = await page.evaluate(() => history.state && history.state.gobIdx);
  await clickStab(page, 'Leaders');
  await page.waitForSelector('#leaders-view .full');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
  await expect(page.locator('#leaders-view .ldb-v').first()).toContainText('20.0');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
  await mouseClick(page, '#leaders-view .full');
  await page.waitForSelector('#leaders-view .gob-full tbody tr');
  expect(page.url()).toContain('leader=PTS');
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
  await expect(page.locator('#leaders-view .gob-full tbody tr')).toHaveCount(30);
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 400; });
  const link = page.locator('#leaders-view .gob-full .gob-team').nth(10);
  await link.scrollIntoViewIfNeeded();
  await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const head = document.querySelector('html.gob-shell .pg-head');
    const header = document.querySelector('#leaders-view .gob-full thead th');
    const a = document.querySelectorAll('#leaders-view .gob-full .gob-team')[10];
    const limit = Math.max(head.getBoundingClientRect().bottom, header.getBoundingClientRect().bottom) + 12;
    if (a.getBoundingClientRect().top < limit) main.scrollTop -= (limit - a.getBoundingClientRect().top);
  });
  const saved = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(saved).toBeGreaterThan(80);
  await mouseClick(page, link);
  await page.waitForURL(/tab=team-view/);
  await page.goBack();
  await page.waitForURL(/leader=PTS/);
  await page.waitForSelector('#leaders-view .gob-full tbody tr');
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, saved, { timeout: 8000 });
});

test('a team with no logo URL and a team whose logo 404s both render a monogram', async ({ page }) => {
  const state = { week: 1 };
  await installApi(page, state);
  await page.route('**/images/teams/no-such/**', (route) => route.fulfill({ status: 404, body: '' }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await page.evaluate(() => {
    const real = window.getTeamAssetPath;
    window.getTeamAssetPath = function (name, key, visual) {
      if (name === 'Club 1') return '';
      if (name === 'Club 2') return '/images/teams/no-such/no-such_logo_square.png';
      return real ? real(name, key, visual) : '';
    };
  });
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view .gob-tbl tbody tr');
  await clickStab(page, 'Team Stats');
  await page.waitForSelector('#team-stats-view tr');
  function teamCell(name) {
    return page.locator('#team-stats-view a.gob-team').filter({
      has: page.locator('span', { hasText: new RegExp('^' + name + '$') }),
    });
  }
  const club1 = teamCell('Club 1');
  const club2 = teamCell('Club 2');
  await expect(club1.locator('.gob-mark')).toHaveText('C');
  await expect(club1.locator('img')).toHaveCount(0);
  await expect(club1.locator('.gob-mark')).toHaveCSS('background-color', 'rgb(17, 34, 51)');
  await expect(club2.locator('.gob-mark')).toHaveText('C');
  await expect(club2.locator('img')).toHaveCount(0);
  await expect(club2.locator('.gob-mark')).toHaveCSS('background-color', 'rgb(68, 85, 102)');
  const broken = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('#team-stats-view img')).filter(function (img) {
      return img.complete && img.naturalWidth === 0;
    }).length;
  });
  expect(broken).toBe(0);
});
