// @ts-check
/**
 * Recruiting hub tables: the pinned header is opaque (Jamie, 2026-10-02). When the table
 * scrolls under it, no row content shows through the group row, the column row or the
 * Lean column, and a hairline appears under the header only once the table has scrolled.
 * The same header is pinned on Player Stats in the command center; it is checked here too.
 *
 *   STH_SHOTS=before|after   shots to reports/recruiting-sticky-header/
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const league = require('./helpers/tablesLeagueFixtures');
const { openHub, scrollMain, scrollTableUnder, inspectHeader, headerPixels, pixelDiff } = require('./helpers/recruitingHubFixture');

const OUT = path.join(__dirname, '../../reports/recruiting-sticky-header');
const PHASE = process.env.STH_SHOTS || '';
const SCROLL = 420;

test.describe.configure({ timeout: 120000 });

const TABLES = {
  pool: { hub: 'pool', week: 7, table: '#hub-pool table.pool' },
  leans: { hub: 'leans', week: 21, table: '#hub-pool table.pool' },
};
// Header and body row heights at rest, as they were before the fix (shots on develop).
const HEIGHTS = { 1280: { head: [32.5, 33], row: 43 }, 1920: { head: [34.5, 35], row: 45 } };

function viewport(width) {
  return { width, height: width === 1280 ? 720 : 1080 };
}

/** The computed value of a token on :root, for comparing against a computed style. */
function token(page, name) {
  return page.evaluate((n) => {
    const probe = document.createElement('div');
    probe.style.backgroundColor = 'var(' + n + ')';
    document.body.appendChild(probe);
    const value = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return value;
  }, name);
}

/** What the body paints: each row's zebra or on-board tint, the shade tint and row heights. */
function bodyPaint(page, tableSelector) {
  return page.evaluate((selector) => {
    const table = document.querySelector(selector);
    const rows = [...table.querySelectorAll('tbody tr')].slice(0, 9);
    return rows.map((tr, i) => {
      const plain = tr.querySelector('td:not(.gshade):not(.lean-col)');
      const shade = tr.querySelector('td.gshade');
      return {
        height: Math.round(tr.getBoundingClientRect().height * 10) / 10,
        onBoard: tr.classList.contains('on-board'),
        even: i % 2 === 1,
        fill: getComputedStyle(plain).backgroundColor,
        shade: shade && getComputedStyle(shade).backgroundColor,
      };
    });
  }, tableSelector);
}

/** The computed colour of a CSS background value, for comparing against a computed style. */
function paintOf(page, value) {
  return page.evaluate((v) => {
    const probe = document.createElement('div');
    probe.style.backgroundColor = v;
    document.body.appendChild(probe);
    const out = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return out;
  }, value);
}

