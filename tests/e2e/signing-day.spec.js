// @ts-check
/**
 * Signing Day (week 35) — stop deciding for the player, stop showing a fake number.
 *
 * Real recruiting-hub.js / -common.js / -spine.js + recruiting-spine.css and
 * recruiting-signing.css; only the network is stubbed. Every write is recorded, so a
 * load-time allocation would be visible as state rather than inferred.
 *
 * Run: npx playwright test tests/e2e/signing-day.spec.js --project=chromium
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
const YEARS = ['JH', 'Freshman', 'Sophomore', 'Junior'];
const USER = 'user-team-id';

/** leanRank: 1 => user #1, 2 => user #2, 0 => user absent. */
function recruit(i, leanRank) {
  const attributes = {};
  ATTRS.forEach((k, j) => { attributes[k] = ((i * 5 + j * 9) % 91) + 5; });
  const lean = leanRank === 1 ? { 1: USER, 2: 'rival-1', 3: null }
    : leanRank === 2 ? { 1: 'rival-1', 2: USER, 3: null }
      : { 1: 'rival-1', 2: 'rival-2', 3: null };
  return {
    recruit_id: `r-${i}`, name: `Recruit ${String(i).padStart(2, '0')}`,
    image_id: `img-${i}`, archetype: 'Slasher', 'Home Region': 'C',
    year: YEARS[i % YEARS.length], height: 72, weight: 190, attributes,
    position_ratings: { [POS[i % POS.length]]: 80 - i }, Lean: lean,
  };
}

function fixture(o = {}) {
  const recruits = [];
  for (let i = 0; i < 10; i++) recruits.push(recruit(i, i % 3 === 0 ? 1 : i % 3 === 1 ? 2 : 0));
  return {
    team: 'Kettle Falls', team_id: USER, team_region: 'C', week: 35, recruits,
    team_name_map: { [USER]: 'Kettle Falls', 'rival-1': 'Fairview', 'rival-2': 'Brackenridge' },
    saved_orders: {}, watchlist: [], new_lean_recruit_ids: [],
    week_35_recruiting_results: {}, week_35_recruiting_ran: !!o.ran,
    saved_order_entries_week_35: o.savedEntries || [],
    week_35_points_budget: 50,
    roster_capacity: o.capacity || { roster_spots: 4, scholarships: 2, roster_cap: 15, roster_used: 11 },
    competition_counts: o.competition || { 'r-0': 6, 'r-1': 1, 'r-3': 5, 'r-4': 2 },
    recruiting_wire: { week: 35, events: [], events_this_week: [], visited_recruit_ids: [], counts: {} },
  };
}

async function mount(page, o = {}) {
  await page.setViewportSize({ width: 1500, height: 1100 });
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
      return Promise.resolve({ status: 'success' });
    };
  }, { data: fixture(o) });
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector('#hub-sign .prow', { timeout: 10000 });
}

const railText = (page) => page.evaluate(() => document.querySelector('#sign-rail').textContent);

/** The pool opens on "Leaning to you"; switch to All to see recruits with no lean to us. */
async function showAllTab(page) {
  await page.click('#hub-sign .spool-tab[data-stab="all"]');
  await page.waitForFunction(() => document.querySelectorAll('#hub-sign .prow').length >= 10);
}

test.describe('loads at 0 of 50 with no promises', () => {
  test('nothing is allocated and nothing is promised on load', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      remaining: document.querySelector('#sign-rail .budget-nums .rem').textContent.trim(),
      total: document.querySelector('#sign-rail .budget-nums .of').textContent.trim(),
      promises: document.querySelector('#sign-rail .budget-promises b').textContent.trim(),
      committed: document.querySelectorAll('#sign-rail .citem').length,
      funded: document.querySelectorAll('#hub-sign .prow.funded').length,
      steppers: [...document.querySelectorAll('#hub-sign .stepper .val')].map((v) => v.textContent.trim()),
      bindings: document.querySelectorAll('#hub-sign .promise-cell.set').length,
    }));
    expect(m.remaining).toBe('50');
    expect(m.total).toBe('/ 50');
    expect(m.promises).toBe('0');
    expect(m.committed).toBe(0);
    expect(m.funded).toBe(0);
    expect(m.bindings).toBe(0);
    expect(m.steppers.every((v) => v === '0')).toBe(true);
  });

  test('load performs no writes at all', async ({ page }) => {
    await mount(page);
    expect(await page.evaluate(() => window.__writes)).toHaveLength(0);
  });

  test('a previously SAVED allocation is still restored', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 14, playing_time: true }] });
    const m = await page.evaluate(() => ({
      remaining: document.querySelector('#sign-rail .budget-nums .rem').textContent.trim(),
      promises: document.querySelector('#sign-rail .budget-promises b').textContent.trim(),
      committed: document.querySelectorAll('#sign-rail .citem').length,
    }));
    expect(m.remaining).toBe('36');
    expect(m.promises).toBe('1');
    expect(m.committed).toBe(1);
  });
});

