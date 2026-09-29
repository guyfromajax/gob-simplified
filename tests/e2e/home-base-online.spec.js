// @ts-check
/**
 * Home Base, online. Covers the Ch7 green rule (exactly one primary forward
 * action), the delete flow, tab memory, the desktop offline guard, and the
 * hard fit requirement: nothing below the fold at 1280x720 or 1920x1080.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

const LONG_NAME = 'Northwestern Ocean City Maritime Polytechnic';

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

function commandCenter(name, week, opts) {
  opts = opts || {};
  return {
    current_season: 3,
    week: week,
    rankings: [{ team_id: 'obj-' + opts.id, team_name: name, W: 12, L: 3, next: 'Lancaster' }],
    active_game_resume: opts.live
      ? {
        status: 'stoppage_anchor',
        game_id: 'g-' + opts.id,
        user_team_side: 'home',
        away_display_name: 'Xavien',
        away_team_name: 'Xavien',
        home_display_name: name,
        quarter: 3,
        clock: '4:12',
        away_score: 61,
        home_score: 58,
      }
      : null,
  };
}

function atlSlot(i, userId) {
  return {
    user_id: userId,
    franchise_id: 'atl-f-' + i,
    username: 'Coach ' + i,
    team_name: i % 2 ? 'Lancaster' : 'Morristown',
    primary_color: '#27408e',
    secondary_color: '#15181f',
    wins: 10 + i,
    losses: i,
    national_rank: i + 1,
    current_season: 4,
    week: 14,
    next_opponent: { is_away: false, team_name: 'Xavien' },
    last_game: { won: i % 2 === 0, is_away: false, opponent: 'Four Corners', user_score: 81, opp_score: 74 },
    completed_at: '2026-09-28T1' + i + ':00:00Z',
  };
}

function leaderboard(rows) {
  const top = [];
  for (let i = 1; i <= rows; i += 1) {
    top.push({ rank: i, username: 'Coach ' + i, geek_points: 1300 - i * 20, is_current_user: false });
  }
  return {
    top: top,
    current_user: { rank: 38, username: 'e2e', geek_points: 380, is_current_user: true },
    titles_top: top.slice(0, 5).map((e, i) => ({
      rank: i + 1, username: e.username, total_titles: 7 - i, national_titles: 1, is_current_user: false,
    })),
    titles_current_user: { rank: 22, username: 'e2e', total_titles: 1, national_titles: 0, is_current_user: true },
  };
}

/** GET /franchise/coach-career. `earned: false` is a coach who has played nothing. */
function coachCareer(earned) {
  if (earned === null) return {};
  return {
    user_id: 'e2e-user',
    username: 'e2e',
    record: earned
      ? { wins: 73, losses: 22, total_games: 95, win_rate: 77 }
      : { wins: 0, losses: 0, total_games: 0, win_rate: 0 },
    championships_total: earned
      ? { conf_rs: 1, conf_t: 1, region: 1, national: 0 }
      : { conf_rs: 0, conf_t: 0, region: 0, national: 0 },
    // Pre-summed by the server (Ch7 PR2): the client shows this verbatim.
    titles_total: earned ? 3 : 0,
    win_pct_display: earned ? '.768' : null,
    geek_points: earned ? 4060 : 0,
    seasons_completed: earned ? 4 : 0,
    programs: earned ? 2 : 0,
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {{programs?: number, live?: boolean, desktop?: boolean, width?: number, height?: number,
 *          longNames?: boolean, atl?: number, lbRows?: number, tab?: string,
 *          career?: boolean|null}} [opts]
 */
async function openHomeBase(page, opts) {
  opts = opts || {};
  const programs = opts.programs == null ? 2 : opts.programs;
  const width = opts.width || 1280;
  const height = opts.height || 720;
  const community = [];

  page.on('request', (req) => {
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (_err) { return; }
    if (pathname.startsWith('/api/community/') || pathname === '/api/auth/leaderboard'
      || pathname.startsWith('/api/leaderboard/')) community.push(pathname);
  });

  if (opts.desktop) await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  if (opts.tab) {
    await page.addInitScript((tab) => { localStorage.setItem('gob_hb_tab', tab); }, opts.tab);
  }
  await stubAuth(page);

  const names = opts.longNames
    ? [LONG_NAME, LONG_NAME + ' South']
    : ['Bentley-Truman', 'Ocean City'];
  const list = [];
  for (let i = 0; i < programs; i += 1) list.push(franchise('f' + (i + 1), i + 1, names[i], 14 - i));

  await page.route('**/api/auth/me', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
  }));
  await page.route('**/franchise/list', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({
      franchises: list,
      count: list.length,
      max: 2,
      // Slot 2 is the most recent, so the green must not simply follow slot order.
      most_recent_franchise_id: programs >= 2 ? 'f2' : (programs === 1 ? 'f1' : null),
    }),
  }));
  await page.route('**/teams', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(list.map((f) => ({
      object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9,
    }))),
  }));
  await page.route('**/franchise/command-center/data**', (r) => {
    const id = new URL(r.request().url()).searchParams.get('franchise_id') || '';
    const f = list.find((x) => x.franchise_id === id);
    if (!f) return r.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    // The live game sits on slot 1, which is NOT the most recent program: the
    // green has to move to it anyway.
    return r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(commandCenter(f.user_team_id, f.week, { id: id, live: !!opts.live && id === 'f1' })),
    });
  });
  await page.route('**/api/community/around-the-league', (r) => {
    const n = opts.atl == null ? 8 : opts.atl;
    const slots = [];
    for (let i = 0; i < n; i += 1) slots.push(atlSlot(i, i === 0 ? 'e2e-user' : 'other-' + i));
    return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ slots: slots }) });
  });
  await page.route('**/api/auth/leaderboard', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(leaderboard(opts.lbRows == null ? 10 : opts.lbRows)),
  }));
  await page.route('**/franchise/coach-career', (r) => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify(coachCareer(opts.career === undefined ? true : opts.career)),
  }));

  await page.setViewportSize({ width: width, height: height });
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.hb-top')).toBeVisible();
  return community;
}

