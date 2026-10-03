// @ts-check
/**
 * Training Report, top of the page: the Notes cards (Standouts, Trends, Readiness) and the
 * Team Report grid (Jamie, 2026-10-02).
 *
 *   TRT_SHOTS=before   shots only, on the old tree
 *   TRT_SHOTS=after    shots alongside the assertions
 * Shots: reports/training-report-top/<phase>-<week>-<width>.png
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { SCENARIOS, busy, quiet, camp, installReportApi, reportUrl } = require('./helpers/trainingReportFixture');

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/training-report-top');
const PHASE = process.env.TRT_SHOTS || '';
const SIZES = [[1280, 720], [1920, 1080], [2000, 1125]];

async function openReport(page, report, opts) {
  await stubAuth(page);
  await installReportApi(page, report, opts);
  await page.goto(reportUrl(report));
  await expect(page.locator('#training-report-view')).not.toHaveClass(/is-loading/, { timeout: 30000 });
  await expect(page.locator('#players-tbody tr').first()).toBeVisible();
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

test.describe('shots', () => {
  test.skip(!PHASE, 'TRT_SHOTS only');
  for (const name of Object.keys(SCENARIOS)) {
    for (const [width, height] of SIZES) {
      test(name + ' at ' + width, async ({ page }) => {
        fs.mkdirSync(OUT, { recursive: true });
        await page.setViewportSize({ width, height });
        await openReport(page, SCENARIOS[name]());
        await page.mouse.move(0, 0);
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(OUT, PHASE + '-' + name + '-' + width + '.png'), animations: 'disabled' });
      });
    }
  }
});

// The two calls the brief left open, shot both ways (1280, the three cards). Jamie chose
// the five-step meter, and "Lagging" in camp.
test.describe('option shots', () => {
  test.skip(PHASE !== 'after', 'TRT_SHOTS=after only');

  test('readiness meter: five steps (shipped, Jamie\'s choice) and three steps', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openReport(page, camp());
    const cards = page.locator('#training-report-view .tr-cards');
    await cards.screenshot({ path: path.join(OUT, 'option-readiness-5-step-1280.png'), animations: 'disabled' });
    // Three steps, the first build: "Very" lit the same step as the plain word.
    await page.evaluate(() => {
      const three = { 'very weak': 1, weak: 1, neutral: 2, strong: 3, 'very strong': 3 };
      document.querySelectorAll('#training-report-view .tr-readiness').forEach((pair) => {
        const meter = pair.querySelector('.tr-meter');
        const level = three[String(pair.dataset.word || '').toLowerCase()] || 0;
        meter.innerHTML = '';
        for (let i = 1; i <= 3; i += 1) {
          const step = document.createElement('i');
          if (i <= level) step.className = 'on';
          meter.appendChild(step);
        }
      });
    });
    await cards.screenshot({ path: path.join(OUT, 'option-readiness-3-step-1280.png'), animations: 'disabled' });
  });

  test('camp: the second trend line reads "Lagging" (shipped) or "Falling"', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openReport(page, camp());
    const cards = page.locator('#training-report-view .tr-cards');
    await cards.screenshot({ path: path.join(OUT, 'option-camp-lagging-1280.png'), animations: 'disabled' });
    await page.evaluate(() => {
      document.querySelector('#training-report-view [data-trend="falling"] .tr-label').textContent = 'Falling';
    });
    await cards.screenshot({ path: path.join(OUT, 'option-camp-falling-1280.png'), animations: 'disabled' });
  });
});

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

const WHITE = 'rgb(255, 255, 255)';
const QUIET = 'rgba(255, 255, 255, 0.38)';
const LABEL = 'rgba(255, 255, 255, 0.6)';

/** Chrome reports a color-mix() as `color(srgb r g b / a)`; read it back as rgba(). */
function rgba(color) {
  const m = /^color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)(?: \/ ([\d.]+))?\)$/.exec(color);
  if (!m) return color;
  const ch = (v) => Math.round(Number(v) * 255);
  const alpha = m[4] == null ? 1 : Math.round(Number(m[4]) * 100) / 100;
  return alpha === 1
    ? 'rgb(' + ch(m[1]) + ', ' + ch(m[2]) + ', ' + ch(m[3]) + ')'
    : 'rgba(' + ch(m[1]) + ', ' + ch(m[2]) + ', ' + ch(m[3]) + ', ' + alpha + ')';
}

