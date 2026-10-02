// @ts-check
/**
 * Training / Training Report / Game Plan / Playbooks / Set Lineup polish
 * (Jamie's walk-through, 2026-10-02). One test per brief item; the shots test
 * writes reports/training-playbooks/<phase>-<item>-1280.png.
 *
 *   TP_SHOTS=before  capture the "before" set only (run on the old tree)
 *   TP_SHOTS=after   capture the "after" set alongside the assertions
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/training-playbooks');
const PHASE = process.env.TP_SHOTS || '';
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/images/players/generic_headshot.png'));

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

/** The 12 active players, RT-descending, the shape /franchise/training-points serves. */
function inSeasonPoints() {
  const points = clone(FIXTURE.trainingPoints);
  points.week = 12;
  points.is_camp_week = false;
  points.is_first_training = false;
  points.training_points = 24;
  points.training_unavailable = false;
  points.custom_focus_roster = points.custom_focus_roster.slice(0, 12);
  return points;
}

function bestRt(row) {
  return Math.max.apply(null, Object.values(row.position_ratings || {}).map(Number));
}

/**
 * A report with every arrow band on it. Player deltas are raw attribute points, keyed by
 * player name (what training-report.js reads).
 */
function report(week) {
  const roster = inSeasonPoints().custom_focus_roster;
  const players = roster.map((row) => ({
    player_id: row.player_id,
    id: row.player_id,
    name: row.name,
    jersey: row.jersey,
    year: 'JR',
    pos: row.pos,
    position: row.pos,
    position_ratings: row.position_ratings,
    attributes: row.attrs,
    attrs: row.attrs,
    season_stats: {},
  }));
  const names = players.map((p) => p.name);
  const player_changes = {};
  // One player per band: +6 / +2.5 / +0.4 / 0 / -0.3 / -1 / -2 / -3.
  [6, 2.5, 0.4, 0, -0.3, -1, -2, -3].forEach((delta, i) => {
    player_changes[names[i]] = { SC: delta, SH: delta, RB: delta };
  });
  const plays_data = clone(FIXTURE.teamData.plays_data);
  Object.keys(plays_data).forEach((name, i) => { plays_data[name].effectiveness = 40 + (i * 3) % 55; });
  const plays_effectiveness_changes = {};
  Object.keys(plays_data).forEach((name, i) => {
    plays_effectiveness_changes[name] = [3.5, 1.2, 0.2, -1, -3][i % 5];
  });
  return {
    week,
    upcoming_opponent: 'Four Corners',
    coaching_focus: { archetype: 'systems-coach', sub_option: 'systems-coach-offense', leaf_display_name: 'Offense' },
    players,
    player_changes,
    player_attribute_display_movements: {},
    exceptional_gains: [],
    team_attributes: {
      shot_threshold: 0, rebound_modifier: 1, offensive_efficiency: 4, defensive_efficiency: 2,
      fb_efficiency: 1, pt_efficiency: 6, fight: 2, discipline: 3, team_chemistry: 8,
      fb_opp_modifier: -2, pt_opp_modifier: -1,
    },
    team_changes: {
      offensive_efficiency: 6, defensive_efficiency: 2.5, fb_efficiency: 0.4,
      pt_efficiency: -1, fight: -2, discipline: -3,
    },
    plays_data,
    scouting_data: clone(FIXTURE.teamData.scouting_data),
    plays_effectiveness_changes,
    defenses_effectiveness_changes: {},
    projected_starting_five: [],
    training_notes: [
      { title: 'Practice Player Of The Week', body: names[0] },
      { title: 'Biggest Regression', body: 'No Significant Updates' },
      { title: 'Strongest Offensive Plays', body: 'Horn' },
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
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, points);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/api/gameplan') {
      if (method === 'PUT') return fulfillJson(route, { success: true });
      return fulfillJson(route, FIXTURE.gameplan);
    }
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') {
      if (opts.playbookGets) opts.playbookGets.push(request.headers());
      if (opts.playbooksStatus) return fulfillJson(route, { detail: 'nope' }, opts.playbooksStatus);
      if (method === 'POST') {
        return fulfillJson(route, { success: true, position_shot_weights: FIXTURE.preview.position_shot_weights });
      }
      return fulfillJson(route, FIXTURE.playbooks);
    }
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      const body = request.postDataJSON() || {};
      if (opts.devSaves) opts.devSaves.push(body);
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    if (pathname === '/franchise/training-report') {
      if (opts.reportDelayMs) await new Promise((resolve) => setTimeout(resolve, opts.reportDelayMs));
      return fulfillJson(route, report(opts.reportWeek || cc.week || 12));
    }
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

async function openTraining(page, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/training.html?' + query({ from: 'locker-room', session_type: 'in-season' }));
  await waitOverlay(page);
  await expect(page.locator('#training-view .ps').first()).toBeVisible({ timeout: 30000 });
}

async function openFcc(page, tab, extra) {
  await stubAuth(page);
  await installApi(page, extra);
  await page.goto('/franchise-command-center.html?' + query({ tab, from: 'command_center' }));
  await waitOverlay(page);
}

async function openReport(page, extra) {
  const opts = extra || {};
  await stubAuth(page);
  await installApi(page, opts);
  await page.goto('/training-report.html?' + query({ week: String(opts.reportWeek || 12), from: 'training', origin: 'prep' }));
}

async function settle(page) {
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
}

async function shot(page, item, locator) {
  if (!PHASE) return;
  fs.mkdirSync(OUT, { recursive: true });
  await settle(page);
  const dest = path.join(OUT, PHASE + '-' + item + '-1280.png');
  if (locator) {
    // Bring the item to the top of its scroller, clear of any sticky page head.
    await locator.first().evaluate((el) => {
      el.scrollIntoView({ block: 'start' });
      let node = el.parentElement;
      while (node && node !== document.body) {
        const cs = getComputedStyle(node);
        if (/(auto|scroll)/.test(cs.overflowY) && node.scrollHeight > node.clientHeight) break;
        node = node.parentElement;
      }
      const scroller = (node && node !== document.body) ? node : document.scrollingElement;
      scroller.scrollTop = Math.max(0, scroller.scrollTop - 110);
    });
    await page.mouse.move(0, 0);
    await settle(page);
  }
  await page.screenshot({ path: dest, animations: 'disabled' });
}

