// @ts-check
/**
 * Office, Top Recruits follow-up (polish/v3-office-2, Jamie 2026-10-03).
 *
 * 1  Recruit rows (Top, Watchlist, week 35 Your Orders): the second line reads
 *    "Pos: C  RT: C  YR: JH". Labels quiet, values as before (RT keeps its tier colour).
 *    Nothing truncates at 1280 or 1920, with the longest name and the longest lean.
 * 2  A server from before the year and the watchlist block (the site can deploy ahead of
 *    the server): no YR label without a year, and no Watchlist side at all. "Hey Coach,
 *    add players to your watchlist" appears only when the server sent an empty watchlist.
 *
 *   V3O2_SHOTS=before|after   shots to reports/v3-office-2/
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const OUT = path.join(__dirname, '../../reports/v3-office-2');
const PHASE = process.env.V3O2_SHOTS || '';
const SIZES = [[1280, 720], [1920, 1080]];
const EMPTY = 'Hey Coach, add players to your watchlist';
// The longest recruit name and the longest team name in the league data (staging, 2026-10-03).
const LONG_NAME = 'Marquise All Other Names';
const LONG_NAME_2 = 'Bartholomew Fitzpatrick';
const LONG_LEAN = 'Amariabi International';
const LONG_LEAN_2 = 'Long Island Methodist';

const clone = (value) => JSON.parse(JSON.stringify(value));

function week(n) {
  const data = clone(O.STATES.win);
  data.week = n;
  data.office_digest.top_recruits = O.topRecruitsBlock();
  return data;
}

/** Every row at its widest: longest names, longest leans, junior-high year, two-letter grade. */
function widest() {
  const data = week(10);
  const top = data.office_digest.top_recruits;
  const stretch = (row, i) => Object.assign(row, {
    name: i % 2 ? LONG_NAME_2 : LONG_NAME,
    position: i % 2 ? 'SG' : 'PF',
    rt: 97 - i,
    year: i % 2 ? 'SO' : 'JH',
    lean_team_name: i % 2 ? LONG_LEAN_2 : LONG_LEAN,
    lean_team_id: 'team-long-' + i,
  });
  top.rows.forEach(stretch);
  top.watchlist.rows.forEach(stretch);
  return data;
}

function signingSubmitted(wide) {
  const data = clone(O.STATES.signing_day);
  data.office_digest.signing_day.orders_submitted = true;
  data.office_digest.signing_day.orders = O.submittedOrders();
  data.office_digest.signing_day.points_remaining = 12;
  if (wide) {
    data.office_digest.signing_day.orders.forEach((row, i) => Object.assign(row, {
      name: i % 2 ? LONG_NAME_2 : LONG_NAME, position: 'PF', rt: 'A+', year: 'JH', points: 100 - i,
    }));
  }
  return data;
}

/** What the server sent before polish/v3-office: rows without a year, no watchlist block. */
function olderServer() {
  const data = week(10);
  const top = data.office_digest.top_recruits;
  delete top.watchlist;
  top.rows.forEach((row) => { delete row.year; });
  return data;
}

