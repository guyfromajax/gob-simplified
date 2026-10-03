const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/gameplan-scouting-tokens');
const BEFORE_METRICS = path.join(__dirname, 'fixtures/gameplan-before-metrics.json');
const REPORT_METRICS = path.join(OUT, 'before-metrics.json');
const CAPTURE_BEFORE = process.env.GAMEPLAN_SCOUT_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';

const SCOUT_FID = 'f-e2e-prep-scout';
const SCOUT_TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SCOUT_OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function loadBefore() {
  if (CAPTURE_BEFORE) return null;
  if (fs.existsSync(BEFORE_METRICS)) return JSON.parse(fs.readFileSync(BEFORE_METRICS, 'utf8'));
  if (fs.existsSync(REPORT_METRICS)) return JSON.parse(fs.readFileSync(REPORT_METRICS, 'utf8'));
  return null;
}
const BEFORE = loadBefore();

function parseRgba(value) {
  const m = String(value).match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (!m) return null;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] == null ? 1 : Number(m[4]) };
}

function samePaint(actual, expected) {
  if (actual === expected) return true;
  const a = parseRgba(actual);
  const b = parseRgba(expected);
  if (!a || !b) return false;
  return Math.abs(a.r - b.r) <= 2 && Math.abs(a.g - b.g) <= 2
    && Math.abs(a.b - b.b) <= 2 && Math.abs(a.a - b.a) <= 0.02;
}

function orange(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.15) return false;
  return p.r > 200 && p.g > 100 && p.g < 190 && p.b < 80;
}

function green(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.15) return false;
  return p.g > 180 && p.r < 120 && p.b < 120;
}

function navy(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.15) return false;
  return p.b > p.r + 40 && p.b > 100 && p.r < 80;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installPlanApi(page, saves) {
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
        tutorial_state: { game_id: 'g-tut', step: 'situation' },
      });
    }
    if (pathname === '/api/auth/tutorial-advance') return fulfillJson(route, { ok: true });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, FIXTURE.cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, FIXTURE.trainingPoints);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/api/gameplan') {
      if (method === 'PUT') {
        if (saves) saves.push('gameplan');
        return fulfillJson(route, { success: true });
      }
      return fulfillJson(route, FIXTURE.gameplan);
    }
    return fulfillJson(route, {});
  });
}

function scoutCc() {
  return {
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
    next_game_summary: {
      week: 12,
      matchup_label: 'vs',
      opponent_team_id: SCOUT_OPP,
      opponent_team_name: 'Four Corners',
    },
  };
}

async function installScoutApi(page) {
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) {
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
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, scoutCc());
    if (pathname === '/franchise/play-next-game') {
      return fulfillJson(route, { error: 'scouting must not POST play-next-game' }, 500);
    }
    if (pathname === '/franchise/scouting-report') {
      return fulfillJson(route, {
        opponent_team_id: SCOUT_OPP,
        opponent_team_name: 'Four Corners',
        measures: [
          { key: 'shot_threshold', label: 'Shooting', rank: 12, rank_of: 128, percentile: 72, direction: 'lower_better' },
          { key: 'rebound_modifier', label: 'Rebounding', rank: 8, rank_of: 128, percentile: 88, direction: 'higher_better' },
          { key: 'team_chemistry', label: 'Chemistry', rank: 20, rank_of: 128, percentile: 55, value: 18, scale_max: 25, direction: 'higher_better' },
          { key: 'offensive_efficiency', label: 'Offense', rank: 30, rank_of: 128, percentile: 40, direction: 'higher_better' },
          { key: 'defensive_efficiency', label: 'Defense', rank: 18, rank_of: 128, percentile: 62, direction: 'higher_better' },
          { key: 'fb_efficiency', label: 'Fast Break', rank: 40, rank_of: 128, percentile: 35, direction: 'higher_better' },
          { key: 'fb_opp_modifier', label: 'Fast Break Defense', rank: 22, rank_of: 128, percentile: 58, direction: 'higher_better' },
          { key: 'pt_efficiency', label: 'P/T Defense', rank: 25, rank_of: 128, percentile: 50, direction: 'higher_better' },
          { key: 'pt_opp_modifier', label: 'P/T Offense', rank: 33, rank_of: 128, percentile: 42, direction: 'higher_better' },
          { key: 'discipline', label: 'Discipline', rank: 15, rank_of: 128, percentile: 70, direction: 'higher_better' },
          { key: 'fight', label: 'Fight', rank: 10, rank_of: 128, percentile: 80, direction: 'higher_better' },
        ],
        projected_starting_five: [
          {
            player_id: 'scout-pg-01', position: 'PG', name: 'Jordan Reyes', jersey: 4, year: 'sr',
            rt: 92, potential_rt_ratcheted: 95,
            attributes: { SC: 7, SH: 8, ID: 4, OD: 7, PS: 9, BH: 8, RB: 3, ST: 4, AG: 7, ND: 6, IQ: 7, FT: 7 },
          },
        ],
        play_usage: { half_court_offense: [], press: [], transition: [] },
        player_season_stats: {},
      });
    }
    return fulfillJson(route, {});
  });
}