/**
 * The fit rule: no scrollbar AND nothing clipped. Home Base sets
 * overflow:hidden, so scrollHeight alone would happily hide content that runs
 * off the bottom — every zone's own box has to be measured too.
 */
async function expectNothingBelowTheFold(page) {
  const result = await page.evaluate(() => {
    const clipped = [];
    const zones = '.hb-top, .door, .vacant, .hb-career, .hb-util, .fag, .hbt, .agc-g, .lbp, .lbl, .sec-f';
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

test.describe('green rule', () => {
  test('no programs: nothing is green', async ({ page }) => {
    await openHomeBase(page, { programs: 0 });
    await expect(page.locator('.hb .advance')).toHaveCount(0);
    await expect(page.locator('.vacant')).toHaveCount(2);
    await expect(page.locator('.vacant b').first()).toHaveText('Start Your Coaching Journey');
    // Find Your Program is quiet, never the primary action.
    await expect(page.locator('[data-hb-new-franchise]').first()).toHaveClass(/btn-ghost/);
    await expectNothingBelowTheFold(page);
  });

  test('one program: its Enter is the only green', async ({ page }) => {
    await openHomeBase(page, { programs: 1 });
    await expect(page.locator('.hb .advance')).toHaveCount(1);
    await expect(page.locator('.hb .advance')).toHaveText('Enter');
    await expect(page.locator('.door')).toHaveCount(1);
    await expect(page.locator('.vacant b')).toHaveText('Start Another Franchise');
    await expectNothingBelowTheFold(page);
  });

  test('two programs: only the most recently played is green', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await expect(page.locator('.hb .advance')).toHaveCount(1);
    const green = page.locator('.door', { has: page.locator('.advance') });
    await expect(green).toHaveAttribute('data-franchise-id', 'f2');
    await expect(green.locator('.door-tag')).toHaveText('Last played');
    // The other slot repeats the action quietly.
    await expect(page.locator('[data-hb-slot="1"] [data-hb-enter]')).toHaveClass(/btn-ghost/);
    await expectNothingBelowTheFold(page);
  });

  test('a game in progress takes the green from the most recent program', async ({ page }) => {
    await openHomeBase(page, { programs: 2, live: true });
    await expect(page.locator('.hb .advance')).toHaveCount(1);
    const green = page.locator('.door', { has: page.locator('.advance') });
    await expect(green).toHaveAttribute('data-franchise-id', 'f1');
    await expect(green.locator('.advance')).toHaveText('Resume Game');
    // The strip says the week and nothing else: no score, no quarter.
    await expect(green.locator('.door-live')).toHaveText('Game in progress · Week 14');
    await expect(page.locator('[data-hb-slot="2"] [data-hb-enter]')).toHaveClass(/btn-ghost/);
    await expectNothingBelowTheFold(page);
  });

  test('no orange and no reward gold anywhere on Home Base chrome', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    const offenders = await page.evaluate(() => {
      const bad = [];
      document.querySelectorAll('#home-base *').forEach((el) => {
        const cs = getComputedStyle(el);
        const ink = cs.backgroundColor + ' ' + cs.color + ' ' + cs.borderColor;
        // Alpha orange #F79420 and reward gold #F0C560.
        if (/247,\s*148,\s*32|240,\s*197,\s*96/.test(ink)) bad.push(el.className + ' :: ' + ink);
      });
      return bad;
    });
    expect(offenders, offenders.join('\n')).toEqual([]);
  });
});

test.describe('career strip', () => {
  test('sits between slot 02 and the Tutorials row and formats server values', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    const strip = page.locator('[data-hb-career]');
    await expect(strip).toBeVisible();

    // Order in the left zone: slots, then the strip, then the utility row.
    const order = await page.evaluate(() => Array.prototype.map.call(
      document.querySelector('.hb-l').children, (el) => el.className.split(' ')[0],
    ));
    expect(order).toEqual(['hb-h', 'slots', 'hb-career', 'hb-util']);

    const cells = strip.locator('.cr-n > div');
    await expect(cells).toHaveCount(4);
    await expect(cells.nth(0).locator('b')).toHaveText('73–22');
    // The % is the server's win_pct_display verbatim, not record.win_rate (77).
    await expect(cells.nth(0).locator('em')).toHaveText('.768');
    await expect(cells.nth(0).locator('span')).toHaveText('Career record');
    // No label may be clipped by its cell.
    const clipped = await page.locator('[data-hb-career] .cr-n span').evaluateAll(
      (els) => els.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent),
    );
    expect(clipped, clipped.join(', ')).toEqual([]);
    await expect(cells.nth(1).locator('b')).toHaveText('3');
    await expect(cells.nth(2).locator('b')).toHaveText('4');
    await expect(cells.nth(3).locator('b')).toHaveText('4,060');
    await expect(strip.locator('.hollow')).toHaveCount(0);
    await expectNothingBelowTheFold(page);
  });

  test('a coach who has played nothing gets hollow numerals', async ({ page }) => {
    await openHomeBase(page, { programs: 0, career: false });
    const strip = page.locator('[data-hb-career]');
    await expect(strip.locator('.cr-n > div')).toHaveCount(4);
    await expect(strip.locator('.hollow')).toHaveCount(4);
    // No win % to show, so nothing rides the numeral.
    await expect(strip.locator('.cr-n em')).toHaveCount(0);
    await expect(strip.locator('.cr-n > div').first().locator('span')).toHaveText('Career record');
    const stroke = await strip.locator('.hollow').first()
      .evaluate((el) => getComputedStyle(el).webkitTextStrokeWidth);
    expect(stroke).not.toBe('0px');
    await expectNothingBelowTheFold(page);
  });

  test('absent fields drop their cell rather than showing a guess', async ({ page }) => {
    await openHomeBase(page, { programs: 1, career: null });
    await expect(page.locator('[data-hb-career]')).toHaveCount(0);
    await expectNothingBelowTheFold(page);
  });

  test('the Trophy Case entry routes to the standalone page', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    const link = page.locator('[data-hb-trophy-case]');
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', '/trophy-case.html');
  });

  test('desktop shows the offline career zone in place of the left-zone strip', async ({ page }) => {
    // PR2: the coach-career payload feeds the offline "Your Career" right zone
    // over loopback (a /franchise route, never a community host), so desktop DOES
    // request it now — but the left-zone strip stays absent (the zone replaces it).
    const seen = [];
    page.on('request', (req) => {
      if (req.url().includes('/franchise/coach-career')) seen.push(req.url());
    });
    await openHomeBase(page, { programs: 2, desktop: true });
    await expect(page.locator('[data-hb-career]')).toHaveCount(0);
    await expect(page.locator('[data-hb-right-offline]')).toBeVisible();
    expect(seen.length).toBeGreaterThan(0);
  });
});

