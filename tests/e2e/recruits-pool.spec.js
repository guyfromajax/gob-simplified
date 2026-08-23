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
function fixture({ week = 7, watchlist = [], savedOrders = {}, noLeans = false } = {}) {
  const recruits = [];
  for (let i = 0; i < 450; i++) {
    const attributes = {};
    ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 13) % 91) + 5; });
    // noLeans: nobody leans to the user, so the board seeds from the watchlist alone.
    const lean = noLeans
      ? { 1: 'rival-1', 2: null, 3: null }
      : i % 11 === 0
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
  };
}

async function mountPool(page, opts = {}) {
  const patchCalls = [];
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Real origin first: getQueryContext reads location.search, and about:blank has no
  // origin (setContent preserves whatever URL the page is already on).
  // The real homepage is never used — setContent replaces the document on the next
  // line. goto only supplies a same-origin URL (sessionStorage, location.search), so
  // serve a stub and skip a full app page load per test. Under parallel workers those
  // loads queue on the dev server and were the cause of intermittent timeouts here.
  await page.route('**/', (route) => (route.request().resourceType() === 'document'
    ? route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>o</title>' })
    : route.continue()));
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

test.describe('450 rows', () => {
  test('all 450 render and the pool scrolls, not the page', async ({ page }) => {
    await mountPool(page);
    expect(await rowCount(page)).toBe(450);
    const m = await page.evaluate(() => {
      const s = document.querySelector('#hub-pool .pool-scroll');
      return {
        scrollable: s.scrollHeight > s.clientHeight,
        bodyOverflowsX: document.body.scrollWidth > window.innerWidth + 1,
      };
    });
    expect(m.scrollable).toBe(true);
    expect(m.bodyOverflowsX).toBe(false);
  });

  test('header stays pinned while the body scrolls', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(async () => {
      const s = document.querySelector('#hub-pool .pool-scroll');
      const th = document.querySelector('#hub-pool thead th.name-col');
      const before = th.getBoundingClientRect().top;
      s.scrollTop = 1200;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const after = th.getBoundingClientRect().top;
      return { before, after, scrolled: s.scrollTop };
    });
    expect(m.scrolled).toBeGreaterThan(500);
    expect(Math.abs(m.after - m.before)).toBeLessThan
      (1.5);
  });

  test('re-render on a filter keystroke stays responsive', async ({ page }) => {
    await mountPool(page);
    const ms = await page.evaluate(() => {
      const input = document.querySelector('#pool-search');
      const t0 = performance.now();
      input.value = 'Recruit 1';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return performance.now() - t0;
    });
    // Generous ceiling; the point is to catch an order-of-magnitude regression.
    expect(ms).toBeLessThan(1500);
  });

  test('headshots are lazy so 450 images do not all fetch', async ({ page }) => {
    await mountPool(page);
    const allLazy = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-pool .pc-av img')].every((i) => i.loading === 'lazy'));
    expect(allLazy).toBe(true);
  });
});

