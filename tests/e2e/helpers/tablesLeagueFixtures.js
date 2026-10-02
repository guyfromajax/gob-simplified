/**
 * One stubbed league for tables-league.spec.js: the 128 real teams from base_league.json
 * with deterministic records, so every League and Team view renders a full, realistic page.
 * Payload shapes follow the routes the views read; nothing here is read by the app.
 */
const fs = require('fs');
const path = require('path');

const FID = 'f-e2e-tables-league';
const FIRST = ['Jalen', 'Marcus', 'Devin', 'Tyrese', 'Isaiah', 'Caleb', 'Andre', 'Miles', 'Jordan', 'Elijah', 'Darius', 'Owen'];
const LAST = ['Carter', 'Brooks', 'Hayes', 'Mitchell', 'Reed', 'Bennett', 'Coleman', 'Price', 'Warren', 'Foster', 'Hughes', 'Sullivan'];
const POS = ['PG', 'SG', 'SF', 'PF', 'C', 'PG', 'SG', 'SF', 'PF', 'C', 'SG', 'PF'];
const YRS = ['SR', 'JR', 'SO', 'FR'];
const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
const LEADER_STATS = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];
const REGIONS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

function rng(seed) {
  let s = seed >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function hexId(i) {
  return ('a' + String(i).padStart(3, '0')).padEnd(24, 'e');
}

function buildLeague() {
  const base = JSON.parse(fs.readFileSync(path.join(__dirname, '../../../base_league.json'), 'utf8'));
  const rand = rng(29);
  const teams = base.collections.teams.map(function (team, i) {
    return {
      team_id: hexId(i),
      name: team.name,
      region: team.region,
      conference: Number(team.conference),
      primary_color: team.primary_color,
      prestige: Number(team.prestige) || 0,
    };
  });
  teams.sort(function (a, b) { return b.prestige - a.prestige || a.name.localeCompare(b.name); });
  teams.forEach(function (team, i) {
    team.natl_rank = i + 1;
    const strength = 1 - i / teams.length;
    team.W = Math.max(0, Math.min(12, Math.round(strength * 10 + rand() * 3)));
    team.L = 12 - team.W;
    team.PF = Math.round(900 + strength * 120 + rand() * 40);
    team.PA = Math.round(900 + (1 - strength) * 110 + rand() * 40);
  });
  const user = teams.find(function (team) { return team.name === 'Lancaster'; }) || teams[40];
  return { teams: teams, user: user };
}

const LEAGUE = buildLeague();
const USER = LEAGUE.user;
const TID = USER.team_id;
const BY_ID = {};
LEAGUE.teams.forEach(function (team) { BY_ID[team.team_id] = team; });

function conferenceTeams(conference) {
  return LEAGUE.teams.filter(function (team) { return team.conference === conference; });
}

function opponentOf(team, offset) {
  const pool = conferenceTeams(team.conference).filter(function (other) { return other !== team; });
  return pool[offset % pool.length];
}

const OPP = opponentOf(USER, 2);

function rankings() {
  return LEAGUE.teams.map(function (team, i) {
    const last = opponentOf(team, 1);
    const next = opponentOf(team, 2);
    const won = i % 3 !== 2;
    const us = 62 + (i % 17);
    const them = won ? us - 3 - (i % 9) : us + 4 + (i % 7);
    return {
      team_id: team.team_id, natl_rank: team.natl_rank, team_name: team.name, name: team.name,
      primary_color: team.primary_color, conference: team.conference,
      W: team.W, L: team.L, PF: team.PF, PA: team.PA,
      last_week: (i % 2 ? '@ ' : 'vs ') + last.name + ', ' + us + '-' + them,
      last_week_result: won ? 'W' : 'L',
      next: (i % 2 ? 'vs ' : '@ ') + next.name,
    };
  });
}

function standings() {
  return {
    standings: LEAGUE.teams.map(function (team, i) {
      const next = opponentOf(team, 2);
      return {
        team_id: team.team_id, name: team.name, display_name: team.name,
        region: team.region, conference: team.conference, primary_color: team.primary_color,
        W: team.W, L: team.L, pct: team.W / 12, PF: team.PF, PA: team.PA,
        differential: team.PF - team.PA,
        streak: (i % 3 ? 'W' : 'L') + (1 + (i % 4)),
        natl_rank: team.natl_rank,
        next_opponent_id: next.team_id, next_opponent_name: next.name, next_week: 13, next_site: 'vs',
      };
    }),
    user_conference: USER.conference,
    user_region: USER.region,
  };
}

function leaders(limit, scope) {
  const pool = scope === 'conference' ? conferenceTeams(USER.conference) : LEAGUE.teams;
  const body = {};
  LEADER_STATS.forEach(function (stat, s) {
    const rows = [];
    for (let i = 0; i < limit; i += 1) {
      const team = pool[(i * 3 + s) % pool.length];
      const mine = i === 3 && s % 2 === 0;
      const rate = stat === 'FG%' || stat === 'DEF%';
      const total = stat === '3PTM' || stat === 'BLK' || stat === 'STL';
      rows.push({
        player_id: stat + '-p' + i,
        name: FIRST[(i + s) % FIRST.length] + ' ' + LAST[(i * 5 + s) % LAST.length],
        team: mine ? USER.name : team.name,
        team_id: mine ? TID : team.team_id,
        position: i % 2 ? 'G' : 'F',
        year: YRS[i % 4],
        value: rate ? 58.4 - i * 0.9 : (total ? 44 - i * 2 : 24.6 - i * 0.7),
      });
    }
    body[stat] = rows;
  });
  return body;
}

function teamStats(scope) {
  const rows = scope === 'conference' ? conferenceTeams(USER.conference) : LEAGUE.teams;
  return {
    teams: rows.map(function (team, i) {
      const fga = 58 + (i % 9);
      const fgm = Math.round(fga * (0.41 + (i % 7) / 100));
      return {
        team: team.name, team_id: team.team_id, primary_color: team.primary_color,
        natl_rank: team.natl_rank, conference: team.conference, region: team.region,
        stats: {
          W: team.W, L: team.L, PF: Math.round(team.PF / 12), PA: Math.round(team.PA / 12),
          FGM: fgm, FGA: fga, FG_PCT: Math.round((fgm / fga) * 1000) / 10,
          '3PTM': 7 + (i % 5), '3PTA': 21 + (i % 6), TP_PCT: 33.3 + (i % 8),
          FTM: 11 + (i % 6), FTA: 16 + (i % 5), FT_PCT: 68 + (i % 12),
          DREB: 23 + (i % 5), OREB: 9 + (i % 4), TREB: 32 + (i % 7),
          AST: 13 + (i % 6), F: 15 + (i % 4), TO: 11 + (i % 5), SCR_A: 12 + (i % 4), SCR_PCT: 44 + (i % 10),
          STL: 6 + (i % 4), BLK: 2 + (i % 4), DEF_A: 38 + (i % 9), DEF_PCT: 51 + (i % 9),
        },
      };
    }),
  };
}

function side(team) {
  return { team_id: team.team_id, name: team.name, natl_rank: team.natl_rank, primary_color: team.primary_color };
}

function weekCatalog(current) {
  const labels = { 27: 'Conference Tourney - R1', 30: 'Region Tourney - R1' };
  const weeks = [];
  for (let w = 1; w <= 34; w += 1) {
    weeks.push({ week: w, label: 'Week ' + w + (labels[w] ? ': ' + labels[w] : ''), enabled: w <= current });
  }
  return weeks;
}

/** A regular-season week: 64 conference games. Weeks before `current` are final. */
function regularWeek(week, current) {
  const done = week < current;
  const games = [];
  for (let conf = 1; conf <= 16; conf += 1) {
    const list = conferenceTeams(conf).slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    for (let i = 0; i < list.length; i += 2) {
      const away = list[(i + week) % list.length];
      const home = list[(i + week + 1) % list.length];
      const n = games.length;
      const awayScore = 58 + ((n * 7 + week) % 25);
      const homeScore = 58 + ((n * 11 + week * 3) % 25) + (n % 5 === 0 ? 1 : 0);
      games.push({
        away: side(away), home: side(home),
        status: done ? 'complete' : 'scheduled',
        away_score: done ? awayScore : null,
        home_score: done ? (homeScore === awayScore ? homeScore + 2 : homeScore) : null,
        game_id: done ? 'g-' + week + '-' + n : null,
        is_user: away.team_id === TID || home.team_id === TID,
        tournament_context: null,
      });
    }
  }
  games.sort(function (a, b) { return Number(b.is_user) - Number(a.is_user); });
  return { week: week, label: 'Week ' + week, current_week: current, user_team_id: TID, weeks: weekCatalog(current), games: games, byes: [] };
}

/**
 * Week 30, Region Tourney R1. Each region sends two, three or four teams, so a region is
 * two games, one game and one bye, or two byes. The server lists games in its own order
 * (the user's first) and the byes by region.
 */
function regionWeek() {
  const games = [];
  const byes = [];
  REGIONS.forEach(function (letter, r) {
    const pool = LEAGUE.teams.filter(function (team) { return team.region === letter; });
    const shape = letter === USER.region ? 1 : r % 3; // 0: two games, 1: game + bye, 2: two byes
    const four = letter === USER.region
      ? [USER].concat(pool.filter(function (team) { return team !== USER; }).slice(0, 3))
      : pool.slice(0, 4);
    function game(away, home) {
      games.push({
        away: side(away), home: side(home), status: 'scheduled', away_score: null, home_score: null,
        game_id: null, is_user: away.team_id === TID || home.team_id === TID,
        tournament_context: 'Region ' + letter, region: letter,
      });
    }
    function bye(team) {
      byes.push({ team: side(team), region: letter, is_user: team.team_id === TID, tournament_context: 'Region ' + letter });
    }
    if (shape === 0) { game(four[0], four[3]); game(four[1], four[2]); }
    else if (shape === 1) { game(four[1], four[2]); bye(four[0]); }
    else { bye(four[0]); bye(four[1]); }
  });
  // The route sorts by the user's conference first, so the page cannot rely on A..H.
  games.sort(function (a, b) { return Number(b.is_user) - Number(a.is_user) || b.region.localeCompare(a.region); });
  return {
    week: 30, label: 'Week 30: Region Tourney - R1', current_week: 30, user_team_id: TID,
    weeks: weekCatalog(30), games: games, byes: byes,
  };
}

function players(team) {
  const seed = LEAGUE.teams.indexOf(team);
  const rand = rng(100 + seed);
  return FIRST.map(function (first, i) {
    const attributes = {};
    ATTRS.forEach(function (key, k) {
      attributes[key] = Math.max(8, Math.min(99, Math.round(38 + rand() * 55 - i * 1.5 + (k % 3) * 4)));
    });
    return {
      _id: team.team_id.slice(0, 20) + String(i).padStart(4, '0'),
      name: first + ' ' + LAST[(i * 5 + seed) % LAST.length],
      position: POS[i], year: YRS[i % 4], jersey: [4, 11, 23, 32, 50, 7, 3, 14, 21, 44, 10, 35][i],
      height: 73 + (i % 5) * 2 + (i > 6 ? 1 : 0), weight: 178 + (i % 5) * 14 + i,
      rt: Math.round(88 - i * 4.5), potential_rt_ratcheted: Math.round(92 - i * 3.5),
      starter: i < 5, lineup_order: i,
      attributes: attributes,
    };
  });
}

function roster(teamId) {
  const team = BY_ID[teamId] || USER;
  return {
    team: team.name, is_user_team: team === USER,
    players: players(team), training_squad: [], practice_squad_recruits: [],
  };
}

function playerStats(teamId) {
  const team = BY_ID[teamId] || USER;
  return {
    team_id: team.team_id,
    players: players(team).map(function (p, i) {
      const gp = 12;
      const per = {
        GP: gp, MIN: 31.5 - i * 2.2, PTS: 18.4 - i * 1.3, FGM: 6.9 - i * 0.5, FGA: 14.2 - i * 0.9,
        '3PTM': Math.max(0, 2.4 - i * 0.2), '3PTA': Math.max(0, 6.1 - i * 0.5), FTM: 2.8 - i * 0.2, FTA: 3.6 - i * 0.25,
        OREB: 0.8 + (i % 5) * 0.4, DREB: 2.6 + (i % 5) * 0.8, REB: 3.4 + (i % 5) * 1.2,
        AST: Math.max(0.3, 5.2 - i * 0.4), TO: 2.1 - i * 0.1, STL: 1.4 - i * 0.1, BLK: 0.2 + (i % 5) * 0.3, F: 2.2 + (i % 3) * 0.4,
      };
      const totals = {};
      Object.keys(per).forEach(function (key) { totals[key] = key === 'GP' ? gp : Math.round(per[key] * gp); });
      return {
        player_id: p._id, name: p.name, position: p.position, year: p.year, jersey: p.jersey,
        per_game: per, totals: totals,
        rates: { fg_pct: 48.6 - i * 0.8, tp_pct: i % 5 === 4 ? null : 37.2 - i * 0.6, ft_pct: 78.1 - i * 1.1, def_pct: 52.3 - i * 0.7 },
      };
    }),
  };
}

function gameRow(team, week, played) {
  const opp = opponentOf(team, week);
  const us = 61 + ((week * 7) % 19);
  const them = week % 3 === 0 ? us + 5 : us - 6;
  const row = {
    week: week, site: week % 2 ? 'home' : 'away', opponent_id: opp.team_id, opponent_name: opp.name,
    opponent_primary_color: opp.primary_color, opponent_natl_rank: opp.natl_rank,
    opponent_wins: opp.W, opponent_losses: opp.L,
  };
  if (played) Object.assign(row, { team_score: us, opp_score: them, result: us > them ? 'W' : 'L', game_id: 'g-' + team.team_id.slice(0, 4) + '-' + week });
  return row;
}

function teamDetail(teamId) {
  const team = BY_ID[teamId] || USER;
  const results = [];
  for (let w = 12; w >= 1; w -= 1) results.push(gameRow(team, w, true));
  const upcoming = [];
  for (let w = 14; w <= 26; w += 1) upcoming.push(gameRow(team, w, false));
  return {
    team_id: team.team_id, name: team.name, primary_color: team.primary_color,
    conference: team.region + team.conference, region: team.region,
    record: { wins: team.W, losses: team.L }, natl_rank: team.natl_rank,
    conference_place: '2nd of 8', streak: 'W3',
    next_game: gameRow(team, 13, false), results: results, upcoming: upcoming,
  };
}

const MEASURE_DEFS = [
  ['character', 'team_chemistry', 'Chemistry', 19, 25, null],
  ['character', 'fight', 'Fight', 6, null, 20],
  ['character', 'discipline', 'Discipline', -3, null, 20],
  ['floor', 'offensive_efficiency', 'Offense', 12, null, 20],
  ['floor', 'defensive_efficiency', 'Defense', 5, null, 20],
  ['floor', 'pt_opp_modifier', 'P/T Offense', -4, null, 20],
  ['floor', 'pt_efficiency', 'P/T Defense', 9, null, 20],
  ['floor', 'fb_efficiency', 'Fast Break', 14, null, 20],
  ['floor', 'fb_opp_modifier', 'Fast Break Defense', -7, null, 20],
  ['floor', 'shot_threshold', 'Shooting', 88, null, null],
  ['floor', 'rebound_modifier', 'Rebounding', 0.52, null, null],
];

function teamData(teamId) {
  const shift = teamId && teamId !== TID ? 5 : 0;
  const attrs = {};
  const measures = MEASURE_DEFS.map(function (def, i) {
    const signed = def[5];
    const value = signed ? Math.max(-20, Math.min(20, def[3] - shift * (i % 2 ? 1 : -1))) : def[3];
    attrs[def[1]] = value;
    const rank = [34, 21, 77, 1, 40, 96, 18, 3, 104, 12, 8][i] + shift;
    return {
      family: def[0], family_label: def[0] === 'character' ? 'Character' : 'On the floor',
      key: def[1], label: def[2], value: value, scale_max: def[4], signed_scale: signed,
      meter_pct: def[1] === 'team_chemistry' ? (value / 25) * 100 : null,
      delta: null, description: null,
      direction: def[1] === 'shot_threshold' ? 'lower_better' : 'higher_better',
      rank: rank, rank_of: 128, percentile: Math.round(100 - (rank / 128) * 100),
      rank_delta: [null, 2, -1, 0, 3, null, -4, 1, null, 5, null][i], tied: i === 1,
    };
  });
  return { team_attributes: attrs, measures: measures, updated_after_week: 12, plays_data: {}, scouting_data: {} };
}

function scoutingReport() {
  const five = players(OPP).slice(0, 5).map(function (p) {
    const display = {};
    Object.keys(p.attributes).forEach(function (key) { display[key] = Math.floor(p.attributes[key] / 10); });
    return {
      player_id: p._id, position: p.position, name: p.name, jersey: p.jersey, year: p.year.toLowerCase(),
      height: p.height, weight: p.weight, rt: p.rt, potential_rt_ratcheted: p.potential_rt_ratcheted, attributes: display,
    };
  });
  const stats = {};
  five.forEach(function (p, i) {
    stats[p.player_id] = {
      PTS: 18.6 - i * 2.1, FGM: 6.8 - i * 0.7, FGA: 14.1 - i * 1.2, 'FG%': 48.1 - i, '3PTM': 2.2 - i * 0.4, '3PTA': 5.8 - i,
      '3PT%': 37.9 - i * 2, FTM: 2.9 - i * 0.3, FTA: 3.7 - i * 0.3, 'FT%': 78.4 - i * 2, DREB: 2.9 + i, OREB: 0.6 + i * 0.5,
      TREB: 3.5 + i * 1.5, AST: 5.4 - i, STL: 1.5 - i * 0.2, BLK: 0.2 + i * 0.4, F: 2.1 + i * 0.2, MIN: 31 - i * 1.5, TO: 2.4 - i * 0.3,
    };
  });
  return {
    projected_starting_five: five, player_season_stats: stats,
    play_usage_unlocked: true, fast_break_usage_unlocked: true, hct_usage_unlocked: true,
    plays: [
      { name: '4-1 Motion', times_run: 86, successes: 46 },
      { name: '5-0 Flex', times_run: 64, successes: 31 },
      { name: 'Horns Flare', times_run: 41, successes: 22 },
      { name: 'Double Drag', times_run: 28, successes: 11 },
    ],
    fast_break_plays: [{ name: 'Pitch Ahead', times_run: 19, successes: 12 }],
    hct_trap_plays: [{ name: 'Corner Trap', times_run: 14, successes: 6 }],
  };
}

function practiceSquad(kind, week) {
  const labels = { 1: 'All-Americans', 2: 'All-Stars', 3: 'Varsity', 4: 'JV', 5: 'Squad' };
  const names = {};
  const tiers = [1, 2, 3, 4, 5].map(function (tier) {
    return {
      tier: String(tier), label: labels[tier],
      rows: REGIONS.map(function (letter, i) {
        const id = 'ps_' + letter + '_' + tier;
        names[id] = { display_name: 'Region ' + letter + ' ' + labels[tier] };
        const w = Math.max(0, 9 - ((i * 3 + tier) % 8));
        return { team_id: id, name: names[id].display_name, w: w, l: 10 - w, win_pct: w / 10, is_user: letter === USER.region };
      }).sort(function (a, b) { return b.w - a.w; }),
    };
  });
  if (kind === 'standings') return { initialized: true, week: 12, tiers: tiers, teams: names };
  if (kind === 'brackets') return { initialized: true, week: 12, tournaments: {}, championship: {}, teams: names };
  if (week == null) {
    const weeks = [];
    for (let w = 2; w <= 19; w += 1) weeks.push(w);
    return { initialized: true, week: 12, current_week: 12, weeks: weeks };
  }
  const games = [];
  [1, 2, 3, 4, 5].forEach(function (tier) {
    for (let i = 0; i < 8; i += 2) {
      games.push({
        away_team_id: 'ps_' + REGIONS[i] + '_' + tier, away_display: 'Region ' + REGIONS[i] + ' ' + labels[tier],
        home_team_id: 'ps_' + REGIONS[i + 1] + '_' + tier, home_display: 'Region ' + REGIONS[i + 1] + ' ' + labels[tier],
        status: 'completed', away_score: 60 + i + tier, home_score: 66 - i + tier, game_id: 'ps-' + tier + '-' + i,
      });
    }
  });
  return { initialized: true, week: Number(week), games: games };
}

/** Four weeks of stories, several per week, so the feed needs breaking up. */
function news() {
  const out = { news: [], dispatches: [] };
  const kinds = [
    ['upset_report', 'Upset Report'], ['recruiting_report', 'Recruiting Report'], ['ps_game_results', 'Practice Squad Results'],
    ['recruiting_leans', 'Recruiting Leans'], ['ps_all_stars', 'Practice Squad All-Stars'],
  ];
  for (let week = 12; week >= 9; week -= 1) {
    kinds.forEach(function (kind, i) {
      if (week === 9 && i > 2) return;
      out.news.push({
        story_id: 'w' + week + '-' + kind[0], type: kind[0], headline: 'Week ' + week + ' ' + kind[1], week: week,
        yours: i === 1 && week % 2 === 0,
        // The Practice Squad All-Stars story carries a roster table.
        rich_lines: kind[0] === 'ps_all_stars'
          ? [{ type: 'heading', text: 'All-Stars' }, {
            type: 'player_table',
            players: players(USER).slice(0, 6).map(function (p) {
              return { name: p.name, pos: p.position, year: p.year, height: p.height, weight: p.weight, attributes: p.attributes, rt: p.rt };
            }),
          }]
          : [{ type: 'heading', text: kind[1] }],
      });
    });
    const opp = opponentOf(USER, week);
    out.dispatches.push({
      type: 'game_result', headline: USER.name + ' defeated ' + opp.name + ' ' + (70 + week) + '-' + (58 + week),
      target: '/box-score.html?game_id=g-' + week, week: week, yours: true,
    });
    out.dispatches.push({ type: 'training_report', headline: 'Week ' + week + ' training report', target: '/training-report.html?week=' + week, week: week, yours: true });
  }
  return out;
}

/**
 * Week 27, exactly as the server stores it the moment the conference brackets are drawn
 * (`initialize_conference_tournaments`): round 1 unplayed, `score: {}`, no game id, and the
 * later rounds empty. The older spec only covered brackets with results filled in.
 */
function brackets(week) {
  const tournaments = {};
  const teams = {};
  for (let conf = 1; conf <= 16; conf += 1) {
    const list = conferenceTeams(conf).slice().sort(function (a, b) { return b.W - a.W || a.natl_rank - b.natl_rank; });
    const seeds = {};
    list.forEach(function (team, i) {
      seeds[team.team_id] = i + 1;
      teams[team.team_id] = { name: team.name, mascot: null, conference: conf, region: team.region, natl_rank: team.natl_rank, W: team.W, L: team.L, logo: team.name };
    });
    const pair = function (hi, lo) { return { home_team: list[hi].team_id, away_team: list[lo].team_id, game_id: null, winner: null, score: {} }; };
    tournaments[String(conf)] = {
      bracket: { round1: [pair(0, 7), pair(3, 4), pair(1, 6), pair(2, 5)], round2: [], final: [] },
      current_round: 1, seeds: seeds, champion: null,
    };
  }
  return {
    week: week, first_week: 27, locked: week < 27, current_phase: week >= 27 ? 'conference' : null,
    round_labels: {
      conference: { round1: 'Quarterfinal', round2: 'Semifinal', final: 'Final' },
      region: { round1: 'Semifinal', final: 'Final' },
      national: { round1: 'Quarterfinal', round2: 'Semifinal', final: 'Final' },
    },
    phase_draw_week: { conference: 27, region: 30, national: 32 },
    conference_tournaments: week >= 27 ? tournaments : {},
    region_tournaments: {}, national_tournament: {}, eos_tournament: null,
    teams: teams, user_team_id: TID, user_conference: USER.conference, user_region: USER.region,
    user_eliminated: false, eliminated_in_round: null, has_eos_game_this_week: week === 27, has_bye_this_week: false,
    region_qualified: false, tournament_complete: false, champion: null, region_tournaments_stale: false,
  };
}

function commandCenter(week) {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, user_team_object_id: TID,
    team: USER.name, week: week, rank: USER.natl_rank, season: 1, current_season: 1,
    training_completed: true, session_type: 'in-season', cut_required: false,
    eos_tournament_active: week >= 27,
    region_bye_modal_eligible: false,
    conference_rs_region_modal: { eligible: false }, bracket_reveal_modal: { eligible: false },
    bracket_update_modal: { eligible: false }, recruiting_results_modal: { eligible: false },
    walk_on_welcome_modal: { eligible: false },
    recruiting_wire: { board_saved_week: week, counts: {}, events: [] },
    user_conference: USER.conference, user_region: USER.region,
    team_record: { wins: USER.W, losses: USER.L },
    rankings: rankings(),
    next_game_summary: { week: week, matchup_label: 'vs', opponent_team_id: OPP.team_id, opponent_team_name: OPP.name },
  };
}

