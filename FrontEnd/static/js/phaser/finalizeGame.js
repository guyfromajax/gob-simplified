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

export async function finalizeGame({ simData, tournamentId, franchiseId, game }) {
  console.warn('[COMPLETE-WEEK TRACE] finalizeGame ENTRY', { hasSimData: !!simData, franchiseId, tournamentId });
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
  const params = new URLSearchParams(window.location.search);
  let week = parseInt(params.get('week'), 10);
  const homeIdParam = params.get('home_id');
  const awayIdParam = params.get('away_id');
  if (!week || Number.isNaN(week)) {
    if (typeof localStorage !== 'undefined') {
      week = parseInt(localStorage.getItem('franchise_week'), 10);
    }
  }
  if (!week || Number.isNaN(week)) {
    if (simData && simData.week) {
      week = parseInt(simData.week, 10);
    }
  }
  if ((!week || Number.isNaN(week)) && simData?.final_game_document?.week != null) {
    week = parseInt(simData.final_game_document.week, 10);
  }
  if ((!week || Number.isNaN(week)) && franchiseId && !tournamentId) {
    week = await recoverFranchiseWeek(franchiseId);
    if (Number.isInteger(week) && week >= 1 && typeof localStorage !== 'undefined') {
      localStorage.setItem('franchise_week', String(week));
    }
  }

  // POST to /tournament/save-result if needed
  console.log('🔍 [FINALIZE_GAME] Checking tournamentId:', {
    tournamentId: tournamentId,
    franchiseId: franchiseId,
    hasTournamentId: !!tournamentId,
    willCallSaveResult: !!tournamentId
  });
  
  if (tournamentId) {
    try {
      console.log('✅ [FINALIZE_GAME] tournamentId present, calling /tournament/save-result');
      
      // ✅ SS&S: Build request body (matches Franchise mode pattern)
      const requestBody = {
        tournament_id: tournamentId,
        game_id: simData.game_id || simData._id,
        winner: winner,
        score: {
          [homeKey]: homeScore,
          [awayKey]: awayScore,
        },
      };
      
      // ✅ FIX: Pass game_document if available (from simulate-quarter when is_final=True)
      // This eliminates race condition where save-result is called before Q4 save completes
      // Matches Franchise mode pattern exactly
      // Also handle case where simData itself IS the game document (from bootGame.js "Sim Full Game")
      if (simData && simData.final_game_document) {
        console.log('✅ Passing final_game_document to tournament/save-result (eliminates race condition)');
        requestBody.game_document = simData.final_game_document;
      } else if (simData && simData.box_score && (simData.game_id || simData._id)) {
        // ✅ FIX: If simData itself is a complete game document (has box_score and game_id),
        // use it directly as game_document (handles "Sim Full Game" flow from bootGame.js)
        console.log('✅ Using simData as game_document (Sim Full Game flow)');
        requestBody.game_document = simData;
      }
      
      const saveResultUrl = API_CONFIG.buildUrl("/tournament/save-result");
      console.log('📤 [FINALIZE_GAME] POSTing to:', saveResultUrl);
      console.log('📤 [FINALIZE_GAME] Request body (stringified):', JSON.stringify(requestBody, null, 2));
      console.log('📤 [FINALIZE_GAME] Has game_document?', !!requestBody.game_document);
      if (requestBody.game_document) {
        console.log('📤 [FINALIZE_GAME] game_document keys:', Object.keys(requestBody.game_document));
        console.log('📤 [FINALIZE_GAME] game_document has box_score?', !!requestBody.game_document.box_score);
      }
      
      // ✅ Show "Simulating Computer Games" when transitioning to computer games
      showStatus('Simulating Computer Games...');
      
      const res = await fetch(saveResultUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      
      // Hide status after response (whether success or error)
      hideStatus();
      console.log('📥 [FINALIZE_GAME] Response status:', res.status, res.statusText);
      console.log('📥 [FINALIZE_GAME] Response ok?', res.ok);
      
      if (!res.ok) {
        const errorText = await res.text();
        console.error("❌ Failed to save tournament result. Status:", res.status);
        console.error("❌ Error response text:", errorText);
      } else {
        const responseData = await res.json().catch((e) => {
          console.warn("⚠️ Could not parse JSON response:", e);
          return null;
        });
        console.log("✅ Tournament result saved successfully!");
        console.log("✅ Response data:", JSON.stringify(responseData, null, 2));
        try {
          const updated = await fetch(`${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${encodeURIComponent(tournamentId)}`).then((r) =>
            r.json()
          );
          if (window.opener && window.opener.handleTournamentUpdate) {
            if (DEBUG_BRACKET)
              console.log("[DebugBracket] invoking handleTournamentUpdate", {
                id: updated?._id,
                current_round: updated?.current_round,
              });
            window.opener.handleTournamentUpdate(updated);
            window.opener.refreshLeaders?.();
          } else if (window.handleTournamentUpdate) {
            if (DEBUG_BRACKET)
              console.log("[DebugBracket] invoking handleTournamentUpdate", {
                id: updated?._id,
                current_round: updated?.current_round,
              });
            window.handleTournamentUpdate(updated);
            window.refreshLeaders?.();
          } else {
            localStorage.setItem("activeTournament", JSON.stringify(updated));
            // ✅ PHASE 2: Include tournament_id and team_id in navigation URL
            const params = new URLSearchParams();
            if (tournamentId) {
              params.set('tournament_id', tournamentId);
              // Try to get team_id from URL, updated tournament state, or simData
              const urlParams = new URLSearchParams(window.location.search);
              const teamId = urlParams.get('team_id') || 
                            updated?.user_team_id || 
                            updated?.user_team_object_id ||
                            simData?.user_team_id ||
                            (game && game.user_team_id);
              if (teamId) {
                params.set('team_id', teamId);
              }
            }
            const url = params.toString() ? `/tournament.html?${params.toString()}` : '/tournament.html';
            window.location.href = url;
          }
        } catch (e) {
          console.error("Failed to update tournament state", e);
        }
      }
    } catch (err) {
      console.error("🚨 Error during tournament result save!");
      console.error("🚨 Error message:", err.message);
      console.error("🚨 Error stack:", err.stack);
      console.error("🚨 Tournament ID:", tournamentId);
      console.error("🚨 Game ID:", simData.game_id || simData._id);
    }
  } else {
    console.log('⚠️ [FINALIZE_GAME] tournamentId is missing, skipping /tournament/save-result call');
  }

  // POST to /franchise/complete-week if needed (only if NOT in tournament mode)
  const canCompleteWeek = franchiseId && !tournamentId && Number.isInteger(week) && week >= 1;
  if (!franchiseId || tournamentId) {
    console.warn('[COMPLETE-WEEK TRACE] Skipping complete-week: not franchise mode', { franchiseId, tournamentId });
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
      // ✅ SS&S: Extract game_id from simData (actual gameplay document ID)
      const gameId = simData.game_id || simData._id;
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

      if (simData && simData.final_game_document) {
        console.log('✅ Passing final_game_document to phase-a (eliminates race condition)');
        requestBody.game_document = simData.final_game_document;
      }

      franchiseCompleteWeekPayload = requestBody;
      franchisePhaseBPending = { franchise_id: franchiseId, week };

      // Phase A: persist user game only; EOG "Sim Computer Games" → phase-b (CPU + week advance)
      showStatus('Saving game...');
      console.warn('[COMPLETE-WEEK TRACE] POSTing /franchise/complete-week/phase-a', { week, gameId, franchiseId });
      const res = await fetch(API_CONFIG.buildUrl('/franchise/complete-week/phase-a'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
      hideStatus();
      franchisePhaseAOk = res.ok;
      if (!res.ok) {
        console.error('❌ Failed franchise phase-a:', await res.text());
      } else {
        console.log('✅ Franchise phase-a completed.');
        try {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(
              'franchise_complete_week_pending',
              JSON.stringify({ franchise_id: franchiseId, week })
            );
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
