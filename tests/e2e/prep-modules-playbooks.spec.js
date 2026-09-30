const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/prep-modules-playbooks');
const BEFORE_PATH = path.join(OUT, 'before-metrics.json');
const CAPTURE_BEFORE = process.env.PLAYBOOKS_BEFORE === '1';
const BEFORE = CAPTURE_BEFORE || !fs.existsSync(BEFORE_PATH)
  ? null
  : JSON.parse(fs.readFileSync(BEFORE_PATH, 'utf8'));

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function playbooksWithCmd() {
  const pb = clone(FIXTURE.playbooks);
  const cmd = {};
  pb.set_plays.forEach((play, i) => { cmd[play.play_id] = 30 + ((i * 37) % 61); });
  ['set_plays', 'set_play_inside', 'set_play_attack', 'set_play_outside'].forEach((key) => {
    (pb[key] || []).forEach((play) => { play.effectiveness = cmd[play.play_id]; });
  });
  pb.set_plays.reverse();
  return pb;
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

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, saves) {
  const playbooks = playbooksWithCmd();
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
    if (pathname === '/api/gameplan') return fulfillJson(route, FIXTURE.gameplan);
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') {
      if (method === 'POST') {
        if (saves) saves.push('playbooks');
        return fulfillJson(route, { success: true, position_shot_weights: FIXTURE.preview.position_shot_weights });
      }
      return fulfillJson(route, playbooks);
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
    tab: 'playbooks-view',
    from: 'command_center',
  });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

async function openInApp(page, extra) {
  await stubAuth(page);
  await installApi(page, extra && extra._saves);
  await page.goto('/franchise-command-center.html?' + fccQuery(extra));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible({ timeout: 30000 });
}

async function openStandalone(page, extra) {
  await stubAuth(page);
  await installApi(page, extra && extra._saves);
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: extra && extra.mode ? extra.mode : 'franchise',
  });
  Object.keys(extra || {}).forEach((key) => {
    if (key === '_saves') return;
    q.set(key, extra[key]);
  });
  await page.goto('/playbooks.html?' + q.toString());
  await expect(page.locator('.play').first()).toBeVisible({ timeout: 30000 });
}

