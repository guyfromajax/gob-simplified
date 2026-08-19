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
function fixture({ week = 7, watchlist = [], savedOrders = {}, visitHistory = null,
  threeLeans = false, archetype = 'Slasher' } = {}) {
  const recruits = [];
  for (let i = 0; i < 450; i++) {
    const attributes = {};
    ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 13) % 91) + 5; });
    // threeLeans fills every slot — the case that made the old edge-of-row week stamp
    // and the lean ladder fight for the same space.
    const lean = threeLeans
      ? { 1: USER_TEAM, 2: 'rival-1', 3: 'rival-2' }
      : i % 11 === 0
        ? { 1: USER_TEAM, 2: 'rival-1', 3: null }
        : i % 7 === 0 ? { 1: 'rival-1', 2: USER_TEAM, 3: null }
          : { 1: 'rival-1', 2: null, 3: null };
    recruits.push({
      recruit_id: `r-${i}`,
      name: `Recruit ${String(i).padStart(3, '0')}`,
      image_id: i % 3 === 0 ? `img-${i}` : null,
      archetype,
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
    recruits, team_name_map: { [USER_TEAM]: 'South Lancaster', 'rival-1': 'Fairview', 'rival-2': 'Brackenridge' },
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
    // One trailing unlabelled column (the remove button). The visit column that used to
    // sit beside it is gone — the count moved in beside the archetype.
    expect(m.heads).toEqual(['#', 'Recruit', 'Pos', 'RT', 'Yr', 'Ht', 'Wt', 'Lean', '']);
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

test.describe('visit pill', () => {
  const hist = (byWeek) => [20, 21, 22, 23, 24, 25, 26].map((w) => ({
    week: w, recruit_id: byWeek[w] || null, name: byWeek[w] ? `Recruit ${byWeek[w]}` : null, lean: null,
  }));

  const pills = (page) => page.evaluate(() =>
    Object.fromEntries([...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => {
      const p = r.querySelector('.bvisit-pill');
      return [r.dataset.id, p ? p.textContent.trim() : null];
    })));

  test('counts visits and agrees with itself on the plural', async ({ page }) => {
    // r-0 came three times, r-1 once, r-2 never. The COUNT is the payload — which weeks
    // is already the whole point of the calendar above the board.
    await mountPool(page, {
      week: 26,
      savedOrders: { 1: 'r-0', 2: 'r-1', 3: 'r-2' },
      visitHistory: hist({ 20: 'r-0', 21: 'r-1', 22: 'r-0', 24: 'r-0' }),
    });
    expect(await pills(page)).toEqual({ 'r-0': '3 visits', 'r-1': '1 visit', 'r-2': null });
  });

  test('it sits beside the archetype, not out at the row edge', async ({ page }) => {
    // The old week stamp lived in its own column next to the lean ladder, where three
    // leans left it nowhere to go. That column is gone.
    await mountPool(page, {
      week: 23, savedOrders: { 1: 'r-0' }, visitHistory: hist({ 20: 'r-0' }),
    });
    const m = await page.evaluate(() => {
      const row = document.querySelector('#hub-board .brow[data-id="r-0"]');
      const pill = row.querySelector('.bvisit-pill').getBoundingClientRect();
      const arch = row.querySelector('.barch').getBoundingClientRect();
      const ladder = row.querySelector('.bladder').getBoundingClientRect();
      return {
        rightOfArchetype: pill.left >= arch.right - 1,
        leftOfLadder: pill.right <= ladder.left,
        marked: row.classList.contains('is-visited'),
        oldColumn: document.querySelectorAll('#hub-board .bvisit, #hub-board .bvisit-chip').length,
      };
    });
    expect(m.rightOfArchetype).toBe(true);
    expect(m.leftOfLadder).toBe(true);
    expect(m.marked).toBe(true);
    expect(m.oldColumn).toBe(0);
  });

  test('a full three-lean ladder is not squeezed by it', async ({ page }) => {
    // The reason for the change: the ladder must render all three slots at full width
    // whether or not the row also carries a pill.
    await mountPool(page, {
      week: 26,
      savedOrders: { 1: 'r-0', 2: 'r-2' },
      visitHistory: hist({ 20: 'r-0', 22: 'r-0' }),
      threeLeans: true,
    });
    const m = await page.evaluate(() => {
      const box = (id) => {
        const r = document.querySelector(`#hub-board .brow[data-id="${id}"]`);
        return { slots: r.querySelectorAll('.lb-slot').length,
                 w: r.querySelector('.bladder').getBoundingClientRect().width,
                 pill: !!r.querySelector('.bvisit-pill') };
      };
      return { visited: box('r-0'), clean: box('r-2') };
    });
    expect(m.visited.pill).toBe(true);
    expect(m.clean.pill).toBe(false);
    expect(m.visited.slots).toBe(3);
    expect(m.clean.slots).toBe(3);
    // Same ladder width in both rows: the pill changed no column.
    expect(Math.abs(m.visited.w - m.clean.w)).toBeLessThan(1);
  });

  test('a long archetype shortens itself rather than pushing the pill out', async ({ page }) => {
    await mountPool(page, {
      week: 26,
      savedOrders: { 1: 'r-0' },
      visitHistory: hist({ 20: 'r-0' }),
      archetype: 'Downhill Rim-Pressuring Slashing Combo Forward',
    });
    const m = await page.evaluate(() => {
      const row = document.querySelector('#hub-board .brow[data-id="r-0"]');
      const small = row.querySelector('.btxt small').getBoundingClientRect();
      const pill = row.querySelector('.bvisit-pill').getBoundingClientRect();
      const arch = row.querySelector('.barch');
      // Clipping is a PAINT effect, so no geometry API distinguishes it: scrollWidth
      // exceeds clientWidth whether the overflow is clipped or spilling across the Pos
      // column, and a Range still reports the full text extent either way. The
      // computed style is the mechanism, so it is what gets asserted.
      const cs = getComputedStyle(arch);
      return {
        pillInside: pill.right <= small.right + 1,
        pillFull: pill.width > 30,
        archOverflows: arch.scrollWidth > arch.clientWidth,
        archClips: cs.overflow === 'hidden' && cs.textOverflow === 'ellipsis',
      };
    });
    expect(m.archOverflows).toBe(true);   // there IS more text than room
    expect(m.archClips).toBe(true);       // and it is clipped, not spilling
    expect(m.pillInside).toBe(true);
    expect(m.pillFull).toBe(true);
  });
});

test.describe('board shape tiles', () => {
  const posTiles = (page) => page.evaluate(() =>
    [...document.querySelectorAll('#hub-board .bpos-t')].map((t) => ({
      pos: t.querySelector('b').textContent.trim(),
      n: Number(t.querySelector('i').textContent.trim()),
      zero: t.classList.contains('is-zero'),
    })));

  test('one tile per position, always all five, in playbook order', async ({ page }) => {
    await mountPool(page, { week: 22, savedOrders: {} });
    const t = await posTiles(page);
    expect(t.map((x) => x.pos)).toEqual(['PG', 'SG', 'SF', 'PF', 'C']);
    // An empty board still draws all five: the gap is the point, and a tile that
    // vanishes at zero hides exactly the thing worth seeing.
    expect(t.every((x) => x.n === 0 && x.zero)).toBe(true);
  });

  test('counts follow the board, and update as it is edited', async ({ page }) => {
    await mountPool(page, { week: 22 });
    // Add the first four pool rows, then read what the tiles say against the rows.
    for (let i = 0; i < 4; i++) await page.click(`#hub-pool tbody tr.rec:nth-child(${i + 1}) .pool-add`);
    const m = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#hub-board .brow[data-id]')]
        .map((r) => r.querySelectorAll('.bc')[0].textContent.trim());
      const tiles = Object.fromEntries([...document.querySelectorAll('#hub-board .bpos-t')]
        .map((t) => [t.querySelector('b').textContent.trim(), Number(t.querySelector('i').textContent.trim())]));
      return { rows, tiles };
    });
    const expected = { PG: 0, SG: 0, SF: 0, PF: 0, C: 0 };
    m.rows.forEach((p) => { expected[p] += 1; });
    expect(m.tiles).toEqual(expected);
    expect(m.rows).toHaveLength(4);

    // Remove one and the tiles follow — they are derived, not stamped once at load.
    await page.click('#hub-board .brow[data-id] .bx');
    const after = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .bpos-t i')]
        .reduce((n, i) => n + Number(i.textContent.trim()), 0));
    expect(after).toBe(3);
  });

  test('they sit between the title and the action, on the header centre line', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const m = await page.evaluate(() => {
      const head = document.querySelector('#hub-board .bpanel-head').getBoundingClientRect();
      const title = document.querySelector('#hub-board .bpanel-title').getBoundingClientRect();
      const cta = document.querySelector('#hub-board #dock-save').getBoundingClientRect();
      const tiles = document.querySelector('#hub-board .bpos').getBoundingClientRect();
      return {
        afterTitle: tiles.left >= title.right,
        beforeCta: tiles.right <= cta.left,
        inHead: tiles.top >= head.top - 1 && tiles.bottom <= head.bottom + 1,
        vCentred: Math.abs((tiles.top + tiles.bottom) / 2 - (head.top + head.bottom) / 2) < 2,
      };
    });
    expect(m.afterTitle).toBe(true);
    expect(m.beforeCta).toBe(true);
    expect(m.inHead).toBe(true);
    expect(m.vCentred).toBe(true);
  });

  test('the board title carries no eyebrow', async ({ page }) => {
    await mountPool(page, { week: 21 });
    expect(await page.locator('#hub-board .bpanel-title small').count()).toBe(0);
    expect(await page.evaluate(() =>
      document.querySelector('#hub-board .bpanel-title').textContent.trim())).toBe('Invite Board');
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
