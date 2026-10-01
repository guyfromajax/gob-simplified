const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

/**
 * Token hygiene (2026-10-01): values that lived in page sheets and scripts now come
 * from gob-tokens.css. Nothing may look different.
 *   --you / --you-soft / --you-line / --you-ink are tokens (were local to recruiting-spine.css)
 *   RT classes resolve through the tier tokens (elite through --blue, the same value)
 *   css/gob-buttons.css reads tokens, with the old literals as fallbacks
 *   --pos-pg / -sg / -sf / -pf / -c are tokens
 *
 * HYGIENE_SHOTS=before writes before-*.png and skips the guards: run it on develop for
 * the BEFORE set. The default run writes after-*.png and asserts computed styles.
 */
test.describe.configure({ timeout: 120000 });

const BEFORE = process.env.HYGIENE_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/token-hygiene');
const STATIC_DIR = path.join(__dirname, '../../FrontEnd/static');
const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const HUB_FID = 'f-e2e-token-hygiene';
const HUB_TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

const RT = { low: 'rgb(255, 109, 109)', mid: 'rgb(255, 215, 0)', high: 'rgb(52, 236, 39)', elite: 'rgb(74, 144, 217)', unknown: 'rgba(255, 255, 255, 0.4)' };
// A color-mix() of a token computes to color(srgb r g b / a); the old literal to rgba().
const NAVY_28 = /rgba\(39, 64, 142, 0\.28\)|srgb 0\.15\d* 0\.25\d* 0\.55\d* \/ 0\.28/;
const NAVY_55 = /rgba\(39, 64, 142, 0\.55\)|srgb 0\.15\d* 0\.25\d* 0\.55\d* \/ 0\.55/;
const ORANGE_55 = /rgba\(247, 148, 32, 0\.55\)|srgb 0\.96\d* 0\.58\d* 0\.12\d* \/ 0\.55/;
const GREEN_55 = /rgba\(52, 236, 39, 0\.55\)|srgb 0\.20\d* 0\.92\d* 0\.15\d* \/ 0\.55/;