for (const [name, cfg] of Object.entries(TABLES)) {
  for (const width of [1280, 1920]) {
    test.describe(name + ' at ' + width, () => {
      test.beforeEach(async ({ page }) => {
        await page.setViewportSize(viewport(width));
        await openHub(page, cfg.hub, cfg.week);
      });

      test('no row content is visible inside the pinned header', async ({ page }) => {
        await page.mouse.move(0, 0);
        // At rest: the header in view, three rows short of the pinning edge (Leans sits far down the page).
        await scrollTableUnder(page, cfg.table, -3);
        expect((await inspectHeader(page, cfg.table)).pinned).toBe(false);
        const rest = await headerPixels(page, cfg.table);
        await scrollTableUnder(page, cfg.table, 2.5);
        const header = await inspectHeader(page, cfg.table);
        expect(header.rowsUnder, 'rows have scrolled under the header').toBeGreaterThan(0);
        expect(header.cells).toBeGreaterThan(20);
        // What the header shows pinned is what it shows at rest: no digit, chip or tint of a
        // row comes through anywhere in its box (the bottom pixel row is the hairline).
        const scrolled = await headerPixels(page, cfg.table, rest.clip);
        expect(scrolled.width).toBeGreaterThan(1000);
        expect(scrolled.height).toBeGreaterThan(50);
        const diff = pixelDiff(rest, scrolled, 1, 12);
        expect(diff, JSON.stringify(diff.first)).toEqual(expect.objectContaining({ count: 0 }));
        // And nothing in the body stacks above the header (the Lean chips are positioned).
        expect(header.samples).toBeGreaterThan(1000);
        expect(header.leaks).toEqual([]);
        expect(header.leakCount).toBe(0);
        // The Lean column is part of the header's box: its last cell reaches the table's right edge.
        const lean = await page.locator(cfg.table + ' thead th').last().boundingBox();
        const table = await page.locator(cfg.table).boundingBox();
        expect(Math.abs(lean.x + lean.width - (table.x + table.width))).toBeLessThan(2);
      });

      test('every header cell is painted opaque: a solid base, the group tint layered on top', async ({ page }) => {
        const header = await inspectHeader(page, cfg.table);
        expect(header.translucentFill).toEqual([]);
        expect(header.translucentBorder).toEqual([]);
        expect(header.translucentLine).toEqual([]);
        const solid = await token(page, '--bg-page-solid');
        const shade = await token(page, '--group-shade');
        const cells = await page.locator(cfg.table + ' thead th.gshade').evaluateAll((ths) => ths.map((th) => {
          const cs = getComputedStyle(th);
          return { color: cs.backgroundColor, image: cs.backgroundImage };
        }));
        expect(cells.length).toBeGreaterThan(3);
        for (const cell of cells) {
          expect(cell.color).toBe(solid);
          expect(cell.image).toBe('linear-gradient(' + shade + ', ' + shade + ')');
        }
      });

      test('a hairline under the header only once the table has scrolled', async ({ page }) => {
        const line = await paintOf(page, 'color-mix(in srgb, var(--white) 8%, var(--bg-page-solid))');
        const hairline = await paintOf(page, 'color-mix(in srgb, var(--white) 14%, var(--bg-page-solid))');
        expect(hairline).not.toBe(line);
        const rest = await inspectHeader(page, cfg.table);
        expect(rest.pinned).toBe(false);
        expect(rest.lastRowLine).toEqual([line]);

        await scrollTableUnder(page, cfg.table, 2.5);
        const scrolled = await inspectHeader(page, cfg.table);
        expect(scrolled.pinned).toBe(true);
        expect(scrolled.lastRowLine).toEqual([hairline]);

        await scrollMain(page, 0);
        const back = await inspectHeader(page, cfg.table);
        expect(back.pinned).toBe(false);
        expect(back.lastRowLine).toEqual([line]);
      });

      test('the body is untouched: zebra, shade tint and row heights', async ({ page }) => {
        const rows = await bodyPaint(page, cfg.table);
        const zebra = await token(page, '--white-2');
        const clear = 'rgba(0, 0, 0, 0)';
        const onBoard = await paintOf(page, 'color-mix(in srgb, var(--navy) 14%, transparent)');
        const shade = await token(page, '--group-shade');
        expect(rows.length).toBe(9);
        // Every Leans row is on the board (tinted); the Pool has plain rows, so the zebra is sampled there.
        if (name === 'pool') expect(rows.filter((r) => !r.onBoard && r.even).length, 'a plain even row is sampled').toBeGreaterThan(0);
        for (const row of rows) {
          expect(row.height).toBe(HEIGHTS[width].row);
          expect(row.fill).toBe(row.onBoard ? onBoard : row.even ? zebra : clear);
          expect(row.shade).toBe(row.onBoard ? onBoard : shade);
        }
        const header = await inspectHeader(page, cfg.table);
        expect(header.headHeights).toEqual(HEIGHTS[width].head);
      });
    });
  }
}

test.describe('the same header elsewhere', () => {
  test('Player Stats in the command center: no row content inside the pinned header', async ({ page }) => {
    await page.setViewportSize(viewport(1280));
    await stubAuth(page);
    await league.installApi(page, { week: 13 });
    await page.goto('/franchise-command-center.html?franchise_id=' + league.FID + '&team_id=' + league.TID + '&tab=player-stats-view');
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    await page.waitForSelector('#player-stats-view a.gob-player', { timeout: 20000 });
    await page.waitForTimeout(500);
    const table = '#player-stats-view table.gob-tbl';
    await expect(page.locator(table + ' thead tr.gob-groups th.gshade').first()).toBeAttached();
    await scrollMain(page, SCROLL);
    const header = await inspectHeader(page, table);
    expect(header.pinned).toBe(true);
    expect(header.rowsUnder).toBeGreaterThan(0);
    expect(header.leaks).toEqual([]);
    expect(header.translucentFill).toEqual([]);
    expect(header.translucentBorder).toEqual([]);
    expect(header.translucentLine).toEqual([]);
  });
});

test.describe('shots', () => {
  test.skip(!PHASE, 'STH_SHOTS only');
  for (const width of [1280, 1920]) {
    test('pool at ' + width, async ({ page }) => {
      fs.mkdirSync(OUT, { recursive: true });
      await page.setViewportSize(viewport(width));
      await openHub(page, 'pool', 7);
      await page.mouse.move(0, 0);
      await page.waitForTimeout(250);
      await page.screenshot({ path: path.join(OUT, PHASE + '-pool-unscrolled-' + width + '.png'), animations: 'disabled' });
      await scrollMain(page, SCROLL);
      await page.screenshot({ path: path.join(OUT, PHASE + '-pool-scrolled-' + width + '.png'), animations: 'disabled' });
    });
  }
});
