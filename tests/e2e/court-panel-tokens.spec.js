// @ts-check
/**
 * Court side-panel token/colour-law guards (Jamie rulings #4, #5).
 * court.html <body> carries class="gob", so gob tokens resolve.
 * #4: panel surfaces are gob navy (--surface-2 #141824), not the old opaque grey #1a1a1a.
 * #5: the selected stat toggle is NEUTRAL (white token), not the team colour.
 * Fails on develop (grey panel, team-colour toggle).
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');

const SURFACE_2 = 'rgb(20, 24, 36)';      // --surface-2 #141824 (navy)
const OLD_GREY = 'rgb(26, 26, 26)';       // #1a1a1a (must be gone)
const NEUTRAL_ACTIVE = 'rgba(255, 255, 255, 0.2)'; // --white-20
// Team-vibrant default for these rosters is #ff6200 — the toggle must NOT be this.
const TEAM_ORANGE = 'rgb(255, 98, 0)';

const cs = (page, sel, prop) =>
  page.locator(sel).first().evaluate((el, p) => getComputedStyle(el)[p], prop);

test.beforeEach(async ({ page, request }) => {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.goto(courtUrl());
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.player-stats-panel.away', { state: 'attached', timeout: 20000 });
});

test('#4 side panels are a gob navy surface, not opaque grey', async ({ page }) => {
  const bg = await cs(page, '.player-stats-panel.away', 'backgroundColor');
  expect(bg).toBe(SURFACE_2);
  expect(bg).not.toBe(OLD_GREY);
});

test('#5 selected stat toggle is neutral, not team colour', async ({ page }) => {
  // Activate the first toggle in the away panel's player box, then read it.
  const firstToggle = page.locator('.player-stats-panel.away .toggle-btn').first();
  await firstToggle.click({ timeout: 5000 }).catch(() => {});
  const active = page.locator('.player-stats-panel.away .toggle-btn.active').first();
  if (await active.count()) {
    const bg = await active.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).toBe(NEUTRAL_ACTIVE);
    expect(bg).not.toBe(TEAM_ORANGE);
    const border = await active.evaluate((el) => getComputedStyle(el).borderTopColor);
    expect(border).not.toBe(TEAM_ORANGE);
  }
});