/** Set Lineup on the seeded rosters, with playbook shot weights so the charts draw. */
async function openSetLineup(page, request) {
  await stubAuth(page);
  await waitForCanonicalRosters(request);
  await page.route('**/api/playbooks?**', (route) => fulfillJson(route, FIXTURE.playbooks));
  await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
  await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
  await expect(page.locator('#lineup-shot-weights .psw-bar-row').first()).toBeVisible({ timeout: 15000 });
  await page.waitForTimeout(400);
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

// The same views on the old tree, under the same file names, so each item has a pair.
// Selectors here are the OLD ones on purpose (e.g. "Choose Attributes").
test.describe('before shots', () => {
  test.skip(PHASE !== 'before', 'TP_SHOTS=before only');

  test('training page', async ({ page }) => {
    await openTraining(page);
    await shot(page, 'T1-T7-T9-training-top');
    await shot(page, 'T4-coaching-focus', page.locator('.coaching-section'));
    // Nothing below Coaching Focus: the section is hidden on the weekly page.
    await page.evaluate(() => { const m = document.getElementById('gob-main'); if (m) m.scrollTop = m.scrollHeight; window.scrollTo(0, document.body.scrollHeight); });
    await shot(page, 'T2-T3-player-development');
    await page.evaluate(() => { const m = document.getElementById('gob-main'); if (m) m.scrollTop = 0; window.scrollTo(0, 0); });
    await page.locator('label.archetype-option', { hasText: 'Choose Attributes' }).click();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(300);
    // What the coach saw: the modal opened below the fold, so nothing appears to happen.
    await page.evaluate(() => { const m = document.getElementById('gob-main'); if (m) m.scrollTop = 0; window.scrollTo(0, 0); });
    await shot(page, 'T5-player-maximizer-modal');
    await page.locator('.pm-modal-mode-option', { hasText: 'Custom' }).click();
    // Scroll a little way into the table: the header rides over the first player rows.
    await page.locator('#custom-focus-table').evaluate((el) => {
      el.scrollIntoView({ block: 'start' });
      const m = document.getElementById('gob-main');
      if (m) m.scrollTop += 70; else window.scrollBy(0, 70);
    });
    await shot(page, 'T6-custom-focus-attributes');
  });

  test('custom playbook', async ({ page }) => {
    await openTraining(page);
    await page.evaluate(() => {
      document.querySelectorAll('.slider').forEach((el, i) => {
        el.value = i === 7 ? '3' : (i === 8 ? '2' : '0');
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForTimeout(1500);
    await shot(page, 'T8-custom-playbook');
  });

  test('fcc player development tab', async ({ page }) => {
    await openFcc(page, 'training-view');
    await expect(page.locator('#training-view .pdg-grid')).toBeVisible({ timeout: 30000 });
    await shot(page, 'T10-fcc-player-development');
  });

  test('report loading beat', async ({ page }) => {
    await openReport(page, { reportDelayMs: 4000 });
    await waitOverlay(page);
    await page.waitForTimeout(600);
    await shot(page, 'R1-report-loading-beat');
  });

  test('report in season', async ({ page }) => {
    await openReport(page);
    await expect(page.locator('#week-number')).toHaveText('12', { timeout: 15000 });
    await waitOverlay(page);
    await shot(page, 'R2-report-in-season');
    await shot(page, 'R2-player-report-training-changes', page.locator('.players-section'));
    await page.locator('.players-section .toggle-btn[data-view="attributes"]').click();
    await shot(page, 'R3-player-report-attributes', page.locator('.players-section'));
    await shot(page, 'R4-playbook-summary', page.locator('.playbook-summary-section'));
  });

  test('report camp week', async ({ page }) => {
    await openReport(page, { reportWeek: 1 });
    await expect(page.locator('#week-number')).toHaveText('1', { timeout: 15000 });
    await waitOverlay(page);
    await shot(page, 'R2-report-camp');
  });

  test('game plan', async ({ page }) => {
    await openFcc(page, 'game-plan-view');
    await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible({ timeout: 30000 });
    await shot(page, 'G1-game-plan');
  });

  test('playbooks', async ({ page }) => {
    await openFcc(page, 'playbooks-view');
    await expect(page.locator('#playbooks-view .play').first()).toBeVisible({ timeout: 30000 });
    await shot(page, 'P1-P2-P4-playbooks-offense');
    await shot(page, 'P1-set-plays', page.locator('#playbooks-view section[data-section="setPlays"]'));
    // Fast Breaks lived at the foot of Offense, HC Traps at the foot of Defense.
    await shot(page, 'P2-fast-breaks-tab', page.locator('#playbooks-view section[data-section="fastBreaks"]'));
    await page.locator('#playbooks-view .playbooks-tab[data-tab="defense"]').click();
    await shot(page, 'P2-press-traps-tab', page.locator('#playbooks-view section[data-section="hcTraps"]'));
  });

  test('set lineup', async ({ page, request }) => {
    await openSetLineup(page, request);
    await shot(page, 'L1-set-lineup');
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.waitForTimeout(200);
    await shot(page, 'L1-set-lineup-tall');
  });
});

// ---------------------------------------------------------------------------
// Training page
// ---------------------------------------------------------------------------

async function sfxSpy(page) {
  await page.addInitScript(() => { window.__gobSfxCalls = []; });
}

async function allocate(page, values) {
  await page.evaluate((vals) => {
    document.querySelectorAll('.slider').forEach((el, i) => {
      el.value = String(vals[i] || 0);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }, values);
}

test.describe('training page', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('T1 Auto-Train plays the Autoset Lineup cue', async ({ page }) => {
    await sfxSpy(page);
    await openTraining(page);
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.locator('#auto-train-btn').click();
    await expect(page.locator('#auto-train-modal')).toHaveClass(/is-visible/);
    // One cue for the action, and it is the one Autoset Lineup plays on Set Lineup.
    await expect.poll(() => page.evaluate(() => window.__gobSfxCalls.slice())).toEqual(['chaotic-choice.wav']);
    const autoset = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/set-lineup.js'), 'utf8');
    expect(autoset).toContain("playSound('chaotic-choice.wav')");
    expect(fs.existsSync(path.join(__dirname, '../../FrontEnd/static/sounds/chaotic-choice.wav'))).toBe(true);
  });

  test('T2 T3 Player Development sits under Coaching Focus: 4 columns of 3 by RT, and saves', async ({ page }) => {
    const devSaves = [];
    await openTraining(page, { devSaves });
    const section = page.locator('#player-dev-section');
    await expect(section).toBeVisible();
    await expect(section.locator('.pdg-card')).toHaveCount(12);
    const geom = await page.evaluate(() => {
      const coaching = document.querySelector('#training-view .coaching-section').getBoundingClientRect();
      const dev = document.getElementById('player-dev-section').getBoundingClientRect();
      const cards = [...document.querySelectorAll('#player-dev-section .pdg-card')].map((el) => {
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.left), y: Math.round(r.top), name: el.querySelector('.pdg-name').textContent };
      });
      return { coachingBottom: coaching.bottom, devTop: dev.top, cards };
    });
    expect(geom.devTop).toBeGreaterThanOrEqual(geom.coachingBottom);
    const xs = [...new Set(geom.cards.map((c) => c.x))].sort((a, b) => a - b);
    const ys = [...new Set(geom.cards.map((c) => c.y))].sort((a, b) => a - b);
    expect(xs.length, JSON.stringify(xs)).toBe(4);
    expect(ys.length, JSON.stringify(ys)).toBe(3);
    // DOM order is RT order; it must run down each column, then across.
    geom.cards.forEach((card, i) => {
      expect(card.x, card.name).toBe(xs[Math.floor(i / 3)]);
      expect(card.y, card.name).toBe(ys[i % 3]);
    });
    const roster = inSeasonPoints().custom_focus_roster;
    expect(geom.cards.map((c) => c.name)).toEqual(roster.map((r) => r.name));
    const rts = roster.map(bestRt);
    expect(rts).toEqual([...rts].sort((a, b) => b - a));

    // Both editors are there for every player and a change saves.
    await expect(section.locator('.pdg-card select')).toHaveCount(24);
    const first = section.locator('.pdg-card').first();
    await first.locator('select').nth(1).selectOption('defensive');
    await expect.poll(() => devSaves.length).toBe(1);
    expect(devSaves[0].training_focus).toBe('defensive');
    await first.locator('select').nth(0).selectOption('PF');
    await expect.poll(() => devSaves.length).toBe(2);
    expect(devSaves[1].training_position).toBe('PF');
    await shot(page, 'T2-T3-player-development', section);
  });

  test('T2 a 15-player camp roster keeps four columns and adds a row', async ({ page }) => {
    const points = clone(FIXTURE.trainingPoints);
    expect(points.custom_focus_roster.length).toBe(15);
    await openTraining(page, { cc: clone(FIXTURE.cc), points });
    await expect(page.locator('#player-dev-section .pdg-card')).toHaveCount(15);
    const cards = await page.evaluate(() => [...document.querySelectorAll('#player-dev-section .pdg-card')].map((el) => {
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.left), y: Math.round(r.top) };
    }));
    const xs = [...new Set(cards.map((c) => c.x))].sort((a, b) => a - b);
    const ys = [...new Set(cards.map((c) => c.y))].sort((a, b) => a - b);
    expect(xs.length).toBe(4);
    expect(ys.length).toBe(4);
    cards.forEach((card, i) => {
      expect(card.x).toBe(xs[Math.floor(i / 4)]);
      expect(card.y).toBe(ys[i % 4]);
    });
  });

  test('T4 coaching styles are neutral cards with a coloured mark', async ({ page }) => {
    await openTraining(page);
    const look = await page.evaluate(() => {
      const probe = (name) => {
        const el = document.createElement('i');
        el.style.color = 'var(' + name + ')';
        document.documentElement.appendChild(el);
        const c = getComputedStyle(el).color;
        el.remove();
        return c;
      };
      const keys = { authoritarian: '--coach-authoritarian', 'systems-coach': '--coach-systems', 'player-maximizer': '--coach-maximizer', 'culture-builder': '--coach-culture' };
      return Object.keys(keys).map((key) => {
        const block = document.querySelector('#training-view .archetype-block[data-archetype="' + key + '"]');
        const cs = getComputedStyle(block);
        const mark = block.querySelector('.arch-mark');
        return {
          key,
          token: probe(keys[key]),
          edge: cs.borderLeftColor,
          edgeWidth: cs.borderLeftWidth,
          mark: getComputedStyle(mark).color,
          hasIcon: !!mark.querySelector('svg'),
          background: cs.backgroundColor,
          top: Math.round(block.getBoundingClientRect().top),
        };
      });
    });
    const expected = {
      authoritarian: 'rgb(255, 109, 109)', 'systems-coach': 'rgb(255, 215, 0)',
      'player-maximizer': 'rgb(52, 236, 39)', 'culture-builder': 'rgb(168, 118, 230)',
    };
    look.forEach((card) => {
      expect(card.token, card.key).toBe(expected[card.key]);
      expect(card.edge, card.key).toBe(card.token);
      expect(card.mark, card.key).toBe(card.token);
      expect(card.edgeWidth, card.key).toBe('2px');
      expect(card.hasIcon, card.key).toBe(true);
      // Otherwise neutral: a near-transparent white fill, never the style colour.
      expect(card.background, card.key).toMatch(/^rgba\(255, 255, 255, 0\.0\d+\)$/);
      expect(card.top, card.key).toBe(look[0].top);
    });
    // The selected option is a neutral choice, not the style colour.
    await page.locator('label.archetype-option', { hasText: 'Discipline' }).click();
    const chip = await page.locator('label.archetype-option', { hasText: 'Discipline' }).evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(chip).toMatch(/^rgba\(255, 255, 255, /);
    await shot(page, 'T4-coaching-focus', page.locator('.coaching-section'));
  });

  test('T5 four Player Maximizer options, each opening its own modal in view', async ({ page }) => {
    await openTraining(page);
    const block = page.locator('.archetype-block[data-archetype="player-maximizer"]');
    await expect(block.locator('label.archetype-option')).toHaveText([
      'Top 3 Attributes', 'Attributes 4\u20136', 'Positional Focus', 'Custom',
    ]);
    await expect(page.locator('label.archetype-option', { hasText: 'Choose Attributes' })).toHaveCount(0);
    for (const name of ['Top 3 Attributes', 'Attributes 4\u20136', 'Positional Focus', 'Custom']) {
      await block.locator('label.archetype-option', { hasText: name }).click();
      const modal = page.locator('#custom-focus-modal');
      await expect(modal).toHaveClass(/is-visible/);
      await expect(modal.locator('.custom-focus-modal-title')).toHaveText(name);
      const box = await modal.locator('.custom-focus-modal-content').boundingBox();
      expect(box.y, name).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height, name).toBeLessThanOrEqual(720);
      expect(box.x, name).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width, name).toBeLessThanOrEqual(1280);
      // All twelve players show without scrolling the table.
      const scroll = await modal.locator('.custom-focus-table-wrap').evaluate((el) => el.scrollHeight - el.clientHeight);
      expect(scroll, name).toBeLessThanOrEqual(1);
      if (name === 'Top 3 Attributes') await shot(page, 'T5-player-maximizer-modal');
      await page.locator('#custom-focus-cancel-btn').click();
      await expect(modal).not.toHaveClass(/is-visible/);
      // Cancel returns to the focus that was in force: none.
      await expect(page.locator('input[name="coaching-focus"]:checked')).toHaveCount(0);
    }
    // Assign keeps the option and names it in the requirements bar.
    await block.locator('label.archetype-option', { hasText: 'Positional Focus' }).click();
    await page.locator('#custom-focus-assign-btn').click();
    await expect(page.locator('input[name="coaching-focus"]:checked')).toHaveValue('player-maximizer-positional-focus');
    await expect(page.locator('#req-focus-value')).toHaveText('Positional Focus \u00b7 Player Maximizer');
    // Escape on a second option falls back to the assigned one.
    await block.locator('label.archetype-option', { hasText: 'Custom' }).click();
    await page.keyboard.press('Escape');
    await expect(page.locator('#custom-focus-modal')).not.toHaveClass(/is-visible/);
    await expect(page.locator('input[name="coaching-focus"]:checked')).toHaveValue('player-maximizer-positional-focus');
  });

  test('T5 the chosen leaf is what Submit sends; Custom sends its picks', async ({ page }) => {
    const bodies = [];
    await openTraining(page);
    await page.route('**/franchise/run-training/user', async (route) => {
      bodies.push(route.request().postDataJSON());
      await fulfillJson(route, { status: 'success' });
    });
    await page.route('**/franchise/run-training/cpu-train', (route) => fulfillJson(route, {
      status: 'success', redirect: '/training-report.html?mode=franchise&franchise_id=' + FID + '&from=training',
    }));
    await allocate(page, [5, 5, 5, 5, 4]);
    const block = page.locator('.archetype-block[data-archetype="player-maximizer"]');
    await block.locator('label.archetype-option', { hasText: 'Custom' }).click();
    await expect(page.locator('#custom-focus-assign-btn')).toBeDisabled();
    const rows = page.locator('#custom-focus-tbody tr');
    await expect(rows).toHaveCount(12);
    for (let r = 0; r < 12; r += 1) {
      for (let c = 0; c < 3; c += 1) await rows.nth(r).locator('td.custom-focus-cell').nth(c).click();
    }
    await expect(page.locator('#custom-focus-assign-btn')).toBeEnabled();
    await page.locator('#custom-focus-assign-btn').click();
    await expect(page.locator('#submit-btn')).toBeEnabled();
    await page.locator('#submit-btn').click();
    await expect.poll(() => bodies.length).toBe(1);
    const data = bodies[0].training_data;
    expect(data.coaching_focus).toBe('player-maximizer-custom');
    expect(Object.keys(data.coaching_focus_custom_by_player)).toHaveLength(12);
    Object.values(data.coaching_focus_custom_by_player).forEach((picks) => {
      expect(picks).toEqual(['SC', 'SH', 'ID']);
    });
  });

  test('T6 the Custom header row never covers a player row', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 560 });
    await openTraining(page);
    await page.locator('.archetype-block[data-archetype="player-maximizer"] label.archetype-option', { hasText: 'Custom' }).click();
    const modal = page.locator('#custom-focus-modal');
    await expect(modal).toHaveClass(/is-visible/);
    const measure = () => page.evaluate(() => {
      const wrap = document.querySelector('#custom-focus-modal .custom-focus-table-wrap');
      const head = document.querySelector('#custom-focus-thead th').getBoundingClientRect();
      const first = document.querySelector('#custom-focus-tbody tr').getBoundingClientRect();
      const w = wrap.getBoundingClientRect();
      return { headTop: head.top, headBottom: head.bottom, firstTop: first.top, wrapTop: w.top, scrollable: wrap.scrollHeight - wrap.clientHeight };
    });
    const atRest = await measure();
    // At rest the first player row starts where the header ends: nothing is covered.
    expect(atRest.firstTop).toBeGreaterThanOrEqual(atRest.headBottom - 0.5);
    expect(Math.abs(atRest.headTop - atRest.wrapTop)).toBeLessThanOrEqual(2);
    // On a short window the table scrolls inside the modal and the header stays put.
    expect(atRest.scrollable).toBeGreaterThan(0);
    await modal.locator('.custom-focus-table-wrap').evaluate((el) => { el.scrollTop = 60; });
    const scrolled = await measure();
    expect(Math.abs(scrolled.headTop - atRest.headTop)).toBeLessThanOrEqual(1);
    await page.setViewportSize({ width: 1280, height: 720 });
    await modal.locator('.custom-focus-table-wrap').evaluate((el) => { el.scrollTop = 0; });
    await shot(page, 'T6-custom-focus-attributes');
  });

  test('T7 T9 Press/Traps and Training Plays', async ({ page }) => {
    await openTraining(page);
    const text = await page.locator('#training-view').innerText();
    expect(text).not.toMatch(/P\/T/);
    expect(text).toMatch(/PRESS\/TRAPS/i);
    await expect(page.locator('.label-text', { hasText: 'Press/Traps Offense Install' })).toBeVisible();
    await expect(page.locator('.label-text', { hasText: 'Press/Traps Defense Install' })).toBeVisible();
    await expect(page.locator('label.archetype-option', { hasText: 'Press/Traps' })).toBeVisible();
    const head = page.locator('.playbook-mode-selection .drill-title');
    await expect(head).toHaveText('Training Plays');
    const gap = await page.evaluate(() => {
      const h = document.querySelector('.playbook-mode-selection .drill-title').getBoundingClientRect();
      const t = document.querySelector('.playbook-mode-toggle').getBoundingClientRect();
      return t.top - h.bottom;
    });
    expect(gap).toBeGreaterThanOrEqual(10);
    await shot(page, 'T1-T7-T9-training-top');
  });

  test('T8 Custom Playbook opens after points are spent, and comes back selected', async ({ page }) => {
    await openTraining(page);
    // The broken case: any allocation made the leave-confirm swallow the click.
    await allocate(page, [0, 0, 0, 0, 0, 0, 0, 3, 2]);
    await page.locator('#playbook-mode-custom-btn').click();
    await expect(page).toHaveURL(/\/training-playbooks\.html/, { timeout: 20000 });
    await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
    await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
    await expect(page.locator('#tp-dock-off-install')).toHaveText('Offense Install \u00b7 3 PTS');
    await expect(page.locator('#tp-dock-def-install')).toHaveText('Defense Install \u00b7 2 PTS');
    await shot(page, 'T8-custom-playbook');
    await page.locator('#tp-offense-grid .tp-card').first().click();
    await page.locator('#tp-defense-grid .tp-card').first().click();
    await page.locator('#tp-save').click();
    await expect(page).toHaveURL(/\/training\.html/, { timeout: 20000 });
    await expect(page.locator('#playbook-mode-custom-btn')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#custom-playbook-banner')).toBeVisible();
    // The allocation made before the trip is still there.
    await expect(page.locator('#team-offense-install')).toHaveValue('3');
    await expect(page.locator('#team-defense-install')).toHaveValue('2');
    await shot(page, 'T8-custom-playbook-returned');
  });

  test('T10 Prep Player Training: air between the tutorial button and the tallies', async ({ page }) => {
    await openFcc(page, 'training-view');
    await expect(page.locator('#training-view .pdg-grid')).toBeVisible({ timeout: 30000 });
    const gap = await page.evaluate(() => {
      const btn = document.getElementById('player-dev-tutorial-btn').getBoundingClientRect();
      const tally = document.querySelector('#training-view .pdg-tally').getBoundingClientRect();
      return tally.top - btn.bottom;
    });
    expect(gap).toBeGreaterThanOrEqual(14);
    // Prep keeps its table; the card grid is the weekly page's layout.
    await expect(page.locator('#training-view .pdg-table tbody tr')).toHaveCount(12);
    await shot(page, 'T10-fcc-player-development');
  });
});

