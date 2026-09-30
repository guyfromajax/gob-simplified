// @ts-check
/**
 * #alpha-badge must render at most once. The franchise shell
 * (franchise-command-center.html) loads BOTH alphaBanner.js (a body-top badge)
 * and, via authGuard, authBarInit.js (a badge baked into the site auth bar). When
 * alphaBanner won the async race it left a standalone badge and authBarInit then
 * added a second — a duplicate id. authBarInit now removes any stray badge before
 * inserting its bar. Public auth pages (login/signup/reset-password) carry a static
 * badge and are guarded here too.
 */
const { test, expect } = require('@playwright/test');

const FID = 'f-alpha-badge';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

async function stubFranchise(page) {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 't-e2e');
    localStorage.setItem('auth_user', JSON.stringify({ user_id: 'u', username: 'e', email: 'e@e.com' }));
  });
  await page.route('**/api/auth/me', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_id: 'u', username: 'e' }) }));
  await page.route('**/app-config', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ isAlpha: true }) }));
  await page.route('**/teams', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ name: 'Lancaster', object_id: TID, _id: TID }]) }));
  await page.route('**/franchise/command-center/data**', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 5, current_season: 1, office_digest: { state: 'season', what_moved: {}, result: null, todos: [], recruiting_wire: { events: [] } } }),
  }));
  await page.route('**/franchise/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
}

async function countBadges(page) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(800); // authBarInit / alphaBanner are async
  return page.locator('#alpha-badge').count();
}

test.describe('alpha badge renders at most once', () => {
  test('franchise-command-center.html (the shell that loaded two injectors)', async ({ page }) => {
    await stubFranchise(page);
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID).catch(() => {});
    const count = await countBadges(page);
    expect(count, `FCC has ${count} #alpha-badge elements`).toBeLessThanOrEqual(1);
  });

  for (const path of ['/login.html', '/signup.html', '/reset-password.html']) {
    test(`static-badge auth page ${path}`, async ({ page }) => {
      await page.goto(path).catch(() => {});
      const count = await countBadges(page);
      expect(count, `${path} has ${count} #alpha-badge elements`).toBeLessThanOrEqual(1);
    });
  }
});
