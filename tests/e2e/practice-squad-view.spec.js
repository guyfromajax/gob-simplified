const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-ps';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/ps-view-pr-a');

function winPct(wins, losses) {
  const played = wins + losses;
  if (!played) return 0;
  return Math.round((wins / played) * 1000) / 1000;
}

function rows(region) {
  return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].map(function (letter, index) {
    const wins = 8 - index;
    const losses = index;
    return {
      team_id: 'ps_' + letter + '_' + region,
      name: 'Region ' + letter + ' Squad',
      w: wins,
      l: losses,
      win_pct: winPct(wins, losses),
      is_user: letter === 'C',
    };
  });
}

function tiers() {
  return ['All-Americans', 'All-Stars', 'Varsity', 'JV', 'Squad'].map(function (label, index) {
    return { tier: String(index + 1), label: label, rows: rows(index + 1) };
  });
}

function bracket(tier) {
  function game(home, away) {
    return { home_team: home, away_team: away, home_score: null, away_score: null, winner: null };
  }
  const id = String(tier);
  return {
    round1: [
      game('ps_C_' + id, 'ps_A_' + id),
      game('ps_B_' + id, 'ps_D_' + id),
      game('ps_E_' + id, 'ps_F_' + id),
      game('ps_G_' + id, 'ps_H_' + id),
    ],
    round2: [game('ps_C_' + id, 'ps_B_' + id), game('ps_E_' + id, 'ps_G_' + id)],
    final: [game('ps_C_' + id, 'ps_E_' + id)],
  };
}

function tournaments() {
  const out = {};
  for (let tier = 1; tier <= 5; tier += 1) out[String(tier)] = { bracket: bracket(tier) };
  return out;
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
        tournaments: tournaments(),
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
        page: {
          team_id: url.searchParams.get('ps_team_id'), name: 'Region C All-Americans', practice_squad: true,
          tier: 1, tier_label: 'All-Americans', region: 'C', record: { wins: 6, losses: 2 }, tier_place: '3rd of 8',
          results: [], upcoming: [], next_game: null,
        },
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
    // The stub player has no portrait file; the roster falls back to initials.
    if (msg.type() === 'error' && !/\/images\/players\//.test((msg.location() || {}).url || '')) errors.push(msg.text());
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
    const sevenOne = page.locator('#practice-squad-view .gob-ps-grid tr', { hasText: 'Region B Squad' }).first();
    await expect(sevenOne.locator('td').nth(1)).toHaveText('7');
    await expect(sevenOne.locator('td').nth(2)).toHaveText('1');
    await expect(sevenOne.locator('td').nth(3)).toHaveText('.875');
    if (size[2] === '1280') {
      await page.screenshot({ path: path.join(OUT, 'record-1280.png') });
    }
    await expect(page.locator('#practice-squad-view .gob-ps-grid a.gob-team').first()).toHaveCSS('text-decoration-line', 'none');
    await expect(page.locator('#gob-subtabs .gob-wk-label')).toHaveText('Week 8');
    await expect(page.locator('#practice-squad-view .gob-ps-schedule a.gob-res')).toHaveText('60-70');
    await expect(page.locator('#practice-squad-view .gob-ps-schedule')).not.toContainText('Box score');
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
    await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveCount(1);
    await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveAttribute('data-ps-tier', '1');
    await expect(page.locator('#practice-squad-view .gob-ps-tiers button.on')).toHaveText('All-Americans');
    await expect(page.locator('#practice-squad-view .gob-ps-bracket .tname').first()).toContainText('Region');
    await expect(page.locator('#practice-squad-view .gob-ps-bracket .mu--user').first()).toBeVisible();
    await expect(page.locator('#practice-squad-view .gob-ps-champ-eye')).toHaveText('Championship');
    await expect(page.locator('#practice-squad-view .gob-ps-champ a.gob-res')).toHaveText('71-80');
    await expect(page.locator('#practice-squad-view .gob-ps-champ a.gob-team.is-win')).toContainText('Region C Squad');
    await expect(page.locator('#practice-squad-view .gob-ps-grid')).toBeVisible();
    await page.screenshot({ path: path.join(OUT, 'week-17-' + size[2] + '.png') });
    await page.locator('#practice-squad-view .gob-ps-tiers button[data-ps-tier="2"]').click();
    await expect(page).toHaveURL(/ps_tier=2/);
    await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveAttribute('data-ps-tier', '2');
    await expect(page.locator('#practice-squad-view .gob-ps-tiers button.on')).toHaveText('All-Stars');
  }

  await page.setViewportSize({ width: 1280, height: 720 });
  await openPs(page, { week: 17, initialized: true, currentWeek: 17 });
  await expect(page.locator('#practice-squad-view .gob-ps-bracket')).toHaveCount(1);
  await expect(page.locator('#practice-squad-view .gob-ps-champ')).toHaveCount(0);

  await openPs(page, {
    week: 19,
    initialized: true,
    currentWeek: 19,
    championship: {
      game_id: 'ps-final',
      home_team_id: 'ps_C_1',
      away_team_id: 'ps_A_1',
      home_score: null,
      away_score: null,
    },
  });
  await expect(page.locator('#practice-squad-view .gob-ps-champ-eye')).toHaveText('Championship');
  await expect(page.locator('#practice-squad-view .gob-ps-champ')).toContainText('Region A Squad');
  await expect(page.locator('#practice-squad-view .gob-ps-champ')).toContainText('Region C Squad');
  await expect(page.locator('#practice-squad-view .gob-ps-champ a.gob-res')).toHaveCount(0);

  await page.setViewportSize({ width: 1280, height: 720 });
  await openPs(page, { week: 8, initialized: true, currentWeek: 8 });
  await page.locator('#practice-squad-view tr.me a').first().click();
  // A squad opens on the standard team page, in the shell.
  await expect(page).toHaveURL(/franchise-command-center\.html/);
  await expect(page).toHaveURL(/tab=team-view/);
  await expect(page).toHaveURL(/ps_team_id=ps_C_/);
  await expect(page).not.toHaveURL(/team-roster-view|mode=practice_squad|tab=roster-view/);
  await expect(page.locator('#team-view .gob-hero-n')).toHaveText('Region C All-Americans');
  await expect(page.locator('#team-view')).toContainText('Casey Lane');
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
