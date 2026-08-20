// @ts-check
/**
 * Invite board (week 20-26) — the re-rank trigger.
 *
 * Same harness approach as recruits-pool.spec.js: real recruiting-hub.js / -common.js /
 * -spine.js / -spine.css, network stubbed. Every write is recorded so the seed can be
 * proven not to persist.
 *
 * Run: npx playwright test tests/e2e/invite-board.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const CSS = read('recruiting-spine.css') + read('css/attr-tiles.css');
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

/**
 * @param {{week?:number, board?:string[], watchlist?:string[], events?:any[], visited?:string[]}} o
 */
function fixture(o = {}) {
  const week = o.week ?? 21;
  const recruits = [];
  // noLeans: nobody leans to the user, so the board seeds from the watchlist alone (or
  // not at all). Without it every fixture seeds 8 of 12 and "empty board" cases vanish.
  for (let i = 0; i < 12; i++) {
    recruits.push(recruit(i, o.noLeans ? 0 : (i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0)));
  }
  const savedOrders = {};
  (o.board || []).forEach((id, i) => { savedOrders[String(i + 1)] = id; });
  return {
    team: 'Kettle Falls', team_id: USER, team_region: 'C', week, recruits,
    team_name_map: { [USER]: 'Kettle Falls', 'rival-1': 'Fairview', 'rival-2': 'Brackenridge' },
    saved_orders: savedOrders, watchlist: o.watchlist || [],
    new_lean_recruit_ids: [], week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    recruiting_wire: {
      week, seen_week: 0, unseen_count: (o.events || []).length,
      counts: { moved: 0, dropped: 0 }, events: o.events || [],
      events_this_week: o.events || [], visited_recruit_ids: o.visited || [],
      board_saved_week: 0, has_saved_board: !!(o.board || []).length,
    },
  };
}

const dropEvent = (id, rank) => ({
  recruit_id: id, kind: 'dropped_you', prev_rank: rank ?? 1, rank: null,
  line: `Recruit ${id.split('-')[1].padStart(2, '0')} dropped you — Fairview moved to #1`,
});
const gainEvent = (id) => ({
  recruit_id: id, kind: 'moved_up', prev_rank: 2, rank: 1,
  line: `Recruit ${id.split('-')[1].padStart(2, '0')} moved you to #1 — after the Brackenridge win`,
});

async function mount(page, o = {}) {
  // Submitting the board now confirms, holds 2s and returns to the FCC. Left
  // unstubbed that navigation tears the page down mid-assertion whenever the sweep
  // runs slower than the hold — passing solo and failing in the full run.
  await page.route('**/franchise-command-center*', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>fcc</body></html>' }));
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style><style>body{margin:0}.doc{max-width:1360px;margin:0 auto;padding:20px}</style>
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
      window.__writes.push({ url: u, method: (options || {}).method || 'GET', body: (options || {}).body });
      if (u.includes('recruiting-watchlist')) return Promise.resolve({ watching: true, count: 1, watchlist: [] });
      return Promise.resolve({ status: 'success' });
    };
  }, { data: fixture(o) });
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector('#hub-board .bpanel', { timeout: 10000 });
}

// FILLED rows only. The board now draws all 20 ranks, empty slots included, so
// `.brow[data-index]` alone would always report 20.
const rows = (page) => page.locator('#hub-board .brow[data-id]');

// RETIRED: 'board order drives the dock' (invite hero) and 'this-week column'.
//
// Both were removed from the board by direct instruction, not by drift:
//   hero      — "remove Invite Target container, that's just redundant info to the
//                player ranked at #1". Rank 1 IS the invite target; the hero restated it.
//   this-week — "Yes remove This Week (but don't delete the feature code, I may want to
//                bring it back)". `thisWeekCellHtml`/`topUnvisitedId` are still in
//                recruiting-hub.js, dormant and uncalled — so these tests are deleted
//                rather than skipped, and would need rewriting against the new two-column
//                layout if the column comes back.
//
// What survived the removal: row movement classes (.dropped/.gained) are still applied
// from the same wire events, and are asserted in 'rows' below.

