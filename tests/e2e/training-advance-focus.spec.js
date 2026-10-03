const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/training-advance-focus');
const V3_OUT = path.join(__dirname, '../../reports/v3-office');
const TEAM_OBJECT_ID = FIXTURE.cc.user_team_object_id;
const CAPTURE_BEFORE = process.env.TRAINING_ADVANCE_BEFORE === '1';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function inSeasonCc() {
  const cc = clone(FIXTURE.cc);
  cc.week = 12;
  cc.session_type = 'in-season';
  cc.training_completed = false;
  cc.training_disabled_for_postseason = false;
  cc.training_disabled_for_eos = false;
  return cc;
}

function inSeasonPoints() {
  const points = clone(FIXTURE.trainingPoints);
  points.week = 12;
  points.is_camp_week = false;
  points.is_first_training = false;
  points.training_points = 24;
  points.training_unavailable = false;
  return points;
}

function campCc() {
  return clone(FIXTURE.cc);
}

function campPoints() {
  return clone(FIXTURE.trainingPoints);
}

function officeWithChangesCc() {
  const cc = inSeasonCc();
  cc.training_completed = true;
  cc.office_digest = {
    state: 'ready',
    result: { week: 12, user_won: true, site: 'home', home_score: 70, away_score: 60 },
    next_game: { week: 13, opponent: 'Four Corners' },
    what_moved: {
      national_rank: { now: 36, prev: 40, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 8, losses: 4 },
      streak: 'W2',
      attribute_changes: ['Amy', 'Bea', 'Cal', 'Dee', 'Eve', 'Fay'].map((name, i) => ({
        player_id: 'p-' + i,
        name: name,
        attribute: 'ball_handling',
        from: 4,
        to: 6,
        delta: 2,
      })),
    },
    team_snapshot: { state: 'ready', chemistry: { value: 12, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    conference_standings: { conference: 1, region: 'A', rows: [] },
    recruiting_wire: { events: [] },
    todos: [],
  };
  return cc;
}

function postWeek26Cc() {
  const cc = clone(FIXTURE.cc);
  cc.week = 28;
  cc.session_type = 'in-season';
  cc.training_completed = true;
  cc.training_disabled_for_postseason = true;
  return cc;
}

function tokenisedReport(cc, lastSubmit) {
  const leaf = lastSubmit && lastSubmit.training_data && lastSubmit.training_data.coaching_focus;
  const coaching_focus = leaf === 'authoritarian-discipline'
    ? {
      archetype: 'authoritarian',
      sub_option: 'authoritarian-discipline',
      leaf_display_name: 'Discipline',
    }
    : {
      archetype: 'systems-coach',
      sub_option: 'systems-coach-offense',
      leaf_display_name: 'Offense',
    };
  return {
    week: cc.week || 12,
    upcoming_opponent: 'Four Corners',
    coaching_focus,
    players: [],
    player_changes: {},
    team_attributes: {
      shot_threshold: 0,
      rebound_modifier: 1,
      offensive_efficiency: 4,
      defensive_efficiency: 2,
      fb_efficiency: 1,
      pt_efficiency: 6,
      fight: 2,
      discipline: 3,
      team_chemistry: 8,
      fb_opp_modifier: -2,
      pt_opp_modifier: -1,
    },
    team_changes: { offensive_efficiency: 1, pt_efficiency: 2 },
    plays_data: {},
    scouting_data: {},
    training_notes: [
      { title: 'Practice Player Of The Week', body: 'Roger Henrich' },
      { title: 'Biggest Regression', body: 'No Significant Updates' },
      { title: 'Most Positive Locker Room Influence', body: 'Roger Henrich' },
      { title: 'Strong Cumulative Increase', body: 'Inside Defense' },
      { title: 'Strongest Defensive Set', body: 'Man' },
      { title: 'Strongest Offensive Plays', body: 'Horn' },
      { title: 'Fast Break Readiness', body: 'Ready' },
      { title: 'Press/Trap Readiness', body: 'Improving' },
      { title: 'Player Energy Levels', body: 'No Significant Updates' },
    ],
  };
}


async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, extra) {
  const opts = extra || {};
  const cc = opts.cc || inSeasonCc();
  const points = opts.points || inSeasonPoints();
  const submits = opts._submits;
  await page.route('**/*', async (route) => {
    const request = route.request();
    const method = request.method();
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
      return fulfillJson(route, Object.assign({
        user_id: 'e2e-user',
        username: 'e2e',
        email: 'e2e@example.com',
        tutorial_state: { game_id: 'g-tut', step: 'situation' },
      }, opts.me || {}));
    }
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, points);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      const body = request.postDataJSON() || {};
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    if (pathname === '/franchise/run-training/user') {
      if (submits) submits.push({ kind: 'user', body: request.postData() });
      if (opts.lastSubmit) {
        try { Object.assign(opts.lastSubmit, request.postDataJSON() || {}); }
        catch (err) { /* keep prior */ }
      }
      return fulfillJson(route, { status: 'success' });
    }
    if (pathname === '/franchise/run-training/cpu-train') {
      if (submits) submits.push({ kind: 'cpu' });
      return fulfillJson(route, {
        status: 'success',
        redirect: '/training-report.html?mode=franchise&franchise_id=' + FID + '&from=training',
      });
    }
    if (pathname === '/franchise/play-next-game') {
      return fulfillJson(route, {
        home: 'Lancaster',
        away: 'Four-Corners',
        week: cc.week,
        home_id: TEAM,
        away_id: 'Four-Corners',
      });
    }
    if (pathname === '/franchise/training-report') {
      if (opts.reportGets) {
        let week = '';
        try { week = new URL(request.url()).searchParams.get('week') || ''; }
        catch (err) { week = ''; }
        opts.reportGets.push({ week, url: request.url() });
      }
      return fulfillJson(route, tokenisedReport(cc, opts.lastSubmit));
    }
    return fulfillJson(route, {});
  });
}