test.describe('no percentage anywhere', () => {
  test('the rendered screen contains no % character', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 12, playing_time: true }] });
    const found = await page.evaluate(() => {
      const root = document.getElementById('hub-root');
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const hits = [];
      while (walker.nextNode()) {
        const t = walker.currentNode.nodeValue || '';
        if (t.includes('%')) hits.push(t.trim());
      }
      return hits;
    });
    expect(found).toEqual([]);
  });

  test('no odds bar or odds label survives', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      odds: document.querySelectorAll('#hub-sign .odds, #hub-sign .odds-bar, #hub-sign .odds-pct').length,
      headers: [...document.querySelectorAll('#hub-sign .spool-colhdr span')].map((s) => s.textContent.trim()),
    }));
    expect(m.odds).toBe(0);
    expect(m.headers).not.toContain('Sign odds');
    expect(m.headers).toContain('Standing');
    expect(m.headers).toContain('Field');
  });
});

test.describe('Standing column', () => {
  test('shows lean position and its multiplier', async ({ page }) => {
    await mount(page);
    await showAllTab(page);   // r-2 has no lean to us, so it only appears under All
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-sign .prow')].map((r) => ({
        id: r.dataset.id,
        pos: r.querySelector('.stand-pos').textContent.trim(),
        mult: r.querySelector('.stand-mult').textContent.trim(),
      })));
    const byId = Object.fromEntries(m.map((x) => [x.id, x]));
    // r-0 => user #1 (x5), r-1 => user #2 (x3), r-2 => absent (x1)
    expect(byId['r-0']).toMatchObject({ pos: '#1', mult: 'x5' });
    expect(byId['r-1']).toMatchObject({ pos: '#2', mult: 'x3' });
    expect(byId['r-2']).toMatchObject({ pos: '—', mult: 'x1' });
  });
});

test.describe('Field column', () => {
  test('count matches the seeded competition counts', async ({ page }) => {
    await mount(page, { competition: { 'r-0': 6, 'r-1': 1, 'r-2': 3 } });
    await showAllTab(page);
    const m = await page.evaluate(() =>
      Object.fromEntries([...document.querySelectorAll('#hub-sign .prow')].map((r) => [
        r.dataset.id, r.querySelector('.field-n').textContent.trim(),
      ])));
    expect(m['r-0']).toBe('6');
    expect(m['r-1']).toBe('1');
    expect(m['r-2']).toBe('3');
  });

  test('a recruit absent from the counts reads "no field yet", not zero', async ({ page }) => {
    await mount(page, { competition: { 'r-0': 4 } });
    await showAllTab(page);
    const m = await page.evaluate(() => {
      const row = [...document.querySelectorAll('#hub-sign .prow')].find((r) => r.dataset.id === 'r-5');
      return { n: row.querySelector('.field-n').textContent.trim(), lab: row.querySelector('.field-lab').textContent.trim() };
    });
    expect(m.n).toBe('—');
    expect(m.lab).toBe('no field yet');
  });

  test('segment bar has one segment per program, the user\'s highlighted once funded', async ({ page }) => {
    await mount(page, { competition: { 'r-0': 3 } });
    const before = await page.evaluate(() => {
      const row = [...document.querySelectorAll('#hub-sign .prow')].find((r) => r.dataset.id === 'r-0');
      return { segs: row.querySelectorAll('.field-bar i').length, mine: row.querySelectorAll('.field-bar i.mine').length };
    });
    expect(before.segs).toBe(3);
    expect(before.mine).toBe(0);
    await page.click('#hub-sign .prow[data-id="r-0"] .stepper button[data-step="1"]');
    const after = await page.evaluate(() => {
      const row = [...document.querySelectorAll('#hub-sign .prow')].find((r) => r.dataset.id === 'r-0');
      return { segs: row.querySelectorAll('.field-bar i').length, mine: row.querySelectorAll('.field-bar i.mine').length, n: row.querySelector('.field-n').textContent.trim() };
    });
    // Funding yourself adds your own segment; the server snapshot predates the save.
    expect(after.segs).toBe(4);
    expect(after.n).toBe('4');
    expect(after.mine).toBe(1);
  });
});

