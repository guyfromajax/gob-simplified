// @ts-check
/** Pool · Leans · Visits on the recruiting underline row. */
const { test, expect } = require('@playwright/test');

test.describe.configure({ timeout: 120000 });
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-recruiting-tabs';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/recruiting-tabs');

function recruit(id, name, leans) {
  return {
    recruit_id: id,
    image_id: id,
    name: name,
    archetype: 'Slasher',
    'Home Region': 'C',
    year: 'Junior',
    height: 76,
    weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: leans ? { 1: TID, 2: null, 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function history(rows) {
  return [20, 21, 22, 23, 24, 25, 26].map((week) => {
    const row = rows[week] || {};
    return { week: week, recruit_id: row.id || null, name: row.name || null, lean: row.lean || null };
  });
}

function dataFor(week, extra) {
  const body = Object.assign({
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: week,
    recruits: [recruit('r-lean', 'Ada Lean', true), recruit('r-other', 'Bea Other', false)],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: history({}),
    current_results_week: week === 22 ? 22 : null,
    conferences: { order: [], by_team_id: {} },
  }, extra || {});
  return body;
}

function cc(week, wire) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: Object.assign({ board_saved_week: week, counts: {}, week_35_orders_submitted: week >= 35 }, wire || {}),
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openHub(page, week, extra, wire) {
  const resultsCalls = [];
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, dataFor(week, extra));
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc(week, wire));
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-results')) {
      resultsCalls.push(pathname);
      await fulfillJson(route, { regions: [] });
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/app-config' || pathname === '/teams') {
      await fulfillJson(route, pathname === '/app-config' ? { isAlpha: false, version: '1.0' } : {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await hubReady(page);
  return resultsCalls;
}

// The hub is ready when three things have happened, in any order: recruiting-data
// has painted (the phase strip is the first node renderShell writes), the shell has
// mounted, and the command-center payload has settled browse vs focus (the shell
// drops gob-pending). "Not pending" alone is true before the shell mounts.
async function hubReady(page) {
  await page.waitForSelector('#hub-phase .pstrip');
  await page.waitForFunction(() => {
    const cls = document.documentElement.classList;
    return cls.contains('gob-shell') && !cls.contains('gob-pending');
  });
}

// Leave the hub and come Back to it. The away page must not navigate on its own:
// /login.html redirects a signed-in user to Home Base, and that redirect replaces
// the login entry only if it lands before the load event. When it lands after,
// it adds an entry, Back returns to login, login redirects again, and the hub
// never comes back. about:blank has no script and needs no server.
async function leaveAndComeBack(page) {
  const hubUrl = page.url();
  await page.goto('about:blank');
  await page.goBack();
  await expect(page).toHaveURL(hubUrl);
  await hubReady(page);
  await page.waitForSelector('#hub-pool tbody tr.rec');
}

// The wide-table fade is a mask. It does not change hit testing, so a covered
// "Showing" count still comes back from elementFromPoint. Reject any mask in
// the hub, and require the count's own box to be the hit target.
async function assertHubClear(page) {
  await expect(page.locator('.spine-h')).toHaveCount(0);
  if (await page.locator('#hub-sign').count() === 0) {
    await expect(page.locator('.hub-anchor')).toHaveCount(0);
  }
  const count = page.locator('#hub-pool .pool-fcount');
  if (await count.count()) {
    await count.scrollIntoViewIfNeeded();
    const hit = await page.evaluate(() => {
      const el = document.querySelector('#hub-pool .pool-fcount');
      const rect = el.getBoundingClientRect();
      const x = Math.floor(Math.min(rect.right - 4, window.innerWidth - 2));
      const y = Math.floor(rect.top + rect.height / 2);
      const top = document.elementFromPoint(x, y);
      return {
        ok: top === el || !!(top && el.contains(top)),
        hit: top ? String(top.className || top.tagName) : 'none',
      };
    });
    expect(hit.ok, JSON.stringify(hit)).toBe(true);
    await page.evaluate(() => {
      const main = document.querySelector('.main');
      if (main) main.scrollTop = 0;
    });
  }
  const masked = await page.evaluate(() => {
    const found = [];
    document.querySelectorAll('#hub-root, #hub-root *').forEach((el) => {
      const mask = getComputedStyle(el).webkitMaskImage || getComputedStyle(el).maskImage || 'none';
      if (mask && mask !== 'none') found.push(String(el.className).slice(0, 80));
    });
    return found;
  });
  expect(masked).toEqual([]);
}

function tab(page, label) {
  return page.getByRole('tab', { name: label, exact: true });
}

async function park(page) {
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + Math.min(320, box.width / 2), box.y + Math.min(280, box.height - 24));
}

async function shot(page, name) {
  await park(page);
  await page.screenshot({ path: path.join(OUT, name) });
}

test('invite weeks keep the stack on pool and leans, and visits is the calendar', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 22, {
    visit_history: history({ 20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } } }),
  });
  await expect(tab(page, 'Pool')).toHaveCount(0);
  await expect(tab(page, 'Leans')).toHaveCount(0);
  await expect(tab(page, 'Visits')).toHaveCount(0);
  await expect(page.locator('.pool-view[data-view="leans"]')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('#gob-subtabs .gob-search')).toHaveAttribute('placeholder', 'Search name…');
  await expect(page.locator('#hub-visits .vcal')).toBeVisible();
  await expect(page.locator('#hub-board')).toBeVisible();
  await expect(page.locator('#hub-pool')).toBeVisible();
  await expect(page.locator('.hub-more')).toBeVisible();
  await expect(page.locator('#hub-weekly')).toHaveCount(0);
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(2);

  await page.locator('.pool-view[data-view="leans"]').click();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(1);
  await page.locator('.pool-view[data-view="leans"]').click();
  await expect(page.locator('#hub-visits')).toBeVisible();
  await expect(page.locator('#hub-board')).toBeVisible();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(2);
  await expect(page.locator('#hub-weekly')).toHaveCount(0);
  await assertHubClear(page);
  await shot(page, 'pool-w22-1280.png');

  await page.locator('.pool-view[data-view="leans"]').click();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(1);
  await expect(page.locator('#hub-board')).toBeVisible();
  await assertHubClear(page);
  await shot(page, 'leans-w22-1280.png');

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.locator('.pool-view[data-view="leans"]').click();
  await expect(page.locator('#hub-pool tbody tr.rec')).toHaveCount(2);
  await assertHubClear(page);
  await shot(page, 'pool-w22-1920.png');
  await page.locator('.pool-view[data-view="leans"]').click();
  await assertHubClear(page);
  await shot(page, 'leans-w22-1920.png');
});

