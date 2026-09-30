// @ts-check
/**
 * Returning to the FCC after a game must show FRESH state (staging bug, Sep 30,
 * week 25 -> 26: the FCC came back with the old week and a live "Play Next Game"
 * instead of "Review Recruit Invites"; pressing it skipped the invites and training).
 *
 * The API is mocked with STATE: phase-b advances the franchise from week 25 to 26,
 * where the invite step (weeks 21-26) must be the Advance button again. No manual
 * reload anywhere. Every FCC document records each Advance the player could have
 * pressed (enabled and on top) while the return is watched; the only one allowed is
 * the fresh week's invite step.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

// The return lands on a back-forward-cache entry; Playwright disables it by default.
test.use({ launchOptions: { ignoreDefaultArgs: ['--disable-back-forward-cache'] } });

const FID = 'f-e2e-fresh';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const GAME = 'g-e2e-fresh';
// Right after the week advances the server is busy: its FCC read answers slowly.
const SLOW_FCC_MS = 1500;
const FRESH = 'Week 26 | Review Recruit Invites | recruit-invites';
const PLAYERS = [
  ['111111111111111111111101', 'Ada Player', 'PG'],
  ['111111111111111111111102', 'Bea Player', 'SG'],
  ['111111111111111111111103', 'Cy Player', 'SF'],
  ['111111111111111111111104', 'Dee Player', 'PF'],
  ['111111111111111111111105', 'Eli Player', 'C'],
];
const ROSTER = PLAYERS.map(([id, name, pos]) => ({
  _id: id, player_id: id, name, first_name: name.split(' ')[0], last_name: 'Player', jersey: 11, position: pos,
  attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
  position_ratings: { PG: 70, SG: 60, SF: 50, PF: 40, C: 30 }, stats: { game: {} },
}));

function commandCenter(state) {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster',
    week: state.week, season: 1, current_season: 1,
    training_completed: state.trainingCompleted, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: state.boardSavedWeek },
    user_conference: 1, sister_conference: 2, user_region: 'A',
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

/** Stateful mock: `state` changes as the real client progresses the week. */
async function installApi(page, state) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const method = request.method();
    let path = '';
    try { path = new URL(request.url()).pathname; } catch (e) { await route.continue(); return; }
    const api = path.startsWith('/api/') || path.startsWith('/franchise/') || path.startsWith('/roster/')
      || path.startsWith('/player/') || path.startsWith('/recruit/') || path === '/teams' || path === '/app-config';
    if (!api) { await route.continue(); return; }
    if (path === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (path === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (path === '/franchise/list') {
      return fulfillJson(route, { franchises: [{ franchise_id: FID, user_team_id: 'Lancaster', home_slot: 1, team_name: 'Lancaster' }], max: 2 });
    }
    if (path === '/teams') {
      return fulfillJson(route, [
        { name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID, primary_color: '#27408E', secondary_color: '#ffffff' },
        { name: 'Four-Corners', display_name: 'Four-Corners', object_id: OPP, _id: OPP, primary_color: '#c0392b', secondary_color: '#ffffff' },
      ]);
    }
    if (path.startsWith('/franchise/command-center/data')) {
      const advanced = state.week > state.startWeek;
      // A deploy cutover or an overloaded worker right after the advance.
      if (advanced && state.failFccReads > 0) {
        state.failFccReads -= 1;
        return fulfillJson(route, { detail: 'upstream unavailable' }, 503);
      }
      // A slow server answers with what was true when it was asked.
      const body = commandCenter(state);
      if (advanced) await new Promise((r) => setTimeout(r, SLOW_FCC_MS));
      return fulfillJson(route, body);
    }
    if (path.startsWith('/franchise/standings')) {
      return fulfillJson(route, { user_conference: 1, sister_conference: 2, standings: [
        { team_id: TID, name: 'Lancaster', display_name: 'Lancaster', conference: 1, region: 'A', W: 20, L: 4, PF: 80, PA: 70, natl_rank: 4 },
        { team_id: OPP, name: 'Four-Corners', display_name: 'Four-Corners', conference: 2, region: 'A', W: 12, L: 12, PF: 70, PA: 72, natl_rank: 40 },
      ] });
    }
    if (path.startsWith('/franchise/team-data')) return fulfillJson(route, { team_attributes: { team_chemistry: 15 }, players: ROSTER });
    if (path.startsWith('/franchise/recruiting-data')) {
      // The user reviews and sends this week's invites on the recruiting page.
      state.boardSavedWeek = state.week;
      return fulfillJson(route, { week: state.week, team_id: TID, team: 'Lancaster', team_region: 'A' });
    }
    if (path === '/franchise/play-next-game' && method === 'POST') {
      return fulfillJson(route, { home: 'Lancaster', away: 'Four-Corners', week: state.week, home_id: TID, away_id: OPP,
        home_display: 'Lancaster', away_display: 'Four-Corners' });
    }
    if (path.startsWith('/roster/')) return fulfillJson(route, { players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
    if (path === '/api/init-game' && method === 'POST') return fulfillJson(route, { game_id: GAME });
    if (path === '/api/autoset-lineup' && method === 'POST') {
      return fulfillJson(route, { lineup: { PG: PLAYERS[0][0], SG: PLAYERS[1][0], SF: PLAYERS[2][0], PF: PLAYERS[3][0], C: PLAYERS[4][0] } });
    }
    if (path === '/api/playbooks') return fulfillJson(route, { motion: [], set_plays: [], man_defense_rows: [], zone_defense_rows: [] });
    if (path.includes('/resume-state')) return fulfillJson(route, { status: 'quarter_break' });
    if (path === '/api/simulate-quarter' && method === 'POST') {
      return fulfillJson(route, {
        is_final: true, game_id: GAME, quarter: 4, week: state.week, turns: [],
        home_team: { name: 'Lancaster', score: 70 }, away_team: { name: 'Four-Corners', score: 60 },
        home_team_id: TID, away_team_id: OPP,
        score: { Lancaster: 70, 'Four-Corners': 60 }, final_score: { Lancaster: 70, 'Four-Corners': 60 },
        teams: {}, box_score: { home: [], away: [] },
      });
    }
    if (path === '/franchise/complete-week/phase-b' && method === 'POST') {
      // The week really advances: 25 -> 26, training not yet run, invites not sent.
      state.week += 1;
      state.trainingCompleted = false;
      return fulfillJson(route, { status: 'ok', phase: 'b', week: state.week - 1, idempotent: false });
    }
    if (path.startsWith('/franchise/complete-week/')) return fulfillJson(route, { ok: true });
    if (path.startsWith('/franchise/championship-moments/')) return fulfillJson(route, { is_championship: false });
    if (path.startsWith('/api/game/') && method === 'GET') {
      return fulfillJson(route, { game_id: GAME, status: 'final', is_final: true, players: [],
        score: { Lancaster: 70, 'Four-Corners': 60 }, home_team: 'Lancaster', away_team: 'Four-Corners', week: state.week });
    }
    if (path === '/api/community/around-the-league') return fulfillJson(route, { slots: [] });
    return fulfillJson(route, method === 'GET' ? {} : { ok: true });
  });
}

/**
 * Every FCC document records each Advance the player could press while the return
 * is watched: enabled, and the top element at its centre (not under an overlay).
 * sessionStorage survives the bfcache restore and the replace, so nothing is lost.
 */
async function installAdvanceSampler(page) {
  await page.addInitScript(() => {
    if (!/franchise-command-center\.html$/.test(location.pathname)) return;
    const sample = () => {
      try {
        if (sessionStorage.getItem('e2e-watch-return') !== '1') return;
        const btn = document.getElementById('play-now');
        if (!btn || btn.disabled) return;
        const box = btn.getBoundingClientRect();
        if (!box.width || !box.height) return;
        const top = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
        if (!top || !btn.contains(top)) return;
        const week = document.getElementById('gob-week-value');
        const row = [week ? week.textContent.trim() : '', btn.textContent.trim(), btn.getAttribute('data-mode') || ''].join(' | ');
        const seen = JSON.parse(sessionStorage.getItem('e2e-advance-seen') || '[]');
        if (seen.indexOf(row) === -1) {
          seen.push(row);
          sessionStorage.setItem('e2e-advance-seen', JSON.stringify(seen));
        }
      } catch (e) { /* sampling only */ }
    };
    setInterval(sample, 20);
  });
}

async function watchReturn(page) {
  await page.evaluate(() => {
    sessionStorage.setItem('e2e-watch-return', '1');
    sessionStorage.removeItem('e2e-advance-seen');
  });
}

async function advanceStatesSeen(page) {
  return page.evaluate(() => JSON.parse(sessionStorage.getItem('e2e-advance-seen') || '[]'));
}

async function enterFcc(page) {
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await page.locator('[data-hb-enter]').first().click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page.locator('#play-now')).toBeEnabled({ timeout: 20000 });
}

