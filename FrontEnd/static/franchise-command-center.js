async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Request failed');
    return await res.json();
  } catch (err) {
    console.error('Failed loading', url, err);
    return null;
  }
}

let franchiseId = null;
const userTeamName = localStorage.getItem('franchise_user_team') || '';
// ✅ SS&S: Store team ObjectId for consistent navigation
let userTeamId = null; // Will be resolved from command center data or URL params
let userTeamNameForLeaders = null; // Store user team name for leaderboard highlighting
let teamColorCache = null; // Cache for team primary colors
const ATTR_HEADERS = ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT"];

const teamMap = {
  "Four Corners": "FC",
  "Bentley-Truman": "BT",
  "Lancaster": "Lan",
  "Little York": "LY",
  "Morristown": "Mor",
  "Ocean City": "OC",
  "South Lancaster": "SL",
  "Xavien": "Xav",
};

const teamIdNameMap = {};

function populateTop(data) {
  if (!data) return;
  document.querySelector('.username').textContent = data.username || 'User';
  const formattedTeam = formatTeamName(data.team);
  const logoSrc = `/static/images/homepage-logos/${formattedTeam}.png`;
  document.getElementById('team-logo').src = logoSrc;
  console.log('Team logo URL:', logoSrc);

  const abbr = teamMap[formattedTeam];
  const sammyEl = document.getElementById('coach-sammy');
  const dukeEl = document.getElementById('coach-duke');
  if (abbr) {
    if (sammyEl) {
      sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
      console.log('Coach Sammy URL:', sammyEl.src);
    }
    if (dukeEl) {
      dukeEl.src = `/static/images/coaches/${abbr}/Duke-${abbr}.png`;
      console.log('Coach Duke URL:', dukeEl.src);
    }
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (dukeEl) dukeEl.removeAttribute('src');
  }

  document.querySelector('.chemistry-bar').textContent = `${data.team_chemistry || 0} / 25`;
  document.getElementById('stat-offense').textContent = `Offense: ${data.offense || '--'}`;
  document.getElementById('stat-defense').textContent = `Defense: ${data.defense || '--'}`;
  document.getElementById('stat-athleticism').textContent = `Athleticism: ${data.athleticism || '--'}`;
  document.getElementById('stat-intangibles').textContent = `Intangibles: ${data.intangibles || '--'}`;
  document.getElementById('stat-prestige').textContent = `Prestige: ${data.prestige || '--'}`;
  document.getElementById('stat-rank').textContent = `Nat'l Rank: ${data.rank || '--'}`;
}

