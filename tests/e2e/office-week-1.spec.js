// @ts-check
/**
 * The Office in week 1 of a season: the season preview (feature/office-week-1, 2026-10-02).
 *
 * Week 1 of EVERY season, before the first game: Season Preview / Opening Week / Recruiting.
 * From week 2 the Office is the normal one, plus Top Recruits (all season, until Signing Day).
 *
 * OW1_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/office-week-1');
const TAG = process.env.OW1_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));

/** Season 1, week 1: the fixture's default preview. */
function seasonOne() {
  const data = clone(O.STATES.first_week);
  data.week = 1;
  data.season = 1;
  data.current_season = 1;
  // Before the first game: the preseason rank, and nobody has played.
  data.rank = 40;
  data.team_record = { wins: 0, losses: 0 };
  data.office_digest.conference_standings.rows.forEach((row) => { row.wins = 0; row.losses = 0; });
  return data;
}

/** A later season's week 1: last season's line, the class that signed, last season's meeting. */
function laterSeason() {
  const data = seasonOne();
  data.season = 3;
  data.current_season = 3;
  const preview = data.office_digest.season_preview;
  preview.season = 3;
  preview.outlook.last_season = { wins: 18, losses: 8, finish: 'lost in the Region semifinal' };
  preview.newcomers = {
    players: [
      { player_id: 'n-1', name: 'Rafe Dalton', pos: 'PG', rt: 62 },
      { player_id: 'n-2', name: 'Emeka Sorensen', pos: 'C', rt: 57 },
      { player_id: 'n-3', name: 'Coby Tran', pos: 'SF', rt: 49 },
      { player_id: 'n-4', name: 'Will Hask', pos: 'SG', rt: 44 },
    ],
    returning: 9,
    lost_seniors: 3,
    newcomers: 4,
  };
  preview.opener.last_meeting = { won: true, user_score: 71, opp_score: 64, week: 14 };
  preview.walk_ons = [{ player_id: 'w-9', name: 'Gus Penn', pos: 'SF', year: 'FR', rt: 30 }];
  return data;
}

/** Week 2: the normal Office, with Top Recruits in the recruiting column. */
function weekTwo() {
  const data = clone(O.STATES.win);
  data.week = 2;
  return data;
}

/** What the Office shows: each column's heading and the title (or kind) of each card in it, in order. */
function layout(page) {
  return page.evaluate(() => [...document.querySelectorAll('#office-root .office-col')].map((col) => ({
    heading: col.querySelector('.office-h h2').textContent.replace(/^\d+/, '').trim(),
    cards: [...col.querySelectorAll(':scope > .card')].map((card) => {
      const title = card.querySelector('.card-h h3');
      if (title) return title.textContent.trim();
      if (card.classList.contains('office-outlook')) return '(outlook)';
      if (card.classList.contains('office-next')) return '(game)';
      if (card.classList.contains('office-wire')) return '(wire)';
      return '(' + card.className + ')';
    }),
  })));
}

/** The rows of a card: its text cells, whether the row is the navy "yours" row, and its link. */
function rowsOf(page, selector) {
  return page.locator(selector).evaluate((card) => [...card.querySelectorAll('.wr, .st-r:not(.st-hd), .ptw')].map((row) => {
    // Leaf texts joined by a space: the name and its small label are separate spans.
    const text = (el) => {
      if (!el) return '';
      const leaves = [...el.querySelectorAll('*')].filter((node) => !node.children.length);
      const parts = leaves.length ? leaves.map((node) => node.textContent) : [el.textContent];
      return parts.join(' ').replace(/\s+/g, ' ').trim();
    };
    const grade = row.querySelector('.tdig');
    return {
      cells: [...row.children].map(text).filter(Boolean),
      mine: row.classList.contains('me'),
      href: row.getAttribute('href') || (row.querySelector('a') ? row.querySelector('a').getAttribute('href') : null),
      gradeClass: grade ? grade.className : null,
      bg: getComputedStyle(row).backgroundColor,
    };
  }));
}

