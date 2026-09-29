// @ts-check
/**
 * Home Base, offline (desktop profile). Covers the "Your Career" right zone:
 * career numerals (hollow when nothing is earned), the Trophy Case shelf (gold
 * title medallions, neutral milestones, dashed empty slots), and Top Seasons in
 * the server's order. The hard rules: zero community/auth requests, reward gold
 * only on title medallions and title finishes, and nothing below the fold at
 * 1280x720 and 1920x1080 in both the zero and populated states.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const REWARD_GOLD = 'rgb(240, 197, 96)'; // --reward-gold #F0C560

// Any request to a community or auth host must never fire on desktop.
const FORBIDDEN = [
  '/api/community/',
  '/api/auth/leaderboard',
  '/api/leaderboard/',
  '/api/auth/me',
];

function forbidden(url) {
  let pathname = '';
  try { pathname = new URL(url).pathname; } catch (_err) { return null; }
  return FORBIDDEN.find((p) => pathname === p || pathname.startsWith(p)) || null;
}

function franchise(id, slot, name, week) {
  return {
    franchise_id: id,
    home_slot: slot,
    user_team_id: name,
    user_team_object_id: 'obj-' + id,
    week: week,
    current_season: 3,
    primary_color: '#27408e',
    secondary_color: '#15181f',
    last_played_at: '2026-09-2' + slot + 'T10:00:00Z',
  };
}

function coachCareerZero() {
  return {
    user_id: 'local-desktop-user',
    username: 'Coach',
    record: { wins: 0, losses: 0, total_games: 0, win_rate: 0 },
    championships_total: { conf_rs: 0, conf_t: 0, region: 0, national: 0 },
    titles_total: 0,
    win_pct_display: null,
    geek_points: 0,
    seasons_completed: 0,
    programs: 0,
    trophies: [],
    top_seasons: [],
  };
}

function trophy(kind, season, team, fid) {
  return { kind: kind, season: season, team_name: team, franchise_id: fid, team_id: 't-' + fid };
}

function topSeason(fid, team, slug, season, wins, losses, finish, isTitle, gp, inProgress, week) {
  return {
    franchise_id: fid, team_name: team, team_slug: slug, season: season,
    wins: wins, losses: losses, finish: finish, finish_is_title: isTitle,
    season_gp: gp, in_progress: inProgress, week: week,
  };
}

function coachCareerPopulated() {
  return {
    user_id: 'local-desktop-user',
    username: 'Coach',
    record: { wins: 73, losses: 22, total_games: 95, win_rate: 77 },
    championships_total: { conf_rs: 1, conf_t: 1, region: 1, national: 0 },
    titles_total: 3,
    win_pct_display: '.770',
    geek_points: 4060,
    seasons_completed: 4,
    programs: 2,
    // Newest-first, mixed kinds. All-Americans and season records are NOT shelf
    // medallions and must be filtered out; three titles + two milestones remain.
    trophies: [
      trophy('national', 2, 'Lawrence Eagles', 'f1'),
      trophy('region', 2, 'Lawrence Eagles', 'f1'),
      trophy('all_american_1', 2, 'Lawrence Eagles', 'f1'),
      trophy('season_record', 2, 'Lawrence Eagles', 'f1'),
      trophy('conf_t', 1, 'Lawrence Eagles', 'f1'),
      trophy('milestone_first_signing_class', 1, 'Lawrence Eagles', 'f1'),
      trophy('milestone_first_bracket', 1, 'Lawrence Eagles', 'f1'),
    ],
    // Server order (already ranked by season GP desc): a title finish, a title
    // finish, a NON-title completed finish, then an in-progress season.
    top_seasons: [
      topSeason('f1', 'Lawrence Eagles', 'lawrence', 2, 31, 5, 'National champions', true, 1860, false, null),
      topSeason('f1', 'Lawrence Eagles', 'lawrence', 1, 22, 10, 'Conference champions', true, 1120, false, null),
      topSeason('f1', 'Lawrence Eagles', 'lawrence', 4, 24, 8, 'National semifinal', false, 980, false, null),
      topSeason('f2', 'Chapel Hill Sky', 'chapel_hill', 1, 4, 2, null, false, 140, true, 6),
    ],
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {{state?: 'zero'|'populated', programs?: number, width?: number, height?: number}} [opts]
 * @returns {Promise<string[]>} forbidden host paths that were requested (must stay empty)
 */
