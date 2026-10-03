/**
 * (b) Team art: logo_square falls back to logo_primary (known-asset list in
 *     common.js), so League tables request no missing team art.
 * (c) Save Game Plan / Save Playbooks: neutral at rest, orange only with a real
 *     unsaved edit, neutral again after a save (colour law: orange = there is
 *     something to save).
 * Desktop SQLite server, real Week-1 franchise (playwright.desktop.config.js).
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const OUT = process.env.LOGO_SAVE_OUT || path.join(__dirname, '../../reports/logo-fallback-save-state');
const PREFIX = process.env.LOGO_SAVE_PREFIX || 'after';

test.describe.configure({ mode: 'serial', timeout: 180000 });

function parseRgba(value) {
  const v = String(value);
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4] };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: m[1] * 255, g: m[2] * 255, b: m[3] * 255, a: m[4] == null ? 1 : +m[4] };
  return null;
}
const isOrange = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.5 && p.r > 200 && p.g > 100 && p.g < 200 && p.b < 110; };

let ctx = null;

async function prime(page) {
  await page.addInitScript((port) => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = Number(port);
    window.alert = () => {};
  }, PORT);
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('.main').forEach((m) => { m.scrollTop = 0; }); });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-1280.png`) });
}

test.beforeAll(async ({ request }) => {
  const create = await request.post('/franchise/select-team', { data: { team_name: 'Lancaster' } });
  expect(create.ok(), await create.text()).toBeTruthy();
  const fid = (await create.json()).franchise_id;
  const next = await request.post('/franchise/play-next-game', { data: { franchise_id: fid } });
  const m = await next.json();
  const tid = String(m.home === 'Lancaster' ? m.home_id : m.away_id);
  ctx = { fid, fcc: (tab) => `/franchise-command-center.html?franchise_id=${fid}&team_id=${tid}&user_team_id=${tid}&tab=${tab}` };
});

test.afterAll(async ({ request }) => {
  // Leave the shared desktop e2e sqlite as we found it (two-franchise cap).
  if (ctx && ctx.fid) await request.delete('/franchise/' + ctx.fid).catch(() => {});
});

for (const [name, tab, rowSel] of [
  ['standings', 'standings-view', '#standings-view tbody tr'],
  ['team-stats', 'team-stats-view', '#team-stats-view tbody tr'],
  ['rankings', 'rankings-view', '#rankings-view tbody tr'],
]) {
  test(`(b) ${name}: no team-art 404s, primary logos where squares are missing`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await prime(page);
    const missing = [];
    page.on('response', (r) => {
      const u = new URL(r.url());
      if (r.status() >= 400 && u.pathname.includes('/images/teams/')) missing.push(r.status() + ' ' + u.pathname);
    });
    await page.goto(ctx.fcc(tab));
    await page.locator(rowSel).first().waitFor({ timeout: 30000 });
    await page.waitForTimeout(3000);
    const art = await page.evaluate((sel) => {
      const host = document.querySelector(sel.split(' ')[0]);
      const imgs = Array.from(host.querySelectorAll('img')).map((i) => i.getAttribute('src') || '');
      return {
        primary: imgs.filter((s) => s.includes('_logo_primary.png')).length,
        square: imgs.filter((s) => s.includes('_logo_square.png')).length,
        tiles: host.querySelectorAll('.gob-mark').length,
      };
    }, rowSel);
    await shot(page, name);
    expect(missing, `team-art 404s on ${name}: ${missing.slice(0, 5).join(', ')}`).toEqual([]);
    expect(art.primary, `${name}: primary logos stand in for missing squares`).toBeGreaterThan(0);
  });
}

async function saveState(page, sel) {
  return page.locator(sel).evaluate((el) => {
    const s = getComputedStyle(el);
    return { bg: s.backgroundColor, dirty: el.classList.contains('is-dirty'), disabled: el.disabled };
  });
}

test('(c) Save Game Plan: rest neutral, dirty orange, saved neutral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await prime(page);
  await page.goto(ctx.fcc('game-plan-view'));
  const btn = '#btn-save-game-plan';
  await page.locator(btn).waitFor({ timeout: 30000 });
  await page.waitForTimeout(2000);
  const rest = await saveState(page, btn);
  await shot(page, 'game-plan-rest');
  const slider = page.locator('#slider-offense');
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  const dirty = await saveState(page, btn);
  await shot(page, 'game-plan-dirty');
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(300);
  const reverted = await saveState(page, btn);
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  await page.locator(btn).click();
  await page.waitForTimeout(2500);
  const saved = await saveState(page, btn);
  await shot(page, 'game-plan-saved');
  expect(isOrange(rest.bg), `rest ${rest.bg}`).toBe(false);
  expect(isOrange(dirty.bg), `dirty ${dirty.bg}`).toBe(true);
  expect(isOrange(reverted.bg), `moved back = no edit ${reverted.bg}`).toBe(false);
  expect(isOrange(saved.bg), `after save ${saved.bg}`).toBe(false);
});

test('(c) Save Playbooks: rest neutral, dirty orange, saved neutral', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await prime(page);
  await page.goto(ctx.fcc('playbooks-view'));
  const btn = '#save-btn';
  await page.locator('.et-slider').first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(2000);
  const rest = await saveState(page, btn);
  await shot(page, 'playbooks-rest');
  const slider = page.locator('.et-slider').first();
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(400);
  const dirty = await saveState(page, btn);
  await shot(page, 'playbooks-dirty');
  // No "step back" check here: a weight move rebalances the sibling plays, so one
  // step back is not a revert and hasEdits() (the leave prompt's own check) stays
  // true. The class mirrors hasEdits() exactly.
  if (!dirty.disabled) {
    await page.locator(btn).click();
    await page.waitForTimeout(2500);
  }
  const saved = await saveState(page, btn);
  await shot(page, 'playbooks-saved');
  expect(isOrange(rest.bg), `rest ${rest.bg}`).toBe(false);
  expect(dirty.disabled, 'a weight edit keeps Save enabled (fast breaks / traps still balanced)').toBe(false);
  expect(isOrange(dirty.bg), `dirty ${dirty.bg}`).toBe(true);
  expect(isOrange(saved.bg), `after save ${saved.bg}`).toBe(false);
});
