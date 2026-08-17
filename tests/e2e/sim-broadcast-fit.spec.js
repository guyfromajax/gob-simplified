// @ts-check
/**
 * Sim Broadcast overlay — fit, resting state, bench rails.
 *
 * Loads the REAL simGamePresentation.js / simTimelineAssembler.js modules from the dev
 * server, so the layout under test is the shipped code. Reference measurements come from
 * `_documentation_master/projects/sim-broadcast-handoff/Sim Broadcast - Mockup 1 Rest State.html`
 * ("Worm expands" is the locked treatment): wormblock 276, wormfill 246, slot 200.
 */
const { test, expect } = require('@playwright/test');

const FIT_W = 1228, FIT_H = 572;

const TEAMS = {
  home: { teamName: 'Lancaster', name: 'Lancaster', abbr: 'LAN', color: '#1F8A5B', rank: 12, rec: '3–1' },
  away: { teamName: 'Xavier', name: 'Xavier', abbr: 'XAV', color: '#9E1B32', rank: 20, rec: '2–2' },
};
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];

function player(side, i, over = {}) {
  return {
    id: `${side}${i}`, pos: POS[i], name: `${side === 'home' ? 'Home' : 'Away'} ${i}`,
    jersey: 10 + i, rt: 70, pts: 4, reb: 2, ast: 1, def: 50, fouls: 0,
    hot: false, cold: false, out: false, sub: false, spot: false, ...over,
  };
}
function frame(over = {}) {
  return {
    phase: 'play', quarter: 1,
    score: { away: 2, home: 4, clock: '3:06', quarter: 'Q1', shot: 21, afoul: 1, hfoul: 2 },
    worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed: 174, margin: 2 }], elapsed: 174, domain: 1920, progress: 0.09 },
    teamPanel: null,
    away: POS.map((_, i) => player('away', i)),
    home: POS.map((_, i) => player('home', i)),
    benchAway: [], benchHome: [], ticker: null, ...over,
  };
}

async function mount(page, { width = 1920, height = 1080, frames } = {}) {
  await page.setViewportSize({ width, height });
  await page.goto('/');
  await page.setContent('<div id="scoreboard" style="height:120px;background:#111"></div>');
  // Playback holds each frame 130-900ms and then DISSOLVES AND REMOVES the overlay. A
  // one-frame timeline therefore self-destructs about a second after mount, which the
  // measurements below would lose a race against. Repeat the resting frame so playback
  // cannot finish while the test is still looking at it.
  const list = frames || [frame()];
  const padded = Array.from({ length: 400 }, (_, i) => list[Math.min(i, list.length - 1)]);
  await page.evaluate(async ({ teams, frames }) => {
    const mod = await import('/js/phaser/utils/simGamePresentation.js');
    window.__mod = mod;
    // Never resolves during the test; we only inspect the mounted DOM.
    mod.showSimGamePresentation({ teams, frames }, { driveScoreboard: false });
  }, { teams: TEAMS, frames: padded });
  await page.waitForSelector('.sgp-root [data-fit]');
  await page.waitForTimeout(250);
  const alive = await page.evaluate(() => {
    const r = document.querySelector('.sgp-root');
    return !!r && !r.classList.contains('dissolving');
  });
  expect(alive, 'overlay tore itself down before the assertions ran').toBe(true);
}

const box = (page, sel) => page.evaluate((s) => {
  const e = document.querySelector(s);
  if (!e) return null;
  const r = e.getBoundingClientRect();
  const cs = getComputedStyle(e);
  return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top),
           layoutW: e.offsetWidth, layoutH: e.offsetHeight, shadow: cs.boxShadow };
}, sel);

