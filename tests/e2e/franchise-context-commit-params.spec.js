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

/**
 * Slice 3 reads the flags slice 2 writes. A mismatch here is silent: each
 * file looks fine in isolation and the game just never resumes.
 */
async function openSetLineup(page, search) {
  await page.goto(`/static/set-lineup.html?${search}`);
  await page.waitForFunction(() => window.FranchiseContext && window.FranchiseContext.get);
}

test.describe('set-lineup reads the resume bag slice 2 writes', () => {
  test('timeout path: lineup reads resume_from_timeout and href back to court keeps it', async ({ page }) => {
    await openSetLineup(
      page,
      'home=Lancaster&away=Four-Corners&resume_from_timeout=true&resume_from_anchor=true&quarter_break_from=mid_game_resume&locked_exhausted_user_lineup=true&game_id=probe-timeout-roundtrip&my_team=home'
    );

    const read = await page.evaluate(() => ({
      resume: window.FranchiseContext.get('resume_from_timeout'),
      anchor: window.FranchiseContext.get('resume_from_anchor'),
      qbreak: window.FranchiseContext.get('quarter_break_from'),
      locked: window.FranchiseContext.get('locked_exhausted_user_lineup'),
    }));
    expect(read.resume).toBe('true');
    expect(read.anchor).toBe('true');
    expect(read.qbreak).toBe('mid_game_resume');
    expect(read.locked).toBe('true');

    await page.evaluate(() => {
      const p = window.FranchiseContext.toSearchParams();
      p.set('lineup_checkpoint', 'true');
      if (p.get('quarter_break_from') === 'mid_game_resume') {
        p.set('consume_resume_anchor', 'true');
        p.set('resume_from_anchor', 'true');
      }
      window.location.href = `/court.html?${p.toString()}`;
    });
    await page.waitForURL('**/court.html**');
    await page.waitForFunction(() => window.FranchiseContext && window.FranchiseContext.get);

    expect(await page.evaluate(() => window.FranchiseContext.get('resume_from_timeout'))).toBe('true');
    expect(await page.evaluate(() => window.FranchiseContext.get('resume_from_anchor'))).toBe('true');
    expect(await page.evaluate(() => window.FranchiseContext.get('lineup_checkpoint'))).toBe('true');

    const documentLoads = await commitAndHold(page, () => {
      const p = window.FranchiseContext.toSearchParams();
      p.set('resume_from_timeout', 'false');
      p.delete('resume_from_anchor');
      p.delete('consume_resume_anchor');
      p.delete('active_resume');
      window.FranchiseContext.commitParams(p);
    });
    expect(documentLoads).toBe(0);
    expect(await sentinelAlive(page)).toBe(true);
    expect(page.url()).toContain('court.html');
    expect(await page.evaluate(() => window.FranchiseContext.get('resume_from_timeout'))).toBe('false');
  });

  test('quarter-break path: lineup reads quarter_break_from and href back to court keeps it', async ({ page }) => {
    await openSetLineup(
      page,
      'home=Lancaster&away=Four-Corners&resume_from_timeout=false&quarter_break_from=play_quarter&lineup_checkpoint=true&game_id=probe-qbreak-roundtrip&my_team=home&quarter=2'
    );

    const read = await page.evaluate(() => ({
      resume: window.FranchiseContext.get('resume_from_timeout'),
      qbreak: window.FranchiseContext.get('quarter_break_from'),
      checkpoint: window.FranchiseContext.get('lineup_checkpoint'),
    }));
    expect(read.resume).toBe('false');
    expect(read.qbreak).toBe('play_quarter');
    expect(read.checkpoint).toBe('true');

    await page.evaluate(() => {
      const p = window.FranchiseContext.toSearchParams();
      p.set('lineup_checkpoint', 'true');
      const qbreak = p.get('quarter_break_from');
      if (qbreak) p.set('quarter_break_from', qbreak);
      window.location.href = `/court.html?${p.toString()}`;
    });
    await page.waitForURL('**/court.html**');
    await page.waitForFunction(() => window.FranchiseContext && window.FranchiseContext.get);

    expect(await page.evaluate(() => window.FranchiseContext.get('quarter_break_from'))).toBe('play_quarter');
    expect(await page.evaluate(() => window.FranchiseContext.get('lineup_checkpoint'))).toBe('true');

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
  });
});

