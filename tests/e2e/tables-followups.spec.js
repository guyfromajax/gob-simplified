const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

/**
 * Tables follow-ups: attribute pairs on Assign Practice Squad and the Practice Squad
 * training report, and "Half-Court Traps" on the playbook report, the box score and Set
 * Lineup. TF_SHOTS=1 also writes reports/tables-followups/after-*.png.
 */
test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.TF_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/tables-followups');
const FID = 'f-e2e-tables-followups';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const PAIRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
const PLAN = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

async function shot(page, name) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, 'after-' + name + '-1280.png'), animations: 'disabled' });
}

const NAMES = ['Ada Keeper', 'Bea Reserve', 'Cy Bench', 'Dee Marsh', 'Eli Stone', 'Finn Late'];

/** Every attribute different, so a column in the wrong place shows as the wrong number. */
function attributes(i) {
  const out = {};
  PAIRS.forEach((key, k) => { out[key] = 30 + ((i * 7 + k * 11) % 60); });
  return out;
}

/**
 * The rhythm of one attribute table, measured between the boxes that hold the values
 * (adjacent cells always touch, so the cell boxes say nothing).
 */
async function rhythm(page, table) {
  return page.evaluate((selector) => {
    const root = document.querySelector(selector);
    const head = root.querySelector('thead tr');
    const rows = Array.from(root.querySelectorAll('tbody tr'));
    const row = rows[0];
    const box = (cell) => cell.querySelector('.ak').getBoundingClientRect();
    const starts = Array.from(row.querySelectorAll('.gstart'));
    const ends = Array.from(row.querySelectorAll('.gend'));
    const within = [];
    const between = [];
    starts.forEach((start, i) => {
      within.push(Math.round(box(ends[i]).left - box(start).right));
      if (starts[i + 1]) between.push(Math.round(box(starts[i + 1]).left - box(ends[i]).right));
    });
    const lead = row.querySelector('.wt, .tsr-lead');
    const range = document.createRange();
    range.selectNodeContents(lead);
    const heads = Array.from(head.querySelectorAll('.gstart, .gend'));
    const cells = Array.from(row.querySelectorAll('.gstart, .gend'));
    return {
      heads: heads.map((cell) => cell.textContent.trim()),
      values: cells.map((cell) => cell.textContent.trim()),
      within: within,
      between: between,
      lead: Math.round(box(starts[0]).left - range.getBoundingClientRect().right),
      // Each label sits over its own value.
      offCentre: Math.max.apply(null, heads.map((cell, i) => {
        const a = box(cell);
        const b = box(cells[i]);
        return Math.abs((a.left + a.width / 2) - (b.left + b.width / 2));
      })),
      heights: rows.map((tr) => Math.round(tr.getBoundingClientRect().height * 100) / 100),
      overflow: root.scrollWidth - root.parentElement.clientWidth,
    };
  }, table);
}