test.describe('fit: scale, never stretch', () => {
  test('the content box keeps its authored 1228x572 layout size at every viewport', async ({ page }) => {
    for (const [w, h] of [[1280, 720], [1920, 1080], [2560, 1440], [3840, 2160]]) {
      await mount(page, { width: w, height: h });
      const fit = await box(page, '.sgp-root [data-fit]');
      expect(fit.layoutW, `${w}x${h} width`).toBe(FIT_W);
      expect(fit.layoutH, `${w}x${h} height`).toBe(FIT_H);
      // Zone columns and rows must not have absorbed the space instead.
      const zones = await box(page, '.sgp-root .zones');
      const row = await box(page, '.sgp-root .prow');
      expect(zones.layoutH, `${w}x${h} zones`).toBe(512);
      expect(row.layoutH, `${w}x${h} row`).toBe(84);
    }
  });

  test('scales up on a large viewport, uniformly in both axes', async ({ page }) => {
    await mount(page, { width: 2560, height: 1440 });
    const fit = await box(page, '.sgp-root [data-fit]');
    const kx = fit.w / FIT_W, ky = fit.h / FIT_H;
    expect(kx).toBeGreaterThan(1.05);            // actually grew
    expect(Math.abs(kx - ky)).toBeLessThan(0.01); // aspect preserved — scaled, not stretched
  });

  test('caps at 1.6x so portraits do not become cartoonish', async ({ page }) => {
    await mount(page, { width: 3840, height: 2160 });
    const fit = await box(page, '.sgp-root [data-fit]');
    expect(fit.w / FIT_W).toBeLessThanOrEqual(1.6 + 0.01);
    expect(fit.w / FIT_W).toBeGreaterThan(1.55);
  });

  test('never scales below 1.0 — 720p is the floor, not a target to shrink past', async ({ page }) => {
    await mount(page, { width: 1280, height: 720 });
    const fit = await box(page, '.sgp-root [data-fit]');
    expect(fit.w / FIT_W).toBeGreaterThanOrEqual(1);
  });

  test('is anchored to the top edge under the scoreboard', async ({ page }) => {
    await mount(page, { width: 2560, height: 1440 });
    const m = await page.evaluate(() => {
      const root = document.querySelector('.sgp-root');
      const ov = root.querySelector('.overlay');
      const fit = root.querySelector('[data-fit]');
      const pad = parseFloat(getComputedStyle(ov).paddingTop);
      return { fitTop: fit.getBoundingClientRect().top, ovTop: ov.getBoundingClientRect().top, pad,
               scoreboardBottom: document.getElementById('scoreboard').getBoundingClientRect().bottom };
    });
    expect(Math.abs(m.fitTop - (m.ovTop + m.pad))).toBeLessThan(2);
    expect(m.ovTop).toBeGreaterThanOrEqual(m.scoreboardBottom - 1);
  });
});

test.describe('resting state', () => {
  test('worm claims the stage; slot reserved at 200 and invisible', async ({ page }) => {
    await mount(page);
    const wb = await box(page, '.sgp-root .wormblock');
    const wf = await box(page, '.sgp-root .wormfill');
    const slot = await box(page, '.sgp-root .slot');
    expect(wb.layoutH).toBe(276);     // mockup "Worm expands"
    expect(wf.layoutH).toBe(246);
    expect(slot.layoutH).toBe(200);
    expect(slot.shadow).toBe('none'); // no border, no frame — nothing was ever there
  });

  test('no empty bordered container is rendered at rest', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => {
      const slot = document.querySelector('.sgp-root .slot');
      const cs = getComputedStyle(slot);
      return {
        framed: slot.classList.contains('framed'),
        shadow: cs.boxShadow, border: cs.borderWidth,
        bg: cs.backgroundColor,
        visibleKids: [...slot.children].filter((c) => getComputedStyle(c).display !== 'none').length,
      };
    });
    expect(m.framed).toBe(false);
    expect(m.shadow).toBe('none');
    expect(parseFloat(m.border)).toBe(0);
    expect(m.bg === 'rgba(0, 0, 0, 0)' || m.bg === 'transparent').toBe(true);
    expect(m.visibleKids).toBe(0);
  });

  test('the stage never changes size between resting worm and team panel', async ({ page }) => {
    await mount(page);
    const before = await box(page, '.sgp-root .stage');
    const wormBlockBefore = await box(page, '.sgp-root .wormblock');
    await page.click('.sgp-root .ctlseg [data-v="team"]');
    await page.waitForTimeout(150);
    const after = await box(page, '.sgp-root .stage');
    const slotAfter = await box(page, '.sgp-root .slot');
    expect(after.layoutH).toBe(before.layoutH);
    expect(slotAfter.layoutH).toBe(200);
    expect(await page.locator('.sgp-root [data-team-panel]').isVisible()).toBe(true);
    // Worm gives back nothing — the panel occupies the already-reserved band.
    expect((await box(page, '.sgp-root .wormblock')).layoutH).toBe(wormBlockBefore.layoutH);
  });
});

