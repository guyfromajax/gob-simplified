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
    game_id: 'g-t1',
    score: { home: 72, away: 65 },
  }, {
    home_team: OPP,
    away_team: TID,
    winner: OPP,
    game_id: 'g-t2',
    score: { home: 68, away: 70 },
  }, {
    home_team: TID,
    away_team: OPP,
    winner: TID,
    game_id: 'g-t3',
    score: { home: 75, away: 60 },
  }, {
    home_team: OPP,
    away_team: TID,
    winner: TID,
    game_id: 'g-t4',
    score: { home: 55, away: 62 },
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
        round1: [{ home_team: TID, away_team: OPP, winner: TID, game_id: 'g-r1', score: { home: 70, away: 65 } }],
        final: [],
        current_round: 1,
        seeds: {},
      },
    },
    national_tournament: {
      bracket: {
        round1: bracketRound1(true),
        round2: [],
        final: [{ home_team: TID, away_team: OPP, winner: TID, game_id: 'g-nat', score: { home: 80, away: 70 } }],
      },
      champion: null,
      seeds: { [TID]: 1, [OPP]: 8 },
    },
    eos_tournament: null,
    teams: {
      [TID]: { name: 'Lancaster', mascot: 'Knights', conference: 1, region: 'A', natl_rank: 4, W: 20, L: 6, logo: 'Lancaster' },
      [OPP]: { name: 'Rival U', mascot: 'Owls', conference: 1, region: 'A', natl_rank: 12, W: 18, L: 8, logo: 'Rival U' },
    },
    region_tournaments_stale: false,
  }, extra || {});
}

function ccData(body) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: body.week,
    rank: 4,
    user_conference: 1,
    user_region: 'A',
    training_completed: true,
    cut_required: false,
    eos_tournament_active: body.week >= 27,
    region_bye_modal_eligible: false,
    conference_rs_region_modal: { eligible: false },
    bracket_reveal_modal: { eligible: false },
    bracket_update_modal: { eligible: false },
    recruiting_results_modal: { eligible: false },
    walk_on_welcome_modal: { eligible: false },
    recruiting_wire: { board_saved_week: body.week, counts: {} },
    team_record: { wins: 20, losses: 6 },
  };
}

async function installApi(page, body) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname === '/app-config' || pathname === '/teams';
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
    if (pathname === '/teams') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ name: 'Lancaster', object_id: TID, _id: TID }]) });
      return;
    }
    if (pathname.startsWith('/franchise/tournament/brackets')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ccData(body)) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

async function waitForBrowseReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForFunction(() => {
    const modal = document.querySelector('.bn-overlay.show, .sammy-modal-backdrop.open');
    return !modal;
  });
}

async function waitForBracket(page) {
  await expect(page.locator('#tournament-view .fcc-tb-mu').first()).toBeVisible();
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    if (overlay && getComputedStyle(overlay).display !== 'none') return false;
    const mu = document.querySelector('#tournament-view .fcc-tb-mu');
    if (!mu) return false;
    return getComputedStyle(mu).opacity !== '0';
  });
}

async function openView(page, body) {
  await stubAuth(page);
  await installApi(page, body);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=tournament-view');
  await waitForBrowseReady(page);
  await expect(page.locator('#tournament-view.tab-content.active')).toBeVisible();
}

async function assertNoLoader(page) {
  await expect(page.locator('#page-load-overlay')).toBeHidden();
  await expect(page.locator('.bn-overlay.show')).toHaveCount(0);
  await expect(page.locator('#tournament-view .gob-view-skel')).toHaveCount(0);
}

test.describe('tournament view', () => {
  test('bracket states and no page loader', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });

    async function shot(name, width, height, opts) {
      await page.setViewportSize({ width: width, height: height });
      if (!opts || opts.bracket !== false) {
        await waitForBracket(page);
      } else {
        await assertNoLoader(page);
      }
      await assertNoLoader(page);
      await page.screenshot({ path: path.join(OUT, name) });
    }

    await openView(page, payload(26));
    await assertNoLoader(page);
    await expect(page.locator('#tournament-view .gob-tour-phases')).toHaveCount(0);
    await expect(page.locator('#tournament-view .gob-tour-locked-title')).toContainText('Week 27');
    await expect(page.locator('#tournament-view .fcc-tb-mu')).toHaveCount(0);
    await shot('week-26-locked-1280.png', 1280, 720, { bracket: false });
    await shot('week-26-locked-1920.png', 1920, 1080, { bracket: false });

    await openView(page, payload(27));
    await expect(page.locator('#tournament-view .fcc-tb-mu').first()).toBeVisible();
    await expect(page.locator('#tournament-view .fcc-tb-team--user').first()).toBeVisible();
    await expect(page.locator('#tournament-view .fcc-tb-res-link')).toHaveCount(0);
    await expect(page.locator('#tournament-view a.fcc-tb-score.gob-res').first()).toBeVisible();
    await shot('week-27-conference-1280.png', 1280, 720);
    await shot('week-27-conference-1920.png', 1920, 1080);

    await openView(page, payload(30));
    await page.locator('#tournament-view [data-tour-phase="region"]').click();
    await shot('week-30-region-1280.png', 1280, 720);
    await shot('week-30-region-1920.png', 1920, 1080);

    await openView(page, payload(32));
    await page.locator('#tournament-view [data-tour-phase="national"]').click();
    await shot('week-32-national-1280.png', 1280, 720);
    await shot('week-32-national-1920.png', 1920, 1080);

    await openView(page, payload(28, {
      user_eliminated: true,
      eliminated_in_round: 'Quarterfinal',
      has_eos_game_this_week: false,
    }));
    await expect(page.locator('#tournament-view .gob-tour-status-eye')).toHaveText('Eliminated');
    await shot('eliminated-1280.png', 1280, 720);
    await shot('eliminated-1920.png', 1920, 1080);

    await openView(page, payload(34, {
      tournament_complete: true,
      champion: TID,
      national_tournament: payload(34).national_tournament,
      current_phase: 'national',
    }));
    await page.locator('#tournament-view [data-tour-phase="national"]').click();
    await expect(page.locator('#tournament-view .gob-tour-status')).toHaveCount(0);
    await expect(page.locator('#tournament-view .fcc-tb-team--champion')).toBeVisible();
    await shot('complete-1280.png', 1280, 720);
    await shot('complete-1920.png', 1920, 1080);
  });

  test('brackets.html redirects into the view', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/brackets.html?franchise_id=' + FID + '&team_id=' + TID);
    await page.waitForURL(/tab=tournament-view/);
  });

  test('offline loopback sqlite week 27', async ({ page }) => {
    const base = process.env.TOURNEY_OFFLINE_BASE;
    test.skip(!base, 'set TOURNEY_OFFLINE_BASE after seed + loopback');
    fs.mkdirSync(OUT, { recursive: true });
    const meta = JSON.parse(process.env.TOURNEY_OFFLINE_META || '{}');
    const fid = meta.franchise_id;
    const tid = meta.team_id;
    const port = Number(process.env.TOURNEY_OFFLINE_PORT || '8025');
    await page.addInitScript((p) => {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = p;
    }, port);
    await page.goto(base + '/franchise-command-center.html?franchise_id=' + fid + '&team_id=' + tid + '&tab=tournament-view');
    await waitForBrowseReady(page);
    await waitForBracket(page);
    await assertNoLoader(page);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.screenshot({ path: path.join(OUT, 'offline-week-27-1280.png') });
  });
});
