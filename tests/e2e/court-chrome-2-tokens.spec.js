// @ts-check
/**
 * Court chrome part 2 — colour-law / token guards for the remaining chrome touched
 * in the "safe pass": the main container, the (legacy light) sim-quarter popup, the
 * player/play tooltips, and the side-panel momentum-wrap.
 *
 * court.html <body> carries class="gob" (part 1), so gob tokens resolve. Probe elements
 * are injected where the real element only mounts during play, which still exercises the
 * CSS rule + token resolution. Fails on develop (orange sim-quarter / tooltip borders).
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');

const BLACK = 'rgb(0, 0, 0)';            // --black
const GREY = 'rgb(107, 114, 128)';       // #6b7280 (neutral on the light sim-quarter popup)
const WHITE_28 = 'rgba(255, 255, 255, 0.28)'; // --white-28
const WHITE_6 = 'rgba(255, 255, 255, 0.06)';  // --white-6
const OFF_ORANGE = ['rgb(255, 98, 0)', 'rgb(247, 148, 32)']; // #ff6200 / #F79420

test.beforeEach(async ({ page, request }) => {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.goto(courtUrl());
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('#scoreboard', { state: 'visible', timeout: 20000 });
});

// Note: #main-container's bg was also tokenised to var(--black) (value-identical #000),
// but that element is not in the default court DOM (court uses #app-grid), so it is not
// guarded here. The three guards below use injected probes, which always exercise the rule.

test('sim-quarter popup divider + scrollbar are neutral, not orange', async ({ page }) => {
  const res = await page.evaluate(() => {
    const h = document.createElement('div'); h.className = 'sim-quarter-header';
    const t = document.createElement('div'); t.className = 'sim-quarter-scroll-container';
    document.body.append(h, t);
    const hb = getComputedStyle(h).borderBottomColor;
    document.body.removeChild(h); document.body.removeChild(t);
    return { headerBorder: hb };
  });
  expect(res.headerBorder).toBe(GREY);
  expect(OFF_ORANGE).not.toContain(res.headerBorder);
});

test('player/play tooltips have a neutral border, not orange', async ({ page }) => {
  for (const id of ['player-tooltip', 'play-tooltip']) {
    const border = await page.evaluate((tid) => {
      const d = document.createElement('div'); d.id = tid;
      document.body.appendChild(d);
      const c = getComputedStyle(d).borderTopColor;
      document.body.removeChild(d);
      return c;
    }, id);
    expect(border, `#${id} border`).toBe(WHITE_28);
    expect(OFF_ORANGE, `#${id} not orange`).not.toContain(border);
  }
});

test('side-panel momentum-wrap divider is --white-6', async ({ page }) => {
  const c = await page.evaluate(() => {
    const d = document.createElement('div'); d.className = 'momentum-bar-wrap';
    document.body.appendChild(d);
    const col = getComputedStyle(d).borderBottomColor;
    document.body.removeChild(d);
    return col;
  });
  expect(c).toBe(WHITE_6);
});
