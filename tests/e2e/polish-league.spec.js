const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 240000 });

const FID = 'f-e2e-polish-league';
const OUT = path.join(__dirname, '../../reports/polish-league');
const SHOTS = process.env.POLISH_SHOTS === '1';
const NAVY_ROW = 'rgb(28, 42, 82)';
const STATS = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];
const FIRST = ['Jalen', 'Marcus', 'Devin', 'Tyrese', 'Isaiah', 'Caleb', 'Andre', 'Miles', 'Jordan', 'Elijah', 'Darius', 'Owen'];
const LAST = ['Carter', 'Brooks', 'Hayes', 'Mitchell', 'Reed', 'Bennett', 'Coleman', 'Price', 'Warren', 'Foster', 'Hughes', 'Sullivan'];

function rng(seed) {
  let s = seed >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function hexId(i) {
  return ('a' + String(i).padStart(3, '0')).padEnd(24, 'e');
}

function buildLeague() {
  const base = JSON.parse(fs.readFileSync(path.join(__dirname, '../../base_league.json'), 'utf8'));
  const rand = rng(29);
  const teams = base.collections.teams.map(function (team, i) {
    return {
      team_id: hexId(i),
      name: team.name,
      region: team.region,
      conference: team.conference,
      primary_color: team.primary_color,
      prestige: Number(team.prestige) || 0,
    };
  });
  teams.sort(function (a, b) { return b.prestige - a.prestige || a.name.localeCompare(b.name); });
  teams.forEach(function (team, i) {
    team.natl_rank = i + 1;
    const strength = 1 - i / teams.length;
    team.W = Math.max(0, Math.min(12, Math.round(strength * 10 + rand() * 3)));
    team.L = 12 - team.W;
    team.PF = Math.round(900 + strength * 120 + rand() * 40);
    team.PA = Math.round(900 + (1 - strength) * 110 + rand() * 40);
  });
  const user = teams.find(function (team) { return team.name === 'Lancaster'; }) || teams[40];
  return { teams: teams, user: user, rand: rand };
}

const LEAGUE = buildLeague();
const TID = LEAGUE.user.team_id;
const BY_ID = {};
LEAGUE.teams.forEach(function (team) { BY_ID[team.team_id] = team; });

function opponentOf(team, offset) {
  const pool = LEAGUE.teams.filter(function (other) { return other.conference === team.conference && other !== team; });
  return pool[offset % pool.length];
}

function rankings() {
  return LEAGUE.teams.map(function (team, i) {
    const last = opponentOf(team, 1);
    const next = opponentOf(team, 2);
    const won = i % 3 !== 2;
    const us = 62 + (i % 17);
    const them = won ? us - 3 - (i % 9) : us + 4 + (i % 7);
    return {
      team_id: team.team_id,
      natl_rank: team.natl_rank,
      team_name: team.name,
      primary_color: team.primary_color,
      conference: team.conference,
      W: team.W,
      L: team.L,
      PF: team.PF,
      PA: team.PA,
      last_week: (i % 2 ? '@ ' : 'vs ') + last.name + ', ' + us + '-' + them,
      last_week_result: won ? 'W' : 'L',
      next: (i % 2 ? 'vs ' : '@ ') + next.name,
    };
  });
}

function standings() {
  return {
    standings: LEAGUE.teams.map(function (team, i) {
      const next = opponentOf(team, 2);
      return {
        team_id: team.team_id,
        name: team.name,
        display_name: team.name,
        region: team.region,
        conference: team.conference,
        W: team.W,
        L: team.L,
        pct: team.W / 12,
        PF: team.PF,
        PA: team.PA,
        differential: team.PF - team.PA,
        streak: (i % 3 ? 'W' : 'L') + (1 + (i % 4)),
        natl_rank: team.natl_rank,
        next_opponent_id: next.team_id,
        next_opponent_name: next.name,
        next_week: 13,
        next_site: 'vs',
      };
    }),
    user_conference: LEAGUE.user.conference,
    user_region: LEAGUE.user.region,
  };
}

function leaders(limit, scope) {
  const pool = scope === 'conference'
    ? LEAGUE.teams.filter(function (team) { return team.conference === LEAGUE.user.conference; })
    : LEAGUE.teams;
  const body = {};
  STATS.forEach(function (stat, s) {
    const rows = [];
    for (let i = 0; i < limit; i += 1) {
      const team = pool[(i * 3 + s) % pool.length];
      const mine = i === 3 && s % 2 === 0;
      const rate = stat === 'FG%' || stat === 'DEF%';
      const total = stat === '3PTM' || stat === 'BLK' || stat === 'STL';
      rows.push({
        player_id: stat + '-p' + i,
        name: FIRST[(i + s) % FIRST.length] + ' ' + LAST[(i * 5 + s) % LAST.length],
        team: mine ? LEAGUE.user.name : team.name,
        team_id: mine ? TID : team.team_id,
        position: i % 2 ? 'G' : 'F',
        year: ['FR', 'SO', 'JR', 'SR'][i % 4],
        value: rate ? 58.4 - i * 0.9 : (total ? 44 - i * 2 : 24.6 - i * 0.7),
        qualification_caption: rate ? 'min 5 attempts per team game' : undefined,
      });
    }
    body[stat] = rows;
  });
  return body;
}

function teamStats(scope) {
  const rows = scope === 'conference'
    ? LEAGUE.teams.filter(function (team) { return team.conference === LEAGUE.user.conference; })
    : LEAGUE.teams;
  return {
    teams: rows.map(function (team, i) {
      const fga = 58 + (i % 9);
      const fgm = Math.round(fga * (0.41 + (i % 7) / 100));
      return {
        team: team.name,
        team_id: team.team_id,
        primary_color: team.primary_color,
        natl_rank: team.natl_rank,
        conference: team.conference,
        region: team.region,
        stats: {
          W: team.W, L: team.L, PF: Math.round(team.PF / 12), PA: Math.round(team.PA / 12),
          FGM: fgm, FGA: fga, FG_PCT: Math.round((fgm / fga) * 1000) / 10,
          '3PTM': 7 + (i % 5), '3PTA': 21 + (i % 6), TP_PCT: 33.3 + (i % 8),
          FTM: 11 + (i % 6), FTA: 16 + (i % 5), FT_PCT: 68 + (i % 12),
          DREB: 23 + (i % 5), OREB: 9 + (i % 4), TREB: 32 + (i % 7),
          AST: 13 + (i % 6), F: 15 + (i % 4), TO: 11 + (i % 5), SCR_A: 12 + (i % 4), SCR_PCT: 44 + (i % 10),
          STL: 6 + (i % 4), BLK: 2 + (i % 4), DEF_A: 38 + (i % 9), DEF_PCT: 51 + (i % 9),
        },
      };
    }),
  };
}

function scheduleWeek(week) {
  const shown = week || 12;
  const done = shown < 13;
  const byConference = {};
  LEAGUE.teams.forEach(function (team) {
    (byConference[team.conference] = byConference[team.conference] || []).push(team);
  });
  const games = [];
  Object.keys(byConference).sort(function (a, b) { return a - b; }).forEach(function (conf) {
    const list = byConference[conf].slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    for (let i = 0; i < list.length; i += 2) {
      const away = list[(i + shown) % list.length];
      const home = list[(i + shown + 1) % list.length];
      const n = games.length;
      const awayScore = 58 + ((n * 7 + shown) % 25);
      const homeScore = 58 + ((n * 11 + shown * 3) % 25) + (n % 5 === 0 ? 1 : 0);
      games.push({
        away: { team_id: away.team_id, name: away.name, natl_rank: away.natl_rank, primary_color: away.primary_color },
        home: { team_id: home.team_id, name: home.name, natl_rank: home.natl_rank, primary_color: home.primary_color },
        status: done ? 'complete' : 'scheduled',
        away_score: done ? awayScore : null,
        home_score: done ? (homeScore === awayScore ? homeScore + 2 : homeScore) : null,
        game_id: done ? 'g-' + shown + '-' + n : null,
        is_user: away.team_id === TID || home.team_id === TID,
        tournament_context: null,
      });
    }
  });
  const weeks = [];
  for (let w = 1; w <= 26; w += 1) weeks.push({ week: w, label: 'Week ' + w, enabled: w <= 13 });
  return { week: shown, label: 'Week ' + shown, current_week: 13, weeks: weeks, games: games };
}

function payload() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    user_team_object_id: TID,
    team: LEAGUE.user.name,
    week: 13,
    rank: LEAGUE.user.natl_rank,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 13, counts: {} },
    user_conference: LEAGUE.user.conference,
    user_region: LEAGUE.user.region,
    team_record: { wins: LEAGUE.user.W, losses: LEAGUE.user.L },
    rankings: rankings(),
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, seen) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) { await route.continue(); return; }
    const pathname = url.pathname;
    const search = url.searchParams;
    if (pathname.indexOf('/images/players/') !== -1) {
      await route.fulfill({ status: 404, body: '' });
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: LEAGUE.user.name, display_name: LEAGUE.user.name, object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, payload()); return; }
    if (pathname.startsWith('/franchise/standings')) { await fulfillJson(route, standings()); return; }
    if (pathname.startsWith('/franchise/leaders')) {
      const limit = Number(search.get('limit') || '10');
      const scope = search.get('view_scope') || 'national';
      seen.leaders.push(scope + ':' + limit);
      await fulfillJson(route, leaders(limit, scope));
      return;
    }
    if (pathname.startsWith('/franchise/team-stats')) {
      const scope = search.get('scope') || '';
      seen.teamStats.push(scope || 'national');
      await fulfillJson(route, teamStats(scope));
      return;
    }
    if (pathname.startsWith('/franchise/schedule/week')) {
      const week = search.get('week');
      await fulfillJson(route, scheduleWeek(week ? Number(week) : null));
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openTab(page, tab) {
  await stubAuth(page);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=' + tab);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#' + tab + '.tab-content.active');
}