async function resetScroll(page, sel) {
  await page.evaluate((hostSel) => {
    window.scrollTo(0, 0);
    const view = document.querySelector(hostSel);
    if (view) view.scrollTop = 0;
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
    document.querySelectorAll('.main, .main.scroll').forEach((el) => { el.scrollTop = 0; });
  }, sel);
}

async function capturePage(page, dest, hostSel) {
  await resetScroll(page, hostSel || '#game-plan-view');
  await page.screenshot({ path: dest });
}

async function openInApp(page) {
  await stubAuth(page);
  await installPlanApi(page, []);
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab: 'game-plan-view',
    from: 'command_center',
  });
  await page.goto('/franchise-command-center.html?' + q.toString());
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible({ timeout: 30000 });
}

async function openStandalone(page, extra) {
  await stubAuth(page);
  await installPlanApi(page, extra && extra._saves);
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    home: TEAM,
    away: 'Four-Corners',
    my_team: 'home',
    mode: extra && extra.mode ? extra.mode : 'franchise',
  });
  Object.keys(extra || {}).forEach((key) => {
    if (key === '_saves') return;
    q.set(key, extra[key]);
  });
  await page.goto('/game-plan.html?' + q.toString());
  await expect(page.locator('#slider-offense')).toBeVisible({ timeout: 30000 });
}

async function openScouting(page) {
  await stubAuth(page);
  await installScoutApi(page);
  await page.goto('/franchise-command-center.html?franchise_id=' + SCOUT_FID
    + '&team_id=' + SCOUT_TID + '&tab=scouting-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#scouting-view .opp-n', { timeout: 20000 });
}

async function measurePlan(page, hostSel) {
  return page.evaluate((sel) => {
    const host = document.querySelector(sel) || document.body;
    const tracks = [...host.querySelectorAll('.gt.strategy-slider')].map((el) => {
      const b = el.getBoundingClientRect();
      return {
        id: el.id,
        x: Math.round(b.left),
        w: Math.round(b.width),
        side: el.closest('section') ? el.closest('section').getAttribute('aria-label') : '',
      };
    });
    const header = (text) => {
      const el = [...host.querySelectorAll('.grp-h')].find((node) => node.textContent.trim() === text);
      if (!el) return null;
      const s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return { text: el.textContent.trim(), color: s.color, y: Math.round(b.y), h: Math.round(b.height) };
    };
    const save = document.getElementById('btn-save-game-plan');
    const ss = save ? getComputedStyle(save) : null;
    return {
      tracks,
      execution: header('Execution'),
      transition: header('Transition'),
      save: save && !save.hidden && save.style.display !== 'none' ? {
        bg: ss.backgroundColor,
        color: ss.color,
        w: Math.round(save.getBoundingClientRect().width),
        h: Math.round(save.getBoundingClientRect().height),
        text: save.textContent.trim(),
      } : null,
    };
  }, hostSel);
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('in-app default 1280 / 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  const metrics1280 = await measurePlan(page, '#game-plan-view');
  await capturePage(page, path.join(OUT, `${PREFIX}-in-app-1280.png`));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible();
  const metrics1920 = await measurePlan(page, '#game-plan-view');
  await capturePage(page, path.join(OUT, `${PREFIX}-in-app-1920.png`));
  if (CAPTURE_BEFORE) {
    fs.writeFileSync(REPORT_METRICS, JSON.stringify({ inApp1280: metrics1280, inApp1920: metrics1920 }, null, 2));
    return;
  }
  expect(BEFORE, 'geometry fixture missing').toBeTruthy();
  expect(metrics1280.tracks.length).toBe(BEFORE.inApp1280.tracks.length);
  metrics1280.tracks.forEach((track, i) => {
    expect(Math.abs(track.x - BEFORE.inApp1280.tracks[i].x), track.id + ' x').toBeLessThanOrEqual(2);
    expect(Math.abs(track.w - BEFORE.inApp1280.tracks[i].w), track.id + ' w').toBeLessThanOrEqual(2);
  });
  expect(metrics1280.execution.text).toBe('Execution');
  expect(metrics1280.transition.text).toBe('Transition');
  expect(samePaint(metrics1280.execution.color, BEFORE.inApp1280.execution.color)).toBe(true);
  expect(samePaint(metrics1280.transition.color, BEFORE.inApp1280.transition.color)).toBe(true);
  expect(metrics1920.tracks.length).toBe(BEFORE.inApp1920.tracks.length);
});

