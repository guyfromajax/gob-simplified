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

/**
 * Build presentation team meta + core identity for score sampling.
 *
 * Dual-use (§3.1a): score{} / box keys stay on core ``name``; chrome fields
 * (teamName, name, abbr) use display_name || name. Core is returned separately
 * so it is not mistaken for a render label.
 */
function buildTeams(summary, homeRoster, awayRoster, homeTeamName, awayTeamName) {
  const teamsObj = (summary && summary.teams) || {};
  const homeId = nid(summary && summary.home_team_id);
  const awayId = nid(summary && summary.away_team_id);
  const homeT = teamsObj[homeId] || {};
  const awayT = teamsObj[awayId] || {};

  const coreOf = (t, fallback) => t.name || fallback || 'Team';
  const labelOf = (t, fallback) => t.display_name || t.name || fallback || 'Team';
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
  const abbrOf = (t, label) =>
    t.abbreviation || t.abbr || abbrFromName(label);

  const hCore = coreOf(homeT, homeTeamName);
  const aCore = coreOf(awayT, awayTeamName);
  const hLabel = labelOf(homeT, homeTeamName);
  const aLabel = labelOf(awayT, awayTeamName);

  return {
    teams: {
      home: {
        teamName: hLabel,
        name: hLabel,
        abbr: abbrOf(homeT, hLabel),
        color: colorOf(homeT, homeRoster, '#1F8A5B'),
        rank: rankOf(homeT, homeRoster),
        rec: recOf(homeT, homeRoster),
      },
      away: {
        teamName: aLabel,
        name: aLabel,
        abbr: abbrOf(awayT, aLabel),
        color: colorOf(awayT, awayRoster, '#9E1B32'),
        rank: rankOf(awayT, awayRoster),
        rec: recOf(awayT, awayRoster),
      },
    },
    homeCore: hCore,
    awayCore: aCore,
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
  const built = buildTeams(
    last,
    ctx.homeRoster,
    ctx.awayRoster,
    ctx.homeTeamName,
    ctx.awayTeamName
  );
  const teams = built.teams;
  // Directory grows across quarters (bench players appear as they check in).
  // RT rides on each player entry (payload `rt`, backend Chunk 0).
  const directory = {};
  summaries.forEach((s) => Object.assign(directory, buildDirectory(s)));

  // Core identity for score{} sampling only — never render these.
  const homeName = built.homeCore;
  const awayName = built.awayCore;

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

  // 5a fix: turns[] is CUMULATIVE across the per-quarter responses (backend caches
  // gm in ongoing_games; turns clear only for a new Q1). The FINAL response's
  // turns[] already contains the whole game — use it as the single source instead
  // of concatenating (which replayed Q1 four times, Q2 three times, ...).
  const allTurns = Array.isArray(last.turns) ? last.turns : [];

  // Sim Rest of Game: only emit playback frames from this quarter onward (join at
  // Q2+). Earlier quarters still accumulate stats/score/worm below so the join is
  // correct (carried score + cumulative stats), with no replay of already-played
  // quarters. Sim Full Game passes 1 (whole game).
  const startQuarter = Math.max(1, num(ctx.startQuarter) || 1);

  // Per-quarter emitted cumulative snapshots for reconciliation. Each response is
  // cumulative through the quarter it simmed; key by that quarter number.
  const emittedByQuarter = {};
  summaries.forEach((s) => {
    const ts = Array.isArray(s.turns) ? s.turns : [];
    let q = 0;
    ts.forEach((t) => { q = Math.max(q, num(t.quarter)); });
    if (q > 0 && Array.isArray(s.players)) emittedByQuarter[q] = s.players;
  });

  const reconcileQuarter = (q) => {
    const emitted = emittedByQuarter[q];
    if (!Array.isArray(emitted)) return;
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
            quarter: q, playerId: id, name: (directory[id] || {}).name,
            stat: key, accumulated: acc, emitted: emit, delta: acc - emit,
          });
          accStats[key] = emit; // emitted wins — snap display state to authoritative
          cum[id] = accStats;
        }
      });
    });
  };

  // 5b fix: helper turns (inbound / rebound / timeout) omit `score` — carry forward
  // the last known scoreboard values instead of resetting to 0-0 / 0:00.
  const sb = {
    away: 0, home: 0, clock: (openTurn && openTurn.clock) || '8:00', quarter: 1, shot: 24,
    atol: timeoutsFor(last, last && last.away_team_id),
    htol: timeoutsFor(last, last && last.home_team_id),
  };
  const applyTurnToScoreboard = (turn) => {
    const s = (turn && turn.score) || null;
    if (s && (s[homeName] != null || s[awayName] != null)) {
      sb.away = num(s[awayName]);
      sb.home = num(s[homeName]);
    }
    if (turn && turn.clock) sb.clock = turn.clock;
    if (turn && turn.quarter != null) sb.quarter = num(turn.quarter);
    if (turn && turn.shot_clock_remaining != null) sb.shot = num(turn.shot_clock_remaining);
  };
  const scoreSnapshot = () => ({
    away: sb.away, home: sb.home, clock: sb.clock,
    quarter: quarterLabel(sb.quarter), shot: sb.shot,
    afoul: teamFouls('away'), hfoul: teamFouls('home'),
    atol: sb.atol, htol: sb.htol,
  });

  // ── Pre-tip frame ──────────────────────────────────────────────────────
  // Tip-off zero-state only makes sense when starting at Q1 (Sim Full Game); a
  // mid-game Sim Rest join begins directly at its quarter's first frame.
  if (openTurn && startQuarter <= 1) {
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

  // ── Live frames from the single cumulative stream (final response) ─────
  let curQuarter = openTurn ? (num(openTurn.quarter) || 1) : 1;
  let lastHomeLineup = null;
  let lastAwayLineup = null;
  allTurns.forEach((turn, idx) => {
    // Quarter boundary FIRST — reconcile the quarter that just ended BEFORE this
    // turn's deltas land (§4: reconcile at every boundary + final). Otherwise the
    // new quarter's first delta corrupts the previous quarter's check.
    const tQ = num(turn.quarter) || curQuarter;
    if (tQ > curQuarter) {
      reconcileQuarter(curQuarter);
      if (frames.length) {
        const prev = frames[frames.length - 1];
        const spot = computeSpotlight(Array.from(everPlayed));
        const spotDir = directory[spot] || {};
        prev.breakSummary = {
          summaryQ: quarterLabel(curQuarter),
          summaryAway: prev.score.away,
          summaryHome: prev.score.home,
          summaryNote: spot ? `Top performer — ${spotDir.name}, ${num((cum[spot] || {}).PTS)} PTS` : '',
        };
      }
      curQuarter = tQ;
    }

    addDeltas(turn.deltas);

    // Foul-out tracking (persist).
    const foId = nid(turn.foul_out_player || (turn.fouled_out && turn.fouled_out.player_id));
    if (foId) fouledOut.add(foId);

    applyTurnToScoreboard(turn);

    // Bug 4 fix: helper turns (inbound / rebound / timeout) omit the lineups — carry
    // forward the last known five so on-court stats hold instead of the bars pulsing
    // to 0 on those turns.
    const homeLineup =
      turn.home_lineup && Object.keys(turn.home_lineup).length ? turn.home_lineup : (lastHomeLineup || {});
    const awayLineup =
      turn.away_lineup && Object.keys(turn.away_lineup).length ? turn.away_lineup : (lastAwayLineup || {});
    lastHomeLineup = homeLineup;
    lastAwayLineup = awayLineup;
    const homeCourt = onCourtIds(homeLineup);
    const awayCourt = onCourtIds(awayLineup);
    const court = [...homeCourt, ...awayCourt];
    court.forEach((id) => everPlayed.add(id));

    // Worm history spans the whole game (context even when we join mid-game at Q2+).
    worm.push(sb.home - sb.away);

    // Emit playback frames only from startQuarter onward (Sim Rest joins at Q2+).
    if (tQ >= startQuarter) {
      // Subs IN this frame = on court now, not on court previous frame.
      const subIds = new Set();
      if (prevCourt) court.forEach((id) => { if (!prevCourt.has(id)) subIds.add(id); });
      // OUT: fouled-out player still on the row for the beat before the swap.
      const outIds = new Set(court.filter((id) => fouledOut.has(id)));

      const momentumMap = turn.player_momentum || {};
      const spotlightId = computeSpotlight(court);

      const isLast = idx === allTurns.length - 1;
      const frame = {
        phase: isLast ? 'final' : 'live',
        quarter: tQ,
        score: scoreSnapshot(),
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
      if (isLast) {
        frame.final = { home_won: sb.home > sb.away, summaryAway: sb.away, summaryHome: sb.home };
      }
      frames.push(frame);
      prevCourt = new Set(court);
    }
  });

  reconcileQuarter(curQuarter); // final quarter

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
