// @ts-check
/**
 * Prep SFX catalog: one named call per control, none when muted.
 * Game Plan / Playbooks leave-confirm Save is exactly one SFX_COMMIT.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function ccWithOpponent() {
  const cc = clone(FIXTURE.cc);
  cc.week = 12;
  cc.next_game_summary = {
    week: 12,
    matchup_label: 'vs',
    opponent_team_id: OPP,
    opponent_team_name: 'Four Corners',
  };
  return cc;
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, saves) {
  const playbooks = clone(FIXTURE.playbooks);
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
      return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    }
    if (pathname === '/app-config') {
      return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    }
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, ccWithOpponent());
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, FIXTURE.trainingPoints);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/api/gameplan') {
      if (method === 'PUT') {
        if (saves) saves.push('gameplan');
        return fulfillJson(route, { success: true });
      }
      return fulfillJson(route, FIXTURE.gameplan);
    }
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') {
      if (method === 'POST') {
        if (saves) saves.push('playbooks');
        return fulfillJson(route, { success: true, position_shot_weights: FIXTURE.preview.position_shot_weights });
      }
      return fulfillJson(route, playbooks);
    }
    if (pathname.startsWith('/franchise/scouting-report')) {
      return fulfillJson(route, {
        projected_starting_five: [],
        player_season_stats: {},
        play_usage_unlocked: true,
        plays: [],
        fast_break_plays: [],
        hct_trap_plays: [],
      });
    }
    if (pathname.startsWith('/franchise/training-report')) {
      return fulfillJson(route, {
        week: 12,
        upcoming_opponent: 'Four Corners',
        coaching_focus: {},
        players: [],
        player_changes: {},
        team_attributes: {},
        team_changes: {},
        plays_data: {},
        scouting_data: {},
        projected_starting_five: [],
      });
    }
    return fulfillJson(route, {});
  });
}

function fccQuery(tab) {
  return new URLSearchParams({
    franchise_id: FID,
    team_id: TEAM,
    user_team_id: TEAM,
    mode: 'franchise',
    tab,
    from: 'command_center',
  }).toString();
}

async function openTab(page, tab, readySel) {
  await stubAuth(page);
  await installApi(page, []);
  await page.goto('/franchise-command-center.html?' + fccQuery(tab));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(readySel, { timeout: 30000 });
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

async function muteSfx(page) {
  await page.evaluate(async () => {
    const m = await import('/js/shared/uiSfx.js');
    m.setChannelMuted('sfx', true);
    window.__gobSfxCalls = [];
  });
}

async function sfxCalls(page) {
  await page.waitForTimeout(80);
  return page.evaluate(() => (window.__gobSfxCalls || []).slice());
}

async function dirtyGamePlan(page) {
  await page.locator('#game-plan-view #slider-offense').evaluate((el) => {
    el.value = el.value === '4' ? '1' : '4';
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

async function dirtyPlaybooks(page) {
  const slider = page.locator('#playbooks-view .et-slider[data-sl]').first();
  await slider.evaluate((el) => {
    const max = Number(el.max || 100);
    const cur = Number(el.value || 0);
    el.value = String(cur >= max ? Math.max(0, cur - 10) : Math.min(max, cur + 10));
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

async function openLeaveConfirm(page, view) {
  await page.evaluate((id) => {
    window.GOBNav.confirmLeave(function () {}, id);
  }, view);
  await expect(page.locator('[data-leave="save"]')).toBeVisible();
}

test('game plan slider, save, and leave-confirm are one catalog sound', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openTab(page, 'game-plan-view', '#game-plan-view #slider-offense');
  await armSpy(page);
  await dirtyGamePlan(page);
  expect(await sfxCalls(page)).toEqual(['SFX_SELECT']);

  await armSpy(page);
  await page.locator('#btn-save-game-plan').click();
  expect(await sfxCalls(page)).toEqual(['SFX_COMMIT']);

  await dirtyGamePlan(page);
  await openLeaveConfirm(page, 'game-plan-view');
  await armSpy(page);
  await page.locator('[data-leave="save"]').click();
  expect(await sfxCalls(page)).toEqual(['SFX_COMMIT']);

  await dirtyGamePlan(page);
  await openLeaveConfirm(page, 'game-plan-view');
  await muteSfx(page);
  await page.locator('[data-leave="save"]').click();
  expect(await sfxCalls(page)).toEqual([]);
});

test('playbooks tab, save, and leave-confirm are one catalog sound', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openTab(page, 'playbooks-view', '#playbooks-view .play');
  await armSpy(page);
  await page.locator('#playbooks-view .playbooks-tab[data-tab="defense"]').click();
  expect(await sfxCalls(page)).toEqual(['SFX_SELECT']);

  await dirtyPlaybooks(page);
  await expect(page.locator('#save-btn')).toBeEnabled();
  await armSpy(page);
  await page.locator('#save-btn').click();
  expect(await sfxCalls(page)).toEqual(['SFX_COMMIT']);

  await dirtyPlaybooks(page);
  await page.evaluate(() => {
    window.__playbooksPage.confirmLeave(function () {});
  });
  await expect(page.locator('[data-leave="save"]')).toBeVisible();
  await armSpy(page);
  await page.locator('[data-leave="save"]').click();
  expect(await sfxCalls(page)).toEqual(['SFX_COMMIT']);

  await dirtyPlaybooks(page);
  await page.evaluate(() => {
    window.__playbooksPage.confirmLeave(function () {});
  });
  await expect(page.locator('[data-leave="save"]')).toBeVisible();
  await muteSfx(page);
  await page.locator('[data-leave="save"]').click();
  expect(await sfxCalls(page)).toEqual([]);
});

test('training, training report, and scouting toggles use SFX_SELECT', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openTab(page, 'training-view', '#training-view .slider, #training-view .ps');
  const slider = page.locator('#training-view input[type="range"], #training-view .slider').first();
  await expect(slider).toBeVisible();
  await armSpy(page);
  await slider.evaluate((el) => {
    el.value = String(Math.min(Number(el.max || 4), Number(el.value) + 1));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(await sfxCalls(page)).toEqual(['SFX_SELECT']);
  await muteSfx(page);
  await slider.evaluate((el) => {
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(await sfxCalls(page)).toEqual([]);

  await page.goto('/franchise-command-center.html?' + fccQuery('training-report-view'));
  await page.waitForSelector('#training-report-view .toggle-btn, #training-report-view .players-section', { timeout: 30000 });
  const reportToggle = page.locator('#training-report-view .toggle-btn').first();
  if (await reportToggle.count()) {
    await armSpy(page);
    await reportToggle.click();
    expect(await sfxCalls(page)).toEqual(['SFX_SELECT']);
    await muteSfx(page);
    await page.locator('#training-report-view .toggle-btn').nth(1).click().catch(async () => {
      await reportToggle.click();
    });
    expect(await sfxCalls(page)).toEqual([]);
  }

  await page.goto('/franchise-command-center.html?' + fccQuery('scouting-view'));
  await page.waitForSelector('#scouting-view .opp-n', { timeout: 30000 });
  await armSpy(page);
  await page.locator('#scouting-view [data-mode="stats"]').click();
  expect(await sfxCalls(page)).toEqual(['SFX_SELECT']);
  await muteSfx(page);
  await page.locator('#scouting-view [data-mode="attributes"]').click();
  expect(await sfxCalls(page)).toEqual([]);
});