async function clearKeys(page) {
  await page.evaluate(() => {
    ['gob-view-leaders-scope', 'gob-view-team-stats-scope', 'gob-view-rankings-show-all'].forEach(function (key) {
      sessionStorage.removeItem(key);
    });
  });
}

async function parkPointer(page) {
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + box.width - 12, box.y + box.height - 12);
}

async function assertNoOverflow(page, label) {
  const overflow = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const se = document.scrollingElement;
    return { main: main.scrollWidth - main.clientWidth, page: se.scrollWidth - se.clientWidth };
  });
  expect(overflow.main, label + ' main').toBeLessThanOrEqual(1);
  expect(overflow.page, label + ' page').toBeLessThanOrEqual(1);
  await assertOneVerticalScroll(page);
}

async function shot(page, name, size) {
  if (!SHOTS) return;
  await page.waitForFunction(() => {
    return Array.from(document.querySelectorAll('html.gob-shell .main img')).every(function (img) { return img.complete; });
  }, null, { timeout: 10000 }).catch(function () {});
  await page.waitForTimeout(150);
  await parkPointer(page);
  await page.screenshot({ path: path.join(OUT, name + '-' + size + '.png') });
}

async function toolButton(page, owner, value) {
  return page.locator('#gob-subtabs .pg-tools[data-owner="' + owner + '"] button[data-value="' + value + '"]');
}