async function openOffline(page, opts) {
  opts = opts || {};
  const programs = opts.programs == null ? 2 : opts.programs;
  const width = opts.width || 1280;
  const height = opts.height || 720;
  const career = opts.state === 'zero' ? coachCareerZero() : coachCareerPopulated();

  const seen = [];
  page.on('request', (req) => {
    const hit = forbidden(req.url());
    if (hit) seen.push(hit);
  });

  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);

  const list = [];
  const names = ['Lawrence Eagles', 'Chapel Hill Sky'];
  for (let i = 0; i < programs; i += 1) list.push(franchise('f' + (i + 1), i + 1, names[i], 14 - i));

  // Loopback routes (a /franchise route is routable + local -> loopback on desktop).
  await page.route('**/franchise/list', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ franchises: list, count: list.length, max: 2, most_recent_franchise_id: programs ? 'f1' : null }),
  }));
  await page.route('**/teams', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(list.map((f) => ({ object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9 }))),
  }));
  await page.route('**/franchise/command-center/data**', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ current_season: 3, week: 14 }),
  }));
  await page.route('**/franchise/coach-career', (r) => r.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(career),
  }));

  await page.setViewportSize({ width: width, height: height });
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('[data-hb-right-offline]')).toBeVisible();
  return seen;
}

/** No scrollbar AND no zone clipped. overflow:hidden hides run-off, so every
 *  zone's own box is measured, including the offline "Your Career" pieces. */
async function expectNothingBelowTheFold(page) {
  const result = await page.evaluate(() => {
    const clipped = [];
    const zones = '.hb-top, .door, .vacant, .hb-util, .cr-n, .cr-cap, .tcase, .shelf, .tsn-l, .tsn, .sec-h';
    document.querySelectorAll(zones).forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.height === 0 && r.width === 0) return;
      if (r.bottom > window.innerHeight + 1 || r.right > window.innerWidth + 1 || r.top < -1) {
        clipped.push(`${el.className} bottom=${Math.round(r.bottom)} right=${Math.round(r.right)}`);
      }
    });
    return {
      v: document.documentElement.scrollHeight - window.innerHeight,
      h: document.documentElement.scrollWidth - window.innerWidth,
      clipped,
    };
  });
  expect(result.clipped, 'content outside the viewport:\n' + result.clipped.join('\n')).toEqual([]);
  expect(result.v, 'vertical overflow px').toBeLessThanOrEqual(0);
  expect(result.h, 'horizontal overflow px').toBeLessThanOrEqual(0);
}

test.describe('offline guard', () => {
  test('the zone makes zero community or auth requests', async ({ page }) => {
    const seen = await openOffline(page, { state: 'populated' });
    // Well past the online Around GOB poll window; nothing offline should fire.
    await page.waitForTimeout(500);
    expect(seen, JSON.stringify(seen)).toEqual([]);
    // And no online right-zone chrome leaked in.
    await expect(page.locator('.hbt')).toHaveCount(0);
    await expect(page.locator('.fag')).toHaveCount(0);
    await expect(page.locator('[data-hb-career]')).toHaveCount(0); // no left-zone strip
  });
});

