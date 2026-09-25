const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

// Playwright's default Chromium switch disables the back-forward cache, which
// is the mechanism these history returns use. Drop that switch for this file.
test.use({
  launchOptions: {
    ignoreDefaultArgs: ['--disable-back-forward-cache'],
  },
});

const FID = 'f-e2e-nav3';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const GAME = 'g-e2e-nav3';
const PLAYERS = [
  ['111111111111111111111101', 'Ada Player', 'PG'],
  ['111111111111111111111102', 'Bea Player', 'SG'],
  ['111111111111111111111103', 'Cy Player', 'SF'],
  ['111111111111111111111104', 'Dee Player', 'PF'],
  ['111111111111111111111105', 'Eli Player', 'C'],
];

function playerRow(id, name, pos) {
  return {
    _id: id,
    player_id: id,
    name,
    first_name: name.split(' ')[0],
    last_name: 'Player',
    jersey: 11,
    position: pos,
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    position_ratings: { PG: 70, SG: 60, SF: 50, PF: 40, C: 30 },
    stats: { game: {} },
  };
}

const ROSTER = PLAYERS.map((row) => playerRow(row[0], row[1], row[2]));

function commandCenter(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 1,
    season: 1,
    current_season: 1,
    training_completed: false,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 1 },
    user_conference: 1,
    sister_conference: 2,
    user_region: 'A',
  }, overrides || {});
}

function standingsBody() {
  return {
    user_conference: 1,
    sister_conference: 2,
    standings: [
      { team_id: TID, name: 'Lancaster', display_name: 'Lancaster', conference: 1, region: 'A', W: 3, L: 1, PF: 80, PA: 70, natl_rank: 4 },
      { team_id: OPP, name: 'Four-Corners', display_name: 'Four-Corners', conference: 2, region: 'A', W: 2, L: 2, PF: 70, PA: 72, natl_rank: 12 },
    ],
  };
}

