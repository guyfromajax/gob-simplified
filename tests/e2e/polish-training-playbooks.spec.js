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
      const body = report(opts.reportWeek || cc.week || 12);
      if (opts.reportPatch) opts.reportPatch(body);
      return fulfillJson(route, body);
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

async function shot(page, item, locator, file) {
  if (!PHASE && !file) return;
  fs.mkdirSync(OUT, { recursive: true });
  await settle(page);
  const dest = file || path.join(OUT, PHASE + '-' + item + '-1280.png');
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

  test('the Culture Builder mark is a heart; the other three icons are untouched', async ({ page }) => {
    await openTraining(page);
    const marks = await page.evaluate(() => {
      const out = {};
      document.querySelectorAll('#training-view .archetype-block').forEach((block) => {
        const svg = block.querySelector('.arch-mark svg');
        const cs = getComputedStyle(svg);
        const box = svg.getBoundingClientRect();
        out[block.dataset.archetype] = {
          inner: svg.innerHTML,
          viewBox: svg.getAttribute('viewBox'),
          strokeWidth: svg.getAttribute('stroke-width'),
          linecap: svg.getAttribute('stroke-linecap'),
          fill: svg.getAttribute('fill'),
          size: Math.round(box.width) + 'x' + Math.round(box.height),
          color: cs.color,
        };
      });
      return out;
    });
    // Jamie likes these three: byte for byte as they were.
    expect(marks.authoritarian.inner).toBe('<circle cx="6" cy="10" r="3.5"></circle><path d="M6 6.5h8v3H9.4"></path><path d="M3.2 3.6l1.1 1.5M6.4 2.6v1.9"></path>');
    expect(marks['systems-coach'].inner).toBe('<rect x="2.5" y="2.5" width="11" height="11" rx="2"></rect><path d="M5 5l2 2M7 5L5 7"></path><circle cx="10.6" cy="10.6" r="1.3"></circle><path d="M6.2 10.8c1-.2 2.6-1.6 3.4-4"></path>');
    expect(marks['player-maximizer'].inner).toBe('<path d="M2.5 13.5h11"></path><path d="M4.5 13.5v-3M8 13.5v-5.5M11.5 13.5V6.5"></path><path d="M9.5 4.2l2-2 2 2"></path>');
    // The heart: one closed outline, no figures.
    const heart = marks['culture-builder'];
    expect(heart.inner).toBe('<path d="M8 13.4S2.5 10.2 2.5 6.3A2.9 2.9 0 0 1 8 5a2.9 2.9 0 0 1 5.5 1.3c0 3.9-5.5 7.1-5.5 7.1z"></path>');
    expect(heart.inner).not.toContain('circle');
    // Same line weight, size and outline style as the set; its own purple mark colour.
    ['viewBox', 'strokeWidth', 'linecap', 'fill', 'size'].forEach((key) => {
      expect(heart[key], key).toBe(marks.authoritarian[key]);
      expect(heart[key], key).toBe(marks['player-maximizer'][key]);
    });
    expect(heart.color).toBe('rgb(168, 118, 230)');
    if (process.env.PB_SHOTS === '1') {
      const dir = path.join(__dirname, '../../reports/training-followups');
      fs.mkdirSync(dir, { recursive: true });
      await page.locator('.coaching-section').evaluate((el) => {
        el.scrollIntoView({ block: 'center' });
      });
      await settle(page);
      await page.mouse.move(0, 0);
      await page.screenshot({ path: path.join(dir, 'culture-builder-heart-after-1280.png'), animations: 'disabled' });
    }
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
  upFaint: 'rgba(52, 236, 39, 0.45)',
  elite: 'rgb(74, 144, 217)',
  down: 'rgb(255, 109, 109)',
  downFaint: 'rgba(255, 109, 109, 0.6)',
  flat: 'rgba(255, 255, 255, 0.38)',
};

/** Chrome reports a color-mix() as `color(srgb r g b / a)`; read it back as rgba() like the rest. */
function rgba(color) {
  const m = /^color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)(?: \/ ([\d.]+))?\)$/.exec(color);
  if (!m) return color;
  const ch = (v) => Math.round(Number(v) * 255);
  const alpha = m[4] == null ? 1 : Math.round(Number(m[4]) * 100) / 100;
  return alpha === 1
    ? 'rgb(' + ch(m[1]) + ', ' + ch(m[2]) + ', ' + ch(m[3]) + ')'
    : 'rgba(' + ch(m[1]) + ', ' + ch(m[2]) + ', ' + ch(m[3]) + ', ' + alpha + ')';
}
const tones = (mark) => (mark ? { text: mark.text, color: rgba(mark.color) } : null);

/** The drawn box of a point selector: its ::before. */
function boxMark(locator) {
  return locator.evaluate((el) => {
    const cs = getComputedStyle(el, '::before');
    return {
      border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
      bg: cs.backgroundColor,
      opacity: cs.opacity,
    };
  });
}