/** No hidden attribute, and none of the colours the Office keeps for other jobs. */
async function expectClean(page) {
  const found = await page.evaluate(() => {
    const out = [];
    const walker = document.createTreeWalker(document.getElementById('office-root'), NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent.trim();
      if (text === 'CH' || /\bClutch\b/.test(text) || /\b\d+(\.\d+)?%/.test(text)) out.push(text);
    }
    return out;
  });
  expect(found).toEqual([]);
}

/** How far each column runs past the fold, in px (0 when it fits). */
function pastFold(page) {
  return page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    main.scrollTop = 0;
    const fold = main.getBoundingClientRect().top + main.clientHeight;
    return {
      columns: [...document.querySelectorAll('#office-root .office-col')].map((col) => {
        const last = col.lastElementChild;
        return Math.max(0, Math.round(last.getBoundingClientRect().bottom - fold));
      }),
      scroll: main.scrollHeight - main.clientHeight,
      wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}

async function shots(page, name, width, height) {
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(SHOTS, name + '-' + TAG + '-' + width + '.png') });
  // The whole Office, as the coach sees it by scrolling: a window tall enough to hold it.
  const fold = await pastFold(page);
  if (fold.scroll > 0) {
    await page.setViewportSize({ width, height: height + fold.scroll + 8 });
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(SHOTS, name + '-full-' + TAG + '-' + width + '.png') });
    await page.setViewportSize({ width, height });
  }
  return fold;
}

/* ----------------------------------------------------------- season 1 --- */

