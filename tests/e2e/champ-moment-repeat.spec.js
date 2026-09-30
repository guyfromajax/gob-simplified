// @ts-check
/**
 * Championship moments are consumed when the takeover mounts, so Box score /
 * Continue / a second Office load cannot re-show the same item.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const FID = 'f-e2e-champ-repeat';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const SHOTS = path.join(__dirname, '../../reports/champ-moment-repeat');

function champItem() {
  return {
    id: 'championship', kind: 'championship', tier: 'SEASON_PEAK',
    priority: 10, payload_ref: 'pending_championship_moments',
    seen_key: 'pending_championship_moments', title: 'Championship moment',
    line: 'A title moment is waiting.', style: 'gold',
    sting: 'STING_SEASON_PEAK', duration: 'long',
  };
}

function digest() {
  return {
    state: 'regular',
    what_moved: {
      national_rank: { now: 1, prev: 3, delta: 2 },
      conference_standing: { now: 1, prev: 2, delta: 1 },
      record: { wins: 26, losses: 0 },
      streak: 'W8',
      attribute_changes: [],
    },
    team_snapshot: { state: 'ready', chemistry: { value: 20, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: {
      week: 27, user_won: true, site: 'neutral', home_score: 78, away_score: 71,
      home_team_name: 'Lancaster', away_team_name: 'Four Corners',
      opponent_team_name: 'Four Corners', opponent_rank: 8,
      leader_role: 'potg', leader: { name: 'Devin Park', stats: { pts: 22 } },
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

function cc(flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 27,
    season: 3,
    current_season: 3,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 27, counts: {} },
    office_digest: digest(),
    pending_championship_moments: [],
    moments: [],
    moments_for_this_visit: [],
    weekly_card_items: [],
    team_name_map: { [TID]: 'Lancaster' },
  }, flags || {});
}

function spotlightMoment() {
  return {
    id: 'cm-spot-1',
    type: 'trophy_spotlight',
    season: 3,
    conference: 'A2',
    winner_team_name: 'Lancaster',
    winner_primary_color: '#27408E',
    winner_record: { wins: 26, losses: 0 },
    winner_seed: 1,
    user_is_winner: true,
    game_id: 'g-spot-1',
    loser_team_name: 'Four Corners',
  };
}

function conferenceTitleMoment() {
  return {
    id: 'cm-conf-1',
    type: 'conference_championship',
    season: 3,
    conference: 'A2',
    winner_team_name: 'Lancaster',
    winner_primary_color: '#27408E',
    loser_team_name: 'Four Corners',
    score: { winner: 78, loser: 71 },
    game_id: 'g-conf-1',
    user_is_winner: true,
  };
}

function visitFromState(state) {
  const pending = (state.pending || []).slice();
  const moments = pending.length ? [champItem()] : [];
  return cc({
    pending_championship_moments: pending,
    moments,
    moments_for_this_visit: moments,
  });
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installStatefulApi(page, state, seen, extra) {
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
      if (extra.desktop) {
        await route.abort();
        return;
      }
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
      await fulfillJson(route, visitFromState(state));
      return;
    }
    if (pathname === '/franchise/championship-moments/dismiss') {
      let momentId = '';
      try {
        const raw = request.postData();
        const body = raw ? JSON.parse(raw) : {};
        momentId = body.moment_id || '';
      } catch (err) { momentId = ''; }
      if (momentId) {
        state.pending = (state.pending || []).filter((m) => m.id !== momentId);
      }
      await fulfillJson(route, { status: 'ok', removed: true });
      return;
    }
    if (pathname === '/franchise/season-review-seen') {
      await fulfillJson(route, { ok: true });
      return;
    }
    await fulfillJson(route, extra.desktop ? {} : {});
  });
}

async function waitOfficeReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
}

async function openOffice(page, state, seen, extra) {
  extra = extra || {};
  if (extra.desktop) {
    await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  }
  await stubAuth(page);
  await installStatefulApi(page, state, seen, extra);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await waitOfficeReady(page);
}

async function reopenOffice(page, state, extra) {
  extra = extra || {};
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await waitOfficeReady(page);
}

async function shot(page, name) {
  await page.evaluate(() => { window.scrollTo(0, 0); });
  await page.screenshot({ path: path.join(SHOTS, name) });
}

test.describe('championship moment consume-on-show', () => {
  test.beforeAll(() => {
    fs.mkdirSync(SHOTS, { recursive: true });
  });

  test('trophy_spotlight Box score then Office again does not re-show', async ({ page }) => {
    const seen = [];
    const state = { pending: [spotlightMoment()] };
    await openOffice(page, state, seen);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect(pk.locator('.pk-t')).toContainText('Conference Regular-Season Champions');
    await expect(pk.locator('.pk-f')).toBeVisible();
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(1);
    await page.waitForTimeout(1600);
    await shot(page, 'takeover-1280.png');

    const box = pk.locator('.lnk');
    await expect(box).toBeVisible();
    await box.click();
    await page.waitForURL(/box-score\.html|game\.html/, { timeout: 15000 });
    expect(state.pending).toEqual([]);

    await reopenOffice(page, state);
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
    await expect(page.locator('#office-root')).toBeVisible();
    await shot(page, 'office-next-visit-1280.png');
  });

  test('trophy_spotlight Continue then Office again does not re-show', async ({ page }) => {
    const seen = [];
    const state = { pending: [spotlightMoment()] };
    await openOffice(page, state, seen);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(1);
    await pk.locator('.pk-go').click();
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
    expect(state.pending).toEqual([]);

    await reopenOffice(page, state);
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
  });

  test('conference title Box score then Office again does not re-show', async ({ page }) => {
    const seen = [];
    const state = { pending: [conferenceTitleMoment()] };
    await openOffice(page, state, seen);
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect(pk.locator('.pk-t')).toContainText('Conference Champions');
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(1);
    await pk.locator('.lnk').click();
    await page.waitForURL(/box-score\.html|game\.html/, { timeout: 15000 });
    expect(state.pending).toEqual([]);

    await reopenOffice(page, state);
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
  });

  test('desktop profile: trophy_spotlight Box score then Office again does not re-show', async ({ page }) => {
    const seen = [];
    const state = { pending: [spotlightMoment()] };
    await openOffice(page, state, seen, { desktop: true });
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect.poll(() => seen.filter((s) => s.path.indexOf('championship-moments/dismiss') !== -1).length).toBe(1);
    await pk.locator('.lnk').click();
    await page.waitForURL(/box-score\.html|game\.html/, { timeout: 15000 });
    expect(state.pending).toEqual([]);

    await reopenOffice(page, state, { desktop: true });
    await expect(page.locator('.pk.is-open')).toHaveCount(0);
  });
});
