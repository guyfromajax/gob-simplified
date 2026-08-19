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
    position_ratings: { [POS[i % POS.length]]: 80 - i }, Lean: lean,
  };
}

/** visits: { 20: 'r-1', 22: null, ... } — omitted weeks default to no visit. */
function fixture(o = {}) {
  const week = o.week ?? 23;
  const recruits = [];
  for (let i = 0; i < 12; i++) recruits.push(recruit(i, i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0));
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

  test('and no longer inside the Season panel', async ({ page }) => {
    await mount(page);
    expect(await page.locator('.ptl-inner .vcal').count()).toBe(0);
    expect(await page.locator('.vlog').count()).toBe(0);
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
    // The ladder renders the recruit's real lean list, so the slot count follows the
    // data (r-1 leans two deep). What matters is that it is the same ladder the board
    // draws, and that the user's own place in it is marked.
    expect(t.leanSlots).toBeGreaterThanOrEqual(2);
    expect(t.leanYou).toBe(1);
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

test.describe('the counter', () => {
  test('counts invites spent, out of seven', async ({ page }) => {
    await mount(page, { week: 23, visits: { 20: 'r-1', 22: 'r-4' } });
    const c = await page.evaluate(() => ({
      n: document.querySelector('.vcal-count .n').textContent,
      of: document.querySelector('.vcal-count .of').textContent,
    }));
    expect(c.n).toBe('2');
    expect(c.of).toContain('7');
  });
});
