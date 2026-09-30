const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-prep-scout';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OUT = path.join(__dirname, '../../reports/prep-v2-pr4');

const MEASURES = [
  { key: 'shot_threshold', label: 'Shooting', rank: 12, rank_of: 128, percentile: 72, direction: 'lower_better' },
  { key: 'rebound_modifier', label: 'Rebounding', rank: 8, rank_of: 128, percentile: 88, direction: 'higher_better' },
  { key: 'team_chemistry', label: 'Chemistry', rank: 20, rank_of: 128, percentile: 55, value: 18, scale_max: 25, direction: 'higher_better' },
];

// `attributes` here are on the 0–10 display scale, which is what
// compute_projected_starting_five actually sends (`int(raw) // 10`). The fixture used to
// carry raw 0–99 values, so the view's second divide-by-10 looked correct under test and
// floored every tile to 0 in the real app.
const PROJECTED = [
  {
    player_id: 'scout-pg-01',
    position: 'PG',
    name: 'Jordan Reyes',
    jersey: 4,
    year: 'sr',
    rt: 92,
    potential_rt_ratcheted: 95,
    attributes: { SC: 7, SH: 8, ID: 4, OD: 7, PS: 9, BH: 8, RB: 3, ST: 4, AG: 7, ND: 6, IQ: 7, FT: 7 },
  },
  {
    player_id: 'scout-sg-02',
    position: 'SG',
    name: 'Chris Molina',
    jersey: 12,
    year: 'jr',
    rt: 84,
    potential_rt_ratcheted: 88,
    attributes: { SC: 9, SH: 9, ID: 3, OD: 6, PS: 5, BH: 6, RB: 4, ST: 4, AG: 7, ND: 5, IQ: 6, FT: 8 },
  },
  {
    player_id: 'scout-sf-03',
    position: 'SF',
    name: 'Devon Hale',
    jersey: 21,
    year: 'so',
    rt: 71,
    potential_rt_ratcheted: 78,
    attributes: { SC: 6, SH: 5, ID: 7, OD: 8, PS: 4, BH: 5, RB: 7, ST: 6, AG: 6, ND: 5, IQ: 5, FT: 6 },
  },
  {
    player_id: 'scout-pf-04',
    position: 'PF',
    name: 'Marcus Webb',
    jersey: 33,
    year: 'jr',
    rt: 55,
    potential_rt_ratcheted: 55,
    attributes: { SC: 4, SH: 3, ID: 6, OD: 5, PS: 3, BH: 3, RB: 8, ST: 8, AG: 4, ND: 7, IQ: 4, FT: 4 },
  },
  {
    player_id: 'scout-c-05',
    position: 'C',
    name: 'Tyler Boone',
    jersey: 50,
    year: 'fr',
    rt: 36,
    potential_rt_ratcheted: 52,
    attributes: { SC: 2, SH: 2, ID: 8, OD: 4, PS: 2, BH: 2, RB: 7, ST: 9, AG: 3, ND: 6, IQ: 3, FT: 3 },
  },
];

const PLAYER_SEASON_STATS = {
  'scout-pg-01': { PTS: 14.2, FGM: 5.1, FGA: 10.8, 'FG%': 47.2, MIN: 28.4, AST: 6.1, TREB: 3.2 },
  'scout-sg-02': { PTS: 18.6, FGM: 6.8, FGA: 14.1, 'FG%': 48.1, MIN: 31.0, AST: 2.4, TREB: 4.0 },
  'scout-sf-03': { PTS: 11.3, FGM: 4.2, FGA: 9.6, 'FG%': 43.8, MIN: 26.1, AST: 1.8, TREB: 5.6 },
  'scout-pf-04': { PTS: 9.8, FGM: 3.9, FGA: 8.2, 'FG%': 47.6, MIN: 24.5, AST: 1.1, TREB: 8.4 },
  'scout-c-05': { PTS: 6.4, FGM: 2.6, FGA: 5.1, 'FG%': 50.9, MIN: 18.2, AST: 0.7, TREB: 6.9 },
};