test('week 1, season 1: every section, in order, with its content', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, seasonOne());
  expect(await layout(page)).toEqual([
    { heading: 'Season Preview', cards: ['Rankings', 'Key Players', 'Preseason All-Americans'] },
    // No Team snapshot in week 1: before camp it could only say "Set after camp".
    { heading: 'Opening Week', cards: ['(game)', 'Circle these', 'Preseason National Rankings'] },
    { heading: 'Recruiting', cards: ['(wire)', 'Walk-ons', 'Top Recruits (Region A)'] },
  ]);

  // No "Picked Nth of 8" card (removed 2026-10-02): Rankings says the conference place.
  await expect(page.locator('#office-root .office-outlook')).toHaveCount(0);
  await expect(page.locator('#office-root')).not.toContainText(/Picked \d/);

  // Rankings: three lines from the preseason national rank.
  expect((await rowsOf(page, '#office-root .office-ranks')).map((row) => row.cells)).toEqual([
    ['Conference', '4', 'of 8'], ['Region', '7', 'of 16'], ['National', '40', 'of 128'],
  ]);
  // Season 1 has no last season: the card ends at its rows.
  await expect(page.locator('#office-root .office-ranks .rk-last')).toHaveCount(0);
  await expect(page.locator('#office-root')).not.toContainText(/Last season: \d/);

  // Key Players: the roster's columns in the roster's order, names to the player page.
  const kpHead = await page.locator('#office-root .office-kp .st-hd span').allTextContents();
  expect(kpHead).toEqual(['Player', 'RT', 'Pos', 'Yr', 'Ht', 'Wt']);
  const key = await rowsOf(page, '#office-root .office-kp');
  expect(key).toHaveLength(5);
  expect(key[0].cells).toEqual(['Jalen Carter', 'A', 'PG', 'SR', '6′3″', '190']);
  expect(key[1].cells).toEqual(['Marcus Ruiz', 'B+', 'SF', 'JR', '6′7″', '215']);
  key.forEach((row) => {
    expect(row.href).toMatch(/player/);
    expect(row.gradeClass).toMatch(/\brt-(low|mid|high|elite)\b/); // the canonical RT ramp
  });
  expect(key[0].gradeClass).toMatch(/rt-elite/);
  // A long name gives way; the columns stay where they are.
  const kpCols = await page.locator('#office-root .office-kp').evaluate((card) => {
    const lefts = (row) => [...row.children].slice(1).map((cell) => Math.round(cell.getBoundingClientRect().right));
    const rows = [...card.querySelectorAll('.st-r')];
    return { head: lefts(rows[0]), rows: rows.slice(1).map(lefts), right: Math.round(card.getBoundingClientRect().right) };
  });
  kpCols.rows.forEach((cols) => expect(cols).toEqual(kpCols.head));
  expect(kpCols.head[kpCols.head.length - 1]).toBeLessThanOrEqual(kpCols.right);

  // Preseason All-Americans: first team only. Position, player, team, RT. The user's player is navy.
  await expect(page.locator('#office-root .office-aa .card-h .meta')).toHaveText('First team');
  const aa = await rowsOf(page, '#office-root .office-aa');
  expect(aa.map((row) => row.cells)).toEqual([
    ['PG', 'Tyrese Vaughn Long Island Methodist', 'A++'],
    ['SG', 'Cal Okafor Chapel Hill', 'A+'],
    ['SF', 'Marcus Ruiz Amariabi International', 'A+'],
    ['PF', 'Dre Hollis Four Corners', 'A+'],
    ['C', 'Ansel Brandt Seattle AAA', 'A++'],
  ]);
  expect(aa.map((row) => row.mine)).toEqual([false, false, true, false, false]);
  // Each row carries the player's headshot: a square with a small corner, between the
  // position and the name, the same size on every row.
  const shots = await page.locator('#office-root .office-aa .wr').evaluateAll((rows) => rows.map((row) => {
    const box = row.querySelector('.aa-pt');
    if (!box) return null;
    const r = box.getBoundingClientRect();
    const tag = row.querySelector('.wr-k').getBoundingClientRect();
    const name = row.querySelector('.nm').getBoundingClientRect();
    const rowBox = row.getBoundingClientRect();
    return {
      w: Math.round(r.width), h: Math.round(r.height), radius: parseFloat(getComputedStyle(box).borderTopLeftRadius),
      img: !!box.querySelector('img'), afterTag: r.left >= tag.right - 0.5, beforeName: r.right <= name.left + 0.5,
      inside: r.top >= rowBox.top - 0.5 && r.bottom <= rowBox.bottom + 0.5,
    };
  }));
  expect(shots).toHaveLength(5);
  shots.forEach((shot) => {
    expect(shot).not.toBeNull();
    expect(shot).toMatchObject({ w: 40, h: 40, afterTag: true, beforeName: true, inside: true });
    expect(shot.radius).toBeLessThanOrEqual(8); // a square, never a circle
  });
  expect(aa[2].bg).not.toBe('rgba(0, 0, 0, 0)');
  expect(aa[0].bg).toBe('rgba(0, 0, 0, 0)');

  // Opening Week: the opener, with the opponent's preseason rank. They did not meet last season.
  const game = page.locator('#office-root .office-next');
  await expect(game.locator('.nx-open')).toHaveText('Season Opener');
  await expect(game.locator('.nx-name')).toContainText('Crickstown');
  await expect(game.locator('.nx-sub')).toHaveText('Preseason #21 · Conference A2');
  await expect(game).not.toContainText('0-0');
  // Before camp the Team snapshot has nothing to say, so week 1 does not show it.
  await expect(page.locator('#office-root .office-snap')).toHaveCount(0);
  await expect(page.locator('#office-root')).not.toContainText('Set after camp');

  // Circle these: the three toughest, with their weeks.
  expect((await rowsOf(page, '#office-root .office-circle')).map((row) => row.cells)).toEqual([
    ['Wk 4', 'Long Island Methodist Away', '#3'],
    ['Wk 11', 'Alpha Home', '#12'],
    ['Wk 19', 'Chapel Hill Away', '#7'],
  ]);

  // Preseason National Rankings: the conference by national rank, best first; the user navy.
  const pre = await rowsOf(page, '#office-root .office-pre');
  expect(pre.map((row) => row.cells)).toEqual([
    ['12', 'Alpha'], ['21', 'Crickstown'], ['33', 'Gamma'], ['40', 'Amariabi International'],
    ['58', 'Delta'], ['77', 'Echo'], ['96', 'Foxtrot'], ['120', 'Golf'],
  ]);
  expect(pre.map((row) => row.mine)).toEqual([false, false, false, true, false, false, false, false]);
  await expect(page.locator('#office-root .office-pre .st-more')).toHaveAttribute('href', /rankings-view/);
  await expect(page.locator('#office-root .office-st')).toHaveCount(1); // it replaces the standings card

  // Recruiting: no leans yet; the walk-ons; the region's top recruits and their top lean.
  await expect(page.locator('#office-root .office-wire .wr-empty')).toHaveText('No preseason leans');
  expect((await rowsOf(page, '#office-root .office-walk')).map((row) => row.cells)).toEqual([
    ['Sam Ortega SG · FR', 'D'], ['Kip Lawson PF · SO', 'D'], ['Teo Marsh PG · JR', 'F'],
  ]);
  const top = await rowsOf(page, '#office-root .office-top');
  expect(top.map((row) => row.cells)).toEqual([
    // The name; under it position, RT, year; the lean on the right (v3-office.spec.js).
    ['Darius Kemp C A+ SR', 'Alpha'],
    ['Miles Hart SG A SR', 'Amariabi International'],
    ['Owen Blake PF A JR', 'Crickstown'],
    ['Jon Abara PG B+ SR', 'No lean'],
    ['Luka Fenn SF B SO', 'Gamma'],
  ]);
  expect(top.map((row) => row.mine)).toEqual([false, true, false, false, false]);
  await expect(page.locator('#office-root .office-top .card-h h3')).toHaveText('Top Recruits (Region A)');
  await expect(page.locator('#office-root .office-top .card-h .meta')).toHaveCount(0);

  // Five rows or fewer per section (the conference table is its eight teams).
  const counts = await page.evaluate(() => [...document.querySelectorAll('#office-root .card')].map((card) => ({
    name: card.className, rows: card.querySelectorAll('.wr, .st-r:not(.st-hd), .ptw').length,
  })));
  counts.filter((c) => !/office-st/.test(c.name)).forEach((c) => expect(c.rows, c.name).toBeLessThanOrEqual(5));
  await expectClean(page);
});