test.describe('bench rails', () => {
  const chip = (n, over = {}) => ({ name: n, pts: 0, reb: 0, out: false, ...over });

  test('hidden entirely when empty — no lone BENCH label at tip-off', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      away: document.querySelector('[data-bench="away"]').innerHTML.trim(),
      home: document.querySelector('[data-bench="home"]').innerHTML.trim(),
      labels: document.querySelectorAll('.sgp-root .bench-lbl').length,
    }));
    expect(m.away).toBe('');
    expect(m.home).toBe('');
    expect(m.labels).toBe(0);
  });

  test('caps at 3 chips and collapses the rest to +N', async ({ page }) => {
    await mount(page, { frames: [frame({
      benchAway: ['A', 'B', 'C', 'D', 'E'].map((n) => chip(n)),
      benchHome: [chip('H1'), chip('H2')],
    })] });
    const m = await page.evaluate(() => {
      const rail = document.querySelector('[data-bench="away"]');
      return {
        chips: rail.querySelectorAll('.bchip').length,
        names: [...rail.querySelectorAll('.bchip b')].map((b) => b.textContent),
        home: document.querySelectorAll('[data-bench="home"] .bchip').length,
      };
    });
    expect(m.chips).toBe(4);                              // 3 + the overflow chip
    expect(m.names).toEqual(['A', 'B', 'C', '+2']);
    expect(m.home).toBe(2);                               // under the cap, no +N
  });

  test('names are never truncated — the chip carries identity', async ({ page }) => {
    await mount(page, { frames: [frame({ benchAway: [chip('Ellis Clemons', { out: true })] })] });
    const m = await page.evaluate(() => {
      const b = document.querySelector('[data-bench="away"] .bchip b');
      return { text: b.textContent, clipped: b.scrollWidth > b.clientWidth + 1,
               stat: document.querySelector('[data-bench="away"] .bstat').textContent };
    });
    expect(m.text).toBe('Ellis Clemons');
    expect(m.clipped).toBe(false);
    expect(m.stat).toBe('0p');          // rebounds dropped; points remain
  });

  test('the common case — three chips, one OUT — fits the rail without clipping', async ({ page }) => {
    await mount(page, { frames: [frame({
      benchAway: [chip('Ellis Clemons', { pts: 0, out: true }), chip('Marcus Webb', { pts: 2 }), chip('Ray Ford')],
    })] });
    const m = await page.evaluate(() => {
      const rail = document.querySelector('[data-bench="away"]');
      return { rail: rail.clientWidth, content: rail.scrollWidth,
               names: [...rail.querySelectorAll('.bchip b')].map((b) => b.textContent) };
    });
    expect(m.content).toBeLessThanOrEqual(m.rail);
    expect(m.names).toEqual(['Ellis Clemons', 'Marcus Webb', 'Ray Ford']);
  });

  test('chips never shrink — rail density does not change with roster events', async ({ page }) => {
    await mount(page, { frames: [frame({ benchAway: [chip('Ellis Clemons', { out: true })] })] });
    const one = await page.evaluate(() =>
      document.querySelector('[data-bench="away"] .bchip').getBoundingClientRect().width);
    await mount(page, { frames: [frame({
      benchAway: [chip('Ellis Clemons', { out: true }), chip('Marcus Webb'), chip('Ray Ford')],
    })] });
    const three = await page.evaluate(() =>
      document.querySelector('[data-bench="away"] .bchip').getBoundingClientRect().width);
    expect(Math.abs(one - three)).toBeLessThan(1);   // same chip, same size, regardless of neighbours
  });

  test('a fouled-out player carries the red OUT marker', async ({ page }) => {
    await mount(page, { frames: [frame({ benchAway: [chip('Ellis Clemons', { out: true })] })] });
    const m = await page.evaluate(() => {
      const el = document.querySelector('[data-bench="away"] .bout');
      return { text: el && el.textContent, bg: el && getComputedStyle(el).backgroundColor };
    });
    expect(m.text).toBe('OUT');
    expect(m.bg).toBe('rgb(255, 109, 109)');
  });
});

