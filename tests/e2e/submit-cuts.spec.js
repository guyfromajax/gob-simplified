const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID_PREFIX = 'f-e2e-submit-cuts';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function franchiseIdFor(testInfo) {
  return FID_PREFIX + '-w' + testInfo.workerIndex + '-r' + testInfo.repeatEachIndex;
}
const CUT_COUNT = 3;
const OUT = path.join(__dirname, '../../reports/submit-cuts');
const NAMES = [
  'Ada Keeper', 'Bea Reserve', 'Cy Bench', 'Dee Extra', 'Eli Spare',
  'Fay Depth', 'Gus Walkon', 'Hal Redshirt', 'Ivy Scout', 'Jay Practice',
  'Kit Taxi', 'Lou Taxi', 'Mo Taxi', 'Ned Taxi', 'Oli Taxi',
];

function playerRow(i) {
  const id = '1111111111111111111111' + String(i + 10);
  const name = NAMES[i];
  return {
    _id: id,
    player_id: id,
    name,
    first_name: name.split(' ')[0],
    last_name: name.split(' ')[1],
    jersey: i + 1,
    position: ['PG', 'SG', 'SF', 'PF', 'C'][i % 5],
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    position_ratings: { PG: 70 - i, SG: 60, SF: 50, PF: 40, C: 30 },
  };
}

const ROSTER = NAMES.map((_, i) => playerRow(i));

function ccData(franchiseId, overrides) {
  return Object.assign({
    franchise_id: franchiseId,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 1,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: true,
    cut_count: CUT_COUNT,
    recruiting_wire: {},
    user_conference: 1,
    sister_conference: 2,
    user_region: 'A',
    office_digest: {
      state: 'ready',
      result: null,
      next_game: { week: 1, opponent: 'Four Corners' },
      what_moved: {
        national_rank: { now: 36, prev: 36, delta: 0 },
        conference_standing: { now: 3, prev: 3, delta: 0 },
        record: { wins: 0, losses: 0 },
        streak: '',
        attribute_changes: [],
      },
      team_snapshot: { state: 'ready', chemistry: { value: 12, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
      conference_standings: { conference: 1, region: 'A', rows: [] },
      recruiting_wire: { events: [] },
      todos: [],
    },
  }, overrides || {});
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, state) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const method = request.method();
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname === '/app-config'
      || pathname === '/teams';
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
      await fulfillJson(route, state.assigned
        ? ccData(state.franchiseId, { cut_required: false, cut_count: 0 })
        : ccData(state.franchiseId));
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, { players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
      return;
    }
    if (pathname === '/franchise/cut-players' && method === 'POST') {
      let body = {};
      try { body = request.postDataJSON() || {}; } catch (err) { body = {}; }
      state.posts.push(body);
      state.assigned = true;
      await fulfillJson(route, { ok: true, assigned: body.player_ids || [] });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function armSpy(page) {
  await page.evaluate(async () => {
    const m = await import('/js/shared/uiSfx.js');
    m.setChannelMuted('master', false);
    m.setChannelMuted('sfx', false);
    m.setChannelLevel('master', 100);
    m.setChannelLevel('sfx', 100);
    window.__gobSfxCalls = [];
  });
}

async function sfxCalls(page) {
  return page.evaluate(() => (window.__gobSfxCalls || []).slice());
}

/**
 * The page plays a checkbox's sound through a dynamic import, so it lands a moment after
 * the click. Wait for the sounds already on their way before clearing the list, or a late
 * one is counted against the next step.
 */
async function waitForSfx(page, count) {
  await expect.poll(async () => (await sfxCalls(page)).length, { timeout: 10000 }).toBe(count);
}

async function resetScroll(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
  });
}

async function capture(page, name) {
  await resetScroll(page);
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, name) });
}