/* ------------------------------------------------------- later seasons --- */

test('week 1, a later season: last season, the newcomers, and last season’s meeting', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, laterSeason());
  expect((await layout(page))[0]).toEqual({
    heading: 'Season Preview',
    cards: ['Rankings', 'Key Players', 'Newcomers', 'Preseason All-Americans'],
  });
  await expect(page.locator('#office-root .office-outlook')).toHaveCount(0);
  // Last season: one quiet line at the bottom of the Rankings card, en dash in the record.
  const lastLine = page.locator('#office-root .office-ranks .rk-last');
  await expect(lastLine).toHaveCount(1);
  await expect(lastLine).toHaveText('Last season: 18\u20138, lost in the Region semifinal.');
  expect(await lastLine.evaluate((node) => {
    const card = node.closest('.office-ranks');
    const rows = [...card.querySelectorAll('.ptw')];
    const cs = getComputedStyle(node);
    const rowCs = getComputedStyle(card.querySelector('.ptw b'));
    return {
      last: card.lastElementChild === node,
      below: node.getBoundingClientRect().top >= rows[rows.length - 1].getBoundingClientRect().bottom,
      quieter: parseFloat(cs.fontSize) < parseFloat(rowCs.fontSize),
      color: cs.color,
      fits: node.scrollWidth <= node.clientWidth,
    };
  })).toEqual({ last: true, below: true, quieter: true, color: 'rgba(255, 255, 255, 0.6)', fits: true });
  const newcomers = await rowsOf(page, '#office-root .office-new');
  expect(newcomers.map((row) => row.cells)).toEqual([
    ['Rafe Dalton PG', 'B'], ['Emeka Sorensen C', 'C+'], ['Coby Tran SF', 'C'], ['Will Hask SG', 'C'],
  ]);
  newcomers.forEach((row) => expect(row.href).toMatch(/player/));
  await expect(page.locator('#office-root .office-new .nc-sum')).toHaveText('Returning 9 · Lost 3 seniors · 4 newcomers');
  await expect(page.locator('#office-root .office-next .nx-sub')).toHaveText('Preseason #21 · Conference A2 · Last season: W 71\u201364');
  expect((await rowsOf(page, '#office-root .office-walk')).map((row) => row.cells)).toEqual([['Gus Penn SF · FR', 'D']]);
  await expect(page.locator('#gob-week-phase')).toHaveText('Season 3');
  await expectClean(page);
});

