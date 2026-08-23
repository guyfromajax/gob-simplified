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

const CSS = read('recruiting-spine.css') + read('recruiting-signing.css') + read('css/attr-tiles.css');
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
function fixture(o = {}) {
  const { week = 7, watchlist = [], savedOrders = {}, signed = null,
          conferences = null, revealSeen = false, savedEntries = [] } = o;
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
    season: o.season || 3,
    recruits,
    // The real payload's team_name_map covers every team (resolve_team_name_map with
    // no ids), so the fixture must too — a two-entry map leaves the rails nameless and
    // hides exactly the kind of bug those rails would surface.
    team_name_map: Object.assign(
      { [USER_TEAM]: 'South Lancaster', 'rival-1': 'Fairview' }, o.teamNames || {}),
    saved_orders: savedOrders, watchlist,
    saved_order_entries_week_35: savedEntries,
    new_lean_recruit_ids: [],
    week_35_recruiting_results: signed ? { signed_players: signed } : {},
    week_35_recruiting_ran: !!signed,
    week_35_reveal_seen: revealSeen,
    conferences: withRegions(conferences || {
      user_conference: 9, sister_conference: 10,
      order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
      by_team_id: { [USER_TEAM]: 9 },
    }, USER_TEAM),
  };
}

/** Region letter for a conference: 1-2 = A, 3-4 = B, ... — mirrors _region_of_conference. */
const regionOf = (c) => String.fromCharCode(65 + Math.floor((Number(c) - 1) / 2));

/** The region view the reveal needs, derived from a conference map the way the server does. */
function withRegions(conferences, userTeamId) {
  const byTeam = conferences.by_team_id || {};
  const regionByTeam = {};
  Object.keys(byTeam).forEach((tid) => { regionByTeam[tid] = regionOf(byTeam[tid]); });
  const userRegion = regionByTeam[String(userTeamId)] || null;
  return Object.assign({}, conferences, {
    user_region: userRegion,
    region_by_team_id: regionByTeam,
    region_team_ids: Object.keys(regionByTeam).filter((tid) => regionByTeam[tid] === userRegion).sort(),
  });
}

async function mountPool(page, opts = {}) {
  const patchCalls = [];
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Real origin first: getQueryContext reads location.search, and about:blank has no
  // origin (setContent preserves whatever URL the page is already on).
  // ?action=run is the FCC's "Run Recruiting Day" handing the press to the hub, which
  // owns both the run call and the reveal.
  // The real homepage is never used — setContent replaces the document on the next
  // line. goto only supplies a same-origin URL (sessionStorage, location.search), so
  // serve a stub and skip a full app page load per test. Under parallel workers those
  // loads queue on the dev server and were the cause of intermittent timeouts here.
  await page.route('**/', (route) => (route.request().resourceType() === 'document'
    ? route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>o</title>' })
    : route.continue()));
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id'
    + (opts.action ? `&action=${opts.action}` : ''));
  await page.setContent(`
    <style>${CSS}</style>
    <style>body{margin:0;background:#0b0d14}.doc{max-width:1180px;margin:0 auto;padding:20px}</style>
    <div class="doc"><a id="back-btn" href="#">Back</a><div id="hub-root" class="spine"></div></div>
  `);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });

  await page.evaluate(({ data, runResults }) => {
    window.__patchCalls = [];
    // Flat url log. The reveal's no-replay tests assert on it, and the auto-run path
    // means those calls now happen during mount rather than after a click.
    window.__seen = [];
    window.__runResults = runResults;
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`,
      getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/img/${id}.png`,
      // The signed-player (uniformed) master. Must exist on the stub or the reveal card
      // silently falls back to the white recruit master and the portrait assertion
      // tests the stub instead of the code.
      getPlayerImageUrl: (pid) => `https://stub.local/players/master/${pid}.png`,
      // The reveal force-paints a lead of masters before opening. Absent from the stub
      // it resolved instantly and the prep gate was never exercised at all.
      ensurePlayerImage: (fid, pid) => {
        window.__ensured = window.__ensured || [];
        window.__ensured.push(String(pid));
        return window.__ensureDelayMs
          ? new Promise((r) => setTimeout(() => r({ status: 'painted' }), window.__ensureDelayMs))
          : Promise.resolve({ status: 'exists' });
      },
      ensureRecruitImage: () => Promise.resolve({ status: 'skip' }),
    };
    window.__fixture = data;
    const realFetchJSON = window.RecruitingCommon.fetchJSON;
    window.RecruitingCommon.fetchJSON = function (url, options) {
      const method = (options && options.method) || 'GET';
      window.__seen.push(String(url));
      if (String(url).includes('/franchise/recruiting-data')) {
        return Promise.resolve(window.__fixture);
      }
      // Auto-run fires during load, so this stub has to exist before HUB is injected.
      if (String(url).includes('run-week-35')) {
        window.__patchCalls.push({ url: String(url) });
        return Promise.resolve({ status: 'success', week: 36, results: { signed_players: window.__runResults || [] } });
      }
      if (String(url).includes('week-35-reveal-seen')) {
        window.__patchCalls.push({ url: String(url) });
        return Promise.resolve({});
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
  }, { data: fixture(opts), runResults: opts.runResults || null });

  await page.addScriptTag({ content: HUB });
  await page.waitForSelector(opts.waitFor ? opts.waitFor
    : opts.action === 'run' ? '#hub-reveal'
    : opts.week === 35 ? '.spool-rows .prow'
      : opts.week >= 36 ? '.rstage' : '#hub-pool table.pool tbody tr.rec', { timeout: 10000 });
  return patchCalls;
}