async function startGameToLineup(page) {
  // From whichever page the player is on (FCC, or the recruiting page's own Advance).
  await expect(page.locator('#play-now')).toHaveText('Play Next Game', { timeout: 20000 });
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/set-lineup\.html/, { timeout: 20000 });
  await expect(page).toHaveURL(/game_id=/, { timeout: 20000 });
}

async function simGameToLockerRoom(page, beforeLocker) {
  await startGameToLineup(page);
  await page.locator('#autoset-lineup').click();
  await expect(page.locator('#sim-now')).not.toHaveClass(/disabled/, { timeout: 15000 });
  await page.locator('#sim-now').click();
  await expect(page).toHaveURL(/court\.html/, { timeout: 20000 });
  const tipOff = page.getByRole('button', { name: /Submit & Tip Off|Submit Defense Matchups/ });
  try {
    await tipOff.waitFor({ state: 'visible', timeout: 15000 });
    await tipOff.click();
  } catch (e) { /* matchups are skipped when the gate is off */ }
  const locker = page.locator('a.completion-button.locker-room-button');
  await expect(locker).toBeVisible({ timeout: 45000 });
  if (beforeLocker) await beforeLocker();
  await watchReturn(page);
  await locker.click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
}

async function expectFreshWeek26(page) {
  // Fresh FCC: the new week and the invite step, without any manual reload.
  await expect(page.locator('#gob-week-value')).toHaveText('Week 26', { timeout: 20000 });
  await expect(page.locator('#play-now')).toHaveText('Review Recruit Invites', { timeout: 20000 });
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', 'recruit-invites');
  await expect(page.locator('#play-now')).toBeEnabled();
  // At no point on the way back could the player press anything else.
  expect(await advanceStatesSeen(page)).toEqual([FRESH]);
}