function cc(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 12,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: false,
    session_type: 'in-season',
    cut_required: false,
    rankings: [{ team_id: OPP, natl_rank: 6, W: 18, L: 4, name: 'Four Corners' }],
    next_game_summary: {
      week: 12,
      matchup_label: 'vs',
      opponent_team_id: OPP,
      opponent_team_name: 'Four Corners',
    },
  }, overrides || {});
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

// Counts scouting-report fetches, so a reopen can be distinguished from a first paint.
const fetches = { scouting: 0 };

async function installApi(page, opts) {
  const locked = opts && opts.locked;
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
      await fulfillJson(route, [
        { name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID },
        { name: 'Four Corners', display_name: 'Four Corners', object_id: OPP, _id: OPP },
      ]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.endsWith('/franchise/play-next-game')) {
      await fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four Corners',
        home_id: TID,
        away_id: OPP,
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data')) {
      await fulfillJson(route, {
        team_attributes: {
          offensive_efficiency: 6,
          defensive_efficiency: 4,
          fb_efficiency: 2,
          fb_opp_modifier: -8,
          pt_efficiency: 14,
          pt_opp_modifier: -2,
          discipline: 9,
          fight: 3,
          shot_threshold: 62,
          rebound_modifier: 48,
          team_chemistry: 18,
        },
        measures: MEASURES,
      });
      return;
    }
    if (pathname.startsWith('/franchise/scouting-report')) {
      fetches.scouting += 1;
      await fulfillJson(route, {
        projected_starting_five: PROJECTED,
        player_season_stats: PLAYER_SEASON_STATS,
        play_usage_unlocked: !locked,
        fast_break_usage_unlocked: !locked,
        hct_usage_unlocked: !locked,
        plays: locked ? [] : [
          { name: '4-1 Motion', times_run: 86, successes: 46 },
          { name: '5-0 Flex', times_run: 64, successes: 31 },
          { name: 'Horns Flare', times_run: 41, successes: 22 },
          { name: 'Double Drag', times_run: 28, successes: 11 },
        ],
        fast_break_plays: locked ? [] : [{ name: 'Pitch Ahead', times_run: 19, successes: 12 }],
        hct_trap_plays: [],
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openScouting(page, locked) {
  fetches.scouting = 0;
  await stubAuth(page);
  await installApi(page, { locked });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=scouting-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#scouting-view .opp-n', { timeout: 15000 });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('scouting view renders prep v2 layout', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);
  await expect(page.locator('#scouting-view .opp-n')).toHaveText('Four Corners');
  await expect(page.locator('#scouting-view .opp-rank-row').first()).toContainText('of 128');
  await expect(page.locator('#scouting-view .ms')).toHaveCount(8);
  await expect(page.locator('#scouting-view .agrid tbody tr')).toHaveCount(5);
  await expect(page.locator('#scouting-view .rtl b.rt-elite').first()).toBeVisible();
  await expect(page.locator('#scouting-hco-body tr')).toHaveCount(4);
  await expect(page.locator('#scouting-view .xt')).toHaveCount(0);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1280.png'), fullPage: true });
  await page.locator('#scouting-view [data-mode="stats"]').click();
  await page.screenshot({ path: path.join(OUT, 'scouting-stats-1280.png'), fullPage: true });
});

test('locked play usage shows N/A copy', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, true);
  await expect(page.locator('#scouting-hco-body')).toContainText('Film Study');
  await page.screenshot({ path: path.join(OUT, 'scouting-locked-1280.png'), fullPage: true });
});

test('scouting view at 1920', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openScouting(page, false);
  await page.screenshot({ path: path.join(OUT, 'scouting-attributes-1920.png'), fullPage: true });
});

