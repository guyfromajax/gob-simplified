const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/prep-modules-training');
const TOKENS_OUT = path.join(__dirname, '../../reports/prep-training-tokens');

function alsoTokenShot(name) {
  if (CAPTURE_BEFORE) return;
  fs.mkdirSync(TOKENS_OUT, { recursive: true });
  const src = path.join(OUT, name);
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(TOKENS_OUT, name));
}
const BEFORE_PATH = path.join(OUT, 'before-metrics.json');
const CAPTURE_BEFORE = process.env.TRAINING_BEFORE === '1';
const BEFORE = CAPTURE_BEFORE || !fs.existsSync(BEFORE_PATH)
  ? null
  : JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8'));

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

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

function postWeek26Points() {
  const points = clone(FIXTURE.trainingPoints);
  points.week = 28;
  points.training_points = 0;
  points.training_unavailable = true;
  points.is_camp_week = false;
  return points;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, extra) {
  const opts = extra || {};
  const cc = opts.cc || inSeasonCc();
  const points = opts.points || inSeasonPoints();
  const submits = opts._submits;
  const report = {
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
  };
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
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, points);
    if (pathname === '/franchise/training-report') return fulfillJson(route, report);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      if (opts.failSave) return fulfillJson(route, { detail: 'nope' }, 500);
      const body = request.postDataJSON() || {};
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    if (pathname === '/franchise/run-training/user' && method === 'POST') {
      if (submits) submits.push('user');
      return fulfillJson(route, { status: 'success' });
    }
    if (pathname === '/franchise/run-training/cpu-train' && method === 'POST') {
      if (submits) submits.push('cpu');
      return fulfillJson(route, {
        status: 'success',
        redirect: '/training-report.html?franchise_id=' + FID + '&week=' + String(cc.week || 12) + '&from=training',
      });
    }
    return fulfillJson(route, {});
  });
}

function fccQuery(tab, extra) {
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab: tab,
    from: 'command_center',
  });
  Object.keys(extra || {}).forEach((key) => {
    if (key[0] === '_') return;
    q.set(key, extra[key]);
  });
  return q.toString();
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

async function openInApp(page, extra) {
  const opts = extra || {};
  await stubAuth(page);
  await installApi(page, opts);
  await page.goto('/franchise-command-center.html?' + fccQuery('training-view', opts));
  await waitOverlay(page);
}

async function openStandalone(page, extra) {
  const opts = extra || {};
  await stubAuth(page);
  await installApi(page, opts);
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: opts.mode || 'tutorial',
  });
  Object.keys(opts).forEach((key) => {
    if (key[0] === '_') return;
    if (typeof opts[key] !== 'string' && typeof opts[key] !== 'number') return;
    q.set(key, String(opts[key]));
  });
  await page.goto('/training.html?' + q.toString());
}

async function waitPlayerDev(page) {
  await expect(page.locator('#training-view .pdg-grid, #training-view .devfocus-select').first()).toBeVisible({ timeout: 30000 });
}

async function waitAllocation(page) {
  await expect(page.locator('body.training-weekly .slider, body.training-weekly .ps, .training-page .slider').first()).toBeVisible({ timeout: 30000 });
}

