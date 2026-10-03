// @ts-check
/**
 * Training Report tables: the Player Report (Attributes, Training Changes) and the
 * Projected Starting 5 use the roster's six attribute pairs and the app's row lines,
 * not a boxed grid (Jamie, 2026-10-02).
 *
 *   TRTAB_SHOTS=before   shots only, on the old tree
 *   TRTAB_SHOTS=after    shots alongside the assertions
 * Shots: reports/training-report-tables/<phase>-<week>-<table>-<width>.png
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { busy, camp, installReportApi, reportUrl } = require('./helpers/trainingReportFixture');

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/training-report-tables');
const PHASE = process.env.TRTAB_SHOTS || '';
const SIZES = [[1280, 720], [1920, 1080], [2000, 1125]];
const WEEKS = { season: busy, camp };

async function openReport(page, report) {
  await stubAuth(page);
  await installReportApi(page, report);
  await page.goto(reportUrl(report));
  await expect(page.locator('#training-report-view')).not.toHaveClass(/is-loading/, { timeout: 30000 });
  await expect(page.locator('#players-tbody tr').first()).toBeVisible();
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function showView(page, view) {
  await page.locator('.players-section .toggle-btn[data-view="' + view + '"]').click();
  await expect(page.locator('.players-section .toggle-btn[data-view="' + view + '"]')).toHaveClass(/active/);
}

test.describe('shots', () => {
  test.skip(!PHASE, 'TRTAB_SHOTS only');
  for (const week of Object.keys(WEEKS)) {
    for (const [width, height] of SIZES) {
      test(week + ' at ' + width, async ({ page }) => {
        fs.mkdirSync(OUT, { recursive: true });
        // Tall, so each section is shot whole and in place (no scroll under the sticky head).
        await page.setViewportSize({ width, height: 2400 });
        await openReport(page, WEEKS[week]());
        const shot = async (name, locator) => {
          await page.mouse.move(0, 0);
          await page.waitForTimeout(250);
          await locator.screenshot({ path: path.join(OUT, PHASE + '-' + week + '-' + name + '-' + width + '.png'), animations: 'disabled' });
        };
        await shot('changes', page.locator('.players-section'));
        await showView(page, 'attributes');
        await shot('attributes', page.locator('.players-section'));
        await shot('projected', page.locator('.projected-lineup-section'));
        if (width === 1280) {
          await showView(page, 'changes');
          await page.setViewportSize({ width, height });
          await page.waitForTimeout(250);
          await page.screenshot({ path: path.join(OUT, PHASE + '-' + week + '-page-1280.png'), animations: 'disabled' });
        }
      });
    }
  }
});

// Playbook Summary shots for the play CMD scale (PCS_SHOTS=before|after):
// reports/play-cmd-scale/<phase>-<week>-playbook-summary-<width>.png
test.describe('playbook summary shots', () => {
  const phase = process.env.PCS_SHOTS || '';
  test.skip(!phase, 'PCS_SHOTS only');
  for (const week of Object.keys(WEEKS)) {
    for (const width of [1280, 1920]) {
      test(week + ' at ' + width, async ({ page }) => {
        const dir = path.join(__dirname, '../../reports/play-cmd-scale');
        fs.mkdirSync(dir, { recursive: true });
        await page.setViewportSize({ width, height: 2400 });
        await openReport(page, WEEKS[week]());
        await expect(page.locator('#playbook-summary-container .pbs-row').first()).toBeVisible();
        await page.mouse.move(0, 0);
        await page.waitForTimeout(250);
        await page.locator('.playbook-summary-section').screenshot({
          path: path.join(dir, phase + '-' + week + '-playbook-summary-' + width + '.png'), animations: 'disabled',
        });
      });
    }
  }
});

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

const PAIRS = [['SC', 'SH'], ['ID', 'OD'], ['PS', 'BH'], ['RB', 'ST'], ['AG', 'ND'], ['IQ', 'FT']];
const ALL_TWELVE = PAIRS.flat();

/** A table as the eye reads it: header cells with their classes, and where each value box sits. */
function readTable(page, wrapSelector) {
  return page.evaluate((selector) => {
    const wrap = document.querySelector(selector);
    const table = wrap.querySelector('table');
    const heads = [...table.querySelectorAll('thead th')].filter((th) => !th.classList.contains('tr-fill'));
    const rows = [...table.querySelectorAll('tbody tr')];
    const first = rows[0];
    const columns = heads.map((th, i) => {
      const cell = first.children[i];
      const box = (cell.querySelector('.ak') || cell).getBoundingClientRect();
      const headBox = (th.querySelector('.ak') || th).getBoundingClientRect();
      return {
        label: th.textContent.trim(),
        cls: th.className,
        cellCls: cell.className,
        left: box.left, right: box.right,
        headCentre: (headBox.left + headBox.right) / 2, boxCentre: (box.left + box.right) / 2,
        shade: getComputedStyle(cell).backgroundColor,
      };
    });
    // The longest name: the name column is exactly as wide as it.
    const nameRight = Math.max(...rows.map((tr) => tr.querySelector('.player-name-text').getBoundingClientRect().right));
    return {
      wrapClass: wrap.className, tableClass: table.className,
      columns,
      nameRight,
      rowHeights: [...new Set(rows.map((tr) => Math.round(tr.getBoundingClientRect().height)))],
      rows: rows.length,
      tableWidth: table.getBoundingClientRect().width, wrapWidth: wrap.getBoundingClientRect().width,
    };
  }, wrapSelector);
}