// ---------------------------------------------------------------------------
// Training Report
// ---------------------------------------------------------------------------

const TONE = {
  neutral: 'rgba(255, 255, 255, 0.87)',
  up: 'rgb(52, 236, 39)',
  elite: 'rgb(74, 144, 217)',
  down: 'rgb(255, 109, 109)',
  flat: 'rgba(255, 255, 255, 0.38)',
};

/** Team Report rows by label: the mark text and its painted colour. */
function teamMarks(page) {
  return page.evaluate(() => {
    const out = {};
    document.querySelectorAll('#team-attributes-grid .team-attr-item').forEach((item) => {
      const name = item.querySelector('.attr-name').textContent.trim();
      const mark = item.querySelector('.attr-change');
      out[name] = { text: mark.textContent, color: getComputedStyle(mark).color };
    });
    return out;
  });
}

/** Player Report rows by player: the SC cell's mark text and colour. */
function playerMarks(page, markSelector) {
  return page.evaluate((sel) => {
    const head = [...document.querySelectorAll('#players-thead th')].map((th) => th.textContent.trim());
    const sc = head.indexOf('SC');
    return [...document.querySelectorAll('#players-tbody tr')].map((tr) => {
      const cell = tr.children[sc];
      const mark = sel ? cell.querySelector(sel) : cell;
      return mark ? { text: mark.textContent, color: getComputedStyle(mark).color } : null;
    });
  }, markSelector || '');
}