function fullPool() {
  const regions = ['A', 'B', 'C', 'D', 'E'];
  const years = ['Senior', 'Junior', 'Sophomore'];
  const archetypes = ['Slasher', 'Sharpshooter', 'Floor General', 'Rim Protector', 'Two-Way Wing'];
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  const names = ['Ada Lean', 'Bea Other', 'Cal Brooks', 'Dev Moreno', 'Eli Hart', 'Finn Walsh', 'Gus Pratt',
    'Hal Ortiz', 'Ike Doyle', 'Jon Reyes', 'Kai Fuller', 'Lou Grant', 'Max Rivera', 'Ned Coles'];
  return names.map((name, i) => Object.assign(recruit('r-' + i, name, i % 3 === 0), {
    'Home Region': regions[i % regions.length],
    year: years[i % years.length],
    archetype: archetypes[i % archetypes.length],
    position_ratings: { [positions[i % positions.length]]: 70 + (i * 3) % 25 },
    Lean: i % 3 === 0 ? { 1: TID, 2: 'rival-1', 3: null }
      : i % 3 === 1 ? { 1: 'rival-1', 2: TID, 3: null } : { 1: 'rival-1', 2: null, 3: null },
  }));
}

test('a processed invite week has no results panel and no gap above the visits', async ({ page }) => {
  const gapUnder = () => page.evaluate(() =>
    document.querySelector('#hub-visits .vcal').getBoundingClientRect().top -
    document.querySelector('#hub-phase').getBoundingClientRect().bottom);
  const invite = (week, processed) => ({
    recruits: fullPool(),
    current_results_week: processed ? week : null,
    new_lean_recruit_ids: processed ? ['r-3'] : [],
    visit_history: history({
      20: { id: 'r-0', name: 'Ada Lean', lean: { 1: TID } },
      21: processed ? { id: 'r-3', name: 'Dev Moreno', lean: { 1: TID } } : undefined,
    }),
  });

  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 22, invite(22, false));
  const baseline = await gapUnder();

  const results = await openHub(page, 21, invite(21, true));
  await expect(tab(page, 'Pool')).toHaveCount(0);
  await expect(tab(page, 'Leans')).toHaveCount(0);
  await page.locator('.pool-view[data-view="leans"]').click();
  await expect(page.locator('.pool-view[data-view="leans"]')).toHaveAttribute('aria-pressed', 'true');
  const strip = page.locator('#hub-phase .pstrip');
  await expect(strip).toContainText('Invite Season');
  await expect(strip).toContainText('Invite 1 recruit per week');
  await expect(strip.locator('.pstrip-counter .n')).toHaveText(/^1\s*\/\s*7$/);
  await expect(strip.locator('.pstrip-counter .cap')).toHaveText('Invites sent');
  await expect(strip.getByRole('button', { name: /Season/ })).toBeVisible();
  await expect(page.locator('#hub-weekly')).toHaveCount(0);
  await expect(page.getByText("This Week's Results")).toHaveCount(0);
  await expect(page.getByText('Visits processed')).toHaveCount(0);
  await expect(page.locator('#hub-visits .vcal')).toBeVisible();
  await expect(page.locator('#hub-board')).toBeVisible();
  await expect(page.locator('#hub-pool')).toBeVisible();
  expect(Math.abs((await gapUnder()) - baseline)).toBeLessThan(0.5);
  await assertHubClear(page);
  await park(page);
  await page.screenshot({ path: path.join(__dirname, '../../reports/recruit-hide-results/leans-w21-1280.png') });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#hub-weekly')).toHaveCount(0);
  await assertHubClear(page);
  await park(page);
  await page.screenshot({ path: path.join(__dirname, '../../reports/recruit-hide-results/leans-w21-1920.png') });

  await expect(page.locator('#hub-weekly')).toHaveCount(0);
  expect(results).toEqual([]);
});

