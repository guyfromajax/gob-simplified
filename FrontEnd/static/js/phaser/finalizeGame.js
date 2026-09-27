function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

const DEBUG_BRACKET = window.DEBUG_BRACKET || false;
const DEBUG_GAME_ID = window.DEBUG_GAME_ID || false;

// ✅ SS&S: Import shared status display utility
import { showStatus, hideStatus } from './utils/statusDisplay.js';

async function recoverFranchiseWeek(franchiseId) {
  if (!franchiseId || typeof fetch !== 'function' || typeof API_CONFIG === 'undefined') {
    return null;
  }

  const headers = {
    ...(API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}),
    'Cache-Control': 'no-cache',
  };

  const endpoints = [
    `/franchise/command-center/data?franchise_id=${encodeURIComponent(franchiseId)}&profile=1`,
    `/franchise/state?franchise_id=${encodeURIComponent(franchiseId)}&profile=1`,
  ];

  for (const path of endpoints) {
    try {
      const res = await fetch(API_CONFIG.buildUrl(path), { headers, cache: 'no-store' });
      if (!res.ok) continue;
      const data = await res.json();
      const recoveredWeek = parseInt(data?.week, 10);
      if (Number.isInteger(recoveredWeek) && recoveredWeek >= 1) {
        console.warn('[COMPLETE-WEEK TRACE] Recovered week from backend', {
          franchiseId,
          recoveredWeek,
          source: path,
        });
        return recoveredWeek;
      }
    } catch (error) {
      console.warn('[COMPLETE-WEEK TRACE] Failed to recover week from backend', {
        franchiseId,
        source: path,
        error: error?.message || String(error),
      });
    }
  }

  return null;
}

function idOfGameDoc(doc) {
  if (!doc || typeof doc !== 'object') return null;
  const raw = doc.game_id || doc._id;
  if (raw && typeof raw === 'object' && raw.$oid) return String(raw.$oid);
  if (raw == null || raw === '') return null;
  return String(raw);
}

function documentHasBoxPlayers(doc) {
  if (!doc || typeof doc !== 'object') return false;
  const rows = [];
  const take = (box) => {
    if (!box || typeof box !== 'object') return;
    Object.values(box).forEach((value) => {
      if (!value || typeof value !== 'object') return;
      if (value.playerId || value.player_id) rows.push(value);
      else take(value);
    });
  };
  const teams = doc.teams;
  if (teams && typeof teams === 'object') {
    Object.values(teams).forEach((team) => {
      if (team && typeof team === 'object') take(team.box_score);
    });
  }
  take(doc.box_score);
  return rows.length > 0;
}

function phaseAGameDocument(simData) {
  if (!simData || typeof simData !== 'object') return null;
  if (simData.final_game_document && documentHasBoxPlayers(simData.final_game_document)) {
    return simData.final_game_document;
  }
  if (documentHasBoxPlayers(simData)) return simData;
  return null;
}

function retryPhaseAWithBoxDocument(requestBody, playedDocument, postedGameId) {
  if (!playedDocument || !documentHasBoxPlayers(playedDocument)) return null;
  const boxId = idOfGameDoc(playedDocument);
  if (!boxId || String(boxId) === String(postedGameId)) return null;
  return {
    ...requestBody,
    game_id: boxId,
    game_document: playedDocument,
  };
}

async function postPhaseA(requestBody) {
  return fetch(API_CONFIG.buildUrl('/franchise/complete-week/phase-a'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  });
}

async function readPhaseAError(res) {
  let body = null;
  try {
    body = await res.json();
  } catch (error) {
    body = null;
  }
  const detail = body && body.detail;
  if (detail && typeof detail === 'object') {
    return {
      reason: detail.reason || null,
      message: detail.message || '',
    };
  }
  return { reason: null, message: typeof detail === 'string' ? detail : '' };
}

function clearStaleGameIdFromContext() {
  const ctx = franchiseCtx();
  if (!ctx || typeof ctx.set !== 'function') return;
  ['game_id', 'quarter', 'period', 'clock', 'resume_from_timeout', 'resume_from_anchor', 'consume_resume_anchor', 'active_resume', 'anchor_type', 'quarter_break_from'].forEach((key) => {
    try { ctx.set(key, null); } catch (error) { /* session may be unavailable */ }
  });
}

