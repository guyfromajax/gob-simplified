const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const fx = require('./helpers/tablesLeagueFixtures');

/**
 * Tables and League polish (S1–S16). TL_SHOTS=before writes before-*.png and skips the
 * guards: run it on develop. TL_SHOTS=after writes after-*.png and asserts. With TL_SHOTS
 * unset the guards run and no file is written.
 */
test.describe.configure({ timeout: 240000 });

const MODE = process.env.TL_SHOTS || '';
const BEFORE = MODE === 'before';
const OUT = path.join(__dirname, '../../reports/tables-league');
const SIZES = [[1280, 720], [1920, 1080]];
const FCC = '/franchise-command-center.html?franchise_id=' + fx.FID + '&team_id=' + fx.TID;
const PAIRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];

async function settle(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForFunction(() => {
    return Array.from(document.querySelectorAll('html.gob-shell .main img')).every(function (img) { return img.complete; });
  }, null, { timeout: 10000 }).catch(function () {});
}

async function open(page, tab, opts) {
  const options = opts || {};
  await stubAuth(page);
  await fx.installApi(page, { week: options.week || 13 });
  await page.goto(FCC + '&tab=' + tab + (options.query || ''));
  await settle(page);
  await page.waitForSelector('#' + tab + '.tab-content.active');
  if (options.ready) await page.waitForSelector(options.ready, { timeout: 20000 });
  await settle(page);
}

async function shot(page, name, width, opts) {
  if (!MODE) return;
  fs.mkdirSync(OUT, { recursive: true });
  const options = opts || {};
  if (!options.keepScroll) {
    await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      if (main) main.scrollTop = 0;
    });
  }
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + box.width - 6, box.y + box.height - 6);
  await page.waitForTimeout(250);
  await page.screenshot({
    path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name + '-' + width + '.png'),
    animations: 'disabled',
    fullPage: false,
  });
}

/** The whole view, however tall, as one image: the viewport grows to fit `.main`. */
async function tallShot(page, name, width, height) {
  if (!MODE) return;
  const need = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    return main ? main.scrollHeight - main.clientHeight : 0;
  });
  if (need > 0) await page.setViewportSize({ width: width, height: Math.min(6000, height + need + 4) });
  await shot(page, name, width);
  await page.setViewportSize({ width: width, height: height });
}

async function noMainOverflow(page, label) {
  const over = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    return main.scrollWidth - main.clientWidth;
  });
  expect(over, label + ': .main does not scroll sideways').toBeLessThanOrEqual(1);
}

/**
 * The attribute rhythm of one roster table, measured between the ink (the digits), not
 * the cell boxes: adjacent cells always touch.
 */
async function pairRhythm(page, scope) {
  return page.evaluate((root) => {
    const table = document.querySelector(root + ' table');
    const rows = Array.from(table.querySelectorAll('tbody tr')).filter((tr) => tr.querySelector('.attr-tile'));
    const row = rows[0];
    const ink = (cell) => (cell.querySelector('.attr-tile s') || cell.querySelector('.attr-tile') || cell).getBoundingClientRect();
    const starts = Array.from(row.querySelectorAll('td.gstart'));
    const ends = Array.from(row.querySelectorAll('td.gend'));
    const within = [];
    const between = [];
    starts.forEach((start, i) => {
      within.push(ink(ends[i]).left - ink(start).right);
      if (starts[i + 1]) between.push(ink(starts[i + 1]).left - ink(ends[i]).right);
    });
    const wt = row.querySelector('td.wt');
    const range = document.createRange();
    if (wt) range.selectNodeContents(wt);
    const heads = Array.from(table.querySelectorAll('thead tr:last-child th.gstart, thead tr:last-child th.gend'))
      .map((th) => th.textContent.trim());
    return {
      heads: heads,
      within: within.map(Math.round),
      between: between.map(Math.round),
      lead: wt ? Math.round(ink(starts[0]).left - range.getBoundingClientRect().right) : null,
      heights: rows.map((tr) => Math.round(tr.getBoundingClientRect().height * 100) / 100),
      zebra: rows.slice(0, 4).map((tr) => getComputedStyle(tr.querySelector('td.rt') || tr.cells[1]).backgroundColor),
      shaded: row.querySelectorAll('td.gshade').length,
    };
  }, scope);
}

