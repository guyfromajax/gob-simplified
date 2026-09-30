// @ts-check
/**
 * Set Lineup colour-law guards (computed styles, not class names).
 * - The one Advance (Play Game, #play-now) is green.
 * - Choice controls (view toggles, Autoset) are NOT green and NOT orange.
 * - Headshots are square (a small radius, never a circle).
 * set-lineup.css is on the design system (NEW_DESIGN_CSS); this locks the intent.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const GREEN = 'rgb(52, 236, 39)';   // --green
const ORANGE = 'rgb(247, 148, 32)'; // --orange

function isGreenish(rgb) {
  const m = rgb && rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return g > 150 && g > r + 60 && g > b + 60; // dominant green
}
function isOrangeish(rgb) {
  const m = rgb && rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return r > 200 && g > 110 && g < 190 && b < 90; // orange band
}

test.describe('set lineup colour law', () => {
  test('Advance is green; choice controls neutral; headshots square', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/static/set-lineup.html?mode=franchise&franchise_id=f-guard&team_id=t-guard&my_team=home&week=5&home=Alpha&away=Beta');
    // Static controls are in the initial HTML (present under the load overlay).
    await page.waitForSelector('#play-now', { state: 'attached' });

    const styles = await page.evaluate(() => {
      const bg = (sel) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el).backgroundColor : null;
      };
      // Inject a headshot so its CSS rule is measurable without roster data.
      const hs = document.createElement('img');
      hs.className = 'roster-headshot';
      document.body.appendChild(hs);
      const hsRadius = getComputedStyle(hs).borderTopLeftRadius;
      const hsW = getComputedStyle(hs).width;
      hs.remove();
      return {
        advance: bg('#play-now'),
        autoset: bg('#autoset-lineup'),
        toggle: bg('#roster-view-attributes'),
        hsRadius,
        hsW,
      };
    });

    // Advance (Play Game) is green.
    expect(styles.advance, `advance bg ${styles.advance}`).toBe(GREEN);

    // Choice controls carry neither green nor orange.
    for (const [name, val] of [['autoset', styles.autoset], ['toggle', styles.toggle]]) {
      expect(isGreenish(val), `${name} bg ${val} should not be green`).toBe(false);
      expect(isOrangeish(val), `${name} bg ${val} should not be orange`).toBe(false);
      expect(val, `${name} bg ${val} exact orange`).not.toBe(ORANGE);
      expect(val, `${name} bg ${val} exact green`).not.toBe(GREEN);
    }

    // Headshot is square: a small corner, well under half its side (not a circle).
    const radiusPx = parseFloat(styles.hsRadius);
    const sidePx = parseFloat(styles.hsW);
    expect(Number.isFinite(radiusPx)).toBe(true);
    expect(radiusPx, `radius ${styles.hsRadius}`).toBeLessThan(sidePx / 4);
  });
});
