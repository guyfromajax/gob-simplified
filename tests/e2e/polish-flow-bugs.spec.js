// @ts-check
/**
 * polish/flow-bugs (2026-10-02)
 *
 * A1  Returning to the FCC after a game showed the old week until a manual refresh.
 *     Leaving a flow is a history traversal. On that kind of load Chrome answers a
 *     plain GET from its HTTP cache without revalidating, and the week-completion
 *     writes have just cleared GOBStore's validator, so the season read came back
 *     as the pre-game body and never reached the server. The store now reads with
 *     cache: 'no-store'.
 * A2  Championship announcements replayed on every Office visit: the consume was
 *     skipped because the real command-center payload carries no franchise_id.
 *     Another team's title is quiet: no sting, no confetti.
 * A3  recruiting.html painted the default Pool / Leans / Visits row for a beat
 *     before the hub knew its week.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const STATIC = path.join(__dirname, '../../FrontEnd/static');
const SHOTS = path.join(__dirname, '../../reports/polish-flow-bugs');
// FLOW_SHOT_TAG=before names the shots when the spec is run against the old code.
const TAG = process.env.FLOW_SHOT_TAG || 'after';
const FID = 'f-e2e-flow-bugs';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

/* ------------------------------------------------------------------ A1 --- */

/**
 * A real HTTP server, because Playwright's request routing turns the browser's
 * HTTP cache off (which is why the mocked fcc-fresh-after-game spec never saw
 * this). It serves the real gobStore.js and a season read with the same headers
 * as @browse_cached: ETag + "Cache-Control: private, no-cache".
 */
function startSeasonServer() {
  const state = { week: 5, rev: 1, seasonReads: 0 };
  const CC = '/franchise/command-center/data';
  const page = (title, body) => '<!doctype html><meta charset="utf-8"><title>' + title + '</title>'
    + '<script src="/js/shared/gobStore.js"></script><body>' + body + '</body>';
  const readWeek = 'fetch("' + CC + '?franchise_id=F1").then(function (r) { return r.json(); })'
    + '.then(function (d) { document.getElementById("week").textContent = "Week " + d.week; });';
  const server = http.createServer((req, res) => {
    const url = new URL(req.url || '/', 'http://localhost');
    if (url.pathname === '/js/shared/gobStore.js') {
      res.writeHead(200, { 'Content-Type': 'text/javascript', 'Cache-Control': 'no-store' });
      res.end(fs.readFileSync(path.join(STATIC, 'js/shared/gobStore.js')));
      return;
    }
    if (url.pathname === '/office.html') {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      // The Office reads the season, like franchise-command-center.js does.
      res.end(page('office', '<h1 id="week">…</h1><a id="play" href="/court.html">Play Next Game</a><script>' + readWeek + '</script>'));
      return;
    }
    if (url.pathname === '/court.html') {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      // The court reads the season at boot, then the game ends: the week-completion
      // write (which clears the store) and the exit back onto the Office entry.
      res.end(page('court', '<h1 id="week">…</h1><button id="finish">Go To Locker Room</button><script>' + readWeek
        + 'document.getElementById("finish").addEventListener("click", function () {'
        + '  fetch("/franchise/complete-week/phase-b", { method: "POST", headers: { "Content-Type": "application/json" },'
        + '    body: JSON.stringify({ franchise_id: "F1" }) }).then(function () { history.go(-1); });'
        + '});</script>'));
      return;
    }
    if (url.pathname === CC && req.method === 'GET') {
      state.seasonReads += 1;
      const etag = 'W/"F1:1:' + state.week + ':' + state.rev + ':build:' + CC + '?franchise_id=F1"';
      const headers = { ETag: etag, 'Cache-Control': 'private, no-cache', 'Content-Type': 'application/json' };
      if (req.headers['if-none-match'] === etag) { res.writeHead(304, headers); res.end(); return; }
      res.writeHead(200, headers);
      res.end(JSON.stringify({ week: state.week }));
      return;
    }
    if (url.pathname === '/franchise/complete-week/phase-b' && req.method === 'POST') {
      state.week += 1;
      state.rev += 1;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok' }));
      return;
    }
    res.writeHead(404); res.end();
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const address = /** @type {import('net').AddressInfo} */ (server.address());
      resolve({ server, state, origin: 'http://127.0.0.1:' + address.port });
    });
  });
}