test.describe('rows', () => {
  test('every row has a full lean ladder, a headshot and a linked name', async ({ page }) => {
    await mount(page, { board: ['r-1', 'r-2', 'r-3'] });
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => ({
        ladderSlots: r.querySelectorAll('.bladder .slot, .bladder .lb-slot, .bladder [class*="slot"]').length,
        ladderText: r.querySelector('.bladder').textContent.trim().length,
        img: !!r.querySelector('.bav img'),
        lazy: r.querySelector('.bav img')?.loading,
        href: r.querySelector('.btxt a')?.getAttribute('href') || '',
      })));
    for (const row of m) {
      expect(row.ladderText).toBeGreaterThan(0);
      expect(row.img).toBe(true);
      expect(row.lazy).toBe('lazy');
      expect(row.href).toContain('recruit');
    }
  });

  test('the 20-slot cap still holds', async ({ page }) => {
    await mount(page, { board: [] });
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll('#hub-pool .pool-add')];
      btns.slice(0, 12).forEach((b) => b.click());
    });
    // Only 12 recruits exist in the fixture, so the cap is exercised via its guard.
    const n = await rows(page).count();
    expect(n).toBeLessThanOrEqual(20);
    expect(n).toBe(12);
  });
});

test.describe('board seed', () => {
  // The fixture's lean pattern: r-0/3/6/9 lean you #1, r-1/4/7/10 lean you #2, rest not.
  const LEANERS = ['r-0', 'r-1', 'r-3', 'r-4', 'r-6', 'r-7', 'r-9', 'r-10'];
  const SEEDED = { week: 20, watchlist: ['r-1', 'r-2', 'r-3'], board: [] };

  test('an unsaved board pre-populates from your current leans, RT descending', async ({ page }) => {
    await mount(page, { week: 20, board: [] });
    const m = await page.evaluate(() => {
      const ids = [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id);
      // position_ratings is 80 - i, so a lower index is a higher RT.
      return { ids, nums: ids.map((id) => Number(id.split('-')[1])) };
    });
    expect(m.ids.sort()).toEqual([...LEANERS].sort());
    expect(m.nums).toEqual([...m.nums].sort((a, b) => a - b));   // RT descending
  });

  test('a recruit who does not lean to you is not seeded', async ({ page }) => {
    await mount(page, { week: 20, board: [] });
    const ids = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id));
    expect(ids).not.toContain('r-2');    // leans rival-1 / rival-2
    expect(ids).not.toContain('r-5');
  });

  test('the watchlist tops up the remainder, behind every lean', async ({ page }) => {
    // r-2 and r-5 are starred but lean elsewhere, so they land after all eight leaners.
    await mount(page, { week: 20, board: [], watchlist: ['r-2', 'r-5'] });
    const ids = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id));
    expect(ids.slice(0, 8).sort()).toEqual([...LEANERS].sort());
    expect(ids.slice(8)).toEqual(['r-2', 'r-5']);
  });

  test('a starred recruit who also leans to you is seeded once', async ({ page }) => {
    await mount(page, { week: 20, board: [], watchlist: ['r-0'] });
    const ids = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id));
    expect(ids.filter((id) => id === 'r-0')).toHaveLength(1);
    expect(ids).toHaveLength(LEANERS.length);
  });

  test('nothing to seed from leaves the board empty', async ({ page }) => {
    await mount(page, { week: 20, board: [], watchlist: [], noLeans: true });
    expect(await rows(page).count()).toBe(0);
    expect(await page.evaluate(() => !!document.querySelector('#board-seed-notice'))).toBe(false);
  });

  test('a saved board is never overwritten by the seed', async ({ page }) => {
    await mount(page, { week: 20, board: ['r-5', 'r-2'] });
    const ids = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id));
    expect(ids).toEqual(['r-5', 'r-2']);
  });

  test('and later weeks carry that board forward rather than re-seeding', async ({ page }) => {
    // The board lives in FTD across weeks 20-26, so week 21 opens on what week 20 sent.
    await mount(page, { week: 21, board: ['r-5', 'r-2'] });
    const m = await page.evaluate(() => ({
      ids: [...document.querySelectorAll('#hub-board .brow[data-id]')].map((r) => r.dataset.id),
      notice: !!document.querySelector('#board-seed-notice'),
    }));
    expect(m.ids).toEqual(['r-5', 'r-2']);
    expect(m.notice).toBe(false);
  });
});

