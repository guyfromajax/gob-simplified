// @ts-check
/**
 * Set Lineup colour-law + layout guards (computed styles / bounding boxes).
 * - Play Game (#play-now) is green AND paints with the shell Advance tokens
 *   (--green fill + --white-28 border). gob-components.css is not loaded on this
 *   focus page, so we assert the resolved token values.
 * - Choice controls (view toggles, Autoset) are NOT green and NOT orange.
 * - Headshots are square (a small radius, never a circle).
 * - In every bench row, no two adjacent cells' TEXT overlap, across the Game,
 *   Attributes and Stats views, at 1280 and 1920. (Text is measured with a Range
 *   so this catches content spilling out of a cell, which cell-box edges hide.)
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

// Text bounding boxes (via Range) of every non-empty cell in each bench row of the
// currently visible roster pane. Returns rows of [{l, r, t}] left-to-right.
function benchRowCellTextBoxes(page) {
  return page.evaluate(() => {
    const pane = [...document.querySelectorAll('.roster-roster-pane')].find(
      (p) => !p.hidden && p.offsetParent !== null,
    );
    if (!pane) return [];
    const tbody = pane.querySelector('tbody');
    if (!tbody) return [];
    const rows = [...tbody.querySelectorAll('tr')].filter((tr) => {
      const e = tr.querySelector('.engnum');
      return e && /%/.test(e.textContent || '');
    });
    const textBox = (cell) => {
      const t = (cell.textContent || '').trim();
      if (!t) return null;
      const range = document.createRange();
      range.selectNodeContents(cell);
      const b = range.getBoundingClientRect();
      range.detach();
      if (!b || b.width === 0) return null;
      return { l: Math.round(b.left), r: Math.round(b.right), t: t.slice(0, 6) };
    };
    return rows.map((tr) => [...tr.children].map(textBox).filter(Boolean));
  });
}

test.describe('set lineup colour law + layout', () => {
  test('Advance matches shell green; choices neutral; headshots square; no cell-text overlap', async ({ page, request }) => {
    await stubAuth(page);
    await waitForCanonicalRosters(request);

    for (const width of [1280, 1920]) {
      await page.setViewportSize({ width, height: width === 1280 ? 720 : 1080 });
      await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
      await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
      await page.waitForTimeout(600);

      // Colour-law + headshot checks (once per density).
      const out = await page.evaluate(() => {
        const bg = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).backgroundColor : null; };
        const adv = document.querySelector('#play-now');
        const hs = document.createElement('img');
        hs.className = 'roster-headshot';
        document.body.appendChild(hs);
        const hsRadius = getComputedStyle(hs).borderTopLeftRadius;
        const hsW = getComputedStyle(hs).width;
        hs.remove();
        return {
          advance: bg('#play-now'),
          advanceBorder: adv ? getComputedStyle(adv).borderTopColor : null,
          autoset: bg('#autoset-lineup'),
          toggle: bg('#roster-view-attributes'),
          hsRadius, hsW,
        };
      });
      expect(out.advance, `@${width} advance bg`).toBe(GREEN);
      expect(out.advanceBorder, `@${width} advance border`).toBe('rgba(255, 255, 255, 0.28)'); // --white-28
      for (const [name, val] of [['autoset', out.autoset], ['toggle', out.toggle]]) {
        expect(isGreenish(val), `@${width} ${name} bg ${val} not green`).toBe(false);
        expect(isOrangeish(val), `@${width} ${name} bg ${val} not orange`).toBe(false);
      }
      expect(parseFloat(out.hsRadius)).toBeLessThan(parseFloat(out.hsW) / 4);

      // No cell-text overlap in every bench row, for each of the three views.
      for (const [view, btn] of [['game', '#roster-view-game'], ['attributes', '#roster-view-attributes'], ['stats', '#roster-view-stats']]) {
        await page.locator(btn).click();
        await page.waitForTimeout(350);
        const rows = await benchRowCellTextBoxes(page);
        expect(rows.length, `@${width} ${view}: bench rows present`).toBeGreaterThan(0);
        rows.forEach((cells, ri) => {
          for (let i = 1; i < cells.length; i += 1) {
            expect(
              cells[i].l,
              `@${width} ${view} row ${ri}: "${cells[i].t}" (${cells[i].l}) overlaps "${cells[i - 1].t}" (ends ${cells[i - 1].r})`,
            ).toBeGreaterThanOrEqual(cells[i - 1].r);
          }
        });
      }
    }
  });
});