async function openAssignPage(page, testInfo, opts) {
  opts = opts || {};
  const franchiseId = franchiseIdFor(testInfo);
  if (opts.desktop) {
    await page.addInitScript(() => {
      window.GOB_BUILD_PROFILE = 'desktop';
      if (window.location && window.location.port) {
        window.GOB_LOOPBACK_PORT = Number(window.location.port);
      }
    });
  }
  await stubAuth(page);
  const state = { posts: [], assigned: false, franchiseId: franchiseId };
  await installApi(page, state);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/cut-players.html?franchise_id=' + encodeURIComponent(franchiseId) + '&team_id=' + TID + '&from=fcc');
  await expect(page.locator('#cut-players-table .cut-player-checkbox').first()).toBeVisible({ timeout: 30000 });
  await armSpy(page);
  return state;
}

async function disabledLook(page) {
  return page.evaluate(() => {
    const btn = document.getElementById('submit-btn');
    const s = getComputedStyle(btn);
    const reason = document.getElementById('cut-submit-reason');
    const status = document.getElementById('cut-status');
    const rs = reason ? getComputedStyle(reason) : null;
    const ss = status ? getComputedStyle(status) : null;
    return {
      disabled: btn.disabled,
      text: (btn.textContent || '').trim(),
      cursor: s.cursor,
      opacity: parseFloat(s.opacity),
      color: s.color,
      reason: reason ? (reason.textContent || '').trim() : '',
      reasonVisible: !!(reason && !reason.hidden && rs && rs.display !== 'none' && rs.visibility !== 'hidden'),
      status: status ? (status.textContent || '').trim() : '',
      statusVisible: !!(status && ss && ss.display !== 'none' && ss.visibility !== 'hidden' && ss.opacity !== '0'),
    };
  });
}

async function clickSubmitForce(page) {
  await page.evaluate(() => {
    window.__gobSfxCalls = [];
    const btn = document.getElementById('submit-btn');
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, composed: true }));
  });
  return sfxCalls(page);
}

