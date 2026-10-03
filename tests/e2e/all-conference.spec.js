// @ts-check
/**
 * News › Awards: the All-Conference section under the All-American teams.
 *
 * One conference at a time, picked from a row of the sixteen; the user's conference is
 * the default and is cued "Yours". First and second team only, one player per position.
 * Projected weekly, "Final" from week 27 while All-Americans are still projected. The
 * stubbed body carries the stored fields a server must never send (weights, score,
 * rank, bonus, the rank-3 alternates), so the test proves the page draws none of them.
 * AC_SHOTS=1 writes reports/all-conference/after-*.png at 1280 and 1920.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-all-conference';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OTHER = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const LETTERS = 'ABCDEFGH';
const OUT = path.resolve(__dirname, process.env.AC_SHOTS_DIR || '../../reports/all-conference');
const SHOTS = process.env.AC_SHOTS === '1';
const USER_CONFERENCE = '6';

function labelOf(n) {
  return LETTERS[Math.floor((n - 1) / 2)] + n;
}

function pick(conference, team, position, rank, extra) {
  const mine = conference === USER_CONFERENCE && team === 'first_team' && position === 'SF';
  return Object.assign({
    player_id: 'c' + conference + '-' + team + '-' + position,
    name: labelOf(Number(conference)) + ' ' + position + ' ' + rank,
    year: 'Junior',
    team_id: mine ? TID : OTHER + conference,
    team_name: mine ? 'Lancaster' : 'Team ' + labelOf(Number(conference)),
    position,
    rating: 92 - rank * 10,
    rank,
    score: 88.5 - rank * 9,
    components: { attributes: 80, stats: 70, team: 60 },
    games: 12,
    stats: { PTS: 17.1, REB: 5.2, AST: 3, STL: 1.1, BLK: 0.5, 'DEF%': 58 },
  }, extra || {});
}

function conferences(extra) {
  const out = {};
  for (let n = 1; n <= 16; n += 1) {
    const key = String(n);
    out[key] = {
      first_team: POSITIONS.map((position) => pick(key, 'first_team', position, 1, extra && extra(key, position))),
      second_team: POSITIONS.map((position) => pick(key, 'second_team', position, 2, extra && extra(key, position))),
      // The stored projection keeps rank 3 for the final's coin: it must not reach the page.
      third_team: POSITIONS.map((position) => pick(key, 'third_team', position, 3)),
    };
  }
  return out;
}

function labels() {
  const out = {};
  for (let n = 1; n <= 16; n += 1) out[String(n)] = labelOf(n);
  return out;
}

function americans() {
  const teams = {};
  ['first_team', 'second_team', 'third_team'].forEach((key, i) => {
    teams[key] = POSITIONS.map((position) => pick('1', key, position, i + 1, {
      name: position + ' ' + (i + 1), team_id: OTHER, team_name: 'Four Corners',
    }));
  });
  return teams;
}

function projectedBody() {
  return {
    status: 'projected', week: 12, label: 'After week 12', stats_basis: 'per_game',
    weights: { attributes: 26.3, stats: 70, team: 3.8 },
    all_american_teams: americans(),
    all_conference: {
      status: 'projected', week: 12, label: 'After week 12', stats_basis: 'per_game',
      conference: Number(USER_CONFERENCE), labels: labels(),
      weights: { attributes: 26.3, stats: 70, team: 3.8 },
      conferences: conferences(),
    },
  };
}

function finalConferenceBody() {
  const body = projectedBody();
  body.week = 26;
  body.label = 'End of regular season';
  body.all_conference = {
    status: 'final', label: 'Final', stats_basis: 'per_game',
    conference: Number(USER_CONFERENCE), labels: labels(),
    second_team_ranks: { 6: { PG: 3 } },
    conferences: conferences((key, position) => (key === USER_CONFERENCE && position === 'PG' ? { rank: 3 } : null)),
  };
  return body;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openAwards(page, body, center) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/command-center/data')) {
      if (center) return fulfillJson(route, center);
      return fulfillJson(route, {
        franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 13, rank: 8,
        season: 1, current_season: 1, training_completed: true, session_type: 'in-season',
        cut_required: false, recruiting_wire: { board_saved_week: 1, counts: {} },
        user_conference: 6, user_region: 'C', team_record: { wins: 10, losses: 2 },
      });
    }
    if (pathname.startsWith('/franchise/awards')) return fulfillJson(route, body);
    if (pathname.startsWith('/franchise/news')) return fulfillJson(route, { news: [], dispatches: [] });
    return fulfillJson(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=awards-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#awards-view.tab-content.active .gob-awards-conf');
  await page.mouse.move(800, 500);
}

async function shots(page, name) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.locator('#awards-view .gob-awards-conf').evaluate((node) => {
      // Under the sticky page head, with the section's own head in view.
      node.scrollIntoView({ block: 'start' });
      const main = document.querySelector('html.gob-shell .main');
      if (main) main.scrollTop = Math.max(0, main.scrollTop - 150);
    });
    await page.mouse.move(size.width - 6, size.height - 6);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
}

/** The section as drawn: head, picker, and the two tables' rows. */
function readSection(page) {
  return page.locator('#awards-view .gob-awards-conf').evaluate((root) => ({
    title: root.querySelector('.gob-awards-head h2').textContent,
    status: (root.querySelector('.gob-awards-head p') || {}).textContent || '',
    chosen: root.getAttribute('data-conference'),
    buttons: [...root.querySelectorAll('.gob-awards-conf-row button')].map((b) => ({
      key: b.getAttribute('data-conference'), text: b.querySelector('span').textContent,
      on: b.classList.contains('on'), yours: b.classList.contains('is-yours'),
      cue: (b.querySelector('em') || {}).textContent || '', selected: b.getAttribute('aria-selected'),
    })),
    sections: [...root.querySelectorAll('section')].map((section) => ({
      title: section.querySelector('h3').textContent,
      heads: [...section.querySelectorAll('thead th')].map((th) => th.textContent),
      rows: [...section.querySelectorAll('tbody tr')].map((tr) => ({
        pos: tr.querySelector('.gob-awards-pos').textContent,
        name: tr.querySelector('td:nth-child(2)').textContent,
        mine: tr.classList.contains('me'),
      })),
    })),
    text: root.innerText.replace(/\s+/g, ' '),
  }));
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('All-Conference: the user\'s conference by default, cued, two teams by position, nothing of the formula', async ({ page }) => {
  await openAwards(page, projectedBody());
  const view = page.locator('#awards-view');
  // Under the All-American teams, in the same page.
  await expect(view.locator('.gob-awards > section h3')).toHaveText([
    '1st Team All-American', '2nd Team All-American', '3rd Team All-American',
  ]);
  const section = await readSection(page);
  expect(section.title).toBe('Projected All-Conference');
  expect(section.status).toBe('After week 12');
  expect(section.chosen).toBe(USER_CONFERENCE);
  // Sixteen conferences, A1 to H16, the user's one on and cued.
  expect(section.buttons.map((b) => b.text)).toEqual(Array.from({ length: 16 }, (_, i) => labelOf(i + 1)));
  const on = section.buttons.filter((b) => b.on);
  expect(on.length).toBe(1);
  expect(on[0]).toMatchObject({ key: USER_CONFERENCE, text: 'C6', yours: true, cue: 'Yours', selected: 'true' });
  expect(section.buttons.filter((b) => b.yours).length).toBe(1);
  // First and second team only, PG to C, the user's player on the navy row.
  expect(section.sections.map((s) => s.title)).toEqual(['1st Team All-Conference', '2nd Team All-Conference']);
  section.sections.forEach((s) => {
    expect(s.rows.map((r) => r.pos)).toEqual(POSITIONS);
    expect(s.heads).toEqual(['Pos', 'Player', 'Yr', 'Team', 'RT', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'DEF%']);
  });
  expect(section.sections[0].rows.map((r) => r.name)).toEqual(POSITIONS.map((p) => 'C6 ' + p + ' 1'));
  expect(section.sections[0].rows.filter((r) => r.mine).map((r) => r.pos)).toEqual(['SF']);
  // No third team, no score, no bonus, no weights, no rank.
  expect(section.text).not.toMatch(/3rd Team All-Conference|Score|Bonus|Ratings \d|Team rank|weight|\brank\b/i);
  expect(section.text).not.toContain('C6 PG 3');
  await expect(view.locator('.gob-awards-conf .gob-awards-score, .gob-awards-conf .gob-awards-bonus')).toHaveCount(0);
  await shots(page, 'awards-all-conference-projected');
});

test('the picker shows another conference and remembers it; the cue stays on the user\'s', async ({ page }) => {
  await openAwards(page, projectedBody());
  const view = page.locator('#awards-view');
  await view.locator('.gob-awards-conf').evaluate((node) => node.scrollIntoView({ block: 'start' }));
  const top = await view.locator('.gob-awards-conf').evaluate((node) => Math.round(node.getBoundingClientRect().top));
  await view.locator('.gob-awards-conf-row button[data-conference="11"]').click();
  await expect(view.locator('.gob-awards-conf')).toHaveAttribute('data-conference', '11');
  let section = await readSection(page);
  expect(section.buttons.filter((b) => b.on).map((b) => b.text)).toEqual(['F11']);
  expect(section.buttons.filter((b) => b.yours).map((b) => b.text)).toEqual(['C6']);   // the cue does not move
  expect(section.sections[0].rows.map((r) => r.name)).toEqual(POSITIONS.map((p) => 'F11 ' + p + ' 1'));
  expect(section.sections[0].rows.some((r) => r.mine)).toBe(false);
  // The page did not jump: only the block repainted.
  expect(await view.locator('.gob-awards-conf').evaluate((node) => Math.round(node.getBoundingClientRect().top))).toBe(top);
  // The All-American tables above are untouched.
  await expect(view.locator('.gob-awards > section h3')).toHaveCount(3);
  // Back to the user's conference by its button.
  await view.locator('.gob-awards-conf-row button.is-yours').click();
  section = await readSection(page);
  expect(section.chosen).toBe(USER_CONFERENCE);
  await view.locator('.gob-awards-conf-row button[data-conference="2"]').click();
  await expect(view.locator('.gob-awards-conf')).toHaveAttribute('data-conference', '2');
  // Leave and come back: the choice is remembered for the session.
  await page.getByRole('tab', { name: 'News', exact: true }).click();
  await page.getByRole('tab', { name: 'Awards', exact: true }).click();
  await expect(view.locator('.gob-awards-conf')).toHaveAttribute('data-conference', '2');
});

test('from week 27 All-Conference is final while All-Americans are still projected', async ({ page }) => {
  await openAwards(page, finalConferenceBody());
  const view = page.locator('#awards-view');
  await expect(view.locator('.gob-awards-head').first().locator('h2')).toHaveText('Projected All-Americans');
  await expect(view.locator('.gob-awards-head').first().locator('p')).toContainText('Not final');
  const section = await readSection(page);
  expect(section.title).toBe('All-Conference');
  expect(section.status).toBe('Final');
  // The coin seated rank 3 at PG on the user's conference: shown as the second team, no rank anywhere.
  expect(section.sections[1].rows[0].name).toBe('C6 PG 2');
  expect(section.text).not.toMatch(/\brank\b|Score|Bonus/i);
  await shots(page, 'awards-all-conference-final');
});

test('no All-Conference data: the page is the All-American page alone', async ({ page }) => {
  const body = projectedBody();
  body.all_conference = { status: 'unavailable', conference: null, labels: labels(), conferences: null };
  await stubAuth(page);
  await page.route('**/franchise/awards**', (route) => fulfillJson(route, body));
  await page.route('**/*', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.startsWith('/franchise/awards')) return route.fallback();
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname.startsWith('/franchise/command-center/data')) {
      return fulfillJson(route, { franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 13, season: 1,
        current_season: 1, training_completed: true, session_type: 'in-season', cut_required: false, recruiting_wire: { counts: {} } });
    }
    return fulfillJson(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=awards-view');
  await page.waitForSelector('#awards-view .gob-awards-tbl');
  await expect(page.locator('#awards-view .gob-awards-conf')).toHaveCount(0);
  await expect(page.locator('#awards-view h3')).toHaveCount(3);
});

test('after shots from a real projection', async ({ page }) => {
  // AC_AWARDS_DIR=<dir holding ac-projection.json, a real GET /franchise/awards response>.
  const dir = process.env.AC_AWARDS_DIR || '';
  test.skip(!dir || !SHOTS, 'AC_AWARDS_DIR + AC_SHOTS only');
  const body = JSON.parse(fs.readFileSync(path.join(dir, 'ac-projection.json'), 'utf8'));
  // The same save's command center, so the top strip's week and the block agree.
  const centerPath = path.join(dir, 'ac-command-center.json');
  const center = fs.existsSync(centerPath) ? JSON.parse(fs.readFileSync(centerPath, 'utf8')) : null;
  await openAwards(page, body, center);
  const section = await readSection(page);
  if (center) {
    await expect(page.locator('#fcc-season-label')).toContainText('Week ' + center.week);
    expect(section.status).toBe('After week ' + (Number(center.week) - 1));
  }
  expect(section.buttons.filter((b) => b.on).map((b) => b.key)).toEqual([String(body.all_conference.conference)]);
  expect(section.text).not.toMatch(/Score|Bonus|weight|\brank\b/i);
  await shots(page, 'awards-all-conference-real');
});
