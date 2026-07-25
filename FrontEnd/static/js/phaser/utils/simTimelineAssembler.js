/**
 * Sim Game Presentation — Timeline Assembler (Chunk 1).
 *
 * Pure, side-effect-free transform: the per-quarter `/api/simulate-quarter`
 * responses (each carrying that quarter's `turns[]`) → an ordered array of
 * broadcast FRAMES matching the prototype's `st` shape (sim-presentation.js).
 *
 * UESS COMPLIANCE (see UESS_System.md §1/§3): the FE is a pure renderer.
 * This module ONLY samples/accumulates values the engine already emitted. The
 * one risk is summing per-turn `deltas` into a running cumulative line — that
 * edges toward the FE owning "stats at time T". Guard (required by Prompt 2 §4):
 *   - accumulated totals are DISPLAY STATE ONLY, never authoritative;
 *   - at every quarter boundary and at final we RECONCILE against the emitted
 *     cumulative (`summary.players[].stats`); on any disagreement the EMITTED
 *     value wins (we snap to it) and we LOG the delta so silent drift surfaces.
 *
 * The renderer consumes `frames` + `teams`; it never sees a raw API shape.
 *
 * Frame (`st`) shape — mirrors sim-presentation.js:
 *   { phase, quarter, score:{away,home,clock,quarter,shot,atol,afoul,htol,hfoul},
 *     worm:[margin...], away:[p×5], home:[p×5], benchAway:[c], benchHome:[c],
 *     ticker:null,               // moments tabled (Prompt 2 §2) — slot stays empty
 *     breakSummary?, final? }
 *   player p: { pos,name,jersey,rt,pts,reb,ast,def,fouls,hot,cold,out,sub,spot }
 *   bench chip c: { name,pts,reb,out }
 */

import { calculatePotgPoints } from '../../shared/potg.js';

const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const MO_GLYPH_THRESHOLD = 4; // |MO| >= 4 → hot/cold glyph — matches existing MO_GLYPH_THRESHOLD (gameScene.js:221), the ±5-scale box-score convention

const nid = (v) => (v == null ? '' : String(v));

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

// RT source: the game payload now carries `rt` per player (backend Chunk 0,
// `_player_rt_max`) — the roster/game payload has no position_ratings to join
// against, so RT rides the same players[] the directory is built from. Missing or
// non-positive → null → badge renders empty (never guess a band).

/** {playerId → {name,jersey,team,pos,rt}} from a summary's top-level players[]. */
function buildDirectory(summary) {
  const dir = {};
  const players = Array.isArray(summary && summary.players) ? summary.players : [];
  players.forEach((p) => {
    const id = nid(p.playerId || p.player_id || p._id);
    if (!id) return;
    const rt = num(p.rt);
    dir[id] = {
      name: p.name || 'Unknown',
      jersey: p.jersey != null ? p.jersey : '',
      team: p.team === 'home' || p.team === 'away' ? p.team : null,
      pos: p.pos || null,
      rt: rt > 0 ? rt : null,
    };
  });
  return dir;
}

/** Short abbreviation fallback from a team name ("Four Corners" → "FC"). */
function abbrFromName(name) {
  const words = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '';
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.map((w) => w[0]).join('').slice(0, 3).toUpperCase();
}

/** Build the `T` team object (away/home meta) from a summary + rosters. */
function buildTeams(summary, homeRoster, awayRoster, homeTeamName, awayTeamName) {
  const teamsObj = (summary && summary.teams) || {};
  const homeId = nid(summary && summary.home_team_id);
  const awayId = nid(summary && summary.away_team_id);
  const homeT = teamsObj[homeId] || {};
  const awayT = teamsObj[awayId] || {};

  const nameOf = (t, fallback) => t.name || fallback || 'Team';
  const colorOf = (t, roster, fallback) =>
    (t.colors && t.colors.primary_color) ||
    t.primary_color ||
    (roster && roster.primary_color) ||
    fallback;
  const rankOf = (t, roster) => num(t.natl_rank ?? (roster && roster.natl_rank) ?? 0);
  const recOf = (t, roster) => {
    const w = num(t.wins ?? (roster && roster.wins) ?? 0);
    const l = num(t.losses ?? (roster && roster.losses) ?? 0);
    return `${w}–${l}`;
  };

  const hName = nameOf(homeT, homeTeamName);
  const aName = nameOf(awayT, awayTeamName);
  return {
    home: {
      teamName: hName,
      name: hName,
      abbr: homeT.abbr || abbrFromName(hName),
      color: colorOf(homeT, homeRoster, '#1F8A5B'),
      rank: rankOf(homeT, homeRoster),
      rec: recOf(homeT, homeRoster),
    },
    away: {
      teamName: aName,
      name: aName,
      abbr: awayT.abbr || abbrFromName(aName),
      color: colorOf(awayT, awayRoster, '#9E1B32'),
      rank: rankOf(awayT, awayRoster),
      rec: recOf(awayT, awayRoster),
    },
  };
}

