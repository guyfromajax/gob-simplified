// Box Score Page JavaScript
// Fetches game data and renders box score information

function playSound(filename) {
  try {
    const base = (typeof window.API_CONFIG !== 'undefined' && window.API_CONFIG.buildStaticPath) ? window.API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(() => {});
  } catch (e) {}
}

let gameData = null;

/** PTS from shooting stats — must match BackEnd derive_pts_from_shooting_stats. */
function derivePtsFromShootingStats(stats) {
  if (!stats) return 0;
  const fgm = Number(stats.FGM) || 0;
  const threePm = Number(stats['3PTM']) || 0;
  const ftm = Number(stats.FTM) || 0;
  return (2 * fgm) + threePm + ftm;
}

function hexToRgbString(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
  return result
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : '42, 48, 58';
}

function getTeamContext() {
  const homeTeamId = gameData?.home_team_id;
  const awayTeamId = gameData?.away_team_id;
  const teamsObj = gameData?.teams || {};
  const homeTeam = (homeTeamId && teamsObj[homeTeamId]) ? teamsObj[homeTeamId] : (gameData?.home_team || {});
  const awayTeam = (awayTeamId && teamsObj[awayTeamId]) ? teamsObj[awayTeamId] : (gameData?.away_team || {});
  return { homeTeam, awayTeam, teamsObj, homeTeamId, awayTeamId };
}

/** URL team_id can fail strict equality vs Mongo ids keyed under `teams` — walk keys and embedded ids. */
function mapTeamIdToSide(teamIdRaw, gameData, homeName, awayName, homeTeamId, awayTeamId) {
  const t = String(teamIdRaw || '').trim();
  if (!t) return null;
  const eq = (a, b) => a != null && b != null && String(a).trim() === String(b).trim();
  if (eq(t, homeTeamId) || eq(t, homeName)) return 'home';
  if (eq(t, awayTeamId) || eq(t, awayName)) return 'away';
  const teams = gameData?.teams;
  if (!teams || typeof teams !== 'object') return null;
  for (const key of Object.keys(teams)) {
    const team = teams[key];
    if (!team || typeof team !== 'object') continue;
    const nm = team.name || team.team_name;
    const idHits = [key, team.team_id, team._id, team.teamId].filter((x) => x != null && String(x).trim() !== '');
    for (const id of idHits) {
      if (!eq(t, id)) continue;
      if (nm && eq(nm, homeName)) return 'home';
      if (nm && eq(nm, awayName)) return 'away';
      if (eq(key, homeTeamId) || eq(String(key), String(homeTeamId))) return 'home';
      if (eq(key, awayTeamId) || eq(String(key), String(awayTeamId))) return 'away';
    }
  }
  return null;
}

/** Map `banner_team` query to the same display name string the game doc uses (case / spelling). */
function resolveBannerTeamNameFromParams(bannerParam, homeName, awayName) {
  const b = (bannerParam || '').trim();
  if (!b) return null;
  if (b === homeName) return homeName;
  if (b === awayName) return awayName;
  if (b.toLowerCase() === homeName.toLowerCase()) return homeName;
  if (b.toLowerCase() === awayName.toLowerCase()) return awayName;
  return b;
}

/** User franchise team display name for Phase B pulse overlay (same rules as header banner). */
function resolveUserTeamNameForPhaseBPulse(urlParams) {
  if (!gameData || !urlParams) return '';
  const { homeTeam, awayTeam, homeTeamId, awayTeamId } = getTeamContext();
  const homeCore = teamCoreName(homeTeam, 'Home Team');
  const awayCore = teamCoreName(awayTeam, 'Away Team');
  const homeLabel = teamDisplayLabel(homeTeam, 'Home Team');
  const awayLabel = teamDisplayLabel(awayTeam, 'Away Team');
  const bannerTeamParam = (urlParams.get('banner_team') || '').trim();
  const myTeamParam = urlParams.get('my_team');
  const teamIdParam = urlParams.get('team_id') || urlParams.get('user_team_id');
  let userTeamSide = null;
  if (myTeamParam === 'home' || myTeamParam === 'away') {
    userTeamSide = myTeamParam;
  } else if (teamIdParam) {
    userTeamSide = mapTeamIdToSide(teamIdParam, gameData, homeCore, awayCore, homeTeamId, awayTeamId);
  }
  if (userTeamSide == null && !teamIdParam && !myTeamParam && typeof localStorage !== 'undefined') {
    const fid = urlParams.get('franchise_id');
    const stored =
      fid && window.FranchiseLS
        ? window.FranchiseLS.getLastGameUserTeamSide(fid)
        : null;
    if (stored === 'home' || stored === 'away') userTeamSide = stored;
  }
  if (bannerTeamParam) {
    return resolveBannerTeamNameFromParams(bannerTeamParam, homeLabel, awayLabel)
      || resolveBannerTeamNameFromParams(bannerTeamParam, homeCore, awayCore)
      || '';
  }
  if (userTeamSide === 'away') return awayLabel;
  if (userTeamSide === 'home') return homeLabel;
  return '';
}

function resolveUserTeamSideForPhaseBPulse(urlParams) {
  if (!gameData || !urlParams) return null;
  const { homeTeam, awayTeam, homeTeamId, awayTeamId } = getTeamContext();
  const homeCore = teamCoreName(homeTeam, 'Home Team');
  const awayCore = teamCoreName(awayTeam, 'Away Team');
  const myTeamParam = urlParams.get('my_team');
  const teamIdParam = urlParams.get('team_id') || urlParams.get('user_team_id');
  if (myTeamParam === 'home' || myTeamParam === 'away') return myTeamParam;
  if (teamIdParam) return mapTeamIdToSide(teamIdParam, gameData, homeCore, awayCore, homeTeamId, awayTeamId);
  if (typeof localStorage !== 'undefined') {
    const fid = urlParams.get('franchise_id');
    const stored =
      fid && window.FranchiseLS
        ? window.FranchiseLS.getLastGameUserTeamSide(fid)
        : null;
    if (stored === 'home' || stored === 'away') return stored;
  }
  return null;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const gameId = urlParams.get('game_id');
  const pregame = urlParams.get('pregame') === '1';
  const homeTeamName = urlParams.get('home');
  const awayTeamName = urlParams.get('away');
  const franchiseId = urlParams.get('franchise_id');
  const tournamentId = urlParams.get('tournament_id');
  const mode = urlParams.get('mode');
  
  console.log('📋 Box Score page loaded:', {
    gameId,
    pregame,
    homeTeamName,
    awayTeamName,
    franchiseId,
    tournamentId,
    mode,
    fullUrl: window.location.href,
    allParams: Object.fromEntries(urlParams.entries())
  });
  
  if (!gameId) {
    console.warn('⚠️ No gameId in URL params');
    if (!homeTeamName || !awayTeamName) {
      console.error('❌ No game_id provided and team names missing');
      return;
    }
    try {
      await loadPreGameData({ homeTeamName, awayTeamName, franchiseId, tournamentId, mode });
      renderBoxScore();
      setupTabs();
    } catch (e) {
      console.error('❌ Error loading pregame box score:', e);
    } finally {
      // ✅ Always setup locker room button, even if data loading fails
      setupLockerRoomButton();
    }
    return;
  }

  try {
    await loadGameData(gameId);
    renderBoxScore();
    setupTabs();
  } catch (error) {
    console.error('❌ Error loading box score:', error);
  } finally {
    // ✅ Always setup locker room button, even if data loading fails
    setupLockerRoomButton();
  }
});

// Fetch game data from API and merge with full rosters
async function loadGameData(gameId) {
  console.log('📥 Loading game data for gameId:', gameId);
  const response = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`), { headers: API_CONFIG.getAuthHeaders() });
  if (!response.ok) {
    console.error('❌ Failed to fetch game data:', response.status, response.statusText);
    throw new Error(`Failed to fetch game data: ${response.statusText}`);
  }
  gameData = await response.json();
  const tac = gameData.team_attribute_changes || {};
  const tacKeys = Object.keys(tac);
  console.log('✅ Game data loaded:', {
    gameId,
    hasBoxScore: !!gameData.box_score,
    boxScoreKeys: gameData.box_score ? Object.keys(gameData.box_score) : [],
    hasPlayers: !!gameData.players,
    score: gameData.score,
    quarter: gameData.quarter,
    home_team_id: gameData.home_team_id,
    away_team_id: gameData.away_team_id,
    hasTeams: !!gameData.teams,
    hasTeamAttributeChanges: tacKeys.length > 0,
    teamAttributeChangesKeys: tacKeys
  });
  console.log('🔍 [ATTR-CHANGES] loadGameData: team_attribute_changes keys=', tacKeys, 'key types=', tacKeys.map(k => typeof k), 'raw=', tac);
  
  // ✅ DEBUG: Log box_score structure in detail
  if (gameData.box_score) {
    for (const [teamKey, teamBox] of Object.entries(gameData.box_score)) {
      if (typeof teamBox === 'object' && teamBox !== null) {
        const playerCount = Object.keys(teamBox).length;
        const samplePlayers = Object.entries(teamBox).slice(0, 3).map(([pos, p]) => ({
          pos,
          playerId: p?.playerId || p?.player_id,
          name: p?.name,
          hasStats: p && typeof p === 'object' && Object.keys(p).length > 0
        }));
        console.log(`🔍 [BOX-SCORE DEBUG] Initial box_score[${teamKey}]:`, {
          playerCount,
          samplePlayers
        });
      } else {
        console.warn(`⚠️ [BOX-SCORE DEBUG] box_score[${teamKey}] is not an object:`, typeof teamBox);
      }
    }
  } else {
    console.warn('⚠️ [BOX-SCORE DEBUG] gameData.box_score is missing or empty!');
  }
  
  // Fetch full rosters to ensure all 12 players are shown
  const urlParams = new URLSearchParams(window.location.search);
  console.log('🔍 [BOX-SCORE] loadGameData - URL params:', Object.fromEntries(urlParams.entries()));
  // ✅ UNIFIED STRUCTURE: Extract team names from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  const homeTeamName = urlParams.get('home') || 
                       homeTeamObj?.name ||
                       (typeof gameData.home_team === 'object' ? gameData.home_team?.name : gameData.home_team) ||
                       gameData.home_team?.name;
  const awayTeamName = urlParams.get('away') || 
                       awayTeamObj?.name ||
                       (typeof gameData.away_team === 'object' ? gameData.away_team?.name : gameData.away_team) ||
                       gameData.away_team?.name;
  const franchiseId = urlParams.get('franchise_id');
  const tournamentId = urlParams.get('tournament_id');
  const mode = urlParams.get('mode');
  
  if (homeTeamName && awayTeamName) {
    await mergeFullRosters(homeTeamName, awayTeamName, franchiseId, tournamentId, mode, homeTeamId, awayTeamId);
  }
}

// Fetch and merge full rosters with game data to ensure all 12 players are shown
async function mergeFullRosters(homeTeamName, awayTeamName, franchiseId, tournamentId, mode, homeTeamId = null, awayTeamId = null) {
  if (mode === 'practice_squad') {
    return;
  }
  console.log('🔍 [BOX-SCORE DEBUG] mergeFullRosters() called:', {
    homeTeamName,
    awayTeamName,
    franchiseId,
    tournamentId,
    mode,
    homeTeamId,
    awayTeamId,
    hasGameData: !!gameData,
    boxScoreKeys: gameData?.box_score ? Object.keys(gameData.box_score) : [],
    boxScoreStructure: gameData?.box_score
  });

  const fetchRoster = async (team) => {
    // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
    let path = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(team)}`);
    const params = new URLSearchParams();
    if (mode === 'franchise' && franchiseId) {
      params.append('franchise_id', franchiseId);
    } else if (mode === 'tournament' && tournamentId) {
      params.append('tournament_id', tournamentId);
    }
    // Note: Single game mode has no params (loads from universal collection)
    if (params.toString()) {
      path += `?${params.toString()}`;
    }
    console.log(`🔍 [BOX-SCORE DEBUG] Fetching roster for ${team} from: ${path} (mode=${mode || 'single'})`);
    const res = await fetch(path);
    if (!res.ok) {
      console.error(`❌ [BOX-SCORE DEBUG] Failed to load roster for ${team}: ${res.status} ${res.statusText}`);
      throw new Error(`Failed to load roster for ${team}`);
    }
    const data = await res.json();
    const players = Array.isArray(data.players) ? data.players : [];
    console.log(`🔍 [BOX-SCORE DEBUG] Roster fetch for ${team}: ${players.length} players returned`);
    if (players.length > 0) {
      const samplePlayer = players[0];
      console.log(`🔍 [BOX-SCORE DEBUG] Sample player from ${team}:`, {
        _id: samplePlayer._id,
        name: samplePlayer.name,
        playerId: samplePlayer.playerId,
        hasAttributes: !!samplePlayer.attributes
      });
    }
    return players;
  };

  const [homeRoster, awayRoster] = await Promise.all([
    fetchRoster(homeTeamName),
    fetchRoster(awayTeamName),
  ]);

  // ✅ SS&S: Get team_id values for box_score lookup (use parameters if provided, otherwise get from gameData)
  const finalHomeTeamId = homeTeamId || gameData?.home_team_id;
  const finalAwayTeamId = awayTeamId || gameData?.away_team_id;
  
  console.log('🔍 [BOX-SCORE DEBUG] After roster fetch:', {
    homeRosterCount: homeRoster.length,
    awayRosterCount: awayRoster.length,
    homeTeamId: finalHomeTeamId,
    awayTeamId: finalAwayTeamId,
    boxScoreKeys: gameData?.box_score ? Object.keys(gameData.box_score) : []
  });
  
  // Map roster players to box-score-ready format
  const mapPlayers = (players, teamKey, teamName, teamId) => {
    console.log(`🔍 [BOX-SCORE DEBUG] mapPlayers() for ${teamKey} (${teamName}):`, {
      playerCount: players.length,
      teamId,
      boxScoreKeys: gameData?.box_score ? Object.keys(gameData.box_score) : []
    });
    
    // ✅ FIX: Normalize team name to canonical format (uppercase with underscores) for box_score lookup
    // Box score keys are in canonical format (e.g., "BENTLEY_TRUMAN") but team names are "Bentley-Truman"
    const normalizeToCanonical = (name) => {
      if (!name) return null;
      return name.replace(/-/g, '_').replace(/\s+/g, '_').toUpperCase();
    };
    const canonicalTeamName = normalizeToCanonical(teamName);
    
    // ✅ SS&S: box_score uses team_id keys (canonical format), fallback to normalized team_name
    const boxScore = (teamId && gameData.box_score?.[teamId]) || 
                     (canonicalTeamName && gameData.box_score?.[canonicalTeamName]) || 
                     gameData.box_score?.[teamName] || {};
    console.log(`🔍 [BOX-SCORE DEBUG] Box score lookup for ${teamKey}:`, {
      teamId,
      teamName,
      canonicalTeamName,
      usingTeamId: !!(teamId && gameData.box_score?.[teamId]),
      usingCanonicalName: !!(canonicalTeamName && gameData.box_score?.[canonicalTeamName]),
      usingTeamName: !!gameData.box_score?.[teamName],
      boxScoreKeys: Object.keys(boxScore),
      boxScorePlayerCount: Object.keys(boxScore).length
    });
    
    return players.map((p, idx) => {
      // Check if this player is in the game data (lineup players)
      const gamePlayer = gameData.players?.find(
        gp => (gp.playerId || gp._id || gp.player_id) === (p._id || p.playerId)
      );
      
      // Check if this player has box score stats
      const boxScorePlayer = Object.entries(boxScore).find(
        ([pos, playerData]) => 
          typeof playerData === 'object' && 
          playerData.name === p.name ||
          (playerData.playerId || playerData.player_id) === (p._id || p.playerId)
      )?.[1];
      
      if (idx < 2 || boxScorePlayer) { // Log first 2 players or any with box score match
        console.log(`🔍 [BOX-SCORE DEBUG] Player ${p.name} (${p._id}):`, {
          foundInGameData: !!gamePlayer,
          foundInBoxScore: !!boxScorePlayer,
          boxScorePlayerId: boxScorePlayer?.playerId || boxScorePlayer?.player_id,
          boxScorePlayerName: boxScorePlayer?.name,
          rosterPlayerId: p._id || p.playerId,
          rosterPlayerName: p.name
        });
      }

      // Calculate highest RT from position_ratings
      const posRatings = p.position_ratings || {};
      const rtValues = Object.values(posRatings);
      const highestRT = rtValues.length > 0 ? Math.max(...rtValues) : -Infinity;

      const finalStats = gamePlayer?.stats?.game || boxScorePlayer || gamePlayer?.stats || {};
      const hasStats = Object.keys(finalStats).length > 0;
      
      if (idx < 2 || hasStats) { // Log first 2 players or any with stats
        console.log(`🔍 [BOX-SCORE DEBUG] Final player data for ${p.name}:`, {
          playerId: p._id || p.playerId,
          hasStats,
          statKeys: Object.keys(finalStats),
          statSample: Object.keys(finalStats).slice(0, 5).reduce((acc, key) => {
            acc[key] = finalStats[key];
            return acc;
          }, {})
        });
      }
      
      return {
        playerId: p._id || p.playerId,
        team: teamKey,
        team_id: teamId || undefined, // mergeFullRosters must preserve canonical id for Play Usage top-scorer name lookup
        name: p.name,
        jersey: boxScorePlayer?.jersey !== undefined ? boxScorePlayer.jersey : (typeof p.jersey === 'number' ? p.jersey : (p.jersey !== undefined && p.jersey !== null && p.jersey !== '' ? p.jersey : '')),
        pos: p.pos || p.position || null,
        stats: finalStats,
        year: p.year || 'SR',
        highestRT: highestRT,
      };
    });
  };

  // Merge roster players with game data players and sort by RT
  const positionOrder = ['PG', 'SG', 'SF', 'PF', 'C'];
  const sortByRT = (players) => players.sort((a, b) => {
    const rtA = a.highestRT !== undefined ? a.highestRT : -Infinity;
    const rtB = b.highestRT !== undefined ? b.highestRT : -Infinity;
    if (rtA !== rtB) return rtB - rtA; // Descending order
    const aPos = positionOrder.indexOf(a.pos) !== -1 ? positionOrder.indexOf(a.pos) : 999;
    const bPos = positionOrder.indexOf(b.pos) !== -1 ? positionOrder.indexOf(b.pos) : 999;
    if (aPos !== bPos) return aPos - bPos;
    return (a.jersey || 0) - (b.jersey || 0);
  });
  
  const homeMapped = sortByRT(mapPlayers(homeRoster, 'home', homeTeamName, finalHomeTeamId));
  const awayMapped = sortByRT(mapPlayers(awayRoster, 'away', awayTeamName, finalAwayTeamId));
  
  gameData.players = [...homeMapped, ...awayMapped];
  
  const playersWithStats = gameData.players.filter(p => Object.keys(p.stats || {}).length > 0);
  console.log(`🔍 [BOX-SCORE DEBUG] Merged full rosters:`, {
    homeRosterCount: homeRoster.length,
    awayRosterCount: awayRoster.length,
    totalMappedPlayers: gameData.players.length,
    playersWithStats: playersWithStats.length,
    samplePlayerWithStats: playersWithStats[0] ? {
      name: playersWithStats[0].name,
      playerId: playersWithStats[0].playerId,
      statKeys: Object.keys(playersWithStats[0].stats || {})
    } : null
  });
}