test.describe('columns and headers', () => {
  test('column order is Recruit Pos RT Yr Ht Wt Rgn Attributes Lean Watch', async ({ page }) => {
    await mountPool(page);
    const labels = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-pool thead th')].map((t) => t.textContent.replace(/[▲▼]/g, '').trim()));
    expect(labels).toEqual(['Recruit', 'Pos', 'RT', 'Yr', 'Ht', 'Wt', 'Rgn', 'Attributes', 'Lean', 'Watch']);
  });

  test('every header is centered over its column', async ({ page }) => {
    await mountPool(page);
    const offsets = await page.evaluate(() => {
      const heads = [...document.querySelectorAll('#hub-pool thead th')];
      const cells = [...document.querySelectorAll('#hub-pool tbody tr.rec:first-child td')];
      return heads.map((th, i) => {
        const h = th.getBoundingClientRect(), c = cells[i].getBoundingClientRect();
        return { label: th.textContent.replace(/[▲▼]/g, '').trim(), delta: Math.abs((h.left + h.width / 2) - (c.left + c.width / 2)) };
      });
    });
    // Header box must be centred on its column box (the name column is left-aligned text
    // by design, but the CELL must still align with the header cell).
    for (const o of offsets) expect(o.delta, `${o.label} column`).toBeLessThan(1.5);
  });

  test('Attributes header centers across the whole 12-chip block, not the first chip', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const th = [...document.querySelectorAll('#hub-pool thead th')].find((t) => t.textContent.trim() === 'Attributes');
      const chips = [...document.querySelectorAll('#hub-pool tbody tr.rec:first-child .attr-tile')];
      const first = chips[0].getBoundingClientRect(), last = chips[chips.length - 1].getBoundingClientRect();
      const h = th.getBoundingClientRect();
      return {
        chipCount: chips.length,
        headerCenter: h.left + h.width / 2,
        blockCenter: (first.left + last.right) / 2,
        firstChipCenter: first.left + first.width / 2,
      };
    });
    expect(m.chipCount).toBe(12);
    expect(Math.abs(m.headerCenter - m.blockCenter)).toBeLessThan(2);
    // Explicitly NOT left-aligned over the first chip.
    expect(Math.abs(m.headerCenter - m.firstChipCenter)).toBeGreaterThan(20);
  });

  test('attributes are visible (no condensed mode) and the name column is capped', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => ({
      condensedClass: !!document.querySelector('#hub-pool table.pool.condensed'),
      chipsVisible: document.querySelectorAll('#hub-pool tbody tr.rec:first-child .attr-tile').length,
      nameWidth: document.querySelector('#hub-pool tbody tr.rec:first-child td.name-col').getBoundingClientRect().width,
      tableWidth: document.querySelector('#hub-pool table.pool').getBoundingClientRect().width,
    }));
    expect(m.condensedClass).toBe(false);
    expect(m.chipsVisible).toBe(12);
    expect(Math.round(m.nameWidth)).toBe(248);
    // Content-sized, not stretched to a much wider container. Wt widened it ~44px;
    // see the known-limitation note on the invite-phase width test.
    expect(m.tableWidth).toBeLessThan(1250);
  });

  test('RT sorts descending by default and is the active sort', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const rtTh = [...document.querySelectorAll('#hub-pool thead th')].find((t) => t.textContent.includes('RT'));
      const vals = [...document.querySelectorAll('#hub-pool tbody tr.rec td.rt .v')].slice(0, 12).map((e) => e.textContent.trim());
      return { arrow: rtTh.textContent.includes('▼'), vals };
    });
    expect(m.arrow).toBe(true);
    // Letter grades: A++ > A+ > A > B+ > B > C+ > C > D > F.
    const ORDER = ['A++', 'A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F'];
    const ranks = m.vals.map((v) => ORDER.indexOf(v.split('/')[0].trim()));
    for (let i = 1; i < ranks.length; i++) expect(ranks[i]).toBeGreaterThanOrEqual(ranks[i - 1]);
  });

  test('names link to player detail', async ({ page }) => {
    await mountPool(page);
    const href = await page.evaluate(() =>
      document.querySelector('#hub-pool tbody tr.rec .nm a')?.getAttribute('href') || '');
    expect(href).toContain('recruit');
  });
});

test.describe('filters compose', () => {
  test('region + position + year + search narrow together', async ({ page }) => {
    await mountPool(page);
    const before = await rowCount(page);
    expect(before).toBe(450);

    await page.selectOption('#pool-region', 'C');
    const afterRegion = await rowCount(page);
    expect(afterRegion).toBeLessThan(before);

    await page.click('#hub-pool .pool-seg button[data-pos="PG"]');
    const afterPos = await rowCount(page);
    expect(afterPos).toBeLessThanOrEqual(afterRegion);

    await page.click('#hub-pool .pool-seg button[data-year="Junior"]');
    const afterYear = await rowCount(page);
    expect(afterYear).toBeLessThanOrEqual(afterPos);

    // Every surviving row must satisfy all three at once.
    const ok = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-pool tbody tr.rec')].every((tr) => {
        const td = tr.querySelectorAll('td');
        return td[1].textContent.trim() === 'PG'
          && td[3].textContent.trim() === 'JR'
          && td[5].textContent.trim() === 'C';
      }));
    expect(ok).toBe(true);
  });

  test('count line reflects the filtered total', async ({ page }) => {
    await mountPool(page);
    await page.selectOption('#pool-region', 'B');
    const m = await page.evaluate(() => ({
      shown: Number(document.querySelector('#hub-pool .pool-fcount b').textContent),
      rows: document.querySelectorAll('#hub-pool tbody tr.rec').length,
    }));
    expect(m.shown).toBe(m.rows);
  });

  test('Leans to me view keeps only recruits leaning to the user', async ({ page }) => {
    await mountPool(page);
    await page.click('#hub-pool .pool-view[data-view="leans"]');
    const m = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#hub-pool tbody tr.rec')];
      return { n: rows.length, allMine: rows.every((r) => r.classList.contains('mine') || r.classList.contains('list-mine')) };
    });
    expect(m.n).toBeGreaterThan(0);
    expect(m.n).toBeLessThan(450);
    expect(m.allMine).toBe(true);
  });

  test('clicking the active view clears it', async ({ page }) => {
    await mountPool(page);
    await page.click('#hub-pool .pool-view[data-view="leans"]');
    const filtered = await rowCount(page);
    await page.click('#hub-pool .pool-view[data-view="leans"]');
    expect(await rowCount(page)).toBe(450);
    expect(filtered).toBeLessThan(450);
  });
});