function quarterSim(body) {
  if (body && body.full_sim) {
    return {
      is_final: true,
      game_id: GAME,
      quarter: 4,
      week: 1,
      turns: [],
      home_team: { name: 'Lancaster', score: 70 },
      away_team: { name: 'Four-Corners', score: 60 },
      home_team_id: TID,
      away_team_id: OPP,
      score: { Lancaster: 70, 'Four-Corners': 60 },
      final_score: { Lancaster: 70, 'Four-Corners': 60 },
      teams: {},
      box_score: { home: [], away: [] },
    };
  }
  return {
    turns: [],
    quarter: (body && body.quarter) || 1,
    is_final: false,
    game_id: GAME,
    week: 1,
    home_score: 0,
    away_score: 0,
    home_team: { name: 'Lancaster', score: 0 },
    away_team: { name: 'Four-Corners', score: 0 },
    teams: {},
    players: [],
    clock: '8:00',
    time_remaining: 480,
    home_team_fouls: 0,
    away_team_fouls: 0,
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, ccData, options) {
  options = options || {};
  const seen = [];
  page.__apiSeen = seen;
  await page.route('**/*', async (route) => {
    const request = route.request();
    let path = '';
    let method = request.method();
    try {
      path = new URL(request.url()).pathname;
    } catch (e) {
      await route.continue();
      return;
    }
    const api = path.startsWith('/api/')
      || path.startsWith('/franchise/')
      || path.startsWith('/roster/')
      || path.startsWith('/player/')
      || path.startsWith('/recruit/')
      || path === '/teams'
      || path === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (path === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (path === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (path === '/franchise/list') {
      await fulfillJson(route, {
        franchises: [{ franchise_id: FID, user_team_id: 'Lancaster', home_slot: 1, team_name: 'Lancaster' }],
        max: 2,
      });
      return;
    }
    if (path === '/teams') {
      await fulfillJson(route, [
        { name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID, primary_color: '#27408E', secondary_color: '#ffffff' },
        { name: 'Four-Corners', display_name: 'Four-Corners', object_id: OPP, _id: OPP, primary_color: '#c0392b', secondary_color: '#ffffff' },
      ]);
      return;
    }
    if (path.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, ccData);
      return;
    }
    if (path.startsWith('/franchise/standings')) {
      await fulfillJson(route, standingsBody());
      return;
    }
    if (path.startsWith('/franchise/team-data')) {
      await fulfillJson(route, { team_attributes: { team_chemistry: 15 }, players: ROSTER });
      return;
    }
    if (path.startsWith('/franchise/training-points')) {
      await fulfillJson(route, {
        training_points: 0,
        week: 1,
        season: 1,
        is_first_training: false,
        custom_focus_roster: [],
        user_team_name: 'Lancaster',
      });
      return;
    }
    if (path === '/franchise/run-training/user' && method === 'POST') {
      await fulfillJson(route, {
        status: 'already_completed',
        redirect: '/training-report.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&week=1',
      });
      return;
    }
    if (path.startsWith('/franchise/training-report')) {
      await fulfillJson(route, {
        team_name: 'Lancaster',
        week: 1,
        players: [],
        team_attributes: {},
        playbook_summary: {},
      });
      return;
    }
    if (path === '/franchise/play-next-game' && method === 'POST') {
      await fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four-Corners',
        week: 1,
        home_id: TID,
        away_id: OPP,
        home_display: 'Lancaster',
        away_display: 'Four-Corners',
      });
      return;
    }
    if (path.startsWith('/roster/')) {
      await fulfillJson(route, { players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
      return;
    }
    if (path === '/api/init-game' && method === 'POST') {
      await fulfillJson(route, { game_id: GAME });
      return;
    }
    if (path === '/api/autoset-lineup' && method === 'POST') {
      await fulfillJson(route, {
        lineup: { PG: PLAYERS[0][0], SG: PLAYERS[1][0], SF: PLAYERS[2][0], PF: PLAYERS[3][0], C: PLAYERS[4][0] },
      });
      return;
    }
    if (path === '/api/playbooks') {
      await fulfillJson(route, { motion: [], set_plays: [], man_defense_rows: [], zone_defense_rows: [] });
      return;
    }
    if (path.includes('/resume-state')) {
      await fulfillJson(route, options.resumeState || { status: 'quarter_break' });
      return;
    }
    if (path === '/api/simulate-quarter' && method === 'POST') {
      let body = {};
      try { body = request.postDataJSON() || {}; } catch (e) { body = {}; }
      seen.push('simulate-quarter full_sim=' + !!body.full_sim);
      if (options.quarterAlreadyPlayed) {
        await fulfillJson(route, {
          error: 'QUARTER_ALREADY_PLAYED',
          saved_quarter: 2,
          requested_quarter: body.quarter || 1,
        }, 409);
        return;
      }
      await fulfillJson(route, quarterSim(body));
      return;
    }
    if (path === '/api/simulate-turn' && method === 'POST') {
      seen.push('simulate-turn');
      await fulfillJson(route, {
        turn: null,
        quarter_complete: true,
        is_final: false,
        home_score: 10,
        away_score: 8,
        time_remaining: 0,
        quarter: 2,
        clock: '0:00',
      });
      return;
    }
    if (path.startsWith('/franchise/complete-week/')) {
      await fulfillJson(route, { ok: true });
      return;
    }
    if (path.startsWith('/franchise/championship-moments/')) {
      await fulfillJson(route, { is_championship: false });
      return;
    }
    if (path.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, { week: ccData.week || 1, team_id: TID, team: 'Lancaster', team_region: 'A' });
      return;
    }
    if (path.startsWith('/player/')) {
      await fulfillJson(route, {
        _id: PLAYERS[0][0],
        name: 'Ada Player',
        first_name: 'Ada',
        last_name: 'Player',
        jersey: 11,
        position: 'PG',
        team: 'Lancaster',
        attributes: { SC: 50 },
        position_ratings: { PG: 70 },
        stats: {},
      });
      return;
    }
    if (path.startsWith('/api/game/') && method === 'GET') {
      await fulfillJson(route, {
        game_id: GAME,
        status: 'final',
        is_final: true,
        players: [],
        score: { Lancaster: 70, 'Four-Corners': 60 },
        home_team: 'Lancaster',
        away_team: 'Four-Corners',
        week: 1,
      });
      return;
    }
    if (path === '/api/community/around-the-league') {
      await fulfillJson(route, { slots: [] });
      return;
    }
    await fulfillJson(route, method === 'GET' ? {} : { ok: true });
  });
}

async function openLockerRoom(page) {
  await page.goto('/mode-select.html');
  await page.locator('[data-action="enter-franchise"]').first().click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page.locator('#play-now')).toBeEnabled({ timeout: 20000 });
}