async function resetScroll(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
    document.querySelectorAll('.main, .main.scroll').forEach((el) => { el.scrollTop = 0; });
  });
}

async function expectHeaderVisible(page) {
  const geom = await page.evaluate(() => {
    const main = document.getElementById('gob-main');
    const meta = document.querySelector('.header-meta-line');
    const back = document.querySelector('#locker-room-btn');
    const box = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, height: r.height };
    };
    const mb = box(meta);
    const bb = box(back);
    return {
      windowScrollY: window.scrollY,
      gobMainScrollTop: main ? main.scrollTop : null,
      meta: mb,
      back: bb,
      metaFullyVisible: !!(mb && mb.top >= 0 && mb.bottom <= window.innerHeight && mb.height > 4),
      backFullyVisible: !!(bb && bb.top >= 0 && bb.bottom <= window.innerHeight && bb.height > 4),
    };
  });
  expect(geom.windowScrollY, JSON.stringify(geom)).toBe(0);
  expect(geom.gobMainScrollTop, JSON.stringify(geom)).toBe(0);
  expect(geom.metaFullyVisible, JSON.stringify(geom)).toBe(true);
  expect(geom.backFullyVisible, JSON.stringify(geom)).toBe(true);
}

async function capturePage(page, dest) {
  await resetScroll(page);
  const host = new URL(page.url()).pathname;
  if (host === '/training.html' || host === '/training-report.html') {
    await page.waitForFunction(() => {
      if (!document.documentElement.classList.contains('gob-focus')) return false;
      if (document.querySelector('nav.rail')) return false;
      if (document.getElementById('play-now')) return false;
      if ((document.body.innerText || '').includes('STARTING')) return false;
      return true;
    });
  }
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  await page.screenshot({ path: dest, animations: 'disabled' });
}

function fccQuery(tab) {
  const q = new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab: tab,
    from: 'command_center',
  });
  return q.toString();
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

