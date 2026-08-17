// @ts-check
/**
 * Cadence debug panel (brief §9: "instrument this").
 * Off unless ?debug_cards=1, and it must never participate in the composition's layout.
 */
const { test, expect } = require('@playwright/test');

const TEAMS = {
  home: { teamName: 'Lancaster', name: 'Lancaster', abbr: 'LAN', color: '#1F8A5B', rank: 1, rec: '1-0' },
  away: { teamName: 'Xavier', name: 'Xavier', abbr: 'XAV', color: '#9E1B32', rank: 2, rec: '1-0' },
};
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const row = (side, i, over = {}) => ({
  id: `${side}${i}`, pos: POS[i], name: `${side} ${i}`, jersey: 10 + i, rt: 70,
  pts: 6, reb: 3, ast: 2, fgm: 3, fga: 7, fouls: 0,
  hot: false, cold: false, out: false, sub: false, spot: false, ...over,
});
const frame = (over = {}) => ({
  phase: 'play', quarter: 1,
  score: { away: 20, home: 22, clock: '4:00', quarter: 'Q1', shot: 20, afoul: 2, hfoul: 1 },
  worm: { samples: [{ elapsed: 0, margin: 0 }], elapsed: 100, domain: 1920, progress: 0.05 },
  teamPanel: { away: { reb: 18, to: 9, fb: 6, paint: 14, fgm: 8, fga: 20, fgPct: 40, tpm: 2, fouls: 7 },
               home: { reb: 22, to: 5, fb: 15, paint: 20, fgm: 10, fga: 20, fgPct: 50, tpm: 4, fouls: 4 } },
  away: POS.map((_, i) => row('away', i)),
  home: POS.map((_, i) => row('home', i)),
  benchAway: [], benchHome: [],
  events: [{ id: 'home0', kind: 'bucket', last: 2 }],
  ticker: null, ...over,
});

async function mount(page, { debug = false } = {}) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(debug ? '/?debug_cards=1' : '/');
  await page.addScriptTag({ url: '/js/config/api-config.js' });
  await page.evaluate(async ({ teams, frames }) => {
    const mod = await import('/js/phaser/utils/simGamePresentation.js');
    mod.showSimGamePresentation({ teams, frames }, { driveScoreboard: false });
  }, { teams: TEAMS, frames: Array.from({ length: 400 }, () => frame()) });
  await page.waitForSelector('.sgp-root [data-fit]');
}

test('the panel is absent by default', async ({ page }) => {
  await mount(page);
  expect(await page.locator('.sgp-dbg').count()).toBe(0);
});

test('?debug_cards=1 shows it', async ({ page }) => {
  await mount(page, { debug: true });
  await expect(page.locator('.sgp-dbg')).toBeVisible();
});

test('it reports fired counts, share, per-quarter and gate values', async ({ page }) => {
  await mount(page, { debug: true });
  await page.waitForFunction(() => {
    const t = document.querySelector('.sgp-dbg');
    return t && /cards fired/.test(t.textContent) && /gates now/.test(t.textContent);
  }, null, { timeout: 8000 });
  const text = await page.locator('.sgp-dbg').textContent();
  expect(text).toContain('playback');
  expect(text).toContain('cards fired');
  expect(text).toContain('share on screen');
  expect(text).toContain('fired by quarter');
  expect(text).toMatch(/Q1[\s\S]*Q2[\s\S]*Q3[\s\S]*Q4/);
  expect(text).toContain('player cool');
  expect(text).toContain('variety hold');
});

test('every suppressed candidate is listed with its reason', async ({ page }) => {
  await mount(page, { debug: true });
  await page.waitForFunction(() => {
    const c = document.querySelector('.sgp-root').__cadence;
    return c && c.stats().suppressed > 0;
  }, null, { timeout: 12000 });
  // Assert against the by-reason SUMMARY, not the whole panel: the candidate log prints the
  // same reason strings, so a panel-wide toContain passes even with the summary deleted.
  const m = await page.evaluate(() => {
    const c = document.querySelector('.sgp-root').__cadence;
    return { reasons: Object.keys(c.stats().suppressedByReason),
             summary: document.querySelector('[data-dbg-reasons]').textContent,
             counts: [...document.querySelectorAll('[data-dbg-reasons] b')].map((b) => Number(b.textContent)) };
  });
  expect(m.reasons.length).toBeGreaterThan(0);
  for (const r of m.reasons) expect(m.summary, r).toContain(r);
  expect(m.counts.length).toBe(m.reasons.length);
  for (const n of m.counts) expect(n).toBeGreaterThan(0);
});

test('it does not disturb the composition it is measuring', async ({ page }) => {
  await mount(page);
  const plain = await page.evaluate(() => {
    const f = document.querySelector('.sgp-root [data-fit]');
    return { w: f.offsetWidth, h: f.offsetHeight, scale: f.getBoundingClientRect().width };
  });
  await mount(page, { debug: true });
  const debugged = await page.evaluate(() => {
    const f = document.querySelector('.sgp-root [data-fit]');
    const dbg = document.querySelector('.sgp-dbg');
    return { w: f.offsetWidth, h: f.offsetHeight, scale: f.getBoundingClientRect().width,
             position: getComputedStyle(dbg).position };
  });
  expect(debugged.position).toBe('fixed');
  expect(debugged.w).toBe(plain.w);
  expect(debugged.h).toBe(plain.h);
  expect(Math.abs(debugged.scale - plain.scale)).toBeLessThan(1);
});

test('it shows the held state when Team Stats is up', async ({ page }) => {
  await mount(page, { debug: true });
  await page.waitForFunction(() => !!document.querySelector('.sgp-root').__cadence, null, { timeout: 8000 });
  await page.click('.sgp-root .ctlseg [data-v="team"]');
  await expect(page.locator('.sgp-dbg h4').first()).toContainText('HELD');
});
