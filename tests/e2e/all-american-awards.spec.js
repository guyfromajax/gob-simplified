// @ts-check
/**
 * News › Awards: "Projected All-Americans" by position, then the final.
 *
 * How the teams are picked is hidden: the page shows no weights, score, rank or bonus.
 * The stubbed bodies below still carry those fields (the stored shape), so the test
 * proves the page draws none of them whatever a server sends.
 *
 * AA_SHOTS_DIR=<dir of week-NN.json from a simulated season> also writes the report
 * shots (reports/all-american/awards-*-1280.png) from those real payloads.
 * TPL_SHOTS=1 writes reports/team-page-links/after-awards-*.png at 1280 and 1920.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-all-american';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OTHER = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const OUT = path.join(__dirname, '../../reports/all-american');
const SHOTS_DIR = process.env.AA_SHOTS_DIR || '';
const HIDDEN_SHOTS = process.env.TPL_SHOTS === '1';
const HIDDEN_OUT = path.join(__dirname, '../../reports/team-page-links');
const COLUMNS = ['Pos', 'Player', 'Yr', 'Team', 'RT'];
const STAT_COLUMNS = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'DEF%'];

function pick(team, position, rank, extra) {
  const mine = team === 'first_team' && position === 'SF';
  return Object.assign({
    player_id: team + '-' + position,
    name: position + ' ' + rank,
    year: 'Senior',
    team_id: mine ? TID : OTHER,
    team_name: mine ? 'Lancaster' : 'Four Corners',
    position,
    rating: 96 - rank * 12,
    rank,
    score: 90.25 - rank * 10,
    components: { attributes: 80, stats: 70, team: 60 },
    games: 12,
    stats: { PTS: 18.4, REB: 6.1, AST: 4, STL: 1.2, BLK: 0.6, 'DEF%': 61 },
  }, extra || {});
}

function teams(extra) {
  const out = {};
  ['first_team', 'second_team', 'third_team'].forEach((key, i) => {
    out[key] = POSITIONS.map((position) => pick(key, position, i + 1, extra && extra(key, position)));
  });
  return out;
}

function projected() {
  return {
    status: 'projected',
    week: 12,
    label: 'After week 12',
    weights: { attributes: 26.3, stats: 70, team: 3.8 },
    stats_basis: 'per_game',
    all_american_teams: teams(),
  };
}

function preseason() {
  const empty = { PTS: null, REB: null, AST: null, STL: null, BLK: null, 'DEF%': null };
  return {
    status: 'projected',
    week: 0,
    label: 'Preseason',
    weights: { attributes: 100, stats: 0, team: 0 },
    stats_basis: 'per_game',
    all_american_teams: teams(() => ({ stats: empty, games: 0 })),
  };
}

function finalBody() {
  return {
    status: 'final',
    label: 'Final',
    stats_basis: 'per_game',
    all_american_teams: teams((key, position) => ({
      rank: key === 'third_team' && position === 'SG' ? 4 : undefined,
      week26_score: 70,
      bonus: key === 'first_team' && position === 'SF'
        ? { team: 10, individual: 5, total: 15 }
        : { team: 0, individual: 0, total: 0 },
    })),
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openAwards(page, body) {
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
      return fulfillJson(route, {
        franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 13, rank: 8,
        season: 1, current_season: 1, training_completed: true, session_type: 'in-season',
        cut_required: false, recruiting_wire: { board_saved_week: 1, counts: {} },
        user_conference: 1, user_region: 'A', team_record: { wins: 10, losses: 2 },
      });
    }
    if (pathname.startsWith('/franchise/awards')) return fulfillJson(route, body);
    if (pathname.startsWith('/franchise/news')) return fulfillJson(route, { stories: [], dispatches: [] });
    return fulfillJson(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
  await page.locator('.rail [data-gob-section="news"]').evaluate((el) => el.click());
  await page.getByRole('tab', { name: 'Awards', exact: true }).evaluate((el) => el.click());
  await expect(page.locator('#awards-view.tab-content.active')).toBeVisible();
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(OUT, name + '-1280.png'), animations: 'disabled' });
}

async function hiddenShots(page, name) {
  if (!HIDDEN_SHOTS) return;
  fs.mkdirSync(HIDDEN_OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.mouse.move(0, 0);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(HIDDEN_OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
}

/** No weights, percentages of the mix, score, rank or bonus anywhere on the page. */
async function expectFormulaHidden(view) {
  await expect(view.locator('table.gob-awards-tbl').first()).toBeVisible();
  const heads = await view.locator('table.gob-awards-tbl thead th').allTextContents();
  expect(heads).not.toContain('Score');
  expect(heads).not.toContain('Bonus');
  expect(heads).not.toContain('Rank');
  await expect(view.locator('.gob-awards-score, .gob-awards-bonus, col.c-score')).toHaveCount(0);
  const text = (await view.innerText()).replace(/\s+/g, ' ');
  expect(text).not.toMatch(/Ratings|Team rank|Stats \d|Score|Bonus|weight|0\u2013100|within the position/i);
  // The only percent signs on the page are the DEF% column and its values.
  const head = await view.locator('.gob-awards-head').innerText();
  expect(head).not.toMatch(/%|\d\s*points/);
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('Awards shows Projected All-Americans by position, and the final after the tournament', async ({ page }) => {
  await openAwards(page, projected());
  const view = page.locator('#awards-view');
  await expect(view.locator('.gob-awards-head h2')).toHaveText('Projected All-Americans');
  // The plain status only: no weight mix under the heading.
  await expect(view.locator('.gob-awards-head p')).toHaveText('After week 12');
  await expectFormulaHidden(view);
  await expect(view.locator('h3')).toHaveText([
    '1st Team All-American', '2nd Team All-American', '3rd Team All-American',
  ]);
  // One player per position on each team, in position order.
  for (let i = 0; i < 3; i += 1) {
    const table = view.locator('table.gob-awards-tbl').nth(i);
    await expect(table.locator('tbody tr')).toHaveCount(5);
    await expect(table.locator('tbody td.gob-awards-pos')).toHaveText(POSITIONS);
  }
  const first = view.locator('table.gob-awards-tbl').first();
  await expect(first.locator('thead th')).toHaveText(COLUMNS.concat(STAT_COLUMNS));
  await expect(first.locator('tbody tr').first().locator('td')).toHaveCount(COLUMNS.length + STAT_COLUMNS.length);
  await expect(view.locator('.gob-awards-note')).toHaveText('Stats are per game, regular season.');
  // Per game to one decimal; the user's row is the navy "yours" row.
  const mine = view.locator('tr.me');
  await expect(mine).toHaveCount(1);
  await expect(mine).toContainText('SF 1');
  await expect(mine).toContainText('18.4');
  await expect(mine).toContainText('4.0');
  await expect(mine).toContainText('61%');
  // The stored score (80.25) is in the stubbed body and not on the page.
  await expect(mine).not.toContainText('80.3');
  await expect(mine).not.toContainText('80.25');
  // RT paints the canonical ramp (84 is an A: blue); the position is neutral.
  const paint = await mine.evaluate((row) => {
    const cells = [...row.children];
    const colour = (el) => getComputedStyle(el).color;
    return { rt: colour(cells[4]), rtText: cells[4].textContent, pos: colour(cells[0]) };
  });
  expect(paint.rtText).toBe('A');
  expect(paint.rt).toBe('rgb(74, 144, 217)');
  expect(paint.pos).toMatch(/^rgba\(255, 255, 255, 0\.6\d*\)$/);
  // No green, orange or gold anywhere on the page: a projection is information.
  const loud = await view.evaluate((root) => [...root.querySelectorAll('*')].filter((el) => {
    const m = getComputedStyle(el).color.match(/(\d+), (\d+), (\d+)/);
    if (!m) return false;
    const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
    const green = g > 200 && r < 120 && b < 120;
    const orange = r > 220 && g > 110 && g < 190 && b < 90;
    return (green || orange) && !/rt-/.test(el.className);
  }).length);
  expect(loud).toBe(0);
  if (!SHOTS_DIR) await shot(page, 'awards-projected-fixture');
  await hiddenShots(page, 'awards-projection');

  // Preseason: no games, so no stat columns rather than six columns of dashes.
  await openAwards(page, preseason());
  await expect(view.locator('.gob-awards-head p')).toHaveText('Preseason');
  await expect(view.locator('table.gob-awards-tbl').first().locator('thead th')).toHaveText(COLUMNS);
  await expectFormulaHidden(view);

  // Week 26 on: the status says the teams can still change.
  await openAwards(page, Object.assign(projected(), { week: 26, label: 'End of regular season' }));
  await expect(view.locator('.gob-awards-head p')).toHaveText(
    'End of regular season \u00b7 Not final: tournament play can still change these'
  );
  await expectFormulaHidden(view);

  // After the National Tournament the same page is the final teams.
  await openAwards(page, finalBody());
  await expect(view.locator('.gob-awards-head h2')).toHaveText('All-Americans');
  await expect(view.locator('.gob-awards-head p')).toHaveText('Final');
  await expect(view).not.toContainText('Projected');
  await expect(view.locator('table.gob-awards-tbl').first().locator('thead th')).toHaveText(COLUMNS.concat(STAT_COLUMNS));
  await expect(view.locator('tr.me')).not.toContainText('+15');
  await expectFormulaHidden(view);
  await hiddenShots(page, 'awards-final');
  for (let i = 0; i < 3; i += 1) {
    await expect(view.locator('table.gob-awards-tbl').nth(i).locator('tbody td.gob-awards-pos')).toHaveText(POSITIONS);
  }

  // Nothing to show yet reads as the one empty state.
  await openAwards(page, { status: 'unavailable', all_american_teams: null });
  await expect(view.locator('.gob-empty')).toHaveText('Awards are not available yet.');
});

test('after shots from a real projection', async ({ page }) => {
  // TPL_AWARDS_DIR=<dir holding projection.json, a real GET /franchise/awards response>.
  const dir = process.env.TPL_AWARDS_DIR || '';
  test.skip(!dir || !HIDDEN_SHOTS, 'TPL_AWARDS_DIR + TPL_SHOTS only');
  await openAwards(page, JSON.parse(fs.readFileSync(path.join(dir, 'projection.json'), 'utf8')));
  await expectFormulaHidden(page.locator('#awards-view'));
  await hiddenShots(page, 'awards-projection-real');
});

test('report shots from a simulated season', async ({ page }) => {
  test.skip(!SHOTS_DIR, 'AA_SHOTS_DIR only');
  const load = (week) => JSON.parse(fs.readFileSync(path.join(SHOTS_DIR, 'week-' + String(week).padStart(2, '0') + '.json'), 'utf8')).awards;
  for (const [week, name] of [[1, 'awards-preseason'], [11, 'awards-week-10'], [27, 'awards-week-26'], [35, 'awards-final']]) {
    await openAwards(page, load(week));
    await expect(page.locator('#awards-view table.gob-awards-tbl').first()).toBeVisible();
    await shot(page, name);
    await page.locator('html.gob-shell .main').evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await shot(page, name + '-lower');
  }
});