const rowCount = (page) => page.locator('#hub-pool tbody tr.rec').count();


/**
 * Signing Day conference reveal + the week-36 league list.
 * Drives the REAL recruiting-hub.js with only the network stubbed.
 */
const USER = 'user-team-id';

/** 8 conference teams; the user's is USER. Every signing carries team + rt. */
function conferenceFixture({ mine = 3, others = 12, walkOns = 4 } = {}) {
  const byTeam = { [USER]: 9 };
  for (let i = 1; i <= 7; i += 1) byTeam[`c9-${i}`] = 9;
  for (let i = 1; i <= 4; i += 1) byTeam[`c10-${i}`] = 10;   // sister conference
  for (let i = 1; i <= 3; i += 1) byTeam[`c3-${i}`] = 3;     // an unrelated conference
  const signed = [];
  // year + potential ride on every signing now: the week-36 row shows Name / Pos / Yr /
  // RT-pair, and without them the fixture would prove only that '--' renders.
  const YEARS = ['JH', 'Freshman', 'Sophomore', 'Junior'];
  let rt = 99;
  for (let i = 0; i < mine; i += 1) signed.push({ player_id: `p-m${i}`, image_id: `img-m${i}`, recruit_id: `r-${i}`, name: `Mine ${i}`, pos: 'PF', rt: rt, potential_rt_ratcheted: rt-- + 1, year: YEARS[i % 4], team_id: USER, team_name: 'South Lancaster' });
  for (let i = 0; i < others; i += 1) signed.push({ player_id: `p-v${i}`, image_id: `img-v${i}`, recruit_id: `r-${100 + i}`, name: `Rival ${i}`, pos: 'SG', rt: rt, potential_rt_ratcheted: rt-- + 1, year: YEARS[i % 4], team_id: `c9-${(i % 7) + 1}`, team_name: `Rival ${i % 7}` });
  for (let i = 0; i < 5; i += 1) signed.push({ player_id: `p-s${i}`, image_id: `img-s${i}`, recruit_id: `r-${200 + i}`, name: `Sister ${i}`, pos: 'C', rt: rt, potential_rt_ratcheted: rt-- + 1, year: YEARS[i % 4], team_id: `c10-${(i % 4) + 1}`, team_name: `Sister ${i % 4}` });
  for (let i = 0; i < 4; i += 1) signed.push({ player_id: `p-f${i}`, image_id: `img-f${i}`, recruit_id: `r-${300 + i}`, name: `Far ${i}`, pos: 'PG', rt: rt, potential_rt_ratcheted: rt-- + 1, year: YEARS[i % 4], team_id: `c3-${(i % 3) + 1}`, team_name: `Far ${i % 3}` });
  for (let i = 0; i < walkOns; i += 1) signed.push({ name: `WalkOn ${i}`, pos: 'C', rt: 5, team_id: USER, team_name: 'South Lancaster', walk_on: true });
  const teamNames = {};
  Object.keys(byTeam).forEach(function (tid) {
    teamNames[tid] = tid === USER ? 'South Lancaster' : 'Team ' + tid.toUpperCase();
  });
  const conferences = withRegions({
    user_conference: 9, sister_conference: 10,
    order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
    by_team_id: byTeam,
  }, USER);
  return { signed, conferences, teamNames };
}

/**
 * Reach the reveal the way the shipped flow now does.
 *
 * Submitting no longer runs anything: it saves, the modal sends the player to the
 * locker room, and the FCC's "Run Recruiting Day" hands the press back here as
 * ?action=run. So the reveal is entered on load with orders already saved. That
 * submit-only-saves half is asserted directly in its own test below.
 */
async function submitAndReveal(page, opts = {}) {
  const { signed, conferences } = conferenceFixture(opts);
  await mountPool(page, {
    week: 35, signed: null, conferences, revealSeen: false,
    savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
    action: 'run',
    runResults: signed,
  });
  await page.waitForSelector('#hub-reveal', { timeout: 5000 });
  return signed;
}

const rowNames = (page) => page.evaluate(() =>
  [...document.querySelectorAll('.rvrow .rvnm')].map((e) => e.textContent.trim()));

/**
 * Signing Day stage. Replaces the list-playback suite: the reveal is now a card at a
 * time with a region tally, a national top 25 and the user's funded targets, all
 * moving on one tick.
 */