function digest() {
  return {
    state: 'win',
    what_moved: {
      national_rank: { now: 18, prev: 22, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 8, losses: 3 },
      streak: 'W4',
      attribute_changes: [
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'SH', from: 6, to: 7 },
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'ND', from: 7, to: 6 },
        { player_id: 'p-marcus', name: 'Marcus Ruiz', attribute: 'BH', from: 4, to: 5 },
      ],
    },
    team_snapshot: {
      state: 'ready',
      chemistry: { value: 18, max: 25 },
      attitude: {
        player_count: 12,
        buckets: [
          { id: 'em_0_19', min: 0, max: 19, count: 1 },
          { id: 'em_20_39', min: 20, max: 39, count: 2 },
          { id: 'em_40_59', min: 40, max: 59, count: 4 },
          { id: 'em_60_79', min: 60, max: 79, count: 3 },
          { id: 'em_80_plus', min: 80, max: null, count: 2 },
        ],
      },
      moved_most: [
        { measure: 'fight', value: 1.4, delta: 0.3 },
        { measure: 'discipline', value: 0.9, delta: -0.2 },
      ],
    },
    result: {
      week: 11,
      home_team_name: 'Lancaster',
      away_team_name: 'Four Corners',
      home_score: 71,
      away_score: 64,
      user_is_home: true,
      site: 'home',
      neutral: null,
      opponent_team_name: 'Four Corners',
      opponent_rank: 9,
      round_name: null,
      user_won: true,
      leader_role: 'potg',
      leader: { player_id: 'p-jalen', name: 'Jalen Carter', stats: { pts: 24, reb: 6, ast: 4, fgm: 9, fga: 16, fg3m: 3, fg3a: 7, min: 2040 } },
      headline: 'Carter closes it late',
      box_score: { path: '/box-score.html', params: { mode: 'franchise', franchise_id: FID, game_id: 'g1', home: 'Lancaster', away: 'Four Corners' } },
      result_key: 'g1',
    },
    next_game: {
      week: 12, date: null, site: 'away', neutral: null, opponent: 'Bentley-Truman', rank: 21,
      record: { wins: 7, losses: 4 }, conference: 2, conference_position: 2, conference_size: 8,
      top_scorer: { name: 'Avery Cole', average: 18.4 }, top_rebounder: { name: 'Noah Peck', average: 9.1 },
      projected_starting_five: null, round_name: null, seeds: null, stakes: null, team_rt: null,
    },
    conference_standings: {
      conference: 2,
      region: 'A',
      rows: ['IDA', 'Bentley-Truman', 'Seattle AAA', 'Lancaster', 'Morristown', 'Four Corners', 'Port Allen', 'Kettle Falls'].map(function (name, index) {
        return { team_id: 'team-' + index, team_name: name, wins: 10 - index, losses: index + 1, differential: 24 - index * 4, position: index + 1, is_user: index === 3 };
      }),
    },
    todos: [
      { id: 'run_training', label_key: 'run_training', required: true, done: true, gates_advance: false, is_advance_action: false, route: '/training.html' },
      { id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: true, route: '/set-lineup.html' },
    ],
    recruiting_wire: {
      status: 'Two leans moved',
      events: [
        { recruit_id: 'r1', recruit: 'Miles Hart', position: 'SG', stars: null, filmed_grade: null, event_type: 'gained', event_text: 'Miles Hart moved you to #2', event_detail: 'Moved you to #2', list_position: 2, direction: 'up' },
        { recruit_id: 'r2', recruit: 'Owen Blake', position: 'PF', stars: null, filmed_grade: null, event_type: 'lost', event_text: 'Owen Blake dropped you to #4', event_detail: 'Dropped you to #4', list_position: 4, direction: 'down' },
      ],
      pending_count: 1,
      urgent: true,
      unseen_count: 3,
    },
    signing_day: null,
    season_preview: null,
    weekly_card_items: [],
    also: null,
  };
}

function cc(wire) {
  const body = JSON.parse(JSON.stringify(FIXTURE.cc));
  body.week = 12;
  body.session_type = 'in-season';
  body.training_completed = true;
  body.cut_required = false;
  body.team_record = { wins: 8, losses: 3 };
  body.recruiting_wire = { board_saved_week: 0, counts: {}, pending_count: 1, urgent: true, unseen_count: 3 };
  body.office_digest = digest();
  if (wire) {
    body.recruiting_wire = wire;
    body.office_digest.recruiting_wire = Object.assign({}, body.office_digest.recruiting_wire, { pending_count: 0, urgent: false });
  }
  body.moments = [];
  body.moments_for_this_visit = [];
  body.weekly_card_items = [];
  return body;
}

function points() {
  const body = JSON.parse(JSON.stringify(FIXTURE.trainingPoints));
  body.week = 12;
  body.is_camp_week = false;
  body.is_first_training = false;
  body.training_points = 24;
  body.training_unavailable = false;
  return body;
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, wire) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, cc(wire));
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, points());
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/api/gameplan' || pathname.startsWith('/api/gameplan/')) return fulfillJson(route, FIXTURE.gameplan);
    if (pathname === '/api/playbooks' || pathname.startsWith('/api/playbooks/')) return fulfillJson(route, FIXTURE.playbooks);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    return fulfillJson(route, {});
  });
}


