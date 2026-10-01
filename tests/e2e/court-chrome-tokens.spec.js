// @ts-check
/**
 * Court chrome colour-law / token guards.
 *
 * court.html carries `class="gob"` on <body> so gob-tokens.css custom properties
 * resolve. These guards assert the tokenised computed values on the pre-game start
 * prompt, the scoreboard top bar, and the game-controls strip — proving (a) the
 * tokens actually resolve (an unresolved var() would NOT compute to these rgb values)
 * and (b) the colour law holds (Advance green; no orange/blue/purple on controls).
 *
 * Guards the court-chrome-tokens change; fails on develop (orange Play Quarter, etc.).
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');

const GREEN = 'rgb(52, 236, 39)';   // --green #34EC27 (Advance)
const INK = 'rgb(11, 13, 20)';      // --bg #0b0d14 (ink on green)
const BLACK = 'rgb(0, 0, 0)';       // --black
const WHITE = 'rgb(255, 255, 255)'; // --text-100
const WHITE_10 = 'rgba(255, 255, 255, 0.1)'; // --white-10
const ORANGE = 'rgb(247, 148, 32)'; // #F79420 (must NOT appear on Advance/controls)
// Off-law control colours that must be gone: orange #ff6200/#F79420, blue #007bff, purple #9c27b0.
const OFF_LAW_CONTROL = new Set([
  'rgb(247, 148, 32)', 'rgb(255, 98, 0)', 'rgb(0, 123, 255)', 'rgb(156, 39, 176)',
]);
// Neutral white-token backgrounds the controls may use (--white-6 / --white-10 / --white-20).
const NEUTRAL_BG = new Set([
  'rgba(255, 255, 255, 0.06)', 'rgba(255, 255, 255, 0.1)', 'rgba(255, 255, 255, 0.2)',
]);

const cs = (page, sel, prop) =>
  page.locator(sel).first().evaluate((el, p) => getComputedStyle(el)[p], prop);

test.beforeEach(async ({ page, request }) => {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.goto(courtUrl());
  await page.waitForLoadState('networkidle');
});

test('body carries .gob so court tokens resolve', async ({ page }) => {
  const hasGob = await page.evaluate(() => document.body.classList.contains('gob'));
  expect(hasGob).toBe(true);
});

test('pre-game: Play Quarter is the green Advance, accent + Sim are neutral', async ({ page }) => {
  await page.waitForSelector('.pre-game-container:not(.hidden) .play-button', { state: 'visible', timeout: 20000 });
  // Play Quarter → green Advance, ink text (proves --green/--bg resolved).
  expect(await cs(page, '.pre-game-container:not(.hidden) .play-button', 'backgroundColor')).toBe(GREEN);
  expect(await cs(page, '.pre-game-container:not(.hidden) .play-button', 'color')).toBe(INK);
  expect(await cs(page, '.pre-game-container:not(.hidden) .play-button', 'backgroundColor')).not.toBe(ORANGE);
  // Accent rule is neutral (not orange).
  expect(await cs(page, '.pre-game-container:not(.hidden) .pre-game-modal-accent', 'backgroundColor')).not.toBe(ORANGE);
  // Sim Full Game is a neutral secondary (not green, not orange).
  const simBg = await cs(page, '.pre-game-container:not(.hidden) .sim-full-game-button', 'backgroundColor');
  expect(simBg).not.toBe(GREEN);
  expect(simBg).not.toBe(ORANGE);
});

test('scoreboard: black bar, white scores (tokens resolved)', async ({ page }) => {
  await page.waitForSelector('#scoreboard', { state: 'visible', timeout: 20000 });
  expect(await cs(page, '#scoreboard', 'backgroundColor')).toBe(BLACK);
  expect(await cs(page, '#away-score', 'color')).toBe(WHITE);
  expect(await cs(page, '#home-score', 'color')).toBe(WHITE);
});

test('controls: pause / skip / game-speed are neutral, not orange / blue / purple', async ({ page }) => {
  // The controls strip may mount during play; assert only if present in the DOM.
  const ids = ['#pause-btn', '#skip-btn', '#game-speed-btn'];
  for (const id of ids) {
    if (await page.locator(id).count()) {
      const bg = await cs(page, id, 'backgroundColor');
      expect(OFF_LAW_CONTROL.has(bg), `${id} must not be orange/blue/purple (got ${bg})`).toBe(false);
      expect(NEUTRAL_BG.has(bg), `${id} must be a neutral white token (got ${bg})`).toBe(true);
    }
  }
});
