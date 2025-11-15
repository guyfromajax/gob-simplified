// Box Score Page JavaScript
// Fetches game data and renders box score information

let gameData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const gameId = urlParams.get('game_id');
  
  if (!gameId) {
    console.error('No game_id provided');
    return;
  }

  try {
    await loadGameData(gameId);
    renderBoxScore();
    setupTabs();
    setupLockerRoomButton();
  } catch (error) {
    console.error('Error loading box score:', error);
  }
});

// Fetch game data from API
async function loadGameData(gameId) {
  const response = await fetch(`/api/game/${gameId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch game data: ${response.statusText}`);
  }
  gameData = await response.json();
  console.log('Game data loaded:', gameData);
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

// Render header with team names and scores
function renderHeader() {
  const homeTeam = gameData.home_team || {};
  const awayTeam = gameData.away_team || {};
  const score = gameData.score || {};

  const homeName = homeTeam.name || 'Home Team';
  const awayName = awayTeam.name || 'Away Team';
  const homeScore = score[homeName] || homeTeam.score || 0;
  const awayScore = score[awayName] || awayTeam.score || 0;

  document.getElementById('home-team-name').textContent = homeName;
  document.getElementById('away-team-name').textContent = awayName;
  document.getElementById('home-score').textContent = homeScore;
  document.getElementById('away-score').textContent = awayScore;
}

// Render quarter scoring table
function renderQuarterScoring() {
  const homeTeam = gameData.home_team || {};
  const awayTeam = gameData.away_team || {};
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

  // Get all players including bench (from box_score if available)
  const homeTeamName = gameData.home_team?.name || 'Home Team';
  const awayTeamName = gameData.away_team?.name || 'Away Team';
  
  // box_score structure: { teamName: { pos: { name, FGM, FGA, ... } } }
  const homeBoxScore = boxScore[homeTeamName] || {};
  const awayBoxScore = boxScore[awayTeamName] || {};

  // Combine lineup players with box_score players
  const allHomePlayers = combinePlayersAndBoxScore(homePlayers, homeBoxScore, homeTeamName);
  const allAwayPlayers = combinePlayersAndBoxScore(awayPlayers, awayBoxScore, awayTeamName);

  renderPlayerStatsTable('home', allHomePlayers);
  renderPlayerStatsTable('away', allAwayPlayers);
}