async function measureTraining(page, hostSel) {
  return page.evaluate((sel) => {
    const host = document.querySelector(sel) || document.body;
    const tracks = [...host.querySelectorAll('.slider-container')].slice(0, 6).map((el) => {
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.left), w: Math.round(b.width), y: Math.round(b.top) };
    });
    const pill = document.getElementById('requirements-bar');
    const pb = pill ? pill.getBoundingClientRect() : null;
    const ps = pill ? getComputedStyle(pill) : null;
    const tools = document.querySelector('.pg-tools');
    const tb = tools ? tools.getBoundingClientRect() : null;
    const advance = document.getElementById('play-now');
    const as = advance ? getComputedStyle(advance) : null;
    const modal = document.getElementById('custom-focus-modal');
    const mb = modal ? modal.getBoundingClientRect() : null;
    const ms = modal ? getComputedStyle(modal) : null;
    return {
      tracks,
      pill: pb ? {
        x: Math.round(pb.left),
        y: Math.round(pb.top),
        w: Math.round(pb.width),
        h: Math.round(pb.height),
        bg: ps.backgroundColor,
        display: ps.display,
      } : null,
      tools: tb ? { x: Math.round(tb.left), y: Math.round(tb.top), w: Math.round(tb.width) } : null,
      advance: advance ? {
        text: advance.textContent.trim(),
        bg: as.backgroundColor,
        color: as.color,
      } : null,
      modal: modal ? {
        display: ms.display,
        x: Math.round(mb.left),
        y: Math.round(mb.top),
        w: Math.round(mb.width),
      } : null,
      submitInView: !!(host.querySelector('#submit-btn') && !host.querySelector('#submit-btn').hidden),
      noteHidden: !!(host.querySelector('#training-state-note') && host.querySelector('#training-state-note').hidden),
    };
  }, hostSel);
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('in-season 1280 / 1920 shots and geometry', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  await waitPlayerDev(page);
  const metrics1280 = await measureTraining(page, '#training-view');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-season-1280.png`) });
  alsoTokenShot(`${prefix}-in-season-1280.png`);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#training-view .pdg-grid, #training-view .devfocus-select').first()).toBeVisible();
  const metrics1920 = await measureTraining(page, '#training-view');
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-season-1920.png`) });
  alsoTokenShot(`${prefix}-in-season-1920.png`);
  if (CAPTURE_BEFORE) {
    const bag = fs.existsSync(BEFORE_PATH) ? JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8')) : {};
    bag.inSeason1280 = metrics1280;
    bag.inSeason1920 = metrics1920;
    fs.writeFileSync(BEFORE_PATH, JSON.stringify(bag, null, 2));
    return;
  }
  expect(metrics1280.submitInView).toBe(false);
  await expect(page.locator('#training-view .main-content-grid')).toBeHidden();
  await expect(page.locator('#training-view .coaching-section')).toBeHidden();
  await expect(page.locator('#training-view .slider').first()).toBeHidden();
  await expect(page.locator('#training-view')).toContainText('Weekly training is set when you advance.');
});

test('camp week 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page, { cc: campCc(), points: campPoints() });
  await waitPlayerDev(page);
  const metrics = await measureTraining(page, '#training-view');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-camp-1280.png`) });
  alsoTokenShot(`${prefix}-camp-1280.png`);
  if (CAPTURE_BEFORE) {
    const bag = fs.existsSync(BEFORE_PATH) ? JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8')) : {};
    bag.camp1280 = metrics;
    fs.writeFileSync(BEFORE_PATH, JSON.stringify(bag, null, 2));
    return;
  }
  expect(metrics.submitInView).toBe(false);
  await expect(page.locator('#training-view .pdg-grid, #training-view .devfocus-select').first()).toBeVisible();
});

test('post-week-26 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page, { cc: postWeek26Cc(), points: postWeek26Points() });
  await expect(page.locator('#training-view .pdg-grid, #training-view .devfocus-select').first()).toBeVisible({ timeout: 30000 });
  const metrics = await measureTraining(page, '#training-view');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-post-week-26-1280.png`) });
  alsoTokenShot(`${prefix}-post-week-26-1280.png`);
  if (CAPTURE_BEFORE) {
    const bag = fs.existsSync(BEFORE_PATH) ? JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8')) : {};
    bag.postWeek26 = metrics;
    fs.writeFileSync(BEFORE_PATH, JSON.stringify(bag, null, 2));
    return;
  }
  await expect(page.locator('#training-view')).not.toContainText('No team training during the tournament');
  expect(page.locator('#play-now')).not.toHaveText(/Submit Training|Run Training Camp/);
  await expect(page.locator('#training-view #player-dev-section')).toBeVisible();
  await expect(page.locator('#training-view .main-content-grid')).toBeHidden();
});

test('tutorial 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial' });
  await expect(page.locator('.slider, .ps').first()).toBeVisible({ timeout: 30000 });
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-tutorial-1280.png`) });
  alsoTokenShot(`${prefix}-tutorial-1280.png`);
  if (!CAPTURE_BEFORE) {
    expect(page.url()).toContain('training.html');
    expect(page.url()).toContain('mode=tutorial');
    await expect(page.locator('#submit-btn')).toBeVisible();
  }
});

test('custom-focus modal 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'franchise', session_type: 'in-season' });
  await waitAllocation(page);
  await page.locator('.archetype-option:has(input[value="player-maximizer-choose-attributes"])').click();
  await expect(page.locator('#custom-focus-modal')).toBeVisible({ timeout: 10000 });
  const metrics = await measureTraining(page, 'body');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-custom-focus-1280.png`) });
  alsoTokenShot(`${prefix}-custom-focus-1280.png`);
  if (CAPTURE_BEFORE) {
    const bag = fs.existsSync(BEFORE_PATH) ? JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8')) : {};
    bag.customFocus = metrics;
    fs.writeFileSync(BEFORE_PATH, JSON.stringify(bag, null, 2));
    return;
  }
  expect(metrics.modal.display).not.toBe('none');
});

