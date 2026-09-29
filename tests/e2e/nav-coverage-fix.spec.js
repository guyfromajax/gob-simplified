const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

/**
 * Navigation fixes from reports/coverage-map-2026-09-29.md (Findings 1–5).
 * Both profiles run against stubbed API routes. The desktop profile is served
 * from 127.0.0.1 on the same port, so its loopback calls stay same-origin.
 */

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-navfix';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const DOVER = 'cccccccccccccccccccccccc';
const WEB_BASE = process.env.BASE_URL || 'http://localhost:8000';
const PORT = new URL(WEB_BASE).port || '8000';
const DESKTOP_BASE = 'http://127.0.0.1:' + PORT;
const PROFILES = ['web', 'desktop'];
const OUT = path.join(__dirname, '../../reports/nav-coverage-fix');

function base(profile) {
  return profile === 'desktop' ? DESKTOP_BASE : WEB_BASE;
}

function cc(week) {
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
    recruiting_wire: { board_saved_week: week, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
  };
}

function rosterBody() {
  const players = [];
  for (let i = 0; i < 8; i += 1) {
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
      resolved_training_focus: 'standard',
      training_focus: 'standard',
    });
  }
  return { team: 'Lancaster', is_user_team: true, players: players, training_squad: [], practice_squad_recruits: [] };
}

function playerDetail(id) {
  const mine = id.charAt(0) === 'p';
  return {
    player_id: id,
    name: id === 'p0' ? 'Cedric Buckles' : ('Player ' + id.replace('p', '')),
    team_id: mine ? TID : OPP,
    team_name: mine ? 'Lancaster' : 'York',
    team_primary_color: mine ? '#27408E' : null,
    position: 'SG',
    year: 'JR',
    height_in: 76,
    weight: 210,
    jersey: '12',
    is_user_team: mine,
    rt: 80,
    potential: 92,
    attributes: [{ id: 'offense', label: 'Offense', attrs: [{ attr: 'SC', raw: 70, display: 7 }] }],
    season: { gp: 10, min_per_game: 28, pts_per_game: 14, reb_per_game: 4, ast_per_game: 3, stl_per_game: 1, blk_per_game: 0, fg_pct: 48, tp_pct: 36, ft_pct: 80, def_pct: null },
    career: { gp: 40, min_per_game: 22, pts_per_game: 11, reb_per_game: 3, ast_per_game: 2, stl_per_game: 1, blk_per_game: 0, fg_pct: 45, tp_pct: 33, ft_pct: 78, def_pct: null },
    recent_changes: [],
    development: { focus: 'standard', focus_label: 'Standard', emphasises: [], editable: false },
  };
}

const NAMES = { [TID]: 'Lancaster', [OPP]: 'York', [DOVER]: 'Dover' };

function teamDetail(id) {
  const others = [TID, OPP, DOVER].filter((other) => other !== id);
  return {
    team_id: id,
    name: NAMES[id] || 'Team',
    primary_color: id === TID ? '#27408E' : null,
    conference: 'A2',
    region: 'A',
    record: { wins: 10, losses: 2 },
    natl_rank: 6,
    conference_place: '1st of 8',
    streak: 'W4',
    next_game: null,
    results: [
      { week: 3, site: 'home', team_score: 70, opp_score: 60, result: 'W', opponent_id: others[0], opponent_name: NAMES[others[0]], opponent_primary_color: null, opponent_natl_rank: 6 },
    ],
    upcoming: [
      { week: 26, site: 'away', opponent_id: others[1], opponent_name: NAMES[others[1]], opponent_primary_color: null, opponent_natl_rank: 20 },
    ],
  };
}

function standings() {
  return {
    standings: [TID, OPP, DOVER].map((id, i) => ({
      team_id: id,
      name: NAMES[id],
      display_name: NAMES[id],
      primary_color: '#27408E',
      W: 10 - i,
      L: i,
      pct: 0.8,
      PF: 70,
      PA: 60,
      differential: 10,
      streak: 'W1',
      conference: 2,
      region: 'A',
    })),
    user_team_id: TID,
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function setup(page, profile, opts) {
  const state = Object.assign({ week: 3 }, opts || {});
  await page.addInitScript(({ desktop, apiBase, port }) => {
    if (desktop) {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
    }
    window.API_BASE_URL = apiBase;
    localStorage.setItem('auth_token', 'e2e-stub-token');
    localStorage.setItem('auth_user', JSON.stringify({ user_id: 'e2e-user', email: 'e2e@example.com', username: 'e2e' }));
  }, { desktop: profile === 'desktop', apiBase: base(profile), port: PORT });
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) {
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(pathname)) {
        await route.fulfill({ status: 404, body: '' });
        return;
      }
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
      await fulfillJson(route, cc(state.week));
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, standings());
      return;
    }
    if (pathname.startsWith('/franchise/player-detail')) {
      const id = new URL(request.url()).searchParams.get('player_id') || 'p0';
      await fulfillJson(route, playerDetail(id));
      return;
    }
    if (pathname.startsWith('/franchise/team-detail')) {
      const id = new URL(request.url()).searchParams.get('team_id') || TID;
      await fulfillJson(route, teamDetail(id));
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, rosterBody());
      return;
    }
    await fulfillJson(route, {});
  });
  return state;
}