async function backToModeSelect(page) {
  await expect(page.locator('#play-now')).toBeEnabled({ timeout: 20000 });
  await page.goBack({ waitUntil: 'commit' });
  await expect(page).toHaveURL(/mode-select\.html/, { timeout: 15000 });
}

test.beforeEach(async ({ page }) => {
  await stubAuth(page);
  page.on('dialog', (dialog) => dialog.accept());
});

test('training submit lands on the report, then one Back reaches mode-select', async ({ page }) => {
  await installApi(page, commandCenter({ training_completed: false, week: 1 }));
  await openLockerRoom(page);
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/training\.html/, { timeout: 20000 });
  await page.waitForFunction(() => {
    const el = document.getElementById('points-remaining');
    return el && String(el.textContent || '').replace(/\s/g, '').includes('0');
  }, null, { timeout: 15000 });
  await page.locator('input[name="coaching-focus"][value="authoritarian-discipline"]').check({ force: true });
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 10000 });
  await page.locator('#submit-btn').click();
  await expect(page).toHaveURL(/\/training-report\.html/, { timeout: 20000 });
  expect(new URL(page.url()).pathname).toBe('/training-report.html');
  await page.locator('#locker-room-btn').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await backToModeSelect(page);
});

async function playToEndOfGame(page) {
  test.setTimeout(120000);
  await installApi(page, commandCenter({ training_completed: true, week: 1 }));
  await openLockerRoom(page);
  await expect(page.locator('#play-now')).toHaveText('Play Next Game');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/game_id=/, { timeout: 20000 });
  await page.locator('#autoset-lineup').click();
  await expect(page.locator('#play-now')).not.toHaveClass(/disabled/, { timeout: 15000 });
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/court\.html/, { timeout: 20000 });
  const tipOff = page.getByRole('button', { name: /Submit & Tip Off|Submit Defense Matchups/ });
  try {
    await tipOff.waitFor({ state: 'visible', timeout: 15000 });
    await tipOff.click();
  } catch (e) { /* matchups are skipped when the gate is off */ }
  const logs = [];
  page.on('console', (msg) => logs.push(msg.type() + ': ' + msg.text()));
  page.on('pageerror', (err) => logs.push('pageerror: ' + err.message));
  const quarterButton = page.getByRole('button', { name: 'Go To Locker Room' }).last();
  try {
    await expect(quarterButton).toBeVisible({ timeout: 20000 });
  } catch (err) {
    throw new Error(
      'quarter popup missing\napi=' + JSON.stringify(page.__apiSeen || [])
      + '\nlogs=\n' + logs.slice(-25).join('\n')
    );
  }
  await quarterButton.click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/game_id=/);
  const peek = page.locator('a.player-name-link').first();
  await expect(peek).toBeVisible({ timeout: 20000 });
  await peek.click();
  await expect(page).toHaveURL(/player-detail\.html/, { timeout: 20000 });
  await page.locator('.pd-back-btn').first().click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await page.locator('#autoset-lineup').click();
  await expect(page.locator('#sim-now')).not.toHaveClass(/disabled/, { timeout: 15000 });
  await page.locator('#sim-now').click();
  await expect(page).toHaveURL(/court\.html/, { timeout: 20000 });
  await expect(page.locator('a.completion-button.locker-room-button')).toBeVisible({ timeout: 45000 });
}