function renderStandings(data) {
  if (!data) return;
  const tbody = document.getElementById('standings-body');
  tbody.innerHTML = '';
  (data.standings || []).forEach(t => {
    teamIdNameMap[t.team_id] = t.name;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${t.name}</td><td>${t.W}</td><td>${t.L}</td><td>${t.pct.toFixed(3)}</td><td>${t.PF}</td><td>${t.PA}</td><td>${t.next}</td>`;
    tbody.appendChild(tr);
  });
}

// Helper function to initialize team color cache
async function initializeTeamColorCache() {
  if (teamColorCache) return; // Already initialized
  
  try {
    const res = await fetch('/teams');
    const teamData = await res.json();
    teamColorCache = {};
    teamData.forEach(t => {
      teamColorCache[t.name] = t.primary_color;
    });
  } catch (err) {
    console.warn('Failed to load team colors:', err);
    teamColorCache = {};
  }
}

// Helper function to get team primary color (synchronous, uses cache)
function getTeamPrimaryColor(teamName) {
  if (!teamName || !teamColorCache) return null;
  return teamColorCache[teamName] || null;
}

function renderLeaders(data) {
  if (!data) return;
  const container = document.getElementById('leaders-container');
  container.innerHTML = '';
  const categories = Object.keys(data);
  const primaryColor = getTeamPrimaryColor(userTeamNameForLeaders);
  
  categories.forEach(cat => {
    const section = document.createElement('div');
    const h3 = document.createElement('h3');
    h3.textContent = cat;
    section.appendChild(h3);
    const div = document.createElement('div');
    div.className = 'scroll-x';
    const table = document.createElement('table');
    table.className = 'leaders-table';
    table.innerHTML = '<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>Value</th></tr></thead>';
    const body = document.createElement('tbody');
    (data[cat] || []).forEach((p, idx) => {
      const tr = document.createElement('tr');
      const isUserTeam = userTeamNameForLeaders && p.team === userTeamNameForLeaders;
      
      // Create cells individually to apply styling
      const rankCell = document.createElement('td');
      rankCell.textContent = idx + 1;
      const playerCell = document.createElement('td');
      playerCell.textContent = p.name;
      const teamCell = document.createElement('td');
      teamCell.textContent = p.team;
      const valueCell = document.createElement('td');
      valueCell.textContent = p.value;
      
      // Apply bold and color if user team player
      if (isUserTeam && primaryColor) {
        [rankCell, playerCell, teamCell, valueCell].forEach(cell => {
          cell.style.fontWeight = 'bold';
          cell.style.color = primaryColor;
        });
      }
      
      tr.appendChild(rankCell);
      tr.appendChild(playerCell);
      tr.appendChild(teamCell);
      tr.appendChild(valueCell);
      body.appendChild(tr);
    });
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

// Store teams data for sorting
let teamsDataForSorting = [];

function renderTeamStats(data) {
  if (!data) return;
  teamsDataForSorting = JSON.parse(JSON.stringify(data.teams || [])); // Deep copy for sorting
  renderTeamStatsTable(teamsDataForSorting);
  
  // Add click handlers to sortable headers (only once)
  const sortableHeaders = document.querySelectorAll('#stats-tab .sortable');
  sortableHeaders.forEach(header => {
    // Remove existing listeners to avoid duplicates
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const stat = newHeader.dataset.stat;
      sortTeamStats(stat);
    });
  });
}

function renderTeamStatsTable(teams) {
  const tbody = document.getElementById('teamstats-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  teams.forEach(t => {
    const tr = document.createElement('tr');
    const s = t.stats || {};
    
    // Calculate percentages
    const fgPct = s.FGA > 0 ? ((s.FGM || 0) / s.FGA * 100).toFixed(1) : '0.0';
    const threePct = s.TPA > 0 ? ((s.TPM || 0) / s.TPA * 100).toFixed(1) : '0.0';
    const ftPct = s.FTA > 0 ? ((s.FTM || 0) / s.FTA * 100).toFixed(1) : '0.0';
    const defPct = s.DEF_A > 0 ? ((s.DEF_S || 0) / s.DEF_A * 100).toFixed(1) : '0.0';
    const scrPct = s.SCR_A > 0 ? ((s.SCR_S || 0) / s.SCR_A * 100).toFixed(1) : '0.0';
    
    tr.innerHTML = `
      <td>${t.team}</td>
      <td>${s.PF || 0}</td>
      <td>${s.PA || 0}</td>
      <td>${s.FGM || 0}</td>
      <td>${s.FGA || 0}</td>
      <td>${fgPct}%</td>
      <td>${s.TPM || 0}</td>
      <td>${s.TPA || 0}</td>
      <td>${threePct}%</td>
      <td>${s.FTM || 0}</td>
      <td>${s.FTA || 0}</td>
      <td>${ftPct}%</td>
      <td>${s.DREB || 0}</td>
      <td>${s.OREB || 0}</td>
      <td>${s.TREB || 0}</td>
      <td>${s.AST || 0}</td>
      <td>${s.STL || 0}</td>
      <td>${s.BLK || 0}</td>
      <td>${s.F || 0}</td>
      <td>${s.TO || 0}</td>
      <td>${s.DEF_A || 0}</td>
      <td>${defPct}%</td>
      <td>${s.SCR_A || 0}</td>
      <td>${scrPct}%</td>
    `;
    tbody.appendChild(tr);
  });
}

function sortTeamStats(statKey) {
  // Map display stat names to data stat keys
  const statMap = {
    'team': 'team',
    'PF': 'PF',
    'PA': 'PA',
    'FGM': 'FGM',
    'FGA': 'FGA',
    'FG%': 'FG%',
    'TPM': 'TPM',
    'TPA': 'TPA',
    '3PT%': '3PT%',
    'FTM': 'FTM',
    'FTA': 'FTA',
    'FT%': 'FT%',
    'DREB': 'DREB',
    'OREB': 'OREB',
    'TREB': 'TREB',
    'AST': 'AST',
    'STL': 'STL',
    'BLK': 'BLK',
    'F': 'F',
    'TO': 'TO',
    'DEF_A': 'DEF_A',
    'DEF%': 'DEF%',
    'SCR_A': 'SCR_A',
    'SCR%': 'SCR%'
  };
  
  const dataKey = statMap[statKey] || statKey;
  
  // Sort teams by the selected stat (descending order)
  teamsDataForSorting.sort((a, b) => {
    const s1 = a.stats || {};
    const s2 = b.stats || {};
    
    let val1, val2;
    
    if (dataKey === 'team') {
      val1 = a.team || '';
      val2 = b.team || '';
      return val2.localeCompare(val1); // Reverse for descending
    } else if (dataKey === 'FG%') {
      val1 = s1.FGA > 0 ? (s1.FGM || 0) / s1.FGA : 0;
      val2 = s2.FGA > 0 ? (s2.FGM || 0) / s2.FGA : 0;
    } else if (dataKey === '3PT%') {
      val1 = s1.TPA > 0 ? (s1.TPM || 0) / s1.TPA : 0;
      val2 = s2.TPA > 0 ? (s2.TPM || 0) / s2.TPA : 0;
    } else if (dataKey === 'FT%') {
      val1 = s1.FTA > 0 ? (s1.FTM || 0) / s1.FTA : 0;
      val2 = s2.FTA > 0 ? (s2.FTM || 0) / s2.FTA : 0;
    } else if (dataKey === 'DEF%') {
      val1 = s1.DEF_A > 0 ? (s1.DEF_S || 0) / s1.DEF_A : 0;
      val2 = s2.DEF_A > 0 ? (s2.DEF_S || 0) / s2.DEF_A : 0;
    } else if (dataKey === 'SCR%') {
      val1 = s1.SCR_A > 0 ? (s1.SCR_S || 0) / s1.SCR_A : 0;
      val2 = s2.SCR_A > 0 ? (s2.SCR_S || 0) / s2.SCR_A : 0;
    } else {
      val1 = s1[dataKey] || 0;
      val2 = s2[dataKey] || 0;
    }
    
    return val2 - val1; // Descending order
  });
  
  // Re-render with sorted data
  renderTeamStatsTable(teamsDataForSorting);
}

function renderRecruits(data) {
  if (!data) return;
  const tbody = document.getElementById('recruits-body');
  tbody.innerHTML = '';
  
  // Process recruits to add position and rating info
  let recruits = (data.recruits || []).map(r => {
    const a = r.attributes || {};
    const ratings = r.position_ratings || {};
    const best = getBestPosition(ratings);
    
    return {
      name: r.name,
      archetype: r.archetype || '--',
      height: formatHeight(r.height),
      weight: r.weight ?? '--',
      pos: best.pos,
      rt: best.rating,
      attributes: a
    };
  });
  
  // Sort by rating (highest to lowest)
  recruits.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  
  // Render sorted recruits
  recruits.forEach(r => {
    const tr = document.createElement('tr');
    const a = r.attributes;
    
    // Format attributes: 0-9 displays 0, 10-19 displays 1, 20-29 displays 2, etc.
    const formatAttr = (attr) => {
      const value = attr ?? 0;
      return Math.floor(value / 10);
    };
    
    tr.innerHTML = `<td>${r.name}</td><td>${r.archetype}</td><td>${r.height}</td><td>${r.weight}</td><td>${r.pos}</td><td>${formatAttr(a.SC)}</td><td>${formatAttr(a.SH)}</td><td>${formatAttr(a.ID)}</td><td>${formatAttr(a.OD)}</td><td>${formatAttr(a.PS)}</td><td>${formatAttr(a.BH)}</td><td>${formatAttr(a.RB)}</td><td>${formatAttr(a.AG)}</td><td>${formatAttr(a.ST)}</td><td>${formatAttr(a.ND)}</td><td>${formatAttr(a.IQ)}</td><td>${formatAttr(a.FT)}</td><td>${r.rt ?? '-'}</td>`;
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

function renderTrainingResults(data) {
  const container = document.getElementById('training-results-container');
  if (!container) return;
  
  if (!data || (!data.player_logs || Object.keys(data.player_logs).length === 0)) {
    container.innerHTML = '<p>No training session completed yet.</p>';
    return;
  }
  
  container.innerHTML = '';
  
  // Add session type header
  const sessionHeader = document.createElement('h4');
  const sessionLabel = data.session_type === 'preseason' ? 'Training Camp' : 'In-Season Training';
  sessionHeader.textContent = sessionLabel + (data.week ? ` (Week ${data.week})` : '');
  sessionHeader.style.marginBottom = '15px';
  container.appendChild(sessionHeader);
  
  // Player Results
  const playerHeader = document.createElement('h5');
  playerHeader.textContent = 'Player Attribute Changes';
  playerHeader.style.marginTop = '10px';
  container.appendChild(playerHeader);
  
  const traitOrder = ['SH','SC','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];
  
  if (data.player_logs && typeof data.player_logs === 'object') {
    Object.entries(data.player_logs).forEach(([name, traits]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const bold = document.createElement('strong');
      bold.textContent = name + ': ';
      row.appendChild(bold);

      const parts = traitOrder.map(attr => {
        const val = Object.hasOwnProperty.call(traits, attr) ? traits[attr] : 0;
        if (val === 0) return null;
        const sign = val > 0 ? '+' : '';
        return `${attr} ${sign}${val}`;
      }).filter(p => p !== null);

      row.appendChild(document.createTextNode(parts.join(', ')));
      container.appendChild(row);
    });
  }
  
  // Team Results
  if (data.team_log && typeof data.team_log === 'object' && Object.keys(data.team_log).length > 0) {
    const teamHeader = document.createElement('h5');
    teamHeader.textContent = 'Team Attribute Changes';
    teamHeader.style.marginTop = '20px';
    container.appendChild(teamHeader);

    Object.entries(data.team_log).forEach(([attr, delta]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const sign = delta > 0 ? '+' : '';
      row.textContent = `${attr}: ${sign}${delta}`;
      container.appendChild(row);
    });
  }
}

function renderTeam(data) {
  console.log('renderTeam called with data:', data);
  if (!data) {
    console.log('No data provided to renderTeam');
    return;
  }
  const tbody = document.getElementById('team-body');
  if (!tbody) {
    console.log('team-body element not found');
    return;
  }
  tbody.innerHTML = '';
  console.log('Players data:', data.players);
  let players = (data.players || []).map(p => {
    try {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      const player = {
        _id: p._id, // Add missing _id field for player detail links
        name: fullName,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
      };
      console.log('Mapped player:', player);
      return player;
    } catch (error) {
      console.error('Error mapping player:', p, error);
      return null;
    }
  }).filter(p => p !== null);
  players.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  console.log('Sorted players:', players);
  console.log('About to render', players.length, 'players');
  players.forEach((p, index) => {
    console.log(`Rendering player ${index + 1}:`, p.name);
    const tr = document.createElement('tr');
    
    // Create player name as clickable link
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
    nameLink.href = `/static/player-detail.html?id=${p._id}`;
    nameLink.textContent = p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    tr.appendChild(nameTd);
    
    // Add other columns directly as DOM elements
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    
    ATTR_HEADERS.forEach(h => {
      const attrs = p.attributes || {};
      // Use anchor attribute (base value) as fallback, same as lineup screen
      const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
      console.log(`  ${h}: anchor_${h}=${attrs[`anchor_${h}`]}, ${h}=${attrs[h]}, rawVal=${rawVal}`);
      // Convert to 0-12 scale, except NG which stays as decimal
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.rt ?? '-');
    
    tbody.appendChild(tr);
    console.log(`Added row for ${p.name} to table`);
  });
  console.log('Finished rendering all players. Table now has', tbody.children.length, 'rows');
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
  
  // Also render player stats
  renderRosterStats(data.players || []);
}

function renderSchedule(data) {
  if (!data) return;
  // Schedule container is now in the schedule-tab, not standings-tab
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';
  const teamId = data.team_id;
  (data.schedule || []).forEach((weekGames, idx) => {
    const weekDiv = document.createElement('div');
    weekDiv.className = 'schedule-week';
    const h4 = document.createElement('h4');
    h4.textContent = `Week ${idx + 1}`;
    weekDiv.appendChild(h4);
    weekGames.forEach(g => {
      const gameDiv = document.createElement('div');
      gameDiv.className = 'schedule-game';
      const away = teamIdNameMap[g.away_team_id] || g.away_team_id;
      const home = teamIdNameMap[g.home_team_id] || g.home_team_id;
      let text = '';
      if (g.status === 'complete') {
        let awayStr = `${away} (${g.away_score})`;
        let homeStr = `${home} (${g.home_score})`;
        if (g.away_score > g.home_score) awayStr = `<strong>${awayStr}</strong>`;
        if (g.home_score > g.away_score) homeStr = `<strong>${homeStr}</strong>`;
        text = `${awayStr} at ${homeStr}`;
      } else {
        text = `${away} at ${home}`;
      }
      gameDiv.innerHTML = text;
      
      // ✅ SS&S: Add box score link for all completed games
      if (g.status === 'complete' && g.game_id) {
        const boxScoreLink = document.createElement('a');
        boxScoreLink.href = `/static/box-score.html?mode=franchise&franchise_id=${franchiseId}&game_id=${g.game_id}`;
        boxScoreLink.textContent = ' [Box Score]';
        boxScoreLink.className = 'box-score-link';
        boxScoreLink.style.color = '#4a90e2';
        boxScoreLink.style.textDecoration = 'none';
        boxScoreLink.style.marginLeft = '8px';
        boxScoreLink.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(boxScoreLink);
      }
      
      // Add training report link if this is user's team's game and training report exists
      if (g.is_user_team && g.has_training_report) {
        const link = document.createElement('a');
        // ✅ SS&S: Use ObjectId for consistent navigation
        const teamIdParam = userTeamId || teamId;
        link.href = `/static/training-report.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamIdParam}&week=${g.week}`;
        link.textContent = ' [Training Report]';
        link.className = 'training-report-link';
        link.style.color = '#4a90e2';
        link.style.textDecoration = 'none';
        link.style.marginLeft = '8px';
        link.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(link);
      }
      
      weekDiv.appendChild(gameDiv);
    });
    container.appendChild(weekDiv);
  });
}

async function init() {
  // ✅ SS&S: Check URL params first for team_id (ObjectId) - allows seamless navigation
  const urlParams = new URLSearchParams(window.location.search);
  const urlTeamId = urlParams.get('team_id');
  if (urlTeamId) {
    userTeamId = urlTeamId;
    localStorage.setItem('franchise_user_team_id', userTeamId);
  } else {
    // Fallback to localStorage
    userTeamId = localStorage.getItem('franchise_user_team_id');
  }
  
  const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
  populateTop(topData);
  
  // ✅ SS&S: Resolve team_id from command center data if not already set
  if (topData && topData.team_id && !userTeamId) {
    userTeamId = topData.team_id;
    localStorage.setItem('franchise_user_team_id', userTeamId);
  }
  
  // Store user team name for leaderboard highlighting
  if (topData && topData.team) {
    userTeamNameForLeaders = topData.team;
  }
  
  // Initialize team color cache for leaderboard highlighting
  await initializeTeamColorCache();
  
  // Update button based on training status
  updatePlayButton(topData);
  
  if (topData && topData.team) {
    // Use franchise-specific roster endpoint to get updated player attributes
    console.log('Loading franchise roster for team:', topData.team, 'franchiseId:', franchiseId);
    if (!franchiseId) {
      console.error('No franchiseId found - cannot load roster');
      return;
    }
    try {
      const rosterData = await fetchJSON(`/franchise/roster?franchise_id=${franchiseId}&team_name=${encodeURIComponent(topData.team)}`);
      console.log('Franchise roster data:', rosterData);
      
      // Load player stats separately from franchise document
      const franchiseDoc = await fetchJSON(`/franchise/state?franchise_id=${franchiseId}`);
      console.log('🔍 [FCC] Franchise document loaded:', {
        hasPlayers: !!franchiseDoc?.players,
        playerCount: franchiseDoc?.players ? Object.keys(franchiseDoc.players).length : 0,
        firstPlayerId: franchiseDoc?.players ? Object.keys(franchiseDoc.players)[0] : null,
        firstPlayerData: franchiseDoc?.players ? Object.keys(franchiseDoc.players).length > 0 ? franchiseDoc.players[Object.keys(franchiseDoc.players)[0]] : null : null
      });
      
      if (franchiseDoc && franchiseDoc.players && rosterData.players) {
        // Merge stats into player data
        let statsFound = 0;
        let statsMissing = 0;
        rosterData.players = rosterData.players.map(player => {
          const playerId = player._id;
          const franchisePlayer = franchiseDoc.players[playerId];
          if (franchisePlayer && franchisePlayer.season) {
            player.stats = { season: franchisePlayer.season };
            statsFound++;
            console.log(`✅ [FCC] Stats found for player ${player.name} (${playerId}):`, franchisePlayer.season);
          } else {
            player.stats = { season: {} };
            statsMissing++;
            console.log(`❌ [FCC] No stats found for player ${player.name} (${playerId}). Franchise player data:`, franchisePlayer);
          }
          return player;
        });
        console.log(`🔍 [FCC] Stats merge complete: ${statsFound} found, ${statsMissing} missing`);
      } else {
        console.error('❌ [FCC] Cannot merge stats:', {
          hasFranchiseDoc: !!franchiseDoc,
          hasPlayers: !!franchiseDoc?.players,
          hasRosterPlayers: !!rosterData?.players
        });
      }
      
      if (rosterData.players && rosterData.players.length > 0) {
        console.log('🔍 [FCC] First player data:', {
          name: rosterData.players[0].name,
          id: rosterData.players[0]._id,
          attributes: rosterData.players[0].attributes,
          stats: rosterData.players[0].stats
        });
      }
      renderTeam(rosterData);
    } catch (error) {
      console.error('Failed to load franchise roster:', error);
    }
  }
  const standingsData = await fetchJSON(`/franchise/standings?franchise_id=${franchiseId}`);
  renderStandings(standingsData);
    const scheduleData = await fetchJSON(`/franchise/schedule?franchise_id=${franchiseId}`);
    renderSchedule(scheduleData);
    renderLeaders(await fetchJSON(`/franchise/leaders?franchise_id=${franchiseId}`));
    renderTeamStats(await fetchJSON(`/franchise/team-stats?franchise_id=${franchiseId}`));
    renderRecruits(await fetchJSON(`/franchise/recruits?franchise_id=${franchiseId}`));
    // ✅ Removed: renderTrainingResults - Training Reports are now linked directly on Schedule page
    
    // Initialize tooltips for table headers
    if (typeof initAttributeTooltips !== 'undefined') {
      const rosterTable = document.querySelector('#roster-tab .roster-table');
      const recruitsTable = document.querySelector('#recruits-tab .roster-table');
      if (rosterTable) initAttributeTooltips(rosterTable, ['th']);
      if (recruitsTable) initAttributeTooltips(recruitsTable, ['th']);
    }
    
    // Load team data for Team tab
    await loadTeamData();
  }

function updatePlayButton(data) {
  const playNowBtn = document.getElementById('play-now');
  if (!data) return;
  
  const trainingCompleted = data.training_completed || false;
  const sessionType = data.session_type || 'in-season';
  
  if (!trainingCompleted) {
    playNowBtn.textContent = sessionType === 'preseason' ? 'Run Training Camp' : 'Run Training';
    playNowBtn.dataset.mode = 'training';
  } else {
    playNowBtn.textContent = 'Play Now';
    playNowBtn.dataset.mode = 'play';
  }
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
playNowBtn.addEventListener('click', async () => {
  const mode = playNowBtn.dataset.mode || 'play';
  
  if (mode === 'training') {
    // Navigate to training page
    const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
    const sessionType = topData?.session_type || 'in-season';
    // ✅ SS&S: Include team_id (ObjectId) for consistent navigation
    const teamIdParam = userTeamId ? `&team_id=${encodeURIComponent(userTeamId)}` : '';
    window.location.href = `/static/training.html?franchise_id=${franchiseId}&mode=franchise&session_type=${sessionType}${teamIdParam}`;
    return;
  }
  
  // Otherwise, play the game
  console.log('Play Now click search:', window.location.search);
  const originalText = playNowBtn.textContent;
  playNowBtn.disabled = true;
  playNowBtn.textContent = 'Loading...';
  if (!franchiseId) {
    alert('Franchise not loaded');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
    return;
  }
  try {
    const res = await fetch('/franchise/play-next-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    if (!res.ok) throw new Error('Simulation failed');
    const { home, away, week, home_id, away_id } = await res.json();
    if (!home || !away) throw new Error('Matchup not found');
    try {
      localStorage.setItem('franchise_week', week);
    } catch {}
    const mySide = userTeamName === home ? 'home' : (userTeamName === away ? 'away' : '');
    let url = `/static/set-lineup.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&home_id=${encodeURIComponent(home_id)}&away_id=${encodeURIComponent(away_id)}`;
    // ✅ SS&S: Use ObjectId for consistent navigation
    if (userTeamId) url += `&team_id=${encodeURIComponent(userTeamId)}`;
    if (mySide) url += `&my_team=${mySide}`;
    console.log('Navigating to', url);
    window.location.href = url;
  } catch (err) {
    console.error(err);
    alert('Unable to play next game');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
  }
});

// Set Game Plan button (Franchise Command Center)
const setGameplanBtn = document.getElementById('set-gameplan-franchise');
if (setGameplanBtn) {
  setGameplanBtn.addEventListener('click', () => {
    if (!franchiseId || !userTeamId) {
      alert('Franchise or user team not loaded');
      return;
    }
    
    // ✅ SS&S: Redirect to Game Plan screen with ObjectId for consistent navigation
    const url = `/game-plan.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}&from=command_center`;
    window.location.href = url;
  });
}

// Playbooks button (Franchise Command Center)
const playbooksBtn = document.getElementById('playbooks-franchise');
if (playbooksBtn) {
  playbooksBtn.addEventListener('click', () => {
    if (!franchiseId || !userTeamId) {
      alert('Franchise or user team not loaded');
      return;
    }
    
      // ✅ SS&S: Build playbooks URL with ObjectId for consistent navigation
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('franchise_id', franchiseId);
      params.set('team_id', userTeamId);
      params.set('from', 'franchise-command-center'); // Track navigation source
      
      window.location.href = `/static/playbooks.html?${params.toString()}`;
  });
}

window.addEventListener('DOMContentLoaded', () => {
  franchiseId = localStorage.getItem('franchiseId');
  if (franchiseId) {
    playNowBtn.disabled = false;
  }
  init();
  
  // Listen for tab changes to render Team Report when Team tab is opened
  const tabButtons = document.querySelectorAll('.tab-buttons button');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === 'team-tab') {
        // Load and render team data when Team tab is opened
        if (!teamData) {
          loadTeamData();
        } else {
          renderTeamReport();
          renderPlaybookSummary();
        }
      }
    });
  });
});

// Team Report and Playbook Summary functions (adapted from training-report.js)
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Trap',
  'foul_modifier': 'Aggression',
  'turnover_modifier': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'Press/Trap Breaks'
};

let teamData = null;

async function loadTeamData() {
  if (!franchiseId || !userTeamId) return;
  
  try {
    // First, ensure team objects exist (this will create them if missing)
    try {
      // ✅ SS&S: Use ObjectId directly - backend accepts it
      await fetch(`/api/gameplan?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`);
    } catch (error) {
      console.warn('Could not ensure team objects exist:', error);
    }
    
    // ✅ SS&S: Use ObjectId directly - backend accepts team_id parameter
    const response = await fetch(`/franchise/team-data?franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`);
    
    if (!response.ok) {
      console.error('Failed to load team data:', response.status, response.statusText);
      return;
    }
    
    const data = await response.json();
    
    // Also load players for top scorer lookup
    let players = [];
    try {
      const rosterResponse = await fetch(`/franchise/roster?franchise_id=${encodeURIComponent(franchiseId)}&team_name=${encodeURIComponent(data.team_name || '')}`);
      if (rosterResponse.ok) {
        const rosterData = await rosterResponse.json();
        players = rosterData.players || [];
      }
    } catch (error) {
      console.warn('Could not load players for team data:', error);
    }
    
    teamData = {
      team_attributes: data.team_attributes || {},
      plays_data: data.plays_data || {},
      scouting_data: data.scouting_data || {},
      players: players
    };
    
    console.log('📊 [TEAM DATA] Loaded team data:', {
      attributes: Object.keys(teamData.team_attributes).length,
      plays: Object.keys(teamData.plays_data).length,
      defenses: Object.keys(teamData.scouting_data?.defense || {}).length
    });
    
    // Render if Team tab is active
    const teamTab = document.getElementById('team-tab');
    if (teamTab && teamTab.classList.contains('active')) {
      renderTeamReport();
      renderPlaybookSummary();
    }
  } catch (error) {
    console.error('Failed to load team data:', error);
  }
}

function renderTeamReport() {
  if (!teamData) return;
  
  const grid = document.getElementById('team-attributes-grid');
  if (!grid) return;
  
  grid.innerHTML = '';
  
  const teamAttrs = teamData.team_attributes || {};
  
  const attrOrder = [
    'shot_threshold',
    'rebound_modifier',
    'offensive_efficiency',
    'defensive_efficiency',
    'fb_efficiency',
    'pt_efficiency',
    'foul_modifier',
    'turnover_modifier',
    'momentum_score',
    'team_chemistry',
    'fb_opp_modifier',
    'pt_opp_modifier'
  ];
  
  attrOrder.forEach(attrKey => {
    const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], 0);
    if (item) grid.appendChild(item);
  });
}

function createTeamAttrItem(attrKey, currentValue, change) {
  const displayName = TEAM_ATTR_NAMES[attrKey];
  if (!displayName) return null;
  
  if (currentValue === undefined || currentValue === null) {
    currentValue = 0;
  }
  if (change === undefined || change === null) {
    change = 0;
  }
  
  const item = document.createElement('div');
  item.className = 'team-attr-item';
  
  const label = document.createElement('div');
  label.className = 'attr-label';
  
  const nameSpan = document.createElement('span');
  nameSpan.textContent = displayName;
  
  label.appendChild(nameSpan);
  item.appendChild(label);
  
  if (attrKey === 'team_chemistry') {
    const barContainer = document.createElement('div');
    barContainer.className = 'chemistry-bar-container';
    
    const barFill = document.createElement('div');
    barFill.className = 'chemistry-bar-fill';
    const percentage = (currentValue / 25) * 100;
    barFill.style.width = `${percentage}%`;
    
    const barText = document.createElement('div');
    barText.className = 'chemistry-bar-text';
    barText.textContent = `${currentValue} / 25`;
    
    barContainer.appendChild(barFill);
    barContainer.appendChild(barText);
    item.appendChild(barContainer);
  } else if (attrKey === 'fb_opp_modifier' || attrKey === 'pt_opp_modifier') {
    const indicatorContainer = document.createElement('div');
    indicatorContainer.className = 'plus-minus-container';
    indicatorContainer.style.textAlign = 'center';
    indicatorContainer.style.marginTop = 'var(--spacing-sm)';
    
    const indicator = document.createElement('span');
    indicator.className = 'plus-minus-indicator';
    indicator.style.fontWeight = '700';
    
    if (currentValue >= 10) {
      indicator.textContent = '+++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 5) {
      indicator.textContent = '++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 1) {
      indicator.textContent = '+';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue === 0) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-zero';
    } else if (currentValue >= -4) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-negative';
    } else if (currentValue >= -9) {
      indicator.textContent = '--';
      indicator.className += ' plus-minus-negative';
    } else {
      indicator.textContent = '---';
      indicator.className += ' plus-minus-negative';
    }
    
    indicatorContainer.appendChild(indicator);
    item.appendChild(indicatorContainer);
  } else {
    const pill = createPill(currentValue, attrKey);
    item.appendChild(pill);
  }
  
  return item;
}

function createPill(originalValue, attrKey) {
  const pill = document.createElement('div');
  pill.className = 'attr-pill';
  
  const centerLine = document.createElement('div');
  centerLine.className = 'pill-center-line';
  pill.appendChild(centerLine);
  
  let maxValue = 10;
  let value = originalValue;
  
  if (attrKey === 'shot_threshold') {
    maxValue = 200;
  } else if (attrKey === 'rebound_modifier') {
    maxValue = 0.2;
    value = originalValue - 1.0;
  }
  
  if (value > 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-positive';
    const percentage = Math.min((value / maxValue) * 50, 50);
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  } else if (value < 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-negative';
    const absValue = Math.abs(value);
    const percentage = Math.min((absValue / maxValue) * 50, 50);
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  }
  
  return pill;
}

function renderPlaybookSummary() {
  if (!teamData) return;
  
  const container = document.getElementById('playbook-summary-container');
  if (!container) return;
  
  container.innerHTML = '';
  
  const plays_data = teamData.plays_data || {};
  const scouting_data = teamData.scouting_data || {};
  
  const motion_plays = [];
  const set_plays = [];
  
  for (const [play_name, play_data] of Object.entries(plays_data)) {
    if (typeof play_data === 'object' && play_data !== null) {
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push({ name: play_name, ...play_data });
      } else if (play_type === 'set_play') {
        set_plays.push({ name: play_name, ...play_data });
      }
    }
  }
  
  motion_plays.sort((a, b) => a.name.localeCompare(b.name));
  set_plays.sort((a, b) => a.name.localeCompare(b.name));
  
  const man_defenses = [];
  const zone_defenses = [];
  
  if (scouting_data.defense) {
    for (const [defense_name, defense_data] of Object.entries(scouting_data.defense)) {
      if (typeof defense_data === 'object' && defense_data !== null) {
        if (defense_name === 'Man') {
          man_defenses.push({ name: defense_name, ...defense_data });
        } else if (defense_name.includes('Zone')) {
          zone_defenses.push({ name: defense_name, ...defense_data });
        }
      }
    }
  }
  
  man_defenses.sort((a, b) => a.name.localeCompare(b.name));
  zone_defenses.sort((a, b) => a.name.localeCompare(b.name));
  
  const offenseSection = document.createElement('div');
  offenseSection.className = 'playbook-category';
  
  const offenseTitle = document.createElement('h3');
  offenseTitle.textContent = 'Offense';
  offenseSection.appendChild(offenseTitle);
  
  // Get players data for top scorer lookup (only for offensive plays)
  const players = teamData.players || [];
  
  if (motion_plays.length > 0) {
    motion_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.name, play, null, players);
      offenseSection.appendChild(playRow);
    });
  }
  
  if (set_plays.length > 0) {
    set_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.name, play, null, players);
      offenseSection.appendChild(playRow);
    });
  }
  
  const emptyRow = document.createElement('div');
  emptyRow.className = 'playbook-empty-row';
  offenseSection.appendChild(emptyRow);
  
  container.appendChild(offenseSection);
  
  const defenseSection = document.createElement('div');
  defenseSection.className = 'playbook-category';
  
  const defenseTitle = document.createElement('h3');
  defenseTitle.textContent = 'Defense';
  defenseSection.appendChild(defenseTitle);
  
  if (man_defenses.length > 0) {
    man_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, null);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  if (zone_defenses.length > 0) {
    zone_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, null);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  container.appendChild(defenseSection);
}

function createPlayRow(playName, playData, change, players = []) {
  // playData can be an object with effectiveness, momentum, cloaking, or just a number (effectiveness)
  // Handle both formats for backward compatibility
  const effectiveness = typeof playData === 'object' ? (playData.effectiveness || 0) : (playData || 0);
  const momentum = typeof playData === 'object' ? (playData.momentum || 0) : 0;
  const cloaking = typeof playData === 'object' ? (playData.cloaking || 0) : 0;
  
  // Check if this is an offensive play (motion or set_play) to show success rate and top scorer
  const isOffensivePlay = typeof playData === 'object' && 
    (playData.play_type === 'motion' || playData.play_type === 'set_play');
  
  const row = document.createElement('div');
  row.className = 'playbook-row';
  
  // Play name
  const nameDiv = document.createElement('div');
  nameDiv.className = 'playbook-name';
  nameDiv.textContent = playName;
  row.appendChild(nameDiv);
  
  // Metrics container - holds all three bars
  const metricsContainer = document.createElement('div');
  metricsContainer.className = 'playbook-metrics-container';
  
  // Command (Effectiveness) - Blue, 0-100 scale
  const commandMetric = createMetricBar('Command', effectiveness, 100, '#4a90e2', null);
  metricsContainer.appendChild(commandMetric);
  
  // Momentum - Orange, 0-10 scale
  const momentumMetric = createMetricBar('Momentum', momentum, 10, '#ff9800', null);
  metricsContainer.appendChild(momentumMetric);
  
  // Cloaking - Purple, 0-10 scale
  const cloakingMetric = createMetricBar('Cloaking', cloaking, 10, '#9c27b0', null);
  metricsContainer.appendChild(cloakingMetric);
  
  row.appendChild(metricsContainer);
  
  // Success Rate and Top Scorer column (only for offensive plays)
  if (isOffensivePlay) {
    const statsContainer = document.createElement('div');
    statsContainer.className = 'playbook-stats-container';
    statsContainer.style.display = 'flex';
    statsContainer.style.flexDirection = 'column';
    statsContainer.style.gap = '8px';
    
    // Calculate success rate from season_stats
    const seasonStats = playData.season_stats || {};
    const timesRun = seasonStats.times_run || 0;
    const successes = seasonStats.successes || 0;
    const successRate = timesRun > 0 ? Math.round((successes / timesRun) * 100) : 0;
    
    // Success Rate
    const successRateDiv = document.createElement('div');
    successRateDiv.className = 'playbook-success-rate';
    successRateDiv.textContent = `Success Rate: ${successRate}%`;
    statsContainer.appendChild(successRateDiv);
    
    // Top Scorer
    const topScorerDiv = document.createElement('div');
    topScorerDiv.className = 'playbook-top-scorer';
    
    const playerPoints = seasonStats.player_points || {};
    let topScorerId = null;
    let topScorerPoints = 0;
    
    // Find top scorer
    for (const [playerId, points] of Object.entries(playerPoints)) {
      if (points > topScorerPoints) {
        topScorerPoints = points;
        topScorerId = playerId;
      }
    }
    
    if (topScorerId && topScorerPoints > 0) {
      // Find player name
      const player = players.find(p => p._id === topScorerId || p.id === topScorerId);
      const playerName = player ? (player.name || `${player.first_name || ''} ${player.last_name || ''}`.trim()) : 'Unknown Player';
      topScorerDiv.textContent = `Top Scorer: ${playerName}, ${topScorerPoints} PTS`;
    } else {
      topScorerDiv.textContent = 'Top Scorer: N/A';
    }
    
    statsContainer.appendChild(topScorerDiv);
    row.appendChild(statsContainer);
  }
  
  return row;
}

function createMetricBar(title, value, maxValue, color, change) {
  const metricDiv = document.createElement('div');
  metricDiv.className = 'playbook-metric';
  
  // Title
  const titleDiv = document.createElement('div');
  titleDiv.className = 'playbook-metric-title';
  titleDiv.textContent = title;
  metricDiv.appendChild(titleDiv);
  
  // Progress bar container
  const progressContainer = document.createElement('div');
  progressContainer.className = 'playbook-progress-container';
  
  const progressBar = document.createElement('div');
  progressBar.className = 'playbook-progress-bar';
  
  const progressFill = document.createElement('div');
  progressFill.className = 'playbook-progress-fill';
  progressFill.style.backgroundColor = color;
  const percentage = Math.min(100, (value / maxValue) * 100);
  progressFill.style.width = `${percentage}%`;
  
  progressBar.appendChild(progressFill);
  progressContainer.appendChild(progressBar);
  metricDiv.appendChild(progressContainer);
  
  // Change indicator (only for Command/Effectiveness)
  if (change !== null && change !== undefined) {
    const changeDiv = document.createElement('div');
    changeDiv.className = 'playbook-change';
    
    if (change > 0) {
      changeDiv.textContent = `+${change}`;
      changeDiv.style.color = '#4CAF50'; // Green
    } else if (change < 0) {
      changeDiv.textContent = `-${Math.abs(change)}`;
      changeDiv.style.color = '#f44336'; // Red
    } else {
      changeDiv.textContent = '0';
      changeDiv.style.color = '#ffffff'; // White
    }
    
    metricDiv.appendChild(changeDiv);
  }
  
  return metricDiv;
}

// Store players data for sorting (roster stats)
let rosterPlayersDataForSorting = [];

// Update renderTeam to also render player stats
function renderRosterStats(players) {
  if (!players || players.length === 0) {
    const tbody = document.getElementById('roster-stats-body');
    if (tbody) tbody.innerHTML = '';
    return;
  }
  
  rosterPlayersDataForSorting = JSON.parse(JSON.stringify(players)); // Deep copy for sorting
  renderRosterStatsTable(rosterPlayersDataForSorting);
  
  // Add click handlers to sortable headers (only once) - target only the stats table
  const statsTable = document.querySelector('#roster-tab .stats-table');
  if (statsTable) {
    const sortableHeaders = statsTable.querySelectorAll('thead .sortable');
    sortableHeaders.forEach(header => {
      // Remove existing listeners to avoid duplicates
      const newHeader = header.cloneNode(true);
      header.parentNode.replaceChild(newHeader, header);
      
      newHeader.style.cursor = 'pointer';
      newHeader.style.userSelect = 'none';
      newHeader.addEventListener('click', () => {
        const stat = newHeader.dataset.stat;
        sortRosterStats(stat);
      });
    });
  }
}

function renderRosterStatsTable(players) {
  const tbody = document.getElementById('roster-stats-body');
  if (!tbody) return;
  
  tbody.innerHTML = '';
  
  players.forEach(p => {
    const stats = p.stats?.season || {};
    // ✅ FIX: Map 3PTM/3PTA to TPM/TPA for display (database stores as 3PTM/3PTA, frontend expects TPM/TPA)
    const tpm = stats['3PTM'] || stats.TPM || 0;
    const tpa = stats['3PTA'] || stats.TPA || 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name || `${p.first_name || ''} ${p.last_name || ''}`.trim()}</td>
      <td>${stats.PTS || 0}</td>
      <td>${stats.FGM || 0}</td>
      <td>${stats.FGA || 0}</td>
      <td>${tpm}</td>
      <td>${tpa}</td>
      <td>${stats.FTM || 0}</td>
      <td>${stats.FTA || 0}</td>
      <td>${stats.REB || 0}</td>
      <td>${stats.AST || 0}</td>
      <td>${stats.STL || 0}</td>
      <td>${stats.BLK || 0}</td>
      <td>${stats.F || 0}</td>
      <td>${stats.MIN || 0}</td>
      <td>${stats.TO || 0}</td>`;
    tbody.appendChild(tr);
  });
}

