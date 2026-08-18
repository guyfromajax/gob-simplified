// @ts-check
/**
 * Sim Broadcast cards (brief §8) — the four types in the directed slot.
 *
 * SKIPPED (Mockup 4): directed cards / three-zone stage / Highlights↔Team Stats switch
 * were removed in favour of worm callouts + always-visible team stats. Keep this file
 * for history until callout e2e coverage replaces it.
 *
 * Reference: `Sim Broadcast - Mockup 2 Cards.html`.
 */
const { test, expect } = require('@playwright/test');

const TEAMS = {
  home: { teamName: 'Lancaster', name: 'Lancaster', abbr: 'LAN', color: '#1F8A5B', rank: 12, rec: '3–1' },
  away: { teamName: 'Xavier', name: 'Xavier', abbr: 'XAV', color: '#9E1B32', rank: 20, rec: '2–2' },
};
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const player = (side, i) => ({
  id: `${side}${i}`, pos: POS[i], name: `${side} ${i}`, jersey: 10 + i, rt: 70,
  pts: 4, reb: 2, ast: 1, def: 50, fouls: 0,
  hot: false, cold: false, out: false, sub: false, spot: false,
});
const teamPanel = (over = {}) => ({
  away: { reb: 18, to: 9, fb: 6, paint: 14, fgm: 12, fga: 30, fgPct: 40, tpm: 3, fouls: 7, ...(over.away || {}) },
  home: { reb: 22, to: 5, fb: 15, paint: 20, fgm: 14, fga: 28, fgPct: 50, tpm: 5, fouls: 4, ...(over.home || {}) },
});
const frame = (over = {}) => ({
  phase: 'play', quarter: 2,
  score: { away: 30, home: 36, clock: '4:10', quarter: 'Q2', shot: 18, afoul: 3, hfoul: 2 },
  worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed: 700, margin: 6 }], elapsed: 700, domain: 1920, progress: 0.36 },
  teamPanel: teamPanel(),
  away: POS.map((_, i) => player('away', i)),
  home: POS.map((_, i) => player('home', i)),
  benchAway: [], benchHome: [], ticker: null, ...over,
});

async function mount(page, opts = {}) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto('/');
  await page.addScriptTag({ url: '/js/config/api-config.js' });
  await page.setContent('<div id="scoreboard" style="height:120px;background:#111"></div>');
  await page.addScriptTag({ url: '/js/config/api-config.js' });
  const padded = Array.from({ length: 400 }, () => opts.frame || frame());
  await page.evaluate(async ({ teams, frames }) => {
    const mod = await import('/js/phaser/utils/simGamePresentation.js');
    const copy = await import('/js/phaser/utils/simMomentCopy.js');
    window.__pack = await copy.loadMomentCopy();
    window.__pick = copy.pickLine;
    mod.showSimGamePresentation({ teams, frames }, { driveScoreboard: false });
  }, { teams: TEAMS, frames: padded });
  await page.waitForSelector('.sgp-root [data-fit]');
  await page.waitForFunction(() => !!document.querySelector('.sgp-root').__cards);
}

/** Build a card model the way the cadence engine will: copy from the pack, numbers from the frame. */
const show = (page, model) => page.evaluate((m) => {
  const root = document.querySelector('.sgp-root');
  return root.__cards.showCard(m);
}, model);

const momentModel = (page, id, values) => page.evaluate(({ id, values }) => {
  const p = window.__pick(window.__pack, id, values, () => 0);
  return p && { kind: 'moment', tag: p.tag, color: p.color, line: p.line, sub: null };
}, { id, values });