// Render all box score sections
function renderBoxScore() {
  if (!gameData) return;

  renderHeader();
  renderQuarterScoring();
  renderPlayerOfTheGameSection();
  renderPlayerStats();
  renderTeamStats();
  renderScoutingNotes();
  renderPlayUsageForBoxScore();
  renderTeamAttributeChangesForTab('home');
  renderTeamAttributeChangesForTab('away');
}

async function renderPlayerOfTheGameSection() {
  const section = document.getElementById('potg-section');
  const playerLine = document.getElementById('potg-player-line');
  const statsLine = document.getElementById('potg-stats-line');
  const potgPortrait = document.getElementById('potg-portrait');
  if (!section || !playerLine || !statsLine) return;

  const urlParams = new URLSearchParams(window.location.search);
  const isPregame = urlParams.get('pregame') === '1';
  if (isPregame) {
    section.style.display = 'none';
    return;
  }

  const isGameComplete = isGameCompleteForPotg(gameData);
  if (!isGameComplete) {
    playerLine.textContent = '';
    statsLine.textContent = '';
    if (potgPortrait) {
      potgPortrait.removeAttribute('src');
      potgPortrait.style.display = 'none';
    }
    return;
  }

  try {
    const staticBase = (typeof window !== 'undefined' && window.API_CONFIG?.getStaticPath)
      ? window.API_CONFIG.getStaticPath()
      : '';
    const { calculatePlayerOfTheGame } = await import(`${staticBase}/js/shared/potg.js`);
    const gameId = urlParams.get('game_id') || '';
    const potg = calculatePlayerOfTheGame(gameData, { gameId });

    if (!potg) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    playerLine.textContent = `${potg.name} - ${potg.teamName}`;
    statsLine.textContent = `${potg.stats.pts} PTS  ${potg.stats.reb} REB  ${potg.stats.ast} AST  ${potg.stats.stl} STL  ${potg.stats.blk} BLK  ${potg.stats.defPct} DEF%`;
    if (potgPortrait && potg.playerId) {
      potgPortrait.style.display = '';
      potgPortrait.src = potg.photo || (
        window.API_CONFIG?.getPlayerImageUrl
          ? window.API_CONFIG.getPlayerImageUrl(potg.playerId, { size: 'card' })
          : `${staticBase}/images/players/${potg.playerId}.png`
      );
      potgPortrait.alt = potg.name || '';
      potgPortrait.onerror = function () {
        this.onerror = null;
        const api = window.API_CONFIG;
        const ensure = potg.portraitSource === 'recruit' && potg.imageId
          ? api?.ensureRecruitImage?.(potg.imageId)
          : api?.ensurePlayerImage?.(api.currentFranchiseId?.(), potg.playerId);
        Promise.resolve(ensure).then(() => {
          this.onerror = () => {
            this.onerror = null;
            this.src = api?.getGenericHeadshotUrl
              ? api.getGenericHeadshotUrl({ size: 'card' })
              : `${staticBase}/images/players/generic_headshot.png`;
          };
          const retryUrl = potg.portraitSource === 'recruit' && potg.imageId
            ? api?.getRecruitImageUrl?.(potg.imageId, { size: 'card' })
            : api?.getPlayerImageUrl?.(potg.playerId, { size: 'card' });
          const resolvedRetryUrl = retryUrl || potg.photo;
          if (!resolvedRetryUrl) {
            this.onerror();
            return;
          }
          this.src = `${resolvedRetryUrl}${resolvedRetryUrl.includes('?') ? '&' : '?'}r=1`;
        });
      };
    } else if (potgPortrait) {
      potgPortrait.style.display = 'none';
    }
  } catch (err) {
    console.warn('[box-score] Failed to render POTG section:', err);
    section.style.display = 'none';
  }
}

function isGameCompleteForPotg(data) {
  if (!data || typeof data !== 'object') return false;

  if (data.is_final === true || data.finalized === true || data.game_complete === true) {
    return true;
  }

  const status = String(data.status || data.game_status || '').toLowerCase();
  if (['complete', 'completed', 'final', 'finalized'].includes(status)) {
    return true;
  }

  // Conservative fallback for older game docs without explicit completion flags.
  const quarter = Number(data.quarter || 0);
  const timeRemaining = Number(data.time_remaining);
  const clock = String(data.clock || '').trim();
  const score = data.score || {};
  const teamsObj = data.teams || {};
  const homeTeamName = (data.home_team_id && teamsObj[data.home_team_id]?.name) || data.home_team?.name || 'Home Team';
  const awayTeamName = (data.away_team_id && teamsObj[data.away_team_id]?.name) || data.away_team?.name || 'Away Team';
  const homeScore = Number(score[homeTeamName] ?? data.home_team?.score ?? 0);
  const awayScore = Number(score[awayTeamName] ?? data.away_team?.score ?? 0);
  const hasWinner = homeScore !== awayScore;
  const clockAtZero = clock === '0:00' || clock === '00:00';
  const noClockData = !Number.isFinite(timeRemaining) && !clock;

  if (quarter > 4 && hasWinner && (clockAtZero || !Number.isFinite(timeRemaining) || timeRemaining <= 0 || noClockData)) return true;
  if (quarter === 4 && hasWinner && (clockAtZero || (Number.isFinite(timeRemaining) && timeRemaining <= 0) || noClockData)) return true;

  return false;
}

// Build zeroed box score data from rosters when viewing pre-game
async function loadPreGameData({ homeTeamName, awayTeamName, franchiseId, tournamentId, mode }) {
  const fetchRoster = async (team) => {
    // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
    let path = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(team)}`);
    const params = new URLSearchParams();
    if (mode === 'franchise' && franchiseId) {
      params.append('franchise_id', franchiseId);
    } else if (mode === 'tournament' && tournamentId) {
      params.append('tournament_id', tournamentId);
    }
    if (params.toString()) {
      path += `?${params.toString()}`;
    }
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Failed to load roster for ${team}`);
    const data = await res.json();
    return Array.isArray(data.players) ? data.players : [];
  };

  const [homeRoster, awayRoster] = await Promise.all([
    fetchRoster(homeTeamName),
    fetchRoster(awayTeamName),
  ]);

  // Map players to box-score-ready format with zeroed stats
  const mapPlayers = (players, teamKey) =>
    players.map((p) => {
      // Calculate highest RT from position_ratings
      const posRatings = p.position_ratings || {};
      const rtValues = Object.values(posRatings);
      const highestRT = rtValues.length > 0 ? Math.max(...rtValues) : -Infinity;
      
      return {
        playerId: p._id,
        team: teamKey,
        name: p.name,
        jersey: (typeof p.jersey === 'number') ? p.jersey : (p.jersey !== undefined && p.jersey !== null && p.jersey !== '' ? p.jersey : ''),
        pos: p.pos || p.position || null,
        stats: {}, // zeroed in renderer
        year: p.year || 'SR',
        highestRT: highestRT,
      };
    });

  // Sort players by highest RT (descending) before storing
  const homePlayers = mapPlayers(homeRoster, 'home');
  const awayPlayers = mapPlayers(awayRoster, 'away');
  const positionOrder = ['PG', 'SG', 'SF', 'PF', 'C'];
  
  const sortByRT = (players) => players.sort((a, b) => {
    const rtA = a.highestRT !== undefined ? a.highestRT : -Infinity;
    const rtB = b.highestRT !== undefined ? b.highestRT : -Infinity;
    if (rtA !== rtB) return rtB - rtA; // Descending order
    const aPos = positionOrder.indexOf(a.pos) !== -1 ? positionOrder.indexOf(a.pos) : 999;
    const bPos = positionOrder.indexOf(b.pos) !== -1 ? positionOrder.indexOf(b.pos) : 999;
    if (aPos !== bPos) return aPos - bPos;
    return (a.jersey || 0) - (b.jersey || 0);
  });

  gameData = {
    home_team: { name: homeTeamName, score: 0 },
    away_team: { name: awayTeamName, score: 0 },
    score: { [homeTeamName]: 0, [awayTeamName]: 0 },
    points_by_quarter: { [homeTeamName]: [0, 0, 0, 0], [awayTeamName]: [0, 0, 0, 0] },
    players: [
      ...sortByRT(homePlayers),
      ...sortByRT(awayPlayers),
    ],
    box_score: {},
    team_totals: { [homeTeamName]: {}, [awayTeamName]: {} },
    team_stats: {},
  };
}

/** Core identity for score{} lookup; overlay for labels. */
function teamCoreName(teamObj, fallback) {
  return (teamObj && teamObj.name) || fallback || 'Team';
}
function teamDisplayLabel(teamObj, fallback) {
  if (!teamObj) return fallback || 'Team';
  return teamObj.display_name || teamObj.name || fallback || 'Team';
}

