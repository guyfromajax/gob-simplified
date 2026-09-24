const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { courtUrl, waitForCanonicalRosters } = require('./helpers/rosters');

const FRAME_DIR = path.join(__dirname, '../../reports/game-start-frames');

async function sampleCover(page) {
  return page.evaluate(() => {
    function kindOf(el) {
      let node = el;
      while (node && node !== document.documentElement) {
        const cl = node.classList;
        if (cl) {
          if (node.id === 'page-load-overlay' || cl.contains('page-load-overlay')) return 'overlay';
          if (cl.contains('pgxp-bridge')) return 'bridge';
          if (cl.contains('pgxp-root') || cl.contains('pgxp-tipoff')) return 'preview';
          if (cl.contains('defense-matchups-popup') || cl.contains('defense-matchups-content') || cl.contains('dm-m-submit')) return 'matchups';
          if (cl.contains('pre-game-container') || cl.contains('pre-game-modal') || cl.contains('pre-game-backdrop') || node.id === 'resume-game-container') return 'pregame';
          if (node.id === 'scoreboard') return 'scoreboard';
          if (node.id === 'phaser-container' || node.tagName === 'CANVAS') return 'court';
        }
        node = node.parentElement;
      }
      return 'other';
    }
    const points = [
      ['scoreboard', window.innerWidth / 2, 28],
      ['court', window.innerWidth / 2, window.innerHeight * 0.45],
    ];
    const samples = {};
    for (const [name, x, y] of points) {
      const el = document.elementFromPoint(x, y);
      samples[name] = {
        kind: kindOf(el),
        id: el && el.id ? el.id : '',
        cls: el && el.className && typeof el.className === 'string' ? el.className.slice(0, 120) : '',
      };
    }
    samples.url = location.search;
    samples.bridge = !!document.querySelector('.pgxp-root.pgxp-bridge');
    samples.preview = !!document.querySelector('.pgxp-root:not(.pgxp-bridge)');
    samples.matchups = !!document.querySelector('.defense-matchups-popup');
    return samples;
  });
}

async function frameStrip(page, name, { ms = 6000, stopWhen } = {}) {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
  const frames = [];
  const leaks = [];
  const started = Date.now();
  let i = 0;
  while (Date.now() - started < ms) {
    const sample = await sampleCover(page);
    const file = path.join(FRAME_DIR, `${name}-${String(i).padStart(3, '0')}.png`);
    await page.screenshot({ path: file });
    const row = { t: Date.now() - started, file: path.basename(file), sample };
    frames.push(row);
    for (const point of ['scoreboard', 'court']) {
      const kind = sample[point].kind;
      if (kind === 'scoreboard' || kind === 'court' || kind === 'other') {
        leaks.push({ t: row.t, point, kind, id: sample[point].id, cls: sample[point].cls });
      }
    }
    if (stopWhen && stopWhen(sample)) break;
    await page.waitForTimeout(150);
    i += 1;
  }
  fs.writeFileSync(path.join(FRAME_DIR, `${name}.json`), JSON.stringify({ frames, leaks }, null, 2));
  return { frames, leaks };
}

test.beforeEach(async ({ page, request }) => {
  await stubAuth(page);
  page.on('dialog', (dialog) => dialog.dismiss());
  await waitForCanonicalRosters(request);
});

test('set lineup offers Play and Sim with the locked labels', async ({ page }) => {
  await page.route('**/api/validate-pointer**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true }),
  }));
  await page.route('**/api/game/**', (route) => route.fulfill({
    status: 404,
    contentType: 'application/json',
    body: '{}',
  }));
  await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
  await expect(page.locator('#play-now')).toHaveText('Play Game', { timeout: 15000 });
  await expect(page.locator('#sim-now')).toHaveText('Sim Game');
  await expect(page.locator('#sim-now')).toHaveClass(/lineup-btn-ghost/);
  await expect(page.locator('#play-now')).toHaveClass(/lineup-btn-green/);

  await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home&mode=single&game_id=g-q2&quarter=2');
  await expect(page.locator('#play-now')).toHaveText('Play Quarter', { timeout: 15000 });
  await expect(page.locator('#sim-now')).toHaveText('Sim Rest Of Game');

  await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home&mode=single&game_id=g-to&quarter=2&resume_from_timeout=true');
  await expect(page.locator('#play-now')).toHaveText('Return to Game', { timeout: 15000 });
  await expect(page.locator('#sim-now')).toBeHidden();
  const tookFocus = await page.locator('#sim-now').evaluate((btn) => {
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    btn.focus();
    return document.activeElement === btn;
  });
  expect(tookFocus).toBe(false);
  await page.waitForTimeout(400);
  expect(page.url()).toContain('set-lineup.html');
  expect(page.url()).not.toContain('court_start');
});