/** Each recruit row of a card as the eye reads it, with what is clipped. */
function readRows(page, selector) {
  return page.locator(selector).evaluate((card) => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const natural = (el) => {
      const range = document.createRange();
      range.selectNodeContents(el);
      return range.getBoundingClientRect().width;
    };
    const clipped = (el) => natural(el) > el.getBoundingClientRect().width + 0.5 || el.scrollWidth > el.clientWidth + 0.5;
    const cardBox = card.getBoundingClientRect();
    return [...card.querySelectorAll('.wr.rc-row')].map((row) => {
      const name = row.querySelector('.wr-1 .nm');
      const facts = row.querySelector('.rc-facts');
      const right = row.lastElementChild;
      const pieces = facts ? [...facts.querySelectorAll('.rc-f')] : [];
      const factsBox = facts ? facts.getBoundingClientRect() : null;
      const rightBox = right.getBoundingClientRect();
      const rowBox = row.getBoundingClientRect();
      return {
        name: text(name),
        // The facts are separate elements spaced by the row's gap: read them as the eye does.
        line: pieces.map(text).join(' '),
        gaps: pieces.slice(1).map((piece, i) => Math.round(piece.getBoundingClientRect().left - pieces[i].getBoundingClientRect().right)),
        facts: pieces.map((piece) => ({
          label: text(piece.querySelector('.rc-k')),
          value: text(piece.lastElementChild),
          labelColor: getComputedStyle(piece.querySelector('.rc-k')).color,
          valueColor: getComputedStyle(piece.lastElementChild).color,
          valueClass: piece.lastElementChild.className,
          labelStyle: getComputedStyle(piece.querySelector('.rc-k')).fontStyle,
        })),
        right: text(right),
        clipped: {
          name: clipped(name),
          facts: facts ? clipped(facts) || factsBox.right > rowBox.right + 0.5 : false,
          right: clipped(right),
          // The second line never runs under the right-hand column or out of the card.
          factsUnderRight: facts ? factsBox.right > rightBox.left + 0.5 && factsBox.bottom > rightBox.top && factsBox.top < rightBox.bottom : false,
          outOfCard: rowBox.right > cardBox.right + 0.5 || rightBox.right > cardBox.right + 0.5,
        },
        oneLine: facts ? facts.getClientRects().length === 1 && factsBox.height < 26 : true,
      };
    });
  });
}

const TOP = '#office-root .office-top';
const ORDERS = '#office-root .office-orders';
const pick = (page, name) => page.locator(TOP + ' .stats-toggle button', { hasText: name }).click();
const QUIET = 'rgba(255, 255, 255, 0.38)';
const VALUE = 'rgba(255, 255, 255, 0.6)';

/* ------------------------------------------------- 1: "Pos: C  RT: C  YR: JH" --- */

test('1: Top — the second line reads "Pos: … RT: … YR: …", labels quiet, values as before', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  const rows = await readRows(page, TOP);
  expect(rows.map((row) => [row.name, row.line])).toEqual([
    ['Darius Kemp', 'Pos: C RT: A+ YR: SR'],
    ['Miles Hart', 'Pos: SG RT: A YR: SR'],
    ['Owen Blake', 'Pos: PF RT: A YR: JR'],
    ['Jon Abara', 'Pos: PG RT: B+ YR: SR'],
    ['Luka Fenn', 'Pos: SF RT: B YR: SO'],
  ]);
  for (const row of rows) {
    expect(row.facts.map((fact) => fact.label), row.name).toEqual(['Pos:', 'RT:', 'YR:']);
    // The facts stand apart from each other, further than a label stands from its value.
    row.gaps.forEach((gap) => expect(gap, row.name).toBeGreaterThanOrEqual(8));
    // Labels: the quiet tone, upright. Values: what they were.
    row.facts.forEach((fact) => {
      expect(fact.labelColor, row.name + ' ' + fact.label).toBe(QUIET);
      expect(fact.labelStyle).toBe('normal');
    });
    expect(row.facts[0].valueColor, row.name + ' position').toBe(VALUE);
    expect(row.facts[2].valueColor, row.name + ' year').toBe(VALUE);
    // RT keeps its tier colour: the grade node and its tier class, not the quiet or value tone.
    expect(row.facts[1].valueClass, row.name).toMatch(/\btdig\b/);
    expect(row.facts[1].valueClass, row.name).toMatch(/rt-|grade-|tier-/);
    expect([QUIET, VALUE]).not.toContain(row.facts[1].valueColor);
  }
  // Two tiers on the card, two colours.
  expect(new Set(rows.map((row) => row.facts[1].valueColor)).size).toBeGreaterThan(1);
});

test('1: RT is painted exactly as the same grade is elsewhere on the Office', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  const paint = await page.evaluate(() => {
    const grade = document.querySelector('#office-root .office-top .rc-f .tdig');
    // The class the RT helper gives that number, painted on a bare node in the same card.
    const probe = document.createElement('b');
    probe.className = grade.className;
    grade.closest('.rc-facts').appendChild(probe);
    const same = getComputedStyle(probe).color;
    probe.remove();
    return { color: getComputedStyle(grade).color, same, text: grade.textContent };
  });
  expect(paint.text).toBe('A+');
  expect(paint.color).toBe(paint.same);
});