function expectPairs(r, where) {
  expect(r.heads, where + ': six pairs, the roster order').toEqual(PAIRS);
  const within = Math.max.apply(null, r.within);
  const between = Math.min.apply(null, r.between);
  expect(within, where + ': inside a pair').toBeLessThanOrEqual(8);
  expect(between, where + ': between pairs').toBeGreaterThanOrEqual(within * 3);
  expect(Math.max.apply(null, r.within) - Math.min.apply(null, r.within), where).toBeLessThanOrEqual(1);
  // Sub-pixel character widths round either way: two pixels is the same gutter.
  expect(Math.max.apply(null, r.between) - Math.min.apply(null, r.between), where).toBeLessThanOrEqual(2);
  expect(r.lead, where + ': the gap before SC is the widest').toBeGreaterThan(Math.max.apply(null, r.between));
  expect(r.offCentre, where + ': labels over their values').toBeLessThanOrEqual(1);
  expect(new Set(r.heights).size, where + ': one row height').toBe(1);
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('Assign Practice Squad: the twelve attributes read as six pairs, rows unchanged', async ({ page }) => {
  await stubAuth(page);
  const roster = NAMES.map((name, i) => ({
    _id: '11111111111111111111110' + (i + 1), name,
    position_ratings: { PG: 72 - i * 5, SG: 60, SF: 50, PF: 40, C: 30 },
    attributes: attributes(i), height: 73 + i, weight: 180 + i * 7, year: ['FR', 'SO', 'JR', 'SR'][i % 4],
  }));
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json(route, { franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 1, season: 1, current_season: 1, cut_required: true, cut_count: 2, recruiting_wire: {} });
    }
    if (pathname.startsWith('/roster/')) return json(route, { players: roster, conference: 1, region: 'A', team_chemistry: 15 });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json(route, pathname === '/teams' ? [] : {});
    return route.continue();
  });
  await page.goto('/cut-players.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc');
  await page.locator('#cut-players-body tr').nth(5).waitFor({ timeout: 30000 });
  await page.waitForTimeout(300);
  await shot(page, 'assign-practice-squad');

  const r = await rhythm(page, '#cut-players-table');
  expectPairs(r, 'assign practice squad');
  // The value under each label is that attribute's, in the new order.
  const first = attributes(0);
  expect(r.values).toEqual(PAIRS.map((key) => String(Math.floor(first[key] / 10))));
  // The row height the page had before the pairs (44.55px, measured on develop f56d9ec29).
  expect(r.heights[0]).toBe(44.55);
  expect(r.overflow).toBeLessThanOrEqual(1);
  // The headers before and after the block are where they were.
  const heads = await page.locator('#cut-players-table thead th').allTextContents();
  expect(heads.map((t) => t.trim())).toEqual(['Name', 'POS', 'Year', 'Height', 'Weight'].concat(PAIRS, ['RT', 'To Practice Squad']));
});

test('Practice Squad training report: six pairs then CH, in both views, rows unchanged', async ({ page }) => {
  await stubAuth(page);
  // The server's own key order: AG before ST, CH last.
  const serverKeys = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT', 'CH'];
  const players = NAMES.map((name, i) => {
    const baseline = Object.assign(attributes(i), { CH: 12 });
    const current = {};
    Object.keys(baseline).forEach((key, k) => { current[key] = baseline[key] + ((i + k) % 4) - 1; });
    return { player_id: 'p' + i, name, pos: ['PG', 'SG', 'SF', 'PF', 'C'][i % 5], baseline, current };
  });
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    if (pathname.startsWith('/franchise/training-squad-reports')) {
      return json(route, { attr_keys: serverKeys, reports: [{ week: 8, players }] });
    }
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json(route, pathname === '/teams' ? [] : {});
    return route.continue();
  });
  await page.goto('/training-squad-report.html?franchise_id=' + FID + '&team_id=' + TID);
  await expect(page.locator('.tsr-toggle .toggle-btn.active')).toBeVisible({ timeout: 30000 });
  await page.locator('.tsr-table tbody tr').nth(5).waitFor();
  await shot(page, 'practice-squad-report-changes');

  const changes = await rhythm(page, '.tsr-table');
  expectPairs(changes, 'practice squad report, changes');
  // CH is not one of the twelve: it follows the pairs, on its own.
  const all = await page.locator('.tsr-table thead tr').first().locator('td, th').allTextContents();
  expect(all.map((t) => t.trim())).toEqual(['Name', 'POS'].concat(PAIRS, ['CH']));
  // Each change is still that attribute's: current minus baseline, read by key.
  const p0 = players[0];
  expect(changes.values).toEqual(PAIRS.map((key) => {
    const delta = p0.current[key] - p0.baseline[key];
    return delta > 0 ? '+' + delta : String(delta);
  }));
  // 30.55px on develop f56d9ec29, in both views.
  expect(changes.heights[0]).toBe(30.55);

  await page.locator('.tsr-toggle .toggle-btn', { hasText: 'Absolute' }).click();
  await shot(page, 'practice-squad-report-absolute');
  const absolute = await rhythm(page, '.tsr-table');
  expectPairs(absolute, 'practice squad report, absolute');
  expect(absolute.values).toEqual(PAIRS.map((key) => String(p0.current[key])));
  expect(absolute.heights[0]).toBe(30.55);
});