// Mockup 4 removed directed cards / three-zone stage / Highlights↔Team Stats switch.
test.describe.skip('the four types', () => {
  test('a moment card shows a tag and a one-line stat readout', async ({ page }) => {
    await mount(page);
    const model = await momentModel(page, 'bucket', { NAME: 'REYES', PTS: 24, FGM: 9, FGA: 14, LAST: 2, REB: 5, AST: 3 });
    expect(await show(page, model)).toBe(true);
    const m = await page.evaluate(() => {
      const c = document.querySelector('.sgp-root [data-card]');
      return { kind: c.dataset.kind, tag: c.querySelector('.ctag').textContent.trim(),
               line: c.querySelector('.cline').textContent.trim(),
               lines: c.querySelectorAll('.cline').length };
    });
    expect(m.kind).toBe('moment');
    expect(m.tag).toBe('BUCKET');
    expect(m.lines).toBe(1);                 // one line, not a paragraph
    expect(m.line).not.toMatch(/\{[A-Z]+\}/);
    expect(m.line).toContain('REYES');
  });

  test('a run card carries the RUN tag', async ({ page }) => {
    await mount(page);
    const model = await momentModel(page, 'run', { TEAM: 'LANCASTER', RUN: '11–0' });
    await show(page, { ...model, kind: 'run' });
    const m = await page.evaluate(() => {
      const c = document.querySelector('.sgp-root [data-card]');
      return { kind: c.dataset.kind, tag: c.querySelector('.ctag').textContent.trim(),
               line: c.querySelector('.cline').textContent.trim() };
    });
    expect(m.kind).toBe('run');
    expect(m.tag).toBe('RUN');
    expect(m.line).toContain('LANCASTER');
  });

  test('a margin card promotes the tug: two values plus the bar, no headline text', async ({ page }) => {
    await mount(page);
    await show(page, { kind: 'margin', color: 'blue', sub: null,
                       margin: { label: 'FAST BREAK', away: 6, home: 15 } });
    const m = await page.evaluate(() => {
      const c = document.querySelector('.sgp-root [data-card]');
      const vals = [...c.querySelectorAll('.cmval')].map((v) => v.textContent.trim());
      const pull = c.querySelector('.cmtug .pull');
      const tug = c.querySelector('.cmtug').getBoundingClientRect();
      const box = pull.getBoundingClientRect();
      return { tag: c.querySelector('.ctag').textContent.trim(), vals,
               hasHeadline: !!c.querySelector('.cline'),
               towardHome: box.left + box.width / 2 > tug.left + tug.width / 2,
               width: box.width };
    });
    expect(m.tag).toBe('FAST BREAK');
    expect(m.vals).toEqual(['6', '15']);
    expect(m.hasHeadline).toBe(false);       // it is a promoted bar, not a sentence
    expect(m.towardHome).toBe(true);         // home leads fast break
    expect(m.width).toBeGreaterThan(0);
  });

  test('a context card pairs the setting with the outcome and asserts nothing', async ({ page }) => {
    await mount(page);
    const ctx = await page.evaluate(() => window.__pack.context[0]);
    await show(page, { kind: 'context', color: 'gold',
                       ctx, sub: `${ctx.base} · ${ctx.league}` });
    const m = await page.evaluate(() => {
      const c = document.querySelector('.sgp-root [data-card]');
      return { setting: c.querySelector('.cset').textContent.trim(),
               n: c.querySelector('.cbig .n').textContent.trim(),
               label: c.querySelector('.cbig .l').textContent.trim(),
               sub: c.querySelector('.csub').textContent.trim(),
               text: c.textContent.toLowerCase() };
    });
    expect(m.setting).toContain(':');
    expect(m.n).toBeTruthy();
    expect(m.label).toBeTruthy();
    expect(m.sub).toContain('avg');
    // No causation, no probability — the viewer draws the conclusion.
    for (const banned of ['because', 'caused', 'due to', 'chance', 'probability', 'likely', '%']) {
      expect(m.text, banned).not.toContain(banned);
    }
  });
});