function recruit(id, name, leans) {
  return {
    recruit_id: id,
    image_id: id,
    name: name,
    archetype: 'Slasher',
    'Home Region': 'C',
    year: 'Junior',
    height: 76,
    weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: leans ? { 1: HUB_TID, 2: 'rival-1', 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function history(rows) {
  return [20, 21, 22, 23, 24, 25, 26].map((week) => {
    const row = rows[week] || {};
    return { week: week, recruit_id: row.id || null, name: row.name || null, lean: row.lean || null };
  });
}

function dataFor(week, extra) {
  return Object.assign({
    team: 'Lancaster',
    team_id: HUB_TID,
    team_region: 'C',
    week: week,
    recruits: [recruit('r-lean', 'Ada Lean', true), recruit('r-other', 'Bea Other', false)],
    board: week >= 20 && week <= 26 ? ['r-lean'] : [],
    team_name_map: { [HUB_TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: week === 35 ? { 'r-lean': { points: 12, promise: false } } : {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: week >= 36 ? {
      signed_players: [{
        player_id: 'p-lean', image_id: 'r-lean', recruit_id: 'r-lean',
        name: 'Ada Lean', pos: 'PG', rt: 88, potential_rt_ratcheted: 92,
        year: 'Junior', team_id: HUB_TID, team_name: 'Lancaster',
      }],
    } : {},
    week_35_recruiting_ran: week >= 36,
    week_35_reveal_seen: week >= 36,
    invite_seed_modal_seen: true,
    visit_history: history(week >= 21 ? { 20: { id: 'r-lean', name: 'Ada Lean', lean: { 1: HUB_TID } } } : {}),
    current_results_week: null,
    conferences: {
      user_conference: 1, sister_conference: 2, order: [1, 2],
      by_team_id: { [HUB_TID]: 1, 'rival-1': 1 },
      user_region: 'C',
      region_by_team_id: { [HUB_TID]: 'C', 'rival-1': 'C' },
      region_team_ids: [HUB_TID, 'rival-1'],
    },
  }, extra || {});
}

function hubCc(week, wire) {
  return {
    franchise_id: HUB_FID,
    team_id: HUB_TID,
    user_team_id: HUB_TID,
    team: 'Lancaster',
    week: week,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: Object.assign({
      board_saved_week: week >= 20 && week <= 26 ? week : 0,
      counts: {},
      week_35_orders_submitted: week >= 35,
    }, wire || {}),
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function openHub(page, week, extra, wire) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, dataFor(week, extra));
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, hubCc(week, wire));
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-results')) {
      await fulfillJson(route, { regions: [] });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, version: '1.0' });
      return;
    }
    if (pathname === '/teams' || pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) {
      await fulfillJson(route, pathname === '/teams' ? [] : {});
      return;
    }
    await route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + HUB_FID + '&team_id=' + HUB_TID);
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
}


async function openFcc(page, tab, ready) {
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, mode: 'franchise', tab: tab, from: 'command_center' });
  await page.goto('/franchise-command-center.html?' + q.toString());
  await page.waitForSelector('html.gob-shell .top', { timeout: 30000 });
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready, { timeout: 30000 });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForFunction(() => Array.from(document.images).every((img) => img.complete), null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1000);
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.querySelector('html.gob-shell .main');
    if (main) main.scrollTop = 0;
  });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name), animations: 'disabled' });
}

const BUTTONS_HTML =
  '<div id="hygiene-buttons" style="display:grid;grid-template-columns:repeat(4,max-content);gap:18px 22px;padding:28px;align-items:center">' +
    '<button class="gob-btn" id="hb-default">Default</button>' +
    '<button class="gob-btn gob-btn--action" id="hb-action">Save Plan</button>' +
    '<button class="gob-btn gob-btn--gate" id="hb-gate">Advance</button>' +
    '<button class="gob-btn gob-btn--neutral" id="hb-neutral">Got It</button>' +
    '<button class="gob-btn gob-btn--ghost" id="hb-ghost">Dismiss</button>' +
    '<button class="gob-btn gob-btn--action" id="hb-disabled" disabled>Disabled</button>' +
    '<button class="gob-btn gob-btn--gate gob-btn--lg" id="hb-lg">Set Lineup</button>' +
    '<a class="gob-btn gob-btn--ghost gob-btn--lg" id="hb-link" href="#">Link</a>' +
  '</div>';

