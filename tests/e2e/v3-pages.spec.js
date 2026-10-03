// @ts-check
/**
 * Final polish round (v3 pages):
 *  - Player page: the Recent changes week sits inside the card, clear of its border; the
 *    hero's season line is two stacked rows (PTS REB AST over FG% 3PT% FT% DEF%).
 *  - Team › Schedule: every score is fully visible inside its card at 1280, 1920 and 2000.
 *  - A practice squad opens on the standard team page; what a squad has no data for is
 *    left out.
 * V3_SHOTS=1 writes reports/v3-pages/after-*.png.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.V3_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/v3-pages');
const FID = 'f-e2e-v3';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SQUAD = 'ps_C_3';

const TEAMS = [
  'Cagers World', 'Chapel Hill', 'Little York', 'South Lancaster', 'Four Corners', 'Myrtle Private',
  'Durham', 'Crickstown', 'IDA', 'Xavien', 'Bentley-Truman', 'Nickel Beach', 'San Bernardino Valley State',
];

function cc() {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 12, rank: 4,
    season: 1, current_season: 1, training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 12, counts: {}, events: [] },
    user_conference: 1, user_region: 'A', team_record: '8-3',
  };
}

function opponent(week) {
  const name = TEAMS[(week - 1) % TEAMS.length];
  return {
    week, site: week % 2 ? 'home' : 'away', opponent_id: 'b' + String(week).padStart(23, '0'),
    opponent_name: name, opponent_primary_color: '#778899',
    // Ranked opponents carry the "#N " prefix: the longest names the column has to hold.
    opponent_natl_rank: week % 3 === 0 ? week : 80, opponent_wins: 7, opponent_losses: 4,
  };
}

function teamDetail() {
  // Three-digit scores on both sides: the widest result the column ever shows.
  const results = [];
  for (let week = 1; week <= 11; week += 1) {
    const won = week % 3 !== 0;
    results.push(Object.assign({
      team_score: won ? 100 + week : 98, opp_score: won ? 99 : 100 + week,
      result: won ? 'W' : 'L', game_id: 'g-' + week,
    }, opponent(week)));
  }
  const upcoming = [];
  for (let week = 13; week <= 26; week += 1) upcoming.push(opponent(week));
  return { team_id: TID, name: 'Lancaster', next_game: opponent(12), results, upcoming };
}

function playerDetail() {
  return {
    player_id: 'p1', name: 'Ervin Miller', team_id: TID, team_name: 'Lancaster', is_user_team: true,
    team_primary_color: '#c8532a', position: 'PG', year: 'SO', jersey: 5, height_in: 69, weight: 161,
    rt: 78, potential: 88,
    season: { gp: 9, pts_per_game: 21.8, reb_per_game: 10.3, ast_per_game: 11, fg_pct: 100, tp_pct: 40, ft_pct: 85.7, def_pct: 69.2 },
    career: { gp: 9, pts_per_game: 21.8, reb_per_game: 10.3, ast_per_game: 11, fg_pct: 100, tp_pct: 40, ft_pct: 85.7, def_pct: 69.2 },
    attributes: [
      { label: 'Offense', attrs: [{ attr: 'SC', display: 2 }, { attr: 'SH', display: 3 }] },
      { label: 'Defense', attrs: [{ attr: 'ID', display: 2 }, { attr: 'OD', display: 6 }] },
    ],
    recent_changes: [
      { week: 11, changes: [{ attr: 'RB', from: 2, to: 1 }, { attr: 'IQ', from: 6, to: 5 }] },
      { week: 3, changes: [{ attr: 'PS', from: 5, to: 4 }] },
    ],
    development: { focus: 'standard', focus_label: 'Standard', editable: false, emphasises: [] },
  };
}

function squadPlayer(id, name, source, parent, gp) {
  return {
    player_id: id, source, name, parent_team_name: parent, year: 'FR', height: 76, weight: 190,
    portrait_source: source === 'frd' ? 'recruit' : 'player', image_id: source === 'frd' ? 'img-77' : null,
    position_ratings: { PG: 61, SG: 66, SF: 70, PF: 58, C: 50 }, potential_rt_ratcheted: 80,
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    rt: 70, position: 'SF', starter: source === 'fpd', lineup_order: source === 'fpd' ? 0 : null,
    per_game: { GP: gp, MIN: gp ? 20 : null, PTS: gp ? 11.5 : null, REB: gp ? 4 : null, AST: gp ? 2 : null },
    totals: { GP: gp, MIN: gp * 20, PTS: gp * 11.5, REB: gp * 4, AST: gp * 2 },
    rates: { fg_pct: gp ? 45 : null, tp_pct: gp ? 33.3 : null, ft_pct: gp ? 70 : null, def_pct: gp ? 50 : null },
  };
}

function squadBody(kind) {
  const played = kind !== 'new';
  const game = (week, site, opp, mine, theirs, extra) => Object.assign({
    week, site, opponent_id: 'ps_' + opp + '_3', opponent_name: 'Region ' + opp + ' Varsity',
  }, mine == null ? {} : {
    team_score: mine, opp_score: theirs, result: mine > theirs ? 'W' : 'L', forfeit: false, game_id: 'ps-g-' + week,
  }, extra || {});
  return {
    team: { display_name: 'Region C Varsity', tier: 3, region: 'C' },
    players: [
      squadPlayer('p-ps-1', 'Casey Lane', 'fpd', 'Lancaster', played ? 6 : 0),
      squadPlayer('r-ps-2', 'Drew Park', 'frd', null, played ? 6 : 0),
    ].concat(kind !== 'programs' ? [] : [
      // The longest program name in the league, under a long player name.
      squadPlayer('p-ps-3', 'Maximilian Featherstonehaugh', 'fpd', 'San Bernardino Valley State', 6),
      squadPlayer('r-ps-4', 'Al Wu', 'frd', null, 6),
    ]),
    projected_starting_five: [],
    page: {
      team_id: SQUAD, name: 'Region C Varsity', practice_squad: true, tier: 3, tier_label: 'Varsity', region: 'C',
      record: { wins: played ? 4 : 0, losses: played ? 2 : 0 }, tier_place: played ? '2nd of 8' : '1st of 8',
      results: played ? [game(2, 'home', 'A', 70, 61), game(3, 'away', 'B', 55, 64)] : [],
      upcoming: kind === 'new' ? [] : [game(9, 'home', 'D')],
      next_game: kind === 'new' ? null : game(9, 'home', 'D'),
    },
  };
}

function squadStandings() {
  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].map((letter, index) => ({
    team_id: 'ps_' + letter + '_3', name: 'Region ' + letter + ' Varsity', w: 8 - index, l: index,
    win_pct: 0.5, is_user: letter === 'C',
  }));
  return { initialized: true, week: 12, tiers: [{ tier: '3', label: 'Varsity', rows }], teams: {} };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function install(page, state) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let url;
    try { url = new URL(route.request().url()); } catch (err) { return route.continue(); }
    const pathname = url.pathname;
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/command-center/data')) return fulfillJson(route, cc());
    if (pathname.startsWith('/franchise/team-detail')) return fulfillJson(route, teamDetail());
    if (pathname.startsWith('/franchise/player-detail')) return fulfillJson(route, playerDetail());
    if (pathname.startsWith('/franchise/practice-squad/team')) {
      state.squadReads.push(url.searchParams.get('ps_team_id'));
      return fulfillJson(route, squadBody(state.squad));
    }
    if (pathname.startsWith('/franchise/practice-squad/standings')) return fulfillJson(route, squadStandings());
    if (pathname.startsWith('/franchise/practice-squad/schedule')) {
      return fulfillJson(route, { initialized: true, week: 12, current_week: 12, weeks: [2, 3], games: [] });
    }
    if (pathname.startsWith('/franchise/practice-squad/brackets')) {
      return fulfillJson(route, { initialized: true, week: 12, tournaments: {}, championship: {}, teams: {} });
    }
    return fulfillJson(route, {});
  });
}

async function open(page, search, width, height) {
  await page.setViewportSize({ width, height });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&' + search);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function shot(page, name) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(700, 4);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, name), animations: 'disabled' });
}

const SIZES = [[1280, 720], [1920, 1080], [2000, 1100]];

for (const [width, height] of SIZES) {
  test('Schedule: every score is fully visible inside its card at ' + width, async ({ page }) => {
    await install(page, { squad: 'played', squadReads: [] });
    await open(page, 'tab=team-schedule-view', width, height);
    await expect(page.locator('#team-schedule-view a.gob-res')).toHaveCount(11);
    const seen = await page.evaluate(() => {
      return [...document.querySelectorAll('#team-schedule-view td.res')].filter((td) => td.textContent.trim()).map((td) => {
        const card = td.closest('.gob-schcol').getBoundingClientRect();
        const cell = td.getBoundingClientRect();
        const link = td.querySelector('a.gob-res');
        const range = document.createRange();
        range.selectNodeContents(link || td);
        const text = range.getBoundingClientRect();
        const team = td.parentElement.querySelector('td.team a.gob-team').getBoundingClientRect();
        // The pixel at each end of the score belongs to the score, not to something over it.
        const mid = text.top + text.height / 2;
        const hits = [text.left + 1, text.right - 1].map((x) => {
          const el = document.elementFromPoint(x, mid);
          return !!(el && td.contains(el));
        });
        return {
          text: td.textContent.trim(),
          leftInside: text.left - card.left, rightInside: card.right - text.right,
          cellClip: td.scrollWidth - td.clientWidth,
          overlapTeam: team.right - text.left,
          inCell: text.left >= cell.left - 0.5 && text.right <= cell.right + 0.5,
          hits,
        };
      });
    });
    expect(seen.length).toBe(11);
    seen.forEach((row) => {
      const note = JSON.stringify(row);
      expect(row.text, note).toMatch(/^[WL] \d+-\d+$/);
      // Clear of the card's border on both sides, and of the team name to its left.
      expect(row.rightInside, note).toBeGreaterThanOrEqual(8);
      expect(row.leftInside, note).toBeGreaterThanOrEqual(8);
      expect(row.cellClip, note).toBeLessThanOrEqual(0);
      expect(row.inCell, note).toBe(true);
      expect(row.overlapTeam, note).toBeLessThanOrEqual(0);
      expect(row.hits, note).toEqual([true, true]);
    });
    // The long name gives way, the page does not scroll sideways.
    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth - main.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(0);
    await shot(page, 'after-schedule-' + width + '.png');
  });
}

for (const [width, height] of SIZES.slice(0, 2)) {
  test('Player page: week clear of the card border, stats in two stacked rows at ' + width, async ({ page }) => {
    await install(page, { squad: 'played', squadReads: [] });
    await open(page, 'tab=player-view&player_id=p1&origin=team', width, height);
    await expect(page.locator('#player-view .gob-chg')).toHaveCount(3);
    const seen = await page.evaluate(() => {
      const card = [...document.querySelectorAll('#player-view .gob-tcard')].find((c) => /Recent changes/.test(c.textContent));
      const box = card.getBoundingClientRect();
      const weeks = [...card.querySelectorAll('.gob-chg em')].map((em) => {
        const r = em.getBoundingClientRect();
        return { text: em.textContent, gap: box.right - r.right };
      });
      const names = [...card.querySelectorAll('.gob-chg > span')].map((el) => el.getBoundingClientRect().left - box.left);
      const head = card.querySelector('.card-h h3').getBoundingClientRect().left - box.left;
      const portrait = document.querySelector('#player-view .gob-portrait').getBoundingClientRect();
      const rows = [...document.querySelectorAll('#player-view .gob-hero .gob-hs-rows > .gob-hs')].map((row) => {
        return [...row.children].map((cell) => {
          const r = cell.getBoundingClientRect();
          return { label: cell.querySelector('span').textContent, value: cell.querySelector('b').textContent, top: Math.round(r.top), left: Math.round(r.left), right: Math.round(r.right) };
        });
      });
      const hero = document.querySelector('#player-view .gob-hero').getBoundingClientRect();
      return { weeks, names, head, rows, portraitRight: portrait.right, heroRight: hero.right, text: document.querySelector('#player-view').innerText };
    });
    // 2a. Every week label keeps the card's padding from the border; so do the row names and the heading.
    expect(seen.weeks.map((w) => w.text)).toEqual(['Wk 11', 'Wk 11', 'Wk 3']);
    seen.weeks.forEach((w) => expect(w.gap, JSON.stringify(w)).toBeGreaterThanOrEqual(12));
    seen.names.forEach((gap) => expect(gap).toBeGreaterThanOrEqual(12));
    expect(seen.head).toBeGreaterThanOrEqual(12);
    // 2b. Two rows, in this order, each on one line, the second under the first, right of the headshot.
    expect(seen.rows.map((row) => row.map((c) => c.label))).toEqual([['PTS', 'REB', 'AST'], ['FG%', '3PT%', 'FT%', 'DEF%']]);
    expect(seen.rows[0].map((c) => c.value)).toEqual(['21.8', '10.3', '11.0']);
    seen.rows.forEach((row) => {
      expect(new Set(row.map((c) => c.top)).size).toBe(1);
      row.forEach((c, i) => {
        if (i) expect(c.left).toBeGreaterThanOrEqual(row[i - 1].right);
        expect(c.left).toBeGreaterThan(seen.portraitRight);
        expect(c.right).toBeLessThanOrEqual(seen.heroRight);
      });
    });
    expect(seen.rows[1][0].top).toBeGreaterThan(seen.rows[0][0].top + 20);
    // The two rows share their columns: FG% under PTS, 3PT% under REB, FT% under AST.
    [0, 1, 2].forEach((i) => expect(seen.rows[1][i].left).toBe(seen.rows[0][i].left));
    expect(seen.text).not.toMatch(/\bCH\b/);
    await shot(page, 'after-player-' + width + '.png');
  });
}

test('Practice squad: opens on the standard team page, with only what a squad has', async ({ page }) => {
  const state = { squad: 'played', squadReads: [] };
  const portraitRequests = [];
  page.on('request', (request) => { if (/\.png(\?|$)/.test(request.url())) portraitRequests.push(request.url()); });
  await install(page, state);
  await open(page, 'tab=practice-squad-view', 1280, 720);
  // From the Practice Squads table, the squad's name opens the team page in the shell.
  await page.locator('#practice-squad-view a', { hasText: 'Region C Varsity' }).first().click();
  await expect(page).toHaveURL(/franchise-command-center\.html/);
  await expect(page).toHaveURL(/tab=team-view/);
  await expect(page).toHaveURL(new RegExp('ps_team_id=' + SQUAD));
  await expect(page).not.toHaveURL(/team-roster-view|mode=practice_squad|view_team_id=/);
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Region C Varsity');
  expect(state.squadReads).toContain(SQUAD);

  const seen = await page.evaluate((state) => {
    const root = document.querySelector('#team-view');
    const text = (sel) => [...root.querySelectorAll(sel)].map((el) => el.textContent.trim());
    return {
      eyebrow: text('.gob-hero-k')[0],
      bio: text('.gob-hero-bio')[0],
      stats: text('.gob-hero .gob-hs span'),
      values: text('.gob-hero .gob-hs b'),
      scout: root.querySelectorAll('.gob-scout').length,
      cards: text('.gob-card-head h2').map((t) => t.replace(/\d.*$/, '').trim()),
      modes: text('.gob-team-mode button'),
      heads: text('.gob-team-roster-body thead tr:not(.gob-groups) th'),
      separators: text('.gob-team-roster-body tr.gob-sep'),
      players: text('.gob-team-roster-body a.gob-player .gob-id > span:first-child'),
      crumb: text('.gob-dt-crumb')[0],
      up: text('.gob-dt-up')[0],
      rail: [...document.querySelectorAll('.rail [data-gob-section].active, .rail [data-gob-section][aria-current]')].map((el) => el.getAttribute('data-gob-section')),
      subs: [...root.querySelectorAll('.gob-sch-split h3')].map((el) => el.textContent.trim()),
      results: text('.gob-sch-list .gob-sch-res'),
      opponents: [...root.querySelectorAll('.gob-sch-list a.gob-team')].map((a) => a.getAttribute('href')),
      boxes: [...root.querySelectorAll('.gob-sch-list a.gob-sch-res')].map((a) => a.getAttribute('href')),
      playerLinks: [...root.querySelectorAll('.gob-team-roster-body a.gob-player')].map((a) => a.getAttribute('href')),
      portraits: state.portraits,
      all: root.innerText,
    };
  }, { portraits: portraitRequests });
  // The signed player's portrait is asked for by player id, the recruit's by image id.
  expect(seen.portraits.some((u) => /players\/p-ps-1\.png/.test(u)), seen.portraits.join(' ')).toBe(true);
  expect(seen.portraits.some((u) => /img-77\.png/.test(u)), seen.portraits.join(' ')).toBe(true);
  expect(seen.portraits.some((u) => /r-ps-2\.png/.test(u)), seen.portraits.join(' ')).toBe(false);
  expect(seen.eyebrow).toBe('Practice Squad · Varsity');
  expect(seen.bio).toBe('Next · vs Region D Varsity · Week 9');
  // The hero keeps Record and Standing. No national rank, conference or streak.
  expect(seen.stats).toEqual(['Record', 'Standing']);
  expect(seen.values).toEqual(['4–2', '2nd of 8']);
  expect(seen.scout).toBe(0);
  expect(seen.cards).toEqual(['Roster', 'Schedule']);
  // Both roster tabs have data, so both stay.
  expect(seen.modes).toEqual(['Attributes', 'Stats']);
  expect(seen.heads).not.toContain('Dev focus');
  expect(seen.heads.slice(0, 6)).toEqual(['Player', 'RT', 'POS', 'YR', 'HT', 'WT']);
  // The projected five are the Starters, as on any team page.
  expect(seen.separators).toEqual(['Starters', 'Bench']);
  expect(seen.players).toEqual(['Casey Lane', 'Drew Park']);
  expect(seen.up).toBe('← Practice Squads');
  expect(seen.crumb).toContain('League');
  expect(seen.subs).toEqual(['Results', 'Upcoming']);
  expect(seen.results).toEqual(['W 70–61', 'L 55–64']);
  seen.opponents.forEach((href) => {
    expect(href).toMatch(/tab=team-view/);
    expect(href).toMatch(/ps_team_id=ps_[A-H]_3/);
    expect(href).not.toMatch(/view_team_id=/);
  });
  seen.boxes.forEach((href) => expect(href).toMatch(/mode=practice_squad/));
  // A signed player has a player page; an unsigned recruit has the recruit page.
  expect(seen.playerLinks[0]).toMatch(/tab=player-view/);
  expect(seen.playerLinks[0]).toMatch(/player_id=p-ps-1/);
  expect(seen.playerLinks[0]).not.toMatch(/ps_team_id=/);
  expect(seen.playerLinks[1]).toMatch(/^\/player-detail\.html\?recruit_id=r-ps-2/);
  expect(seen.all).not.toMatch(/\bCH\b/);
  expect(seen.all).not.toMatch(/National|Conference|Streak|undefined|NaN|--/);
  await shot(page, 'after-practice-squad-team-1280.png');

  // Stats: the squad's own season lines, no second request for varsity stats.
  await page.locator('#team-view .gob-team-mode button', { hasText: 'Stats' }).click();
  await expect(page.locator('#team-view .gob-team-roster-body tbody tr')).toHaveCount(2);
  await expect(page.locator('#team-view .gob-team-roster-body')).toContainText('11.5');
  await shot(page, 'after-practice-squad-team-stats-1280.png');
  await page.locator('#team-view .gob-team-mode button', { hasText: 'Attributes' }).click();

  // An opponent in the schedule is another squad on the same page; Back returns here.
  await page.locator('#team-view .gob-sch-list a.gob-team').first().click();
  await expect(page).toHaveURL(/ps_team_id=ps_A_3/);
  expect(state.squadReads).toContain('ps_A_3');
  await page.goBack();
  await expect(page).toHaveURL(new RegExp('ps_team_id=' + SQUAD));
  // Up returns to the Practice Squads table, and the squad does not ride along.
  await page.locator('#team-view .gob-dt-up').click();
  await expect(page.locator('#practice-squad-view.tab-content.active')).toHaveCount(1);
  await expect(page).not.toHaveURL(/ps_team_id=/);
  await page.locator('[data-gob-section="team"]').evaluate((el) => el.click());
  await expect(page).not.toHaveURL(/ps_team_id=/);
});

test('Practice squad at 1920, and an old link lands on the same page', async ({ page }) => {
  const state = { squad: 'played', squadReads: [] };
  await install(page, state);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/team-roster-view.html?mode=practice_squad&ps_team_id=' + SQUAD + '&franchise_id=' + FID + '&team_id=' + TID
    + '&return_url=' + encodeURIComponent('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=practice-squad-view'));
  await expect(page).toHaveURL(/franchise-command-center\.html/);
  await expect(page).toHaveURL(/tab=team-view/);
  await expect(page).toHaveURL(new RegExp('ps_team_id=' + SQUAD));
  await expect(page).not.toHaveURL(/mode=practice_squad|return_url=/);
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Region C Varsity');
  await expect(page.locator('#team-view .gob-hero .gob-hs span')).toHaveText(['Record', 'Standing']);
  const overflow = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    return main.scrollWidth - main.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(0);
  await shot(page, 'after-practice-squad-team-1920.png');
});

test('Practice squad before its first game: no Stats tab and no Schedule card', async ({ page }) => {
  const state = { squad: 'new', squadReads: [] };
  await install(page, state);
  // The reader last left a team page on Stats; a squad with no games still opens on Attributes.
  await page.addInitScript(() => { try { sessionStorage.setItem('gob-view-team-roster-mode', 'stats'); } catch (err) { /* default */ } });
  await open(page, 'tab=team-view&ps_team_id=' + SQUAD + '&origin=league&return_tab=practice-squad-view', 1280, 720);
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Region C Varsity');
  await expect(page.locator('#team-view .gob-team-mode')).toHaveCount(0);
  await expect(page.locator('#team-view .gob-team-sched')).toHaveCount(0);
  await expect(page.locator('#team-view .gob-card-head h2')).toHaveCount(1);
  await expect(page.locator('#team-view .gob-team-roster-body a.gob-player')).toHaveCount(2);
  await expect(page.locator('#team-view .gob-team-roster-body thead')).toContainText('SC');
  await expect(page.locator('#team-view .gob-hero .gob-hs b').first()).toHaveText('0–0');
  await shot(page, 'after-practice-squad-team-new-1280.png');
});

