// @ts-check
/**
 * Season-peak takeover (.pk / .rv) and the Trophy Case page.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const FID = 'f-e2e-peak';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SHOTS = path.join(__dirname, '../../reports/season-peak-trophy-case');
const GREEN = ['rgb(52, 236, 39)', 'rgb(43, 214, 106)', '#34ec27', '#2bd66a', '#34EC27'];
const FORBIDDEN = ['/api/community/', '/api/auth/leaderboard', '/api/leaderboard/', '/api/auth/me'];

function digest() {
  return {
    state: 'regular',
    what_moved: {
      national_rank: { now: 1, prev: 3, delta: 2 },
      conference_standing: { now: 1, prev: 2, delta: 1 },
      record: { wins: 31, losses: 5 },
      streak: 'W4',
      attribute_changes: [],
    },
    team_snapshot: { state: 'ready', chemistry: { value: 20, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: {
      week: 34, user_won: true, site: 'neutral', home_score: 72, away_score: 66,
      home_team_name: 'Lancaster', away_team_name: 'Harbor City',
      opponent_team_name: 'Harbor City', opponent_rank: 2,
      leader_role: 'potg', leader: { name: 'Devin Park', stats: { pts: 24 } },
      box_score: { path: '/box-score.html', params: {} },
    },
    next_game: null,
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [],
    recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 },
    signing_day: null,
    season_preview: null,
    weekly_card_items: [],
  };
}

function champItem() {
  return {
    id: 'championship', kind: 'championship', tier: 'SEASON_PEAK',
    priority: 10, payload_ref: 'pending_championship_moments',
    seen_key: 'pending_championship_moments', title: 'Championship moment',
    line: 'A title moment is waiting.', style: 'gold',
    sting: 'STING_SEASON_PEAK', duration: 'long',
  };
}

function reviewItem() {
  return {
    id: 'season_review', kind: 'season_review', tier: 'SEASON_PEAK',
    priority: 15, payload_ref: 'season_review',
    seen_key: 'season_review_seen_season', title: 'Season review',
    line: 'Your season, start to finish.', style: 'gold',
    sting: 'STING_SEASON_PEAK', duration: 'long',
  };
}

function championships() {
  return [
    {
      id: 'cm-nat', type: 'national_championship', season: 2,
      winner_team_name: 'Lancaster', winner_primary_color: '#27408E',
      loser_team_name: 'Harbor City', score: { winner: 72, loser: 66 },
      game_id: 'g-nat', user_is_winner: true,
    },
    {
      id: 'cm-reg', type: 'region_championship', season: 2,
      winner_team_name: 'Lancaster', winner_primary_color: '#27408E',
      loser_team_name: 'Maple Ridge', score: { winner: 70, loser: 64 },
      game_id: 'g-reg', user_is_winner: true, region: 'B',
    },
    {
      id: 'cm-conf', type: 'conference_championship', season: 2,
      winner_team_name: 'Lancaster', winner_primary_color: '#27408E',
      loser_team_name: 'Four Corners', score: { winner: 78, loser: 71 },
      game_id: 'g-conf', user_is_winner: true, conference: 'A2',
    },
  ];
}

function seasonReviewPayload() {
  return {
    eligible: true, season: 2, national_rank: 1, season_gp: 1860,
    wins: 31, losses: 5, conf_finish: 1,
    titles: [
      { kind: 'national', season: 2, team_name: 'Lancaster' },
      { kind: 'region', season: 2, team_name: 'Lancaster' },
      { kind: 'conf_t', season: 2, team_name: 'Lancaster' },
    ],
    best_players: [
      { name: 'Devin Park', position: 'PG', class_year: 'JR', all_american: 'all_american_1', stats: { ppg: 18.9, apg: 6.1, rpg: 4.4 } },
      { name: 'Isaiah Monroe', position: 'SF', class_year: 'SO', all_american: 'all_american_3', stats: { ppg: 15.2, rpg: 7.0, spg: 1.3 } },
      { name: 'Silas Kerr', position: 'C', class_year: 'SR', stats: { ppg: 11.8, rpg: 9.6 } },
    ],
    class_signed: [
      { name: 'Jordan Price', position: 'PG', home_region: 'B', rt_now: 71, rt_potential: 84 },
      { name: 'Malik Stone', position: 'SF', home_region: 'B', rt_now: 64, rt_potential: 78 },
    ],
  };
}

function cc(flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 36,
    season: 2,
    current_season: 2,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 36, counts: {} },
    office_digest: digest(),
    pending_championship_moments: [],
    moments: [],
    moments_for_this_visit: [],
    weekly_card_items: [],
    team_name_map: { [TID]: 'Lancaster' },
  }, flags || {});
}

function visitTitleAndReview() {
  const moments = [champItem(), reviewItem()];
  return cc({
    pending_championship_moments: championships(),
    season_review: seasonReviewPayload(),
    moments,
    moments_for_this_visit: moments,
  });
}

function visitTitleOnly() {
  const moments = [champItem()];
  return cc({
    pending_championship_moments: championships(),
    moments,
    moments_for_this_visit: moments,
  });
}

function visitReviewOnly() {
  const moments = [reviewItem()];
  return cc({
    season_review: seasonReviewPayload(),
    moments,
    moments_for_this_visit: moments,
  });
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data, seen) {
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(function () {});
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
    if (seen && (request.method() === 'PATCH' || request.method() === 'POST')) {
      seen.push({ path: pathname, method: request.method() });
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, {
        user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com',
        lead_archetype: 'pure_offense', archetype_reveal_seen: true,
      });
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
    if (pathname === '/franchise/championship-moments/dismiss') {
      await fulfillJson(route, { ok: true });
      return;
    }
    if (pathname === '/franchise/season-review-seen') {
      await fulfillJson(route, { ok: true });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openOffice(page, data, seen) {
  await stubAuth(page);
  await installApi(page, data, seen);
  await page.addInitScript(() => { window.__gobSeasonPeakSfx = []; });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
}

function coachCareerEmpty() {
  return {
    user_id: 'e2e-user', username: 'Coach',
    record: { wins: 0, losses: 0, total_games: 0, win_rate: 0 },
    championships_total: { conf_rs: 0, conf_t: 0, region: 0, national: 0 },
    titles_total: 0, win_pct_display: null, geek_points: 0,
    seasons_completed: 0, programs: 0, trophies: [], top_seasons: [],
  };
}

function seasonRecord(season, team, fid, wins, losses, extra) {
  return Object.assign({
    kind: 'season_record', season: season, team_name: team, franchise_id: fid, team_id: 't-' + fid,
    detail: Object.assign({
      wins: wins, losses: losses, national_rank: 1, conf_finish: 1,
      best_players: seasonReviewPayload().best_players,
      class_signed: seasonReviewPayload().class_signed,
    }, extra || {}),
  });
}

function coachCareerPopulated() {
  return {
    user_id: 'e2e-user', username: 'Coach Demo',
    record: { wins: 73, losses: 22, total_games: 95, win_rate: 77 },
    championships_total: { conf_rs: 0, conf_t: 1, region: 1, national: 1 },
    titles_total: 3, win_pct_display: '.770', geek_points: 4060,
    seasons_completed: 4, programs: 2,
    trophies: [
      { kind: 'national', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'region', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'conf_t', season: 1, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'milestone_first_signing_class', season: 1, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'milestone_first_archetype', season: 1, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      seasonRecord(2, 'Lawrence Eagles', 'f1', 31, 5),
      seasonRecord(1, 'Lawrence Eagles', 'f1', 22, 10, { national_rank: 18, conf_finish: 1 }),
    ],
    top_seasons: [
      { franchise_id: 'f1', team_name: 'Lawrence Eagles', season: 3, wins: 16, losses: 5, in_progress: true, week: 14 },
      { franchise_id: 'f2', team_name: 'Chapel Hill Sky', season: 1, wins: 4, losses: 2, in_progress: true, week: 6 },
    ],
  };
}

async function installTrophyApi(page, career, extra) {
  extra = extra || {};
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(function () {});
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/franchise/coach-career') {
      await fulfillJson(route, career);
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/api/auth/me') {
      if (extra.desktop) {
        await route.abort();
        return;
      }
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' });
      return;
    }
    await fulfillJson(route, extra.desktop ? {} : {});
  });
}

async function openTrophyCase(page, career, opts) {
  opts = opts || {};
  if (opts.desktop) await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await installTrophyApi(page, career, opts);
  await page.setViewportSize({ width: opts.width || 1280, height: opts.height || 720 });
  await page.goto('/trophy-case.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.tc-head h1')).toContainText('Trophy Case');
}

async function colorsOf(page, selector) {
  return page.evaluate((sel) => {
    const goldProbe = document.createElement('span');
    goldProbe.style.color = 'var(--reward-gold)';
    document.body.appendChild(goldProbe);
    const gold = getComputedStyle(goldProbe).color;
    goldProbe.remove();
    const root = document.querySelector(sel);
    if (!root) return { gold: gold, hits: [] };
    const hits = [];
    const walk = (el) => {
      const cs = getComputedStyle(el);
      ['color', 'backgroundColor', 'borderTopColor', 'borderBottomColor'].forEach((prop) => {
        hits.push({ prop: prop, value: cs[prop], cls: el.className });
      });
      Array.from(el.children || []).forEach(walk);
    };
    walk(root);
    return { gold: gold, hits: hits };
  }, selector);
}

function isGreen(value) {
  const v = String(value || '').replace(/\s/g, '').toLowerCase();
  return GREEN.some((g) => v === g.replace(/\s/g, '').toLowerCase());
}

test.describe('season peak title', () => {
  test.beforeAll(() => {
    fs.mkdirSync(SHOTS, { recursive: true });
  });

  test('title takeover is gold-only in the allowed places, no green, one sting', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const seen = [];
    await openOffice(page, visitTitleOnly(), seen);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect(pk.locator('.pk-t')).toContainText('National Champions');
    await expect(pk.locator('.pk-score')).toContainText('72');
    await expect(pk.locator('.pk-score')).toContainText('66');
    await expect(pk.locator('.med.gold')).toHaveCount(3);
    await expect(pk.locator('.cf i')).toHaveCount(60);
    await expect(pk.locator('.cf i.g, .cf i.w, .cf i.d')).toHaveCount(60);
    await expect(pk.locator('.btn-ghost.lg')).toBeVisible();
    await expect(pk.getByText('Trophy Case')).toBeVisible();
    await page.waitForTimeout(700);
    const sfx = await page.evaluate(() => window.__gobSeasonPeakSfx || []);
    expect(sfx.filter((n) => n === 'STING_SEASON_PEAK')).toHaveLength(1);

    const info = await colorsOf(page, '.pk');
    const goldBits = (info.gold.match(/\d+/g) || []).join(',');
    const rule = await page.evaluate(() => getComputedStyle(document.querySelector('.pk-rule')).backgroundImage);
    expect(rule.replace(/\s/g, '')).toContain(goldBits);
    const em = await page.evaluate(() => getComputedStyle(document.querySelector('.pk-f em')).color);
    expect(em).toBe(info.gold);
    const med = await page.evaluate(() => getComputedStyle(document.querySelector('.med.gold')).color);
    expect(med).toBe(info.gold);
    const btnBg = await page.evaluate(() => getComputedStyle(document.querySelector('.pk .btn-ghost')).backgroundColor);
    expect(btnBg).not.toBe(info.gold);
    info.hits.forEach((h) => expect(isGreen(h.value), h.cls + ' ' + h.prop).toBe(false));

    await pk.locator('.pk-go').click();
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(3);

    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitTitleOnly());
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.pk-f')).toBeVisible();
    await page.waitForTimeout(1600);
    await page.screenshot({ path: path.join(SHOTS, 'peak-title-1280.png') });
  });

  test('title at 1920', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await openOffice(page, visitTitleOnly());
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.pk-f')).toBeVisible();
    await page.waitForTimeout(1600);
    await page.screenshot({ path: path.join(SHOTS, 'peak-title-1920.png') });
  });

  test('reduced motion draws no confetti and still plays the sting', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitTitleOnly());
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.pk .cf i')).toHaveCount(0);
    await page.waitForTimeout(700);
    const sfx = await page.evaluate(() => window.__gobSeasonPeakSfx || []);
    expect(sfx.filter((n) => n === 'STING_SEASON_PEAK')).toHaveLength(1);
  });
});

test.describe('season peak review', () => {
  test('title then review is 1 of 2 / 2 of 2 and PATCHes season-review-seen', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const seen = [];
    await openOffice(page, visitTitleAndReview(), seen);
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.pk .mq')).toContainText('1 of 2');
    await expect(page.locator('.rv.is-open')).toHaveCount(0);
    await page.locator('.pk-go').click();
    await expect(page.locator('.rv.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.rv .mq')).toContainText('2 of 2');
    await expect(page.locator('.rv-rec')).toContainText('31–5');
    await expect(page.locator('.rv-fin')).toContainText('#1');
    await expect(page.locator('.rv-fin')).toContainText('1st');
    await expect(page.getByText('1 seed')).toHaveCount(0);
    await expect(page.locator('.rv-t .tro')).toHaveCount(3);
    await expect(page.locator('.bp')).toHaveCount(3);
    await expect(page.locator('.aw')).toHaveCount(2);
    await expect(page.locator('.rv .rc')).toHaveCount(2);
    await expect(page.locator('.rv-f em')).toHaveText('Trophy Case');
    await expect.poll(() => page.evaluate(() => (window.__gobSeasonPeakSfx || []).filter((n) => n === 'STING_SEASON_PEAK').length)).toBe(1);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOTS, 'peak-review-1280.png') });
    const reviewShots = path.join(__dirname, '../../reports/review-record');
    fs.mkdirSync(reviewShots, { recursive: true });
    await page.screenshot({ path: path.join(reviewShots, 'peak-review-1280.png') });
    await page.locator('.rv-go').click();
    await expect(page.locator('.rv.is-open')).toHaveCount(0);
    expect(seen.some((s) => s.path.indexOf('season-review-seen') !== -1)).toBe(true);
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(3);
  });

  test('review at 1920', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await openOffice(page, visitTitleAndReview());
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await page.locator('.pk-go').click();
    await expect(page.locator('.rv.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.rv-f')).toBeVisible();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOTS, 'peak-review-1920.png') });
  });

  test('review alone works and PATCHes', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const seen = [];
    await openOffice(page, visitReviewOnly(), seen);
    await expect(page.locator('.pk')).toHaveCount(0);
    await expect(page.locator('.rv.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.rv .mq')).toHaveCount(0);
    await expect(page.locator('.rv-rec')).toContainText('31–5');
    await expect(page.locator('.rv-fin')).toContainText('1st');
    await expect(page.locator('.rv-t .tro')).toHaveCount(3);
    await page.locator('.rv-go').click();
    expect(seen.some((s) => s.path.indexOf('season-review-seen') !== -1)).toBe(true);
  });

  test('live review titles come from season trophies, not visit championships', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const data = visitTitleAndReview();
    const payload = Object.assign({}, data.season_review);
    delete payload.titles;
    data.season_review = payload;
    await openOffice(page, data);
    await expect(page.locator('.pk.is-open')).toBeVisible({ timeout: 15000 });
    await page.locator('.pk-go').click();
    await expect(page.locator('.rv.is-open')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.rv-t .tro')).toHaveCount(0);
    await expect(page.locator('.rv-rec')).toContainText('31–5');
  });
});

test.describe('trophy case', () => {
  test('populated and empty states, gold only on title medallions', async ({ page }) => {
    await openTrophyCase(page, coachCareerPopulated());
    await expect(page.locator('.cn').nth(0)).toContainText('73–22');
    await expect(page.locator('.med.gold.lg')).toHaveCount(3);
    await expect(page.locator('.med.ms')).toHaveCount(2);
    await expect(page.locator('[data-tc-review]')).toHaveCount(2);
    const gold = await page.evaluate(() => {
      const host = document.querySelector('.gob') || document.body;
      const p = document.createElement('span');
      p.style.color = 'var(--reward-gold)';
      host.appendChild(p);
      const g = getComputedStyle(p).color;
      p.remove();
      const title = getComputedStyle(document.querySelector('.tc .med.gold')).color;
      const mile = getComputedStyle(document.querySelector('.tc .med.ms')).color;
      return { g: g, title: title, mile: mile };
    });
    expect(gold.title).toBe(gold.g);
    expect(gold.mile).not.toBe(gold.g);
    await page.screenshot({ path: path.join(SHOTS, 'trophy-case-populated-1280.png') });

    await page.setViewportSize({ width: 1920, height: 1080 });
    await openTrophyCase(page, coachCareerPopulated(), { width: 1920, height: 1080 });
    await page.screenshot({ path: path.join(SHOTS, 'trophy-case-populated-1920.png') });

    await page.setViewportSize({ width: 1280, height: 720 });
    await openTrophyCase(page, coachCareerEmpty());
    await expect(page.locator('.shelf.is-empty')).toBeVisible();
    await expect(page.locator('.tc-empty')).toHaveCount(2);
    await page.screenshot({ path: path.join(SHOTS, 'trophy-case-empty-1280.png') });
  });

  test('desktop profile hits only coach-career', async ({ page }) => {
    const forbidden = [];
    page.on('request', (req) => {
      let pathname = '';
      try { pathname = new URL(req.url()).pathname; } catch (e) { return; }
      if (FORBIDDEN.find((p) => pathname === p || pathname.startsWith(p))) forbidden.push(pathname);
    });
    await openTrophyCase(page, coachCareerPopulated(), { desktop: true });
    await expect(page.locator('.hb-conn.off')).toBeVisible();
    expect(forbidden).toEqual([]);
    await page.screenshot({ path: path.join(SHOTS, 'trophy-case-desktop-1280.png') });
  });

  test('Review opens the stored snapshot', async ({ page }) => {
    await openTrophyCase(page, coachCareerPopulated());
    await page.locator('[data-tc-review]').first().click();
    await expect(page.locator('.rv.is-open')).toBeVisible();
    await expect(page.locator('.rv .mq')).toHaveCount(0);
    await expect(page.locator('.rv-rec')).toContainText('31–5');
    await expect(page.locator('.rv-fin')).toContainText('#1');
    await expect(page.getByText('1 seed')).toHaveCount(0);
    await expect(page.locator('.rv-f')).toBeVisible();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOTS, 'review-from-trophy-case-1280.png') });
    await page.locator('.rv-go').click();
    await expect(page.locator('.rv.is-open')).toHaveCount(0);
  });

  test('Home Base links route to the Trophy Case', async ({ page }) => {
    await stubAuth(page);
    await page.route('**/api/auth/me', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
    }));
    await page.route('**/franchise/list', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        franchises: [{
          franchise_id: 'f1', home_slot: 1, user_team_id: 'Lancaster',
          user_team_object_id: TID, week: 14, current_season: 3,
          primary_color: '#27408e', secondary_color: '#15181f',
          last_played_at: '2026-09-21T10:00:00Z',
        }],
        count: 1, max: 2, most_recent_franchise_id: 'f1',
      }),
    }));
    await page.route('**/franchise/coach-career', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(coachCareerPopulated()),
    }));
    await page.route('**/teams', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify([{ object_id: TID, name: 'Lancaster', natl_rank: 9 }]),
    }));
    await page.route('**/franchise/command-center/data**', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ current_season: 3, week: 14 }),
    }));
    await page.route('**/api/community/around-the-league', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ slots: [] }),
    }));
    await page.route('**/api/auth/leaderboard', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ top: [], current_user: { rank: 1, username: 'e2e', geek_points: 0 } }),
    }));
    await page.route('**/app-config', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ isAlpha: false }),
    }));
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/mode-select.html');
    await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
    const link = page.locator('[data-hb-trophy-case]').first();
    await expect(link).toBeVisible({ timeout: 15000 });
    await expect(link).toHaveAttribute('href', '/trophy-case.html');
    await link.click();
    await expect(page).toHaveURL(/trophy-case\.html/);
    await expect(page.locator('.tc-head h1')).toContainText('Trophy Case');
  });
});
