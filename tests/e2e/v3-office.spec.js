// @ts-check
/**
 * Office, final polish round (polish/v3-office, 2026-10-03).
 *
 * 1  Team snapshot: the heading reads "Team Attributes Moved Most"; neither quiet line
 *    ("Set after camp", "No movement this week") carries a trailing dash.
 * 2  Top Recruits: "Top Recruits (Region A)" with a Top / Watchlist segment on the right.
 *    Watchlist is the coach's five best by RT from any region, titled "Your Watchlist", and
 *    one line when empty. Rows: the name; under it position, RT, year; the lean on the right.
 *    The choice is remembered for the session.
 * 3  Week 35, Orders submitted, Signing Day not run: the Signing Day card, then everyone
 *    the coach put points on, most points first, the points on the right.
 *
 * V3_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/v3-office');
const TAG = process.env.V3_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));

function week(n) {
  const data = clone(O.STATES.win);
  data.week = n;
  data.office_digest.top_recruits = O.topRecruitsBlock();
  return data;
}

function signingSubmitted() {
  const data = clone(O.STATES.signing_day);
  data.office_digest.signing_day.orders_submitted = true;
  data.office_digest.signing_day.orders = O.submittedOrders();
  data.office_digest.signing_day.points_remaining = 12;
  return data;
}

/** The recruits card: its title, the segment, and each row as the eye reads it. */
function recruitsCard(page, selector) {
  return page.locator(selector || '#office-root .office-top').evaluate((card) => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const head = card.querySelector('.card-h');
    const title = head.querySelector('h3');
    const seg = head.querySelector('.stats-toggle');
    const box = (el) => el.getBoundingClientRect();
    return {
      title: text(title),
      titleLeft: Math.round(box(title).left - box(head).left),
      meta: head.querySelectorAll('.meta').length,
      seg: seg ? {
        role: seg.getAttribute('role'),
        buttons: [...seg.querySelectorAll('button')].map((b) => ({
          text: text(b), on: b.classList.contains('on'), pressed: b.getAttribute('aria-pressed'),
        })),
        // Flush with the right edge of the title row, and after the title.
        rightGap: Math.round(box(head).right - box(seg).right),
        afterTitle: box(seg).left >= box(title).right,
        sameRow: Math.abs((box(seg).top + box(seg).bottom) / 2 - (box(title).top + box(title).bottom) / 2) <= 6,
      } : null,
      empty: text(card.querySelector('.wr-empty')),
      rows: [...card.querySelectorAll('.wr')].map((row) => {
        const name = row.querySelector('.wr-1 .nm');
        const facts = row.querySelector('.rc-facts');
        const right = row.lastElementChild;
        const natural = (el) => {
          const range = document.createRange();
          range.selectNodeContents(el);
          return range.getBoundingClientRect().width;
        };
        return {
          name: text(name),
          // The second line, in order: Pos, RT, YR, each a quiet label and its value.
          facts: facts ? [...facts.children].map(text) : [],
          factsBelowName: facts ? box(facts).top >= box(name).bottom - 1 : false,
          nameLine: [...row.querySelector('.wr-1').children].map(text),
          right: (right.children.length ? [...right.children].map(text).join(' ') : text(right)),
          rightClass: right.className,
          rightOfBody: box(right).left >= box(row.querySelector('.wr-b')).right - 1,
          mine: row.classList.contains('me'),
          grade: !!(facts && facts.querySelector('.tdig')),
          clipped: [name, right].some((el) => natural(el) > box(el).width + 0.5),
          href: row.getAttribute('href') || '',
        };
      }),
    };
  });
}

/* ------------------------------------------------------- 1: Team snapshot --- */

test('1: the snapshot heading reads "Team Attributes Moved Most"; no quiet line has a dash', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const moved = week(10);
  await O.openOffice(page, moved);
  const snap = page.locator('#office-root .office-snap');
  await expect(snap.locator('.sub-h', { hasText: /moved most/i })).toHaveText('Team Attributes Moved Most');
  await expect(snap).not.toContainText(/^Moved most$/m);
  // The heading fits its card on one line.
  expect(await snap.locator('.sub-h', { hasText: /moved most/i }).evaluate((node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    return range.getClientRects().length === 1 && node.scrollWidth <= node.clientWidth;
  })).toBe(true);

  for (const [state, label] of [['set_after_camp', 'Set after camp'], ['ready', 'No movement this week']]) {
    const data = week(10);
    data.office_digest.team_snapshot.state = state;
    data.office_digest.team_snapshot.moved_most = [];
    await O.openOffice(page, data);
    const line = page.locator('#office-root .office-snap .msr-empty');
    await expect(line).toHaveCount(1);
    await expect(line).toHaveText(label);
    expect(await line.evaluate((node) => node.children.length), label + ' is the whole line').toBe(1);
    await expect(page.locator('#office-root .office-snap')).not.toContainText('—');
    await expect(page.locator('#office-root .office-snap .sub-h', { hasText: /moved most/i })).toHaveText('Team Attributes Moved Most');
  }
});

