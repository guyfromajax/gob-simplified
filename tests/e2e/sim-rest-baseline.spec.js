// @ts-check
const { test, expect } = require('@playwright/test');

const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const HOME = ['h1', 'h2', 'h3', 'h4', 'h5'];
const AWAY = ['a1', 'a2', 'a3', 'a4', 'a5'];
const HOME_NAME = 'Team A';
const AWAY_NAME = 'Team B';
const lineup = (ids) => POS.reduce((out, pos, i) => ({ ...out, [pos]: ids[i] }), {});
const score = (home, away) => ({ [HOME_NAME]: home, [AWAY_NAME]: away });

function turn(quarter, clock, home, away, scorer = null, points = 0) {
  return {
    quarter,
    clock,
    score: score(home, away),
    home_lineup: lineup(HOME),
    away_lineup: lineup(AWAY),
    deltas: scorer ? { [scorer]: { stats: { PTS: points, FGM: 1, FGA: 1 } } } : {},
  };
}

function summary(turns) {
  return {
    home_team_id: 'home',
    away_team_id: 'away',
    teams: { home: { name: HOME_NAME }, away: { name: AWAY_NAME } },
    players: [
      ...HOME.map((id, i) => ({ playerId: id, name: `Home ${i}`, team: 'home', pos: POS[i] })),
      ...AWAY.map((id, i) => ({ playerId: id, name: `Away ${i}`, team: 'away', pos: POS[i] })),
    ],
    turns,
  };
}

test.describe('Sim Rest join baseline', () => {
  for (const startQuarter of [2, 3, 4]) {
    test(`worm starts exactly at Q${startQuarter} with the carried margin`, async ({ page }) => {
      await page.goto('/');
      const result = await page.evaluate(async ({ payload, startQuarter }) => {
        const { buildSimTimeline, REG_Q_SEC } = await import('/js/phaser/utils/simTimelineAssembler.js');
        const timeline = buildSimTimeline([payload], {
          homeTeamName: 'Team A', awayTeamName: 'Team B', startQuarter,
        });
        const first = timeline.frames[0];
        return {
          expectedElapsed: (startQuarter - 1) * REG_Q_SEC,
          samples: first.worm.samples,
          startScore: timeline.meta.startScore,
        };
      }, {
        startQuarter,
        payload: summary([
          turn(1, '0:00', 20, 18),
          ...(startQuarter >= 3 ? [turn(2, '0:00', 44, 43)] : []),
          ...(startQuarter >= 4 ? [turn(3, '0:00', 60, 58)] : []),
          turn(startQuarter, '7:50', startQuarter === 2 ? 22 : startQuarter === 3 ? 46 : 62,
            startQuarter === 2 ? 18 : startQuarter === 3 ? 43 : 58, 'h1', 2),
        ]),
      });

      expect(result.samples[0].elapsed).toBe(result.expectedElapsed);
      expect(result.samples[0].margin).toBe(result.startScore.home - result.startScore.away);
      expect(result.samples.every((sample) => sample.elapsed >= result.expectedElapsed)).toBe(true);
    });
  }

  test('carried 44-43 is not classified as a 44-point run', async ({ page }) => {
    await page.goto('/');
    const result = await page.evaluate(async () => {
      const { CalloutCadence } = await import('/js/phaser/utils/simCalloutCadence.js');
      const shown = [];
      const cadence = new CalloutCadence({ teams: {}, pack: { categories: {} }, onCallout: (m) => { shown.push(m); return true; } });
      cadence.primeScore({ home: 44, away: 43 });
      cadence.step({
        quarter: 3,
        score: { home: 46, away: 43, clock: '7:50' },
        home: [], away: [], events: [], teamPanel: {},
      }, 1);
      return { run: cadence.run, shown };
    });

    expect(result.run).toEqual({ side: 'home', pts: 2 });
    expect(result.shown).toEqual([]);
  });

  test('an unprimed cadence treats its first observed score as baseline', async ({ page }) => {
    await page.goto('/');
    const run = await page.evaluate(async () => {
      const { CalloutCadence } = await import('/js/phaser/utils/simCalloutCadence.js');
      const cadence = new CalloutCadence({ teams: {}, pack: { categories: {} } });
      cadence.step({ quarter: 3, score: { home: 44, away: 43 }, home: [], away: [], events: [], teamPanel: {} }, 1);
      return cadence.run;
    });
    expect(run).toEqual({ side: null, pts: 0 });
  });
});
