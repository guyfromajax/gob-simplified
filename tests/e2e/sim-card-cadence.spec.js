// @ts-check
/**
 * Card cadence (brief §9) — which card, and when.
 *
 * Drives the real CardCadence in the browser with synthetic frames, so the gates, the
 * per-quarter curve and the selection weights under test are the shipped ones.
 */
const { test, expect } = require('@playwright/test');

const TEAMS = { home: { name: 'Lancaster', abbr: 'LAN' }, away: { name: 'Xavier', abbr: 'XAV' } };

async function engine(page, opts = {}) {
  await page.goto('/');
  await page.addScriptTag({ url: '/js/config/api-config.js' });
  await page.evaluate(async ({ teams, seed }) => {
    const { CardCadence } = await import('/js/phaser/utils/simCardCadence.js');
    const { loadMomentCopy } = await import('/js/phaser/utils/simMomentCopy.js');
    const pack = await loadMomentCopy();
    window.__shown = [];
    window.__eng = new CardCadence({
      pack, teams, seed: seed == null ? 7 : seed,
      onCard: (m) => { window.__shown.push(m); return true; },
    });
  }, { teams: TEAMS, seed: opts.seed });
}

/** Feed frames; each step advances playback by `dt` seconds. */
const run = (page, frames, dt) => page.evaluate(({ frames, dt }) => {
  frames.forEach((f) => window.__eng.step(f, dt));
  return { shown: window.__shown.map((c) => ({ kind: c.kind, tag: c.tag, line: c.line })),
           stats: window.__eng.stats() };
}, { frames, dt });

const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
function row(side, i, over = {}) {
  return { id: `${side}${i}`, pos: POS[i], name: `${side === 'home' ? 'Hank' : 'Avery'} ${i}`,
           pts: 6, reb: 3, ast: 2, fgm: 3, fga: 7, fouls: 1, ...over };
}
function frame(over = {}) {
  return {
    quarter: 1,
    score: { away: 20, home: 22 },
    teamPanel: { away: { reb: 18, to: 9, fb: 6, paint: 14, fouls: 7 },
                 home: { reb: 22, to: 5, fb: 15, paint: 20, fouls: 4 } },
    away: POS.map((_, i) => row('away', i)),
    home: POS.map((_, i) => row('home', i)),
    events: [],
    ...over,
  };
}
const bucket = (id) => ({ id, kind: 'bucket', last: 2 });

test.describe('gates', () => {
  test('a card holds the slot for 2.6s and then respects the rest floor and the gap', async ({ page }) => {
    await engine(page);
    // One event per step, 1s of playback each — plenty of supply, so gates are what bind.
    const frames = Array.from({ length: 40 }, () => frame({ events: [bucket('home0')] }));
    const { shown, stats } = await run(page, frames, 1);
    expect(shown.length).toBeGreaterThan(0);
    // Q1 gap is 6.5s and the hold is 2.6s, so cards cannot be closer than the gap.
    const reasons = Object.keys(stats.suppressedByReason);
    expect(reasons).toEqual(expect.arrayContaining(['card up']));
    expect(stats.total).toBeLessThanOrEqual(Math.ceil(40 / 6.5) + 1);
  });

  test('every suppressed candidate keeps a reason — silent drops are untunable', async ({ page }) => {
    await engine(page);
    const frames = Array.from({ length: 30 }, () => frame({ events: [bucket('home0'), bucket('home1')] }));
    const { stats } = await run(page, frames, 1);
    expect(stats.suppressed).toBeGreaterThan(0);
    for (const [reason, n] of Object.entries(stats.suppressedByReason)) {
      expect(reason, 'reason must be a real string').toBeTruthy();
      expect(reason).not.toBe('null');
      expect(n).toBeGreaterThan(0);
    }
  });

  test('the same player cannot carry back-to-back cards inside the cooldown', async ({ page }) => {
    await engine(page);
    const frames = Array.from({ length: 30 }, () => frame({ events: [bucket('home0')] }));
    const { stats } = await run(page, frames, 1);
    expect(Object.keys(stats.suppressedByReason)).toContain('player cooldown');
  });

  test('density climbs from Q1 to Q4 on identical supply', async ({ page }) => {
    const perQuarter = {};
    for (const q of [1, 4]) {
      await engine(page);
      const frames = Array.from({ length: 60 }, () => frame({ quarter: q, events: [bucket('home0'), bucket('away1'), bucket('home2')] }));
      const { stats } = await run(page, frames, 1);
      perQuarter[q] = stats.total;
    }
    expect(perQuarter[4]).toBeGreaterThan(perQuarter[1]);
  });
});