async function measurePlaybooks(page, hostSel) {
  return page.evaluate((sel) => {
    const host = document.querySelector(sel) || document.body;
    const tracks = [...host.querySelectorAll('.wb.et-slider')].slice(0, 6).map((el) => {
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.left), w: Math.round(b.width), y: Math.round(b.top) };
    });
    const groups = [...host.querySelectorAll('.psw-group')];
    const divider = groups[1] ? getComputedStyle(groups[1]).boxShadow : '';
    const toggle = host.querySelector('.playbooks-side-row .playbooks-tabs');
    const tb = toggle ? toggle.getBoundingClientRect() : null;
    const save = document.getElementById('save-btn');
    const ss = save ? getComputedStyle(save) : null;
    const lock = host.querySelector('#set-plays-grid .play [data-lock]');
    const live = host.querySelector('.psw-live-pill');
    return {
      tracks,
      divider,
      toggle: tb ? { x: Math.round(tb.left), y: Math.round(tb.top), w: Math.round(tb.width) } : null,
      save: save ? {
        bg: ss.backgroundColor,
        color: ss.color,
        border: ss.borderColor,
        w: Math.round(save.getBoundingClientRect().width),
        h: Math.round(save.getBoundingClientRect().height),
        text: save.textContent.trim(),
      } : null,
      lockVisible: !!(lock && lock.offsetParent),
      liveCount: live ? 1 : 0,
      toastHost: !!document.querySelector('#playbooks-view #toast'),
    };
  }, hostSel);
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('in-app 1280 / 1920 shots and geometry', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  const metrics1280 = await measurePlaybooks(page, '#playbooks-view');
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-app-1280.png`) });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible();
  const metrics1920 = await measurePlaybooks(page, '#playbooks-view');
  await page.screenshot({ path: path.join(OUT, `${prefix}-in-app-1920.png`) });
  if (CAPTURE_BEFORE) {
    fs.writeFileSync(BEFORE_PATH, JSON.stringify({ inApp1280: metrics1280, inApp1920: metrics1920 }, null, 2));
    return;
  }
  expect(metrics1280.toastHost).toBe(false);
  expect(metrics1280.liveCount).toBe(0);
  expect(metrics1280.lockVisible).toBe(true);
  expect(metrics1280.divider).not.toBe('none');
  if (!BEFORE) return;
  expect(metrics1280.tracks.length).toBe(BEFORE.inApp1280.tracks.length);
  metrics1280.tracks.forEach((track, i) => {
    expect(Math.abs(track.x - BEFORE.inApp1280.tracks[i].x)).toBeLessThanOrEqual(2);
    expect(Math.abs(track.w - BEFORE.inApp1280.tracks[i].w)).toBeLessThanOrEqual(2);
  });
  expect(Math.abs(metrics1280.toggle.x - BEFORE.inApp1280.toggle.x)).toBeLessThanOrEqual(2);
  expect(Math.abs(metrics1280.toggle.y - BEFORE.inApp1280.toggle.y)).toBeLessThanOrEqual(2);
  expect(samePaint(metrics1280.save.bg, BEFORE.inApp1280.save.bg)).toBe(true);
  expect(samePaint(metrics1280.save.color, BEFORE.inApp1280.save.color)).toBe(true);
  expect(metrics1920.tracks.length).toBe(BEFORE.inApp1920.tracks.length);
});

test('tutorial 1280 shot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial' });
  const prefix = CAPTURE_BEFORE ? 'before' : 'after';
  await page.screenshot({ path: path.join(OUT, `${prefix}-tutorial-1280.png`) });
  if (!CAPTURE_BEFORE) {
    expect(page.url()).toContain('mode=tutorial');
    expect(page.url()).toContain('playbooks.html');
  }
});

test('the view does not fetch the old embed HTML', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const embeds = [];
  const loaders = [];
  const bridges = [];
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('playbooks.html')) embeds.push(url);
    if (url.includes('viewLoader.js')) loaders.push(url);
    if (url.includes('prepEmbed.js')) bridges.push(url);
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page);
  expect(embeds).toEqual([]);
  expect(bridges).toEqual([]);
  expect(loaders.length).toBeGreaterThan(0);
  const clash = await page.evaluate(() => {
    const host = document.getElementById('playbooks-view');
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
    const host = document.getElementById('playbooks-view');
    host.dataset.keep = '1';
    return host.querySelector('.pbc, .playbooks-layout') ? 'ok' : '';
  });
  expect(token).toBe('ok');
  await page.evaluate(() => {
    if (window.GOBViews && window.GOBViews.show) window.GOBViews.show('playbooks-view');
  });
  await expect(page.locator('#playbooks-view')).toHaveAttribute('data-keep', '1');
  await expect(page.locator('#playbooks-view .pbc, #playbooks-view .playbooks-layout')).toHaveCount(1);
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible();
});

test('save shows the shared toast and stays on the view', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const saves = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openInApp(page, { _saves: saves });
  await page.locator('#playbooks-view .et-slider[data-sl]').first().focus();
  await page.keyboard.press('ArrowRight');
  await page.locator('#save-btn').click();
  const toast = page.locator('.gob-save-toast');
  await expect(toast).toHaveText('Playbooks saved');
  await expect(toast).toBeVisible();
  await page.screenshot({ path: path.join(OUT, 'playbooks-toast.png') });
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible();
  expect(saves).toEqual(['playbooks']);
});

test('tutorial path stays on the standalone file', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial' });
  expect(page.url()).toContain('playbooks.html');
  expect(page.url()).toContain('mode=tutorial');
  await expect(page.locator('#save-btn')).toBeVisible();
  await page.locator('.et-slider[data-sl]').first().focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#save-btn')).toBeEnabled();
});

test('standalone save leaves for the playbook report', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'before capture only');
  const saves = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openStandalone(page, { mode: 'tutorial', from: 'command_center', _saves: saves });
  await page.locator('.et-slider[data-sl]').first().focus();
  await page.keyboard.press('ArrowRight');
  await page.locator('#save-btn').click();
  await page.waitForURL(/playbook-report\.html|franchise-command-center\.html/, { timeout: 20000 });
  expect(saves).toEqual(['playbooks']);
});
