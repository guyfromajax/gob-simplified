// @ts-check
/**
 * Chrome follow-ups 2 (polish/chrome-followups-2, 2026-10-02).
 *
 * G1 offline: the "Coaching archetype evolved" weekly row is cleared on this computer, so it shows once
 * G2 finish labels are one case (capitalised) wherever they sit together; nothing truncates
 * G3 the court's Play Stats table reads "Half-Court Traps" on one line
 * G5 the Office conference standings card always shows every team, at normal row spacing
 *
 * FOLLOWUP2_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/chrome-followups-2');
const TAG = process.env.FOLLOWUP2_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];
const shot = (page, name, width, opts) => page.screenshot(Object.assign(
  { path: path.join(SHOTS, name + '-' + TAG + '-' + width + '.png') }, opts || {}));

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));
const FID = O.FID;

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

function apiPath(route) {
  let pathname = '';
  try { pathname = new URL(route.request().url()).pathname; } catch (err) { return null; }
  const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
    || pathname === '/teams' || pathname === '/app-config';
  return api ? pathname : null;
}

/* ------------------------------------------------------------------ G1 --- */

const EVOLUTION_ROW = {
  id: 'archetype_evolution', kind: 'archetype_evolution', tier: 'WEEKLY', priority: 100,
  payload_ref: 'archetype_evolution_pending', seen_key: 'archetype_evolution_pending',
  title: 'Coaching archetype', line: 'Your coaching archetype evolved.',
};

function evolutionVisit(state) {
  const data = clone(O.STATES.loss);
  delete data.franchise_id; // the real payload has no franchise_id
  const row = clone(EVOLUTION_ROW);
  // The coaching-archetypes page is online only, so the offline row has no link.
  if (!state.desktop) row.href = '/coaching-archetypes.html';
  const items = state.pending ? [row] : [];
  data.lead_archetype = 'defensive_rebounding';
  data.archetype_reveal_seen = true;
  data.archetype_evolution_pending = state.pending ? 'defensive_rebounding' : '';
  data.moments = items;
  data.moments_for_this_visit = [];
  data.weekly_card_items = items;
  data.office_digest.weekly_card_items = items;
  data.office_digest.also = state.pending
    ? { kind: row.kind, title: row.title, line: row.line, href: row.href || null }
    : null;
  return data;
}

async function installEvolutionApi(page, state, writes) {
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    const request = route.request();
    if (request.method() !== 'GET') {
      let body = {};
      try { body = JSON.parse(request.postData() || '{}'); } catch (err) { body = {}; }
      writes.push({ path: pathname, method: request.method(), body });
    }
    if (pathname.startsWith('/api/auth/') && state.desktop) { await route.abort(); return; } // always remote
    if (pathname === '/franchise/archetype-evolution-seen') {
      if (writes[writes.length - 1].body.franchise_id === FID) state.pending = false;
      await fulfillJson(route, { archetype_evolution_pending: '' });
      return;
    }
    if (pathname === '/api/auth/archetype-evolution-seen') {
      state.pending = false;
      await fulfillJson(route, { archetype_evolution_pending: '', message: 'Archetype evolution cleared' });
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', lead_archetype: 'defensive_rebounding',
        archetype_reveal_seen: true, archetype_evolution_pending: state.pending ? 'defensive_rebounding' : '' });
      return;
    }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: O.TID, _id: O.TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) {
      // As the server does: one ETag per browse revision. An account write does not move
      // it, so a client that still holds the cached body gets a 304 of the stale one.
      const etag = 'W/"' + FID + ':1:22:' + (state.rev || 0) + ':e2e:cc"';
      if (state.etags && request.headers()['if-none-match'] === etag) {
        await route.fulfill({ status: 304, headers: { ETag: etag } });
        return;
      }
      const headers = state.etags ? { ETag: etag, 'Cache-Control': 'private, no-cache', 'Access-Control-Expose-Headers': 'ETag' } : {};
      await route.fulfill({ status: 200, contentType: 'application/json', headers, body: JSON.stringify(evolutionVisit(state)) });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, tab) {
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + O.TID + (tab ? '&tab=' + tab : ''));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none') && root && root.getAttribute('aria-busy') === 'false';
  });
}