test('a varsity team page is unchanged: four hero stats, both cards, lineup order', async ({ page }) => {
  await install(page, { squad: 'played', squadReads: [] });
  await open(page, 'tab=team-view&view_team_id=' + TID + '&origin=team', 1280, 720);
  await expect(page.locator('#team-view .gob-hero .gob-hs span')).toHaveText(['Record', 'National', 'Conference', 'Streak']);
  await expect(page.locator('#team-view .gob-card-head h2')).toHaveCount(2);
  await expect(page.locator('#team-view .gob-team-mode button')).toHaveText(['Attributes', 'Stats']);
});

// ── The parent program under a signed player's name (v3 pages 2) ─────────────────
const SHOTS2 = process.env.V32_SHOTS === '1';
const OUT2 = path.join(__dirname, '../../reports/v3-pages-2');

async function shot2(page, name) {
  if (!SHOTS2) return;
  fs.mkdirSync(OUT2, { recursive: true });
  await page.mouse.move(700, 4);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT2, name), animations: 'disabled' });
}

function readNameCells(page) {
  return page.evaluate(() => {
    const body = document.querySelector('#team-view .gob-team-roster-body');
    const rows = [...body.querySelectorAll('tbody tr')].filter((tr) => tr.querySelector('a.gob-player'));
    return {
      marked: !!body.querySelector('.gob-roster.has-program'),
      rows: rows.map((tr) => {
        const link = tr.querySelector('a.gob-player');
        const id = link.querySelector('.gob-id');
        const name = id ? id.querySelector(':scope > span:first-child') : link.querySelector(':scope > span:last-child');
        const line = id ? id.querySelector('.sub') : null;
        const cell = link.closest('td').getBoundingClientRect();
        const fits = (el) => !el || (el.scrollWidth <= el.clientWidth && el.getBoundingClientRect().right <= cell.right + 0.5);
        const style = line ? getComputedStyle(line) : null;
        return {
          name: name.textContent,
          line: line ? line.textContent : null,
          height: Math.round(tr.getBoundingClientRect().height * 10) / 10,
          fits: fits(name) && fits(line),
          below: line ? line.getBoundingClientRect().top >= name.getBoundingClientRect().bottom - 1 : null,
          quiet: style ? style.color !== getComputedStyle(name).color && parseFloat(style.fontSize) < parseFloat(getComputedStyle(name).fontSize) : null,
        };
      }),
    };
  });
}

