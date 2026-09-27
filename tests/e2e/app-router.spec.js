const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-router';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/app-router');

function rankings(topName, userName) {
  const rows = [];
  for (let i = 0; i < 128; i += 1) {
    const mine = i === 3;
    rows.push({
      natl_rank: i + 1,
      team_id: mine ? TID : ('bbbbbbbbbbbbbbbbbbbbbbb' + (i % 10)),
      team_name: mine ? (userName || 'Lancaster') : (i === 0 ? topName : ('Program ' + (i + 1))),
      conference: mine ? 1 : (i % 16) + 1,
      primary_color: '#c4a35a',
      W: mine ? 12 : 10 - (i % 4),
      L: mine ? 1 : i % 4,
      last_week: mine ? 'W vs Program 2' : 'L vs Program 9',
      last_week_result: mine ? 'W' : 'L',
      next: 'vs Program 4',
    });
  }
  return rows;
}

function payload(week, topName) {
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
    team_record: { wins: 12, losses: 1 },
    rankings: rankings(topName, 'Lancaster'),
  };
}

function etag(week) {
  return 'W/"' + FID + ':1:' + week + ':0:router:1"';
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
  global.__gobRouterState = state;
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
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
      state.body = payload(2, 'Beta State');
      await fulfillJson(route, { ok: true, week: state.week });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      const live = global.__gobRouterState || state;
      const tag = etag(live.week);
      const inm = request.headers()['if-none-match'] || '';
      if (inm === tag) {
        await route.fulfill({ status: 304, headers: { ETag: tag } });
        return;
      }
      await route.fulfill({
        status: 200,
        headers: { ETag: tag, 'Content-Type': 'application/json' },
        body: JSON.stringify(live.body),
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data') || pathname.startsWith('/roster/')) {
      await fulfillJson(route, { team_attributes: { team_chemistry: 10 }, players: [] });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, resetView) {
  await stubAuth(page);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
  if (resetView) {
    await page.evaluate(() => sessionStorage.removeItem('gob-view-rankings-show-all'));
    await page.reload();
    await page.waitForSelector('#play-now.advance');
  }
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

function stab(page, label) {
  return page.locator('#gob-subtabs .stab').filter({ hasText: new RegExp('^' + label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') });
}

async function docStamp(page) {
  return page.evaluate(() => {
    if (!window.__docStamp) window.__docStamp = String(Math.random());
    return {
      stamp: window.__docStamp,
      nav: performance.getEntriesByType('navigation').length,
    };
  });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('rankings opens in place, stays cached, and restores history', async ({ page }) => {
  const state = { week: 1, body: payload(1, 'Alpha State') };
  const notes = [];
  await installApi(page, state);
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page, true);
    const before = await docStamp(page);
    await mouseClick(page, '[data-gob-section="league"]');
    await expect(page.locator('#standings-view.tab-content.active')).toBeVisible();
    const leagueIdx = await page.evaluate(() => history.state && history.state.gobIdx);

    let ccHits = [];
    const onResponse = (res) => {
      if (res.url().includes('/franchise/command-center/data')) {
        ccHits.push(res.status());
      }
    };
    page.on('response', onResponse);
    const t0 = Date.now();
    await mouseClick(page, stab(page, 'Rankings'));
    await page.waitForSelector('#rankings-view.tab-content.active #rankings-table tbody tr');
    const firstMs = Date.now() - t0;
    const after = await docStamp(page);
    expect(after.stamp).toBe(before.stamp);
    expect(after.nav).toBe(before.nav);
    expect(page.url()).toContain('tab=rankings-view');
    expect(page.url()).not.toContain('rankings.html');
    expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(leagueIdx);
    expect(ccHits, 'first open downloads a new body').toEqual([]);
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(25);
    await expect(page.locator('#rankings-table tbody tr.is-user')).toHaveCount(1);
    await expect(page.locator('#rankings-table tbody tr.is-user a')).toHaveText('Lancaster');

    ccHits = [];
    await mouseClick(page, stab(page, 'Standings'));
    await expect(page.locator('#standings-view.tab-content.active')).toBeVisible();
    expect(ccHits, 'standings refetches command center').toEqual([]);
    expect(await docStamp(page)).toEqual(after);

    const secondBody = page.waitForResponse((res) => res.url().includes('/franchise/command-center/data'), { timeout: 4000 }).catch(() => null);
    const t1 = Date.now();
    await mouseClick(page, stab(page, 'Rankings'));
    await page.waitForSelector('#rankings-view.tab-content.active #rankings-table tbody tr');
    const secondMs = Date.now() - t1;
    const secondRes = await secondBody;
    expect(secondMs).toBeLessThan(1000);
    if (secondRes) expect(secondRes.status()).toBe(304);
    const secondHits = secondRes ? [secondRes.status()] : [];
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(25);

    await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      if (main) main.scrollTop = 0;
    });
    await mouseClick(page, '#rankings-toggle-all');
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(128);
    await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      main.scrollTop = 480;
    });
    const scrolled = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
    expect(scrolled).toBeGreaterThan(200);
    const link = page.locator('#rankings-table tbody tr').nth(10).locator('a');
    await link.scrollIntoViewIfNeeded();
    await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      const head = document.querySelector('html.gob-shell .pg-head');
      const header = document.querySelector('#rankings-table thead th');
      const a = document.querySelectorAll('#rankings-table tbody tr')[10].querySelector('a');
      const limit = Math.max(head.getBoundingClientRect().bottom, header.getBoundingClientRect().bottom) + 8;
      const top = a.getBoundingClientRect().top;
      if (top < limit) main.scrollTop -= (limit - top);
    });
    const scrollBeforeLeave = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
    await mouseClick(page, link);
    await page.waitForURL(/tab=roster-view/);
    await page.goBack();
    await page.waitForURL(/tab=rankings-view/);
    await expect(page.locator('#rankings-view.tab-content.active')).toBeVisible();
    await page.waitForFunction((saved) => {
      const main = document.querySelector('html.gob-shell .main');
      return main && Math.abs(main.scrollTop - saved) <= 2;
    }, scrollBeforeLeave, { timeout: 8000 });
    const backIdx = await page.evaluate(() => history.state && history.state.gobIdx);
    expect(backIdx).toBe(leagueIdx);
    await page.goBack();
    await expect(page.locator('#home-tab.tab-content.active')).toBeVisible();
    await page.goForward();
    await page.waitForURL(/tab=rankings-view/);
    await expect(page.locator('#rankings-view.tab-content.active')).toBeVisible();

    await assertOneVerticalScroll(page);
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

    notes.push(size[2] + ' first ' + firstMs + 'ms second ' + secondMs + 'ms revalidate ' + JSON.stringify(secondHits));
    page.off('response', onResponse);
  }

  await page.evaluate(async (fid) => {
    const res = await fetch('/franchise/complete-week', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
    if (!res.ok) throw new Error('advance failed');
  }, FID);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=rankings-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#rankings-table tbody tr').first()).toContainText('Beta State');

  fs.writeFileSync(path.join(OUT, 'timings.txt'), notes.join('\n') + '\n');
});

