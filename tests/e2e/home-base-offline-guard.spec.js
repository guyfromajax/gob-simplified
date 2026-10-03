// @ts-check
/** Desktop Home Base makes no always-remote community requests; web still does. */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const COMMUNITY = [
  '/api/community/around-the-league',
  '/api/community/highlights',
  '/api/auth/leaderboard',
  '/api/leaderboard/by-team',
];

function communityPath(url) {
  let pathname = '';
  try { pathname = new URL(url).pathname; } catch (_err) { return null; }
  return COMMUNITY.find((p) => pathname === p || pathname.startsWith(p + '/')) || null;
}

async function openModeSelect(page, desktop) {
  const seen = [];
  page.on('request', (req) => {
    const hit = communityPath(req.url());
    if (hit) seen.push({ path: hit, host: new URL(req.url()).host });
  });
  if (desktop) await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await page.route('**/api/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
  }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.clock.install();
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  return seen;
}

test('desktop Home Base makes zero community requests and leaves the right zone empty', async ({ page }) => {
  const seen = await openModeSelect(page, true);
  // Well past the 20 s Around GOB poll, plus a visibility return.
  await page.clock.runFor(65000);
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.clock.runFor(1000);
  expect(seen, JSON.stringify(seen)).toEqual([]);

  await expect(page.locator('[data-hb-right-offline]')).toBeVisible();
  await expect(page.locator('.hbt')).toHaveCount(0);
  await expect(page.locator('.fag')).toHaveCount(0);
  const text = await page.locator('#home-base').innerText();
  expect(text).not.toMatch(/sign in to see|could not load|around gob|leaderboard|community highlights/i);
  await expect(page.locator('.hb-l')).toBeVisible();

  await page.mouse.move(1200, 700);
  await page.screenshot({ path: 'reports/home-base-data/mode-select-offline-1280x720.png' });
});

test('web Home Base still loads the community payloads and polls Around GOB', async ({ page }) => {
  const seen = await openModeSelect(page, false);
  await expect.poll(() => seen.map((s) => s.path).sort()).toEqual(expect.arrayContaining([
    '/api/auth/leaderboard',
    '/api/community/around-the-league',
  ]));
  // Community Highlights left Home Base with Chapter 7.
  expect(seen.filter((s) => s.path === '/api/community/highlights')).toEqual([]);

  const atlBefore = seen.filter((s) => s.path === '/api/community/around-the-league').length;
  await page.clock.runFor(21000);
  await expect.poll(() => seen.filter((s) => s.path === '/api/community/around-the-league').length)
    .toBeGreaterThan(atlBefore);
  await expect(page.locator('.fag')).toBeVisible();
  await expect(page.locator('.hbt')).toBeVisible();

  await page.mouse.move(1200, 700);
  await page.screenshot({ path: 'reports/home-base-data/mode-select-online-1280x720.png' });

  await page.click('[data-hb-tab="lb"]');
  await page.click('[data-hb-by-team]');
  await expect.poll(() => seen.some((s) => s.path === '/api/leaderboard/by-team')).toBe(true);
});