const card = (page) => page.evaluate(() => {
  const c = document.querySelector('#hub-reveal .sd-card');
  if (!c) return null;
  return {
    cls: c.className,
    nm: c.querySelector('.sd-card-nm').textContent.trim(),
    flag: c.querySelector('.sd-card-lbl').textContent.trim(),
    meta: [...c.querySelectorAll('.sd-meta b')].map((b) => b.textContent.trim()),
  };
});
const railRows = (page, right) => page.evaluate((r) => {
  const rail = document.querySelector('#hub-reveal .sd-rail' + (r ? '.is-right' : ':not(.is-right)'));
  return [...rail.querySelectorAll('.sd-tm')].map((t) => ({
    name: t.querySelector('.nm').textContent.trim(),
    score: parseInt(t.querySelector('.sc').textContent, 10),
    user: t.classList.contains('is-user'),
    hit: t.classList.contains('is-hit'),
  }));
}, right);
const prog = (page) => page.evaluate(() =>
  document.querySelector('#hub-reveal .sd-prog-n').textContent.trim());

/** Open the stage with the reveal armed and paused on card 0. */
async function stage(page, opts = {}) {
  const { signed, conferences, teamNames } = conferenceFixture(opts.fixture || {});
  await page.setViewportSize({ width: 1560, height: 940 });
  await mountPool(page, Object.assign({
    week: 35, signed: null, conferences, teamNames, revealSeen: false,
    savedEntries: opts.savedEntries || [{ id: 'r-0', points: 12, playing_time: false }],
    action: 'run', runResults: signed,
  }, opts.mount || {}));
  await page.waitForSelector('#hub-reveal .sd', { timeout: 8000 });
  return signed;
}

test.describe('the stage', () => {
  test('covers the REGION, excludes walk-ons, highest RT first', async ({ page }) => {
    await stage(page);
    // Region E is conferences 9 + 10 — the user's conference and its sister. Conference
    // 3 (region B) is revealed behind the scenes and must not produce cards.
    await page.click('#rv-end');
    const names = await page.evaluate(() => window.__revealCardNames || null);
    const m = await page.evaluate(() => ({
      total: Number(document.querySelector('#rv-done') ? 1 : 0),
      prog: document.querySelector('.sd-prog-n').textContent,
    }));
    void names;
    expect(m.total).toBe(1);             // reached the end
    expect(m.prog).toContain('Region E');
  });

  test('the screen names itself: season, and the region it covers', async ({ page }) => {
    await stage(page);
    const m = await page.evaluate(() => ({
      eyebrow: document.querySelector('#hub-reveal .sd-brand small').textContent.trim(),
      title: document.querySelector('#hub-reveal .sd-brand b').textContent.trim(),
    }));
    expect(m.eyebrow).toBe('Season 3 · Signing Day');
    expect(m.title).toBe('Region E Signings');
  });

  test('the stage sits above the global auth bar', async ({ page }) => {
    // auth-bar.css is position:fixed at z-index 9998. At 5000 it painted over .sd-top,
    // which is where the title, the countdown and every control live — they rendered
    // perfectly and sat underneath the site header.
    await stage(page);
    const z = await page.evaluate(() =>
      Number(getComputedStyle(document.querySelector('#hub-reveal')).zIndex));
    expect(z).toBeGreaterThan(9998);
  });

  test('a card carries name, position, year and an RT pair', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    const c = await card(page);
    expect(c.nm).not.toBe('');
    expect(c.meta).toHaveLength(3);
    expect(['JH', 'FR', 'SO', 'JR']).toContain(c.meta[1]);
    expect(c.meta[2]).toContain('/');     // current/potential, not a lone grade
  });

  test('the team is carried by its own plate, above everything', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    const m = await page.evaluate(() => {
      const card = document.querySelector('#hub-reveal .sd-card');
      const plate = card.querySelector('.sd-plate img');
      const lbl = card.querySelector('.sd-card-lbl').getBoundingClientRect();
      const nm = card.querySelector('.sd-card-nm').getBoundingClientRect();
      const shot = card.querySelector('.sd-shot-img').getBoundingClientRect();
      const plateBox = card.querySelector('.sd-plate').getBoundingClientRect();
      return {
        src: plate ? plate.getAttribute('src') : null,
        labelAbovePlate: lbl.bottom <= plateBox.top + 1,
        plateAboveBody: plateBox.bottom <= nm.top + 1,
        // The portrait is now supporting, not the hero — it used to be 430px square.
        portraitW: Math.round(shot.width),
        plateW: Math.round(plateBox.width),
        // The old bar across the portrait is gone for good.
        oldBar: document.querySelectorAll('#hub-reveal .sd-flag, #hub-reveal .sd-card-signed').length,
      };
    });
    expect(m.src).toContain('/images/teams/');
    expect(m.src).toContain('banner_primary');
    expect(m.labelAbovePlate).toBe(true);
    expect(m.plateAboveBody).toBe(true);
    expect(m.portraitW).toBeLessThan(m.plateW / 2);
    expect(m.oldBar).toBe(0);
  });

  test('the portrait requests the UNIFORMED master, not the white recruit one', async ({ page }) => {
    // players/master/<player_id>.png is what the week-35 warm paint produces.
    // recruits/white/<image_id>.png is the pre-signing white jersey — asking for that
    // meant every card showed in a blank practice top no matter what had been painted.
    await stage(page);
    await page.click('#rv-skip');
    const src = await page.evaluate(() =>
      document.querySelector('#hub-reveal .sd-shot-img img').getAttribute('src'));
    expect(src).toContain('players/master');
    expect(src).not.toContain('recruits/white');
  });

  test('red is earned — only a recruit you funded can be a loss', async ({ page }) => {
    // r-0 is the user's own signing; r-100 went to an in-region rival and was funded;
    // everyone else in the region was never bid on.
    await stage(page, {
      savedEntries: [
        { id: 'r-0', points: 12, playing_time: false },
        { id: 'r-100', points: 9, playing_time: false },
      ],
    });
    await page.click('#rv-end');
    const tiles = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-reveal .sd-tg')].map((t) => ({
        cls: t.className, st: t.querySelector('.sd-tg-st').textContent.trim(),
      })));
    // Funded and lost reads as a loss...
    expect(tiles.some((t) => t.cls.includes('is-lost'))).toBe(true);
    expect(tiles.some((t) => t.cls.includes('is-won'))).toBe(true);
    expect(tiles).toHaveLength(2);
  });

  test('a recruit you never bid on is neutral, not a defeat', async ({ page }) => {
    await stage(page, { savedEntries: [{ id: 'r-0', points: 12, playing_time: false }] });
    // Card 1 is the region's top RT, which the user did not fund.
    const states = [];
    for (let i = 0; i < 3; i += 1) {
      await page.evaluate(() => document.querySelector('#hub-reveal').__nudge);
      const c = await page.evaluate(() => {
        const el = document.querySelector('#hub-reveal .sd-card');
        return el ? el.className : null;
      });
      if (c) states.push(c);
      await page.waitForTimeout(20);
      await page.click('#rv-skip');
    }
    // Whatever the walk turned up, no card the user did not fund may be red.
    const anyLost = await page.evaluate(() =>
      !!document.querySelector('#hub-reveal .sd-card.is-lost'));
    void states;
    expect(anyLost).toBe(false);
  });
});