test('projected five attribute values render, not zeros', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);

  const tiles = await page.locator('#scouting-view .agrid tbody .ad').allTextContents();
  expect(tiles.length).toBe(60);
  // The bug this guards: the server pre-divides by 10, the view divided again, and every
  // tile floored to 0. A grid of zeros and a grid of dashes are both failures.
  expect(tiles.every((text) => text.trim() === '0')).toBe(false);
  expect(tiles.some((text) => text.trim() === '—')).toBe(false);

  const firstRow = await page.locator('#scouting-view .agrid tbody tr').first()
    .locator('.ad').allTextContents();
  expect(firstRow.map((text) => text.trim()))
    .toEqual(['7', '8', '4', '7', '9', '8', '3', '4', '7', '6', '7', '7']);
});

test('opponent logo resolves to an image that loaded', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);

  const logo = await page.locator('#scouting-view .logo img').first().evaluate((img) => ({
    src: img.getAttribute('src'),
    naturalWidth: img.naturalWidth,
    width: Math.round(img.getBoundingClientRect().width),
  }));
  expect(logo.src).toBeTruthy();
  // A broken src still leaves an <img> in the DOM, so the check is that pixels arrived.
  expect(logo.naturalWidth).toBeGreaterThan(0);
  expect(logo.width).toBeGreaterThan(0);
});

test('section rhythm is one token at both densities', async ({ page }) => {
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openScouting(page, false);

    const gaps = await page.evaluate(() => {
      // Every top-level block, not just the <section>s: the opponent header and the
      // three-up play-usage group are part of the same vertical rhythm.
      const col = document.querySelector('#scouting-view .scouting-ready');
      const secs = Array.from(col.children)
        .filter((node) => node.getBoundingClientRect().height > 0);
      const out = [];
      for (let i = 1; i < secs.length; i += 1) {
        out.push(Math.round(secs[i].getBoundingClientRect().top
          - secs[i - 1].getBoundingClientRect().bottom));
      }
      return out;
    });
    expect(gaps.length).toBeGreaterThan(2);
    // One rhythm: every gap within a pixel of the first.
    gaps.forEach((gap) => { expect(Math.abs(gap - gaps[0])).toBeLessThanOrEqual(1); });
    // And no cramped stack.
    expect(gaps[0]).toBeGreaterThanOrEqual(20);
  }
});

test('reopening keeps the rendered panel up', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);
  await expect(page.locator('#scouting-view .agrid tbody tr')).toHaveCount(5);

  // Stamp the live table so a rebuilt one can be told from the one already on screen.
  await page.evaluate(() => {
    document.querySelector('#scouting-view .agrid tbody').dataset.stamp = 'first-paint';
  });

  // Sample every frame while leaving for another Prep tab and coming back.
  await page.evaluate(() => {
    window.__blankFrames = 0;
    window.__watching = true;
    const tick = () => {
      if (!window.__watching) return;
      const panel = document.getElementById('scouting-view');
      if (panel && !panel.hidden && getComputedStyle(panel).display !== 'none') {
        const ready = panel.querySelector('.scouting-ready');
        const rows = panel.querySelectorAll('.agrid tbody tr').length;
        if (!rows || (ready && ready.hidden)) window.__blankFrames += 1;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  await page.getByRole('tab', { name: 'Game Plan', exact: true }).click();
  await expect(page.locator('#scouting-view')).toBeHidden();
  await page.getByRole('tab', { name: 'Scouting Report', exact: true }).click();
  await page.waitForTimeout(800);

  const blankFrames = await page.evaluate(() => {
    window.__watching = false;
    return window.__blankFrames;
  });

  expect(blankFrames).toBe(0);
  await expect(page.locator('#scouting-view .agrid tbody tr')).toHaveCount(5);
  // The same table came back, so the panel was kept rather than re-rendered.
  await expect(page.locator('#scouting-view .agrid tbody')).toHaveAttribute('data-stamp', 'first-paint');
});

test('scouting uses the shared measure vocabulary', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);

  const view = page.locator('#scouting-view');
  for (const label of ['P/T Offense', 'P/T Defense', 'Fast Break', 'Fast Break Defense']) {
    await expect(view).toContainText(label);
  }
  for (const old of ['Press Break', 'Press/Trap Defense', 'Fast Break Offense']) {
    await expect(view).not.toContainText(old);
  }
});

