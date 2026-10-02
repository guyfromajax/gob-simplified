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
    // A played game's score links to its box score as a read (GOBNav adds return_url).
    const scores = page.locator('#tournament-view a.gob-res');
    const played = await scores.count();
    if (week > 27) expect(played).toBeGreaterThan(0);
    for (let i = 0; i < played; i += 1) {
      await expect(scores.nth(i)).toHaveAttribute('data-return', '');
      await expect(scores.nth(i)).toHaveAttribute('href', /\/box-score\.html\?game_id=/);
    }
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

// ── A result's box score, from a real played game ─────────────────────────────
// The responses below are the real server's, recorded from one real game played to the
// final buzzer on the offline engine (week 3), with the week then closed (week 4). That
// is the state that sent every "Box score" click back to the Office: the game is final,
// it is the franchise's last game, and the week has moved on, which is exactly what the
// closed-game guard looks for. A box score opened to read carries return_url and is left
// alone; the post-game flow page, which carries none, is still guarded.
const GAME = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/boxscore-real-game.json'), 'utf8'));
const RESULT_URL = '/franchise-command-center.html?franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id;

async function installRealGame(page) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) { return route.continue(); }
    const pathname = url.pathname;
    if (pathname.indexOf('/images/players/') !== -1) return route.fulfill({ status: 404, body: '' });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/command-center/data')) return json(route, GAME.command_center);
    if (pathname.startsWith('/franchise/team-detail')) return json(route, GAME.team_detail);
    if (pathname.startsWith('/franchise/schedule/week')) return json(route, GAME.schedule_week_3);
    if (pathname.startsWith('/franchise/news')) {
      return json(route, {
        news: [],
        dispatches: [{
          type: 'game_result', week: 3, yours: true, headline: 'Lancaster defeated Little York 63-58',
          target: '/box-score.html?game_id=' + GAME.game_id + '&mode=franchise&franchise_id=' + GAME.franchise_id,
        }],
      });
    }
    if (pathname === '/api/game/' + GAME.game_id + '/resume-state') return json(route, GAME.resume_state);
    if (pathname === '/api/game/' + GAME.game_id) return json(route, GAME.game);
    if (pathname.startsWith('/roster/')) {
      return json(route, pathname.indexOf(GAME.opponent_id) !== -1 ? GAME.roster_opponent : GAME.roster_user);
    }
    return json(route, {});
  });
}

async function openResultSource(page, query, ready) {
  await installRealGame(page);
  await page.goto(RESULT_URL + query);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready, { timeout: 20000 });
}

/** The box score for the recorded game is on screen and stays there. */
async function expectBoxScore(page) {
  await expect(page).toHaveURL(/\/box-score\.html\?/, { timeout: 15000 });
  await page.waitForSelector('#home-player-stats-body tr', { timeout: 20000 });
  // The bounce took a second or two (two reads, then the jump): give it room to happen.
  await page.waitForTimeout(3500);
  await expect(page).toHaveURL(/\/box-score\.html\?/);
  const here = new URL(page.url());
  expect(here.searchParams.get('game_id')).toBe(GAME.game_id);
  await expect(page.locator('#box-score-container')).toContainText('Lancaster');
  await expect(page.locator('#box-score-container')).toContainText('63');
  await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(0);
  return here;
}

test('the real game is the case the guard matches: final, the last game, the week moved on', () => {
  expect(GAME.resume_state.status).toBe('final');
  expect(String(GAME.command_center.last_game_summary.game_id)).toBe(GAME.game_id);
  expect(Number(GAME.command_center.last_game_summary.week)).toBeLessThan(Number(GAME.command_center.week));
});