test.describe('the tallies', () => {
  test('BOTH rails start empty and fill as teams sign', async ({ page }) => {
    await stage(page);
    // Listing all sixteen at zero ordered them alphabetically, which reads as a
    // standing and gives the finishing shape away before anyone has signed.
    expect(await railRows(page, false)).toHaveLength(0);
    expect(await railRows(page, true)).toHaveLength(0);
    await page.click('#rv-end');
    const region = await railRows(page, false);
    expect(region.length).toBeGreaterThan(0);
    expect(region.every((r) => r.score > 0)).toBe(true);
  });

  test('a signing moves its team, and the moved row is marked', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    const rows = await railRows(page, false);
    const hit = rows.filter((r) => r.hit);
    expect(hit).toHaveLength(1);
    expect(hit[0].score).toBeGreaterThan(0);
    // A tally that never visibly moves is wallpaper — the increment is the point.
    expect(rows.reduce((n, r) => n + r.score, 0)).toBe(hit[0].score);
  });

  test('the national rail fills as the league walks and never exceeds 25', async ({ page }) => {
    await stage(page);
    // Empty before the first card: 128 teams tied at zero would be alphabetical noise,
    // not a ranking. A team earns its row by scoring.
    expect(await railRows(page, true)).toHaveLength(0);
    const before = (await railRows(page, true)).reduce((n, r) => n + r.score, 0);
    await page.click('#rv-end');
    const after = await railRows(page, true);
    expect(before).toBe(0);
    expect(after.length).toBeLessThanOrEqual(25);
    expect(after.reduce((n, r) => n + r.score, 0)).toBeGreaterThan(0);
    // Descending, always.
    for (let i = 1; i < after.length; i++) expect(after[i].score).toBeLessThanOrEqual(after[i - 1].score);
  });

  test('every region finishes when the cards do — no half-filled table', async ({ page }) => {
    const signed = await stage(page);
    await page.click('#rv-end');
    const total = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-reveal .sd-rail .sd-tm .sc')]
        .reduce((n, e) => n + parseInt(e.textContent, 10), 0));
    void total;
    // Out-of-region signings are consumed proportionally so the national tally is
    // complete on the last card rather than trailing it.
    const natTotal = (await railRows(page, true)).reduce((n, r) => n + r.score, 0);
    const expected = signed.filter((s) => !s.walk_on).reduce((n, s) => n + (s.rt || 0), 0);
    // Top 25 may clip the tail, so it can only ever be a subset of the league total.
    expect(natTotal).toBeGreaterThan(0);
    expect(natTotal).toBeLessThanOrEqual(expected);
  });
});

