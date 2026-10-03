// @ts-check
/**
 * Office (FCC home tab) fixtures: a command-center payload per digest state and
 * the API mock that serves it. Shared by specs that only need a believable
 * Office to stand on; office-frontend.spec.js keeps its own copy.
 */
const { stubAuth } = require('./auth');

const FID = 'f-e2e-office';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function resultBlock(overrides) {
  return Object.assign({
    week: 21,
    home_team_id: TID,
    away_team_id: 'bbbbbbbbbbbbbbbbbbbbbbbb',
    home_team_name: 'Amariabi International',
    away_team_name: 'Long Island Methodist',
    home_score: 71,
    away_score: 64,
    user_is_home: true,
    site: 'home',
    neutral: null,
    opponent_team_id: 'bbbbbbbbbbbbbbbbbbbbbbbb',
    opponent_team_name: 'Long Island Methodist',
    opponent_rank: 9,
    round_name: null,
    user_won: true,
    leader_role: 'potg',
    leader: {
      player_id: 'p-jalen',
      name: 'Jalen Carter',
      stats: { pts: 24, reb: 6, ast: 4, fgm: 9, fga: 16, fg3m: 3, fg3a: 7, min: 2040 },
    },
    headline: 'Carter closes it late',
    box_score: {
      path: '/box-score.html',
      params: { mode: 'franchise', franchise_id: FID, game_id: 'g1', home: 'Lancaster', away: 'Four Corners' },
    },
  }, overrides || {});
}

function nextBlock(overrides) {
  return Object.assign({
    week: 22,
    date: null,
    site: 'away',
    neutral: null,
    opponent_team_id: 'cccccccccccccccccccccccc',
    opponent: 'Crickstown',
    rank: 21,
    record: { wins: 11, losses: 8 },
    conference: 2,
    conference_position: 2,
    conference_size: 8,
    top_scorer: { name: 'Avery Cole', average: 18.4 },
    top_rebounder: { name: 'Noah Peck', average: 9.1 },
    projected_starting_five: null,
    round_name: null,
    seeds: null,
    stakes: null,
    team_rt: null,
  }, overrides || {});
}

function wireBlock(overrides) {
  return Object.assign({
    status: 'Two leans moved',
    events: [
      {
        recruit_id: 'r1',
        recruit: 'Miles Hart',
        position: 'SG',
        stars: null,
        filmed_grade: null,
        event_type: 'gained',
        event_text: 'Miles Hart moved you to #2',
        event_detail: 'Moved you to #2',
        list_position: 2,
        direction: 'up',
      },
      {
        recruit_id: 'r2',
        recruit: 'Owen Blake',
        position: 'PF',
        stars: null,
        filmed_grade: null,
        event_type: 'lost',
        event_text: 'Owen Blake dropped you to #4',
        event_detail: 'Dropped you to #4',
        list_position: 4,
        direction: 'down',
      },
    ],
    pending_count: 1,
    urgent: true,
    unseen_count: 3,
  }, overrides || {});
}

function snapshotBlock(overrides) {
  return Object.assign({
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
  }, overrides || {});
}

function standingsBlock() {
  const names = ['Alpha', 'Crickstown', 'Gamma', 'Amariabi International', 'Delta', 'Echo', 'Foxtrot', 'Golf'];
  return {
    conference: 2,
    region: 'A',
    rows: names.map(function (name, index) {
      return {
        team_id: index === 3 ? TID : ('team-' + index),
        team_name: name,
        wins: 14 - index,
        losses: index,
        differential: 24 - index * 4,
        position: index + 1,
        is_user: index === 3,
      };
    }),
  };
}

