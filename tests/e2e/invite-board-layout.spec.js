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

const CSS = read('recruiting-spine.css') + read('css/attr-tiles.css');
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
function fixture({ week = 7, watchlist = [], savedOrders = {}, visitHistory = null } = {}) {
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
    team: 'South Lancaster', team_id: USER_TEAM, team_region: 'A', week,
    recruits, team_name_map: { [USER_TEAM]: 'South Lancaster', 'rival-1': 'Fairview' },
    saved_orders: savedOrders, watchlist,
    new_lean_recruit_ids: [], week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    // Weeks 20-26; a null recruit_id is an invite still to spend.
    visit_history: visitHistory
      || [20, 21, 22, 23, 24, 25, 26].map((w) => ({ week: w, recruit_id: null, name: null, lean: null })),
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
  await page.waitForSelector('#hub-pool table.pool tbody tr.rec', { timeout: 10000 });
  return patchCalls;
}

const rowCount = (page) => page.locator('#hub-pool tbody tr.rec').count();


/** Invite Board (weeks 20-26) — two fixed columns of ten, static size. */
const board = (page) => page.evaluate(() => {
  const cols = [...document.querySelectorAll('#hub-board .bcol')];
  const rows = (c) => [...c.querySelectorAll('.brow:not(.bhdr)')];
  return {
    columns: cols.length,
    perColumn: cols.map((c) => rows(c).length),
    ranks: cols.flatMap((c) => rows(c).map((r) => r.querySelector('.bnum').textContent.trim())),
    empties: document.querySelectorAll('#hub-board .brow.is-empty').length,
    heads: [...document.querySelectorAll('#hub-board .bcol:first-child .bhdr div')].map((d) => d.textContent.trim()),
    hero: document.querySelectorAll('#hub-board .bhero').length,
    cta: (document.getElementById('dock-save') || {}).textContent,
    ctaInHead: !!document.querySelector('#hub-board .bpanel-head #dock-save'),
    countInHead: !!document.querySelector('#hub-board .bpanel-head .bpanel-count'),
    panelH: Math.round(document.querySelector('#hub-board .bpanel').getBoundingClientRect().height),
  };
});

test.describe('Invite Board layout', () => {
  test('two columns of ten, all 20 ranks always present', async ({ page }) => {
    await mountPool(page, { week: 22, savedOrders: {} });
    const m = await board(page);
    expect(m.columns).toBe(2);
    expect(m.perColumn).toEqual([10, 10]);
    expect(m.ranks).toEqual(Array.from({ length: 20 }, (_, i) => String(i + 1)));
    expect(m.empties).toBe(20);           // nothing ranked yet — 20 open slots
  });

  test('the panel is a static size however many are ranked', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const empty = (await board(page)).panelH;
    // Rank three recruits through the real + control.
    for (const i of [0, 1, 2]) {
      await page.click(`#hub-pool tbody tr.rec:nth-child(${i + 1}) .pool-add`);
    }
    const filled = await board(page);
    expect(filled.panelH).toBe(empty);    // the pool below never gets pushed down
    expect(filled.empties).toBe(17);
    expect(filled.perColumn).toEqual([10, 10]);
  });

  test('header carries the count and Submit Invites; the hero panel is gone', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const m = await board(page);
    expect(m.cta).toBe('Submit Invites');
    expect(m.ctaInHead).toBe(true);
    expect(m.countInHead).toBe(true);
    expect(m.hero).toBe(0);               // "No invite target" removed as redundant
  });

  test('row columns are Pos, RT, Yr, Ht, Wt, Lean — This week is gone', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const m = await board(page);
    expect(m.heads).toEqual(['#', 'Recruit', 'Pos', 'RT', 'Yr', 'Ht', 'Wt', 'Lean', '', '']);
    expect(m.heads).not.toContain('This week');
  });

  test('a ranked row shows headshot, name and archetype stacked', async ({ page }) => {
    await mountPool(page, { week: 22 });
    await page.click('#hub-pool tbody tr.rec:first-child .pool-add');
    const m = await page.evaluate(() => {
      const row = document.querySelector('#hub-board .brow:not(.bhdr):not(.is-empty)');
      const name = row.querySelector('.btxt a, .btxt');
      const arch = row.querySelector('.btxt small');
      return {
        headshot: !!row.querySelector('.bav'),
        arch: arch ? arch.textContent.trim() : null,
        stacked: arch ? arch.getBoundingClientRect().top > name.getBoundingClientRect().top : false,
        wt: !!row.querySelector('.bc'),
      };
    });
    expect(m.headshot).toBe(true);
    expect(m.arch).toBeTruthy();
    expect(m.stacked).toBe(true);
  });
});

test.describe('visit chip', () => {
  test('a recruit who visited shows a week-stamped chip', async ({ page }) => {
    await mountPool(page, {
      week: 23,
      savedOrders: { 1: 'r-0' },
      visitHistory: [
        { week: 20, recruit_id: 'r-0', name: 'Recruit 000', lean: {} },
        ...[21, 22, 23, 24, 25, 26].map((w) => ({ week: w, recruit_id: null, name: null, lean: null })),
      ],
    });
    const m = await page.evaluate(() => {
      const row = document.querySelector('#hub-board .brow[data-id="r-0"]');
      const chip = row && row.querySelector('.bvisit-chip');
      return { chip: chip ? chip.textContent.trim() : null,
               marked: row ? row.classList.contains('is-visited') : false,
               others: document.querySelectorAll('#hub-board .bvisit-chip').length };
    });
    expect(m.chip).toBe('Wk 20');
    expect(m.marked).toBe(true);
    expect(m.others).toBe(1);           // only the recruit who actually visited
  });
});

// SUPERSEDED: 'Season panel visit log'.
//
// The visit list moved out of the Season panel and became the seven-square calendar
// above the invite board — a list of seven rows read as history, where seven squares in
// a row read as a budget, which is what invite season is. Its successor covers the same
// ground and more (the three empty states, which the list conflated into one) in
// tests/e2e/invite-visit-calendar.spec.js.

test('the pool now shows Wt', async ({ page }) => {
  await mountPool(page, { week: 7 });
  const m = await page.evaluate(() => {
    const heads = [...document.querySelectorAll('#hub-pool thead th')].map((h) => h.textContent.trim());
    const cells = document.querySelectorAll('#hub-pool tbody tr.rec:first-child td').length;
    return { heads, cells };
  });
  expect(m.heads).toContain('Wt');
  expect(m.cells).toBe(m.heads.length);   // header and body stay in step
});