/** What the three cards say, read off the page. */
function readCards(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : null);
    const view = document.getElementById('training-report-view');
    const cards = [...view.querySelectorAll('.tr-cards > .tr-card')];
    const standouts = [...view.querySelectorAll('.tr-card--standouts .tr-standout')].map((row) => ({
      key: row.dataset.standout,
      label: text(row.querySelector('.tr-label')),
      name: text(row.querySelector('.training-notes-hero-name')),
      meta: text(row.querySelector('.training-notes-hero-meta')),
      muted: row.classList.contains('is-muted'),
      photo: !!row.querySelector('img.training-notes-hero-portrait-img'),
      fallback: text(row.querySelector('.training-notes-hero-portrait-fallback')),
      nameColor: getComputedStyle(row.querySelector('.training-notes-hero-name')).color,
    }));
    const trends = [...view.querySelectorAll('.tr-card--trends .tr-trend')].map((pair) => ({
      key: pair.dataset.trend,
      label: text(pair.querySelector('.tr-label')),
      tags: [...pair.querySelectorAll('.tr-tag')].map((tag) => ({
        text: text(tag).replace(/^[▲▼]\s*/, ''),
        arrow: tag.querySelector('i').textContent,
        tone: tag.querySelector('i').className,
        color: getComputedStyle(tag.querySelector('i')).color,
      })),
      none: text(pair.querySelector('.tr-none')),
    }));
    const schemes = [...view.querySelectorAll('.tr-card--trends .tr-scheme')].map((pair) => ({
      label: text(pair.querySelector('.tr-label')), value: text(pair.querySelector('.tr-value')),
    }));
    const readiness = [...view.querySelectorAll('.tr-card--readiness .tr-readiness')].map((pair) => {
      const steps = [...pair.querySelectorAll('.tr-meter i')];
      return {
        key: pair.dataset.ready,
        label: text(pair.querySelector('.tr-label')),
        word: text(pair.querySelector('.tr-ready-word')),
        steps: steps.length,
        lit: steps.filter((el) => el.classList.contains('on')).length,
        litColors: [...new Set(steps.filter((el) => el.classList.contains('on')).map((el) => getComputedStyle(el).backgroundColor))],
        offColors: [...new Set(steps.filter((el) => !el.classList.contains('on')).map((el) => getComputedStyle(el).backgroundColor))],
      };
    });
    return {
      titles: cards.map((card) => text(card.querySelector('.card-h h3'))),
      keys: cards.map((card) => card.dataset.card),
      standouts, trends, schemes, readiness,
      energy: text(view.querySelector('.tr-energy .tr-value')),
      energyLabel: text(view.querySelector('.tr-energy .tr-label')),
    };
  });
}

/** The Team Report as the eye reads it: columns left to right, each read down. */
function readTeamGrid(page) {
  return page.evaluate(() => {
    const cells = [...document.querySelectorAll('#team-attributes-grid .team-attr-item')].map((item) => {
      const name = item.querySelector('.attr-name');
      const mark = item.querySelector('.attr-change');
      const box = item.getBoundingClientRect();
      return {
        name: name.textContent.trim(),
        mark: mark.textContent,
        moved: item.classList.contains('is-delta'),
        x: Math.round(box.left), y: Math.round(box.top),
        nameColor: getComputedStyle(name).color,
        nameWeight: Number(getComputedStyle(name).fontWeight),
        markColor: getComputedStyle(mark).color,
      };
    });
    const xs = [...new Set(cells.map((cell) => cell.x))].sort((a, b) => a - b);
    const columns = xs.map((x) => cells.filter((cell) => cell.x === x).sort((a, b) => a.y - b.y).map((cell) => cell.name));
    return { cells, columns, text: document.getElementById('team-attributes-grid').textContent };
  });
}