/** The week-1 preview as season_preview.py sends it. Season 1 by default: no last season, no newcomers. */
function previewBlock(overrides) {
  const conference = [
    ['team-0', 'Alpha', 12], ['team-1', 'Crickstown', 21], ['team-2', 'Gamma', 33], [TID, 'Amariabi International', 40],
    ['team-4', 'Delta', 58], ['team-5', 'Echo', 77], ['team-6', 'Foxtrot', 96], ['team-7', 'Golf', 120],
  ];
  return Object.assign({
    ready: true,
    season: 1,
    preseason_rank: 40,
    national_rank: 40,
    outlook: { conference: 2, picked: { rank: 4, of: 8 }, last_season: null },
    rankings: { conference: { rank: 4, of: 8 }, region: { rank: 7, of: 16 }, national: { rank: 40, of: 128 } },
    key_players: [
      { player_id: 'p-jalen', name: 'Jalen Carter', rt: 84, pos: 'PG', year: 'SR', height: 75, weight: 190 },
      { player_id: 'p-marcus', name: 'Marcus Ruiz', rt: 77, pos: 'SF', year: 'JR', height: 79, weight: 215 },
      { player_id: 'p-avery', name: 'Avery Cole', rt: 71, pos: 'C', year: 'JR', height: 83, weight: 245 },
      { player_id: 'p-noah', name: 'Noah Peck', rt: 64, pos: 'PF', year: 'SO', height: 81, weight: 230 },
      { player_id: 'p-dev', name: 'Devonte Whitfield-Alexander', rt: 58, pos: 'SG', year: 'FR', height: 76, weight: 195 },
    ],
    newcomers: null,
    all_americans: [
      { position: 'PG', player_id: 'aa-1', name: 'Tyrese Vaughn', team_id: 'team-90', team_name: 'Long Island Methodist', rt: 103, is_user: false },
      { position: 'SG', player_id: 'aa-2', name: 'Cal Okafor', team_id: 'team-91', team_name: 'Chapel Hill', rt: 98, is_user: false },
      { position: 'SF', player_id: 'p-marcus', name: 'Marcus Ruiz', team_id: TID, team_name: 'Amariabi International', rt: 96, is_user: true },
      { position: 'PF', player_id: 'aa-4', name: 'Dre Hollis', team_id: 'team-93', team_name: 'Four Corners', rt: 95, is_user: false },
      { position: 'C', player_id: 'aa-5', name: 'Ansel Brandt', team_id: 'team-94', team_name: 'Seattle AAA', rt: 101, is_user: false },
    ],
    opener: nextBlock({ week: 1, site: 'home', record: { wins: 0, losses: 0 }, top_scorer: null, top_rebounder: null, last_meeting: null }),
    circle_these: [
      { week: 4, site: 'away', opponent_team_id: 'team-90', opponent: 'Long Island Methodist', rank: 3 },
      { week: 11, site: 'home', opponent_team_id: 'team-0', opponent: 'Alpha', rank: 12 },
      { week: 19, site: 'away', opponent_team_id: 'team-91', opponent: 'Chapel Hill', rank: 7 },
    ],
    preseason_rankings: {
      conference: 2,
      rows: conference.map((row) => ({ team_id: row[0], team_name: row[1], national_rank: row[2], is_user: row[0] === TID })),
    },
    walk_ons: [
      { player_id: 'w-1', name: 'Sam Ortega', pos: 'SG', year: 'FR', rt: 34 },
      { player_id: 'w-2', name: 'Kip Lawson', pos: 'PF', year: 'SO', rt: 31 },
      { player_id: 'w-3', name: 'Teo Marsh', pos: 'PG', year: 'JR', rt: 29 },
    ],
  }, overrides || {});
}

/** The region's best recruits and their top lean: sent every week until Signing Day. */
function topRecruitsBlock(overrides) {
  return Object.assign({
    region: 'A',
    rows: [
      { recruit_id: 'r10', name: 'Darius Kemp', position: 'C', rt: 92, year: 'SR', lean_team_id: 'team-0', lean_team_name: 'Alpha', lean_is_user: false },
      { recruit_id: 'r11', name: 'Miles Hart', position: 'SG', rt: 88, year: 'SR', lean_team_id: TID, lean_team_name: 'Amariabi International', lean_is_user: true },
      { recruit_id: 'r12', name: 'Owen Blake', position: 'PF', rt: 81, year: 'JR', lean_team_id: 'team-1', lean_team_name: 'Crickstown', lean_is_user: false },
      { recruit_id: 'r13', name: 'Jon Abara', position: 'PG', rt: 74, year: 'SR', lean_team_id: null, lean_team_name: null, lean_is_user: false },
      { recruit_id: 'r14', name: 'Luka Fenn', position: 'SF', rt: 69, year: 'SO', lean_team_id: 'team-2', lean_team_name: 'Gamma', lean_is_user: false },
    ],
    // The coach's watchlist: the five best of seven watched, from any region.
    watchlist: {
      count: 7,
      rows: [
        { recruit_id: 'w1', name: 'Tobias Okonkwo-Reyes', position: 'PF', rt: 95, year: 'SR', lean_team_id: 'team-9', lean_team_name: 'Long Island Methodist', lean_is_user: false },
        { recruit_id: 'r11', name: 'Miles Hart', position: 'SG', rt: 88, year: 'SR', lean_team_id: TID, lean_team_name: 'Amariabi International', lean_is_user: true },
        { recruit_id: 'w3', name: 'Enzo Varga', position: 'PG', rt: 84, year: 'JR', lean_team_id: 'team-7', lean_team_name: 'Chapel Hill', lean_is_user: false },
        { recruit_id: 'w4', name: 'Sol Whitaker', position: 'C', rt: 77, year: 'SR', lean_team_id: null, lean_team_name: null, lean_is_user: false },
        { recruit_id: 'w5', name: 'Kofi Brandt', position: 'SF', rt: 70, year: 'FR', lean_team_id: 'team-3', lean_team_name: 'Delta', lean_is_user: false },
      ],
    },
  }, overrides || {});
}

