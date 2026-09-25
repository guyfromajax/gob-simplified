const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-shell2';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/shell-2');

const BROWSE = [
  'recruiting.html',
  'rankings.html',
  'schedule.html',
  'practice-squad-standings.html',
  'practice-squad-bracket.html',
  'brackets.html',
  'awards.html',
  'news.html',
  'leaders.html',
  'player-detail.html',
  'team-roster-view.html',
  'standings.html',
  'team-stats.html',
  'stats.html',
];

const FOCUS = [
  'set-lineup.html',
  'training.html',
  'training-report.html',
  'training-squad-report.html',
  'training-playbooks.html',
  'cut-players.html',
  'game-plan.html',
  'playbooks.html',
  'playbook-report.html',
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
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 1, counts: {} },
    user_conference: 1,
    user_region: 'A',
    team_record: { wins: 16, losses: 5 },
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
    await fulfillJson(route, {});
  });
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

async function openPage(page, file, data, extra) {
  await stubAuth(page);
  await installApi(page, data);
  const q = 'franchise_id=' + FID + '&team_id=' + TID + (extra || '');
  await page.goto('/' + file + '?' + q);
  await page.waitForSelector('html.gob-shell .app');
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('browse and focus pages, screenshots, and one vertical scroll', async ({ page }) => {
  const loads = [];
  const pages = BROWSE.concat(FOCUS).concat(['box-score.html']);
  for (const file of pages) {
    const extra = file === 'box-score.html' ? '&return_url=' + encodeURIComponent('/schedule.html') : '';
    await openPage(page, file, cc(), extra);
    const focus = FOCUS.indexOf(file) !== -1;
    if (focus) {
      await expect(page.locator('html.gob-focus')).toHaveCount(1);
      await expect(page.locator('.rail')).toHaveCount(0);
      await expect(page.locator('#play-now.advance')).toHaveCount(0);
      await expect(page.locator('#gob-focus-settings')).toBeVisible();
    } else {
      await expect(page.locator('.rail')).toHaveCount(1);
      await expect(page.locator('#play-now.advance')).toHaveCount(1);
    }
    const meta = await page.evaluate(() => ({
      ms: window.__gobAdvanceLoadMs,
      reused: !!window.__gobAdvanceLoadReused,
    }));
    loads.push(file + ' ' + (meta.reused ? 'reused' : 'fetched') + ' ' + Math.round(meta.ms || 0) + 'ms');
    for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.waitForTimeout(150);
      await assertOneVerticalScroll(page);
      const name = file.replace('.html', '') + (extra ? '-browse' : '') + '-' + size[2] + '.png';
      await page.screenshot({ path: path.join(OUT, name) });
    }
  }
  await openPage(page, 'box-score.html', cc(), '&from=lineup');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await page.screenshot({ path: path.join(OUT, 'box-score-flow-1280.png') });
  fs.writeFileSync(path.join(OUT, 'load-times.txt'), loads.join('\n') + '\n');
});

test('advance label matches the office on three weeks', async ({ page }) => {
  const weeks = [
    cc({ week: 4, training_completed: false, session_type: 'in-season' }),
    cc({ week: 8, training_completed: true }),
    cc({ week: 20, training_completed: true, recruiting_wire: { board_saved_week: 0, counts: {} } }),
  ];
  const surfaces = ['franchise-command-center.html', 'rankings.html', 'schedule.html', 'awards.html'];
  for (const data of weeks) {
    let office = null;
    for (const file of surfaces) {
      await openPage(page, file, data);
      await page.waitForFunction(() => {
        const btn = document.getElementById('play-now');
        return btn && btn.dataset.mode && btn.textContent && btn.textContent !== 'STARTING…';
      });
      const read = await page.evaluate(() => ({
        label: document.getElementById('play-now').textContent,
        mode: document.getElementById('play-now').dataset.mode,
      }));
      if (!office) office = read;
      expect(read).toEqual(office);
    }
  }
});

test('rankings sub-tab replace then back returns to League', async ({ page }) => {
  await openPage(page, 'franchise-command-center.html', cc());
  await page.waitForSelector('#play-now.advance');
  await mouseClick(page, '.rail [data-gob-section="league"]');
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Standings');
  await mouseClick(page, stab(page, 'Rankings'));
  await page.waitForURL(/rankings\.html/);
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Rankings');
  const mid = await page.evaluate(() => (history.state && history.state.gobIdx));
  await mouseClick(page, stab(page, 'Standings'));
  await page.waitForURL(/franchise-command-center\.html/);
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Standings');
  const after = await page.evaluate(() => (history.state && history.state.gobIdx));
  expect(after).toBe(mid);
  await page.goBack();
  await page.waitForURL(/franchise-command-center\.html\?.*tab=standings-tab/);
  await expect(page.locator('.rail [data-gob-section="league"].on')).toHaveCount(1);
});

test('flow pages keep their own exit and the court has no shell', async ({ page }) => {
  await openPage(page, 'training.html', cc({ training_completed: false }));
  await expect(page.locator('#back-btn')).toHaveCount(1);
  await expect(page.locator('.rail')).toHaveCount(0);
  await openPage(page, 'recruiting.html', cc(), '&action=run');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await stubAuth(page);
  await installApi(page, cc());
  await page.goto('/court.html?mode=franchise&franchise_id=' + FID);
  await page.waitForTimeout(400);
  await expect(page.locator('html.gob-shell')).toHaveCount(0);
  await expect(page.locator('.rail')).toHaveCount(0);
});

test('office home has one vertical scroller', async ({ page }) => {
  await openPage(page, 'franchise-command-center.html', cc());
  await page.setViewportSize({ width: 1280, height: 720 });
  await assertOneVerticalScroll(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await assertOneVerticalScroll(page);
});
