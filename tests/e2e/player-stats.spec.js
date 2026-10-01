const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-pstats';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 8,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 8, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
  };
}

function counting(gp, totals) {
  const keys = ['MIN', 'PTS', 'FGM', 'FGA', '3PTM', '3PTA', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 'AST', 'TO', 'STL', 'BLK', 'F'];
  const per = { GP: gp };
  const sum = { GP: gp };
  keys.forEach(function (key) {
    const total = totals[key] == null ? 0 : totals[key];
    sum[key] = total;
    per[key] = gp > 0 ? total / gp : null;
  });
  return { per_game: per, totals: sum };
}

function players() {
  const ada = counting(2, {
    MIN: 40, PTS: 22, FGM: 0, FGA: 0, FTM: 0, FTA: 4, OREB: 2, DREB: 6, REB: 8, AST: 3, TO: 1, STL: 2, BLK: 0, F: 3,
  });
  ada.rates = { fg_pct: null, tp_pct: null, ft_pct: 0, def_pct: null };
  const bo = counting(2, {
    MIN: 20, PTS: 10, FGM: 4, FGA: 8, FTM: 2, FTA: 2, OREB: 0, DREB: 2, REB: 2, AST: 1, TO: 2, STL: 0, BLK: 1, F: 2,
  });
  bo.rates = { fg_pct: 50, tp_pct: null, ft_pct: 100, def_pct: 25 };
  const cy = counting(0, {});
  cy.rates = { fg_pct: null, tp_pct: null, ft_pct: null, def_pct: null };
  return {
    team_id: TID,
    players: [
      Object.assign({ player_id: 'ada', name: 'Ada Ace', position: 'SG', year: 'JR', jersey: 23 }, ada),
      Object.assign({ player_id: 'bo', name: 'Bo Low', position: 'PF', year: 'SO', jersey: 11 }, bo),
      Object.assign({ player_id: 'cy', name: 'Cy Zero', position: 'C', year: 'FR', jersey: 0 }, cy),
    ],
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, mode) {
  let hits = 0;
  let release = null;
  const gate = new Promise(function (resolve) { release = resolve; });
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
      || pathname.startsWith('/recruit/')
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
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, {
        team: 'Lancaster',
        is_user_team: true,
        players: [{
          _id: 'ada',
          name: 'Ada Ace',
          year: 'JR',
          position: 'SG',
          height: 76,
          weight: 210,
          rt: 80,
          starter: true,
          lineup_order: 0,
          attributes: { SC: 60, SH: 60, ID: 60, OD: 60, PS: 60, BH: 60, RB: 60, AG: 60, ST: 60, ND: 60, IQ: 60, FT: 60 },
        }],
        training_squad: [],
        practice_squad_recruits: [],
      });
      return;
    }
    if (pathname.startsWith('/franchise/player-stats')) {
      hits += 1;
      if (mode === 'error' && hits === 1) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      if (mode === 'delay' && hits === 1) await gate;
      await fulfillJson(route, players());
      return;
    }
    await fulfillJson(route, {});
  });
  return { release: release };
}

async function openFcc(page, search) {
  await stubAuth(page);
  const qs = search || ('?franchise_id=' + FID + '&team_id=' + TID);
  await page.goto('/franchise-command-center.html' + qs);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

function cell(page, name, key) {
  return page.locator('#player-stats-view tbody tr', { hasText: name }).first().locator('td[data-k="' + key + '"]');
}

async function mainOverflow(page) {
  return page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    return main.scrollWidth - main.clientWidth;
  });
}

// Player rows are 44px whatever the avatar holds (`a.gob-team.gob-player { vertical-align: middle }`;
// the full guard is player-row-44.spec.js). Still measure only when every avatar has
// settled: loaded, or already swapped for its monogram.
async function avatarsSettled(page, view) {
  await page.waitForFunction((id) => {
    const imgs = Array.from(document.querySelectorAll('#' + id + ' .av img'));
    return imgs.every((img) => img.complete && img.naturalWidth > 0);
  }, view);
}

async function playerRowHeights(page) {
  await page.waitForSelector('#roster-view a.gob-player');
  await avatarsSettled(page, 'roster-view');
  const rosterH = await page.locator('#roster-view a.gob-player').first().evaluate((el) => {
    return el.closest('tr').getBoundingClientRect().height;
  });
  await page.mouse.move(980, 420);
  await page.locator('#gob-subtabs [data-tab="player-stats-view"]').evaluate((el) => el.click());
  await page.waitForSelector('#player-stats-view a.gob-player');
  await avatarsSettled(page, 'player-stats-view');
  const stats = await page.locator('#player-stats-view a.gob-player').first().evaluate((el) => {
    const name = el.querySelector('.gob-id > span:first-child');
    return {
      height: el.closest('tr').getBoundingClientRect().height,
      deco: getComputedStyle(name).textDecorationLine,
    };
  });
  return { rosterH: rosterH, stats: stats };
}

test('player cell matches the roster row', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  const got = await playerRowHeights(page);
  expect(Math.round(got.stats.height)).toBeLessThanOrEqual(Math.round(got.rosterH));
  expect(got.stats.deco).toBe('none');
});