const writesTo = (writes, pathname) => writes.filter((w) => w.path === pathname);
const evolutionRow = (page) => page.locator('#office-root .wkc-also').filter({ hasText: 'Coaching archetype' });

for (const [width, height] of SIZES) {
  test('G1: offline, the "Coaching archetype" weekly row is cleared locally and shows once (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    const writes = [];
    const state = { pending: true, desktop: true };
    await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
    await stubAuth(page);
    await installEvolutionApi(page, state, writes);

    await openFcc(page);
    await expect(evolutionRow(page)).toBeVisible({ timeout: 15000 });
    await shot(page, 'g1-evolution-row-first-visit', width);
    // Cleared on this computer once the Office has shown it, with the franchise the Office is on.
    await expect.poll(() => writesTo(writes, '/franchise/archetype-evolution-seen').length).toBe(1);
    expect(writesTo(writes, '/franchise/archetype-evolution-seen')[0]).toMatchObject({ method: 'PATCH', body: { franchise_id: FID } });
    expect(writes.filter((w) => w.path.startsWith('/api/auth/'))).toHaveLength(0);
    // The row stays for the visit it was shown on.
    await expect(evolutionRow(page)).toBeVisible();

    // Every later Office visit: no row, and no second write.
    for (let visit = 0; visit < 2; visit += 1) {
      await openFcc(page);
      await page.waitForTimeout(800);
      await expect(evolutionRow(page)).toHaveCount(0);
    }
    await shot(page, 'g1-evolution-row-next-visit', width);
    expect(writesTo(writes, '/franchise/archetype-evolution-seen')).toHaveLength(1);
  });
}

test('G1: offline, a visit that does not show the Office leaves the row for the next one', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const writes = [];
  const state = { pending: true, desktop: true };
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await installEvolutionApi(page, state, writes);
  await openFcc(page, 'team-view');
  await expect(page.locator('#office-root')).toBeHidden();
  await page.waitForTimeout(1500);
  expect(writesTo(writes, '/franchise/archetype-evolution-seen')).toHaveLength(0);
  // The Office, next: the row is there, and now it is cleared.
  await openFcc(page, 'home-tab');
  await expect(evolutionRow(page)).toBeVisible({ timeout: 15000 });
  await expect.poll(() => writesTo(writes, '/franchise/archetype-evolution-seen').length).toBe(1);
});

test('G1: online, the row is marked seen through the account route and is gone on the next visit', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const writes = [];
  const reads = [];
  const state = { pending: true, desktop: false, etags: true };
  await stubAuth(page);
  await installEvolutionApi(page, state, writes);
  page.on('request', (request) => {
    if (request.url().includes('/franchise/command-center/data')) reads.push(request.headers()['if-none-match'] || '');
  });
  await openFcc(page);
  await expect(evolutionRow(page)).toBeVisible({ timeout: 15000 });
  await expect.poll(() => writesTo(writes, '/api/auth/archetype-evolution-seen').length).toBe(1);
  expect(writesTo(writes, '/api/auth/archetype-evolution-seen')[0].method).toBe('PATCH');
  expect(writesTo(writes, '/franchise/archetype-evolution-seen')).toHaveLength(0);
  await expect(evolutionRow(page)).toBeVisible();

  for (let visit = 0; visit < 2; visit += 1) {
    await openFcc(page);
    await page.waitForTimeout(800);
    await expect(evolutionRow(page)).toHaveCount(0);
  }
  expect(writesTo(writes, '/api/auth/archetype-evolution-seen')).toHaveLength(1);
  // The account write does not change the Office's ETag, so the cached body must be dropped:
  // the visit after the write asks for a full body, not a revalidation of the stale one.
  expect(reads[1]).toBe('');
});