/** Gaps between neighbouring value boxes: inside each pair, and between groups. */
function gaps(columns) {
  const inside = [];
  const between = [];
  for (let i = 1; i < columns.length; i += 1) {
    const prev = columns[i - 1];
    const next = columns[i];
    if (!/g(start|end|solo)/.test(prev.cls) || !/g(start|end|solo)/.test(next.cls)) continue;
    const gap = next.left - prev.right;
    if (/gstart/.test(prev.cls) && /gend/.test(next.cls)) inside.push(gap);
    else between.push(gap);
  }
  return { inside, between };
}

test.describe('player report', () => {
  test.skip(PHASE === 'before', 'after tree only');
  test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

  test('Attributes: six pairs in the roster\'s order, on the shared table classes', async ({ page }) => {
    for (const [width, height] of SIZES) {
      await page.setViewportSize({ width, height });
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await openReport(page, busy());
      await showView(page, 'attributes');
      const table = await readTable(page, '.players-section .tr-ptable');
      expect(table.wrapClass).toMatch(/\bgob-pairs\b/);
      expect(table.wrapClass).toMatch(/\bgob-roster\b/);
      expect(table.tableClass).toBe('gob-tbl');
      expect(table.columns.map((c) => c.label), 'at ' + width).toEqual(['Name'].concat(ALL_TWELVE, ['NG', 'EM', 'RT']));
      const attrs = table.columns.slice(1, 13);
      attrs.forEach((column, i) => {
        const shaded = Math.floor(i / 2) % 2 === 1;      // ID OD, RB ST, IQ FT: the roster's shade
        expect(column.cls, column.label).toBe((i % 2 === 0 ? 'gstart' : 'gend') + (shaded ? ' gshade' : ''));
        expect(column.cellCls, column.label).toContain(i % 2 === 0 ? 'gstart' : 'gend');
        // The label sits over its value.
        expect(Math.abs(column.headCentre - column.boxCentre), column.label).toBeLessThanOrEqual(1);
      });
      // Tight inside a pair, a gutter between pairs, and the same everywhere.
      const { inside, between } = gaps(attrs);
      expect(inside).toHaveLength(6);
      expect(between).toHaveLength(5);
      inside.forEach((gap) => { expect(gap).toBeGreaterThanOrEqual(0); expect(gap).toBeLessThanOrEqual(6); });
      between.forEach((gap) => expect(gap).toBeGreaterThanOrEqual(16));
      expect(Math.max(...inside) - Math.min(...inside)).toBeLessThanOrEqual(1);
      expect(Math.max(...between) - Math.min(...between)).toBeLessThanOrEqual(1);
      expect(Math.min(...between)).toBeGreaterThan(3 * Math.max(...inside));
      // The pair shade is the roster's token, on every other pair.
      expect(attrs[2].shade).not.toBe(attrs[0].shade);
      expect(attrs[2].shade).toBe(attrs[3].shade);
      expect(attrs[4].shade).toBe(attrs[0].shade);
      // The values start right beside the names, not across the page.
      expect(attrs[0].left - table.nameRight).toBeGreaterThan(0);
      expect(attrs[0].left - table.nameRight).toBeLessThanOrEqual(width === 1280 ? 80 : 130);
      // Rows still run the full width.
      expect(Math.round(table.tableWidth)).toBe(Math.round(table.wrapWidth));
    }
  });

  test('no boxed cells: row zebra, no borders, and a moved cell is marked by its arrows alone', async ({ page }) => {
    await openReport(page, busy());
    const look = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#players-tbody tr')];
      const cells = rows.flatMap((tr) => [...tr.children]);
      const box = (cell) => {
        const cs = getComputedStyle(cell);
        return [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth, cs.boxShadow, cs.outlineStyle].join(' ');
      };
      const moved = cells.filter((cell) => /[▲▼]/.test(cell.textContent));
      const unmoved = cells.filter((cell) => cell.textContent.trim() === '–');
      const plain = (tr) => getComputedStyle(tr.querySelector('td.gstart:not(.gshade)')).backgroundColor;
      return {
        boxes: [...new Set(cells.map(box))],
        moved: moved.length, unmoved: unmoved.length,
        movedBoxes: [...new Set(moved.map(box))], unmovedBoxes: [...new Set(unmoved.map(box))],
        isDelta: document.querySelectorAll('#players-tbody .is-delta').length,
        odd: plain(rows[0]), even: plain(rows[1]),
        legacyClass: document.getElementById('players-table').classList.contains('players-table'),
      };
    });
    expect(look.moved).toBeGreaterThan(20);
    expect(look.unmoved).toBeGreaterThan(0);
    expect(look.boxes).toEqual(['0px 0px 0px 0px none none']);
    expect(look.movedBoxes).toEqual(look.unmovedBoxes);
    expect(look.isDelta).toBe(0);
    expect(look.even).not.toBe(look.odd);          // zebra
    expect(look.legacyClass).toBe(false);          // the old boxed-grid rules no longer apply
  });

  test('Training Changes: only what was trained, and a pair stays together when both are present', async ({ page }) => {
    // In season: SC SH PS AG ND were trained. SC SH and AG ND are whole pairs; PS is alone.
    await openReport(page, busy());
    let table = await readTable(page, '.players-section .tr-ptable');
    expect(table.columns.map((c) => c.label)).toEqual(['Name', 'SC', 'SH', 'PS', 'AG', 'ND', 'RT']);
    expect(table.columns.slice(1, 6).map((c) => c.cls)).toEqual(['gstart', 'gend', 'gsolo gshade', 'gstart', 'gend']);
    let g = gaps(table.columns.slice(1, 6));
    expect(g.inside).toHaveLength(2);
    g.inside.forEach((gap) => expect(gap).toBeLessThanOrEqual(6));
    g.between.forEach((gap) => expect(gap).toBeGreaterThanOrEqual(16));
    expect(Math.min(...g.between)).toBeGreaterThan(3 * Math.max(...g.inside));

    // Camp: all twelve moved, so all six pairs, exactly as on Attributes.
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await openReport(page, camp());
    table = await readTable(page, '.players-section .tr-ptable');
    expect(table.columns.map((c) => c.label)).toEqual(['Name'].concat(ALL_TWELVE, ['RT']));
    g = gaps(table.columns.slice(1, 13));
    expect(g.inside).toHaveLength(6);
    expect(g.between).toHaveLength(5);

    // One of each pair only: every column stands alone, none glued to a stranger.
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    const report = busy();
    Object.keys(report.player_changes).forEach((name) => { report.player_changes[name] = { SH: 1, ID: -1, ST: 0.5 }; });
    await openReport(page, report);
    table = await readTable(page, '.players-section .tr-ptable');
    expect(table.columns.map((c) => c.label)).toEqual(['Name', 'SH', 'ID', 'ST', 'RT']);
    expect(table.columns.slice(1, 4).map((c) => c.cls)).toEqual(['gsolo', 'gsolo gshade', 'gsolo']);
    g = gaps(table.columns.slice(1, 4));
    expect(g.inside).toEqual([]);
    g.between.forEach((gap) => expect(gap).toBeGreaterThanOrEqual(16));
  });

  test('name, position chip and RT stay; rows are the roster\'s 44px', async ({ page }) => {
    const report = busy();
    await openReport(page, report);
    const table = await readTable(page, '.players-section .tr-ptable');
    expect(table.rows).toBe(report.players.length);
    expect(table.rowHeights).toEqual([44]);
    const first = page.locator('#players-tbody tr').first();
    await expect(first.locator('.position-badge')).toBeVisible();
    await expect(first.locator('.player-name-text')).toBeVisible();
    await expect(first.locator('td.tr-rt')).toHaveText(/^[A-F][+-]?$/);
    // Same row in Attributes.
    await showView(page, 'attributes');
    expect((await readTable(page, '.players-section .tr-ptable')).rowHeights).toEqual([44]);
  });

  test('CH is hidden: no CH column in any table, whatever the data carries', async ({ page }) => {
    const report = busy();
    report.players.forEach((player) => { player.attributes.CH = 77; });
    Object.keys(report.player_changes).forEach((name) => { report.player_changes[name].CH = 2; });
    report.projected_starting_five.forEach((row) => { row.attributes.CH = 7; });
    await openReport(page, report);
    const heads = () => page.evaluate(() => [...document.querySelectorAll('#players-thead th, #training-projected-lineup thead th')].map((th) => th.textContent.trim()));
    expect(await heads()).not.toContain('CH');
    await showView(page, 'attributes');
    expect(await heads()).not.toContain('CH');
    const text = await page.evaluate(() => (
      document.querySelector('.players-section').textContent + ' ' + document.querySelector('.projected-lineup-section').textContent
    ));
    expect(text).not.toMatch(/\bCH\b/);
  });

  for (const [width, height] of [[1280, 720], [1920, 1080]]) {
    for (const week of Object.keys(WEEKS)) {
      test(week + ': the Player Report still starts above the fold at ' + width + 'x' + height, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await openReport(page, WEEKS[week]());
        const m = await page.evaluate(() => ({
          heading: document.querySelector('.players-section h2').getBoundingClientRect().bottom,
          head: document.querySelector('#players-thead').getBoundingClientRect().bottom,
          firstRow: document.querySelector('#players-tbody tr').getBoundingClientRect().bottom,
          fold: window.innerHeight,
        }));
        expect(m.heading).toBeLessThan(m.fold);
        expect(m.head).toBeLessThan(m.fold);
        expect(m.firstRow).toBeLessThan(m.fold);
      });
    }
  }
});

