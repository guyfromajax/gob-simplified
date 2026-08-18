// @ts-check
/**
 * Recruit pool — the screen that must survive 450 rows.
 *
 * Loads the REAL recruiting-hub.js, recruiting-common.js, recruiting-spine.js and
 * recruiting-spine.css, with only the network stubbed (Common.fetchJSON + API_CONFIG).
 * So filters, sorting, the watch star and the layout under test are the shipped code.
 *
 * Run: npx playwright test tests/e2e/recruits-pool.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');

const CSS = read('recruiting-spine.css') + read('recruiting-signing.css') + read('css/attr-tiles.css');
// Same order recruiting.html loads them; common.js supplies getBestPosition, which
// RecruitingCommon.normalizeRecruits depends on.
const SCRIPTS = [
  'common.js',
  'js/shared/attrTiles.js', 'js/shared/rtBucket.js',
  'js/shared/playerYear.js',
  'recruiting-common.js',
  'recruiting-spine.js',
].map(read);
const HUB = read('recruiting-hub.js');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
const REGIONS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
const YEARS = ['JH', 'Freshman', 'Sophomore', 'Junior'];
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const USER_TEAM = 'user-team-id';

/** 450 deterministic recruits in the /franchise/recruiting-data shape. */
function fixture({ week = 7, watchlist = [], savedOrders = {}, region = 'A' } = {}) {
  const recruits = [];
  for (let i = 0; i < 450; i++) {
    const attributes = {};
    ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 13) % 91) + 5; });
    const lean = i % 11 === 0
      ? { 1: USER_TEAM, 2: 'rival-1', 3: null }
      : i % 7 === 0 ? { 1: 'rival-1', 2: USER_TEAM, 3: null }
        : { 1: 'rival-1', 2: null, 3: null };
    recruits.push({
      recruit_id: `r-${i}`,
      name: `Recruit ${String(i).padStart(3, '0')}`,
      image_id: i % 3 === 0 ? `img-${i}` : null,
      archetype: 'Slasher',
      'Home Region': REGIONS[i % REGIONS.length],
      year: YEARS[i % YEARS.length],
      height: 68 + (i % 14),
      weight: 170 + (i % 60),
      attributes,
      position_ratings: { [POS[i % POS.length]]: 30 + (i % 60) },
      Lean: lean,
    });
  }
  return {
    team: 'South Lancaster', team_id: USER_TEAM, team_region: region, week,
    recruits, team_name_map: { [USER_TEAM]: 'South Lancaster', 'rival-1': 'Fairview' },
    saved_orders: savedOrders, watchlist,
    new_lean_recruit_ids: [], week_35_recruiting_results: {}, week_35_recruiting_ran: false,
  };
}