async function reportReady(page, week) {
  await expect(page.locator('#week-number')).toHaveText(String(week), { timeout: 15000 });
  await waitOverlay(page);
}

test.describe('training report', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('R1 no undesigned beat: sections stay hidden until the data is in', async ({ page }) => {
    await openReport(page, { reportDelayMs: 2500 });
    const host = page.locator('#training-report-view');
    await expect(host).toHaveClass(/is-loading/);
    await waitOverlay(page);
    // During the wait: no section headings, no "--" placeholders, a skeleton instead.
    const during = await page.evaluate(() => {
      const visible = (el) => {
        const cs = getComputedStyle(el);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0;
      };
      return {
        headings: [...document.querySelectorAll('#training-report-view h2')].filter(visible).map((el) => el.textContent.trim()),
        placeholders: [...document.querySelectorAll('#week-number, #upcoming-opponent, #training-focus, #training-notes-brief')].filter(visible).length,
        skeleton: visible(document.querySelector('#training-report-view .report-skeleton')),
        bars: [...document.querySelectorAll('#training-report-view .rsk')].filter(visible).length,
        loading: document.getElementById('training-report-view').classList.contains('is-loading'),
      };
    });
    expect(during.loading).toBe(true);
    expect(during.headings).toEqual([]);
    expect(during.placeholders).toBe(0);
    expect(during.skeleton).toBe(true);
    expect(during.bars).toBeGreaterThan(4);
    await shot(page, 'R1-report-loading-beat');
    await reportReady(page, 12);
    await expect(host).not.toHaveClass(/is-loading/);
    await expect(page.locator('#training-report-view .report-skeleton')).toBeHidden();
    await expect(page.locator('#training-report-view h2', { hasText: 'Team Report' })).toBeVisible();
  });

  test('R1 the static host page is hidden from first paint', async () => {
    const html = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/training-report.html'), 'utf8');
    expect(html).toMatch(/<div id="training-report-view" class="is-loading"/);
    expect(html).toContain('class="report-skeleton"');
  });

  test('R2 in-season marks: one up and one down neutral, two up green, three up blue, more down red', async ({ page }) => {
    await openReport(page, { reportWeek: 12 });
    await reportReady(page, 12);
    const team = await teamMarks(page);
    expect(team.Offense).toEqual({ text: '▲▲▲', color: TONE.elite });      // +6
    expect(team.Defense).toEqual({ text: '▲▲', color: TONE.up });           // +2.5
    expect(team['Fast Break']).toEqual({ text: '▲', color: TONE.neutral });  // +0.4
    expect(team['P/T Defense']).toEqual({ text: '▼', color: TONE.neutral }); // -1: one down, neutral outside camp
    expect(team.Fight).toEqual({ text: '▼▼', color: TONE.down });           // -2
    expect(team.Discipline).toEqual({ text: '▼▼▼', color: TONE.down });     // -3
    // Player Report, Training Changes: +6 / +2.5 / +0.4 / 0 / -0.3 / -1 / -2 / -3
    const players = await playerMarks(page);
    expect(players.slice(0, 8)).toEqual([
      { text: '▲▲▲', color: TONE.elite },
      { text: '▲▲', color: TONE.up },
      { text: '▲', color: TONE.neutral },
      { text: '–', color: TONE.flat },      // exactly 0 is a dash, as in camp
      { text: '▲', color: TONE.neutral },   // -0.3 still reads as holding
      { text: '▼', color: TONE.neutral },
      { text: '▼▼', color: TONE.down },
      { text: '▼▼▼', color: TONE.down },
    ]);
    // Team Report: an attribute that did not move carries no arrow, in season as in camp.
    expect(team.Shooting.text).not.toMatch(/[▲▼]/);
    await shot(page, 'R2-report-in-season');
    await shot(page, 'R2-player-report-training-changes', page.locator('.players-section'));
  });

  test('R2 camp marks: the camp scale, and any down is red', async ({ page }) => {
    await openReport(page, { reportWeek: 1 });
    await reportReady(page, 1);
    const team = await teamMarks(page);
    expect(team.Offense).toEqual({ text: '▲▲▲', color: TONE.elite });   // +6  (> 5)
    expect(team.Defense).toEqual({ text: '▲▲', color: TONE.up });        // +2.5 (2..5)
    expect(team['Fast Break']).toEqual({ text: '▲', color: TONE.neutral }); // +0.4 (< 2)
    expect(team['P/T Defense']).toEqual({ text: '▼', color: TONE.down });   // -1: one down is red in camp
    expect(team.Fight).toEqual({ text: '▼▼', color: TONE.down });        // -2
    expect(team.Discipline).toEqual({ text: '▼▼', color: TONE.down });   // -3 is still two on the camp scale
    const players = await playerMarks(page);
    expect(players[3]).toEqual({ text: '–', color: TONE.flat });          // exactly 0 is a dash
    expect(players[4]).toEqual({ text: '▼', color: TONE.down });          // -0.3
    await shot(page, 'R2-report-camp');
  });

  test('R3 Attributes view marks are pluses and minuses in the same tones', async ({ page }) => {
    await openReport(page, { reportWeek: 12 });
    await reportReady(page, 12);
    await page.locator('.players-section .toggle-btn[data-view="attributes"]').click();
    const marks = await playerMarks(page, '.delta-mark');
    expect(marks.slice(0, 8)).toEqual([
      { text: '+++', color: TONE.elite },
      { text: '++', color: TONE.up },
      { text: '+', color: TONE.neutral },
      null,                                   // no change: no mark
      { text: '+', color: TONE.neutral },    // -0.3 reads as holding in season
      { text: '\u2212', color: TONE.neutral },
      { text: '\u2212\u2212', color: TONE.down },
      { text: '\u2212\u2212\u2212', color: TONE.down },
    ]);
    const table = await page.locator('#players-tbody').innerText();
    expect(table).not.toMatch(/[▲▼]/);
    // Exactly 0: no plus beside the value, and nothing to hover for.
    const zero = await page.evaluate(() => {
      const head = [...document.querySelectorAll('#players-thead th')].map((th) => th.textContent.trim());
      const cell = document.querySelectorAll('#players-tbody tr')[3].children[head.indexOf('SC')];
      return { delta: cell.classList.contains('is-delta'), tip: cell.getAttribute('data-tooltip') };
    });
    expect(zero).toEqual({ delta: false, tip: null });
    await shot(page, 'R3-player-report-attributes', page.locator('.players-section'));
  });

  test('R4 Playbook Summary: Offense and Defense panels, sub-sections as columns, no Section column', async ({ page }) => {
    await openReport(page, { reportWeek: 12 });
    await reportReady(page, 12);
    const section = page.locator('.playbook-summary-section');
    await expect(section.locator('.pbs-panel-title')).toHaveText(['Offense', 'Defense']);
    await expect(section.locator('.pbs-panel--offense .pbs-group-head h4')).toHaveText([
      'Motion', 'Inside Set Plays', 'Attack Set Plays', 'Outside Set Plays',
    ]);
    await expect(section.locator('.pbs-panel--defense .pbs-group-head h4')).toHaveText(['Man', 'Zone']);
    // No defense moved this week (in season): every row is a dash, not one up.
    const defenseDeltas = await section.locator('.pbs-panel--defense .pbs-delta').evaluateAll((els) => els.map((el) => ({
      text: el.textContent, color: getComputedStyle(el).color,
    })));
    expect(defenseDeltas.length).toBeGreaterThan(0);
    defenseDeltas.forEach((delta) => expect(delta).toEqual({ text: '–', color: TONE.flat }));
    expect(await section.locator('.pbs-panel--offense .pbs-delta').allTextContents()).toContain('▲');
    await expect(section.locator('table')).toHaveCount(0);
    expect(await section.innerText()).not.toMatch(/\bSection\b/);
    const plays = FIXTURE.teamData.plays_data;
    const count = (pred) => Object.values(plays).filter(pred).length;
    const groups = section.locator('.pbs-panel--offense .pbs-group');
    await expect(groups.nth(0).locator('.pbs-row')).toHaveCount(count((p) => p.play_type === 'motion'));
    await expect(groups.nth(1).locator('.pbs-row')).toHaveCount(count((p) => p.play_type === 'set_play' && p.play_focus === 'inside'));
    await expect(groups.nth(2).locator('.pbs-row')).toHaveCount(count((p) => p.play_type === 'set_play' && p.play_focus === 'attack'));
    await expect(groups.nth(3).locator('.pbs-row')).toHaveCount(count((p) => p.play_type === 'set_play' && p.play_focus === 'outside'));
    const geom = await page.evaluate(() => {
      const box = (el) => { const r = el.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), r: Math.round(r.right), h: Math.round(r.height) }; };
      return {
        panels: [...document.querySelectorAll('.pbs-panel')].map(box),
        offense: [...document.querySelectorAll('.pbs-panel--offense .pbs-group')].map(box),
        defense: [...document.querySelectorAll('.pbs-panel--defense .pbs-group')].map(box),
        section: box(document.querySelector('.playbook-summary-section')),
        rows: document.querySelectorAll('.pbs-row').length,
      };
    });
    // Side by side, and the sub-sections run across, not down.
    expect(geom.panels[0].y).toBe(geom.panels[1].y);
    expect(geom.panels[1].x).toBeGreaterThan(geom.panels[0].r);
    expect(new Set(geom.offense.map((g) => g.y)).size).toBe(1);
    expect(new Set(geom.offense.map((g) => g.x)).size).toBe(4);
    expect(new Set(geom.defense.map((g) => g.y)).size).toBe(1);
    // Compact: far shorter than one row per play stacked in a single list.
    expect(geom.section.h).toBeLessThan(geom.rows * 30 * 0.6);
    await shot(page, 'R4-playbook-summary', section);
  });
});