test.describe('projected starting 5', () => {
  test.skip(PHASE === 'before', 'after tree only');
  test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

  test('Attributes: identity columns, then the same six pairs, then RT', async ({ page }) => {
    await openReport(page, busy());
    const table = await readTable(page, '#training-projected-lineup .tr-ptable');
    expect(table.wrapClass).toMatch(/\bgob-pairs\b/);
    expect(table.tableClass).toBe('gob-tbl');
    expect(table.columns.map((c) => c.label)).toEqual(['Player', 'Year', 'Ht', 'Wt'].concat(ALL_TWELVE, ['RT']));
    expect(table.rows).toBe(5);
    const attrs = table.columns.slice(4, 16);
    attrs.forEach((column, i) => {
      expect(column.cls, column.label).toBe((i % 2 === 0 ? 'gstart' : 'gend') + (Math.floor(i / 2) % 2 === 1 ? ' gshade' : ''));
    });
    const { inside, between } = gaps(attrs);
    expect(inside).toHaveLength(6);
    inside.forEach((gap) => expect(gap).toBeLessThanOrEqual(6));
    between.forEach((gap) => expect(gap).toBeGreaterThanOrEqual(16));
    // The same pair rhythm as the Player Report above it.
    await showView(page, 'attributes');
    const players = await readTable(page, '.players-section .tr-ptable');
    const p = gaps(players.columns.slice(1, 13));
    expect(Math.abs(p.inside[0] - inside[0])).toBeLessThanOrEqual(1);
    expect(Math.abs(p.between[0] - between[0])).toBeLessThanOrEqual(1);
    expect(table.rowHeights).toEqual([44]);
    const first = page.locator('#training-projected-lineup tbody tr').first();
    await expect(first.locator('.position-badge')).toHaveText('PG');
  });

  test('Stats view is unchanged', async ({ page }) => {
    await openReport(page, busy());
    await page.locator('.projected-lineup-toggle .toggle-btn[data-projected-view="stats"]').click();
    const stats = page.locator('#training-projected-lineup table.training-projected-table');
    await expect(stats).toBeVisible();
    const heads = await stats.locator('thead th').allTextContents();
    expect(heads.slice(0, 5)).toEqual(['Pos', 'Player', 'PTS', 'FGM', 'FGA']);
    await expect(page.locator('#training-projected-lineup .gob-pairs')).toHaveCount(0);
    // And back.
    await page.locator('.projected-lineup-toggle .toggle-btn[data-projected-view="attributes"]').click();
    await expect(page.locator('#training-projected-lineup .gob-pairs table.gob-tbl')).toBeVisible();
  });
});