function quarterLabel(q) {
  const n = num(q);
  return n > 4 ? `OT${n - 4}` : `Q${n}`;
}

/** Cumulative stat helpers keyed on the canonical box keys (PTS/OREB/DREB/AST/F/DEF_A/DEF_S…). */
function reb(stats) {
  return num(stats.REB) || num(stats.OREB) + num(stats.DREB);
}
function defPct(stats) {
  const a = num(stats.DEF_A);
  return a > 0 ? Math.round((num(stats.DEF_S) / a) * 100) : 0;
}

/**
 * Assemble the broadcast timeline.
 *
 * @param {Array<object>} quarterSummaries  ordered `/api/simulate-quarter` responses (Q1..final)
 * @param {object} ctx  { homeRoster, awayRoster, homeTeamName, awayTeamName }
 * @returns {{ teams, frames, meta }}
 */
export function buildSimTimeline(quarterSummaries, ctx = {}) {
  const summaries = (quarterSummaries || []).filter((s) => s && typeof s === 'object');
  const last = summaries[summaries.length - 1] || {};
  const teams = buildTeams(
    last,
    ctx.homeRoster,
    ctx.awayRoster,
    ctx.homeTeamName,
    ctx.awayTeamName
  );
  // Directory grows across quarters (bench players appear as they check in).
  // RT rides on each player entry (payload `rt`, backend Chunk 0).
  const directory = {};
  summaries.forEach((s) => Object.assign(directory, buildDirectory(s)));

  const homeName = teams.home.teamName;
  const awayName = teams.away.teamName;

  // Running, DISPLAY-ONLY cumulative per player: { playerId: { STAT: value } }.
  const cum = {};
  const addDeltas = (deltas) => {
    if (!deltas || typeof deltas !== 'object') return;
    Object.entries(deltas).forEach(([pid, entry]) => {
      const id = nid(pid);
      const stats = (entry && entry.stats) || {};
      const bucket = (cum[id] = cum[id] || {});
      Object.entries(stats).forEach(([k, v]) => {
        if (k === 'REB' || k === 'Outlet_Score_List' || k === 'Shot_Result_List') return;
        bucket[k] = num(bucket[k]) + num(v);
      });
    });
  };

  const teamOf = (id) => (directory[id] && directory[id].team) || null;
  const everPlayed = new Set(); // ids seen on court at any point

  const worm = [];
  const frames = [];
  const reconciliation = { checks: 0, drifts: [] };

  // Synthetic pre-tip zero frame (phase pretip) from the opening lineup of Q1.
  const first = summaries[0] || {};
  const firstTurns = Array.isArray(first.turns) ? first.turns : [];
  const openTurn = firstTurns[0];

  const buildPlayer = (id, pos, momentumMap, spotlightId, subIds, outIds) => {
    const stats = cum[id] || {};
    const dir = directory[id] || {};
    const mo = num(momentumMap[id]);
    const rt = dir.rt != null ? dir.rt : null; // payload RT (Chunk 0); null → badge empty (never guess)
    return {
      id, // playerId — for the real-headshot lookup (API_CONFIG.getPlayerImageUrl)
      pos,
      name: dir.name || 'Unknown',
      jersey: dir.jersey != null ? dir.jersey : '',
      rt,
      pts: num(stats.PTS),
      reb: reb(stats),
      ast: num(stats.AST),
      def: defPct(stats),
      fouls: num(stats.F),
      hot: mo >= MO_GLYPH_THRESHOLD,
      cold: mo <= -MO_GLYPH_THRESHOLD,
      out: outIds.has(id),
      sub: subIds.has(id),
      spot: spotlightId === id,
    };
  };

  const onCourtIds = (lineup) =>
    POSITIONS.map((pos) => nid(lineup && lineup[pos])).filter(Boolean);

  const computeSpotlight = (ids) => {
    let best = null;
    let bestScore = -Infinity;
    ids.forEach((id) => {
      const res = calculatePotgPoints({ stats: cum[id] || {} });
      if (res.score > bestScore) {
        bestScore = res.score;
        best = id;
      }
    });
    return best;
  };

  const benchChips = (courtIds, teamKey, outIds) =>
    Array.from(everPlayed)
      .filter((id) => teamOf(id) === teamKey && !courtIds.includes(id))
      .map((id) => {
        const stats = cum[id] || {};
        const dir = directory[id] || {};
        return {
          name: dir.name || 'Unknown',
          pts: num(stats.PTS),
          reb: reb(stats),
          out: outIds.has(id),
        };
      })
      // stable, readable order: highest scorers first
      .sort((a, b) => b.pts - a.pts);

  const teamFouls = (teamKey) =>
    Object.keys(cum).reduce(
      (sum, id) => (teamOf(id) === teamKey ? sum + num(cum[id].F) : sum),
      0
    );

  const timeoutsFor = (summary, teamId) => {
    const t = summary && summary.teams && summary.teams[nid(teamId)];
    return t && t.timeouts != null ? num(t.timeouts) : null;
  };

  // Track ids that have fouled out (persist across the game) and the previous
  // on-court set (to tag IN swaps).
  const fouledOut = new Set();
  let prevCourt = null;

  const makeScore = (turn, summary, teamFoulsFn) => {
    const s = (turn && turn.score) || {};
    const homePts = num(s[homeName]);
    const awayPts = num(s[awayName]);
    return {
      away: awayPts,
      home: homePts,
      clock: (turn && turn.clock) || '0:00',
      quarter: quarterLabel(turn && turn.quarter),
      shot: turn && turn.shot_clock_remaining != null ? num(turn.shot_clock_remaining) : 0,
      afoul: teamFoulsFn('away'),
      hfoul: teamFoulsFn('home'),
      // Timeouts: best-effort per-quarter value (not stamped per turn) — flagged as a bend.
      atol: timeoutsFor(summary, summary && summary.away_team_id),
      htol: timeoutsFor(summary, summary && summary.home_team_id),
    };
  };

  // ── Pre-tip frame ──────────────────────────────────────────────────────
  if (openTurn) {
    const homeCourt = onCourtIds(openTurn.home_lineup);
    const awayCourt = onCourtIds(openTurn.away_lineup);
    [...homeCourt, ...awayCourt].forEach((id) => everPlayed.add(id));
    const mo = {};
    frames.push({
      phase: 'pretip',
      quarter: num(openTurn.quarter) || 1,
      score: {
        away: 0,
        home: 0,
        clock: (openTurn.clock) || '8:00',
        quarter: quarterLabel(openTurn.quarter || 1),
        shot: 24,
        afoul: 0,
        hfoul: 0,
        atol: timeoutsFor(first, first.away_team_id),
        htol: timeoutsFor(first, first.home_team_id),
      },
      worm: [0],
      away: POSITIONS.map((pos, i) =>
        buildPlayer(nid(openTurn.away_lineup && openTurn.away_lineup[pos]), pos, mo, null, new Set(), new Set())
      ),
      home: POSITIONS.map((pos, i) =>
        buildPlayer(nid(openTurn.home_lineup && openTurn.home_lineup[pos]), pos, mo, null, new Set(), new Set())
      ),
      benchAway: [],
      benchHome: [],
      ticker: null,
    });
    prevCourt = new Set([...homeCourt, ...awayCourt]);
  }

  // ── Live frames, quarter by quarter ────────────────────────────────────
  summaries.forEach((summary, qIdx) => {
    const turns = Array.isArray(summary.turns) ? summary.turns : [];
    const isFinalQuarter = qIdx === summaries.length - 1 && summary.is_final;

    turns.forEach((turn, tIdx) => {
      addDeltas(turn.deltas);

      // Foul-out tracking (persist).
      const foId = nid(turn.foul_out_player || (turn.fouled_out && turn.fouled_out.player_id));
      if (foId) fouledOut.add(foId);

      const homeLineup = turn.home_lineup || {};
      const awayLineup = turn.away_lineup || {};
      const homeCourt = onCourtIds(homeLineup);
      const awayCourt = onCourtIds(awayLineup);
      const court = [...homeCourt, ...awayCourt];
      court.forEach((id) => everPlayed.add(id));

      // Subs IN this frame = on court now, not on court previous frame.
      const subIds = new Set();
      if (prevCourt) court.forEach((id) => { if (!prevCourt.has(id)) subIds.add(id); });

      // OUT flag: a player who fouled out this turn but still shows on the row
      // for the beat before the swap. On court + fouledOut → flash OUT.
      const outIds = new Set(court.filter((id) => fouledOut.has(id)));

      const momentumMap = turn.player_momentum || {};
      const spotlightId = computeSpotlight(court);

      const margin = num((turn.score || {})[homeName]) - num((turn.score || {})[awayName]);
      worm.push(margin);

      const isQuarterEnd = tIdx === turns.length - 1;
      let phase = 'live';
      if (isQuarterEnd && isFinalQuarter) phase = 'final';

      const frame = {
        phase,
        quarter: num(turn.quarter) || qIdx + 1,
        score: makeScore(turn, summary, teamFouls),
        worm: worm.slice(),
        away: POSITIONS.map((pos) =>
          buildPlayer(nid(awayLineup[pos]), pos, momentumMap, spotlightId, subIds, outIds)
        ),
        home: POSITIONS.map((pos) =>
          buildPlayer(nid(homeLineup[pos]), pos, momentumMap, spotlightId, subIds, outIds)
        ),
        benchAway: benchChips(court, 'away', fouledOut),
        benchHome: benchChips(court, 'home', fouledOut),
        ticker: null, // moments tabled — engine leaves the 44px slot empty
      };

      if (isQuarterEnd) {
        const awayPts = frame.score.away;
        const homePts = frame.score.home;
        if (isFinalQuarter) {
          frame.final = {
            home_won: homePts > awayPts,
            summaryAway: awayPts,
            summaryHome: homePts,
          };
        } else {
          // Top performer note across everyone who played, this quarter's cumulative.
          const spot = computeSpotlight(Array.from(everPlayed));
          const spotDir = directory[spot] || {};
          const spotPts = num((cum[spot] || {}).PTS);
          frame.breakSummary = {
            summaryQ: quarterLabel(turn.quarter),
            summaryAway: awayPts,
            summaryHome: homePts,
            summaryNote: spot ? `Top performer — ${spotDir.name}, ${spotPts} PTS` : '',
          };
        }
      }

      frames.push(frame);
      prevCourt = new Set(court);
    });

    // ── Reconciliation guard (Prompt 2 §4): quarter boundary + final ──────
    const emitted = Array.isArray(summary.players) ? summary.players : [];
    emitted.forEach((p) => {
      const id = nid(p.playerId || p.player_id || p._id);
      if (!id) return;
      const emittedStats = p.stats || {};
      const accStats = cum[id] || {};
      ['PTS', 'OREB', 'DREB', 'AST', 'STL', 'BLK', 'F', 'DEF_A', 'DEF_S', 'TO'].forEach((key) => {
        reconciliation.checks += 1;
        const acc = num(accStats[key]);
        const emit = num(emittedStats[key]);
        if (acc !== emit) {
          reconciliation.drifts.push({
            quarter: qIdx + 1,
            playerId: id,
            name: (directory[id] || {}).name,
            stat: key,
            accumulated: acc,
            emitted: emit,
            delta: acc - emit,
          });
          // Emitted wins — snap display state to the authoritative value.
          accStats[key] = emit;
          cum[id] = accStats;
        }
      });
    });
  });

  if (reconciliation.drifts.length) {
    console.warn(
      `⚠️ [SIM-PRES] Timeline reconciliation snapped ${reconciliation.drifts.length} stat(s) to the emitted authoritative value (FE accumulation drifted). Details:`,
      reconciliation.drifts
    );
  } else {
    console.log(
      `✅ [SIM-PRES] Timeline reconciliation clean across ${reconciliation.checks} checks (${frames.length} frames).`
    );
  }

  const homeWon =
    frames.length && frames[frames.length - 1].final
      ? frames[frames.length - 1].final.home_won
      : num((last.score || {})[homeName]) > num((last.score || {})[awayName]);

  return {
    teams,
    frames,
    meta: {
      quarters: summaries.length,
      frameCount: frames.length,
      homeWon,
      reconciliation,
    },
  };
}