test.describe('delete flow', () => {
  test('menu opens, confirm defaults to Cancel, Esc and Cancel back out', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await expect(page.locator('.pop')).toHaveCount(0);

    await page.click('[data-hb-more][data-slot="1"]');
    await expect(page.locator('.pop [data-hb-delete]')).toHaveText('Delete program…');
    await expect(page.locator('[data-hb-more][data-slot="1"]')).toHaveAttribute('aria-expanded', 'true');

    await page.click('[data-hb-delete]');
    const dialog = page.locator('.cfm[role="alertdialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('h3')).toHaveText('Delete Bentley-Truman?');
    // Trophies survive a delete; the copy has to say so.
    await expect(dialog.locator('p')).toContainText('Your trophies and season history stay in your Trophy Case.');
    await expect(page.locator('[data-hb-cancel]')).toBeFocused();
    await expect(page.locator('.btn-del')).toHaveText('Delete Program');
    await expectNothingBelowTheFold(page);

    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  });

  test('confirming issues the DELETE for that slot', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    let deleted = '';
    await page.route('**/franchise/f1', (r) => {
      if (r.request().method() === 'DELETE') deleted = 'f1';
      return r.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });
    await page.click('[data-hb-more][data-slot="1"]');
    await page.click('[data-hb-delete]');
    await page.click('.btn-del');
    await expect.poll(() => deleted).toBe('f1');
  });
});

