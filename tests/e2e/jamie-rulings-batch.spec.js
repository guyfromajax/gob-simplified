const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { waitForCanonicalRosters } = require('./helpers/rosters');

/**
 * Jamie's rulings, 2026-10-01 (reports/jamie-decisions-2026-10-01.md):
 *   #1  things you picked are navy with a navy-hi edge (Set Lineup, Playbooks, lean ladder, bracket)
 *   #6  senior-tribute title marks are reward gold
 *   #7  the recruiting presence dot is neutral
 *   #8  the big-news modal button is a neutral CTA
 *   #10 homepage-v3.html and play-builder.html (v1) are gone; the v1 path redirects to v2
 *
 * RULINGS_SHOTS=before writes before-*.png and skips the guards: run it on develop for
 * the BEFORE set. The default run writes after-*.png and asserts computed styles.
 */
test.describe.configure({ timeout: 120000 });

const BEFORE = process.env.RULINGS_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/jamie-rulings-batch');
const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const RIVAL = 'Four-Corners';

// Chrome reports a color-mix() result as color(srgb r g b / a); a plain token as rgb().
const NAVY = /39,\s*64,\s*142|srgb 0\.15\d* 0\.25\d* 0\.55\d*/;
const NAVY_HI = /74,\s*110,\s*210|srgb 0\.29\d* 0\.43\d* 0\.82\d*/;
const ORANGE = /247,\s*148,\s*32|srgb 0\.96\d* 0\.58\d* 0\.12\d*/;
const GREEN = /52,\s*236,\s*39|43,\s*214,\s*106|srgb 0\.16\d* 0\.83\d* 0\.41\d*|srgb 0\.20\d* 0\.92\d* 0\.15\d*/;
const GOLD = /240,\s*197,\s*96|212,\s*168,\s*72|srgb 0\.94\d* 0\.77\d* 0\.37\d*|srgb 0\.83\d* 0\.65\d* 0\.28\d*/;

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

async function fccPage(page, wire) {
  await stubAuth(page);
  await installApi(page, wire);
  await page.addInitScript(() => { try { localStorage.setItem('gob-office-seen-result', 'g1'); } catch (err) { /* ignore */ } });
  await page.setViewportSize({ width: 1280, height: 720 });
}