test.describe.skip('presentation', () => {
  test('the stage does not change size when a card arrives or leaves', async ({ page }) => {
    await mount(page);
    const h = () => page.evaluate(() => ({
      stage: document.querySelector('.sgp-root .stage').offsetHeight,
      slot: document.querySelector('.sgp-root .slot').offsetHeight,
      worm: document.querySelector('.sgp-root .wormblock').offsetHeight,
    }));
    const before = await h();
    await show(page, { kind: 'margin', color: 'blue', margin: { label: 'REBOUNDS', away: 18, home: 22 } });
    const during = await h();
    await page.evaluate(() => document.querySelector('.sgp-root').__cards.endCard());
    const after = await h();
    expect(during).toEqual(before);
    expect(after).toEqual(before);
  });

  test('boards dim to brightness .72 under a card — never the quarter-break blur', async ({ page }) => {
    await mount(page);
    await show(page, { kind: 'moment', tag: 'BOARD', color: 'blue', line: 'X 10 REB' });
    // .board transitions filter over .18s, so an immediate read is mid-interpolation.
    // Waiting for it to settle both waits and asserts: a value that never arrives times out.
    await page.waitForFunction(() =>
      getComputedStyle(document.querySelector('.sgp-root .board')).filter === 'brightness(0.72)',
    null, { timeout: 2000 });
    const during = await page.evaluate(() => {
      const cs = getComputedStyle(document.querySelector('.sgp-root .board'));
      return { filter: cs.filter, opacity: cs.opacity };
    });
    expect(during.filter).toBe('brightness(0.72)');
    expect(during.filter).not.toContain('blur');
    expect(Number(during.opacity)).toBe(1);

    await page.evaluate(() => document.querySelector('.sgp-root').__cards.endCard());
    await page.waitForFunction(() => {
      const f = getComputedStyle(document.querySelector('.sgp-root .board')).filter;
      return f === 'none' || f === 'brightness(1)';
    }, null, { timeout: 2000 });
  });

  test('entry animates but the settled card carries no transform', async ({ page }) => {
    await mount(page);
    await show(page, { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'X 12 PTS' });
    const entering = await page.evaluate(() => {
      const c = document.querySelector('.sgp-root [data-card]');
      return { hasEnter: c.classList.contains('enter'), transition: getComputedStyle(c).transitionDuration };
    });
    expect(entering.transition).toContain('0.18s');
    await page.waitForFunction(() => !document.querySelector('.sgp-root [data-card]').classList.contains('enter'));
    // The transform is still easing back to identity for 180ms after the class drops.
    await page.waitForFunction(() => {
      const t = getComputedStyle(document.querySelector('.sgp-root [data-card]')).transform;
      return t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)';
    }, null, { timeout: 2000 });
  });

  test('the card clears itself after the 2.6s hold', async ({ page }) => {
    await mount(page);
    await show(page, { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'X 12 PTS' });
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(1);
    await page.waitForTimeout(1500);
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(1);   // still up mid-hold
    await page.waitForFunction(() => !document.querySelector('.sgp-root [data-card]'), null, { timeout: 4000 });
    const dim = await page.evaluate(() =>
      document.querySelector('.sgp-root .zones').classList.contains('is-carddim'));
    expect(dim).toBe(false);
  });

  test('only one card is up at a time', async ({ page }) => {
    await mount(page);
    expect(await show(page, { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'FIRST' })).toBe(true);
    expect(await show(page, { kind: 'moment', tag: 'DIME', color: 'blue', line: 'SECOND' })).toBe(false);
    const m = await page.evaluate(() => ({
      count: document.querySelectorAll('.sgp-root [data-card]').length,
      line: document.querySelector('.sgp-root .cline').textContent.trim(),
    }));
    expect(m.count).toBe(1);
    expect(m.line).toBe('FIRST');
  });
});

test.describe.skip('team stats is a hold mode', () => {
  test('all card types are suppressed while the panel is up, and nothing queues', async ({ page }) => {
    await mount(page);
    await page.click('.sgp-root .ctlseg [data-v="team"]');
    for (const model of [
      { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'X 12 PTS' },
      { kind: 'run', tag: 'RUN', color: 'orange', line: 'LAN 11–0' },
      { kind: 'margin', color: 'blue', margin: { label: 'REBOUNDS', away: 18, home: 22 } },
      { kind: 'context', color: 'gold', ctx: { setting: 'TEMPO', value: 'FAST', stat: 'TURNOVERS', now: '14' } },
    ]) {
      expect(await show(page, model), model.kind).toBe(false);
    }
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(0);

    // Switching back rejoins the live cadence — nothing that was refused reappears.
    await page.click('.sgp-root .ctlseg [data-v="worm"]');
    await page.waitForTimeout(200);
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(0);
    expect(await show(page, { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'LIVE' })).toBe(true);
  });

  test('raising the panel gives the slot back immediately', async ({ page }) => {
    await mount(page);
    await show(page, { kind: 'moment', tag: 'BUCKET', color: 'green', line: 'X 12 PTS' });
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(1);
    await page.click('.sgp-root .ctlseg [data-v="team"]');
    expect(await page.locator('.sgp-root [data-card]').count()).toBe(0);
    const dim = await page.evaluate(() =>
      document.querySelector('.sgp-root .zones').classList.contains('is-carddim'));
    expect(dim).toBe(false);
  });
});
