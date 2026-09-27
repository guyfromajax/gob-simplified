const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-subtabs';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/subtabs-underline');

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 3,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 3, counts: {} },
    user_conference: 1,
    user_region: 'A',
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, {
        standings: [{ team_id: TID, name: 'Lancaster', display_name: 'Lancaster', W: 2, L: 0, conference: 1, region: 'A', pct: 1, PF: 80, PA: 70, differential: 10, streak: 'W2', natl_rank: 4 }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-stats') || pathname.startsWith('/franchise/leaders')) {
      await fulfillJson(route, { teams: [], leaders: [] });
      return;
    }
    await fulfillJson(route, {});
  });
}

const routed = new WeakSet();

async function openFcc(page, search) {
  await stubAuth(page);
  if (!routed.has(page)) {
    routed.add(page);
    await installApi(page);
  }
  await page.goto('/franchise-command-center.html' + (search || ('?franchise_id=' + FID + '&team_id=' + TID)));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function settle(page) {
  await page.evaluate(() => new Promise(function (resolve) {
    requestAnimationFrame(function () { requestAnimationFrame(resolve); });
  }));
}

async function park(page) {
  const box = await page.locator('html.gob-shell .main').boundingBox();
  if (box) await page.mouse.move(box.x + Math.min(320, box.width / 2), box.y + Math.min(280, box.height - 24));
}

function tab(page, label) {
  return page.getByRole('tab', { name: label, exact: true });
}

async function inkBox(page) {
  return page.evaluate(() => {
    const ink = document.querySelector('#gob-subtabs .ink');
    const selected = document.querySelector('#gob-subtabs .tabs > .tb[aria-selected="true"]');
    if (!ink || !selected) return null;
    const ib = ink.getBoundingClientRect();
    const tb = selected.getBoundingClientRect();
    return {
      dx: Math.abs(ib.left - tb.left),
      dw: Math.abs(ib.width - tb.width),
      width: ib.width,
    };
  });
}

async function rowState(page) {
  return page.evaluate(() => {
    const row = document.getElementById('gob-subtabs');
    const search = row.querySelector('.gob-search');
    const folded = Array.from(row.querySelectorAll('.tabs > .tb.ovf .tb-l')).map((el) => el.textContent);
    const selected = row.querySelector('.tabs > .tb[aria-selected="true"] .tb-l');
    return {
      searchCollapsed: !!(search && search.classList.contains('is-collapsed')),
      searchShown: !!(search && getComputedStyle(search).display !== 'none'),
      more: !!row.querySelector('.more-w.show'),
      folded: folded,
      selected: selected ? selected.textContent : '',
      selectedFolded: !!(selected && selected.closest('.tb').classList.contains('ovf')),
    };
  });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('switching, ink, overflow, keyboard, lock, and search', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await page.locator('[data-gob-section="league"]').click();
  await expect(page.locator('#standings-view.tab-content.active')).toBeVisible();
  await expect(tab(page, 'Standings')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#gob-subtabs .tabs')).toHaveAttribute('aria-label', 'League sections');

  await tab(page, 'Rankings').click();
  await expect(page.locator('#rankings-view.tab-content.active')).toBeVisible();
  await expect(tab(page, 'Rankings')).toHaveAttribute('aria-selected', 'true');
  await expect(tab(page, 'Standings')).toHaveAttribute('aria-selected', 'false');
  await expect.poll(async () => {
    const box = await inkBox(page);
    return box ? Math.max(box.dx, box.dw) : 999;
  }).toBeLessThan(1.5);
  expect((await inkBox(page)).width).toBeGreaterThan(10);

  await tab(page, 'Standings').focus();
  await page.keyboard.press('ArrowRight');
  await expect(tab(page, 'Rankings')).toBeFocused();
  await expect(tab(page, 'Rankings')).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('Home');
  await expect(tab(page, 'Standings')).toBeFocused();
  await expect(tab(page, 'Standings')).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('End');
  await expect(tab(page, 'Tournament')).toBeFocused();
  await expect(tab(page, 'Standings')).toHaveAttribute('aria-selected', 'true');
  await expect(tab(page, 'Tournament')).toHaveAttribute('aria-disabled', 'true');
  await expect(tab(page, 'Tournament').locator('.ltip')).toBeVisible();
  await expect(tab(page, 'Tournament')).not.toHaveAttribute('title');
  const opens = await page.evaluate(() => {
    for (let w = 1; w <= 40; w += 1) {
      if (window.GOBTierEmblem && window.GOBTierEmblem.tierForWeek(w)) return w;
    }
    return 0;
  });
  expect(opens).toBeGreaterThan(0);
  await expect(tab(page, 'Tournament').locator('.ltip b')).toHaveText('Opens Week ' + opens);
  await page.keyboard.press('Enter');
  await expect(page.locator('#standings-view.tab-content.active')).toBeVisible();

  const standings = await rowState(page);
  expect(standings.more).toBe(false);
  expect(standings.folded).toEqual([]);
  expect(standings.searchCollapsed).toBe(false);
  expect(standings.selectedFolded).toBe(false);

  await tab(page, 'Team Stats').click();
  await expect(page.locator('#team-stats-view.tab-content.active')).toBeVisible();
  const stats = await rowState(page);
  expect(stats.more).toBe(false);
  expect(stats.selected).toBe('Team Stats');
  expect(stats.selectedFolded).toBe(false);
  // Production Team Stats has a search and no second segment, so 1280 still fits.
  expect(stats.searchCollapsed).toBe(false);

  const ladder = [];
  for (const width of [1100, 1000, 920, 840, 760, 680]) {
    await page.setViewportSize({ width: width, height: 720 });
    await settle(page);
    ladder.push(Object.assign({ width: width }, await rowState(page)));
  }
  const searchOnly = ladder.find(function (state) { return state.searchCollapsed && !state.more; });
  const folded = ladder.find(function (state) { return state.more && !state.selectedFolded; });
  expect(searchOnly, JSON.stringify(ladder)).toBeTruthy();
  expect(folded, JSON.stringify(ladder)).toBeTruthy();
  expect(searchOnly.width).toBeGreaterThan(folded.width);
  await page.setViewportSize({ width: searchOnly.width, height: 720 });
  await settle(page);
  await expect(page.locator('#gob-subtabs .sbtn.show')).toBeVisible();

  await page.keyboard.press('/');
  await expect(page.locator('#gob-subtabs .gob-search')).toBeFocused();
  const expanded = await rowState(page);
  expect(expanded.searchCollapsed).toBe(false);
  await page.keyboard.type('Lancaster');
  await page.keyboard.press('Escape');
  await expect(page.locator('#gob-subtabs .gob-search')).toHaveValue('');
  await expect(page.locator('#gob-subtabs .gob-search')).not.toBeFocused();

  await page.setViewportSize({ width: folded.width, height: 720 });
  await settle(page);
  await expect(page.locator('#gob-subtabs .more-w.show')).toBeVisible();
  const narrow = await rowState(page);
  expect(narrow.more).toBe(true);
  expect(narrow.folded.length).toBeGreaterThan(0);
  expect(narrow.selectedFolded).toBe(false);
  expect(narrow.folded).not.toContain('Team Stats');
  await page.locator('#gob-subtabs .more').click();
  await expect(page.locator('#gob-subtabs .mmenu.open')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#gob-subtabs .mmenu.open')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs .more')).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('#gob-subtabs .mmenu.open .mi').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#gob-subtabs .more')).toBeFocused();
});

test('section shots, locked tooltip, more menu, and a detail view', async ({ page }) => {
  const sections = [
    ['team', 'Roster', 'team-roster'],
    ['prep', 'Training', 'prep-training'],
    ['league', 'Standings', 'league-standings'],
    ['league', 'Team Stats', 'league-team-stats'],
    ['news', 'News', 'news'],
  ];
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page);
    for (const row of sections) {
      await page.locator('[data-gob-section="' + row[0] + '"]').click();
      await tab(page, row[1]).click();
      await park(page);
      await page.screenshot({ path: path.join(OUT, 'fixture-' + row[2] + '-' + size[2] + '.png') });
    }
    await page.locator('[data-gob-section="league"]').click();
    await tab(page, 'Tournament').focus();
    await expect(tab(page, 'Tournament').locator('.ltip')).toBeVisible();
    await park(page);
    await tab(page, 'Tournament').hover();
    await page.screenshot({ path: path.join(OUT, 'fixture-tournament-lock-' + size[2] + '.png') });
  }

  await page.setViewportSize({ width: 680, height: 720 });
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-stats-view');
  await settle(page);
  await expect(page.locator('#gob-subtabs .more-w.show')).toBeVisible();
  await page.locator('#gob-subtabs .more').click();
  await expect(page.locator('#gob-subtabs .mmenu.open')).toBeVisible();
  await park(page);
  await page.screenshot({ path: path.join(OUT, 'fixture-more-680.png') });

  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&origin=team&return_tab=roster-view&player_id=p1');
  await expect(page.locator('#player-view .gob-dt-bar')).toBeVisible();
  await expect(tab(page, 'Roster')).toHaveAttribute('aria-selected', 'true');
  const air = await page.evaluate(() => {
    const row = document.querySelector('#gob-subtabs');
    const bar = document.querySelector('#player-view .gob-dt-bar');
    const cs = getComputedStyle(bar);
    return {
      gap: bar.getBoundingClientRect().top - row.getBoundingClientRect().bottom,
      position: cs.position,
    };
  });
  expect(air.position).toBe('static');
  expect(air.gap).toBeGreaterThan(6);
  expect(air.gap).toBeLessThan(12);
  await park(page);
  await page.screenshot({ path: path.join(OUT, 'fixture-player-detail-1280.png') });

  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&origin=team&player_id=p1');
  await expect(page.locator('#gob-subtabs .tb[aria-selected="true"]')).toHaveCount(0);
  const bare = await inkBox(page);
  expect(bare).toBeNull();

  await page.locator('[data-gob-section="recruiting"]').click();
  await page.waitForURL(/recruiting\.html/);
  await expect(page.locator('#gob-subtabs .tb')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs')).toBeHidden();
});

test('unselected link tabs have no stray underline', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  const sections = ['team', 'prep', 'league', 'news'];
  let links = 0;
  for (const section of sections) {
    await page.locator('[data-gob-section="' + section + '"]').click();
    await settle(page);
    await park(page);
    const rows = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#gob-subtabs .tabs > .tb')).filter(function (el) {
        return !el.classList.contains('more');
      }).map(function (el) {
        const cs = getComputedStyle(el);
        const after = getComputedStyle(el, '::after');
        return {
          tag: el.tagName,
          label: (el.querySelector('.tb-l') || {}).textContent || '',
          selected: el.getAttribute('aria-selected'),
          decoration: cs.textDecorationLine,
          border: [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth].join(' '),
          shadow: cs.boxShadow,
          after: after.content,
          hovered: el.matches(':hover'),
        };
      });
    });
    expect(rows.length, section).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.decoration, section + ' ' + row.label).toBe('none');
      expect(row.border, section + ' ' + row.label).toBe('0px 0px 0px 0px');
      expect(row.hovered, section + ' ' + row.label).toBe(false);
      if (row.selected !== 'true') expect(row.after, section + ' ' + row.label).toBe('none');
      if (!row.hovered) expect(row.shadow, section + ' ' + row.label).toBe('none');
      if (row.tag === 'A' && row.selected !== 'true') links += 1;
    }
  }
  expect(links).toBeGreaterThan(0);

  await page.locator('[data-gob-section="league"]').click();
  await tab(page, 'Schedule').hover();
  const preview = await tab(page, 'Schedule').evaluate((el) => getComputedStyle(el, '::after').content);
  expect(preview).not.toBe('none');
  await park(page);
  const resting = await tab(page, 'Schedule').evaluate((el) => ({
    decoration: getComputedStyle(el).textDecorationLine,
    after: getComputedStyle(el, '::after').content,
    hovered: el.matches(':hover'),
  }));
  expect(resting.hovered).toBe(false);
  expect(resting.decoration).toBe('none');
  expect(resting.after).toBe('none');
});