test('passive and tournament visits use the existing calendar tiles', async ({ page }) => {
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 7);
    await tab(page, 'Visits').click();
    await expect(page.locator('.vcal-title')).toHaveText('Invite window opens Week 20');
    await expect(page.locator('#hub-visits .vwk.is-upcoming')).toHaveCount(7);
    await expect(page.locator('#hub-pool')).toHaveCount(0);
    await assertHubClear(page);
    await shot(page, 'visits-w7-' + size[2] + '.png');
  }

  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 30, {
      visit_history: history({
        20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: TID } },
        21: { id: 'r-other', name: 'Bea Other', lean: { 1: 'rival-1' } },
      }),
    });
    await tab(page, 'Visits').click();
    await expect(page.locator('.vcal-title')).toHaveText('Invite Visits');
    await expect(page.locator('#hub-visits .vwk.is-filled')).toHaveCount(2);
    await expect(page.locator('#hub-visits .vwk.is-missed')).toHaveCount(5);
    await expect(page.locator('#hub-pool')).toHaveCount(0);
    await assertHubClear(page);
    await shot(page, 'visits-w30-' + size[2] + '.png');
  }
});

test('signing day and results hide the tab row', async ({ page }) => {
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 35);
    await expect(page.locator('#hub-sign')).toBeVisible();
    await expect(page.locator('#gob-subtabs')).toBeHidden();
    await expect(page.locator('#gob-subtabs .gob-search')).toHaveCount(0);
    await assertHubClear(page);
    await shot(page, 'signing-w35-' + size[2] + '.png');
  }
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 36);
    await expect(page.locator('#hub-signings')).toBeVisible();
    await expect(page.locator('#gob-subtabs')).toBeHidden();
    await assertHubClear(page);
    await shot(page, 'results-w36-' + size[2] + '.png');
  }
});