test.describe('cards', () => {
  test.skip(PHASE === 'before', 'after tree only');
  test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

  test('three cards in order, one kind of information each; the staff-only brief line is gone', async ({ page }) => {
    await openReport(page, busy());
    const cards = await readCards(page);
    expect(cards.titles).toEqual(['Standouts', 'Trends', 'Readiness']);
    expect(cards.keys).toEqual(['standouts', 'trends', 'readiness']);
    // The shared card, not a new one.
    const look = await page.locator('.tr-card--standouts').evaluate((el) => {
      const cs = getComputedStyle(el);
      return { card: el.classList.contains('card'), border: cs.borderTopWidth + ' ' + cs.borderTopStyle, radius: cs.borderTopLeftRadius };
    });
    expect(look.card).toBe(true);
    expect(look.border).toBe('1px solid');
    expect(parseFloat(look.radius)).toBeGreaterThan(0);
    await expect(page.locator('#training-notes-brief')).toHaveCount(0);
    await expect(page.locator('.training-notes-section')).not.toContainText(/training brief|coaching staff only/i);
    // One layer of small grey caps: every label is the same quiet caps, every value white.
    const labels = await page.evaluate(() => [...document.querySelectorAll('#training-report-view .tr-cards .tr-label')].map((el) => {
      const cs = getComputedStyle(el);
      return cs.color + ' ' + cs.textTransform + ' ' + cs.fontSize;
    }));
    expect(new Set(labels).size).toBe(1);
    expect(labels[0]).toBe(LABEL + ' uppercase 10px');
  });

  test('Standouts: three people with headshot, name, position and year', async ({ page }) => {
    const report = busy();
    await openReport(page, report);
    const { standouts } = await readCards(page);
    // Order (Jamie, 2026-10-03): the week's best, the locker room, then the regression.
    expect(standouts.map((row) => row.label)).toEqual([
      'Practice Player Of The Week', 'Most Positive Locker Room Influence', 'Biggest Regression',
    ]);
    expect(standouts.map((row) => row.name)).toEqual([
      report.players[11].name, report.players[2].name, report.players[8].name,
    ]);
    standouts.forEach((row, i) => {
      const player = [report.players[11], report.players[2], report.players[8]][i];
      expect(row.photo).toBe(true);
      expect(row.muted).toBe(false);
      expect(row.meta).toBe(player.position + ' · ' + player.year);
      expect(row.nameColor).toBe(WHITE);
    });
  });

  test('Standouts: "No Significant Updates" keeps its quiet empty state', async ({ page }) => {
    const report = quiet();
    await openReport(page, report);
    const { standouts } = await readCards(page);
    expect(standouts[0].name).toBe(report.players[3].name);
    [standouts[1], standouts[2]].forEach((row) => {
      expect(row.name).toBe('No Significant Updates');
      expect(row.muted).toBe(true);
      expect(row.photo).toBe(false);
      expect(row.fallback).toBe('NS');
      expect(row.meta).toBeNull();
      expect(row.nameColor).toBe(QUIET);
    });
  });

  test('Trends: Rising and Falling are tagged with the same faint arrows as the marks below', async ({ page }) => {
    await openReport(page, busy());
    const { trends, schemes } = await readCards(page);
    expect(trends.map((row) => row.label)).toEqual(['Rising', 'Falling']);
    expect(trends[0].tags.map((tag) => tag.text)).toEqual(['Scoring (SC)', 'Passing (PS)']);
    expect(trends[1].tags.map((tag) => tag.text)).toEqual(['Agility (AG)']);
    trends[0].tags.forEach((tag) => { expect(tag.arrow).toBe('▲'); expect(tag.tone).toBe('tr-tone-up-faint'); });
    trends[1].tags.forEach((tag) => { expect(tag.arrow).toBe('▼'); expect(tag.tone).toBe('tr-tone-down-faint'); });
    // The very colours of a one-up and a one-down mark in the Team Report under them.
    const grid = await readTeamGrid(page);
    const oneUp = grid.cells.find((cell) => cell.name === 'Fast Break');
    const oneDown = grid.cells.find((cell) => cell.name === 'Fast Break Defense');
    expect(oneUp.mark).toBe('▲');
    expect(oneDown.mark).toBe('▼');
    expect(rgba(trends[0].tags[0].color)).toBe(rgba(oneUp.markColor));
    expect(rgba(trends[1].tags[0].color)).toBe(rgba(oneDown.markColor));
    expect(rgba(oneUp.markColor)).toBe('rgba(52, 236, 39, 0.45)');
    expect(rgba(oneDown.markColor)).toBe('rgba(255, 109, 109, 0.6)');
    expect(schemes).toEqual([
      { label: 'Strongest Defensive Set', value: '2-3 Zone' },
      { label: 'Strongest Offensive Plays', value: '4-1 Motion, Horns Flare, 5-0 Flex' },
    ]);
  });

  test('Trends: a week with nothing rising or falling says so quietly, with no arrows', async ({ page }) => {
    await openReport(page, quiet());
    const { trends, schemes } = await readCards(page);
    trends.forEach((row) => {
      expect(row.tags).toEqual([]);
      expect(row.none).toBe('No Significant Updates');
    });
    await expect(page.locator('.tr-card--trends .tr-none').first()).toHaveCSS('color', QUIET);
    expect(schemes.map((row) => row.value)).toEqual(['Man-to-Man', '4-1 Motion']);
  });

  test('Trends in camp: nothing falls at camp, so the second line reads "Lagging"', async ({ page }) => {
    await openReport(page, camp());
    const { trends, standouts } = await readCards(page);
    expect(trends.map((row) => row.label)).toEqual(['Rising', 'Lagging']);
    expect(trends[0].tags.map((tag) => tag.text)).toEqual(['Scoring (SC)', 'Strength (ST)', 'Shooting (SH)']);
    expect(trends[1].tags.map((tag) => tag.text)).toEqual(['Free Throws (FT)']);
    expect(standouts.map((row) => row.label)).toEqual([
      'Training Camp MVP', 'Most Positive Locker Room Influence', 'Biggest Concern',
    ]);
  });

  test('Readiness: six-bar meters with the word in parentheses beside them, neutral colours', async ({ page }) => {
    await openReport(page, busy());
    let { readiness } = await readCards(page);
    expect(readiness.map((row) => row.label)).toEqual(['Fast Break', 'Press/Traps']);
    expect(readiness.map((row) => [row.word, row.lit, row.steps])).toEqual([['(Strong)', 4, 6], ['(Weak)', 2, 6]]);
    expect(readiness[1].litColors).toEqual(['rgba(255, 255, 255, 0.87)']);
    expect(readiness[1].offColors).toEqual(['rgba(255, 255, 255, 0.12)']);
    // The meter and its word share a line, the word right after the meter.
    const beside = await page.locator('[data-ready="fast-break"] .tr-ready').evaluate((el) => {
      const meter = el.querySelector('.tr-meter').getBoundingClientRect();
      const word = el.querySelector('.tr-ready-word').getBoundingClientRect();
      return { gap: word.left - meter.right, sameLine: Math.abs((word.top + word.bottom) / 2 - (meter.top + meter.bottom) / 2) };
    });
    expect(beside.gap).toBeGreaterThan(0);
    expect(beside.gap).toBeLessThanOrEqual(16);
    expect(beside.sameLine).toBeLessThanOrEqual(3);
    await expect(page.locator('[data-ready="fast-break"] .tr-meter')).toHaveAttribute('aria-label', 'Strong');

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await openReport(page, quiet());
    ({ readiness } = await readCards(page));
    expect(readiness.map((row) => [row.word, row.lit])).toEqual([['(Neutral)', 3], ['(Neutral)', 3]]);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await openReport(page, camp());
    ({ readiness } = await readCards(page));
    expect(readiness.map((row) => [row.word, row.lit, row.steps])).toEqual([['(Very Strong)', 5, 6], ['(Neutral)', 3, 6]]);
  });

  // Every band of the six-bar scale is tested in v3-training.spec.js.

  test('Player Energy: no row when there is nothing to report; a row, label above text, when there is', async ({ page }) => {
    await openReport(page, busy());
    await expect(page.locator('#training-report-view .tr-energy')).toHaveCount(0);
    await expect(page.locator('.training-notes-section')).not.toContainText(/player energy/i);
    // The row used to be labelled "Misc": that word is gone from the page.
    await expect(page.locator('.training-notes-section')).not.toContainText(/misc/i);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    const report = camp();
    await openReport(page, report);
    const cards = await readCards(page);
    expect(cards.energyLabel).toBe('Player Energy');
    expect(cards.energy).toBe(report.players[5].name + ' and ' + report.players[9].name + ' came out of camp with heavy legs.');
    await expect(page.locator('.training-notes-section')).not.toContainText(/misc/i);
    await expect(page.locator('#training-report-view .tr-energy')).toHaveCount(1);
  });

  test('CH is hidden: it never appears, whatever a stored note says', async ({ page }) => {
    const report = busy();
    report.training_notes = report.training_notes.map((note) => {
      if (note.title === 'Strong Cumulative Increase') return { title: note.title, body: 'CH, SC' };
      if (note.title === 'Concerning Regression') return { title: note.title, body: 'CH' };
      return note;
    });
    await openReport(page, report);
    const { trends } = await readCards(page);
    expect(trends[0].tags.map((tag) => tag.text)).toEqual(['Scoring (SC)']);
    // CH was the only thing falling: the line is empty, not "CH".
    expect(trends[1].tags).toEqual([]);
    expect(trends[1].none).toBe('No Significant Updates');
    const top = await page.evaluate(() => (
      document.querySelector('.training-notes-section').textContent + ' ' + document.querySelector('.team-section').textContent
    ));
    expect(top).not.toMatch(/\bCH\b/);
    expect(top).not.toMatch(/\(CH\)/);
  });
});

