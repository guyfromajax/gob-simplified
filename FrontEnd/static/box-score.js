// Box Score Page JavaScript
// Fetches game data and renders box score information

let gameData = null;

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
  const response = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`));
  if (!response.ok) {
    console.error('❌ Failed to fetch game data:', response.status, response.statusText);
    throw new Error(`Failed to fetch game data: ${response.statusText}`);
  }
  gameData = await response.json();
  console.log('✅ Game data loaded:', {
    gameId,
    hasBoxScore: !!gameData.box_score,
    boxScoreKeys: gameData.box_score ? Object.keys(gameData.box_score) : [],
    hasPlayers: !!gameData.players,
    playerCount: gameData.players ? gameData.players.length : 0,
    score: gameData.score,
    quarter: gameData.quarter
  });
  
  // Fetch full rosters to ensure all 12 players are shown
  const urlParams = new URLSearchParams(window.location.search);
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
    await mergeFullRosters(homeTeamName, awayTeamName, franchiseId, tournamentId, mode);
  }
}

// Fetch and merge full rosters with game data to ensure all 12 players are shown
async function mergeFullRosters(homeTeamName, awayTeamName, franchiseId, tournamentId, mode) {
  const fetchRoster = async (team) => {
    let path;
    if (mode === 'franchise' && franchiseId) {
      path = `${API_CONFIG.buildUrl('/franchise/roster')}?franchise_id=${franchiseId}&team_name=${encodeURIComponent(team)}`;
    } else if (mode === 'tournament' && tournamentId) {
      path = `${API_CONFIG.buildUrl('/tournament/roster')}?tournament_id=${tournamentId}&team_name=${encodeURIComponent(team)}`;
    } else {
      path = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(team)}`);
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

  // Map roster players to box-score-ready format
  const mapPlayers = (players, teamKey, teamName) =>
    players.map((p) => {
      // Check if this player is in the game data (lineup players)
      const gamePlayer = gameData.players?.find(
        gp => (gp.playerId || gp._id || gp.player_id) === (p._id || p.playerId)
      );
      
      // Check if this player has box score stats
      const boxScore = gameData.box_score?.[teamName] || {};
      const boxScorePlayer = Object.entries(boxScore).find(
        ([pos, playerData]) => 
          typeof playerData === 'object' && 
          playerData.name === p.name ||
          (playerData.playerId || playerData.player_id) === (p._id || p.playerId)
      )?.[1];

      // Calculate highest RT from position_ratings
      const posRatings = p.position_ratings || {};
      const rtValues = Object.values(posRatings);
      const highestRT = rtValues.length > 0 ? Math.max(...rtValues) : -Infinity;

      return {
        playerId: p._id || p.playerId,
        team: teamKey,
        name: p.name,
        jersey: boxScorePlayer?.jersey !== undefined ? boxScorePlayer.jersey : (p.jersey || ''),
        pos: p.pos || p.position || null,
        stats: gamePlayer?.stats?.game || boxScorePlayer || gamePlayer?.stats || {},
        year: p.year || 'SR',
        highestRT: highestRT,
      };
    });

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
  
  gameData.players = [
    ...sortByRT(mapPlayers(homeRoster, 'home', homeTeamName)),
    ...sortByRT(mapPlayers(awayRoster, 'away', awayTeamName)),
  ];
  
  console.log(`Merged full rosters: ${homeRoster.length} home players, ${awayRoster.length} away players`);
}

// Render all box score sections
function renderBoxScore() {
  if (!gameData) return;

  renderHeader();
  renderQuarterScoring();
  renderPlayerStats();
  renderTeamStats();
  renderScoutingNotes();
}