test.describe('right zone', () => {
  test('one tabbed panel, arrow keys switch it, and the choice is remembered', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await expect(page.locator('[role="tab"]')).toHaveCount(2);
    await expect(page.locator('[data-hb-tab="ag"]')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('[data-hb-panel="lb"]')).toBeHidden();
    await expect(page.locator('.fag[aria-disabled="true"] .soon')).toHaveText('Coming Soon');

    await page.locator('[data-hb-tab="ag"]').focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.locator('[data-hb-tab="lb"]')).toBeFocused();
    await expect(page.locator('[data-hb-panel="lb"]')).toBeVisible();
    await expect(page.locator('[data-hb-panel="ag"]')).toBeHidden();
    expect(await page.evaluate(() => localStorage.getItem('gob_hb_tab'))).toBe('lb');

    await page.reload();
    await expect(page.locator('[data-hb-tab="lb"]')).toHaveAttribute('aria-selected', 'true');
  });

  test('Around GOB puts your card first with the navy ring', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await expect(page.locator('.agc').first()).toHaveClass(/is-me/);
    await expect(page.locator('.agc').first().locator('.agc-coach')).toHaveText('You');
    await expect(page.locator('.agc.is-me')).toHaveCount(1);
    await expect(page.locator('.agc:not(.is-wait)')).toHaveCount(8);
    // W/L plates are white or outline, never green or red.
    await expect(page.locator('.wl').first()).toHaveCount(1);
  });

  test('leaderboard shows three tiles and pins your row', async ({ page }) => {
    await openHomeBase(page, { programs: 2, tab: 'lb' });
    await expect(page.locator('.lbt')).toHaveCount(3);
    await expect(page.locator('.ldb-r.me')).toHaveCount(1);
    await expect(page.locator('.ldb-r.me em')).toHaveText('You');
    await expect(page.locator('.sec-f .lnk')).toHaveCount(2);
    await expectNothingBelowTheFold(page);

    await page.click('[data-hb-lb-view="titles"]');
    await expect(page.locator('[data-hb-lb-view="titles"]')).toHaveAttribute('aria-checked', 'true');
    await expect(page.locator('.lbt span small').first()).toHaveText('TITLES');
    await expectNothingBelowTheFold(page);
  });

  test('Community Highlights is gone from Home Base', async ({ page }) => {
    const community = await openHomeBase(page, { programs: 2 });
    await expect(page.locator('.community-highlights-panel')).toHaveCount(0);
    expect(community.filter((p) => p === '/api/community/highlights')).toEqual([]);
  });
});