async function openOffice(page, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/franchise-command-center.html?' + fccQuery('home-tab'));
  await waitOverlay(page);
}

async function openPrepTraining(page, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/franchise-command-center.html?' + fccQuery('training-view'));
  await waitOverlay(page);
}

async function allocateClassic24(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.slider').forEach((el, i) => {
      el.value = i === 0 ? '5' : (i < 5 ? '4' : (i === 5 ? '3' : '0'));
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  await page.locator('label.archetype-option', { hasText: 'Discipline' }).click();
}

const EXPECTED_USER_BODY = {
  franchise_id: FID,
  team_id: '69a6fcb68d2c56aa82e48a54',
  training_data: {
    player_drills: {
      offense: { inside: 5, outside: 4 },
      defense: { inside: 4, outside: 4 },
      technical: { passing: 4, ball_handling: 3, rebounding: 0 },
      weight_room: { strength: 0, agility: 0 },
    },
    team_drills: {
      team_offense: { install: 0 },
      team_defense: { install: 0 },
      fast_breaks: { offense_install: 0, defense_install: 0 },
      scrimmages: 0,
      presses_traps: { defense_install: 0, offense_install: 0 },
    },
    general: { conditioning: 0, free_throws: 0, film_study: 0, breaks: 0 },
    coaching_focus: 'authoritarian-discipline',
    playbook_training_mode: 'current-playbooks',
    training_playbook_focus: null,
  },
};

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('today or new flow shots 1280 / 1920', async ({ page }) => {
  test.skip(!CAPTURE_BEFORE, 'before-only capture');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openPrepTraining(page);
  await expect(page.locator('#training-view .slider, #training-view .pdg-grid, body.training-page .slider').first()).toBeVisible({ timeout: 30000 });
  await capturePage(page, path.join(OUT, 'before-prep-player-training-1280.png'));
  await capturePage(page, path.join(OUT, 'before-flow-in-app-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await resetScroll(page);
  await capturePage(page, path.join(OUT, 'before-prep-player-training-1920.png'));
});

test('a) training week Advance → focus → allocate → Submit → Report → Office', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  const submits = [];
  const lastSubmit = {};
  const reportGets = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { _submits: submits, lastSubmit, reportGets });
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs')).toHaveCount(0);
  await expect(page.locator('#play-now.advance')).toHaveCount(0);
  await expect(page.locator('#play-now')).toHaveCount(0);
  await waitOverlay(page);
  await expect(page.locator('#back-btn')).toHaveText('Back to Locker Room');
  await expect(page.locator('#submit-btn')).toHaveText('Submit Training');
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  // Player Development is back on the weekly page, under Coaching Focus (2026-10-02).
  await expect(page.locator('#player-dev-section')).toBeVisible();
  await expect(page.locator('#player-dev-section .pdg-card')).toHaveCount(inSeasonPoints().custom_focus_roster.length);
  const focusLook = await page.evaluate(() => {
    const header = document.querySelector('#training-view .training-header');
    const hs = header ? getComputedStyle(header) : null;
    const note = document.getElementById('training-state-note');
    const ns = note ? getComputedStyle(note) : null;
    const empty = [...document.querySelectorAll('button, a.gob-btn, a[role="button"]')].filter((el) => {
      if (el.closest('.ps') || el.closest('.slider-container')) return false;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden' || el.hidden) return false;
      if (!el.getClientRects().length) return false;
      const name = (el.getAttribute('aria-label') || el.title || el.textContent || '').replace(/\s+/g, '');
      return !name.length;
    }).map((el) => el.id || el.className);
    const rows = [...document.querySelectorAll('#training-view .slider-label')];
    const rowControls = rows.map((row) => {
      const range = row.querySelector('input[type=range]');
      const pips = row.querySelector('.ps');
      const box = (el) => {
        if (!el) return { visible: false, w: 0 };
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        const clipped = s.clipPath && s.clipPath !== 'none';
        const tiny = r.width <= 2 && r.height <= 2;
        return {
          visible: s.display !== 'none' && s.visibility !== 'hidden' && r.width > 8 && r.height > 4 && !clipped && !tiny,
          w: r.width,
        };
      };
      return { range: box(range), pips: box(pips) };
    });
    const fb = [...document.querySelectorAll('#training-view .label-text')].find((el) =>
      (el.textContent || '').includes('Fast Break Defense'));
    const coaching = document.querySelector('#training-view h2.coaching-title');
    const cs = coaching ? getComputedStyle(coaching) : null;
    return {
      host: !!document.getElementById('training-view'),
      headerBgImage: hs ? hs.backgroundImage : '',
      noteDisplay: ns ? ns.display : '',
      emptyButtons: empty,
      rowControls,
      fbLabel: fb ? (fb.textContent || '').replace(/\s+/g, ' ').trim() : '',
      fbOverflow: fb ? getComputedStyle(fb).overflow : '',
      coachingAlign: cs ? cs.textAlign : '',
    };
  });
  expect(focusLook.host, JSON.stringify(focusLook)).toBe(true);
  expect(focusLook.headerBgImage, JSON.stringify(focusLook)).toBe('none');
  expect(focusLook.noteDisplay, JSON.stringify(focusLook)).toBe('none');
  expect(focusLook.emptyButtons, JSON.stringify(focusLook)).toEqual([]);
  expect(focusLook.rowControls.length, JSON.stringify(focusLook)).toBeGreaterThan(0);
  focusLook.rowControls.forEach((row) => {
    expect(row.range.visible, JSON.stringify(row)).toBe(false);
    expect(row.pips.visible, JSON.stringify(row)).toBe(true);
  });
  expect(focusLook.fbLabel, JSON.stringify(focusLook)).toBe('Fast Break Defense Install');
  expect(focusLook.coachingAlign, JSON.stringify(focusLook)).toBe('left');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await capturePage(page, path.join(OUT, 'after-focus-default-1280.png'));

  await allocateClassic24(page);
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 10000 });
  await capturePage(page, path.join(OUT, 'after-focus-allocated-unsaved-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await capturePage(page, path.join(OUT, 'after-focus-allocated-unsaved-1920.png'));
  await page.setViewportSize({ width: 1280, height: 720 });

  await page.locator('#submit-btn').click();
  await page.waitForURL(/\/training-report\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await expect(page.locator('#gob-subtabs')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Continue to Office', exact: true })).toBeVisible({ timeout: 20000 });
  await expectHeaderVisible(page);
  await expect(page.locator('#training-report-view h1.page-title')).toBeVisible();
  await expect(page.locator('#training-report-view h1.page-title')).toHaveText('Training Report');
  await expect(page.locator('#training-focus')).toHaveText('Discipline (Authoritarian)');
  await expect(page.locator('#training-notes-container')).toContainText('Roger Henrich');
  await expect(page.locator('#training-notes-container')).not.toContainText('No training notes');
  const reportLook = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('#training-report-view .team-attr-item')];
    const pills = [...document.querySelectorAll('#training-report-view .attr-pill, #training-report-view .chemistry-bar-container')].filter((el) => {
      const s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length > 0;
    });
    const first = rows[0];
    const fs = first ? getComputedStyle(first) : null;
    const empty = [...document.querySelectorAll('button, a.gob-btn, a[role="button"]')].filter((el) => {
      if (el.closest('.ps') || el.closest('.slider-container')) return false;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden' || el.hidden) return false;
      if (!el.getClientRects().length) return false;
      const name = (el.getAttribute('aria-label') || el.title || el.textContent || '').replace(/\s+/g, '');
      return !name.length;
    }).map((el) => el.id || el.className);
    return {
      host: !!document.getElementById('training-report-view'),
      rowCount: rows.length,
      visiblePills: pills.length,
      rowDisplay: fs ? fs.display : '',
      rowBgImage: fs ? fs.backgroundImage : '',
      emptyButtons: empty,
    };
  });
  expect(reportLook.host, JSON.stringify(reportLook)).toBe(true);
  expect(reportLook.rowCount, JSON.stringify(reportLook)).toBe(11);
  expect(reportLook.visiblePills, JSON.stringify(reportLook)).toBe(0);
  // Team Report cells are plain blocks in a four-column grid (name and mark side by side).
  expect(reportLook.rowDisplay, JSON.stringify(reportLook)).toBe('block');
  expect(reportLook.rowBgImage, JSON.stringify(reportLook)).toBe('none');
  expect(reportLook.emptyButtons, JSON.stringify(reportLook)).toEqual([]);
  expect(reportGets.some((row) => String(row.week) === '12'), JSON.stringify(reportGets)).toBe(true);
  await capturePage(page, path.join(OUT, 'after-submit-report-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expectHeaderVisible(page);
  await capturePage(page, path.join(OUT, 'after-submit-report-1920.png'));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole('button', { name: 'Continue to Office', exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname, { timeout: 20000 }).toBe('/franchise-command-center.html');

  const user = submits.find((row) => row.kind === 'user');
  expect(user).toBeTruthy();
  expect(JSON.parse(user.body)).toEqual(EXPECTED_USER_BODY);
});

test('a) focus page at 1920 and Set Lineup chrome compare', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await capturePage(page, path.join(OUT, 'after-focus-default-1920.png'));

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/set-lineup.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TEAM
    + '&week=12&home=Lancaster&away=Four-Corners&home_id=' + TEAM + '&away_id=Four-Corners&my_team=home');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await capturePage(page, path.join(OUT, 'after-set-lineup-chrome-1280.png'));
});