/* --------------------------------------------------------- 2: Top Recruits --- */

test('2a/2b/2d: "Top Recruits (Region A)", the segment on the right, and the row layout', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  const card = await recruitsCard(page);
  // The region sits beside the title, as part of it; nothing is right-aligned but the segment.
  expect(card.title).toBe('Top Recruits (Region A)');
  expect(card.titleLeft).toBe(0);
  expect(card.meta).toBe(0);
  // The app's segment control: two choices, Top on.
  expect(card.seg.role).toBe('group');
  expect(card.seg.buttons).toEqual([
    { text: 'Top', on: true, pressed: 'true' },
    { text: 'Watchlist', on: false, pressed: 'false' },
  ]);
  expect(card.seg.rightGap).toBe(0);
  expect(card.seg.afterTitle).toBe(true);
  expect(card.seg.sameRow).toBe(true);
  // It is the same control the tables use: same class, same on-state paint.
  const paint = await page.evaluate(() => {
    const on = document.querySelector('#office-root .office-top .stats-toggle button.on');
    const off = document.querySelector('#office-root .office-top .stats-toggle button:not(.on)');
    const ring = getComputedStyle(on.parentElement).boxShadow;
    return { on: getComputedStyle(on).backgroundColor, off: getComputedStyle(off).backgroundColor, ring: ring !== 'none' };
  });
  expect(paint).toEqual({ on: 'rgba(255, 255, 255, 0.1)', off: 'rgba(0, 0, 0, 0)', ring: true });

  // Rows: the name alone on top; under it position, RT, year; the lean on the right.
  expect(card.rows.map((row) => [row.name, row.facts, row.right])).toEqual([
    ['Darius Kemp', ['Pos: C', 'RT: A+', 'YR: SR'], 'Alpha'],
    ['Miles Hart', ['Pos: SG', 'RT: A', 'YR: SR'], 'Amariabi International'],
    ['Owen Blake', ['Pos: PF', 'RT: A', 'YR: JR'], 'Crickstown'],
    ['Jon Abara', ['Pos: PG', 'RT: B+', 'YR: SR'], 'No lean'],
    ['Luka Fenn', ['Pos: SF', 'RT: B', 'YR: SO'], 'Gamma'],
  ]);
  card.rows.forEach((row) => {
    expect(row.nameLine, row.name).toEqual([row.name]);
    expect(row.factsBelowName, row.name).toBe(true);
    expect(row.grade, row.name).toBe(true);
    expect(row.rightClass, row.name).toMatch(/rc-lean/);
    expect(row.rightOfBody, row.name).toBe(true);
    expect(row.clipped, row.name + ' is not truncated').toBe(false);
    expect(row.href, row.name).toMatch(/recruiting\.html/);
  });
  // The recruit leaning to the coach's own team is still the highlighted row.
  expect(card.rows.map((row) => row.mine)).toEqual([false, true, false, false, false]);
  // No RT in the right-hand column any more, and no "Leans" prefix.
  await expect(page.locator('#office-root .office-top .sg-rt')).toHaveCount(0);
  await expect(page.locator('#office-root .office-top')).not.toContainText(/Leans /);
});

test('2c: Watchlist is the coach’s five best from any region, titled "Your Watchlist"', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' }).click();
  const card = await recruitsCard(page);
  expect(card.title).toBe('Your Watchlist');
  expect(card.seg.buttons).toEqual([
    { text: 'Top', on: false, pressed: 'false' },
    { text: 'Watchlist', on: true, pressed: 'true' },
  ]);
  expect(card.rows.map((row) => [row.name, row.facts, row.right])).toEqual([
    ['Tobias Okonkwo-Reyes', ['Pos: PF', 'RT: A+', 'YR: SR'], 'Long Island Methodist'],
    ['Miles Hart', ['Pos: SG', 'RT: A', 'YR: SR'], 'Amariabi International'],
    ['Enzo Varga', ['Pos: PG', 'RT: A', 'YR: JR'], 'Chapel Hill'],
    ['Sol Whitaker', ['Pos: C', 'RT: B+', 'YR: SR'], 'No lean'],
    ['Kofi Brandt', ['Pos: SF', 'RT: B+', 'YR: FR'], 'Delta'],
  ]);
  card.rows.forEach((row) => {
    expect(row.factsBelowName, row.name).toBe(true);
    expect(row.clipped, row.name + ' is not truncated').toBe(false);
  });
  // Clicking the list did not leave the Office or reload it.
  expect(new URL(page.url()).pathname).toBe('/franchise-command-center.html');
  // Back to Top: the region returns.
  await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Top' }).click();
  expect((await recruitsCard(page)).title).toBe('Top Recruits (Region A)');
});

