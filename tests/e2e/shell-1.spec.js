const { test, expect } = require('@playwright/test');

test.describe.configure({ timeout: 180000 });
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-shell1';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/shell-1');
const TABS = [
  ['home-tab', 'office'],
  ['roster-tab', 'team'],
  ['player-stats-tab', 'team'],
  ['team-stats-tab', 'team'],
  ['game-plan-tab', 'prep'],
  ['playbooks-tab', 'prep'],
  ['coaches-tab', 'prep'],
  ['standings-tab', 'league'],
  ['schedule-tab', 'league'],
  ['fcc-team-stats-summary-tab', 'team'],
  ['awards-tab', 'league'],
  ['training-tab', 'prep'],
  ['recruits-tab', 'recruiting'],
  ['press-tab', 'news'],
];

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
    training_completed: false,
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

async function openFcc(page, data, search) {
  await stubAuth(page);
  await installApi(page, data);
  const qs = search || ('?franchise_id=' + FID + '&team_id=' + TID);
  await page.goto('/franchise-command-center.html' + qs);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
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

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('office before and after at both sizes', async ({ page }) => {
  const beforeHtml = execSync('git show 8eff297c0:FrontEnd/static/franchise-command-center.html', {
    cwd: path.join(__dirname, '../..'),
  }).toString();
  await stubAuth(page);
  await installApi(page, cc());
  await page.route(/franchise-command-center\.html/, async (route) => {
    if (route.request().resourceType() !== 'document') {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 200, contentType: 'text/html', body: beforeHtml });
  });
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    await page.waitForSelector('#play-now');
    await page.screenshot({ path: path.join(OUT, 'office-before-' + size[2] + '.png') });
  }
  await page.unroute(/franchise-command-center\.html/);
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
    await page.waitForSelector('html.gob-shell .app');
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    await expect(page.locator('#gob-top-name')).toHaveText('Lancaster');
    const appBox = await page.locator('html.gob-shell .app').boundingBox();
    expect(appBox.x).toBeLessThan(2);
    expect(appBox.y).toBeLessThan(2);
    expect(appBox.width).toBeGreaterThan(size[0] - 4);
    expect(appBox.height).toBeGreaterThan(size[1] - 4);
    const frame = await page.locator('#franchise-container').evaluate((el) => getComputedStyle(el, '::before').content);
    expect(frame).toBe('none');
    const cardPad = await page.locator('.fcc-home-card').first().evaluate((el) => getComputedStyle(el).paddingLeft);
    expect(cardPad).toBe('16px');
    const exit = page.locator('#gob-rail-exit');
    await expect(exit).toBeVisible();
    await expect(exit).toHaveText(/Exit Franchise/);
    const exitBox = await exit.boundingBox();
    expect(exitBox.height).toBeGreaterThanOrEqual(36);
    expect(exitBox.y + exitBox.height).toBeLessThanOrEqual(size[1]);
    await page.screenshot({ path: path.join(OUT, 'office-after-' + size[2] + '.png') });
  }
});

test('sections and sub-tabs open the matching panel', async ({ page }) => {
  const shots = [
    ['office', 'home-tab', null],
    ['team', 'roster-tab', 'Roster'],
    ['team-stats', 'player-stats-tab', 'Stats'],
    ['team-development', 'team-stats-tab', 'Development'],
    ['prep', 'training-tab', 'Training'],
    ['prep-plan', 'game-plan-tab', 'Game Plan'],
    ['prep-playbooks', 'playbooks-tab', 'Playbooks'],
    ['prep-scouting', 'coaches-tab', 'Scouting'],
    ['league', 'standings-tab', 'Standings'],
    ['league-schedule', 'schedule-tab', 'Schedule & Results'],
    ['league-leaders', 'awards-tab', 'Leaders'],
    ['recruiting', 'recruits-tab', null],
    ['news', 'press-tab', 'News'],
  ];
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openFcc(page, cc());
    const sectionFor = {
      office: 'office', team: 'team', 'team-stats': 'team', 'team-development': 'team',
      prep: 'prep', 'prep-plan': 'prep', 'prep-playbooks': 'prep', 'prep-scouting': 'prep',
      league: 'league', 'league-schedule': 'league', 'league-leaders': 'league',
      recruiting: 'recruiting', news: 'news',
    };
    for (const row of shots) {
      await mouseClick(page, '[data-gob-section="' + sectionFor[row[0]] + '"]');
      if (row[2]) await mouseClick(page, stab(page, row[2]));
      await expect(page.locator('#' + row[1] + '.tab-content.active')).toBeVisible();
      const activeRail = page.locator('.rail [data-gob-section].on');
      await expect(activeRail).toHaveCount(1);
      await expect(activeRail).toHaveAttribute('data-gob-section', sectionFor[row[0]]);
      if (row[0] === 'team' && row[2] === 'Roster') {
        const stabMetrics = await page.evaluate(() => {
          const read = (el) => {
            const cs = getComputedStyle(el);
            return { fontFamily: cs.fontFamily, height: cs.height, clipPath: cs.clipPath };
          };
          const tabs = Array.from(document.querySelectorAll('#gob-subtabs > .stab'));
          const button = tabs.find((el) => el.tagName === 'BUTTON' && !el.classList.contains('on'));
          const link = tabs.find((el) => el.tagName === 'A');
          return { button: read(button), link: read(link) };
        });
        expect(stabMetrics.button).toEqual(stabMetrics.link);
        expect(stabMetrics.button.height).toBe('40px');
        expect(stabMetrics.button.fontFamily).toMatch(/Bebas/);
        expect(stabMetrics.button.clipPath).toContain('polygon');
      }
      await page.screenshot({ path: path.join(OUT, row[0] + '-' + size[2] + '.png') });
    }
    await mouseClick(page, '[data-gob-section="prep"]');
    await expect(page.locator('#gob-subtabs .stab', { hasText: /^Lineup$/ })).toHaveCount(0);
    await mouseClick(page, '[data-gob-section="team"]');
    await mouseClick(page, stab(page, 'Stats'));
    await mouseClick(page, page.locator('#gob-stats-toggle button').filter({ hasText: /^Team$/ }));
    await expect(page.locator('#fcc-team-stats-summary-tab.tab-content.active')).toBeVisible();
    await page.screenshot({ path: path.join(OUT, 'team-stats-team-' + size[2] + '.png') });
  }
});