test.describe('selection', () => {
  test('milestones jump the queue and latch — each crossing fires once', async ({ page }) => {
    await engine(page);
    const frames = [];
    // Player crosses 10, then 20, then 30 over a long enough span to clear the gaps.
    for (const pts of [10, 10, 20, 20, 30, 30]) {
      for (let k = 0; k < 8; k += 1) {
        frames.push(frame({ quarter: 2, events: [bucket('home0')],
          home: POS.map((_, i) => (i === 0 ? row('home', 0, { pts, reb: 4 }) : row('home', i))) }));
      }
    }
    const { shown } = await run(page, frames, 1);
    const tags = shown.filter((c) => c.kind === 'moment').map((c) => c.tag);
    expect(tags).toContain('DOUBLE FIGURES');
    expect(tags).toContain('20');
    expect(tags).toContain('30');
    expect(tags.filter((t) => t === '20').length).toBe(1);   // latched
    expect(tags.filter((t) => t === '30').length).toBe(1);
  });

  test('a run of 8+ unanswered fires a RUN card', async ({ page }) => {
    await engine(page);
    const frames = [];
    let home = 20;
    for (let i = 0; i < 12; i += 1) {
      home += 2;
      frames.push(frame({ score: { away: 20, home }, events: [] }));
    }
    const { shown } = await run(page, frames, 2);
    const run8 = shown.find((c) => c.kind === 'run');
    expect(run8).toBeTruthy();
    expect(run8.tag).toBe('RUN');
    expect(run8.line).toContain('LANCASTER');
  });

  test('the margin card promotes whichever tug has the widest edge', async ({ page }) => {
    await engine(page);
    const m = await page.evaluate(async () => {
      const { widestTug } = await import('/js/phaser/utils/simCardCadence.js');
      return {
        fb: widestTug({ away: { reb: 20, to: 10, fb: 2, paint: 20, fouls: 8 },
                        home: { reb: 21, to: 11, fb: 18, paint: 21, fouls: 9 } }),
        reb: widestTug({ away: { reb: 4, to: 10, fb: 10, paint: 20, fouls: 8 },
                         home: { reb: 30, to: 10, fb: 10, paint: 20, fouls: 8 } }),
        level: widestTug({ away: { reb: 10, to: 5, fb: 3, paint: 8, fouls: 4 },
                           home: { reb: 10, to: 5, fb: 3, paint: 8, fouls: 4 } }),
      };
    });
    expect(m.fb.label).toBe('FAST BREAK');
    expect(m.reb.label).toBe('REBOUNDS');
    expect(m.level).toBeNull();       // nothing to promote when every tug is level
  });

  test("quiet players are boosted so the feed is not one player's channel", async ({ page }) => {
    await engine(page);
    // A 24-point headliner and a 2-point role player generate identical events.
    const frames = Array.from({ length: 80 }, () => frame({
      quarter: 3,
      events: [bucket('home0'), bucket('home1')],
      home: POS.map((_, i) => (i === 0 ? row('home', 0, { pts: 24 })
        : i === 1 ? row('home', 1, { pts: 2 }) : row('home', i))),
    }));
    const { shown } = await run(page, frames, 1);
    const names = shown.filter((c) => c.kind === 'moment').map((c) => c.line);
    const quiet = names.filter((l) => l.includes('HANK 1')).length;
    expect(quiet).toBeGreaterThan(0);   // the quiet player gets on screen at all
  });

  test('only a 4th or 5th foul earns a foul card', async ({ page }) => {
    await engine(page);
    const frames = Array.from({ length: 30 }, () => frame({
      quarter: 2, events: [{ id: 'home0', kind: 'foul', last: 1 }],
      home: POS.map((_, i) => (i === 0 ? row('home', 0, { fouls: 2 }) : row('home', i))),
    }));
    const { shown } = await run(page, frames, 1);
    expect(shown.filter((c) => c.tag === 'FOUL').length).toBe(0);
  });
});

test.describe('team stats hold mode', () => {
  test('nothing fires and nothing queues while suspended', async ({ page }) => {
    await engine(page);
    await page.evaluate(() => window.__eng.suspend(true));
    const frames = Array.from({ length: 40 }, () => frame({ events: [bucket('home0')] }));
    const { shown, stats } = await run(page, frames, 1);
    expect(shown.length).toBe(0);
    expect(stats.suppressedByReason['team stats held']).toBeGreaterThan(0);

    // Coming back rejoins the LIVE cadence: the 40 candidates refused while held are gone,
    // so resuming must not dump a backlog — at most a single card on normal gates.
    const after = await page.evaluate(() => {
      window.__eng.suspend(false);
      window.__shown.length = 0;
      for (let i = 0; i < 3; i += 1) {
        window.__eng.step({ quarter: 1, score: { away: 20, home: 22 }, teamPanel: null,
                            away: [], home: [], events: [] }, 1);
      }
      return window.__shown.length;
    });
    expect(after).toBeLessThanOrEqual(1);
  });
});

test('instrumentation reports per-quarter counts and the on-screen share', async ({ page }) => {
  await engine(page);
  const frames = Array.from({ length: 60 }, (_, i) => frame({
    quarter: i < 30 ? 1 : 2, events: [bucket(`home${i % 5}`)],
  }));
  const { stats } = await run(page, frames, 1);
  expect(stats.byQuarter.map((q) => q.q)).toEqual([1, 2, 3, 4]);
  expect(stats.byQuarter[0].fired + stats.byQuarter[1].fired).toBe(stats.total);
  expect(stats.share).toBeGreaterThan(0);
  expect(stats.share).toBeLessThanOrEqual(100);
  expect(stats.counts.moment).toBeGreaterThan(0);
});
