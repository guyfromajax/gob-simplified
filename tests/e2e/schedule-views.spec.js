const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-sched';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 8,
    rank: 4,
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

function side(id, name, rank, color) {
  return {
    team_id: id,
    name: name,
    primary_color: color,
    natl_rank: rank,
    wins: 3,
    losses: 1,
  };
}

function catalog() {
  const rows = [];
  for (let week = 1; week <= 34; week++) {
    rows.push({
      week: week,
      label: week >= 27 ? 'Week ' + week + ': Tourney' : 'Week ' + week,
      enabled: week === 1 || week === 8 || week === 12,
    });
  }
  return rows;
}

function league(week) {
  const shown = week || 8;
  const games = shown === 8 ? [
    {
      away: side(OPP, 'York', 80, '#778899'),
      home: side(TID, 'Lancaster', 4, '#112233'),
      away_score: 60,
      home_score: 70,
      status: 'complete',
      game_id: 'g-box',
      is_user: true,
      tournament_context: null,
    },
    {
      away: side('cccccccccccccccccccccccc', 'Four-Corners', 21, '#445566'),
      home: side(OPP, 'York', 80, '#778899'),
      away_score: null,
      home_score: null,
      status: 'scheduled',
      game_id: null,
      is_user: false,
      tournament_context: null,
    },
  ] : [{
    away: side(OPP, 'York', 80, '#778899'),
    home: side('cccccccccccccccccccccccc', 'Four-Corners', 21, '#445566'),
    away_score: null,
    home_score: null,
    status: 'scheduled',
    game_id: null,
    is_user: false,
    tournament_context: shown >= 27 ? 'Conference 1' : null,
  }];
  const round = shown === 27 ? 'Week 27: Conference Tourney - R1' : 'Week ' + shown;
  return {
    week: shown,
    label: round,
    current_week: 8,
    user_team_id: TID,
    weeks: catalog(),
    games: games,
  };
}

function opponent(week, site) {
  return {
    week: week,
    site: site,
    opponent_id: OPP,
    opponent_name: 'York',
    opponent_primary_color: '#778899',
    opponent_natl_rank: 80,
    opponent_wins: 3,
    opponent_losses: 1,
  };
}

function teamDetail() {
  return {
    team_id: TID,
    name: 'Lancaster',
    next_game: opponent(8, 'home'),
    results: [Object.assign({ team_score: 70, opp_score: 60, result: 'W', game_id: 'g-team' }, opponent(1, 'away'))],
    upcoming: [opponent(12, 'away')],
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
    let week = null;
    try {
      const url = new URL(request.url());
      pathname = url.pathname;
      week = url.searchParams.get('week');
    } catch (err) {
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
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    const scheduleApi = pathname.startsWith('/franchise/schedule/week')
      || pathname.startsWith('/franchise/team-detail');
    if (scheduleApi) {
      hits += 1;
      if (mode === 'error' && hits === 1) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      if (mode === 'delay' && hits === 1) await gate;
      if (pathname.startsWith('/franchise/schedule/week')) {
        await fulfillJson(route, league(week ? Number(week) : 8));
        return;
      }
      await fulfillJson(route, teamDetail());
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

async function openSub(page, section, tab) {
  await page.locator('[data-gob-section="' + section + '"]').evaluate((el) => el.click());
  await page.mouse.move(980, 420);
  await page.locator('#gob-subtabs [data-tab="' + tab + '"]').evaluate((el) => el.click());
}

async function mainOverflow(page) {
  return page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    return main.scrollWidth - main.clientWidth;
  });
}

test('both schedule tabs open from the row', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page);
  await openSub(page, 'team', 'team-schedule-view');
  await expect(page.locator('#team-schedule-view.tab-content.active')).toBeVisible();
  await expect(page.locator('#team-schedule-view .gob-schcol')).toHaveCount(4);
  await expect(page.locator('#team-schedule-view tr.is-next')).toContainText('York');
  await expect(page.locator('#team-schedule-view tr.is-next td.res')).toHaveText('');
  await expect(page.locator('#team-schedule-view tr[data-week="1"] .gob-wl')).toHaveText('W');
  await expect(page.locator('#team-schedule-view tr[data-week="1"]')).toContainText('70-60');
  await expect(page.locator('#team-schedule-view tr[data-week="1"] a.gob-res')).toHaveAttribute('href', /box-score\.html\?game_id=g-team/);
  await expect(page.locator('#team-schedule-view tr[data-week="1"] a.gob-res')).toHaveText('W 70-60');
  await expect(page.locator('#team-schedule-view tr[data-week="2"]')).toContainText('Open');
  await expect(page.locator('#team-schedule-view tr.is-eos').first()).toContainText('Conference Tournaments');
  expect(page.url()).toContain('tab=team-schedule-view');

  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=schedule-tab');
  await expect(page.locator('#team-schedule-view.tab-content.active')).toBeVisible();
  expect(page.url()).toContain('tab=team-schedule-view');

  await openSub(page, 'league', 'league-schedule-view');
  await expect(page.locator('#league-schedule-view.tab-content.active')).toBeVisible();
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 8');
  await expect(page.locator('#league-schedule-view .gob-game.me')).toContainText('70');
  await expect(page.locator('#league-schedule-view .gob-game.me .gob-box')).toHaveAttribute('href', /game_id=g-box/);
  const open = page.locator('#league-schedule-view .gob-game').nth(1);
  await expect(open).toContainText('Scheduled');
  await expect(open.locator('.gob-box')).toHaveCount(0);
});

