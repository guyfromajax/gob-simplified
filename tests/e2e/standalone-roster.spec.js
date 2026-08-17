// @ts-check
/** Standalone roster page — one surface, two switches, grouped stats, per-game default. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');

const PAGE = read('team-roster-view.html');
const PAGE_CSS = PAGE.slice(PAGE.indexOf('<style>') + 7, PAGE.indexOf('</style>'));
const CSS = read('css/attr-tiles.css') + read('css/rt-buckets.css') + PAGE_CSS;
const BODY = PAGE.slice(PAGE.indexOf('<div class="resource-page-container'), PAGE.indexOf('<script src="/js/config'));
const JS = read('team-roster-view.js');

const ATTRS = ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];

const NO_RECORD = Symbol('no-record');
const DEFAULT_RECORD = { wins: 18, losses: 6, conference: 1, conference_place: 2, conference_size: 16 };

async function mount(page, opts = {}) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto('/?mode=franchise&franchise_id=f1&team_id=t1');
  await page.setContent(`<style>${CSS}</style><style>body{margin:0;background:#0b0d14}</style>${BODY}`);
  await page.addScriptTag({ content: read('js/shared/playerYear.js') });
  await page.addScriptTag({ content: read('js/shared/rtBucket.js') });
  await page.addScriptTag({ content: read('js/shared/attrTiles.js') });
  await page.addScriptTag({ content: read('js/shared/attributeTooltips.js') });
  await page.addScriptTag({ content: read('js/shared/scoutingReport.js') });
  await page.evaluate(() => {
    window.buildPlayerDetailUrl = (id) => '/player-detail.html?id=' + id;
    window.getTeamAssetPath = () => '/img.jpg';
    const mk = (i, n) => {
      const a = {}; ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT']
        .forEach((k, j) => a[k] = ((i * 7 + j * 13) % 95 + 5));
      return { _id: 'p' + i, name: n, jersey: i + 2, pos: 'PF', year: 'JR',
               height: `6'${i}"`, heightRaw: 72 + i, weight: 200 + i,
               attributes: a, highestRT: 80 - i * 5, potential_rt_ratcheted: 88 - i * 3 };
    };
    window.__roster = [mk(0, 'Alpha'), mk(1, 'Bravo'), mk(2, 'Charlie')];
    window.__ps = [mk(7, 'Practice One')];
    window.__stats = window.__roster.map((p, i) => ({
      _id: p._id,
      stats: { GP: 10, PTS: 100 + i * 10, FGM: 40, FGA: 90, 'FG%': 44.4,
               '3PTM': 10, '3PTA': 30, '3PT%': 33.3, FTM: 20, FTA: 25, 'FT%': 80,
               DREB: 50, OREB: 20, TREB: 70, AST: 30, STL: 12, BLK: 8,
               DEFA: 40, 'DEF%': 41.2, SCRA: 22, 'SCR%': 55.5, F: 18, TO: 24 },
    }));
  });
  // Load the page module as a real top-level classic script — the module's data lives in
  // top-level `let` bindings, which an eval() inside page.evaluate() would scope away.
  // Only the boot listener is stripped; every renderer under test is the real one.
  await page.addScriptTag({
    content: JS.replace(/document\.addEventListener\('DOMContentLoaded'[\s\S]*?\}\);\n/, ''),
  });
  await page.evaluate((rec) => {
    rosterData = window.__roster;
    trainingSquadData = window.__ps;
    statsData = window.__stats;
    trRenderLockup({ team_name: 'Kettle Falls', team_record: rec });
    trBindToolbar();
    renderTrTable();
  }, opts.record === NO_RECORD ? null : DEFAULT_RECORD);
}

test.describe('one surface', () => {
  test('four stacked tables collapse to one', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      tables: document.querySelectorAll('table').length,
      titles: document.querySelectorAll('.section-title').length,
      gone: ['stats-table','ts-roster-table','ps-stats-table'].filter((id) => document.getElementById(id)),
    }));
    expect(m.tables).toBe(1);
    expect(m.titles).toBe(0);
    expect(m.gone).toEqual([]);
  });

  test('scope switch swaps the body', async ({ page }) => {
    await mount(page);
    expect(await page.locator('#roster-body tr').count()).toBe(3);
    await page.click('[data-tr-scope="practice"]');
    expect(await page.locator('#roster-body tr').count()).toBe(1);
    expect(await page.evaluate(() => document.querySelector('#roster-body .ident-name').textContent.trim()))
      .toBe('Practice One');
  });

  test('view switch swaps attributes for grouped season stats', async ({ page }) => {
    await mount(page);
    expect(await page.locator('#roster-body .attr-tile').count()).toBe(36);   // 3 rows x 12
    await page.click('[data-tr-view="stats"]');
    const groups = await page.evaluate(() =>
      [...document.querySelectorAll('#tr-head .tr-grp')].map((g) => g.textContent.trim()));
    expect(groups).toEqual(['SCORING','FIELD GOALS','3-POINT','FREE THROWS','REBOUNDING','PLAYMAKING','DEFENSE','SCREENS','MISTAKES']);
    expect(await page.locator('#roster-body .attr-tile').count()).toBe(0);
  });

  test('header cell count matches body cell count in both views', async ({ page }) => {
    await mount(page);
    const attrs = await page.evaluate(() => ({
      heads: document.querySelectorAll('#tr-head tr:last-child th').length,
      cells: document.querySelectorAll('#roster-body tr:first-child td').length,
    }));
    expect(attrs.heads).toBe(attrs.cells);
    await page.click('[data-tr-view="stats"]');
    const stats = await page.evaluate(() => ({
      heads: document.querySelectorAll('#tr-head tr.tr-colrow th').length + 1, // +1 rowspan Player
      cells: document.querySelectorAll('#roster-body tr:first-child td').length,
    }));
    expect(stats.heads).toBe(stats.cells);
  });
});

test.describe('per game / totals', () => {
  test('toggle is stats-only and defaults to Per game', async ({ page }) => {
    await mount(page);
    expect(await page.evaluate(() =>
      getComputedStyle(document.getElementById('tr-per-track')).display)).toBe('none');
    await page.click('[data-tr-view="stats"]');
    const m = await page.evaluate(() => ({
      visible: getComputedStyle(document.getElementById('tr-per-track')).display !== 'none',
      pressed: document.querySelector('[data-tr-per="game"]').getAttribute('aria-pressed'),
      pts: document.querySelector('#roster-body tr:first-child td:nth-child(2)').textContent.trim(),
    }));
    expect(m.visible).toBe(true);
    expect(m.pressed).toBe('true');
    expect(m.pts).toBe('12.0');            // 120 PTS / 10 GP, highest scorer sorts first
  });

  test('Totals shows season totals; percentages are unaffected', async ({ page }) => {
    await mount(page);
    await page.click('[data-tr-view="stats"]');
    const perGame = await page.evaluate(() => [...document.querySelectorAll('#roster-body tr:first-child td')].map((t) => t.textContent.trim()));
    await page.click('[data-tr-per="total"]');
    const totals = await page.evaluate(() => [...document.querySelectorAll('#roster-body tr:first-child td')].map((t) => t.textContent.trim()));
    expect(perGame[1]).toBe('12.0');
    expect(totals[1]).toBe('120');
    // FG% is the 4th stat column (index 4 incl. the identity cell) and must not change.
    expect(perGame[4]).toBe(totals[4]);
    expect(perGame[4]).toBe('44.4');
  });
});

test.describe('identity lockup', () => {
  test('shows record and conference standing from the payload', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => ({
      name: document.getElementById('tr-team-name').textContent.trim(),
      record: document.getElementById('tr-record').textContent.trim(),
      standing: document.getElementById('tr-standing').textContent.trim(),
      banner: document.getElementById('team-banner-card').getBoundingClientRect(),
    }));
    expect(m.name).toBe('Kettle Falls');
    expect(m.record).toBe('18-6');
    expect(m.standing).toBe('2 of 16');
    expect(Math.round(m.banner.width)).toBe(224);
    expect(Math.round(m.banner.height)).toBe(79);
  });

  test('hides the record block when the payload has none', async ({ page }) => {
    await mount(page, { record: NO_RECORD });
    expect(await page.evaluate(() =>
      getComputedStyle(document.getElementById('tr-record-block')).display)).toBe('none');
  });

  test('no scholarship count anywhere — scholarships are sunset', async ({ page }) => {
    await mount(page);
    const txt = await page.evaluate(() => document.body.textContent.toLowerCase());
    expect(txt).not.toContain('scholarship');
  });
});

test.describe('sticky + banding', () => {
  test('identity column is sticky and solid; rows are zebra-banded', async ({ page }) => {
    await mount(page);
    const m = await page.evaluate(() => {
      const cell = document.querySelector('#roster-body td.c-ident');
      const even = document.querySelector('#roster-body tr:nth-child(2)');
      return {
        pos: getComputedStyle(cell).position,
        bg: getComputedStyle(cell).backgroundColor,
        zebra: getComputedStyle(even).backgroundColor,
      };
    });
    expect(m.pos).toBe('sticky');
    expect(m.bg).not.toContain('rgba');
    expect(m.zebra).not.toBe('rgba(0, 0, 0, 0)');
  });

  test('both stats header rows stick and are opaque', async ({ page }) => {
    await mount(page);
    await page.click('[data-tr-view="stats"]');
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#tr-head th')].slice(0, 4).map((t) => ({
        pos: getComputedStyle(t).position,
        bg: getComputedStyle(t).backgroundColor,
      })));
    for (const t of m) {
      expect(t.pos).toBe('sticky');
      expect(t.bg).not.toContain('rgba');
    }
  });
});

test('all 12 attributes sort in the attributes view', async ({ page }) => {
  await mount(page);
  expect(await page.locator('#tr-head [data-attr-sort]').count()).toBe(12);
});

test.describe('projected starting five', () => {
  test('keeps headshots and is unaffected by the Per game / Totals toggle', async ({ page }) => {
    await mount(page);
    await page.evaluate(() => {
      projectedStartingFive = window.__roster.slice(0, 3).map((p, i) => ({
        player_id: p._id, name: p.name, position: ['PG','SF','C'][i],
        image_url: '/images/players/' + p._id + '.png', ppg: 12.5 - i, rpg: 5, apg: 3,
      }));
      renderStartingFive();
    });
    const before = await page.evaluate(() => ({
      visible: getComputedStyle(document.getElementById('starting-five-section')).display !== 'none',
      imgs: document.querySelectorAll('#roster-starting-five img').length,
      html: document.getElementById('roster-starting-five').innerHTML,
    }));
    expect(before.visible).toBe(true);
    expect(before.imgs).toBeGreaterThan(0);

    await page.click('[data-tr-view="stats"]');
    await page.click('[data-tr-per="total"]');
    const after = await page.evaluate(() => document.getElementById('roster-starting-five').innerHTML);
    expect(after).toBe(before.html);          // per game always, regardless of the table toggle
  });
});
