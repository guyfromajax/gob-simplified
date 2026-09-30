const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/training-advance-focus');
const CAPTURE_BEFORE = process.env.TRAINING_ADVANCE_BEFORE === '1';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function inSeasonCc() {
  const cc = clone(FIXTURE.cc);
  cc.week = 12;
  cc.session_type = 'in-season';
  cc.training_completed = false;
  cc.training_disabled_for_postseason = false;
  cc.training_disabled_for_eos = false;
  return cc;
}

function inSeasonPoints() {
  const points = clone(FIXTURE.trainingPoints);
  points.week = 12;
  points.is_camp_week = false;
  points.is_first_training = false;
  points.training_points = 24;
  points.training_unavailable = false;
  return points;
}

function campCc() {
  return clone(FIXTURE.cc);
}

function campPoints() {
  return clone(FIXTURE.trainingPoints);
}

function postWeek26Cc() {
  const cc = clone(FIXTURE.cc);
  cc.week = 28;
  cc.session_type = 'in-season';
  cc.training_completed = true;
  cc.training_disabled_for_postseason = true;
  return cc;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, extra) {
  const opts = extra || {};
  const cc = opts.cc || inSeasonCc();
  const points = opts.points || inSeasonPoints();
  const submits = opts._submits;
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
      return fulfillJson(route, Object.assign({
        user_id: 'e2e-user',
        username: 'e2e',
        email: 'e2e@example.com',
        tutorial_state: { game_id: 'g-tut', step: 'situation' },
      }, opts.me || {}));
    }
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, points);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      const body = request.postDataJSON() || {};
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    if (pathname === '/franchise/run-training/user') {
      if (submits) submits.push({ kind: 'user', body: request.postData() });
      return fulfillJson(route, { status: 'success' });
    }
    if (pathname === '/franchise/run-training/cpu-train') {
      if (submits) submits.push({ kind: 'cpu' });
      return fulfillJson(route, {
        status: 'success',
        redirect: '/training-report.html?mode=franchise&franchise_id=' + FID + '&from=training',
      });
    }
    if (pathname === '/franchise/play-next-game') {
      return fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four-Corners',
        week: cc.week,
        home_id: TEAM,
        away_id: 'Four-Corners',
      });
    }
    if (pathname === '/franchise/training-report') {
      return fulfillJson(route, {
        week: cc.week || 12,
        upcoming_opponent: 'Four Corners',
        coaching_focus: {},
        players: [],
        player_changes: {},
        team_attributes: {},
        team_changes: {},
        plays_data: {},
        scouting_data: {},
        training_notes: [],
      });
    }
    return fulfillJson(route, {});
  });
}

async function resetScroll(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
    document.querySelectorAll('.main, .main.scroll').forEach((el) => { el.scrollTop = 0; });
  });
}

async function capturePage(page, dest) {
  await resetScroll(page);
  await page.screenshot({ path: dest });
}

function fccQuery(tab) {
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab: tab,
    from: 'command_center',
  });
  return q.toString();
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

async function openOffice(page, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/franchise-command-center.html?' + fccQuery('home-tab'));
  await waitOverlay(page);
}

async function openPrepTraining(page, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/franchise-command-center.html?' + fccQuery('training-view'));
  await waitOverlay(page);
}

async function allocateClassic24(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.slider').forEach((el, i) => {
      el.value = i === 0 ? '5' : (i < 5 ? '4' : (i === 5 ? '3' : '0'));
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  await page.locator('label.archetype-option', { hasText: 'Discipline' }).click();
}

const EXPECTED_USER_BODY = {
  franchise_id: FID,
  team_id: '69a6fcb68d2c56aa82e48a54',
  training_data: {
    player_drills: {
      offense: { inside: 5, outside: 4 },
      defense: { inside: 4, outside: 4 },
      technical: { passing: 4, ball_handling: 3, rebounding: 0 },
      weight_room: { strength: 0, agility: 0 },
    },
    team_drills: {
      team_offense: { install: 0 },
      team_defense: { install: 0 },
      fast_breaks: { offense_install: 0, defense_install: 0 },
      scrimmages: 0,
      presses_traps: { defense_install: 0, offense_install: 0 },
    },
    general: { conditioning: 0, free_throws: 0, film_study: 0, breaks: 0 },
    coaching_focus: 'authoritarian-discipline',
    playbook_training_mode: 'current-playbooks',
    training_playbook_focus: null,
  },
};

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('today or new flow shots 1280 / 1920', async ({ page }) => {
  test.skip(!CAPTURE_BEFORE, 'before-only capture');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openPrepTraining(page);
  await expect(page.locator('#training-view .slider, #training-view .pdg-grid, body.training-page .slider').first()).toBeVisible({ timeout: 30000 });
  await capturePage(page, path.join(OUT, 'before-prep-player-training-1280.png'));
  await capturePage(page, path.join(OUT, 'before-flow-in-app-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await resetScroll(page);
  await capturePage(page, path.join(OUT, 'before-prep-player-training-1920.png'));
});

test('a) training week Advance → focus → allocate → Submit → Report → Office', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  const submits = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { _submits: submits });
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs')).toHaveCount(0);
  await expect(page.locator('#play-now.advance')).toHaveCount(0);
  await expect(page.locator('#back-btn')).toHaveText('Back to Locker Room');
  await expect(page.locator('#submit-btn')).toHaveText('Submit Training');
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('#player-dev-section')).toBeHidden();
  await capturePage(page, path.join(OUT, 'after-focus-default-1280.png'));

  await allocateClassic24(page);
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 10000 });
  await capturePage(page, path.join(OUT, 'after-focus-allocated-unsaved-1280.png'));

  await page.locator('#submit-btn').click();
  await page.waitForURL(/tab=training-report-view/, { timeout: 20000 });
  await expect(page.getByRole('button', { name: 'Back to Office', exact: true })).toBeVisible({ timeout: 20000 });
  await capturePage(page, path.join(OUT, 'after-submit-report-1280.png'));
  await page.getByRole('button', { name: 'Back to Office', exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname, { timeout: 20000 }).toBe('/franchise-command-center.html');

  const user = submits.find((row) => row.kind === 'user');
  expect(user).toBeTruthy();
  expect(JSON.parse(user.body)).toEqual(EXPECTED_USER_BODY);
});