for (const [width, height] of SIZES.slice(0, 2)) {
  test('Practice squad roster: the parent program under a signed player\'s name at ' + width, async ({ page }) => {
    await install(page, { squad: 'programs', squadReads: [] });
    await open(page, 'tab=team-view&ps_team_id=' + SQUAD + '&origin=league&return_tab=practice-squad-view', width, height);
    await expect(page.locator('#team-view .gob-team-roster-body a.gob-player')).toHaveCount(4);

    // Attributes: the program is the second line; a recruit has none.
    const attrs = await readNameCells(page);
    const byName = (seen) => Object.fromEntries(seen.rows.map((row) => [row.name, row]));
    expect(attrs.marked).toBe(true);
    expect(byName(attrs)['Casey Lane'].line).toBe('Lancaster');
    expect(byName(attrs)['Maximilian Featherstonehaugh'].line).toBe('San Bernardino Valley State');
    expect(byName(attrs)['Drew Park'].line).toBeNull();
    expect(byName(attrs)['Al Wu'].line).toBeNull();
    attrs.rows.forEach((row) => {
      const note = JSON.stringify(row);
      expect(row.fits, note).toBe(true);
      if (row.line) {
        expect(row.below, note).toBe(true);
        expect(row.quiet, note).toBe(true);
      }
    });
    // One row height, with or without the second line.
    expect(new Set(attrs.rows.map((row) => row.height)).size, JSON.stringify(attrs.rows.map((r) => r.height))).toBe(1);
    await shot2(page, 'after-squad-roster-attributes-' + width + '.png');

    // Stats: the program closes the line that already carries position and year.
    await page.locator('#team-view .gob-team-mode button', { hasText: 'Stats' }).click();
    await expect(page.locator('#team-view .gob-team-roster-body .gob-pstats')).toHaveCount(1);
    const stats = await readNameCells(page);
    expect(byName(stats)['Casey Lane'].line).toBe('SF · FR · Lancaster');
    expect(byName(stats)['Maximilian Featherstonehaugh'].line).toBe('SF · FR · San Bernardino Valley State');
    expect(byName(stats)['Drew Park'].line).toBe('SF · FR');
    expect(byName(stats)['Al Wu'].line).toBe('SF · FR');
    stats.rows.forEach((row) => expect(row.fits, JSON.stringify(row)).toBe(true));
    expect(new Set(stats.rows.map((row) => row.height)).size).toBe(1);
    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth - main.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(0);
    await shot2(page, 'after-squad-roster-stats-' + width + '.png');
  });
}