// The play CMD scale (Jamie approved the cut-offs, 2026-10-02): a play's or a defense's
// movement in the Playbook Summary is marked on its own scale, not the player-attribute one.
test.describe('play CMD marks (Playbook Summary)', () => {
  test.skip(PHASE === 'before', 'after tree only');
  test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

  function withCmdChanges(overrides) {
    const report = busy();
    report.plays_effectiveness_changes = Object.assign({
      '4-1 Motion': 3, '5-0 Motion': 5, '3-2 Motion': 19, 'PF Post Motion': 20,
      'Base Post Play': 4, 'Quick Midrange Jumper': 0,
    }, (overrides && overrides.plays) || {});
    report.defenses_effectiveness_changes = Object.assign(
      { man: 50, '2-3-zone': 29, '3-2-zone': 30, '1-3-1-zone': 49 }, (overrides && overrides.defenses) || {},
    );
    return report;
  }

  /** Every Playbook Summary row: its mark and the mark's painted colour. */
  function marks(page) {
    return page.evaluate(() => {
      const out = {};
      document.querySelectorAll('#playbook-summary-container .pbs-row').forEach((row) => {
        const delta = row.querySelector('.pbs-delta');
        out[row.querySelector('.pbs-name').textContent.trim()] = {
          text: delta.textContent, color: getComputedStyle(delta).color, label: delta.getAttribute('aria-label'),
          defense: !!row.closest('.pbs-panel--defense'),
        };
      });
      return out;
    });
  }

  test('the play scale ships: one constant, the approved cut-offs', async () => {
    const source = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/training-report.js'), 'utf8');
    expect(source).toContain("const PLAY_CMD_SCALE = 'play';");
    expect(source).toMatch(/offense: \{ up: \[5, 20\], down: \[5, 10\] \}/);
    expect(source).toMatch(/defense: \{ up: \[30, 50\], down: \[10, 20\] \}/);
  });

  test('offense: one arrow under 5, two from 5, three from 20; an untrained play is a dash', async ({ page }) => {
    await openReport(page, withCmdChanges());
    const m = await marks(page);
    expect(m['4-1 Motion'].text).toBe('▲');          // +3
    expect(m['Base Post Play'].text).toBe('▲');      // +4
    expect(m['5-0 Motion'].text).toBe('▲▲');         // +5
    expect(m['3-2 Motion'].text).toBe('▲▲');         // +19
    expect(m['PF Post Motion'].text).toBe('▲▲▲');    // +20
    expect(m['Quick Midrange Jumper'].text).toBe('–');
    expect(m['Iso'].text).toBe('–');                 // not trained at all
    // The existing training movement marks: faint green, green, blue.
    expect(m['4-1 Motion'].color).toMatch(/0\.45\)$|\/ 0\.45\)$/);
    expect(m['5-0 Motion'].color).toBe('rgb(52, 236, 39)');
    expect(m['PF Post Motion'].color).toBe('rgb(74, 144, 217)');
  });

  test('defense: one arrow under 30, two from 30, three from 50', async ({ page }) => {
    await openReport(page, withCmdChanges());
    const m = await marks(page);
    const defense = Object.values(m).filter((row) => row.defense).map((row) => row.label + ' ' + row.text);
    expect(defense).toContain('Training change +29 ▲');
    expect(defense).toContain('Training change +30 ▲▲');
    expect(defense).toContain('Training change +49 ▲▲');
    expect(defense).toContain('Training change +50 ▲▲▲');
    // A gain that is three arrows for a play is one for a defense: the scales are separate.
    expect(m['PF Post Motion'].text).toBe('▲▲▲');   // +20
  });

  test('drops, should a report ever carry one: offense 5 / 10, defense 10 / 20', async ({ page }) => {
    await openReport(page, withCmdChanges({
      plays: { '4-1 Motion': -4, '5-0 Motion': -5, '3-2 Motion': -9, 'PF Post Motion': -10 },
      defenses: { man: -20, '2-3-zone': -9, '3-2-zone': -10, '1-3-1-zone': -19 },
    }));
    const m = await marks(page);
    expect(m['4-1 Motion'].text).toBe('▼');
    expect(m['5-0 Motion'].text).toBe('▼▼');
    expect(m['3-2 Motion'].text).toBe('▼▼');
    expect(m['PF Post Motion'].text).toBe('▼▼▼');
    const defense = Object.values(m).filter((row) => row.defense).map((row) => row.label + ' ' + row.text);
    expect(defense).toContain('Training change -9 ▼');
    expect(defense).toContain('Training change -10 ▼▼');
    expect(defense).toContain('Training change -19 ▼▼');
    expect(defense).toContain('Training change -20 ▼▼▼');
  });

  test('a real-sized week no longer reads as all three arrows; camp uses the camp tones', async ({ page }) => {
    // In season: set plays a few points, motions a few dozen, zones 26-52, Man 85.
    await openReport(page, busy());
    let m = await marks(page);
    const counts = (rows) => rows.reduce((acc, row) => { acc[row.text] = (acc[row.text] || 0) + 1; return acc; }, {});
    const offense = counts(Object.values(m).filter((row) => !row.defense && row.text !== '–'));
    expect(offense).toEqual({ '▲': 4, '▲▲': 4, '▲▲▲': 3 });
    const defense = counts(Object.values(m).filter((row) => row.defense && row.text !== '–'));
    expect(defense).toEqual({ '▲': 1, '▲▲': 1, '▲▲▲': 2 });

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await openReport(page, camp());
    m = await marks(page);
    expect(m['Misdirection Three'].text).toBe('▲');          // +4
    expect(m['Misdirection Three'].color).toBe('rgba(255, 255, 255, 0.87)');   // camp: one up is neutral
    expect(m['Back Door Cut'].text).toBe('▲▲');             // +12
    expect(m['4-1 Motion'].text).toBe('▲▲▲');               // +46
  });

  test('player marks are untouched: the attribute scale still marks the Player Report', async ({ page }) => {
    await openReport(page, withCmdChanges());
    // Roger Henrich gained 2.5 on SC this week: two arrows on the attribute scale.
    const sc = await page.locator('#players-tbody tr').first().locator('td.gstart').first().textContent();
    expect(sc).toBe('▲▲');
  });
});