test.describe('attribute tiles', () => {
  test('10+ renders in the brand RT display blue', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      // Force a known spread onto the first row's chips and re-read the classes.
      const chips = [...document.querySelectorAll('#hub-pool tbody tr.rec:first-child .attr-tile')];
      return chips.map((c) => ({
        v: Number(c.querySelector('s').textContent),
        cls: c.className,
        color: getComputedStyle(c.querySelector('s')).color,
      }));
    });
    const blue = 'rgb(74, 144, 217)';
    for (const chip of m) {
      if (chip.v >= 10) {
        expect(chip.cls, `value ${chip.v}`).toContain('is-elite');
        expect(chip.color, `value ${chip.v}`).toBe(blue);
      } else {
        expect(chip.cls, `value ${chip.v}`).not.toContain('is-elite');
        expect(chip.color, `value ${chip.v}`).not.toBe(blue);
      }
    }
  });

  test('the tier boundaries hold at 9/10', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const chip = document.querySelector('#hub-pool tbody tr.rec:first-child .attr-tile');
      const s = chip.querySelector('s');
      const read = (v) => {
        s.textContent = String(v);
        chip.className = 'attr-tile ' + (v >= 10 ? 'is-elite' : v >= 7 ? 'is-hi' : v <= 3 ? 'is-lo' : '');
        return getComputedStyle(s).color;
      };
      return { nine: read(9), ten: read(10), sixteen: read(16) };
    });
    expect(m.ten).toBe('rgb(74, 144, 217)');
    expect(m.sixteen).toBe('rgb(74, 144, 217)');
    expect(m.nine).not.toBe('rgb(74, 144, 217)');
  });
});

