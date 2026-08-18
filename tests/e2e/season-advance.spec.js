// @ts-check
/**
 * Season rollover cover + the walk-on reveal window.
 *
 * The cover uses the REAL markup/CSS from franchise-command-center; the walk-on rule is
 * asserted against the API source, which is the single point every surface reads.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../FrontEnd/static');
const CSS = fs.readFileSync(path.join(S, 'franchise-command-center.css'), 'utf8');
const JS = fs.readFileSync(path.join(S, 'franchise-command-center.js'), 'utf8');

/** Inject only the cover helpers; the module is a classic script full of page globals. */
async function mount(page, { season = 3 } = {}) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.setContent(`<style>${CSS}</style>
    <style>body{margin:0;background:#0b0d14}</style>
    <img id="team-logo" src="/images/teams/general/general_banner_primary.jpg" alt="">`);
  const start = JS.indexOf('function showSeasonAdvanceOverlay');
  const end = JS.indexOf('function showNewSeasonConfirmModal');
  await page.addScriptTag({ content: [
    'function escapeHomeHtml(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}',
    `var commandCenterTopDataCache = { current_season: ${season - 1} };`,
    JS.slice(start, end),
    'window.showSeasonAdvanceOverlay = showSeasonAdvanceOverlay;',
    'window.nextSeasonNumber = nextSeasonNumber;',
  ].join('\n') });
}

test.describe('Advancing To Season cover', () => {
  test('shows logo, destination season and pulse bar, stacked and centred', async ({ page }) => {
    await mount(page, { season: 3 });
    await page.evaluate(() => window.showSeasonAdvanceOverlay(window.nextSeasonNumber()));
    const m = await page.evaluate(() => {
      const o = document.querySelector('.fcc-season-advance');
      const stack = o.querySelector('.fcc-season-advance__stack');
      const logo = o.querySelector('.fcc-season-advance__logo').getBoundingClientRect();
      const copy = o.querySelector('.fcc-season-advance__copy');
      const bar = o.querySelector('.fcc-season-advance__bar').getBoundingClientRect();
      const c = copy.getBoundingClientRect();
      const sb = stack.getBoundingClientRect();
      const centre = (r) => r.left + r.width / 2;
      return {
        text: copy.textContent.trim(),
        order: [Math.round(logo.top), Math.round(c.top), Math.round(bar.top)],
        centres: [centre(logo), centre(c), centre(bar)].map((x) => Math.round(x)),
        viewportCentreX: Math.round(window.innerWidth / 2),
        stackCentreY: Math.round(sb.top + sb.height / 2),
        viewportCentreY: Math.round(window.innerHeight / 2),
        covers: Math.round(o.getBoundingClientRect().width) === window.innerWidth,
      };
    });
    expect(m.text).toBe('Advancing To Season 3');
    // Stacked in order: logo, copy, bar.
    expect(m.order[0]).toBeLessThan(m.order[1]);
    expect(m.order[1]).toBeLessThan(m.order[2]);
    // Horizontally centred, all three on the same axis.
    for (const cx of m.centres) expect(Math.abs(cx - m.viewportCentreX)).toBeLessThan(2);
    // The group as one item, vertically centred.
    expect(Math.abs(m.stackCentreY - m.viewportCentreY)).toBeLessThan(2);
    expect(m.covers).toBe(true);
  });

  test('uses the team logo already on screen', async ({ page }) => {
    await mount(page);
    await page.evaluate(() => {
      document.getElementById('team-logo').src = '/images/teams/general/general_banner_primary.jpg';
      window.showSeasonAdvanceOverlay(2);
    });
    const src = await page.evaluate(() =>
      document.querySelector('.fcc-season-advance__logo').getAttribute('src'));
    expect(src).toContain('banner_primary');
  });

  test('names the season being entered, not the one being left', async ({ page }) => {
    for (const [current, expected] of [[1, 2], [4, 5], [11, 12]]) {
      await mount(page, { season: current + 1 });
      const n = await page.evaluate(() => window.nextSeasonNumber());
      expect(n).toBe(expected);
    }
  });

  test('the pulse bar is indeterminate — it never claims a percentage', async ({ page }) => {
    await mount(page);
    await page.evaluate(() => window.showSeasonAdvanceOverlay(2));
    const m = await page.evaluate(() => {
      const bar = document.querySelector('.fcc-season-advance__bar');
      const fill = bar.querySelector('i');
      return { anim: getComputedStyle(fill).animationName,
               text: bar.textContent.trim(),
               fillW: fill.getBoundingClientRect().width,
               barW: bar.getBoundingClientRect().width };
    });
    expect(m.anim).toBe('fcc-season-advance-sweep');
    expect(m.text).toBe('');                 // no "42%" anywhere
    expect(m.fillW).toBeLessThan(m.barW);    // a sweeping segment, not a filled meter
  });

  test('only one cover exists however many times it is raised', async ({ page }) => {
    await mount(page);
    await page.evaluate(() => {
      window.showSeasonAdvanceOverlay(2);
      window.showSeasonAdvanceOverlay(2);
      window.showSeasonAdvanceOverlay(2);
    });
    expect(await page.locator('.fcc-season-advance').count()).toBe(1);
  });
});

test.describe('the rollover flow takes the screen', () => {
  test('the confirm modal is dismissed before the request, not after', async () => {
    // Source-level: closeModal() and the cover must both precede the fetch, or the
    // dialog and its re-armed button sit on screen for the whole rollover.
    const proceed = JS.slice(JS.indexOf("#fcc-new-season-proceed"), JS.indexOf("/franchise/play-next-game"));
    const closeAt = proceed.indexOf('closeModal();');
    const coverAt = proceed.indexOf('showSeasonAdvanceOverlay(');
    const fetchAt = proceed.indexOf('/franchise/finish-season');
    expect(closeAt).toBeGreaterThan(-1);
    expect(coverAt).toBeGreaterThan(-1);
    expect(closeAt).toBeLessThan(fetchAt);
    expect(coverAt).toBeLessThan(fetchAt);
    // And the cover must NOT be torn down in a finally — it stays up through navigation.
    expect(proceed).not.toMatch(/finally\s*\{[^}]*advanceOverlay/);
  });
});