test('b) Prep › Player Training is player-dev only and edits save', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openPrepTraining(page);
  await expect(page.locator('#training-view .devfocus-select').first()).toBeVisible({ timeout: 30000 });
  const hidden = await page.evaluate(() => {
    const host = document.getElementById('training-view');
    const vis = (sel) => {
      const el = host.querySelector(sel);
      if (!el) return false;
      const s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && !el.hidden;
    };
    return {
      sliders: vis('.main-content-grid'),
      coaching: vis('.coaching-section'),
      req: vis('#requirements-bar'),
      auto: vis('#auto-train-btn'),
      submit: vis('#submit-btn'),
      pointer: (host.textContent || '').includes('Weekly training is set when you advance.'),
    };
  });
  expect(hidden.sliders).toBe(false);
  expect(hidden.coaching).toBe(false);
  expect(hidden.req).toBe(false);
  expect(hidden.auto).toBe(false);
  expect(hidden.submit).toBe(false);
  expect(hidden.pointer).toBe(true);
  await expect(page.locator('#gob-subtabs .tb[aria-selected="true"] .tb-l')).toHaveText('Player Training');
  const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
  await focus.selectOption('offensive');
  await expect(page.locator('.gob-save-toast.is-on')).toHaveText('Saved', { timeout: 5000 });
  await capturePage(page, path.join(OUT, 'after-prep-player-training-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await capturePage(page, path.join(OUT, 'after-prep-player-training-1920.png'));
});

test('c) post-week-26 Advance skips the training page', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { cc: postWeek26Cc() });
  await expect(page.locator('#play-now')).not.toHaveText(/Run Training|Submit Training|Run Training Camp/);
  await expect(page.locator('#play-now')).toHaveAttribute('data-mode', /play|sim-rest-tournament|new-season/);
  await page.locator('#play-now').click();
  await page.waitForTimeout(800);
  expect(page.url()).not.toContain('/training.html');
});