test('advance labels match the three week states and repeat clicks are ignored', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc({ week: 1, training_completed: false, session_type: 'in-season' }));
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', 'training');

  await page.evaluate(() => {
    window.__shellNav = [];
    window.GOBNav.go = (url) => { window.__shellNav.push(url); };
  });
  const box = await page.locator('#play-now').boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.locator('#play-now')).toHaveText('STARTING…');
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.locator('#play-now')).toHaveText('STARTING…');
  await page.waitForTimeout(400);
  const navCount = await page.evaluate(() => (window.__shellNav || []).length);
  expect(navCount).toBe(1);
  expect(await page.evaluate(() => window.__shellNav[0])).toContain('/training.html');

  await openFcc(page, cc({ week: 8, training_completed: true }));
  await expect(page.locator('#play-now')).toHaveText('Play Next Game');
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', 'play');

  await openFcc(page, cc({ week: 8, training_completed: true, cut_required: true }));
  await expect(page.locator('#play-now')).toHaveText('Assign Practice Squad');
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', 'cut-players');

  await openFcc(page, cc({ week: 28, training_completed: true, training_disabled_for_postseason: true, user_eliminated: false, has_eos_game_this_week: true }));
  await expect(page.locator('header.top')).toHaveClass(/is-tier/);
  await expect(page.locator('#gob-week-phase')).toBeHidden();
});

test('back restores the section as it was left, including scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  await mouseClick(page, '[data-gob-section="team"]');
  await mouseClick(page, stab(page, 'Stats'));
  await expect(page.locator('#player-stats-tab.tab-content.active')).toBeVisible();
  const scrolled = await page.evaluate(() => {
    const panel = document.getElementById('player-stats-tab');
    const main = document.querySelector('html.gob-shell .main');
    panel.style.minHeight = '2400px';
    main.scrollTop = 640;
    return { top: main.scrollTop, sh: main.scrollHeight, ch: main.clientHeight };
  });
  expect(scrolled.top, JSON.stringify(scrolled)).toBeGreaterThan(500);
  await mouseClick(page, '[data-gob-section="league"]');
  await expect(page.locator('#standings-tab.tab-content.active')).toBeVisible();
  await page.goBack();
  await expect(page.locator('#player-stats-tab.tab-content.active')).toBeVisible();
  await expect(page.locator('[data-gob-section="team"]')).toHaveClass(/on/);
  const top = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(top).toBeGreaterThan(500);
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toBeVisible();
});

test('old tab query opens the new section', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  for (const pair of TABS) {
    await openFcc(page, cc(), '?franchise_id=' + FID + '&team_id=' + TID + '&tab=' + pair[0]);
    await expect(page.locator('#' + pair[0] + '.tab-content.active')).toBeVisible();
    await expect(page.locator('[data-gob-section="' + pair[1] + '"]')).toHaveClass(/on/);
  }
});

test('rail hover does not move main', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  const before = await page.locator('.main').boundingBox();
  const rail = await page.locator('.rail').boundingBox();
  await page.mouse.move(rail.x + 20, rail.y + 80);
  await page.waitForTimeout(500);
  const after = await page.locator('.main').boundingBox();
  expect(Math.round(after.x)).toBe(Math.round(before.x));
  expect(Math.round(after.width)).toBe(Math.round(before.width));
});