test.describe('fit', () => {
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    for (const state of [{ programs: 0 }, { programs: 1 }, { programs: 2 }, { programs: 2, live: true }]) {
      const label = `${size.width}x${size.height} with ${state.programs} program(s)${state.live ? ' live' : ''}`;
      test(`nothing below the fold at ${label}`, async ({ page }) => {
        await openHomeBase(page, Object.assign({}, size, state));
        await expectNothingBelowTheFold(page);
        await page.locator('[data-hb-tab="lb"]').click();
        await expectNothingBelowTheFold(page);
      });
    }
  }

  test('worst-case data still fits: longest names, a full grid and a full board', async ({ page }) => {
    await openHomeBase(page, { programs: 2, longNames: true, atl: 8, lbRows: 15 });
    await expect(page.locator('.door-n').first()).toContainText('Northwestern Ocean City');
    await expectNothingBelowTheFold(page);
    await page.locator('[data-hb-tab="lb"]').click();
    await expectNothingBelowTheFold(page);
  });

  test('the right density class is on the root at each size', async ({ page }) => {
    await openHomeBase(page, { programs: 2, width: 1280, height: 720 });
    await expect(page.locator('#home-base')).toHaveClass(/gob-1280/);
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(page.locator('#home-base')).toHaveClass(/gob-1920/);
  });
});

test.describe('keyboard', () => {
  test('doors are focusable and Enter opens them', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await page.locator('[data-hb-slot="2"] .door').focus();
    await expect(page.locator('[data-hb-slot="2"] .door')).toBeFocused();
    await page.keyboard.press('Enter');
    await page.waitForURL(/franchise/, { timeout: 15000 });
  });

  test('the slot menu traps focus on its item and Esc returns it to the trigger', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await page.click('[data-hb-more][data-slot="1"]');
    await expect(page.locator('.pop [data-hb-delete]')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-hb-more][data-slot="1"]')).toBeFocused();
  });

  test('every control shows a visible focus ring', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    const selectors = ['.hb-tl', '.door', '[data-hb-enter]', '[data-hb-more]', '[data-hb-tab="lb"]', '.hb-link'];
    for (const sel of selectors) {
      const outline = await page.locator(sel).first().evaluate((el) => {
        el.focus();
        const cs = getComputedStyle(el);
        return cs.outlineStyle + ' ' + cs.outlineWidth;
      });
      expect(outline, sel).not.toMatch(/^none/);
    }
  });
});

test('desktop keeps the offline guard: no community requests, "Your Career" right zone', async ({ page }) => {
  const community = await openHomeBase(page, { programs: 2, desktop: true });
  await page.clock.install();
  await page.clock.runFor(65000);
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.clock.runFor(1000);
  expect(community, JSON.stringify(community)).toEqual([]);

  // PR2 fills the offline right zone with "Your Career" (from loopback only); the
  // online tab panel and Find A Game placard never appear.
  await expect(page.locator('[data-hb-right-offline]')).toBeVisible();
  await expect(page.locator('.cr .cr-n')).toBeVisible();
  await expect(page.locator('.hbt')).toHaveCount(0);
  await expect(page.locator('.fag')).toHaveCount(0);
  // The left zone and the green rule still work with no network.
  await expect(page.locator('.door')).toHaveCount(2);
  await expect(page.locator('.hb .advance')).toHaveCount(1);
  await expect(page.locator('.hb-conn')).toHaveClass(/off/);
  await expectNothingBelowTheFold(page);
});

