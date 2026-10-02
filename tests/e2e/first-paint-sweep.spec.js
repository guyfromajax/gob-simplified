// @ts-check
/**
 * First-paint sweep, online: every gallery screen on the hosted profile, with every API
 * response held back 1.5 s.
 *
 * A tool, not a gate: it runs only with FP_SWEEP set. The franchise screens replay the
 * real responses the offline pass recorded (FP_OUT/recordings.json, FP_OUT/ctx.json), so
 * run desktop-first-paint-sweep.spec.js first. Account-free pages hit the hosted server.
 */
const { test } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { delayApi, settle, sweepScreen } = require('./helpers/firstPaint');
const { screens } = require('./helpers/firstPaintScreens');

const PHASE = process.env.FP_SWEEP || '';
const OUT = process.env.FP_OUT || path.join(__dirname, '../../reports/first-paint-sweep/raw');
const DELAY = Number(process.env.FP_DELAY_MS || 1500);
const ONLY = (process.env.FP_ONLY || '').split(',').filter(Boolean);

test.describe.configure({ mode: 'serial', timeout: 1800000 });
test.skip(!PHASE, 'FP_SWEEP only');

test('sweep every screen online', async ({ browser }) => {
  const ctx = JSON.parse(fs.readFileSync(path.join(OUT, 'ctx.json'), 'utf8'));
  ctx.q = (extra) => new URLSearchParams(Object.assign(
    { franchise_id: ctx.fid, team_id: ctx.tid, user_team_id: ctx.tid }, extra || {},
  )).toString();
  const recordings = JSON.parse(fs.readFileSync(path.join(OUT, 'recordings.json'), 'utf8'));
  const anyScreen = {};
  Object.values(recordings).forEach((bag) => Object.assign(anyScreen, bag));
  fs.mkdirSync(path.join(OUT, 'online'), { recursive: true });
  const results = {};

  const list = screens(ctx).filter((s) => !ONLY.length || ONLY.includes(s.id));
  for (const screen of list) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    const page = await context.newPage();
    await stubAuth(page);
    await page.addInitScript(() => { window.alert = () => {}; });
    const own = recordings[screen.id] || {};
    const tracker = await delayApi(page, DELAY, (request) => {
      const pathname = new URL(request.url()).pathname;
      const key = request.method() + ' ' + pathname;
      const hit = own[key] || anyScreen[key];
      if (hit) return { status: hit.status, body: hit.body };
      if (pathname === '/api/auth/me') {
        return { status: 200, body: { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' } };
      }
      return null;
    });
    const shot = (suffix) => page.screenshot({
      path: path.join(OUT, 'online', PHASE + '-' + screen.id + '-' + suffix + '.png'), animations: 'disabled',
    }).catch(() => {});
    const swept = await sweepScreen(page, tracker, screen.url, shot, screen.settings ? {
      before: async () => {
        await settle(page, tracker, 1500, 25000);
        await page.evaluate(() => window.GOBSettings && window.GOBSettings.open && window.GOBSettings.open());
      },
    } : null);
    results[screen.id] = Object.assign({ name: screen.name, owner: screen.owner || '', done: !!screen.done }, swept);
    await context.close();
  }
  fs.writeFileSync(path.join(OUT, 'online', 'results-' + PHASE + '.json'), JSON.stringify(results, null, 2));
});