test.describe('row content', () => {
  test('year and archetype are both on the row', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-sign .prow')].slice(0, 4).map((r) => ({
        yr: r.querySelector('.prow-yr')?.textContent.trim(),
        arch: r.querySelector('.prow-arch').textContent.trim(),
      })));
    for (const row of m) {
      expect(row.yr).toBeTruthy();
      expect(['JH', 'FR', 'SO', 'JR', 'SR', 'GR']).toContain(row.yr);
      expect(row.arch).toContain('Slasher');
    }
    // Not every row is the same year — a senior and a freshman must differ.
    expect(new Set(m.map((r) => r.yr)).size).toBeGreaterThan(1);
  });

  test('names link to player detail', async ({ page }) => {
    await mount(page);
    const href = await page.evaluate(() =>
      document.querySelector('#hub-sign .prow .nm a')?.getAttribute('href') || '');
    expect(href).toContain('recruit');
  });

  test('no scholarship control exists', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      controls: document.querySelectorAll('#hub-sign [data-scholarship], #hub-sign .scholarship-toggle').length,
      headers: [...document.querySelectorAll('#hub-sign .spool-colhdr span')].map((s) => s.textContent.trim()),
    }));
    expect(m.controls).toBe(0);
    expect(m.headers.join(' ')).not.toContain('Scholarship');
  });
});

test.describe('steppers stop at 0 remaining', () => {
  test('every + button disables once the budget is exhausted', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 20, playing_time: false }, { id: 'r-1', points: 20, playing_time: false }, { id: 'r-2', points: 10, playing_time: false }] });
    const m = await page.evaluate(() => ({
      rem: document.querySelector('#sign-rail .budget-nums .rem').textContent.trim(),
      plusEnabled: [...document.querySelectorAll('#hub-sign .stepper button[data-step="1"]')].filter((b) => !b.disabled).length,
    }));
    expect(m.rem).toBe('0');
    expect(m.plusEnabled).toBe(0);
  });

  test('minus stays available so the player can free points back up', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 20, playing_time: false }, { id: 'r-1', points: 20, playing_time: false }, { id: 'r-2', points: 10, playing_time: false }] });
    await showAllTab(page);
    const enabled = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-sign .stepper button[data-step="-1"]')].filter((b) => !b.disabled).length);
    expect(enabled).toBe(3);
  });

  test('the per-recruit cap holds', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 20, playing_time: false }] });
    const disabled = await page.evaluate(() =>
      document.querySelector('#hub-sign .prow[data-id="r-0"] .stepper button[data-step="1"]').disabled);
    expect(disabled).toBe(true);
  });
});

test.describe('capacity comes from the payload', () => {
  test('roster spots and scholarships render the served numbers', async ({ page }) => {
    await mount(page, { capacity: { roster_spots: 3, scholarships: 7, roster_cap: 15, roster_used: 12 } });
    const txt = await page.evaluate(() => document.querySelector('#sign-rail .cap-row').textContent);
    expect(txt).toContain('3');
    expect(txt).toContain('15');
    expect(txt).toContain('7');
    expect(txt).toContain('roster spots');
    expect(txt).toContain('scholarships');
  });

  test('a different served number changes the display — not recomputed locally', async ({ page }) => {
    await mount(page, { capacity: { roster_spots: 9, scholarships: 1, roster_cap: 15, roster_used: 6 } });
    const txt = await page.evaluate(() => document.querySelector('#sign-rail .cap-row').textContent);
    expect(txt).toContain('9');
    expect(txt).toContain('1');
  });
});