test('settings anchors beside the rail and closes three ways', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  await mouseClick(page, '#gob-rail-settings');
  await page.mouse.move(640, 360);
  await expect(page.locator('#gob-settings-host')).toBeVisible();
  const metrics = await page.evaluate(() => {
    const host = document.getElementById('gob-settings-host').getBoundingClientRect();
    const rail = document.querySelector('.rail').getBoundingClientRect();
    const face = document.querySelector('.rail-face').getBoundingClientRect();
    return {
      host: Math.round(host.x),
      railRight: Math.round(rail.right),
      faceRight: Math.round(face.right),
      railW: getComputedStyle(document.documentElement).getPropertyValue('--rail-w').trim(),
    };
  });
  expect(Math.abs(metrics.host - metrics.faceRight), JSON.stringify(metrics)).toBeLessThan(3);
  await expect(page.locator('#gob-rail-settings')).toHaveClass(/open/);
  await page.keyboard.press('Escape');
  await expect(page.locator('#gob-settings-host')).toBeHidden();
  await mouseClick(page, '#gob-rail-settings');
  await expect(page.locator('#gob-settings-host')).toBeVisible();
  const scrim = await page.locator('[data-settings-scrim]').boundingBox();
  await page.mouse.click(scrim.x + scrim.width - 20, scrim.y + 40);
  await expect(page.locator('#gob-settings-host')).toBeHidden();
  await mouseClick(page, '#gob-rail-settings');
  await expect(page.locator('#gob-settings-host')).toBeVisible();
  await mouseClick(page, '#gob-rail-settings');
  await expect(page.locator('#gob-settings-host')).toBeHidden();
});

test('rail active state follows deep links and back, and exit calls the existing control', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc(), '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-tab');
  await expect(page.locator('.rail [data-gob-section].on')).toHaveAttribute('data-gob-section', 'team');
  await mouseClick(page, '[data-gob-section="prep"]');
  await expect(page.locator('.rail [data-gob-section].on')).toHaveAttribute('data-gob-section', 'prep');
  await page.goBack();
  await expect(page.locator('#roster-tab.tab-content.active')).toBeVisible();
  await expect(page.locator('.rail [data-gob-section].on')).toHaveAttribute('data-gob-section', 'team');
  await page.goForward();
  await expect(page.locator('#training-tab.tab-content.active')).toBeVisible();
  await expect(page.locator('.rail [data-gob-section].on')).toHaveAttribute('data-gob-section', 'prep');
  await page.evaluate(() => {
    const exit = document.getElementById('exit-franchise');
    exit.addEventListener('click', (event) => {
      event.stopImmediatePropagation();
      event.preventDefault();
      window.__railExit = (window.__railExit || 0) + 1;
    }, true);
  });
  await mouseClick(page, '#gob-rail-exit');
  expect(await page.evaluate(() => window.__railExit)).toBe(1);
});

test('shared tab clicks still replace and stay visible without the shell', async ({ page }) => {
  await stubAuth(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/coaching-archetypes.html');
  await page.evaluate(() => {
    document.body.insertAdjacentHTML('beforeend', [
      '<div class="tab-buttons">',
      '<button type="button" data-tab="standings-tab">Standings</button>',
      '<button type="button" data-tab="bracket-tab">Bracket</button>',
      '</div>',
      '<div id="standings-tab" class="tab-content"></div>',
      '<div id="bracket-tab" class="tab-content"></div>',
    ].join(''));
  });
  await page.addScriptTag({ url: '/js/shared/commandCenterTabs.js' });
  await page.evaluate(() => {
    window.CommandCenterTabs.initCommandCenterTabs({ defaultTab: 'standings-tab' });
  });
  const before = await page.evaluate(() => history.length);
  const tab = page.locator('.tab-buttons [data-tab="bracket-tab"]');
  await tab.scrollIntoViewIfNeeded();
  const box = await tab.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  const after = await page.evaluate(() => history.length);
  expect(after).toBe(before);
  await expect(page.locator('#bracket-tab')).toHaveClass(/active/);
  await expect(page.locator('html')).not.toHaveClass(/gob-shell/);
  await expect(page.locator('.tab-buttons')).toBeVisible();
});

test('no horizontal scrollbar at 1280 and nested scrollers are listed', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page, cc());
  const metrics = await page.evaluate(() => {
    const bar = window.innerWidth - document.documentElement.clientWidth > 1;
    const nested = [];
    document.querySelectorAll('html.gob-shell .main *').forEach((el) => {
      const style = getComputedStyle(el);
      const oy = style.overflowY;
      const ox = style.overflowX;
      const scrolls = oy === 'auto' || oy === 'scroll' || ox === 'auto' || ox === 'scroll';
      const overflows = el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2;
      if (scrolls && overflows) nested.push(el.id || String(el.className));
    });
    return { bar, nested: nested.slice(0, 40), mainOverflow: getComputedStyle(document.querySelector('.main')).overflowY };
  });
  expect(metrics.bar).toBe(false);
  expect(metrics.mainOverflow).toBe('auto');
  fs.writeFileSync(path.join(OUT, 'nested-scroll.txt'), JSON.stringify(metrics.nested, null, 2));
});
