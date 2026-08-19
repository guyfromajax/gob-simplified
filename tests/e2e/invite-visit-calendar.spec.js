// @ts-check
/**
 * Invite visits as a seven-square calendar (weeks 20-26), above the invite board.
 *
 * The row IS the season: seven squares, one per invite week, so what has been spent
 * and what is left are the same picture. Measured, not eyeballed — real
 * recruiting-hub.js / -spine.js / -spine.css with only the network stubbed.
 *
 * Run: npx playwright test tests/e2e/invite-visit-calendar.spec.js --project=chromium
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
const WEEKS = [20, 21, 22, 23, 24, 25, 26];

function recruit(i, leanRank) {
  const attributes = {};
  ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 11) % 91) + 5; });
  const lean = leanRank === 1 ? { 1: USER, 2: 'rival-1', 3: null }
    : leanRank === 2 ? { 1: 'rival-1', 2: USER, 3: null }
      : { 1: 'rival-1', 2: 'rival-2', 3: null };
  return {
    recruit_id: `r-${i}`, name: `Longnameson Recruit ${String(i).padStart(2, '0')}`,
    image_id: `img-${i}`, archetype: 'Slasher', 'Home Region': 'C',
    year: 'Sophomore', height: 72, weight: 190, attributes,
    // A potential well above current makes RT render as a PAIR, so the right-hand cell
    // is much wider than the left. Without that asymmetry, space-between and a real
    // 1fr/auto/1fr grid put the position in the same place and the test proves nothing.
    potential_rt_ratcheted: 95,
    position_ratings: { [POS[i % POS.length]]: 80 - i }, Lean: lean,
  };
}

/** visits: { 20: 'r-1', 22: null, ... } — omitted weeks default to no visit. */
function fixture(o = {}) {
  // Per-recruit lean overrides, so a one-lean and a three-lean tile can sit side by side.
  const leans = o.leans || {};
  const week = o.week ?? 23;
  const recruits = [];
  for (let i = 0; i < 12; i++) recruits.push(recruit(i, i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0));
  recruits.forEach((r) => { if (leans[r.recruit_id]) r.Lean = leans[r.recruit_id]; });
  const byId = Object.fromEntries(recruits.map((r) => [r.recruit_id, r]));
  const visits = o.visits || { 20: 'r-1', 21: 'r-4' };
  return {
    team: 'Kettle Falls', team_id: USER, team_region: 'C', week, recruits,
    team_name_map: { [USER]: 'Kettle Falls', 'rival-1': 'Fairview', 'rival-2': 'Brackenridge' },
    saved_orders: { 1: 'r-0', 2: 'r-2' }, watchlist: [], new_lean_recruit_ids: [],
    week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    visit_history: WEEKS.map((w) => {
      const rid = visits[w] || null;
      return { week: w, recruit_id: rid, name: rid ? byId[rid].name : null, lean: rid ? byId[rid].Lean : null };
    }),
    recruiting_wire: {
      week, seen_week: 0, unseen_count: 0, counts: { moved: 0, dropped: 0 },
      events: [], events_this_week: [], visited_recruit_ids: Object.values(visits).filter(Boolean),
      board_saved_week: 0, has_saved_board: true,
    },
  };
}

