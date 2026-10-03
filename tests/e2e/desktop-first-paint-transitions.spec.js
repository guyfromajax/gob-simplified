// @ts-check
/**
 * First-paint sweep, transitions: what the coach sees while moving through a loading
 * step, on the desktop SQLite server (a real 128-team league), every API response held
 * back 1.5 s.
 *
 *   open a team page, open a player page   (in-app drill-ins)
 *   after training                         (Submit Training -> Training Report)
 *   after a game                           (the box score of a real, simmed game)
 *   after advancing                        (the Office in the new week)
 *
 * A tool, not a gate: it runs only with FP_SWEEP set, under playwright.desktop.config.js.
 * Shots and results-transitions-<phase>.json go to FP_OUT/transitions.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { delayApi, settle, sweepScreen } = require('./helpers/firstPaint');

const PHASE = process.env.FP_SWEEP || '';
const OUT = process.env.FP_OUT || path.join(__dirname, '../../reports/first-paint-sweep/raw');
const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const DELAY = Number(process.env.FP_DELAY_MS || 1500);
const LONG = 2400000;

test.describe.configure({ mode: 'serial', timeout: 3600000 });
test.skip(!PHASE, 'FP_SWEEP only');

let fid = '';
const results = {};

test.afterAll(async ({ request }) => {
  fs.mkdirSync(path.join(OUT, 'transitions'), { recursive: true });
  fs.writeFileSync(path.join(OUT, 'transitions', 'results-transitions-' + PHASE + '.json'), JSON.stringify(results, null, 2));
  // Leave the desktop e2e sqlite as we found it (two-franchise cap).
  if (fid) await request.delete('/franchise/' + fid).catch(() => {});
});

test('sweep the transitions', async ({ browser, request }) => {
  fs.mkdirSync(path.join(OUT, 'transitions'), { recursive: true });
  const create = await request.post('/franchise/select-team', { data: { team_name: 'Lancaster' } });
  expect(create.ok(), await create.text()).toBeTruthy();
  fid = (await create.json()).franchise_id;
  const next = await (await request.post('/franchise/play-next-game', { data: { franchise_id: fid } })).json();
  const mine = next.home === 'Lancaster';
  const tid = String(mine ? next.home_id : next.away_id);
  const week = Number(next.week || 1);
  const q = (extra) => new URLSearchParams(Object.assign(
    { franchise_id: fid, team_id: tid, user_team_id: tid, mode: 'franchise' }, extra || {},
  )).toString();

  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  // A step that cannot find its control should fail in seconds, not sit out the hour.
  context.setDefaultTimeout(45000);
  context.setDefaultNavigationTimeout(90000);
  const page = await context.newPage();
  await page.addInitScript((port) => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = Number(port);
    window.alert = () => {};
  }, PORT);
  const tracker = await delayApi(page, DELAY);
  const shotFor = (id) => (suffix) => page.screenshot({
    path: path.join(OUT, 'transitions', PHASE + '-' + id + '-' + suffix + '.png'), animations: 'disabled',
  }).catch(() => {});
  const run = async (id, name, action, opts) => {
    const swept = await sweepScreen(page, tracker, '', shotFor(id), Object.assign({ action }, opts || {}));
    results[id] = Object.assign({ name }, swept);
  };
  // A milestone pop-up (first archetype, a title) opens over the page once it is settled.
  // It is a designed moment, not a loading state: close it so the next click lands.
  const dismissMoments = async () => {
    for (let i = 0; i < 6; i += 1) {
      const open = await page.locator('.mm-scrim.is-open').count();
      if (!open) return;
      await page.keyboard.press('Escape');
      await page.waitForTimeout(700);
    }
  };
  const open = async (url) => {
    await page.goto(url);
    await settle(page, tracker, 1500, 40000);
    await page.waitForTimeout(900);
    await dismissMoments();
  };

  // 1. Open a team page from Standings.
  await open('/franchise-command-center.html?' + q({ tab: 'standings-view' }));
  await run('t1-open-team-page', 'Open a team page (from Standings)', async () => {
    await page.locator('#standings-view a.gob-team').filter({ hasNotText: 'Lancaster' }).first().click();
  });

  // 2. Open a player page from the Roster.
  await open('/franchise-command-center.html?' + q({ tab: 'roster-view' }));
  await run('t2-open-player-page', 'Open a player page (from Roster)', async () => {
    await page.locator('#roster-view a.gob-player').first().click();
  });

  // 3. After training: Auto-Train, Submit, and through to the Training Report.
  await open('/training.html?' + q({ from: 'locker-room' }));
  await page.locator('#auto-train-btn').click();
  await page.locator('#auto-train-modal-close').click().catch(() => {});
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 15000 });
  await shotFor('t3-after-training')('ready');
  await run('t3-after-training', 'After training (Submit Training → Training Report)', async () => {
    await page.locator('#submit-btn').click();
  }, { overlayCap: LONG, settleCap: 120000 });

  // 4. After a game. The game itself is simmed through the API (the court is not a
  //    loading step); the sweep opens what the coach is shown next: the box score.
  const init = await (await request.post('/api/init-game', {
    data: {
      home_team: next.home, away_team: next.away, home_id: next.home_id, away_id: next.away_id,
      mode: 'franchise', franchise_id: fid, user_team_side: mine ? 'home' : 'away',
    },
    timeout: LONG,
  })).json();
  const gameId = String(init.game_id);
  const sim = await (await request.post('/api/simulate-quarter', {
    data: {
      game_id: gameId, home_team: next.home, away_team: next.away, quarter: 1, mode: 'franchise',
      franchise_id: fid, full_sim: true, advance_method: 'sim_rest_of_game',
    },
    timeout: LONG,
  })).json();
  const score = (sim && sim.score) || {};
  const homeScore = Number(score[next.home] || score.home || 70);
  const awayScore = Number(score[next.away] || score.away || 65);
  await request.post('/franchise/complete-week/start-cpu-sims', { data: { franchise_id: fid, week }, timeout: LONG });
  const phaseA = await request.post('/franchise/complete-week/phase-a', {
    data: {
      franchise_id: fid, week, game_id: gameId,
      result: { team1_id: next.away_id, team2_id: next.home_id, team1_score: awayScore, team2_score: homeScore },
    },
    timeout: LONG,
  });
  expect(phaseA.ok(), await phaseA.text()).toBeTruthy();
  await page.evaluate((pending) => {
    localStorage.setItem('franchise_complete_week_pending', JSON.stringify(pending));
  }, { franchise_id: fid, week });
  const boxUrl = '/box-score.html?' + q({
    game_id: gameId, home: next.home, away: next.away, my_team: mine ? 'home' : 'away', post_game_phase_b: '1',
  });
  results['t4-after-a-game'] = Object.assign(
    { name: 'After a game (box score of the game just played)', owner: 'stats (box-score.js)' },
    await sweepScreen(page, tracker, boxUrl, shotFor('t4-after-a-game')),
  );

  // 5. After advancing. The week is completed through the API (phase B is what the
  //    end-of-game "Go To Locker Room" runs behind its loader; a live game cannot be
  //    played headlessly here), then the sweep opens what the coach lands on: the Office
  //    in the new week, with its digest and pop-ups.
  const phaseB = await request.post('/franchise/complete-week/phase-b', {
    data: { franchise_id: fid, week }, timeout: LONG,
  });
  expect(phaseB.ok(), await phaseB.text()).toBeTruthy();
  await page.evaluate(() => { localStorage.removeItem('franchise_complete_week_pending'); });
  results['t5-after-advancing'] = Object.assign(
    { name: 'After advancing (the Office in the new week)' },
    await sweepScreen(page, tracker, '/franchise-command-center.html?' + q({ tab: 'home-tab' }), shotFor('t5-after-advancing')),
  );

  await context.close();
});