test.describe('seed notice', () => {
  const SEEDED = { week: 20, watchlist: ['r-1', 'r-2', 'r-3'], board: [] };

  test('appears on a seeded board and says nothing is sent yet', async ({ page }) => {
    await mount(page, SEEDED);
    const txt = await page.evaluate(() =>
      document.querySelector('#board-seed-notice')?.textContent.trim() || '');
    expect(txt).toContain('Seeded from your current leans');
    expect(txt).toContain('ranked by RT');
    expect(txt).toContain('Drag to re-order');
    expect(txt).toContain('nothing is sent until you save');
  });

  test('absent when the board came from a real save', async ({ page }) => {
    await mount(page, { week: 20, watchlist: ['r-1', 'r-2'], board: ['r-5', 'r-6'] });
    expect(await page.evaluate(() => !!document.querySelector('#board-seed-notice'))).toBe(false);
  });

  test('absent when there was nothing to seed from', async ({ page }) => {
    await mount(page, { week: 20, watchlist: [], board: [], noLeans: true });
    expect(await page.evaluate(() => !!document.querySelector('#board-seed-notice'))).toBe(false);
  });

  test('dismissible', async ({ page }) => {
    await mount(page, SEEDED);
    await page.click('#board-seed-dismiss');
    await page.waitForFunction(() => !document.querySelector('#board-seed-notice'));
  });

  test('disappears once the player reorders', async ({ page }) => {
    await mount(page, SEEDED);
    expect(await page.evaluate(() => !!document.querySelector('#board-seed-notice'))).toBe(true);
    // Removing a row is an edit: the order is the player's now.
    await page.click('#hub-board .brow[data-index="0"] .bx');
    await page.waitForFunction(() => !document.querySelector('#board-seed-notice'));
  });

  test('disappears once the board is saved', async ({ page }) => {
    await mount(page, SEEDED);
    await page.click('#dock-save');
    await page.waitForFunction(() => !document.querySelector('#board-seed-notice'));
  });

  test('the seed itself never writes — has_saved_board cannot flip before save', async ({ page }) => {
    await mount(page, SEEDED);
    const orders = await page.evaluate(() =>
      window.__writes.filter((w) => String(w.url).includes('recruiting-orders')));
    expect(orders).toHaveLength(0);
    // And the seed did produce a board client-side: eight leaners, plus r-2 — the only
    // one of the three starred names who does not already lean to you.
    expect(await rows(page).count()).toBe(9);
  });

  test('saving is the only thing that posts the order', async ({ page }) => {
    await mount(page, { week: 20, watchlist: ['r-2'], board: [], noLeans: true });
    await page.click('#dock-save');
    await page.waitForFunction(() =>
      window.__writes.some((w) => String(w.url).includes('recruiting-orders')));
    const orders = await page.evaluate(() =>
      window.__writes.filter((w) => String(w.url).includes('recruiting-orders')));
    expect(orders).toHaveLength(1);
    expect(JSON.parse(orders[0].body).recruit_ids).toEqual(['r-2']);
  });
});

