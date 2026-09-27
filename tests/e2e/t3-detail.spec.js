const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-t3';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 3,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 3, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
  };
}

function rosterBody(focus) {
  const players = [];
  for (let i = 0; i < 12; i += 1) {
    players.push({
      _id: 'p' + i,
      name: i === 0 ? 'Cedric Buckles' : ('Player ' + i),
      year: 'JR',
      height: 76,
      weight: 210,
      position: 'SG',
      rt: 80,
      potential_rt_ratcheted: 90,
      starter: i < 5,
      lineup_order: i < 5 ? i : null,
      attributes: { SC: 70, SH: 60, ID: 50, OD: 40, PS: 80, BH: 55, RB: 65, AG: 75, ST: 85, ND: 45, IQ: 90, FT: 35 },
      resolved_training_focus: i === 0 ? (focus || 'offensive') : 'standard',
      training_focus: i === 0 ? (focus || 'offensive') : 'standard',
    });
  }
  return { team: 'Lancaster', is_user_team: true, players: players, training_squad: [], practice_squad_recruits: [] };
}

function groups() {
  return [
    { id: 'offense', label: 'Offense', attrs: [{ attr: 'SC', raw: 70, display: 7 }, { attr: 'SH', raw: 60, display: 6 }] },
    { id: 'defense', label: 'Defense', attrs: [{ attr: 'ID', raw: 50, display: 5 }, { attr: 'OD', raw: 40, display: 4 }] },
  ];
}

function playerDetail(id, opts) {
  const mine = id === 'p0' || (opts && opts.user);
  return {
    player_id: id,
    name: id === 'p0' ? 'Cedric Buckles' : (id === 'cpu' ? 'Riley Quinn' : ('Player ' + id.replace('p', ''))),
    team_id: mine ? TID : OPP,
    team_name: mine ? 'Lancaster' : 'York',
    team_primary_color: mine ? '#27408E' : null,
    position: 'SG',
    year: 'JR',
    height_in: 76,
    weight: 210,
    jersey: '12',
    is_user_team: !!mine,
    rt: 80,
    potential: 92,
    attributes: groups(),
    season: { gp: 10, min_per_game: 28.2, pts_per_game: 14.2, reb_per_game: 4, ast_per_game: 3.1, stl_per_game: 1, blk_per_game: 0.4, fg_pct: 48.2, tp_pct: 36.5, ft_pct: 80, def_pct: null },
    career: { gp: 40, min_per_game: 22, pts_per_game: 11, reb_per_game: 3.5, ast_per_game: 2, stl_per_game: 0.8, blk_per_game: 0.2, fg_pct: 45, tp_pct: 33, ft_pct: 78, def_pct: 12.5 },
    recent_changes: [
      { week: 3, session_type: 'in-season', changes: [{ attr: 'SC', from: 4, to: 5 }] },
      { week: 2, session_type: 'in-season', changes: [{ attr: 'ZZ', delta: 1 }] },
    ],
    development: {
      focus: opts && opts.focus ? opts.focus : 'offensive',
      focus_label: opts && opts.focus === 'rebounding' ? 'Rebounding' : 'Offensive',
      emphasises: ['SC', 'SH'],
      editable: !!mine,
    },
  };
}

function teamDetail(id) {
  const mine = id === TID;
  return {
    team_id: id,
    name: mine ? 'Lancaster' : 'York',
    primary_color: mine ? '#27408E' : null,
    conference: 'A2',
    region: 'A',
    record: { wins: 10, losses: 2 },
    natl_rank: mine ? 14 : 6,
    conference_place: '1st of 8',
    streak: 'W4',
    next_game: mine
      ? { week: 25, site: 'away', opponent_id: OPP, opponent_name: 'York', opponent_primary_color: null, opponent_natl_rank: 6 }
      : { week: 25, site: 'home', opponent_id: TID, opponent_name: 'Lancaster', opponent_primary_color: '#27408E', opponent_natl_rank: 14 },
    results: [
      { week: 3, site: 'home', team_score: 70, opp_score: 60, result: 'W', opponent_id: OPP, opponent_name: 'York', opponent_primary_color: null, opponent_natl_rank: 6 },
    ],
    upcoming: [
      { week: 26, site: 'away', opponent_id: 'cccccccccccccccccccccccc', opponent_name: 'Dover', opponent_primary_color: '#333333', opponent_natl_rank: 20 },
    ],
  };
}