// Combine lineup players with box_score to get all 12 players
// box_score structure: { pos: { name, FGM, FGA, ... } } (stats are direct properties)
function combinePlayersAndBoxScore(lineupPlayers, boxScore, teamName) {
  const playerMap = new Map();
  
  // Add lineup players
  lineupPlayers.forEach(p => {
    playerMap.set(p.playerId, {
      ...p,
      stats: p.stats?.game || p.stats || {},
      year: p.year || 'SR' // Use year from player data or default
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
                         'DEF_A', 'DEF_S', 'HELP_D', 'SCR_A', 'SCR_S'];
        const boxStats = {};
        statKeys.forEach(key => {
          if (playerData[key] !== undefined) {
            boxStats[key] = playerData[key];
          }
        });
        existingPlayer.stats = { ...existingPlayer.stats, ...boxStats };
      } else {
        // New player from box_score (bench player)
        const statKeys = ['FGM', 'FGA', '3PTM', '3PTA', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 
                         'AST', 'STL', 'BLK', 'TO', 'F', 'MIN', 'PTS', 'PIP', 'FB_PTS',
                         'DEF_A', 'DEF_S', 'HELP_D', 'SCR_A', 'SCR_S'];
        const boxStats = {};
        statKeys.forEach(key => {
          if (playerData[key] !== undefined) {
            boxStats[key] = playerData[key];
          }
        });
        playerMap.set(`bench_${pos}`, {
          playerId: playerData.playerId || `bench_${pos}`,
          name: playerData.name || `Player ${pos}`,
          jersey: playerData.jersey || '',
          pos: pos,
          stats: boxStats,
          year: playerData.year || 'SR'
        });
      }
    }
  });

  // Sort by position (PG, SG, SF, PF, C, then bench)
  const positionOrder = ['PG', 'SG', 'SF', 'PF', 'C'];
  return Array.from(playerMap.values()).sort((a, b) => {
    const aPos = positionOrder.indexOf(a.pos) !== -1 ? positionOrder.indexOf(a.pos) : 999;
    const bPos = positionOrder.indexOf(b.pos) !== -1 ? positionOrder.indexOf(b.pos) : 999;
    if (aPos !== bPos) return aPos - bPos;
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
      const year = player.year || 'SR'; // Default to SR if not available
      
      // Calculate TREB and DEF%
      const treb = (stats.DREB || 0) + (stats.OREB || 0);
      const defa = stats.DEF_A || 0;
      const defs = stats.DEF_S || 0;
      const defPct = defa > 0 ? ((defs / defa) * 100).toFixed(0) : '0';
      
      // Format MIN (convert seconds to MM:SS or just minutes)
      const min = formatMinutes(stats.MIN || 0);

      row.innerHTML = `
        <td>${name}${jersey ? ` (#${jersey})` : ''}</td>
        <td>${year}</td>
        <td>${stats.PTS || 0}</td>
        <td>${stats.FGM || 0}/${stats.FGA || 0}</td>
        <td>${stats['3PTM'] || 0}/${stats['3PTA'] || 0}</td>
        <td>${stats.FTM || 0}/${stats.FTA || 0}</td>
        <td>${stats.DREB || 0}</td>
        <td>${stats.OREB || 0}</td>
        <td>${treb}</td>
        <td>${stats.AST || 0}</td>
        <td>${stats.STL || 0}</td>
        <td>${stats.BLK || 0}</td>
        <td>${stats.F || 0}</td>
        <td>${stats.TO || 0}</td>
        <td>${defa}</td>
        <td>${defPct}%</td>
        <td>${min}</td>
      `;
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
      `;
    }
    
    tbody.appendChild(row);
  }
}