// Render header with team names and scores
function renderHeader() {
  const { homeTeam: homeTeamObj, awayTeam: awayTeamObj } = getTeamContext();
  const score = gameData.score || {};
  const homeCore = teamCoreName(homeTeamObj, 'Home Team');
  const awayCore = teamCoreName(awayTeamObj, 'Away Team');
  const homeLabel = teamDisplayLabel(homeTeamObj, 'Home Team');
  const awayLabel = teamDisplayLabel(awayTeamObj, 'Away Team');
  const homeScore = score[homeCore] || homeTeamObj.score || 0;
  const awayScore = score[awayCore] || awayTeamObj.score || 0;
  const homeTeamId = gameData?.home_team_id;
  const awayTeamId = gameData?.away_team_id;

  document.getElementById('home-team-name').textContent = homeLabel;
  document.getElementById('away-team-name').textContent = awayLabel;
  document.getElementById('home-score').textContent = homeScore;
  document.getElementById('away-score').textContent = awayScore;

  const homeNameEl = document.getElementById('home-team-name');
  const awayNameEl = document.getElementById('away-team-name');
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  const homeWon = homeScore > awayScore;
  const awayWon = awayScore > homeScore;
  const winningColor = '#ffffff';
  const losingColor = 'rgba(255,255,255,0.45)';
  homeNameEl.style.color = homeWon ? winningColor : awayWon ? losingColor : 'rgba(255, 255, 255, 0.6)';
  homeScoreEl.style.color = homeWon ? winningColor : awayWon ? losingColor : '#ffffff';
  awayNameEl.style.color = awayWon ? winningColor : homeWon ? losingColor : 'rgba(255, 255, 255, 0.6)';
  awayScoreEl.style.color = awayWon ? winningColor : homeWon ? losingColor : '#ffffff';
  document.querySelectorAll('#header-content .score, #header-content .team-name').forEach(el => {
    el.style.textShadow = '0 2px 8px rgba(0,0,0,0.9), 0 0 20px rgba(0,0,0,0.7)';
  });

  const homeTabButton = document.querySelector('.tab-button[data-team="home"]');
  const awayTabButton = document.querySelector('.tab-button[data-team="away"]');
  const homePrimaryColor = homeTeamObj?.colors?.primary_color || homeTeamObj?.primary_color || '#F79420';
  const awayPrimaryColor = awayTeamObj?.colors?.primary_color || awayTeamObj?.primary_color || '#4065AF';

  const urlParams = new URLSearchParams(window.location.search);
  const bannerTeamParam = (urlParams.get('banner_team') || '').trim();
  const myTeamParam = urlParams.get('my_team');
  const teamIdParam = urlParams.get('team_id') || urlParams.get('user_team_id');

  let userTeamSide = null;
  if (myTeamParam === 'home' || myTeamParam === 'away') {
    userTeamSide = myTeamParam;
  } else if (teamIdParam) {
    userTeamSide = mapTeamIdToSide(teamIdParam, gameData, homeCore, awayCore, homeTeamId, awayTeamId);
  }
  if (userTeamSide == null && !teamIdParam && !myTeamParam && typeof localStorage !== 'undefined') {
    const fid = urlParams.get('franchise_id');
    const stored =
      fid && window.FranchiseLS
        ? window.FranchiseLS.getLastGameUserTeamSide(fid)
        : null;
    if (stored === 'home' || stored === 'away') userTeamSide = stored;
  }

  // Banner / assets use display labels; side mapping uses core identity.
  const userTeamNameForBanner = bannerTeamParam
    ? resolveBannerTeamNameFromParams(bannerTeamParam, homeLabel, awayLabel)
      || resolveBannerTeamNameFromParams(bannerTeamParam, homeCore, awayCore)
    : userTeamSide === 'away'
    ? awayLabel
    : userTeamSide === 'home'
    ? homeLabel
    : null;

  console.log('[box-score renderHeader] getTeamAssetPath scope', typeof getTeamAssetPath, typeof window !== 'undefined' ? typeof window.getTeamAssetPath : 'n/a');

  const resolveTeamBannerPath =
    typeof getTeamAssetPath === 'function'
      ? getTeamAssetPath
      : (typeof window !== 'undefined' && typeof window.getTeamAssetPath === 'function'
        ? window.getTeamAssetPath
        : null);

  const bannerPathFromTeamName = (name) => {
    const slug = String(name).toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
    return `/images/teams/${slug}/${slug}_banner_primary.jpg`;
  };

  let bannerUrl;
  if (userTeamNameForBanner) {
    bannerUrl = resolveTeamBannerPath
      ? resolveTeamBannerPath(userTeamNameForBanner, 'banner_primary')
      : bannerPathFromTeamName(userTeamNameForBanner);
  } else {
    bannerUrl = resolveTeamBannerPath
      ? resolveTeamBannerPath(null, 'banner_primary')
      : '/images/teams/general/general_banner_primary.jpg';
  }

  const header = document.getElementById('box-score-header');
  if (header && bannerUrl) {
    header.style.backgroundImage = `
      linear-gradient(to bottom, rgba(13,17,36,0.15) 0%, rgba(13,17,36,0.5) 50%, rgba(13,17,36,0.92) 75%, rgba(13,17,36,0.98) 100%),
      linear-gradient(to right, rgba(13,17,36,0.0) 0%, rgba(13,17,36,0.0) 30%, rgba(13,17,36,0.7) 60%, rgba(13,17,36,0.85) 100%),
      url('${bannerUrl}')
    `;
    header.style.backgroundSize = 'cover';
    header.style.backgroundPosition = 'center';
    console.log('[box-score renderHeader] header.style.backgroundImage =', JSON.stringify(header.style.backgroundImage));
  }

  if (homeTabButton) {
    homeTabButton.textContent = homeLabel;
    homeTabButton.style.setProperty('--tab-color', homePrimaryColor);
    homeTabButton.style.setProperty('--tab-color-rgb', hexToRgbString(homePrimaryColor));
  }
  if (awayTabButton) {
    awayTabButton.textContent = awayLabel;
    awayTabButton.style.setProperty('--tab-color', awayPrimaryColor);
    awayTabButton.style.setProperty('--tab-color-rgb', hexToRgbString(awayPrimaryColor));
  }
}

// Render quarter scoring table
function renderQuarterScoring() {
  // ✅ UNIFIED STRUCTURE: Get team data from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  
  const homeTeam = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : (gameData.home_team || {});
  const awayTeam = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : (gameData.away_team || {});
  const pointsByQuarter = gameData.points_by_quarter || {};
  const score = gameData.score || {};

  const homeCore = teamCoreName(homeTeam, 'Home Team');
  const awayCore = teamCoreName(awayTeam, 'Away Team');
  const homeLabel = teamDisplayLabel(homeTeam, 'Home Team');
  const awayLabel = teamDisplayLabel(awayTeam, 'Away Team');
  const homePoints = pointsByQuarter[homeCore] || [0, 0, 0, 0];
  const awayPoints = pointsByQuarter[awayCore] || [0, 0, 0, 0];

  // Check for overtime
  const hasOT = homePoints.length > 4 || awayPoints.length > 4;
  if (hasOT) {
    document.getElementById('ot-header').style.display = '';
    document.getElementById('home-ot-score').style.display = '';
    document.getElementById('away-ot-score').style.display = '';
    
    // Sum all OT periods
    const homeOT = homePoints.slice(4).reduce((a, b) => a + b, 0);
    const awayOT = awayPoints.slice(4).reduce((a, b) => a + b, 0);
    document.getElementById('home-ot-score').textContent = homeOT;
    document.getElementById('away-ot-score').textContent = awayOT;
  }

  // Render quarter scores
  for (let i = 0; i < 4; i++) {
    const homeCells = document.querySelectorAll(`#home-quarter-row .quarter-score[data-quarter="${i}"]`);
    const awayCells = document.querySelectorAll(`#away-quarter-row .quarter-score[data-quarter="${i}"]`);
    homeCells.forEach(cell => cell.textContent = homePoints[i] || 0);
    awayCells.forEach(cell => cell.textContent = awayPoints[i] || 0);
  }

  // Render final scores
  const homeFinal = score[homeCore] || homeTeam.score || homePoints.reduce((a, b) => a + b, 0);
  const awayFinal = score[awayCore] || awayTeam.score || awayPoints.reduce((a, b) => a + b, 0);
  document.getElementById('home-final-score').textContent = homeFinal;
  document.getElementById('away-final-score').textContent = awayFinal;

  // Update team names in table (chrome)
  document.getElementById('home-quarter-team-name').textContent = homeLabel;
  document.getElementById('away-quarter-team-name').textContent = awayLabel;
}

// Render player stats for both teams
function renderPlayerStats() {
  const players = gameData.players || [];
  const boxScore = gameData.box_score || {};

  // Separate players by team
  const homePlayers = players.filter(p => p.team === 'home');
  const awayPlayers = players.filter(p => p.team === 'away');

  // ✅ UNIFIED STRUCTURE: Get team names from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  const homeTeamName = homeTeamObj?.name || gameData.home_team?.name || 'Home Team';
  const awayTeamName = awayTeamObj?.name || gameData.away_team?.name || 'Away Team';
  
  // box_score structure: { teamName: { pos: { name, FGM, FGA, ... } } }
  const homeBoxScore = boxScore[homeTeamName] || {};
  const awayBoxScore = boxScore[awayTeamName] || {};

  // Combine lineup players with box_score players
  const allHomePlayers = combinePlayersAndBoxScore(homePlayers, homeBoxScore, homeTeamName);
  const allAwayPlayers = combinePlayersAndBoxScore(awayPlayers, awayBoxScore, awayTeamName);

  renderPlayerStatsTable('home', allHomePlayers);
  renderPlayerStatsTable('away', allAwayPlayers);
}

// Combine roster players with box_score to get all 12 players with stats
// Now rosterPlayers includes all 12 players from the roster, not just lineup players
// box_score structure: { pos: { name, FGM, FGA, ... } } (stats are direct properties)
function combinePlayersAndBoxScore(rosterPlayers, boxScore, teamName) {
  const playerMap = new Map();
  
  // Add all roster players (all 12 players, not just lineup)
  rosterPlayers.forEach(p => {
    playerMap.set(p.playerId || p._id, {
      ...p,
      stats: p.stats?.game || p.stats || {},
      year: p.year || 'SR', // Use year from player data or default
      jersey: p.jersey !== undefined ? p.jersey : (typeof p.jerseyNumber === 'number' ? p.jerseyNumber : (p.jerseyNumber !== undefined && p.jerseyNumber !== null && p.jerseyNumber !== '' ? p.jerseyNumber : (typeof p.jersey_number === 'number' ? p.jersey_number : (p.jersey_number !== undefined && p.jersey_number !== null && p.jersey_number !== '' ? p.jersey_number : '')))) // Preserve jersey from multiple possible sources, handle 0
    });
  });

  // Add box_score players (includes bench)
  // box_score structure: { pos: { name, FGM, FGA, ... } } (stats are direct properties)
  Object.entries(boxScore).forEach(([pos, playerData]) => {
    if (typeof playerData === 'object' && playerData.name) {
      // Try to find matching player by name or position
      const existingPlayer = Array.from(playerMap.values()).find(
        p => p.name === playerData.name || (p.pos === pos && p.name)
      );
      
      if (existingPlayer) {
        // Update stats from box_score (stats are direct properties, not nested)
        // Filter out non-stat properties (name, jersey, etc.)
        const statKeys = ['FGM', 'FGA', '3PTM', '3PTA', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 
                         'AST', 'STL', 'BLK', 'TO', 'F', 'MIN', 'PTS', 'PIP', 'FB_PTS',
                         'DEF_A', 'DEF_S', 'HELP_D', 'SCR_A', 'SCR_S',
                         'FB_A', 'FB_S', 'FB_A_D', 'FB_S_D', 'FB_F_D',
                         'Outlet_A', 'Outlet_S', 'Outlet_Score', 'Outlet_Score_List', 'Outlet_Score_Cum',
                         'HCT_A', 'HCT_S', 'HCT_A_D', 'HCT_S_D',
                         'FCP_A', 'FCP_S', 'FCP_A_D', 'FCP_S_D'];
        const boxStats = {};
        statKeys.forEach(key => {
          if (playerData[key] !== undefined) {
            boxStats[key] = playerData[key];
          }
        });
        existingPlayer.stats = { ...existingPlayer.stats, ...boxStats };
        // Preserve jersey if it exists in box_score, otherwise keep existing jersey
        if (playerData.jersey !== undefined) {
          existingPlayer.jersey = playerData.jersey;
        }
      } else {
        // New player from box_score (bench player)
        const statKeys = ['FGM', 'FGA', '3PTM', '3PTA', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 
                         'AST', 'STL', 'BLK', 'TO', 'F', 'MIN', 'PTS', 'PIP', 'FB_PTS',
                         'DEF_A', 'DEF_S', 'HELP_D', 'SCR_A', 'SCR_S',
                         'FB_A', 'FB_S', 'FB_A_D', 'FB_S_D', 'FB_F_D',
                         'Outlet_A', 'Outlet_S', 'Outlet_Score', 'Outlet_Score_List', 'Outlet_Score_Cum',
                         'HCT_A', 'HCT_S', 'HCT_A_D', 'HCT_S_D',
                         'FCP_A', 'FCP_S', 'FCP_A_D', 'FCP_S_D'];
        const boxStats = {};
        statKeys.forEach(key => {
          if (playerData[key] !== undefined) {
            boxStats[key] = playerData[key];
          }
        });
        playerMap.set(`bench_${pos}`, {
          playerId: playerData.playerId || `bench_${pos}`,
          name: playerData.name || `Player ${pos}`,
          jersey: playerData.jersey !== undefined ? playerData.jersey : (typeof playerData.jerseyNumber === 'number' ? playerData.jerseyNumber : (playerData.jerseyNumber !== undefined && playerData.jerseyNumber !== null && playerData.jerseyNumber !== '' ? playerData.jerseyNumber : (typeof playerData.jersey_number === 'number' ? playerData.jersey_number : (playerData.jersey_number !== undefined && playerData.jersey_number !== null && playerData.jersey_number !== '' ? playerData.jersey_number : '')))),
          pos: pos,
          stats: boxStats,
          year: playerData.year || 'SR'
        });
      }
    }
  });

  // Sort by highest RT (descending), then by position if RT is equal
  const positionOrder = ['PG', 'SG', 'SF', 'PF', 'C'];
  return Array.from(playerMap.values()).sort((a, b) => {
    // Primary sort: highest RT (descending)
    const rtA = a.highestRT !== undefined ? a.highestRT : -Infinity;
    const rtB = b.highestRT !== undefined ? b.highestRT : -Infinity;
    if (rtA !== rtB) return rtB - rtA; // Descending order
    
    // Secondary sort: position if RT is equal
    const aPos = positionOrder.indexOf(a.pos) !== -1 ? positionOrder.indexOf(a.pos) : 999;
    const bPos = positionOrder.indexOf(b.pos) !== -1 ? positionOrder.indexOf(b.pos) : 999;
    if (aPos !== bPos) return aPos - bPos;
    
    // Tertiary sort: jersey number if position is also equal
    return (a.jersey || 0) - (b.jersey || 0);
  });
}