test('pool grid matches the roster tiles and the league content edge', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 3);
  const hub = await page.evaluate(() => {
    const phase = document.querySelector('#hub-phase .pstrip');
    const hair = document.querySelector('.pg-head');
    const row = document.querySelector('#hub-pool tbody tr.rec');
    const link = row.querySelector('.recruit-name-link');
    const av = row.querySelector('.pc-av');
    const gap = phase.getBoundingClientRect().top - hair.getBoundingClientRect().bottom;
    const dsp = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dsp-8'));
    const headPad = parseFloat(getComputedStyle(hair).paddingBottom);
    const main = document.querySelector('html.gob-shell .main');
    const mainCs = getComputedStyle(main);
    const contentRight = main.getBoundingClientRect().right - (parseFloat(mainCs.paddingRight) || 0);
    const sc = document.querySelector('#hub-pool .pool-scroll');
    const head = document.querySelector('#hub-pool thead tr.gob-groups th');
    const lean = row.querySelector('td.lean-col');
    return {
      left: phase.getBoundingClientRect().left,
      gap,
      dsp,
      headPad,
      tiles: row.querySelectorAll('.attr-tile').length,
      labels: row.querySelectorAll('.attr-tile u').length,
      orange: getComputedStyle(link).color === 'rgb(247, 148, 32)',
      rt: row.querySelector('.rtl').textContent,
      portrait: !!(av.querySelector('img') || av.textContent.trim()),
      leanInside: lean.getBoundingClientRect().right <= contentRight + 1,
      overflow: sc.scrollWidth - sc.clientWidth,
      wide: sc.classList.contains('gob-wide-wrap'),
      headTop: getComputedStyle(head).top,
      stickTop: getComputedStyle(document.documentElement).getPropertyValue('--gob-stick-top').trim(),
      backdrop: getComputedStyle(head).backdropFilter,
    };
  });
  expect(Math.abs(hub.headPad - hub.dsp)).toBeLessThan(0.6);
  expect(hub.gap).toBeLessThan(1.5);
  expect(hub.tiles).toBe(12);
  expect(hub.labels).toBe(0);
  expect(hub.orange).toBe(false);
  expect(hub.rt).toMatch(/[A-F]/);
  expect(hub.portrait).toBe(true);
  expect(hub.leanInside).toBe(true);
  expect(hub.overflow).toBeLessThanOrEqual(1);
  expect(hub.wide).toBe(false);
  expect(hub.headTop).toBe(hub.stickTop);
  expect(hub.backdrop).toBe('none');

  await page.goto('/standings.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  const leagueLeft = await page.evaluate(() => {
    const main = document.querySelector('.main');
    const head = document.querySelector('.pg-head');
    if (!main || !head) return null;
    const headBottom = head.getBoundingClientRect().bottom;
    let best = null;
    main.querySelectorAll('*').forEach((el) => {
      if (head.contains(el)) return;
      const r = el.getBoundingClientRect();
      if (r.width < 200 || r.height < 12 || r.top < headBottom - 1) return;
      if (!best || r.top < best.top - 1) best = r;
    });
    return best ? best.left : null;
  });
  expect(leagueLeft).not.toBeNull();
  expect(Math.abs(leagueLeft - hub.left)).toBeLessThan(1.5);
});

// fullPool(): 14 recruits over regions A-E. The user is first or second in the lean of
// r-0/1/3/4/6/7/9/10/12/13. Region C (his) holds r-2, r-7 and r-12; r-7 and r-12 lean to him.
const LEANS_OUT = path.join(__dirname, '../../reports/recruit-leans-toggle');
const leansBtn = (page) => page.locator('#hub-pool .pool-view[data-view="leans"]');
const poolIds = (page) => page.locator('#hub-pool tbody tr.rec').evaluateAll((rows) =>
  rows.map((row) => row.dataset.recId).sort());
const fcount = (page) => page.locator('#hub-pool .pool-fcount').innerText();

async function showPoolBar(page) {
  await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const bar = document.querySelector('#hub-pool .pool-fbar');
    main.scrollTop += bar.getBoundingClientRect().top - main.getBoundingClientRect().top - 12;
  });
  await page.mouse.move(4, 4);
}

