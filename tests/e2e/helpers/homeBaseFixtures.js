// @ts-check
/**
 * Home Base (mode-select, online) fixtures: programs, community feeds and the
 * coach-career numerals. home-base-online.spec.js keeps its own copy.
 */
const { expect } = require('@playwright/test');
const { stubAuth } = require('./auth');

const LONG_NAME = 'Northwestern Ocean City Maritime Polytechnic';

function franchise(id, slot, name, week) {
  return {
    franchise_id: id,
    home_slot: slot,
    user_team_id: name,
    user_team_object_id: 'obj-' + id,
    week: week,
    current_season: 3,
    primary_color: '#27408e',
    secondary_color: '#15181f',
    last_played_at: '2026-09-2' + slot + 'T10:00:00Z',
  };
}

function commandCenter(name, week, opts) {
  opts = opts || {};
  return {
    current_season: 3,
    week: week,
    rankings: [{ team_id: 'obj-' + opts.id, team_name: name, W: 12, L: 3, next: 'Lancaster' }],
    active_game_resume: opts.live
      ? {
        status: 'stoppage_anchor',
        game_id: 'g-' + opts.id,
        user_team_side: 'home',
        away_display_name: 'Xavien',
        away_team_name: 'Xavien',
        home_display_name: name,
        quarter: 3,
        clock: '4:12',
        away_score: 61,
        home_score: 58,
      }
      : null,
  };
}

function atlSlot(i, userId) {
  return {
    user_id: userId,
    franchise_id: 'atl-f-' + i,
    username: 'Coach ' + i,
    team_name: i % 2 ? 'Lancaster' : 'Morristown',
    primary_color: '#27408e',
    secondary_color: '#15181f',
    wins: 10 + i,
    losses: i,
    national_rank: i + 1,
    current_season: 4,
    week: 14,
    next_opponent: { is_away: false, team_name: 'Xavien' },
    last_game: { won: i % 2 === 0, is_away: false, opponent: 'Four Corners', user_score: 81, opp_score: 74 },
    completed_at: '2026-09-28T1' + i + ':00:00Z',
  };
}

function leaderboard(rows) {
  const top = [];
  for (let i = 1; i <= rows; i += 1) {
    top.push({ rank: i, username: 'Coach ' + i, geek_points: 1300 - i * 20, is_current_user: false });
  }
  return {
    top: top,
    current_user: { rank: 38, username: 'e2e', geek_points: 380, is_current_user: true },
    titles_top: top.slice(0, 5).map((e, i) => ({
      rank: i + 1, username: e.username, total_titles: 7 - i, national_titles: 1, is_current_user: false,
    })),
    titles_current_user: { rank: 22, username: 'e2e', total_titles: 1, national_titles: 0, is_current_user: true },
  };
}

/** GET /franchise/coach-career. `earned: false` is a coach who has played nothing. */
function coachCareer(earned) {
  if (earned === null) return {};
  return {
    user_id: 'e2e-user',
    username: 'e2e',
    record: earned
      ? { wins: 73, losses: 22, total_games: 95, win_rate: 77 }
      : { wins: 0, losses: 0, total_games: 0, win_rate: 0 },
    championships_total: earned
      ? { conf_rs: 1, conf_t: 1, region: 1, national: 0 }
      : { conf_rs: 0, conf_t: 0, region: 0, national: 0 },
    // Pre-summed by the server (Ch7 PR2): the client shows this verbatim.
    titles_total: earned ? 3 : 0,
    win_pct_display: earned ? '.768' : null,
    geek_points: earned ? 4060 : 0,
    seasons_completed: earned ? 4 : 0,
    programs: earned ? 2 : 0,
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {{programs?: number, live?: boolean, desktop?: boolean, width?: number, height?: number,
 *          longNames?: boolean, atl?: number, lbRows?: number, tab?: string,
 *          career?: boolean|null}} [opts]
 */
async function openHomeBase(page, opts) {
  opts = opts || {};
  const programs = opts.programs == null ? 2 : opts.programs;
  const width = opts.width || 1280;
  const height = opts.height || 720;
  const community = [];

  page.on('request', (req) => {
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (_err) { return; }
    if (pathname.startsWith('/api/community/') || pathname === '/api/auth/leaderboard'
      || pathname.startsWith('/api/leaderboard/')) community.push(pathname);
  });

  if (opts.desktop) await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  if (opts.tab) {
    await page.addInitScript((tab) => { localStorage.setItem('gob_hb_tab', tab); }, opts.tab);
  }
  await stubAuth(page);

  const names = opts.longNames
    ? [LONG_NAME, LONG_NAME + ' South']
    : ['Bentley-Truman', 'Ocean City'];
  const list = [];
  for (let i = 0; i < programs; i += 1) list.push(franchise('f' + (i + 1), i + 1, names[i], 14 - i));

  await page.route('**/api/auth/me', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
  }));
  await page.route('**/franchise/list', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({
      franchises: list,
      count: list.length,
      max: 2,
      // Slot 2 is the most recent, so the green must not simply follow slot order.
      most_recent_franchise_id: programs >= 2 ? 'f2' : (programs === 1 ? 'f1' : null),
    }),
  }));
  await page.route('**/teams', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(list.map((f) => ({
      object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9,
    }))),
  }));
  await page.route('**/franchise/command-center/data**', (r) => {
    const id = new URL(r.request().url()).searchParams.get('franchise_id') || '';
    const f = list.find((x) => x.franchise_id === id);
    if (!f) return r.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    // The live game sits on slot 1, which is NOT the most recent program: the
    // green has to move to it anyway.
    return r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(commandCenter(f.user_team_id, f.week, { id: id, live: !!opts.live && id === 'f1' })),
    });
  });
  await page.route('**/api/community/around-the-league', (r) => {
    const n = opts.atl == null ? 8 : opts.atl;
    const slots = [];
    for (let i = 0; i < n; i += 1) slots.push(atlSlot(i, i === 0 ? 'e2e-user' : 'other-' + i));
    return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ slots: slots }) });
  });
  await page.route('**/api/auth/leaderboard', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(leaderboard(opts.lbRows == null ? 10 : opts.lbRows)),
  }));
  await page.route('**/franchise/coach-career', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(opts.careerBody || coachCareer(opts.career === undefined ? true : opts.career)),
  }));

  await page.setViewportSize({ width: width, height: height });
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.hb-top')).toBeVisible();
  return community;
}

module.exports = { openHomeBase, coachCareer, franchise, commandCenter, leaderboard, atlSlot };
