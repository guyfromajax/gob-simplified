// @ts-check
/** Week 36 signing results — browse-template layout inside GOB shell. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/recruit-results-week');
const FID = 'f-e2e-recruit-results-week';
const USER = 'user-team-id';

const regionOf = (c) => String.fromCharCode(65 + Math.floor((Number(c) - 1) / 2));

function withRegions(conferences, userTeamId) {
  const byTeam = conferences.by_team_id || {};
  const regionByTeam = {};
  Object.keys(byTeam).forEach((tid) => { regionByTeam[tid] = regionOf(byTeam[tid]); });
  const userRegion = regionByTeam[String(userTeamId)] || null;
  return Object.assign({}, conferences, {
    user_region: userRegion,
    region_by_team_id: regionByTeam,
    region_team_ids: Object.keys(regionByTeam).filter((tid) => regionByTeam[tid] === userRegion).sort(),
  });
}

/** Six conferences with signings for screenshot + order checks. */
function fixtureLeague() {
  const byTeam = { [USER]: 9 };
  for (let i = 1; i <= 7; i += 1) byTeam[`c9-${i}`] = 9;
  for (let i = 1; i <= 4; i += 1) byTeam[`c10-${i}`] = 10;
  for (let c of [1, 2, 3, 4, 5, 6]) {
    byTeam[`c${c}-a`] = c;
    byTeam[`c${c}-b`] = c;
  }
  const teamNames = { [USER]: 'South Lancaster' };
  Object.keys(byTeam).forEach((tid) => {
    if (!teamNames[tid]) teamNames[tid] = 'Team ' + tid;
  });
  const signed = [];
  const YEARS = ['JH', 'Freshman', 'Sophomore', 'Junior'];
  let rt = 92;
  for (let i = 0; i < 5; i += 1) {
    signed.push({
      player_id: `p-u${i}`, image_id: `img-u${i}`, recruit_id: `r-u${i}`,
      name: `Lancaster ${i}`, pos: 'SF', rt: rt--, potential_rt_ratcheted: rt + 2,
      year: YEARS[i % 4], team_id: USER, team_name: 'South Lancaster',
    });
  }
  Object.keys(byTeam).forEach((tid, idx) => {
    if (tid === USER) return;
    signed.push({
      player_id: `p-${idx}`, recruit_id: `r-${idx}`, name: `Sign ${idx}`, pos: 'PG',
      rt: 70 + (idx % 20), potential_rt_ratcheted: 80 + (idx % 15), year: 'Junior',
      team_id: tid, team_name: teamNames[tid],
    });
  });
  const conferences = withRegions({
    user_conference: 9,
    sister_conference: 10,
    order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
    by_team_id: byTeam,
  }, USER);
  return { signed, conferences, teamNames };
}

function recruitingPayload() {
  const { signed, conferences, teamNames } = fixtureLeague();
  return {
    team: 'South Lancaster', team_id: USER, team_region: 'A', week: 36, season: 3,
    recruits: [],
    team_name_map: teamNames,
    saved_orders: {}, watchlist: [], saved_order_entries_week_35: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: { signed_players: signed },
    week_35_recruiting_ran: true,
    week_35_reveal_seen: true,
    conferences,
  };
}

function commandCenterPayload() {
  return {
    franchise_id: FID,
    team_id: USER,
    user_team_id: USER,
    team: 'South Lancaster',
    week: 36,
    rank: 14,
    season: 3,
    current_season: 3,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 36, counts: {}, week_35_orders_submitted: true },
    user_conference: 9,
    user_region: 'A',
    team_record: { wins: 4, losses: 1 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openWeek36Results(page) {
  const seenCalls = [];
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, recruitingPayload());
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, commandCenterPayload());
      return;
    }
    if (pathname.includes('week-36-results-seen')) {
      seenCalls.push(pathname);
      await fulfillJson(route, {});
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/app-config' || pathname === '/teams') {
      await fulfillJson(route, pathname === '/app-config' ? { isAlpha: false, version: '1.0' } : {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + USER);
  await page.waitForSelector('#hub-signings .gob-rec-results', { timeout: 15000 });
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  await page.waitForSelector('html.gob-shell .rail', { timeout: 15000 });
  return seenCalls;
}

async function assertBrowseChrome(page) {
  const tcard = page.locator('#hub-signings .gob-tcard').first();
  await expect(tcard).toBeVisible();
  const cardPaint = await tcard.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      bg: cs.backgroundColor,
      borderWidth: parseFloat(cs.borderTopWidth) || 0,
      borderAlpha: cs.borderTopColor,
    };
  });
  expect(cardPaint.borderWidth).toBeGreaterThan(0);
  expect(cardPaint.bg).not.toMatch(/^rgba\(0,\s*0,\s*0,\s*0\)$/);

  const rtHeader = page.locator('#hub-signings .gob-rec-your-class thead th').filter({ hasText: 'RT' });
  await expect(rtHeader).toBeVisible();
  const headerFont = await rtHeader.evaluate((el) => getComputedStyle(el).fontFamily.toLowerCase());
  expect(headerFont).toMatch(/bebas/);

  const countGap = await page.locator('#hub-signings .gob-rec-your-class h2 em').evaluate((el) => {
    return parseFloat(getComputedStyle(el).marginLeft) || 0;
  });
  expect(countGap).toBeGreaterThan(4);

  const rtYour = page.locator('#hub-signings .gob-rec-your-class tbody td.rt').first();
  await expect(rtYour).toBeVisible();
  const rtLeague = page.locator('#hub-signings .gob-rec-league td.rt').first();
  await expect(rtLeague).toBeVisible();

  await expect(page.locator('html.gob-shell .top')).toBeVisible();
  await expect(page.locator('html.gob-shell .rail')).toBeVisible();
}