function drillRow(page, id) {
  return page.locator('#training-view .slider-label').filter({ has: page.locator('#' + id) });
}

const SEL_SHOTS = path.join(__dirname, '../../reports/training-followups');
const CLEAR_WHITE = 'rgba(0, 0, 0, 0)';
const OUTLINE = 'rgba(255, 255, 255, 0.45)';     // --train-box-outline as shipped (option B, Jamie's choice)
const OUTLINE_A = 'rgba(255, 255, 255, 0.25)';   // option A, the subtler strength not chosen

test.describe('training point selectors', () => {
  test.skip(PHASE === 'before', 'after tree only');

  test('an empty row reads as five open slots: outlined, unfilled, no permanent zero mark', async ({ page }) => {
    await openTraining(page);
    const rows = page.locator('#training-view .slider-label');
    expect(await rows.count()).toBe(20);
    const shape = await page.evaluate(() => [...document.querySelectorAll('#training-view .ps')].map((ps) => ({
      boxes: ps.querySelectorAll('.pip').length,
      buttons: ps.querySelectorAll('button').length,
      clearOpacity: getComputedStyle(ps.querySelector('.ps-clear')).opacity,
      clearEvents: getComputedStyle(ps.querySelector('.ps-clear')).pointerEvents,
      numeral: ps.querySelector('.ps-n').textContent,
      numeralColor: getComputedStyle(ps.querySelector('.ps-n')).color,
    })));
    shape.forEach((row) => {
      expect(row.boxes).toBe(5);
      expect(row.buttons).toBe(6);            // five boxes and the clear control
      expect(row.clearOpacity).toBe('0');     // not a permanent mark
      expect(row.clearEvents).toBe('none');
      expect(row.numeral).toBe('0');
      expect(row.numeralColor).toBe('rgba(255, 255, 255, 0.38)');   // dim at rest
    });
    const row = drillRow(page, 'offense-inside');
    for (let n = 0; n < 5; n++) {
      const mark = await boxMark(row.locator('.pip').nth(n));
      expect(mark.border).toBe('1px solid ' + OUTLINE);
      expect(mark.bg).toBe(CLEAR_WHITE);
    }
    // Size: a 28px tall hit area per box.
    const hit = await row.locator('.pip').first().boundingBox();
    expect(hit.height).toBeGreaterThanOrEqual(28);
    expect(hit.width).toBeGreaterThanOrEqual(22);
    // The outline strength is one token.
    await page.addStyleTag({ content: ':root{--train-box-outline:var(--white-25)}' });
    await page.waitForTimeout(250);
    expect((await boxMark(row.locator('.pip').nth(2))).border).toBe('1px solid ' + OUTLINE_A);
    expect((await boxMark(drillRow(page, 'team-scrimmages').locator('.pip').nth(4))).border).toBe('1px solid ' + OUTLINE_A);
  });

  test('filled boxes are solid white and the number turns full white', async ({ page }) => {
    await openTraining(page);
    const row = drillRow(page, 'offense-inside');
    await row.locator('.pip').nth(2).click();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(250);
    await expect(page.locator('#offense-inside')).toHaveValue('3');
    for (let n = 0; n < 5; n++) {
      const mark = await boxMark(row.locator('.pip').nth(n));
      if (n < 3) expect(mark.bg).toBe('rgb(255, 255, 255)');
      else {
        expect(mark.bg).toBe(CLEAR_WHITE);
        expect(mark.border).toBe('1px solid ' + OUTLINE);
      }
    }
    await expect(row.locator('.ps-n')).toHaveText('3');
    await expect(row.locator('.ps-n')).toHaveCSS('color', 'rgb(255, 255, 255)');
  });

  test('hovering box N previews 1..N without changing the value, and the row highlights', async ({ page }) => {
    await openTraining(page);
    const row = drillRow(page, 'offense-outside');
    await expect(row).toHaveCSS('background-color', CLEAR_WHITE);
    await row.locator('.pip').nth(2).hover();
    await page.waitForTimeout(250);
    for (let n = 0; n < 5; n++) {
      const mark = await boxMark(row.locator('.pip').nth(n));
      if (n < 3) expect(mark.bg, 'box ' + (n + 1)).toBe('rgba(255, 255, 255, 0.25)');
      else expect(mark.bg, 'box ' + (n + 1)).toBe(CLEAR_WHITE);
    }
    await expect(page.locator('#offense-outside')).toHaveValue('0');
    await expect(row).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.03)');
    // The row above is untouched.
    expect((await boxMark(drillRow(page, 'offense-inside').locator('.pip').first())).bg).toBe(CLEAR_WHITE);

    // Hovering below the current value shows what would be given back.
    await row.locator('.pip').nth(3).click();
    await row.locator('.pip').nth(1).hover();
    await page.waitForTimeout(250);
    const marks = [];
    for (let n = 0; n < 5; n++) marks.push((await boxMark(row.locator('.pip').nth(n))).bg);
    expect(marks).toEqual([
      'rgb(255, 255, 255)', 'rgb(255, 255, 255)',
      'rgba(255, 255, 255, 0.45)', 'rgba(255, 255, 255, 0.45)',
      CLEAR_WHITE,
    ]);
    await expect(page.locator('#offense-outside')).toHaveValue('4');
  });

  test('the clear control shows only with points or on row hover, and clears by click or key', async ({ page }) => {
    await openTraining(page);
    const row = drillRow(page, 'defense-inside');
    const clear = row.locator('.ps-clear');
    const slider = page.locator('#defense-inside');
    await expect(clear).toHaveCSS('opacity', '0');
    // Row hover with nothing to clear: it ghosts in, and does nothing.
    await row.locator('.label-text').hover();
    await page.waitForTimeout(250);
    await expect(clear).toHaveCSS('opacity', '0.35');
    await expect(clear).toBeDisabled();
    await page.mouse.move(0, 0);

    await row.locator('.pip').nth(3).click();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(250);
    await expect(slider).toHaveValue('4');
    await expect(clear).toHaveCSS('opacity', '1');     // stays while the row has points
    await expect(clear).toBeEnabled();
    await expect(page.locator('#req-points-used')).toHaveText('4');
    await clear.click();
    await expect(slider).toHaveValue('0');
    await expect(row.locator('.ps-n')).toHaveText('0');
    await expect(page.locator('#req-points-used')).toHaveText('0');
    await page.mouse.move(0, 0);
    await page.waitForTimeout(250);
    await expect(clear).toHaveCSS('opacity', '0');

    // By keyboard: Delete, Backspace, 0 and Home all clear from the focused row.
    for (const key of ['Delete', 'Backspace', '0', 'Home']) {
      await row.locator('.pip').nth(2).click();
      await expect(slider).toHaveValue('3');
      await slider.focus();
      await page.keyboard.press(key);
      await expect(slider, key).toHaveValue('0');
    }
    await expect(page.locator('#req-points-used')).toHaveText('0');
  });

  test('left and right arrows change the value, with a visible focus ring', async ({ page }) => {
    await openTraining(page);
    const slider = page.locator('#technical-passing');
    const row = drillRow(page, 'technical-passing');
    await page.keyboard.press('Tab');
    await slider.focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await expect(slider).toHaveValue('3');
    await expect(row.locator('.ps-n')).toHaveText('3');
    await expect(row.locator('.pip.f')).toHaveCount(3);
    await page.keyboard.press('ArrowLeft');
    await expect(slider).toHaveValue('2');
    await expect(row.locator('.pip.f')).toHaveCount(2);
    await expect(page.locator('#req-points-used')).toHaveText('2');
    const ring = await row.locator('.ps').evaluate((el) => {
      const cs = getComputedStyle(el);
      return cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor;
    });
    expect(ring).toBe('solid 2px rgb(255, 255, 255)');
    await expect(row).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.03)');
  });

  test('out of points: boxes the budget cannot reach dim further and do not take a click', async ({ page }) => {
    await openTraining(page);
    // 24 to spend: 22 spent leaves 2.
    await allocate(page, [5, 5, 5, 5, 2]);
    await expect(page.locator('#req-points-used')).toHaveText('22');
    const row = drillRow(page, 'technical-ball-handling');
    const slider = page.locator('#technical-ball-handling');
    await page.waitForTimeout(250);
    for (let n = 0; n < 5; n++) {
      const pip = row.locator('.pip').nth(n);
      const mark = await boxMark(pip);
      if (n < 2) {
        await expect(pip).toBeEnabled();
        expect(mark.opacity).toBe('1');
      } else {
        await expect(pip).toBeDisabled();
        expect(mark.opacity).toBe('0.35');
        await expect(pip).toHaveCSS('pointer-events', 'none');
      }
    }
    const far = await row.locator('.pip').nth(4).boundingBox();
    await page.mouse.click(far.x + far.width / 2, far.y + far.height / 2);
    await expect(slider).toHaveValue('0');
    // An unaffordable box never previews.
    await row.locator('.pip').nth(1).hover();
    await page.waitForTimeout(250);
    expect((await boxMark(row.locator('.pip').nth(3))).bg).toBe(CLEAR_WHITE);
    await row.locator('.pip').nth(1).click();
    await expect(slider).toHaveValue('2');
    await expect(page.locator('#req-points-used')).toHaveText('24');
    // Nothing left: every empty box on the page is out of reach, the spent ones are not.
    await page.mouse.move(0, 0);
    expect(await page.locator('#training-view .pip.x:not(:disabled)').count()).toBe(0);
    expect(await page.locator('#training-view .pip.f:disabled').count()).toBe(0);
    // Arrow keys respect the same budget.
    await page.locator('#technical-rebounding').focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.locator('#technical-rebounding')).toHaveValue('0');
  });

  for (const width of [1280, 1920, 2200]) {
    test('the boxes sit within about 200px of their label at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 1280 ? 720 : 1080 });
      await openTraining(page);
      const gaps = await page.evaluate(() => [...document.querySelectorAll('#training-view .slider-label')].map((row) => {
        const range = document.createRange();
        range.selectNodeContents(row.querySelector('.label-text'));
        return Math.round(row.querySelector('.ps .pip').getBoundingClientRect().left - range.getBoundingClientRect().right);
      }));
      expect(gaps.length).toBe(20);
      expect(Math.max(...gaps)).toBeLessThanOrEqual(215);
      expect(Math.min(...gaps)).toBeGreaterThan(24);
    });
  }

  test('option-a / option-b shots', async ({ page }) => {
    test.skip(process.env.PB_SHOTS !== '1', 'PB_SHOTS=1 only');
    test.setTimeout(240000);
    fs.mkdirSync(SEL_SHOTS, { recursive: true });
    const ASSIGNED = [3, 0, 2, 0, 0, 4, 0, 0, 5, 0, 0, 1, 0, 0, 2, 0, 0, 0, 1, 0];
    const crops = {};
    for (const width of [1280, 1920]) {
      for (const option of ['a', 'b']) {
        await page.setViewportSize({ width, height: width === 1280 ? 900 : 1080 });
        await openTraining(page);
        if (option === 'a') await page.addStyleTag({ content: ':root{--train-box-outline:var(--white-25)}' });
        await settle(page);
        await page.mouse.move(0, 0);
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(SEL_SHOTS, 'selectors-option-' + option + '-untouched-' + width + '.png'), animations: 'disabled' });
        await allocate(page, ASSIGNED);
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(SEL_SHOTS, 'selectors-option-' + option + '-assigned-' + width + '.png'), animations: 'disabled' });
        crops[option + width] = (await page.locator('#training-view .main-content-grid').screenshot({ animations: 'disabled' })).toString('base64');
        if (option === 'a' && width === 1280) {
          await drillRow(page, 'defense-outside').locator('.pip').nth(3).hover();
          await page.waitForTimeout(300);
          await page.screenshot({ path: path.join(SEL_SHOTS, 'selectors-hover-preview-1280.png') });
          await page.mouse.move(0, 0);
          await allocate(page, []);
          await allocate(page, [5, 0, 5, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 4, 0, 0, 3]);
          await page.waitForTimeout(300);
          await page.screenshot({ path: path.join(SEL_SHOTS, 'selectors-out-of-points-1280.png'), animations: 'disabled' });
          await page.locator('#technical-rebounding').focus();
          await page.keyboard.press('ArrowLeft');
          await page.waitForTimeout(300);
          await page.screenshot({ path: path.join(SEL_SHOTS, 'selectors-keyboard-focus-1280.png'), animations: 'disabled' });
        }
        // The page keeps a draft of the allocation: leave none for the next pass.
        await allocate(page, []);
        await page.evaluate(() => {
          try { localStorage.clear(); sessionStorage.clear(); } catch (err) { /* storage off */ }
        });
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    }
    // The two strengths on one sheet, A above B, same rows assigned.
    for (const width of [1280, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      await page.setContent('<body style="margin:0;padding:16px;background:#0b0e14;color:#fff;font:600 13px/1 sans-serif">'
        + '<p style="margin:0 0 8px">OPTION A: --train-box-outline: var(--white-25)</p>'
        + '<img style="display:block;max-width:100%" src="data:image/png;base64,' + crops['a' + width] + '">'
        + '<p style="margin:24px 0 8px">OPTION B (shipped, Jamie\'s choice): --train-box-outline: var(--white-45)</p>'
        + '<img style="display:block;max-width:100%" src="data:image/png;base64,' + crops['b' + width] + '">'
        + '</body>');
      await page.waitForTimeout(300);
      await page.locator('body').screenshot({ path: path.join(SEL_SHOTS, 'selectors-option-a-vs-b-' + width + '.png') });
    }
  });
});

