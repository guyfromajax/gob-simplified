// @ts-check
/**
 * Unsubmitted recruiting edits survive leaving the page.
 *
 * Opening a recruit's profile from the board and coming back is a full navigation, so
 * without a draft the hub reloads the SERVER copy and the player's edits are gone. The
 * draft is sessionStorage, keyed by franchise + team + week, same pattern as the
 * training form draft in training.js.
 *
 * Both phases are covered: the invite board (weeks 20-26) and the week-35 allocation.
 * Real recruiting-hub.js / -common.js / -spine.js, network stubbed.
 *
 * Run: npx playwright test tests/e2e/recruiting-draft.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const CSS = read('recruiting-spine.css') + read('recruiting-signing.css') + read('css/attr-tiles.css');
const SCRIPTS = ['common.js', 'js/shared/attrTiles.js', 'js/shared/rtBucket.js', 'js/shared/playerYear.js',
  'recruiting-common.js', 'recruiting-spine.js'].map(read);
const HUB = read('recruiting-hub.js');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const USER = 'user-team-id';

function recruit(i, leanRank) {
  const attributes = {};
  ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 11) % 91) + 5; });
  const lean = leanRank === 1 ? { 1: USER, 2: 'rival-1', 3: null }
    : leanRank === 2 ? { 1: 'rival-1', 2: USER, 3: null }
      : { 1: 'rival-1', 2: 'rival-2', 3: null };
  return {
    recruit_id: `r-${i}`, name: `Recruit ${String(i).padStart(2, '0')}`,
    image_id: `img-${i}`, archetype: 'Slasher', 'Home Region': 'C',
    year: 'JH', height: 72, weight: 190, attributes,
    position_ratings: { [POS[i % POS.length]]: 80 - i }, Lean: lean,
  };
}

function fixture(o = {}) {
  const week = o.week ?? 21;
  const recruits = [];
  for (let i = 0; i < 12; i++) recruits.push(recruit(i, i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0));
  const savedOrders = {};
  (o.board || []).forEach((id, i) => { savedOrders[String(i + 1)] = id; });
  return {
    team: 'Kettle Falls', team_id: USER, team_region: 'C', week, recruits,
    team_name_map: { [USER]: 'Kettle Falls', 'rival-1': 'Fairview', 'rival-2': 'Brackenridge' },
    saved_orders: savedOrders, watchlist: o.watchlist || [], new_lean_recruit_ids: [],
    week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    saved_order_entries_week_35: o.savedEntries || [],
    week_35_points_budget: 50,
    roster_capacity: { roster_spots: 4, scholarships: 2, roster_cap: 15, roster_used: 11 },
    competition_counts: { 'r-0': 6, 'r-1': 1, 'r-3': 5 },
    recruiting_wire: {
      week, seen_week: 0, unseen_count: 0, counts: { moved: 0, dropped: 0 },
      events: [], events_this_week: [], visited_recruit_ids: [],
      board_saved_week: 0, has_saved_board: !!(o.board || []).length,
    },
  };
}

/**
 * Mount the hub. Calling this again on the same page is a RETURN navigation: the origin
 * is unchanged, so sessionStorage — and therefore any draft — carries over.
 */
