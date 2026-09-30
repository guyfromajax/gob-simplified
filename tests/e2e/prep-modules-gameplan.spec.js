const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/prep-modules-gameplan');
const BEFORE_PATH = path.join(OUT, 'before-metrics.json');
const CAPTURE_BEFORE = process.env.GAMEPLAN_BEFORE === '1';
const BEFORE = CAPTURE_BEFORE || !fs.existsSync(BEFORE_PATH)
  ? null
  : JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8'));

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

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, saves) {
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

function fccQuery(extra) {
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab: 'game-plan-view',
    from: 'command_center',
  });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

async function openInApp(page, extra) {
  await stubAuth(page);
  await installApi(page, []);
  await page.goto('/franchise-command-center.html?' + fccQuery(extra));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible({ timeout: 30000 });
}

async function openStandalone(page, extra) {
  await stubAuth(page);
  await installApi(page, extra && extra._saves);
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
  if (!(extra && extra.mode === 'tutorial')) {
    await expect(page.locator('#btn-save-game-plan[data-wired="1"]')).toBeVisible({ timeout: 15000 });
  }
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
      return { text: el.textContent.trim(), color: s.color, font: s.font, y: Math.round(b.y), h: Math.round(b.height) };
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
        border: ss.borderColor,
        w: Math.round(save.getBoundingClientRect().width),
        h: Math.round(save.getBoundingClientRect().height),
        text: save.textContent.trim(),
      } : null,
      toastHost: !!document.querySelector('#game-plan-view #toast'),
    };
  }, hostSel);
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('in-app 1280 / 1920 shots and geometry', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  const metrics1280 = await measurePlan(page, '#game-plan-view');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-app-1280.png`) });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible();
  const metrics1920 = await measurePlan(page, '#game-plan-view');
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-app-1920.png`) });
  if (CAPTURE_BEFORE) {
    fs.writeFileSync(BEFORE_PATH, JSON.stringify({ inApp1280: metrics1280, inApp1920: metrics1920 }, null, 2));
    return;
  }
  expect(metrics1280.toastHost).toBe(false);
  expect(metrics1280.tracks.length).toBe(BEFORE.inApp1280.tracks.length);
  metrics1280.tracks.forEach((track, i) => {
    expect(Math.abs(track.x - BEFORE.inApp1280.tracks[i].x)).toBeLessThanOrEqual(2);
    expect(Math.abs(track.w - BEFORE.inApp1280.tracks[i].w)).toBeLessThanOrEqual(2);
  });
  expect(metrics1280.execution.text).toBe('Execution');
  expect(metrics1280.transition.text).toBe('Transition');
  expect(samePaint(metrics1280.execution.color, BEFORE.inApp1280.execution.color)).toBe(true);
  expect(samePaint(metrics1280.transition.color, BEFORE.inApp1280.transition.color)).toBe(true);
  expect(samePaint(metrics1280.save.bg, BEFORE.inApp1280.save.bg)).toBe(true);
  expect(samePaint(metrics1280.save.color, BEFORE.inApp1280.save.color)).toBe(true);
  expect(metrics1920.tracks.length).toBe(BEFORE.inApp1920.tracks.length);
});

test('timeout 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, {
    resume_from_timeout: 'true',
    from: 'lineup',
    game_id: 'g-mid',
    quarter: '2',
  });
  await expect(page.locator('html')).toHaveClass(/gob-focus/);
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-timeout-1280.png`) });
  if (!CAPTURE_BEFORE) {
    expect(page.url()).toContain('resume_from_timeout=true');
    expect(page.url()).toContain('game-plan.html');
  }
});

test('tutorial 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial', game_id: 'g-tut', from: 'lineup' });
  await page.locator('.gob-modal, .sammy-modal, [data-sammy]').first().click({ timeout: 3000 }).catch(() => {});
  const gotIt = page.getByRole('button', { name: /GOT IT/i });
  if (await gotIt.count()) await gotIt.click();
  await expect(page.locator('#btn-tutorial-gameplan-continue')).toBeVisible({ timeout: 15000 });
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-tutorial-1280.png`) });
  if (!CAPTURE_BEFORE) {
    expect(page.url()).toContain('mode=tutorial');
    expect(page.url()).toContain('game-plan.html');
  }
});

test('the view does not fetch the old embed HTML', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const embeds = [];
  const loaders = [];
  const bridges = [];
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('game-plan.html')) embeds.push(url);
    if (url.includes('viewLoader.js')) loaders.push(url);
    if (url.includes('prepEmbed.js')) bridges.push(url);
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  expect(embeds).toEqual([]);
  expect(bridges).toEqual([]);
  expect(loaders.length).toBeGreaterThan(0);
  const clash = await page.evaluate(() => {
    const host = document.getElementById('game-plan-view');
    const dupes = [];
    host.querySelectorAll('[id]').forEach((el) => {
      const id = el.id;
      if (id && document.querySelectorAll('[id="' + CSS.escape(id) + '"]').length > 1) dupes.push(id);
    });
    if (host.querySelector('#toast')) dupes.push('toast-in-view');
    return dupes;
  });
  expect(clash).toEqual([]);
});

test('reopening keeps the panel and does not rebuild the shell', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  const token = await page.evaluate(() => {
    const host = document.getElementById('game-plan-view');
    host.dataset.keep = '1';
    return host.querySelector('.gpc') ? 'ok' : '';
  });
  expect(token).toBe('ok');
  await page.evaluate(() => {
    if (window.GOBViews && window.GOBViews.show) window.GOBViews.show('game-plan-view');
  });
  await expect(page.locator('#game-plan-view')).toHaveAttribute('data-keep', '1');
  await expect(page.locator('#game-plan-view .gpc')).toHaveCount(1);
  await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible();
});

test('timeout save leaves the plan and returns toward the court', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const saves = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, {
    resume_from_timeout: 'true',
    from: 'lineup',
    game_id: 'g-mid',
    quarter: '2',
    _saves: saves,
  });
  await page.locator('#slider-offense').focus();
  await page.keyboard.press('ArrowRight');
  const waitSave = page.waitForRequest((req) => req.url().includes('/api/gameplan') && req.method() === 'PUT', { timeout: 15000 });
  await page.getByRole('button', { name: 'Save Game Plan' }).click();
  await waitSave;
  await page.waitForURL(/court\.html|set-lineup\.html/, { timeout: 20000 });
  expect(saves).toEqual(['gameplan']);
});

test('tutorial PLAY NOW stays on the standalone path', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial', game_id: 'g-tut', from: 'lineup' });
  const gotIt = page.getByRole('button', { name: /GOT IT/i });
  if (await gotIt.count()) await gotIt.click();
  const cta = page.locator('#btn-tutorial-gameplan-continue');
  await expect(cta).toBeVisible({ timeout: 15000 });
  await cta.click();
  await page.waitForURL(/tutorial-situation\.html/, { timeout: 20000 });
});