/** Week 35 once the Orders list is in: every recruit with points, most points first. */
function submittedOrders() {
  return [
    { recruit_id: 'r1', name: 'Miles Hart', position: 'SG', rt: 'A', year: 'SR', points: 18 },
    { recruit_id: 'r2', name: 'Owen Blake', position: 'PF', rt: 'B+', year: 'JR', points: 12 },
    { recruit_id: 'r3', name: 'Tobias Okonkwo-Reyes', position: 'PF', rt: 'A+', year: 'SR', points: 5 },
    { recruit_id: 'r4', name: 'Sol Whitaker', position: 'C', rt: 'B', year: 'SR', points: 2 },
    { recruit_id: 'r5', name: 'Kofi Brandt', position: 'SF', rt: 'C+', year: 'FR', points: 1 },
  ];
}

function digest(state, patch) {
  const body = {
    state: state,
    what_moved: {
      national_rank: { now: 18, prev: 22, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 16, losses: 5 },
      streak: 'W4',
      attribute_changes: [
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'SH', from: 6, to: 7 },
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'ND', from: 7, to: 6 },
        { player_id: 'p-marcus', name: 'Marcus Ruiz', attribute: 'BH', from: 4, to: 5 },
      ],
    },
    team_snapshot: snapshotBlock(),
    result: resultBlock(),
    next_game: nextBlock(),
    conference_standings: standingsBlock(),
    todos: [
      { id: 'run_training', label_key: 'run_training', required: true, done: true, gates_advance: false, is_advance_action: false, route: '/training.html' },
      { id: 'review_recruit_invites', label_key: 'review_recruit_invites', required: true, done: false, gates_advance: true, is_advance_action: false, route: '/recruiting.html' },
      { id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: true, route: '/set-lineup.html' },
      { id: 'resume_training', label_key: 'resume_training', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' },
      { id: 'run_training_camp', label_key: 'run_training_camp', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' },
    ],
    recruiting_wire: wireBlock(),
    signing_day: null,
    season_preview: null,
    // Top Recruits stays all season; the server stops sending it from Signing Day.
    top_recruits: state === 'signing_day' ? null : topRecruitsBlock(),
  };
  return Object.assign(body, patch || {});
}

function commandCenter(office, flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 22,
    rank: 18,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 22, counts: {} },
    user_conference: 1,
    user_region: 'A',
    office_digest: office,
  }, flags || {});
}