// ---------------------------------------------------------------------------
// Game Plan, Playbooks, Set Lineup
// ---------------------------------------------------------------------------

test.describe('game plan', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('G1 four section heads with one spacing: Shot Diet, Execution, Disruption, Transition', async ({ page }) => {
    await openFcc(page, 'game-plan-view');
    const view = page.locator('#game-plan-view');
    await expect(view.locator('#slider-offense')).toBeVisible({ timeout: 30000 });
    await expect(view.locator('section[aria-label="Offense"] .grp-h')).toHaveText(['Shot Diet', 'Execution']);
    await expect(view.locator('section[aria-label="Defense"] .grp-h')).toHaveText(['Disruption', 'Transition']);
    const geom = await page.evaluate(() => {
      const host = document.getElementById('game-plan-view');
      const heads = {};
      host.querySelectorAll('.grp-h').forEach((el) => {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const section = el.closest('section');
        // The slider row that follows the head, and the one before it.
        const rows = [...section.querySelectorAll('.gpr')].map((row) => row.getBoundingClientRect());
        const next = rows.find((row) => row.top >= r.bottom - 1);
        const prev = [...rows].reverse().find((row) => row.bottom <= r.top + 1);
        heads[el.textContent.trim()] = {
          y: Math.round(r.top), bottom: Math.round(r.bottom), x: Math.round(r.left),
          font: cs.font, color: cs.color, padTop: cs.paddingTop,
          toNext: Math.round(next.top - r.bottom), fromPrev: Math.round(r.top - prev.bottom),
        };
      });
      const order = (label) => [...host.querySelectorAll('section[aria-label="' + label + '"] .grp-h, section[aria-label="' + label + '"] .gt')]
        .map((el) => (el.classList.contains('grp-h') ? '# ' + el.textContent.trim() : el.id));
      const tracks = [...host.querySelectorAll('.gt')].map((el) => {
        const r = el.getBoundingClientRect();
        return { id: el.id, x: Math.round(r.left), w: Math.round(r.width), side: el.closest('section').getAttribute('aria-label') };
      });
      return { heads, offense: order('Offense'), defense: order('Defense'), tracks };
    });
    expect(geom.offense).toEqual([
      'slider-offense', '# Shot Diet', 'slider-inside', 'slider-attack', 'slider-outside',
      '# Execution', 'slider-tempo', 'slider-alterations',
    ]);
    expect(geom.defense).toEqual([
      'slider-defense', '# Disruption', 'slider-aggression', 'slider-hc-trap', 'slider-fc-press',
      '# Transition', 'slider-fast_breaks', 'slider-rebounding',
    ]);
    const h = geom.heads;
    // Same type, same spacing above and below, for all four.
    ['Shot Diet', 'Disruption', 'Transition'].forEach((name) => {
      expect(h[name].font, name).toBe(h.Execution.font);
      expect(h[name].color, name).toBe(h.Execution.color);
      expect(h[name].padTop, name).toBe(h.Execution.padTop);
      expect(h[name].toNext, name).toBe(h.Execution.toNext);
      expect(h[name].fromPrev, name).toBe(h.Execution.fromPrev);
    });
    // And they line up across the gutter.
    expect(h['Shot Diet'].y).toBe(h.Disruption.y);
    expect(h.Execution.y).toBe(h.Transition.y);
    // Shot Diet is no longer inset: its tracks share the column's one geometry.
    ['Offense', 'Defense'].forEach((side) => {
      const col = geom.tracks.filter((t) => t.side === side);
      expect(new Set(col.map((t) => t.x)).size, side).toBe(1);
      expect(new Set(col.map((t) => t.w)).size, side).toBe(1);
    });
    // The tip still belongs to the Shot Diet head.
    await view.locator('#shot-diet-nest .slider-nest__info').hover();
    await page.mouse.move(0, 0);
    await shot(page, 'G1-game-plan');
  });
});

