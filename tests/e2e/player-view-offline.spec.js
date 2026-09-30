const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

/**
 * Player drill-in on both profiles. Desktop used to drop player_id when
 * CommandCenterTabs.show rebuilt the URL from session (coverage-map 2026-09-29).
 */

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-pview';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const WEB_BASE = process.env.BASE_URL || 'http://localhost:8000';
const PORT = new URL(WEB_BASE).port || '8000';
const DESKTOP_BASE = 'http://127.0.0.1:' + PORT;
const PROFILES = ['web', 'desktop'];
const OUT = path.join(__dirname, '../../reports/player-view-offline');

function base(profile) {
  return profile === 'desktop' ? DESKTOP_BASE : WEB_BASE;
}

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
  return {
    player_id: id,
    name: id === 'p0' ? 'Cedric Buckles' : (id === 'p3' ? 'Player 3' : ('Player ' + String(id).replace('p', ''))),
    team_id: TID,
    team_name: 'Lancaster',
    team_primary_color: '#27408E',
    position: 'SG',
    year: 'JR',
    height_in: 76,
    weight: 210,
    jersey: '12',
    is_user_team: true,
    rt: 80,
    potential: 92,
    attributes: [
      { id: 'offense', label: 'Offense', attrs: [{ attr: 'SC', raw: 70, display: 7 }, { attr: 'SH', raw: 60, display: 6 }] },
      { id: 'defense', label: 'Defense', attrs: [{ attr: 'ID', raw: 50, display: 5 }, { attr: 'OD', raw: 40, display: 4 }] },
    ],
    season: { gp: 10, min_per_game: 28, pts_per_game: 14.2, reb_per_game: 4, ast_per_game: 3, stl_per_game: 1, blk_per_game: 0, fg_pct: 48, tp_pct: 36, ft_pct: 80, def_pct: null },
    career: { gp: 40, min_per_game: 22, pts_per_game: 11, reb_per_game: 3, ast_per_game: 2, stl_per_game: 1, blk_per_game: 0, fg_pct: 45, tp_pct: 33, ft_pct: 78, def_pct: null },
    recent_changes: [],
    development: { focus: 'standard', focus_label: 'Standard', emphasises: [], editable: false },
  };
}

function leaders() {
  return {
    PTS: [
      { player_id: 'p0', name: 'Cedric Buckles', team: 'Lancaster', team_id: TID, value: 18.2, position: 'SG', year: 'JR' },
      { player_id: 'p3', name: 'Player 3', team: 'Lancaster', team_id: TID, value: 14.1, position: 'SG', year: 'JR' },
    ],
    REB: [{ player_id: 'p0', name: 'Cedric Buckles', team: 'Lancaster', team_id: TID, value: 7.4, position: 'SG', year: 'JR' }],
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function watchPage(page) {
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err.message || err)));
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (/favicon|Failed to load resource|net::ERR/.test(text)) return;
    errors.push(text);
  });
  return errors;
}

async function setup(page, profile) {
  await page.addInitScript(({ desktop, apiBase, port }) => {
    if (desktop) {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
    }
    window.API_BASE_URL = apiBase;
    localStorage.setItem('auth_token', 'e2e-stub-token');
    localStorage.setItem('auth_user', JSON.stringify({
      user_id: 'e2e-user',
      email: 'e2e@example.com',
      username: 'e2e',
    }));
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
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.startsWith('/franchise/player-detail')) {
      const id = new URL(request.url()).searchParams.get('player_id') || '';
      if (!id) {
        await fulfillJson(route, { detail: 'missing player_id' }, 400);
        return;
      }
      await fulfillJson(route, playerDetail(id));
      return;
    }
    if (pathname.startsWith('/franchise/leaders')) {
      await fulfillJson(route, leaders());
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, rosterBody());
      return;
    }
    await fulfillJson(route, {});
  });
}

async function waitReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('html.gob-shell .rail');
}

function fccUrl(profile, extra) {
  return base(profile) + '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + (extra ? '&' + extra : '');
}

async function assertPlayerPage(page, name) {
  const root = page.locator('#player-view');
  await expect(root).not.toContainText('could not be opened');
  await expect(root.locator('.gob-hero-n')).toHaveText(name);
  await expect(root.locator('.gob-apan')).toBeVisible();
  await expect(root.locator('.gob-apr')).toHaveCount(4);
  await expect(root.locator('.gob-tbl')).toBeVisible();
  await expect(root.locator('.gob-tbl')).toContainText('Season');
  await expect(root.locator('.gob-tbl')).toContainText('Career');
  await expect(root.locator('.gob-tbl')).toContainText('14.2');
  expect(new URL(page.url()).searchParams.get('tab')).toBe('player-view');
  expect(new URL(page.url()).searchParams.get('player_id')).toBeTruthy();
}

for (const profile of PROFILES) {
  test(profile + ': roster and leaders open player-view with name, attributes, and stats', async ({ page }) => {
    const errors = watchPage(page);
    await setup(page, profile);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(fccUrl(profile, 'tab=roster-view'));
    await waitReady(page);
    await page.waitForSelector('#roster-view a.gob-player');
    await page.locator('#roster-view a.gob-player').filter({ hasText: 'Player 3' }).first().evaluate((anchor) => anchor.click());
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'player-view');
    await assertPlayerPage(page, 'Player 3');
    expect(new URL(page.url()).searchParams.get('player_id')).toBe('p3');
    fs.mkdirSync(OUT, { recursive: true });
    const afterName = profile === 'desktop' ? 'offline-after-1280.png' : 'online-after-1280.png';
    await page.screenshot({ path: path.join(OUT, afterName) });
    await page.screenshot({ path: path.join(OUT, profile + '-roster-after-1280.png') });

    await page.goto(fccUrl(profile, 'tab=leaders-view'));
    await waitReady(page);
    await page.waitForSelector('#leaders-view a.gob-player');
    await page.locator('#leaders-view a.gob-player').filter({ hasText: 'Cedric Buckles' }).first().evaluate((anchor) => anchor.click());
    await page.waitForFunction(() => new URLSearchParams(location.search).get('tab') === 'player-view');
    await assertPlayerPage(page, 'Cedric Buckles');
    expect(new URL(page.url()).searchParams.get('player_id')).toBe('p0');
    await page.screenshot({ path: path.join(OUT, profile + '-leaders-after-1280.png') });
    expect(errors, errors.join('\n')).toEqual([]);
  });
}

test('desktop: player-view without player_id still shows the error card', async ({ page }) => {
  await setup(page, 'desktop');
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(fccUrl('desktop', 'tab=player-view'));
  await waitReady(page);
  await expect(page.locator('#player-view')).toContainText('This player could not be opened');
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, 'offline-before-1280.png') });
});