async function buttonPaint(page) {
  return page.evaluate(() => {
    const out = {};
    ['default', 'action', 'gate', 'neutral', 'ghost', 'disabled', 'lg', 'link'].forEach((key) => {
      const s = getComputedStyle(document.getElementById('hb-' + key));
      out[key] = {
        bg: s.backgroundColor, color: s.color, border: s.borderTopColor, shadow: s.boxShadow,
        family: s.fontFamily, size: s.fontSize, weight: s.fontWeight, tracking: s.letterSpacing, lh: s.lineHeight,
        radius: s.borderTopLeftRadius, padL: s.paddingLeft, h: s.height, minW: s.minWidth, opacity: s.opacity,
      };
    });
    return out;
  });
}

// sizes: false on a host page whose own button rules resize the text (the FCC does).
function expectButtons(got, where, sizes) {
  const d = got.default;
  expect(d.bg, where).toBe('rgba(0, 0, 0, 0)');
  expect(d.color, where).toBe('rgb(255, 255, 255)');
  expect(d.border, where).toBe('rgba(255, 255, 255, 0.28)');
  expect(d.shadow, where).toContain('rgba(255, 255, 255, 0.18)');
  expect(d.family, where).toMatch(/Bebas Neue Pro/);
  expect(d.weight, where).toBe('700');
  if (sizes !== false) {
    expect(d.size, where).toBe('16px');
    expect(d.tracking, where).toBe('0.96px');
  }
  expect(d.radius, where).toBe('10px');
  expect(d.padL, where).toBe('18px');
  expect(d.h, where).toBe('42px');
  expect(d.minW, where).toBe('138px');
  expect(got.action.bg, where).toBe('rgb(247, 148, 32)');
  expect(got.action.border, where).toMatch(ORANGE_55);
  expect(got.action.color, where).toBe('rgb(21, 24, 31)');
  expect(got.gate.bg, where).toBe('rgb(52, 236, 39)');
  expect(got.gate.border, where).toMatch(GREEN_55);
  expect(got.neutral.bg, where).toBe('rgba(255, 255, 255, 0.9)');
  expect(got.neutral.color, where).toBe('rgb(11, 13, 20)');
  expect(got.ghost.bg, where).toBe('rgba(255, 255, 255, 0.06)');
  expect(got.ghost.border, where).toBe('rgba(255, 255, 255, 0.18)');
  expect(got.ghost.color, where).toBe('rgba(255, 255, 255, 0.85)');
  expect(got.disabled.opacity, where).toBe('0.5');
  if (sizes !== false) {
    expect(got.lg.size, where).toBe('19px');
    expect(got.lg.tracking, where).toBe('1.52px');
  }
  expect(got.lg.h, where).toBe('50px');
}