/** A heading that names Half-Court Traps on one line, inside its box. */
async function oneLine(locator) {
  return locator.evaluate((el) => {
    const range = document.createRange();
    range.selectNodeContents(el);
    const lines = new Set(Array.from(range.getClientRects()).map((rect) => Math.round(rect.top)));
    return { lines: lines.size, clipped: el.scrollWidth > el.clientWidth + 1 };
  });
}

test('playbook report: the section is "Half-Court Traps"', async ({ page }) => {
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  await page.route('**/*', async (route) => {
    const req = route.request();
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (err) { return route.continue(); }
    if (/googletagmanager|sentry|google-analytics/.test(req.url())) return route.fulfill({ status: 204, body: '' });
    if (pathname === '/api/playbooks') return json(route, req.method() === 'GET' ? PLAN.playbooks : { success: true });
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e', fte_v2_complete: true });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0', sentryDsn: null });
    return route.continue();
  });
  await page.goto('/playbook-report.html?franchise_id=' + FID + '&team_id=' + TID + '&mode=franchise', { waitUntil: 'load' });
  await page.locator('.report-row').first().waitFor({ timeout: 30000 });
  const heading = page.locator('.report-section-head h2', { hasText: 'Traps' });
  await heading.scrollIntoViewIfNeeded();
  if (SHOTS) {
    fs.mkdirSync(OUT, { recursive: true });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-playbook-report-half-court-traps-1280.png'), animations: 'disabled' });
  }
  await expect(heading).toHaveText('Half-Court Traps');
  await expect(page.locator('body')).not.toContainText('HC Traps');
  expect(await oneLine(heading)).toEqual({ lines: 1, clipped: false });
  // It sits level with its neighbour, Fast Breaks.
  const tops = await page.locator('.report-section-head h2').evaluateAll((nodes) => {
    const pick = (text) => nodes.find((n) => n.textContent.trim() === text).getBoundingClientRect();
    return { traps: Math.round(pick('Half-Court Traps').top), breaks: Math.round(pick('Fast Breaks').top), same: pick('Half-Court Traps').height === pick('Fast Breaks').height };
  });
  expect(tops.traps).toBe(tops.breaks);
  expect(tops.same).toBe(true);
});