test('A1: the season read after a game reaches the server, not the HTTP cache', async ({ page }) => {
  const { server, state, origin } = await startSeasonServer();
  try {
    await page.goto(origin + '/office.html');
    await expect(page.locator('#week')).toHaveText('Week 5');

    await page.locator('#play').click();
    await expect(page).toHaveURL(/court\.html/);
    await expect(page.locator('#week')).toHaveText('Week 5');
    const readsBeforeReturn = state.seasonReads;

    // The game ends: the week advances on the server, then the exit goes back
    // onto the Office's history entry (GOBNav.exitFlow -> history.go).
    await page.locator('#finish').click();
    await expect(page).toHaveURL(/office\.html/);
    expect(await page.evaluate(() => {
      const nav = /** @type {PerformanceNavigationTiming} */ (performance.getEntriesByType('navigation')[0]);
      return nav.type;
    })).toBe('back_forward');

    // No refresh: the Office shows the advanced week, and it asked the server.
    await expect(page.locator('#week')).toHaveText('Week 6');
    expect(state.seasonReads).toBe(readsBeforeReturn + 1);
  } finally {
    server.close();
  }
});

/* ---------------------------------------------------------- shared mocks --- */

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

function isApi(pathname) {
  return pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
    || pathname.startsWith('/player/') || pathname.startsWith('/recruit/') || pathname === '/teams'
    || pathname === '/app-config';
}

/* ------------------------------------------------------------------ A2 --- */

function champItem(quiet) {
  return {
    id: 'championship', kind: 'championship', tier: 'SEASON_PEAK',
    priority: 10, payload_ref: 'pending_championship_moments',
    seen_key: 'pending_championship_moments', title: 'Championship moment',
    line: 'A title moment is waiting.', duration: 'long',
    style: quiet ? 'quiet' : 'gold', sting: quiet ? null : 'STING_SEASON_PEAK',
  };
}

function digest() {
  return {
    state: 'regular',
    what_moved: { national_rank: { now: 4, prev: 4, delta: 0 }, conference_standing: { now: 2, prev: 2, delta: 0 },
      record: { wins: 20, losses: 6 }, streak: 'W2', attribute_changes: [] },
    team_snapshot: { state: 'ready', chemistry: { value: 20, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: null, next_game: null,
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [], recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 },
    signing_day: null, season_preview: null, weekly_card_items: [],
  };
}

/**
 * The command-center payload in the shape the server really sends it: there is
 * NO franchise_id key. The earlier spec's mock added one, which hid the bug.
 */
function commandCenter(state) {
  const pending = (state.pending || []).slice();
  const userWon = pending.some((m) => m.user_is_winner);
  const moments = pending.length ? [champItem(!userWon)] : [];
  if (state.elimination) {
    moments.push({ id: 'elimination', kind: 'elimination', tier: 'MILESTONE', priority: 20, payload_ref: 'elimination',
      seen_key: 'elimination_seen_season', title: 'Season over', line: 'Your season ended in the Region Final.',
      style: 'quiet', sting: null, duration: 'short' });
  }
  return {
    team_id: TID, user_team_object_id: TID, team: 'Lancaster',
    week: state.week || 30, current_season: state.season || 3,
    training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 0, counts: {} },
    office_digest: digest(),
    pending_championship_moments: pending,
    elimination: state.elimination ? { eligible: true, round_name: 'Region Final', season: 3 } : null,
    moments, moments_for_this_visit: moments.slice(0, 1), weekly_card_items: [],
    team_name_map: { [TID]: 'Lancaster', [OPP]: 'Four Corners' },
  };
}

function title(type, overrides) {
  return Object.assign({
    id: 'cm-' + type, type, season: 3, conference: 2, region: 'A',
    winner_team_id: OPP, winner_team_name: 'Four Corners', winner_primary_color: '#8E2727',
    loser_team_id: TID, loser_team_name: 'Lancaster',
    score: { winner: 78, loser: 71 }, game_id: null, user_is_winner: false,
  }, overrides || {});
}

async function installOfficeApi(page, state, writes) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { await route.continue(); return; }
    if (!isApi(pathname)) { await route.continue(); return; }
    if (request.method() !== 'GET') {
      let body = {};
      try { body = JSON.parse(request.postData() || '{}'); } catch (err) { body = {}; }
      writes.push({ path: pathname, method: request.method(), body });
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com', archetype_reveal_seen: true });
      return;
    }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, commandCenter(state)); return; }
    if (pathname === '/franchise/championship-moments/dismiss') {
      const body = writes[writes.length - 1].body;
      // The real route 422s without a franchise id; only a full request consumes.
      if (body.franchise_id === FID && body.moment_id) {
        state.pending = (state.pending || []).filter((m) => m.id !== body.moment_id);
      }
      await fulfillJson(route, { status: 'ok', removed: true });
      return;
    }
    if (pathname === '/franchise/elimination-seen') {
      if (writes[writes.length - 1].body.franchise_id === FID) state.elimination = false;
      await fulfillJson(route, { ok: true });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openOffice(page) {
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none') && root && root.getAttribute('aria-busy') === 'false';
  });
}