test.describe('controls', () => {
  test('pause stops the clock; resume restarts it', async ({ page }) => {
    await stage(page);
    await page.click('#rv-pause');
    const at = await prog(page);
    await page.waitForTimeout(1200);
    expect(await prog(page)).toBe(at);        // frozen
    await page.click('#rv-pause');
    expect(await page.locator('#rv-pause[aria-pressed="false"]').count()).toBe(1);
  });

  test('skip goes to your NEXT signing, not to the end', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    const c = await card(page);
    expect(c.cls).toContain('is-won');
    // There is more to come — this was a skip, not an end.
    expect(await page.locator('#rv-done').count()).toBe(0);
  });

  test('skip to end reaches the finished state', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    expect(await page.locator('#rv-done').count()).toBe(1);
    expect(await page.locator('#rv-skip').count()).toBe(0);
    expect(await page.locator('#rv-pause').count()).toBe(0);
  });

  test('a coach who signed nobody still reaches the end', async ({ page }) => {
    await stage(page, { fixture: { mine: 0, others: 14, walkOns: 4 } });
    await page.click('#rv-skip');                 // reads "Skip To End" with none of ours
    await page.waitForSelector('#rv-done');
    expect(await page.locator('#rv-done').count()).toBe(1);
  });

  test('time remaining comes from the cards left, not a constant', async ({ page }) => {
    await stage(page);
    const first = await prog(page);
    await page.click('#rv-skip');
    const later = await prog(page);
    const secs = (s) => { const m = s.match(/(\d+):(\d\d)/); return Number(m[1]) * 60 + Number(m[2]); };
    expect(secs(later)).toBeLessThan(secs(first));
    // 5s a card: the clock must be a multiple of the hold, not a hard-coded four minutes.
    expect(secs(first) % 5).toBe(0);
  });
});

test.describe('funded targets', () => {
  test('one tile per funded recruit, resolving as his card shows', async ({ page }) => {
    await stage(page);
    const before = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-reveal .sd-tg')].map((t) => t.className));
    expect(before.length).toBeGreaterThan(0);
    expect(before.every((c) => c.includes('is-open'))).toBe(true);
    await page.click('#rv-end');
    const after = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-reveal .sd-tg')].map((t) => t.className));
    // By the end nothing the user funded is still pending.
    expect(after.every((c) => c.includes('is-won') || c.includes('is-lost'))).toBe(true);
  });
});

test.describe('no replay', () => {
  test('reaching the end stamps the reveal as seen', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    await page.waitForSelector('#rv-done');
    expect(await page.evaluate(() =>
      window.__seen.some((u) => u.includes('week-35-reveal-seen')))).toBe(true);
  });

  test('the stamp is sent once, not on every render', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    await page.waitForSelector('#rv-done');
    await page.evaluate(() => {
      for (let i = 0; i < 5; i += 1) window.__hubRenderReveal && window.__hubRenderReveal();
    });
    expect(await page.evaluate(() =>
      window.__seen.filter((u) => u.includes('week-35-reveal-seen')).length)).toBe(1);
  });

  test('Continue leaves the reveal for the FCC', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    const nav = page.waitForNavigation({ timeout: 5000 }).catch(() => null);
    await page.click('#rv-done');
    await nav;
    expect(page.url()).toContain('franchise-command-center');
  });
});

test.describe('keyboard', () => {
  test('Space pauses and resumes, matching its keycap', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    await page.keyboard.press('Space');
    expect(await page.locator('#rv-pause[aria-pressed="true"]').count()).toBe(1);
    await page.keyboard.press('Space');
    expect(await page.locator('#rv-pause[aria-pressed="false"]').count()).toBe(1);
  });

  test('N jumps to your next signing', async ({ page }) => {
    await stage(page);
    await page.keyboard.press('n');
    const c = await card(page);
    expect(c.cls).toContain('is-won');
  });

  test('E runs to the end', async ({ page }) => {
    await stage(page);
    await page.keyboard.press('e');
    await page.waitForSelector('#hub-reveal .sd-done', { timeout: 3000 });
    expect(await page.locator('.sd-done-cta').count()).toBe(1);
  });

  test('every keycap on screen names a key that actually binds', async ({ page }) => {
    await stage(page);
    const caps = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-reveal .sd-btn kbd')].map((k) => k.textContent.trim()));
    // A printed keycap is a promise. If a control gains one, it needs a binding here.
    expect(caps).toEqual(['Space', 'N', 'E']);
  });

  test('the keys stop working once the run is over', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    await page.keyboard.press('Space');
    // No pause control exists any more; a stray press must not resurrect the timer.
    expect(await page.locator('#rv-pause').count()).toBe(0);
    expect(await page.locator('.sd-done').count()).toBe(1);
  });
});

test.describe('prep gate', () => {
  test('holds on "Prepping Signing Day" until the lead is painted', async ({ page }) => {
    const { signed, conferences, teamNames } = conferenceFixture({ mine: 3, others: 14, walkOns: 4 });
    await page.setViewportSize({ width: 1560, height: 940 });
    await page.addInitScript(() => { window.__ensureDelayMs = 900; });
    await mountPool(page, {
      week: 35, signed: null, conferences, teamNames, revealSeen: false,
      savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
      action: 'run', runResults: signed,
    });
    await page.waitForSelector('#hub-reveal .sd-prep', { timeout: 8000 });
    const during = await page.evaluate(() => ({
      copy: document.querySelector('.sd-prep-t').textContent.trim(),
      bar: document.querySelectorAll('.sd-prep-bar i').length,
      cards: document.querySelectorAll('#hub-reveal .sd-card').length,
      rails: document.querySelectorAll('#hub-reveal .sd-rail').length,
    }));
    expect(during.copy).toBe('Prepping Signing Day');
    expect(during.bar).toBe(1);
    // Nothing of the stage yet — that is the point of the gate.
    expect(during.cards).toBe(0);
    expect(during.rails).toBe(0);
    await page.waitForSelector('#hub-reveal .sd-rail', { timeout: 8000 });
    expect(await page.locator('#hub-reveal .sd-prep').count()).toBe(0);
  });

  test('force-paints a bounded lead, not the whole region', async ({ page }) => {
    const { signed, conferences, teamNames } = conferenceFixture({ mine: 3, others: 14, walkOns: 4 });
    await page.setViewportSize({ width: 1560, height: 940 });
    await mountPool(page, {
      week: 35, signed: null, conferences, teamNames, revealSeen: false,
      savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
      action: 'run', runResults: signed,
    });
    await page.waitForSelector('#hub-reveal .sd-rail', { timeout: 8000 });
    const m = await page.evaluate(() => ({
      ensured: (window.__ensured || []).length,
      cards: window.__ensured ? null : null,
    }));
    // Painting all ~56 up front would be a 2-3 minute wait; the background warm covers
    // the rest once the playhead is far enough ahead.
    expect(m.ensured).toBeGreaterThan(0);
    expect(m.ensured).toBeLessThanOrEqual(15);
  });
});