test('d) camp week 1 Advance opens the focus page', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { cc: campCc(), points: campPoints() });
  await expect(page.locator('#play-now')).toHaveText(/Run Training Camp|Run Training/);
  await page.locator('#play-now').click();
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await expect(page.url()).toContain('session_type=preseason');
});

test('e) tutorial path stays weekly focus on training.html', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=tutorial');
  await expect(page).toHaveURL(/training\.html/);
  await expect(page).toHaveURL(/mode=tutorial/);
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#submit-btn')).toBeVisible();
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('#player-dev-section')).toBeHidden();
  await capturePage(page, path.join(OUT, 'after-tutorial-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await capturePage(page, path.join(OUT, 'after-tutorial-1920.png'));
});

test('f) leave-confirm on unsaved allocation; clean Back just leaves', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });

  await page.goto('/training.html?franchise_id=' + FID + '&team_id=' + TEAM + '&mode=franchise&session_type=in-season');
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await page.locator('.slider').first().evaluate((el) => {
    el.value = '2';
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toBeVisible({ timeout: 10000 });
  await page.locator('.gob-leave-confirm [data-leave="stay"]').click();
  await expect(page).toHaveURL(/\/training\.html/);
  await page.locator('#back-btn').click();
  await expect(page.locator('.gob-leave-confirm')).toBeVisible();
  await page.locator('.gob-leave-confirm [data-leave="discard"]').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
});