function sortRosterStats(statKey) {
  // Map display stat names to data stat keys
  const statMap = {
    'name': 'name',
    'PTS': 'PTS',
    'FGM': 'FGM',
    'FGA': 'FGA',
    'TPM': 'TPM',
    'TPA': 'TPA',
    'FTM': 'FTM',
    'FTA': 'FTA',
    'REB': 'REB',
    'AST': 'AST',
    'STL': 'STL',
    'BLK': 'BLK',
    'F': 'F',
    'MIN': 'MIN',
    'TO': 'TO'
  };
  
  const dataKey = statMap[statKey] || statKey;
  
  // Sort players by the selected stat (descending order)
  rosterPlayersDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (dataKey === 'name') {
      const name1 = a.name || `${a.first_name || ''} ${a.last_name || ''}`.trim() || '';
      const name2 = b.name || `${b.first_name || ''} ${b.last_name || ''}`.trim() || '';
      return name2.localeCompare(name1); // Reverse for descending
    } else {
      const stats1 = a.stats?.season || {};
      const stats2 = b.stats?.season || {};
      
      // Handle 3PTM/3PTA mapping
      if (dataKey === 'TPM') {
        val1 = stats1['3PTM'] || stats1.TPM || 0;
        val2 = stats2['3PTM'] || stats2.TPM || 0;
      } else if (dataKey === 'TPA') {
        val1 = stats1['3PTA'] || stats1.TPA || 0;
        val2 = stats2['3PTA'] || stats2.TPA || 0;
      } else {
        val1 = stats1[dataKey] || 0;
        val2 = stats2[dataKey] || 0;
      }
    }
    
    return val2 - val1; // Descending order
  });
  
  // Re-render with sorted data
  renderRosterStatsTable(rosterPlayersDataForSorting);
}