test('in-app unsaved + saved 1280', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  await page.locator('#game-plan-view #slider-offense').focus();
  await page.keyboard.press('ArrowRight');
  const save = page.locator('#btn-save-game-plan');
  await expect(save).toBeVisible();
  await capturePage(page, path.join(OUT, `${PREFIX}-unsaved-1280.png`));
  if (!CAPTURE_BEFORE) {
    const savePaint = await save.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(orange(savePaint)).toBe(true);
  }
  await save.click();
  const toast = page.locator('.gob-save-toast');
  await expect(toast).toHaveText('Game plan saved');
  await expect(toast).toBeVisible();
  await capturePage(page, path.join(OUT, `${PREFIX}-saved-1280.png`));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.locator('#game-plan-view #slider-tempo').focus();
  await page.keyboard.press('ArrowRight');
  await capturePage(page, path.join(OUT, `${PREFIX}-unsaved-1920.png`));
  await save.click();
  await expect(toast).toBeVisible();
  await capturePage(page, path.join(OUT, `${PREFIX}-saved-1920.png`));
});

test('timeout resume 1280', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, {
    resume_from_timeout: 'true',
    from: 'lineup',
    game_id: 'g-mid',
    quarter: '2',
  });
  await expect(page.locator('html')).toHaveClass(/gob-focus/);
  await capturePage(page, path.join(OUT, `${PREFIX}-timeout-1280.png`), 'body');
});

test('tutorial 1280', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial', game_id: 'g-tut', from: 'lineup' });
  const gotIt = page.getByRole('button', { name: /GOT IT/i });
  if (await gotIt.count()) await gotIt.click();
  await expect(page.locator('#btn-tutorial-gameplan-continue')).toBeVisible({ timeout: 15000 });
  await capturePage(page, path.join(OUT, `${PREFIX}-tutorial-1280.png`), 'body');
});

test('scouting in-app 1280 / 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page);
  await capturePage(page, path.join(OUT, `${PREFIX}-scouting-1280.png`), '#scouting-view');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#scouting-view .opp-n')).toBeVisible();
  await capturePage(page, path.join(OUT, `${PREFIX}-scouting-1920.png`), '#scouting-view');
});

test('computed styles: choice controls neutral, Save orange, square headshots', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  await page.locator('#game-plan-view #slider-offense').focus();
  await page.keyboard.press('ArrowRight');
  const paints = await page.evaluate(() => {
    const host = document.getElementById('game-plan-view');
    const paint = (el) => {
      if (!el) return { bg: '', color: '' };
      const s = getComputedStyle(el);
      return { bg: s.backgroundColor, color: s.color, radius: s.borderRadius };
    };
    const knob = paint(host.querySelector('.gt-k'));
    const nest = paint(host.querySelector('.slider-nest__info'));
    const save = paint(document.getElementById('btn-save-game-plan'));
    const labels = [...host.querySelectorAll('.gt-l.on')].slice(0, 3).map((el) => paint(el));
    return { knob, nest, save, labels };
  });
  expect(orange(paints.knob.bg) || green(paints.knob.bg)).toBe(false);
  expect(navy(paints.knob.bg)).toBe(false);
  expect(orange(paints.nest.color) || green(paints.nest.color)).toBe(false);
  expect(orange(paints.save.bg)).toBe(true);
  paints.labels.forEach((label) => {
    expect(orange(label.color) || green(label.color)).toBe(false);
  });

  await openScouting(page);
  const head = await page.evaluate(() => {
    const av = document.querySelector('#scouting-view .av');
    if (!av) return null;
    const s = getComputedStyle(av);
    const b = av.getBoundingClientRect();
    const radius = parseFloat(s.borderRadius) || 0;
    return { w: Math.round(b.width), h: Math.round(b.height), radius };
  });
  expect(head).toBeTruthy();
  expect(Math.abs(head.w - head.h)).toBeLessThanOrEqual(1);
  expect(head.radius).toBeLessThanOrEqual(head.w / 4);
});

test('handoff frames', async ({ page }) => {
  const base = process.env.FRAMES_BASE;
  test.skip(!base, 'FRAMES_BASE not set');
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(base + '/design_handoff_prep_v2/frames/prep-game-plan-1280.html');
  await page.waitForSelector('.gpc, .gt', { timeout: 15000 });
  await capturePage(page, path.join(OUT, 'frame-game-plan-v2-1280.png'), 'body');
  await page.goto(base + '/design_handoff_prep/frames/prep-game-plan-1280.html');
  await page.waitForSelector('.gpc, .gt, .set, .save', { timeout: 15000 });
  await capturePage(page, path.join(OUT, 'frame-game-plan-v1-1280.png'), 'body');
  await page.goto(base + '/design_handoff_prep_v2/frames/prep-scouting-1280.html');
  await page.waitForSelector('.opp-n, .pv, .sc', { timeout: 15000 });
  await capturePage(page, path.join(OUT, 'frame-scouting-v2-1280.png'), 'body');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(base + '/design_handoff_prep_v2/frames/prep-scouting-1920.html');
  await page.waitForSelector('.opp-n, .pv, .sc', { timeout: 15000 });
  await capturePage(page, path.join(OUT, 'frame-scouting-v2-1920.png'), 'body');
});
