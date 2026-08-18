// @ts-check
/**
 * Sim Broadcast overlay — fit, resting state, bench rails (Mockup 4 · wide worm).
 *
 * Loads the REAL simGamePresentation.js / simTimelineAssembler.js modules from the dev
 * server, so the layout under test is the shipped code. Reference: worm 242 / plot 208 /
 * band 256 (433|330|433) / compact rows 40 / footer 46.
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

/** Prefer Mockup 4 selectors; fall back to legacy names if present. */
const teamStatSel = {
  row: (key) => `.tsr4[data-stat="${key}"], .tsr[data-stat="${key}"]`,
  tug: '.tug4, .tug',
  pull: '.tug4 .pull, .tug .pull, .pull',
};

test.describe('fit: scale, never stretch', () => {
  test('the content box keeps its authored 1228x572 layout size at every viewport', async ({ page }) => {
    for (const [w, h] of [[1280, 720], [1920, 1080], [2560, 1440], [3840, 2160]]) {
      await mount(page, { width: w, height: h });
      const fit = await box(page, '.sgp-root [data-fit]');
      expect(fit.layoutW, `${w}x${h} width`).toBe(FIT_W);
      expect(fit.layoutH, `${w}x${h} height`).toBe(FIT_H);
      // Band and compact rows must not have absorbed the space instead.
      const band = await box(page, '.sgp-root .band');
      const row = await box(page, '.sgp-root .r4');
      expect(band.layoutH, `${w}x${h} band`).toBe(256);
      expect(row.layoutH, `${w}x${h} row`).toBe(40);
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
  test('wide worm claims the stage; plot is 208 and no card slot', async ({ page }) => {
    await mount(page);
    const w4 = await box(page, '.sgp-root .w4');
    const plot = await box(page, '.sgp-root [data-plot]');
    const slot = await page.locator('.sgp-root .slot').count();
    expect(w4.layoutH).toBe(242);
    expect(plot.layoutH).toBe(208);
    expect(slot).toBe(0);
  });

  test('team stats panel is always visible — no toggle required', async ({ page }) => {
    await mount(page);
    const panel = page.locator('.sgp-root [data-team-panel]');
    await expect(panel).toBeVisible();
    expect(await page.locator('.sgp-root .ctlseg').count()).toBe(0);
    expect(await page.locator('.sgp-root [data-highlights]').count()).toBe(1);
    expect(await page.locator('.sgp-root .f4').count()).toBe(1);
  });

  test('band columns stay 433 / 330 / 433 at rest', async ({ page }) => {
    await mount(page);
    const cols = await page.evaluate(() => {
      const band = document.querySelector('.sgp-root .band');
      const panes = [...band.querySelectorAll(':scope > .pane')];
      return panes.map((p) => p.offsetWidth);
    });
    expect(cols).toEqual([433, 330, 433]);
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

test.describe('worm fixed nonlinear compress', () => {
  /** Tip Y in SVG user space for a given margin at game progress (0..1). */
  async function tipY(page, progress, margin) {
    const elapsed = Math.round(progress * 1920);
    await mount(page, { frames: [frame({
      worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed, margin }], elapsed, domain: 1920, progress },
    })] });
    return page.evaluate(() => {
      const dot = document.querySelector('.sgp-root .wormdot');
      return Number(dot.getAttribute('cy'));
    });
  }

  /** Fraction of half-height the tip has climbed (0 = mid, 1 = top pad). */
  async function reachFraction(page, progress, margin) {
    const elapsed = Math.round(progress * 1920);
    await mount(page, { frames: [frame({
      worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed, margin }], elapsed, domain: 1920, progress },
    })] });
    return page.evaluate(() => {
      const svg = document.querySelector('.sgp-root .wormsvg');
      const h = Number(svg.getAttribute('viewBox').split(' ')[3]);
      const cy = Number(document.querySelector('.sgp-root .wormdot').getAttribute('cy'));
      const pad = 10, mid = h / 2;
      return (mid - cy) / (mid - pad);
    });
  }

  test('same margin at tip and late game maps to the same height', async ({ page }) => {
    const atTip = await tipY(page, 0.05, 8);
    const atLate = await tipY(page, 0.95, 8);
    expect(Math.abs(atTip - atLate)).toBeLessThan(0.5);
  });

  test('a 30-point margin sits between the ±10 guide and the top (under-drawn)', async ({ page }) => {
    const reach = await reachFraction(page, 0.5, 30);
    const ratios = await page.evaluate(() => {
      const { compressMargin } = window.__mod;
      const knee = Math.abs(compressMargin(10)) / Math.abs(compressMargin(45));
      const blow = Math.abs(compressMargin(30)) / Math.abs(compressMargin(45));
      return { knee, blow };
    });
    // ±10 guide ≈ 0.588 of half-height; 30pts ≈ compress(30)/compress(45) ≈ 0.824
    expect(ratios.knee).toBeCloseTo(10 / 17, 3);
    expect(ratios.blow).toBeCloseTo(14 / 17, 3);
    expect(reach).toBeGreaterThan(ratios.knee);
    expect(reach).toBeLessThan(1);
    expect(reach).toBeCloseTo(ratios.blow, 2);
  });

  test('compressMargin is exported from the presentation module', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => {
      const { compressMargin } = window.__mod;
      return {
        type: typeof compressMargin,
        at10: compressMargin(10),
        at30: compressMargin(30),
        at45: compressMargin(45),
        atNeg: compressMargin(-12),
      };
    });
    expect(m.type).toBe('function');
    expect(m.at10).toBe(10);
    expect(m.at30).toBe(14);   // 10 + 20 * 0.20
    expect(m.at45).toBe(17);   // 10 + 35 * 0.20
    expect(m.atNeg).toBe(-10.4);
  });
});

