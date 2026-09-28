const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-tournament';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OUT = path.join(__dirname, '../../reports/tournament-view');

function bracketRound1(userWon) {
  return [{
    home_team: TID,
    away_team: OPP,
    winner: userWon ? TID : OPP,
    game_id: userWon ? 'g-t1' : 'g-t1',
    score: { home: 72, away: 65 },
  }];
}

function payload(week, extra) {
  return Object.assign({
    week: week,
    first_week: 27,
    locked: week < 27,
    current_phase: week >= 32 ? 'national' : week >= 30 ? 'region' : week >= 27 ? 'conference' : null,
    user_team_id: TID,
    user_conference: 1,
    user_region: 'A',
    user_eliminated: false,
    eliminated_in_round: null,
    has_eos_game_this_week: week === 27,
    has_bye_this_week: false,
    region_qualified: false,
    tournament_complete: false,
    champion: null,
    phase_draw_week: { conference: 27, region: 30, national: 32 },
    round_labels: {
      conference: { round1: 'Quarterfinal', round2: 'Semifinal', final: 'Final' },
      region: { round1: 'Semifinal', final: 'Final' },
      national: { round1: 'Quarterfinal', round2: 'Semifinal', final: 'Final' },
    },
    conference_tournaments: {
      '1': {
        current_round: 1,
        bracket: {
          round1: bracketRound1(true),
          round2: [],
          final: [],
        },
        seeds: { [TID]: 3, [OPP]: 6 },
      },
    },
    region_tournaments: {
      A: {
        round1: [{ home_team: TID, away_team: OPP, winner: null, score: {} }],
        final: [],
        current_round: 1,
      },
    },
    national_tournament: {
      bracket: { round1: [], round2: [], final: [] },
      champion: null,
    },
    eos_tournament: null,
    teams: {
      [TID]: { name: 'Lancaster', mascot: 'Knights', conference: 1, region: 'A', natl_rank: 4, W: 20, L: 6, logo: 'Lancaster' },
      [OPP]: { name: 'Rival U', mascot: 'Owls', conference: 1, region: 'A', natl_rank: 12, W: 18, L: 8, logo: 'Rival U' },
    },
    region_tournaments_stale: false,
  }, extra || {});
}

async function installApi(page, body) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_id: 'e2e', username: 'e2e' }) });
      return;
    }
    if (pathname === '/app-config') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ isAlpha: false }) });
      return;
    }
    if (pathname.startsWith('/franchise/tournament/brackets')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          franchise_id: FID,
          team_id: TID,
          user_team_id: TID,
          week: body.week,
          user_conference: 1,
          user_region: 'A',
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

async function openView(page, body) {
  await stubAuth(page);
  await installApi(page, body);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=tournament-view');
  await expect(page.locator('#tournament-view.tab-content.active')).toBeVisible();
}

test.describe('tournament view', () => {
  test('week 26 locked and week 27 conference bracket', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openView(page, payload(26));
    await expect(page.locator('#tournament-view .gob-tour-locked')).toContainText('Week 27');
    await page.screenshot({ path: path.join(OUT, 'week-26-locked-1280.png') });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.screenshot({ path: path.join(OUT, 'week-26-locked-1920.png') });
    await page.setViewportSize({ width: 1280, height: 720 });

    await openView(page, payload(27));
    await expect(page.locator('#tournament-view .fcc-tb-team--user')).toBeVisible();
    await expect(page.locator('#tournament-view a.fcc-tb-res-link')).toHaveText('65-72');
    await page.screenshot({ path: path.join(OUT, 'week-27-conference-1280.png') });

    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.screenshot({ path: path.join(OUT, 'week-27-conference-1920.png') });
  });

  test('region phase, eliminated, and champion states', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openView(page, payload(30));
    await page.locator('#tournament-view [data-tour-phase="region"]').click();
    await expect(page).toHaveURL(/tournament_phase=region/);
    await page.screenshot({ path: path.join(OUT, 'week-30-region-1280.png') });

    await openView(page, payload(28, {
      user_eliminated: true,
      eliminated_in_round: 'Quarterfinal',
      has_eos_game_this_week: false,
    }));
    await expect(page.locator('#tournament-view .gob-tour-note')).toContainText('Eliminated in Quarterfinal');
    await page.screenshot({ path: path.join(OUT, 'eliminated-1280.png') });

    await openView(page, payload(34, {
      tournament_complete: true,
      champion: TID,
      national_tournament: {
        bracket: {
          round1: bracketRound1(true),
          round2: [],
          final: [{ home_team: TID, away_team: OPP, winner: TID, game_id: 'g-nat', score: { home: 80, away: 70 } }],
        },
        champion: TID,
      },
      current_phase: 'national',
    }));
    await page.locator('#tournament-view [data-tour-phase="national"]').click();
    await expect(page.locator('#tournament-view .gob-tour-champ')).toContainText('Lancaster');
    await page.screenshot({ path: path.join(OUT, 'complete-1280.png') });
  });

  test('brackets.html redirects into the view', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/brackets.html?franchise_id=' + FID + '&team_id=' + TID);
    await page.waitForURL(/tab=tournament-view/);
  });
});