test('a varsity roster has no program line, and its rows are the height a squad\'s are', async ({ page }) => {
  const state = { squad: 'programs', squadReads: [] };
  await install(page, state);
  await page.route('**/roster/**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ is_user_team: false, players: [
      Object.assign(squadPlayer('v-1', 'Vern Wall', 'fpd', 'Lancaster', 6), { starter: false }),
      Object.assign(squadPlayer('v-2', 'Perry Gray', 'fpd', null, 6), { starter: false }),
    ] }),
  }));
  await open(page, 'tab=team-view&view_team_id=' + TID + '&origin=team', 1280, 720);
  await expect(page.locator('#team-view .gob-team-roster-body a.gob-player')).toHaveCount(2);
  const varsity = await readNameCells(page);
  expect(varsity.marked).toBe(false);
  expect(await page.locator('#team-view .gob-team-roster-body .gob-id').count()).toBe(0);
  varsity.rows.forEach((row) => expect(row.line).toBeNull());
  await shot2(page, 'after-varsity-roster-1280.png');

  await open(page, 'tab=team-view&ps_team_id=' + SQUAD + '&origin=league&return_tab=practice-squad-view', 1280, 720);
  await expect(page.locator('#team-view .gob-team-roster-body a.gob-player')).toHaveCount(4);
  const squad = await readNameCells(page);
  expect(squad.rows[0].height).toBe(varsity.rows[0].height);
});