test.describe('pre-flight warnings', () => {
  test('thin funding against a crowded field names the recruit and both numbers', async ({ page }) => {
    await mount(page, {
      competition: { 'r-1': 6 },
      savedEntries: [{ id: 'r-1', points: 5, playing_time: false }],
    });
    const txt = await railText(page);
    expect(txt).toContain('6 programs funding Recruit 01');
    expect(txt).toContain("you're #2 at x3");
    expect(txt).toContain('5 points is unlikely to carry');
  });

  test('unspent points against open spots names an uncontested recruit', async ({ page }) => {
    await mount(page, {
      capacity: { roster_spots: 4, scholarships: 2, roster_cap: 15, roster_used: 11 },
      competition: { 'r-4': 1 },
    });
    const txt = await railText(page);
    expect(txt).toContain('50 points unspent and 4 roster spots');
    expect(txt).toContain('Recruit 04');
    expect(txt).toContain('uncontested at x');
  });

  test('a binding promise at x1 is flagged with the recruit named', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-2', points: 4, playing_time: true }] });
    const txt = await railText(page);
    expect(txt).toContain('Binding promise on Recruit 02 at x1');
  });

  test('more funded recruits than roster spots is flagged with both counts', async ({ page }) => {
    await mount(page, {
      capacity: { roster_spots: 1, scholarships: 0, roster_cap: 15, roster_used: 14 },
      savedEntries: [{ id: 'r-0', points: 3, playing_time: false }, { id: 'r-1', points: 3, playing_time: false }],
    });
    const txt = await railText(page);
    expect(txt).toContain('2 recruits funded but only 1 roster spot');
  });

  test('a clean board says so rather than showing an empty panel', async ({ page }) => {
    await mount(page, {
      capacity: { roster_spots: 0, scholarships: 0, roster_cap: 15, roster_used: 15 },
      competition: {},
    });
    const m = await page.evaluate(() => ({
      ok: !!document.querySelector('#sign-rail .pfw.ok'),
      text: document.querySelector('#sign-rail .preflight').textContent.trim(),
    }));
    expect(m.ok).toBe(true);
    expect(m.text).toContain('Nothing flagged');
  });

  test('warnings never contain a percentage', async ({ page }) => {
    await mount(page, {
      competition: { 'r-1': 6 },
      savedEntries: [{ id: 'r-1', points: 5, playing_time: true }],
    });
    expect(await page.evaluate(() =>
      document.querySelector('#sign-rail .preflight').textContent)).not.toContain('%');
  });
});

test.describe('submit summary', () => {
  test('shows what was committed and waits for a click instead of redirecting', async ({ page }) => {
    await mount(page, {
      competition: { 'r-0': 4 },
      savedEntries: [{ id: 'r-0', points: 12, playing_time: true }, { id: 'r-1', points: 8, playing_time: false }],
    });
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    const m = await page.evaluate(() => ({
      title: document.querySelector('.ssum-title').textContent.trim(),
      sub: document.querySelector('.ssum-sub').textContent.trim(),
      rows: [...document.querySelectorAll('.ssum-row')].map((r) => r.textContent.trim()),
      hasButton: !!document.querySelector('#ssum-go'),
      text: document.querySelector('.ssum').textContent,
    }));
    expect(m.title).toBe('Orders Submitted');
    expect(m.sub).toContain('20 of 50 points committed across 2 recruits');
    expect(m.sub).toContain('1 binding promise');
    expect(m.rows).toHaveLength(2);
    // Highest funding first, and each row carries standing + multiplier + field.
    expect(m.rows[0]).toContain('Recruit 00');
    expect(m.rows[0]).toContain('12 pts');
    expect(m.rows[0]).toContain('#1 x5');
    expect(m.rows[0]).toContain('4 programs');
    expect(m.hasButton).toBe(true);
    expect(m.text).not.toContain('%');
  });

  test('both requests fire before the summary appears', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 5, playing_time: false }] });
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    const writes = await page.evaluate(() => window.__writes.map((w) => w.url));
    expect(writes.some((u) => u.includes('/franchise/recruiting-orders'))).toBe(true);
    expect(writes.some((u) => u.includes('/franchise/run-week-35-recruiting'))).toBe(true);
  });

  test('submitting nothing still explains the consequence', async ({ page }) => {
    await mount(page);
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    const txt = await page.evaluate(() => document.querySelector('.ssum').textContent);
    expect(txt).toContain('0 of 50 points committed');
    expect(txt).toContain('signs elsewhere');
  });

  test('the posted entries carry no scholarship field', async ({ page }) => {
    await mount(page, { savedEntries: [{ id: 'r-0', points: 5, playing_time: true }] });
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    const body = await page.evaluate(() =>
      JSON.parse(window.__writes.find((w) => w.url.includes('recruiting-orders')).body));
    expect(body.order_entries[0]).toEqual({ id: 'r-0', points: 5, playing_time: true });
    expect(body.order_entries[0]).not.toHaveProperty('scholarship');
  });
});