test('g) desktop profile uses the same Advance → focus path', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.addInitScript(() => {
    window.GOB_BUILD_PROFILE = 'desktop';
    if (window.location && window.location.port) {
      window.GOB_LOOPBACK_PORT = Number(window.location.port);
    }
    window.__gobAuthMeData = {
      user_id: 'e2e-user',
      username: 'e2e',
      email: 'e2e@example.com',
      tutorial_alerts_franchise_id: 'other-franchise',
      tutorial_alerts_dismissed: [
        'player-attributes', 'training', 'team-attributes', 'game-plans',
        'playbooks', 'scouting', 'recruiting',
      ],
    };
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { me: { tutorial_alerts_franchise_id: 'other-franchise' } });
  await expect(page.locator('#play-now')).toHaveText('Run Training');
  await page.locator('#play-now').click();
  const later = page.getByRole('button', { name: /do this later/i });
  try {
    await later.waitFor({ state: 'visible', timeout: 2500 });
    await later.click();
  } catch (err) { /* no tutorial intercept */ }
  await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#submit-btn')).toHaveText('Submit Training');
});

test('h) Office All changes → standalone report → Back → Office', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, { cc: officeWithChangesCc() });
  await expect(page.locator('#play-now')).toHaveText('Play Next Game');
  await expect(page.locator('#play-now')).not.toHaveText(/Run Training|Run Training Camp|Submit Training/);
  const link = page.locator('#office-root .wkc-f .lnk');
  await expect(link).toHaveText(/All changes/);
  const href = await link.getAttribute('href');
  expect(href).toContain('/training-report.html');
  expect(href).not.toContain('tab=training-report-view');
  expect(href).toContain('from=office');
  expect(href).toContain('week=12');
  await link.click();
  await expect(page).toHaveURL(/\/training-report\.html/, { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('nav.rail')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Back to Locker Room', exact: true })).toBeVisible({ timeout: 20000 });
  await expectHeaderVisible(page);
  await capturePage(page, path.join(OUT, 'after-report-from-office-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expectHeaderVisible(page);
  await capturePage(page, path.join(OUT, 'after-report-from-office-1920.png'));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole('button', { name: 'Back to Locker Room', exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname, { timeout: 20000 }).toBe('/franchise-command-center.html');
  await expect(page.locator('#office-root')).toBeVisible({ timeout: 15000 });
});

test('h2) All changes loads the report when the Office was opened with franchise_id only', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  // The app returns to the Office this way after a game, from the mode select and from
  // Set Lineup: no team_id in the address. The link must still carry the coach's team,
  // or the report page has nothing to load.
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page, { cc: officeWithChangesCc() });
  const reportCalls = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/franchise/training-report') reportCalls.push(request.url());
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID);
  await waitOverlay(page);
  const link = page.locator('#office-root .wkc-f .lnk');
  await expect(link).toHaveText(/All changes/);
  const href = new URL(await link.getAttribute('href'), 'http://local');
  await link.click();
  await expect(page).toHaveURL(/\/training-report\.html/, { timeout: 20000 });
  // Landed on the report itself: its week, its title, its rows, and no failure card.
  await expect(page.locator('#week-number')).toHaveText('12', { timeout: 20000 });
  await expect(page.locator('#training-report-view h1.page-title')).toHaveText('Training Report');
  await expect(page.locator('#training-report-view')).toContainText('Roger Henrich', { timeout: 20000 });
  await expect(page.locator('#training-report-view')).not.toContainText(/could not|couldn.t|failed to load/i);
  expect(reportCalls.length).toBeGreaterThan(0);
  expect(new URL(reportCalls[0]).searchParams.get('team_id')).toBe(TEAM_OBJECT_ID);
  // The link carried everything the page needs.
  expect(href.pathname).toBe('/training-report.html');
  expect(href.searchParams.get('franchise_id')).toBe(FID);
  expect(href.searchParams.get('team_id')).toBe(TEAM_OBJECT_ID);
  expect(href.searchParams.get('week')).toBe('12');
  await expectHeaderVisible(page);
  await capturePage(page, path.join(V3_OUT, 'all-changes-report-after-1280.png'));
  await page.setViewportSize({ width: 1920, height: 1080 });
  await capturePage(page, path.join(V3_OUT, 'all-changes-report-after-1920.png'));
});

