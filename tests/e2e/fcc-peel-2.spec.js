const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * FCC peel 2: dead franchise-command-center.css rules removed, remaining colour-law
 * hits neutralised. Office, Team, League and Prep must look the same.
 *
 * FCC_SHOTS=before writes before-*.png and skips the guards: run it on develop for
 * the BEFORE set. The default run writes after-*.png and asserts computed styles.
 */
const BEFORE = process.env.FCC_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/fcc-peel-2');
const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const SIZES = [[1280, 720, '1280'], [1920, 1080, '1920']];
const GREEN_RGB = 'rgb(52, 236, 39)';
const ORANGE_RGB = 'rgb(247, 148, 32)';

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

const VIEWS = [
  ['office', 'home-tab', '#office-root, .office'],
  ['team', 'roster-view', '#roster-view table tbody tr'],
  ['league', 'standings-view', '#standings-view table tbody tr'],
  ['prep', 'training-view', '#training-view .pdg-row, #training-view .pdg, #training-view table'],
];

async function open(page, tab, ready) {
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, mode: 'franchise', tab: tab, from: 'command_center' });
  await page.goto('/franchise-command-center.html?' + q.toString());
  await page.waitForSelector('html.gob-shell .top', { timeout: 30000 });
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready, { timeout: 30000 });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  // A headshot that lands after the shot changes the row height, so wait for every image.
  await page.waitForFunction(() => Array.from(document.images).every((img) => img.complete), null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.querySelector('html.gob-shell .main');
    if (main) main.scrollTop = 0;
  });
  await page.mouse.move(700, 715);
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name), animations: 'disabled' });
}

async function paint(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return { color: s.color, bg: s.backgroundColor, bgImage: s.backgroundImage, shadow: s.boxShadow, outline: s.outlineColor, display: s.display };
  }, selector);
}