/** RT must sit inside the card; compact tables must not scroll horizontally. */
async function assertTableFitsCard(page, cardSel, wrapSel) {
  const geom = await page.evaluate(({ cardSel: cSel, wrapSel: wSel }) => {
    const card = document.querySelector(cSel);
    const wrap = document.querySelector(wSel);
    const rt = wrap && wrap.querySelector('td.rt');
    if (!card || !wrap || !rt) return { ok: false, reason: 'missing nodes' };
    const cr = card.getBoundingClientRect();
    const rr = rt.getBoundingClientRect();
    const rtInside = rr.left >= cr.left - 1 && rr.right <= cr.right + 1
      && rr.top >= cr.top - 1 && rr.bottom <= cr.bottom + 1;
    const noHScroll = wrap.scrollWidth <= wrap.clientWidth + 1;
    const noMask = !wrap.classList.contains('can-r') && !wrap.classList.contains('can-l');
    return { ok: rtInside && noHScroll, rtInside, noHScroll, noMask, scrollW: wrap.scrollWidth, clientW: wrap.clientWidth };
  }, { cardSel, wrapSel });
  expect(geom.ok, JSON.stringify(geom)).toBe(true);
}

test.describe('week 36 signing results browse layout', () => {
  test('your class first, conference order, navy rows, seen PATCH once, styled tables', async ({ page }) => {
    const seenCalls = await openWeek36Results(page);
    await assertBrowseChrome(page);

    await assertTableFitsCard(
      page,
      '#hub-signings .gob-rec-your-class',
      '#hub-signings .gob-rec-your-class .gob-rec-class',
    );
    await assertTableFitsCard(
      page,
      '#hub-signings .gob-rec-conf',
      '#hub-signings .gob-rec-conf .gob-rec-league',
    );

    const layout = await page.evaluate(() => {
      const root = document.querySelector('#hub-signings .gob-rec-results');
      const kids = [...root.children].map((el) => el.className);
      const confTitles = [...document.querySelectorAll('#hub-signings .gob-rec-conf h2')].map((h) => h.textContent.trim());
      const navy = document.querySelectorAll('#hub-signings .gob-rec-league tr.me').length;
      const yourHeaders = [...document.querySelectorAll('#hub-signings .gob-rec-your-class thead th')].map((th) => th.textContent.trim());
      const leagueThead = document.querySelectorAll('#hub-signings .gob-rec-league thead').length;
      const lead = document.querySelector('#hub-signings .gob-rec-lead');
      return { kids, confTitles, navy, yourHeaders, leagueThead, lead: !!lead };
    });
    expect(layout.lead).toBe(false);
    expect(layout.kids[0]).toContain('gob-rec-your-class');
    const classIdx = layout.kids.findIndex((c) => c.includes('gob-rec-your-class'));
    const gridIdx = layout.kids.findIndex((c) => c.includes('gob-rec-conf-grid'));
    expect(classIdx).toBeGreaterThan(-1);
    expect(gridIdx).toBeGreaterThan(classIdx);
    expect(layout.confTitles[0]).toBe('Conference E9');
    expect(layout.confTitles[1]).toBe('Conference E10');
    expect(layout.confTitles[2]).toBe('Conference A1');
    expect(layout.yourHeaders).toEqual(['', 'Name', 'Pos', 'Yr', 'RT']);
    expect(layout.leagueThead).toBe(0);
    expect(layout.navy).toBeGreaterThan(0);
    expect(seenCalls.length).toBe(1);
    await expect(page.locator('#hub-signings .gob-rec-player-link').first()).toHaveAttribute('href', /player-view/);
    await expect(page.locator('#hub-signings .gob-rec-your-class h2 em')).toHaveText('5');
  });

  test('screenshots at 1280 and 1920 with shell', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });
    for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await openWeek36Results(page);
      await assertBrowseChrome(page);
      await page.screenshot({ path: path.join(OUT, `results-w36-${size[2]}.png`) });
    }
  });
});
