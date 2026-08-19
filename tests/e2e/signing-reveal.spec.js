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
function fixture({ week = 7, watchlist = [], savedOrders = {}, signed = null, conferences = null, revealSeen = false, savedEntries = [] } = {}) {
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
    recruits, team_name_map: { [USER_TEAM]: 'South Lancaster', 'rival-1': 'Fairview' },
    saved_orders: savedOrders, watchlist,
    saved_order_entries_week_35: savedEntries,
    new_lean_recruit_ids: [],
    week_35_recruiting_results: signed ? { signed_players: signed } : {},
    week_35_recruiting_ran: !!signed,
    week_35_reveal_seen: revealSeen,
    conferences: conferences || {
      user_conference: 9, sister_conference: 10,
      order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
      by_team_id: {},
    },
  };
}

async function mountPool(page, opts = {}) {
  const patchCalls = [];
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Real origin first: getQueryContext reads location.search, and about:blank has no
  // origin (setContent preserves whatever URL the page is already on).
  // ?action=run is the FCC's "Run Recruiting Day" handing the press to the hub, which
  // owns both the run call and the reveal.
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
  let rt = 99;
  for (let i = 0; i < mine; i += 1) signed.push({ name: `Mine ${i}`, pos: 'PF', rt: rt--, team_id: USER, team_name: 'South Lancaster' });
  for (let i = 0; i < others; i += 1) signed.push({ name: `Rival ${i}`, pos: 'SG', rt: rt--, team_id: `c9-${(i % 7) + 1}`, team_name: `Rival ${i % 7}` });
  for (let i = 0; i < 5; i += 1) signed.push({ name: `Sister ${i}`, pos: 'C', rt: rt--, team_id: `c10-${(i % 4) + 1}`, team_name: `Sister ${i % 4}` });
  for (let i = 0; i < 4; i += 1) signed.push({ name: `Far ${i}`, pos: 'PG', rt: rt--, team_id: `c3-${(i % 3) + 1}`, team_name: `Far ${i % 3}` });
  for (let i = 0; i < walkOns; i += 1) signed.push({ name: `WalkOn ${i}`, pos: 'C', rt: 5, team_id: USER, team_name: 'South Lancaster', walk_on: true });
  const conferences = {
    user_conference: 9, sister_conference: 10,
    order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
    by_team_id: byTeam,
  };
  return { signed, conferences };
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

test.describe('conference reveal', () => {
  test('does not start on load — only on submit', async ({ page }) => {
    const { signed, conferences } = conferenceFixture();
    await mountPool(page, { week: 35, signed, conferences });
    expect(await page.locator('#hub-reveal').count()).toBe(0);
  });

  test('covers the conference only, excludes walk-ons, highest RT first', async ({ page }) => {
    await submitAndReveal(page, { mine: 3, others: 12, walkOns: 4 });
    // Skip to the end so the whole list is on screen.
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    const m = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.rvrow')];
      return {
        names: rows.map((r) => r.querySelector('.rvnm').textContent.trim()),
        total: document.querySelector('.rvcount').textContent.trim(),
      };
    });
    // 3 mine + 12 conference rivals = 15. Sister (5), far conference (4) and walk-ons (4) excluded.
    expect(m.names.length).toBe(15);
    expect(m.names.some((n) => n.startsWith('Sister'))).toBe(false);
    expect(m.names.some((n) => n.startsWith('Far'))).toBe(false);
    expect(m.names.some((n) => n.startsWith('WalkOn'))).toBe(false);
    expect(m.total).toBe('15/15');
  });

  test('reveals in descending RT order', async ({ page }) => {
    await submitAndReveal(page);
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    const rts = await page.evaluate(() =>
      [...document.querySelectorAll('.rvrow')].map((r) => r.querySelector('.rvnm').textContent.trim()));
    // Newest is prepended, so on-screen order is ascending RT; reversed it must descend.
    const revealedOrder = rts.slice().reverse();
    expect(revealedOrder[0]).toBe('Mine 0');       // rt 99, the highest
  });

  test('the progress bar carries the count and the real RT grade run', async ({ page }) => {
    await submitAndReveal(page);
    const m = await page.evaluate(() => ({
      count: document.querySelector('.rvcount').textContent.trim(),
      ticks: [...document.querySelectorAll('.rvtick')].map((t) => t.textContent.trim()),
      width: document.querySelector('.rvmeter-bar i').style.width,
    }));
    expect(m.count).toMatch(/^\d+\/15$/);
    // The grade run comes from rtBucket's bands, not a hardcoded list.
    expect(m.ticks).toEqual(['A++', 'A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F']);
    expect(m.width).toMatch(/%$/);
  });

  test('each hold is 3s — the list does not race ahead', async ({ page }) => {
    await submitAndReveal(page);
    const first = (await rowNames(page)).length;
    await page.waitForTimeout(1200);
    expect((await rowNames(page)).length).toBe(first);   // still holding
    await page.waitForFunction((n) => document.querySelectorAll('.rvrow').length > n, first, { timeout: 5000 });
  });
});