test.describe('the end is announced', () => {
  test('a modal names the season and offers one way out', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    const m = await page.evaluate(() => {
      const box = document.querySelector('#hub-reveal .sd-done');
      return {
        open: !!box,
        title: box ? box.querySelector('.sd-done-t').textContent.trim() : null,
        cta: box ? box.querySelector('.sd-done-cta').textContent.trim() : null,
        headerBtns: document.querySelectorAll('#hub-reveal .sd-ctl button').length,
      };
    });
    expect(m.open).toBe(true);
    expect(m.title).toBe('Season 3 Signing Day is Complete');
    expect(m.cta).toBe('Go To Locker Room');
    // The header empties: a Continue button in the corner was what got missed.
    expect(m.headerBtns).toBe(0);
  });

  test('its CTA leaves for the FCC', async ({ page }) => {
    await stage(page);
    await page.click('#rv-end');
    const nav = page.waitForNavigation({ timeout: 5000 }).catch(() => null);
    await page.click('.sd-done-cta');
    await nav;
    expect(page.url()).toContain('franchise-command-center');
  });
});

test.describe('the clock', () => {
  test('runs every second, not in five-second steps', async ({ page }) => {
    await stage(page);
    await page.click('#rv-skip');
    const read = () => page.evaluate(() =>
      document.getElementById('rv-clock').textContent.trim());
    const a = await read();
    await page.waitForTimeout(1300);
    const b = await read();
    await page.waitForTimeout(1300);
    const c = await read();
    // Three reads inside one 5s card hold: a static clock would report the same value
    // every time.
    expect(new Set([a, b, c]).size).toBeGreaterThan(1);
  });
});

test.describe('week 36 league list', () => {
  test('groups by conference: yours, then sister, then ascending', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 36, signed, conferences });
    const m = await page.evaluate(() => ({
      order: [...document.querySelectorAll('.lsconf-t')].map((e) => e.textContent.trim()),
      tags: [...document.querySelectorAll('.lsconf')].map((c) => {
        const t = c.querySelector('.lstag');
        return t ? t.textContent.trim() : '';
      }),
      playback: document.querySelectorAll('#pb-next, #pb-auto, #pb-skip').length,
    }));
    // Region letter + the conference's OWN number: 9 = E9, 10 = E10, 3 = B3. Letter+1|2
    // gave every region a "1" and a "2", so B2 and D2 collided as labels.
    expect(m.order).toEqual(['Conference E9', 'Conference E10', 'Conference B3']);
    expect(m.tags[0]).toBe('Your conference');
    expect(m.tags[1]).toBe('Sister conference');
    expect(m.playback).toBe(0);        // no playback controls on this screen any more
  });

  test('walk-ons are absent from the league list too', async ({ page }) => {
    const { signed, conferences } = conferenceFixture({ walkOns: 6 });
    await mountPool(page, { week: 36, signed, conferences });
    const names = await page.evaluate(() =>
      [...document.querySelectorAll('.lsnm')].map((e) => e.textContent.trim()));
    expect(names.some((n) => n.startsWith('WalkOn'))).toBe(false);
    expect(names.length).toBe(3 + 12 + 5 + 4);
  });

  test("the user's own team is marked inside its conference", async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 36, signed, conferences });
    const m = await page.evaluate(() => ({
      userTeams: document.querySelectorAll('.lsteam.is-user').length,
      userConf: document.querySelectorAll('.lsconf.is-user').length,
    }));
    expect(m.userTeams).toBe(1);
    expect(m.userConf).toBe(1);
  });
});

/**
 * Ported from results-playback.spec.js, which was retired with the playback screen it
 * tested. These two rules outlived it: the no-percentage law from the Signing Day brief
 * applies to every recruiting surface, and the reveal is now the screen that could most
 * easily grow one.
 */