test.describe('label and value stay together', () => {
  test.skip(PHASE === 'before', 'after tree only');
  for (const [width, height] of SIZES) {
    for (const name of Object.keys(SCENARIOS)) {
      test(name + ' at ' + width + ': every label sits directly above or beside its value', async ({ page }) => {
        await page.setViewportSize({ width, height });
        await openReport(page, SCENARIOS[name]());
        const pairs = await page.evaluate(() => {
          const box = (el) => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; };
          const out = [];
          document.querySelectorAll('#training-report-view .training-notes-section .tr-pair').forEach((pair) => {
            const label = pair.querySelector('.tr-label');
            const value = pair.querySelector('.tr-value');
            const host = pair.closest('.tr-card') || pair;
            out.push({ what: label.textContent.trim(), label: box(label), value: box(value), card: box(host) });
          });
          document.querySelectorAll('#team-attributes-grid .team-attr-item').forEach((item) => {
            out.push({
              what: item.querySelector('.attr-name').textContent.trim(), team: true,
              label: box(item.querySelector('.attr-name')), value: box(item.querySelector('.attr-change')),
              card: box(document.getElementById('team-attributes-grid')),
            });
          });
          return out;
        });
        expect(pairs.length).toBeGreaterThanOrEqual(9 + 11);
        pairs.forEach((pair) => {
          const { label, value, card } = pair;
          const above = value.t >= label.b - 1;
          const cardWidth = card.r - card.l;
          if (above) {
            // Directly above: left edges line up and the value starts right under the label.
            expect(Math.abs(value.l - label.l), pair.what + ' left edges').toBeLessThanOrEqual(1);
            expect(value.t - label.b, pair.what + ' vertical gap').toBeLessThanOrEqual(8);
          } else {
            // Immediately beside: on the label's line, a short step to its right.
            expect(value.t, pair.what + ' same line').toBeLessThan(label.b);
            expect(value.b, pair.what + ' same line').toBeGreaterThan(label.t);
            expect(value.l - label.l, pair.what + ' beside').toBeGreaterThan(0);
            expect(value.l - label.l, pair.what + ' distance from label start').toBeLessThanOrEqual(pair.team ? 190 : 90);
          }
          // Never split across the card, and never outside it.
          expect(value.l - label.l, pair.what + ' vs card width').toBeLessThan(cardWidth / 2);
          [label, value].forEach((box) => {
            expect(box.l, pair.what).toBeGreaterThanOrEqual(card.l - 1);
            expect(box.r, pair.what).toBeLessThanOrEqual(card.r + 1);
          });
        });
      });
    }
  }
});