test('the view does not fetch the old embed HTML', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const embeds = [];
  const loaders = [];
  const bridges = [];
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('training.html')) embeds.push(url);
    if (url.includes('viewLoader.js')) loaders.push(url);
    if (url.includes('prepEmbed.js')) bridges.push(url);
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  await waitPlayerDev(page);
  expect(embeds).toEqual([]);
  expect(bridges).toEqual([]);
  expect(loaders.length).toBeGreaterThan(0);
  const clash = await page.evaluate(() => {
    const host = document.getElementById('training-view');
    const dupes = [];
    host.querySelectorAll('[id]').forEach((el) => {
      const id = el.id;
      if (id && document.querySelectorAll('[id="' + CSS.escape(id) + '"]').length > 1) dupes.push(id);
    });
    const submit = host.querySelector('#submit-btn');
    if (submit && !submit.hidden) dupes.push('submit-btn-in-view');
    return dupes;
  });
  expect(clash).toEqual([]);
});

test('reopening keeps the panel and does not rebuild the shell', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  await waitPlayerDev(page);
  const token = await page.evaluate(() => {
    const host = document.getElementById('training-view');
    host.dataset.keep = '1';
    return host.querySelector('.training-container, #player-dev-section') ? 'ok' : '';
  });
  expect(token).toBe('ok');
  await page.evaluate(() => {
    if (window.GOBViews && window.GOBViews.show) window.GOBViews.show('training-view');
  });
  await expect(page.locator('#training-view')).toHaveAttribute('data-keep', '1');
  await expect(page.locator('#training-view .training-container')).toHaveCount(1);
  await expect(page.locator('#training-view #player-dev-section')).toBeVisible();
});

test('submit lands on the Training Report drill-in', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const submits = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'franchise', session_type: 'in-season', _submits: submits });
  await waitAllocation(page);
  await page.locator('.archetype-option:has(input[value="authoritarian-discipline"])').click();
  await page.evaluate(() => {
    document.querySelectorAll('.slider').forEach((el, i) => {
      el.value = i === 0 ? '5' : (i < 5 ? '4' : (i === 5 ? '3' : '0'));
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 10000 });
  await page.locator('#submit-btn').click();
  await page.waitForURL(/tab=training-report-view/, { timeout: 20000 });
  await expect(page.getByRole('button', { name: 'Back to Office', exact: true })).toBeVisible({ timeout: 20000 });
  expect(new URL(page.url()).searchParams.get('tut_alert') || '').toBe('');
  expect(submits).toContain('user');
  expect(submits).toContain('cpu');
});

test('camp-week Advance label stays the camp override', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page, { cc: campCc(), points: campPoints() });
  await waitPlayerDev(page);
  const label = await page.locator('#play-now').innerText();
  expect(label).toMatch(/Run Training Camp|Run Training/);
  const submit = page.locator('#training-view #submit-btn');
  if (await submit.count()) await expect(submit).toBeHidden();
});

test('draft survives leave and reload', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'franchise', session_type: 'in-season' });
  await waitAllocation(page);
  const first = page.locator('.slider').first();
  await first.evaluate((el) => {
    el.value = '3';
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.reload();
  await waitAllocation(page);
  await expect(page.locator('.slider').first()).toHaveValue('3');
});

test('per-player change shows a Saved toast', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
  await expect(focus).toBeVisible({ timeout: 30000 });
  await focus.selectOption('offensive');
  await expect(page.locator('.gob-save-toast.is-on')).toHaveText('Saved', { timeout: 5000 });
});

test('tutorial path stays on the standalone file', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial' });
  expect(page.url()).toContain('training.html');
  expect(page.url()).toContain('mode=tutorial');
  await expect(page.locator('#submit-btn')).toBeVisible();
  await expect(page.locator('.slider, .ps').first()).toBeVisible();
});