function dismisses(writes) {
  return writes.filter((w) => w.path === '/franchise/championship-moments/dismiss');
}

async function prepareOffice(page, state, writes) {
  await stubAuth(page);
  await page.addInitScript(() => { window.__gobSfxCalls = []; });
  await installOfficeApi(page, state, writes);
  await page.setViewportSize({ width: 1280, height: 720 });
}

test.describe('A2: championship announcements', () => {
  for (const type of ['conference_championship', 'region_championship', 'national_championship']) {
    test(type + ' is announced once, then never again (reload, next visit, next season)', async ({ page }) => {
      const writes = [];
      const state = { pending: [title(type)], week: 30, season: 3 };
      await prepareOffice(page, state, writes);

      await openOffice(page);
      await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
      // Consumed as it is shown, with the franchise id the payload does not carry.
      await expect.poll(() => dismisses(writes).length).toBe(1);
      expect(dismisses(writes)[0].body).toEqual({ franchise_id: FID, moment_id: 'cm-' + type });

      // Reload mid-announcement: it does not come back.
      await page.reload();
      await page.waitForFunction(() => {
        const root = document.getElementById('office-root');
        return root && root.getAttribute('aria-busy') === 'false';
      });
      await page.waitForTimeout(1200);
      await expect(page.locator('.pk.is-open')).toHaveCount(0);

      // A later return to the Office, and the first week of the next season.
      state.week = 31;
      await openOffice(page);
      await page.waitForTimeout(1200);
      await expect(page.locator('.pk.is-open')).toHaveCount(0);
      state.season = 4; state.week = 1;
      await openOffice(page);
      await page.waitForTimeout(1200);
      await expect(page.locator('.pk.is-open')).toHaveCount(0);
      expect(dismisses(writes).length).toBe(1);
    });
  }

  test('another team\'s title: no sting, no confetti, nothing for the Trophy Case', async ({ page }) => {
    const writes = [];
    const state = { pending: [title('conference_championship')] };
    await prepareOffice(page, state, writes);
    await openOffice(page);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1600);
    await page.screenshot({ path: path.join(SHOTS, 'a2-' + TAG + '-rival-title-1280.png') });
    await expect(pk).toHaveClass(/is-quiet/);
    await expect(pk.locator('.pk-team')).toHaveText('Four Corners');
    await expect(pk.locator('.cf')).toHaveCount(0);
    await expect(pk.locator('.pk-f')).not.toContainText('Trophy Case');
    // Well past the 600ms sting delay: nothing was played.
    const sounds = await page.evaluate(() => ({
      peak: window.__gobSeasonPeakSfx || [],
      stings: (window.__gobSfxCalls || []).filter((c) => /STING/.test(String(c && (c.name || c[0] || c)))),
    }));
    expect(sounds.peak).toEqual([]);
    expect(sounds.stings).toEqual([]);
  });

  test('the coach\'s own title still celebrates: sting and confetti', async ({ page }) => {
    const writes = [];
    const state = { pending: [title('conference_championship', {
      winner_team_id: TID, winner_team_name: 'Lancaster', winner_primary_color: '#27408E',
      loser_team_id: OPP, loser_team_name: 'Four Corners', user_is_winner: true,
    })] };
    await prepareOffice(page, state, writes);
    await openOffice(page);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect(pk).not.toHaveClass(/is-quiet/);
    await expect(pk.locator('.cf i').first()).toBeAttached();
    await expect(pk.locator('.pk-f')).toContainText('Trophy Case');
    await expect.poll(() => page.evaluate(() => window.__gobSeasonPeakSfx || [])).toEqual(['STING_SEASON_PEAK']);
    await page.screenshot({ path: path.join(SHOTS, 'a2-' + TAG + '-own-title-1280.png') });
  });

  test('a milestone is marked seen with the franchise id from the page context', async ({ page }) => {
    const writes = [];
    const state = { pending: [], elimination: true };
    await prepareOffice(page, state, writes);
    await openOffice(page);
    await expect(page.locator('.mm-scrim.is-open')).toBeVisible({ timeout: 15000 });
    await expect.poll(() => writes.filter((w) => w.path === '/franchise/elimination-seen').length).toBe(1);
    expect(writes.filter((w) => w.path === '/franchise/elimination-seen')[0].body.franchise_id).toBe(FID);
    await openOffice(page);
    await page.waitForTimeout(1200);
    await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  });
});

