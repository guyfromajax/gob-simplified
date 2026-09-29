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
  'js/shared/franchiseContext.js',
  'common.js',
  'js/utils/attributeDisplay.js',
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
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id&hub=pool');
  await page.setContent(`
    <style>${CSS}</style>
    <style>body{margin:0;background:#0b0d14}.doc{max-width:${opts.docWidth || 1180}px;margin:0 auto;padding:20px}</style>
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
      const table = document.querySelector('#hub-pool table.pool');
      const fits = table.scrollWidth <= s.clientWidth + 1;
      return {
        scrollable: s.scrollHeight > s.clientHeight,
        bodyOverflowsX: document.body.scrollWidth > window.innerWidth + 1,
        fits,
        reps: document.querySelectorAll('#hub-pool tbody tr.gob-rep').length,
      };
    });
    expect(m.scrollable).toBe(true);
    expect(m.bodyOverflowsX).toBe(false);
    // Narrow tables drop the 16-row repeat; a table that still overflows keeps all 28.
    expect(m.reps).toBe(m.fits ? 0 : 28);
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
      const input = document.querySelector('.gob-search');
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
  test('column order is Watch Recruit POS RT YR HT WT RGN then the six groups then Lean', async ({ page }) => {
    await mountPool(page);
    const labels = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-pool thead tr.gob-cols th')].map((t) => t.textContent.replace(/[▲▼]/g, '').trim()));
    expect(labels).toEqual(['', 'Recruit', 'POS', 'RT', 'YR', 'HT', 'WT', 'RGN', 'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'Lean']);
  });

  test('every header is centered over its column', async ({ page }) => {
    await mountPool(page);
    const offsets = await page.evaluate(() => {
      const heads = [...document.querySelectorAll('#hub-pool thead tr.gob-cols th')];
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

  test('each attribute is a label-less roster tile under its group header', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const row = document.querySelector('#hub-pool tbody tr.rec');
      const tiles = [...row.querySelectorAll('.attr-tile')];
      const groups = [...document.querySelectorAll('#hub-pool thead tr.gob-groups th.gob-g')].map((th) => ({
        name: th.textContent.trim(),
        span: Number(th.colSpan),
      }));
      const offense = document.querySelector('#hub-pool thead tr.gob-groups th.gob-g');
      const sc = row.querySelector('.attr-tile[data-attr="SC"]');
      const sh = row.querySelector('.attr-tile[data-attr="SH"]');
      const head = offense.getBoundingClientRect();
      const a = sc.getBoundingClientRect();
      const b = sh.getBoundingClientRect();
      return {
        tiles: tiles.length,
        labels: row.querySelectorAll('.attr-tile u').length,
        groups,
        offenseCenter: head.left + head.width / 2,
        pairCenter: (a.left + b.right) / 2,
      };
    });
    expect(m.tiles).toBe(12);
    expect(m.labels).toBe(0);
    const first = await page.evaluate(() => {
      const row = document.querySelector('#hub-pool tbody tr.rec');
      const rt = row.querySelector('td.rt .rtl b:not(.pot)');
      const digits = [...row.querySelectorAll('.attr-tile s')].map((s) => s.textContent.trim());
      const tile = row.querySelector('.attr-tile');
      const digit = tile.querySelector('s');
      const tileBox = tile.getBoundingClientRect();
      const av = row.querySelector('.pc-av');
      const rowBox = row.getBoundingClientRect();
      return {
        rt: rt ? rt.textContent.trim() : '',
        digits,
        tileW: tileBox.width,
        tileH: tileBox.height,
        digitSize: parseFloat(getComputedStyle(digit).fontSize),
        digitWeight: getComputedStyle(digit).fontWeight,
        digitFamily: getComputedStyle(digit).fontFamily,
        radius: getComputedStyle(av).borderRadius,
        avW: av.getBoundingClientRect().width,
        rowH: rowBox.height,
      };
    });
    expect(CSS).toContain('.pool .attr-tile{width:var(--dsz-30);height:var(--dsz-26);border-radius:var(--radius-5)}');
    expect(CSS).toContain('font:var(--fw-bold) var(--fs-20)/var(--lh-1) var(--font-display)');
    expect(CSS).toContain('border-radius:var(--radius-6)');
    expect(first.rt).toMatch(/^[A-F]/);
    expect(first.digits).toHaveLength(12);
    for (const digit of first.digits) expect(digit, 'tile digit').toMatch(/^\d+$/);
    // The harness page does not load gob-tokens, so --dsz-30 / --fs-20 do not resolve
    // there. When they do (the shell), the tile must be the roster size.
    const dszW = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dsz-30')));
    if (Number.isFinite(dszW)) {
      expect(first.tileW).toBeCloseTo(dszW, 0);
      expect(first.tileH).toBeCloseTo(first.digitSize === 23.5 ? 30.5 : 26, 0);
      expect([20, 23.5]).toContain(first.digitSize);
      expect(Number(first.digitWeight)).toBeGreaterThanOrEqual(700);
      // Square, like every other player headshot: a small corner, not half the side.
      expect(first.radius, 'portrait radius').not.toBe('50%');
      expect(parseFloat(first.radius) / first.avW).toBeLessThanOrEqual(0.25);
    }
    expect(m.groups.map((g) => g.name)).toEqual(['Offense', 'Defense', 'Skills', 'Grit', 'Body', 'Mind']);
    expect(m.groups.every((g) => g.span === 2)).toBe(true);
    expect(Math.abs(m.offenseCenter - m.pairCenter)).toBeLessThan(2);
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
    // Column sum, not the page. The harness does not resolve --dsz-30, so the
    // attribute columns shrink to their content here; in the shell they are 38px
    // and the passive table is 1140.
    expect(m.tableWidth).toBeGreaterThan(900);
    expect(m.tableWidth).toBeLessThan(1400);
  });

  test('RT sorts descending by default and is the active sort', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const rtTh = [...document.querySelectorAll('#hub-pool thead th')].find((t) => t.textContent.includes('RT'));
      const vals = [...document.querySelectorAll('#hub-pool tbody tr.rec td.rt .rtl b:not(.pot)')].slice(0, 12).map((e) => e.textContent.trim());
      return { arrow: rtTh.textContent.includes('▼'), vals };
    });
    expect(m.arrow).toBe(true);
    // Letter grades: A++ > A+ > A > B+ > B > C+ > C > D > F.
    const ORDER = ['A++', 'A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F'];
    const ranks = m.vals.map((v) => ORDER.indexOf(v.trim()));
    for (let i = 1; i < ranks.length; i++) expect(ranks[i]).toBeGreaterThanOrEqual(ranks[i - 1]);
  });

  test('names link to player detail', async ({ page }) => {
    await mountPool(page);
    const href = await page.evaluate(() =>
      document.querySelector('#hub-pool tbody tr.rec .nm a')?.getAttribute('href') || '');
    expect(href).toContain('recruit');
  });

  test('names are not orange, RT is letters, and every headshot is an image or a monogram', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const link = document.querySelector('#hub-pool .recruit-name-link');
      const color = getComputedStyle(link).color;
      const cell = document.querySelector('#hub-pool td.rt');
      const rt = cell.querySelector('.rtl').textContent.replace(/\s/g, '');
      const shots = [...document.querySelectorAll('#hub-pool tbody tr.rec .pc-av')];
      const empty = shots.filter((el) => !el.querySelector('img') && !el.textContent.trim()).length;
      const withImg = shots.filter((el) => el.querySelector('img')).length;
      const letters = shots.filter((el) => !el.querySelector('img') && el.textContent.trim()).length;
      return { color, rt, title: cell.getAttribute('title'), empty, withImg, letters, rows: shots.length };
    });
    expect(m.color).not.toBe('rgb(247, 148, 32)');
    expect(m.rt).toMatch(/^[A-F][+\-−]*$/);
    expect(m.title).toBe('Current → Potential');
    expect(m.empty).toBe(0);
    expect(m.withImg + m.letters).toBe(m.rows);
    expect(m.letters).toBeGreaterThan(0);
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
        return tr.querySelector('td.pos').textContent.trim() === 'PG'
          && tr.querySelector('td.year').textContent.trim() === 'JR'
          && tr.querySelector('td.rgn').textContent.trim() === 'C';
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

  test('Leans tab keeps only recruits leaning to the user', async ({ page }) => {
    await mountPool(page);
    await page.evaluate(() => window.RecruitingHub.show('leans'));
    const m = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#hub-pool tbody tr.rec')];
      return { n: rows.length, allMine: rows.every((r) => r.classList.contains('mine') || r.classList.contains('list-mine')) };
    });
    expect(m.n).toBeGreaterThan(0);
    expect(m.n).toBeLessThan(450);
    expect(m.allMine).toBe(true);
    await page.evaluate(() => window.RecruitingHub.show('pool'));
    expect(await rowCount(page)).toBe(450);
  });

  test('clicking the active view clears it', async ({ page }) => {
    await mountPool(page, { watchlist: ['r-3', 'r-9'] });
    await page.click('#hub-pool .pool-view[data-view="watch"]');
    const filtered = await rowCount(page);
    await page.click('#hub-pool .pool-view[data-view="watch"]');
    expect(await rowCount(page)).toBe(450);
    expect(filtered).toBeLessThan(450);
  });
});

test.describe('attribute tiles', () => {
  test('9+ renders in the brand blue, and nothing below 9 does', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const chips = [...document.querySelectorAll('#hub-pool tbody tr.rec:first-child .attr-tile')];
      return chips.map((c) => ({
        v: Number(c.querySelector('s').textContent),
        cls: c.className,
        color: getComputedStyle(c.querySelector('s')).color,
      }));
    });
    const blue = 'rgb(74, 144, 217)';
    for (const chip of m) {
      if (chip.v >= 9) {
        expect(chip.cls, `value ${chip.v}`).toContain('is-elite');
        expect(chip.color, `value ${chip.v}`).toBe(blue);
      } else {
        expect(chip.cls, `value ${chip.v}`).not.toContain('is-elite');
        expect(chip.color, `value ${chip.v}`).not.toBe(blue);
      }
    }
  });

  test('tier class paints 9 elite, 8 high, 6 mid, 4 low', async ({ page }) => {
    await mountPool(page);
    const m = await page.evaluate(() => {
      const chip = document.querySelector('#hub-pool tbody tr.rec:first-child .attr-tile');
      const s = chip.querySelector('s');
      const read = (v) => {
        s.textContent = String(v);
        chip.className = 'attr-tile ' + window.GOB_AttrTiles.tierClass(v);
        return getComputedStyle(s).color;
      };
      return { nine: read(9), eight: read(8), six: read(6), four: read(4) };
    });
    expect(m.nine).toBe('rgb(74, 144, 217)');
    expect(m.eight).not.toBe('rgb(74, 144, 217)');
    expect(m.six).toBe('rgb(255, 215, 0)');
    expect(m.four).not.toBe('rgb(74, 144, 217)');
  });
});

test.describe('watchlist', () => {
  test('star toggles, is 32px, neutral when on, hollow when off, and has no text label', async ({ page }) => {
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
    // Park the pointer away from the row so hover does not tint the resting colour.
    await page.mouse.move(0, 0);
    // .wt has transition: color .14s — wait for the resting text colour.
    await page.waitForFunction(() =>
      getComputedStyle(document.querySelector('#hub-pool tbody tr.rec:first-child .wt')).color
        === 'rgb(244, 245, 248)', null, { timeout: 3000 });
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
    expect(after.color).toBe('rgb(244, 245, 248)');
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

  test('at 1280 a passive week shows Lean inside the viewport with no horizontal overflow', async ({ page }) => {
    await mountPool(page, { week: 7 });
    await page.setViewportSize({ width: 1280, height: 720 });
    const m = await page.evaluate(() => {
      const sc = document.querySelector('#hub-pool .pool-scroll');
      const lean = document.querySelector('#hub-pool tbody tr.rec td.lean-col');
      const th = document.querySelector('#hub-pool thead th');
      return {
        leanRight: lean.getBoundingClientRect().right,
        inner: window.innerWidth,
        overflow: sc.scrollWidth - sc.clientWidth,
        reps: document.querySelectorAll('#hub-pool tbody tr.gob-rep').length,
        sticky: getComputedStyle(th).position,
        backdrop: getComputedStyle(th).backdropFilter,
      };
    });
    expect(m.leanRight).toBeLessThanOrEqual(m.inner + 1);
    expect(m.overflow).toBeLessThanOrEqual(1);
    expect(m.reps).toBe(0);
    expect(m.sticky).toBe('sticky');
    expect(m.backdrop).toBe('none');
  });

  test('a table wider than its scrollport keeps the repeated header', async ({ page }) => {
    await mountPool(page, { week: 7, docWidth: 640 });
    const m = await page.evaluate(() => {
      const sc = document.querySelector('#hub-pool .pool-scroll');
      return {
        overflow: sc.scrollWidth - sc.clientWidth,
        reps: document.querySelectorAll('#hub-pool tbody tr.gob-rep').length,
      };
    });
    expect(m.overflow).toBeGreaterThan(1);
    expect(m.reps).toBe(28);
  });

  test('Lean stays on screen when the invite column is open', async ({ page }) => {
    await mountPool(page, { week: 22 });
    const m = await page.evaluate(() => {
      const sc = document.querySelector('#hub-pool .pool-scroll');
      const lean = document.querySelector('#hub-pool tbody tr.rec td.lean-col');
      const box = sc.getBoundingClientRect();
      const fits = sc.scrollWidth <= sc.clientWidth + 1;
      return {
        hasLean: !!document.querySelector('#hub-pool thead th.lean-h'),
        hasWatch: !!document.querySelector('#hub-pool thead th.watch-col'),
        hasAdd: !!document.querySelector('#hub-pool thead th.act'),
        leanInside: lean.getBoundingClientRect().right <= box.left + sc.clientWidth + 1,
        overflowBy: sc.scrollWidth - sc.clientWidth,
        reps: document.querySelectorAll('#hub-pool tbody tr.gob-rep').length,
        fits,
      };
    });
    expect(m.hasLean).toBe(true);
    expect(m.hasWatch).toBe(true);
    expect(m.hasAdd).toBe(true);
    expect(m.leanInside).toBe(true);
    expect(m.overflowBy).toBeLessThan(320);
    expect(m.reps).toBe(m.fits ? 0 : 28);
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
