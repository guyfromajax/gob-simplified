const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-train-follow';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/player-training-followup');

const ROSTER = [
  {
    player_id: 'p-roger',
    name: 'Roger Henrich',
    year: 'JR',
    height: 80,
    weight: 220,
    pos: 'C',
    training_position: 'C',
    training_focus: 'standard',
    resolved_training_position: 'C',
    resolved_training_focus: 'standard',
    position_ratings: { PG: 20, SG: 30, SF: 45, PF: 70, C: 82 },
    attrs: { SC: 40, SH: 40, ID: 60, OD: 70, PS: 30, BH: 30, RB: 80, ST: 80, AG: 40, ND: 50, IQ: 50, FT: 40 },
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
    rankings: [],
  }, overrides || {});
}

function points(overrides) {
  return Object.assign({
    training_points: 24,
    training_unavailable: false,
    is_first_training: false,
    is_camp_week: false,
    week: 12,
    season: 1,
    user_team_name: 'Lancaster',
    custom_focus_roster: ROSTER,
    position_tallies: { PG: 0, SG: 0, SF: 0, PF: 0, C: 1 },
    focus_tallies: { standard: 1, offensive: 0, defensive: 0, athletic: 0, fundamentals: 0, rebounding: 0 },
    player_maximizer_ranking_attrs: ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'],
    cpu_training_resume: null,
  }, overrides || {});
}

const REPORT = {
  week: 12,
  upcoming_opponent: 'Four Corners',
  coaching_focus: {},
  players: [],
  player_changes: {},
  team_attributes: {},
  team_changes: {},
  plays_data: {},
  scouting_data: {},
  training_notes: [],
};

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, opts) {
  const options = opts || {};
  const ccData = cc(options.cc);
  const pointsData = points(options.points);
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
      return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    }
    if (pathname.startsWith('/franchise/command-center/data')) return fulfillJson(route, ccData);
    if (pathname.startsWith('/franchise/training-points')) return fulfillJson(route, pointsData);
    if (pathname.startsWith('/franchise/training-report')) return fulfillJson(route, REPORT);
    if (pathname === '/franchise/player/development-focus' && request.method() === 'POST') {
      if (options.failSave) return fulfillJson(route, { detail: 'nope' }, 500);
      const body = request.postDataJSON() || {};
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    return fulfillJson(route, {});
  });
}

async function openFcc(page, tab, extra, opts) {
  await stubAuth(page);
  await installApi(page, opts);
  const bag = new URLSearchParams({
    franchise_id: FID,
    team_id: TID,
    tab: tab,
  });
  Object.keys(extra || {}).forEach((key) => bag.set(key, extra[key]));
  await page.goto('/franchise-command-center.html?' + bag.toString());
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('Player Training tab always shows the settings, even after a submitted week', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, 'training-view', null, { cc: { training_completed: true, week: 12 } });
  await expect(page.locator('#training-view.tab-content.active')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('#training-view #player-dev-section')).toBeVisible();
  await expect(page.locator('#training-view .devfocus-select').first()).toBeVisible();
  await expect(page.locator('#training-view .main-content-grid')).toBeHidden();
  await expect(page.locator('#training-view')).toContainText('Weekly training is set when you advance.');
  await expect(page.getByRole('tab', { name: 'Player Training', exact: true })).toHaveAttribute('aria-selected', 'true');
});

test('the report is a drill-in: no Player Training highlight, Back returns', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training-report.html?franchise_id=' + FID + '&team_id=' + TID
    + '&mode=franchise&week=12&from=office&origin=office');
  await expect(page).toHaveURL(/\/training-report\.html/);
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Back to Locker Room', exact: true })).toBeVisible();
  await expect(page.locator('html')).not.toHaveClass(/gob-office/);

  await page.screenshot({ path: path.join(OUT, 'training-report-drillin-1280.png') });
});

test('post-submit Continue to Office keeps tut_alert=training_return', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training-report.html?franchise_id=' + FID + '&team_id=' + TID
    + '&mode=franchise&week=12&from=training&origin=prep');
  const btn = page.getByRole('button', { name: 'Continue to Office', exact: true });
  await expect(btn).toBeVisible();

  const waitNav = page.waitForURL(/tut_alert=training_return/, { timeout: 15000 });
  await btn.click();
  await waitNav;
});

test('per-player change shows a Saved toast; a failure reverts', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, 'training-view');
  const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
  await expect(focus).toBeVisible({ timeout: 20000 });
  const before = await focus.inputValue();
  expect(before).toBe('standard');

  await focus.selectOption('offensive');
  await expect(page.locator('.gob-save-toast.is-on')).toHaveText('Saved', { timeout: 5000 });
  await expect(focus).toHaveValue('offensive');

  await page.screenshot({ path: path.join(OUT, 'player-save-toast-1280.png') });
});

test('a failed save toasts and reverts the select', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, 'training-view', null, { failSave: true });
  const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
  await expect(focus).toBeVisible({ timeout: 20000 });
  await expect(focus).toHaveValue('standard');
  await focus.selectOption('defensive');
  await expect(page.locator('.gob-save-toast.is-on')).toHaveText('Not saved. Try again.', { timeout: 5000 });
  await expect(focus).toHaveValue('standard');
});

test('after week 26 the settings stay, with no weekly allocation', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, 'training-view', null, {
    cc: { week: 28, training_disabled_for_postseason: true, training_completed: true },
    points: { week: 28, training_points: 0, training_unavailable: true },
  });
  await expect(page.locator('#training-view #player-dev-section')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('#training-view .devfocus-select').first()).toBeVisible();
  await expect(page.locator('#training-view .main-content-grid')).toBeHidden();
  await expect(page.locator('#requirements-bar')).toBeHidden();
  await expect(page.locator('#training-view')).not.toContainText('No team training during the tournament');
  await expect(page.locator('#play-now')).not.toHaveText(/Submit Training|Run Training Camp/);

  await page.screenshot({ path: path.join(OUT, 'post-week-26-1280.png') });
});

test('player training screenshot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, 'training-view');
  await expect(page.locator('#training-view .devfocus-select').first()).toBeVisible({ timeout: 20000 });
  await expect(page.locator('#training-state-note')).toBeHidden();
  await page.screenshot({ path: path.join(OUT, 'player-training-1280.png') });
});