test('a) focus page at 1920 and Set Lineup chrome compare', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await capturePage(page, path.join(OUT, 'after-focus-default-1920.png'));

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/set-lineup.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TEAM
    + '&week=12&home=Lancaster&away=Four-Corners&home_id=' + TEAM + '&away_id=Four-Corners&my_team=home');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await capturePage(page, path.join(OUT, 'after-set-lineup-chrome-1280.png'));
});

test('b) Prep › Player Training is player-dev only and edits save', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openPrepTraining(page);
  await expect(page.locator('#training-view .devfocus-select').first()).toBeVisible({ timeout: 30000 });
  const hidden = await page.evaluate(() => {
    const host = document.getElementById('training-view');
    const vis = (sel) => {
      const el = host.querySelector(sel);
      if (!el) return false;
      const s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && !el.hidden;
    };
    return {
      sliders: vis('.main-content-grid'),
      coaching: vis('.coaching-section'),
      req: vis('#requirements-bar'),
      auto: vis('#auto-train-btn'),
      submit: vis('#submit-btn'),
      pointer: (host.textContent || '').includes('Weekly training is set when you advance.'),
    };
  });
  expect(hidden.sliders).toBe(false);
  expect(hidden.coaching).toBe(false);
  expect(hidden.req).toBe(false);
  expect(hidden.auto).toBe(false);
  expect(hidden.submit).toBe(false);
  expect(hidden.pointer).toBe(true);
  await expect(page.locator('#gob-subtabs .tb[aria-selected="true"] .tb-l')).toHaveText('Player Training');
  const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
  await focus.selectOption('offensive');
  await expect(page.locator('.gob-save-toast.is-on')).toHaveText('Saved', { timeout: 5000 });
  await capturePage(page, path.join(OUT, 'after-prep-player-training-1280.png'));
});

test('c) post-week-26 Advance skips the training page', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { cc: postWeek26Cc() });
  await expect(page.locator('#play-now')).not.toHaveText(/Run Training|Submit Training|Run Training Camp/);
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', /play|sim-rest-tournament|new-season/);
  await page.locator('#play-now').click();
  await page.waitForTimeout(800);
  expect(page.url()).not.toContain('/training.html');
});

test('d) camp week 1 Advance opens the focus page', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { cc: campCc(), points: campPoints() });
  await expect(page.locator('#play-now')).toHaveText(/Run Training Camp|Run Training/);
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await expect(page.url()).toContain('session_type=preseason');
});

test('e) tutorial path stays weekly focus on training.html', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=tutorial');
  await expect(page).toHaveURL(/training\.html/);
  await expect(page).toHaveURL(/mode=tutorial/);
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#submit-btn')).toBeVisible();
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('#player-dev-section')).toBeHidden();
  await capturePage(page, path.join(OUT, 'after-tutorial-1280.png'));
});

test('f) leave-confirm on unsaved allocation; clean Back just leaves', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });

  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('.slider').first()).toBeVisible({ timeout: 30000 });
  await page.locator('.slider').first().evaluate((el) => {
    el.value = '2';
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toBeVisible({ timeout: 10000 });
  await page.locator('.gob-leave-confirm [data-leave="stay"]').click();
  await expect(page).toHaveURL(/\/training\.html/);
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toBeVisible();
  await page.locator('.gob-leave-confirm [data-leave="discard"]').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
});

test('g) desktop profile uses the same Advance → focus path', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.addInitScript(() => {
    window.GOB_BUILD_PROFILE = 'desktop';
    if (window.location && window.location.port) {
      window.GOB_LOOPBACK_PORT = Number(window.location.port);
    }
    window.__gobAuthMeData = {
      user_id: 'e2e-user',
      username: 'e2e',
      email: 'e2e@example.com',
      tutorial_alerts_franchise_id: 'other-franchise',
      tutorial_alerts_dismissed: [
        'player-attributes', 'training', 'team-attributes', 'game-plans',
        'playbooks', 'scouting', 'recruiting',
      ],
    };
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { me: { tutorial_alerts_franchise_id: 'other-franchise' } });
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  const later = page.getByRole('button', { name: /do this later/i });
  try {
    await later.waitFor({ state: 'visible', timeout: 2500 });
    await later.click();
  } catch (err) { /* no tutorial intercept */ }
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#submit-btn')).toHaveText('Submit Training');
});