/** Team Report rows by label: the mark text and its painted colour. */
async function teamMarks(page) {
  const raw = await page.evaluate(() => {
    const out = {};
    document.querySelectorAll('#team-attributes-grid .team-attr-item').forEach((item) => {
      const name = item.querySelector('.attr-name').textContent.trim();
      const mark = item.querySelector('.attr-change');
      out[name] = { text: mark.textContent, color: getComputedStyle(mark).color };
    });
    return out;
  });
  Object.keys(raw).forEach((name) => { raw[name] = tones(raw[name]); });
  return raw;
}

/** Player Report rows by player: the SC cell's mark text and colour. */
async function playerMarks(page, markSelector) {
  const raw = await page.evaluate((sel) => {
    const head = [...document.querySelectorAll('#players-thead th')].map((th) => th.textContent.trim());
    const sc = head.indexOf('SC');
    return [...document.querySelectorAll('#players-tbody tr')].map((tr) => {
      const cell = tr.children[sc];
      const mark = sel ? cell.querySelector(sel) : cell;
      return mark ? { text: mark.textContent, color: getComputedStyle(mark).color } : null;
    });
  }, markSelector || '');
  return raw.map(tones);
}

/** WCAG contrast of a (possibly translucent) colour painted over an opaque one. */
function contrastOver(fg, bg) {
  const parse = (c) => {
    const m = /^rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)$/.exec(rgba(c));
    return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] == null ? 1 : Number(m[4])];
  };
  const f = parse(fg);
  const b = parse(bg);
  const mixed = [0, 1, 2].map((i) => f[i] * f[3] + b[i] * (1 - f[3]));
  const lum = (rgb) => {
    const lin = rgb.map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  };
  const a = lum(mixed);
  const c = lum(b);
  return (Math.max(a, c) + 0.05) / (Math.min(a, c) + 0.05);
}

