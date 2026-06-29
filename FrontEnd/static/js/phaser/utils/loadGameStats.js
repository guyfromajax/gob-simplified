/**
 * Load and display accumulated game statistics for resumed games
 * Used when loading Q4 after simming Q1-Q3
 */

/** Throttle rank/record diagnostic: log when payload changes or every ~3.5s. */
let _gobScoreboardHeaderLogAt = 0;
let _gobScoreboardHeaderLastSig = '';
const GO_SCOREBOARD_HEADER_LOG_MS = 3500;

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

async function fetchResumeState(gameId) {
  if (!gameId) return null;

  try {
    const res = await fetch(API_CONFIG.buildUrl(`/api/game/${encodeURIComponent(gameId)}/resume-state`), {
      headers: API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {},
    });
    if (!res.ok) return null;
    const resumeState = await res.json();
    if (!resumeState || resumeState.status !== 'stoppage_anchor') return null;
    console.warn('[RESUME-ANCHOR-CLIENT] loaded anchor UI state', {
      game_id: resumeState.game_id || gameId,
      quarter: resumeState.quarter,
      clock: resumeState.clock,
      time_remaining: resumeState.time_remaining,
      home_score: resumeState.home_score,
      away_score: resumeState.away_score,
    });
    return resumeState;
  } catch (err) {
    console.warn('⚠️ [COURT RESUME] Could not fetch anchor UI state:', err);
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

function numericValue(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function objectHasNonZeroNumber(value) {
  if (!value || typeof value !== 'object') return false;
  if (Array.isArray(value)) {
    return value.some((item) => objectHasNonZeroNumber(item));
  }
  return Object.values(value).some((item) => {
    if (typeof item === 'number') return item !== 0;
    if (typeof item === 'string' && item.trim() !== '') {
      const n = Number(item);
      return Number.isFinite(n) && n !== 0;
    }
    return item && typeof item === 'object' ? objectHasNonZeroNumber(item) : false;
  });
}

function getTeamRows(gameData) {
  return Object.values(gameData?.teams || {}).filter((team) => team && typeof team === 'object');
}

function isPreAnchorQ1DirtyGame(gameData) {
  if (!gameData || typeof gameData !== 'object') return false;
  if (gameData.resume_anchor || gameData.status === 'stoppage_anchor') return false;

  const quarter = numericValue(gameData.quarter) || 1;
  if (quarter !== 1) return false;

  const timeRemaining = gameData.time_remaining == null ? 480 : numericValue(gameData.time_remaining);
  const clock = typeof gameData.clock === 'string' ? gameData.clock.trim() : '';
  const shotClock = gameData.shot_clock_remaining == null ? 30 : numericValue(gameData.shot_clock_remaining);

  if (timeRemaining !== 480) return true;
  if (clock && clock !== '8:00') return true;
  if (shotClock !== 30) return true;
  if (objectHasNonZeroNumber(gameData.score)) return true;
  if (objectHasNonZeroNumber(gameData.box_score)) return true;
  if (objectHasNonZeroNumber(gameData.team_totals)) return true;
  if (objectHasNonZeroNumber(gameData.team_stats)) return true;
  if (objectHasNonZeroNumber(gameData.fouls)) return true;
  if (objectHasNonZeroNumber(gameData.no_defender_shots)) return true;

  for (const team of getTeamRows(gameData)) {
    if (numericValue(team.score) !== 0) return true;
    if (numericValue(team.team_fouls) !== 0) return true;
    if (team.timeouts != null && numericValue(team.timeouts) !== 4) return true;
    if (objectHasNonZeroNumber(team.points_by_quarter)) return true;
    if (objectHasNonZeroNumber(team.box_score)) return true;
    if (objectHasNonZeroNumber(team.team_game_stats)) return true;
    if (objectHasNonZeroNumber(team.totals)) return true;
  }

  const players = Array.isArray(gameData.players) ? gameData.players : [];
  return players.some((player) => {
    if (!player || typeof player !== 'object') return false;
    if (objectHasNonZeroNumber(player.stats)) return true;
    const attrs = player.attributes || {};
    if (attrs.MO != null && numericValue(attrs.MO) !== 0) return true;
    return false;
  });
}

function resetPreAnchorCourtChrome(homeTeam, awayTeam) {
  setScoreboardHeaderDefaults(homeTeam, awayTeam);

  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  const clockEl = document.getElementById('game-clock');
  const quarterEl = document.getElementById('quarter');
  const shotClockEl = document.getElementById('shot-clock');
  const homeStatsBody = document.getElementById('home-stats-body');
  const awayStatsBody = document.getElementById('away-stats-body');

  if (homeScoreEl) homeScoreEl.textContent = '0';
  if (awayScoreEl) awayScoreEl.textContent = '0';
  if (clockEl) clockEl.textContent = '8:00';
  if (quarterEl) quarterEl.textContent = 'Q1';
  if (shotClockEl) shotClockEl.textContent = '30';
  if (homeStatsBody) homeStatsBody.innerHTML = '';
  if (awayStatsBody) awayStatsBody.innerHTML = '';
  window.currentPlayerStats = { home: {}, away: {} };

  if (typeof window.setTeamBoxData === 'function') {
    window.setTeamBoxData({
      home: { offense: {}, defense: {}, attributes: {}, totals: {} },
      away: { offense: {}, defense: {}, attributes: {}, totals: {} },
    });
  }
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
  // Name-keyed meta: same keys as gameData.score / box_score (?home= & ?away=).
  const metaByName = gameData.team_scoreboard_meta && typeof gameData.team_scoreboard_meta === 'object'
    ? gameData.team_scoreboard_meta
    : {};
  const pickNameMeta = (nm) => {
    if (!nm || !metaByName) return null;
    if (metaByName[nm]) return metaByName[nm];
    const keys = Object.keys(metaByName);
    const t = String(nm).trim();
    let k = keys.find((x) => String(x).trim() === t);
    if (!k) k = keys.find((x) => String(x).trim().toLowerCase() === t.toLowerCase());
    return k ? metaByName[k] : null;
  };
  const hByName = pickNameMeta(homeTeam);
  const aByName = pickNameMeta(awayTeam);
  const hRankRec = { ...hMeta, ...(hByName || {}) };
  const aRankRec = { ...aMeta, ...(aByName || {}) };
  if (typeof window !== 'undefined' && metaByName && typeof metaByName === 'object' && Object.keys(metaByName).length) {
    window.__gobCourtScoreboardMetaByName = { ...(window.__gobCourtScoreboardMetaByName || {}), ...metaByName };
  }
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
  if (homeRankEl) homeRankEl.textContent = fmtRank(hRankRec);
  if (homeRecEl) homeRecEl.textContent = fmtRec(hRankRec);
  if (awayRankEl) awayRankEl.textContent = fmtRank(aRankRec);
  if (awayRecEl) awayRecEl.textContent = fmtRec(aRankRec);

  try {
    const hdrBlob = {
      homeName: homeTeam,
      awayName: awayTeam,
      home_team_id: hid,
      away_team_id: aid,
      home_team_legacy: legH,
      away_team_legacy: legA,
      home_team_row: homeTeamObj,
      away_team_row: awayTeamObj,
      team_scoreboard_meta: metaByName,
      merged_home_rank_record: hRankRec,
      merged_away_rank_record: aRankRec,
      painted: {
        home: { rank: fmtRank(hRankRec), record: fmtRec(hRankRec) },
        away: { rank: fmtRank(aRankRec), record: fmtRec(aRankRec) },
      },
    };
    const sig = JSON.stringify({
      hid,
      aid,
      hr: hRankRec?.natl_rank,
      ar: aRankRec?.natl_rank,
      hw: hRankRec?.wins ?? hRankRec?.team_wins,
      hl: hRankRec?.losses ?? hRankRec?.team_losses,
      aw: aRankRec?.wins ?? aRankRec?.team_wins,
      al: aRankRec?.losses ?? aRankRec?.team_losses,
      mkeys: Object.keys(metaByName),
    });
    const t = Date.now();
    if (typeof window !== 'undefined' && (sig !== _gobScoreboardHeaderLastSig || t - _gobScoreboardHeaderLogAt >= GO_SCOREBOARD_HEADER_LOG_MS)) {
      _gobScoreboardHeaderLastSig = sig;
      _gobScoreboardHeaderLogAt = t;
      console.log('[GOB scoreboard rank/record] full merge sources (auto; throttled unless data changed)', hdrBlob);
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

export function displayAccumulatedClockState(gameData) {
  if (!gameData) return;

  const clockEl = document.getElementById('game-clock');
  const quarterEl = document.getElementById('quarter');
  const shotClockEl = document.getElementById('shot-clock');
  const quarter = Number(gameData.quarter) || 1;
  const clock = gameData.clock || (
    Number.isFinite(Number(gameData.time_remaining))
      ? `${Math.floor(Number(gameData.time_remaining) / 60)}:${String(Math.floor(Number(gameData.time_remaining) % 60)).padStart(2, '0')}`
      : null
  );
  const period = quarter <= 4 ? `Q${quarter}` : `OT${quarter - 4}`;

  if (clockEl && clock) clockEl.textContent = clock;
  if (quarterEl) quarterEl.textContent = period;
  if (shotClockEl && gameData.shot_clock_remaining != null) {
    shotClockEl.textContent = String(gameData.shot_clock_remaining);
  }
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
  const quarterBreakFrom = urlParams.get('quarter_break_from');
  const quarter = Number(urlParams.get('quarter') || 1);
  const liveQuarterStart = quarterBreakFrom === 'play_quarter' || quarterBreakFrom === 'sim_quarter';
  const wantsAnchorUi =
    !liveQuarterStart && (
      urlParams.get('active_resume') === 'true' ||
      urlParams.get('resume_from_anchor') === 'true' ||
      urlParams.get('consume_resume_anchor') === 'true'
    );
  
  if (!homeTeam || !awayTeam) return;

  setScoreboardHeaderDefaults(homeTeam, awayTeam);
  if (!gameId) return;
  
  const gameData = wantsAnchorUi
    ? await fetchResumeState(gameId)
    : await fetchGameState(gameId);
  if (!wantsAnchorUi && !liveQuarterStart && quarter === 1 && isPreAnchorQ1DirtyGame(gameData)) {
    window.__GOB_PRE_ANCHOR_Q1_REFRESH__ = true;
    window.__GOB_PRE_ANCHOR_Q1_REFRESH_GAME_ID__ = gameId;
    console.warn('[PRE-ANCHOR-Q1-REFRESH] dirty pre-anchor game doc detected; suppressing accumulated stats', {
      game_id: gameId,
      quarter: gameData?.quarter,
      clock: gameData?.clock,
      time_remaining: gameData?.time_remaining,
      score: gameData?.score,
    });
    resetPreAnchorCourtChrome(homeTeam, awayTeam);
    return;
  }
  if (gameData) {
    displayAccumulatedHeaderState(gameData, homeTeam, awayTeam);
    displayAccumulatedClockState(gameData);
    displayAccumulatedScores(gameData, homeTeam, awayTeam);
    displayAccumulatedPlayerStats(gameData, homeTeam, awayTeam);
    displayTeamBoxScore(gameData, homeTeam, awayTeam);
  }
}