/** Week 36 results: every conference has eight teams, some of which signed nobody. */
function recruitingResults() {
  const byTeam = {};
  const names = {};
  LEAGUE.teams.forEach(function (team) { byTeam[team.team_id] = team.conference; names[team.team_id] = team.name; });
  const signed = [];
  const years = ['JH', 'Freshman', 'Sophomore', 'Junior'];
  LEAGUE.teams.forEach(function (team, t) {
    const count = team === USER ? 4 : (t % 7 === 3 ? 0 : 1 + (t % 4));
    for (let i = 0; i < count; i += 1) {
      const rt = 92 - ((t * 5 + i * 9) % 55);
      signed.push({
        player_id: 'p-' + t + '-' + i, recruit_id: 'r-' + t + '-' + i, image_id: 'img-' + t + '-' + i,
        name: FIRST[(t + i) % FIRST.length] + ' ' + LAST[(t * 3 + i) % LAST.length],
        pos: POS[(t + i) % 5], rt: rt, potential_rt_ratcheted: Math.min(99, rt + 6),
        year: years[(t + i) % 4], team_id: team.team_id, team_name: team.name,
      });
    }
  });
  const sister = USER.conference % 2 ? USER.conference + 1 : USER.conference - 1;
  const lead = [USER.conference, sister];
  const order = lead.concat(Array.from({ length: 16 }, function (_, i) { return i + 1; }).filter(function (c) { return lead.indexOf(c) === -1; }));
  const regionByTeam = {};
  LEAGUE.teams.forEach(function (team) { regionByTeam[team.team_id] = team.region; });
  return {
    team: USER.name, team_id: TID, team_region: USER.region, week: 36, season: 1,
    recruits: [], team_name_map: names, saved_orders: {}, watchlist: [], saved_order_entries_week_35: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: { signed_players: signed },
    week_35_recruiting_ran: true, week_35_reveal_seen: true,
    conferences: {
      user_conference: USER.conference, sister_conference: sister, order: order, by_team_id: byTeam,
      user_region: USER.region, region_by_team_id: regionByTeam,
      region_team_ids: LEAGUE.teams.filter(function (team) { return team.region === USER.region; }).map(function (team) { return team.team_id; }).sort(),
    },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

/**
 * `state.week` is the franchise week. `state.byes === false` drops the bye fields, which is
 * what a server without them sends.
 */
async function installApi(page, state) {
  await page.route('**/*', async (route) => {
    let url;
    try { url = new URL(route.request().url()); } catch (err) { await route.continue(); return; }
    const pathname = url.pathname;
    const q = url.searchParams;
    if (pathname.indexOf('/images/players/') !== -1 || pathname.indexOf('/images/recruits/') !== -1) {
      await route.fulfill({ status: 404, body: '' });
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/') || pathname.startsWith('/recruit/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    const week = state.week || 13;
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') {
      return fulfillJson(route, LEAGUE.teams.map(function (team) {
        return { name: team.name, display_name: team.name, object_id: team.team_id, _id: team.team_id };
      }));
    }
    if (pathname.startsWith('/franchise/command-center/data')) return fulfillJson(route, commandCenter(week));
    if (pathname.startsWith('/franchise/recruiting-data')) return fulfillJson(route, recruitingResults());
    if (pathname.startsWith('/franchise/standings')) return fulfillJson(route, standings());
    if (pathname.startsWith('/franchise/leaders')) return fulfillJson(route, leaders(Number(q.get('limit') || '10'), q.get('view_scope') || 'national'));
    if (pathname.startsWith('/franchise/team-stats')) return fulfillJson(route, teamStats(q.get('scope') || ''));
    if (pathname.startsWith('/franchise/schedule/week')) {
      const asked = q.get('week') ? Number(q.get('week')) : week;
      return fulfillJson(route, asked === 30 ? regionWeek() : regularWeek(asked, week));
    }
    if (pathname.startsWith('/franchise/player-stats')) return fulfillJson(route, playerStats(q.get('team_id')));
    if (pathname.startsWith('/franchise/team-detail')) return fulfillJson(route, teamDetail(q.get('team_id')));
    if (pathname.startsWith('/franchise/team-data')) return fulfillJson(route, teamData(q.get('team_id')));
    if (pathname.startsWith('/franchise/scouting-report')) return fulfillJson(route, scoutingReport());
    if (pathname.startsWith('/franchise/practice-squad/standings')) return fulfillJson(route, practiceSquad('standings'));
    if (pathname.startsWith('/franchise/practice-squad/brackets')) return fulfillJson(route, practiceSquad('brackets'));
    if (pathname.startsWith('/franchise/practice-squad/schedule')) return fulfillJson(route, practiceSquad('schedule', q.get('week')));
    if (pathname.startsWith('/franchise/tournament/brackets')) return fulfillJson(route, brackets(week));
    if (pathname.startsWith('/franchise/news')) return fulfillJson(route, news());
    if (pathname.startsWith('/roster/')) return fulfillJson(route, roster(decodeURIComponent(pathname.split('/')[2] || '')));
    return fulfillJson(route, {});
  });
}

module.exports = {
  FID, TID, USER, OPP, LEAGUE, BY_ID, REGIONS, ATTRS,
  installApi, conferenceTeams, recruitingResults, regionWeek, standings, brackets,
};