test('week 21 focus flow lands on the region pool, and Leans toggles to leaners and back', async ({ page }) => {
  const fs = require('fs');
  fs.mkdirSync(LEANS_OUT, { recursive: true });
  for (const size of [[1280, 720], [1920, 1080]]) {
    const tag = size[0] + 'x' + size[1];
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openHub(page, 21, { recruits: fullPool() }, { board_saved_week: 0 });
    await expect(page.locator('html.gob-focus')).toHaveCount(1);
    await expect(page.locator('#gob-subtabs [role="tab"]:visible')).toHaveCount(0);
    await expect(page.locator('#hub-board')).toBeVisible();
    const views = await page.locator('#hub-pool .pool-view').evaluateAll((b) => b.map((x) => x.dataset.view));
    expect(views).toEqual(['leans', 'watch', 'unranked']);
    await expect(page.locator('#pool-region')).toHaveValue('C');
    await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');
    await expect(leansBtn(page).locator('.n')).toHaveText('10');
    expect(await poolIds(page)).toEqual(['r-12', 'r-2', 'r-7']);
    expect(await fcount(page)).toMatch(/Showing\s*3\s*of 14$/);
    await showPoolBar(page);
    await page.screenshot({ path: path.join(LEANS_OUT, 'focus-w21-default-' + tag + '.png') });

    await leansBtn(page).click();
    await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
    await expect(leansBtn(page)).toHaveClass(/is-on/);
    expect(await poolIds(page)).toEqual(['r-12', 'r-7']);
    expect(await fcount(page)).toMatch(/Showing\s*2\s*of 14$/);

    await page.selectOption('#pool-region', 'all');
    expect((await poolIds(page)).length).toBe(10);
    await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
    await showPoolBar(page);
    await page.screenshot({ path: path.join(LEANS_OUT, 'focus-w21-leans-' + tag + '.png') });

    // One view at a time: Watchlist turns Leans off, and Leans turns Watchlist off.
    await page.locator('#hub-pool .pool-view[data-view="watch"]').click();
    await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');
    await leansBtn(page).click();
    await expect(page.locator('#hub-pool .pool-view[data-view="watch"]')).toHaveAttribute('aria-pressed', 'false');
    expect((await poolIds(page)).length).toBe(10);

    await leansBtn(page).click();
    await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');
    expect((await poolIds(page)).length).toBe(14);
    expect(await fcount(page)).toMatch(/Showing\s*14\s*of 14 · no filters$/);
  }

  // Back/forward restore keeps the toggle and the filters.
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 21, { recruits: fullPool() }, { board_saved_week: 0 });
  await page.selectOption('#pool-region', 'all');
  await leansBtn(page).click();
  await leaveAndComeBack(page);
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#pool-region')).toHaveValue('all');
  expect((await poolIds(page)).length).toBe(10);

  // A fresh visit (not back/forward) lands on the default again.
  await openHub(page, 21, { recruits: fullPool() }, { board_saved_week: 0 });
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('#pool-region')).toHaveValue('C');

});

test('browse hub keeps the Leans tab and the Leans toggle in sync', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 7, { recruits: fullPool() });
  await expect(tab(page, 'Leans')).toHaveAttribute('aria-selected', 'true');
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
  await page.selectOption('#pool-region', 'C');
  expect(page.url()).toContain('hub=leans');
  expect(await poolIds(page)).toEqual(['r-12', 'r-7']);

  await tab(page, 'Pool').click();
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');
  expect(page.url()).toContain('hub=pool');
  expect((await poolIds(page)).length).toBe(3);

  await page.locator('#hub-pool .pool-view[data-view="watch"]').click();
  await tab(page, 'Leans').click();
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#hub-pool .pool-view[data-view="watch"]')).toHaveAttribute('aria-pressed', 'false');
  expect(await poolIds(page)).toEqual(['r-12', 'r-7']);

  await page.locator('#hub-pool .pool-view[data-view="unranked"]').click();
  await expect(tab(page, 'Pool')).toHaveAttribute('aria-selected', 'true');
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'false');

  await leansBtn(page).click();
  await leansBtn(page).click();
  await expect(tab(page, 'Pool')).toHaveAttribute('aria-selected', 'true');
  expect(page.url()).toContain('hub=pool');

  await tab(page, 'Leans').click();
  await leaveAndComeBack(page);
  await expect(tab(page, 'Leans')).toHaveAttribute('aria-selected', 'true');
  await expect(leansBtn(page)).toHaveAttribute('aria-pressed', 'true');
  expect(await poolIds(page)).toEqual(['r-12', 'r-7']);
});

test('focus mode still hides the head during an unsaved invite week', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, 22, {}, { board_saved_week: 0 });
  await expect(page.locator('html.gob-shell.gob-focus .pg-head')).toBeHidden();
  await expect(page.locator('#hub-board')).toBeVisible();
});