function fccUrl(profile, extra) {
  return base(profile) + '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + (extra ? '&' + extra : '');
}

async function waitReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('html.gob-shell .rail');
}

async function openFcc(page, profile, extra) {
  await page.goto(fccUrl(profile, extra));
  await waitReady(page);
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  await loc.scrollIntoViewIfNeeded();
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

function tabOf(page) {
  return new URL(page.url()).searchParams.get('tab');
}

// Counts main-frame document loads from now on. pushState does not issue one.
function watchDocuments(page) {
  const loads = [];
  page.on('request', (req) => {
    if (req.isNavigationRequest() && req.frame() === page.mainFrame()) loads.push(req.url());
  });
  return loads;
}

async function markDocument(page) {
  await page.evaluate(() => { window.__sameDocument = 'yes'; });
}

async function expectSameDocument(page) {
  expect(await page.evaluate(() => window.__sameDocument || '')).toBe('yes');
}

test('desktop: a roster player opens, and Back returns to Roster', async ({ page }) => {
  await setup(page, 'desktop');
  await openFcc(page, 'desktop', 'tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
  await expect(page.locator('.rail #gob-rail-feedback')).toBeHidden();
  await markDocument(page);
  const link = page.locator('#roster-view a.gob-player').filter({ hasText: 'Player 3' }).first();
  await link.evaluate((anchor) => anchor.click());
  await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'player-view');
  await expect(page.locator('#player-view .gob-hero-n')).toHaveText('Player 3');
  await expect(page.locator('#player-view')).not.toContainText('could not be opened');
  expect(new URL(page.url()).searchParams.get('player_id')).toBe('p3');
  await expectSameDocument(page);
  await page.goBack();
  await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'roster-view');
  await expect(page.locator('#roster-view')).toBeVisible();
  await expect(page.locator('#roster-view a.gob-player').first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get('player_id')).toBeNull();
  await expectSameDocument(page);
});

test('desktop: player-detail.html?id= lands on that player', async ({ page }) => {
  await setup(page, 'desktop');
  await page.goto(DESKTOP_BASE + '/player-detail.html?id=p5&mode=franchise&franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'player-view');
  await waitReady(page);
  await expect(page.locator('#player-view .gob-hero-n')).toHaveText('Player 5');
  await expect(page.locator('#player-view')).not.toContainText('could not be opened');
  expect(new URL(page.url()).searchParams.get('player_id')).toBe('p5');
});

for (const profile of PROFILES) {
  test(profile + ': the Office rail button works from player-view and team-view', async ({ page }) => {
    await setup(page, profile);
    const views = [
      // No origin: the view stamps one from the loaded player (own team → team).
      // First, so the desktop session has no origin from an earlier drill.
      ['tab=player-view&player_id=p2', '#player-view .gob-hero-n', 'team'],
      ['tab=player-view&player_id=p2&origin=team', '#player-view .gob-hero-n', 'team'],
      ['tab=team-view&view_team_id=' + OPP + '&origin=league', '#team-view .gob-hero-n', 'league'],
    ];
    for (const [search, ready, origin] of views) {
      await openFcc(page, profile, search);
      await page.waitForSelector(ready);
      await expect(page.locator('.rail [data-gob-section].on')).toHaveCount(1);
      await expect(page.locator('.rail [data-gob-section="' + origin + '"].on')).toHaveCount(1);
      expect(new URL(page.url()).searchParams.get('origin')).toBe(origin);
      await markDocument(page);
      await mouseClick(page, '.rail [data-gob-section="office"]');
      await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'home-tab');
      await expect(page.locator('.rail [data-gob-section="office"].on')).toHaveCount(1);
      await expectSameDocument(page);
    }
  });

  test(profile + ': a team link opens in-app and Back returns', async ({ page }) => {
    await setup(page, profile);
    await openFcc(page, profile, 'tab=standings-view');
    const team = page.locator('#standings-view a.gob-team').filter({ hasText: 'York' }).first();
    await expect(team).toBeVisible();
    expect(await team.getAttribute('href')).not.toContain('team-roster-view.html');
    await markDocument(page);
    const loads = watchDocuments(page);
    await mouseClick(page, team);
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'team-view');
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('York');
    expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(OPP);
    await expect(page.locator('.rail [data-gob-section="league"].on')).toHaveCount(1);
    expect(loads).toEqual([]);
    await expectSameDocument(page);
    await page.goBack();
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'standings-view');
    await expect(page.locator('#standings-view')).toBeVisible();
    expect(loads).toEqual([]);
    await expectSameDocument(page);
  });

  test(profile + ': an old team-roster-view.html link clicked in the app opens in place', async ({ page }) => {
    await setup(page, profile);
    await openFcc(page, profile, 'tab=standings-view');
    await expect(page.locator('#standings-view a.gob-team').first()).toBeVisible();
    await page.evaluate(({ fid, tid, opp }) => {
      const a = document.createElement('a');
      a.id = 'legacy-team-link';
      a.textContent = 'York';
      a.href = '/team-roster-view.html?mode=franchise&franchise_id=' + fid + '&team_id=' + tid
        + '&roster_team_id=' + opp + '&team_name=York&return_tab=standings-view';
      a.setAttribute('data-return', '');
      document.getElementById('standings-view').prepend(a);
    }, { fid: FID, tid: TID, opp: OPP });
    await markDocument(page);
    const loads = watchDocuments(page);
    await mouseClick(page, '#legacy-team-link');
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'team-view');
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('York');
    const url = new URL(page.url());
    expect(url.pathname).toBe('/franchise-command-center.html');
    expect(url.searchParams.get('return_url')).toBeNull();
    expect(url.searchParams.get('origin')).toBe('league');
    expect(loads).toEqual([]);
    await expectSameDocument(page);
    await page.goBack();
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'standings-view');
    await expectSameDocument(page);
  });

  test(profile + ': return_url does not nest after 3 drills', async ({ page }) => {
    await setup(page, profile);
    await openFcc(page, profile, 'tab=standings-view');
    await markDocument(page);
    const loads = watchDocuments(page);
    await mouseClick(page, page.locator('#standings-view a.gob-team').filter({ hasText: 'York' }).first());
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('York');
    const firstLength = page.url().length;
    await mouseClick(page, page.locator('#team-view .gob-sch-opp a.gob-team').filter({ hasText: 'Lancaster' }).first());
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Lancaster');
    await mouseClick(page, page.locator('#team-view .gob-sch-opp a.gob-team').filter({ hasText: 'Dover' }).first());
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Dover');
    const url = new URL(page.url());
    expect(url.searchParams.get('return_url')).toBeNull();
    expect(decodeURIComponent(page.url())).not.toContain('return_url');
    expect(page.url().length).toBeLessThanOrEqual(firstLength + 40);
    expect(url.searchParams.getAll('view_team_id')).toEqual([DOVER]);
    expect(loads).toEqual([]);
    for (const name of ['Lancaster', 'York']) {
      await page.goBack();
      await expect(page.locator('#team-view .gob-hero-n')).toHaveText(name);
    }
    await page.goBack();
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'standings-view');
    await expectSameDocument(page);
  });
}

