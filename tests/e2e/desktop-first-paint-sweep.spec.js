// @ts-check
/**
 * First-paint sweep, offline: every gallery screen on the desktop SQLite server (a real
 * 128-team league), with every API response held back 1.5 s.
 *
 * A tool, not a gate: it runs only with FP_SWEEP set, under playwright.desktop.config.js.
 *   FP_SWEEP=before|after   label for the shots
 *   FP_OUT=<dir>            where shots, results.json and the recorded API bodies go
 * The recorded bodies are what the online pass (first-paint-sweep.spec.js) replays.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { delayApi, settle, sweepScreen } = require('./helpers/firstPaint');
const { screens } = require('./helpers/firstPaintScreens');

const PHASE = process.env.FP_SWEEP || '';
const OUT = process.env.FP_OUT || path.join(__dirname, '../../reports/first-paint-sweep/raw');
const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const DELAY = Number(process.env.FP_DELAY_MS || 1500);
const ONLY = (process.env.FP_ONLY || '').split(',').filter(Boolean);

test.describe.configure({ mode: 'serial', timeout: 1800000 });
test.skip(!PHASE, 'FP_SWEEP only');

let ctx = null;
const results = {};
const recordings = {};

async function prime(page) {
  await page.addInitScript((port) => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = Number(port);
    window.alert = () => {};
  }, PORT);
}

test.beforeAll(async ({ request }) => {
  fs.mkdirSync(path.join(OUT, 'offline'), { recursive: true });
  const create = await request.post('/franchise/select-team', { data: { team_name: 'Lancaster' } });
  expect(create.ok(), await create.text()).toBeTruthy();
  const fid = (await create.json()).franchise_id;
  const next = await request.post('/franchise/play-next-game', { data: { franchise_id: fid } });
  const m = await next.json();
  const mine = m.home === 'Lancaster';
  const tid = String(mine ? m.home_id : m.away_id);
  const other = String(mine ? m.away_id : m.home_id);
  let playerId = '';
  const roster = await request.get('/franchise/roster?franchise_id=' + fid + '&team_id=' + tid);
  if (roster.ok()) {
    const body = await roster.json();
    const players = body.players || body.roster || (Array.isArray(body) ? body : []);
    const firstPlayer = players[0] || {};
    playerId = String(firstPlayer.player_id || firstPlayer.id || firstPlayer._id || '');
  }
  ctx = {
    fid, tid, otherTeamId: other, playerId,
    week: m.week || 1, home: m.home, away: m.away,
    homeId: String(m.home_id), awayId: String(m.away_id), myTeam: mine ? 'home' : 'away',
    q: (extra) => new URLSearchParams(Object.assign({ franchise_id: fid, team_id: tid, user_team_id: tid }, extra || {})).toString(),
  };
  fs.writeFileSync(path.join(OUT, 'ctx.json'), JSON.stringify(ctx, null, 2));
});

test.afterAll(async ({ request }) => {
  fs.writeFileSync(path.join(OUT, 'offline', 'results-' + PHASE + '.json'), JSON.stringify(results, null, 2));
  fs.writeFileSync(path.join(OUT, 'recordings.json'), JSON.stringify(recordings));
  // Leave the shared desktop e2e sqlite as we found it (two-franchise cap).
  if (ctx && ctx.fid) await request.delete('/franchise/' + ctx.fid).catch(() => {});
});

test('sweep every screen offline', async ({ browser }) => {
  const list = screens(ctx).filter((s) => s.where === 'both' && (!ONLY.length || ONLY.includes(s.id)));
  for (const screen of list) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    const page = await context.newPage();
    await prime(page);
    const recorded = {};
    page.on('response', async (response) => {
      const request = response.request();
      const type = request.resourceType();
      if (type !== 'fetch' && type !== 'xhr') return;
      try {
        const url = new URL(response.url());
        if (/\.(js|css|html|png|jpe?g|svg|gif|json|woff2?)$/i.test(url.pathname)) return;
        const text = await response.text();
        if (text.length > 600000) return;
        recorded[request.method() + ' ' + url.pathname] = { status: response.status(), body: text };
      } catch (err) { /* body gone: page navigated */ }
    });
    const tracker = await delayApi(page, DELAY);
    const shot = (suffix) => page.screenshot({
      path: path.join(OUT, 'offline', PHASE + '-' + screen.id + '-' + suffix + '.png'), animations: 'disabled',
    }).catch(() => {});
    const swept = await sweepScreen(page, tracker, screen.url, shot, screen.settings ? {
      before: async () => {
        await settle(page, tracker, 1500, 25000);
        await page.evaluate(() => window.GOBSettings && window.GOBSettings.open && window.GOBSettings.open());
      },
    } : null);
    results[screen.id] = Object.assign({ name: screen.name, owner: screen.owner || '', done: !!screen.done }, swept);
    recordings[screen.id] = recorded;
    await context.close();
  }
});
