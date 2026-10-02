// @ts-check
/**
 * Office follow-ups (polish/office-followups, 2026-10-02).
 *
 * M  Team snapshot "Moved most" ranks only the eight signed-scale team attributes
 *    (Offense, Defense, Discipline, Fast Break, Fast Break Defense, Fight, P/T Offense,
 *    P/T Defense). Chemistry, Shooting and Rebounding are on other scales and are never
 *    listed; when none of the eight moved the card shows one quiet line, "No movement this
 *    week", with no trailing dash.
 *
 * The server filters the list (tests/test_office_digest.py). These tests feed the card
 * payloads that still carry the excluded measures, the way an unfiltered server would.
 *
 * OFU_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/office-followups');
const TAG = process.env.OFU_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));

function officeWith(moved) {
  const data = clone(O.STATES.win);
  data.week = 10;
  data.office_digest.team_snapshot.state = 'ready';
  data.office_digest.team_snapshot.moved_most = moved;
  return data;
}

/** Shooting moved most, then Rebounding, Chemistry and Momentum; two of the eight moved less. */
const SHOOTING_FIRST = [
  { measure: 'shot_threshold', value: 84, delta: -6 },
  { measure: 'rebound_modifier', value: 6, delta: 5 },
  { measure: 'team_chemistry', value: 19, delta: 5 },
  { measure: 'momentum_score', value: 11, delta: 9 },
  { measure: 'discipline', value: 3, delta: -2 },
  { measure: 'fb_opp_modifier', value: 4, delta: 1 },
  { measure: 'fight', value: 3, delta: 0.5 },
];
/** Only the excluded three moved. */
const EXCLUDED_ONLY = [
  { measure: 'shot_threshold', value: 84, delta: -6 },
  { measure: 'rebound_modifier', value: 6, delta: 5 },
  { measure: 'team_chemistry', value: 19, delta: 5 },
];

/** The Team snapshot card: its "Moved most" rows, and whether the Chemistry bar is there. */
function snapshot(page) {
  return page.locator('#office-root .office-snap').evaluate((card) => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const heads = [...card.querySelectorAll('.sub-h')].map(text);
    return {
      heads,
      rows: [...card.querySelectorAll('.msr')].map((row) => ({
        label: text(row.children[0]),
        value: text(row.querySelector('b')),
        chip: !!row.querySelector('.chip'),
        empty: row.classList.contains('msr-empty'),
        color: getComputedStyle(row.children[0]).color,
      })),
      chemistry: text(card.querySelector('.sn-v')),
      text: text(card),
    };
  });
}

test('M: a week where Shooting moved most does not list it', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, officeWith(SHOOTING_FIRST));
  const card = await snapshot(page);
  expect(card.heads).toContain('Moved most');
  // The two of the eight that moved furthest, in the order sent. Nothing on another scale.
  expect(card.rows.map((row) => row.label)).toEqual(['Discipline', 'Fast Break Defense']);
  card.rows.forEach((row) => {
    expect(row.empty).toBe(false);
    expect(row.chip).toBe(true);
  });
  expect(card.text).not.toMatch(/Shooting|Rebounding|Momentum/);
  // Chemistry is not a "Moved most" row; it keeps its own bar at the top of the card.
  expect(card.rows.map((row) => row.label)).not.toContain('Chemistry');
  expect(card.chemistry).toBe('18/25');
});

test('M: a week where only Chemistry, Shooting and Rebounding moved shows the quiet line', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, officeWith(EXCLUDED_ONLY));
  const card = await snapshot(page);
  expect(card.heads).toContain('Moved most');
  expect(card.rows).toHaveLength(1);
  // The line stands alone: no trailing dash (Jamie, 2026-10-02).
  expect(card.rows[0]).toMatchObject({ label: 'No movement this week', value: '', chip: false, empty: true });
  expect(card.text).not.toContain('\u2014');
  expect(card.text).not.toMatch(/Shooting|Rebounding|Momentum/);
  expect(card.chemistry).toBe('18/25');
  // Quiet: dimmer than a row that names a measure, and it does not light up like a link.
  const row = page.locator('#office-root .office-snap .msr-empty');
  await row.hover();
  const hovered = await row.evaluate((node) => {
    const cs = getComputedStyle(node.children[0]);
    return { color: cs.color, line: cs.textDecorationLine };
  });
  expect(hovered.line).toBe('none');
  expect(hovered.color).toBe(card.rows[0].color);
});

test('M: nothing moved at all shows the same quiet line; every one of the eight can be listed', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, officeWith([]));
  const none = await snapshot(page);
  expect(none.rows.map((row) => row.label)).toEqual(['No movement this week']);
  expect(none.rows[0].value).toBe('');

  const eight = [
    ['offensive_efficiency', 'Offense'], ['defensive_efficiency', 'Defense'], ['discipline', 'Discipline'],
    ['fb_efficiency', 'Fast Break'], ['fb_opp_modifier', 'Fast Break Defense'], ['fight', 'Fight'],
    ['pt_opp_modifier', 'P/T Offense'], ['pt_efficiency', 'P/T Defense'],
  ];
  for (let i = 0; i < eight.length; i += 2) {
    await O.openOffice(page, officeWith([
      { measure: eight[i][0], value: 4, delta: 2 },
      { measure: eight[i + 1][0], value: 3, delta: -1 },
    ]));
    expect((await snapshot(page)).rows.map((row) => row.label)).toEqual([eight[i][1], eight[i + 1][1]]);
  }
});

test('M: before camp the line still reads "Set after camp" (from week 2 only; week 1 has no card)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const data = officeWith([]);
  data.office_digest.team_snapshot.state = 'set_after_camp';
  await O.openOffice(page, data);
  const camp = await snapshot(page);
  expect(camp.rows.map((row) => row.label)).toEqual(['Set after camp']);
  expect(camp.rows[0].value).toBe('\u2014'); // unchanged: only "No movement this week" lost its dash
});

for (const [width, height] of SIZES) {
  test('M: shots at ' + width, async ({ page }) => {
    for (const [name, moved] of [['moved-most-shooting-first', SHOOTING_FIRST], ['moved-most-excluded-only', EXCLUDED_ONLY]]) {
      await page.setViewportSize({ width, height });
      await O.openOffice(page, officeWith(moved));
      await page.waitForTimeout(2500); // the arrival
      await page.mouse.move(0, 0);
      await page.screenshot({ path: path.join(SHOTS, name + '-' + TAG + '-' + width + '.png') });
      await page.locator('#office-root .office-snap').screenshot({
        path: path.join(SHOTS, name + '-card-' + TAG + '-' + width + '.png'),
      });
    }
  });
}
