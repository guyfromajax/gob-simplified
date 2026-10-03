// @ts-check
/**
 * Training Report fixtures for the top-of-report redesign (Notes cards + Team Report grid).
 *
 * Three weeks, the shape /franchise/training-report serves:
 *   busy   in season, plenty moved
 *   quiet  in season, almost nothing moved
 *   camp   training camp (week 1): camp titles, camp mark scale
 * The notes are in the server's own vocabulary (BackEnd/models/training_notes.py).
 */
const fs = require('fs');
const path = require('path');

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '../fixtures/prep-plan.json'), 'utf8'));
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../../FrontEnd/static/images/players/generic_headshot.png'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function roster() {
  return clone(FIXTURE.trainingPoints.custom_focus_roster).slice(0, 12);
}

function players() {
  const years = ['SR', 'JR', 'SO', 'FR'];
  return roster().map((row, i) => ({
    player_id: row.player_id,
    id: row.player_id,
    name: row.name,
    jersey: row.jersey,
    year: years[i % years.length],
    pos: row.pos,
    position: row.pos,
    position_ratings: row.position_ratings,
    attributes: row.attrs,
    attrs: row.attrs,
    height: row.height,
    weight: row.weight,
    season_stats: {},
  }));
}

/** Five starters in the shape `compute_projected_starting_five` serves (0-10 display scale). */
function projectedFive(list) {
  return ['PG', 'SG', 'SF', 'PF', 'C'].map((position, i) => {
    const player = list.find((p) => p.position === position) || list[i];
    const attributes = {};
    Object.keys(player.attributes).forEach((key) => { attributes[key] = Math.floor(Number(player.attributes[key]) / 10); });
    return {
      position,
      player_id: player.player_id,
      name: player.name,
      jersey: player.jersey,
      year: player.year,
      height: player.height,
      weight: player.weight,
      rt: Math.max.apply(null, Object.values(player.position_ratings || {}).map(Number)),
      attributes,
    };
  });
}

const TEAM_ATTRIBUTES = {
  shot_threshold: 0, rebound_modifier: 1, offensive_efficiency: 4, defensive_efficiency: 2,
  fb_efficiency: 1, pt_efficiency: 6, fight: 2, discipline: 3, team_chemistry: 8,
  fb_opp_modifier: -2, pt_opp_modifier: -1,
};

function base(week) {
  const list = players();
  const plays_data = clone(FIXTURE.teamData.plays_data);
  Object.keys(plays_data).forEach((name, i) => { plays_data[name].effectiveness = 40 + (i * 3) % 55; });
  return {
    week,
    upcoming_opponent: 'Four Corners',
    coaching_focus: { archetype: 'systems-coach', sub_option: 'systems-coach-offense', leaf_display_name: 'Offense' },
    players: list,
    player_changes: {},
    player_attribute_display_movements: {},
    exceptional_gains: [],
    team_attributes: clone(TEAM_ATTRIBUTES),
    team_changes: {},
    plays_data,
    scouting_data: clone(FIXTURE.teamData.scouting_data),
    plays_effectiveness_changes: {},
    defenses_effectiveness_changes: {},
    projected_starting_five: projectedFive(list),
    training_notes: [],
  };
}

function person(title, player) {
  return { title, body: player.name, player_id: player.player_id, player_ids: [player.player_id] };
}

/** In season, a week where plenty moved. */
function busy() {
  const report = base(12);
  const p = report.players;
  [2.5, 0.4, 0.6, -0.3, 1.2, 0, -1, 0.2, -2, 0.5, -0.4, 3.2].forEach((delta, i) => {
    // Five trained attributes: one whole pair (SC SH), PS alone, and the AG ND pair.
    report.player_changes[p[i].name] = { SC: delta, SH: delta / 2, PS: delta, AG: -delta / 2, ND: delta / 4 };
  });
  report.team_changes = {
    shot_threshold: -1, offensive_efficiency: 3.5, defensive_efficiency: 1.2, fb_efficiency: 0.4,
    fb_opp_modifier: -0.6, fight: -2, discipline: -3,
  };
  // CMD gains the size the engine really gives in a session (measured 2026-10-02): set
  // plays a few points, motions a few dozen, zones 20-50, Man near 85. Untrained plays: 0.
  report.plays_effectiveness_changes = {
    '4-1 Motion': 29, '5-0 Motion': 23, '3-2 Motion': 33, 'PF Post Motion': 16,
    'Pick & Roll - Entry Pass': 5, 'Double Screen Three - Wing': 4, 'Base Post Play': 6,
    'Iso': 3, 'Back Door Cut': 7, 'Misdirection Three': 4, 'Quick Midrange Jumper': 2,
  };
  report.defenses_effectiveness_changes = { man: 85, '2-3-zone': 26, '3-2-zone': 31, '1-3-1-zone': 52 };
  report.training_notes = [
    person('Practice Player Of The Week', p[11]),
    person('Biggest Regression', p[8]),
    person('Most Positive Locker Room Influence', p[2]),
    { title: 'Strong Cumulative Increase', body: 'SC, PS' },
    { title: 'Concerning Regression', body: 'AG' },
    { title: 'Strongest Offensive Plays', body: '4-1 Motion, Horns Flare, 5-0 Flex' },
    { title: 'Strongest Defensive Set', body: '2-3 Zone' },
    { title: 'Fast Break Readiness', body: 'Strong', value: 12 },
    { title: 'Press/Trap Readiness', body: 'Weak', value: -14 },
    { title: 'Player Energy Levels', body: 'No Significant Updates' },
  ];
  return report;
}