test('a loss last season reads as a loss', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = laterSeason();
  data.office_digest.season_preview.opener.last_meeting = { won: false, user_score: 58, opp_score: 61, week: 9 };
  data.office_digest.season_preview.outlook.last_season = { wins: 31, losses: 5, finish: 'won the National championship' };
  await O.openOffice(page, data);
  await expect(page.locator('#office-root .office-next .nx-sub')).toContainText('Last season: L 58\u201361');
  await expect(page.locator('#office-root .office-ranks .rk-last')).toHaveText('Last season: 31\u20135, won the National championship.');
});

test('a last season with a record but no finish, or no record at all, keeps the Rankings card tidy', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = laterSeason();
  data.office_digest.season_preview.outlook.last_season = { wins: 12, losses: 14, finish: null };
  await O.openOffice(page, data);
  await expect(page.locator('#office-root .office-ranks .rk-last')).toHaveText('Last season: 12\u201314.');
  const none = laterSeason();
  none.office_digest.season_preview.outlook.last_season = null;
  await O.openOffice(page, none);
  await expect(page.locator('#office-root .office-ranks .rk-last')).toHaveCount(0);
});

/* -------------------------------------------------------------- week 2 --- */

test('week 2: the normal Office, plus Top Recruits', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, weekTwo());
  expect(await layout(page)).toEqual([
    { heading: 'Since last week', cards: ['(card wkc ar-card)'] },
    { heading: 'This Week', cards: ['(game)', 'Team snapshot', 'Conference A2 standings'] },
    { heading: 'Recruiting', cards: ['(wire)', 'Top Recruits (Region A)'] },
  ].map((col, i) => (i === 0 ? { heading: col.heading, cards: (expect.any(Array)) } : col)));
  // No week-1 section survives into week 2.
  for (const selector of ['.office-outlook', '.office-ranks', '.office-kp', '.office-new', '.office-aa', '.office-circle', '.office-pre', '.office-walk', '.nx-open']) {
    await expect(page.locator('#office-root ' + selector), selector).toHaveCount(0);
  }
  await expect(page.locator('#office-root .office-wire .wr').first()).toBeVisible();
  expect(await rowsOf(page, '#office-root .office-top')).toHaveLength(5);
  // From week 2 the Team snapshot is back where it was.
  await expect(page.locator('#office-root .office-snap')).toHaveCount(1);
  await expect(page.locator('#office-root .office-next .nx-sub')).toContainText('11\u20138'); // the record, as before
  await expectClean(page);
});

test('Top Recruits steps aside from Signing Day', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, clone(O.STATES.signing_day));
  await expect(page.locator('#office-root .office-top')).toHaveCount(0);
  // Even if a payload still carried it, the signed class owns the column once Signing Day has run.
  const after = clone(O.STATES.regular);
  after.week = 36;
  after.office_digest.signed_class = { recruits: [{ name: 'Rafe Dalton', position: 'PG', rt_now: 62 }] };
  after.office_digest.top_recruits = O.topRecruitsBlock();
  await O.openOffice(page, after);
  await expect(page.locator('#office-root .office-class')).toHaveCount(1);
  await expect(page.locator('#office-root .office-top')).toHaveCount(0);
});

/* -------------------------------------------------------- empty states --- */

test('empty states: no walk-ons, no recruits, no newcomers count, no meeting', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = laterSeason();
  const preview = data.office_digest.season_preview;
  preview.walk_ons = [];
  preview.newcomers.lost_seniors = null; // a save that rolled over before the snapshot existed
  preview.opener.last_meeting = null;
  preview.all_americans = [];
  preview.circle_these = [];
  data.office_digest.top_recruits = { region: 'A', rows: [] };
  await O.openOffice(page, data);
  await expect(page.locator('#office-root .office-walk .wr-empty')).toHaveText('No walk-ons');
  await expect(page.locator('#office-root .office-walk .wr')).toHaveCount(0);
  await expect(page.locator('#office-root .office-top .wr-empty')).toHaveText('No recruits in your region yet');
  await expect(page.locator('#office-root .office-new .nc-sum')).toHaveText('Returning 9 · 4 newcomers');
  await expect(page.locator('#office-root .office-next .nx-sub')).toHaveText('Preseason #21 · Conference A2');
  // A section with nothing to say is left out, not drawn empty.
  await expect(page.locator('#office-root .office-aa')).toHaveCount(0);
  await expect(page.locator('#office-root .office-circle')).toHaveCount(0);
  await expectClean(page);
});

