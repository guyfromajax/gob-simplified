const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

/**
 * WS-3: commitParams must not navigate.
 *
 * Slice-1 unit stubs accept `loc.search = …`, which is a real-browser
 * navigation/reload. Path + query assertions pass after that reload (the
 * new URL is the intended bag). A window sentinel cannot: a reload
 * destroys it. That is the property the stub cannot satisfy vacuously.
 */

const SENTINEL = '__GOB_COMMIT_SENTINEL';

async function openCourt(page, search) {
  await page.goto(`/static/court.html?${search}`);
  await page.waitForFunction(() => window.FranchiseContext && window.FranchiseContext.commitParams);
}

async function plantSentinel(page) {
  await page.evaluate((key) => {
    window[key] = { planted: true };
  }, SENTINEL);
}

async function sentinelAlive(page) {
  return page.evaluate((key) => !!(window[key] && window[key].planted), SENTINEL);
}

async function commitAndHold(page, mutate) {
  // framenavigated also fires on replaceState. load does not — it means
  // location.search (or href) reloaded the document, which kills the sentinel.
  let documentLoads = 0;
  const onLoad = () => { documentLoads += 1; };
  page.on('load', onLoad);
  await plantSentinel(page);
  await page.evaluate(mutate);
  await page.waitForTimeout(300);
  page.off('load', onLoad);
  return documentLoads;
}

test.beforeEach(async ({ page, request }) => {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
});

test.describe('FranchiseContext.commitParams must not navigate', () => {
  test('a window sentinel survives commitParams', async ({ page }) => {
    await openCourt(page, 'home=Lancaster&away=Four-Corners&game_id=probe-sentinel');

    const documentLoads = await commitAndHold(page, () => {
      const p = window.FranchiseContext.toSearchParams();
      p.set('clock', '7:00');
      window.FranchiseContext.commitParams(p);
    });

    expect(documentLoads).toBe(0);
    expect(await sentinelAlive(page)).toBe(true);
    expect(page.url()).toContain('court.html');
    expect(await page.evaluate(() => window.FranchiseContext.get('clock'))).toBe('7:00');
    expect(await page.evaluate(() => window.FranchiseContext.get('game_id'))).toBe('probe-sentinel');
  });

  test('timeout consume stays on court.html', async ({ page }) => {
    await openCourt(
      page,
      'home=Lancaster&away=Four-Corners&resume_from_timeout=true&game_id=probe-timeout&active_resume=true'
    );

    const documentLoads = await commitAndHold(page, () => {
      const p = window.FranchiseContext.toSearchParams();
      p.set('resume_from_timeout', 'false');
      p.delete('active_resume');
      window.FranchiseContext.commitParams(p);
    });

    expect(documentLoads).toBe(0);
    expect(await sentinelAlive(page)).toBe(true);
    expect(page.url()).toContain('court.html');
    expect(await page.evaluate(() => window.FranchiseContext.get('resume_from_timeout'))).toBe('false');
    expect(await page.evaluate(() => window.FranchiseContext.get('active_resume'))).toBeNull();
    expect(await page.evaluate(() => window.FranchiseContext.get('game_id'))).toBe('probe-timeout');
  });

  test('quarter-break consume stays on court.html', async ({ page }) => {
    await openCourt(
      page,
      'home=Lancaster&away=Four-Corners&quarter_break_from=play_quarter&lineup_checkpoint=true&game_id=probe-qbreak'
    );

    const documentLoads = await commitAndHold(page, () => {
      const p = window.FranchiseContext.toSearchParams();
      p.delete('quarter_break_from');
      p.delete('lineup_checkpoint');
      window.FranchiseContext.commitParams(p);
    });

    expect(documentLoads).toBe(0);
    expect(await sentinelAlive(page)).toBe(true);
    expect(page.url()).toContain('court.html');
    expect(await page.evaluate(() => window.FranchiseContext.get('quarter_break_from'))).toBeNull();
    expect(await page.evaluate(() => window.FranchiseContext.get('lineup_checkpoint'))).toBeNull();
    expect(await page.evaluate(() => window.FranchiseContext.get('game_id'))).toBe('probe-qbreak');
  });
});