test.describe('watchlist', () => {
  test('star toggles, is 32px, gold when on, hollow when off, and has no text label', async ({ page }) => {
    await mountPool(page);
    const before = await page.evaluate(() => {
      const b = document.querySelector('#hub-pool .wt');
      const r = b.getBoundingClientRect();
      return {
        w: r.width, h: r.height, on: b.classList.contains('is-on'),
        fill: b.querySelector('path').getAttribute('fill'),
        text: b.textContent.trim(),
      };
    });
    expect(before.w).toBe(32);
    expect(before.h).toBe(32);
    expect(before.on).toBe(false);
    expect(before.fill).toBe('none');
    expect(before.text).toBe('');

    await page.click('#hub-pool tbody tr.rec:first-child .wt');
    await page.waitForFunction(() =>
      document.querySelector('#hub-pool tbody tr.rec:first-child .wt').classList.contains('is-on'));
    // Park the pointer away from the row: .wt.is-on:hover is a different (lighter) gold,
    // so measuring while hovering would test the wrong state.
    await page.mouse.move(0, 0);
    // .wt has transition: color .14s, so getComputedStyle mid-flight returns an
    // interpolated colour. Wait for it to settle on the resting gold — this both waits
    // and asserts (a colour that never settles fails on timeout).
    await page.waitForFunction(() =>
      getComputedStyle(document.querySelector('#hub-pool tbody tr.rec:first-child .wt')).color
        === 'rgb(255, 215, 0)', null, { timeout: 3000 });
    const after = await page.evaluate(() => {
      const b = document.querySelector('#hub-pool tbody tr.rec:first-child .wt');
      return {
        fill: b.querySelector('path').getAttribute('fill'),
        color: getComputedStyle(b).color,
        pressed: b.getAttribute('aria-pressed'),
      };
    });
    expect(after.fill).toBe('currentColor');
    expect(after.pressed).toBe('true');
    // Gold #FFD700
    expect(after.color).toBe('rgb(255, 215, 0)');
  });

  test('toggle PATCHes the watchlist endpoint and nothing else', async ({ page }) => {
    await mountPool(page);
    await page.click('#hub-pool tbody tr.rec:first-child .wt');
    await page.waitForFunction(() => window.__patchCalls.length > 0);
    const calls = await page.evaluate(() => window.__patchCalls);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain('/franchise/recruiting-watchlist');
    expect(calls[0].body.watching).toBe(true);
    expect(calls[0].unexpected).toBeUndefined();
  });

  test('the toggle request is sent as JSON, not text/plain', async ({ page }) => {
    // mountPool stubs fetchJSON and asserts only on the parsed body, so it never sees
    // the request headers — which is how a missing Content-Type shipped. fetch()
    // defaults a string body to text/plain and FastAPI 422s it before the handler
    // runs, so the star flipped optimistically and reverted on every click. Assert on
    // the options the hub passes, since that is what decides the header.
    await mountPool(page);
    await page.evaluate(() => {
      window.__wire = [];
      const realFetchJSON = window.RecruitingCommon.fetchJSON;
      window.RecruitingCommon.fetchJSON = function (url, options) {
        const headers = Object.assign(
          {}, window.API_CONFIG ? window.API_CONFIG.getAuthHeaders() : {}, (options || {}).headers || {},
        );
        window.__wire.push({
          url: String(url),
          method: (options || {}).method,
          hasBody: typeof (options || {}).body === 'string',
          contentType: headers['Content-Type'] || headers['content-type'] || null,
        });
        return realFetchJSON.call(this, url, options);
      };
    });

    await page.click('#hub-pool tbody tr.rec:first-child .wt');
    await page.waitForFunction(() => (window.__wire || []).length > 0);
    const [call] = await page.evaluate(() => window.__wire);
    expect(call.url).toContain('/franchise/recruiting-watchlist');
    expect(call.method).toBe('PATCH');
    expect(call.hasBody).toBe(true);
    expect(call.contentType).toBe('application/json');
  });

  test('watchlist view collapses 450 to the shortlist in one click', async ({ page }) => {
    await mountPool(page, { watchlist: ['r-3', 'r-9', 'r-21'] });
    expect(await rowCount(page)).toBe(450);
    await page.click('#hub-pool .pool-view[data-view="watch"]');
    expect(await rowCount(page)).toBe(3);
  });

  test('a persisted watchlist paints stars on load', async ({ page }) => {
    await mountPool(page, { watchlist: ['r-0', 'r-1'] });
    const onCount = await page.evaluate(() =>
      document.querySelectorAll('#hub-pool .wt.is-on').length);
    expect(onCount).toBe(2);
  });

  test('the Watchlist view count matches the watchlist size', async ({ page }) => {
    await mountPool(page, { watchlist: ['r-5', 'r-6', 'r-7', 'r-8'] });
    const n = await page.evaluate(() =>
      document.querySelector('#hub-pool .pool-view[data-view="watch"] .n').textContent);
    expect(n).toBe('4');
  });
});