test('a preview that is not ready paints none of its sections; the Office still loads', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = seasonOne();
  data.office_digest.season_preview = { ready: false, preseason_rank: 40, national_rank: 40, opener: O.nextBlock({ week: 1 }) };
  data.office_digest.top_recruits = null;
  await O.openOffice(page, data);
  const cols = await layout(page);
  expect(cols[0]).toEqual({ heading: 'Season Preview', cards: [] });
  expect(cols[1].cards).toEqual(['(game)', 'Conference A2 standings']);
  expect(cols[2].cards).toEqual(['(wire)']);
  await expect(page.locator('#office-root .office-wire .wr-empty')).toHaveText('No preseason leans');
});

test('the loading Office shows the skeleton, never a half-built section', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const { stubAuth } = require('./helpers/auth');
  await stubAuth(page);
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await O.installApi(page, seasonOne());
  await page.route('**/franchise/command-center/data**', async (route) => {
    await held;
    await route.fallback();
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + O.FID + '&team_id=' + O.TID);
  await page.waitForSelector('#office-root');
  await page.waitForTimeout(1200);
  expect(await page.locator('#office-root .office-outlook, #office-root .office-kp, #office-root .office-top, #office-root .office-walk').count()).toBe(0);
  await expect(page.locator('#office-root')).toHaveAttribute('aria-busy', 'true');
  release();
  await expect(page.locator('#office-root .office-kp')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('#office-root')).toHaveAttribute('aria-busy', 'false');
});

/* ------------------------------------------- shots, and the fold report --- */

const VIEWS = [
  ['season-1-week-1', seasonOne],
  ['later-season-week-1', laterSeason],
  ['week-2', weekTwo],
];

for (const [width, height] of SIZES) {
  test('shots and fold at ' + width + 'x' + height, async ({ page }) => {
    const report = {};
    for (const [name, build] of VIEWS) {
      await page.setViewportSize({ width, height });
      await O.openOffice(page, build());
      await page.waitForTimeout(name === 'week-2' ? 2500 : 600);
      const fold = await shots(page, name, width, height);
      report[name] = fold;
      // Nothing is cut off sideways, and no card overlaps the one under it.
      expect(fold.wide, name).toBeLessThanOrEqual(0);
      const overlaps = await page.evaluate(() => {
        const bad = [];
        document.querySelectorAll('#office-root .office-col').forEach((col, c) => {
          const cards = [...col.querySelectorAll(':scope > .card')].map((card) => card.getBoundingClientRect());
          for (let i = 1; i < cards.length; i += 1) {
            if (cards[i].top < cards[i - 1].bottom - 0.5) bad.push('col ' + (c + 1) + ' card ' + i);
          }
        });
        // A row's text never spills out of its row.
        document.querySelectorAll('#office-root .office-list .wr, #office-root .office-tb .st-r, #office-root .office-st .st-r').forEach((row) => {
          const box = row.getBoundingClientRect();
          [...row.querySelectorAll('.nm, .st-nm, .wr-2, .tdig, .tb-c')].forEach((cell) => {
            const r = cell.getBoundingClientRect();
            if (r.width && (r.right > box.right + 1 || r.bottom > box.bottom + 1)) bad.push('cell out of row: ' + cell.textContent.trim());
          });
        });
        return bad;
      });
      expect(overlaps, name).toEqual([]);
    }
    fs.writeFileSync(path.join(SHOTS, 'fold-' + TAG + '-' + width + '.json'), JSON.stringify(report, null, 2));
  });
}