/** The FCC's warm-paint cache (sessionStorage `fcc-shell:<fid>:<team>`), as it holds now. */
async function readFccShellCache(page) {
  await page.waitForFunction(() => Object.keys(sessionStorage).some((k) => k.indexOf('fcc-shell:') === 0));
  return page.evaluate(() => {
    const key = Object.keys(sessionStorage).find((k) => k.indexOf('fcc-shell:') === 0);
    return { key, value: sessionStorage.getItem(key) };
  });
}

test.beforeEach(async ({ page }) => {
  await stubAuth(page);
  await installAdvanceSampler(page);
  page.on('dialog', (dialog) => dialog.accept());
});

test('after a game in an invite week, the FCC shows the new week and the invite step', async ({ page }) => {
  test.setTimeout(150000);
  const state = { week: 25, startWeek: 25, trainingCompleted: true, boardSavedWeek: 25, failFccReads: 0 };
  await installApi(page, state);
  await enterFcc(page);
  await simGameToLockerRoom(page);
  await expectFreshWeek26(page);
});

test('review invites, Play Next Game from the recruiting page, return: fresh week', async ({ page }) => {
  test.setTimeout(150000);
  const state = { week: 25, startWeek: 25, trainingCompleted: true, boardSavedWeek: 24, failFccReads: 0 };
  await installApi(page, state);
  await enterFcc(page);
  await expect(page.locator('#play-now')).toHaveText('Review Recruit Invites');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/recruiting\.html/, { timeout: 20000 });
  await page.waitForFunction(() => document.readyState === 'complete');
  // Invites sent: the recruiting page's own Advance now offers Play Next Game.
  await simGameToLockerRoom(page);
  await expectFreshWeek26(page);
});

test('pre-game warm-paint cache plus a failed first read: the FCC still never offers the old week', async ({ page }) => {
  // The staging symptom. The pre-game FCC's sessionStorage cache (week 25, Play Next
  // Game) outlives the week advance: it is written by the FCC's own late reads and
  // nothing on the game pages clears it. The first read after the advance then fails.
  test.setTimeout(150000);
  const state = { week: 25, startWeek: 25, trainingCompleted: true, boardSavedWeek: 25, failFccReads: 1 };
  await installApi(page, state);
  await enterFcc(page);
  await expect(page.locator('#play-now')).toHaveText('Play Next Game', { timeout: 20000 });
  const preGame = await readFccShellCache(page);
  expect(JSON.parse(preGame.value).topData.week).toBe(25);
  await simGameToLockerRoom(page, async () => {
    await page.evaluate(({ key, value }) => sessionStorage.setItem(key, value), preGame);
  });
  await expectFreshWeek26(page);
});

test('a back-forward-cache restore the nav markers miss still refreshes before Advance is live', async ({ page }) => {
  // Returning to the FCC after ANY flow shows fresh state, even when gobNav has no
  // marker for the return: the restored document checks the server itself. The
  // FCC is not bfcache-eligible in this harness (Back loads it fresh), so the
  // restore is the pageshow Chrome fires for one: persisted, same document.
  test.setTimeout(150000);
  const state = { week: 25, startWeek: 25, trainingCompleted: true, boardSavedWeek: 25, failFccReads: 0 };
  await installApi(page, state);
  await enterFcc(page);
  await expect(page.locator('#play-now')).toHaveText('Play Next Game', { timeout: 20000 });
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 20000 });
  // The week moved on while this document sat in the cache (the game was played).
  state.week = 26;
  state.trainingCompleted = false;
  // Watch from the restore itself: before it, this is the live pre-game FCC.
  await page.evaluate(() => {
    sessionStorage.removeItem('e2e-advance-seen');
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    sessionStorage.setItem('e2e-watch-return', '1');
  });
  await expectFreshWeek26(page);
});