// Render player stats table for a team
function renderPlayerStatsTable(team, players) {
  const tbody = document.getElementById(`${team}-player-stats-body`);
  tbody.innerHTML = '';

  // Ensure we have at least 12 rows (pad with empty rows if needed)
  const maxRows = Math.max(12, players.length);
  
  for (let i = 0; i < maxRows; i++) {
    const player = players[i];
    const row = document.createElement('tr');
    
    if (player) {
      const stats = player.stats || {};
      const name = player.name || 'Unknown';
      // ✅ FIX: Handle jersey number 0 - this is just an intermediate variable, proper handling happens at line 502+
      const jersey = (typeof player.jersey === 'number') ? player.jersey : (player.jersey !== undefined && player.jersey !== null && player.jersey !== '' ? player.jersey : '');
      
      // Calculate TREB, DEF%, and SCR%
      const treb = (stats.DREB || 0) + (stats.OREB || 0);
      const defa = stats.DEF_A || 0;
      const defs = stats.DEF_S || 0;
      const defPct = defa > 0 ? ((defs / defa) * 100).toFixed(0) : '0';
      const scra = stats.SCR_A || 0;
      const scrs = stats.SCR_S || 0;
      const scrPct = scra > 0 ? ((scrs / scra) * 100).toFixed(0) : '0';
      
      // Format MIN (convert seconds to MM:SS or just minutes)
      const min = formatMinutes(stats.MIN || 0);
      
      // Format jersey number - check multiple possible fields and handle 0 as valid jersey number
      // Jersey can be a number (including 0) or string
      let jerseyNum = null;
      // Check in order: jersey, jerseyNumber, jersey_number
      // Allow 0 as a valid jersey number, only exclude undefined/null/empty string
      if (typeof jersey === 'number') {
        // Handle jersey as number (including 0)
        jerseyNum = jersey;
      } else if (jersey !== undefined && jersey !== null && jersey !== '') {
        jerseyNum = jersey;
      } else if (typeof player.jerseyNumber === 'number') {
        jerseyNum = player.jerseyNumber;
      } else if (player.jerseyNumber !== undefined && player.jerseyNumber !== null && player.jerseyNumber !== '') {
        jerseyNum = player.jerseyNumber;
      } else if (typeof player.jersey_number === 'number') {
        jerseyNum = player.jersey_number;
      } else if (player.jersey_number !== undefined && player.jersey_number !== null && player.jersey_number !== '') {
        jerseyNum = player.jersey_number;
      }
      
      // Debug logging (can be removed after verification)
      if (!jerseyNum && player.playerId) {
        console.log(`[Box Score] No jersey found for ${name} (${player.playerId}):`, {
          jersey,
          jerseyNumber: player.jerseyNumber,
          jersey_number: player.jersey_number,
          playerKeys: Object.keys(player)
        });
      }
      
      // Convert to string and display if we have a valid jersey (including 0)
      const jerseyDisplay = (jerseyNum !== null && jerseyNum !== undefined) ? ` (#${String(jerseyNum)})` : '';

      // Build row with clickable player name
      const nameCell = document.createElement('td');
      const nameLink = document.createElement('span');
      nameLink.className = 'player-name-link';
      nameLink.textContent = `${name}${jerseyDisplay}`;
      nameLink.style.cursor = 'pointer';
      nameLink.addEventListener('click', () => showSpecialStatsPopup(player));
      nameCell.appendChild(nameLink);
      
      // Clear row and build it properly
      row.innerHTML = '';
      row.appendChild(nameCell);
      row.appendChild(createTableCell(derivePtsFromShootingStats(stats)));
      row.appendChild(createTableCell(`${stats.FGM || 0}/${stats.FGA || 0}`));
      row.appendChild(createTableCell(`${stats['3PTM'] || 0}/${stats['3PTA'] || 0}`));
      row.appendChild(createTableCell(`${stats.FTM || 0}/${stats.FTA || 0}`));
      row.appendChild(createTableCell(stats.DREB || 0));
      row.appendChild(createTableCell(stats.OREB || 0));
      row.appendChild(createTableCell(treb));
      row.appendChild(createTableCell(stats.AST || 0));
      row.appendChild(createTableCell(stats.STL || 0));
      row.appendChild(createTableCell(stats.BLK || 0));
      row.appendChild(createTableCell(stats.F || 0));
      row.appendChild(createTableCell(stats.TO || 0));
      row.appendChild(createTableCell(defa));
      row.appendChild(createTableCell(`${defPct}%`));
      row.appendChild(createTableCell(scra));
      row.appendChild(createTableCell(`${scrPct}%`));
      row.appendChild(createTableCell(min));
    } else {
      // Empty row
      row.innerHTML = `
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
        <td>-</td>
      `;
    }
    
    tbody.appendChild(row);
  }
}

// Format minutes (convert seconds to integer minutes only)
function formatMinutes(seconds) {
  if (!seconds) return '0';
  return Math.floor(seconds / 60).toString();
}

// Helper function to create table cell
function createTableCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

// Render team stats
function renderTeamStats() {
  // ✅ UNIFIED STRUCTURE: Get team names from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  const teamTotals = gameData.team_totals || {};
  const homeTeamName = homeTeamObj?.name || gameData.home_team?.name || 'Home Team';
  const awayTeamName = awayTeamObj?.name || gameData.away_team?.name || 'Away Team';

  const homeTotals = teamTotals[homeTeamName] || {};
  const awayTotals = teamTotals[awayTeamName] || {};

  renderTeamStatsTable('home', homeTotals);
  renderTeamStatsTable('away', awayTotals);

  // Render special stats
  renderSpecialStats('home', homeTotals, homeTeamName);
  renderSpecialStats('away', awayTotals, awayTeamName);
}

// Render team stats table
function renderTeamStatsTable(team, totals) {
  const tbody = document.getElementById(`${team}-team-stats-body`);
  tbody.innerHTML = '';

  const row = document.createElement('tr');
  
  // Calculate TREB, DEF%, and percentages
  const treb = (totals.DREB || 0) + (totals.OREB || 0);
  const defa = totals.DEF_A || 0;
  const defs = totals.DEF_S || 0;
  const defPct = defa > 0 ? ((defs / defa) * 100).toFixed(0) : '0';
  const fgPct = totals.FGA > 0 ? ((totals.FGM || 0) / totals.FGA * 100).toFixed(1) : '0.0';
  const threePct = totals['3PTA'] > 0 ? ((totals['3PTM'] || 0) / totals['3PTA'] * 100).toFixed(1) : '0.0';
  const ftPct = totals.FTA > 0 ? ((totals.FTM || 0) / totals.FTA * 100).toFixed(1) : '0.0';
  const scrA = totals.SCR_A || 0;
  const scrS = totals.SCR_S || 0;
  const scrPct = scrA > 0 ? ((scrS / scrA) * 100).toFixed(1) : '0.0';

  row.innerHTML = `
    <td>${totals.PTS || 0}</td>
    <td>${totals.FGM || 0}/${totals.FGA || 0}</td>
    <td>${fgPct}%</td>
    <td>${totals['3PTM'] || 0}/${totals['3PTA'] || 0}</td>
    <td>${threePct}%</td>
    <td>${totals.FTM || 0}/${totals.FTA || 0}</td>
    <td>${ftPct}%</td>
    <td>${totals.DREB || 0}</td>
    <td>${totals.OREB || 0}</td>
    <td>${treb}</td>
    <td>${totals.AST || 0}</td>
    <td>${totals.STL || 0}</td>
    <td>${totals.BLK || 0}</td>
    <td>${totals.F || 0}</td>
    <td>${totals.TO || 0}</td>
    <td>${defa}</td>
    <td>${defPct}%</td>
    <td>${scrA}</td>
    <td>${scrPct}%</td>
  `;

  tbody.appendChild(row);
}

// Render special stats (Fast Break Points, PIP)
function renderSpecialStats(team, totals, teamName) {
  // Fast Breaks ratio is shown in Special Situations section, not here
  // Show Fast Break Points, Points In The Paint, and Points Off Turnovers
  document.getElementById(`${team}-fb-points`).textContent = totals.FB_PTS || 0;
  document.getElementById(`${team}-pip`).textContent = totals.PIP || 0;
  document.getElementById(`${team}-pot`).textContent = totals.POT || 0;
}

// Resolve attribute changes for a team from team_attribute_changes (SS&S: home_team_id / away_team_id).
function resolveChangesForTeamId(attributeChanges, teamId) {
  if (!attributeChanges || !teamId) {
    console.log('🔍 [ATTR-CHANGES] resolveChangesForTeamId: early return', { hasChanges: !!attributeChanges, teamId });
    return null;
  }
  let out = attributeChanges[teamId] || attributeChanges[String(teamId)] || null;
  if (out && typeof out === 'object' && Object.keys(out).length > 0) {
    console.log('🔍 [ATTR-CHANGES] resolveChangesForTeamId: matched direct', { teamId, keyUsed: attributeChanges[teamId] !== undefined ? 'teamId' : 'String(teamId)' });
    return out;
  }
  for (const key of Object.keys(attributeChanges)) {
    if (String(key) === String(teamId)) {
      console.log('🔍 [ATTR-CHANGES] resolveChangesForTeamId: matched via iteration', { teamId, key });
      return attributeChanges[key] || null;
    }
  }
  console.log('🔍 [ATTR-CHANGES] resolveChangesForTeamId: no match', { teamId, teamIdType: typeof teamId, keys: Object.keys(attributeChanges) });
  return null;
}

// Render Attribute Changes for one tab (home or away). Franchise only; uses gameData only.
function renderTeamAttributeChangesForTab(team) {
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  console.log('🔍 [ATTR-CHANGES] renderTeamAttributeChangesForTab', { team, mode, hasGameData: !!gameData, urlParams: Object.fromEntries(urlParams.entries()) });
  if (mode !== 'franchise' || !gameData) {
    console.log('🔍 [ATTR-CHANGES] renderTeamAttributeChangesForTab: early return (not franchise or no gameData)');
    return;
  }

  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamId = team === 'home' ? homeTeamId : awayTeamId;
  const attributeChanges = gameData.team_attribute_changes || {};
  const changes = resolveChangesForTeamId(attributeChanges, teamId);

  const section = document.getElementById(`${team}-attribute-changes-section`);
  const container = document.getElementById(`${team}-attribute-changes-content`);
  console.log('🔍 [ATTR-CHANGES] renderTeamAttributeChangesForTab', { team, homeTeamId, awayTeamId, teamId, tacKeys: Object.keys(attributeChanges), hasChanges: !!(changes && Object.keys(changes).length), section: !!section, container: !!container });
  if (!section || !container) {
    console.log('🔍 [ATTR-CHANGES] renderTeamAttributeChangesForTab: missing section or container', { team });
    return;
  }

  console.log('🔍 [ATTR-CHANGES] renderTeamAttributeChangesForTab: showing section', { team, changeKeys: Object.keys(changes || {}) });
  section.style.display = 'block';
  renderAttributeChangePills(container, changes || {});
}

function renderAttributeChangePills(container, attributeDeltas) {
  function normalizeAttrKey(key) {
    return String(key || '')
      .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
      .replace(/[\s-]+/g, '_')
      .toLowerCase();
  }

  const ATTR_CONFIG = {
    // invert: raw delta sign flipped in copy (raw −10 → display +10 green); pill fill uses same golf-score sense.
    shot_threshold: { label: 'Shooting', scale: window.TeamShotThresholdScale?.HALF_SPAN ?? 100, invert: true },
    rebound_modifier: { label: 'Rebounding', scale: 0.5, invert: false },  // 0.0-1.0 range; scale<1 → 2-decimal delta (this view shows deltas, not a centered gauge)
    offensive_efficiency: { label: 'Offense', scale: 20, invert: false },
    defensive_efficiency: { label: 'Defense', scale: 20, invert: false },
    fb_efficiency: { label: 'Fast Break', scale: 20, invert: false },
    fb_defense: { label: 'FB Defense', scale: 20, invert: false },
    pt_efficiency: { label: 'Press/Trap', scale: 20, invert: false },
    pt_breaks: { label: 'P/T Breaks', scale: 20, invert: false },
    fight: { label: 'Fight', scale: 20, invert: false },
    discipline: { label: 'Discipline', scale: 20, invert: false },
    momentum_score: { label: 'Momentum', scale: 10, invert: false },
    team_chemistry: { label: 'Chemistry', scale: 10, invert: false },
    fb_opp_modifier: { label: 'FB Defense', scale: 20, invert: false },
    pt_opp_modifier: { label: 'P/T Breaks', scale: 20, invert: false },
    offensiveefficiency: { label: 'Offense', scale: 20, invert: false },
    defensiveefficiency: { label: 'Defense', scale: 20, invert: false },
    reboundmodifier: { label: 'Rebounding', scale: 0.5, invert: false },
    shotthreshold: { label: 'Shooting', scale: window.TeamShotThresholdScale?.HALF_SPAN ?? 100, invert: true }, // same as shot_threshold
    teamchemistry: { label: 'Chemistry', scale: 10, invert: false },
    momentumscore: { label: 'Momentum', scale: 10, invert: false },
    fbefficiency: { label: 'Fast Break', scale: 20, invert: false },
    ptefficiency: { label: 'Press/Trap', scale: 20, invert: false },
    ptbreaks: { label: 'P/T Breaks', scale: 20, invert: false }
  };
  container.innerHTML = '';
  container.className = 'attr-changes';
  console.log('🔍 [ATTR-CHANGES] renderAttributeChangePills keys=', Object.keys(attributeDeltas || {}));

  const movers = [];
  const flat = [];

  Object.entries(attributeDeltas).forEach(([key, rawDelta]) => {
    const normalizedKey = normalizeAttrKey(key);
    const compactKey = normalizedKey.replace(/_/g, '');
    const config = ATTR_CONFIG[normalizedKey] || ATTR_CONFIG[compactKey];
    if (!config) return;

    const numDelta = Number(rawDelta) || 0;
    const effectiveDelta = config.invert ? -numDelta : numDelta;
    const isPositive = effectiveDelta > 0;
    const isNegative = effectiveDelta < 0;
    const sign = effectiveDelta > 0 ? '+' : '';
    const displayDelta = config.scale < 1
      ? `${sign}${effectiveDelta.toFixed(2)}`
      : `${sign}${Math.round(effectiveDelta)}`;

    const item = {
      label: config.label,
      displayDelta,
      effectiveDelta,
      isPositive,
      isNegative
    };

    if (numDelta !== 0) {
      movers.push(item);
    } else {
      flat.push(item);
    }
  });

  movers.sort((a, b) => Math.abs(b.effectiveDelta) - Math.abs(a.effectiveDelta));

  if (movers.length > 0) {
    const lead = document.createElement('div');
    lead.className = 'attr-changes-lead';
    lead.textContent = 'What changed this game';
    container.appendChild(lead);

    const chips = document.createElement('div');
    chips.className = 'attr-chips';
    movers.forEach((item) => {
      const chip = document.createElement('div');
      chip.className = `attr-chip ${item.isPositive ? 'up' : item.isNegative ? 'down' : ''}`.trim();
      chip.innerHTML = `
        <span class="attr-chip-name">${item.label}</span>
        <span class="attr-chip-val ${item.isPositive ? 'up' : item.isNegative ? 'down' : ''}">${item.displayDelta}</span>
      `;
      chips.appendChild(chip);
    });
    container.appendChild(chips);
  }

  if (flat.length > 0) {
    const flatWrap = document.createElement('div');
    flatWrap.className = 'attr-flat';

    const flatLead = document.createElement('div');
    flatLead.className = 'attr-flat-lead';
    flatLead.textContent = 'No change';
    flatWrap.appendChild(flatLead);

    const flatList = document.createElement('div');
    flatList.className = 'attr-flat-list';
    flat.forEach((item) => {
      const pill = document.createElement('span');
      pill.className = 'attr-flat-item';
      pill.textContent = item.label;
      flatList.appendChild(pill);
    });
    flatWrap.appendChild(flatList);
    container.appendChild(flatWrap);
  }
}