test.describe('week-1 practice-squad assignment', () => {
  test('web: wrong count is disabled, looks dead, no sound; exact count confirms on top and lands on FCC', async ({ page }, testInfo) => {
    const state = await openAssignPage(page, testInfo);
    const captureShots = testInfo.repeatEachIndex === 0;

    await expect(page.locator('#submit-btn')).toHaveText('Assign Practice Squad');
    await expect(page.locator('#submit-btn')).toBeDisabled();
    const fewer = await disabledLook(page);
    expect(fewer.disabled).toBe(true);
    expect(fewer.cursor).toBe('not-allowed');
    expect(fewer.opacity).toBeLessThan(1);
    expect(fewer.reasonVisible, JSON.stringify(fewer)).toBe(true);
    expect(fewer.reason).toBe('Assign 3 more to the practice squad');
    expect(fewer.statusVisible, JSON.stringify(fewer)).toBe(true);
    expect(await clickSubmitForce(page)).toEqual([]);
    await expect(page.locator('#cut-modal-backdrop.is-visible')).toHaveCount(0);
    if (captureShots) await capture(page, 'wrong-count-1280.png');

    const boxes = page.locator('#cut-players-table .cut-player-checkbox');
    await boxes.nth(0).check();
    await boxes.nth(1).check();
    await boxes.nth(2).check();
    await boxes.nth(3).check();
    await waitForSfx(page, 4);
    const more = await disabledLook(page);
    expect(more.disabled).toBe(true);
    expect(more.reason).toBe('Remove 1');
    expect(await clickSubmitForce(page)).toEqual([]);

    await boxes.nth(3).uncheck();
    await waitForSfx(page, 1);
    await expect(page.locator('#submit-btn')).toBeEnabled();
    const exact = await disabledLook(page);
    expect(exact.disabled).toBe(false);
    expect(exact.reasonVisible).toBe(false);
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await resetScroll(page);
    if (captureShots) await capture(page, 'exact-count-1280.png');

    await page.locator('#submit-btn').click();
    await expect(page.locator('#cut-modal-backdrop.is-visible')).toBeVisible();
    await expect(page.locator('#cut-modal-title')).toHaveText('Confirm Practice Squad');
    // The title and the two buttons, no body copy.
    await expect(page.locator('#cut-modal-message')).toBeHidden();
    await expect(page.locator('#cut-modal-message')).toHaveText('');
    await expect(page.locator('#cut-modal-actions button')).toHaveText(['Cancel', 'Confirm']);
    expect((await page.locator('#cut-modal-backdrop .gob-modal-box').innerText()).split('\n').map((s) => s.trim()).filter(Boolean))
      .toEqual(['Confirm Practice Squad', 'Cancel', 'Confirm']);
    if (process.env.V3_SHOTS === '1') {
      const v3 = path.join(__dirname, '../../reports/v3-pages');
      fs.mkdirSync(v3, { recursive: true });
      await page.screenshot({ path: path.join(v3, 'after-confirm-practice-squad-1280.png') });
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.screenshot({ path: path.join(v3, 'after-confirm-practice-squad-1920.png') });
      await page.setViewportSize({ width: 1280, height: 720 });
    }
    const stack = await page.evaluate(() => {
      const overlay = document.getElementById('cut-modal-backdrop');
      const r = overlay.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return {
        parent: overlay.parentElement && overlay.parentElement.tagName,
        inMain: !!(overlay.closest('#gob-main')),
        visible: overlay.classList.contains('is-visible'),
        hitInOverlay: !!(hit && hit.closest('#cut-modal-backdrop')),
        hitTag: hit ? hit.tagName : '',
        overlayZ: getComputedStyle(overlay).zIndex,
        overlayPos: getComputedStyle(overlay).position,
      };
    });
    expect(stack.parent, JSON.stringify(stack)).toBe('BODY');
    expect(stack.inMain, JSON.stringify(stack)).toBe(false);
    expect(stack.hitInOverlay, JSON.stringify(stack)).toBe(true);
    expect(stack.overlayPos, JSON.stringify(stack)).toBe('fixed');
    if (captureShots) await capture(page, 'confirm-modal-1280.png');

    await page.getByRole('button', { name: 'Confirm', exact: true }).click();
    await expect.poll(() => state.posts.length, { timeout: 20000 }).toBe(1);
    expect(state.posts[0].franchise_id).toBe(state.franchiseId);
    expect(state.posts[0].player_ids).toEqual(ROSTER.slice(0, 3).map((row) => row._id));
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 20000 }).toBe('/franchise-command-center.html');
    await expect(page.locator('#play-now')).toBeVisible({ timeout: 20000 });
    await resetScroll(page);
    if (captureShots) await capture(page, 'landing-1280.png');
  });

  test('desktop: wrong count is disabled with no sound; exact count POSTs and lands on FCC', async ({ page }, testInfo) => {
    const state = await openAssignPage(page, testInfo, { desktop: true });
    await expect(page.locator('#submit-btn')).toHaveText('Assign Practice Squad');
    await expect(page.locator('#submit-btn')).toBeDisabled();
    const fewer = await disabledLook(page);
    expect(fewer.cursor).toBe('not-allowed');
    expect(fewer.reason).toBe('Assign 3 more to the practice squad');
    expect(await clickSubmitForce(page)).toEqual([]);

    const boxes = page.locator('#cut-players-table .cut-player-checkbox');
    await boxes.nth(0).check();
    await boxes.nth(1).check();
    await boxes.nth(2).check();
    await expect(page.locator('#submit-btn')).toBeEnabled();
    await waitForSfx(page, 3);
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.locator('#submit-btn').click();
    await expect(page.locator('#cut-modal-backdrop.is-visible')).toBeVisible();
    const onTop = await page.evaluate(() => {
      const overlay = document.getElementById('cut-modal-backdrop');
      const r = overlay.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!(hit && hit.closest('#cut-modal-backdrop')) && overlay.parentElement.tagName === 'BODY';
    });
    expect(onTop).toBe(true);
    await page.getByRole('button', { name: 'Confirm', exact: true }).click();
    await expect.poll(() => state.posts.length, { timeout: 20000 }).toBe(1);
    expect(state.posts[0].player_ids).toEqual(ROSTER.slice(0, 3).map((row) => row._id));
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 20000 }).toBe('/franchise-command-center.html');
    await expect(page.locator('#play-now')).toBeVisible({ timeout: 20000 });
  });
});