test('2c: an empty watchlist shows one line', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = week(10);
  data.office_digest.top_recruits.watchlist = { count: 0, rows: [] };
  await O.openOffice(page, data);
  await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' }).click();
  const card = await recruitsCard(page);
  expect(card.title).toBe('Your Watchlist');
  expect(card.rows).toEqual([]);
  expect(card.empty).toBe('Hey Coach, add players to your watchlist');
  await expect(page.locator('#office-root .office-top .wr-empty')).toHaveCount(1);
  // A payload from before the watchlist block (an older server) never claims the watchlist
  // is empty: see v3-office-2.spec.js.
});

test('2e: the choice is remembered for the session, and a new session starts on Top', async ({ page, context }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' }).click();
  expect(await page.evaluate(() => sessionStorage.getItem('gob-office-recruits-list'))).toBe('watchlist');
  // The Office paints again (a reload, the next week): still Watchlist.
  await page.reload();
  await expect(page.locator('#office-root .office-top .stats-toggle button.on')).toHaveText('Watchlist');
  expect((await recruitsCard(page)).title).toBe('Your Watchlist');
  await O.openOffice(page, week(11));
  await expect(page.locator('#office-root .office-top .stats-toggle button.on')).toHaveText('Watchlist');
  // Week 1 has the same card.
  const first = clone(O.STATES.first_week);
  first.office_digest.top_recruits = O.topRecruitsBlock();
  await O.openOffice(page, first);
  await expect(page.locator('#office-root .office-top .stats-toggle button.on')).toHaveText('Watchlist');
  // A new session (a new tab) starts on Top.
  const fresh = await context.newPage();
  await fresh.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(fresh, week(10));
  await expect(fresh.locator('#office-root .office-top .stats-toggle button.on')).toHaveText('Top');
  await fresh.close();
});

test('2: the segment is a keyboard control and never navigates', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, week(10));
  const watch = page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' });
  await watch.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#office-root .office-top .stats-toggle button.on')).toHaveText('Watchlist');
  expect(new URL(page.url()).pathname).toBe('/franchise-command-center.html');
});

/* ------------------------------------------------------ 3: week 35 Orders --- */

test('3: Orders submitted — the Signing Day card, then everyone with points, most first', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, signingSubmitted());
  const col = page.locator('#office-root .office-col').nth(2);
  // The open-spots card stays on top, with its numbers.
  const cards = await col.evaluate((node) => [...node.querySelectorAll(':scope > .card')].map((card) => card.className.split(' ').filter((c) => /^office-/.test(c)).join(' ')));
  expect(cards).toEqual(['office-sign', 'office-list office-orders']);
  const sign = col.locator('.office-sign');
  await expect(sign.locator('.sg-pv b')).toHaveText('12');
  await expect(sign).toContainText('Open spots');
  await expect(sign.locator('.mv-cell', { hasText: 'Open spots' }).locator('b')).toHaveText('3');
  // The list below is all of them, so the card no longer repeats three "Targets".
  await expect(sign).not.toContainText('Targets');
  await expect(sign.locator('.sg-t')).toHaveCount(0);

  const card = await recruitsCard(page, '#office-root .office-orders');
  expect(card.title).toBe('Your Orders');
  expect(card.seg).toBe(null);
  expect(card.rows.map((row) => [row.name, row.facts, row.right])).toEqual([
    ['Miles Hart', ['Pos: SG', 'RT: A', 'YR: SR'], '18 pts'],
    ['Owen Blake', ['Pos: PF', 'RT: B+', 'YR: JR'], '12 pts'],
    ['Tobias Okonkwo-Reyes', ['Pos: PF', 'RT: A+', 'YR: SR'], '5 pts'],
    ['Sol Whitaker', ['Pos: C', 'RT: B', 'YR: SR'], '2 pts'],
    ['Kofi Brandt', ['Pos: SF', 'RT: C+', 'YR: FR'], '1 pt'],
  ]);
  card.rows.forEach((row) => {
    expect(row.nameLine, row.name).toEqual([row.name]);
    expect(row.factsBelowName, row.name).toBe(true);
    expect(row.rightClass, row.name).toMatch(/rc-pts/);
    expect(row.clipped, row.name).toBe(false);
  });
  // The coach's own points only: nothing about odds, scores or multipliers.
  await expect(page.locator('#office-root .office-orders')).not.toContainText(/score|odds|chance|%|x\d/i);
  // Top Recruits has stepped aside by Signing Day.
  await expect(page.locator('#office-root .office-top')).toHaveCount(0);
});

