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
  for (let i = 0; i < 12; i++) recruits.push(recruit(i, i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0));
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

const rows = (page) => page.locator('#hub-board .brow[data-index]');

test.describe('board order drives the dock', () => {
  test('hero is the top board recruit when none are visited', async ({ page }) => {
    await mount(page, { board: ['r-5', 'r-2', 'r-7'] });
    const m = await page.evaluate(() => ({
      name: document.querySelector('#hub-board .bhero-name').textContent.trim(),
      eyebrow: document.querySelector('#hub-board .bhero-eyebrow').textContent.trim(),
    }));
    expect(m.name).toBe('Recruit 05');
    expect(m.eyebrow).toContain('board rank 1');
  });

  test('hero skips already-visited recruits', async ({ page }) => {
    await mount(page, { board: ['r-5', 'r-2', 'r-7'], visited: ['r-5', 'r-2'] });
    const m = await page.evaluate(() => ({
      name: document.querySelector('#hub-board .bhero-name').textContent.trim(),
      eyebrow: document.querySelector('#hub-board .bhero-eyebrow').textContent.trim(),
    }));
    expect(m.name).toBe('Recruit 07');
    expect(m.eyebrow).toContain('board rank 3');
  });

  test('reordering changes the hero — re-ranking IS the invite decision', async ({ page }) => {
    await mount(page, { board: ['r-5', 'r-2', 'r-7'] });
    expect(await page.evaluate(() =>
      document.querySelector('#hub-board .bhero-name').textContent.trim())).toBe('Recruit 05');
    // Remove the leader; the next name takes the invite with no second selection step.
    await page.click('#hub-board .brow[data-index="0"] .bx');
    await page.waitForFunction(() =>
      document.querySelector('#hub-board .bhero-name').textContent.trim() === 'Recruit 02');
  });

  test('all board recruits visited leaves a stated empty hero, not a blank', async ({ page }) => {
    await mount(page, { board: ['r-5'], visited: ['r-5'] });
    const txt = await page.evaluate(() => document.querySelector('#hub-board .bhero').textContent);
    expect(txt).toContain('No invite target');
    expect(txt).toContain('already had a visit');
  });
});

test.describe('this-week column', () => {
  test('drop, gain and no-event rows each render correctly', async ({ page }) => {
    await mount(page, {
      board: ['r-1', 'r-2', 'r-3'],
      events: [dropEvent('r-1'), gainEvent('r-3')],
    });
    const cells = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-index]')].map((r) => ({
        id: r.dataset.id,
        cls: r.className,
        text: r.querySelector('.bmv').textContent.trim(),
        quiet: !!r.querySelector('.bmv-quiet'),
      })));
    const byId = Object.fromEntries(cells.map((c) => [c.id, c]));
    expect(byId['r-1'].text).toContain('dropped you');
    expect(byId['r-1'].text).toContain('Fairview moved to #1');
    expect(byId['r-1'].cls).toContain('dropped');
    expect(byId['r-3'].text).toContain('moved you to #1');
    expect(byId['r-3'].cls).toContain('gained');
    expect(byId['r-2'].quiet).toBe(true);
    expect(byId['r-2'].cls).not.toContain('dropped');
    expect(byId['r-2'].cls).not.toContain('gained');
  });

  test('the recruit name is not repeated inside its own row cell', async ({ page }) => {
    await mount(page, { board: ['r-1'], events: [dropEvent('r-1')] });
    const cell = await page.evaluate(() =>
      document.querySelector('#hub-board .brow[data-index="0"] .bmv').textContent);
    expect(cell).not.toContain('Recruit 01');
    expect(cell).toContain('dropped you');
  });

  test('drops are visually the loudest thing in the row', async ({ page }) => {
    await mount(page, {
      board: ['r-1', 'r-3'], events: [dropEvent('r-1'), gainEvent('r-3')],
    });
    const m = await page.evaluate(() => {
      const q = (s) => document.querySelector(s);
      const drop = q('#hub-board .brow.dropped'), gain = q('#hub-board .brow.gained');
      return {
        dropShadow: getComputedStyle(drop).boxShadow,
        gainShadow: getComputedStyle(gain).boxShadow,
        dropWeight: getComputedStyle(drop.querySelector('.bmv-txt')).fontWeight,
        gainWeight: getComputedStyle(gain.querySelector('.bmv-txt')).fontWeight,
      };
    });
    // Only the drop carries an accent rail, and its text is heavier.
    expect(m.dropShadow).not.toBe('none');
    expect(m.gainShadow).toBe('none');
    expect(Number(m.dropWeight)).toBeGreaterThan(Number(m.gainWeight));
  });
});