function getTeamPlayDisplayNameForUsage(storageKey, playData) {
  if (playData && typeof playData === 'object' && typeof playData.name === 'string' && playData.name.trim()) {
    return playData.name.trim();
  }
  return storageKey;
}

function buildPlayerNameLookupForTeam(teamId) {
  const map = {};
  const players = (gameData && gameData.players) || [];
  const tid = String(teamId || '').trim();
  for (const p of players) {
    if (!p || typeof p !== 'object') continue;
    if (String(p.team_id || '').trim() !== tid) continue;
    const id = String(p.playerId || p.player_id || '').trim();
    if (!id) continue;
    const name = (p.name || '').trim();
    map[id] = name || 'Player';
  }
  return map;
}

function topScorerLabelFromPlayerPoints(playerPoints, nameById) {
  if (!playerPoints || typeof playerPoints !== 'object') return '';
  let bestId = null;
  let bestPts = -1;
  for (const [pid, raw] of Object.entries(playerPoints)) {
    const pts = Number(raw);
    if (!Number.isFinite(pts)) continue;
    if (pts > bestPts) {
      bestPts = pts;
      bestId = pid;
    }
  }
  if (bestId == null || bestPts <= 0) return '';
  const label = nameById[bestId] || 'Player';
  return `${label} (${bestPts})`;
}

function buildPlayUsageRowsForTeam(playsObj, teamIdForNames) {
  const rows = [];
  if (!playsObj || typeof playsObj !== 'object') return rows;
  let totalPlaycalls = 0;
  const entries = [];
  for (const [storageKey, playData] of Object.entries(playsObj)) {
    if (!playData || typeof playData !== 'object') continue;
    const gameStats = playData.game_stats || {};
    const timesRun = gameStats.times_run || 0;
    totalPlaycalls += timesRun;
    entries.push({
      playData,
      displayName: getTeamPlayDisplayNameForUsage(storageKey, playData),
      gameStats,
    });
  }
  const nameById = buildPlayerNameLookupForTeam(teamIdForNames);
  for (const { playData, displayName, gameStats } of entries) {
    const timesRun = gameStats.times_run || 0;
    if (timesRun <= 0) continue;
    const successes = gameStats.successes || 0;
    const playerPoints = gameStats.player_points || {};
    const topScorer = topScorerLabelFromPlayerPoints(playerPoints, nameById);
    rows.push({
      play_id: playData.play_id,
      name: displayName,
      times_run: timesRun,
      successes,
      total_playcalls: totalPlaycalls,
      topScorer,
    });
  }
  rows.sort((a, b) => (b.times_run || 0) - (a.times_run || 0));
  return rows;
}

function isUserInvolvedInPlayUsageContext(data, urlParams) {
  if (!data || !urlParams) return false;
  // SS&S: persisted game document is primary; URL params supplement older saves / deep links.
  const docSide = data.user_team_side;
  if (docSide === 'home' || docSide === 'away') return true;

  const my = urlParams.get('my_team');
  if (my === 'home' || my === 'away') return true;

  const teamIdParam = (urlParams.get('team_id') || urlParams.get('user_team_id') || '').trim();
  if (teamIdParam) {
    const { homeTeam, awayTeam, homeTeamId, awayTeamId } = getTeamContext();
    const homeName = homeTeam.name || 'Home Team';
    const awayName = awayTeam.name || 'Away Team';
    const side = mapTeamIdToSide(teamIdParam, data, homeName, awayName, homeTeamId, awayTeamId);
    if (side) return true;
  }

  const mode = (urlParams.get('mode') || '').trim();
  if (mode === 'single') return true;
  return false;
}

function teamSideHasPlayUsageRows(data, teamSide) {
  const tid = teamSide === 'home' ? data.home_team_id : data.away_team_id;
  const team = tid && data.teams ? data.teams[tid] : null;
  const plays = team && team.plays;
  if (!plays || typeof plays !== 'object') return false;
  for (const playData of Object.values(plays)) {
    const tr = (playData && playData.game_stats && playData.game_stats.times_run) || 0;
    if (tr > 0) return true;
  }
  return false;
}

/**
 * Play usage: exclude distant sim only. Show when (a) turn-by-turn save, (b) user-controlled game
 * (`user_team_side` on game doc first, then URL hints — see isUserInvolvedInPlayUsageContext),
 * (c) legacy engine games with playcall rows. Hide full_quarter_sim when neither doc nor URL
 * indicates a user side (batch / non-UI sim).
 */
function shouldShowPlayUsageSectionForBoxScore(data, urlParams) {
  if (!data || !urlParams) return false;
  if (urlParams.get('pregame') === '1') return false;
  if (data.simulation_engine === 'distant') return false;
  if (isUserInvolvedInPlayUsageContext(data, urlParams)) return true;
  if (data.simulation_engine === 'turn_by_turn') return true;
  if (data.simulation_engine === 'full_quarter_sim') return false;
  if (data.simulation_engine == null || data.simulation_engine === '') {
    return teamSideHasPlayUsageRows(data, 'home') || teamSideHasPlayUsageRows(data, 'away');
  }
  return false;
}

function renderPlayUsageForBoxScore() {
  const urlParams = new URLSearchParams(window.location.search);
  const show = gameData && shouldShowPlayUsageSectionForBoxScore(gameData, urlParams);
  ['home', 'away'].forEach((side) => {
    const sec = document.getElementById(`${side}-play-usage-section`);
    if (!sec) return;
    if (!show) {
      sec.style.display = 'none';
      return;
    }
    sec.style.display = '';
    const teamId = side === 'home' ? gameData.home_team_id : gameData.away_team_id;
    const team = teamId && gameData.teams ? gameData.teams[teamId] : null;
    const rows = buildPlayUsageRowsForTeam(team && team.plays, teamId);
    const tbodyId = `${side}-play-usage-body`;
    if (typeof renderPlayUsage === 'function') {
      renderPlayUsage(
        rows,
        'No offensive playcall usage recorded for this game.',
        tbodyId,
        { showTopScorer: true },
      );
    }
  });
}

// Render scouting notes
function renderScoutingNotes() {
  // ✅ UNIFIED STRUCTURE: Get team names from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  const teamStats = gameData.team_stats || {};
  const homeTeamName = homeTeamObj?.name || gameData.home_team?.name || 'Home Team';
  const awayTeamName = awayTeamObj?.name || gameData.away_team?.name || 'Away Team';
  const eogInputs = gameData.eog_inputs || {};
  const homeEogSnapshot = eogInputs.home || null;
  const awayEogSnapshot = eogInputs.away || null;

  console.log('🔍 [SCOUTING] renderScoutingNotes source selection:', {
    hasEogInputs: !!gameData.eog_inputs,
    homeTeamId,
    awayTeamId,
    homeTeamName,
    awayTeamName,
    homeUsesEogSnapshot: !!homeEogSnapshot,
    awayUsesEogSnapshot: !!awayEogSnapshot,
  });

  renderScoutingContent('home', teamStats[homeTeamName] || {}, homeEogSnapshot);
  renderScoutingContent('away', teamStats[awayTeamName] || {}, awayEogSnapshot);
}