test.describe('week-20 seeding must not persist', () => {
  test('board pre-populates from the watchlist without any write', async ({ page }) => {
    // noLeans isolates the watchlist half of the seed; the leans half is covered in
    // invite-board.spec.js.
    await mountPool(page, { week: 20, noLeans: true, watchlist: ['r-4', 'r-8', 'r-12'] });
    // The stamp rides behind two dynamic imports, so it lands after load settles.
    // Waiting for it is what makes the exact-list assertion below deterministic.
    await page.waitForFunction(() =>
      window.__patchCalls.some((c) => String(c.url).includes('invite-seed-modal-seen')));
    const m = await page.evaluate(() => ({
      orders: window.__patchCalls.filter((c) => String(c.url).includes('recruiting-orders')),
      other: window.__patchCalls.map((c) => String(c.url).split('/').pop()),
      slots: [...document.querySelectorAll('#hub-pool .pool-rankbadge')].length,
    }));
    // The seed is client state only: nothing is posted to recruiting-orders, which is
    // the only field has_saved_board reads.
    expect(m.orders).toHaveLength(0);
    // One load-time write IS expected now and must stay accounted for by name — the
    // seeded-board Sammy note stamping itself seen. Anything else on this list is a
    // regression, so it is asserted exactly rather than filtered away.
    expect(m.other).toEqual(['invite-seed-modal-seen']);
    expect(m.slots).toBe(3);
  });

  test('a saved board is never overwritten by the watchlist', async ({ page }) => {
    await mountPool(page, {
      week: 20,
      watchlist: ['r-100', 'r-200'],
      savedOrders: { 1: 'r-1', 2: 'r-2' },
    });
    // Rows are RT-sorted, so badge DOM order is not board order — assert membership.
    const ranked = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-pool .pool-rankbadge')].map((b) => b.dataset.id));
    expect(ranked.sort()).toEqual(['r-1', 'r-2']);
    expect(ranked).not.toContain('r-100');
    expect(ranked).not.toContain('r-200');
  });

  test('nothing to seed from leaves the board empty', async ({ page }) => {
    await mountPool(page, { week: 20, noLeans: true });
    const slots = await page.evaluate(() => document.querySelectorAll('#hub-pool .pool-rankbadge').length);
    expect(slots).toBe(0);
  });
});


test.describe('invite phase runs full width (no board rail)', () => {
  test('the rail is gone and the body is a single column', async ({ page }) => {
    await mountPool(page, { week: 22 });          // invite season
    const m = await page.evaluate(() => {
      const body = document.querySelector('.spine-body');
      return {
        rail: document.querySelectorAll('.brail, #hub-dock').length,
        cls: body.className,
        cols: getComputedStyle(body).gridTemplateColumns.split(' ').length,
        board: !!document.getElementById('hub-board'),
      };
    });
    expect(m.rail).toBe(0);
    expect(m.cls).toContain('no-dock');
    expect(m.cols).toBe(1);
    expect(m.board).toBe(true);                   // the invite board itself stays
  });

  test('the Lean and Watch columns are rendered, but still overflow (known limitation)', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const m = await page.evaluate(() => {
      const sc = document.querySelector('#hub-pool .pool-scroll');
      const heads = [...document.querySelectorAll('#hub-pool thead th')].map((h) => h.className);
      return {
        hasLean: heads.some((c) => c.includes('lean')),
        hasWatch: heads.some((c) => c.includes('watch')),
        client: sc.clientWidth,
        overflowBy: sc.scrollWidth - sc.clientWidth,
      };
    });
    // Both columns exist and are reachable by scrolling .pool-scroll.
    expect(m.hasLean).toBe(true);
    expect(m.hasWatch).toBe(true);

    // KNOWN LIMITATION, recorded rather than asserted away.
    //
    // Removing the 306px rail gave the pool that width back, but the table still needs
    // ~88px more than it has, so Lean and Watch sit off the right edge until the user
    // scrolls sideways. The cause is NOT the rail: `.doc { max-width: 1360px }` in
    // recruiting-spine.css caps the whole hub page, so the pool measures the same
    // 1096px at 1440, 1600, 1920 and 2200 viewports. Fixing it means raising that cap,
    // narrowing the 12-tile attributes column, or dropping a column — a product call.
    //
    // Asserts the CURRENT truth so the suite stays honest; flip to toBe(0) once settled.
    expect(m.overflowBy).toBeGreaterThan(0);
    expect(m.overflowBy).toBeLessThan(200);   // if this grows, something else regressed
  });

  test('the passive phase is unchanged — it never had a rail', async ({ page }) => {
    await mountPool(page, { week: 7 });
    const m = await page.evaluate(() => ({
      cls: document.querySelector('.spine-body').className,
      board: !!document.getElementById('hub-board'),
    }));
    expect(m.cls).toContain('no-dock');
    expect(m.board).toBe(false);
  });
});
