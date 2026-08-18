// @ts-check
/**
 * Game-winning shot: detection in the assembler, presentation as a callout.
 *
 * Spec: 10 seconds or less remaining, the score CHANGES the lead, free throws count,
 * the LAST such score in the game wins the title, and it must belong to the team that
 * actually won. The engine declares `pgpc_tier_c.game_winner_shot` but never writes it,
 * so this is derived from the emitted score + deltas — no engine change.
 */
const { test, expect } = require('@playwright/test');

const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const HOME = ['h1', 'h2', 'h3', 'h4', 'h5'];
const AWAY = ['a1', 'a2', 'a3', 'a4', 'a5'];
const lineup = (ids) => POS.reduce((o, p, i) => (ids[i] ? { ...o, [p]: ids[i] } : o), {});

function summary(turns) {
  const players = [
    ...HOME.map((id, i) => ({ playerId: id, name: `Home ${i + 1}`, jersey: i + 1, team: 'home', pos: POS[i], rt: 70 })),
    ...AWAY.map((id, i) => ({ playerId: id, name: `Away ${i + 1}`, jersey: i + 1, team: 'away', pos: POS[i], rt: 70 })),
  ];
  return {
    home_team_id: 'H', away_team_id: 'A',
    teams: { H: { name: 'Lancaster' }, A: { name: 'Xavier' } },
    players, turns,
  };
}

// `turn.score` is keyed by TEAM NAME, not home/away — see applyTurnToScoreboard.
const HOME_NAME = 'Lancaster';
const AWAY_NAME = 'Xavier';
const scoreOf = (home, away) => ({ [HOME_NAME]: home, [AWAY_NAME]: away });

/** One turn: score after the play, plus the scorer's PTS delta. */
const turn = (quarter, clock, home, away, scorer, pts) => ({
  quarter, clock,
  score: scoreOf(home, away),
  home_lineup: lineup(HOME), away_lineup: lineup(AWAY),
  deltas: scorer ? { [scorer]: { team: 'x', stats: { PTS: pts, FGM: 1, FGA: 1 } } } : {},
});

/** A free-throw turn: PTS moves, no FGA. */
const ftTurn = (quarter, clock, home, away, scorer, pts) => ({
  quarter, clock,
  score: scoreOf(home, away),
  home_lineup: lineup(HOME), away_lineup: lineup(AWAY),
  deltas: { [scorer]: { team: 'x', stats: { PTS: pts, FTM: pts, FTA: pts } } },
});

async function build(page, turns) {
  await page.goto('/');
  return page.evaluate(async (s) => {
    const mod = await import('/js/phaser/utils/simTimelineAssembler.js');
    const tl = mod.buildSimTimeline([s], { homeTeamName: 'Lancaster', awayTeamName: 'Xavier' });
    const stamped = tl.frames.filter((f) => f.gameWinner).map((f) => f.gameWinner);
    return { winner: tl.meta.gameWinner, stampedCount: stamped.length, stamped: stamped[0] || null };
  }, summary(turns));
}

