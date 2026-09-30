// @ts-check
/**
 * Server-capped visit list: this visit shows the queued pop-ups; the rest wait.
 * Fixtures use moment-queue v2 shapes (kind, tier, style, sting, duration, payload_ref).
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const FID = 'f-e2e-moments';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function walkOn() {
  return {
    eligible: true,
    season: 2,
    count: 1,
    walk_ons: [{
      name: 'Ellis Clemons', pos: 'PF', year: 'Junior', height: 78, weight: 210,
      attributes: { SC: 40, SH: 45, ID: 50, OD: 55, PS: 60, BH: 65, RB: 70, AG: 35, ST: 40, ND: 45, IQ: 50, FT: 55 },
      rt: 72, potential_rt: 88,
    }],
  };
}

function digest() {
  return {
    state: 'regular',
    what_moved: {
      national_rank: { now: 18, prev: 22, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 16, losses: 5 },
      streak: 'W4',
      attribute_changes: [],
    },
    team_snapshot: { state: 'ready', chemistry: { value: 18, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: {
      week: 21, user_won: true, site: 'home', home_score: 71, away_score: 64,
      home_team_name: 'Lancaster', away_team_name: 'Crickstown',
      opponent_team_name: 'Crickstown', opponent_rank: 9,
      leader_role: 'potg', leader: { name: 'Jalen Carter', stats: { pts: 24 } },
      box_score: { path: '/box-score.html', params: {} },
    },
    next_game: { week: 22, site: 'away', opponent: 'Morristown', rank: 21, record: { wins: 11, losses: 8 }, conference: 2 },
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [],
    recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 },
    signing_day: null,
    season_preview: null,
  };
}

function cc(flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 22,
    season: 2,
    current_season: 2,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 22, counts: {} },
    office_digest: digest(),
    pending_championship_moments: [],
    recruiting_results_modal: { eligible: true },
    moments: [],
    moments_for_this_visit: [],
    weekly_card_items: [],
    team_name_map: { [TID]: 'Lancaster' },
  }, flags || {});
}

function visitOne() {
  const conference = { eligible: true, lost_round: 'round1' };
  const moments = [
    {
      id: 'conference_rs_region', kind: 'conference_rs_region', tier: 'MILESTONE',
      priority: 65, payload_ref: 'conference_rs_region_modal',
      seen_key: 'conference_rs_region_modal_seen_season', duration: 'short',
      title: 'Region tournament qualified', line: 'Qualified.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    {
      id: 'region_bye', kind: 'region_bye', tier: 'MILESTONE',
      priority: 60, payload_ref: 'region_bye_modal_eligible',
      seen_key: 'region_bye_modal_seen_season', duration: 'short',
      title: 'Region tournament bye', line: 'Bye.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    {
      id: 'walk_on_welcome', kind: 'walk_on_welcome', tier: 'MILESTONE',
      priority: 50, payload_ref: 'walk_on_welcome_modal',
      seen_key: 'walk_on_welcome_modal_seen_season', duration: 'long',
      title: 'Walk-on welcome', line: '1 walk-on joined the roster.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
  ];
  return cc({
    walk_on_welcome_modal: walkOn(),
    conference_rs_region_modal: conference,
    region_bye_modal_eligible: true,
    moments,
    moments_for_this_visit: [moments[0], moments[1]],
    office_digest: Object.assign(digest(), { weekly_card_items: [] }),
  });
}

function weeklyItems() {
  return [
    {
      id: 'bracket_update', kind: 'bracket_update', tier: 'WEEKLY', priority: 80,
      payload_ref: 'bracket_update_modal', seen_key: 'bracket_update',
      title: 'Tournament update', line: 'The tournament bracket moved this week.',
      href: '/franchise-command-center.html?tab=tournament-view',
      style: null, sting: null,
    },
    {
      id: 'recruit_visit', kind: 'recruit_visit', tier: 'WEEKLY', priority: 90,
      payload_ref: 'recruit_visit_modal', seen_key: 'recruit_visit_modal_seen_week',
      title: 'Recruit visit', line: 'Ellis Clemons is visiting this week.',
      href: '/recruiting.html',
      style: null, sting: null,
    },
  ];
}

function visitWeekly() {
  const items = weeklyItems();
  return cc({
    moments: items,
    moments_for_this_visit: [],
    weekly_card_items: items,
    // The card folds the top weekly item into its Also row; the rest expand inline.
    office_digest: Object.assign(digest(), { weekly_card_items: items, also: items[0] }),
  });
}

function visitCut() {
  const conference = { eligible: true, lost_round: 'round1' };
  const moments = [
    {
      id: 'conference_rs_region', kind: 'conference_rs_region', tier: 'MILESTONE',
      priority: 65, payload_ref: 'conference_rs_region_modal',
      seen_key: 'conference_rs_region_modal_seen_season', duration: 'short',
      title: 'Region tournament qualified', line: 'Qualified.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
  ];
  return cc({
    cut_required: true,
    cut_count: 2,
    conference_rs_region_modal: conference,
    moments,
    moments_for_this_visit: moments,
    office_digest: Object.assign(digest(), { weekly_card_items: [] }),
  });
}

function visitTwo() {
  const conference = { eligible: true, lost_round: 'final' };
  const moments = [
    {
      id: 'conference_rs_region', kind: 'conference_rs_region', tier: 'MILESTONE',
      priority: 65, payload_ref: 'conference_rs_region_modal',
      seen_key: 'conference_rs_region_modal_seen_season', duration: 'short',
      title: 'Region tournament qualified', line: 'Qualified.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
  ];
  return cc({
    walk_on_welcome_modal: { eligible: false },
    conference_rs_region_modal: conference,
    region_bye_modal_eligible: false,
    moments,
    moments_for_this_visit: moments,
    office_digest: Object.assign(digest(), { weekly_card_items: [] }),
  });
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data) {
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
    await fulfillJson(route, {});
  });
}

function overlayCount() {
  return document.querySelectorAll(
    '.mm-scrim.is-open, .sammy-modal-backdrop.open, .bn-overlay.show, .cm-overlay.is-visible, .arch-reveal-overlay.is-visible'
  ).length;
}

async function openOffice(page, data) {
  await stubAuth(page);
  await installApi(page, data);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
}

async function dismissMm(page) {
  const modal = page.locator('.mm-scrim.is-open');
  await expect(modal).toBeVisible({ timeout: 15000 });
  const count = await page.evaluate(overlayCount);
  expect(count).toBeLessThanOrEqual(2);
  const kind = (await modal.getAttribute('data-kind')) || '';
  await modal.locator('.mm-go').click();
  await page.waitForFunction((prev) => {
    const open = document.querySelector('.mm-scrim.is-open');
    if (!open) return true;
    return open.getAttribute('data-kind') !== prev;
  }, kind, { timeout: 8000 });
}

const SHOTS = path.join(__dirname, '../../reports/moment-queue');

test('three eligible moments show at most two pop-ups; the rest wait for the next visit', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitOne());
  await expect(page.locator('.mm-scrim.is-open')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.mm-scrim.is-open')).toHaveAttribute('data-kind', 'conference_rs_region');
  await page.screenshot({ path: path.join(SHOTS, 'popup-1-of-2.png') });
  await dismissMm(page);
  await dismissMm(page);
  await expect.poll(async () => page.evaluate(overlayCount)).toBe(0);

  await openOffice(page, visitTwo());
  await dismissMm(page);
  await expect.poll(async () => page.evaluate(overlayCount)).toBe(0);
});

test('the weekly items fold into the card Also row and expand inline', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitWeekly());
  // The folded moments now live inside the "Since last week" (.wkc) card, not a
  // separate column-2 card.
  await expect(page.locator('#office-root .office-weekly')).toHaveCount(0);
  const card = page.locator('#office-root .wkc');
  await expect(card).toBeVisible();
  // Top weekly item shows as the Also row; the second expands behind "+1 more".
  await expect(card.locator('.wkc-also').first()).toContainText('Tournament update');
  await expect(card.locator('.wkc-also a[href*="tab=tournament-view"]')).toHaveCount(1);
  const more = card.locator('.wkc-more');
  await expect(more).toHaveText('+1 more');
  await expect(card.locator('.wkc-extra')).toBeHidden();
  await more.click();
  await expect(card.locator('.wkc-extra')).toBeVisible();
  await expect(card.getByText('Recruit visit')).toBeVisible();
  await expect(card.locator('.wkc-extra a[href*="recruiting.html"]')).toHaveCount(1);
  await page.screenshot({ path: path.join(SHOTS, 'office-weekly-card.png') });
});

async function assertCutModalOnTop(page) {
  await page.waitForFunction(() => {
    const box = document.querySelector('.fcc-cut-required-modal .gob-modal-box');
    return !!(box && parseFloat(getComputedStyle(box).opacity) === 1);
  }, null, { timeout: 5000 });
  const hits = await page.evaluate(() => {
    function insideModal(el) {
      const modal = document.querySelector('.fcc-cut-required-modal');
      if (!el || !modal) return false;
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!(hit && modal.contains(hit));
    }
    return {
      title: insideModal(document.getElementById('fcc-cut-required-title')),
      button: insideModal(document.getElementById('fcc-cut-required-close')),
    };
  });
  expect(hits.title, 'title centre should hit the cut modal').toBe(true);
  expect(hits.button, 'button centre should hit the cut modal').toBe(true);
}

test('cut modal opens once after the pop-up closes', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitCut());
  await expect(page.locator('.mm-scrim.is-open')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.fcc-cut-required-modal')).toHaveCount(0);
  await dismissMm(page);
  await expect(page.locator('.fcc-cut-required-modal.is-visible')).toHaveCount(1);
  await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  await assertCutModalOnTop(page);
  await page.screenshot({ path: path.join(SHOTS, 'cut-after-popup.png') });
  await page.waitForTimeout(8500);
  await expect(page.locator('.fcc-cut-required-modal')).toHaveCount(1);
});