for (const profile of PROFILES) {
  test(profile + ': rail Feedback on recruiting.html and stats.html', async ({ page }) => {
    await setup(page, profile);
    // The auth bar (which owns #feedback-btn) loads async; make it land after
    // the shell has mounted, as it does on a slow load.
    await page.route('**/js/shared/authBarInit.js', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.continue();
    });
    for (const file of ['recruiting.html', 'stats.html']) {
      await page.goto(base(profile) + '/' + file + '?franchise_id=' + FID + '&team_id=' + TID);
      await page.waitForSelector('html.gob-shell .rail');
      const rail = page.locator('.rail #gob-rail-feedback');
      await expect(rail).toHaveCount(1);
      if (profile === 'desktop') {
        await page.waitForTimeout(2000);
        if (file === 'recruiting.html') {
          fs.mkdirSync(OUT, { recursive: true });
          await page.setViewportSize({ width: 1280, height: 720 });
          await page.locator('.rail').screenshot({ path: path.join(OUT, 'desktop-rail-recruiting-1280.png') });
        }
        await expect(rail).toBeHidden();
      } else {
        await expect(rail).toBeVisible({ timeout: 15000 });
        await expect(rail).not.toHaveAttribute('hidden', /.*/, { timeout: 15000 });
      }
    }
  });
}

test('desktop: a resumed locked Tournament tab falls back to Office', async ({ page }) => {
  await setup(page, 'desktop', { week: 3 });
  await openFcc(page, 'desktop', 'tab=tournament-view');
  await expect(page.locator('#tournament-view')).toBeVisible();
  await page.waitForTimeout(500);
  expect(tabOf(page)).toBe('tournament-view');
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('gob:franchise_context') || '{}').tab);
  expect(stored).toBe('tournament-view');

  await page.goto(fccUrl('desktop'));
  await waitReady(page);
  await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'home-tab');
  await expect(page.locator('.rail [data-gob-section="office"].on')).toHaveCount(1);
  await expect(page.locator('#tournament-view')).toBeHidden();
});

test('web: no ?tab= opens Office, and an explicit Tournament link keeps its locked screen', async ({ page }) => {
  await setup(page, 'web', { week: 3 });
  await openFcc(page, 'web', 'tab=tournament-view');
  await expect(page.locator('#tournament-view')).toBeVisible();
  await page.waitForTimeout(500);
  expect(tabOf(page)).toBe('tournament-view');
  await page.goto(fccUrl('web'));
  await waitReady(page);
  await expect(page.locator('.rail [data-gob-section="office"].on')).toHaveCount(1);
});