async function mount(page, o = {}) {
  await page.setViewportSize({ width: o.width || 1440, height: 1200 });
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style><style>body{margin:0}.doc{max-width:1360px;margin:0 auto;padding:20px}</style>
    <div class="doc"><a id="back-btn" href="#"></a><div id="hub-root" class="spine"></div></div>`);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });
  await page.evaluate(({ data }) => {
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`, getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/${id}.png`,
      ensureRecruitImage: () => Promise.resolve({ status: 'skip' }),
    };
    window.RecruitingCommon.fetchJSON = function (url) {
      if (String(url).includes('/franchise/recruiting-data')) return Promise.resolve(data);
      return Promise.resolve({ status: 'success' });
    };
  }, { data: fixture(o) });
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector('#hub-visits .vcal', { timeout: 10000 });
}

const tiles = (page) => page.evaluate(() =>
  [...document.querySelectorAll('#hub-visits .vwk')].map((t) => {
    const r = t.getBoundingClientRect();
    return {
      cls: t.className,
      week: (t.querySelector('.vwk-wk') || {}).textContent,
      name: (t.querySelector('.vwk-nm') || {}).textContent || null,
      state: (t.querySelector('.vwk-state') || {}).textContent || null,
      rt: (t.querySelector('.vwk-rt') || {}).textContent || null,
      pos: (t.querySelector('.vwk-pos') || {}).textContent || null,
      yr: (t.querySelector('.vwk-yr') || {}).textContent || null,
      leanSlots: t.querySelectorAll('.lb-slot').length,
      leanYou: t.querySelectorAll('.lb-slot.is-you, .lb-slot.is-you-list').length,
      img: !!t.querySelector('.vwk-av img'),
      w: r.width, h: r.height, top: r.top,
    };
  }));

test.describe('shape', () => {
  test('one row of seven squares — the season, not a scroll', async ({ page }) => {
    await mount(page);
    const t = await tiles(page);
    expect(t).toHaveLength(7);
    expect(t.map((x) => x.week)).toEqual(WEEKS.map((w) => `Wk ${w}`));
    // One row: every tile shares a top edge.
    expect(new Set(t.map((x) => Math.round(x.top))).size).toBe(1);
    // Actually square at the shipped page width (.doc caps at 1360), and all one size.
    // min-height only takes over well below that, so a square here is a real square.
    expect(new Set(t.map((x) => Math.round(x.w))).size).toBe(1);
    for (const x of t) expect(Math.abs(x.w - x.h)).toBeLessThan(1);
  });

  test('nothing overflows its square, at 1440 or at 1280', async ({ page }) => {
    for (const width of [1440, 1280]) {
      await mount(page, { width });
      const bad = await page.evaluate(() =>
        [...document.querySelectorAll('#hub-visits .vwk')].filter((t) =>
          t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1).length);
      expect(bad, `width ${width}`).toBe(0);
    }
  });

  test('it sits above the invite board', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      cal: document.querySelector('#hub-visits .vcal').getBoundingClientRect().bottom,
      board: document.querySelector('#hub-board .bpanel').getBoundingClientRect().top,
    }));
    expect(m.cal).toBeLessThanOrEqual(m.board);
  });

  test('no counter — the seven squares are the count', async ({ page }) => {
    await mount(page);
    expect(await page.locator('#hub-visits .vcal-count').count()).toBe(0);
  });

  test('and no longer inside the Season panel', async ({ page }) => {
    await mount(page);
    expect(await page.locator('.ptl-inner .vcal').count()).toBe(0);
    expect(await page.locator('.vlog').count()).toBe(0);
  });

  test('the panel title carries no eyebrow', async ({ page }) => {
    await mount(page);
    expect(await page.locator('.vcal-title small').count()).toBe(0);
    expect(await page.evaluate(() =>
      document.querySelector('.vcal-title').textContent.trim())).toBe('Invite Visits');
  });
});

test.describe('a spent week shows what it bought', () => {
  test('headshot, name, RT, year and the current leans', async ({ page }) => {
    await mount(page, { week: 23, visits: { 20: 'r-1' } });
    const t = (await tiles(page))[0];
    expect(t.cls).toContain('is-filled');
    expect(t.name).toContain('Recruit 01');
    expect(t.img).toBe(true);
    expect(t.rt).toBeTruthy();
    expect(t.yr).toBe('SO');
    expect(t.pos).toBeTruthy();
    // The ladder renders the recruit's real lean list, so the slot count follows the
    // data (r-1 leans two deep). What matters is that it is the same ladder the board
    // draws, and that the user's own place in it is marked.
    expect(t.leanSlots).toBeGreaterThanOrEqual(2);
    expect(t.leanYou).toBe(1);
  });

  test('week, position and RT share one header line — left, centre, right', async ({ page }) => {
    await mount(page, { week: 23, visits: { 20: 'r-1' } });
    const m = await page.evaluate(() => {
      const t = document.querySelector('#hub-visits .vwk.is-filled');
      const box = (sel) => t.querySelector(sel).getBoundingClientRect();
      const tile = t.getBoundingClientRect();
      const wk = box('.vwk-wk'), pos = box('.vwk-pos'), rt = box('.vwk-rt');
      // Centre lines, not tops: the three run at different font sizes, so their boxes
      // start a pixel apart even when they are perfectly on one line.
      const midY = (r) => (r.top + r.bottom) / 2;
      return {
        oneLine: Math.abs(midY(wk) - midY(pos)) < 2 && Math.abs(midY(pos) - midY(rt)) < 2,
        order: wk.left < pos.left && pos.left < rt.left,
        // Centre means the tile's centre line, not merely "between the other two".
        // Sub-pixel, deliberately: space-between lands the position within 1.4px of
        // centre here purely because "Wk 20" and the RT pair happen to measure alike,
        // so a 2px tolerance would pass on a layout that only looks centred.
        posOffset: Math.abs((pos.left + pos.right) / 2 - (tile.left + tile.right) / 2),
        // What actually guarantees it: 1fr/auto/1fr makes the flanking cells equal,
        // whatever their contents. Content-sized cells are 33.1 and 30.4.
        flanksEqual: Math.abs(wk.width - rt.width) < 0.5,
        aboveImage: pos.bottom <= box('.vwk-av').top,
      };
    });
    expect(m.oneLine).toBe(true);
    expect(m.order).toBe(true);
    expect(m.posOffset).toBeLessThan(0.5);
    expect(m.flanksEqual).toBe(true);
    expect(m.aboveImage).toBe(true);
  });

  test('the year sits under the name, on its own line', async ({ page }) => {
    // Inline beside the name it took ~24px off a 148px-wide tile and clipped the name.
    await mount(page, { week: 23, visits: { 20: 'r-1' } });
    const m = await page.evaluate(() => {
      const t = document.querySelector('#hub-visits .vwk.is-filled');
      const nm = t.querySelector('.vwk-nm');
      const nmBox = nm.getBoundingClientRect();
      const yr = t.querySelector('.vwk-yr').getBoundingClientRect();
      return {
        below: yr.top >= nmBox.bottom - 1,
        // The name gets the tile's full usable width back.
        nameFullWidth: nmBox.width >= t.clientWidth - 21,
        nameClips: getComputedStyle(nm).textOverflow === 'ellipsis',
      };
    });
    expect(m.below).toBe(true);
    expect(m.nameFullWidth).toBe(true);
    expect(m.nameClips).toBe(true);
  });

  test('one lean takes one third, not the whole ladder', async ({ page }) => {
    // A recruit with one lean and a recruit with three must not read as two full-width
    // ladders — the empty thirds ARE the information.
    await mount(page, {
      week: 26, visits: { 20: 'r-2', 21: 'r-1' },
      leans: {
        'r-2': { 1: USER, 2: null, 3: null },
        'r-1': { 1: 'rival-1', 2: USER, 3: 'rival-2' },
      },
    });
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-visits .vwk.is-filled')].map((t) => {
        const slots = [...t.querySelectorAll('.lb-slot')];
        return {
          n: slots.length,
          first: slots[0].getBoundingClientRect().width,
          ladder: t.querySelector('.lean-b').getBoundingClientRect().width,
        };
      }));
    // r-2 leans once, r-1 three times — different counts, identical slot width.
    expect(m[0].n).not.toBe(m[1].n);
    expect(Math.abs(m[0].first - m[1].first)).toBeLessThan(1);
    // And a slot is a third of the ladder, never the whole of it.
    for (const x of m) expect(x.first).toBeLessThan(x.ladder / 2);
  });

  test('a long name is clipped, never widening the square', async ({ page }) => {
    await mount(page, { week: 23, visits: { 20: 'r-1' } });
    const t = await tiles(page);
    expect(Math.abs(t[0].w - t[6].w)).toBeLessThan(1);
  });
});

test.describe('the three empty states are three different things', () => {
  test('this week is live, past weeks are spent, future weeks are open', async ({ page }) => {
    await mount(page, { week: 23, visits: { 20: 'r-1' } });
    const t = await tiles(page);
    const by = Object.fromEntries(t.map((x) => [x.week, x]));
    // Week 21 and 22 ran and gave nothing back — that invite is GONE, so it must not
    // read the same as week 24, which the player still holds.
    expect(by['Wk 21'].cls).toContain('is-missed');
    expect(by['Wk 21'].state).toBe('No visit');
    expect(by['Wk 23'].cls).toContain('is-pending');
    expect(by['Wk 23'].state).toBe('This week');
    expect(by['Wk 24'].cls).toContain('is-upcoming');
    expect(by['Wk 24'].state).toBe('Upcoming');
    expect(by['Wk 21'].cls).not.toContain('is-upcoming');
  });

  test('this week is the only amber square', async ({ page }) => {
    await mount(page, { week: 22, visits: { 20: 'r-1' } });
    const amber = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-visits .vwk')]
        .filter((t) => getComputedStyle(t).borderTopColor.includes('247, 148, 32'))
        .map((t) => t.querySelector('.vwk-wk').textContent));
    expect(amber).toEqual(['Wk 22']);
  });

  test('a week that already resolved is filled even while it is the current week', async ({ page }) => {
    // Visits are assigned at run-training, which does not end the week.
    await mount(page, { week: 20, visits: { 20: 'r-1' } });
    const t = await tiles(page);
    expect(t[0].cls).toContain('is-filled');
    expect(t[1].cls).toContain('is-upcoming');
  });
});
