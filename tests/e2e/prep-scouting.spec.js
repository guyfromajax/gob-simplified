const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-prep-scout';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OUT = path.join(__dirname, '../../reports/prep-v2-pr4');

const MEASURES = [
  { key: 'shot_threshold', label: 'Shooting', rank: 12, rank_of: 128, percentile: 72, direction: 'lower_better' },
  { key: 'rebound_modifier', label: 'Rebounding', rank: 8, rank_of: 128, percentile: 88, direction: 'higher_better' },
  { key: 'team_chemistry', label: 'Chemistry', rank: 20, rank_of: 128, percentile: 55, value: 18, scale_max: 25, direction: 'higher_better' },
];

// Attribute keys use raw storage (display = floor(raw / 10); tier from display digit).
const PROJECTED = [
  {
    player_id: 'scout-pg-01',
    position: 'PG',
    name: 'Jordan Reyes',
    jersey: 4,
    year: 'sr',
    rt: 92,
    potential_rt_ratcheted: 95,
    attributes: { SC: 75, SH: 88, ID: 42, OD: 71, PS: 92, BH: 81, RB: 34, ST: 45, AG: 79, ND: 68, IQ: 77, FT: 72 },
  },
  {
    player_id: 'scout-sg-02',
    position: 'SG',
    name: 'Chris Molina',
    jersey: 12,
    year: 'jr',
    rt: 84,
    potential_rt_ratcheted: 88,
    attributes: { SC: 91, SH: 98, ID: 38, OD: 63, PS: 55, BH: 66, RB: 41, ST: 44, AG: 73, ND: 58, IQ: 62, FT: 85 },
  },
  {
    player_id: 'scout-sf-03',
    position: 'SF',
    name: 'Devon Hale',
    jersey: 21,
    year: 'so',
    rt: 71,
    potential_rt_ratcheted: 78,
    attributes: { SC: 64, SH: 58, ID: 74, OD: 82, PS: 49, BH: 52, RB: 71, ST: 63, AG: 66, ND: 55, IQ: 54, FT: 61 },
  },
  {
    player_id: 'scout-pf-04',
    position: 'PF',
    name: 'Marcus Webb',
    jersey: 33,
    year: 'jr',
    rt: 55,
    potential_rt_ratcheted: 55,
    attributes: { SC: 48, SH: 35, ID: 66, OD: 52, PS: 38, BH: 33, RB: 88, ST: 86, AG: 47, ND: 73, IQ: 44, FT: 41 },
  },
  {
    player_id: 'scout-c-05',
    position: 'C',
    name: 'Tyler Boone',
    jersey: 50,
    year: 'fr',
    rt: 36,
    potential_rt_ratcheted: 52,
    attributes: { SC: 28, SH: 22, ID: 81, OD: 46, PS: 25, BH: 24, RB: 79, ST: 93, AG: 36, ND: 64, IQ: 33, FT: 31 },
  },
];

const PLAYER_SEASON_STATS = {
  'scout-pg-01': { PTS: 14.2, FGM: 5.1, FGA: 10.8, 'FG%': 47.2, MIN: 28.4, AST: 6.1, TREB: 3.2 },
  'scout-sg-02': { PTS: 18.6, FGM: 6.8, FGA: 14.1, 'FG%': 48.1, MIN: 31.0, AST: 2.4, TREB: 4.0 },
  'scout-sf-03': { PTS: 11.3, FGM: 4.2, FGA: 9.6, 'FG%': 43.8, MIN: 26.1, AST: 1.8, TREB: 5.6 },
  'scout-pf-04': { PTS: 9.8, FGM: 3.9, FGA: 8.2, 'FG%': 47.6, MIN: 24.5, AST: 1.1, TREB: 8.4 },
  'scout-c-05': { PTS: 6.4, FGM: 2.6, FGA: 5.1, 'FG%': 50.9, MIN: 18.2, AST: 0.7, TREB: 6.9 },
};

function cc(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 12,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: false,
    session_type: 'in-season',
    cut_required: false,
    rankings: [{ team_id: OPP, natl_rank: 6, W: 18, L: 4, name: 'Four Corners' }],
  }, overrides || {});
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, opts) {
  const locked = opts && opts.locked;
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
      await fulfillJson(route, [
        { name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID },
        { name: 'Four Corners', display_name: 'Four Corners', object_id: OPP, _id: OPP },
      ]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.endsWith('/franchise/play-next-game')) {
      await fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four Corners',
        home_id: TID,
        away_id: OPP,
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data')) {
      await fulfillJson(route, {
        team_attributes: {
          offensive_efficiency: 6,
          defensive_efficiency: 4,
          fb_efficiency: 2,
          fb_opp_modifier: -8,
          pt_efficiency: 14,
          pt_opp_modifier: -2,
          discipline: 9,
          fight: 3,
          shot_threshold: 62,
          rebound_modifier: 48,
          team_chemistry: 18,
        },
        measures: MEASURES,
      });
      return;
    }
    if (pathname.startsWith('/franchise/scouting-report')) {
      await fulfillJson(route, {
        projected_starting_five: PROJECTED,
        player_season_stats: PLAYER_SEASON_STATS,
        play_usage_unlocked: !locked,
        fast_break_usage_unlocked: !locked,
        hct_usage_unlocked: !locked,
        plays: locked ? [] : [
          { name: '4-1 Motion', times_run: 86, successes: 46 },
          { name: '5-0 Flex', times_run: 64, successes: 31 },
          { name: 'Horns Flare', times_run: 41, successes: 22 },
          { name: 'Double Drag', times_run: 28, successes: 11 },
        ],
        fast_break_plays: locked ? [] : [{ name: 'Pitch Ahead', times_run: 19, successes: 12 }],
        hct_trap_plays: [],
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openScouting(page, locked) {
  await stubAuth(page);
  await installApi(page, { locked });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=scouting-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#scouting-view .opp-n', { timeout: 15000 });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('scouting view renders prep v2 layout', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);
  await expect(page.locator('#scouting-view .opp-n')).toHaveText('Four Corners');
  await expect(page.locator('#scouting-view .opp-rank-row').first()).toContainText('of 128');
  await expect(page.locator('#scouting-view .ms')).toHaveCount(8);
  await expect(page.locator('#scouting-view .agrid tbody tr')).toHaveCount(5);
  await expect(page.locator('#scouting-view .rtl b.rt-elite').first()).toBeVisible();
  await expect(page.locator('#scouting-hco-body tr')).toHaveCount(4);
  await expect(page.locator('#scouting-view .xt')).toHaveCount(0);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1280.png'), fullPage: true });
  await page.locator('#scouting-view [data-mode="stats"]').click();
  await page.screenshot({ path: path.join(OUT, 'scouting-stats-1280.png'), fullPage: true });
});

test('locked play usage shows N/A copy', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, true);
  await expect(page.locator('#scouting-hco-body')).toContainText('Film Study');
  await page.screenshot({ path: path.join(OUT, 'scouting-locked-1280.png'), fullPage: true });
});

test('scouting view at 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openScouting(page, false);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1920.png'), fullPage: true });
});