async function mount(page, o = {}) {
  await page.setViewportSize({ width: 1500, height: 1100 });
  await page.route('**/franchise-command-center*', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>fcc</body></html>' }));
  // The real homepage is never used — setContent replaces the document on the next
  // line. goto only supplies a same-origin URL (sessionStorage, location.search), so
  // serve a stub and skip a full app page load per test. Under parallel workers those
  // loads queue on the dev server and were the cause of intermittent timeouts here.
  await page.route('**/', (route) => (route.request().resourceType() === 'document'
    ? route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>o</title>' })
    : route.continue()));
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style><style>body{margin:0}.doc{max-width:1440px;margin:0 auto;padding:16px}</style>
    <div class="doc"><a id="back-btn" href="#"></a><div id="hub-root" class="spine"></div></div>`);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });
  await page.evaluate(({ data }) => {
    window.__writes = [];
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`, getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/${id}.png`,
      ensureRecruitImage: () => Promise.resolve({ status: 'skip' }),
    };
    window.RecruitingCommon.fetchJSON = function (url, options) {
      const u = String(url);
      if (u.includes('/franchise/recruiting-data')) return Promise.resolve(data);
      window.__writes.push({ url: u, body: (options || {}).body });
      // Mirrored: submitting the board now leaves for the FCC on the same tick, so a
      // page-scoped array is gone before a test can read it.
      try { sessionStorage.setItem('__writes', JSON.stringify(window.__writes)); } catch (e) { void e; }
      if (u.includes('recruiting-watchlist')) return Promise.resolve({ watching: true, count: 1, watchlist: [] });
      return Promise.resolve({ status: 'success' });
    };
  }, { data: fixture(o) });
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector(o.week === 35 ? '#hub-sign .prow' : '#hub-board .bpanel', { timeout: 10000 });
}

const boardIds = (page) => page.evaluate(() =>
  [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id));

/** The allocation as the signing rows report it: id -> points, funded rows only. */
const allocOf = (page) => page.evaluate(() => {
  const out = {};
  document.querySelectorAll('#hub-sign .prow').forEach((r) => {
    const val = r.querySelector('.stepper .val');
    const n = val ? Number(val.textContent.trim()) : 0;
    if (r.dataset.id && n > 0) out[r.dataset.id] = n;
  });
  return out;
});

/** Real HTML5 drag on the board — the reorder path has no click handler of its own. */
async function dragRow(page, fromIndex, toIndex) {
  await page.evaluate(({ fromIndex, toIndex }) => {
    const row = (i) => document.querySelector(`#hub-board .brow[data-index="${i}"]`);
    const dt = new DataTransfer();
    row(fromIndex).dispatchEvent(new DragEvent('dragstart', { dataTransfer: dt, bubbles: true }));
    row(toIndex).dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }));
    row(toIndex).dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  }, { fromIndex, toIndex });
}

/** Write a draft directly, to exercise restore against payloads the UI cannot produce. */
async function seedDraft(page, week, payload) {
  await page.evaluate(({ week, payload }) => {
    sessionStorage.setItem(`gob_recruiting_draft_fid-test|user-team-id|w${week}`, JSON.stringify(payload));
  }, { week, payload });
}

test.beforeEach(async ({ page }) => {
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.evaluate(() => sessionStorage.clear());
});