test('end-of-game locker room link returns to the locker room, and Forward stays out of the game', async ({ page }) => {
  await playToEndOfGame(page);
  const link = page.locator('a.completion-button.locker-room-button');
  await expect(link).toHaveAttribute('href', /franchise-command-center\.html/);
  await link.click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/tab=home-tab/);
  await backToModeSelect(page);
  await page.goForward({ waitUntil: 'commit' });
  await expect(page).not.toHaveURL(/court\.html|set-lineup\.html/);
});

test('end-of-game box score exit returns to the locker room', async ({ page }) => {
  await playToEndOfGame(page);
  await page.locator('a.completion-button.box-score-button').click();
  await expect(page).toHaveURL(/box-score\.html/, { timeout: 20000 });
  await page.locator('#locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/tab=home-tab/);
  await backToModeSelect(page);
});

test('standings team page returns instantly with in-app Back and browser Back', async ({ page }) => {
  await installApi(page, commandCenter({ training_completed: true, week: 1 }));
  await openLockerRoom(page);
  await page.locator('[data-tab="standings-tab"]').click();
  const teamLink = page.locator('#standings-by-region a').first();
  await expect(teamLink).toBeVisible({ timeout: 20000 });
  await page.evaluate(() => { window.__standingsMark = 'alive'; });
  await teamLink.click();
  await expect(page).toHaveURL(/team-roster-view\.html/, { timeout: 20000 });
  await page.locator('#back-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 15000 });
  await expect(page).toHaveURL(/tab=standings-tab/);
  const afterInApp = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    return { mark: window.__standingsMark || null, type: nav ? nav.type : '' };
  });
  expect(afterInApp.mark === 'alive' || afterInApp.type === 'back_forward', JSON.stringify(afterInApp)).toBe(true);
  await page.evaluate(() => { window.__standingsMark = 'alive'; });
  await page.locator('#standings-by-region a').first().click();
  await expect(page).toHaveURL(/team-roster-view\.html/, { timeout: 20000 });
  await page.goBack({ waitUntil: 'commit' });
  await expect(page).toHaveURL(/tab=standings-tab/, { timeout: 15000 });
  await expect(page).toHaveURL(/franchise-command-center\.html/);
  const afterBrowser = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    return { mark: window.__standingsMark || null, type: nav ? nav.type : '' };
  });
  expect(afterBrowser.mark === 'alive' || afterBrowser.type === 'back_forward', JSON.stringify(afterBrowser)).toBe(true);
});

test('a corrupted exit index still lands on the locker room', async ({ page }) => {
  await playToEndOfGame(page);
  await page.evaluate(() => {
    const state = history.state && typeof history.state === 'object' ? history.state : {};
    const current = typeof state.gobIdx === 'number' ? state.gobIdx : 1;
    const copy = Object.assign({}, state, { gobIdx: current + 1 });
    history.replaceState(copy, '', location.pathname + location.search + location.hash);
    sessionStorage.setItem('gob_nav_idx', JSON.stringify(current + 1));
  });
  await page.locator('a.completion-button.locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page).not.toHaveURL(/mode-select\.html/);
  await expect(page).toHaveURL(/tab=home-tab/);
});

test('custom playbooks adds one step and Back removes it, then training still returns with one Back', async ({ page }) => {
  await installApi(page, commandCenter({ training_completed: false, week: 1 }));
  await openLockerRoom(page);
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/training\.html/, { timeout: 20000 });
  await page.locator('#playbook-mode-custom-btn').click();
  await expect(page).toHaveURL(/training-playbooks\.html/, { timeout: 20000 });
  await page.locator('#tp-back').click();
  await expect(page).toHaveURL(/training\.html/, { timeout: 20000 });
  await expect(page).not.toHaveURL(/training-playbooks\.html/);
  await page.waitForFunction(() => {
    const el = document.getElementById('points-remaining');
    return el && String(el.textContent || '').replace(/\s/g, '').includes('0');
  }, null, { timeout: 15000 });
  await page.locator('input[name="coaching-focus"][value="authoritarian-discipline"]').check({ force: true });
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 10000 });
  await page.locator('#submit-btn').click();
  await expect(page).toHaveURL(/\/training-report\.html/, { timeout: 20000 });
  await page.locator('#locker-room-btn').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await backToModeSelect(page);
});