function expectPairs(rhythm, where) {
  expect(rhythm.heads, where + ': six pairs in order').toEqual(PAIRS);
  const within = Math.max.apply(null, rhythm.within);
  const between = Math.min.apply(null, rhythm.between);
  // A small gap inside a pair, a clearly larger one between pairs.
  expect(within, where + ': inside a pair').toBeLessThanOrEqual(26);
  expect(between, where + ': between pairs').toBeGreaterThanOrEqual(within * 2);
  // Every pair is the same, and every gutter is the same.
  expect(Math.max.apply(null, rhythm.within) - Math.min.apply(null, rhythm.within), where).toBeLessThanOrEqual(2);
  expect(Math.max.apply(null, rhythm.between) - Math.min.apply(null, rhythm.between), where).toBeLessThanOrEqual(2);
  // WT to SC is the widest gutter on the row.
  expect(rhythm.lead, where + ': WT to SC').toBeGreaterThan(Math.max.apply(null, rhythm.between));
}

/** Left padding of a family's first column against a column inside the family. */
async function familyGutters(page, scope) {
  return page.evaluate((root) => {
    const row = document.querySelector(root + ' tbody tr');
    const cells = Array.from(row.cells);
    const pad = (cell, side) => parseFloat(getComputedStyle(cell)['padding' + side]);
    const start = cells.find((c) => c.classList.contains('fs') && !c.classList.contains('fe') && !c.classList.contains('team'));
    const inside = cells.find((c) => !c.classList.contains('fs') && !c.classList.contains('fe') && !c.classList.contains('team') && !c.classList.contains('pin'));
    return {
      families: cells.filter((c) => c.classList.contains('fs')).length,
      outer: pad(start, 'Left'),
      inner: inside ? pad(inside, 'Left') : null,
    };
  }, scope);
}

/** Gaps between the text of named columns in the first body row. */
async function columnGaps(page, scope, labels) {
  return page.evaluate(({ root, names }) => {
    const table = document.querySelector(root + ' table');
    const heads = Array.from(table.querySelectorAll('thead tr:last-child th')).map((th) => th.textContent.trim());
    const row = table.querySelector('tbody tr');
    const box = (name) => {
      const cell = row.cells[heads.indexOf(name)];
      const range = document.createRange();
      range.selectNodeContents(cell);
      return range.getBoundingClientRect();
    };
    const out = {};
    for (let i = 0; i + 1 < names.length; i += 1) {
      out[names[i] + '>' + names[i + 1]] = Math.round(box(names[i + 1]).left - box(names[i]).right);
    }
    return out;
  }, { root: scope, names: labels });
}