test('G1: online, a visit that does not show the Office leaves the row for the next one', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const writes = [];
  const state = { pending: true, desktop: false };
  await stubAuth(page);
  await installEvolutionApi(page, state, writes);
  await openFcc(page, 'team-view');
  await expect(page.locator('#office-root')).toBeHidden();
  await page.waitForTimeout(1500);
  expect(writesTo(writes, '/api/auth/archetype-evolution-seen')).toHaveLength(0);
  await openFcc(page, 'home-tab');
  await expect(evolutionRow(page)).toBeVisible({ timeout: 15000 });
  await expect.poll(() => writesTo(writes, '/api/auth/archetype-evolution-seen').length).toBe(1);
});

/* ------------------------------------------------------------------ G2 --- */

const TITLE_LABELS = ['National Champions', 'Region Champions', 'Conference Tournament Champions', 'Regular Season Conference Champions'];
// Capitalised: every word but "the" starts with a capital.
const CAPITALISED = /^(?:[A-Z][A-Za-z-]*|the)(?: (?:[A-Z][A-Za-z-]*|the))*$/;

function trophy(kind, season) {
  return { kind, season, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' };
}

function seasonRecord(season, wins, losses, finish) {
  const detail = { wins, losses, national_rank: 1, conf_finish: 1, best_players: [], class_signed: [] };
  if (finish) detail.finish = finish;
  return { kind: 'season_record', season, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1', detail };
}

function topSeason(season, wins, losses, finish, isTitle, gp) {
  return { franchise_id: 'f1', team_name: 'Lawrence Eagles', team_slug: 'lawrence', season, wins, losses,
    finish, finish_is_title: isTitle, season_gp: gp, in_progress: false, week: null };
}

/** Finish lines as the server sends them (career_data.finish_label); season 2 has none, so the page names its title. */
function career() {
  return {
    user_id: 'e2e-user', username: 'Coach Demo',
    record: { wins: 140, losses: 52, total_games: 192, win_rate: 73 },
    championships_total: { conf_rs: 1, conf_t: 1, region: 1, national: 1 },
    titles_total: 4, win_pct_display: '.729', geek_points: 6060, seasons_completed: 6, programs: 1,
    trophies: [
      trophy('national', 2), trophy('region', 2), trophy('conf_t', 1), trophy('conf_rs', 3),
      seasonRecord(6, 20, 12, 'Missed the Bracket'),
      seasonRecord(5, 24, 9, 'Region Semifinal'),
      seasonRecord(4, 26, 8, 'National Quarterfinal'),
      seasonRecord(3, 24, 8, 'Regular Season Conference Champions'),
      seasonRecord(2, 31, 5, null),
      seasonRecord(1, 22, 10, 'Conference Tournament Champions'),
    ],
    top_seasons: [
      topSeason(2, 31, 5, 'National Champions', true, 1860),
      topSeason(1, 22, 10, 'Conference Tournament Champions', true, 1120),
      topSeason(3, 24, 8, 'Regular Season Conference Champions', true, 980),
      topSeason(4, 26, 8, 'National Quarterfinal', false, 940),
      topSeason(5, 24, 9, 'Region Semifinal', false, 900),
    ],
  };
}

async function installCareerApi(page) {
  await page.route('**/*', async (route) => {
    const pathname = apiPath(route);
    if (!pathname) { await route.continue(); return; }
    if (pathname === '/franchise/coach-career') { await fulfillJson(route, career()); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' }); return; }
    if (pathname === '/franchise/list') { await fulfillJson(route, { franchises: [], count: 0, max: 2, most_recent_franchise_id: null }); return; }
    if (pathname === '/teams') { await fulfillJson(route, []); return; }
    await fulfillJson(route, {});
  });
}

/** Text of each node, whether it is cut off, and how many lines it takes. */
const measure = (locator) => locator.evaluateAll((nodes) => nodes
  .filter((n) => n.textContent.trim())
  .map((n) => {
    const cs = getComputedStyle(n);
    const range = document.createRange();
    range.selectNodeContents(n);
    const lines = new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size;
    // scrollWidth is a whole number, so it misses an overflow of under a pixel, which is
    // enough to draw the ellipsis. Compare the text's own width with the room it has.
    const room = n.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const probe = n.cloneNode(true);
    probe.style.cssText = 'position:absolute;visibility:hidden;width:auto;max-width:none;overflow:visible;white-space:nowrap';
    n.parentNode.appendChild(probe);
    const natural = probe.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    probe.remove();
    const nowrap = cs.whiteSpace === 'nowrap';
    return {
      text: n.textContent.replace(/\s+/g, ' ').trim(),
      clipped: (nowrap && natural > room + 0.01) || n.scrollHeight > n.clientHeight + 1,
      spare: nowrap ? Math.round((room - natural) * 10) / 10 : null,
      lines,
    };
  }));

for (const [width, height] of SIZES) {
  test('G2: Trophy Case finish labels are one case and none is cut off (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    await stubAuth(page);
    await installCareerApi(page);
    await page.goto('/trophy-case.html');
    await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
    await expect(page.locator('.tc-head h1')).toContainText('Trophy Case');
    const table = page.locator('.tc .tbl');
    await table.scrollIntoViewIfNeeded();
    await shot(page, 'g2-trophy-case-season-reviews', width);
    const finishes = await measure(table.locator('tbody tr td:nth-child(4)'));
    expect(finishes.map((f) => f.text)).toEqual([
      'Missed the Bracket', 'Region Semifinal', 'National Quarterfinal', 'Regular Season Conference Champions',
      'National Champions', 'Conference Tournament Champions',
    ]);
    finishes.forEach((f) => {
      expect(f.text).toMatch(CAPITALISED);
      expect(f).toMatchObject({ clipped: false, lines: 1 });
    });
    // The shelf above it uses the same four names.
    const shelf = await measure(page.locator('.tc .med.gold').locator('xpath=following-sibling::div[1]/b'));
    expect(shelf.map((s) => s.text).sort()).toEqual(TITLE_LABELS.slice().sort());
    shelf.forEach((s) => expect(s).toMatchObject({ clipped: false }));
  });

  test('G2: Home Base shelf and Top Seasons use the same capitalised labels, none cut off (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
    await stubAuth(page);
    await installCareerApi(page);
    await page.goto('/mode-select.html');
    await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
    await expect(page.locator('.cr .shelf')).toBeVisible({ timeout: 15000 });
    await shot(page, 'g2-home-base', width);
    const shelf = await measure(page.locator('.cr .shelf .tro b'));
    const titles = shelf.filter((s) => /Champions$/i.test(s.text));
    expect(titles.map((s) => s.text).sort()).toEqual(TITLE_LABELS.slice().sort());
    titles.forEach((s) => expect(s).toMatchObject({ clipped: false }));
    const finishes = await measure(page.locator('.tsn .tsn-f'));
    expect(finishes.map((f) => f.text)).toEqual([
      'National Champions', 'Conference Tournament Champions', 'Regular Season Conference Champions',
      'National Quarterfinal', 'Region Semifinal',
    ]);
    finishes.forEach((f) => {
      expect(f.text).toMatch(CAPITALISED);
      expect(f).toMatchObject({ clipped: false, lines: 1 });
      expect(f.spare).toBeGreaterThanOrEqual(4); // not a sub-pixel fit
    });
    // No sentence-case champion label is left anywhere on the page.
    const text = (await page.locator('.cr').innerText()).replace(/\s+/g, ' ');
    expect(text).not.toMatch(/\b(champions|semifinal|quarterfinal|final|bracket)\b/);
  });
}

/* ------------------------------------------------------------------ G3 --- */

// The court's panels are a fixed share of the stage; 1700 is its one breakpoint.
const COURT_WIDTHS = [[1280, 720], [1366, 768], [1440, 900], [1700, 956], [1701, 957], [1920, 1080]];

for (const [width, height] of COURT_WIDTHS) {
  test('G3: the court Play Stats table reads "Half-Court Traps" on one line at ' + width, async ({ page, request }) => {
    await page.setViewportSize({ width, height });
    await stubAuth(page);
    await waitForCanonicalRosters(request);
    await page.goto(courtUrl());
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.player-stats-panel.away', { state: 'attached', timeout: 20000 });
    for (const side of ['away', 'home']) {
      // The pre-game layer sits over the stage until tip-off; the tab switch itself is what is under test.
      await page.locator('.team-toggle-btn[data-team="' + side + '"][data-tab="S2"]').evaluate((el) => el.click());
      const content = page.locator('.team-stats-content[data-team="' + side + '"]');
      await expect(content.locator('.team-tab-S2')).toBeVisible();
      await expect(page.locator('.team-toggle-btn[data-team="' + side + '"][data-tab="S2"]')).toHaveClass(/active/);
      const got = await content.evaluate((el) => {
        const lineCount = (node) => {
          const range = document.createRange();
          range.selectNodeContents(node);
          return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size;
        };
        const rows = [...el.querySelectorAll('.team-tab-S2 tr')];
        const row = (label) => rows.find((tr) => tr.children[0] && tr.children[0].textContent.trim() === label);
        const traps = row('Half-Court Traps');
        const breaks = row('Fast Breaks');
        const table = el.querySelector('.team-tab-S2 table');
        return {
          found: !!traps,
          lines: traps ? lineCount(traps.children[0]) : 0,
          sameHeight: !!traps && Math.abs(traps.getBoundingClientRect().height - breaks.getBoundingClientRect().height) < 1,
          overflows: el.scrollWidth > el.clientWidth + 1 || table.getBoundingClientRect().right > el.getBoundingClientRect().right + 1,
          old: rows.some((tr) => /HC Traps/.test(tr.textContent)),
        };
      });
      expect(got).toEqual({ found: true, lines: 1, sameHeight: true, overflows: false, old: false });
    }
    if (width === 1280 || width === 1920) {
      await page.mouse.move(0, 0);
      // Shots without the pre-game layer, as the panels read during a game.
      await page.addStyleTag({ content: '.pre-game-backdrop, .pre-game-container { display: none !important; }' });
      await shot(page, 'g3-court-play-stats', width);
      await page.locator('.team-stats-content[data-team="away"]').screenshot(
        { path: path.join(SHOTS, 'g3-court-play-stats-away-panel-' + TAG + '-' + width + '.png') });
    }
  });
}

/* ------------------------------------------------------------------ G5 --- */

/** A conference as the server sends it: standings order, ties included. */
function conference(records, userIndex) {
  const names = ['Alpha State', 'Bentley-Truman', 'Chapel Hill', 'Crickstown', 'Delta Tech', 'Amariabi International', 'Foxtrot', 'Golf Coast'];
  return {
    conference: 2,
    region: 'A',
    rows: names.map((name, index) => ({
      team_id: index === userIndex ? O.TID : 'team-' + index,
      team_name: name,
      wins: records[index][0],
      losses: records[index][1],
      differential: 20 - index * 5,
      position: index + 1,
      is_user: index === userIndex,
    })),
  };
}

/** Week 6: a tall middle column (the state that used to squeeze the card to two rows). */
function standingsOffice(state, table) {
  const data = clone(O.STATES[state]);
  data.week = 6;
  data.office_digest.conference_standings = table;
  return data;
}

async function standingsCard(page) {
  return page.evaluate(() => {
    const card = document.querySelector('#office-root .office-st');
    const rows = [...card.querySelectorAll('.st-r:not(.st-hd)')];
    const box = (el) => { const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, height: r.height, left: r.left, right: r.right }; };
    // The other Office list row at its normal spacing (a tournament week tightens its own).
    const watch = document.querySelector('#office-root .office-next:not(.tier) .ptw');
    const main = document.querySelector('html.gob-shell .main');
    return {
      rows: rows.map((row) => {
        const name = row.querySelector('.st-nm');
        const mark = row.querySelector('.st-n img, .st-n .gob-mark');
        const cs = getComputedStyle(row);
        return {
          pos: row.querySelector('.st-pos').textContent.trim(),
          name: name ? name.textContent.trim() : '',
          record: row.querySelector('.st-wl').textContent.trim(),
          me: row.classList.contains('me'),
          bg: cs.backgroundColor,
          padTop: parseFloat(cs.paddingTop), padBottom: parseFloat(cs.paddingBottom),
          box: box(row),
          text: [...row.querySelectorAll('.st-pos, .st-nm, .st-wl')].map(box),
          mark: mark ? Object.assign(box(mark), { tag: mark.tagName.toLowerCase() }) : null,
          nameCut: name ? name.scrollWidth > name.clientWidth + 1 : false,
        };
      }),
      classes: card.className,
      header: getComputedStyle(card.querySelector('.st-hd')).display !== 'none',
      more: [...card.querySelectorAll('.card-h .st-more')].map((a) => ({ text: a.textContent.trim(), href: a.getAttribute('href') })),
      title: card.querySelector('.card-h h3').textContent.trim(),
      column: [...document.querySelectorAll('#office-root .office-col')].findIndex((col) => col.contains(card)) + 1,
      watchPad: watch ? [parseFloat(getComputedStyle(watch).paddingTop), parseFloat(getComputedStyle(watch).paddingBottom)] : null,
      cardRight: box(card).right,
      pageWide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      mainWide: main.scrollWidth - main.clientWidth,
    };
  });
}