test.describe('detection', () => {
  test('a lead-changing bucket inside 10 seconds by the winner is the game-winner', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 70, 71, 'a1', 2),          // away ahead
      turn(4, '0:08', 72, 71, 'h3', 2),          // home takes the lead inside 10s
      turn(4, '0:00', 72, 71, null, 0),
    ]);
    expect(m.winner).toBeTruthy();
    expect(m.winner.playerId).toBe('h3');
    expect(m.winner.name).toBe('Home 3');
    expect(m.winner.side).toBe('home');
    expect(m.winner.clock).toBe('0:08');
  });

  test('a free throw counts', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:20', 70, 71, 'a1', 2),
      ftTurn(4, '0:04', 72, 71, 'h2', 2),
      turn(4, '0:00', 72, 71, null, 0),
    ]);
    expect(m.winner.playerId).toBe('h2');
  });

  test('outside 10 seconds it is not a game-winner', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 70, 71, 'a1', 2),
      turn(4, '0:11', 72, 71, 'h3', 2),          // 11s — one second too early
      turn(4, '0:00', 72, 71, null, 0),
    ]);
    expect(m.winner).toBeNull();
  });

  test('a score that does not change the lead is not a game-winner', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 72, 70, 'h1', 2),          // home already ahead
      turn(4, '0:05', 75, 70, 'h3', 3),          // dagger, but no lead change
      turn(4, '0:00', 75, 70, null, 0),
    ]);
    expect(m.winner).toBeNull();
  });

  test('the LAST qualifying score wins the title', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 70, 71, 'a1', 2),
      turn(4, '0:10', 72, 71, 'h3', 2),          // home leads with 10s
      turn(4, '0:01', 72, 73, 'a4', 2),          // away retakes it with 1s — this is it
      turn(4, '0:00', 72, 73, null, 0),
    ]);
    expect(m.winner.playerId).toBe('a4');
    expect(m.winner.clock).toBe('0:01');
  });

  test('it must belong to the team that actually won', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 70, 71, 'a1', 2),
      turn(4, '0:09', 72, 71, 'h3', 2),          // home goes ahead...
      turn(5, '0:20', 78, 80, 'a2', 2),          // ...but away wins in OT
      turn(5, '0:00', 78, 80, null, 0),
    ]);
    // h3's shot changed the lead inside 10s of Q4, but home lost — so no game-winner.
    expect(m.winner).toBeNull();
  });

  test('an OT game-winner is found in the OT period', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:02', 70, 70, 'h1', 2),
      turn(5, '0:40', 76, 78, 'a1', 2),
      turn(5, '0:06', 79, 78, 'h5', 3),          // lead change inside 10s of OT
      turn(5, '0:00', 79, 78, null, 0),
    ]);
    expect(m.winner.playerId).toBe('h5');
    expect(m.winner.quarter).toBe(5);
  });

  test('a game with no late lead change has no game-winner', async ({ page }) => {
    const m = await build(page, [
      turn(4, '2:00', 80, 60, 'h1', 2),
      turn(4, '0:05', 82, 60, 'h2', 2),
      turn(4, '0:00', 82, 60, null, 0),
    ]);
    expect(m.winner).toBeNull();
  });

  test('the winner is stamped onto exactly one frame', async ({ page }) => {
    const m = await build(page, [
      turn(4, '0:30', 70, 71, 'a1', 2),
      turn(4, '0:07', 72, 71, 'h3', 2),
      turn(4, '0:00', 72, 71, null, 0),
    ]);
    expect(m.stampedCount).toBe(1);
    expect(m.stamped.playerId).toBe('h3');
  });
});

test.describe('copy', () => {
  test('the line lives in sim-callout-copy.md, not in source', async ({ page }) => {
    await page.goto('/');
    await page.addScriptTag({ url: '/js/config/api-config.js' });
    const m = await page.evaluate(async () => {
      const mod = await import('/js/phaser/utils/simCalloutCopy.js');
      const res = await fetch(mod.copyUrl ? mod.copyUrl() : '/static/sim-callout-copy.md');
      const pack = mod.parseCalloutMd
        ? mod.parseCalloutMd(await res.text())
        : await mod.loadCalloutCopy();
      const cat = pack.categories.gamewinner;
      return { ok: res.ok, avatar: cat && cat.avatar, lines: cat && cat.lines };
    });
    expect(m.ok).toBe(true);
    expect(m.avatar).toBe('headshot');
    expect(m.lines.join(' ')).toContain('Game Winning Shot!');
  });

  test('no game-winner string is hardcoded in the cadence or presentation source', async () => {
    const fs = require('fs');
    const path = require('path');
    const dir = path.join(__dirname, '../../FrontEnd/static/js/phaser/utils');
    for (const f of ['simCalloutCadence.js', 'simGamePresentation.js']) {
      expect(fs.readFileSync(path.join(dir, f), 'utf8')).not.toContain('Game Winning Shot');
    }
  });
});

test.describe('hold', () => {
  test('the game-winner holds for 6s, every other tier for 2.6s', async ({ page }) => {
    await page.goto('/');
    const m = await page.evaluate(async () => {
      const c = await import('/js/phaser/utils/simCalloutCadence.js');
      return { standard: c.CALLOUT_HOLD_S, winner: c.GAME_WINNER_HOLD_S, tier: c.GAME_WINNER_TIER };
    });
    expect(m.standard).toBe(2.6);
    expect(m.winner).toBe(6);
    expect(m.tier).toBe('gamewinner');
  });
});
