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
 * Frame shape (slice 1):
 *   { phase, quarter, score:{...},
 *     worm:{ samples:[{elapsed,margin}], elapsed, domain, progress },
 *     teamPanel:{ away:{reb,to,fb,paint,fgm,fga,fgPct,tpm,fouls}, home:{...} },
 *     away:[p×5], home:[p×5], benchAway:[c], benchHome:[c],
 *     events:[{id,kind,last}]  — what happened this turn, for the card engine,
 *     ticker:null, breakSummary?, final? }
 *   player p: { id,pos,name,jersey,rt,pts,reb,ast,def,fouls,hot,cold,out,sub,spot }
 *   bench chip c: { name,pts,reb,out }
 */

import { calculatePotgPoints } from '../../shared/potg.js';
import { readableTeamPresentationColor } from './matchupsUiShared.js';
import {
  REG_Q_SEC,
  elapsedGameSeconds,
  wormDomainSeconds,
} from './simWormTime.js';

export { REG_Q_SEC, OT_Q_SEC, clockToSeconds, elapsedGameSeconds, wormDomainSeconds } from './simWormTime.js';

const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const MO_GLYPH_THRESHOLD = 4; // |MO| >= 4 → hot/cold glyph — matches existing MO_GLYPH_THRESHOLD (gameScene.js:221), the ±5-scale box-score convention