test('1: Watchlist rows read the same way', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  await pick(page, 'Watchlist');
  const rows = await readRows(page, TOP);
  expect(rows.map((row) => [row.name, row.line])).toEqual([
    ['Tobias Okonkwo-Reyes', 'Pos: PF RT: A+ YR: SR'],
    ['Miles Hart', 'Pos: SG RT: A YR: SR'],
    ['Enzo Varga', 'Pos: PG RT: A YR: JR'],
    ['Sol Whitaker', 'Pos: C RT: B+ YR: SR'],
    ['Kofi Brandt', 'Pos: SF RT: B+ YR: FR'],
  ]);
  rows.forEach((row) => row.facts.forEach((fact) => expect(fact.labelColor).toBe(QUIET)));
});

test('1: week 35 Your Orders rows read the same way, points on the right', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, signingSubmitted());
  const rows = await readRows(page, ORDERS);
  expect(rows.map((row) => [row.name, row.line, row.right])).toEqual([
    ['Miles Hart', 'Pos: SG RT: A YR: SR', '18pts'],
    ['Owen Blake', 'Pos: PF RT: B+ YR: JR', '12pts'],
    ['Tobias Okonkwo-Reyes', 'Pos: PF RT: A+ YR: SR', '5pts'],
    ['Sol Whitaker', 'Pos: C RT: B YR: SR', '2pts'],
    ['Kofi Brandt', 'Pos: SF RT: C+ YR: FR', '1pt'],
  ]);
  rows.forEach((row) => row.facts.forEach((fact) => expect(fact.labelColor).toBe(QUIET)));
});

test('1: the brief\'s own example — "Pos: C  RT: C  YR: JH"', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = week(10);
  Object.assign(data.office_digest.top_recruits.rows[0], { position: 'C', rt: 55, year: 'JH' });
  await O.openOffice(page, data);
  const rows = await readRows(page, TOP);
  expect(rows[0].line).toMatch(/^Pos: C RT: [A-F][+-]? YR: JH$/);
});

for (const [width, height] of SIZES) {
  test('1: nothing truncates at ' + width + ' with the longest name and lean', async ({ page }) => {
    await page.setViewportSize({ width, height });
    for (const [list, build, card, choose] of [
      ['top', widest, TOP, 'Top'],
      ['watchlist', widest, TOP, 'Watchlist'],
      ['orders', () => signingSubmitted(true), ORDERS, null],
    ]) {
      await O.openOffice(page, build());
      if (choose) await pick(page, choose);
      const rows = await readRows(page, card);
      expect(rows.length, list).toBe(5);
      for (const row of rows) {
        const where = list + ' ' + width + ': ' + row.name;
        expect([LONG_NAME, LONG_NAME_2], where).toContain(row.name);
        expect(row.clipped, where).toEqual({ name: false, facts: false, right: false, factsUnderRight: false, outOfCard: false });
        expect(row.oneLine, where + ' second line on one line').toBe(true);
        expect(row.line, where).toMatch(/^Pos: (PF|SG) RT: [A-F][+-]? YR: (JH|SO)$/);
        if (list !== 'orders') expect([LONG_LEAN, LONG_LEAN_2], where).toContain(row.right);
      }
      const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(wide, list).toBeLessThanOrEqual(0);
    }
  });
}

/* ---------------------------------------- 2: an older server, a newer page --- */

test('2b: no year from the server — no YR label, nothing blank', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, olderServer());
  const rows = await readRows(page, TOP);
  expect(rows.map((row) => row.line)).toEqual([
    'Pos: C RT: A+', 'Pos: SG RT: A', 'Pos: PF RT: A', 'Pos: PG RT: B+', 'Pos: SF RT: B',
  ]);
  await expect(page.locator(TOP)).not.toContainText('YR:');
});

test('2b: no watchlist block from the server — no Watchlist side, and no empty-watchlist message', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, olderServer());
  const card = page.locator(TOP);
  await expect(card).toHaveAttribute('data-watchlist', 'not-sent');
  await expect(card.locator('.stats-toggle')).toHaveCount(0);
  await expect(card.locator('button')).toHaveCount(0);
  await expect(card).not.toContainText('Watchlist');
  await expect(card).not.toContainText(EMPTY);
  await expect(card.locator('.wr-empty')).toHaveCount(0);
  // The Top list is all there, titled with its region.
  await expect(card.locator('.card-h h3')).toHaveText('Top Recruits (Region A)');
  await expect(card.locator('.wr.rc-row')).toHaveCount(5);
});