test.describe('team report', () => {
  test.skip(PHASE === 'before', 'after tree only');
  test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

  test('eleven attributes in the four columns of Team › Team Attributes, read down', async ({ page }) => {
    for (const [width, height] of SIZES) {
      await page.setViewportSize({ width, height });
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await openReport(page, busy());
      const grid = await readTeamGrid(page);
      expect(grid.columns, 'at ' + width).toEqual([
        ['Shooting', 'Rebounding', 'Chemistry'],
        ['Offense', 'Defense', 'Discipline'],
        ['Fast Break', 'Fast Break Defense', 'Fight'],
        ['P/T Offense', 'P/T Defense'],
      ]);
      expect(grid.cells).toHaveLength(11);
    }
    await expect(page.locator('#team-attributes-grid')).toHaveClass(/\bcard\b/);
  });

  test('a cell is the name and its mark; no change is a quiet dash, never the words', async ({ page }) => {
    await openReport(page, busy());
    const grid = await readTeamGrid(page);
    expect(grid.text).not.toMatch(/no change/i);
    const byName = Object.fromEntries(grid.cells.map((cell) => [cell.name, cell]));
    expect(Object.fromEntries(grid.cells.map((cell) => [cell.name, cell.mark]))).toEqual({
      Shooting: '▲▲', Rebounding: '–', Chemistry: '–',
      Offense: '▲▲▲', Defense: '▲▲', Discipline: '▼▼▼',
      'Fast Break': '▲', 'Fast Break Defense': '▼', Fight: '▼▼',
      'P/T Offense': '–', 'P/T Defense': '–',
    });
    // What moved stands out: full white and heavier; what did not is quiet.
    grid.cells.forEach((cell) => {
      if (cell.moved) {
        expect(cell.nameColor, cell.name).toBe(WHITE);
        expect(cell.nameWeight, cell.name).toBeGreaterThanOrEqual(600);
      } else {
        expect(cell.nameColor, cell.name).toBe(LABEL);
        expect(cell.nameWeight, cell.name).toBeLessThan(600);
        expect(cell.markColor, cell.name).toBe(QUIET);
      }
    });
    expect(rgba(byName.Offense.markColor)).toBe('rgb(74, 144, 217)');
    expect(rgba(byName.Discipline.markColor)).toBe('rgb(255, 109, 109)');
    await expect(page.locator('[data-attr="rebound_modifier"] .attr-change')).toHaveAttribute('aria-label', 'No change');
  });

  test('a week where almost nothing moved still reads as designed: one mark, ten dashes', async ({ page }) => {
    await openReport(page, quiet());
    const grid = await readTeamGrid(page);
    expect(grid.cells).toHaveLength(11);
    expect(grid.cells.filter((cell) => cell.moved).map((cell) => cell.name)).toEqual(['Fast Break']);
    expect(grid.cells.filter((cell) => cell.mark === '–')).toHaveLength(10);
    const cards = await readCards(page);
    expect(cards.standouts).toHaveLength(3);
    expect(cards.trends).toHaveLength(2);
    expect(cards.schemes).toHaveLength(2);
    expect(cards.readiness).toHaveLength(2);
  });
});