async function openPlaybooks(page) {
  await openFcc(page, 'playbooks-view');
  await expect(page.locator('#playbooks-view .play').first()).toBeVisible({ timeout: 30000 });
}

test.describe('playbooks', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('P1 Set Plays read as Inside, Attack and Outside', async ({ page }) => {
    await openPlaybooks(page);
    const grid = page.locator('#playbooks-view #set-plays-grid');
    await expect(grid.locator('.pb-sub h3')).toHaveText(['Inside', 'Attack', 'Outside']);
    const layout = await grid.evaluate((el) => [...el.children].map((child) => {
      if (child.classList.contains('pb-sub')) return '# ' + child.dataset.focusGroup;
      if (child.classList.contains('play')) return child.dataset.focus || 'none';
      return child.className;
    }));
    // Every play sits under the head for its own focus.
    let current = '';
    const seen = [];
    layout.forEach((entry) => {
      if (entry.startsWith('# ')) { current = entry.slice(2); seen.push(current); return; }
      if (entry === 'pdet') return;
      expect(entry).toBe(current);
    });
    expect(seen).toEqual(['inside', 'attack', 'outside']);
    const plays = FIXTURE.playbooks.set_plays;
    for (const focus of ['inside', 'attack', 'outside']) {
      const n = plays.filter((p) => p.play_focus === focus).length;
      await expect(grid.locator('.play[data-focus="' + focus + '"]')).toHaveCount(n);
      await expect(grid.locator('.pb-sub[data-focus-group="' + focus + '"] .pb-sub-cnt')).toHaveText(n + (n === 1 ? ' play' : ' plays'));
    }
    // The three sub-totals are the section's 100%.
    const totals = await grid.locator('.pb-sub-tot').allTextContents();
    expect(totals.map((t) => parseInt(t, 10)).reduce((a, b) => a + b, 0)).toBe(100);
    // The focus is the heading now, not a prefix on every row.
    expect(await grid.locator('.play .pn span').first().textContent()).toMatch(/^Target shooter /);
    await shot(page, 'P1-set-plays', page.locator('#playbooks-view section[data-section="setPlays"]'));
  });

  test('P2 four tabs in order, Fast Breaks and Press/Traps on their own', async ({ page }) => {
    await openPlaybooks(page);
    const tabs = page.locator('#playbooks-view .playbooks-tab');
    await expect(tabs).toHaveText(['Offense', 'Defense', 'Fast Breaks', 'Press/Traps']);
    const visibleSections = () => page.evaluate(() => [...document.querySelectorAll('#playbooks-view .pb-sec')]
      .filter((el) => el.getClientRects().length > 0).map((el) => el.dataset.section));
    expect(await visibleSections()).toEqual(['motion', 'setPlays']);
    await tabs.nth(1).click();
    expect(await visibleSections()).toEqual(['manDefense', 'zoneDefense']);
    await tabs.nth(2).click();
    await expect(tabs.nth(2)).toHaveAttribute('aria-selected', 'true');
    expect(await visibleSections()).toEqual(['fastBreaks']);
    await expect(page.locator('#playbooks-view #fast-breaks-chips > *')).toHaveCount(FIXTURE.playbooks.fast_breaks.length);
    await shot(page, 'P2-fast-breaks-tab');
    await tabs.nth(3).click();
    await expect(tabs.nth(3)).toHaveAttribute('aria-selected', 'true');
    expect(await visibleSections()).toEqual(['hcTraps']);
    await expect(page.locator('#playbooks-view section[data-section="hcTraps"] h2')).toHaveText('Half-Court Traps');
    await expect(page.locator('#playbooks-view #hc-traps-chips > *')).toHaveCount(FIXTURE.playbooks.hc_traps.length);
    await shot(page, 'P2-press-traps-tab');
    await tabs.nth(0).click();
    expect(await visibleSections()).toEqual(['motion', 'setPlays']);
  });

  test('P3 arrow keys move a slider, including straight after a click on it', async ({ page }) => {
    await openPlaybooks(page);
    const value = (sel) => page.locator(sel).first().getAttribute('aria-valuenow').then(Number);
    // An enforced (Motion) slider that is free to move.
    const id = await page.evaluate(() => {
      const el = document.querySelector('#playbooks-view #motion-grid .et-slider');
      return el.dataset.sl;
    });
    const sel = '#playbooks-view [data-sl="' + id + '"]';
    // Click the track: the tile is re-rendered when the pointer lifts. Focus must survive.
    const box = await page.locator(sel).boundingBox();
    await page.mouse.click(box.x + box.width * 0.4, box.y + box.height / 2);
    await expect.poll(() => page.evaluate(() => document.activeElement && document.activeElement.dataset.sl)).toBe(id);
    const start = await value(sel);
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => value(sel)).toBe(start + 1);
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowLeft');
    await expect.poll(() => value(sel)).toBe(start - 1);

    // A chip slider (Fast Breaks), by keyboard alone and after a click.
    await page.locator('#playbooks-view .playbooks-tab[data-tab="fastBreaks"]').click();
    const chipId = await page.evaluate(() => document.querySelector('#playbooks-view #fast-breaks-chips .chip-slider').dataset.csl);
    const chipSel = '#playbooks-view [data-csl="' + chipId + '"]';
    const chipBox = await page.locator(chipSel).boundingBox();
    await page.mouse.click(chipBox.x + chipBox.width * 0.5, chipBox.y + chipBox.height / 2);
    await expect.poll(() => page.evaluate(() => document.activeElement && document.activeElement.dataset.csl)).toBe(chipId);
    const chipStart = await value(chipSel);
    await page.keyboard.press('ArrowLeft');
    await expect.poll(() => value(chipSel)).toBe(chipStart - 1);
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => value(chipSel)).toBe(chipStart + 1);
  });

  test('P4 the strip is called Shot Distribution', async ({ page }) => {
    await openPlaybooks(page);
    const label = page.locator('#playbooks-view .psw-strip-label');
    await expect(label).toHaveText('Shot Distribution');
    await expect(page.locator('#playbooks-view')).not.toContainText('Expected', { ignoreCase: true });
    await shot(page, 'P1-P2-P4-playbooks-offense');
  });
});

