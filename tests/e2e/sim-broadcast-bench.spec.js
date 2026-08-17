// @ts-check
/**
 * Sim Broadcast bench rail — what may appear on it, and in what order.
 *
 * Drives the REAL buildSimTimeline in the browser (its potg.js dependency is CJS and
 * will not resolve under bare Node). The rail's contents are only players who have
 * logged court time and are NOT in the current five; with no rotation subs the only
 * route onto it is a foul-out.
 */
const { test, expect } = require('@playwright/test');

const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const HOME_IDS = ['h1', 'h2', 'h3', 'h4', 'h5'];
const AWAY_IDS = ['a1', 'a2', 'a3', 'a4', 'a5'];

function lineup(ids) {
  const out = {};
  POS.forEach((p, i) => { if (ids[i]) out[p] = ids[i]; });
  return out;
}

function summary(turns) {
  const players = [...HOME_IDS.map((id, i) => ({ playerId: id, name: `Home ${i + 1}`, jersey: i + 1, team: 'home', pos: POS[i], rt: 70 })),
                   ...AWAY_IDS.map((id, i) => ({ playerId: id, name: `Away ${i + 1}`, jersey: i + 1, team: 'away', pos: POS[i], rt: 70 })),
                   { playerId: 'h6', name: 'Home Sub A', jersey: 6, team: 'home', pos: 'PG', rt: 65 },
                   { playerId: 'h7', name: 'Home Sub B', jersey: 7, team: 'home', pos: 'SF', rt: 64 },
                   { playerId: 'a6', name: 'Away Sub', jersey: 6, team: 'away', pos: 'PG', rt: 65 }];
  return {
    home_team_id: 'H', away_team_id: 'A',
    teams: { H: { name: 'Lancaster' }, A: { name: 'Xavier' } },
    players, turns,
  };
}

/** team_totals rows are keyed by core team name and are cumulative for the whole game. */
function totals({ homeF = 0, awayF = 0 } = {}) {
  const row = (F) => ({ PTS: 20, FGM: 8, FGA: 18, '3PTM': 2, FTM: 2, FTA: 3,
                        OREB: 3, DREB: 7, REB: 10, AST: 5, STL: 2, BLK: 1, TO: 4,
                        F, PIP: 8, FB_PTS: 4, DEF_A: 12, DEF_S: 5 });
  return { Lancaster: row(homeF), Xavier: row(awayF) };
}

const turn = (over = {}) => ({
  quarter: 1, clock: '3:06',
  score: { home: 4, away: 2 },
  home_lineup: lineup(HOME_IDS), away_lineup: lineup(AWAY_IDS),
  deltas: {}, ...over,
});

async function build(page, turns) {
  await page.goto('/');
  return page.evaluate(async (s) => {
    const mod = await import('/js/phaser/utils/simTimelineAssembler.js');
    const tl = mod.buildSimTimeline([s], { homeTeamName: 'Lancaster', awayTeamName: 'Xavier' });
    return tl.frames.map((f) => ({
      phase: f.phase,
      benchHome: (f.benchHome || []).map((c) => ({ name: c.name, out: c.out })),
      benchAway: (f.benchAway || []).map((c) => ({ name: c.name, out: c.out })),
    }));
  }, summary(turns));
}

test('both rails are empty early in Q1 with no foul-outs', async ({ page }) => {
  const frames = await build(page, [turn(), turn({ clock: '3:00' }), turn({ clock: '2:40' })]);
  for (const f of frames) {
    expect(f.benchHome, f.phase).toEqual([]);
    expect(f.benchAway, f.phase).toEqual([]);
  }
});

test('a partially-emitted lineup does not drop still-playing starters onto the rail', async ({ page }) => {
  // Helper turns (inbound / rebound / free throws) can name only some of the five.
  // Those unnamed players are still on the floor.
  const frames = await build(page, [
    turn(),
    turn({ clock: '3:00', home_lineup: { PG: 'h1', SG: 'h2' } }),   // partial
    turn({ clock: '2:50', home_lineup: {} }),                        // omitted entirely
    turn({ clock: '2:40' }),
  ]);
  for (const f of frames) {
    expect(f.benchHome, f.phase).toEqual([]);
    expect(f.benchAway, f.phase).toEqual([]);
  }
});