test.describe('zero state', () => {
  test('numerals are hollow, medallion slots are dashed, 5 dashed ranks', async ({ page }) => {
    await openOffline(page, { state: 'zero' });

    // Four numerals, all hollow.
    await expect(page.locator('.cr .cr-n > div')).toHaveCount(4);
    await expect(page.locator('.cr .cr-n .hollow')).toHaveCount(4);
    await expect(page.locator('.cr .cr-n > div').first().locator('span')).toHaveText('Career record');

    // The caption only shows in the zero state.
    await expect(page.locator('.cr-cap')).toHaveText('Every game you coach, in any program, adds to these.');

    // Trophy Case: four labelled dashed slots, no earned medallions.
    await expect(page.locator('.shelf .tro.slot-e')).toHaveCount(4);
    await expect(page.locator('.tro:not(.slot-e)')).toHaveCount(0);
    await expect(page.locator('.tro.slot-e .med').first()).toHaveText('C');
    const labels = await page.locator('.tro.slot-e div b').allTextContents();
    expect(labels).toEqual(['Conference', 'Region', 'National', 'First signing class']);
    await expect(page.locator('.tcase .sec-h > span')).toHaveText('Still to win');

    // Top Seasons: five dashed ranks, the first carries the first-game copy.
    await expect(page.locator('.tsn.is-e')).toHaveCount(5);
    await expect(page.locator('.tsn:not(.is-e)')).toHaveCount(0);
    await expect(page.locator('.tsn.is-e').first().locator('span'))
      .toHaveText('Coach your first game and your season ranks here');

    await expectNothingBelowTheFold(page);
  });
});

test.describe('populated state', () => {
  test('numerals are solid and read the server values', async ({ page }) => {
    await openOffline(page, { state: 'populated' });
    const cells = page.locator('.cr .cr-n > div');
    await expect(cells).toHaveCount(4);
    await expect(page.locator('.cr .cr-n .hollow')).toHaveCount(0);
    await expect(cells.nth(0).locator('b')).toHaveText('73–22');
    await expect(cells.nth(0).locator('span')).toHaveText('Career record · .770');
    await expect(cells.nth(1).locator('b')).toHaveText('3'); // titles_total, no client math
    await expect(cells.nth(2).locator('b')).toHaveText('4');
    await expect(cells.nth(3).locator('b')).toHaveText('4,060');
    await expectNothingBelowTheFold(page);
  });

  test('reward gold sits only on title medallions and title finishes', async ({ page }) => {
    await openOffline(page, { state: 'populated' });

    // Three gold title medallions, two neutral milestone medallions.
    await expect(page.locator('.shelf .med.gold')).toHaveCount(3);
    await expect(page.locator('.shelf .med.ms')).toHaveCount(2);
    await expect(page.locator('.tcase .sec-h > span')).toHaveText('3 titles · 2 milestones');

    // Assert the computed colour: gold medallions are reward gold, milestones are not.
    const goldColor = await page.locator('.med.gold').first().evaluate((el) => getComputedStyle(el).color);
    expect(goldColor).toBe(REWARD_GOLD);
    const msColor = await page.locator('.med.ms').first().evaluate((el) => getComputedStyle(el).color);
    expect(msColor).not.toBe(REWARD_GOLD);

    // Medallion letters and labels.
    const letters = await page.locator('.shelf .med').allTextContents();
    expect(letters).toEqual(['N', 'R', 'C', 'S', 'B']); // titles first, then milestones
    await expect(page.locator('.tro').filter({ hasText: 'First signing class' }).locator('.med')).toHaveText('S');

    // Title finishes are gold; the non-title finish is not.
    await expect(page.locator('.tsn-f.gold-t')).toHaveCount(2);
    const finishGold = await page.locator('.tsn-f.gold-t').first().evaluate((el) => getComputedStyle(el).color);
    expect(finishGold).toBe(REWARD_GOLD);
    const semi = page.locator('.tsn-f').filter({ hasText: 'National semifinal' });
    await expect(semi).not.toHaveClass(/gold-t/);
    const semiColor = await semi.evaluate((el) => getComputedStyle(el).color);
    expect(semiColor).not.toBe(REWARD_GOLD);
  });

  test('Top Seasons keeps server order and marks the in-progress season', async ({ page }) => {
    await openOffline(page, { state: 'populated' });
    const rows = page.locator('.tsn:not(.is-e)');
    await expect(rows).toHaveCount(4);
    // Server order preserved: GP 1,860 / 1,120 / 980 / 140.
    const gp = await page.locator('.tsn:not(.is-e) .tsn-g').allTextContents();
    expect(gp.map((t) => t.replace(/GP$/, '').trim())).toEqual(['1,860', '1,120', '980', '140']);
    // The in-progress season shows its week, not a finish.
    await expect(page.locator('.tsn-f .ip')).toHaveText('In progress · Week 6');
    await expect(rows.nth(3).locator('.tsn-n b')).toHaveText('Chapel Hill Sky');
    // One rank remains, dashed, with the next-season copy.
    await expect(page.locator('.tsn.is-e')).toHaveCount(1);
    await expect(page.locator('.tsn.is-e span')).toHaveText('Your next season can land here');
    await expectNothingBelowTheFold(page);
  });

  test('the Trophy Case View all link routes to the standalone page', async ({ page }) => {
    await openOffline(page, { state: 'populated' });
    const link = page.locator('[data-hb-trophy-case]');
    await expect(link).toBeVisible();
    await expect(link).toHaveText('View all');
    await expect(link).toHaveAttribute('href', '/trophy-case.html');
  });
});