// The same comparison with the headshot answering late, which is what a busy machine does.
test('player cell matches the roster row when headshots answer late', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  // Registered after installApi, so it answers the headshot requests.
  await page.route(/\/images\/players\//, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.fulfill({ status: 404, body: '' });
  });
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  const got = await playerRowHeights(page);
  expect(Math.round(got.stats.height)).toBeLessThanOrEqual(Math.round(got.rosterH));
  expect(Math.round(got.rosterH)).toBe(44);
  expect(Math.round(got.stats.height)).toBe(44);
});

// With headshots that load, both rows carry an image and are still 44px.
test('player cell matches the roster row when headshots load', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  const png = require('fs').readFileSync(require('path').join(__dirname, '../../FrontEnd/static/images/geekedout_logo.png'));
  await page.route(/\/images\/players\//, (route) => route.fulfill({ status: 200, contentType: 'image/png', body: png }));
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  const got = await playerRowHeights(page);
  expect(Math.round(got.stats.height)).toBeLessThanOrEqual(Math.round(got.rosterH));
  expect(Math.round(got.rosterH)).toBe(44);
  expect(Math.round(got.stats.height)).toBe(44);
});

test('team sub-tab opens player stats and the old id maps', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const api = await installApi(page, 'ok');
  await openFcc(page);
  await page.locator('[data-gob-section="team"]').click();
  await page.mouse.move(980, 420);
  await page.locator('#gob-subtabs [data-tab="player-stats-view"]').evaluate((el) => el.click());
  await expect(page.locator('#player-stats-view.tab-content.active')).toBeVisible();
  await expect(page.locator('#player-stats-view tbody tr')).toHaveCount(3);
  await expect(page.locator('.pg-tools button.on')).toHaveText('Per game');
  expect(page.url()).toContain('tab=player-stats-view');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-tab');
  await expect(page.locator('#player-stats-view.tab-content.active')).toBeVisible();
  expect(page.url()).toContain('tab=player-stats-view');
  void api;
});

test('per game and totals, sort, and null versus zero', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-view');
  await expect(page.locator('#player-stats-view tbody tr').first()).toContainText('Ada Ace');
  await expect(cell(page, 'Ada Ace', 'PTS')).toHaveText('11.0');
  await expect(cell(page, 'Ada Ace', 'fg_pct')).toHaveText('—');
  await expect(cell(page, 'Ada Ace', 'ft_pct')).toHaveText('0.0');
  await expect(cell(page, 'Cy Zero', 'PTS')).toHaveText('—');
  await expect(cell(page, 'Cy Zero', 'GP')).toHaveText('0');
  await expect(cell(page, 'Bo Low', 'fg_pct')).toHaveText('50.0');
  await page.locator('#player-stats-view th[data-sort="PTS"]').first().click();
  await expect(page.locator('#player-stats-view tbody tr').first()).toContainText('Bo Low');
  await expect(page.locator('#player-stats-view tbody tr').nth(1)).toContainText('Ada Ace');
  await page.locator('.pg-tools button', { hasText: 'Totals' }).click();
  await expect(cell(page, 'Ada Ace', 'PTS')).toHaveText('22');
  await expect(cell(page, 'Ada Ace', 'fg_pct')).toHaveText('—');
  await expect(cell(page, 'Ada Ace', 'ft_pct')).toHaveText('0.0');
  await expect(cell(page, 'Bo Low', 'FGA')).toHaveText('8');
});

test('row click pushes player-view with the pager and back restores scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-view');
  await expect(page.locator('#player-stats-view tbody tr').first()).toContainText('Ada Ace');
  const scrolled = await page.evaluate(() => {
    const panel = document.getElementById('player-stats-view');
    const main = document.querySelector('html.gob-shell .main');
    panel.style.minHeight = '2400px';
    main.scrollTop = 640;
    return main.scrollTop;
  });
  expect(scrolled).toBeGreaterThan(500);
  await cell(page, 'Ada Ace', 'PTS').evaluate((el) => el.click());
  await page.waitForURL(/tab=player-view/);
  expect(page.url()).toContain('pager=player-stats');
  expect(page.url()).toContain('origin=team');
  expect(page.url()).toContain('return_tab=player-stats-view');
  const order = await page.evaluate(() => JSON.parse(sessionStorage.getItem('gob-view-player-stats-order') || '[]'));
  expect(order[0]).toBe('ada');
  await page.goBack();
  await expect(page.locator('#player-stats-view.tab-content.active')).toBeVisible();
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, scrolled);
});

test('main does not scroll sideways at 1280 or 1920', async ({ page }) => {
  await installApi(page, 'ok');
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-view');
    await expect(page.locator('#player-stats-view tbody tr')).toHaveCount(3);
    const overflow = await mainOverflow(page);
    expect(overflow, 'main overflow ' + size[0]).toBeLessThanOrEqual(1);
  }
});

test('skeleton then rows, and error then retry', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const delayed = await installApi(page, 'delay');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-view');
  await expect(page.locator('#player-stats-view .gob-view-skel')).toBeVisible();
  delayed.release();
  await expect(page.locator('#player-stats-view tbody tr')).toHaveCount(3);

  await installApi(page, 'error');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-stats-view');
  await expect(page.locator('#player-stats-view .gob-view-error')).toBeVisible();
  await page.locator('#player-stats-view .gob-view-retry').click();
  await expect(page.locator('#player-stats-view tbody tr')).toHaveCount(3);
});