// ── Practice squad marks: never another team's logo (v3 pages 3) ─────────────────
const SHOTS3 = process.env.V33_SHOTS === '1';
const OUT3 = path.join(__dirname, '../../reports/v3-pages-3');
const TIERS = ['All-Americans', 'All-Stars', 'Varsity', 'JV', 'Squad', 'Scrubs'];
const REGIONS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
// Any program's art, the generic set included (the generic square is Bentley-Truman's knight).
const TEAM_ART = /\/images\/teams\//;

async function shot3(page, name) {
  if (!SHOTS3) return;
  fs.mkdirSync(OUT3, { recursive: true });
  await page.mouse.move(700, 4);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT3, name), animations: 'disabled' });
}

test('no practice squad name or id ever resolves to a program\'s art', async ({ page }) => {
  await install(page, { squad: 'played', squadReads: [] });
  await open(page, 'tab=practice-squad-view', 1280, 720);
  const seen = await page.evaluate(({ tiers, regions }) => {
    const names = [];
    regions.forEach((region) => {
      tiers.forEach((tier, index) => {
        names.push('Region ' + region + ' ' + tier);
        names.push('ps_' + region + '_' + (index + 1));
      });
    });
    const bad = [];
    const keys = ['logo_square', 'banner_primary', 'banner_card', 'background', 'mark', 'no-such-key'];
    names.forEach((name) => {
      keys.forEach((key) => {
        const url = window.getTeamAssetPath(name, key);
        if (/\/images\//.test(String(url))) bad.push(name + ' ' + key + ' -> ' + url);
      });
      const logo = window.GOBTables.logo(name);
      if (/\/images\//.test(String(logo))) bad.push(name + ' GOBTables.logo -> ' + logo);
      const mark = window.GOBTables.markHtml(name, '');
      if (/<img/i.test(mark) || !/gob-squad-mark/.test(mark)) bad.push(name + ' markHtml -> ' + mark);
      const link = window.GOBTables.teamLink('#', name, name, '') + window.GOBTables.nextCell(name, '#', '');
      if (/<img/i.test(link)) bad.push(name + ' teamLink/nextCell -> ' + link);
    });
    return {
      bad,
      count: names.length,
      letter: window.practiceSquadOf('Region C Varsity'),
      // A real program is untouched.
      real: [window.getTeamAssetPath('Lancaster', 'logo_square'), window.practiceSquadOf('Lancaster'), window.practiceSquadOf('Four Corners')],
      court: window.getTeamAssetPath('Region A Squad', 'court'),
    };
  }, { tiers: TIERS, regions: REGIONS });
  expect(seen.count).toBe(96);
  expect(seen.bad, seen.bad.slice(0, 5).join('\n')).toEqual([]);
  expect(seen.letter).toEqual({ region: 'C', tier: 'Varsity' });
  expect(seen.real[0]).toMatch(/\/images\/teams\/lancaster\//);
  expect(seen.real[1]).toBeNull();
  expect(seen.real[2]).toBeNull();
});

for (const [width, height] of SIZES.slice(0, 2)) {
  test('squad mark: letter and tier on the banner, letter alone when small, at ' + width, async ({ page }) => {
    const art = [];
    page.on('request', (request) => { if (TEAM_ART.test(request.url())) art.push(new URL(request.url()).pathname); });
    await install(page, { squad: 'played', squadReads: [] });
    await open(page, 'tab=team-view&ps_team_id=' + SQUAD + '&origin=league&return_tab=practice-squad-view', width, height);
    await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Region C Varsity');
    const seen = await page.evaluate((tiers) => {
      const root = document.querySelector('#team-view');
      const read = (el) => {
        const letter = el.querySelector('b');
        const tier = el.querySelector('i');
        const box = el.getBoundingClientRect();
        const shown = tier && getComputedStyle(tier).display !== 'none';
        const inside = (node) => {
          const r = node.getBoundingClientRect();
          return r.left >= box.left - 0.5 && r.right <= box.right + 0.5 && r.top >= box.top - 0.5 && r.bottom <= box.bottom + 0.5;
        };
        return {
          size: [Math.round(box.width), Math.round(box.height)],
          letter: letter.textContent,
          letterPx: parseFloat(getComputedStyle(letter).fontSize),
          letterInside: inside(letter),
          tier: tier ? tier.textContent : '',
          tierShown: !!shown,
          tierPx: shown ? parseFloat(getComputedStyle(tier).fontSize) : 0,
          tierFits: shown ? tier.scrollWidth <= tier.clientWidth && inside(tier) : null,
          tierBelow: shown ? tier.getBoundingClientRect().top >= letter.getBoundingClientRect().top + 10 : null,
          label: el.getAttribute('aria-label'),
        };
      };
      const hero = root.querySelector('.gob-hero-logo .gob-squad-mark');
      // Every tier name the data has, on the same banner mark: the longest must fit.
      const each = tiers.map((name) => {
        hero.querySelector('i').textContent = name;
        return Object.assign({ name }, read(hero));
      });
      hero.querySelector('i').textContent = 'Varsity';
      return {
        hero: read(hero),
        each,
        small: [...root.querySelectorAll('.gob-sch-list .gob-squad-mark')].map(read),
        images: [...root.querySelectorAll('img')].map((img) => img.getAttribute('src') || ''),
        backgrounds: [...root.querySelectorAll('*')].map((el) => getComputedStyle(el).backgroundImage).filter((bg) => /url\(/.test(bg)),
      };
    }, TIERS);
    // The banner mark: the Region letter large, the tier name small under it.
    expect(seen.hero.size).toEqual([72, 72]);
    expect(seen.hero.letter).toBe('C');
    expect(seen.hero.tier).toBe('Varsity');
    expect(seen.hero.tierShown).toBe(true);
    expect(seen.hero.tierBelow).toBe(true);
    expect(seen.hero.letterPx).toBeGreaterThan(seen.hero.tierPx * 4);
    expect(seen.hero.label).toBe('Region C Varsity');
    seen.each.forEach((row) => {
      const note = JSON.stringify(row);
      expect(row.tierShown, note).toBe(true);
      expect(row.tierFits, note).toBe(true);
      expect(row.tierPx, note).toBeGreaterThanOrEqual(8);
      expect(row.letterInside, note).toBe(true);
    });
    // The small mark beside an opponent's name: the letter alone, readable.
    expect(seen.small.length).toBe(3);
    seen.small.forEach((row) => {
      const note = JSON.stringify(row);
      expect(row.size, note).toEqual([18, 18]);
      expect(row.tierShown, note).toBe(false);
      expect(row.letter, note).toMatch(/^[A-H]$/);
      expect(row.letterPx, note).toBeGreaterThanOrEqual(10);
      expect(row.letterInside, note).toBe(true);
    });
    expect(seen.small.map((row) => row.letter)).toEqual(['A', 'B', 'D']);
    // No program's art anywhere on the squad's page: no image, no background, no request
    // for the generic set or for any team but the user's own (the top strip's banner).
    expect(seen.images.filter((src) => TEAM_ART.test(src))).toEqual([]);
    expect(seen.backgrounds.filter((bg) => TEAM_ART.test(bg))).toEqual([]);
    expect(art.filter((p) => !/\/images\/teams\/lancaster\//.test(p)), art.join('\n')).toEqual([]);
    await shot3(page, 'after-squad-mark-team-page-' + width + '.png');
  });
}

test('a practice squad box score has no program banner behind it; a varsity one keeps its own', async ({ page }) => {
  const game = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/practice-squad-real-game.json'), 'utf8'));
  const art = [];
  page.on('request', (request) => { if (TEAM_ART.test(request.url())) art.push(new URL(request.url()).pathname); });
  await install(page, { squad: 'played', squadReads: [] });
  await page.route('**/api/game/**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(game) }));
  const back = encodeURIComponent('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=practice-squad-view');
  for (const [width, height] of SIZES.slice(0, 2)) {
    await page.setViewportSize({ width, height });
    await page.goto('/box-score.html?game_id=ps-real&mode=practice_squad&franchise_id=' + FID + '&team_id=' + TID + '&return_url=' + back);
    await expect(page.locator('#home-player-stats-body tr').first()).toBeVisible({ timeout: 30000 });
    await expect(page.locator('#box-score-header')).toContainText('Region A All-Americans');
    const header = await page.evaluate(() => getComputedStyle(document.getElementById('box-score-header')).backgroundImage);
    expect(header).toBe('none');
    await shot3(page, 'after-squad-box-score-' + width + '.png');
  }
  expect(art.filter((p) => !/\/images\/teams\/lancaster\//.test(p)), art.join('\n')).toEqual([]);

  // The same game document read as a varsity game still draws a banner.
  await page.goto('/box-score.html?game_id=ps-real&mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&return_url=' + back);
  await expect(page.locator('#home-player-stats-body tr').first()).toBeVisible({ timeout: 30000 });
  expect(await page.evaluate(() => getComputedStyle(document.getElementById('box-score-header')).backgroundImage)).toMatch(/url\(/);
});

test('the Practice Squads table, schedule and bracket draw no program art', async ({ page }) => {
  const art = [];
  page.on('request', (request) => { if (TEAM_ART.test(request.url())) art.push(new URL(request.url()).pathname); });
  await install(page, { squad: 'played', squadReads: [] });
  await open(page, 'tab=practice-squad-view', 1280, 720);
  await expect(page.locator('#practice-squad-view a', { hasText: 'Region C Varsity' }).first()).toBeVisible();
  const images = await page.evaluate(() => [...document.querySelectorAll('#practice-squad-view img')].map((img) => img.getAttribute('src') || ''));
  expect(images.filter((src) => TEAM_ART.test(src))).toEqual([]);
  expect(art.filter((p) => !/\/images\/teams\/lancaster\//.test(p)), art.join('\n')).toEqual([]);
});

test('practice squad roster: five Starters from PG to C, the other seven on the Bench', async ({ page }) => {
  const slots = ['PG', 'SG', 'SF', 'PF', 'C'];
  const players = [];
  for (let n = 0; n < 12; n += 1) {
    // Sent out of order: the page sorts the five by their slot.
    const order = n < 5 ? 4 - n : null;
    players.push(Object.assign(squadPlayer('p-' + n, 'Player ' + String.fromCharCode(65 + n), n % 2 ? 'frd' : 'fpd', n % 2 ? null : 'Lancaster', 6), {
      starter: n < 5, lineup_order: order, position: n < 5 ? slots[order] : 'SF',
    }));
  }
  await install(page, { squad: 'played', squadReads: [] });
  await page.route('**/franchise/practice-squad/team**', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(Object.assign(squadBody('played'), { players })),
  }));
  await open(page, 'tab=team-view&ps_team_id=' + SQUAD + '&origin=league&return_tab=practice-squad-view', 1280, 720);
  await expect(page.locator('#team-view .gob-team-roster-body a.gob-player')).toHaveCount(12);
  const groups = await page.evaluate(() => {
    const out = {}; let current = '';
    [...document.querySelectorAll('#team-view .gob-team-roster-body tbody tr')].forEach((tr) => {
      if (tr.classList.contains('gob-sep')) { current = tr.textContent.trim(); out[current] = []; return; }
      if (tr.querySelector('a.gob-player') && current) out[current].push(tr.children[2].textContent.trim());
    });
    return out;
  });
  expect(Object.keys(groups)).toEqual(['Starters', 'Bench']);
  expect(groups.Starters).toEqual(slots);
  expect(groups.Bench.length).toBe(7);
});
