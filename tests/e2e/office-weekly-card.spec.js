// @ts-check
/**
 * Chapter 7 · the Office weekly "Since last week" card (.wkc).
 *
 * Jamie's overrides: NO team-colour wash (win or loss) — the card is neutral
 * chrome and the white WIN plate / outline LOSS tag carries the result; ▲/▼
 * deltas are neutral (no green/red). Reward gold appears ONLY on the
 * exceptional-gain marker. The entrance plays once per result_key; STING_WIN on a
 * win's first showing only.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-weekly';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const REWARD_GOLD = 'rgb(240, 197, 96)';
const SHOTS = path.join(__dirname, '../../reports/office-weekly-card');

function changes(xg) {
  return [
    { player_id: 'p-park', name: 'Devin Park', attribute: 'SH', from: 7, to: 8, delta: 1 },
    { player_id: 'p-monroe', name: 'Isaiah Monroe', attribute: 'AG', from: 6, to: 7, delta: 1 },
    { player_id: 'p-monroe', name: 'Isaiah Monroe', attribute: 'ND', from: 5, to: 6, delta: 1 },
    { player_id: 'p-kerr', name: 'Silas Kerr', attribute: 'ST', from: 6, to: 5, delta: -1 },
  ].map(function (row, i) {
    if (xg && i === 0) return Object.assign({}, row, { from: 6, to: 8, delta: 2, exceptional: true });
    return row;
  });
}

function digest(kind, resultKey) {
  const won = kind === 'win' || kind === 'gain';
  const xg = kind === 'gain' || kind === 'lossgain';
  const also = won ? null : {
    kind: 'archetype_evolution', title: 'Coach archetype',
    line: 'Systems Coach established', href: '/coaching-archetypes.html',
  };
  const items = won ? [] : [
    { kind: 'archetype_evolution', title: 'Coach archetype', line: 'Systems Coach established', href: '/coaching-archetypes.html' },
    { kind: 'bracket_update', title: 'Tournament update', line: 'The tournament bracket moved this week.', href: '/franchise-command-center.html?tab=tournament-view' },
    { kind: 'recruit_visit', title: 'Recruit visit', line: 'Ellis Clemons is visiting this week.', href: '/recruiting.html' },
  ];
  return {
    state: 'regular',
    what_moved: {
      national_rank: won ? { now: 14, prev: 17, delta: 3 } : { now: 17, prev: 14, delta: -3 },
      conference_standing: won ? { now: 2, prev: 3, delta: 1 } : { now: 3, prev: 2, delta: -1 },
      record: won ? { wins: 16, losses: 5 } : { wins: 15, losses: 6 },
      streak: won ? 'W4' : 'L1',
      attribute_changes: changes(xg),
    },
    team_snapshot: { state: 'ready', chemistry: { value: 18, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: {
      result_key: resultKey || (kind + '-key'),
      week: 14, user_won: won, site: won ? 'home' : 'away',
      user_is_home: won,
      home_team_id: won ? TID : 'opp-team', away_team_id: won ? 'opp-team' : TID,
      home_team_name: won ? 'Lawrence' : 'Maple Ridge',
      away_team_name: won ? 'Four Corners' : 'Lawrence',
      home_score: won ? 78 : 70, away_score: won ? 71 : 64,
      opponent_team_id: 'opp-team',
      opponent_team_name: won ? 'Four Corners' : 'Maple Ridge',
      opponent_rank: won ? 21 : 9,
      round_name: null,
      leader_role: won ? 'potg' : 'team_leader',
      // A real served headshot uuid, so the screenshot proves the image path (not
      // the silhouette/initials fallback). Local host => /images/players/<id>.png.
      leader: { player_id: '030d9bd9-125d-4ad5-a49c-12b528d7ae89', name: 'Devin Park', stats: { pts: won ? 24 : 19, reb: won ? 9 : 6, ast: won ? 5 : 3 } },
      headline: won ? 'Park’s 24 carry Lawrence past Four Corners' : null,
      box_score: { path: '/box-score.html', params: { mode: 'franchise', franchise_id: FID, game_id: 'g-1' } },
    },
    next_game: { week: 15, site: 'away', opponent: 'Four Corners', rank: 21, record: { wins: 12, losses: 9 }, conference: 2 },
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [],
    recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 },
    signing_day: null,
    season_preview: null,
    also: also,
    weekly_card_items: items,
  };
}

function cc(kind, resultKey) {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lawrence',
    week: 15, season: 3, current_season: 3,
    training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 15, counts: {} },
    office_digest: digest(kind, resultKey),
    pending_championship_moments: [],
    moments: [], moments_for_this_visit: [], weekly_card_items: [],
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data, seenSting) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { await route.continue(); return; }
    if (seenSting && /sting-win\.wav/.test(request.url())) seenSting.push(request.url());
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') { await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' }); return; }
    if (pathname === '/app-config') { await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' }); return; }
    if (pathname === '/teams') { await fulfillJson(route, [{ name: 'Lawrence', display_name: 'Lawrence', object_id: TID, _id: TID }]); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, data); return; }
    await fulfillJson(route, {});
  });
}

async function openOffice(page, data, seenSting) {
  await stubAuth(page);
  await installApi(page, data, seenSting);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
  await expect(page.locator('#office-root .wkc')).toBeVisible();
}

function bg(page, sel) {
  return page.locator(sel).evaluate((el) => {
    const cs = getComputedStyle(el);
    return cs.backgroundColor + ' | ' + cs.backgroundImage;
  });
}

function isNeutralGray(rgb) {
  const m = rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const r = +m[1], g = +m[2], b = +m[3];
  return Math.abs(r - g) <= 4 && Math.abs(g - b) <= 4 && Math.abs(r - b) <= 4;
}

test.describe('weekly card', () => {
  test('win renders: white WIN plate, neutral card, POTG, four badges, no gold', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('win'));
    const wkc = page.locator('#office-root .wkc');
    await expect(wkc).toHaveClass(/is-win/);
    await expect(wkc.locator('.wtag')).toHaveText('WIN');
    // WIN tag is a white plate (opaque background), not green/red.
    const tagBg = await wkc.locator('.wtag').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(tagBg).not.toBe('rgba(0, 0, 0, 0)');
    expect(tagBg).not.toBe(REWARD_GOLD);
    await expect(wkc.locator('.pg2-id .eyebrow')).toHaveText('Player of the Game');
    await expect(wkc.locator('.bdg')).toHaveCount(4);
    await expect(wkc.locator('.wkc-hl')).toBeVisible();
    // No reward gold anywhere on a plain win (no exceptional gain).
    await expect(wkc.locator('.gc.xg')).toHaveCount(0);
    await expect(wkc.locator('.xg-key')).toHaveCount(0);
    await page.screenshot({ path: path.join(SHOTS, 'win-1280.png') });
  });

  test('no team-colour wash on win or loss (both neutral, identical)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, cc('win'));
    const winBg = await bg(page, '#office-root .wkc');
    await openOffice(page, cc('loss'));
    const lossBg = await bg(page, '#office-root .wkc');
    expect(winBg).toBe(lossBg);
    // and neither carries the seeded team colour (navy #27408e ~ rgb(39,64,142))
    expect(winBg).not.toContain('39, 64, 142');
  });

  test('loss is dignified: outline LOSS tag, Team leader, scores t87, no gold', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('loss'));
    const wkc = page.locator('#office-root .wkc');
    await expect(wkc).toHaveClass(/is-loss/);
    const tagBg = await wkc.locator('.wtag').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(tagBg).toBe('rgba(0, 0, 0, 0)'); // outline, not a plate
    await expect(wkc.locator('.pg2-id .eyebrow')).toHaveText('Team leader');
    // Both scores at the same tone (loser not dimmed).
    const tones = await wkc.locator('.sb2-p').evaluateAll((els) => els.map((e) => getComputedStyle(e).color));
    expect(tones[0]).toBe(tones[1]);
    // Deltas neutral, never red.
    const em = await wkc.locator('.bdg-v em').first().evaluate((e) => getComputedStyle(e).color);
    expect(isNeutralGray(em)).toBe(true);
    await page.screenshot({ path: path.join(SHOTS, 'loss-1280.png') });
  });

  test('deltas are neutral on a win too (no green)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, cc('win'));
    const em = await page.locator('#office-root .wkc .bdg-v em').first().evaluate((e) => getComputedStyle(e).color);
    expect(isNeutralGray(em)).toBe(true);
    const chipDelta = await page.locator('#office-root .wkc .gc i').first().evaluate((e) => getComputedStyle(e).color);
    expect(isNeutralGray(chipDelta)).toBe(true);
  });

  test('exceptional gain is the only gold: marker chip, gold delta, and the key', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('gain'));
    const wkc = page.locator('#office-root .wkc');
    await expect(wkc.locator('.gc.xg')).toHaveCount(1);
    await expect(wkc.locator('.xg-key')).toHaveText('Exceptional gain');
    const goldDelta = await wkc.locator('.gc.xg i').evaluate((e) => getComputedStyle(e).color);
    expect(goldDelta).toBe(REWARD_GOLD);
    const keyColor = await wkc.locator('.xg-key').evaluate((e) => getComputedStyle(e).color);
    expect(keyColor).toBe(REWARD_GOLD);
    // Chrome stays gold-free: a non-xg chip delta and the badges are neutral.
    const plainChip = await wkc.locator('.gc:not(.xg) i').first().evaluate((e) => getComputedStyle(e).color);
    expect(plainChip).not.toBe(REWARD_GOLD);
    await page.screenshot({ path: path.join(SHOTS, 'gain-1280.png') });
  });

  test('the exceptional marker still shows on a loss', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('lossgain'));
    const wkc = page.locator('#office-root .wkc');
    await expect(wkc).toHaveClass(/is-loss/);
    await expect(wkc.locator('.gc.xg')).toHaveCount(1);
    const goldDelta = await wkc.locator('.gc.xg i').evaluate((e) => getComputedStyle(e).color);
    expect(goldDelta).toBe(REWARD_GOLD);
    await page.screenshot({ path: path.join(SHOTS, 'lossgain-1280.png') });
  });

  test('the Also row folds the top moment, and "+N more" expands the rest inline', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('loss'));
    const wkc = page.locator('#office-root .wkc');
    await expect(wkc.locator('.wkc-also').first()).toContainText('Coach archetype');
    // 3 weekly items => the Also row + "+2 more".
    const more = wkc.locator('.wkc-more');
    await expect(more).toHaveText('+2 more');
    await expect(wkc.locator('.wkc-extra')).toBeHidden();
    await more.click();
    await expect(wkc.locator('.wkc-extra')).toBeVisible();
    await expect(wkc.locator('.wkc-extra .wkc-also')).toHaveCount(2);
    await expect(more).toHaveText('Show less');
    await page.screenshot({ path: path.join(SHOTS, 'also-expanded-1280.png') });
  });

  test('the entrance and the win sting play once per result_key, not on reload', async ({ page }) => {
    const sting = [];
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, cc('win', 'once-key'), sting);
    // First showing: the office arrives (the entrance class sits on #office-root).
    await expect(page.locator('#office-root')).toHaveClass(/arriving/);
    await page.waitForTimeout(1100); // past the 720ms cue
    expect(sting.length, 'sting requested on first win').toBeGreaterThan(0);

    // Second load, same result_key: final state, no arrival, no sting.
    const sting2 = [];
    await installApi(page, cc('win', 'once-key'), sting2);
    await page.reload();
    await page.waitForFunction(() => {
      const root = document.getElementById('office-root');
      return root && root.getAttribute('aria-busy') === 'false';
    });
    await expect(page.locator('#office-root .wkc')).toBeVisible();
    await expect(page.locator('#office-root')).not.toHaveClass(/arriving/);
    await page.waitForTimeout(1100);
    expect(sting2.length, 'no sting on the second load').toBe(0);
  });

  test('a loss never plays the sting', async ({ page }) => {
    const sting = [];
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, cc('loss', 'loss-key'), sting);
    await page.waitForTimeout(1100);
    expect(sting.length).toBe(0);
  });

  test('reduced motion shows the final state (no arrival, no count-up)', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, cc('win', 'rm-key'));
    await expect(page.locator('#office-root')).not.toHaveClass(/arriving/);
    // Scores are final immediately, not counting from 0.
    const top = await page.locator('#office-root .wkc .sb2-p').first().textContent();
    expect(top).toBe('78');
  });

  test('the card fits column 1 at 1280x720 and 1920x1080', async ({ page }) => {
    for (const [w, h] of [[1280, 720], [1920, 1080]]) {
      for (const kind of ['gain', 'lossgain']) {
        await page.setViewportSize({ width: w, height: h });
        await openOffice(page, cc(kind));
        const fit = await page.evaluate(() => {
          const wkc = document.querySelector('#office-root .wkc');
          const col = wkc && wkc.closest('.office-col');
          if (!wkc || !col) return { ok: false };
          const cr = col.getBoundingClientRect();
          const wr = wkc.getBoundingClientRect();
          return {
            ok: true,
            widerThanCol: wr.right > cr.right + 1,
            belowFold: wr.bottom > window.innerHeight + 1,
          };
        });
        expect(fit.ok, kind + ' ' + w + 'x' + h).toBe(true);
        expect(fit.widerThanCol, kind + ' ' + w + 'x' + h + ' wider than column').toBe(false);
        expect(fit.belowFold, kind + ' ' + w + 'x' + h + ' below fold').toBe(false);
      }
    }
  });

  test('capture win-1920', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.emulateMedia({ reducedMotion: 'reduce' }); // settled '&still' state for the screenshot
    await openOffice(page, cc('win'));
    await page.screenshot({ path: path.join(SHOTS, 'win-1920.png') });
  });
});

// PR2 follow-up: the offline Home Base doors showed generic swirl art in
// reports/home-base-offline/populated-1280.png. Cause = the PR2 fixture seeded
// franchise display names ("Lawrence Eagles") whose derived slug has no on-disk
// art; the door art resolves from the display name via nameToTeamSlug, so a
// non-canonical name falls back to general art. Top Seasons used the server
// team_slug ("lawrence") and showed real art. It is NOT a desktop bug: the door
// path is profile-independent, and a real franchise's user_team_id is the
// canonical team name. This proves it: real core names ("Lawrence", "Chapel
// Hill") render their real door banners on the same desktop/loopback path.
test('door-art check: real program names render real door banners (desktop)', async ({ page }) => {
  const HFID = 'f-doors';
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  const list = [
    { franchise_id: 'f1', home_slot: 1, user_team_id: 'Lawrence', user_team_object_id: 'obj-f1', week: 14, current_season: 3, last_played_at: '2026-09-21T10:00:00Z' },
    { franchise_id: 'f2', home_slot: 2, user_team_id: 'Chapel Hill', user_team_object_id: 'obj-f2', week: 12, current_season: 3, last_played_at: '2026-09-20T10:00:00Z' },
  ];
  await page.route('**/franchise/list', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ franchises: list, count: 2, max: 2, most_recent_franchise_id: 'f1' }) }));
  await page.route('**/teams', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list.map((f) => ({ object_id: f.user_team_object_id, name: f.user_team_id, natl_rank: 9 }))) }));
  await page.route('**/franchise/command-center/data**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current_season: 3, week: 14 }) }));
  await page.route('**/franchise/coach-career', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ record: { wins: 0, losses: 0 }, titles_total: 0, seasons_completed: 0, geek_points: 0, trophies: [], top_seasons: [] }) }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/mode-select.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.door')).toHaveCount(2);
  // The door banners resolve to the real per-team files, not the general fallback.
  const srcs = await page.locator('.door .door-art img').evaluateAll((imgs) => imgs.map((i) => i.getAttribute('src')));
  expect(srcs.length).toBe(2);
  expect(srcs.some((s) => /lawrence/i.test(s))).toBe(true);
  expect(srcs.every((s) => !/general_banner/i.test(s))).toBe(true);
  // And they actually load (naturalWidth > 0), not broken images.
  const loaded = await page.locator('.door .door-art img').evaluateAll((imgs) => imgs.map((i) => i.complete && i.naturalWidth > 0));
  expect(loaded.every(Boolean)).toBe(true);
  await page.mouse.move(4, 4);
  await page.screenshot({ path: path.join(SHOTS, 'home-base-doors-1280.png') });
});
