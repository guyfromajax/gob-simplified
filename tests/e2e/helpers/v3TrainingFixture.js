// @ts-check
/**
 * Weekly Training page + Custom Playbook page for v3-training.spec.js, on the prep-plan
 * fixture. The API double keeps the franchise's saved Training playbook choice the way the
 * server does (PATCH /franchise/training-playbook-choice, read back on
 * GET /franchise/training-points), so a test can train, come back next week, next camp or
 * next season and see what the page does with it.
 */
const fs = require('fs');
const path = require('path');
const { expect } = require('@playwright/test');
const { stubAuth } = require('./auth');

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '../fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../../FrontEnd/static/images/players/generic_headshot.png'));
const CURRENT = { mode: 'current-playbooks', focus: null };

const PLAYS = {
  motion: FIXTURE.playbooks.motion.map((p) => String(p.play_id)),
  sets: FIXTURE.playbooks.set_plays.map((p) => String(p.play_id)),
  man: FIXTURE.playbooks.man_defense_rows.map((r) => String(r.id)),
  zone: FIXTURE.playbooks.zone_defense_rows.map((r) => String(r.id)),
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

/** A fresh franchise state: week 12 of season 1, nothing saved. */
function newState(extra) {
  return Object.assign({ week: 12, season: 1, choice: clone(CURRENT), patches: [], submits: [] }, extra || {});
}

function ccFor(state) {
  const cc = clone(FIXTURE.cc);
  cc.week = state.week;
  cc.current_season = state.season;
  cc.session_type = state.week === 1 ? 'preseason' : 'in-season';
  cc.training_completed = false;
  cc.training_disabled_for_postseason = false;
  cc.training_disabled_for_eos = false;
  return cc;
}

function pointsFor(state) {
  const points = clone(FIXTURE.trainingPoints);
  const camp = state.week === 1;
  points.week = state.week;
  points.season = state.season;
  points.is_camp_week = camp;
  points.is_first_training = camp;
  points.training_points = camp ? 30 : 24;
  points.training_unavailable = false;
  points.custom_focus_roster = points.custom_focus_roster.slice(0, 12);
  // What the server adds: the saved choice, normalised.
  points.training_playbook_choice = clone(state.choice);
  return points;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

/** The server's save rule: custom needs an offense play and a defense; current removes it. */
function applyPatch(state, body) {
  const focus = body.focus || {};
  const offense = (focus.offense || []).map(String);
  const defense = (focus.defense || []).map(String);
  if (body.mode === 'custom' && offense.length && defense.length) {
    state.choice = { mode: 'custom', focus: { offense, defense } };
    return 200;
  }
  if (body.mode === 'current-playbooks') {
    state.choice = clone(CURRENT);
    return 200;
  }
  return 400;
}

async function installApi(page, state) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const method = request.method();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/images/players/')) {
      return route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, ccFor(state));
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, pointsFor(state));
    if (pathname === '/franchise/training-playbook-choice' && method === 'PATCH') {
      const body = request.postDataJSON() || {};
      state.patches.push(body);
      const status = applyPatch(state, body);
      return fulfillJson(route, status === 200 ? state.choice : { detail: 'refused' }, status);
    }
    if (pathname === '/franchise/run-training/user' && method === 'POST') {
      state.submits.push((request.postDataJSON() || {}).training_data || {});
      return fulfillJson(route, { status: 'success' });
    }
    if (pathname === '/franchise/run-training/cpu-train' && method === 'POST') {
      return fulfillJson(route, { status: 'success', redirect: '/training-report.html?mode=franchise&franchise_id=' + FID + '&from=training' });
    }
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/api/gameplan') return fulfillJson(route, FIXTURE.gameplan);
    if (pathname === '/api/playbooks') return fulfillJson(route, FIXTURE.playbooks);
    return fulfillJson(route, {});
  });
}

function query(extra) {
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, mode: 'franchise' });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

async function waitOverlay(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
}

let installed = new WeakSet();

/** Open the weekly Training page for the state's week (week 1 is training camp). */
async function openTraining(page, state) {
  if (!installed.has(page)) {
    await stubAuth(page);
    await installApi(page, state);
    installed.add(page);
  }
  const session = state.week === 1 ? 'training-camp' : 'in-season';
  await page.goto('/training.html?' + query({ from: 'locker-room', session_type: session }));
  await waitOverlay(page);
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('#playbook-mode-current-btn')).toBeVisible();
}

/** What the Training Plays toggle shows and what the page would train with. */
function readMode(page) {
  return page.evaluate(() => {
    const current = document.getElementById('playbook-mode-current-btn');
    const custom = document.getElementById('playbook-mode-custom-btn');
    const banner = document.getElementById('custom-playbook-banner');
    let focus = null;
    try { focus = JSON.parse(sessionStorage.getItem('gob_training_playbook_focus') || 'null'); } catch (e) { focus = null; }
    return {
      selected: custom.classList.contains('is-selected') ? 'custom' : current.classList.contains('is-selected') ? 'current-playbooks' : 'none',
      pressed: { current: current.getAttribute('aria-pressed'), custom: custom.getAttribute('aria-pressed') },
      banner: banner && !banner.hidden ? banner.textContent.replace(/\s+/g, ' ').trim() : '',
      sessionMode: sessionStorage.getItem('gob_playbook_training_mode'),
      focus,
    };
  });
}

/** Spend every point and pick a coaching focus, then submit; resolves once the server has the orders. */
async function submitTraining(page, state) {
  const before = state.submits.length;
  const total = state.week === 1 ? 30 : 24;
  await page.evaluate((points) => {
    let left = points;
    document.querySelectorAll('.slider').forEach((el) => {
      const max = Number(el.max || 5);
      const give = Math.min(max, left);
      el.value = String(give);
      left -= give;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }, total);
  await page.locator('.archetype-block[data-archetype="systems-coach"] label.archetype-option', { hasText: 'Offense' }).click();
  await expect(page.locator('#submit-btn')).toBeEnabled();
  await page.locator('#submit-btn').click();
  await expect.poll(() => state.submits.length, { timeout: 20000 }).toBe(before + 1);
  await page.waitForURL(/training-report\.html/, { timeout: 20000 });
  return state.submits[state.submits.length - 1];
}

module.exports = {
  FIXTURE, FID, TEAM, CURRENT, PLAYS, clone, newState, openTraining, readMode, submitTraining, waitOverlay, query,
};