test('box score: the special-situations line is "Half-Court Traps:"', async ({ page }) => {
  await stubAuth(page);
  const players = [
    { name: 'Jalen Carter', playerId: 'p1', team: 'home', position: 'PG', jersey: 1, stats: { pts: 22, reb: 5, ast: 4, min: 32 } },
    { name: 'Omar Lane', playerId: 'p2', team: 'away', position: 'SG', jersey: 2, stats: { pts: 18, reb: 3, ast: 2, min: 30 } },
  ];
  // Three-figure counts for the home side: the longest the line gets.
  const teamStats = (used, success) => ({
    offense: {
      Playcalls: {
        Motion: { overall: { attempts: 40, success: 21 } },
        Set: { overall: { attempts: 18, success: 9 } },
        Cumulative: {},
      },
    },
    defense: { HCT: { used: used, success: success }, FCP: { used: 9, success: 4 } },
  });
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json(route, { franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 12, season: 1, current_season: 1, training_completed: true, team_record: { wins: 8, losses: 4 }, recruiting_wire: {}, user_conference: 1, user_region: 'A' });
    }
    if (pathname.indexOf('/api/game/') === 0 && pathname.indexOf('resume-state') === -1) {
      const box = { Lancaster: {}, 'Four Corners': {} };
      players.forEach((p) => { box[p.team === 'home' ? 'Lancaster' : 'Four Corners'][p.position + p.jersey] = Object.assign({ name: p.name, playerId: p.playerId }, p.stats); });
      return json(route, {
        home_team_id: TID, away_team_id: OPP,
        teams: { [TID]: { name: 'Lancaster' }, [OPP]: { name: 'Four Corners' } },
        home_team: { name: 'Lancaster' }, away_team: { name: 'Four Corners' },
        score: { Lancaster: 78, 'Four Corners': 71 },
        points_by_quarter: { Lancaster: [20, 18, 22, 18], 'Four Corners': [19, 17, 18, 17] },
        clock: '0:00', quarter: 4, is_final: true, players, box_score: box,
        team_stats: { Lancaster: teamStats(112, 104), 'Four Corners': teamStats(7, 3) },
        player_of_the_game: { playerId: 'p1', name: 'Jalen Carter', stats: { pts: 22, reb: 5, ast: 4, stl: 1, blk: 0, defPct: '42%' } },
      });
    }
    return json(route, {});
  });
  await page.goto('/box-score.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID
    + '&game_id=g-box&home=Lancaster&away=Four%20Corners&my_team=home&return_url=' + encodeURIComponent('/schedule.html'));
  await page.waitForSelector('#home-player-stats-body tr', { timeout: 30000 });
  const line = page.locator('#home-scouting-content .scouting-play-type-header', { hasText: 'Traps' });
  await line.waitFor({ state: 'attached', timeout: 15000 }).catch(() => {});
  expect(errors, 'the box score rendered without a script error').toEqual([]);
  await line.scrollIntoViewIfNeeded();
  if (SHOTS) {
    fs.mkdirSync(OUT, { recursive: true });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-box-score-half-court-traps-1280.png'), animations: 'disabled' });
  }
  await expect(line).toBeVisible();
  await expect(line.locator('span').first()).toHaveText('Half-Court Traps:');
  await expect(line.locator('span').nth(1)).toHaveText('104 / 112 (93%)');
  // Label and figures on one line, inside the column.
  const fit = await line.evaluate((el) => {
    const spans = Array.from(el.querySelectorAll('span')).map((s) => s.getBoundingClientRect());
    const column = el.closest('.scouting-section').getBoundingClientRect();
    return { sameLine: Math.abs(spans[0].top - spans[1].top) <= 2, inside: spans[1].right <= column.right + 1 };
  });
  expect(fit).toEqual({ sameLine: true, inside: true });
  await expect(page.locator('#home-scouting-content')).not.toContainText('HC Traps');
});

test('Set Lineup: the playbooks modal section is "Half-Court Traps"', async ({ page, request }) => {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.route('**/api/playbooks?**', (route) => json(route, PLAN.playbooks));
  await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
  await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
  await page.locator('#playbooks-button').click();
  const heads = page.locator('#playbooks-modal-sections .lineup-playbooks-head');
  await expect(heads).toHaveCount(6, { timeout: 15000 });
  await heads.nth(5).scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  if (SHOTS) {
    fs.mkdirSync(OUT, { recursive: true });
    await page.screenshot({ path: path.join(OUT, 'after-set-lineup-half-court-traps-1280.png'), animations: 'disabled' });
  }
  await expect(heads).toHaveText(['Motion Plays', 'Set Plays', 'Man Defense', 'Zone Defense', 'Fast Breaks', 'Half-Court Traps']);
  const traps = heads.nth(5);
  expect(await oneLine(traps)).toEqual({ lines: 1, clipped: false });
  // The same head height as the other five: the longer name did not grow it.
  const heights = await heads.evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().height)));
  expect(new Set(heights).size).toBe(1);
});