test('i) old /training-report.html and ?tab=training-report-view land on the standalone page', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training-report.html?franchise_id=' + FID + '&team_id=' + TEAM
    + '&mode=franchise&week=12&from=office');
  await expect(page).toHaveURL(/\/training-report\.html/);
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#week-number')).toHaveText('12', { timeout: 20000 });
  await expect(page.locator('#training-report-view h1.page-title')).toHaveText('Training Report');
  await expect(page.getByRole('button', { name: 'Back to Locker Room', exact: true })).toBeVisible();
  await expectHeaderVisible(page);
  await capturePage(page, path.join(OUT, 'after-report-standalone-1280.png'));

  await page.goto('/franchise-command-center.html?' + fccQuery('training-report-view') + '&week=12&from=office');
  await expect(page).toHaveURL(/\/training-report\.html/, { timeout: 20000 });
  expect(page.url()).not.toContain('tab=training-report-view');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.locator('#week-number')).toHaveText('12', { timeout: 20000 });
});

test('j) report focus at 1920 and desktop profile', async ({ page }) => {
  test.skip(CAPTURE_BEFORE, 'after only');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training-report.html?franchise_id=' + FID + '&team_id=' + TEAM
    + '&mode=franchise&week=12&from=training');
  await expect(page.locator('#week-number')).toHaveText('12', { timeout: 20000 });
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Continue to Office', exact: true })).toBeVisible();
  await expectHeaderVisible(page);
  await capturePage(page, path.join(OUT, 'after-report-standalone-1920.png'));

  await page.addInitScript(() => {
    window.GOB_BUILD_PROFILE = 'desktop';
    if (window.location && window.location.port) {
      window.GOB_LOOPBACK_PORT = Number(window.location.port);
    }
    window.__gobAuthMeData = {
      user_id: 'e2e-user',
      username: 'e2e',
      email: 'e2e@example.com',
      tutorial_alerts_franchise_id: 'other-franchise',
      tutorial_alerts_dismissed: [
        'player-attributes', 'training', 'team-attributes', 'game-plans',
        'playbooks', 'scouting', 'recruiting',
      ],
    };
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await installApi(page);
  await page.goto('/training-report.html?franchise_id=' + FID + '&team_id=' + TEAM
    + '&mode=franchise&week=12&from=office');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Back to Locker Room', exact: true })).toBeVisible({ timeout: 20000 });
});