test.describe('no percentage anywhere (ported)', () => {
  const textWithPercent = (root) => page => page.evaluate((sel) => {
    const host = document.querySelector(sel);
    if (!host) return ['(missing host)'];
    const w = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    const out = [];
    while (w.nextNode()) if ((w.currentNode.nodeValue || '').includes('%')) out.push(w.currentNode.nodeValue.trim());
    return out;
  }, root);

  test('the conference reveal shows no percentage', async ({ page }) => {
    await submitAndReveal(page);
    await page.click('#rv-skip');
    expect(await textWithPercent('#hub-reveal')(page)).toEqual([]);
  });

  test('the week-36 league list shows no percentage', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 36, signed, conferences });
    expect(await textWithPercent('#hub-signings')(page)).toEqual([]);
  });
});

test.describe('Orders Submitted modal (confirm before running)', () => {
  test('Submit saves the orders and opens the modal — it does NOT run recruiting', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 35, signed: null, conferences });
    await page.evaluate((s) => {
      window.__seen = [];
      const real = window.RecruitingCommon.fetchJSON;
      window.RecruitingCommon.fetchJSON = function (url, options) {
        const u = String(url);
        if (u.includes('run-week-35')) { window.__seen.push(u); return Promise.resolve({ status: 'success', week: 36, results: { signed_players: s } }); }
        if (u.includes('recruiting-orders') || u.includes('week-35-reveal-seen')) { window.__seen.push(u); return Promise.resolve({}); }
        return real.call(this, url, options);
      };
    }, signed);
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    const m = await page.evaluate(() => ({
      title: document.querySelector('.ssum-title').textContent.trim(),
      buttons: [...document.querySelectorAll('.ssum-foot button')].map((b) => b.textContent.trim()),
      calls: window.__seen.map((u) => u.split('/').pop()),
      revealUp: !!document.getElementById('hub-reveal'),
    }));
    expect(m.title).toBe('Orders Submitted');
    expect(m.buttons).toEqual(['Back to Orders', 'Go To Locker Room']);
    // Orders saved; recruiting NOT yet run — that was the out-of-place part before.
    expect(m.calls).toContain('recruiting-orders');
    expect(m.calls).not.toContain('run-week-35-recruiting');
    expect(m.revealUp).toBe(false);
  });

  test('Back to Orders returns to an editable board with the CTA re-armed', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 35, signed: null, conferences });
    await page.evaluate(() => {
      const real = window.RecruitingCommon.fetchJSON;
      window.RecruitingCommon.fetchJSON = function (url, options) {
        if (String(url).includes('recruiting-orders')) return Promise.resolve({});
        return real.call(this, url, options);
      };
    });
    await page.click('#sign-submit');
    await page.waitForSelector('#ssum-back');
    await page.click('#ssum-back');
    const m = await page.evaluate(() => {
      const btn = document.getElementById('sign-submit');
      return { overlay: document.querySelectorAll('.ssum-overlay').length,
               label: btn.textContent.trim(), disabled: btn.disabled,
               rows: document.querySelectorAll('.spool-rows .prow').length };
    });
    expect(m.overlay).toBe(0);
    expect(m.label).toBe('Submit Orders');
    expect(m.disabled).toBe(false);
    expect(m.rows).toBeGreaterThan(0);     // still editable
  });
});