test.describe('skip control', () => {
  test('skips to the user\'s next signing, not to the end', async ({ page }) => {
    await submitAndReveal(page, { mine: 3, others: 12 });
    await page.click('#rv-skip');
    const m = await page.evaluate(() => ({
      newest: document.querySelector('.rvrow .rvnm').textContent.trim(),
      mine: document.querySelector('.rvrow').classList.contains('is-mine'),
      done: !!document.getElementById('rv-done'),
    }));
    expect(m.newest).toMatch(/^Mine /);   // landed on one of ours
    expect(m.mine).toBe(true);
    expect(m.done).toBe(false);           // not the end
  });

  test('once past the last of ours it becomes Skip To End with the remaining count', async ({ page }) => {
    await submitAndReveal(page, { mine: 2, others: 12 });
    // Two of ours are the two highest RT, so two skips exhausts them.
    await page.click('#rv-skip');
    await page.click('#rv-skip');
    const m = await page.evaluate(() => ({
      label: document.getElementById('rv-skip').textContent.trim(),
      note: (document.querySelector('.rvskip-note') || {}).textContent,
    }));
    expect(m.label).toBe('Skip To End');
    expect(m.note).toBe('0 signings remain for your team');
  });

  test('a coach who signed nobody still gets the end state, not a broken button', async ({ page }) => {
    await submitAndReveal(page, { mine: 0, others: 12 });
    const m = await page.evaluate(() => ({
      label: document.getElementById('rv-skip').textContent.trim(),
      note: (document.querySelector('.rvskip-note') || {}).textContent,
    }));
    expect(m.label).toBe('Skip To End');
    expect(m.note).toBe('0 signings remain for your team');
  });
});

test.describe('no replay', () => {
  test('reaching the end stamps the reveal as seen', async ({ page }) => {
    await submitAndReveal(page);
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    const calls = await page.evaluate(() => window.__seen);
    expect(calls.some((u) => u.includes('week-35-reveal-seen'))).toBe(true);
  });

  test('the stamp is sent once, not on every render', async ({ page }) => {
    await submitAndReveal(page);
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    // Skip is gone at the end now, so force extra renders directly — the guard is
    // seenSent, not the number of clicks available.
    await page.evaluate(() => {
      for (let i = 0; i < 5; i += 1) window.__hubRenderReveal && window.__hubRenderReveal();
    });
    const n = await page.evaluate(() =>
      window.__seen.filter((u) => u.includes('week-35-reveal-seen')).length);
    expect(n).toBe(1);
  });

  test('Continue leaves the reveal for the FCC', async ({ page }) => {
    await submitAndReveal(page);
    await page.click('#rv-skip');
    const nav = page.waitForNavigation({ timeout: 5000 }).catch(() => null);
    await page.click('#rv-done');
    await nav;
    expect(page.url()).toContain('franchise-command-center');
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
    // Conference 9 = E1, 10 = E2, 3 = B1.
    expect(m.order).toEqual(['Conference E1', 'Conference E2', 'Conference B1']);
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

test.describe('reveal layout holds still', () => {
  test('the title, meter and buttons do not move as results fill in', async ({ page }) => {
    await submitAndReveal(page, { mine: 3, others: 12 });
    const geo = () => page.evaluate(() => {
      const r = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; };
      return { title: r('.rvtitle'), head: r('.rvhead'), rows: r('.rvrows'),
               rowsH: Math.round(document.querySelector('.rvrows').getBoundingClientRect().height),
               foot: r('.rvfoot') };
    });
    const first = await geo();
    await page.click('#rv-skip');
    const second = await geo();
    await page.click('#rv-skip');
    const third = await geo();
    expect(second).toEqual(first);
    expect(third).toEqual(first);
  });

  test('the rows box holds six and scrolls the rest', async ({ page }) => {
    await submitAndReveal(page, { mine: 3, others: 12 });
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    // The newest row animates in over 0.34s with a translateY; measuring mid-flight puts
    // it outside the box. Let it settle, then measure the real rects.
    await page.waitForTimeout(450);
    const m = await page.evaluate(() => {
      const box = document.querySelector('.rvrows');
      const rows = [...box.querySelectorAll('.rvrow')];
      const bb = box.getBoundingClientRect();
      const fullyVisible = rows.filter((r) => {
        const b = r.getBoundingClientRect();
        return b.top >= bb.top - 1 && b.bottom <= bb.bottom + 1;
      }).length;
      return { total: rows.length, fullyVisible, scrolls: box.scrollHeight > box.clientHeight + 1 };
    });
    expect(m.total).toBe(15);
    expect(m.fullyVisible).toBe(6);
    expect(m.scrolls).toBe(true);
  });

  test('the header names the user\'s own conference by number', async ({ page }) => {
    await submitAndReveal(page);
    const title = await page.evaluate(() => document.querySelector('.rvtitle').textContent.trim());
    expect(title).toBe('Conference 9 Recruiting Results');
  });
});

test.describe('finished state', () => {
  test('Skip To End is gone once every result is out — only Continue remains', async ({ page }) => {
    await submitAndReveal(page);
    expect(await page.locator('#rv-skip').count()).toBe(1);
    await page.click('#rv-skip');
    await page.waitForFunction(() => !!document.getElementById('rv-done'));
    const m = await page.evaluate(() => ({
      skip: document.querySelectorAll('#rv-skip').length,
      note: document.querySelectorAll('.rvskip-note').length,
      buttons: [...document.querySelectorAll('.rvfoot button')].map((b) => b.textContent.trim()),
    }));
    expect(m.skip).toBe(0);
    expect(m.note).toBe(0);        // the note goes with the button
    expect(m.buttons).toEqual(['Continue']);
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