test('scouting report screenshots for the polish batch', async ({ page }) => {
  const out = path.join(__dirname, '../../reports/polish-prep-train-scout');
  fs.mkdirSync(out, { recursive: true });
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openScouting(page, false);
    // Portraits 404 under the stub and fall back to initials via onerror. Shooting before
    // that settles catches empty badges, which is a property of the harness, not the view.
    await page.waitForFunction(() => {
      const badges = Array.from(document.querySelectorAll('#scouting-view .agrid .av'));
      return badges.length > 0 && badges.every((badge) => {
        const img = badge.querySelector('img');
        return img ? img.complete : badge.textContent.trim().length > 0;
      });
    }, null, { timeout: 15000 });
    await page.screenshot({
      path: path.join(out, 'scouting-report-' + size[0] + '.png'),
      fullPage: true,
    });
    // The shell scrolls internally, so the measures and play-usage sections need a
    // second frame to be looked at at all.
    await page.evaluate(() => {
      const sc = document.querySelector('#scouting-view .pv.sc').closest('[class*="scroll"], .tab-content')
        || document.scrollingElement;
      const target = document.querySelector('#scouting-view .cols3');
      if (target) target.scrollIntoView({ block: 'end' });
      else sc.scrollTop = sc.scrollHeight;
    });
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(out, 'scouting-report-lower-' + size[0] + '.png'),
      fullPage: true,
    });
  }
});

test('scouting does not fetch play-next-game before the report', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  fetches.scouting = 0;
  await stubAuth(page);
  await installApi(page, { locked: false });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=training-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#training-view .training-container, #training-view .pdg-grid, #training-view .devfocus-select', {
    timeout: 15000,
  });

  const timeline = [];
  page.on('request', (req) => {
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (err) { return; }
    if (
      pathname.endsWith('/franchise/play-next-game')
      || pathname.endsWith('/franchise/team-data')
      || pathname.endsWith('/franchise/scouting-report')
    ) {
      timeline.push({ t: Date.now(), method: req.method(), path: pathname });
    }
  });

  await page.getByRole('tab', { name: 'Scouting Report', exact: true }).click();
  await page.waitForSelector('#scouting-view .opp-n', { timeout: 15000 });

  const opponentPosts = timeline.filter((row) => row.path.endsWith('/franchise/play-next-game'));
  const report = timeline.find((row) => row.path.endsWith('/franchise/scouting-report'));
  const teamData = timeline.find((row) => row.path.endsWith('/franchise/team-data'));
  expect(opponentPosts).toEqual([]);
  if (report && teamData) {
    expect(Math.abs(report.t - teamData.t)).toBeLessThan(80);
  }
  await expect(page.locator('#scouting-view .opp-n')).toHaveText('Four Corners');
});

test('prep sub-tabs: Player Training is named and ordered last', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openScouting(page, false);

  const labels = await page.getByRole('tab').filter({ hasNotText: /^$/ })
    .evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));
  const prep = labels.filter((label) => ['Game Plan', 'Playbooks', 'Scouting Report',
    'Player Training', 'Training'].includes(label));
  expect(prep).toEqual(['Game Plan', 'Playbooks', 'Scouting Report', 'Player Training']);

  // The Advance week-flow targets the view id, which the rename left alone.
  await page.getByRole('tab', { name: 'Player Training', exact: true }).click();
  await expect(page.locator('#training-view')).toBeVisible();

  const out = path.join(__dirname, '../../reports/polish-prep-train-scout');
  fs.mkdirSync(out, { recursive: true });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(out, 'player-training-tabs-1280.png'), fullPage: true });
});