test('Enter Franchise gives the locker room its own step, and one Back returns to mode-select', async ({ page }) => {
  await installApi(page, commandCenter({ training_completed: true, week: 1 }));
  await page.goto('/mode-select.html');
  const modeIdx = await page.evaluate(() => {
    const state = history.state;
    return state && typeof state.gobIdx === 'number' ? state.gobIdx : null;
  });
  await page.locator('[data-action="enter-franchise"]').first().click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  const lockerIdx = await page.evaluate(() => {
    const state = history.state;
    return state && typeof state.gobIdx === 'number' ? state.gobIdx : null;
  });
  expect(modeIdx).toBe(0);
  expect(lockerIdx).toBe(1);
  await backToModeSelect(page);
});

test('a replayed quarter 409 leaves the court unpainted and returns to the lineup', async ({ page }) => {
  test.setTimeout(120000);
  const dialogs = [];
  page.on('dialog', (dialog) => dialogs.push(dialog.message()));
  await page.addInitScript(() => {
    const mark = () => {
      if (document.querySelector('#phaser-container canvas')) {
        try { sessionStorage.setItem('e2e_phaser_canvas', '1'); } catch (e) {}
      }
    };
    try { sessionStorage.removeItem('e2e_phaser_canvas'); } catch (e) {}
    new MutationObserver(mark).observe(document.documentElement, { childList: true, subtree: true });
    mark();
  });
  await installApi(page, commandCenter({ training_completed: true, week: 1 }), {
    quarterAlreadyPlayed: true,
    resumeState: { status: 'quarter_break', quarter: 2 },
  });
  await openLockerRoom(page);
  await expect(page.locator('#play-now')).toHaveText('Play Next Game');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await page.locator('#autoset-lineup').click();
  await expect(page.locator('#sim-now')).not.toHaveClass(/disabled/, { timeout: 15000 });
  await page.locator('#sim-now').click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/quarter=2/);
  await expect(page).not.toHaveURL(/court\.html/);
  expect(dialogs, dialogs.join('\n')).toEqual([]);
  const painted = await page.evaluate(() => sessionStorage.getItem('e2e_phaser_canvas') === '1');
  expect(painted).toBe(false);
});

test('recruiting and cut-players exits return to the locker room they started from', async ({ page }) => {
  await installApi(page, commandCenter({
    week: 20,
    training_completed: true,
    cut_required: false,
    recruiting_wire: { board_saved_week: 0 },
  }));
  await openLockerRoom(page);
  await expect(page.locator('#play-now')).toHaveText('Set Recruit Invites');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/recruiting\.html/, { timeout: 20000 });
  await page.locator('#back-btn').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page).not.toHaveURL(/mode-select\.html/);

  await installApi(page, commandCenter({
    week: 1,
    training_completed: true,
    cut_required: true,
    recruiting_wire: {},
    cut_count: 1,
  }));
  await page.goto('/mode-select.html');
  await page.locator('[data-action="enter-franchise"]').first().click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page.locator('#fcc-cut-required-close')).toBeVisible({ timeout: 20000 });
  await page.locator('#fcc-cut-required-close').click();
  await expect(page).toHaveURL(/cut-players\.html/, { timeout: 20000 });
  await page.locator('#back-btn').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page).not.toHaveURL(/mode-select\.html/);
});
