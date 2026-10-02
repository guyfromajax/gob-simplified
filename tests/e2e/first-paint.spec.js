// @ts-check
/**
 * First paint: no screen is shown half-built.
 *
 * Each test holds every API response back, looks at the page before any data can have
 * arrived, and asserts it shows nothing but the shared loader (Prep › Scouting, which
 * stands a shared skeleton in instead, is gated in prep-scouting.spec.js):
 * no bare titles, no placeholder values, no "NR", no footer waiting to jump. Then the
 * data lands and the page must be there.
 *
 * The full sweep of every gallery screen is the tool in first-paint-sweep.spec.js; these
 * are the gates for the screens that sweep fixed (reports/first-paint-sweep-2026-10-02.md).
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { delayApi, settle, probe } = require('./helpers/firstPaint');

test.describe.configure({ timeout: 90000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const HOLD_MS = 1200;

function franchiseQuery(extra) {
  return new URLSearchParams(Object.assign(
    { franchise_id: FID, team_id: 'Lancaster', user_team_id: 'Lancaster', mode: 'franchise' }, extra || {},
  )).toString();
}

/** Canned franchise responses; anything else goes to the seeded server. */
function franchiseApi(overrides) {
  const table = Object.assign({
    '/api/auth/me': { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' },
    '/franchise/command-center/data': FIXTURE.cc,
    '/franchise/team-data': FIXTURE.teamData,
    '/franchise/training-points': FIXTURE.trainingPoints,
    '/franchise/league-news': FIXTURE.news,
    '/franchise/standings': FIXTURE.standings,
    '/teams': FIXTURE.teams,
    '/api/gameplan': FIXTURE.gameplan,
    '/api/playbooks': FIXTURE.playbooks,
    '/api/playbooks/preview-shot-weights': FIXTURE.preview,
  }, overrides || {});
  return (request) => {
    const pathname = new URL(request.url()).pathname;
    if (Object.prototype.hasOwnProperty.call(table, pathname)) return { status: 200, body: table[pathname] };
    if (pathname.startsWith('/roster/')) return { status: 200, body: FIXTURE.roster };
    if (pathname.startsWith('/franchise/') || pathname.startsWith('/api/')) return { status: 200, body: {} };
    return null;
  };
}

/** Open `url` with the API held, and report what is visible before any of it answers. */
async function openHeld(page, url, fulfil) {
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  const tracker = await delayApi(page, HOLD_MS, fulfil);
  await page.goto(url, { waitUntil: 'commit' });
  await page.waitForTimeout(HOLD_MS - 450);
  const first = await probe(page);
  return { tracker, first };
}

/** Nothing of the page body is on show: only the loader stands. */
function expectHeldBack(first) {
  expect(first.error, 'probe').toBeUndefined();
  expect(first.overlayOn, 'the shared loader is up').toBe(true);
  expect(first.contentCount, 'page text visible before data: ' + first.sample).toBe(0);
  expect(first.flagged.map((entry) => entry.t), 'placeholders visible before data').toEqual([]);
  expect(first.headings.filter((h) => !h.chrome).map((h) => h.t), 'bare headings before data').toEqual([]);
}

async function landed(page, tracker) {
  await settle(page, tracker, 800, 30000);
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

// The shared page loader is solid (Jamie, 2026-10-02): the page fill at full opacity, so
// nothing being built behind it ghosts through. At 92% black the Office's skeleton heads
// and the default Advance label could be read under it.
const LOADER_FILL = 'rgb(11, 13, 20)';   // --bg
const STATIC = path.join(__dirname, '../../FrontEnd/static');

function loaderFill(page) {
  return page.evaluate(() => {
    const overlay = document.getElementById('page-load-overlay');
    if (!overlay) return null;
    const cs = getComputedStyle(overlay);
    return { shown: cs.display !== 'none', bg: cs.backgroundColor, opacity: cs.opacity, image: cs.backgroundImage };
  });
}

test.describe('the page loader is opaque', () => {
  const pages = [
    ['Office', '/franchise-command-center.html?' + franchiseQuery({ tab: 'home-tab' }), 'office'],
    ['a browse page (Standings)', '/franchise-command-center.html?' + franchiseQuery({ tab: 'standings-view' }), 'standings'],
    ['weekly Training', '/training.html?' + franchiseQuery({ from: 'locker-room', session_type: 'preseason' }), 'training'],
    ['court pre-game', '/court.html?' + franchiseQuery({ home: 'Lancaster', away: 'Four-Corners', my_team: 'home', week: '1' }), 'court-pregame'],
  ];
  for (const [name, url, slug] of pages) {
    test(name, async ({ page }) => {
      await stubAuth(page);
      await page.addInitScript(() => { window.alert = () => {}; });
      await delayApi(page, 2500, franchiseApi());
      await page.goto(url, { waitUntil: 'commit' });
      await page.waitForFunction(() => {
        const overlay = document.getElementById('page-load-overlay');
        return !!overlay && getComputedStyle(overlay).display !== 'none';
      });
      await page.waitForTimeout(500);
      const fill = await loaderFill(page);
      expect(fill.shown).toBe(true);
      expect(fill.bg).toBe(LOADER_FILL);       // no alpha channel: fully opaque
      expect(fill.opacity).toBe('1');
      // Whatever is under the middle of each quadrant, the loader is what is on top.
      const covered = await page.evaluate(() => {
        const overlay = document.getElementById('page-load-overlay');
        const points = [[0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9], [0.5, 0.2]];
        return points.every(([fx, fy]) => {
          const hit = document.elementFromPoint(window.innerWidth * fx, window.innerHeight * fy);
          return !!hit && (hit === overlay || overlay.contains(hit));
        });
      });
      expect(covered).toBe(true);
      if (process.env.PB_SHOTS === '1') {
        const dir = path.join(__dirname, '../../reports/first-paint-sweep');
        fs.mkdirSync(dir, { recursive: true });
        await page.screenshot({ path: path.join(dir, 'loader-solid-' + slug + '-after-1280.png'), animations: 'disabled' });
      }
    });
  }

  test('no page carries a see-through loader in its markup or in the shared script', () => {
    const script = fs.readFileSync(path.join(STATIC, 'js/shared/pageLoadOverlay.js'), 'utf8');
    expect(script).toContain("var OVERLAY_BG = 'var(--bg)'");
    expect(script).not.toMatch(/overlay\.style\.background\s*=\s*'(?!var\(--bg\))/);
    expect(script).not.toMatch(/background:color-mix/);
    const carriers = fs.readdirSync(STATIC).filter((name) => name.endsWith('.html'))
      .map((name) => [name, fs.readFileSync(path.join(STATIC, name), 'utf8')])
      .filter(([, html]) => html.includes('id="page-load-overlay"'));
    expect(carriers.map(([name]) => name).sort()).toEqual([
      'box-score.html', 'court.html', 'franchise-command-center.html', 'mode-select.html', 'set-lineup.html', 'trophy-case.html',
    ]);
    carriers.forEach(([name, html]) => {
      const tag = html.slice(html.indexOf('<div id="page-load-overlay"'));
      const open = tag.slice(0, tag.indexOf('>') + 1);
      expect(open, name).toContain('background:var(--bg);');
      expect(open, name).toContain('class="gob-scope"');     // the token resolves outside .gob
      expect(open, name).not.toMatch(/rgba\(|color-mix|transparent/);
    });
  });
});

test('shell top strip: no "NR" and no logo alt text before the season data is in', async ({ page }) => {
  const { tracker } = await openHeld(
    page, '/training-playbooks.html?' + franchiseQuery(), franchiseApi(),
  );
  const before = await page.evaluate(() => {
    const rank = document.getElementById('gob-rank-stat');
    const logo = document.querySelector('.top .top-id img');
    return {
      rankShown: !!rank && !rank.hidden && rank.getClientRects().length > 0,
      rankText: rank ? rank.textContent.trim() : '',
      logoVisibility: logo ? getComputedStyle(logo).visibility : 'none',
      logoSrc: logo ? (logo.getAttribute('src') || '') : '',
    };
  });
  expect(before.rankShown, 'rank stat shown before data: ' + before.rankText).toBe(false);
  if (!before.logoSrc) expect(before.logoVisibility).toBe('hidden');
  await landed(page, tracker);
  // FIXTURE.cc ranks the team: the stat comes back with the real answer.
  await expect(page.locator('#gob-rank-stat')).toBeVisible();
  await expect(page.locator('#gob-rank-stat')).toContainText(/#\d+|NR/);
});

test('Program select: held behind the loader until the programs are drawn', async ({ page }) => {
  const { tracker, first } = await openHeld(page, '/franchise-select-team.html', null);
  expectHeldBack(first);
  await expect(page.locator('html')).toHaveClass(/is-loading/);
  await expect(page.locator('#claim-root')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('#claim-root')).toHaveCSS('visibility', 'visible');
  await expect(page.locator('#site-footer, footer').first()).toHaveCSS('visibility', 'visible');
});

test('Team Builder: no boot line over a bare footer; the loader holds until step 1 is drawn', async ({ page, request }) => {
  const teams = await (await request.get('/teams')).json();
  const replaced = String(teams[0].object_id);
  const { tracker, first } = await openHeld(page, '/team-builder.html?replaced_object_id=' + replaced, (req) => {
    const pathname = new URL(req.url()).pathname;
    // The draft store is account-backed: answer it here so step 1 can open.
    if (pathname.startsWith('/franchise/team-builder/')) {
      return { status: 200, body: { draft_id: 'e2e-first-paint', drafts: [], budgets: {} } };
    }
    return null;
  });
  expectHeldBack(first);
  await expect(page.locator('#tb-boot')).toHaveCSS('visibility', 'hidden');
  await settle(page, tracker, 800, 30000);
  // Step 1, or the page's own error card: either way the loader is gone and the boot
  // line is not what is left standing.
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await expect(page.locator('#tb-boot')).toBeHidden();
  await expect.poll(() => page.evaluate(() => (
    !document.getElementById('tb-app').hidden || !document.getElementById('tb-fatal').hidden
  ))).toBe(true);
});

test('Team Builder with no program to replace hands over to program select without lifting the loader', async ({ page }) => {
  await stubAuth(page);
  const seen = [];
  await page.exposeFunction('__fpSeen', (state) => { seen.push(state); });
  await page.addInitScript(() => {
    // Record, on every frame, whether the page body was on show without the loader.
    const tick = () => {
      const overlay = document.getElementById('page-load-overlay');
      const loaderUp = !!overlay && getComputedStyle(overlay).display !== 'none';
      const held = document.documentElement.classList.contains('is-loading');
      if (document.body && !loaderUp && !held) window.__fpSeen(location.pathname);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  await page.goto('/team-builder.html');
  await page.waitForURL(/franchise-select-team\.html/);
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await expect(page.locator('#claim-root')).toBeVisible();
  // The Team Builder page itself was never shown bare.
  expect(seen.filter((pathname) => pathname.indexOf('team-builder') !== -1)).toEqual([]);
});

test('Training playbook: no bare Offense / Defense titles, "—" docks or live Save before data', async ({ page }) => {
  const { tracker, first } = await openHeld(
    page, '/training-playbooks.html?' + franchiseQuery(), franchiseApi(),
  );
  expectHeldBack(first);
  await expect(page.locator('.tp-shell')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('.tp-shell')).toHaveCSS('visibility', 'visible');
  await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
  await expect(page.locator('#tp-defense-grid .tp-card').first()).toBeVisible();
});

test('Training playbook: a failed load still lifts the loader', async ({ page }) => {
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  await page.route('**/api/playbooks**', (route) => route.fulfill({
    status: 500, contentType: 'application/json', body: '{"detail":"nope"}',
  }));
  await page.goto('/training-playbooks.html?' + franchiseQuery());
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await expect(page.locator('#tp-back')).toBeVisible();
});

test('Weekly training: the form is held until the week is in, so the default budget is never shown', async ({ page }) => {
  const points = Object.assign({}, FIXTURE.trainingPoints, { training_points: 30 });
  const { tracker, first } = await openHeld(
    page, '/training.html?' + franchiseQuery({ from: 'locker-room', session_type: 'preseason' }),
    franchiseApi({ '/franchise/training-points': points }),
  );
  expectHeldBack(first);
  await expect(page.locator('#training-view')).toHaveCSS('visibility', 'hidden');
  // The markup's default is 24: it must not be what the coach is shown.
  await landed(page, tracker);
  await expect(page.locator('#training-view')).toHaveCSS('visibility', 'visible');
  await expect(page.locator('#req-points-total')).toHaveText('30');
  await expect(page.locator('#training-view .ps').first()).toBeVisible();
});

test('Archetype leaderboard: no "Loading…" line with the footer under it', async ({ page }) => {
  const { tracker, first } = await openHeld(page, '/coaching-archetypes-leaderboard.html', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/leaderboard/by-archetype') return { status: 200, body: {} };
    return null;
  });
  expectHeldBack(first);
  await expect(page.locator('.alb')).toHaveCSS('visibility', 'hidden');
  await expect(page.locator('#site-footer')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('#alb-grid .alb-card')).toHaveCount(18);
  await expect(page.locator('#site-footer')).toHaveCSS('visibility', 'visible');
});

test('Account: no placeholder "Coach", "0" or empty cards before the account is in', async ({ page }) => {
  const { tracker, first } = await openHeld(page, '/account.html', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/auth/me') {
      return { status: 200, body: { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com', geek_points: 1250 } };
    }
    return null;
  });
  expectHeldBack(first);
  await expect(page.locator('.acct')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('#acct-name')).toHaveText('e2e');
  await expect(page.locator('#gp-total')).toHaveText('1,250');
});

// ── Playbook report, cut players, box score with no game (the sweep's items 31, 29, 28) ──
const NF_SHOTS = process.env.NF_SHOTS === '1';
const NF_OUT = path.join(__dirname, '../../reports/news-followups');

async function nfShots(page, name) {
  if (!NF_SHOTS) return;
  fs.mkdirSync(NF_OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.mouse.move(size.width - 6, size.height - 6);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(NF_OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
}

/** Where each section head sits, by its text. */
function headTops(page, scope) {
  return page.locator(scope + ' h2, ' + scope + ' h3').evaluateAll((nodes) => {
    const out = {};
    nodes.filter((node) => node.getClientRects().length > 0).forEach((node) => {
      out[node.textContent.trim()] = Math.round(node.getBoundingClientRect().top + window.scrollY);
    });
    return out;
  });
}

test('Playbook report: no bare section heads before data, and no head moves once it is shown', async ({ page }) => {
  // Record every frame in which the page body is on show, with where its heads sit.
  const frames = [];
  await page.exposeFunction('__pbFrame', (frame) => { frames.push(frame); });
  await page.addInitScript(() => {
    const tick = () => {
      const shell = document.querySelector('.playbook-report-shell');
      const overlay = document.getElementById('page-load-overlay');
      const loaderUp = !!overlay && getComputedStyle(overlay).display !== 'none';
      if (shell && !loaderUp && getComputedStyle(shell).visibility !== 'hidden') {
        const heads = {};
        shell.querySelectorAll('h2, h3').forEach((node) => {
          if (node.getClientRects().length) heads[node.textContent.trim()] = Math.round(node.getBoundingClientRect().top + window.scrollY);
        });
        window.__pbFrame({ heads, rows: shell.querySelectorAll('.report-list > *').length });
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const { tracker, first } = await openHeld(page, '/playbook-report.html?' + franchiseQuery(), franchiseApi({
    '/franchise/play-next-game': { home: 'Lancaster', away: 'Four-Corners', home_id: 'Lancaster', away_id: 'Four-Corners', week: 1 },
  }));
  expectHeldBack(first);
  await expect(page.locator('html')).toHaveClass(/is-loading/);
  await expect(page.locator('.playbook-report-shell')).toHaveCSS('visibility', 'hidden');
  expect(frames, 'the page body was on show before its data').toEqual([]);

  await landed(page, tracker);
  await expect(page.locator('.playbook-report-shell')).toHaveCSS('visibility', 'visible');
  await expect(page.locator('#offense-motion-list > *').first()).toBeVisible();
  // The markup's placeholder ("vs Opponent") was never on show; the real opponent is.
  await expect(page.locator('#report-subhead')).toHaveText(/^vs Four[ -]Corners$/);
  await page.waitForTimeout(600);
  // Every frame the page was on show, it already had its rows and its heads were where
  // they end up: "Set Plays" and "Zone" do not jump, and no head appears late.
  const settled = await headTops(page, '.playbook-report-shell');
  expect(Object.keys(settled)).toEqual(expect.arrayContaining([
    'Offense', 'Motion', 'Set Plays', 'Defense', 'Man', 'Zone', 'Fast Breaks', 'Half-Court Traps',
  ]));
  expect(frames.length).toBeGreaterThan(0);
  frames.forEach((frame) => {
    expect(frame.rows, 'shown with no rows').toBeGreaterThan(0);
    expect(frame.heads).toEqual(settled);
  });
  await nfShots(page, 'playbook-report');
});

test('Playbook report: a failed load still lifts the loader', async ({ page }) => {
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  await page.route('**/api/playbooks**', (route) => route.fulfill({
    status: 500, contentType: 'application/json', body: '{"detail":"nope"}',
  }));
  await page.goto('/playbook-report.html?' + franchiseQuery());
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await expect(page.locator('#back-btn')).toBeVisible();
});

test('Cut players, nothing to cut: the heading and table shell are never shown before "No Cuts Required"', async ({ page }) => {
  // Record every frame in which the page is on show without the modal over it.
  const bare = [];
  await page.exposeFunction('__cutBare', (text) => { bare.push(text); });
  await page.addInitScript(() => {
    const tick = () => {
      const view = document.getElementById('cut-players-view');
      const overlay = document.getElementById('page-load-overlay');
      const modal = document.getElementById('cut-modal-backdrop');
      const loaderUp = !!overlay && getComputedStyle(overlay).display !== 'none';
      const modalUp = !!modal && modal.classList.contains('is-visible');
      if (view && !loaderUp && !modalUp && getComputedStyle(view).visibility !== 'hidden') {
        const head = view.querySelector('h1');
        window.__cutBare(head ? head.textContent.trim() : 'view');
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const { tracker, first } = await openHeld(page, '/cut-players.html?' + franchiseQuery(), franchiseApi());
  expectHeldBack(first);
  await expect(page.locator('#cut-players-view')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('#cut-modal-title')).toHaveText('No Cuts Required');
  await expect(page.locator('#cut-modal-title')).toBeVisible();
  await page.waitForTimeout(500);
  expect(bare, 'the page was on show without the modal').toEqual([]);
  await nfShots(page, 'cut-players-no-cuts');
});

test('Cut players, cuts to make: held until the roster and the count are in, then the table', async ({ page }) => {
  const cc = Object.assign({}, FIXTURE.cc, { cut_required: true, cut_count: 3 });
  const { tracker, first } = await openHeld(
    page, '/cut-players.html?' + franchiseQuery(), franchiseApi({ '/franchise/command-center/data': cc }),
  );
  expectHeldBack(first);
  await expect(page.locator('#cut-players-view')).toHaveCSS('visibility', 'hidden');
  await landed(page, tracker);
  await expect(page.locator('#cut-players-view')).toHaveCSS('visibility', 'visible');
  await expect(page.locator('#cut-players-view h1')).toHaveText('Assign Practice Squad');
  await expect(page.locator('#cut-players-body tr')).toHaveCount(FIXTURE.roster.players.length);
  await expect(page.locator('#cut-status')).toContainText('3');
});

test('Cut players: a failed load still lifts the loader', async ({ page }) => {
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  await page.route('**/roster/**', (route) => route.fulfill({
    status: 500, contentType: 'application/json', body: '{"detail":"nope"}',
  }));
  await page.goto('/cut-players.html?' + franchiseQuery());
  await expect(page.locator('html')).not.toHaveClass(/is-loading/);
  await expect(page.locator('#cut-modal-message')).toHaveText('Unable to load practice squad assignment data.');
});

for (const [name, query, api] of [
  ['opened without a game id', {}, null],
  ['a game that cannot be loaded', { game_id: 'aaaaaaaaaaaaaaaaaaaaaaaa' }, { status: 404, body: { detail: 'Game not found' } }],
]) {
  test('Box score, ' + name + ': one card says so, no bare section heads', async ({ page }) => {
    await stubAuth(page);
    await page.addInitScript(() => { window.alert = () => {}; });
    const fulfil = franchiseApi();
    await page.route('**/*', async (route) => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;
      if (api && pathname.startsWith('/api/game/')) {
        return route.fulfill({ status: api.status, contentType: 'application/json', body: JSON.stringify(api.body) });
      }
      const canned = (request.resourceType() === 'fetch' || request.resourceType() === 'xhr') ? fulfil(request) : null;
      if (canned) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(canned.body) });
      return route.continue();
    });
    await page.goto('/box-score.html?' + franchiseQuery(query));
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    const card = page.locator('#box-score-container .box-score-empty');
    await expect(card).toBeVisible();
    await expect(card).toContainText('This box score could not be opened.');
    await page.waitForTimeout(400);
    const seen = await probe(page);
    // No "Quarter Scoring / Player Of The Game / Player Stats" heads, and no placeholder
    // header ("Away Team 0 @ Home Team 0").
    expect(seen.headings.filter((h) => !h.chrome).map((h) => h.t)).toEqual([]);
    expect(seen.sample).not.toMatch(/Quarter Scoring|Player Of The Game|Player Stats|Away Team|Home Team/);
    expect(seen.flagged.filter((entry) => !entry.chrome).map((entry) => entry.t)).toEqual([]);
    await expect(page.locator('#box-score-header')).toBeHidden();
    await expect(page.locator('#quarter-scoring-section')).toBeHidden();
    // The way out is still there, and it works.
    const back = page.locator('#locker-room-button');
    await expect(back).toBeVisible();
    if (!api) await nfShots(page, 'box-score-no-game');
    await back.click();
    await expect(page).toHaveURL(/franchise-command-center\.html|mode-select\.html/, { timeout: 20000 });
  });
}