/* ------------------------------------------------------------------ A3 --- */

const HUB_DELAY_MS = 900;

function recruitingData(week) {
  return {
    week, team_id: TID, team: 'Lancaster', team_region: 'A', season: 3,
    recruits: [], team_name_map: { [TID]: 'Lancaster' }, recruiting_wire: {},
    roster_capacity: {}, competition_counts: {}, lean_multipliers: {}, watchlist: [],
    saved_orders: {}, visit_history: [], invite_seed_modal_seen: true, week_35_reveal_seen: true,
    week_35_recruiting_ran: week >= 36, week_35_recruiting_results: {},
  };
}

async function installRecruitingApi(page, week) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { await route.continue(); return; }
    if (!isApi(pathname)) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]); return; }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      // The beat Jamie saw: the page is up, the hub's data is still on its way.
      await new Promise((r) => setTimeout(r, HUB_DELAY_MS));
      await fulfillJson(route, recruitingData(week));
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, { team_id: TID, user_team_object_id: TID, team: 'Lancaster', week, current_season: 3,
        training_completed: true, session_type: 'in-season', cut_required: false,
        recruiting_wire: { board_saved_week: week, week_35_orders_submitted: true }, team_record: { wins: 3, losses: 1 }, rank: 12 });
      return;
    }
    await fulfillJson(route, {});
  });
}

/** Every animation frame: is a Pool / Leans / Visits control on screen, and is the hub? */
async function installRowSampler(page) {
  await page.addInitScript(() => {
    if (!/recruiting\.html$/.test(location.pathname)) return;
    const frames = [];
    window.__rowFrames = frames;
    const shown = (el) => {
      if (!el) return false;
      const box = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return box.width > 0 && box.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    };
    const tick = () => {
      const row = document.getElementById('gob-subtabs');
      const tabs = row ? Array.from(row.querySelectorAll('button, a, [role="tab"]'))
        .filter((el) => shown(el) && /^(Pool|Leans|Visits)$/.test((el.textContent || '').trim())).length : 0;
      const search = Array.from(document.querySelectorAll('.gob-search')).filter(shown).length;
      const hub = shown(document.getElementById('hub-phase'));
      frames.push({ tabs, search, hub });
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

test.describe('A3: the recruiting page never paints the default row before the hub', () => {
  for (const week of [5, 22, 35]) {
    test('week ' + week, async ({ page }) => {
      await stubAuth(page);
      await installRecruitingApi(page, week);
      await installRowSampler(page);
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc');

      // While the hub's data is on its way: the title and a still skeleton, no row.
      await expect(page.locator('.pg-head h1')).toHaveText('Recruiting');
      await page.waitForTimeout(350);
      await page.screenshot({ path: path.join(SHOTS, 'a3-' + TAG + '-loading-week' + week + '-1280.png') });
      await expect(page.locator('.hub-skel')).toBeVisible();
      await expect(page.locator('#gob-subtabs')).toBeHidden();

      await expect(page.locator('#hub-phase')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('.hub-skel')).toHaveCount(0);
      await page.waitForTimeout(300);

      const frames = await page.evaluate(() => window.__rowFrames);
      expect(frames.length).toBeGreaterThan(10);
      const early = frames.filter((f) => !f.hub && (f.tabs > 0 || f.search > 0));
      expect(early, 'frames with the row painted before the hub').toEqual([]);

      const tabs = page.locator('#gob-subtabs').getByText(/^(Pool|Leans|Visits)$/);
      if (week === 5) {
        // Tab weeks: the row arrives with the hub, in the same paint.
        await expect(tabs).toHaveCount(3);
        expect(frames.some((f) => f.hub && f.tabs === 3)).toBe(true);
        await page.screenshot({ path: path.join(SHOTS, 'a3-' + TAG + '-hub-1280.png') });
      } else {
        // Invite weeks and Signing Day have no Pool / Leans / Visits row at all.
        await expect(tabs).toHaveCount(0);
        expect(frames.every((f) => f.tabs === 0)).toBe(true);
      }
    });
  }
});