test('fallback pre-game modal covers the court and the scoreboard', async ({ page }) => {
  await page.goto(courtUrl());
  await expect(page.getByRole('button', { name: 'Play Quarter' })).toBeVisible({ timeout: 15000 });
  const box = await page.locator('.pre-game-container').first().evaluate((el) => {
    const cs = getComputedStyle(el);
    const backdrop = el.querySelector('.pre-game-backdrop');
    const bcs = backdrop ? getComputedStyle(backdrop) : null;
    return {
      position: cs.position,
      zIndex: cs.zIndex,
      background: cs.backgroundColor,
      backdrop: bcs ? bcs.backgroundColor : '',
    };
  });
  expect(box.position).toBe('fixed');
  expect(Number(box.zIndex)).toBeGreaterThan(1000);
  const sample = await sampleCover(page);
  expect(sample.scoreboard.kind).toBe('pregame');
  expect(sample.court.kind).toBe('pregame');
  fs.mkdirSync(FRAME_DIR, { recursive: true });
  await page.screenshot({ path: path.join(FRAME_DIR, 'fallback-pregame.png') });
});

test('court_start=play strips the param and keeps a cover up', async ({ page }) => {
  test.setTimeout(45000);
  await page.goto(`${courtUrl()}&court_start=play`);
  await page.waitForFunction(() => !new URLSearchParams(location.search).has('court_start'), null, { timeout: 15000 });
  const { leaks } = await frameStrip(page, 'q1-play', {
    ms: 6000,
    stopWhen: (sample) => sample.matchups || sample.preview,
  });
  const early = leaks.filter((leak) => leak.kind === 'scoreboard' || leak.kind === 'court');
  expect(early, JSON.stringify(early.slice(0, 4))).toEqual([]);
});

test('court_start=sim strips the param and keeps a cover up', async ({ page }) => {
  test.setTimeout(45000);
  await page.goto(`${courtUrl()}&court_start=sim`);
  await page.waitForFunction(() => !new URLSearchParams(location.search).has('court_start'), null, { timeout: 15000 });
  const { leaks } = await frameStrip(page, 'q1-sim', {
    ms: 6000,
    stopWhen: (sample) => sample.preview,
  });
  const early = leaks.filter((leak) => leak.kind === 'scoreboard' || leak.kind === 'court');
  if (early.length) {
    await expect(page.locator('body')).toContainText(/simulation failed/i);
  }
});

test('refresh after court_start is stripped does not auto-start again', async ({ page }) => {
  await page.goto(`${courtUrl()}&court_start=play`);
  await page.waitForFunction(() => !new URLSearchParams(location.search).has('court_start'), null, { timeout: 15000 });
  await page.reload();
  await page.waitForTimeout(1500);
  expect(new URL(page.url()).searchParams.has('court_start')).toBe(false);
  await expect(page.getByRole('button', { name: 'Play Quarter' })).toBeVisible({ timeout: 15000 });
  const sample = await sampleCover(page);
  expect(sample.bridge).toBe(false);
  expect(sample.scoreboard.kind).toBe('pregame');
});

test('lineup-for-matchups 404 clears the bridge', async ({ page }) => {
  await page.route('**/lineup-for-matchups**', (route) => route.fulfill({
    status: 404,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'missing' }),
  }));
  await page.goto(`${courtUrl()}&court_start=play`);
  await page.waitForSelector('.pgxp-root.pgxp-bridge', { timeout: 15000 });
  await page.evaluate(async () => {
    const mod = await import('/js/phaser/utils/defenseMatchupsPopup.js');
    await mod.showDefenseMatchupsPopup('missing-game', { quarter: 1 }, { isQ1Start: true });
  });
  await expect.poll(() => page.locator('.pgxp-root.pgxp-bridge').count()).toBe(0);
  fs.mkdirSync(FRAME_DIR, { recursive: true });
  await page.screenshot({ path: path.join(FRAME_DIR, 'lineup-404.png') });
});
