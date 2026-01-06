/**
 * Load and display accumulated game statistics for resumed games
 * Used when loading Q4 after simming Q1-Q3
 */

/**
 * Fetch game state from backend
 * @param {string} gameId - Game ID
 * @returns {Object} Game state with scores and stats
 */
export async function fetchGameState(gameId) {
  if (!gameId) return null;
  
  try {
    const res = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`));
    if (!res.ok) {
      console.warn(`⚠️ Could not fetch game state for ${gameId}`);
      return null;
    }
    const gameData = await res.json();
    console.log('📊 Loaded game state:', gameData);
    return gameData;
  } catch (err) {
    console.error('Error fetching game state:', err);
    return null;
  }
}

/**
 * Update scoreboard with accumulated scores
 * @param {Object} gameData - Game data from backend
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 */
export function displayAccumulatedScores(gameData, homeTeam, awayTeam) {
  if (!gameData || !gameData.score) return;
  
  const homeScore = gameData.score[homeTeam] || 0;
  const awayScore = gameData.score[awayTeam] || 0;
  
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  
  if (homeScoreEl) homeScoreEl.textContent = homeScore;
  if (awayScoreEl) awayScoreEl.textContent = awayScore;
  
  console.log('📊 Scoreboard updated with accumulated scores:', { homeScore, awayScore });
}

/**
 * Update player stat tables with accumulated stats
 * @param {Object} gameData - Game data from backend
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 */
export function displayAccumulatedPlayerStats(gameData, homeTeam, awayTeam) {
  if (!gameData || !gameData.box_score) return;
  
  const boxScore = gameData.box_score;
  
  // Store player data globally for toggle system
  window.currentPlayerStats = {
    home: boxScore[homeTeam] || {},
    away: boxScore[awayTeam] || {}
  };
  
  // Update home stats
  const homeStatsBody = document.getElementById('home-stats-body');
  if (homeStatsBody && boxScore[homeTeam]) {
    homeStatsBody.innerHTML = '';
    Object.values(boxScore[homeTeam]).forEach(playerStats => {
      const row = document.createElement('tr');
      const pts = playerStats.PTS || 0;
      const reb = playerStats.REB || ((playerStats.OREB || 0) + (playerStats.DREB || 0));
      const ast = playerStats.AST || 0;
      const fouls = playerStats.F || 0;
      const stl = playerStats.STL || 0;
      const blk = playerStats.BLK || 0;
      const to = playerStats.TO || 0;
      const defAttempts = playerStats.DEF_A || 0;
      const defSuccesses = playerStats.DEF_S || 0;
      const defRate = defAttempts > 0 ? Math.round((defSuccesses / defAttempts) * 100) : 0;
      
      row.innerHTML = `
        <td>${playerStats.name}</td>
        <td>${pts}</td>
        <td>${reb}</td>
        <td>${ast}</td>
        <td>${fouls}</td>
        <td style="display: none;">${stl}</td>
        <td style="display: none;">${blk}</td>
        <td style="display: none;">${to}</td>
        <td style="display: none;">${defAttempts}</td>
        <td style="display: none;">${defRate}%</td>
      `;
      homeStatsBody.appendChild(row);
    });
  }
  
  // Update away stats
  const awayStatsBody = document.getElementById('away-stats-body');
  if (awayStatsBody && boxScore[awayTeam]) {
    awayStatsBody.innerHTML = '';
    Object.values(boxScore[awayTeam]).forEach(playerStats => {
      const row = document.createElement('tr');
      const pts = playerStats.PTS || 0;
      const reb = playerStats.REB || ((playerStats.OREB || 0) + (playerStats.DREB || 0));
      const ast = playerStats.AST || 0;
      const fouls = playerStats.F || 0;
      const stl = playerStats.STL || 0;
      const blk = playerStats.BLK || 0;
      const to = playerStats.TO || 0;
      const defAttempts = playerStats.DEF_A || 0;
      const defSuccesses = playerStats.DEF_S || 0;
      const defRate = defAttempts > 0 ? Math.round((defSuccesses / defAttempts) * 100) : 0;
      
      row.innerHTML = `
        <td>${playerStats.name}</td>
        <td>${pts}</td>
        <td>${reb}</td>
        <td>${ast}</td>
        <td>${fouls}</td>
        <td style="display: none;">${stl}</td>
        <td style="display: none;">${blk}</td>
        <td style="display: none;">${to}</td>
        <td style="display: none;">${defAttempts}</td>
        <td style="display: none;">${defRate}%</td>
      `;
      awayStatsBody.appendChild(row);
    });
  }
  
  console.log('📊 Player stats tables updated with accumulated stats');
}

/**
 * Update Team Box Score (S1, S2, S3 tabs)
 * @param {Object} gameData - Game data from backend
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 */
export function displayTeamBoxScore(gameData, homeTeam, awayTeam) {
  if (!gameData) {
    console.warn('⚠️ No game data provided to displayTeamBoxScore');
    return;
  }
  
  // Check if setTeamBoxData function exists (defined in court.html)
  if (typeof window.setTeamBoxData !== 'function') {
    console.warn('⚠️ window.setTeamBoxData function not found');
    return;
  }
  
  const homeTotals = gameData.team_totals?.[homeTeam] || {};
  const awayTotals = gameData.team_totals?.[awayTeam] || {};
  
  // Get team attributes from home_team/away_team objects
  const homeAttrs = gameData.home_team?.attributes || {};
  const awayAttrs = gameData.away_team?.attributes || {};
  
  // Get playcall stats (S2 tab) - these come from team_stats if available
  const homeOffense = gameData.team_stats?.[homeTeam]?.offense || {};
  const awayOffense = gameData.team_stats?.[awayTeam]?.offense || {};
  const homeDefense = gameData.team_stats?.[homeTeam]?.defense || {};
  const awayDefense = gameData.team_stats?.[awayTeam]?.defense || {};
  
  console.log('📊 Team Box Score data loaded:', {
    homeTotals,
    awayTotals,
    homeOffense,
    awayOffense
  });
  
  // Call the global setTeamBoxData function (same as used during gameplay)
  window.setTeamBoxData({
    home: {
      offense: homeOffense,
      defense: homeDefense,
      attributes: homeAttrs,
      totals: homeTotals
    },
    away: {
      offense: awayOffense,
      defense: awayDefense,
      attributes: awayAttrs,
      totals: awayTotals
    }
  });
  
  console.log('📊 Team Box Score updated (S1, S2, S3 tabs)');
}

/**
 * Initialize court page with accumulated game stats
 * Call this on page load if game_id exists
 */
export async function initializeGameStats() {
  const urlParams = new URLSearchParams(window.location.search);
  const gameId = urlParams.get('game_id');
  const homeTeam = urlParams.get('home');
  const awayTeam = urlParams.get('away');
  
  if (!gameId || !homeTeam || !awayTeam) return;
  
  const gameData = await fetchGameState(gameId);
  if (gameData) {
    displayAccumulatedScores(gameData, homeTeam, awayTeam);
    displayAccumulatedPlayerStats(gameData, homeTeam, awayTeam);
    displayTeamBoxScore(gameData, homeTeam, awayTeam);
  }
}

