const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-shell1b';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/shell-1b');

function cc(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 1,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 1, counts: {} },
    user_conference: 1,
    user_region: 'A',
  }, overrides || {});
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, data) {
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
      await fulfillJson(route, data);
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, {
        standings: [{ team_id: TID, name: 'Lancaster', W: 16, L: 5, conference: 1, region: 'A' }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data') || pathname.startsWith('/roster/')) {
      await fulfillJson(route, { team_attributes: { team_chemistry: 10 }, players: [] });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, data) {
  await stubAuth(page);
  await installApi(page, data);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
  await page.waitForSelector('#gob-top-id[aria-label="Lancaster"]');
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

function stab(page, label) {
  return page.locator('#gob-subtabs .stab').filter({ hasText: new RegExp('^' + label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') });
}

function assertRailMonotonic(samples) {
  const start = samples[0];
  const end = Math.max.apply(null, samples);
  expect(start).toBeLessThan(80);
  expect(end).toBeGreaterThan(190);
  let rising = false;
  for (let i = 1; i < samples.length; i++) {
    const prev = samples[i - 1];
    const cur = samples[i];
    expect(cur + 0.75, 'width decreased at sample ' + i).toBeGreaterThanOrEqual(prev);
    if (!rising) {
      if (cur > start + 1.5) rising = true;
      continue;
    }
    if (cur >= end - 1) continue;
    if (cur < end - 2 && Math.abs(cur - prev) < 0.35) {
      throw new Error('plateau at ' + cur + ' between ' + start + ' and ' + end);
    }
  }
  expect(rising).toBe(true);
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('top bar logo, name, and national rank at both sizes', async ({ page }) => {
  await openFcc(page, cc());
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(100);
    const metrics = await page.evaluate(() => {
      const logo = document.getElementById('team-logo');
      const topH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--top-h'));
      const box = logo.getBoundingClientRect();
      return {
        topH,
        logoH: box.height,
        logoW: box.width,
        alt: logo.alt,
        title: logo.title,
        label: document.getElementById('gob-top-id').getAttribute('aria-label'),
        visibleText: document.getElementById('gob-top-id').innerText.trim(),
        rank: document.querySelector('#gob-rank-stat span').textContent,
      };
    });
    expect(Math.abs(metrics.logoH - metrics.topH * 0.72)).toBeLessThan(1.5);
    expect(metrics.logoW).toBeGreaterThan(0);
    expect(metrics.alt).toBe('Lancaster');
    expect(metrics.title).toBe('Lancaster');
    expect(metrics.label).toBe('Lancaster');
    expect(metrics.visibleText).toBe('');
    expect(metrics.rank).toBe('National Rank');
    await page.mouse.move(size[0] / 2, size[1] / 2);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'top-bar-' + size[2] + '.png') });
  }
});

test('rail expansion is one monotonic width and does not move main', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  const rail = await page.locator('.rail').boundingBox();
  const before = await page.locator('.main').boundingBox();
  await page.mouse.move(400, 360);
  await page.mouse.move(rail.x + 20, rail.y + 90);
  const sampled = await page.evaluate(async () => {
    const face = document.querySelector('.rail-face');
    const main = document.querySelector('.main');
    const widths = [];
    const mains = [];
    const t0 = performance.now();
    while (performance.now() - t0 < 900) {
      widths.push(Math.round(face.getBoundingClientRect().width * 100) / 100);
      const r = main.getBoundingClientRect();
      mains.push([Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]);
      await new Promise((resolve) => setTimeout(resolve, 16));
    }
    return { widths, mains };
  });
  assertRailMonotonic(sampled.widths);
  const main0 = sampled.mains[0];
  sampled.mains.forEach((box) => {
    expect(box).toEqual(main0);
  });
  expect(Math.round(before.x)).toBe(main0[0]);
  expect(Math.round(before.width)).toBe(main0[2]);
  await page.screenshot({ path: path.join(OUT, 'rail-expanded-1280.png') });
  await page.mouse.move(400, 360);
  await page.waitForTimeout(400);
  const collapsed = await page.locator('.rail-face').evaluate((el) => el.getBoundingClientRect().width);
  expect(collapsed).toBeLessThan(80);
  const labels = await page.evaluate(() => {
    const face = document.querySelector('.rail-face');
    const railRight = face.getBoundingClientRect().right;
    return Array.from(document.querySelectorAll('.rail-l')).map((el) => {
      const box = el.getBoundingClientRect();
      return {
        text: el.textContent,
        opacity: getComputedStyle(el).opacity,
        right: box.right,
        railRight,
      };
    });
  });
  expect(labels.length).toBeGreaterThan(6);
  for (const label of labels) {
    expect(Number(label.opacity), label.text).toBe(0);
    expect(label.right, label.text).toBeLessThanOrEqual(label.railRight + 0.5);
  }

  await page.locator('[data-gob-section="office"]').focus();
  await page.keyboard.press('Tab');
  await page.waitForFunction(() => {
    const el = document.activeElement;
    return !!(el && el.closest && el.closest('.rail'));
  });
  await page.waitForTimeout(700);
  const focusedWidth = await page.locator('.rail-face').evaluate((el) => el.getBoundingClientRect().width);
  expect(focusedWidth).toBeGreaterThan(190);
});

test('section map opens the right panel or the existing page', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc({ week: 1 }));
  const panels = [
    ['team', 'Roster', 'roster-tab'],
    ['team', 'Player Stats', 'player-stats-tab'],
    ['team', 'Team Attributes', 'team-stats-tab'],
    ['team', 'Schedule', 'schedule-tab'],
    ['prep', 'Training', 'training-tab'],
    ['prep', 'Game Plan', 'game-plan-tab'],
    ['prep', 'Playbooks', 'playbooks-tab'],
    ['prep', 'Scouting Report', 'coaches-tab'],
    ['league', 'Standings', 'standings-tab'],
    ['league', 'Leaders', 'awards-tab'],
    ['league', 'Team Stats', 'fcc-team-stats-summary-tab'],
    ['news', 'News', 'press-tab'],
  ];
  for (const row of panels) {
    await mouseClick(page, '[data-gob-section="' + row[0] + '"]');
    await mouseClick(page, stab(page, row[1]));
    await expect(page.locator('#' + row[2] + '.tab-content.active')).toBeVisible();
  }
  await expect(page.locator('#gob-stats-toggle')).toHaveCount(0);
  await mouseClick(page, '[data-gob-section="team"]');
  await expect(page.locator('#gob-subtabs .stab', { hasText: 'Practice Squad' })).toHaveCount(0);

  await page.evaluate(() => {
    window.__shellNav = [];
    window.GOBNav.go = (url) => { window.__shellNav.push(String(url)); };
  });
  await mouseClick(page, '[data-gob-section="league"]');
  const locked = stab(page, 'Tournament');
  await expect(locked).toHaveAttribute('aria-disabled', 'true');
  await expect(locked).toHaveAttribute('tabindex', '-1');
  const opens = await page.evaluate(() => {
    for (let w = 1; w <= 40; w++) {
      if (window.GOBTierEmblem.tierForWeek(w)) return w;
    }
    return 0;
  });
  expect(opens).toBeGreaterThan(0);
  await expect(locked).toHaveAttribute('title', 'Opens Week ' + opens);
  const color = await locked.evaluate((el) => getComputedStyle(el).color);
  const cursor = await locked.evaluate((el) => getComputedStyle(el).cursor);
  expect(cursor).toBe('not-allowed');
  expect(color).toContain('0.38');
  const stabType = await page.evaluate(() => {
    const read = (el) => {
      const cs = getComputedStyle(el);
      return { fontFamily: cs.fontFamily, fontSize: cs.fontSize, height: cs.height };
    };
    const lockedEl = document.querySelector('#gob-subtabs .stab.is-locked');
    const enabled = Array.from(document.querySelectorAll('#gob-subtabs .stab')).find((el) => !el.classList.contains('is-locked'));
    return { locked: read(lockedEl), enabled: read(enabled) };
  });
  expect(stabType.locked).toEqual(stabType.enabled);
  await mouseClick(page, locked);
  expect(await page.evaluate(() => window.__shellNav.length)).toBe(0);
  await page.mouse.move(640, 400);
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, 'tournament-locked-1280.png') });

  async function expectGo(label, needle) {
    await mouseClick(page, stab(page, label));
    const url = await page.evaluate(() => window.__shellNav[window.__shellNav.length - 1] || '');
    expect(url).toContain(needle);
    expect(url).toContain('franchise_id=' + FID);
    expect(url).toContain('team_id=' + TID);
    return url;
  }
  const scheduleUrl = await expectGo('Schedule', '/schedule.html');
  const scheduleHref = await page.locator('#schedule-full-link').getAttribute('href');
  expect(scheduleUrl).toBe(scheduleHref);
  const rankingsUrl = await expectGo('Rankings', '/rankings.html');
  const rankingsHref = scheduleHref.replace('/schedule.html', '/rankings.html');
  expect(rankingsUrl).toBe(rankingsHref);
  const psUrl = await expectGo('Practice Squad', '/practice-squad-standings.html');
  const psHref = await page.locator('#fcc-ps-season-link').getAttribute('href');
  expect(psUrl).toBe(psHref);

  await mouseClick(page, '[data-gob-section="news"]');
  const awardsUrl = await expectGo('Awards', '/awards.html');
  expect(awardsUrl).toContain('franchise_id=');

  await mouseClick(page, '[data-gob-section="recruiting"]');
  await page.waitForFunction(() => (window.__shellNav || []).some((url) => url.indexOf('/recruiting.html') !== -1));
  const recruitingUrl = await page.evaluate(() => window.__shellNav[window.__shellNav.length - 1]);
  expect(recruitingUrl).toContain('from=fcc');
  expect(recruitingUrl).toContain('franchise_id=' + FID);
  expect(recruitingUrl).toContain('team_id=' + TID);
  expect(recruitingUrl).toContain('return_url=');
  await expect(page.locator('#recruits-tab.tab-content.active')).toHaveCount(0);
  await expect(page.locator('#press-tab.tab-content.active')).toBeVisible();

  await page.setViewportSize({ width: 1920, height: 1080 });
  await openFcc(page, cc({ week: opens }));
  await page.evaluate(() => {
    window.__shellNav = [];
    window.GOBNav.go = (url) => { window.__shellNav.push(String(url)); };
  });
  await mouseClick(page, '[data-gob-section="league"]');
  const openTourney = stab(page, 'Tournament');
  await expect(openTourney).not.toHaveAttribute('aria-disabled', 'true');
  await mouseClick(page, openTourney);
  const brackets = await page.evaluate(() => window.__shellNav[0] || '');
  expect(brackets).toContain('/brackets.html');
  await page.screenshot({ path: path.join(OUT, 'tournament-open-1920.png') });
});