test.describe('Jamie rulings batch', () => {
  test('#1 Set Lineup: on-court rows are navy with a navy-hi edge', async ({ page, request }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await waitForCanonicalRosters(request);
    for (const size of [[1280, 720], [1920, 1080]]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.goto('/static/set-lineup.html?home=' + TEAM + '&away=' + RIVAL + '&my_team=home');
      await page.locator('#play-now').filter({ hasText: 'Play Game' }).waitFor({ timeout: 20000 });
      await page.locator('#autoset-lineup').click();
      await page.waitForSelector('.roster-table tbody tr.on-court', { timeout: 15000 });
      // Let the "Lineup auto-generated!" toast leave so both sets show the same frame.
      await page.waitForTimeout(4500);
      await page.mouse.move(640, 705);
      if (captureShots) await shot(page, 'set-lineup-' + size[0] + '.png');
      if (BEFORE) continue;
      const got = await page.evaluate(() => {
        const pane = [...document.querySelectorAll('.roster-roster-pane')].find((p) => !p.hidden && p.offsetParent !== null) || document;
        const on = pane.querySelector('tbody tr.on-court');
        const bench = pane.querySelector('tbody tr.bench') || [...pane.querySelectorAll('tbody tr')].find((tr) => !tr.classList.contains('on-court') && tr.querySelector('td.rt'));
        const first = on.querySelector('td');
        const second = on.querySelectorAll('td')[1];
        return {
          rows: pane.querySelectorAll('tbody tr.on-court').length,
          bg: getComputedStyle(second).backgroundColor,
          edge: getComputedStyle(first).boxShadow,
          benchBg: bench ? getComputedStyle(bench.querySelectorAll('td')[1]).backgroundColor : '',
          benchEdge: bench ? getComputedStyle(bench.querySelector('td')).boxShadow : '',
          toggle: getComputedStyle(document.querySelector('#roster-view-game')).backgroundColor,
        };
      });
      expect(got.rows).toBe(5);
      expect(got.bg, 'on-court tint').toMatch(NAVY);
      expect(got.edge, 'on-court edge').toMatch(NAVY_HI);
      expect(got.benchBg, 'bench is not navy').not.toMatch(NAVY);
      expect(got.benchEdge, 'bench has no navy edge').not.toMatch(NAVY_HI);
      // A choice control stays neutral: the view toggle is not navy.
      expect(got.toggle).not.toMatch(NAVY);
    }
  });

  test('#1 Playbooks: plays in your Playcall Center are navy', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await fccPage(page);
    await openFcc(page, 'playbooks-view', '#playbooks-view .play');
    await page.waitForSelector('#playbooks-view .play.on', { timeout: 15000 });
    await page.mouse.move(700, 715);
    if (captureShots) await shot(page, 'playbooks-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(() => {
      const host = document.getElementById('playbooks-view');
      const css = (el) => {
        if (!el) return null;
        const s = getComputedStyle(el);
        return { bg: s.backgroundColor, shadow: s.boxShadow };
      };
      return {
        picked: css(host.querySelector('.play.on')),
        notPicked: css(host.querySelector('.play:not(.on)')),
        sheetRow: css(host.querySelector('.csr')),
        slot: css(host.querySelector('.play.on .slot:not(.add):not(.lk)')),
        tab: css(host.querySelector('.playbooks-tab.on')),
        lock: css(host.querySelector('.wl.on')),
      };
    });
    expect(got.picked.bg, 'picked play').toMatch(NAVY);
    expect(got.picked.shadow, 'picked play edge').toMatch(NAVY_HI);
    expect(got.notPicked.bg, 'other plays stay untinted').not.toMatch(NAVY);
    if (got.sheetRow) {
      expect(got.sheetRow.bg, 'call sheet row').toMatch(NAVY);
      expect(got.sheetRow.shadow, 'call sheet edge').toMatch(NAVY_HI);
    }
    if (got.slot) expect(got.slot.shadow, 'slot ring').toMatch(NAVY_HI);
    // Choice controls stay neutral.
    if (got.tab) expect(got.tab.bg, 'Offense / Defense tab').not.toMatch(NAVY);
    if (got.lock) expect(got.lock.bg, 'weight lock').not.toMatch(NAVY);
  });

  test('#1 lean ladder: your slot is navy from the tokens', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await fccPage(page);
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    // Forced markup: the classes RecruitingSpine.Lean.ladderHtml() emits, enlarged 3x so
    // the slot is legible in a full-page shot. No recruit in the fixture week has a ladder.
    await page.evaluate(() => {
      const host = document.createElement('div');
      host.id = 'rulings-ladder';
      host.style.cssText = 'position:fixed;left:140px;top:150px;z-index:99999;padding:24px 28px;background:var(--surface-2);border:1px solid var(--line-strong);border-radius:12px;transform:scale(3);transform-origin:top left;';
      host.innerHTML =
        '<div class="lean-b">' +
          '<div class="lb-slot is-you" id="rl-you"><span class="rk">1</span><span class="lb-tok">LAN</span></div>' +
          '<div class="lb-slot" id="rl-other"><span class="rk">2</span><span class="lb-tok">FCO</span></div>' +
          '<div class="lb-slot is-you-list" id="rl-list"><span class="rk">3</span><span class="lb-tok">LAN</span></div>' +
          '<div class="lb-slot is-open"><span class="rk">4</span><span class="lb-tok">open</span></div>' +
        '</div>' +
        '<div style="margin-top:10px;font:500 11px Inter,sans-serif;color:#fff">' +
          '<span class="recruit-stand-dot you1" id="rl-dot"></span>Miles Hart<span class="recruit-stand-chip you1" id="rl-chip">#1</span>' +
          '<span class="recruit-stand-chip list" id="rl-chip-list" style="margin-left:10px">LIST</span>' +
        '</div>';
      document.body.appendChild(host);
    });
    if (captureShots) await shot(page, 'lean-ladder-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(() => {
      const css = (id, sel) => {
        let el = document.getElementById(id);
        if (sel) el = el.querySelector(sel);
        const s = getComputedStyle(el);
        return { bg: s.backgroundColor, border: s.borderTopColor, shadow: s.boxShadow, color: s.color };
      };
      return {
        you: css('rl-you'), youTok: css('rl-you', '.lb-tok'), list: css('rl-list'), listTok: css('rl-list', '.lb-tok'),
        other: css('rl-other'), otherTok: css('rl-other', '.lb-tok'), dot: css('rl-dot'), chip: css('rl-chip'), chipList: css('rl-chip-list'),
        navy: getComputedStyle(document.documentElement).getPropertyValue('--navy').trim(),
      };
    });
    expect(got.navy).not.toBe('');
    expect(got.you.bg).toMatch(NAVY);
    expect(got.you.border).toMatch(NAVY_HI);
    expect(got.you.shadow).toMatch(NAVY_HI);
    expect(got.youTok.bg).toBe('rgb(39, 64, 142)');
    expect(got.list.bg).toMatch(NAVY);
    expect(got.list.border).toMatch(NAVY_HI);
    expect(got.listTok.bg).toBe('rgb(39, 64, 142)');
    expect(got.dot.bg).toBe('rgb(39, 64, 142)');
    expect(got.chip.bg).toMatch(NAVY);
    expect(got.chip.border).toMatch(NAVY_HI);
    expect(got.chipList.border).toMatch(NAVY_HI);
    expect(got.other.bg).not.toMatch(NAVY);
    expect(got.otherTok.bg).not.toMatch(NAVY);
  });

  test('#1 bracket and #8 big-news button: your team navy, CTA neutral, emblem still gold', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await fccPage(page);
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    await page.waitForFunction(() => window.BigNewsModals && typeof window.BigNewsModals.showBracketUpdate === 'function' && typeof FccTournamentStyleA !== 'undefined');
    await page.evaluate(({ me, opp }) => {
      const game = (home, away, winner, hs, as, id) => ({ home_team: home, away_team: away, winner: winner, game_id: id, score: { home: hs, away: as } });
      const payload = {
        eligible: true,
        update_key: 'rulings-batch',
        tier: 'conference',
        layout: 'full',
        display_week: 28,
        eyebrow: 'Conference A1',
        bracket: {
          round1: [game(me, opp, me, 72, 65, 'g1'), game(opp, me, opp, 68, 60, 'g2'), game(me, opp, me, 75, 60, 'g3'), game(opp, me, me, 55, 62, 'g4')],
          round2: [game(me, opp, null, null, null, 'g5')],
          final: [],
        },
        seeds: { [me]: 3, [opp]: 6 },
      };
      const names = { [me]: 'Lancaster', [opp]: 'Four Corners' };
      window.BigNewsModals.showBracketUpdate(payload, { team_id: me, week: 28, team_name_map: names }, { userTeamId: me, teamIdToNameMap: names });
    }, { me: 'aaaaaaaaaaaaaaaaaaaaaaaa', opp: 'bbbbbbbbbbbbbbbbbbbbbbbb' });
    await page.waitForSelector('.bn-overlay.show .bn-cta', { timeout: 15000 });
    await page.waitForSelector('.bn-overlay .fcc-tb-team--user', { timeout: 15000 });
    await page.waitForTimeout(1200);
    if (captureShots) await shot(page, 'big-news-bracket-1280.png');
    if (BEFORE) return;
    const got = await page.evaluate(() => {
      const root = document.querySelector('.bn-overlay.show');
      const css = (sel) => {
        const el = root.querySelector(sel);
        if (!el) return null;
        const s = getComputedStyle(el);
        return { bg: s.backgroundColor, bgImage: s.backgroundImage, border: s.borderTopColor, left: s.borderLeftColor, shadow: s.boxShadow, color: s.color, filter: s.filter };
      };
      return {
        cta: css('.bn-cta'), eyebrow: css('.bn-eyebrow'), emblem: css('.bn-emblem'),
        team: css('.fcc-tb-team--user'), mu: css('.fcc-tb-mu--user'), seed: css('.fcc-tb-team--user .fcc-tb-seed'),
        other: css('.fcc-tb-team:not(.fcc-tb-team--user)'),
      };
    });
    // #8: the button is a neutral plate. No gold in fill, gradient, border or glow.
    expect(got.cta.bgImage).toBe('none');
    for (const part of [got.cta.bg, got.cta.border, got.cta.shadow]) {
      expect(part).not.toMatch(GOLD);
      expect(part).not.toMatch(GREEN);
      expect(part).not.toMatch(ORANGE);
    }
    expect(got.cta.color).toBe('rgb(255, 255, 255)');
    // The gold title art stays.
    expect(got.eyebrow.color).toMatch(GOLD);
    expect(got.emblem.filter).toMatch(GOLD);
    // #1: your team in the bracket is navy, never green.
    expect(got.team.left).toMatch(NAVY);
    expect(got.team.bgImage).toMatch(NAVY);
    expect(got.mu.border + ' ' + got.mu.shadow).toMatch(NAVY_HI);
    for (const part of [got.team.left, got.team.bgImage, got.mu.border, got.mu.shadow, got.seed.color]) {
      expect(part).not.toMatch(GREEN);
    }
    expect(got.other.bgImage).not.toMatch(NAVY);
  });

  test('#6 senior tribute: title marks are reward gold', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await fccPage(page);
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    await page.waitForFunction(() => window.SeniorTribute && typeof window.SeniorTribute.start === 'function');
    await page.evaluate(() => {
      window.SeniorTribute.start({
        season: 4,
        teamColor: '#27408E',
        players: [{
          player_id: 'p-jalen', first_name: 'Jalen', last_name: 'Carter', name: 'Jalen Carter', jersey: 5, position: 'PG',
          games_played: 118, career_points: 1642, titles: { conf_rs: 2, conf_t: 1, region: 1 },
        }],
      });
    });
    await page.waitForSelector('#senior-tribute .st-titles s', { timeout: 15000 });
    await page.waitForTimeout(1500);
    if (captureShots) await shot(page, 'senior-tribute-1280.png');
    const marks = await page.evaluate(() => {
      const el = document.querySelector('#senior-tribute .st-titles s');
      const adv = document.querySelector('#senior-tribute .st-advance');
      return {
        mark: getComputedStyle(el).backgroundColor,
        count: document.querySelectorAll('#senior-tribute .st-titles s').length,
        gold: getComputedStyle(document.documentElement).getPropertyValue('--reward-gold').trim(),
        advance: adv ? getComputedStyle(adv).backgroundImage : '',
      };
    });
    await page.evaluate(() => window.SeniorTribute.teardown());
    if (BEFORE) return;
    expect(marks.count).toBe(3);
    expect(marks.gold.toLowerCase()).toBe('#f0c560');
    expect(marks.mark).toBe('rgb(240, 197, 96)');
  });

  test('#7 recruiting presence dot is neutral', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    // Unseen wire events with nothing pending: the tab carries .inbox-badge, not a count.
    await fccPage(page, { board_saved_week: 0, has_saved_board: false, counts: { moved: 2, dropped: 1 }, pending_count: 0, urgent: false, unseen_count: 3 });
    await openFcc(page, 'roster-view', '#roster-view table tbody tr');
    await page.waitForSelector('.inbox-badge', { state: 'attached', timeout: 15000 });
    await page.mouse.move(700, 715);
    if (captureShots) await shot(page, 'presence-dot-1280.png');
    if (BEFORE) return;
    const dot = await page.evaluate(() => {
      const s = getComputedStyle(document.querySelector('.inbox-badge'));
      return { bg: s.backgroundColor, shadow: s.boxShadow, w: s.width, h: s.height, display: s.display };
    });
    expect(dot.bg).toBe('rgb(255, 255, 255)');
    for (const part of [dot.bg, dot.shadow]) {
      expect(part).not.toMatch(ORANGE);
      expect(part).not.toMatch(GREEN);
    }
    expect(dot.w).toBe('8px');
    expect(dot.display).not.toBe('none');
  });

  test('#10 the v1 play builder path lands on v2; homepage-v3 is gone', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/play-builder.html');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);
    if (captureShots) await shot(page, 'play-builder-v1-path-1280.png');
    if (!BEFORE) {
      expect(new URL(page.url()).pathname).toBe('/play-builder-v2.html');
      expect(fs.existsSync(path.join(__dirname, '../../FrontEnd/static/play-builder.html'))).toBe(false);
      expect(fs.existsSync(path.join(__dirname, '../../FrontEnd/static/play-builder-v2.html'))).toBe(true);
    }
    const res = await page.goto('/static/homepage-v3.html');
    await page.waitForTimeout(800);
    if (captureShots) await shot(page, 'homepage-v3-path-1280.png');
    if (!BEFORE) {
      expect(res.status()).toBe(404);
      expect(fs.existsSync(path.join(__dirname, '../../FrontEnd/static/homepage-v3.html'))).toBe(false);
    }
    const home = await page.goto('/static/homepage.html');
    expect(home.status()).toBe(200);
    await expect(page.locator('img.hero-logo')).toBeVisible();
    if (captureShots) await shot(page, 'homepage-1280.png');
  });
});