// ── League › Tournament, against what a real server does ──────────────────────
// The payloads are the real route's answers for one real season (the offline engine,
// driven by scripts/ws2_loopback_season.py, at the weeks named). The stub keeps the
// hosted server's contract: no Authorization header, no brackets (401). The earlier
// specs answered every request, which is how a tab that sent no session passed them
// all and still showed "Tournament could not be opened." on a real server.
const REAL = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/tournament-real-season.json'), 'utf8'));

async function openRealTournament(page, body, seen) {
  const tid = body.user_team_id;
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { return route.continue(); }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/tournament/brackets')) {
      const auth = request.headers().authorization || '';
      seen.push(auth);
      if (!/^Bearer \S+/.test(auth)) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Not authenticated' }) });
      }
      return json(route, body);
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json(route, {
        franchise_id: FID, team_id: tid, user_team_id: tid, team: (body.teams[tid] || {}).name || 'Lancaster',
        week: body.week, rank: 12, user_conference: body.user_conference, user_region: body.user_region,
        training_completed: true, cut_required: false, eos_tournament_active: true,
        region_bye_modal_eligible: false, conference_rs_region_modal: { eligible: false },
        bracket_reveal_modal: { eligible: false }, bracket_update_modal: { eligible: false },
        recruiting_results_modal: { eligible: false }, walk_on_welcome_modal: { eligible: false },
        recruiting_wire: { board_saved_week: body.week, counts: {} }, team_record: { wins: 14, losses: 12 },
      });
    }
    return json(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + tid + '&tab=tournament-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#tournament-view.tab-content.active')).toBeVisible();
}

for (const week of Object.keys(REAL).map(Number).sort((a, b) => a - b)) {
  test('Tournament tab, real season week ' + week + ': the request carries the session and the bracket draws', async ({ page }) => {
    const body = REAL[String(week)];
    const seen = [];
    await openRealTournament(page, body, seen);
    // The tab opens on the phase the week is in, and that phase has a bracket.
    await expect(page.locator('#tournament-view .fcc-tb-mu').first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(600);
    if (SHOTS) {
      fs.mkdirSync(OUT, { recursive: true });
      await page.mouse.move(0, 0);
      await page.screenshot({ path: path.join(OUT, 'after-tournament-real-week-' + week + '-1280.png'), animations: 'disabled' });
    }
    // Every request for the brackets carried the session.
    expect(seen.length).toBeGreaterThan(0);
    seen.forEach((auth) => { expect(auth).toMatch(/^Bearer \S+/); });
    // No error card, no "not drawn" line: the bracket itself.
    await expect(page.locator('#tournament-view .gob-view-error')).toHaveCount(0);
    await expect(page.locator('#tournament-view')).not.toContainText('could not be opened');
    await expect(page.locator('#tournament-view .gob-tour-empty')).toHaveCount(0);
    await expect(page.locator('#tournament-view [data-tour-phase].on')).toHaveAttribute('data-tour-phase', body.current_phase);
    // The teams drawn are the stored bracket's teams, by name.
    const names = await page.locator('#tournament-view .fcc-tb-mu .fcc-tb-name-text').allTextContents();
    expect(names.length).toBeGreaterThan(1);
    const known = Object.keys(body.teams).map((id) => body.teams[id].name);
    names.filter((text) => text.trim() && text.trim() !== 'TBD').forEach((text) => {
      expect(known.some((name) => text.indexOf(name) !== -1), text).toBe(true);
    });
    // Each phase that has been drawn by this week draws; one that has not says when.
    for (const phase of ['conference', 'region', 'national']) {
      await page.locator('#tournament-view [data-tour-phase="' + phase + '"]').click();
      if (week >= body.phase_draw_week[phase]) {
        await expect(page.locator('#tournament-view .fcc-tb-mu').first()).toBeVisible();
        await expect(page.locator('#tournament-view .gob-tour-empty')).toHaveCount(0);
      } else {
        await expect(page.locator('#tournament-view .gob-tour-empty')).toHaveText('Draws after Week ' + body.phase_draw_week[phase]);
      }
    }
  });
}