test('3: before the Orders are submitted the Office is as it was (Targets, no list)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, clone(O.STATES.signing_day));
  await expect(page.locator('#office-root .office-orders')).toHaveCount(0);
  await expect(page.locator('#office-root .office-sign')).toContainText('Targets');
  await expect(page.locator('#office-root .office-sign .sg-t')).toHaveCount(2);
  // Submitted with no points on anyone: no empty list.
  const none = signingSubmitted();
  none.office_digest.signing_day.orders = [];
  await O.openOffice(page, none);
  await expect(page.locator('#office-root .office-orders')).toHaveCount(0);
  await expect(page.locator('#office-root .office-sign .sg-t')).toHaveCount(2);
});

/* ----------------------------------------------------------------- fit --- */

for (const [width, height] of SIZES) {
  test('nothing is clipped or wide at ' + width, async ({ page }) => {
    await page.setViewportSize({ width, height });
    for (const [name, build, pick] of [
      ['top', () => week(10), null],
      ['watchlist', () => week(10), 'Watchlist'],
      ['orders', signingSubmitted, null],
    ]) {
      await O.openOffice(page, build());
      if (pick) await page.locator('#office-root .office-top .stats-toggle button', { hasText: pick }).click();
      else if (name === 'top') await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Top' }).click();
      const fit = await page.evaluate(() => ({
        wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        head: [...document.querySelectorAll('#office-root .office-top .card-h, #office-root .office-orders .card-h')]
          .map((h) => h.scrollWidth - h.clientWidth),
        oneLine: [...document.querySelectorAll('#office-root .office-top .card-h h3')].map((h) => {
          const range = document.createRange();
          range.selectNodeContents(h);
          return range.getClientRects().length;
        }),
      }));
      expect(fit.wide, name).toBeLessThanOrEqual(0);
      fit.head.forEach((over) => expect(over, name + ' title row').toBeLessThanOrEqual(0));
      fit.oneLine.forEach((lines) => expect(lines, name + ' title on one line').toBe(1));
    }
  });
}

/* --------------------------------------------------------------- shots --- */

async function settle(page) {
  await page.waitForTimeout(2500); // the arrival
  await page.mouse.move(0, 0);
}

for (const [width, height] of SIZES) {
  test('shots at ' + width, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const shot = async (name, selector) => {
      await page.screenshot({ path: path.join(SHOTS, name + '-' + TAG + '-' + width + '.png') });
      if (selector) {
        const node = page.locator(selector).first();
        if (await node.count()) {
          await node.scrollIntoViewIfNeeded();
          await node.screenshot({ path: path.join(SHOTS, name + '-card-' + TAG + '-' + width + '.png') });
          await page.evaluate(() => window.scrollTo(0, 0));
        }
      }
    };

    // 1: the snapshot heading with movers, and both quiet lines.
    await O.openOffice(page, week(10));
    if (await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Top' }).count()) {
      await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Top' }).click();
    }
    await settle(page);
    await shot('snapshot-moved-most', '#office-root .office-snap');
    // 2: Top.
    await shot('top-recruits-top', '#office-root .office-top');
    for (const [name, state] of [['snapshot-no-movement', 'ready'], ['snapshot-set-after-camp', 'set_after_camp']]) {
      const data = week(10);
      data.office_digest.team_snapshot.state = state;
      data.office_digest.team_snapshot.moved_most = [];
      await O.openOffice(page, data);
      await settle(page);
      await shot(name, '#office-root .office-snap');
    }
    // 2: Watchlist, and the empty watchlist.
    await O.openOffice(page, week(10));
    await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' }).click();
    await settle(page);
    await shot('top-recruits-watchlist', '#office-root .office-top');
    const empty = week(10);
    empty.office_digest.top_recruits.watchlist = { count: 0, rows: [] };
    await O.openOffice(page, empty);
    await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Watchlist' }).click();
    await settle(page);
    await shot('top-recruits-watchlist-empty', '#office-root .office-top');
    // 2: week 1 carries the same card.
    const first = clone(O.STATES.first_week);
    first.office_digest.top_recruits = O.topRecruitsBlock();
    await O.openOffice(page, first);
    await page.locator('#office-root .office-top .stats-toggle button', { hasText: 'Top' }).click();
    await settle(page);
    await shot('top-recruits-week-1', '#office-root .office-top');
    // 3: week 35, Orders submitted; and before they are.
    await O.openOffice(page, signingSubmitted());
    await settle(page);
    await shot('week-35-orders-submitted', '#office-root .office-orders');
    await O.openOffice(page, clone(O.STATES.signing_day));
    await settle(page);
    await shot('week-35-before-orders', '#office-root .office-sign');
  });
}
