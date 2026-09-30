// @ts-check
/**
 * Set Lineup colour-law + layout guards (computed styles / bounding boxes).
 * - Play Game (#play-now) is green AND equals the shell Advance paint (a reference
 *   `.gob .advance` element resolves the same --green).
 * - Choice controls (view toggles, Autoset) are NOT green and NOT orange.
 * - Headshots are square (a small radius, never a circle).
 * - Production stat cells (PTS/REB/AST/DEF%) do not overlap each other.
 * set-lineup.css is on the design system (NEW_DESIGN_CSS); this locks the intent.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

const GREEN = 'rgb(52, 236, 39)'; // --green

function isGreenish(rgb) {
  const m = rgb && rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return g > 150 && g > r + 60 && g > b + 60;
}
function isOrangeish(rgb) {
  const m = rgb && rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return r > 200 && g > 110 && g < 190 && b < 90;
}

test.describe('set lineup colour law + layout', () => {
  test('Advance matches shell green; choices neutral; headshots square; no stat overlap', async ({ page, request }) => {
    await stubAuth(page);
    await waitForCanonicalRosters(request);
    await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
    await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
    await page.waitForTimeout(700);

    const out = await page.evaluate(() => {
      const bg = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).backgroundColor : null; };
      const advanceEl = document.querySelector('#play-now');
      const advanceBorder = advanceEl ? getComputedStyle(advanceEl).borderTopColor : null;
      // Headshot radius without depending on roster data.
      const hs = document.createElement('img');
      hs.className = 'roster-headshot';
      document.body.appendChild(hs);
      const hsRadius = getComputedStyle(hs).borderTopLeftRadius;
      const hsW = getComputedStyle(hs).width;
      hs.remove();
      // Production stat cells of the first bench row with a prod cluster.
      let prodBoxes = [];
      const spans = document.querySelectorAll('#roster-body-game tr .prod span');
      prodBoxes = [...spans].slice(0, 4).map((s) => {
        const b = s.getBoundingClientRect();
        return { text: s.textContent.trim(), left: Math.round(b.left), right: Math.round(b.right) };
      });
      return {
        advance: bg('#play-now'),
        advanceBorder,
        autoset: bg('#autoset-lineup'),
        toggle: bg('#roster-view-attributes'),
        hsRadius, hsW, prodBoxes,
      };
    });

    // Play Game paints with the shell Advance tokens: --green fill + --white-28
    // border (the shell's `.gob .advance` uses the same --green, so this is the
    // shell Advance green — gob-components.css is not loaded on this focus page,
    // so we assert the resolved token values rather than a live reference button).
    expect(out.advance).toBe(GREEN);
    expect(out.advanceBorder).toBe('rgba(255, 255, 255, 0.28)'); // --white-28

    // Choice controls: neither green nor orange.
    for (const [name, val] of [['autoset', out.autoset], ['toggle', out.toggle]]) {
      expect(isGreenish(val), `${name} bg ${val} should not be green`).toBe(false);
      expect(isOrangeish(val), `${name} bg ${val} should not be orange`).toBe(false);
    }

    // Headshot square: small corner, well under half the side.
    expect(parseFloat(out.hsRadius)).toBeLessThan(parseFloat(out.hsW) / 4);

    // Production stat cells do not overlap (each starts at or after the previous end).
    expect(out.prodBoxes.length).toBe(4);
    for (let i = 1; i < out.prodBoxes.length; i += 1) {
      expect(
        out.prodBoxes[i].left,
        `"${out.prodBoxes[i].text}" (${out.prodBoxes[i].left}) overlaps "${out.prodBoxes[i - 1].text}" (ends ${out.prodBoxes[i - 1].right})`,
      ).toBeGreaterThanOrEqual(out.prodBoxes[i - 1].right);
    }
  });
});