test.beforeAll(() => {
  if (SHOTS) fs.mkdirSync(OUT, { recursive: true });
});

for (const size of [[1280, 720], [1920, 1080]]) {
  const tag = String(size[0]);

  test('league polish at ' + tag, async ({ page }) => {
    const seen = { leaders: [], teamStats: [] };
    await installApi(page, seen);
    await page.setViewportSize({ width: size[0], height: size[1] });

    await openTab(page, 'standings-view');
    await clearKeys(page);
    await page.waitForSelector('#standings-view .gob-tbl tbody tr');
    await expect(page.locator('#gob-subtabs .pg-tools .stats-toggle')).toHaveCount(0);
    await expect(page.locator('#gob-subtabs .pg-tools')).not.toContainText(/Conference|Region|National/);
    await expect(page.locator('#standings-view .gob-tcard')).toHaveCount(16);
    await expect(page.locator('#standings-view .gob-tbl tbody tr')).toHaveCount(128);
    await expect(page.locator('#standings-view tr.is-user')).toHaveCount(1);
    await expect(page.locator('#standings-view tr.is-user td').first()).toHaveCSS('background-color', NAVY_ROW);
    await assertNoOverflow(page, 'standings ' + tag);
    await shot(page, 'standings', tag);

    await openTab(page, 'rankings-view');
    await page.waitForSelector('#rankings-table tbody tr');
    const card = page.locator('#rankings-view .gob-tcard');
    await expect(card).toHaveCount(1);
    await expect(card.locator('h2')).toHaveText('National Rankings');
    await expect(page.locator('#rankings-table')).toHaveClass(/gob-tbl/);
    const heads = await page.locator('#rankings-table thead th').allTextContents();
    expect(heads.map(function (text) { return text.trim(); })).toEqual(['#', 'Team', 'W', 'L', 'PF', 'PA', 'Last Week', 'Next']);
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(25);
    await expect(page.locator('#rankings-table thead th').first()).toHaveCSS('position', 'sticky');
    await expect(page.locator('#rankings-toggle-top25')).toHaveClass(/on/);
    await page.locator('#rankings-toggle-all').click();
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(128);
    const mine = page.locator('#rankings-table tbody tr.me.is-user');
    await expect(mine).toHaveCount(1);
    await expect(mine).toContainText(LEAGUE.user.name);
    await expect(mine.locator('td').first()).toHaveText(String(LEAGUE.user.natl_rank));
    await expect(mine.locator('td').first()).toHaveCSS('background-color', NAVY_ROW);
    const otherNavy = await page.evaluate((navy) => {
      return Array.from(document.querySelectorAll('#rankings-table tbody tr:not(.me) td:first-child'))
        .filter(function (td) { return getComputedStyle(td).backgroundColor === navy; }).length;
    }, NAVY_ROW);
    expect(otherNavy).toBe(0);
    await page.locator('#rankings-toggle-top25').click();
    await expect(page.locator('#rankings-table tbody tr')).toHaveCount(25);
    await assertNoOverflow(page, 'rankings ' + tag);
    await shot(page, 'rankings', tag);

    await openTab(page, 'leaders-view');
    await page.waitForSelector('#leaders-view .gob-ldb .ldb-top');
    await (await toolButton(page, 'leaders-view', 'national')).click();
    await expect(await toolButton(page, 'leaders-view', 'national')).toHaveClass(/on/);
    await expect(await toolButton(page, 'leaders-view', 'conference')).not.toHaveClass(/on/);
    await expect(page.locator('#leaders-view .gob-ldb').first().locator('.ldb-r')).toHaveCount(9);
    const national = await page.locator('#leaders-view .gob-ldb').evaluateAll(function (boards) {
      return boards.map(function (board) { return board.querySelectorAll('.ldb-top, .ldb-r').length; });
    });
    expect(national).toEqual([10, 10, 10, 10, 10, 10, 10, 10]);
    expect(seen.leaders).toContain('national:10');
    await assertNoOverflow(page, 'leaders national ' + tag);
    await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
    await shot(page, 'leaders-national', tag);
    await (await toolButton(page, 'leaders-view', 'conference')).click();
    await expect(page.locator('#leaders-view .gob-ldb').first().locator('.ldb-r')).toHaveCount(4);
    const conference = await page.locator('#leaders-view .gob-ldb').evaluateAll(function (boards) {
      return boards.map(function (board) { return board.querySelectorAll('.ldb-top, .ldb-r').length; });
    });
    expect(conference).toEqual([5, 5, 5, 5, 5, 5, 5, 5]);
    expect(seen.leaders).toContain('conference:5');
    await assertNoOverflow(page, 'leaders conference ' + tag);
    await shot(page, 'leaders-conference', tag);

    await openTab(page, 'team-stats-view');
    await page.waitForSelector('#teamstats-body tr');
    await expect(page.locator('#team-stats-view thead tr')).toHaveCount(1);
    await expect(page.locator('#team-stats-view tr.gob-rep, #team-stats-view tr.gob-groups')).toHaveCount(0);
    await expect(page.locator('#team-stats-view .gob-xs, #team-stats-view .gob-wide-wrap')).toHaveCount(0);
    await expect(page.locator('#teamstats-body tr')).toHaveCount(128);
    await assertNoOverflow(page, 'team stats ' + tag);
    await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 1400; });
    await page.waitForTimeout(100);
    const pinned = await page.evaluate(() => {
      const head = document.querySelector('html.gob-shell .pg-head').getBoundingClientRect();
      const th = document.querySelector('#team-stats-view thead th').getBoundingClientRect();
      const main = document.querySelector('html.gob-shell .main');
      return { gap: Math.abs(th.top - head.bottom), scrolled: main.scrollTop, visible: th.bottom > head.bottom };
    });
    expect(pinned.scrolled).toBeGreaterThan(1000);
    expect(pinned.gap).toBeLessThanOrEqual(1);
    expect(pinned.visible).toBe(true);
    await expect(page.locator('#team-stats-view tr.me.is-user td').first()).toHaveCSS('background-color', NAVY_ROW);
    await shot(page, 'team-stats-scrolled', tag);
    await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
    await (await toolButton(page, 'team-stats-view', 'conference')).click();
    await expect(await toolButton(page, 'team-stats-view', 'conference')).toHaveClass(/on/);
    await expect(page.locator('#teamstats-body tr')).toHaveCount(8);
    expect(seen.teamStats).toContain('conference');
    await expect(page.locator('#teamstats-body tr.is-user')).toHaveCount(1);
    await (await toolButton(page, 'team-stats-view', 'national')).click();
    await expect(page.locator('#teamstats-body tr')).toHaveCount(128);

    await openTab(page, 'league-schedule-view');
    await page.waitForSelector('#league-schedule-view .gob-game');
    await expect(page.locator('.gob-wk-label')).toHaveText('Week 12');
    await expect(page.locator('#league-schedule-view .gob-game')).toHaveCount(64);
    const grid = await page.evaluate(() => {
      const node = document.querySelector('#league-schedule-view .gob-lgrid');
      const tops = {};
      Array.from(node.children).slice(0, 8).forEach(function (card) {
        const top = Math.round(card.getBoundingClientRect().top);
        tops[top] = (tops[top] || 0) + 1;
      });
      return {
        columns: getComputedStyle(node).gridTemplateColumns.split(' ').length,
        firstRow: tops[Object.keys(tops).sort(function (a, b) { return a - b; })[0]],
        over: node.scrollWidth - node.clientWidth,
      };
    });
    expect(grid.columns).toBe(4);
    expect(grid.firstRow).toBe(4);
    expect(grid.over).toBeLessThanOrEqual(1);
    const ranks = await page.locator('#league-schedule-view .gob-gs .rk').allTextContents();
    expect(ranks.length).toBeGreaterThan(0);
    ranks.forEach(function (text) {
      const n = Number(text);
      expect(n >= 1 && n <= 25, 'rank ' + text).toBe(true);
    });
    const unranked = await page.evaluate((byId) => {
      return Array.from(document.querySelectorAll('#league-schedule-view .gob-gs')).filter(function (line) {
        const link = line.querySelector('a.gob-team');
        const id = link ? new URL(link.href).searchParams.get('view_team_id') : '';
        const team = byId[id];
        return team && team.natl_rank > 25 && line.querySelector('.rk');
      }).length;
    }, BY_ID);
    expect(unranked).toBe(0);
    const clipped = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#league-schedule-view .gob-game')).filter(function (card) {
        return card.scrollWidth > card.clientWidth + 1;
      }).length;
    });
    expect(clipped).toBe(0);
    const yours = page.locator('#league-schedule-view .gob-game.me');
    await expect(yours).toHaveCount(1);
    await expect(yours).toContainText(LEAGUE.user.name);
    const navy = await yours.evaluate(function (node) { return getComputedStyle(node).backgroundColor; });
    const plain = await page.locator('#league-schedule-view .gob-game:not(.me)').first()
      .evaluate(function (node) { return getComputedStyle(node).backgroundColor; });
    expect(navy).not.toBe(plain);
    await expect(yours.locator('.gob-box')).toHaveAttribute('href', /game_id=g-12-/);
    await assertNoOverflow(page, 'league schedule ' + tag);
    await shot(page, 'league-schedule', tag);
  });
}