// Follow-ups from Jamie on Prep › Playbooks (2026-10-02). PB_SHOTS=1 writes the after
// shots to reports/playbooks-followups/.
const PB_OUT = path.join(__dirname, '../../reports/playbooks-followups');
async function pbShot(page, name) {
  if (process.env.PB_SHOTS !== '1') return;
  fs.mkdirSync(PB_OUT, { recursive: true });
  await settle(page);
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(PB_OUT, name + '.png'), animations: 'disabled' });
}

test.describe('playbooks follow-ups', () => {
  test.skip(PHASE === 'before', 'after tree only');

  for (const [width, height] of [[1280, 720], [1920, 1080]]) {
    test('the tab row sits clear below the Shot Distribution strip at ' + width + ', at rest and scrolled', async ({ page }) => {
      await page.setViewportSize({ width, height });
      await openPlaybooks(page);
      const measure = (scrollTop) => page.evaluate((y) => {
        const main = document.querySelector('html.gob-shell .main');
        main.scrollTop = y;
        const box = (sel) => {
          const r = document.querySelector(sel).getBoundingClientRect();
          return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right) };
        };
        const strip = document.querySelector('#playbooks-view .playbooks-shot-weights-strip');
        return {
          scrolled: main.scrollTop,
          head: box('html.gob-shell .pg-head'),
          strip: box('#playbooks-view .playbooks-shot-weights-strip'),
          tabs: box('#playbooks-view .playbooks-tabs'),
          section: box('#playbooks-view .playbooks-tabpane.on .pb-sec-head'),
          stripFill: getComputedStyle(strip).backgroundColor,
        };
      }, scrollTop);
      const rest = await measure(0);
      const sectionGap = rest.section.top - rest.tabs.bottom;
      for (const y of [0, 60, 150, 400, 900]) {
        const m = await measure(y);
        const note = width + ' scroll ' + y + ' ' + JSON.stringify(m);
        // The two boxes never overlap, and the tab row keeps the section spacing below the strip.
        expect(m.tabs.top, note).toBeGreaterThanOrEqual(m.strip.bottom);
        expect(m.tabs.top - m.strip.bottom, note).toBe(rest.tabs.top - rest.strip.bottom);
        expect(m.tabs.top - m.strip.bottom, note).toBeGreaterThanOrEqual(14);
        expect(Math.abs((m.tabs.top - m.strip.bottom) - sectionGap), note).toBeLessThanOrEqual(6);
        // The strip pins under the page head, never over it, and is not see-through.
        expect(m.strip.top, note).toBeGreaterThanOrEqual(m.head.bottom);
        expect(m.stripFill, note).not.toBe('rgba(0, 0, 0, 0)');
      }
      // Scrolled: the plays pass under the pinned pair, the pair stays where it was.
      const scrolled = await measure(400);
      expect(scrolled.scrolled).toBeGreaterThan(0);
      expect(scrolled.strip.top).toBe(rest.strip.top);
      expect(scrolled.tabs.top).toBe(rest.tabs.top);
      expect(scrolled.section.top).toBeLessThan(rest.section.top);
      await measure(0);
      await pbShot(page, 'tabs-strip-after-' + width);
      await measure(150);
      await pbShot(page, 'tabs-strip-after-' + width + '-scrolled');
    });
  }
});