test.describe('fit', () => {
  for (const state of ['zero', 'populated']) {
    for (const [w, h] of [[1280, 720], [1920, 1080]]) {
      test(`${state} fits ${w}x${h}`, async ({ page }) => {
        await openOffline(page, { state: /** @type {'zero'|'populated'} */ (state), width: w, height: h });
        await expectNothingBelowTheFold(page);
      });
    }
  }
});

test.describe('screenshots', () => {
  const shots = [
    ['first-1280', { state: 'zero', programs: 0, width: 1280, height: 720 }],
    ['two-1280', { state: 'populated', programs: 2, width: 1280, height: 720 }],
    ['two-1920', { state: 'populated', programs: 2, width: 1920, height: 1080 }],
    ['populated-1280', { state: 'populated', programs: 2, width: 1280, height: 720 }],
  ];
  for (const [name, opts] of shots) {
    test(`capture ${name}`, async ({ page }) => {
      await openOffline(page, /** @type {any} */ (opts));
      await page.mouse.move(4, 4);
      await page.screenshot({ path: `reports/home-base-offline/${name}.png` });
    });
  }

  // The online left-zone career strip, to confirm titles_total leaves it unchanged.
  test('capture online-strip-1280', async ({ page }) => {
    await stubAuth(page);
    await page.route('**/api/auth/me', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
    }));
    const list = [franchise('f1', 1, 'Bentley-Truman', 14), franchise('f2', 2, 'Ocean City', 13)];
    await page.route('**/franchise/list', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ franchises: list, count: 2, max: 2, most_recent_franchise_id: 'f2' }),
    }));
    await page.route('**/teams', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(list.map((f) => ({ object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9 }))),
    }));
    await page.route('**/franchise/command-center/data**', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ current_season: 3, week: 14 }),
    }));
    await page.route('**/api/community/around-the-league', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ slots: [] }),
    }));
    await page.route('**/api/auth/leaderboard', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ top: [], current_user: null, titles_top: [], titles_current_user: null }),
    }));
    await page.route('**/franchise/coach-career', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(coachCareerPopulated()),
    }));
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/mode-select.html');
    await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
    await expect(page.locator('[data-hb-career]')).toBeVisible();
    // titles_total = 3 shows verbatim on the strip.
    await expect(page.locator('[data-hb-career] .cr-n > div').nth(1).locator('b')).toHaveText('3');
    await page.mouse.move(4, 4);
    await page.screenshot({ path: 'reports/home-base-offline/online-strip-1280.png' });
  });
});
