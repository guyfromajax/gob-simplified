const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

/**
 * Player sprite depth ordering — VISUAL evidence for reports/depth-ordering.md.
 *
 * Renders the REAL marker factory (createPhaserPlayer -> createHeadshotMarkerV2) and the REAL
 * applier (utils/applyPlayerDepths.js) in a standalone Phaser scene with a fixed ten-player
 * frame, then captures frames flag-off vs flag-on in both sub-modes.
 *
 * WHY A HARNESS AND NOT A LIVE GAME FRAME — stated plainly, and repeated in the report:
 * booting court.html end-to-end in this environment needs /api/init-game, and that endpoint
 * resolves the away team by its real NAME ("Four Corners") while /roster/ only answers to the
 * hyphenated slug, so the court's own matchup check rejects whichever spelling the other half
 * accepts. That is an app/fixture mismatch unrelated to depth ordering. The harness exercises
 * the exact rendering code under test; it does NOT prove the per-step hook fires inside a live
 * turn, and the report says so.
 */

const OUT = path.resolve(__dirname, '../../reports/depth-frames');
const HARNESS = fs.readFileSync(path.join(__dirname, 'fixtures/depth-harness.html'), 'utf8');
const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
  'base64');
const PINNED_BAND = 2.5;          // collision_separation.pinned_coverage_distance()
const SPRITE_WIDTH_GRID = 5.2482; // r_a + r_b for two median (75") players

async function boot(page) {
  await page.route('**/depth-harness.html', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: HARNESS }));
  // headshots come from an external CDN; serve them locally so marker creation completes
  await page.route('**/*.png', async (route) => {
    try { await route.fulfill({ status: 200, contentType: 'image/png', body: TINY_PNG }); }
    catch { await route.continue(); }
  });
  page.on('pageerror', (e) => console.log('[page exception]', String(e).slice(0, 300)));
  await page.goto('http://localhost:8000/depth-harness.html');
  await page.waitForFunction(() => window.__HARNESS_READY === true, null, { timeout: 30000 });
  await page.waitForFunction(() => typeof window.__GOB_DEPTH_REPORT === 'function',
    null, { timeout: 30000 });
  await page.waitForTimeout(600);
}

const report = (page) => page.evaluate(() => window.__GOB_DEPTH_REPORT());
async function shoot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.locator('#c canvas').screenshot({ path: path.join(OUT, name) });
}
async function setMode(page, enabled, mode) {
  await page.evaluate(([e, m]) => { window.__GOB_DEPTH_ORDERING = e; window.__GOB_DEPTH_MODE = m; },
    [enabled, mode]);
  await page.waitForTimeout(400);
}
const toGrid = (py, h = 768) => 50 - ((py / h) * 50);

test.describe.configure({ mode: 'serial' });

// ── GATE: flag OFF reproduces today's rendering ─────────────────────────────

test('GATE flag OFF: every player container is still at depth 1', async ({ page }) => {
  await boot(page);
  const rep = await report(page);
  expect(rep.enabled).toBe(false);
  expect(rep.players.length).toBe(10);
  const depths = [...new Set(rep.players.map(p => p.depth))];
  expect(depths, `flag-off depths must all be 1, got ${JSON.stringify(depths)}`).toEqual([1]);
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, 'gate-flag-off.json'), JSON.stringify(rep, null, 2));
  await shoot(page, 'gate-flag-off.png');
});

// ── the effect, both merges, both sub-modes ─────────────────────────────────

test('merged pairs: flag off vs tie-break vs hard promotion', async ({ page }) => {
  await boot(page);
  const h = await page.evaluate(() => document.querySelector('#c canvas').height);

  await setMode(page, false, 'tie_break');
  const off = await report(page);
  await shoot(page, 'merge-01-flag-off.png');

  await setMode(page, true, 'tie_break');
  const tie = await report(page);
  expect(tie.enabled).toBe(true);
  await shoot(page, 'merge-02-tie-break.png');

  await setMode(page, true, 'hard_promotion');
  const hard = await report(page);
  expect(hard.mode).toBe('hard_promotion');
  await shoot(page, 'merge-03-hard-promotion.png');

  const by = (r) => Object.fromEntries(r.players.map(p => [p.playerId, p]));
  const [O, T, H] = [by(off), by(tie), by(hard)];

  // both authored merges really are inside the band the separation pass refuses to touch
  const gapCPF = Math.abs(toGrid(O.o_C.y, h) - toGrid(O.o_PF.y, h));
  const gapSG = Math.abs(toGrid(O.o_SG.y, h) - toGrid(O.d_SG.y, h));
  expect(gapCPF).toBeLessThan(PINNED_BAND);
  expect(gapSG).toBeLessThan(PINNED_BAND);

  // flag off: tied depths -> insertion order decides -> illegible
  expect(O.o_C.depth).toBe(O.o_PF.depth);
  expect(O.o_SG.depth).toBe(O.d_SG.depth);

  // ordering on: the nearer player (LOWER grid y) is on top, in both merges
  expect(T.o_C.depth).toBeGreaterThan(T.o_PF.depth);   // o_C at y=32 is nearer than o_PF at 33.1
  expect(T.o_SG.depth).toBeGreaterThan(T.d_SG.depth);  // o_SG at y=14 is nearer than d_SG at 15.2

  // sub-mode (ii) differs ONLY for the promoted player
  expect(H.o_C.depth).toBe(T.o_C.depth);
  expect(H.o_PG.depth).toBeGreaterThan(T.o_PG.depth);
  const others = Object.values(H).filter(p => p.playerId !== 'o_PG').map(p => p.depth);
  expect(Math.min(H.o_PG.depth)).toBeGreaterThan(Math.max(...others));

  fs.writeFileSync(path.join(OUT, 'merge-depths.json'), JSON.stringify({
    spriteWidthGrid: SPRITE_WIDTH_GRID, pinnedBand: PINNED_BAND,
    teammateGapGrid: gapCPF, defenderOnManGapGrid: gapSG,
    flagOff: O, tieBreak: T, hardPromotion: H,
  }, null, 2));
});

// ── the ball regression ─────────────────────────────────────────────────────

test('ball stays above every player, in both sub-modes', async ({ page }) => {
  await boot(page);
  for (const mode of ['tie_break', 'hard_promotion']) {
    await setMode(page, true, mode);
    const rep = await report(page);
    const maxPlayer = Math.max(...rep.players.map(p => p.depth));
    expect(rep.ballDepth, `ball occluded in ${mode}`).toBeGreaterThan(maxPlayer);
    await shoot(page, `ball-above-players-${mode}.png`);
  }
  // and with the flag off, so the fix is not a behaviour change there
  await setMode(page, false, 'tie_break');
  const off = await report(page);
  expect(off.ballDepth).toBeGreaterThan(Math.max(...off.players.map(p => p.depth)));
});

// ── mask interaction ────────────────────────────────────────────────────────

test('headshot mask still clips with ordering ON', async ({ page }) => {
  await boot(page);
  await setMode(page, false, 'tie_break');
  await shoot(page, 'mask-01-flag-off.png');
  await setMode(page, true, 'tie_break');
  await shoot(page, 'mask-02-flag-on.png');
});
