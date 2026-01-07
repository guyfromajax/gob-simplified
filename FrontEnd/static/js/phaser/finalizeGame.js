const DEBUG_BRACKET = window.DEBUG_BRACKET || false;
const DEBUG_GAME_ID = window.DEBUG_GAME_ID || false;

export async function finalizeGame({ simData, tournamentId, franchiseId, game }) {
  // Extract score and winner - handle both new nested and old flat structure
  // New structure: simData.home_team is an object with {name, score, etc.}
  // Old structure: simData.home_team is a string, simData.homeTeam is an object
  const homeTeamField = simData.home_team;
  const awayTeamField = simData.away_team;
  
  const homeTeamObj = typeof homeTeamField === 'object' ? homeTeamField : (simData.homeTeam || { name: homeTeamField });
  const awayTeamObj = typeof awayTeamField === 'object' ? awayTeamField : (simData.awayTeam || { name: awayTeamField });
  
  const homeKey = homeTeamObj.name || homeTeamField;
  const awayKey = awayTeamObj.name || awayTeamField;
  
  const scoreMap = simData.final_score || simData.score || {};
  // ✅ FIX: Prioritize scoreMap (updated scores) over nested object scores (may be stale from initialSimData)
  // This ensures that when "Sim to 4th Quarter" is used, we use Q4 final scores, not Q3 scores from initialSimData
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
      
      const res = await fetch(saveResultUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
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
            window.location.href = "/tournament.html";
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
  if (franchiseId && !tournamentId && Number.isInteger(week) && week >= 1) {
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
      // This eliminates race condition where complete_week() is called before Q4 save completes
      const requestBody = {
        franchise_id: franchiseId,
        week: week,
        game_id: gameId,  // ✅ SS&S: Pass actual gameplay game_id
        result: {
          team1_id: team1Id,
          team2_id: team2Id,
          team1_score: awayScore,
          team2_score: homeScore,
        },
      };
      
      // If simData contains final_game_document (from simulate-quarter), pass it to eliminate race condition
      if (simData && simData.final_game_document) {
        console.log('✅ Passing final_game_document to complete_week (eliminates race condition)');
        requestBody.game_document = simData.final_game_document;
      }
      
      const res = await fetch(API_CONFIG.buildUrl("/franchise/complete-week"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      if (!res.ok) {
        console.error("❌ Failed to complete franchise week:", await res.text());
      } else {
        console.log("✅ Franchise week completed.");
      }
    } catch (err) {
      console.error("🚨 Error during franchise week completion:", err);
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
  };

  if (game && game.events) {
    game.events.emit("gameComplete", finalScore);
  }

  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('game_id');
    if (DEBUG_GAME_ID) {
      console.debug('Cleared game_id after finalize');
    }
  }

  return finalScore;
}