const NAVY_TINT = /^(rgba|color)\(/; // the navy selected-row wash is a translucent mix

function expectFullTable(card, table, label) {
  // All eight, in the server's order, each with its rank, mark, name and record.
  expect(card.rows.map((r) => r.name), label).toEqual(table.rows.map((r) => r.team_name));
  expect(card.rows.map((r) => r.pos), label).toEqual(table.rows.map((r) => String(r.position)));
  expect(card.rows.map((r) => r.record), label).toEqual(table.rows.map((r) => r.wins + '-' + r.losses));
  expect(card.rows).toHaveLength(8);
  card.rows.forEach((row) => {
    expect(row.mark, label + ' mark ' + row.name).not.toBeNull();
    expect(row.mark.height, label).toBeGreaterThanOrEqual(16);
    expect(row.nameCut, label + ' ' + row.name).toBe(false);
  });
  // The user's row, and only it, is navy.
  expect(card.rows.filter((r) => r.me).map((r) => r.name), label).toEqual(table.rows.filter((r) => r.is_user).map((r) => r.team_name));
  card.rows.forEach((row) => {
    if (row.me) expect(row.bg, label).toMatch(NAVY_TINT);
    else expect(row.bg, label).toBe('rgba(0, 0, 0, 0)');
  });
  expect(card.rows.find((r) => r.me).bg, label).not.toBe('rgba(0, 0, 0, 0)');
  // Normal row spacing: the same padding as the other Office list rows, never the old tight or compact.
  expect(card.classes, label).not.toMatch(/is-tight|is-compact/);
  expect(card.header, label).toBe(true);
  card.rows.forEach((row) => {
    if (card.watchPad) {
      expect(Math.abs(row.padTop - card.watchPad[0]), label).toBeLessThanOrEqual(1);
      expect(Math.abs(row.padBottom - card.watchPad[1]), label).toBeLessThanOrEqual(1);
    }
    expect(row.padTop, label).toBeGreaterThanOrEqual(5);
    expect(row.box.height, label).toBeGreaterThanOrEqual(30);
    // Text sits inside its own row.
    row.text.forEach((t) => {
      expect(t.top, label).toBeGreaterThanOrEqual(row.box.top - 0.5);
      expect(t.bottom, label).toBeLessThanOrEqual(row.box.bottom + 0.5);
    });
    expect(row.box.right, label).toBeLessThanOrEqual(card.cardRight + 0.5);
  });
  // Rows are stacked, one height, and none overlaps the next.
  const heights = card.rows.map((r) => Math.round(r.box.height));
  expect(Math.max(...heights) - Math.min(...heights), label).toBeLessThanOrEqual(1);
  for (let i = 1; i < card.rows.length; i += 1) {
    expect(card.rows[i].box.top, label + ' row ' + i).toBeGreaterThanOrEqual(card.rows[i - 1].box.bottom - 0.5);
    for (const t of card.rows[i].text) {
      for (const u of card.rows[i - 1].text) expect(t.top, label + ' text overlap row ' + i).toBeGreaterThanOrEqual(u.bottom - 0.5);
    }
  }
  // "Full standings" stays, once, to League › Standings.
  expect(card.more, label).toHaveLength(1);
  expect(card.more[0].text, label).toMatch(/^Full standings/);
  expect(card.more[0].href, label).toMatch(/tab=standings-view/);
  expect(card.title, label).toBe('Conference A2 standings');
  expect(card.column, label).toBe(2);
  expect(card.pageWide, label).toBeLessThanOrEqual(0);
  expect(card.mainWide, label).toBeLessThanOrEqual(1);
}

// Jamie's case: week 6, the user 4th at 2-3 behind a 3-2 team, with ties above and below.
const TIED = [[4, 1], [4, 1], [3, 2], [2, 3], [2, 3], [2, 3], [1, 4], [0, 5]];
const STANDINGS_SIZES = [[1280, 720], [1440, 900], [1920, 1080], [2048, 1152], [2560, 1440], [1066, 640], [1024, 600]];

for (const [width, height] of STANDINGS_SIZES) {
  test('G5: the conference standings card shows all 8 teams at normal spacing, ' + width + 'x' + height, async ({ page }) => {
    await page.setViewportSize({ width, height });
    for (const state of ['win', 'loss', 'regular', 'first_week', 'tournament', 'signing_day']) {
      const table = conference(TIED, 3);
      await O.openOffice(page, standingsOffice(state, table));
      const label = state + ' ' + width;
      await expect(page.locator('#office-root .office-st'), label).toHaveCount(1);
      expectFullTable(await standingsCard(page), table, label);
    }
  });
}

for (const [width, height] of SIZES) {
  test('G5: shots, and the card is the same whichever density class lands first (' + width + ')', async ({ page }) => {
    await page.setViewportSize({ width, height });
    const table = conference(TIED, 3);
    await O.openOffice(page, standingsOffice('win', table));
    await page.waitForTimeout(2500); // the score count-up
    const card = page.locator('#office-root .office-st');
    await card.scrollIntoViewIfNeeded();
    await page.mouse.move(0, 0);
    await shot(page, 'g5-office-standings', width);
    await card.screenshot({ path: path.join(SHOTS, 'g5-office-standings-card-' + TAG + '-' + width + '.png') });
    expectFullTable(await standingsCard(page), table, 'settled ' + width);
    // The row-cap race stats fixed read the density class before it was set. This card no
    // longer reads it at all: strip the class, draw again, and the card is unchanged.
    const again = await page.evaluate(() => {
      document.documentElement.classList.remove('gob-1280', 'gob-1920');
      window.GOBOffice.render(window.__gobCommandCenterData.office_digest);
      return document.querySelectorAll('#office-root .office-st .st-r:not(.st-hd)').length;
    });
    expect(again).toBe(8);
  });
}

test('G5: ties render in the server order, every tied team on its own row; the user can be first or last', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const allTied = [[3, 3], [3, 3], [3, 3], [3, 3], [3, 3], [3, 3], [3, 3], [3, 3]];
  for (const userIndex of [0, 7, 3]) {
    const table = conference(allTied, userIndex);
    await O.openOffice(page, standingsOffice('loss', table));
    const card = await standingsCard(page);
    expectFullTable(card, table, 'all tied, user ' + userIndex);
    expect(card.rows.map((r) => r.record)).toEqual(Array(8).fill('3-3'));
    expect(card.rows.findIndex((r) => r.me)).toBe(userIndex);
  }
});