test.describe('token hygiene: nothing looks different', () => {
  test('Set Lineup: RT classes paint the same colours through the tier tokens', async ({ page, request }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await waitForCanonicalRosters(request);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/static/set-lineup.html?home=Lancaster&away=Four-Corners&my_team=home');
    await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
    await page.locator('#autoset-lineup').click();
    await page.waitForSelector('.roster-table tbody tr.on-court', { timeout: 15000 });
    await page.waitForTimeout(4500);
    await page.mouse.move(640, 705);
    if (captureShots) await shot(page, 'set-lineup-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(() => {
      const host = document.createElement('div');
      host.innerHTML = ['low', 'mid', 'high', 'elite', 'unknown'].map((k) => '<span class="rt-' + k + '" id="hy-' + k + '">X</span>').join('');
      document.body.appendChild(host);
      const out = {};
      ['low', 'mid', 'high', 'elite', 'unknown'].forEach((k) => { out[k] = getComputedStyle(document.getElementById('hy-' + k)).color; });
      host.remove();
      const root = document.documentElement;
      out.inline = ['low', 'mid', 'high', 'elite'].map((k) => root.style.getPropertyValue('--rt-' + k + '-color'));
      out.real = [...document.querySelectorAll('.roster-table td.rt')].slice(0, 12).map((td) => getComputedStyle(td).color);
      out.getter = [window.getRtColor(95), window.getRtColor(65), window.getRtColor(45), window.getRtColor(10)];
      return out;
    });
    expect(got.low).toBe(RT.low);
    expect(got.mid).toBe(RT.mid);
    expect(got.high).toBe(RT.high);
    expect(got.elite).toBe(RT.elite);
    expect(got.unknown).toBe(RT.unknown);
    // The page variable now names a token; the old literal is only the fallback.
    expect(got.inline[0]).toMatch(/var\(--tier-red/);
    expect(got.inline[1]).toMatch(/var\(--tier-yellow/);
    expect(got.inline[2]).toMatch(/var\(--tier-green/);
    expect(got.inline[3]).toMatch(/var\(--blue/);
    expect(got.real.length).toBeGreaterThan(5);
    for (const colour of got.real) expect(Object.values(RT)).toContain(colour);
    // Scripts that need a concrete colour (canvas, inline bars) still get one.
    expect(got.getter.map((c) => c.toLowerCase())).toEqual(['#4a90d9', '#34ec27', '#ffd700', '#ff6d6d']);
  });

  test('Recruiting hub: the "yours" aliases are tokens and paint the same', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await page.setViewportSize({ width: 1280, height: 720 });
    await openHub(page, 7);
    await page.waitForSelector('#hub-pool');
    await page.waitForSelector('#hub-pool tbody tr.rec');
    await page.mouse.move(700, 715);
    await page.waitForTimeout(600);
    if (captureShots) await shot(page, 'hub-pool-1280.png');
    const leans = page.getByRole('tab', { name: 'Leans', exact: true });
    if (await leans.count()) await leans.click();
    await page.waitForSelector('#hub-pool tbody tr.rec .lb-slot.is-you');
    await page.mouse.move(700, 715);
    await page.waitForTimeout(600);
    if (captureShots) await shot(page, 'hub-leans-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      const slot = getComputedStyle(document.querySelector('.lb-slot.is-you'));
      const tok = getComputedStyle(document.querySelector('.lb-slot.is-you .lb-tok'));
      const rk = getComputedStyle(document.querySelector('.lb-slot.is-you .rk'));
      // Where is each alias declared? Walk the sheets.
      const where = {};
      for (const sheet of Array.from(document.styleSheets)) {
        let rules = [];
        try { rules = Array.from(sheet.cssRules || []); } catch (err) { continue; }
        const file = (sheet.href || '').split('/').pop().split('?')[0];
        for (const rule of rules) {
          if (!rule.style) continue;
          ['--you', '--you-soft', '--you-line', '--you-ink', '--you-edge'].forEach((name) => {
            if (rule.style.getPropertyValue(name) && (where[name] = where[name] || []).indexOf(file) === -1) where[name].push(file);
          });
        }
      }
      return {
        you: root.getPropertyValue('--you').trim(), soft: root.getPropertyValue('--you-soft').trim(),
        line: root.getPropertyValue('--you-line').trim(), ink: root.getPropertyValue('--you-ink').trim(),
        listSoft: root.getPropertyValue('--list-soft').trim(),
        slotBg: slot.backgroundColor, tokBg: tok.backgroundColor, rk: rk.color, where: where,
      };
    });
    for (const value of [got.you, got.soft, got.line, got.ink, got.listSoft]) expect(value).not.toBe('');
    expect(got.where['--you']).toEqual(['gob-tokens.css']);
    expect(got.where['--you-soft']).toEqual(['gob-tokens.css']);
    expect(got.where['--you-line']).toEqual(['gob-tokens.css']);
    expect(got.where['--you-ink']).toEqual(['gob-tokens.css']);
    expect(got.slotBg).toMatch(NAVY_28);
    expect(got.tokBg).toBe('rgb(39, 64, 142)');
    expect(got.rk).toMatch(/srgb 0\.84\d* 0\.86\d* 0\.92\d*|rgb\(216, 221, 235\)/);
  });

  test('Roster: RT letters keep their colours; position tokens equal the script values', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApi(page);
    await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    await page.mouse.move(700, 715);
    if (captureShots) await shot(page, 'roster-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(async () => {
      const root = getComputedStyle(document.documentElement);
      const mod = await import('/js/phaser/utils/matchupsUiShared.js');
      const pos = {};
      ['PG', 'SG', 'SF', 'PF', 'C'].forEach((p) => { pos[p] = [root.getPropertyValue('--pos-' + p.toLowerCase()).trim().toLowerCase(), String(mod.POSITION_COLORS[p]).toLowerCase()]; });
      const rt = [...document.querySelectorAll('#roster-view [class*="rt-"]')].filter((el) => /\brt-(low|mid|high|elite|unknown)\b/.test(el.className)).slice(0, 30).map((el) => getComputedStyle(el).color);
      return {
        pos: pos, rt: rt,
        tiers: ['--tier-red', '--tier-yellow', '--tier-green', '--blue'].map((n) => root.getPropertyValue(n).trim().toLowerCase()),
      };
    });
    for (const p of Object.keys(got.pos)) {
      expect(got.pos[p][0], '--pos-' + p).not.toBe('');
      expect(got.pos[p][0], '--pos-' + p).toBe(got.pos[p][1]);
    }
    expect(got.tiers).toEqual(['#ff6d6d', '#ffd700', '#34ec27', '#4a90d9']);
    expect(got.rt.length).toBeGreaterThan(5);
    for (const colour of got.rt) expect(Object.values(RT)).toContain(colour);
  });

  test('Buttons on a token page: every variant paints the same', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApi(page);
    await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    // Forced: every variant of the canonical button on one panel, on a real token page.
    await page.addStyleTag({ url: '/css/gob-buttons.css' });
    await page.evaluate((html) => {
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:120px;top:120px;z-index:99999;background:#0b0d14;border:1px solid rgba(255,255,255,.14);border-radius:12px';
      host.innerHTML = html;
      document.body.appendChild(host);
    }, BUTTONS_HTML);
    await page.waitForTimeout(500);
    await page.mouse.move(1200, 700);
    if (captureShots) await shot(page, 'buttons-token-page-1280.png');
    await page.hover('#hb-action');
    await page.waitForTimeout(300);
    const hoverAction = await page.evaluate(() => getComputedStyle(document.getElementById('hb-action')).backgroundColor);
    await page.hover('#hb-ghost');
    await page.waitForTimeout(300);
    const hoverGhost = await page.evaluate(() => { const s = getComputedStyle(document.getElementById('hb-ghost')); return [s.backgroundColor, s.borderTopColor, s.color]; });
    if (captureShots) await shot(page, 'buttons-hover-ghost-1280.png');
    if (BEFORE) return;
    await page.mouse.move(1200, 700);
    await page.waitForTimeout(400);
    expectButtons(await buttonPaint(page), 'token page', false);
    expect(hoverAction).toBe('rgb(255, 168, 74)');
    expect(hoverGhost).toEqual(['rgba(255, 255, 255, 0.11)', 'rgba(255, 255, 255, 0.3)', 'rgb(255, 255, 255)']);
  });

  test('Buttons with no tokens on the page: the fallbacks paint the same', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await page.setViewportSize({ width: 1280, height: 720 });
    const css = fs.readFileSync(path.join(STATIC_DIR, 'css/gob-buttons.css'), 'utf8');
    await page.setContent('<style>body{margin:0;background:#0b0d14;font-family:sans-serif}' + css + '</style>' + BUTTONS_HTML);
    await page.waitForTimeout(300);
    if (captureShots) await shot(page, 'buttons-no-tokens-1280.png');
    if (BEFORE) return;
    const got = await buttonPaint(page);
    // No Bebas on a bare page: the family is still requested first.
    expectButtons(got, 'bare page');
    const hasTokens = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--white-28').trim());
    expect(hasTokens).toBe('');
  });
});