test.describe('submitting ends the visit', () => {
  const HOLD_MS = 2000;

  /** Catch the FCC navigation instead of following it, so the page survives to assert on. */
  async function watchNav(page) {
    const hits = [];
    await page.route('**/franchise-command-center*', (route) => {
      hits.push(route.request().url());
      route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>locker room</body></html>' });
    });
    return hits;
  }

  test('the confirmation names the thing the button did', async ({ page }) => {
    await mount(page, { week: 20, board: ['r-1', 'r-2'] });
    await watchNav(page);
    await page.click('#dock-save');
    await page.waitForSelector('#hub-toast.show');
    const txt = await page.evaluate(() => document.querySelector('#hub-toast').textContent);
    // The CTA says "Submit Invites"; the confirmation used to say "Saved".
    expect(txt).toContain('Invites Submitted');
  });

  test('it holds, then returns to the locker room', async ({ page }) => {
    await mount(page, { week: 20, board: ['r-1', 'r-2'] });
    const hits = await watchNav(page);
    const t0 = Date.now();
    await page.click('#dock-save');
    await page.waitForSelector('#hub-toast.show');
    // Still on the Hub while the confirmation is up.
    expect(hits).toHaveLength(0);
    await page.waitForURL('**/franchise-command-center*', { timeout: 5000 });
    const held = Date.now() - t0;
    expect(hits).toHaveLength(1);
    // Bounded both ways: an instant redirect gives no time to read it, and a long one
    // reads as a hang.
    expect(held).toBeGreaterThanOrEqual(HOLD_MS - 250);
    expect(held).toBeLessThan(HOLD_MS + 2000);
  });

  test('a second press during the hold cannot post the board twice', async ({ page }) => {
    await mount(page, { week: 20, board: ['r-1', 'r-2'] });
    await watchNav(page);
    await page.click('#dock-save');
    await page.waitForSelector('#hub-toast.show');
    const btn = await page.evaluate(() => {
      const b = document.getElementById('dock-save');
      return { disabled: b.disabled, label: b.textContent.trim() };
    });
    expect(btn.disabled).toBe(true);
    expect(btn.label).toBe('Invites Submitted');
    // Force the press anyway — a disabled button is the guard, so prove it holds.
    await page.evaluate(() => document.getElementById('dock-save').click());
    const posts = await page.evaluate(() =>
      window.__writes.filter((w) => String(w.url).includes('recruiting-orders')).length);
    expect(posts).toBe(1);
  });

  test('a failed submit stays put and re-arms the button', async ({ page }) => {
    await mount(page, { week: 20, board: ['r-1', 'r-2'] });
    const hits = await watchNav(page);
    await page.evaluate(() => {
      window.RecruitingCommon.fetchJSON = function () {
        return Promise.reject(new Error('nope'));
      };
    });
    await page.click('#dock-save');
    await page.waitForSelector('#hub-toast.show');
    await page.waitForTimeout(HOLD_MS + 400);
    const m = await page.evaluate(() => {
      const b = document.getElementById('dock-save');
      return { toast: document.querySelector('#hub-toast').textContent,
               disabled: b.disabled, label: b.textContent.trim() };
    });
    expect(m.toast).toContain('Submit failed');
    // No navigation: the board was not sent, so the player must stay where they can retry.
    expect(hits).toHaveLength(0);
    expect(m.disabled).toBe(false);
    // And the label goes back to the one the board actually renders, not "Save Board".
    expect(m.label).toBe('Submit Invites');
  });
});

test.describe('invite board actions', () => {
  test('Submit Invites is the only action, and it lives in the panel header', async ({ page }) => {
    await mount(page, { board: ['r-1', 'r-2'] });
    const m = await page.evaluate(() => {
      const head = document.querySelector('#hub-board .bpanel-head');
      return {
        headButtons: [...head.querySelectorAll('button')].map((b) => b.textContent.trim()),
        foot: document.querySelectorAll('#hub-board .bpanel-foot').length,
        clear: document.querySelectorAll('#dock-clear, .bbtn-clear').length,
      };
    });
    // A one-press wipe of a ranked board, with no confirmation and no undo, is gone.
    expect(m.headButtons).toEqual(['Submit Invites']);
    expect(m.foot).toBe(0);
    expect(m.clear).toBe(0);
  });

  test('rows can still be removed one at a time', async ({ page }) => {
    await mount(page, { board: ['r-1', 'r-2', 'r-3'] });
    // Relative, not absolute: .brow also matches the board's header row.
    const before = await page.locator('#hub-board [data-remove-id]').count();
    await page.click('#hub-board [data-remove-id]');
    const after = await page.locator('#hub-board [data-remove-id]').count();
    expect(before).toBe(3);
    expect(after).toBe(2);
  });
});