/** In season, a week where almost nothing moved. */
function quiet() {
  const report = base(14);
  const p = report.players;
  report.player_changes[p[3].name] = { SC: 0.3 };
  report.team_changes = { fb_efficiency: 0.4 };
  report.training_notes = [
    person('Practice Player Of The Week', p[3]),
    { title: 'Biggest Regression', body: 'None' },
    { title: 'Most Positive Locker Room Influence', body: 'None' },
    { title: 'Strong Cumulative Increase', body: 'No Significant Updates' },
    { title: 'Concerning Regression', body: 'No Significant Updates' },
    { title: 'Strongest Offensive Plays', body: '4-1 Motion' },
    { title: 'Strongest Defensive Set', body: 'Man-to-Man' },
    { title: 'Fast Break Readiness', body: 'Neutral', value: 0 },
    { title: 'Press/Trap Readiness', body: 'Neutral', value: -9 },
    { title: 'Player Energy Levels', body: 'No Significant Updates' },
  ];
  return report;
}

/** Training camp (week 1): camp titles, the camp mark scale, and a Player Energy note to show. */
function camp() {
  const report = base(1);
  const p = report.players;
  [7, 5.5, 4, 3, 6, 2.5, 1.5, 4.5, 0.8, 3.5, 2, 5].forEach((delta, i) => {
    // Camp trains everything: all twelve attributes move.
    report.player_changes[p[i].name] = {
      SC: delta, SH: delta - 1, ID: delta / 2, OD: delta / 3, PS: delta - 2, BH: delta / 4,
      RB: delta / 2, ST: delta / 2, AG: delta / 3, ND: delta - 3, IQ: delta / 5, FT: delta / 6,
    };
  });
  report.team_changes = {
    shot_threshold: -6, rebound_modifier: 0.05, offensive_efficiency: 6, defensive_efficiency: 2.5,
    fb_efficiency: 1, pt_efficiency: 3, fight: 2, discipline: -1, team_chemistry: 4, pt_opp_modifier: 5.5,
  };
  // A camp session with full installs and a Custom Playbook play (real week 1 sizes).
  report.plays_effectiveness_changes = {
    '4-1 Motion': 46, '5-0 Motion': 46, '3-2 Motion': 48,
    'Pick & Roll - Entry Pass': 7, 'Double Screen Three - Wing': 7, 'Base Post Play': 7,
    'Iso': 8, 'Back Door Cut': 12, 'Misdirection Three': 4, 'High Post Drive': 20,
  };
  report.defenses_effectiveness_changes = { man: 120, '2-3-zone': 39, '3-2-zone': 29, '1-3-1-zone': 41 };
  report.training_notes = [
    person('Training Camp MVP', p[0]),
    person('Biggest Concern', p[8]),
    person('Most Positive Locker Room Influence', p[4]),
    { title: 'Strong Cumulative Increase', body: 'SC, ST, SH' },
    { title: 'Concerning Progression', body: 'FT' },
    { title: 'Strongest Offensive Plays', body: 'Horns Flare, Double Drag' },
    { title: 'Strongest Defensive Set', body: '2-3 Zone, Man-to-Man' },
    { title: 'Fast Break Readiness', body: 'Very Strong', value: 24 },
    { title: 'Press/Trap Readiness', body: 'Neutral', value: 3 },
    { title: 'Player Energy Levels', body: p[5].name + ' and ' + p[9].name + ' came out of camp with heavy legs.' },
  ];
  return report;
}

const SCENARIOS = { busy, quiet, camp };

function query(extra) {
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, mode: 'franchise' });
  Object.keys(extra || {}).forEach((key) => q.set(key, extra[key]));
  return q.toString();
}

/** Answer every API call the report page makes; `report` is the report body. */
async function installReportApi(page, report, opts) {
  const options = opts || {};
  const cc = clone(FIXTURE.cc);
  cc.week = report.week;
  cc.session_type = report.week === 1 ? 'preseason' : 'in-season';
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { return route.continue(); }
    if (pathname.startsWith('/images/players/')) {
      return route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname === '/api/auth/me') return json({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/franchise/command-center/data') return json(cc);
    if (pathname === '/franchise/team-data') return json(FIXTURE.teamData);
    if (pathname === '/franchise/league-news') return json(FIXTURE.news);
    if (pathname === '/franchise/standings') return json(FIXTURE.standings);
    if (pathname === '/teams') return json(FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return json(FIXTURE.roster);
    if (pathname === '/franchise/training-report') {
      if (options.delayMs) await new Promise((resolve) => setTimeout(resolve, options.delayMs));
      return json(report);
    }
    return json({});
  });
}

function reportUrl(report) {
  return '/training-report.html?' + query({ week: String(report.week), from: 'training', origin: 'prep' });
}

module.exports = { SCENARIOS, busy, quiet, camp, installReportApi, reportUrl, clone, FIXTURE };