test.describe('branded loader', () => {
  test('the shared overlay covers the session check and lifts once the slots render', async ({ page }) => {
    let releaseSession = () => {};
    const held = new Promise((resolve) => { releaseSession = resolve; });

    await stubAuth(page);
    await page.route('**/api/auth/me', async (r) => {
      await held;
      return r.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }),
      });
    });
    await page.route('**/franchise/list', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        franchises: [franchise('f1', 1, 'Bentley-Truman', 14)],
        count: 1, max: 2, most_recent_franchise_id: 'f1',
      }),
    }));
    await page.route('**/teams', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify([{ object_id: 'obj-f1', name: 'Bentley-Truman', natl_rank: 9 }]),
    }));
    await page.route('**/franchise/command-center/data**', (r) => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(commandCenter('Bentley-Truman', 14, { id: 'f1' })),
    }));
    await page.route('**/api/community/around-the-league', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ slots: [atlSlot(0, 'e2e-user')] }),
    }));
    await page.route('**/api/auth/leaderboard', (r) => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(leaderboard(10)),
    }));

    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/mode-select.html');

    // Held open on the session check: the branded loader is up and no Home
    // Base content has painted behind it.
    await expect(page.locator('#page-load-overlay')).toBeVisible();
    await expect(page.locator('#page-load-overlay img')).toHaveAttribute('src', '/images/loader1.gif');
    await expect(page.locator('.door')).toHaveCount(0);
    await page.screenshot({ path: 'reports/home-base-online/loading-1280.png' });

    releaseSession();
    await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
    await expect(page.locator('.door')).toHaveCount(1);
  });

  test('the old bespoke boot card is gone', async ({ page }) => {
    await openHomeBase(page, { programs: 1 });
    await expect(page.locator('#mode-select-loading')).toHaveCount(0);
    await expect(page.locator('body')).not.toHaveClass(/mode-select-loading/);
    expect(await page.content()).not.toContain('Loading Coach Home Base');
  });

  test('desktop drops the loader without a single community request', async ({ page }) => {
    const community = await openHomeBase(page, { programs: 2, desktop: true });
    await expect(page.locator('#page-load-overlay')).toBeHidden();
    await expect(page.locator('.door')).toHaveCount(2);
    expect(community, JSON.stringify(community)).toEqual([]);
  });
});

test.describe('screenshots', () => {
  const shots = [
    ['first-1280', { programs: 0 }],
    ['one-1280', { programs: 1 }],
    ['two-1280', { programs: 2 }],
    ['live-1280', { programs: 2, live: true }],
    ['leaderboard-1280', { programs: 2, tab: 'lb' }],
    ['two-1920', { programs: 2, width: 1920, height: 1080 }],
    ['desktop-two-1280', { programs: 2, desktop: true }],
    ['strip-two-1280', { programs: 2 }],
    ['strip-first-1280', { programs: 0, career: false }],
  ];
  for (const [name, opts] of shots) {
    test(`capture ${name}`, async ({ page }) => {
      await openHomeBase(page, opts);
      await page.mouse.move(4, 4);
      await page.screenshot({ path: `reports/home-base-online/${name}.png` });
    });
  }

  test('capture confirm-1280', async ({ page }) => {
    await openHomeBase(page, { programs: 2 });
    await page.click('[data-hb-more][data-slot="1"]');
    await page.click('[data-hb-delete]');
    await expect(page.locator('.cfm')).toBeVisible();
    await page.mouse.move(4, 4);
    await page.screenshot({ path: 'reports/home-base-online/confirm-1280.png' });
  });
});