const STATES = {
  win: commandCenter(digest('win')),
  loss: commandCenter(digest('loss', {
    result: resultBlock({
      user_won: false,
      home_score: 58,
      away_score: 71,
      leader_role: 'team_leader',
      leader: { player_id: 'p-jalen', name: 'Jalen Carter', stats: { pts: 19, reb: 4, ast: 3 } },
      headline: null,
    }),
    what_moved: {
      national_rank: { now: 24, prev: 18, delta: -6 },
      conference_standing: { now: 6, prev: 3, delta: -3 },
      record: { wins: 15, losses: 6 },
      streak: 'L1',
      attribute_changes: [],
    },
  })),
  regular: commandCenter(digest('regular', {
    result: resultBlock({ user_won: null, home_score: 70, away_score: 70, headline: null, leader_role: null, leader: null }),
    what_moved: {
      national_rank: { now: 20, prev: 20, delta: 0 },
      conference_standing: { now: 4, prev: 4, delta: 0 },
      record: { wins: 8, losses: 8 },
      streak: null,
      attribute_changes: [],
    },
  })),
  first_week: commandCenter(digest('first_week', {
    result: null,
    what_moved: {
      national_rank: { now: 40, prev: null, delta: null },
      conference_standing: { now: null, prev: null, delta: null },
      record: { wins: 0, losses: 0 },
      streak: null,
      attribute_changes: [],
    },
    team_snapshot: snapshotBlock({ state: 'set_after_camp', moved_most: [] }),
    season_preview: previewBlock(),
    next_game: nextBlock({ week: 1, site: 'home' }),
    recruiting_wire: wireBlock({ status: 'No preseason leans', events: [], pending_count: 0, urgent: false }),
    todos: [
      { id: 'run_training_camp', label_key: 'run_training_camp', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/training.html' },
    ],
  }), { week: 1, training_completed: false, session_type: 'preseason' }),
  tournament: commandCenter(digest('tournament', {
    result: resultBlock({ week: 30, round_name: 'Region Tourney First Round', headline: null }),
    next_game: nextBlock({
      week: 31,
      site: 'home',
      round_name: 'Region Tourney Championship',
      seeds: null,
      stakes: null,
      team_rt: null,
      date: null,
      neutral: null,
      projected_starting_five: null,
    }),
  }), { week: 31, eos_tournament_active: true, training_completed: true, training_disabled_for_postseason: true }),
  signing_day: commandCenter(digest('signing_day', {
    result: resultBlock({ week: 34, round_name: 'National Championship', user_won: true, headline: null }),
    next_game: null,
    recruiting_wire: wireBlock({ status: 'Signing Day', pending_count: 1, urgent: true }),
    signing_day: {
      points_remaining: 12,
      points_total: 50,
      promises_made: 1,
      open_roster_spots: 3,
      targets: [
        { recruit_id: 'r1', name: 'Miles Hart', position: 'SG', stars: null, rt: 'A', lean_rank: 1, direction: 'up' },
        { recruit_id: 'r2', name: 'Owen Blake', position: 'PF', stars: null, rt: 'B+', lean_rank: 2, direction: null },
      ],
    },
    todos: [
      { id: 'run_signing_day', label_key: 'run_signing_day', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/recruiting.html' },
    ],
  }), { week: 35 }),
};

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data) {
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(function () {});
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
      || pathname.startsWith('/recruit/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, data);
      return;
    }
    if (pathname.startsWith('/franchise/play-next-game')) {
      await fulfillJson(route, {
        home: 'Lancaster', away: 'Morristown', week: 22,
        home_id: TID, away_id: 'cccccccccccccccccccccccc',
        home_display: 'Lancaster', away_display: 'Morristown',
      });
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      var table = (data.office_digest && data.office_digest.conference_standings) || standingsBlock();
      await fulfillJson(route, {
        standings: (table.rows || []).map(function (row) {
          return {
            team_id: row.team_id,
            name: row.team_name,
            display_name: row.team_name,
            W: row.wins,
            L: row.losses,
            differential: row.differential,
            conference: table.conference,
            region: table.region,
          };
        }),
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openOffice(page, data) {
  await stubAuth(page);
  await installApi(page, data);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
  await page.waitForFunction(() => {
    const root = document.documentElement;
    return root.classList.contains('gob-1280') || root.classList.contains('gob-1920');
  });
  // The display font (Bebas Neue Pro) loads async and its metrics change card
  // heights; the office re-runs its standings fit on document.fonts.ready. Wait on
  // that real signal (not a guessed timeout) and then until the fit has CONVERGED —
  // the standings row count stable across several frames — so nothing is measured
  // mid-reflow. This replaces the old fixed 900ms sleep.
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    const frame = () => new Promise((r) => requestAnimationFrame(r));
    // A layout signature that captures the async font reflow AND the standings
    // re-fit: the standings row count plus every column's card edges. Wait until it
    // holds steady across several frames — the office is then genuinely at rest.
    const signature = () => {
      const parts = [];
      const st = document.querySelector('#office-root .office-st');
      parts.push(st ? String(st.dataset.standingsShown || '') : 'none');
      document.querySelectorAll('#office-root .office-col > *').forEach((el) => {
        const r = el.getBoundingClientRect();
        parts.push(Math.round(r.top) + ':' + Math.round(r.bottom));
      });
      return parts.join('|');
    };
    let prev = signature();
    let stable = 0;
    for (let i = 0; i < 120 && stable < 5; i += 1) {
      await frame();
      const now = signature();
      if (now === prev) stable += 1; else { stable = 0; prev = now; }
    }
  });
}

module.exports = { FID, TID, STATES, digest, commandCenter, resultBlock, nextBlock, wireBlock, snapshotBlock, standingsBlock, previewBlock, topRecruitsBlock, submittedOrders, installApi, openOffice, fulfillJson };