test.describe('invite board', () => {
  test('an edited board survives leaving and coming back', async ({ page }) => {
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    await page.click('#hub-board .brow[data-id="r-2"] .bx');
    expect(await boardIds(page)).toEqual(['r-1', 'r-3']);
    // The profile round trip: same origin, full reload, server copy unchanged.
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    expect(await boardIds(page)).toEqual(['r-1', 'r-3']);
  });

  test('a reorder survives too, not just an add or remove', async ({ page }) => {
    // Drag has no click handler of its own, so this is the case a per-button hook
    // would miss.
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    await dragRow(page, 0, 2);
    const after = await boardIds(page);
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    expect(await boardIds(page)).toEqual(after);
    expect(after).not.toEqual(['r-1', 'r-2', 'r-3']);
  });

  test('submitting the board ends the draft — the server copy takes over', async ({ page }) => {
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    await page.click('#hub-board .brow[data-id="r-2"] .bx');
    await page.click('#dock-save');
    await page.waitForURL('**/franchise-command-center*', { timeout: 5000 });
    // The server now holds ['r-1','r-3']; the next load reflects THAT, not a stale draft.
    await mount(page, { week: 21, board: ['r-1', 'r-3'] });
    expect(await boardIds(page)).toEqual(['r-1', 'r-3']);
    expect(await page.evaluate(() =>
      sessionStorage.getItem('gob_recruiting_draft_fid-test|user-team-id|w21'))).toBe(null);
  });

  // Week scoping is deliberately doubled: the key carries the week AND the payload
  // re-states it, so a week that advances in another tab cannot resurrect last week's
  // edit under a reused key. Either guard alone satisfies this test.
  test('a draft never crosses into another week', async ({ page }) => {
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    await page.click('#hub-board .brow[data-id="r-2"] .bx');
    // Week 22 opens on the board the server holds. Last week's unsubmitted edit is not
    // a decision about this week.
    await mount(page, { week: 22, board: ['r-1', 'r-2', 'r-3'] });
    expect(await boardIds(page)).toEqual(['r-1', 'r-2', 'r-3']);
  });

  test('recruits the draft names but the pool no longer has are dropped', async ({ page }) => {
    // Asserted on what gets SENT, not on what renders: an unknown id draws as an empty
    // slot either way, so the DOM cannot tell a filtered board from an unfiltered one.
    // Left in, it would hold a rank and go up with the submission.
    await seedDraft(page, 21, { v: 1, week: 21, phase: 'invite', board: ['r-1', 'ghost-9', 'r-3'], alloc: {} });
    await mount(page, { week: 21, board: ['r-1', 'r-2', 'r-3'] });
    expect(await boardIds(page)).toEqual(['r-1', 'r-3']);
    await page.click('#dock-save');
    await page.waitForURL('**/franchise-command-center*', { timeout: 5000 });
    const sent = await page.evaluate(() => {
      const w = JSON.parse(sessionStorage.getItem('__writes') || '[]')
        .find((x) => String(x.url).includes('recruiting-orders'));
      return w ? JSON.parse(w.body).recruit_ids : null;
    });
    expect(sent).toEqual(['r-1', 'r-3']);
  });

  test('a draft from a different phase is ignored', async ({ page }) => {
    await seedDraft(page, 21, { v: 1, week: 21, phase: 'day', board: ['r-5'], alloc: {} });
    await mount(page, { week: 21, board: ['r-1', 'r-2'] });
    expect(await boardIds(page)).toEqual(['r-1', 'r-2']);
  });
});

test.describe('signing day allocation', () => {
  test('unsubmitted points survive leaving and coming back', async ({ page }) => {
    await mount(page, { week: 35 });
    await page.click('#hub-sign .prow[data-id="r-0"] button[data-step="1"]');
    await page.click('#hub-sign .prow[data-id="r-0"] button[data-step="1"]');
    await page.click('#hub-sign .prow[data-id="r-3"] button[data-step="1"]');
    const before = await allocOf(page);
    expect(before).toEqual({ 'r-0': 2, 'r-3': 1 });
    await mount(page, { week: 35 });
    expect(await allocOf(page)).toEqual(before);
  });

  test('submitting the orders ends the draft', async ({ page }) => {
    await mount(page, { week: 35 });
    await page.click('#hub-sign .prow[data-id="r-0"] button[data-step="1"]');
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    expect(await page.evaluate(() =>
      sessionStorage.getItem('gob_recruiting_draft_fid-test|user-team-id|w35'))).toBe(null);
  });

  test('an over-budget draft is discarded whole, not clamped', async ({ page }) => {
    // The UI cannot produce 60 of 50; only a tampered or stale payload can. Restoring
    // it would leave a board that can never be submitted.
    await seedDraft(page, 35, {
      v: 1, week: 35, phase: 'day', board: [],
      alloc: { 'r-0': { points: 40, promise: false }, 'r-1': { points: 20, promise: false } },
    });
    await mount(page, { week: 35, savedEntries: [{ id: 'r-3', points: 7, playing_time: false }] });
    expect(await allocOf(page)).toEqual({ 'r-3': 7 });
  });

  test('a draft beats the saved entries it was edited from', async ({ page }) => {
    await mount(page, { week: 35, savedEntries: [{ id: 'r-3', points: 7, playing_time: false }] });
    await page.click('#hub-sign .prow[data-id="r-3"] button[data-step="1"]');
    await mount(page, { week: 35, savedEntries: [{ id: 'r-3', points: 7, playing_time: false }] });
    expect(await allocOf(page)).toEqual({ 'r-3': 8 });
  });
});
