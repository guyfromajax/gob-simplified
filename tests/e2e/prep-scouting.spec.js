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

const PROJECTED = [
  {
    position: 'PG',
    name: 'Jordan Reyes',
    jersey: 4,
    year: 'sr',
    rt: 92,
    potential_rt_ratcheted: 95,
    attributes: { SC: 7, SH: 8, ID: 4, OD: 7, PS: 9, BH: 8, RB: 3, ST: 4, AG: 8, ND: 7, IQ: 8, FT: 7 },
  },
  {
    position: 'SG',
    name: 'Chris Molina',
    jersey: 12,
    year: 'jr',
    rt: 84,
    potential_rt_ratcheted: 84,
    attributes: { SC: 9, SH: 10, ID: 3, OD: 6, PS: 5, BH: 6, RB: 4, ST: 4, AG: 7, ND: 6, IQ: 6, FT: 8 },
  },
];

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
        player_season_stats: {},
        play_usage_unlocked: !locked,
        fast_break_usage_unlocked: !locked,
        hct_usage_unlocked: !locked,
        plays: locked ? [] : [{ name: '4-1 Motion', times_run: 86, successes: 46 }],
        fast_break_plays: [],
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
  await expect(page.locator('#scouting-view .xt')).toHaveCount(0);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1280.png') });
  await page.locator('#scouting-view [data-mode="stats"]').click();
  await page.screenshot({ path: path.join(OUT, 'scouting-stats-1280.png') });
});

test('locked play usage shows N/A copy', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, true);
  await expect(page.locator('#scouting-hco-body')).toContainText('Film Study');
  await page.screenshot({ path: path.join(OUT, 'scouting-locked-1280.png') });
});

test('scouting view at 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openScouting(page, false);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1920.png') });
});