test('a foul-out puts exactly that player on the rail, marked OUT', async ({ page }) => {
  const frames = await build(page, [
    turn(),
    turn({ clock: '2:30', foul_out_player: 'h3' }),
    // Replacement takes the row; the fouled-out player is now off the floor.
    turn({ clock: '2:20', home_lineup: lineup(['h1', 'h2', 'h6', 'h4', 'h5']) }),
  ]);
  const last = frames[frames.length - 1];
  expect(last.benchHome).toEqual([{ name: 'Home 3', out: true }]);
  expect(last.benchAway).toEqual([]);
});

test('the most recent exit is first on the rail', async ({ page }) => {
  const frames = await build(page, [
    turn(),
    turn({ clock: '2:30', foul_out_player: 'h3' }),
    turn({ clock: '2:20', home_lineup: lineup(['h1', 'h2', 'h6', 'h4', 'h5']) }),
    turn({ clock: '1:10', foul_out_player: 'h1' }),
    // h7 replaces h1; a fouled-out player never returns, so both stay off the floor.
    turn({ clock: '1:00', home_lineup: lineup(['h7', 'h2', 'h6', 'h4', 'h5']) }),
  ]);
  const names = frames[frames.length - 1].benchHome.map((c) => c.name);
  expect(names[0]).toBe('Home 1');          // left most recently
  expect(names).toContain('Home 3');
  expect(names.indexOf('Home 1')).toBeLessThan(names.indexOf('Home 3'));
});

test.describe('team fouls: panel is the game, scoreboard is the quarter', () => {
  async function panelAndBoard(page, turns) {
    await page.goto('/');
    return page.evaluate(async (sum) => {
      const mod = await import('/js/phaser/utils/simTimelineAssembler.js');
      const tl = mod.buildSimTimeline([sum], { homeTeamName: 'Lancaster', awayTeamName: 'Xavier' });
      const f = tl.frames[tl.frames.length - 1];
      return {
        panelAway: f.teamPanel.away.fouls, panelHome: f.teamPanel.home.fouls,
        boardAway: f.score.afoul, boardHome: f.score.hfoul,
      };
    }, summary(turns));
  }

  test('the panel carries the whole-game total, not the quarter count', async ({ page }) => {
    // Q2, quarter counters already reset; the game totals keep climbing.
    const m = await panelAndBoard(page, [
      turn({ quarter: 1, clock: '1:00', team_totals: totals({ homeF: 6, awayF: 5 }),
             home_team_fouls: 6, away_team_fouls: 5 }),
      turn({ quarter: 2, clock: '7:40', team_totals: totals({ homeF: 9, awayF: 8 }),
             home_team_fouls: 3, away_team_fouls: 3 }),
    ]);
    expect(m.panelHome).toBe(9);   // whole game
    expect(m.panelAway).toBe(8);
    expect(m.boardHome).toBe(3);   // this quarter only
    expect(m.boardAway).toBe(3);
  });

  test('the two agree in Q1, before any reset has happened', async ({ page }) => {
    const m = await panelAndBoard(page, [
      turn({ quarter: 1, clock: '5:00', team_totals: totals({ homeF: 4, awayF: 2 }),
             home_team_fouls: 4, away_team_fouls: 2 }),
    ]);
    expect(m.panelHome).toBe(m.boardHome);
    expect(m.panelAway).toBe(m.boardAway);
  });

  test('the panel total never decreases across a quarter break', async ({ page }) => {
    const m = await panelAndBoard(page, [
      turn({ quarter: 1, clock: '0:30', team_totals: totals({ homeF: 7, awayF: 6 }),
             home_team_fouls: 7, away_team_fouls: 6 }),
      turn({ quarter: 2, clock: '7:50', team_totals: totals({ homeF: 7, awayF: 6 }),
             home_team_fouls: 0, away_team_fouls: 0 }),
    ]);
    expect(m.panelHome).toBe(7);
    expect(m.boardHome).toBe(0);   // reset for the new quarter
  });
});