test('week stepper defaults to the current week and stops at the ends', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=league-schedule-view');
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 8');
  expect(page.url()).toContain('week=8');
  await expect(page.locator('.gob-wk button[data-week-step="-1"]')).toBeEnabled();
  await expect(page.locator('.gob-wk button[data-week-step="1"]')).toBeEnabled();
  await page.locator('.gob-wk button[data-week-step="1"]').click();
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 12');
  expect(page.url()).toContain('week=12');
  await expect(page.locator('.gob-wk button[data-week-step="1"]')).toBeDisabled();
  await page.locator('.gob-wk button[data-week-step="-1"]').click();
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 8');
  await page.locator('.gob-wk button[data-week-step="-1"]').click();
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 1');
  await expect(page.locator('.gob-wk button[data-week-step="-1"]')).toBeDisabled();
});

test('opponent push and back restore the team schedule scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-schedule-view');
  await expect(page.locator('#team-schedule-view tr.is-next')).toContainText('York');
  const scrolled = await page.evaluate(() => {
    const panel = document.getElementById('team-schedule-view');
    const main = document.querySelector('html.gob-shell .main');
    panel.style.minHeight = '2400px';
    main.scrollTop = 640;
    return main.scrollTop;
  });
  expect(scrolled).toBeGreaterThan(500);
  await page.locator('#team-schedule-view tr.is-next a.gob-team').evaluate((el) => el.click());
  await page.waitForURL(/tab=team-view/);
  expect(page.url()).toContain('origin=team');
  expect(page.url()).toContain('return_tab=team-schedule-view');
  expect(page.url()).toContain('view_team_id=' + OPP);
  await page.goBack();
  await expect(page.locator('#team-schedule-view.tab-content.active')).toBeVisible();
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, scrolled);
});

test('schedule.html keeps the week and opens the league view', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installApi(page, 'ok');
  await stubAuth(page);
  await page.goto('/schedule.html?franchise_id=' + FID + '&team_id=' + TID + '&week=12&return_url=%2Foffice.html');
  await expect(page.locator('#league-schedule-view.tab-content.active')).toBeVisible();
  expect(page.url()).toContain('tab=league-schedule-view');
  expect(page.url()).toContain('week=12');
  expect(page.url()).toContain('franchise_id=' + FID);
  expect(page.url()).not.toContain('schedule.html');
  await expect(page.locator('.gob-wk-label')).toHaveText('Week 12');
});

test('main does not scroll sideways at 1280 or 1920', async ({ page }) => {
  await installApi(page, 'ok');
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-schedule-view');
    await expect(page.locator('#team-schedule-view tr.is-next')).toBeVisible();
    expect(await mainOverflow(page), 'team ' + size[0]).toBeLessThanOrEqual(1);
    await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=league-schedule-view&week=8');
    await expect(page.locator('#league-schedule-view .gob-game.me')).toBeVisible();
    expect(await mainOverflow(page), 'league ' + size[0]).toBeLessThanOrEqual(1);
  }
});

test('skeleton then rows, and error then retry', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const delayed = await installApi(page, 'delay');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=league-schedule-view');
  await expect(page.locator('#league-schedule-view .gob-view-skel')).toBeVisible();
  delayed.release();
  await expect(page.locator('#league-schedule-view .gob-game.me')).toBeVisible();

  await installApi(page, 'error');
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-schedule-view');
  await expect(page.locator('#team-schedule-view .gob-view-error')).toBeVisible();
  await page.locator('#team-schedule-view .gob-view-retry').click();
  await expect(page.locator('#team-schedule-view tr.is-next')).toContainText('York');
});