test.describe('FCC peel 2', () => {
  test('Office, Team, League and Prep render with the peeled sheet', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApi(page);
    // The weekly-card entrance plays once per result; mark it seen so every load is the settled card.
    await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      for (const view of VIEWS) {
        await open(page, view[1], view[2]);
        if (captureShots) await shot(page, view[0] + '-' + size[2] + '.png');
        if (BEFORE) continue;

        // The one Advance is still the shell's green button.
        const advance = await paint(page, '#play-now');
        expect(advance, 'Advance missing on ' + view[0]).not.toBeNull();
        expect(advance.bg).toBe(GREEN_RGB);

        // No dead panel rule was holding a live view up: the view has real height.
        const box = await page.evaluate((id) => {
          const el = document.getElementById(id);
          const r = el ? el.getBoundingClientRect() : null;
          return r ? { w: Math.round(r.width), h: Math.round(r.height) } : null;
        }, view[1] === 'home-tab' ? 'office-root' : view[1]);
        expect(box, view[0] + ' root missing').not.toBeNull();
        expect(box.w).toBeGreaterThan(600);
        expect(box.h).toBeGreaterThan(200);
      }
    }
  });

  // Ruling 2026-10-01 (#7): the presence dot is neutral. It was orange through --badge.
  test('recruiting presence dot is neutral', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    // Unseen wire events with nothing pending: the tab carries .inbox-badge, not a count.
    await installApi(page, { board_saved_week: 0, has_saved_board: false, counts: { moved: 2, dropped: 1 }, pending_count: 0, urgent: false, unseen_count: 3 });
    await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });
    await page.setViewportSize({ width: 1280, height: 720 });
    await open(page, 'roster-view', '#roster-view table tbody tr');
    await page.waitForSelector('.inbox-badge', { state: 'attached', timeout: 15000 });
    if (captureShots) await shot(page, 'presence-dot-1280.png');
    if (BEFORE) return;
    const badge = await paint(page, '.inbox-badge');
    expect(badge.bg).toBe('rgb(255, 255, 255)');
    expect(badge.bg).not.toBe(ORANGE_RGB);
    expect(badge.shadow).not.toMatch(/247,\s*148,\s*32|srgb 0\.96\d* 0\.58\d* 0\.12/);
  });

  test('neutralised pieces carry no green or orange', async ({ page }) => {
    test.skip(BEFORE, 'guards only');
    await stubAuth(page);
    await installApi(page);
    await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });
    await page.setViewportSize({ width: 1280, height: 720 });
    await open(page, 'roster-view', '#roster-view table tbody tr');

    // Forced markup: none of these states is on screen in the fixture week, so the
    // elements are built by hand with the classes the real renderers emit.
    const got = await page.evaluate(() => {
      const css = (el, pseudo) => {
        const s = getComputedStyle(el, pseudo || null);
        return { color: s.color, bg: s.backgroundColor, border: s.borderTopColor, outline: s.outlineColor, radius: s.borderTopLeftRadius };
      };
      const host = document.createElement('div');
      host.innerHTML =
        '<span class="fcc-newlean-badge">New</span>' +
        '<button type="button" class="attr-abbr is-sorted">SH</button>' +
        '<div class="lean-b">' +
          '<div class="lb-slot" id="peel-slot"><span class="rk">1</span><span class="lb-tok">LAN</span><span class="lb-lock"></span></div>' +
          '<div class="lb-slot is-you" id="peel-you"><span class="rk">2</span><span class="lb-tok">YOU</span></div>' +
        '</div>' +
        '<div class="st-host" style="position:static"><div class="st-titles"><span><s id="peel-title"></s>Title</span></div><div class="st-cti"><s id="peel-cti"></s></div></div>';
      document.body.appendChild(host);
      const out = {
        newlean: css(host.querySelector('.fcc-newlean-badge')),
        sortArrow: css(host.querySelector('.attr-abbr'), '::after'),
        sortLabel: css(host.querySelector('.attr-abbr')),
        slot: css(host.querySelector('#peel-slot')),
        tok: css(host.querySelector('#peel-slot .lb-tok')),
        lock: css(host.querySelector('#peel-slot .lb-lock')),
        you: css(host.querySelector('#peel-you')),
        youTok: css(host.querySelector('#peel-you .lb-tok')),
        title: css(host.querySelector('#peel-title')),
        cti: css(host.querySelector('#peel-cti')),
      };
      // Focus rings: read the declared outline, since :focus-visible needs a real key press.
      const rings = {};
      for (const sheet of Array.from(document.styleSheets)) {
        let rules = [];
        try { rules = Array.from(sheet.cssRules || []); } catch (err) { continue; }
        for (const rule of rules) {
          const sel = rule.selectorText || '';
          if (sel === '.attr-abbr:focus-visible' || sel === '.scope-btn:focus-visible' || sel === '.seg-track button:focus-visible' || sel.indexOf('.recruit-name-link:focus-visible') !== -1) {
            rings[sel] = rule.style.outlineColor || rule.style.outline;
          }
        }
      }
      out.rings = rings;
      host.remove();
      return out;
    });

    const ORANGE = /247,\s*148,\s*32/;
    const GREENISH = /52,\s*(199|236),\s*(122|39)|43,\s*214,\s*106/;
    expect(got.newlean.bg).toBe('rgb(255, 255, 255)');
    expect(got.newlean.bg).not.toMatch(GREENISH);
    expect(got.sortArrow.color).toBe(got.sortLabel.color);
    expect(got.sortArrow.color).not.toMatch(ORANGE);
    expect(got.title.bg).not.toMatch(ORANGE);
    expect(got.cti.bg).not.toMatch(ORANGE);
    // Ruling 2026-10-01 (#6): title marks are reward gold.
    expect(got.title.bg).toBe('rgb(240, 197, 96)');
    expect(Object.keys(got.rings).length).toBeGreaterThanOrEqual(4);
    for (const sel of Object.keys(got.rings)) {
      expect(got.rings[sel], sel).not.toMatch(/247,\s*148,\s*32|#f79420|34c77a|52,\s*199,\s*122/i);
    }
    // Lean ladder: tokens resolve to the literals they replaced.
    expect(got.slot.bg).toBe('rgba(255, 255, 255, 0.03)');
    expect(got.slot.border).toBe('rgba(255, 255, 255, 0.06)');
    expect(got.slot.radius).toBe('8px');
    expect(got.tok.color).toBe('rgba(255, 255, 255, 0.62)');
    expect(got.tok.bg).toBe('rgba(255, 255, 255, 0.06)');
    expect(got.lock.color).toBe('rgb(255, 109, 109)');
    // Ruling 2026-10-01 (#1): "yours" is --navy from the tokens (28% tint, solid chip).
    expect(got.you.bg).toMatch(/rgba\(39, 64, 142, 0\.28\)|srgb 0\.15\d* 0\.25\d* 0\.55\d* \/ 0\.28/);
    expect(got.youTok.bg).toBe('rgb(39, 64, 142)');
  });

  test('franchise-gone notice: neutral button, tokens resolve', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await page.route('**/*', async (route) => {
      let pathname = '';
      try { pathname = new URL(route.request().url()).pathname; } catch (err) { await route.continue(); return; }
      if (pathname === '/franchise/command-center/data') {
        await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Franchise not found' }) });
        return;
      }
      if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/') || pathname === '/teams') {
        return fulfillJson(route, {});
      }
      await route.continue();
    });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TEAM);
    await page.waitForSelector('#fcc-franchise-gone-back', { timeout: 30000 });
    await page.waitForTimeout(400);
    if (captureShots) await shot(page, 'franchise-gone-1280.png');
    if (BEFORE) return;
    const btn = await paint(page, '#fcc-franchise-gone-back');
    expect(btn.bg).toBe('rgba(255, 255, 255, 0.1)');
    expect(btn.bgImage).toBe('none');
    expect(btn.color).toBe('rgb(255, 255, 255)');
    const panel = await paint(page, '#fcc-franchise-gone');
    expect(panel.bg).toBe('rgb(11, 13, 20)');
    const title = await paint(page, '#fcc-franchise-gone > div');
    expect(title.color).toBe('rgb(255, 255, 255)');
  });
});
