const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const PLAN = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = PLAN.franchise_id;
const TEAM = 'Lancaster';
const SCOUT_FID = 'f-e2e-prep-scout';
const SCOUT_TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SCOUT_OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OUT = path.join(__dirname, '../../reports/retire-prep-embed');

const REPORT = {
  week: 12,
  upcoming_opponent: 'Four Corners',
  coaching_focus: {
    archetype: 'systems-coach',
    sub_option: 'systems-coach-offense',
    leaf_display_name: 'Offense',
  },
  players: [],
  player_changes: {},
  player_attribute_display_movements: {},
  exceptional_gains: [],
  team_attributes: {
    offensive_efficiency: 4,
    defensive_efficiency: 2,
    fb_efficiency: 1,
    fb_opp_modifier: -2,
    pt_efficiency: 6,
    pt_opp_modifier: -1,
    discipline: 3,
    fight: 2,
    shot_threshold: 0,
    rebound_modifier: 1,
    team_chemistry: 8,
    momentum_score: 5,
  },
  team_changes: {},
  plays_data: {},
  scouting_data: {},
  plays_effectiveness_changes: {},
  defenses_effectiveness_changes: {},
  projected_starting_five: [],
  training_notes: ['Camp week notes stay on the module path.'],
};

function fulfillJson(route, body) {
  return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

async function installPlanApi(page, extra) {
  const opts = extra || {};
  await page.route('**/*', async (route) => {
    const request = route.request();
    const method = request.method();
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
      return fulfillJson(route, {
        user_id: 'e2e-user',
        username: 'e2e',
        email: 'e2e@example.com',
        tutorial_state: { game_id: 'g-tut', step: 'training' },
      });
    }
    if (pathname === '/api/auth/tutorial-advance') return fulfillJson(route, { ok: true });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, PLAN.cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, PLAN.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, PLAN.trainingPoints);
    if (pathname === '/franchise/training-report') return fulfillJson(route, REPORT);
    if (pathname === '/franchise/league-news') return fulfillJson(route, PLAN.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, PLAN.standings);
    if (pathname === '/teams') return fulfillJson(route, PLAN.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, PLAN.roster);
    if (pathname === '/api/gameplan') return fulfillJson(route, PLAN.gameplan);
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, PLAN.preview);
    if (pathname === '/api/playbooks') {
      if (method === 'POST') return fulfillJson(route, { success: true, position_shot_weights: PLAN.preview.position_shot_weights });
      return fulfillJson(route, PLAN.playbooks);
    }
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      return fulfillJson(route, { ok: true });
    }
    return fulfillJson(route, {});
  });
}

async function installScoutApi(page) {
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
      return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    }
    if (pathname === '/app-config') {
      return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    }
    if (pathname === '/teams') {
      return fulfillJson(route, [
        { name: 'Lancaster', display_name: 'Lancaster', object_id: SCOUT_TID, _id: SCOUT_TID },
        { name: 'Four Corners', display_name: 'Four Corners', object_id: SCOUT_OPP, _id: SCOUT_OPP },
      ]);
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      return fulfillJson(route, {
        franchise_id: SCOUT_FID,
        team_id: SCOUT_TID,
        user_team_id: SCOUT_TID,
        team: 'Lancaster',
        week: 12,
        rank: 14,
        season: 1,
        current_season: 1,
        training_completed: false,
        session_type: 'in-season',
        cut_required: false,
        rankings: [{ team_id: SCOUT_OPP, natl_rank: 6, W: 18, L: 4, name: 'Four Corners' }],
      });
    }
    if (pathname.endsWith('/franchise/play-next-game')) {
      return fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four Corners',
        home_id: SCOUT_TID,
        away_id: SCOUT_OPP,
      });
    }
    if (pathname.startsWith('/franchise/team-data')) {
      return fulfillJson(route, {
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
        measures: [
          { key: 'shot_threshold', label: 'Shooting', rank: 12, rank_of: 128, percentile: 72, direction: 'lower_better' },
        ],
      });
    }
    if (pathname.startsWith('/franchise/scouting-report')) {
      return fulfillJson(route, {
        projected_starting_five: [
          {
            player_id: 'scout-pg-01',
            position: 'PG',
            name: 'Jordan Reyes',
            jersey: 4,
            year: 'sr',
            rt: 92,
            potential_rt_ratcheted: 95,
            attributes: { SC: 7, SH: 8, ID: 4, OD: 7, PS: 9, BH: 8, RB: 3, ST: 4, AG: 7, ND: 6, IQ: 7, FT: 7 },
          },
        ],
        player_season_stats: { 'scout-pg-01': { PTS: 14.2, FGM: 5.1, FGA: 10.8, 'FG%': 47.2, MIN: 28.4, AST: 6.1, TREB: 3.2 } },
        play_usage_unlocked: true,
        fast_break_usage_unlocked: true,
        hct_usage_unlocked: true,
        plays: [{ name: '4-1 Motion', times_run: 86, successes: 46 }],
        fast_break_plays: [{ name: 'Pitch Ahead', times_run: 19, successes: 12 }],
        hct_trap_plays: [],
      });
    }
    return fulfillJson(route, {});
  });
}

function fcc(tab, extra) {
  const q = new URLSearchParams({
    franchise_id: extra && extra.franchise_id ? extra.franchise_id : FID,
    team_id: extra && extra.team_id ? extra.team_id : TEAM,
    user_team_id: extra && extra.user_team_id ? extra.user_team_id : TEAM,
    mode: 'franchise',
    tab: tab,
    from: extra && extra.from ? extra.from : 'command_center',
  });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('in-app Training after', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installPlanApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('training-view'));
  await waitOverlay(page);
  await expect(page.locator('#training-view .slider, #training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, 'after-training-1280.png') });
});

test('in-app Training Report after', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installPlanApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('training-report-view', { week: '12', from: 'office', origin: 'office' }));
  await waitOverlay(page);
  await expect(page.locator('#training-report-view')).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, 'after-training-report-1280.png') });
});

test('in-app Game Plan after', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installPlanApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('game-plan-view'));
  await waitOverlay(page);
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, 'after-game-plan-1280.png') });
});

test('in-app Playbooks after', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installPlanApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('playbooks-view'));
  await waitOverlay(page);
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, 'after-playbooks-1280.png') });
});

test('in-app Scouting develop before', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE !== '1', 'after pass only');
  await stubAuth(page);
  await installScoutApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('scouting-view', {
    franchise_id: SCOUT_FID,
    team_id: SCOUT_TID,
    user_team_id: SCOUT_TID,
  }));
  await waitOverlay(page);
  await expect(page.locator('#scouting-view .opp-n')).toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: path.join(OUT, 'before-scouting-1280.png') });
});

test('in-app Scouting after', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installScoutApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?' + fcc('scouting-view', {
    franchise_id: SCOUT_FID,
    team_id: SCOUT_TID,
    user_team_id: SCOUT_TID,
  }));
  await waitOverlay(page);
  await expect(page.locator('#scouting-view .opp-n')).toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: path.join(OUT, 'after-scouting-1280.png') });
});

test('training.html mode=tutorial stays on the file', async ({ page }) => {
  test.skip(process.env.SCOUTING_BEFORE === '1', 'before capture only');
  await stubAuth(page);
  await installPlanApi(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&user_team_id=' + TEAM + '&mode=tutorial');
  await expect(page).toHaveURL(/training\.html/);
  await expect(page.locator('#submit-btn')).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: path.join(OUT, 'after-tutorial-1280.png') });
});