test('Team › Schedule: clicking a real result opens that game\'s box score, and Back returns to the schedule', async ({ page }) => {
  await openResultSource(page, '&tab=team-schedule-view', '#team-schedule-view a.gob-res');
  const result = page.locator('#team-schedule-view a.gob-res[href*="' + GAME.game_id + '"]');
  await expect(result).toHaveText(/W\s*63-58/);
  await result.click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('tab=team-schedule-view');
  if (SHOTS) {
    fs.mkdirSync(OUT, { recursive: true });
    await page.mouse.move(0, 0);
    await page.screenshot({ path: path.join(OUT, 'after-box-score-from-team-schedule-1280.png'), animations: 'disabled' });
  }
  await page.locator('#locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('team-schedule-view');
});

test('League › Schedule: the "Box score" link of a real result opens the box score', async ({ page }) => {
  await openResultSource(page, '&tab=league-schedule-view&week=3', '#league-schedule-view .gob-game.me a.gob-box');
  await page.locator('#league-schedule-view .gob-game.me a.gob-box').click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('tab=league-schedule-view');
});

test('Office: the weekly card\'s "Box score" link opens the box score', async ({ page }) => {
  await openResultSource(page, '', '#office-root .wkc a.lnk');
  const link = page.locator('#office-root .wkc a.lnk', { hasText: 'Box score' });
  await link.click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('/franchise-command-center.html');
});

test('News: a game-result headline opens the box score', async ({ page }) => {
  await openResultSource(page, '&tab=news-view', '#news-view .gob-news-card');
  await page.locator('#news-view a.gob-news-card', { hasText: 'Box Score' }).click();
  const here = await expectBoxScore(page);
  expect(here.searchParams.get('return_url')).toContain('tab=news-view');
});

test('the finished game\'s flow page is still guarded: no return_url, back to the Office', async ({ page }) => {
  await installRealGame(page);
  await page.goto('/box-score.html?game_id=' + GAME.game_id + '&mode=franchise&franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id);
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('home-tab');
});


// ── Team › Team Attributes: no rank-movement arrows ───────────────────────────
test('Team Attributes draws no rank-movement arrows, whatever rank_delta says', async ({ page }) => {
  await stubAuth(page);
  const defs = [
    ['team_chemistry', 'Chemistry', 19, null, 25, null], ['fight', 'Fight', 6, 20, null, 2],
    ['discipline', 'Discipline', -3, 20, null, -1], ['offensive_efficiency', 'Offense', 12, 20, null, 3],
    ['defensive_efficiency', 'Defense', 5, 20, null, -4], ['pt_opp_modifier', 'P/T Offense', -4, 20, null, 1],
    ['pt_efficiency', 'P/T Defense', 9, 20, null, -2], ['fb_efficiency', 'Fast Break', 14, 20, null, 5],
    ['fb_opp_modifier', 'Fast Break Defense', -7, 20, null, -6], ['shot_threshold', 'Shooting', 88, null, null, 7],
    ['rebound_modifier', 'Rebounding', 0.52, null, null, -8],
  ];
  const attrs = {};
  const measures = defs.map((d, i) => {
    attrs[d[0]] = d[2];
    return {
      family: i < 3 ? 'character' : 'floor', key: d[0], label: d[1], value: d[2], signed_scale: d[3], scale_max: d[4],
      direction: d[0] === 'shot_threshold' ? 'lower_better' : 'higher_better',
      rank: 10 + i * 9, rank_of: 128, percentile: 90 - i * 7, rank_delta: d[5], tied: false,
    };
  });
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, version: '1.0' });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json(route, { franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 13, rank: 14, season: 1, current_season: 1, training_completed: true, cut_required: false, recruiting_wire: { board_saved_week: 13, counts: {} }, team_record: { wins: 9, losses: 3 } });
    }
    if (pathname.startsWith('/franchise/team-data')) {
      return json(route, { team_attributes: attrs, measures: measures, updated_after_week: 12, plays_data: {}, scouting_data: {} });
    }
    return json(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-attributes-view');
  await page.waitForSelector('#team-attributes-view .mcell', { timeout: 20000 });
  await expect(page.locator('#team-attributes-view .mcell')).toHaveCount(11);
  await shot(page, 'team-attributes-no-arrows');
  // Every measure the server tracks has moved (Chemistry is never in the snapshot), and
  // none of it is drawn.
  expect(measures.filter((m) => m.key !== 'team_chemistry').every((m) => m.rank_delta)).toBe(true);
  await expect(page.locator('#team-attributes-view .mv')).toHaveCount(0);
  await expect(page.locator('#team-attributes-view .mgrid')).not.toContainText(/[▲▼]/);
  // Each cell keeps its name, place, gauge and value; the gauge now runs to the value.
  const cell = page.locator('#team-attributes-view .mcell[data-measure="offensive_efficiency"]');
  await expect(cell.locator('.nm')).toHaveText('Offense');
  await expect(cell.locator('.place')).toHaveText('(37th of 128)');
  await expect(cell.locator('.mbar > *')).toHaveCount(2);
  await expect(cell.locator('b')).toHaveText('+12');
  const bar = await cell.locator('.mbar').evaluate((el) => {
    const value = el.querySelector('b').getBoundingClientRect();
    return Math.round(el.getBoundingClientRect().right - value.right);
  });
  expect(bar).toBeLessThanOrEqual(1);
});