function standings() {
  const rows = [];
  for (let i = 0; i < 4; i += 1) {
    const id = i === 0 ? TID : (OPP.slice(0, 23) + i);
    rows.push({
      team_id: id,
      name: i === 0 ? 'Lancaster' : ('York ' + i),
      display_name: i === 0 ? 'Lancaster' : ('York ' + i),
      primary_color: i === 1 ? null : '#27408E',
      W: 10 - i,
      L: i,
      pct: 0.8,
      PF: 70,
      PA: 60,
      differential: 10,
      streak: 'W1',
      conference: 2,
      region: 'A',
    });
  }
  return { standings: rows, user_team_id: TID };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, state) {
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
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(pathname)) {
        await route.fulfill({ status: 404, body: '' });
        return;
      }
      await route.continue();
      return;
    }
    if (request.method() === 'POST' && pathname.indexOf('/franchise/player/development-focus') !== -1) {
      const body = request.postDataJSON() || {};
      state.focus = body.training_focus || state.focus;
      state.posted = body;
      await fulfillJson(route, { ok: true });
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
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, standings());
      return;
    }
    if (pathname.startsWith('/franchise/player-detail')) {
      if (state.failPlayer) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      if (state.holdPlayer && state.gate) await state.gate;
      const id = new URL(request.url()).searchParams.get('player_id') || 'p0';
      await fulfillJson(route, playerDetail(id, { user: id === 'p0', focus: state.focus }));
      return;
    }
    if (pathname.startsWith('/franchise/team-detail')) {
      if (state.failTeam) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      const id = new URL(request.url()).searchParams.get('team_id') || TID;
      await fulfillJson(route, teamDetail(id));
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, rosterBody(state.focus));
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, state, search) {
  await stubAuth(page);
  await installApi(page, state);
  await page.goto('/franchise-command-center.html' + (search || ('?franchise_id=' + FID + '&team_id=' + TID)));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

test('roster push opens a player and Back restores the roster scroll', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 320; });
  const saved = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(saved).toBeGreaterThan(80);
  const before = await page.evaluate(() => history.state && history.state.gobIdx);
  await page.locator('#roster-view a.gob-player').first().evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=player-view/);
  await expect(page.locator('#player-view')).toContainText('Cedric Buckles');
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(before + 1);
  await expect(page.locator('[data-gob-section="team"].on')).toHaveCount(1);
  await page.goBack();
  await page.waitForURL(/tab=roster-view/);
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, saved, { timeout: 8000 });
});

test('the player pager replaces and stops at the ends', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
  await page.locator('#roster-view a.gob-player').first().evaluate((anchor) => anchor.click());
  await page.waitForSelector('#player-view .gob-pager');
  const idx = await page.evaluate(() => history.state && history.state.gobIdx);
  await expect(page.locator('#player-view .gob-pager button[aria-label="Previous"]')).toBeDisabled();
  await page.locator('#player-view .gob-pager button[aria-label="Next"]').evaluate((button) => button.click());
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Player 1');
  expect(page.url()).toContain('player_id=p1');
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(idx);
  await page.locator('#player-view .gob-pager button[aria-label="Previous"]').evaluate((button) => button.click());
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Cedric Buckles');
  await expect(page.locator('#player-view .gob-pager button[aria-label="Previous"]')).toBeDisabled();
});