test.describe('height', () => {
  test.skip(PHASE === 'before', 'after tree only');
  for (const [width, height] of [[1280, 720], [1920, 1080]]) {
    for (const name of Object.keys(SCENARIOS)) {
      test(name + ': the Player Report starts above the fold at ' + width + 'x' + height, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await openReport(page, SCENARIOS[name]());
        const m = await page.evaluate(() => {
          const top = (sel) => document.querySelector(sel).getBoundingClientRect();
          return {
            heading: top('.players-section h2').bottom,
            head: top('#players-thead').bottom,
            firstRow: top('#players-tbody tr').bottom,
            notesTop: top('.training-notes-section').top,
            teamBottom: top('.team-section').bottom,
            fold: window.innerHeight,
          };
        });
        expect(m.heading, 'Player Report heading').toBeLessThan(m.fold);
        expect(m.head, 'Player Report column heads').toBeLessThan(m.fold);
        expect(m.firstRow, 'first player row').toBeLessThan(m.fold);
        // The old top section was 583px tall at 1280 (Notes beside Team Report).
        if (width === 1280) expect(m.teamBottom - m.notesTop).toBeLessThanOrEqual(name === 'camp' ? 420 : 380);   // camp has a Player Energy row
      });
    }
  }
});

test.describe('loading', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('nothing paints half-built: the skeleton stands in the shape of the new top, then the cards', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const report = busy();
    await stubAuth(page);
    await installReportApi(page, report, { delayMs: 1500 });
    await page.goto(reportUrl(report));
    const host = page.locator('#training-report-view');
    await expect(host).toHaveClass(/is-loading/);
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    const during = await page.evaluate(() => {
      const visible = (el) => {
        const cs = getComputedStyle(el);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0;
      };
      const skeleton = document.querySelector('#training-report-view .report-skeleton');
      return {
        loading: document.getElementById('training-report-view').classList.contains('is-loading'),
        headings: [...document.querySelectorAll('#training-report-view h2, #training-report-view h3')].filter(visible).length,
        cards: [...document.querySelectorAll('#training-report-view .tr-card, #team-attributes-grid')].filter(visible).length,
        skeleton: visible(skeleton),
        columns: getComputedStyle(skeleton).gridTemplateColumns.split(' ').length,
        blocks: [...skeleton.children].filter(visible).length,
      };
    });
    expect(during.loading).toBe(true);
    expect(during.headings).toBe(0);
    expect(during.cards).toBe(0);
    expect(during.skeleton).toBe(true);
    expect(during.columns).toBe(3);      // three cards across
    expect(during.blocks).toBe(4);       // and the Team Report under them
    await expect(host).not.toHaveClass(/is-loading/, { timeout: 15000 });
    await expect(page.locator('.tr-cards > .tr-card')).toHaveCount(3);
    await expect(page.locator('#training-report-view .report-skeleton')).toBeHidden();
  });
});
