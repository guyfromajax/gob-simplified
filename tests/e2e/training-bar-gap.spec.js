// @ts-check
/**
 * Training action bar: space under the top strip (Jamie, 2026-10-03).
 *
 * The weekly Training bar (Back to Locker Room, Training Tutorial, Points, Focus,
 * Auto-Train, Submit Training) sat flush against the bottom of the top strip. It now sits
 * --space-10 below it, in season and in training camp. The bar is not pinned: it scrolls
 * away with the page (Jamie: gap only). The Training Report's pinned header and the Custom
 * Playbook page already left that space; they are pinned here so they keep it.
 *
 *   TBG_SHOTS=before|after   shots to reports/training-bar-gap/
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const report = require('./helpers/trainingReportFixture');
const fx = require('./helpers/v3TrainingFixture');

const OUT = path.join(__dirname, '../../reports/training-bar-gap');
const PHASE = process.env.TBG_SHOTS || '';
const SIZES = [[1280, 720], [1920, 1080]];
const BAR = ['#back-btn', '#training-tutorial-btn', '#requirements-bar', '#auto-train-btn', '#submit-btn'];

test.describe.configure({ timeout: 120000 });

async function shot(page, name) {
  if (!PHASE) return;
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, `${PHASE}-${name}-${page.viewportSize().width}.png`) });
}

/** Bottom edge of the shell's top strip, the --space-10 token in px, and each selector's top edge. */
function measure(page, selectors) {
  return page.evaluate((list) => {
    const strip = document.querySelector('html.gob-shell .top');
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;visibility:hidden;height:var(--space-10)';
    document.body.appendChild(probe);
    const token = probe.getBoundingClientRect().height;
    probe.remove();
    return {
      strip: strip.getBoundingClientRect().bottom,
      token,
      tops: list.map((sel) => {
        const el = document.querySelector(sel);
        return el && el.getBoundingClientRect().height > 0 ? el.getBoundingClientRect().top : null;
      }),
    };
  }, selectors);
}

async function scrollMain(page, y) {
  await page.evaluate((top) => { document.querySelector('html.gob-shell .main').scrollTop = top; }, y);
}

async function openPlaybook(page) {
  await fx.openTraining(page, fx.newState());
  await page.locator('#playbook-mode-custom-btn').click();
  await page.waitForURL(/training-playbooks\.html/, { timeout: 20000 });
  await fx.waitOverlay(page);
  await expect(page.locator('.tp-dock')).toBeVisible({ timeout: 30000 });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

async function openReport(page) {
  const data = report.busy();
  await stubAuth(page);
  await report.installReportApi(page, data);
  await page.goto(report.reportUrl(data));
  await expect(page.locator('#training-report-view')).not.toHaveClass(/is-loading/, { timeout: 30000 });
  await expect(page.locator('.report-header')).toBeVisible();
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

for (const [width, height] of SIZES) {
  test.describe(`${width}x${height}`, () => {
    test.use({ viewport: { width, height } });

    for (const [label, week] of [['in season', 12], ['training camp', 1]]) {
      test(`Training, ${label}: the bar sits one spacing token below the top strip`, async ({ page }) => {
        await fx.openTraining(page, fx.newState({ week }));
        await page.evaluate(() => document.fonts && document.fonts.ready);
        const m = await measure(page, BAR);
        if (PHASE === 'before') {
          // The old page fails the checks below; the shots are what is wanted.
          await shot(page, `training-${week === 1 ? 'camp' : 'season'}-rest`);
          await scrollMain(page, 400);
          await shot(page, `training-${week === 1 ? 'camp' : 'season'}-scrolled`);
          return;
        }
        expect(m.token).toBe(10);
        // Every control in the bar clears the strip by at least the token; the tallest ones by exactly it.
        m.tops.forEach((top, i) => {
          expect(top, BAR[i]).not.toBeNull();
          expect(top - m.strip, BAR[i]).toBeGreaterThanOrEqual(m.token);
        });
        expect(Math.min(...m.tops) - m.strip).toBe(m.token);
        // Still one row: the gap did not push anything out of line.
        expect(new Set(m.tops.filter((_, i) => BAR[i] !== '#requirements-bar' && BAR[i] !== '#training-tutorial-btn')).size).toBe(1);
        await shot(page, `training-${week === 1 ? 'camp' : 'season'}-rest`);

        // Not pinned (unchanged): the bar leaves with the page, and nothing else sits against the strip.
        await scrollMain(page, 60);
        const mid = await measure(page, ['.training-header']);
        expect(mid.tops[0] - m.strip).toBeLessThan(0);
        expect(await page.evaluate(() => getComputedStyle(document.querySelector('.training-header')).position)).toBe('static');
        await scrollMain(page, 400);
        await shot(page, `training-${week === 1 ? 'camp' : 'season'}-scrolled`);
      });
    }

    test('Training Report: the pinned header keeps the space, on a solid fill, at rest and scrolled', async ({ page }) => {
      await openReport(page);
      const rest = await measure(page, ['.report-header .page-title', '.report-header button']);
      rest.tops.forEach((top) => expect(top - rest.strip).toBeGreaterThanOrEqual(rest.token));
      await shot(page, 'report-rest');

      await scrollMain(page, 400);
      const scrolled = await measure(page, ['.report-header .page-title', '.report-header button', '.report-header']);
      expect(scrolled.tops.slice(0, 2)).toEqual(rest.tops);
      expect(scrolled.tops[2]).toBe(scrolled.strip);
      // Nothing shows through the gap: the header itself fills it, opaque.
      const gap = await page.evaluate((y) => {
        const header = document.querySelector('.report-header');
        const box = header.getBoundingClientRect();
        const hits = [0.1, 0.5, 0.9].map((f) => {
          const el = document.elementFromPoint(box.left + box.width * f, y);
          return !!el && (el === header || header.contains(el));
        });
        return { hits, bg: getComputedStyle(header).backgroundColor };
      }, scrolled.strip + 4);
      expect(gap.hits).toEqual([true, true, true]);
      expect(gap.bg).toMatch(/^rgb\(/);
      await shot(page, 'report-scrolled');
    });

    test('Custom Playbook: nothing sits against the top strip', async ({ page }) => {
      await openPlaybook(page);
      const m = await measure(page, ['.tp-dock']);
      const first = await page.evaluate(() => {
        // The first thing drawn in the page under the strip: the page card.
        const main = document.querySelector('html.gob-shell .main');
        const tops = [...main.querySelectorAll('button, a, h1, .tp-dock')]
          .filter((el) => el.getBoundingClientRect().height > 0)
          .map((el) => el.getBoundingClientRect().top);
        return Math.min(...tops);
      });
      expect(first - m.strip).toBeGreaterThanOrEqual(m.token);
      // No pinned bar on this page: the dock scrolls with it.
      await shot(page, 'custom-playbook-rest');
      await scrollMain(page, 400);
      const scrolled = await measure(page, ['.tp-dock']);
      expect(scrolled.tops[0]).toBeLessThan(m.tops[0]);
      await shot(page, 'custom-playbook-scrolled');
    });
  });
}