const nid = (v) => (v == null ? '' : String(v));

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Snapshot the seven team-panel stats from an emitted team_totals row. */
function teamPanelFromTotals(row) {
  const r = row || {};
  const fgm = num(r.FGM);
  const fga = num(r.FGA);
  return {
    reb: num(r.REB) || num(r.OREB) + num(r.DREB),
    to: num(r.TO),
    fb: num(r.FB_PTS),
    paint: num(r.PIP),
    fgm,
    fga,
    fgPct: fga > 0 ? (fgm / fga) * 100 : 0,
    tpm: num(r['3PTM'] != null ? r['3PTM'] : r['3PM']),
    fouls: num(r.F),
  };
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

/** Short abbreviation fallback — overlay-aware via resolveTeamAbbreviation. */
function abbrFromName(name, teamId) {
  if (typeof resolveTeamAbbreviation === 'function') {
    return resolveTeamAbbreviation(name, teamId);
  }
  if (typeof deriveTeamAbbreviationFromName === 'function') {
    return deriveTeamAbbreviationFromName(name);
  }
  const clean = String(name || '').replace(/[^A-Za-z0-9]/g, '');
  return (clean.slice(0, 3) || '???').toUpperCase();
}

/**
 * Build presentation team meta + core identity for score sampling.
 *
 * Dual-use (§3.1a): score{} / box keys stay on core ``name``; chrome fields
 * (teamName, name, abbr, color) come from the total chrome snapshot
 * (lookupTeamChrome) — never summary.teams[].colors / roster.primary_color.
 */
function buildTeams(summary, homeRoster, awayRoster, homeTeamName, awayTeamName) {
  const teamsObj = (summary && summary.teams) || {};
  const homeId = nid(summary && summary.home_team_id);
  const awayId = nid(summary && summary.away_team_id);
  const homeT = teamsObj[homeId] || {};
  const awayT = teamsObj[awayId] || {};

  const coreOf = (t, fallback) => t.name || fallback || 'Team';
  const hCore = coreOf(homeT, homeTeamName);
  const aCore = coreOf(awayT, awayTeamName);

  const chromeOf = (core, teamRec, roster) => {
    const fb = {
      label: teamRec.display_name || core,
      primary_color:
        (roster && (roster.primary_color || roster.primary)) ||
        (teamRec.colors && teamRec.colors.primary_color) ||
        teamRec.primary_color,
      secondary_color:
        (roster && (roster.secondary_color || roster.secondary)) ||
        (teamRec.colors && teamRec.colors.secondary_color) ||
        teamRec.secondary_color,
      abbreviation: teamRec.abbreviation || teamRec.abbr,
      team_id: teamRec.team_id,
      object_id: teamRec.object_id || teamRec.team_object_id,
    };
    if (typeof lookupTeamChrome === 'function') {
      return lookupTeamChrome(core, fb);
    }
    return {
      core_name: core,
      label: fb.label || core,
      abbreviation:
        fb.abbreviation ||
        (typeof abbrFromName === 'function' ? abbrFromName(fb.label || core) : '???'),
      primary_color: fb.primary_color || null,
      secondary_color: fb.secondary_color || null,
      is_overlay: false,
    };
  };

  const hChrome = chromeOf(hCore, homeT, homeRoster);
  const aChrome = chromeOf(aCore, awayT, awayRoster);

  const rankOf = (t, roster) => num(t.natl_rank ?? (roster && roster.natl_rank) ?? 0);
  const recOf = (t, roster) => {
    const w = num(t.wins ?? (roster && roster.wins) ?? 0);
    const l = num(t.losses ?? (roster && roster.losses) ?? 0);
    return `${w}–${l}`;
  };

  return {
    teams: {
      home: {
        teamName: hChrome.label,
        name: hChrome.label,
        abbr: hChrome.abbreviation,
        color: readableTeamPresentationColor(
          hChrome.primary_color || '#1F8A5B',
          hChrome.secondary_color
        ),
        rank: rankOf(homeT, homeRoster),
        rec: recOf(homeT, homeRoster),
      },
      away: {
        teamName: aChrome.label,
        name: aChrome.label,
        abbr: aChrome.abbreviation,
        color: readableTeamPresentationColor(
          aChrome.primary_color || '#9E1B32',
          aChrome.secondary_color
        ),
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

  /**
   * Notable per-player events for this turn, read straight off the emitted deltas.
   *
   * The card engine needs to know WHAT just happened; the assembler already carries the
   * numbers, so this classifies them rather than deriving anything new. A Moment card is a
   * running-total readout off one of these — never a described play (brief §8).
   *
   * `last` is the increment that triggered it, which the copy pack's {LAST} slot fills.
   */
  const turnEvents = (deltas) => {
    if (!deltas || typeof deltas !== 'object') return [];
    const out = [];
    Object.entries(deltas).forEach(([pid, entry]) => {
      const id = nid(pid);
      const st = (entry && entry.stats) || {};
      const d = (k) => num(st[k]);
      const fgm = d('FGM');
      const fga = d('FGA');
      const tpm = num(st['3PTM'] != null ? st['3PTM'] : st['3PM']);
      const boards = d('OREB') + d('DREB');
      if (tpm > 0) out.push({ id, kind: 'three', last: 3 });
      else if (fgm > 0) out.push({ id, kind: d('PIP') > 0 ? 'paint' : 'bucket', last: d('PTS') || 2 });
      if (fga > fgm) out.push({ id, kind: 'miss', last: fga - fgm });
      if (boards > 0) out.push({ id, kind: 'board', last: boards });
      if (d('AST') > 0) out.push({ id, kind: 'dime', last: d('AST') });
      if (d('STL') + d('BLK') > 0) out.push({ id, kind: 'stock', last: d('STL') + d('BLK') });
      if (d('F') > 0) out.push({ id, kind: 'foul', last: d('F') });
    });
    return out;
  };

  const teamOf = (id) => (directory[id] && directory[id].team) || null;
  const everPlayed = new Set(); // ids seen on court at any point
  const exitOrder = new Map(); // id -> tick of the turn they last left the floor
  let exitTick = 0;

  const worm = []; // { elapsed, margin }[] — x is game time, never sample index
  const frames = [];
  const reconciliation = { checks: 0, drifts: [] };
  let teamPanel = {
    away: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, fgPct: 0, tpm: 0, fouls: 0 },
    home: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, fgPct: 0, tpm: 0, fouls: 0 },
  };
  let maxQuarterSeen = 1;

  const applyTeamTotals = (turn) => {
    const tt = turn && turn.team_totals;
    if (!tt || typeof tt !== 'object') return;
    if (tt[awayName]) teamPanel = { ...teamPanel, away: teamPanelFromTotals(tt[awayName]) };
    if (tt[homeName]) teamPanel = { ...teamPanel, home: teamPanelFromTotals(tt[homeName]) };
  };

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
      stl: num(stats.STL),
      blk: num(stats.BLK),
      def: defPct(stats),
      defA: num(stats.DEF_A),
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
          id,
          name: dir.name || 'Unknown',
          pts: num(stats.PTS),
          reb: reb(stats),
          out: outIds.has(id),
        };
      })
      // Most-recent exit first: the rail answers "who just left the floor", so a
      // foul-out has to arrive at the head of it. Points break ties among players who
      // left on the same turn.
      .sort((a, b) => (exitOrder.get(b.id) || 0) - (exitOrder.get(a.id) || 0) || b.pts - a.pts);

  // Team fouls and timeouts are NOT derived here. Both are engine-owned and
  // emitted per turn (`home_team_fouls` / `away_team_fouls` / `home_timeouts` /
  // `away_timeouts`, stamped in GameManager._append_turn). Summing player F on
  // the client cannot reproduce the per-quarter team-foul reset, and a single
  // end-state timeout read spoils the whole broadcast with the final value.
  // We sample the emitted numbers and carry them forward; we never compute them.
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
    // Pre-tip defaults. Helper turns and any pre-stamp cached game omit the
    // emitted fields, so these are carry-forward seeds, not derivations.
    afoul: 0, hfoul: 0,
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
    // Emitted-only, carry forward when absent (helper turns / legacy payloads).
    if (turn && turn.away_team_fouls != null) sb.afoul = num(turn.away_team_fouls);
    if (turn && turn.home_team_fouls != null) sb.hfoul = num(turn.home_team_fouls);
    if (turn && turn.away_timeouts != null) sb.atol = num(turn.away_timeouts);
    if (turn && turn.home_timeouts != null) sb.htol = num(turn.home_timeouts);
  };
  const scoreSnapshot = () => ({
    away: sb.away, home: sb.home, clock: sb.clock,
    quarter: quarterLabel(sb.quarter), shot: sb.shot,
    afoul: sb.afoul, hfoul: sb.hfoul,
    atol: sb.atol, htol: sb.htol,
  });

  // TEAM FOULS on the panel is a WHOLE-GAME total, and deliberately not the same number
  // the scoreboard shows. The scoreboard reads the engine's `home_team_fouls` /
  // `away_team_fouls`, which reset every quarter because they drive the bonus. The panel
  // is a box score: it carries `team_totals[].F`, which the engine sums across all
  // players for the full game (team_manager.get_team_game_stats). Both are engine-owned
  // and merely sampled here — the FE still derives neither. This previously overrode the
  // game total with the per-quarter value, so the panel just mirrored the scoreboard.
  const teamPanelSnapshot = () => ({
    away: { ...teamPanel.away },
    home: { ...teamPanel.home },
  });

  const wormMeta = (elapsed) => {
    const domain = wormDomainSeconds(maxQuarterSeen);
    return {
      samples: worm.map((s) => ({ ...s })),
      elapsed,
      domain,
      progress: domain > 0 ? elapsed / domain : 0,
    };
  };

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
        // Tip-off is 0-0 on fouls by definition. Timeouts come from the opening
        // turn's emitted stamp; the summary read is a legacy fallback only (it
        // carries the END-of-quarter value, which would spoil the pre-tip frame).
        afoul: 0,
        hfoul: 0,
        atol: openTurn.away_timeouts != null
          ? num(openTurn.away_timeouts)
          : timeoutsFor(first, first.away_team_id),
        htol: openTurn.home_timeouts != null
          ? num(openTurn.home_timeouts)
          : timeoutsFor(first, first.home_team_id),
      },
      worm: wormMeta(0),
      teamPanel: {
        away: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, fgPct: 0, tpm: 0, fouls: 0 },
        home: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, fgPct: 0, tpm: 0, fouls: 0 },
      },
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
          summarySpotId: spot || null,
          summarySpotName: spot ? (spotDir.name || '') : '',
          summarySpotPts: spot ? num((cum[spot] || {}).PTS) : 0,
        };
      }
      curQuarter = tQ;
    }

    addDeltas(turn.deltas);

    // Foul-out tracking (persist).
    const foId = nid(turn.foul_out_player || (turn.fouled_out && turn.fouled_out.player_id));
    if (foId) fouledOut.add(foId);

    applyTurnToScoreboard(turn);
    applyTeamTotals(turn);
    maxQuarterSeen = Math.max(maxQuarterSeen, tQ);

    // Bug 4 fix: helper turns (inbound / rebound / timeout) omit the lineups — carry
    // forward the last known five so on-court stats hold instead of the bars pulsing
    // to 0 on those turns.
    // Bug 4 fix, extended: helper turns (inbound / rebound / free throws / timeout) may
    // omit the lineups entirely OR name only some of the five. A partial lineup used as-is
    // shrinks the on-court set, and everyone it failed to mention is read as having left
    // the floor — which is how still-playing starters turned up on the bench rail in Q1
    // with no foul-outs. Only a complete five replaces the last known one.
    const completeOr = (lineup, fallback) =>
      (onCourtIds(lineup).length === POSITIONS.length ? lineup : (fallback || lineup || {}));
    const homeLineup = completeOr(turn.home_lineup, lastHomeLineup);
    const awayLineup = completeOr(turn.away_lineup, lastAwayLineup);
    lastHomeLineup = homeLineup;
    lastAwayLineup = awayLineup;
    const homeCourt = onCourtIds(homeLineup);
    const awayCourt = onCourtIds(awayLineup);
    const court = [...homeCourt, ...awayCourt];
    court.forEach((id) => everPlayed.add(id));
    if (prevCourt) {
      exitTick += 1;
      prevCourt.forEach((id) => { if (!court.includes(id)) exitOrder.set(id, exitTick); });
    }

    // Worm history: elapsed game seconds (not sample index) + home−away margin.
    const elapsed = elapsedGameSeconds(sb.quarter, sb.clock);
    worm.push({ elapsed, margin: sb.home - sb.away });

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
        worm: wormMeta(elapsed),
        teamPanel: teamPanelSnapshot(),
        away: POSITIONS.map((pos) =>
          buildPlayer(nid(awayLineup[pos]), pos, momentumMap, spotlightId, subIds, outIds)
        ),
        home: POSITIONS.map((pos) =>
          buildPlayer(nid(homeLineup[pos]), pos, momentumMap, spotlightId, subIds, outIds)
        ),
        benchAway: benchChips(court, 'away', fouledOut),
        benchHome: benchChips(court, 'home', fouledOut),
        events: turnEvents(turn.deltas),
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
