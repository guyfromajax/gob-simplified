const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-ps';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/ps-view-pr-a');

function rows(region) {
  return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].map(function (letter, index) {
    return {
      team_id: 'ps_' + letter + '_' + region,
      name: 'Region ' + letter + ' Squad',
      w: 8 - index,
      l: index,
      win_pct: index === 0 ? 1 : 0.5,
      is_user: letter === 'C',
    };
  });
}

function tiers() {
  return ['All-Americans', 'All-Stars', 'Varsity', 'JV', 'Squad'].map(function (label, index) {
    return { tier: String(index + 1), label: label, rows: rows(index + 1) };
  });
}

function bracket() {
  function game(home, away) {
    return { home_team: home, away_team: away, home_score: null, away_score: null, winner: null };
  }
  return {
    round1: [
      game('ps_C_1', 'ps_A_1'),
      game('ps_B_1', 'ps_D_1'),
      game('ps_E_1', 'ps_F_1'),
      game('ps_G_1', 'ps_H_1'),
    ],
    round2: [game('ps_C_1', 'ps_B_1'), game('ps_E_1', 'ps_G_1')],
    final: [game('ps_C_1', 'ps_E_1')],
  };
}

function names() {
  const teams = {};
  ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].forEach(function (letter) {
    for (let tier = 1; tier <= 5; tier += 1) {
      teams['ps_' + letter + '_' + tier] = { display_name: 'Region ' + letter + ' Squad' };
    }
  });
  return teams;
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function install(page, state) {
  const scheduleHits = [];
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) {
      await route.continue();
      return;
    }
    const pathname = url.pathname;
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
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
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, {
        franchise_id: FID,
        team_id: TID,
        team: 'Lancaster',
        week: state.week,
        rank: 14,
        training_completed: true,
        cut_required: false,
        recruiting_wire: { board_saved_week: state.week, counts: {} },
        team_record: { wins: 4, losses: 2 },
      });
      return;
    }
    if (pathname.startsWith('/franchise/practice-squad/standings')) {
      if (!state.initialized) {
        await fulfillJson(route, { initialized: false, week: state.week, tiers: [], standings: {}, teams: {} });
        return;
      }
      await fulfillJson(route, { initialized: true, week: state.week, tiers: tiers(), teams: names() });
      return;
    }
    if (pathname.startsWith('/franchise/practice-squad/schedule')) {
      scheduleHits.push(url.search);
      if (!url.searchParams.has('week')) {
        const weeks = [];
        for (let w = 2; w <= 19; w += 1) weeks.push(w);
        await fulfillJson(route, {
          initialized: state.initialized,
          week: state.week,
          current_week: state.currentWeek,
          weeks: state.initialized ? weeks : [],
        });
        return;
      }
      await fulfillJson(route, {
        initialized: true,
        week: Number(url.searchParams.get('week')),
        games: [{
          home_team_id: 'ps_C_1',
          away_team_id: 'ps_A_1',
          home_display: 'Region C Squad',
          away_display: 'Region A Squad',
          status: 'completed',
          home_score: 70,
          away_score: 60,
          game_id: 'ps-game-1',
        }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/practice-squad/brackets')) {
      await fulfillJson(route, {
        initialized: true,
        week: state.week,
        tournaments: { '1': { bracket: bracket() } },
        championship: state.championship || {},
        teams: names(),
      });
      return;
    }
    if (pathname.startsWith('/franchise/practice-squad/team')) {
      await fulfillJson(route, {
        team: { display_name: 'Region C All-Americans' },
        players: [{
          player_id: 'p-ps',
          name: 'Casey Lane',
          parent_team_name: 'Lancaster',
          attributes: {},
          position_ratings: { PG: 70 },
          stats: {},
        }],
        projected_starting_five: [],
      });
      return;
    }
    await fulfillJson(route, {});
  });
  return scheduleHits;
}

async function openPs(page, week) {
  await stubAuth(page);
  const hits = await install(page, week);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=practice-squad-view');
  await page.waitForSelector('#practice-squad-view.tab-content.active');
  return hits;
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('practice squad view: before init, in season, and the bracket', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openPs(page, { week: 1, initialized: false, currentWeek: 2 });
    await expect(page.locator('#practice-squad-view')).toContainText('Practice Squad has not started yet');
    await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveCount(0);
    await page.screenshot({ path: path.join(OUT, 'before-init-' + size[2] + '.png') });

    const hits = await openPs(page, { week: 8, initialized: true, currentWeek: 8 });
    await expect(page.locator('#practice-squad-view .gob-ps-grid .gob-tcard')).toHaveCount(5);
    await expect(page.locator('#practice-squad-view tr.me').first()).toContainText('Region C Squad');
    await expect(page.locator('#gob-subtabs .gob-wk-label')).toHaveText('Week 8');
    await expect(page.locator('#practice-squad-view .gob-ps-schedule')).toContainText('60-70');
    await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveCount(0);
    const weekCalls = hits.filter((search) => search.indexOf('week=') !== -1);
    expect(weekCalls.length).toBe(1);
    await page.locator('#practice-squad-view .gob-ps-grid a').first().focus();
    await expect(page.locator('#practice-squad-view .gob-ps-grid a').first()).toBeFocused();
    await page.screenshot({ path: path.join(OUT, 'week-8-' + size[2] + '.png') });

    await openPs(page, {
      week: 17,
      initialized: true,
      currentWeek: 17,
      championship: {
        game_id: 'ps-champ',
        home_team_id: 'ps_C_1',
        away_team_id: 'ps_A_1',
        home_score: 80,
        away_score: 71,
      },
    });
    await expect(page.locator('#practice-squad-view .gob-ps-bracket').first()).toBeVisible();
    await expect(page.locator('#practice-squad-view .gob-ps-bracket .tname').first()).toContainText('Region');
    await expect(page.locator('#practice-squad-view .gob-ps-champ')).toContainText('80');
    await expect(page.locator('#practice-squad-view .gob-ps-grid')).toBeVisible();
    await page.screenshot({ path: path.join(OUT, 'week-17-' + size[2] + '.png') });
  }

  await page.setViewportSize({ width: 1280, height: 720 });
  await openPs(page, { week: 8, initialized: true, currentWeek: 8 });
  await page.locator('#practice-squad-view tr.me a').first().click();
  await expect(page).toHaveURL(/team-roster-view\.html/);
  await expect(page).toHaveURL(/mode=practice_squad/);
  await expect(page).toHaveURL(/ps_team_id=ps_C_/);
  await expect(page).not.toHaveURL(/tab=roster-view/);
  await expect(page.locator('body')).toContainText('Casey Lane');
  await page.screenshot({ path: path.join(OUT, 'ps-team-1280.png') });

  expect(errors, errors.join('\n')).toEqual([]);
});

test('old practice squad pages redirect into the view', async ({ page }) => {
  await stubAuth(page);
  await install(page, { week: 8, initialized: true, currentWeek: 8 });
  await page.goto('/practice-squad-standings.html?franchise_id=' + FID + '&team_id=' + TID);
  await expect(page).toHaveURL(/tab=practice-squad-view/);
  await expect(page).toHaveURL(new RegExp('franchise_id=' + FID));
  await page.goto('/practice-squad-bracket.html?franchise_id=' + FID + '&team_id=' + TID);
  await expect(page).toHaveURL(/tab=practice-squad-view/);
});