test('office team league back returns to team then office', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  await mouseClick(page, '[data-gob-section="team"]');
  await expect(page.locator('#roster-tab.tab-content.active')).toBeVisible();
  await mouseClick(page, '[data-gob-section="league"]');
  await expect(page.locator('#standings-tab.tab-content.active')).toBeVisible();
  await page.goBack();
  await expect(page.locator('#roster-tab.tab-content.active')).toBeVisible();
  await expect(page.locator('[data-gob-section="team"]')).toHaveClass(/on/);
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toBeVisible();
  await expect(page.locator('[data-gob-section="office"]')).toHaveClass(/on/);
});

function hubFixture(leans) {
  return {
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: 7,
    recruits: [{
      recruit_id: 'r-1',
      name: 'Lean Recruit',
      archetype: 'Slasher',
      'Home Region': 'A',
      year: 'Junior',
      height: 74,
      weight: 190,
      attributes: { SC: 40, SH: 40, ID: 40, OD: 40, PS: 40, BH: 40, RB: 40, AG: 40, ST: 40, ND: 40, IQ: 40, FT: 40 },
      position_ratings: { PG: 70 },
      Lean: leans ? { 1: TID, 2: null, 3: null } : { 1: 'rival-1', 2: null, 3: null },
    }],
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
  };
}

async function openHub(page, leans) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, hubFixture(leans));
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/app-config') {
      await fulfillJson(route, {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForSelector('#pool-region');
}

test('recruiting hub lands on leans, otherwise the user region', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openHub(page, true);
  await expect(page.locator('.pool-view[data-view="leans"]')).toHaveClass(/is-on/);
  await page.screenshot({ path: path.join(OUT, 'hub-leans-1280.png') });
  await mouseClick(page, '.pool-view[data-view="leans"]');
  await expect(page.locator('.pool-view[data-view="leans"]')).not.toHaveClass(/is-on/);
  await page.goto('/login.html');
  await page.goBack();
  await page.waitForSelector('#pool-region');
  await expect(page.locator('.pool-view[data-view="leans"]')).not.toHaveClass(/is-on/);

  await openHub(page, false);
  await expect(page.locator('.pool-view.is-on')).toHaveCount(0);
  await expect(page.locator('#pool-region')).toHaveValue('C');
  await expect(page.locator('body')).not.toContainText('Practice Squad');
  await page.screenshot({ path: path.join(OUT, 'hub-region-1280.png') });
});
