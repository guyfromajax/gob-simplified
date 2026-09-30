// @ts-check
/**
 * FCC season-load failure state. When /franchise/command-center/data fails every
 * retry, the Office shows the design-system error card ("Couldn't load your season"
 * + cause + Retry) instead of a silent dead page; Advance stays disabled, says why,
 * and plays no sound. Retry re-runs the full load and, on success, renders the
 * Office and re-enables Advance. A 429-then-200 still loads with no card. Desktop
 * profile behaves the same when the engine is down.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-load-retry';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

const OK_DATA = {
  franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster',
  week: 22, current_season: 1, rank: 18,
  training_completed: true, session_type: 'in-season',
  user_conference: 1, user_region: 'A',
  office_digest: {
    state: 'regular',
    what_moved: {
      national_rank: { now: 18, prev: 20, delta: 2 },
      conference_standing: { now: 3, prev: 4, delta: 1 },
      record: { wins: 16, losses: 5 }, streak: 'W4', attribute_changes: [],
    },
    result: null, next_game: null,
    team_snapshot: { state: 'ready', chemistry: { value: 18, max: 25 }, attitude: { buckets: [] }, moved_most: [] },
    conference_standings: null,
    todos: [{ id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: true, route: '/set-lineup.html' }],
    recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false },
    weekly_card_items: [], also: null,
  },
};

// Route every FCC dependency to a benign success, and hand the command-center read
// to `ccHandler(route, attemptNumber)` so each test controls the failure pattern.
async function installFcc(page, ccHandler) {
  let ccAttempts = 0;
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(() => {});
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (e) { await route.continue(); return; }
    if (pathname.startsWith('/franchise/command-center/data')) {
      ccAttempts += 1;
      await ccHandler(route, ccAttempts);
      return;
    }
    const isApi = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname === '/teams' || pathname === '/app-config';
    if (!isApi) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_id: 'u', username: 'e2e' }) }); return; }
    if (pathname === '/app-config') { await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ isAlpha: false }) }); return; }
    if (pathname === '/teams') { await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ name: 'Lancaster', object_id: TID, _id: TID }]) }); return; }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

const ok = (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OK_DATA) });
// status 0 = a network error (offline / engine down) → abort so fetch throws;
// any other status = an HTTP error response.
const fail = (route, status) => (status === 0
  ? route.abort('failed')
  : route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ detail: 'x' }) }));

async function gotoFcc(page) {
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
}

test.describe('FCC season-load failure + retry', () => {
  test('every attempt fails → card, disabled Advance with reason, no sound', async ({ page }) => {
    test.setTimeout(90000);
    await stubAuth(page);
    await installFcc(page, (route) => fail(route, 500));
    await gotoFcc(page);

    const card = page.locator('#office-root .gob-view-error');
    await expect(card).toBeVisible({ timeout: 45000 });
    await expect(card).toContainText("Couldn't load your season");
    await expect(card).toContainText('Server error.');
    await expect(page.locator('#office-root .gob-view-retry')).toBeVisible();

    const advance = page.locator('#play-now');
    await expect(advance).toBeDisabled();
    await expect(advance).toHaveAttribute('aria-label', "Season didn't load: retry above");

    // Advance plays no sound while failed (disabled button dispatches no click).
    await page.evaluate(async () => {
      const m = await import('/js/shared/uiSfx.js');
      m.setChannelMuted('master', false); m.setChannelMuted('sfx', false);
      m.setChannelLevel('master', 100); m.setChannelLevel('sfx', 100);
      window.__gobSfxCalls = [];
      document.getElementById('play-now').click();
    });
    expect(await page.evaluate(() => window.__gobSfxCalls.slice())).toEqual([]);
  });

  test('Retry after failure re-loads: Office renders, Advance enables', async ({ page }) => {
    test.setTimeout(90000);
    await stubAuth(page);
    let failing = true;
    await installFcc(page, (route) => (failing ? fail(route, 0) : ok(route)));
    await gotoFcc(page);

    await expect(page.locator('#office-root .gob-view-error')).toBeVisible({ timeout: 45000 });
    // "Connection lost." for a network-style failure (status 0).
    await expect(page.locator('#office-root .gob-view-error')).toContainText('Connection lost.');

    failing = false;
    await page.locator('#office-root .gob-view-retry').click();

    await expect(page.locator('#office-root .gob-view-error')).toHaveCount(0, { timeout: 45000 });
    await expect(page.locator('#office-root')).not.toHaveAttribute('data-office-state', 'error');
    const advance = page.locator('#play-now');
    await expect(advance).toBeEnabled();
    await expect(advance).not.toHaveAttribute('aria-label', "Season didn't load: retry above");
  });

  test('429 then 200 loads normally, no error card', async ({ page }) => {
    test.setTimeout(90000);
    await stubAuth(page);
    await installFcc(page, (route, n) => (n === 1 ? fail(route, 429) : ok(route)));
    await gotoFcc(page);

    await expect(page.locator('#play-now')).toBeEnabled({ timeout: 45000 });
    await expect(page.locator('#office-root .gob-view-error')).toHaveCount(0);
  });

  test('desktop profile: engine down shows the same card', async ({ page }) => {
    test.setTimeout(90000);
    await stubAuth(page);
    await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
    await installFcc(page, (route) => fail(route, 0)); // engine unreachable → network error
    await gotoFcc(page);

    await expect(page.locator('#office-root .gob-view-error')).toBeVisible({ timeout: 45000 });
    await expect(page.locator('#office-root .gob-view-error')).toContainText("Couldn't load your season");
    await expect(page.locator('#play-now')).toBeDisabled();
  });
});