test.describe('set lineup', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('L1 the action buttons sit directly under the charts at any panel height', async ({ page, request }) => {
    await openSetLineup(page, request);
    const measure = () => page.evaluate(() => {
      const charts = document.getElementById('lineup-shot-weights').getBoundingClientRect();
      const actions = document.querySelector('.lineup-rail-actions').getBoundingClientRect();
      const autoset = document.getElementById('autoset-lineup').getBoundingClientRect();
      const panel = document.querySelector('.lineup-right-panel').getBoundingClientRect();
      return {
        gap: Math.round(autoset.top - charts.bottom),
        fromChartsTop: Math.round(autoset.top - charts.top),
        panelH: Math.round(panel.height),
        actionsTop: Math.round(actions.top),
      };
    });
    const short = await measure();
    expect(short.gap).toBeGreaterThanOrEqual(8);
    expect(short.gap).toBeLessThanOrEqual(24);
    await shot(page, 'L1-set-lineup');
    // Grow the container: the panel gets taller and the buttons do not move.
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.waitForTimeout(200);
    const tall = await measure();
    expect(tall.panelH).toBeGreaterThan(short.panelH);
    expect(tall.gap).toBe(short.gap);
    expect(tall.fromChartsTop).toBe(short.fromChartsTop);
    await expect(page.locator('#autoset-lineup')).toBeVisible();
    await expect(page.locator('#gameplan-optional')).toBeVisible();
    await expect(page.locator('#playbooks-button')).toBeVisible();
    await shot(page, 'L1-set-lineup-tall');
  });
});