// Render scouting content for a team
function renderScoutingContent(team, teamStats, eogSnapshot = null) {
  const container = document.getElementById(`${team}-scouting-content`);
  container.innerHTML = '';

  const offense = teamStats.offense || {};
  const defense = teamStats.defense || {};
  const playcalls = offense.Playcalls || {};
  const scoutingSnapshot = (eogSnapshot && eogSnapshot.scouting) || {};

  const leftColumn = document.createElement('div');
  leftColumn.className = 'scouting-column';
  const middleColumn = document.createElement('div');
  middleColumn.className = 'scouting-column';
  const rightColumn = document.createElement('div');
  rightColumn.className = 'scouting-column';
  container.appendChild(leftColumn);
  container.appendChild(middleColumn);
  container.appendChild(rightColumn);

  const playCallsSection = document.createElement('div');
  playCallsSection.className = 'scouting-section';
  playCallsSection.innerHTML = '<div class="scouting-section-header">Offense Play Calls</div>';

  // Motion
  const motionSection = createPlaycallSubsection('Motion', playcalls.Motion);
  playCallsSection.appendChild(motionSection);

  // Set Plays
  const setSection = createPlaycallSubsection('Set Plays', playcalls.Set);
  playCallsSection.appendChild(setSection);

  // Focus Success Rates (only show if there's data)
  const cumulative = playcalls.Cumulative || {};
  const hasCumulativeData = Object.values(cumulative).some(focus => (focus.attempts || 0) > 0);
  if (hasCumulativeData) {
    const cumulativeSection = createPlaycallSubsection('Focus Success Rates', cumulative);
  playCallsSection.appendChild(cumulativeSection);
  }

  leftColumn.appendChild(playCallsSection);

  // ── Defense Play Calls → Man Defense (middle column) + Zone Defense (right column). Each shows an
  // aggregate row plus its individual plays, so Man now breaks out Base / Deny / Loose Man (mirrors Zone).
  const gb =
    typeof window !== 'undefined' && window.GOBDefenseDisplay
      ? window.GOBDefenseDisplay
      : null;
  const block = (slug) =>
    gb && typeof gb.getDefenseBlock === 'function'
      ? gb.getDefenseBlock(defense, slug)
      : {};

  // Aggregate one stat across several defense row-blocks (generalized from the old zone-only helper;
  // pulls each row's game_stats/season_stats). Handles nested objects (vs_*), numbers, and score arrays.
  const aggregateDefenseStats = (rows, statKey) => {
    const vals = rows.map((r) => ((r && (r.game_stats || r.season_stats || r)) || {})[statKey]);
    const nested = vals.find((v) => v && typeof v === 'object' && !Array.isArray(v));
    if (nested) {
      return {
        attempts: vals.reduce((s, v) => s + ((v && v.attempts) || 0), 0),
        success: vals.reduce((s, v) => s + ((v && v.success) || 0), 0),
        ev_scores: vals.flatMap((v) => (v && v.ev_scores) || []),
        lean_scores: vals.flatMap((v) => (v && v.lean_scores) || []),
      };
    }
    if (vals.some((v) => Array.isArray(v))) return vals.flatMap((v) => v || []);
    return vals.reduce((s, v) => s + (typeof v === 'number' ? v : 0), 0);
  };
  // Flat aggregate row (top-level keys) for createDefensePlaycallSubsection's aggregate display.
  const aggregateRow = (rows) => {
    const bases = rows.map((r) => (r && (r.game_stats || r.season_stats || r)) || {});
    return {
      used: aggregateDefenseStats(rows, 'used'),
      success: aggregateDefenseStats(rows, 'success'),
      ev_scores: bases.flatMap((b) => b.ev_scores || []),
      lean_scores: bases.flatMap((b) => b.lean_scores || []),
      vs_motion: aggregateDefenseStats(rows, 'vs_motion'),
      vs_set: aggregateDefenseStats(rows, 'vs_set'),
      vs_inside: aggregateDefenseStats(rows, 'vs_inside'),
      vs_attack: aggregateDefenseStats(rows, 'vs_attack'),
      vs_outside: aggregateDefenseStats(rows, 'vs_outside'),
    };
  };

  // MAN DEFENSE (middle column): aggregate "Man" + Base / Deny / Loose breakouts.
  const manRow = Object.keys(block('man')).length > 0 ? block('man') : defense.Man || defense.man || {};
  const denyRow = block('man-tight');
  const looseRow = block('man-loose');
  const manDefenseSection = document.createElement('div');
  manDefenseSection.className = 'scouting-section';
  manDefenseSection.innerHTML = '<div class="scouting-section-header">Man Defense</div>';
  manDefenseSection.appendChild(createDefensePlaycallSubsection('Man', aggregateRow([manRow, denyRow, looseRow])));
  manDefenseSection.appendChild(createDefensePlaycallSubsection('Base Man', manRow));
  manDefenseSection.appendChild(createDefensePlaycallSubsection('Deny Man', denyRow));
  manDefenseSection.appendChild(createDefensePlaycallSubsection('Loose Man', looseRow));
  middleColumn.appendChild(manDefenseSection);

  // Zone (aggregate all zone types: 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
  const zone23 =
    Object.keys(block('2-3-zone')).length > 0 ? block('2-3-zone') : defense['2-3 Zone'] || {};
  const zone32 =
    Object.keys(block('3-2-zone')).length > 0 ? block('3-2-zone') : defense['3-2 Zone'] || {};
  const zone131 =
    Object.keys(block('1-3-1-zone')).length > 0
      ? block('1-3-1-zone')
      : defense['1-3-1 Zone'] || {};
  
  // Aggregate stats from all zone types
  const aggregateZoneStats = (statKey) => {
    const base23 = zone23.game_stats || zone23.season_stats || zone23 || {};
    const base32 = zone32.game_stats || zone32.season_stats || zone32 || {};
    const base131 = zone131.game_stats || zone131.season_stats || zone131 || {};
    
    const stats23 = base23[statKey];
    const stats32 = base32[statKey];
    const stats131 = base131[statKey];
    
    // Check if any of them is an object (like vs_motion, vs_set, etc.)
    if (stats23 && typeof stats23 === 'object' && stats23 !== null && !Array.isArray(stats23)) {
      // It's a nested object (like vs_motion, vs_set, etc.)
      return {
        attempts: (stats23.attempts || 0) + ((stats32 && stats32.attempts) || 0) + ((stats131 && stats131.attempts) || 0),
        success: (stats23.success || 0) + ((stats32 && stats32.success) || 0) + ((stats131 && stats131.success) || 0),
        ev_scores: [...(stats23.ev_scores || []), ...(stats32?.ev_scores || []), ...(stats131?.ev_scores || [])],
        lean_scores: [...(stats23.lean_scores || []), ...(stats32?.lean_scores || []), ...(stats131?.lean_scores || [])]
      };
    } else {
      // It's a number (like used, success) or array (like ev_scores, lean_scores)
      if (Array.isArray(stats23) || Array.isArray(stats32) || Array.isArray(stats131)) {
        // It's an array (like ev_scores, lean_scores)
        return [...(stats23 || []), ...(stats32 || []), ...(stats131 || [])];
      } else {
        // It's a number
        const val23 = (typeof stats23 === 'number') ? stats23 : 0;
        const val32 = (typeof stats32 === 'number') ? stats32 : 0;
        const val131 = (typeof stats131 === 'number') ? stats131 : 0;
        return val23 + val32 + val131;
      }
    }
  };
  
  // Aggregate ev_scores and lean_scores at the top level
  const base23 = zone23.game_stats || zone23.season_stats || zone23 || {};
  const base32 = zone32.game_stats || zone32.season_stats || zone32 || {};
  const base131 = zone131.game_stats || zone131.season_stats || zone131 || {};
  
  const zoneDefense = {
    used: aggregateZoneStats('used'),
    success: aggregateZoneStats('success'),
    ev_scores: [...(base23.ev_scores || []), ...(base32.ev_scores || []), ...(base131.ev_scores || [])],
    lean_scores: [...(base23.lean_scores || []), ...(base32.lean_scores || []), ...(base131.lean_scores || [])],
    vs_motion: aggregateZoneStats('vs_motion'),
    vs_set: aggregateZoneStats('vs_set'),
    vs_inside: aggregateZoneStats('vs_inside'),
    vs_attack: aggregateZoneStats('vs_attack'),
    vs_outside: aggregateZoneStats('vs_outside')
  };
  
  // ZONE DEFENSE (right column): aggregate "Zone" + 2-3 / 3-2 / 1-3-1 breakouts.
  const zoneDefenseSection = document.createElement('div');
  zoneDefenseSection.className = 'scouting-section';
  zoneDefenseSection.innerHTML = '<div class="scouting-section-header">Zone Defense</div>';
  zoneDefenseSection.appendChild(createDefensePlaycallSubsection('Zone', zoneDefense));
  zoneDefenseSection.appendChild(createDefensePlaycallSubsection('2-3 Zone', zone23));
  zoneDefenseSection.appendChild(createDefensePlaycallSubsection('3-2 Zone', zone32));
  zoneDefenseSection.appendChild(createDefensePlaycallSubsection('1-3-1 Zone', zone131));
  rightColumn.appendChild(zoneDefenseSection);

  // Fast Breaks (left column, after Offense Play Calls)
  const fbEntries = scoutingSnapshot.fb_entries ?? offense.Fast_Break_Entries ?? 0;
  const fbSuccess = scoutingSnapshot.fb_success ?? offense.Fast_Break_Success ?? 0;
  const fbPct = fbEntries > 0 ? ((fbSuccess / fbEntries) * 100).toFixed(0) : '0';

  const fastBreakSection = document.createElement('div');
  fastBreakSection.className = 'scouting-section';
  fastBreakSection.innerHTML = '<div class="scouting-section-header">Fast Breaks</div>';
  const fastBreakSub = document.createElement('div');
  fastBreakSub.className = 'scouting-play-type';
  const fastBreakHeader = document.createElement('div');
  fastBreakHeader.className = 'scouting-play-type-header';
  fastBreakHeader.innerHTML = `<span>Fast Breaks:</span><span>${fbSuccess} / ${fbEntries} (${fbPct}%)</span>`;
  fastBreakSub.appendChild(fastBreakHeader);

  const mergedFbPlays = mergeFastBreakPlaysForBoxScore(
    offense.fast_break_plays,
    scoutingSnapshot.fast_break_plays
  );
  const fbPlayRows = [
    { key: 'covert_release', label: 'Covert Release' },
    { key: 'rim_runner', label: 'Rim Runner' },
    { key: 'triangle', label: 'Triangle' },
    { key: 'after_steal', label: 'After Steal' },
  ];
  for (const row of fbPlayRows) {
    const p = mergedFbPlays[row.key] || { A: 0, S: 0 };
    const a = Number(p.A) || 0;
    const s = Number(p.S) || 0;
    const pct = a > 0 ? ((s / a) * 100).toFixed(0) : '0';
    fastBreakSub.appendChild(createScoutingItem(row.label, `${s} / ${a}`, `${pct}%`));
  }

  fastBreakSection.appendChild(fastBreakSub);
  leftColumn.appendChild(fastBreakSection);

  const specialSection = document.createElement('div');
  specialSection.className = 'scouting-section';
  specialSection.innerHTML = '<div class="scouting-section-header">Special Situations</div>';

  const hct = defense.HCT || {};
  const hctUsed = scoutingSnapshot.hct_used ?? hct.used ?? 0;
  const hctSuccess = scoutingSnapshot.hct_success ?? hct.success ?? 0;
  const hctPct = hctUsed > 0 ? ((hctSuccess / hctUsed) * 100).toFixed(0) : '0';
  const hctBlock = document.createElement('div');
  hctBlock.className = 'scouting-play-type';
  hctBlock.innerHTML = `<div class="scouting-play-type-header"><span>HC Traps:</span><span>${hctSuccess} / ${hctUsed} (${hctPct}%)</span></div>`;
  specialSection.appendChild(hctBlock);

  const fcp = defense.FCP || {};
  const fcpUsed = scoutingSnapshot.fcp_used ?? fcp.used ?? 0;
  const fcpSuccess = scoutingSnapshot.fcp_success ?? fcp.success ?? 0;
  const fcpPct = fcpUsed > 0 ? ((fcpSuccess / fcpUsed) * 100).toFixed(0) : '0';
  const fcpBlock = document.createElement('div');
  fcpBlock.className = 'scouting-play-type';
  fcpBlock.innerHTML = `<div class="scouting-play-type-header"><span>FC Presses:</span><span>${fcpSuccess} / ${fcpUsed} (${fcpPct}%)</span></div>`;
  specialSection.appendChild(fcpBlock);

  middleColumn.appendChild(specialSection);
}

/**
 * Merge offense.fast_break_plays with EOG snapshot (if present) for box score display.
 */
function mergeFastBreakPlaysForBoxScore(offensePlays, snapshotPlays) {
  const keys = ['covert_release', 'rim_runner', 'triangle', 'after_steal'];
  const out = {};
  for (const k of keys) {
    const o = (offensePlays && offensePlays[k]) || {};
    const s = (snapshotPlays && snapshotPlays[k]) || {};
    const aO = o.A !== undefined && o.A !== null ? Number(o.A) : 0;
    const sO = o.S !== undefined && o.S !== null ? Number(o.S) : 0;
    const aSnap = s.A !== undefined && s.A !== null ? Number(s.A) : null;
    const sSnap = s.S !== undefined && s.S !== null ? Number(s.S) : null;
    out[k] = {
      A: aSnap !== null ? aSnap : aO,
      S: sSnap !== null ? sSnap : sO,
    };
  }
  return out;
}