test('first open shows a skeleton and a failed module shows retry', async ({ page }) => {
  const state = { week: 1, body: payload(1, 'Alpha State') };
  await page.setViewportSize({ width: 1280, height: 720 });
  let releaseModule;
  const gate = new Promise((resolve) => { releaseModule = resolve; });
  await installApi(page, state);
  await page.route('**/js/shared/views/rankingsView.js', async (route) => {
    if (route.request().url().indexOf('retry=') !== -1) {
      await route.fallback();
      return;
    }
    await gate;
    await route.fallback();
  });
  await openFcc(page);
  await mouseClick(page, '[data-gob-section="league"]');
  await mouseClick(page, stab(page, 'Rankings'));
  await expect(page.locator('#rankings-view .gob-view-skel')).toBeVisible();
  await expect(page.locator('#rankings-view .spinner, #rankings-view [class*="spinner"]')).toHaveCount(0);
  releaseModule();
  await page.waitForSelector('#rankings-table tbody tr');
});

test('a failed rankings module shows a retry card', async ({ page }) => {
  const state = { week: 1, body: payload(1, 'Alpha State') };
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, state);
  await page.route('**/js/shared/views/rankingsView.js*', async (route) => {
    if (route.request().url().indexOf('retry=') !== -1) {
      await route.fallback();
      return;
    }
    await route.fulfill({ status: 500, body: 'nope' });
  });
  await openFcc(page);
  await mouseClick(page, '[data-gob-section="league"]');
  await mouseClick(page, stab(page, 'Rankings'));
  await expect(page.locator('#rankings-view .gob-view-error')).toBeVisible();
  await expect(page.locator('#rankings-view .gob-view-retry')).toBeVisible();
  await expect(page.locator('#rankings-table')).toHaveCount(0);
  await mouseClick(page, '#rankings-view .gob-view-retry');
  await page.waitForSelector('#rankings-table tbody tr');
});

test('rankings.html keeps franchise, team, and return params', async ({ page }) => {
  const state = { week: 1, body: payload(1, 'Alpha State') };
  await installApi(page, state);
  await stubAuth(page);
  const ret = '/schedule.html?franchise_id=' + FID + '&team_id=' + TID;
  await page.goto('/rankings.html?franchise_id=' + FID + '&team_id=' + TID + '&return_url=' + encodeURIComponent(ret) + '&return_tab=rankings-view');
  await page.waitForURL(/franchise-command-center\.html/);
  const landed = new URL(page.url());
  expect(landed.searchParams.get('tab')).toBe('rankings-view');
  expect(landed.searchParams.get('franchise_id')).toBe(FID);
  expect(landed.searchParams.get('team_id')).toBe(TID);
  expect(landed.searchParams.get('return_url')).toBe(ret);
  expect(landed.searchParams.get('return_tab')).toBe('rankings-view');
  await page.waitForSelector('#rankings-table tbody tr');

  const backTo = '/rankings.html?franchise_id=' + FID + '&team_id=' + TID + '&return_tab=rankings-view';
  await page.goto('/team-roster-view.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&team_name=Lancaster&return_url=' + encodeURIComponent(backTo));
  await page.waitForSelector('#back-button');
  await mouseClick(page, '#back-button');
  await page.waitForURL(/tab=rankings-view/);
  const returned = new URL(page.url());
  expect(returned.searchParams.get('tab')).toBe('rankings-view');
  expect(returned.searchParams.get('franchise_id')).toBe(FID);
  expect(returned.searchParams.get('team_id')).toBe(TID);
  await expect(page.locator('#rankings-view.tab-content.active')).toBeVisible();
});
