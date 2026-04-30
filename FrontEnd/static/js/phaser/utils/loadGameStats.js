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
    const res = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`), { headers: API_CONFIG.getAuthHeaders() });
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

function normTeamsSlot(s) {
  if (s == null || s === '') return '';
  return String(s).toUpperCase().replace(/\s+/g, '_').replace(/-/g, '_');
}

/**
 * Key for `gameData.teams[key]`: prefer `home_id`/`away_id` from the court URL when the API
 * still emits legacy `home_team_id` values that do not match `teams` keys.
 */
export function resolveTeamsSlotLookupKey(teamsObj, storedId, urlId, legacyTeam) {
  const teams = teamsObj && typeof teamsObj === 'object' ? teamsObj : {};

  const tryCandidate = (candidate) => {
    if (candidate == null || candidate === '') return null;
    const s = String(candidate);
    if (teams[s]) return s;
    if (teams[candidate]) return String(candidate);
    for (const k of Object.keys(teams)) {
      if (String(k) === s) return k;
    }
    for (const k of Object.keys(teams)) {
      const row = teams[k];
      if (!row || typeof row !== 'object') continue;
      const tid = row.team_id;
      if (tid != null && String(tid) === s) return k;
      const nm = row.name;
      if (nm && (String(nm) === s || normTeamsSlot(nm) === normTeamsSlot(s))) return k;
    }
    return null;
  };

  return tryCandidate(urlId) || tryCandidate(storedId) || tryCandidate(legacyTeam?.name) || null;
}

function setScoreboardHeaderDefaults(homeTeam, awayTeam) {
  const homeLogoEl = document.getElementById('home-logo');
  const awayLogoEl = document.getElementById('away-logo');
  const homeTolEl = document.getElementById('home-tol');
  const awayTolEl = document.getElementById('away-tol');
  const homeFoulsEl = document.getElementById('home-fouls');
  const awayFoulsEl = document.getElementById('away-fouls');

  if (homeLogoEl && homeTeam) {
    homeLogoEl.src = typeof getTeamAssetPath === 'function'
      ? getTeamAssetPath(homeTeam, 'banner_primary')
      : '/images/teams/general/general_banner_primary.jpg';
  }
  if (awayLogoEl && awayTeam) {
    awayLogoEl.src = typeof getTeamAssetPath === 'function'
      ? getTeamAssetPath(awayTeam, 'banner_primary')
      : '/images/teams/general/general_banner_primary.jpg';
  }
  if (homeTolEl) homeTolEl.textContent = 'TOL: 4';
  if (awayTolEl) awayTolEl.textContent = 'TOL: 4';
  if (homeFoulsEl) homeFoulsEl.textContent = 'F: 0';
  if (awayFoulsEl) awayFoulsEl.textContent = 'F: 0';
}

export function displayAccumulatedHeaderState(gameData, homeTeam, awayTeam) {
  setScoreboardHeaderDefaults(homeTeam, awayTeam);

  if (!gameData) return;

  const homeTolEl = document.getElementById('home-tol');
  const awayTolEl = document.getElementById('away-tol');
  const homeFoulsEl = document.getElementById('home-fouls');
  const awayFoulsEl = document.getElementById('away-fouls');
  const teamsObj = gameData.teams || {};
  let urlHomeId = null;
  let urlAwayId = null;
  try {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search);
      urlHomeId = p.get('home_id');
      urlAwayId = p.get('away_id');
    }
  } catch (e) {
    /* ignore */
  }
  const legH = typeof gameData.home_team === 'object' && gameData.home_team ? gameData.home_team : null;
  const legA = typeof gameData.away_team === 'object' && gameData.away_team ? gameData.away_team : null;
  const homeSlotKey =
    resolveTeamsSlotLookupKey(teamsObj, gameData.home_team_id, urlHomeId, legH) ?? gameData.home_team_id;
  const awaySlotKey =
    resolveTeamsSlotLookupKey(teamsObj, gameData.away_team_id, urlAwayId, legA) ?? gameData.away_team_id;
  const homeTeamObj = homeSlotKey && teamsObj[homeSlotKey] ? teamsObj[homeSlotKey] : null;
  const awayTeamObj = awaySlotKey && teamsObj[awaySlotKey] ? teamsObj[awaySlotKey] : null;

  const homeFouls = homeTeamObj?.team_fouls ?? gameData.fouls?.home ?? 0;
  const awayFouls = awayTeamObj?.team_fouls ?? gameData.fouls?.away ?? 0;
  const homeTimeouts = homeTeamObj?.timeouts ?? gameData.timeouts?.home ?? gameData.home_team_timeouts ?? 4;
  const awayTimeouts = awayTeamObj?.timeouts ?? gameData.timeouts?.away ?? gameData.away_team_timeouts ?? 4;

  if (homeFoulsEl) homeFoulsEl.textContent = `F: ${homeFouls}`;
  if (awayFoulsEl) awayFoulsEl.textContent = `F: ${awayFouls}`;
  if (homeTolEl) homeTolEl.textContent = `TOL: ${homeTimeouts}`;
  if (awayTolEl) awayTolEl.textContent = `TOL: ${awayTimeouts}`;

  // Scoreboard rank / record (game doc teams[id] and/or legacy home_team / away_team)
  const homeRankEl = document.getElementById('home-rank');
  const homeRecEl = document.getElementById('home-record');
  const awayRankEl = document.getElementById('away-rank');
  const awayRecEl = document.getElementById('away-record');
  const hid = homeSlotKey;
  const aid = awaySlotKey;
  // SS&S: same merge order as S3 attributes (teams row overwrites legacy home_team for overlapping keys).
  const hMeta = { ...(legH || {}), ...(homeTeamObj || {}) };
  const aMeta = { ...(legA || {}), ...(awayTeamObj || {}) };
  const fmtRank = (t) => {
    const r = Number(t?.natl_rank);
    if (Number.isInteger(r) && r >= 1) return `#${r}`;
    return '#--';
  };
  const fmtRec = (t) => {
    const w = t?.wins ?? t?.team_wins;
    const l = t?.losses ?? t?.team_losses;
    if (w == null || l == null) return '--';
    const wn = Number(w);
    const ln = Number(l);
    if (Number.isFinite(wn) && Number.isFinite(ln)) return `${wn}-${ln}`;
    return '--';
  };
  if (homeRankEl) homeRankEl.textContent = fmtRank(hMeta);
  if (homeRecEl) homeRecEl.textContent = fmtRec(hMeta);
  if (awayRankEl) awayRankEl.textContent = fmtRank(aMeta);
  if (awayRecEl) awayRecEl.textContent = fmtRec(aMeta);

  try {
    if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('debug_scoreboard') === '1') {
      console.info('[court scoreboard] GET /api/game → displayAccumulatedHeaderState', {
        home_team_id: hid,
        away_team_id: aid,
        teams_keys: Object.keys(teamsObj).slice(0, 12),
        hMeta: hMeta
          ? {
              natl_rank: hMeta.natl_rank,
              wins: hMeta.wins ?? hMeta.team_wins,
              losses: hMeta.losses ?? hMeta.team_losses,
            }
          : null,
        aMeta: aMeta
          ? {
              natl_rank: aMeta.natl_rank,
              wins: aMeta.wins ?? aMeta.team_wins,
              losses: aMeta.losses ?? aMeta.team_losses,
            }
          : null,
        painted_home_rank: hMeta ? fmtRank(hMeta) : '(skip, no hMeta)',
        painted_home_rec: hMeta ? fmtRec(hMeta) : '(skip)',
        painted_away_rank: aMeta ? fmtRank(aMeta) : '(skip, no aMeta)',
        painted_away_rec: aMeta ? fmtRec(aMeta) : '(skip)',
      });
    }
  } catch (e) {
    /* ignore */
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
  
  // ✅ UNIFIED STRUCTURE: Get team attributes from unified teams object
  const teamsObj = gameData.teams || {};
  let urlHomeId = null;
  let urlAwayId = null;
  try {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search);
      urlHomeId = p.get('home_id');
      urlAwayId = p.get('away_id');
    }
  } catch (e) {
    /* ignore */
  }
  const legH = typeof gameData.home_team === 'object' ? gameData.home_team : null;
  const legA = typeof gameData.away_team === 'object' ? gameData.away_team : null;
  const homeTeamId =
    resolveTeamsSlotLookupKey(teamsObj, gameData.home_team_id, urlHomeId, legH) ?? gameData.home_team_id;
  const awayTeamId =
    resolveTeamsSlotLookupKey(teamsObj, gameData.away_team_id, urlAwayId, legA) ?? gameData.away_team_id;

  // Get team data from unified structure first
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  // ✅ BACKWARD COMPATIBILITY: Fallback to old structure if unified structure not available
  const homeAttrs = homeTeamObj?.attributes || gameData.home_team?.attributes || {};
  const awayAttrs = awayTeamObj?.attributes || gameData.away_team?.attributes || {};
  
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
  
  if (!homeTeam || !awayTeam) return;

  setScoreboardHeaderDefaults(homeTeam, awayTeam);
  if (!gameId) return;
  
  const gameData = await fetchGameState(gameId);
  if (gameData) {
    displayAccumulatedHeaderState(gameData, homeTeam, awayTeam);
    displayAccumulatedScores(gameData, homeTeam, awayTeam);
    displayAccumulatedPlayerStats(gameData, homeTeam, awayTeam);
    displayTeamBoxScore(gameData, homeTeam, awayTeam);
  }
}