// Build zeroed box score data from rosters when viewing pre-game
async function loadPreGameData({ homeTeamName, awayTeamName, franchiseId, tournamentId, mode }) {
  const fetchRoster = async (team) => {
    let path;
    if (mode === 'franchise' && franchiseId) {
      path = `${API_CONFIG.buildUrl('/franchise/roster')}?franchise_id=${franchiseId}&team_name=${encodeURIComponent(team)}`;
    } else if (mode === 'tournament' && tournamentId) {
      path = `${API_CONFIG.buildUrl('/tournament/roster')}?tournament_id=${tournamentId}&team_name=${encodeURIComponent(team)}`;
    } else {
      path = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(team)}`);
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
        jersey: p.jersey || '',
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

// Render header with team names and scores
function renderHeader() {
  // ✅ UNIFIED STRUCTURE: Get team data from unified teams object, fallback to old structure
  const homeTeamId = gameData.home_team_id;
  const awayTeamId = gameData.away_team_id;
  const teamsObj = gameData.teams || {};
  
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : (gameData.home_team || {});
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : (gameData.away_team || {});
  
  const score = gameData.score || {};

  const homeName = homeTeamObj.name || 'Home Team';
  const awayName = awayTeamObj.name || 'Away Team';
  const homeScore = score[homeName] || homeTeamObj.score || 0;
  const awayScore = score[awayName] || awayTeamObj.score || 0;

  document.getElementById('home-team-name').textContent = homeName;
  document.getElementById('away-team-name').textContent = awayName;
  document.getElementById('home-score').textContent = homeScore;
  document.getElementById('away-score').textContent = awayScore;
  
  // Update tab button labels with team names
  const homeTabButton = document.querySelector('.tab-button[data-team="home"]');
  const awayTabButton = document.querySelector('.tab-button[data-team="away"]');
  if (homeTabButton) homeTabButton.textContent = homeName;
  if (awayTabButton) awayTabButton.textContent = awayName;
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

  const homeName = homeTeam.name || 'Home Team';
  const awayName = awayTeam.name || 'Away Team';
  const homePoints = pointsByQuarter[homeName] || [0, 0, 0, 0];
  const awayPoints = pointsByQuarter[awayName] || [0, 0, 0, 0];

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
  const homeFinal = score[homeName] || homeTeam.score || homePoints.reduce((a, b) => a + b, 0);
  const awayFinal = score[awayName] || awayTeam.score || awayPoints.reduce((a, b) => a + b, 0);
  document.getElementById('home-final-score').textContent = homeFinal;
  document.getElementById('away-final-score').textContent = awayFinal;

  // Update team names in table
  document.getElementById('home-quarter-team-name').textContent = homeName;
  document.getElementById('away-quarter-team-name').textContent = awayName;
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
      jersey: p.jersey !== undefined ? p.jersey : (p.jerseyNumber || p.jersey_number || '') // Preserve jersey from multiple possible sources
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
                         'FB_A', 'FB_S', 'FB_F', 'FB_N', 'FB_A_D', 'FB_S_D', 'FB_F_D',
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
                         'FB_A', 'FB_S', 'FB_F', 'FB_N', 'FB_A_D', 'FB_S_D', 'FB_F_D',
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
          jersey: playerData.jersey !== undefined ? playerData.jersey : (playerData.jerseyNumber || playerData.jersey_number || ''),
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
      const jersey = player.jersey || '';
      
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
      nameLink.style.color = '#0066cc';
      nameLink.style.textDecoration = 'underline';
      nameLink.addEventListener('click', () => showSpecialStatsPopup(player));
      nameCell.appendChild(nameLink);
      
      // Clear row and build it properly
      row.innerHTML = '';
      row.appendChild(nameCell);
      row.appendChild(createTableCell(stats.PTS || 0));
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

  renderScoutingContent('home', teamStats[homeTeamName] || {});
  renderScoutingContent('away', teamStats[awayTeamName] || {});
}

// Render scouting content for a team
function renderScoutingContent(team, teamStats) {
  const container = document.getElementById(`${team}-scouting-content`);
  container.innerHTML = '';

  const offense = teamStats.offense || {};
  const defense = teamStats.defense || {};
  const playcalls = offense.Playcalls || {};

  // Offense Play Calls Section
  const playCallsSection = document.createElement('div');
  playCallsSection.className = 'scouting-section';
  playCallsSection.innerHTML = '<h3>Offense Play Calls</h3>';

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

  container.appendChild(playCallsSection);

  // Special Situations Section
  const specialSection = document.createElement('div');
  specialSection.className = 'scouting-section';
  specialSection.innerHTML = '<h3>Special Situations</h3>';

  // Fast Breaks
  const fbEntries = offense.Fast_Break_Entries || 0;
  const fbSuccess = offense.Fast_Break_Success || 0;
  const fbPct = fbEntries > 0 ? ((fbSuccess / fbEntries) * 100).toFixed(0) : '0';
  specialSection.appendChild(createScoutingItem('Fast Breaks', `${fbSuccess} / ${fbEntries}`, `${fbPct}%`));

  // HC Traps
  const hct = defense.HCT || {};
  const hctUsed = hct.used || 0;
  const hctSuccess = hct.success || 0;
  const hctPct = hctUsed > 0 ? ((hctSuccess / hctUsed) * 100).toFixed(0) : '0';
  specialSection.appendChild(createScoutingItem('HC Traps', `${hctSuccess} / ${hctUsed}`, `${hctPct}%`));

  // FC Presses
  const fcp = defense.FCP || {};
  const fcpUsed = fcp.used || 0;
  const fcpSuccess = fcp.success || 0;
  const fcpPct = fcpUsed > 0 ? ((fcpSuccess / fcpUsed) * 100).toFixed(0) : '0';
  specialSection.appendChild(createScoutingItem('FC Presses', `${fcpSuccess} / ${fcpUsed}`, `${fcpPct}%`));

  container.appendChild(specialSection);

  // Defense Play Calls Section
  const defensePlayCallsSection = document.createElement('div');
  defensePlayCallsSection.className = 'scouting-section';
  defensePlayCallsSection.innerHTML = '<h3>Defense Play Calls</h3>';

  // Man
  const manDefense = defense.Man || {};
  const manDefenseSection = createDefensePlaycallSubsection('Man', manDefense);
  defensePlayCallsSection.appendChild(manDefenseSection);

  // Zone (aggregate all zone types: 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
  const zone23 = defense['2-3 Zone'] || {};
  const zone32 = defense['3-2 Zone'] || {};
  const zone131 = defense['1-3-1 Zone'] || {};
  
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
  
  const zoneDefenseSection = createDefensePlaycallSubsection('Zone', zoneDefense);
  defensePlayCallsSection.appendChild(zoneDefenseSection);

  // 2-3 Zone
  const zone23Defense = defense['2-3 Zone'] || {};
  const zone23DefenseSection = createDefensePlaycallSubsection('2-3 Zone', zone23Defense);
  defensePlayCallsSection.appendChild(zone23DefenseSection);

  // 3-2 Zone
  const zone32Defense = defense['3-2 Zone'] || {};
  const zone32DefenseSection = createDefensePlaycallSubsection('3-2 Zone', zone32Defense);
  defensePlayCallsSection.appendChild(zone32DefenseSection);

  // 1-3-1 Zone
  const zone131Defense = defense['1-3-1 Zone'] || {};
  const zone131DefenseSection = createDefensePlaycallSubsection('1-3-1 Zone', zone131Defense);
  defensePlayCallsSection.appendChild(zone131DefenseSection);

  container.appendChild(defensePlayCallsSection);
}

// Create playcall subsection (Motion, Set, Cumulative)
function createPlaycallSubsection(title, playcallData) {
  if (!playcallData) {
    const empty = document.createElement('div');
    empty.className = 'scouting-subsection';
    empty.innerHTML = `<h4>${title}: No data</h4>`;
    return empty;
  }

  const subsection = document.createElement('div');
  subsection.className = 'scouting-subsection';

  const overall = playcallData.overall || {};
  const overallAttempts = overall.attempts || 0;
  const overallSuccess = overall.success || 0;
  const overallPct = overallAttempts > 0 ? ((overallSuccess / overallAttempts) * 100).toFixed(0) : '0';

  // Calculate average EV and Exec for offense playcalls
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
  
  const overallAvgText = overallAvgEV !== null || overallAvgExec !== null
    ? ` (Avg EV: <span style="color: ${overallEvColor || '#000'}">${overallEvSign}${overallAvgEV || '0'}%</span>) (Avg Exec: <span style="color: ${overallExecColor || '#000'}">${overallExecSign}${overallAvgExec || '0'}%</span>)`
    : '';

  // For "Focus Success Rates", don't show the numbers in the header
  const headerText = title === 'Focus Success Rates' 
    ? `<h4>${title}${overallAvgText}</h4>`
    : `<h4>${title}: ${overallSuccess} / ${overallAttempts} (${overallPct}%)${overallAvgText}</h4>`;
  
  subsection.innerHTML = headerText;

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

// Create a scouting item element
function createScoutingItem(label, value, pct) {
  const item = document.createElement('div');
  item.className = 'scouting-item';
  item.innerHTML = `
    <span class="scouting-item-label">${label}:</span>
    <span class="scouting-item-value">${value}</span>
    <span class="scouting-item-pct">(${pct})</span>
  `;
  return item;
}

// Create a scouting item element with vs Man and vs Zone columns
function createScoutingItemWithVs(label, value, pct, vsManValue, vsManPct, vsZoneValue, vsZonePct) {
  const item = document.createElement('div');
  item.className = 'scouting-item';
  item.innerHTML = `
    <span class="scouting-item-label">${label}:</span>
    <span class="scouting-item-value">${value}</span>
    <span class="scouting-item-pct">(${pct})</span>
    <span class="scouting-item-vs" style="margin-left: 15px;">vs Man: ${vsManValue} (${vsManPct}%), vs Zone: ${vsZoneValue} (${vsZonePct}%)</span>
  `;
  return item;
}

// Create defense playcall subsection (Man, Zone, etc.)
function createDefensePlaycallSubsection(title, defenseData) {
  // Check if we have game_stats or season_stats
  const stats = defenseData.game_stats || defenseData.season_stats || defenseData || {};
  
  const subsection = document.createElement('div');
  subsection.className = 'scouting-subsection';

  const used = stats.used || 0;
  const success = stats.success || 0;
  const pct = used > 0 ? ((success / used) * 100).toFixed(0) : '0';

  // Calculate average EV and Exec (lean_score)
  const evScores = stats.ev_scores || [];
  const leanScores = stats.lean_scores || [];
  const avgEV = evScores.length > 0 
    ? (evScores.reduce((a, b) => a + b, 0) / evScores.length).toFixed(0)
    : '0';
  const avgExec = leanScores.length > 0
    ? (leanScores.reduce((a, b) => a + b, 0) / leanScores.length * 100).toFixed(0)
    : '0';
  
  const evSign = parseFloat(avgEV) >= 0 ? '+' : '';
  const execSign = parseFloat(avgExec) >= 0 ? '+' : '';
  
  // Color coding: negative=red, zero=yellow, positive=green
  const evColor = parseFloat(avgEV) < 0 ? '#ff0000' : (parseFloat(avgEV) === 0 ? '#ffd700' : '#00AA00');
  const execColor = parseFloat(avgExec) < 0 ? '#ff0000' : (parseFloat(avgExec) === 0 ? '#ffd700' : '#00AA00');
  
  const headerText = `${title}: ${success} / ${used} (${pct}%)`;
  const avgText = evScores.length > 0 || leanScores.length > 0
    ? ` (Avg EV: <span style="color: ${evColor}">${evSign}${avgEV}%</span>) (Avg Exec: <span style="color: ${execColor}">${execSign}${avgExec}%</span>)`
    : '';
  
  subsection.innerHTML = `<h4>${headerText}${avgText}</h4>`;

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
  
  const vsMotionAvgText = vsMotionAvgEV !== null || vsMotionAvgExec !== null
    ? ` (Avg EV: <span style="color: ${vsMotionEvColor || '#000'}">${vsMotionEvSign}${vsMotionAvgEV || '0'}%</span>) (Avg Exec: <span style="color: ${vsMotionExecColor || '#000'}">${vsMotionExecSign}${vsMotionAvgExec || '0'}%</span>)`
    : '';
  
  const vsMotionDisplayPct = vsMotionAvgText ? `${vsMotionPct}%${vsMotionAvgText}` : `${vsMotionPct}%`;
  subsection.appendChild(createScoutingItem('vs Motion', `${safeVsMotionSuc} / ${vsMotionAtt}`, vsMotionDisplayPct));

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
  
  const vsSetAvgText = vsSetAvgEV !== null || vsSetAvgExec !== null
    ? ` (Avg EV: <span style="color: ${vsSetEvColor || '#000'}">${vsSetEvSign}${vsSetAvgEV || '0'}%</span>) (Avg Exec: <span style="color: ${vsSetExecColor || '#000'}">${vsSetExecSign}${vsSetAvgExec || '0'}%</span>)`
    : '';
  
  const vsSetDisplayPct = vsSetAvgText ? `${vsSetPct}%${vsSetAvgText}` : `${vsSetPct}%`;
  subsection.appendChild(createScoutingItem('vs Set Play', `${safeVsSetSuc} / ${vsSetAtt}`, vsSetDisplayPct));

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

  // Get team colors from gameData
  const homeTeam = gameData?.home_team || {};
  const awayTeam = gameData?.away_team || {};
  const homePrimaryColor = homeTeam.primary_color || '#000000';
  const awayPrimaryColor = awayTeam.primary_color || '#000000';

  tabButtons.forEach(button => {
      const team = button.dataset.team;

    // Set background color based on team
    if (team === 'home') {
      button.style.backgroundColor = homePrimaryColor;
      button.style.color = '#fff';
    } else if (team === 'away') {
      button.style.backgroundColor = awayPrimaryColor;
      button.style.color = '#fff';
    }
    
    button.addEventListener('click', () => {
      // Update active tab
      tabButtons.forEach(btn => btn.classList.remove('active'));
      button.classList.add('active');

      // Update active content
      teamContents.forEach(content => content.classList.remove('active'));
      document.getElementById(`${team}-content`).classList.add('active');
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
  
  // ✅ SS&S: Handle back navigation from lineup or game-plan screens
  // Both use TimeoutNavigationHelper to preserve timeout state
  if (from === 'lineup' || from === 'game-plan') {
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
      window.location.href = backUrl;
    });
    return;
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
    // ✅ FIX: Use correct franchise command center path
    lockerRoomUrl = '/franchise-command-center.html';
    const franchiseParams = new URLSearchParams();
    franchiseParams.set('mode', 'franchise'); // ✅ Always include mode for consistency
    const finalFranchiseId = urlFranchiseId || (typeof localStorage !== 'undefined' ? localStorage.getItem('franchise_id') : null);
    if (finalFranchiseId) {
      franchiseParams.set('franchise_id', finalFranchiseId);
    }
    if (urlTeamId) {
      franchiseParams.set('team_id', urlTeamId);
    }
    if (franchiseParams.toString()) {
      lockerRoomUrl += `?${franchiseParams.toString()}`;
    }
  } else {
    // Fallback: Check localStorage as last resort (for backward compatibility)
    if (typeof localStorage !== 'undefined' && localStorage.getItem('activeTournament')) {
      navMode = 'tournament';
      lockerRoomUrl = '/tournament.html';
      const storedTournamentId = localStorage.getItem('activeTournament');
      if (storedTournamentId) {
        lockerRoomUrl += `?tournament_id=${storedTournamentId}`;
      }
    } else if (typeof localStorage !== 'undefined' && localStorage.getItem('franchise_id')) {
      navMode = 'franchise';
      lockerRoomUrl = '/franchise-command-center.html';
      const storedFranchiseId = localStorage.getItem('franchise_id');
      if (storedFranchiseId) {
        lockerRoomUrl += `?franchise_id=${storedFranchiseId}`;
      }
    } else {
      navMode = 'single';
      lockerRoomUrl = '/mode-select.html';
    }
  }

  cleanButton.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
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
  
  // Calculate Fast Break stats
  const fbA = stats.FB_A || 0;
  const fbS = stats.FB_S || 0;
  const fbF = stats.FB_F || 0;
  const fbN = fbA - (fbS + fbF); // Calculated
  
  const fbAD = stats.FB_A_D || 0;
  const fbSD = stats.FB_S_D || 0;
  const fbFD = stats.FB_F_D || 0;
  
  // Calculate success rates
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
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${fbA} / ${offenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${fbAD} / ${defenseSuccessRate}%</span>
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
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${hctA} / ${hctOffenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${hctAD} / ${hctDefenseSuccessRate}%</span>
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
            <div class="special-stats-row">
              <span class="special-stats-label">Offense:</span>
              <span class="special-stats-value">${fcpA} / ${fcpOffenseSuccessRate}%</span>
            </div>
            <div class="special-stats-row">
              <span class="special-stats-label">Defense:</span>
              <span class="special-stats-value">${fcpAD} / ${fcpDefenseSuccessRate}%</span>
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

