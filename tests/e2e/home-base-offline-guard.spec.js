// @ts-check
/** Desktop mode-select makes no always-remote community requests; web still does. */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const COMMUNITY = [
  '/api/community/around-the-league',
  '/api/community/highlights',
  '/api/auth/leaderboard',
  '/api/leaderboard/by-team',
];
const PANELS = ['.around-the-league-section', '.community-section', '.community-highlights-section'];

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
  await expect(page.locator('body.mode-select-page:not(.mode-select-loading)')).toHaveCount(1, { timeout: 30000 });
  return seen;
}

test('desktop mode-select makes zero community requests and hides the panels', async ({ page }) => {
  const seen = await openModeSelect(page, true);
  // Well past the 20 s Around The League poll, plus a visibility return.
  await page.clock.runFor(65000);
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.clock.runFor(1000);
  expect(seen, JSON.stringify(seen)).toEqual([]);

  for (const sel of PANELS) await expect(page.locator(sel)).toBeHidden();
  await expect(page.locator('#leaders-by-team-btn')).toBeHidden();
  const text = await page.locator('.mode-wrapper').innerText();
  expect(text).not.toMatch(/sign in to see|could not load|around the league|leaderboard|community highlights/i);
  await expect(page.locator('.franchise-home-section')).toBeVisible();

  await page.mouse.move(1200, 700);
  await page.screenshot({ path: 'reports/home-base-data/mode-select-offline-1280x720.png' });
});

test('web mode-select still loads the community panels and polls Around The League', async ({ page }) => {
  const seen = await openModeSelect(page, false);
  await expect.poll(() => seen.map((s) => s.path).sort()).toEqual(expect.arrayContaining([
    '/api/auth/leaderboard',
    '/api/community/around-the-league',
    '/api/community/highlights',
  ]));
  const atlBefore = seen.filter((s) => s.path === '/api/community/around-the-league').length;
  await page.clock.runFor(21000);
  await expect.poll(() => seen.filter((s) => s.path === '/api/community/around-the-league').length)
    .toBeGreaterThan(atlBefore);
  for (const sel of PANELS) await expect(page.locator(sel)).toBeVisible();

  await page.mouse.move(1200, 700);
  await page.screenshot({ path: 'reports/home-base-data/mode-select-online-1280x720.png' });

  await page.click('#leaders-by-team-btn');
  await expect.poll(() => seen.some((s) => s.path === '/api/leaderboard/by-team')).toBe(true);
});