// Format minutes (convert seconds to MM:SS or just minutes)
function formatMinutes(seconds) {
  if (!seconds) return '0';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (secs === 0) return mins.toString();
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Render team stats
function renderTeamStats() {
  const teamTotals = gameData.team_totals || {};
  const homeTeamName = gameData.home_team?.name || 'Home Team';
  const awayTeamName = gameData.away_team?.name || 'Away Team';

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
  
  // Calculate TREB and DEF%
  const treb = (totals.DREB || 0) + (totals.OREB || 0);
  const defa = totals.DEF_A || 0;
  const defs = totals.DEF_S || 0;
  const defPct = defa > 0 ? ((defs / defa) * 100).toFixed(0) : '0';

  row.innerHTML = `
    <td>${totals.PTS || 0}</td>
    <td>${totals.FGM || 0}/${totals.FGA || 0}</td>
    <td>${totals['3PTM'] || 0}/${totals['3PTA'] || 0}</td>
    <td>${totals.FTM || 0}/${totals.FTA || 0}</td>
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
  `;

  tbody.appendChild(row);
}

// Render special stats (Fast Breaks, PIP)
function renderSpecialStats(team, totals, teamName) {
  // Fast Breaks
  const teamStats = gameData.team_stats || {};
  const scouting = teamStats[teamName] || {};
  const offense = scouting.offense || {};
  
  const fbEntries = offense.Fast_Break_Entries || 0;
  const fbSuccess = offense.Fast_Break_Success || 0;
  const fbPct = fbEntries > 0 ? ((fbSuccess / fbEntries) * 100).toFixed(0) : '0';
  
  document.getElementById(`${team}-fb-attempts`).textContent = `${fbSuccess} / ${fbEntries}`;
  document.getElementById(`${team}-fb-success-pct`).textContent = `(${fbPct}%)`;
  document.getElementById(`${team}-fb-points`).textContent = totals.FB_PTS || 0;
  document.getElementById(`${team}-pip`).textContent = totals.PIP || 0;
}

// Render scouting notes
function renderScoutingNotes() {
  const teamStats = gameData.team_stats || {};
  const homeTeamName = gameData.home_team?.name || 'Home Team';
  const awayTeamName = gameData.away_team?.name || 'Away Team';

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

  // Play Calls Section
  const playCallsSection = document.createElement('div');
  playCallsSection.className = 'scouting-section';
  playCallsSection.innerHTML = '<h3>Play Calls</h3>';

  // Motion
  const motionSection = createPlaycallSubsection('Motion', playcalls.Motion);
  playCallsSection.appendChild(motionSection);

  // Set Plays
  const setSection = createPlaycallSubsection('Set Plays', playcalls.Set);
  playCallsSection.appendChild(setSection);

  // Cumulative
  const cumulativeSection = createPlaycallSubsection('Cumulative', playcalls.Cumulative);
  playCallsSection.appendChild(cumulativeSection);

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

  subsection.innerHTML = `<h4>${title}: ${overallSuccess} / ${overallAttempts} (${overallPct}%)</h4>`;

  // Inside
  const inside = playcallData.Inside || {};
  const insideAttempts = inside.attempts || 0;
  const insideSuccess = inside.success || 0;
  const insidePct = insideAttempts > 0 ? ((insideSuccess / insideAttempts) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('Inside', `${insideSuccess} / ${insideAttempts}`, `${insidePct}%`));

  // Attack
  const attack = playcallData.Attack || {};
  const attackAttempts = attack.attempts || 0;
  const attackSuccess = attack.success || 0;
  const attackPct = attackAttempts > 0 ? ((attackSuccess / attackAttempts) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('Attack', `${attackSuccess} / ${attackAttempts}`, `${attackPct}%`));

  // Outside
  const outside = playcallData.Outside || {};
  const outsideAttempts = outside.attempts || 0;
  const outsideSuccess = outside.success || 0;
  const outsidePct = outsideAttempts > 0 ? ((outsideSuccess / outsideAttempts) * 100).toFixed(0) : '0';
  subsection.appendChild(createScoutingItem('Outside', `${outsideSuccess} / ${outsideAttempts}`, `${outsidePct}%`));

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

// Setup tab switching
function setupTabs() {
  const tabButtons = document.querySelectorAll('.tab-button');
  const teamContents = document.querySelectorAll('.team-content');

  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const team = button.dataset.team;

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
  if (!button) return;

  // Determine mode from URL params or localStorage
  const urlParams = new URLSearchParams(window.location.search);
  const tournamentId = urlParams.get('tournament_id');
  const franchiseId = urlParams.get('franchise_id');
  
  // Also check localStorage for mode context
  let mode = 'single';
  let lockerRoomUrl;
  
  if (tournamentId || (typeof localStorage !== 'undefined' && localStorage.getItem('activeTournament'))) {
    mode = 'tournament';
    lockerRoomUrl = '/static/tournament.html';
    if (tournamentId) {
      lockerRoomUrl += `?tournament_id=${tournamentId}`;
    }
  } else if (franchiseId || (typeof localStorage !== 'undefined' && localStorage.getItem('franchise_id'))) {
    mode = 'franchise';
    const storedFranchiseId = franchiseId || (typeof localStorage !== 'undefined' ? localStorage.getItem('franchise_id') : null);
    lockerRoomUrl = '/franchise/command-center';
    if (storedFranchiseId) {
      lockerRoomUrl += `?franchise_id=${storedFranchiseId}`;
    }
  } else {
    mode = 'single';
    lockerRoomUrl = '/static/mode-select.html';
  }

  button.addEventListener('click', () => {
    window.location.href = lockerRoomUrl;
  });
}