/** The opaque colour actually behind the SC cell of each Player Report row. */
function rowBackgrounds(page) {
  return page.evaluate(() => {
    const parse = (c) => {
      const m = /rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)/.exec(c);
      return m ? [Number(m[1]), Number(m[2]), Number(m[3]), m[4] == null ? 1 : Number(m[4])] : [0, 0, 0, 0];
    };
    const head = [...document.querySelectorAll('#players-thead th')].map((th) => th.textContent.trim());
    const sc = head.indexOf('SC');
    return [...document.querySelectorAll('#players-tbody tr')].map((tr) => {
      const layers = [];
      for (let node = tr.children[sc]; node; node = node.parentElement) layers.unshift(parse(getComputedStyle(node).backgroundColor));
      let out = [0, 0, 0];
      layers.forEach((l) => { out = out.map((v, i) => l[i] * l[3] + v * (1 - l[3])); });
      return { highlight: tr.classList.contains('practice-player-highlight'), color: 'rgb(' + out.map(Math.round).join(', ') + ')' };
    });
  });
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

  test('R2 in-season marks: one up faint green, one down faint red, two up green, three up blue, more down red', async ({ page }) => {
    await openReport(page, { reportWeek: 12 });
    await reportReady(page, 12);
    const team = await teamMarks(page);
    expect(team.Offense).toEqual({ text: '▲▲▲', color: TONE.elite });        // +6
    expect(team.Defense).toEqual({ text: '▲▲', color: TONE.up });             // +2.5
    expect(team['Fast Break']).toEqual({ text: '▲', color: TONE.upFaint });    // +0.4
    expect(team['P/T Defense']).toEqual({ text: '▼', color: TONE.downFaint }); // -1: one down, faint red outside camp
    expect(team.Fight).toEqual({ text: '▼▼', color: TONE.down });             // -2
    expect(team.Discipline).toEqual({ text: '▼▼▼', color: TONE.down });       // -3
    // Player Report, Training Changes: +6 / +2.5 / +0.4 / 0 / -0.3 / -1 / -2 / -3
    const players = await playerMarks(page);
    expect(players.slice(0, 8)).toEqual([
      { text: '▲▲▲', color: TONE.elite },
      { text: '▲▲', color: TONE.up },
      { text: '▲', color: TONE.upFaint },
      { text: '–', color: TONE.flat },        // exactly 0 is a dash, as in camp
      { text: '▼', color: TONE.downFaint },   // -0.3 is a drop: one down, never a green arrow
      { text: '▼', color: TONE.downFaint },
      { text: '▼▼', color: TONE.down },
      { text: '▼▼▼', color: TONE.down },
    ]);
    // Playbook Summary: +3.5 / +1.2 / +0.2 / -1 / -3 across the plays, same marks.
    const plays = (await page.locator('.playbook-summary-section .pbs-panel--offense .pbs-delta').evaluateAll((els) => els.map((el) => ({
      text: el.textContent, color: getComputedStyle(el).color,
    })))).map(tones);
    const byText = {};
    plays.forEach((mark) => { byText[mark.text] = mark.color; });
    expect(byText).toEqual({ '▲▲▲': TONE.elite, '▲▲': TONE.up, '▲': TONE.upFaint, '▼': TONE.downFaint, '▼▼▼': TONE.down });
    // Team Report: an attribute that did not move carries no arrow, in season as in camp.
    expect(team.Shooting.text).not.toMatch(/[▲▼]/);
    await shot(page, 'R2-report-in-season');
    await shot(page, 'R2-player-report-training-changes', page.locator('.players-section'));
  });

  test('R2 in-season: a single arrow follows the sign; the two- and three-arrow thresholds have not moved', async ({ page }) => {
    const deltas = [0.01, 0.99, 1, 2.99, 3, -0.01, -0.5, -1.49, -1.5, -2.49, -2.5, 0];
    await openReport(page, {
      reportWeek: 12,
      reportPatch: (body) => {
        body.player_changes = {};
        body.players.forEach((player, i) => { body.player_changes[player.name] = { SC: deltas[i] }; });
      },
    });
    await reportReady(page, 12);
    const players = await playerMarks(page);
    expect(players.length).toBe(deltas.length);
    expect(players).toEqual([
      { text: '▲', color: TONE.upFaint },     // 0.01
      { text: '▲', color: TONE.upFaint },     // 0.99
      { text: '▲▲', color: TONE.up },         // 1
      { text: '▲▲', color: TONE.up },         // 2.99
      { text: '▲▲▲', color: TONE.elite },     // 3
      { text: '▼', color: TONE.downFaint },   // -0.01
      { text: '▼', color: TONE.downFaint },   // -0.5 (was an up arrow)
      { text: '▼', color: TONE.downFaint },   // -1.49
      { text: '▼▼', color: TONE.down },       // -1.5
      { text: '▼▼', color: TONE.down },       // -2.49
      { text: '▼▼▼', color: TONE.down },      // -2.5
      { text: '–', color: TONE.flat },        // 0
    ]);
  });

  test('R2 in-season: the faint arrows read on both zebra rows (3:1 or better)', async ({ page }) => {
    await openReport(page, { reportWeek: 12 });
    await reportReady(page, 12);
    const rows = (await rowBackgrounds(page)).filter((row) => !row.highlight);
    const zebra = [...new Set(rows.map((row) => row.color))];
    expect(zebra.length).toBe(2);
    // The colours as painted: +0.4 is row 2, -0.3 is row 4.
    const marks = await playerMarks(page);
    const upFaint = marks[2].color;
    const downFaint = marks[4].color;
    expect([upFaint, downFaint]).toEqual([TONE.upFaint, TONE.downFaint]);
    zebra.forEach((bg) => {
      expect(contrastOver(upFaint, bg)).toBeGreaterThanOrEqual(3);
      expect(contrastOver(downFaint, bg)).toBeGreaterThanOrEqual(3);
      // Faint is clearly fainter than full strength on the same row.
      expect(contrastOver(TONE.up, bg) / contrastOver(upFaint, bg)).toBeGreaterThan(2);
      expect(contrastOver(TONE.down, bg) / contrastOver(downFaint, bg)).toBeGreaterThan(1.5);
    });
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

  test('R3 Attributes view shows current values only: no marks, no change tint, no tooltip', async ({ page }) => {
    await openReport(page, {
      reportWeek: 12,
      reportPatch: (body) => {
        // The displayed value moved for two players: that used to tint the value.
        body.player_attribute_display_movements = {
          [String(body.players[0].id)]: { SC: { from: 10, to: 12 } },
          [String(body.players[7].id)]: { SC: { from: 12, to: 10 } },
        };
      },
    });
    await reportReady(page, 12);
    await page.locator('.players-section .toggle-btn[data-view="attributes"]').click();
    await expect(page.locator('#players-tbody .attribute-value-cell').first()).toBeVisible();
    const cells = await page.evaluate(() => {
      const head = [...document.querySelectorAll('#players-thead th')].map((th) => th.textContent.trim());
      const sc = head.indexOf('SC');
      return [...document.querySelectorAll('#players-tbody tr')].map((tr) => {
        const cell = tr.children[sc];
        const cs = getComputedStyle(cell);
        return {
          text: cell.textContent, classes: cell.className, children: cell.children.length,
          tip: cell.getAttribute('data-tooltip'), cursor: cs.cursor, color: cs.color, weight: cs.fontWeight, shadow: cs.boxShadow,
        };
      });
    });
    // +6 / +2.5 / +0.4 / 0 / -0.3 / -1 / -2 / -3 this week: every value reads the same way.
    expect(cells.length).toBeGreaterThanOrEqual(8);
    cells.forEach((cell) => {
      expect(cell.text).toMatch(/^\d+$/);
      // The value, in the roster's pair box (gstart / gend), and nothing else.
      expect(cell.classes).toMatch(/^attribute-value-cell g(start|end)( gshade)?$/);
      expect(cell.children).toBe(1);
      expect(cell.tip).toBeNull();
      expect(cell.cursor).not.toBe('help');
      expect(cell.color).toBe(cells[3].color);    // row 3 did not move
      expect(cell.weight).toBe(cells[3].weight);
      expect(cell.shadow).toBe('none');
    });
    await expect(page.locator('#players-tbody .delta-mark')).toHaveCount(0);
    await expect(page.locator('#players-tbody .is-delta')).toHaveCount(0);
    const values = (await page.locator('#players-tbody .attribute-value-cell').allTextContents()).join(' ');
    expect(values).not.toMatch(/[▲▼+\u2212]/);
    // Nothing to hover for.
    await page.locator('#players-tbody tr').first().locator('.attribute-value-cell').first().hover();
    await expect(page.locator('.attribute-tooltip, #training-report-attr-tooltip')).toHaveCount(0);
    await shot(page, 'R3-player-report-attributes', page.locator('.players-section'));
    // Movement still lives on Training Changes.
    await page.locator('.players-section .toggle-btn[data-view="changes"]').click();
    expect((await playerMarks(page))[0]).toEqual({ text: '▲▲▲', color: TONE.elite });
  });

  // After shots for the chrome follow-ups report (FOLLOWUP_SHOT_TAG=after|before), 1280 and 1920.
  for (const width of [1280, 1920]) {
    test('chrome follow-ups shots at ' + width + ': Attributes tab, marks in season and in camp', async ({ page }) => {
      const tag = process.env.FOLLOWUP_SHOT_TAG;
      test.skip(!tag, 'shots only');
      const dir = path.join(__dirname, '../../reports/chrome-followups');
      const snap = (name, locator) => shot(page, name, locator, path.join(dir, name + '-' + tag + '-' + width + '.png'));
      await page.setViewportSize({ width, height: width === 1280 ? 720 : 1080 });
      await openReport(page, { reportWeek: 12 });
      await reportReady(page, 12);
      await snap('f8-marks-in-season-team-report');
      await snap('f8-marks-in-season-training-changes', page.locator('.players-section'));
      await snap('f8-marks-in-season-playbook-summary', page.locator('.playbook-summary-section'));
      await page.locator('.players-section .toggle-btn[data-view="attributes"]').click();
      await snap('f7-attributes-tab', page.locator('.players-section'));
      const campCc = inSeasonCc();
      campCc.week = 1;
      await openReport(page, { reportWeek: 1, cc: campCc });
      await reportReady(page, 1);
      await snap('f8-marks-camp-team-report');
      await snap('f8-marks-camp-training-changes', page.locator('.players-section'));
    });
  }

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

test.describe('playbooks lock states', () => {
  test.skip(PHASE === 'before', 'after tree only');

  const rowState = (page, name) => page.evaluate((label) => {
    const row = [...document.querySelectorAll('#playbooks-view .play')].find((el) => el.querySelector('.pn b').textContent === label);
    const lock = row.querySelector('[data-lock]');
    const track = row.querySelector('.wb');
    const fill = track.querySelector('i');
    const pct = row.querySelector('.wt input, .wt > b');
    const cs = (el, pseudo) => getComputedStyle(el, pseudo || null);
    return {
      classes: row.className,
      pressed: lock.getAttribute('aria-pressed'),
      lockOn: lock.classList.contains('on'),
      lockColor: cs(lock).color,
      lockPlate: cs(lock).backgroundColor,
      // The closed padlock's shackle comes back down to the body; the open one stops short.
      glyph: lock.querySelector('svg path').getAttribute('d'),
      draggable: track.classList.contains('et-slider'),
      focusable: track.getAttribute('tabindex'),
      handle: cs(fill, '::after').content,
      fill: cs(fill).backgroundColor,
      trackCursor: cs(track).cursor,
      pctColor: cs(pct).color,
      pctReadonly: pct.tagName === 'INPUT' ? pct.readOnly : true,
      nameColor: cs(row.querySelector('.pn b')).color,
    };
  }, name);
  const neutral = (rgb) => {
    const m = String(rgb).match(/([\d.]+),\s*([\d.]+),\s*([\d.]+)/);
    return !!m && Math.abs(m[1] - m[2]) < 6 && Math.abs(m[2] - m[3]) < 6;
  };
  const alpha = (rgb) => { const m = String(rgb).match(/rgba\([^)]*,\s*([\d.]+)\)/); return m ? Number(m[1]) : 1; };

  for (const [width, height] of [[1280, 720], [1920, 1080]]) {
    test('a locked slider row is unmistakable beside unlocked rows at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await openPlaybooks(page);
      const lockOf = (name) => page.locator('#playbooks-view .play', { has: page.locator('.pn b', { hasText: new RegExp('^' + name + '$') }) }).locator('[data-lock]');

      const before = await rowState(page, 'PF Post Motion');
      expect(before.pressed).toBe('false');
      expect(before.classes).not.toMatch(/is-locked/);
      expect(before.draggable).toBe(true);
      expect(before.handle).not.toBe('none');                 // a draggable slider has a handle
      expect(alpha(before.lockPlate)).toBe(0);                // open padlock, no plate
      expect(before.lockColor).toBe('rgba(255, 255, 255, 0.38)');

      await lockOf('PF Post Motion').click();
      await lockOf('4-1 Motion').click();
      const locked = await rowState(page, 'PF Post Motion');
      const other = await rowState(page, '3-2 Motion');

      // The distinct class and aria-pressed.
      expect(locked.classes).toMatch(/(^| )is-locked( |$)/);
      expect(locked.pressed).toBe('true');
      expect(locked.lockOn).toBe(true);
      expect(other.classes).not.toMatch(/is-locked/);
      expect(other.pressed).toBe('false');
      // Closed padlock, full white, on a filled neutral plate. The open one is dim, no plate.
      expect(locked.glyph).not.toBe(other.glyph);
      expect(locked.lockColor).toBe('rgb(255, 255, 255)');
      expect(alpha(locked.lockPlate)).toBeGreaterThan(0.1);
      expect(neutral(locked.lockPlate)).toBe(true);
      expect(alpha(other.lockPlate)).toBe(0);
      // The locked slider: muted track, no handle, not a control.
      expect(locked.draggable).toBe(false);
      expect(locked.focusable).toBeNull();
      expect(locked.handle).toBe('none');
      expect(locked.trackCursor).toBe('default');
      expect(alpha(locked.fill)).toBeLessThan(alpha(other.fill));
      expect(other.handle).not.toBe('none');
      // The percentage dims one step; the play name does not.
      expect(locked.pctColor).toBe('rgba(255, 255, 255, 0.6)');
      expect(other.pctColor).toBe('rgb(255, 255, 255)');
      expect(locked.pctReadonly).toBe(true);
      expect(locked.nameColor).toBe(other.nameColor);
      [locked.lockColor, locked.lockPlate, locked.fill, locked.pctColor].forEach((c) => expect(neutral(c), c).toBe(true));

      // Hover and keyboard focus on the lock button.
      const freeLock = lockOf('3-2 Motion');
      await freeLock.hover();
      await expect.poll(() => freeLock.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
      await page.mouse.move(0, 0);
      await lockOf('PF Post Motion').focus();
      await page.keyboard.press('Shift+Tab');
      await page.keyboard.press('Tab');
      const ring = await lockOf('PF Post Motion').evaluate((el) => {
        const cs = getComputedStyle(el);
        return { focused: document.activeElement === el, style: cs.outlineStyle, width: cs.outlineWidth };
      });
      expect(ring).toEqual({ focused: true, style: 'solid', width: '2px' });
      await page.locator('#playbooks-view .pb-sec-title').first().click();
      await pbShot(page, 'locks-after-' + width);

      // Space on the focused lock unlocks it again.
      await lockOf('PF Post Motion').focus();
      await page.keyboard.press('Space');
      await expect(lockOf('PF Post Motion')).toHaveAttribute('aria-pressed', 'false');
      expect((await rowState(page, 'PF Post Motion')).classes).not.toMatch(/is-locked/);
    });
  }

  test('every lockable slider on every tab carries the lock; the other tabs have none', async ({ page }) => {
    await openPlaybooks(page);
    const tab = (key) => page.locator('#playbooks-view .playbooks-tab[data-tab="' + key + '"]');
    const audit = () => page.evaluate(() => [...document.querySelectorAll('#playbooks-view .playbooks-tabpane.on .pb-sec')].map((sec) => {
      const rows = [...sec.querySelectorAll('.play:not(.lk), .chip, [data-csl]')];
      const locks = [...sec.querySelectorAll('[data-lock]')];
      return {
        section: sec.dataset.section,
        sliders: sec.querySelectorAll('.wb').length,
        locks: locks.length,
        pressed: locks.every((b) => b.getAttribute('aria-pressed') === 'true' || b.getAttribute('aria-pressed') === 'false'),
        rows: rows.length,
      };
    }));
    const offense = await audit();
    expect(offense.map((s) => s.section)).toEqual(['motion', 'setPlays']);
    offense.forEach((s) => { expect(s.locks, s.section).toBe(s.sliders); expect(s.locks, s.section).toBeGreaterThan(0); expect(s.pressed).toBe(true); });
    await tab('defense').click();
    const defense = await audit();
    expect(defense.map((s) => s.section)).toEqual(['manDefense', 'zoneDefense']);
    defense.forEach((s) => { expect(s.locks, s.section).toBe(s.sliders); expect(s.locks, s.section).toBeGreaterThan(0); });
    // A locked defense row takes the same treatment.
    const first = page.locator('#playbooks-view #zone-defense-grid .play').first();
    await first.locator('[data-lock]').click();
    await expect(page.locator('#playbooks-view #zone-defense-grid .play.is-locked [data-lock][aria-pressed="true"]')).toHaveCount(1);
    // Fast Breaks and Press/Traps weights normalise instead of locking: no lock there.
    for (const key of ['fastBreaks', 'pressTraps']) {
      await tab(key).click();
      const flexible = await audit();
      expect(flexible.length).toBe(1);
      expect(flexible[0].locks, key).toBe(0);
      expect(flexible[0].sliders, key).toBeGreaterThan(0);
    }
  });
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