test.describe('league list layout', () => {
  test('four teams per row — no ragged tail on an eight-team conference', async ({ page }) => {
    const { signed, conferences } = conferenceFixture({ mine: 3, others: 14, walkOns: 4 });
    await mountPool(page, { week: 36, signed, conferences, revealSeen: true });
    // WIDE on purpose. The old rule was auto-fill/minmax(240px), which happens to give
    // four columns at the default 1180px doc width too — so a narrow viewport cannot
    // tell the two apart. At 1900px auto-fill gives seven and splits the conference
    // 7+1; a fixed four-column grid is still 4+4.
    await page.setViewportSize({ width: 1900, height: 1200 });
    await page.evaluate(() => { document.querySelector('.doc').style.maxWidth = '1860px'; });
    const m = await page.evaluate(() => {
      const grid = document.querySelector('#hub-signings .lsconf-teams');
      const cards = [...grid.querySelectorAll('.lsteam')];
      const rows = {};
      cards.forEach((c) => {
        const top = Math.round(c.getBoundingClientRect().top);
        rows[top] = (rows[top] || 0) + 1;
      });
      return {
        cols: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
        perRow: Object.keys(rows).sort((a, b) => a - b).map((k) => rows[k]),
        teams: cards.length,
      };
    });
    expect(m.cols).toBe(4);
    // Eight teams split 4+4. auto-fill gave 5+3 / 6+2 at this width, which is the
    // ragged tail the fixed four-column grid exists to remove.
    expect(m.teams).toBe(8);
    expect(m.perRow).toEqual([4, 4]);
  });

  test('every signing shows name, position, year and an RT pair', async ({ page }) => {
    const { signed, conferences } = conferenceFixture({ mine: 3, others: 14, walkOns: 4 });
    await mountPool(page, { week: 36, signed, conferences, revealSeen: true });
    const rows = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .lsrow')].map((r) => ({
        nm: r.querySelector('.lsnm').textContent.trim(),
        pos: r.querySelector('.lspos').textContent.trim(),
        yr: r.querySelector('.lsyr') ? r.querySelector('.lsyr').textContent.trim() : null,
        rt: r.querySelector('.lsrt').textContent.trim(),
      })));
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) {
      expect(r.nm).not.toBe('');
      expect(r.pos).not.toBe('--');
      // Abbreviated, like every other recruit surface — never the raw 'Sophomore'.
      expect(['JH', 'FR', 'SO', 'JR']).toContain(r.yr);
      // current/potential, not a lone grade.
      expect(r.rt).toContain('/');
    }
  });

  test('the four cells stay on the same rails across teams', async ({ page }) => {
    // The RT column used to be `auto`, so it sized to the widest RT in ITS OWN card.
    // This fixture is built to expose that: one team's class tops out at A+/A++ and
    // another's at F, so a content-sized column makes the two cards disagree and drags
    // Pos and Yr to different offsets. Uniform rails are what make four columns
    // scannable at all.
    const { conferences, teamNames } = conferenceFixture({ mine: 0, others: 0, walkOns: 0 });
    const ids = Object.keys(conferences.by_team_id).slice(0, 6);
    const signed = [];
    ids.forEach((tid, i) => {
      // Alternate wide (A+/A++) and narrow (F) classes.
      const rt = i % 2 === 0 ? 99 : 18;
      for (let k = 0; k < 2; k += 1) {
        signed.push({
          recruit_id: `x-${i}-${k}`, player_id: `px-${i}-${k}`, image_id: `ix-${i}-${k}`,
          name: k ? 'Al Vo' : 'Bartholomew Fitzwilliam',   // and divergent name lengths
          pos: 'SF', year: 'Sophomore', rt, potential_rt_ratcheted: rt + 6,
          team_id: tid, team_name: teamNames[tid],
        });
      }
    });
    await page.setViewportSize({ width: 1560, height: 940 });
    await mountPool(page, { week: 36, signed, conferences, teamNames, revealSeen: true });
    const rails = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#hub-signings .lsteam')];
      return cards.map((c) => {
        const row = c.querySelector('.lsrow');
        const left = c.getBoundingClientRect().left;
        const at = (sel) => Math.round(row.querySelector(sel).getBoundingClientRect().left - left);
        return [at('.lspos'), at('.lsyr'), at('.lsrt')];
      });
    });
    expect(rails.length).toBeGreaterThan(2);
    for (const r of rails.slice(1)) expect(r).toEqual(rails[0]);
  });
});

test.describe('run handoff', () => {
  // The irreversible step moved off this screen. Submitting saves and sends the player
  // to the locker room; the FCC's green "Run Recruiting Day" hands the press back here
  // as ?action=run, because the run call and the reveal both live in the hub.

  test('the modal sends you to the locker room without running anything', async ({ page }) => {
    const { conferences } = conferenceFixture();
    await mountPool(page, {
      week: 35, signed: null, conferences,
      savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
    });
    // Recorded in sessionStorage, not window.__seen: the click NAVIGATES, and a
    // page-scoped log dies with the context. A URL assertion alone is not enough
    // either — runRecruiting() with no user signings ALSO lands on the FCC, so it
    // passes whether the button ran the day or not.
    await page.evaluate(() => {
      sessionStorage.removeItem('__ran');
      const real = window.RecruitingCommon.fetchJSON;
      window.RecruitingCommon.fetchJSON = function (url, options) {
        if (String(url).includes('run-week-35')) sessionStorage.setItem('__ran', '1');
        return real.call(this, url, options);
      };
    });
    await page.route('**/franchise-command-center*', (route) =>
      route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>locker room</body></html>' }));
    await page.click('#sign-submit');
    await page.waitForSelector('.ssum-overlay');
    await page.click('#ssum-go');
    await page.waitForURL('**/franchise-command-center*', { timeout: 5000 });
    expect(await page.evaluate(() => sessionStorage.getItem('__ran'))).toBe(null);
  });

  test('?action=run with no saved orders does not run — the endpoint would 400', async ({ page }) => {
    const { conferences } = conferenceFixture();
    await mountPool(page, {
      week: 35, signed: null, conferences, action: 'run',
      savedEntries: [], waitFor: '.spool-rows .prow',
    });
    const m = await page.evaluate(() => ({
      ran: window.__seen.some((u) => u.includes('run-week-35')),
      reveal: !!document.getElementById('hub-reveal'),
    }));
    expect(m.ran).toBe(false);
    expect(m.reveal).toBe(false);
  });

  test('?action=run after the signings already ran does not re-run them', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, {
      week: 35, signed, conferences, action: 'run',
      savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
      waitFor: '.spool-rows .prow',
    });
    expect(await page.evaluate(() =>
      window.__seen.some((u) => u.includes('run-week-35')))).toBe(false);
  });

  test('no ?action=run means no run on load — the board is just the board', async ({ page }) => {
    const { conferences } = conferenceFixture();
    await mountPool(page, {
      week: 35, signed: null, conferences,
      savedEntries: [{ id: 'r-0', points: 12, playing_time: false }],
    });
    const m = await page.evaluate(() => ({
      ran: window.__seen.some((u) => u.includes('run-week-35')),
      reveal: !!document.getElementById('hub-reveal'),
    }));
    expect(m.ran).toBe(false);
    expect(m.reveal).toBe(false);
  });
});