test.describe('worm floor converges', () => {
  /** maxAbs implied by where a known margin lands: margin/maxAbs = reach fraction. */
  async function impliedMax(page, progress, margin) {
    const elapsed = Math.round(progress * 1920);
    await mount(page, { frames: [frame({
      worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed, margin }], elapsed, domain: 1920, progress },
    })] });
    return page.evaluate((mg) => {
      const svg = document.querySelector('.sgp-root .wormsvg');
      const h = Number(svg.getAttribute('viewBox').split(' ')[3]);
      const pts = svg.querySelector('polyline,path[d]');
      const raw = pts.getAttribute('points') || pts.getAttribute('d');
      const ys = String(raw).match(/[-\d.]+/g).map(Number).filter((_, i) => i % 2 === 1);
      const pad = 6, mid = h / 2;
      const reach = (mid - Math.min(...ys)) / (mid - pad);
      return reach > 0 ? mg / reach : null;
    }, margin);
  }

  test('holds about +/-18 at tip and about +/-6 at final', async ({ page }) => {
    const atTip = await impliedMax(page, 0, 4);
    const atFinal = await impliedMax(page, 1, 4);
    expect(atTip).toBeGreaterThan(16);
    expect(atTip).toBeLessThan(20);
    expect(atFinal).toBeGreaterThan(5);
    expect(atFinal).toBeLessThan(7);
  });

  test('eases monotonically between the two', async ({ page }) => {
    const seq = [];
    for (const p of [0, 0.25, 0.5, 0.75, 1]) seq.push(await impliedMax(page, p, 4));
    for (let i = 1; i < seq.length; i += 1) expect(seq[i]).toBeLessThan(seq[i - 1]);
  });

  test('auto-fit still overrides the floor when the game is wider than it', async ({ page }) => {
    const wide = await impliedMax(page, 0.1, 30);   // 30-point margin early
    expect(wide).toBeGreaterThan(28);               // fitted to the extreme, not held at ~17
  });

  test('flattens the reported Q1 frame relative to a flat +/-6 floor', async ({ page }) => {
    // 3:06 of Q1 = 174s of 1920. Slope scales as 1/maxAbs, so the reduction is 6/maxAbs.
    const at306 = await impliedMax(page, 174 / 1920, 2);
    expect(6 / at306).toBeLessThan(0.5);            // at least halves the slope
  });
});

test.describe('team stats: fouls pill', () => {
  const AWAY_COLOR = 'rgb(158, 27, 50)';   // #9E1B32
  const HOME_COLOR = 'rgb(31, 138, 91)';   // #1F8A5B

  async function foulsRow(page, awayFouls, homeFouls) {
    const side = (f) => ({ reb: 10, to: 5, fb: 4, paint: 8, fgm: 9, fga: 20, fgPct: 45, tpm: 2, fouls: f });
    await mount(page, { frames: [frame({ teamPanel: { away: side(awayFouls), home: side(homeFouls) } })] });
    await page.click('.sgp-root .ctlseg [data-v="team"]');
    await page.waitForTimeout(150);
    return page.evaluate(() => {
      const row = document.querySelector('.tsr[data-stat="fouls"]');
      const pull = row.querySelector('.pull');
      const cs = getComputedStyle(pull);
      const rowBox = row.querySelector('.tug').getBoundingClientRect();
      const pullBox = pull.getBoundingClientRect();
      return {
        bg: cs.backgroundColor,
        width: cs.width,
        // Which half of the track the bar occupies.
        towardAway: pullBox.left + pullBox.width / 2 < rowBox.left + rowBox.width / 2,
        awayLead: row.querySelector('.va').classList.contains('lead'),
        homeLead: row.querySelector('.vh').classList.contains('lead'),
      };
    });
  }

  test('grows toward the team with MORE fouls, in that team colour', async ({ page }) => {
    const homeInTrouble = await foulsRow(page, 2, 7);
    expect(homeInTrouble.towardAway).toBe(false);      // pulls to the home side
    expect(homeInTrouble.bg).toBe(HOME_COLOR);

    const awayInTrouble = await foulsRow(page, 8, 3);
    expect(awayInTrouble.towardAway).toBe(true);
    expect(awayInTrouble.bg).toBe(AWAY_COLOR);
  });

  test('the white value highlight still marks the FEWER-fouls team', async ({ page }) => {
    const m = await foulsRow(page, 2, 7);
    expect(m.awayLead).toBe(true);    // away has fewer fouls — still the better number
    expect(m.homeLead).toBe(false);
  });

  test('level fouls leave the pill empty', async ({ page }) => {
    const m = await foulsRow(page, 4, 4);
    expect(m.width).toBe('0px');
  });

  test('turnovers are untouched — still toward the team with FEWER', async ({ page }) => {
    const side = (to) => ({ reb: 10, to, fb: 4, paint: 8, fgm: 9, fga: 20, fgPct: 45, tpm: 2, fouls: 4 });
    await mount(page, { frames: [frame({ teamPanel: { away: side(2), home: side(9) } })] });
    await page.click('.sgp-root .ctlseg [data-v="team"]');
    await page.waitForTimeout(150);
    const m = await page.evaluate(() => {
      const row = document.querySelector('.tsr[data-stat="to"]');
      const pull = row.querySelector('.pull');
      const track = row.querySelector('.tug').getBoundingClientRect();
      const box = pull.getBoundingClientRect();
      return { bg: getComputedStyle(pull).backgroundColor,
               towardAway: box.left + box.width / 2 < track.left + track.width / 2 };
    });
    expect(m.towardAway).toBe(true);   // away committed fewer turnovers
    expect(m.bg).toBe(AWAY_COLOR);
  });
});