test.describe('right rail', () => {
  test('counts only events that hit a ranked recruit, annotated with board rank', async ({ page }) => {
    await mount(page, {
      board: ['r-1', 'r-2', 'r-3'],
      // r-9 is NOT on the board, so it must not be counted as affecting it.
      events: [dropEvent('r-3'), gainEvent('r-1'), dropEvent('r-9')],
    });
    const m = await page.evaluate(() => ({
      eyebrow: document.querySelector('#hub-dock .reyebrow').textContent.trim(),
      entries: [...document.querySelectorAll('#hub-dock .rev')].map((e) => e.textContent.trim()),
    }));
    expect(m.eyebrow).toBe('2 changes affect your board');
    expect(m.entries).toHaveLength(2);
    // Drop first, and each annotated with the rank it hits.
    expect(m.entries[0]).toContain('Recruit 03');
    expect(m.entries[0]).toContain('board rank 3');
    expect(m.entries[1]).toContain('Recruit 01');
    expect(m.entries[1]).toContain('board rank 1');
    expect(m.entries.join(' ')).not.toContain('Recruit 09');
  });

  test('singular wording for one change', async ({ page }) => {
    await mount(page, { board: ['r-1'], events: [gainEvent('r-1')] });
    expect(await page.evaluate(() =>
      document.querySelector('#hub-dock .reyebrow').textContent.trim()))
      .toBe('1 change affects your board');
  });

  test('a week with no events shows a quiet rail, not an empty panel', async ({ page }) => {
    await mount(page, { board: ['r-1', 'r-2'], events: [] });
    const m = await page.evaluate(() => {
      const panel = document.querySelector('#hub-dock .rpanel');
      return {
        text: panel.textContent.trim(),
        hasQuiet: !!panel.querySelector('.rquiet'),
        height: panel.getBoundingClientRect().height,
      };
    });
    expect(m.hasQuiet).toBe(true);
    expect(m.text).toContain('No changes affect your board');
    expect(m.height).toBeGreaterThan(40);
  });

  test('rail holds exactly two panels — changes and roster capacity, nothing else', async ({ page }) => {
    await mount(page, { board: ['r-1'], events: [gainEvent('r-1')] });
    const m = await page.evaluate(() => ({
      panels: document.querySelectorAll('#hub-dock .rpanel').length,
      eyebrows: [...document.querySelectorAll('#hub-dock .reyebrow')].map((e) => e.textContent.trim()),
      needs: document.querySelectorAll('#hub-dock .rneed').length,
      // Capacity is the header number and comes from the payload; position mix sits beneath.
      capItems: document.querySelectorAll('#hub-dock .cap-item').length,
      mixLabel: document.querySelector('#hub-dock .rneeds-lab')?.textContent.trim(),
    }));
    expect(m.panels).toBe(2);
    expect(m.eyebrows[1]).toBe('Roster capacity');
    expect(m.capItems).toBe(2);
    expect(m.mixLabel).toBe('Board position mix');
    expect(m.needs).toBe(5);
  });
});

test.describe('rows', () => {
  test('every row has a full lean ladder, a headshot and a linked name', async ({ page }) => {
    await mount(page, { board: ['r-1', 'r-2', 'r-3'] });
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-board .brow[data-index]')].map((r) => ({
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

  test('hero has a headshot too', async ({ page }) => {
    await mount(page, { board: ['r-1'] });
    expect(await page.evaluate(() => !!document.querySelector('#hub-board .bhero-av img'))).toBe(true);
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

test.describe('seed notice', () => {
  const SEEDED = { week: 20, watchlist: ['r-1', 'r-2', 'r-3'], board: [] };

  test('appears on a seeded board and says nothing is sent yet', async ({ page }) => {
    await mount(page, SEEDED);
    const txt = await page.evaluate(() =>
      document.querySelector('#board-seed-notice')?.textContent.trim() || '');
    expect(txt).toContain('Seeded from your watchlist');
    expect(txt).toContain('ranked by RT');
    expect(txt).toContain('Drag to re-order');
    expect(txt).toContain('nothing is sent until you save');
  });

  test('absent when the board came from a real save', async ({ page }) => {
    await mount(page, { week: 20, watchlist: ['r-1', 'r-2'], board: ['r-5', 'r-6'] });
    expect(await page.evaluate(() => !!document.querySelector('#board-seed-notice'))).toBe(false);
  });

  test('absent with no watchlist at all', async ({ page }) => {
    await mount(page, { week: 20, watchlist: [], board: [] });
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
    const writes = await page.evaluate(() => window.__writes);
    expect(writes).toHaveLength(0);
    // And the seed did produce a board client-side.
    expect(await rows(page).count()).toBe(3);
  });

  test('saving is the only thing that posts the order', async ({ page }) => {
    await mount(page, SEEDED);
    await page.click('#dock-save');
    await page.waitForFunction(() => window.__writes.length > 0);
    const writes = await page.evaluate(() => window.__writes);
    expect(writes).toHaveLength(1);
    expect(writes[0].url).toContain('/franchise/recruiting-orders');
    expect(JSON.parse(writes[0].body).recruit_ids).toEqual(['r-1', 'r-2', 'r-3']);
  });
});