// Create playcall subsection (Motion, Set, Cumulative)
function createPlaycallSubsection(title, playcallData) {
  const subsection = document.createElement('div');
  subsection.className = 'scouting-play-type';
  const suppressOverallSummary = title === 'Focus Success Rates';

  const overall = playcallData.overall || {};
  const overallAttempts = overall.attempts || 0;
  const overallSuccess = overall.success || 0;
  const overallPct = overallAttempts > 0 ? ((overallSuccess / overallAttempts) * 100).toFixed(0) : '0';

  // Calculate average EV and Execution for offense playcalls
  const overallEvScores = overall.ev_scores || [];
  const overallLeanScores = overall.lean_scores || [];
  const overallAvgEV = overallEvScores.length > 0 
    ? (overallEvScores.reduce((a, b) => a + b, 0) / overallEvScores.length).toFixed(0)
    : null;
  const overallAvgExec = overallLeanScores.length > 0
    ? (overallLeanScores.reduce((a, b) => a + b, 0) / overallLeanScores.length * 100).toFixed(0)
    : null;
  
  const overallEvSign = overallAvgEV !== null && parseFloat(overallAvgEV) >= 0 ? '+' : '';
  const overallExecSign = overallAvgExec !== null && parseFloat(overallAvgExec) >= 0 ? '+' : '';
  
  // Color coding: negative=red, zero=yellow, positive=green
  const overallEvColor = overallAvgEV !== null 
    ? (parseFloat(overallAvgEV) < 0 ? '#ff0000' : (parseFloat(overallAvgEV) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  const overallExecColor = overallAvgExec !== null
    ? (parseFloat(overallAvgExec) < 0 ? '#ff0000' : (parseFloat(overallAvgExec) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  
  const primary = document.createElement('div');
  primary.className = 'scouting-play-type-header';
  primary.innerHTML = suppressOverallSummary
    ? `<span>${title}</span>`
    : `
    <span>${title}:</span>
    <span>${overallSuccess} / ${overallAttempts} (${overallPct}%)</span>
    ${overallAvgEV !== null ? `<span class="${getEvClass(overallAvgEV)}">EV ${overallEvSign}${overallAvgEV}%</span>` : ''}
    ${overallAvgExec !== null ? `<span class="${getEvClass(overallAvgExec)}">Execution ${overallExecSign}${overallAvgExec}%</span>` : ''}
  `;
  subsection.appendChild(primary);

  // Inside (backend uses lowercase 'inside')
  const inside = playcallData.inside || playcallData.Inside || {};
  const insideAttempts = inside.attempts || 0;
  const insideSuccess = inside.success || 0;
  const insidePct = insideAttempts > 0 ? ((insideSuccess / insideAttempts) * 100).toFixed(0) : '0';
  const insideVsMan = inside.vs_man || {};
  const insideVsManAtt = insideVsMan.attempts || 0;
  const insideVsManSuc = insideVsMan.success || 0;
  // Safety check: success can't exceed attempts
  const safeInsideVsManSuc = Math.min(insideVsManSuc, insideVsManAtt);
  const insideVsManPct = insideVsManAtt > 0 ? ((safeInsideVsManSuc / insideVsManAtt) * 100).toFixed(0) : '0';
  const insideVsZone = inside.vs_zone || {};
  const insideVsZoneAtt = insideVsZone.attempts || 0;
  const insideVsZoneSuc = insideVsZone.success || 0;
  // Safety check: success can't exceed attempts
  const safeInsideVsZoneSuc = Math.min(insideVsZoneSuc, insideVsZoneAtt);
  const insideVsZonePct = insideVsZoneAtt > 0 ? ((safeInsideVsZoneSuc / insideVsZoneAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItemWithVs('Inside', `${insideSuccess} / ${insideAttempts}`, `${insidePct}%`, `${safeInsideVsManSuc} / ${insideVsManAtt}`, `${insideVsManPct}`, `${safeInsideVsZoneSuc} / ${insideVsZoneAtt}`, `${insideVsZonePct}`));

  // Attack (backend uses lowercase 'attack')
  const attack = playcallData.attack || playcallData.Attack || {};
  const attackAttempts = attack.attempts || 0;
  const attackSuccess = attack.success || 0;
  const attackPct = attackAttempts > 0 ? ((attackSuccess / attackAttempts) * 100).toFixed(0) : '0';
  const attackVsMan = attack.vs_man || {};
  const attackVsManAtt = attackVsMan.attempts || 0;
  const attackVsManSuc = attackVsMan.success || 0;
  // Safety check: success can't exceed attempts
  const safeAttackVsManSuc = Math.min(attackVsManSuc, attackVsManAtt);
  const attackVsManPct = attackVsManAtt > 0 ? ((safeAttackVsManSuc / attackVsManAtt) * 100).toFixed(0) : '0';
  const attackVsZone = attack.vs_zone || {};
  const attackVsZoneAtt = attackVsZone.attempts || 0;
  const attackVsZoneSuc = attackVsZone.success || 0;
  // Safety check: success can't exceed attempts
  const safeAttackVsZoneSuc = Math.min(attackVsZoneSuc, attackVsZoneAtt);
  const attackVsZonePct = attackVsZoneAtt > 0 ? ((safeAttackVsZoneSuc / attackVsZoneAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItemWithVs('Attack', `${attackSuccess} / ${attackAttempts}`, `${attackPct}%`, `${safeAttackVsManSuc} / ${attackVsManAtt}`, `${attackVsManPct}`, `${safeAttackVsZoneSuc} / ${attackVsZoneAtt}`, `${attackVsZonePct}`));

  // Outside (backend uses lowercase 'outside')
  const outside = playcallData.outside || playcallData.Outside || {};
  const outsideAttempts = outside.attempts || 0;
  const outsideSuccess = outside.success || 0;
  const outsidePct = outsideAttempts > 0 ? ((outsideSuccess / outsideAttempts) * 100).toFixed(0) : '0';
  const outsideVsMan = outside.vs_man || {};
  const outsideVsManAtt = outsideVsMan.attempts || 0;
  const outsideVsManSuc = outsideVsMan.success || 0;
  // Safety check: success can't exceed attempts
  const safeOutsideVsManSuc = Math.min(outsideVsManSuc, outsideVsManAtt);
  const outsideVsManPct = outsideVsManAtt > 0 ? ((safeOutsideVsManSuc / outsideVsManAtt) * 100).toFixed(0) : '0';
  const outsideVsZone = outside.vs_zone || {};
  const outsideVsZoneAtt = outsideVsZone.attempts || 0;
  const outsideVsZoneSuc = outsideVsZone.success || 0;
  // Safety check: success can't exceed attempts
  const safeOutsideVsZoneSuc = Math.min(outsideVsZoneSuc, outsideVsZoneAtt);
  const outsideVsZonePct = outsideVsZoneAtt > 0 ? ((safeOutsideVsZoneSuc / outsideVsZoneAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItemWithVs('Outside', `${outsideSuccess} / ${outsideAttempts}`, `${outsidePct}%`, `${safeOutsideVsManSuc} / ${outsideVsManAtt}`, `${outsideVsManPct}`, `${safeOutsideVsZoneSuc} / ${outsideVsZoneAtt}`, `${outsideVsZonePct}`));

  return subsection;
}

function getEvClass(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'ev-neutral';
  if (n > 0) return 'ev-positive';
  if (n < 0) return 'ev-negative';
  return 'ev-neutral';
}

function createScoutingItem(label, value, pct) {
  const item = document.createElement('div');
  item.className = 'scouting-vs-row';
  item.innerHTML = `
    <span class="scouting-vs-label">${label}</span>
    <span>${value}</span>
    <span>${pct}</span>
  `;
  return item;
}

function createScoutingItemWithVs(label, value, pct, vsManValue, vsManPct, vsZoneValue, vsZonePct) {
  const wrap = document.createElement('div');
  wrap.className = 'scouting-focus-group';
  const primary = document.createElement('div');
  primary.className = 'scouting-focus-header';
  primary.innerHTML = `<span>${label}:</span><span>${value}</span><span>${pct}</span>`;
  wrap.appendChild(primary);

  const subRows = document.createElement('div');
  subRows.className = 'scouting-vs-rows';
  subRows.appendChild(createScoutingItem('vs Man', vsManValue, `${vsManPct}%`));
  subRows.appendChild(createScoutingItem('vs Zone', vsZoneValue, `${vsZonePct}%`));
  wrap.appendChild(subRows);
  return wrap;
}

// Create defense playcall subsection (Man, Zone, etc.)
function createDefensePlaycallSubsection(title, defenseData) {
  // Check if we have game_stats or season_stats
  const stats = defenseData.game_stats || defenseData.season_stats || defenseData || {};
  
  const subsection = document.createElement('div');
  subsection.className = 'scouting-play-type';

  const used = stats.used || 0;
  const success = stats.success || 0;
  const pct = used > 0 ? ((success / used) * 100).toFixed(0) : '0';

  // Calculate average EV and Execution (lean_score), then invert for defense display.
  const evScores = stats.ev_scores || [];
  const leanScores = stats.lean_scores || [];
  const rawAvgEV = evScores.length > 0 
    ? (evScores.reduce((a, b) => a + b, 0) / evScores.length).toFixed(0)
    : '0';
  const rawAvgExec = leanScores.length > 0
    ? (leanScores.reduce((a, b) => a + b, 0) / leanScores.length * 100).toFixed(0)
    : '0';
  const avgEV = String(-Number(rawAvgEV || 0));
  const avgExec = String(-Number(rawAvgExec || 0));
  
  const evSign = parseFloat(avgEV) >= 0 ? '+' : '';
  const execSign = parseFloat(avgExec) >= 0 ? '+' : '';
  
  // Color coding: negative=red, zero=yellow, positive=green
  const evColor = parseFloat(avgEV) < 0 ? '#ff0000' : (parseFloat(avgEV) === 0 ? '#ffd700' : '#00AA00');
  const execColor = parseFloat(avgExec) < 0 ? '#ff0000' : (parseFloat(avgExec) === 0 ? '#ffd700' : '#00AA00');
  
  const primary = document.createElement('div');
  primary.className = 'scouting-play-type-header';
  primary.innerHTML = `
    <span>${title}:</span>
    <span>${success} / ${used} (${pct}%)</span>
    ${(evScores.length > 0 || leanScores.length > 0) ? `<span class="${getEvClass(avgEV)}">EV ${evSign}${avgEV}%</span>` : ''}
    ${(evScores.length > 0 || leanScores.length > 0) ? `<span class="${getEvClass(avgExec)}">Execution ${execSign}${avgExec}%</span>` : ''}
  `;
  subsection.appendChild(primary);

  // vs Motion
  const vsMotion = stats.vs_motion || {};
  const vsMotionAtt = vsMotion.attempts || 0;
  const vsMotionSuc = vsMotion.success || 0;
  // Safety check: success can't exceed attempts
  const safeVsMotionSuc = Math.min(vsMotionSuc, vsMotionAtt);
  const vsMotionPct = vsMotionAtt > 0 ? ((safeVsMotionSuc / vsMotionAtt) * 100).toFixed(0) : '0';
  
  // Calculate average EV and Exec for vs Motion
  const vsMotionEvScores = vsMotion.ev_scores || [];
  const vsMotionLeanScores = vsMotion.lean_scores || [];
  const vsMotionAvgEV = vsMotionEvScores.length > 0
    ? (vsMotionEvScores.reduce((a, b) => a + b, 0) / vsMotionEvScores.length).toFixed(0)
    : null;
  const vsMotionAvgExec = vsMotionLeanScores.length > 0
    ? (vsMotionLeanScores.reduce((a, b) => a + b, 0) / vsMotionLeanScores.length * 100).toFixed(0)
    : null;
  
  const vsMotionEvSign = vsMotionAvgEV !== null && parseFloat(vsMotionAvgEV) >= 0 ? '+' : '';
  const vsMotionExecSign = vsMotionAvgExec !== null && parseFloat(vsMotionAvgExec) >= 0 ? '+' : '';
  
  // Color coding for vs Motion
  const vsMotionEvColor = vsMotionAvgEV !== null
    ? (parseFloat(vsMotionAvgEV) < 0 ? '#ff0000' : (parseFloat(vsMotionAvgEV) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  const vsMotionExecColor = vsMotionAvgExec !== null
    ? (parseFloat(vsMotionAvgExec) < 0 ? '#ff0000' : (parseFloat(vsMotionAvgExec) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  
  subsection.appendChild(createScoutingItem('vs Motion', `${safeVsMotionSuc} / ${vsMotionAtt}`, `${vsMotionPct}%`));

  // vs Set Play
  const vsSet = stats.vs_set || {};
  const vsSetAtt = vsSet.attempts || 0;
  const vsSetSuc = vsSet.success || 0;
  // Safety check: success can't exceed attempts
  const safeVsSetSuc = Math.min(vsSetSuc, vsSetAtt);
  const vsSetPct = vsSetAtt > 0 ? ((safeVsSetSuc / vsSetAtt) * 100).toFixed(0) : '0';
  
  // Calculate average EV and Exec for vs Set Play
  const vsSetEvScores = vsSet.ev_scores || [];
  const vsSetLeanScores = vsSet.lean_scores || [];
  const vsSetAvgEV = vsSetEvScores.length > 0
    ? (vsSetEvScores.reduce((a, b) => a + b, 0) / vsSetEvScores.length).toFixed(0)
    : null;
  const vsSetAvgExec = vsSetLeanScores.length > 0
    ? (vsSetLeanScores.reduce((a, b) => a + b, 0) / vsSetLeanScores.length * 100).toFixed(0)
    : null;
  
  const vsSetEvSign = vsSetAvgEV !== null && parseFloat(vsSetAvgEV) >= 0 ? '+' : '';
  const vsSetExecSign = vsSetAvgExec !== null && parseFloat(vsSetAvgExec) >= 0 ? '+' : '';
  
  // Color coding for vs Set Play
  const vsSetEvColor = vsSetAvgEV !== null
    ? (parseFloat(vsSetAvgEV) < 0 ? '#ff0000' : (parseFloat(vsSetAvgEV) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  const vsSetExecColor = vsSetAvgExec !== null
    ? (parseFloat(vsSetAvgExec) < 0 ? '#ff0000' : (parseFloat(vsSetAvgExec) === 0 ? '#ffd700' : '#00AA00'))
    : null;
  
  subsection.appendChild(createScoutingItem('vs Set Play', `${safeVsSetSuc} / ${vsSetAtt}`, `${vsSetPct}%`));

  // vs Inside
  const vsInside = stats.vs_inside || {};
  const vsInsideAtt = vsInside.attempts || 0;
  const vsInsideSuc = vsInside.success || 0;
  // Safety check: success can't exceed attempts
  const safeVsInsideSuc = Math.min(vsInsideSuc, vsInsideAtt);
  const vsInsidePct = vsInsideAtt > 0 ? ((safeVsInsideSuc / vsInsideAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('vs Inside', `${safeVsInsideSuc} / ${vsInsideAtt}`, `${vsInsidePct}%`));

  // vs Attack
  const vsAttack = stats.vs_attack || {};
  const vsAttackAtt = vsAttack.attempts || 0;
  const vsAttackSuc = vsAttack.success || 0;
  // Safety check: success can't exceed attempts
  const safeVsAttackSuc = Math.min(vsAttackSuc, vsAttackAtt);
  const vsAttackPct = vsAttackAtt > 0 ? ((safeVsAttackSuc / vsAttackAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('vs Attack', `${safeVsAttackSuc} / ${vsAttackAtt}`, `${vsAttackPct}%`));

  // vs Outside
  const vsOutside = stats.vs_outside || {};
  const vsOutsideAtt = vsOutside.attempts || 0;
  const vsOutsideSuc = vsOutside.success || 0;
  // Safety check: success can't exceed attempts
  const safeVsOutsideSuc = Math.min(vsOutsideSuc, vsOutsideAtt);
  const vsOutsidePct = vsOutsideAtt > 0 ? ((safeVsOutsideSuc / vsOutsideAtt) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('vs Outside', `${safeVsOutsideSuc} / ${vsOutsideAtt}`, `${vsOutsidePct}%`));

  return subsection;
}

// Setup tab switching
function setupTabs() {
  const tabButtons = document.querySelectorAll('.tab-button');
  const teamContents = document.querySelectorAll('.team-content');

  tabButtons.forEach(button => {
    const team = button.dataset.team;
    button.addEventListener('click', () => {
      playSound('click-tiny.wav');
      document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.team-content').forEach(c => c.classList.remove('active'));
      button.classList.add('active');
      document.getElementById(`${team}-content`)?.classList.add('active');
    });
  });
}

// Setup Locker Room button navigation
function setupLockerRoomButton() {
  const button = document.getElementById('locker-room-button');
  if (!button) {
    console.warn('⚠️ [BOX-SCORE] Locker room button not found in DOM');
    return;
  }
  
  // ✅ Remove any existing event listeners by cloning the button
  const newButton = button.cloneNode(true);
  button.parentNode.replaceChild(newButton, button);
  const cleanButton = newButton;

  // Determine mode from URL params or localStorage
  const urlParams = new URLSearchParams(window.location.search);
  const from = urlParams.get('from');
  // ✅ SS&S: Read mode parameter first (most reliable), then fall back to IDs
  const mode = urlParams.get('mode');
  const tournamentId = urlParams.get('tournament_id');
  const franchiseId = urlParams.get('franchise_id');
  const home = urlParams.get('home');
  const away = urlParams.get('away');
  const homeId = urlParams.get('home_id');
  const awayId = urlParams.get('away_id');
  const myTeam = urlParams.get('my_team');
  const userTeamId = urlParams.get('user_team_id');
  const week = urlParams.get('week');
  const quarter = urlParams.get('quarter');
  const period = urlParams.get('period');
  const startWithInbound = urlParams.get('start_with_inbound');
  const startingPossession = urlParams.get('starting_possession');
  // SS&S with POTG-style completion: Q4 finals without `is_final` (and some distant/tie docs) were misclassified as in-progress → set-lineup "Back" with broken params.
  const isFinalGame = !!(
    gameData &&
    urlParams.get('game_id') &&
    isGameCompleteForPotg(gameData)
  );

  const buildLineupBackUrl = () => {
    const helper = window.TimeoutNavigationHelper;
    if (!helper) return null;
    const currentGameId = helper.getGameId(urlParams);
    const resumeFromTimeout = helper.getResumeFromTimeout(urlParams);
    const lineup = {};
    const myTeamParam = urlParams.get('my_team');
    if (myTeamParam) {
      ['pg', 'sg', 'sf', 'pf', 'c'].forEach((pos) => {
        const playerId = urlParams.get(`${myTeamParam}_${pos}`);
        if (playerId) lineup[pos.toUpperCase()] = playerId;
      });
    }
    const params = helper.buildGameNavigationParams({
      sourceParams: urlParams,
      targetQuarter: parseInt(quarter, 10) || 1,
      gameId: currentGameId,
      resumeFromTimeout,
      lineup,
      myTeamSide: myTeam
    });
    return `/set-lineup.html?${params.toString()}`;
  };
  
  // ✅ SS&S: Handle back navigation from lineup or game-plan screens
  // Both use TimeoutNavigationHelper to preserve timeout state
  if (!isFinalGame && (from === 'lineup' || from === 'game-plan')) {
    cleanButton.textContent = 'Back';
    
    // Remove any existing event listeners by cloning the button
    const newButton = cleanButton.cloneNode(true);
    cleanButton.parentNode.replaceChild(newButton, cleanButton);
    const backButton = newButton;
    
    // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
    const helper = window.TimeoutNavigationHelper;
    if (!helper) {
      console.error('❌ [BOX-SCORE] TimeoutNavigationHelper not loaded!');
      return;
    }
    
    const currentGameId = helper.getGameId(urlParams);
    const resumeFromTimeout = helper.getResumeFromTimeout(urlParams);
    
    // Build lineup object from URL params
    const lineup = {};
    const myTeamParam = urlParams.get('my_team');
    if (myTeamParam) {
      const positions = ['pg', 'sg', 'sf', 'pf', 'c'];
      positions.forEach(pos => {
        const paramKey = `${myTeamParam}_${pos}`;
        const playerId = urlParams.get(paramKey);
        if (playerId) {
          // Convert lowercase pos to uppercase for lineup object
          lineup[pos.toUpperCase()] = playerId;
        }
      });
    }
    
    // Build params using helper (preserves resume_from_timeout and all timeout state)
    const params = helper.buildGameNavigationParams({
      sourceParams: urlParams,
      targetQuarter: parseInt(quarter, 10) || 1,
      gameId: currentGameId,
      resumeFromTimeout: resumeFromTimeout, // ✅ SS&S: Preserves timeout state
      lineup: lineup,
      myTeamSide: myTeam
    });

    // Determine back navigation target based on "from" parameter
    let backUrl;
    if (from === 'lineup') {
      backUrl = `/set-lineup.html?${params.toString()}`;
    } else if (from === 'game-plan') {
      backUrl = `/game-plan.html?${params.toString()}`;
    } else {
      // Fallback to lineup
      backUrl = `/set-lineup.html?${params.toString()}`;
    }

    backButton.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      playSound('x-back.mp3');
      window.location.href = backUrl;
    });
    return;
  }

  const rawReturn = urlParams.get('return_url');
  const safeReturnUrl =
    typeof getSafeReturnUrl === 'function' ? getSafeReturnUrl(rawReturn) : null;
  if (safeReturnUrl && gameData && urlParams.get('game_id') && isFinalGame) {
    cleanButton.textContent = 'Back';
    cleanButton.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      playSound('x-back.mp3');
      window.location.href = safeReturnUrl;
    });
    return;
  }

  if (gameData && urlParams.get('game_id') && !isFinalGame) {
    const lineupUrl = buildLineupBackUrl();
    if (lineupUrl) {
      cleanButton.textContent = 'Back';
      cleanButton.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        playSound('x-back.mp3');
        window.location.href = lineupUrl;
      });
      return;
    }
  }

  // Otherwise, behave like a post-game "Go To Locker Room" button
  // ✅ SS&S: Prioritize mode parameter from URL (most reliable), then check IDs, then localStorage
  let navMode = mode || 'single';
  let lockerRoomUrl;
  
  // Determine mode and IDs with priority: URL params > localStorage
  const urlTournamentId = tournamentId || urlParams.get('tournament_id');
  const urlFranchiseId = franchiseId || urlParams.get('franchise_id');
  const urlTeamId = urlParams.get('team_id');
  
  // If mode is explicitly set in URL, use it
  if (navMode === 'tournament' || (navMode === 'single' && urlTournamentId)) {
    navMode = 'tournament';
    lockerRoomUrl = '/tournament.html';
    const tournamentParams = new URLSearchParams();
    if (urlTournamentId) {
      tournamentParams.set('tournament_id', urlTournamentId);
    }
    if (urlTeamId) {
      tournamentParams.set('team_id', urlTeamId);
    }
    if (tournamentParams.toString()) {
      lockerRoomUrl += `?${tournamentParams.toString()}`;
    }
  } else if (navMode === 'franchise' || (navMode === 'single' && urlFranchiseId)) {
    navMode = 'franchise';
    lockerRoomUrl = typeof resolveFranchiseLockerRoomUrl === 'function'
      ? resolveFranchiseLockerRoomUrl({
          params: urlParams,
          franchiseId: urlFranchiseId,
          teamId: urlTeamId,
          extraParams: { tut_alert: 'game_complete' }
        })
      : buildFranchiseLockerRoomUrl(urlFranchiseId, urlTeamId, { tut_alert: 'game_complete' });
  } else {
    // ✅ PHASE 2.4: Removed localStorage fallbacks - mode and IDs must come from URL
    // If no mode/ID in URL, default to single game mode
    navMode = 'single';
    lockerRoomUrl = '/mode-select.html';
  }

  const postGamePhaseBFromEog = urlParams.get('post_game_phase_b') === '1';
  let showSimComputerGamesLabel = false;
  if (
    postGamePhaseBFromEog &&
    navMode === 'franchise' &&
    isFinalGame &&
    urlFranchiseId &&
    typeof localStorage !== 'undefined'
  ) {
    const pending =
      window.FranchiseLS && urlFranchiseId
        ? window.FranchiseLS.getPendingCompleteWeek(urlFranchiseId)
        : null;
    if (
      pending &&
      pending.franchise_id != null &&
      String(pending.franchise_id) === String(urlFranchiseId)
    ) {
      showSimComputerGamesLabel = true;
    }
  }

  cleanButton.textContent = showSimComputerGamesLabel
    ? 'Go To Locker Room'
    : 'Back to Locker Room';

  cleanButton.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Franchise EOG: if phase-a ran and user opened box score first, finish CPU week before FCC (button label: "Go To Locker Room" when post_game_phase_b pending)
    if (navMode === 'franchise' && isFinalGame && typeof localStorage !== 'undefined') {
      const pending =
        window.FranchiseLS && urlFranchiseId
          ? window.FranchiseLS.getPendingCompleteWeek(urlFranchiseId)
          : null;
      if (pending && typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl) {
        try {
          const phaseBBody =
            pending &&
            pending.franchise_id != null &&
            pending.week != null &&
            !pending.body
              ? { franchise_id: pending.franchise_id, week: pending.week }
              : null;
          const legacyBody = pending && pending.body;
          const fetchBody = phaseBBody || legacyBody;
          if (fetchBody && String(fetchBody.franchise_id) === String(urlFranchiseId)) {
            cleanButton.disabled = true;
            const prevText = cleanButton.textContent;
            const pulseTeamName = resolveUserTeamNameForPhaseBPulse(urlParams);
            const overlayTitle = pulseTeamName || 'Your team';
            let usedStatusFallback = false;
            if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
              const userTeamSideForFeed = resolveUserTeamSideForPhaseBPulse(urlParams);
              const statLines = window.PageLoadOverlay.buildPostgameStatFeed
                ? window.PageLoadOverlay.buildPostgameStatFeed(gameData, {
                    userTeamSide: userTeamSideForFeed === 'away' ? 'away' : 'home',
                  })
                : [];
              window.PageLoadOverlay.show({
                variant: 'pulse',
                title: statLines.length ? '' : overlayTitle,
                label: 'Simulating Computer Games',
                subtitle: '',
                statLines,
                statIntervalMs: 8000,
                teamName: pulseTeamName || '',
                assetKey: 'banner_primary',
              });
            } else {
              cleanButton.textContent = 'Simulating computer games...';
              usedStatusFallback = true;
            }
            const url = phaseBBody
              ? API_CONFIG.buildUrl('/franchise/complete-week/phase-b')
              : API_CONFIG.buildUrl('/franchise/complete-week');
            try {
              const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fetchBody),
              });
              if (res.ok) {
                if (window.FranchiseLS && urlFranchiseId) {
                  window.FranchiseLS.clearPendingAndEog(urlFranchiseId);
                }
              } else {
                console.error('[BOX-SCORE] week finish failed:', res.status, await res.text());
                alert('Could not finish the week (computer games). Try again.');
                return;
              }
            } finally {
              if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
                window.PageLoadOverlay.hide();
              }
              if (usedStatusFallback) {
                cleanButton.textContent = prevText;
              }
              cleanButton.disabled = false;
            }
          }
        } catch (err) {
          console.warn('[BOX-SCORE] franchise_complete_week_pending handling failed:', err);
        }
      }
    }
    // Single game: delete completed game from DB when user leaves for mode-select
    if (navMode === 'single' && lockerRoomUrl === '/mode-select.html') {
      const gameId = urlParams.get('game_id');
      if (gameId && typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl && API_CONFIG.getAuthHeaders) {
        try {
          await fetch(API_CONFIG.buildUrl('/api/games/delete-completed-single'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...API_CONFIG.getAuthHeaders() },
            body: JSON.stringify({ game_id: gameId }),
          });
        } catch (err) {
          console.warn('[BOX-SCORE] delete-completed-single failed:', err);
        }
      }
    }
    console.log('🚪 [BOX-SCORE] Navigating to locker room:', lockerRoomUrl);
    window.location.href = lockerRoomUrl;
  });
}

// Show special stats popup (Fast Break stats and future stat categories)
function showSpecialStatsPopup(player) {
  const stats = player.stats || {};
  const playerName = player.name || 'Unknown';
  
  // Debug: Log player object structure to verify jersey field
  console.log('[Special Stats Popup] Player object:', {
    name: player.name,
    jersey: player.jersey,
    jerseyNumber: player.jerseyNumber,
    jersey_number: player.jersey_number,
    playerId: player.playerId,
    allKeys: Object.keys(player)
  });
  
  // Get jersey number (use same logic as table rendering)
  // Handle 0 as valid jersey number - use nullish coalescing to preserve 0
  const jersey = player.jersey ?? player.jerseyNumber ?? player.jersey_number ?? '';
  
  // Format jersey number - check multiple possible fields and handle 0 as valid jersey number
  // Jersey can be a number (including 0) or string
  let jerseyNum = null;
  // Check in order: jersey, jerseyNumber, jersey_number
  // Allow 0 as a valid jersey number, only exclude undefined/null/empty string
  if (typeof jersey === 'number') {
    // Handle jersey as number (including 0)
    jerseyNum = jersey;
  } else if (jersey !== undefined && jersey !== null && jersey !== '') {
    jerseyNum = jersey;
  } else if (typeof player.jerseyNumber === 'number') {
    jerseyNum = player.jerseyNumber;
  } else if (player.jerseyNumber !== undefined && player.jerseyNumber !== null && player.jerseyNumber !== '') {
    jerseyNum = player.jerseyNumber;
  } else if (typeof player.jersey_number === 'number') {
    jerseyNum = player.jersey_number;
  } else if (player.jersey_number !== undefined && player.jersey_number !== null && player.jersey_number !== '') {
    jerseyNum = player.jersey_number;
  }
  
  // Convert to string and display if we have a valid jersey (including 0)
  const jerseyDisplay = (jerseyNum !== null && jerseyNum !== undefined) ? ` | #${String(jerseyNum)}` : '';
  
  // Calculate Fast Break stats (popup: S / A / %)
  const fbA = stats.FB_A || 0;
  const fbS = stats.FB_S || 0;
  const fbAD = stats.FB_A_D || 0;
  const fbSD = stats.FB_S_D || 0;
  const offenseSuccessRate = fbA > 0 ? ((fbS / fbA) * 100).toFixed(0) : '0';
  const defenseSuccessRate = fbAD > 0 ? ((fbSD / fbAD) * 100).toFixed(0) : '0';
  
  // Calculate outlet pass stats
  const outletA = stats.Outlet_A || 0;
  const outletScoreList = stats.Outlet_Score_List || [];
  const outletScore = outletA > 0 && outletScoreList.length > 0
    ? (outletScoreList.reduce((a, b) => a + b, 0) / outletScoreList.length).toFixed(0)
    : '0';
  const pot = stats.POT || 0;
  
  // Calculate HCT stats
  const hctA = stats.HCT_A || 0;
  const hctS = stats.HCT_S || 0;
  const hctAD = stats.HCT_A_D || 0;
  const hctSD = stats.HCT_S_D || 0;
  const hctOffenseSuccessRate = hctA > 0 ? ((hctS / hctA) * 100).toFixed(0) : '0';
  const hctDefenseSuccessRate = hctAD > 0 ? ((hctSD / hctAD) * 100).toFixed(0) : '0';
  
  // Calculate FCP stats
  const fcpA = stats.FCP_A || 0;
  const fcpS = stats.FCP_S || 0;
  const fcpAD = stats.FCP_A_D || 0;
  const fcpSD = stats.FCP_S_D || 0;
  const fcpOffenseSuccessRate = fcpA > 0 ? ((fcpS / fcpA) * 100).toFixed(0) : '0';
  const fcpDefenseSuccessRate = fcpAD > 0 ? ((fcpSD / fcpAD) * 100).toFixed(0) : '0';
  
  // Create popup HTML
  const popup = document.createElement('div');
  popup.id = 'special-stats-popup';
  popup.className = 'special-stats-popup';
  popup.innerHTML = `
    <div class="special-stats-popup-content">
      <div class="special-stats-popup-header">
        <h2 class="special-stats-popup-title">${playerName}${jerseyDisplay}</h2>
        <button class="special-stats-popup-close" onclick="closeSpecialStatsPopup()">&times;</button>
      </div>
      <div class="special-stats-popup-body">
        <div class="special-stats-columns-container">
          <div class="special-stats-column">
            <div class="special-stats-row">
              <h3>Fast Breaks</h3>
            </div>
            <div class="special-stats-row special-stats-hint-row">
              <span class="special-stats-hint">S / A / %</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${fbS} / ${fbA} / ${offenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${fbSD} / ${fbAD} / ${defenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row empty-row"></div>
            <div class="special-stats-row">
              <h3>Outlet Passes</h3>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Att / Score:</span>
              <span class="special-stats-value">${outletA} / ${outletScore}</span>
            </div>
          </div>
          <div class="special-stats-column">
            <div class="special-stats-row">
              <h3>Traps</h3>
            </div>
            <div class="special-stats-row special-stats-hint-row">
              <span class="special-stats-hint">S / A / %</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${hctS} / ${hctA} / ${hctOffenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${hctSD} / ${hctAD} / ${hctDefenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row empty-row"></div>
            <div class="special-stats-row">
              <h3>Points off TOs</h3>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-value" style="text-align: left;">${pot}</span>
            </div>
          </div>
          <div class="special-stats-column">
            <div class="special-stats-row">
              <h3>Presses</h3>
            </div>
            <div class="special-stats-row special-stats-hint-row">
              <span class="special-stats-hint">S / A / %</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${fcpS} / ${fcpA} / ${fcpOffenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${fcpSD} / ${fcpAD} / ${fcpDefenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row empty-row"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="special-stats-popup-overlay" onclick="closeSpecialStatsPopup()"></div>
  `;
  
  document.body.appendChild(popup);
  
  // Close on Escape key
  const escapeHandler = (e) => {
    if (e.key === 'Escape') {
      closeSpecialStatsPopup();
      document.removeEventListener('keydown', escapeHandler);
    }
  };
  document.addEventListener('keydown', escapeHandler);
}

// Close special stats popup
function closeSpecialStatsPopup() {
  const popup = document.getElementById('special-stats-popup');
  if (popup) {
    popup.remove();
  }
}