export async function finalizeGame({ simData, franchiseId, game }) {
  console.warn('[COMPLETE-WEEK TRACE] finalizeGame ENTRY', { hasSimData: !!simData, franchiseId });
  // ✅ UNIFIED STRUCTURE: Extract team names with priority: unified structure > backward compatibility
  // Unified structure: simData.teams[home_team_id].name (preferred)
  // Backward compatibility: simData.home_team (object with name) or simData.home_team (string) or simData.homeTeam (object)
  
  // Try unified structure first
  const homeTeamId = simData.home_team_id;
  const awayTeamId = simData.away_team_id;
  const teamsObj = simData.teams || {};
  
  let homeTeamObj = null;
  let awayTeamObj = null;
  
  // Priority 1: Unified structure (preferred)
  if (homeTeamId && teamsObj[homeTeamId]) {
    homeTeamObj = teamsObj[homeTeamId];
  }
  if (awayTeamId && teamsObj[awayTeamId]) {
    awayTeamObj = teamsObj[awayTeamId];
  }
  
  // Priority 2: Backward compatibility - old structure
  if (!homeTeamObj) {
    const homeTeamField = simData.home_team;
    homeTeamObj = typeof homeTeamField === 'object' ? homeTeamField : (simData.homeTeam || { name: homeTeamField });
  }
  if (!awayTeamObj) {
    const awayTeamField = simData.away_team;
    awayTeamObj = typeof awayTeamField === 'object' ? awayTeamField : (simData.awayTeam || { name: awayTeamField });
  }
  
  const homeKey = homeTeamObj?.name || homeTeamId || simData.home_team;
  const awayKey = awayTeamObj?.name || awayTeamId || simData.away_team;
  
  const scoreMap = simData.final_score || simData.score || {};
  // ✅ FIX: Prioritize scoreMap (updated scores) over nested object scores (may be stale from initialSimData)
  // This ensures that when "Sim Quarter" is used, we use correct final scores, not stale scores from initialSimData
  const homeScore = (scoreMap[homeKey] !== undefined && scoreMap[homeKey] !== null) 
    ? scoreMap[homeKey] 
    : (homeTeamObj.score ?? 0);
  const awayScore = (scoreMap[awayKey] !== undefined && scoreMap[awayKey] !== null)
    ? scoreMap[awayKey]
    : (awayTeamObj.score ?? 0);
  
  // Debug logging to trace score extraction
  if (DEBUG_GAME_ID || window.DEBUG_SCORES) {
    console.log('🏆 finalizeGame score extraction:', {
      homeKey,
      awayKey,
      scoreMap,
      homeTeamObjScore: homeTeamObj.score,
      awayTeamObjScore: awayTeamObj.score,
      finalHomeScore: homeScore,
      finalAwayScore: awayScore,
      source: {
        home: (scoreMap[homeKey] !== undefined && scoreMap[homeKey] !== null) ? 'scoreMap' : 'homeTeamObj',
        away: (scoreMap[awayKey] !== undefined && scoreMap[awayKey] !== null) ? 'scoreMap' : 'awayTeamObj'
      }
    });
  }
  const winner = homeScore > awayScore ? homeKey : awayKey;
  const params = liveParams();
  let week = NaN;
  const homeIdParam = params.get('home_id');
  const awayIdParam = params.get('away_id');

  // Franchise: prefer sim payload week over URL/localStorage so EOS complete-week matches
  // the slate the server simmed (stale ?week= or franchise_week can sit one week ahead).
  if (franchiseId) {
    if (simData?.final_game_document?.week != null) {
      week = parseInt(simData.final_game_document.week, 10);
    }
    if (!Number.isInteger(week) || week < 1) {
      if (simData?.week != null && simData.week !== '') {
        week = parseInt(simData.week, 10);
      }
    }
  }
  if (!Number.isInteger(week) || week < 1) {
    week = parseInt(params.get('week'), 10);
  }
  if (!Number.isInteger(week) || week < 1) {
    if (franchiseId && window.FranchiseLS) {
      week = window.FranchiseLS.getWeek(franchiseId);
    }
  }
  if (!Number.isInteger(week) || week < 1) {
    if (simData?.week != null && simData.week !== '') {
      week = parseInt(simData.week, 10);
    }
  }
  if ((!Number.isInteger(week) || week < 1) && simData?.final_game_document?.week != null) {
    week = parseInt(simData.final_game_document.week, 10);
  }
  if ((!Number.isInteger(week) || week < 1) && franchiseId) {
    week = await recoverFranchiseWeek(franchiseId);
    if (Number.isInteger(week) && week >= 1 && franchiseId && window.FranchiseLS) {
      window.FranchiseLS.setWeek(franchiseId, week);
    }
  }

  // POST to /franchise/complete-week if needed
  const canCompleteWeek = franchiseId && Number.isInteger(week) && week >= 1;
  if (!franchiseId) {
    console.warn('[COMPLETE-WEEK TRACE] Skipping complete-week: not franchise mode', { franchiseId });
  } else if (!canCompleteWeek) {
    console.warn('[COMPLETE-WEEK TRACE] Skipping complete-week: missing or invalid week', {
      week,
      fromUrl: params.get('week'),
      fromSimData: simData?.week,
      fromFinalDoc: simData?.final_game_document?.week,
    });
  }
  let franchiseCompleteWeekPayload = undefined;
  let franchisePhaseBPending = undefined;
  let franchisePhaseAOk = undefined;
  let finalScorePhaseABlocked = undefined;

  if (canCompleteWeek) {
    try {
      const team1Id =
        awayIdParam ||
        awayTeamObj.team_id ||
        awayTeamObj.teamId ||
        simData.away_team_id ||
        simData.awayTeamId ||
        awayTeamObj.name ||
        simData.away_team;
      const team2Id =
        homeIdParam ||
        homeTeamObj.team_id ||
        homeTeamObj.teamId ||
        simData.home_team_id ||
        simData.homeTeamId ||
        homeTeamObj.name ||
        simData.home_team;
      const playedDocument = phaseAGameDocument(simData);
      // The id that owns the box, not a session id left over from last week.
      const gameId = idOfGameDoc(playedDocument) || simData.game_id || simData._id;
      const quarter = simData.quarter || simData.quarters || 'N/A';
      const isFinal = simData.is_final || false;
      console.log(
        `📡 Saving franchise game: franchiseId=${franchiseId}, week=${week}, game_id=${gameId}, quarter=${quarter}, is_final=${isFinal}, away=${awayTeamObj.name}, home=${homeTeamObj.name}`
      );
      console.log(`🔍 [FRONTEND] finalizeGame() called with simData: game_id=${gameId}, quarter=${quarter}, is_final=${isFinal}`);
      // ✅ FIX: Pass game_document if available (from simulate-quarter when is_final=True)
      const requestBody = {
        franchise_id: franchiseId,
        week: week,
        game_id: gameId,
        result: {
          team1_id: team1Id,
          team2_id: team2Id,
          team1_score: awayScore,
          team2_score: homeScore,
        },
      };

      if (playedDocument) {
        console.log('✅ Passing game document to phase-a (eliminates race condition)');
        requestBody.game_document = playedDocument;
      }

      franchiseCompleteWeekPayload = requestBody;

      // Phase A: persist user game only; EOG "Post-Game Press Conference" → phase-b (CPU + week advance) in PGPC modal
      showStatus('Saving game...');
      console.warn('[COMPLETE-WEEK TRACE] POSTing /franchise/complete-week/phase-a', { week, gameId, franchiseId });
      let res = await postPhaseA(requestBody);
      let phaseAError = res.ok ? null : await readPhaseAError(res);
      if (!res.ok && phaseAError && phaseAError.reason === 'stale_game_id') {
        const retry = retryPhaseAWithBoxDocument(requestBody, playedDocument, gameId);
        if (retry) {
          console.warn('[COMPLETE-WEEK TRACE] Retrying phase-a with the box document id', retry.game_id);
          res = await postPhaseA(retry);
          phaseAError = res.ok ? null : await readPhaseAError(res);
          if (res.ok) {
            requestBody.game_id = retry.game_id;
            requestBody.game_document = retry.game_document;
          }
        }
      }
      hideStatus();
      franchisePhaseAOk = res.ok;
      if (!res.ok) {
        console.error('❌ Failed franchise phase-a:', phaseAError || res.status);
        franchisePhaseBPending = undefined;
        const blocked = phaseAError && (phaseAError.reason === 'stale_game_id' || phaseAError.reason === 'missing_box_score');
        if (blocked) {
          clearStaleGameIdFromContext();
          franchisePhaseAOk = false;
          finalScorePhaseABlocked = {
            reason: phaseAError.reason,
            message: phaseAError.message || 'This game was not saved. Sim this game to record the result.',
          };
        }
      } else {
        franchisePhaseBPending = { franchise_id: franchiseId, week };
        console.log('✅ Franchise phase-a completed.');
        try {
          if (franchiseId && window.FranchiseLS) {
            window.FranchiseLS.setPendingCompleteWeek(franchiseId, {
              franchise_id: franchiseId,
              week,
            });
            const teamIdSnap =
              params.get('team_id') || params.get('home_id') || params.get('away_id') || null;
            const gid = requestBody.game_id || simData.game_id || simData._id;
            window.FranchiseLS.setEogSnapshot(franchiseId, {
              gameId: gid,
              franchiseId,
              teamId: teamIdSnap,
              week,
              my_team: params.get('my_team'),
              homeTeam: homeTeamObj.name,
              awayTeam: awayTeamObj.name,
              homeScore,
              awayScore,
              winner,
              franchisePhaseBPending: { franchise_id: franchiseId, week },
              franchisePhaseAOk: true,
            });
          }
        } catch (_) {}
      }
    } catch (err) {
      hideStatus();
      console.error('🚨 Error during franchise phase-a:', err);
      franchisePhaseAOk = false;
    }
  }

  const finalScore = {
    homeTeam: homeTeamObj.name,
    awayTeam: awayTeamObj.name,
    homeScore,
    awayScore,
    winner,
    homeTeamData: homeTeamObj,
    awayTeamData: awayTeamObj,
    franchiseCompleteWeekPayload,
    franchisePhaseBPending,
    franchisePhaseAOk,
    phaseABlocked: finalScorePhaseABlocked,
  };

  if (game && game.events) {
    game.events.emit("gameComplete", finalScore);
  }

  // ⏸️ TABLED: Resume Last Game feature - Exact game state restoration
  // TODO: Revisit after Phase 1.3+ and site go-live priorities complete
  // See: docs/To Do/resume_last_game_exact_state.md
  // ✅ PHASE 1.2: Clear both game_id and last_game_id when game completes
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('game_id');
    // localStorage.removeItem('last_game_id'); // Clear resume game reference
    // localStorage.removeItem('last_game_user_team_side'); // Clear resume user team side
    if (DEBUG_GAME_ID) {
      console.debug('Cleared game_id after finalize');
    }
  }

  return finalScore;
}