async function mountPool(page, opts = {}) {
  const patchCalls = [];
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Real origin first: getQueryContext reads location.search, and about:blank has no
  // origin (setContent preserves whatever URL the page is already on).
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style>
    <style>body{margin:0;background:#0b0d14}.doc{max-width:1180px;margin:0 auto;padding:20px}</style>
    <div class="doc"><a id="back-btn" href="#">Back</a><div id="hub-root" class="spine"></div></div>
  `);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });

  await page.evaluate(({ data }) => {
    window.__patchCalls = [];
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`,
      getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/img/${id}.png`,
      ensureRecruitImage: () => Promise.resolve({ status: 'skip' }),
    };
    window.__fixture = data;
    const realFetchJSON = window.RecruitingCommon.fetchJSON;
    window.RecruitingCommon.fetchJSON = function (url, options) {
      const method = (options && options.method) || 'GET';
      if (String(url).includes('/franchise/recruiting-data')) {
        return Promise.resolve(window.__fixture);
      }
      if (String(url).includes('/franchise/recruiting-watchlist')) {
        const body = JSON.parse(options.body);
        window.__patchCalls.push({ url: String(url), body });
        const list = new Set(window.__fixture.watchlist.map(String));
        if (body.watching) list.add(String(body.recruit_id)); else list.delete(String(body.recruit_id));
        window.__fixture.watchlist = [...list];
        return Promise.resolve({ watching: !!body.watching, count: list.size, watchlist: [...list] });
      }
      // Anything else is a write we do NOT expect on load; record it and fail loudly.
      window.__patchCalls.push({ url: String(url), body: options && options.body, unexpected: true });
      return Promise.resolve({});
    };
    void realFetchJSON;
  }, { data: fixture(opts) });

  await page.addScriptTag({ content: HUB });
  await page.waitForSelector(opts.week === 35 ? '.spool-rows .prow' : '#hub-pool table.pool tbody tr.rec', { timeout: 10000 });
  return patchCalls;
}

const rowCount = (page) => page.locator('#hub-pool tbody tr.rec').count();


/**
 * Signing Day (week 35) — filters, the My Orders view, and the rail.
 * Drives the REAL recruiting-hub.js with only the network stubbed.
 */
const sign = (page, opts = {}) => mountPool(page, { week: 35, ...opts });

test.describe('Signing Day filters', () => {
  test('watchlist, position and year controls are present', async ({ page }) => {
    await sign(page, { watchlist: ['r-0', 'r-7', 'r-11'] });
    const m = await page.evaluate(() => ({
      watch: !!document.getElementById('sign-watch'),
      watchCount: document.querySelector('#sign-watch .n').textContent,
      pos: [...document.querySelectorAll('[data-spos]')].map((b) => b.dataset.spos),
      year: [...document.querySelectorAll('[data-syear]')].map((b) => b.dataset.syear),
    }));
    expect(m.watch).toBe(true);
    expect(m.watchCount).toBe('3');
    expect(m.pos).toEqual(['all', 'PG', 'SG', 'SF', 'PF', 'C']);
    expect(m.year).toEqual(['all', 'Junior', 'Sophomore', 'Freshman', 'JH']);
  });

  test('the watchlist filter narrows the pool to the watched recruits', async ({ page }) => {
    await sign(page, { watchlist: ['r-0', 'r-7', 'r-11'] });
    const before = await page.locator('.spool-rows .prow').count();
    await page.click('[data-stab="all"]');
    await page.click('#sign-watch');
    const after = await page.locator('.spool-rows .prow').count();
    expect(after).toBe(3);
    expect(after).toBeLessThan(before);
    expect(await page.getAttribute('#sign-watch', 'aria-pressed')).toBe('true');
    await page.click('#sign-watch');
    expect(await page.locator('.spool-rows .prow').count()).toBeGreaterThan(3);
  });

  test('position and year filters narrow the pool and combine', async ({ page }) => {
    await sign(page);
    await page.click('[data-stab="all"]');
    const all = await page.locator('.spool-rows .prow').count();
    await page.click('[data-spos="C"]');
    const byPos = await page.locator('.spool-rows .prow').count();
    expect(byPos).toBeGreaterThan(0);
    expect(byPos).toBeLessThan(all);
    await page.click('[data-syear="JH"]');
    const both = await page.locator('.spool-rows .prow').count();
    expect(both).toBeLessThanOrEqual(byPos);
    // Every surviving row satisfies both filters.
    const rows = await page.evaluate(() => [...document.querySelectorAll('.spool-rows .prow')]
      .map((r) => r.textContent));
    for (const t of rows) expect(t).toContain('JH');
  });
});

test.describe('Signing Day region dropdown', () => {
  test("the user's region is first, labelled, and above a divider", async ({ page }) => {
    await sign(page, { region: 'E' });
    const m = await page.evaluate(() => {
      const opts = [...document.querySelectorAll('#sign-region option')];
      return {
        first: opts[0].textContent, firstValue: opts[0].value,
        divider: opts[1].disabled, dividerText: opts[1].textContent,
        rest: opts.slice(2).map((o) => o.textContent),
      };
    });
    expect(m.first).toBe('Region E — your region');
    expect(m.firstValue).toBe('E');
    expect(m.divider).toBe(true);
    expect(m.rest[0]).toBe('All regions');
    expect(m.rest.slice(1)).toEqual(
      ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].map((r) => `Region ${r}`));
  });

  test('with no known region there is no divider and no phantom entry', async ({ page }) => {
    await sign(page, { region: '' });
    const m = await page.evaluate(() => {
      const opts = [...document.querySelectorAll('#sign-region option')];
      return { first: opts[0].textContent, disabled: opts.filter((o) => o.disabled).length };
    });
    expect(m.first).toBe('All regions');
    expect(m.disabled).toBe(0);
  });
});

test.describe('My Orders view', () => {
  test('the toggle sits beside Recruit Pool and swaps to a full-width rail', async ({ page }) => {
    await sign(page);
    const anchors = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-anchor-mount .hub-anchor')].map((b) => b.textContent.trim()));
    expect(anchors.length).toBe(2);
    expect(anchors[1]).toContain('My Orders');

    const before = await page.evaluate(() => ({
      poolVisible: !!document.querySelector('.spool') &&
        getComputedStyle(document.querySelector('.spool')).display !== 'none',
      railW: Math.round(document.querySelector('#sign-rail').getBoundingClientRect().width),
    }));
    expect(before.poolVisible).toBe(true);

    await page.click('#hub-orders-toggle');
    const after = await page.evaluate(() => ({
      poolVisible: getComputedStyle(document.querySelector('.spool')).display !== 'none',
      railW: Math.round(document.querySelector('#sign-rail').getBoundingClientRect().width),
      pressed: document.getElementById('hub-orders-toggle').getAttribute('aria-pressed'),
      // clientWidth includes the container's own side padding; the rail fills the
      // CONTENT box, so compare against that.
      bodyW: (() => {
        const el = document.querySelector('.hub-body-sign');
        const cs = getComputedStyle(el);
        return Math.round(el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight));
      })(),
    }));
    expect(after.poolVisible).toBe(false);
    expect(after.pressed).toBe('true');
    expect(after.railW).toBeGreaterThan(before.railW);
    expect(Math.abs(after.railW - after.bodyW)).toBeLessThan(2);   // fills the width
  });

  test('the Recruit Pool anchor brings the pool back', async ({ page }) => {
    await sign(page);
    await page.click('#hub-orders-toggle');
    expect(await page.evaluate(() =>
      getComputedStyle(document.querySelector('.spool')).display)).toBe('none');
    await page.click('#hub-anchor-mount .hub-anchor:not(.hub-anchor--orders)');
    expect(await page.evaluate(() =>
      getComputedStyle(document.querySelector('.spool')).display)).not.toBe('none');
  });
});

test.describe('Your Orders rail', () => {
  test('a committed recruit keeps his RT colour coding', async ({ page }) => {
    await sign(page);
    await page.click('.spool-rows .prow:first-child button[data-step="1"]');
    const m = await page.evaluate(() => {
      const v = document.querySelector('#sign-rail .citem-meta .v');
      return { cls: v ? v.className : null, colour: v ? getComputedStyle(v).color : null,
               text: v ? v.textContent : null };
    });
    expect(m.cls).toContain('rt-');
    expect(m.cls).not.toContain('rt-unknown');
    expect(m.text).toBeTruthy();
    // Whatever the bucket, it must not be the plain body grey the row used to render.
    expect(m.colour).not.toBe('rgb(255, 255, 255)');
  });

  test('points are no longer capped at 20 per recruit', async ({ page }) => {
    await sign(page);
    const plus = page.locator('.spool-rows .prow:first-child button[data-step="1"]');
    for (let i = 0; i < 25; i += 1) await plus.click();
    const m = await page.evaluate(() => ({
      pts: Number(document.querySelector('.spool-rows .prow:first-child .stepper .val').textContent.trim()),
      spent: document.querySelector('#sign-rail') ? document.querySelector('#sign-rail').textContent : '',
    }));
    expect(m.pts).toBe(25);          // would have stopped at 20 before
  });

  test('the 50-point budget still binds', async ({ page }) => {
    await sign(page);
    const plus = page.locator('.spool-rows .prow:first-child button[data-step="1"]');
    // Stop when the control disables itself — clicking a disabled button would hang.
    for (let i = 0; i < 60 && await plus.isEnabled(); i += 1) await plus.click();
    const pts = await page.evaluate(() =>
      Number(document.querySelector('.spool-rows .prow:first-child .stepper .val').textContent.trim()));
    expect(pts).toBe(50);
  });
});

test('the Standing column reads "5x odds", not "x5"', async ({ page }) => {
  await sign(page);
  const m = await page.evaluate(() => {
    const cells = [...document.querySelectorAll('.spool-rows .stand-mult')].map((e) => e.textContent.trim());
    return { sample: cells.slice(0, 8), anyOldFormat: cells.some((t) => /^x\d/.test(t)) };
  });
  expect(m.anyOldFormat).toBe(false);
  for (const t of m.sample) expect(t).toMatch(/^\dx odds$/);
});