test('standings opens a team with a conference pager and the league rail', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state);
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view a.gob-team');
  await page.locator('#standings-view a.gob-team').nth(1).evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=team-view/);
  await expect(page.locator('#team-view .gob-hero-n')).toBeVisible();
  await expect(page.locator('#team-view .gob-pager')).toContainText('of 4');
  await expect(page.locator('[data-gob-section="league"].on')).toHaveCount(1);
  const owner = new URL(page.url()).searchParams.get('team_id');
  expect(owner).toBe(TID);
  expect(new URL(page.url()).searchParams.get('view_team_id')).not.toBe(TID);
});

test('old player and other-team links redirect into the views', async ({ page }) => {
  const state = { focus: 'offensive' };
  await stubAuth(page);
  await installApi(page, state);
  await page.goto('/player-detail.html?id=p0&mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&return_tab=roster-view');
  await page.waitForURL(/tab=player-view/);
  expect(new URL(page.url()).searchParams.get('player_id')).toBe('p0');
  expect(new URL(page.url()).searchParams.get('team_id')).toBe(TID);
  await page.goto('/player-detail.html?recruit_id=r1&franchise_id=' + FID);
  await page.waitForURL(/player-detail\.html/);
  expect(page.url()).toContain('recruit_id=r1');
  await page.goto('/team-roster-view.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&roster_team_id=' + OPP + '&return_tab=standings-view');
  await page.waitForURL(/tab=team-view/);
  expect(new URL(page.url()).searchParams.get('team_id')).toBe(TID);
  expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(OPP);
});

test('recent changes skip delta-only entries and a cpu player is read-only', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await expect(page.locator('#player-view')).toContainText('SC');
  await expect(page.locator('#player-view')).toContainText('4');
  await expect(page.locator('#player-view')).toContainText('5');
  await expect(page.locator('#player-view')).not.toContainText('ZZ');
  await expect(page.locator('#player-view .gob-focus')).toBeVisible();
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=cpu&origin=league');
  await expect(page.locator('#player-view .gob-focus-read')).toContainText('Offensive');
  await expect(page.locator('#player-view .gob-focus-read')).toContainText('Emphasises SC · SH');
  await expect(page.locator('#player-view .gob-focus')).toHaveCount(0);
  await expect(page.locator('[data-gob-section="league"].on')).toHaveCount(1);
});

test('development focus posts and the roster shows the saved label', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team&return_tab=roster-view');
  await page.waitForSelector('#player-view .gob-focus');
  await page.locator('#player-view .gob-focus').selectOption('rebounding');
  await page.locator('#player-view .gob-save').click();
  await expect.poll(() => state.posted && state.posted.training_focus).toBe('rebounding');
  await page.locator('#player-view .gob-dt-up').click();
  await page.waitForURL(/tab=roster-view/);
  await expect(page.locator('#roster-view')).toContainText('Rebounding');
});

test('a missing portrait and a missing logo fall back to letters', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=cpu&origin=league');
  await expect(page.locator('#player-view .gob-portrait')).toContainText('RQ');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-view&view_team_id=' + OPP + '&origin=league');
  await expect(page.locator('#team-view .gob-hero-logo .gob-mark')).toContainText('Y');
  await expect(page.locator('#team-view')).toContainText('Scout them');
});

test('first open shows a skeleton and a failed detail retries', async ({ page }) => {
  let release = function () {};
  const state = {
    focus: 'offensive',
    holdPlayer: true,
    gate: new Promise(function (resolve) { release = resolve; }),
  };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await expect(page.locator('#player-view .gob-view-skel')).toBeVisible();
  await expect(page.locator('#player-view .spinner, #player-view [class*="spinner"]')).toHaveCount(0);
  state.holdPlayer = false;
  release();
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Cedric Buckles');
  state.failPlayer = true;
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p1&origin=team');
  await expect(page.locator('#player-view .gob-view-error')).toBeVisible();
  await expect(page.locator('#player-view .gob-view-retry')).toBeVisible();
  state.failPlayer = false;
  await page.locator('#player-view .gob-view-retry').click();
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Player 1');
});

test('the detail pages do not scroll sideways', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await page.waitForSelector('#player-view .gob-hero-n');
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(100);
    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth - main.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
    await assertOneVerticalScroll(page);
  }
});