test('2b: a session that was on Watchlist still opens on Top when the server sends no block', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  await pick(page, 'Watchlist');
  await expect(page.locator(TOP)).toHaveAttribute('data-recruit-list', 'watchlist');
  // Same tab, the next load answered by an older server.
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await O.openOffice(page, olderServer());
  const card = page.locator(TOP);
  await expect(card).toHaveAttribute('data-recruit-list', 'top');
  await expect(card).not.toContainText(EMPTY);
  await expect(card.locator('.wr.rc-row')).toHaveCount(5);
});

test('2b: the empty-watchlist line appears only when the server sent an empty watchlist', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = week(10);
  data.office_digest.top_recruits.watchlist = { count: 0, rows: [] };
  await O.openOffice(page, data);
  const card = page.locator(TOP);
  await expect(card).toHaveAttribute('data-watchlist', 'sent');
  await expect(card.locator('.stats-toggle button')).toHaveText(['Top', 'Watchlist']);
  await expect(card).not.toContainText(EMPTY); // not on the Top side
  await pick(page, 'Watchlist');
  await expect(card.locator('.wr-empty')).toHaveText(EMPTY);
  await expect(card.locator('.wr.rc-row')).toHaveCount(0);

  // A block with no rows array is not an answer either.
  for (const broken of [{ count: 3 }, { rows: null }, null, 'none']) {
    const odd = week(10);
    odd.office_digest.top_recruits.watchlist = broken;
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await O.openOffice(page, odd);
    await expect(page.locator(TOP), JSON.stringify(broken)).toHaveAttribute('data-watchlist', 'not-sent');
    await expect(page.locator(TOP)).not.toContainText(EMPTY);
    await expect(page.locator(TOP + ' .stats-toggle')).toHaveCount(0);
  }
});

/* --------------------------------------------------------------- shots --- */

test.describe('shots', () => {
  test.skip(!PHASE, 'V3O2_SHOTS only');

  for (const [width, height] of SIZES) {
    test('shots at ' + width, async ({ page }) => {
      fs.mkdirSync(OUT, { recursive: true });
      await page.setViewportSize({ width, height });
      const shot = async (name, selector) => {
        await page.waitForTimeout(2500); // the arrival
        await page.mouse.move(0, 0);
        await page.screenshot({ path: path.join(OUT, PHASE + '-' + name + '-' + width + '.png'), animations: 'disabled' });
        const node = page.locator(selector).first();
        if (await node.count()) {
          await node.scrollIntoViewIfNeeded();
          await node.screenshot({ path: path.join(OUT, PHASE + '-' + name + '-card-' + width + '.png'), animations: 'disabled' });
        }
      };
      await O.openOffice(page, week(10));
      await shot('1-top', TOP);
      await pick(page, 'Watchlist');
      await shot('1-watchlist', TOP);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await O.openOffice(page, signingSubmitted());
      await shot('1-orders-week-35', ORDERS);

      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await O.openOffice(page, widest());
      await pick(page, 'Top');
      await shot('1-longest-top', TOP);
      await pick(page, 'Watchlist');
      await shot('1-longest-watchlist', TOP);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await O.openOffice(page, signingSubmitted(true));
      await shot('1-longest-orders', ORDERS);

      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.evaluate(() => sessionStorage.removeItem('gob-office-recruits-list'));
      await O.openOffice(page, olderServer());
      await shot('2-older-server-no-year-no-watchlist', TOP);
      if (PHASE === 'before') {
        // What the page said before: the Watchlist side of a response that had no watchlist.
        const button = page.locator(TOP + ' .stats-toggle button', { hasText: 'Watchlist' });
        if (await button.count()) {
          await button.click();
          await shot('2-older-server-watchlist-side', TOP);
        }
      }
      const empty = week(10);
      empty.office_digest.top_recruits.watchlist = { count: 0, rows: [] };
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await O.openOffice(page, empty);
      await pick(page, 'Watchlist');
      await shot('2-server-sent-empty-watchlist', TOP);
    });
  }
});