test.describe('team stats: fouls pill', () => {
  const AWAY_COLOR = 'rgb(158, 27, 50)';   // #9E1B32
  const HOME_COLOR = 'rgb(31, 138, 91)';   // #1F8A5B

  async function foulsRow(page, awayFouls, homeFouls) {
    const side = (f) => ({ reb: 10, to: 5, fb: 4, paint: 8, fgm: 9, fga: 20, fgPct: 45, tpm: 2, fouls: f });
    await mount(page, { frames: [frame({ teamPanel: { away: side(awayFouls), home: side(homeFouls) } })] });
    // Team panel is always mounted — no ctlseg toggle.
    return page.evaluate(({ rowSel, tugSel, pullSel }) => {
      const row = document.querySelector(rowSel);
      const pull = row.querySelector(pullSel);
      const cs = getComputedStyle(pull);
      const rowBox = row.querySelector(tugSel).getBoundingClientRect();
      const pullBox = pull.getBoundingClientRect();
      return {
        bg: cs.backgroundColor,
        width: cs.width,
        towardAway: pullBox.left + pullBox.width / 2 < rowBox.left + rowBox.width / 2,
        awayLead: row.querySelector('.va').classList.contains('lead'),
        homeLead: row.querySelector('.vh').classList.contains('lead'),
      };
    }, { rowSel: teamStatSel.row('fouls'), tugSel: teamStatSel.tug, pullSel: teamStatSel.pull });
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

  test('turnovers grow toward the team with MORE turnovers', async ({ page }) => {
    const side = (to) => ({ reb: 10, to, fb: 4, paint: 8, fgm: 9, fga: 20, fgPct: 45, tpm: 2, fouls: 4 });
    await mount(page, { frames: [frame({ teamPanel: { away: side(2), home: side(9) } })] });
    const m = await page.evaluate(({ rowSel, tugSel, pullSel }) => {
      const row = document.querySelector(rowSel);
      const pull = row.querySelector(pullSel);
      const track = row.querySelector(tugSel).getBoundingClientRect();
      const box = pull.getBoundingClientRect();
      return { bg: getComputedStyle(pull).backgroundColor,
               towardAway: box.left + box.width / 2 < track.left + track.width / 2 };
    }, { rowSel: teamStatSel.row('to'), tugSel: teamStatSel.tug, pullSel: teamStatSel.pull });
    expect(m.towardAway).toBe(false);  // home committed more turnovers
    expect(m.bg).toBe(HOME_COLOR);
  });

  test('FG% and 3PT tug toward the greater value', async ({ page }) => {
    await mount(page, {
      frames: [frame({
        teamPanel: {
          away: { reb: 10, to: 5, fb: 4, paint: 8, fgm: 9, fga: 20, fgPct: 40, tpm: 2, fouls: 4 },
          home: { reb: 10, to: 5, fb: 4, paint: 8, fgm: 12, fga: 20, fgPct: 55, tpm: 6, fouls: 4 },
        },
      })],
    });
    const m = await page.evaluate(({ tugSel, pullSel }) => {
      const read = (key) => {
        const row = document.querySelector(`.tsr4[data-stat="${key}"], .tsr[data-stat="${key}"]`);
        const pull = row.querySelector(pullSel);
        const track = row.querySelector(tugSel).getBoundingClientRect();
        const box = pull.getBoundingClientRect();
        return {
          label: row.querySelector('.lb').textContent,
          hasPull: !!pull,
          bg: getComputedStyle(pull).backgroundColor,
          towardAway: box.left + box.width / 2 < track.left + track.width / 2,
        };
      };
      const labels = [...document.querySelectorAll('.tsp4 .tsr4 .lb, .tsp .tsr .lb')].map((el) => el.textContent);
      return { labels, fg: read('fg'), tpm: read('tpm') };
    }, { tugSel: teamStatSel.tug, pullSel: teamStatSel.pull });
    expect(m.labels).toEqual([
      'FG%', '3PT', 'PTS IN PAINT', 'FAST BREAK', 'REBOUNDS', 'TURNOVERS', 'TEAM FOULS',
    ]);
    expect(m.fg.hasPull).toBe(true);
    expect(m.fg.towardAway).toBe(false);
    expect(m.fg.bg).toBe(HOME_COLOR);
    expect(m.tpm.hasPull).toBe(true);
    expect(m.tpm.towardAway).toBe(false);
    expect(m.tpm.bg).toBe(HOME_COLOR);
  });
});