for (const size of SIZES) {
  const W = size[0];
  const H = size[1];

  test.describe('at ' + W, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: W, height: H });
    });

    test('S1 roster: six attribute pairs, rows unchanged', async ({ page }) => {
      await open(page, 'roster-view', { ready: '#roster-view a.gob-player' });
      await shot(page, 's01-roster', W);
      if (BEFORE) return;
      const rhythm = await pairRhythm(page, '#roster-view');
      expectPairs(rhythm, 'roster');
      // Zebra rows and the shaded pairs are both still there.
      expect(new Set(rhythm.zebra).size, 'row zebra').toBe(2);
      expect(rhythm.shaded, 'three shaded pairs').toBe(6);
      // No row grew or shrank: 44px at 1280 (the 1920 density is taller, and uniform).
      expect(new Set(rhythm.heights).size, 'one row height').toBe(1);
      if (W === 1280) expect(rhythm.heights[0]).toBe(44);
      await noMainOverflow(page, 'roster');
    });

    test('S1 news story roster: the same six pairs', async ({ page }) => {
      await open(page, 'news-view', { query: '&story=w12-ps_all_stars', ready: '#news-view .gob-news-body table' });
      await shot(page, 's01-news-story-roster', W);
      if (BEFORE) return;
      expectPairs(await pairRhythm(page, '#news-view .gob-news-body'), 'news story roster');
    });

    test('S6 team page: roster above schedule, all twelve attributes, Attributes / Stats', async ({ page }) => {
      await open(page, 'team-view', { query: '&view_team_id=' + fx.OPP.team_id + '&origin=league', ready: '#team-view a.gob-player' });
      await tallShot(page, 's06-team-page', W, H);
      if (BEFORE) return;
      expectPairs(await pairRhythm(page, '#team-view .gob-team-roster'), 'team page roster');
      // Nothing is cut off: every attribute column is inside the card.
      const fit = await page.evaluate(() => {
        const card = document.querySelector('#team-view .gob-team-roster').getBoundingClientRect();
        const last = Array.from(document.querySelectorAll('#team-view .gob-team-roster thead tr:last-child th')).pop().getBoundingClientRect();
        const sched = document.querySelector('#team-view .gob-team-sched').getBoundingClientRect();
        return { inside: last.right <= card.right + 1, below: sched.top >= card.bottom, sameWidth: Math.abs(sched.width - card.width) <= 1 };
      });
      expect(fit).toEqual({ inside: true, below: true, sameWidth: true });
      await noMainOverflow(page, 'team page');

      const toggle = page.locator('#team-view .gob-team-mode button');
      await expect(toggle).toHaveText(['Attributes', 'Stats']);
      await expect(toggle.nth(0)).toHaveClass(/on/);
      await toggle.nth(1).click();
      await expect(toggle.nth(1)).toHaveClass(/on/);
      await page.waitForSelector('#team-view .gob-team-roster th[data-sort="fg_pct"]');
      await expect(page.locator('#team-view .gob-team-roster tbody tr')).toHaveCount(12);
      // Stats opens on points, highest first, and re-sorts from a header.
      const points = () => page.locator('#team-view .gob-team-roster td[data-k="PTS"]').allTextContents();
      const first = (await points()).map(Number);
      expect(first).toEqual(first.slice().sort((a, b) => b - a));
      await page.locator('#team-view .gob-team-roster th[data-sort="REB"]').click();
      const rebounds = (await page.locator('#team-view .gob-team-roster td[data-k="REB"]').allTextContents()).map(Number);
      expect(rebounds).toEqual(rebounds.slice().sort((a, b) => b - a));
      await shot(page, 's06-team-page-stats', W);
      await noMainOverflow(page, 'team page stats');
      await toggle.nth(0).click();
      await expect(page.locator('#team-view .gob-team-roster td.gstart').first()).toBeVisible();
      // The schedule keeps every game: twelve results and thirteen ahead.
      await expect(page.locator('#team-view .gob-team-sched .gob-sch')).toHaveCount(25);
    });

    test('S2 player stats: spaced by stat family', async ({ page }) => {
      await open(page, 'player-stats-view', { ready: '#player-stats-view a.gob-player' });
      await shot(page, 's02-player-stats', W);
      if (BEFORE) return;
      const gutters = await familyGutters(page, '#player-stats-view');
      expect(gutters.families).toBe(8);
      expect(gutters.outer).toBeGreaterThan(gutters.inner);
      const gaps = await columnGaps(page, '#player-stats-view', ['FGM', 'FGA', 'FG%', '3PTM', '3PTA', '3PT%', 'FTM', 'OREB', 'DREB', 'REB', 'AST']);
      // Shooting splits together, rebounds together; the family breaks are wider.
      expect(gaps['FG%>3PTM']).toBeGreaterThan(gaps['FGA>FG%']);
      expect(gaps['3PT%>FTM']).toBeGreaterThan(gaps['3PTA>3PT%']);
      expect(gaps['REB>AST']).toBeGreaterThan(gaps['DREB>REB']);
      const heights = await page.locator('#player-stats-view tbody tr').evaluateAll((rows) => rows.map((tr) => Math.round(tr.getBoundingClientRect().height * 100) / 100));
      expect(new Set(heights).size).toBe(1);
      if (W === 1280) expect(heights[0]).toBe(44);
      await noMainOverflow(page, 'player stats');
    });

    test('S2 team stats: spaced by stat family and still fits', async ({ page }) => {
      await open(page, 'team-stats-view', { ready: '#team-stats-view a.gob-team' });
      await shot(page, 's02-team-stats', W);
      if (BEFORE) return;
      const gutters = await familyGutters(page, '#team-stats-view');
      expect(gutters.outer).toBeGreaterThan(gutters.inner);
      const gaps = await columnGaps(page, '#team-stats-view', ['PF', 'PA', 'FGM', 'FGA', 'FG%', '3PTM', 'DREB', 'OREB', 'TREB', 'AST']);
      expect(gaps['PA>FGM']).toBeGreaterThan(gaps['PF>PA']);
      expect(gaps['FG%>3PTM']).toBeGreaterThan(gaps['FGA>FG%']);
      expect(gaps['TREB>AST']).toBeGreaterThan(gaps['OREB>TREB']);
      // Still one header row that fits .main, so it pins under the page head.
      await expect(page.locator('#team-stats-view .gob-xs, #team-stats-view .gob-wide-wrap')).toHaveCount(0);
      const over = await page.evaluate(() => {
        const table = document.querySelector('#team-stats-view .gob-tbl');
        return table.scrollWidth - table.parentElement.clientWidth;
      });
      expect(over).toBeLessThanOrEqual(1);
      await noMainOverflow(page, 'team stats');
    });

    test('S3 S4 team attributes: the place beside the title, Jamie\'s column order', async ({ page }) => {
      await open(page, 'team-attributes-view', { ready: '#team-attributes-view .mcell' });
      await shot(page, 's03-s04-team-attributes', W);
      if (BEFORE) return;
      const cells = await page.locator('#team-attributes-view .mcell').evaluateAll((nodes) => nodes.map((node) => {
        const name = node.querySelector('.nm').getBoundingClientRect();
        const place = node.querySelector('.place').getBoundingClientRect();
        const box = node.getBoundingClientRect();
        return {
          name: node.querySelector('.nm').textContent.trim(),
          place: node.querySelector('.place').textContent.trim(),
          left: Math.round(box.left),
          top: Math.round(box.top),
          gap: Math.round(place.left - name.right),
          toEdge: Math.round(box.right - place.right),
        };
      }));
      // Read down each column.
      const lefts = Array.from(new Set(cells.map((c) => c.left))).sort((a, b) => a - b);
      const columns = lefts.map((left) => cells.filter((c) => c.left === left).sort((a, b) => a.top - b.top).map((c) => c.name));
      expect(columns).toEqual([
        ['Shooting', 'Rebounding', 'Chemistry'],
        ['Offense', 'Defense', 'Discipline'],
        ['Fast Break', 'Fast Break Defense', 'Fight'],
        ['P/T Offense', 'P/T Defense'],
      ]);
      const offense = cells.find((c) => c.name === 'Offense');
      expect(offense.place).toBe('(1st of 128)');
      // Beside the title, not pushed to the right edge.
      cells.forEach((c) => {
        expect(c.gap, c.name).toBeGreaterThanOrEqual(0);
        expect(c.gap, c.name).toBeLessThanOrEqual(12);
        expect(c.toEdge, c.name).toBeGreaterThan(40);
      });
    });

    test('S5 Practice Squads is a League sub-tab', async ({ page }) => {
      await open(page, 'practice-squad-view', { ready: '#practice-squad-view .gob-ps-grid' });
      await shot(page, 's05-practice-squads', W);
      if (BEFORE) return;
      const labels = async () => (await page.locator('#gob-subtabs .tabs > .tb .tb-l').allTextContents()).map((t) => t.trim()).filter(Boolean);
      expect(await labels()).toEqual(['Standings', 'Rankings', 'Leaders', 'Team Stats', 'Schedule', 'Tournament', 'Practice Squads']);
      await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveAttribute('data-tab', 'practice-squad-view');
      await expect(page.locator('[data-gob-section="league"]')).toHaveClass(/on|active|is-on/);
      // It shows every region's squads, tier by tier.
      await expect(page.locator('#practice-squad-view .gob-ps-grid .gob-tcard')).toHaveCount(5);
      await expect(page.locator('#practice-squad-view .gob-ps-grid .gob-tcard').first().locator('tbody tr')).toHaveCount(8);
      // Team no longer lists it; the roster still has its Varsity / Practice Squad segment.
      await page.locator('[data-gob-section="team"]').evaluate((el) => el.click());
      await page.waitForSelector('#roster-view.tab-content.active');
      expect(await labels()).toEqual(['Roster', 'Player Stats', 'Team Attributes', 'Schedule']);
      await expect(page.locator('#gob-subtabs .pg-tools[data-owner="roster-view"] button')).toHaveText([/Varsity/, /Practice Squad/]);
    });

    test('S8 scouting report: Pos first, HT and WT after YR, spider chart comparison', async ({ page }) => {
      await open(page, 'scouting-view', { ready: '#scouting-view .opp-n' });
      await page.waitForSelector('#scouting-view .agrid tbody tr');
      if (!BEFORE) await page.waitForSelector('#scouting-view .sc-radar[data-side="you"] .tm-radar-svg');
      await tallShot(page, 's08-scouting', W, H);
      if (BEFORE) return;
      const heads = await page.locator('#scouting-view .agrid thead tr').first().locator('th[rowspan]').allTextContents();
      expect(heads.map((t) => t.replace(/cur.*$/i, '').trim())).toEqual(['Pos', 'Player', 'RT', 'Yr', 'Ht', 'Wt']);
      const row = await page.locator('#scouting-view .agrid tbody tr').first().evaluate((tr) => {
        const pos = tr.querySelector('.pos').getBoundingClientRect();
        const av = tr.querySelector('.av').getBoundingClientRect();
        return { posLeftOfImage: pos.right <= av.left, cells: Array.from(tr.cells).slice(0, 6).map((td) => td.textContent.trim()) };
      });
      expect(row.posLeftOfImage).toBe(true);
      expect(row.cells[0]).toBe('PG');
      expect(row.cells[4]).toMatch(/^\d'\d{1,2}"$/);
      expect(row.cells[5]).toMatch(/^\d{3}$/);
      // Stats keeps Pos on the left too.
      await page.locator('#scouting-view [data-scouting-projected-toggle] button[data-mode="stats"]').click();
      await expect(page.locator('#scouting-view .agrid thead th').first()).toHaveText('Pos');
      await page.locator('#scouting-view [data-scouting-projected-toggle] button[data-mode="attributes"]').click();

      // Under the plays: your team on the left, the opponent on the right.
      const spider = await page.evaluate(() => {
        const section = document.querySelector('#scouting-view .sc-spider');
        const plays = document.querySelector('#scouting-view .cols3').getBoundingClientRect();
        const cards = Array.from(section.querySelectorAll('.sc-radar')).map((card) => ({
          side: card.getAttribute('data-side'),
          name: card.querySelector('.nm').textContent.trim(),
          left: Math.round(card.getBoundingClientRect().left),
          charts: card.querySelectorAll('.tm-radar-svg').length,
          shape: card.querySelector('.tm-radar-shape-fill') ? card.querySelector('.tm-radar-shape-fill').getAttribute('points') : '',
        }));
        return { title: section.querySelector('h2').textContent.trim(), below: section.getBoundingClientRect().top >= plays.bottom, cards: cards };
      });
      expect(spider.title).toBe('Spider Chart Comparison');
      expect(spider.below).toBe(true);
      expect(spider.cards.map((c) => c.side)).toEqual(['you', 'opp']);
      expect(spider.cards[0].name).toBe(fx.USER.name);
      expect(spider.cards[1].name).toBe(fx.OPP.name);
      expect(spider.cards[0].left).toBeLessThan(spider.cards[1].left);
      expect(spider.cards.map((c) => c.charts)).toEqual([1, 1]);
      // Two teams, two shapes.
      expect(spider.cards[0].shape).not.toBe(spider.cards[1].shape);
      await noMainOverflow(page, 'scouting');
    });

    test('S9 S10 standings: eight regions, sister conferences side by side', async ({ page }) => {
      await open(page, 'standings-view', { ready: '#standings-view a.gob-team' });
      await shot(page, 's09-s10-standings', W);
      if (BEFORE) return;
      const layout = await page.evaluate(() => Array.from(document.querySelectorAll('#standings-view .gob-region')).map((region) => {
        const cards = Array.from(region.querySelectorAll('.gob-conf'));
        return {
          region: region.getAttribute('data-region'),
          titles: cards.map((card) => card.querySelector('h2').firstChild.textContent.trim()),
          yours: cards.map((card) => card.classList.contains('is-yours')),
          tops: cards.map((card) => Math.round(card.getBoundingClientRect().top)),
          lefts: cards.map((card) => Math.round(card.getBoundingClientRect().left)),
          rows: cards.map((card) => card.querySelectorAll('tbody tr').length),
        };
      }));
      expect(layout.length).toBe(8);
      // The user's region first, then the rest A to H.
      const rest = fx.REGIONS.filter((letter) => letter !== fx.USER.region);
      expect(layout.map((r) => r.region)).toEqual([fx.USER.region].concat(rest));
      // The user's conference on the left of its pair.
      expect(layout[0].yours).toEqual([true, false]);
      expect(layout[0].titles[0]).toBe(fx.USER.region + fx.USER.conference + ' CONFERENCE');
      layout.forEach((r) => {
        expect(r.titles.length, r.region).toBe(2);
        expect(r.rows, r.region).toEqual([8, 8]);
        // Side by side: one row, two columns.
        expect(Math.abs(r.tops[0] - r.tops[1]), r.region).toBeLessThanOrEqual(1);
        expect(r.lefts[1], r.region).toBeGreaterThan(r.lefts[0]);
        expect(r.titles.map((t) => t.charAt(0)), r.region).toEqual([r.region, r.region]);
      });
      // DIFF and its pill: there at 1920, dropped at 1280 to keep the pair uncramped.
      const diff = page.locator('#standings-view .gob-conf').first().locator('th.c-diff');
      if (W >= 1680) await expect(diff).toBeVisible();
      else await expect(diff).toBeHidden();
      // (Team, W, L) then (PF, PA): PF and PA sit closer than the families do.
      const gaps = await columnGaps(page, '#standings-view .gob-conf', ['W', 'L', 'PCT', 'PF', 'PA', 'STRK']);
      expect(gaps['PF>PA']).toBeLessThan(gaps['PCT>PF']);
      expect(gaps['PF>PA']).toBeLessThan(gaps['PA>STRK'] + (W >= 1680 ? 200 : 0));
      await noMainOverflow(page, 'standings');
    });

    test('S10 rankings: (Team, W, L), (PF, PA), Last Week, Next', async ({ page }) => {
      await open(page, 'rankings-view', { ready: '#rankings-view a.gob-team' });
      await shot(page, 's10-rankings', W);
      if (BEFORE) return;
      const gaps = await columnGaps(page, '#rankings-view', ['W', 'L', 'PF', 'PA', 'Last Week']);
      // Less space between PF and PA; more between PA and Last Week.
      expect(gaps['PF>PA']).toBeLessThan(gaps['PA>Last Week']);
      expect(gaps['PF>PA']).toBeLessThan(gaps['L>PF']);
      expect(gaps['W>L']).toBeLessThan(gaps['L>PF']);
      await noMainOverflow(page, 'rankings');
    });

    test('S11 leaders: the full list has a way back to Leaders', async ({ page }) => {
      await open(page, 'leaders-view', { ready: '#leaders-view .gob-ldb' });
      await page.locator('#leaders-view .gob-ldb .full').first().click();
      await page.waitForSelector('#leaders-view .gob-full tbody tr');
      await shot(page, 's11-leaders-full-list', W);
      if (BEFORE) return;
      const back = page.locator('#leaders-view .gob-dt-bar .gob-board');
      await expect(back).toBeVisible();
      await expect(back).toHaveText('← Leaders');
      // Above the list, on the left, and big enough to hit.
      const place = await back.evaluate((el) => {
        const box = el.getBoundingClientRect();
        const card = document.querySelector('#leaders-view .gob-full').getBoundingClientRect();
        return { above: box.bottom <= card.top, left: Math.round(box.left - card.left), height: Math.round(box.height) };
      });
      expect(place.above).toBe(true);
      expect(place.left).toBeLessThanOrEqual(1);
      expect(place.height).toBeGreaterThanOrEqual(28);
      await back.click();
      await expect(page.locator('#leaders-view .gob-ldb')).toHaveCount(8);
      await expect(page.locator('#leaders-view .gob-full')).toHaveCount(0);
      expect(new URL(page.url()).searchParams.get('leader')).toBeNull();
    });

    test('S12 tournament: the tab draws the bracket as the server stores it at the draw', async ({ page }) => {
      await open(page, 'tournament-view', { week: 27 });
      await page.waitForTimeout(800);
      await shot(page, 's12-tournament', W);
      // Guarded in both modes: this is the wiring, and it must hold on develop too.
      await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveAttribute('data-tab', 'tournament-view');
      await expect(page.locator('#gob-subtabs .tb[data-tab="tournament-view"]')).not.toHaveClass(/is-locked/);
      await expect(page.locator('#tournament-view .gob-tour-empty')).toHaveCount(0);
      // Four unplayed quarter-finals: eight teams, the user's among them, no scores yet.
      const mine = fx.conferenceTeams(fx.USER.conference).map((team) => team.name).sort();
      const drawn = await page.locator('#tournament-view .fcc-tb-mu .fcc-tb-name-text').allTextContents();
      const names = mine.filter((name) => drawn.some((text) => text.indexOf(name) !== -1));
      expect(names).toEqual(mine);
      await expect(page.locator('#tournament-view .fcc-tb-team--user')).toHaveCount(1);
      await expect(page.locator('#tournament-view .fcc-tb-team--user')).toContainText(fx.USER.name);
      // The other phases answer too: not drawn yet, said plainly.
      await page.locator('#tournament-view [data-tour-phase="region"]').click();
      await expect(page.locator('#tournament-view .gob-tour-empty')).toHaveText('Draws after Week 30');
    });

    test('S13 schedule: an unplayed game has no "Scheduled" container', async ({ page }) => {
      await open(page, 'league-schedule-view', { ready: '#league-schedule-view .gob-game' });
      await shot(page, 's13-schedule-unplayed', W);
      if (BEFORE) return;
      await expect(page.locator('#league-schedule-view .gob-game')).toHaveCount(64);
      await expect(page.locator('#league-schedule-view')).not.toContainText('Scheduled');
      await expect(page.locator('#league-schedule-view .gob-gf')).toHaveCount(0);
      // A played week keeps its footer: Final and the box score.
      await page.locator('#gob-subtabs .gob-wk button[data-week-step="-1"]').click();
      await expect(page.locator('#gob-subtabs .gob-wk-label')).toHaveText('Week 12');
      await expect(page.locator('#league-schedule-view .gob-gf')).toHaveCount(64);
      await expect(page.locator('#league-schedule-view .gob-gf').first()).toContainText('Final');
      await expect(page.locator('#league-schedule-view .gob-gf .gob-box')).toHaveCount(64);
    });

    test('S14 schedule week 30: byes as cards, region by region', async ({ page }) => {
      await open(page, 'league-schedule-view', { week: 30, ready: '#league-schedule-view .gob-game' });
      await shot(page, 's14-schedule-week-30', W);
      if (BEFORE) return;
      const cards = await page.locator('#league-schedule-view .gob-game').evaluateAll((nodes) => nodes.map((node) => ({
        bye: node.classList.contains('gob-bye'),
        mine: node.classList.contains('me'),
        lines: Array.from(node.querySelectorAll('.gob-gs .nm')).map((el) => el.textContent.trim()),
        region: (node.querySelector('.gob-gf .ctx') || { textContent: '' }).textContent.trim(),
        style: [getComputedStyle(node).borderTopWidth, getComputedStyle(node).borderRadius, getComputedStyle(node).paddingLeft].join(' '),
        teamTop: node.querySelector('.gob-gs').getBoundingClientRect().top,
        secondTop: node.querySelectorAll('.gob-gs')[1].getBoundingClientRect().top,
      })));
      const week = fx.regionWeek();
      expect(cards.length).toBe(week.games.length + week.byes.length);
      // A, B, C ... H, whatever order the games arrived in.
      const letters = cards.map((c) => c.region.replace('Region ', ''));
      expect(letters).toEqual(letters.slice().sort());
      expect(Array.from(new Set(letters))).toEqual(fx.REGIONS);
      // Each region is two cards: its games, then its byes.
      fx.REGIONS.forEach((letter) => {
        const mine = cards.filter((c) => c.region === 'Region ' + letter);
        expect(mine.length, letter).toBe(2);
        expect(mine.map((c) => c.bye), letter).toEqual(mine.map((c) => c.bye).slice().sort());
      });
      const byes = cards.filter((c) => c.bye);
      expect(byes.length).toBe(week.byes.length);
      byes.forEach((c) => {
        // The team on top, "Bye" underneath.
        expect(c.lines.length).toBe(2);
        expect(c.lines[1]).toBe('Bye');
        expect(c.secondTop).toBeGreaterThan(c.teamTop);
      });
      expect(byes.map((c) => c.lines[0])).toEqual(week.byes.map((b) => b.team.name));
      // The same container as a game.
      expect(new Set(cards.map((c) => c.style)).size).toBe(1);
      // The user's bye is the user's card.
      expect(cards.filter((c) => c.mine).map((c) => c.lines[0])).toEqual([fx.USER.name]);
      expect(cards.find((c) => c.mine).bye).toBe(true);
    });

    test('S15 news: three columns, one section per week', async ({ page }) => {
      await open(page, 'news-view', { ready: '#news-view .gob-news-card' });
      await tallShot(page, 's15-news', W, H);
      if (BEFORE) return;
      const weeks = await page.locator('#news-view .gob-news-week').evaluateAll((nodes) => nodes.map((node) => ({
        week: node.getAttribute('data-week'),
        heading: node.querySelector('.gob-news-wk').firstChild.textContent.trim(),
        cards: node.querySelectorAll('.gob-news-card').length,
        hero: node.querySelectorAll('.gob-news-card.is-hero').length,
        columns: node.querySelector('.gob-news-grid') ? getComputedStyle(node.querySelector('.gob-news-grid')).gridTemplateColumns.split(' ').length : 0,
      })));
      expect(weeks.map((w) => w.heading)).toEqual(['Week 12', 'Week 11', 'Week 10', 'Week 9']);
      expect(weeks.map((w) => w.cards)).toEqual([7, 7, 7, 5]);
      // The newest story still leads, full width, in its own week.
      expect(weeks.map((w) => w.hero)).toEqual([1, 0, 0, 0]);
      weeks.forEach((w) => { expect(w.columns, 'Week ' + w.week).toBe(W >= 1680 ? 3 : 2); });
      // The heading carries the week, so the cards do not repeat it.
      await expect(page.locator('#news-view .gob-news-when')).toHaveCount(0);
      await noMainOverflow(page, 'news');
    });

    test('S16 recruiting results: your class, then every conference as two rows of four', async ({ page }) => {
      await stubAuth(page);
      await fx.installApi(page, { week: 36 });
      await page.goto('/recruiting.html?franchise_id=' + fx.FID + '&team_id=' + fx.TID);
      await page.waitForSelector('#hub-signings .gob-rec-results', { timeout: 20000 });
      await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
      await page.waitForSelector('html.gob-shell .rail', { timeout: 15000 });
      await settle(page);
      await shot(page, 's16-recruiting-results', W);
      if (BEFORE) return;
      const view = await page.evaluate(() => {
        const root = document.querySelector('#hub-signings .gob-rec-results');
        return {
          first: root.firstElementChild.className,
          conferences: Array.from(root.querySelectorAll('.gob-rec-conf')).map((card) => {
            const teams = Array.from(card.querySelectorAll('.gob-rec-team'));
            return {
              label: card.getAttribute('data-conference'),
              scores: teams.map((team) => Number(team.querySelector('.sc').textContent)),
              places: teams.map((team) => team.querySelector('.rk').textContent.trim()),
              tops: teams.map((team) => Math.round(team.getBoundingClientRect().top)),
              lefts: teams.map((team) => Math.round(team.getBoundingClientRect().left)),
              userAt: teams.findIndex((team) => team.classList.contains('is-user-team')),
              fullWidth: Math.round(card.getBoundingClientRect().width) === Math.round(root.getBoundingClientRect().width),
              sums: teams.map((team) => Array.from(team.querySelectorAll('tbody tr')).length),
            };
          }),
        };
      });
      expect(view.first).toContain('gob-rec-your-class');
      // The user's conference, its sister, then A1, A2, B3 ... in order.
      const data = fx.recruitingResults();
      const label = (c) => String.fromCharCode(65 + Math.floor((c - 1) / 2)) + c;
      expect(view.conferences.map((c) => c.label)).toEqual(data.conferences.order.map(label));
      expect(view.conferences.length).toBe(16);
      view.conferences.forEach((conf) => {
        // Every conference in one format: eight teams, two rows of four.
        expect(conf.fullWidth, conf.label).toBe(true);
        expect(conf.scores.length, conf.label).toBe(8);
        const rows = Array.from(new Set(conf.tops)).sort((a, b) => a - b);
        expect(rows.length, conf.label).toBe(2);
        expect(conf.tops.filter((top) => top === rows[0]).length, conf.label).toBe(4);
        // Left to right, then top to bottom ...
        expect(conf.lefts.slice(0, 4), conf.label).toEqual(conf.lefts.slice(0, 4).slice().sort((a, b) => a - b));
        expect(conf.lefts.slice(4), conf.label).toEqual(conf.lefts.slice(0, 4));
        // ... by class score, highest first.
        expect(conf.scores, conf.label).toEqual(conf.scores.slice().sort((a, b) => b - a));
        expect(conf.places, conf.label).toEqual(['1', '2', '3', '4', '5', '6', '7', '8']);
      });
      // The score is the signed recruits' RT, summed: the Signing Day class score.
      const mineScore = data.week_35_recruiting_results.signed_players
        .filter((e) => e.team_id === fx.TID).reduce((sum, e) => sum + e.rt, 0);
      const mine = view.conferences[0];
      expect(mine.userAt).toBeGreaterThanOrEqual(0);
      expect(mine.scores[mine.userAt]).toBe(mineScore);
      // A team that signed nobody still has its place.
      expect(view.conferences.some((c) => c.scores.indexOf(0) !== -1)).toBe(true);
      await expect(page.locator('#hub-signings .gob-rec-none').first()).toHaveText('No signings');
    });
  });
}

// Standings below the two reference widths: DIFF comes back once the pair is given up.
for (const narrow of [[1100, 720], [900, 720]]) {
  test('S9 standings at ' + narrow[0] + ': one conference per row, DIFF kept', async ({ page }) => {
    await page.setViewportSize({ width: narrow[0], height: narrow[1] });
    await open(page, 'standings-view', { ready: '#standings-view a.gob-team' });
    await shot(page, 's09-standings', narrow[0]);
    if (BEFORE) return;
    const first = await page.locator('#standings-view .gob-region').first().evaluate((region) => {
      const cards = Array.from(region.querySelectorAll('.gob-conf')).map((card) => card.getBoundingClientRect());
      return { stacked: cards[1].top >= cards[0].bottom, sameLeft: Math.abs(cards[0].left - cards[1].left) <= 1 };
    });
    expect(first).toEqual({ stacked: true, sameLeft: true });
    await expect(page.locator('#standings-view .gob-conf').first().locator('th.c-diff')).toBeVisible();
    await noMainOverflow(page, 'standings ' + narrow[0]);
  });
}
