// Team Roster View - Displays any team's roster with attributes and season stats
// Supports both Franchise and Tournament modes

const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode'); // 'franchise' or 'tournament'
const teamId = urlParams.get('team_id'); // Team ObjectId or name
const teamName = urlParams.get('team_name'); // Team display name
const franchiseId = urlParams.get('franchise_id');
const tournamentId = urlParams.get('tournament_id');
const returnTab = urlParams.get('return_tab'); // 'standings-tab' or 'schedule-tab'
const returnUrl = urlParams.get('return_url'); // Full return URL

let rosterData = [];
let statsData = [];
let rosterSortColumn = 'RT';
let rosterSortDirection = 'desc';
let statsSortColumn = 'PTS';
let statsSortDirection = 'desc';

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  setupBackButton();
  
  // Set team name in header
  const teamNameEl = document.getElementById('team-name');
  if (teamName) {
    teamNameEl.textContent = `${teamName} Roster`;
  } else {
    teamNameEl.textContent = 'Team Roster';
  }
  
  // Load roster and stats
  await loadRoster();
  await loadStats();
  
  // Setup sorting
  setupRosterSorting();
  setupStatsSorting();
});

function setupBackButton() {
  const backBtn = document.getElementById('back-button');
  backBtn.addEventListener('click', () => {
    if (returnUrl) {
      window.location.href = returnUrl;
    } else {
      // Build return URL
      let returnPath = '';
      if (mode === 'franchise' && franchiseId) {
        returnPath = `/franchise-command-center.html?franchise_id=${franchiseId}`;
        if (returnTab) {
          returnPath += `&tab=${returnTab}`;
        }
      } else if (mode === 'tournament' && tournamentId) {
        returnPath = `/tournament.html?tournament_id=${tournamentId}`;
        if (returnTab) {
          returnPath += `&tab=${returnTab}`;
        }
      } else {
        window.history.back();
        return;
      }
      window.location.href = returnPath;
    }
  });
}

async function loadRoster() {
  try {
    let url = '';
    if (mode === 'franchise' && franchiseId) {
      url = `${API_CONFIG.buildUrl('/franchise/roster')}?franchise_id=${franchiseId}`;
      // Use teamName (team display name) for the API call, not teamId (ObjectId)
      if (teamName) {
        url += `&team_name=${encodeURIComponent(teamName)}`;
      } else if (teamId) {
        // Fallback to teamId if teamName not provided (shouldn't happen, but just in case)
        url += `&team_name=${encodeURIComponent(teamId)}`;
      }
    } else if (mode === 'tournament' && tournamentId) {
      url = `${API_CONFIG.buildUrl('/tournament/roster')}?tournament_id=${tournamentId}`;
      // Use teamName (team display name) for the API call, not teamId (ObjectId)
      if (teamName) {
        url += `&team_name=${encodeURIComponent(teamName)}`;
      } else if (teamId) {
        // Fallback to teamId if teamName not provided
        url += `&team_name=${encodeURIComponent(teamId)}`;
      }
    } else {
      document.getElementById('roster-body').innerHTML = '<tr><td colspan="18">Invalid mode or missing IDs</td></tr>';
      return;
    }
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to load roster: ${response.status}`);
    const data = await response.json();
    
    rosterData = (data.players || []).map(p => {
      const attrs = p.attributes || {};
      const posRatings = p.position_ratings || {};
      
      // Calculate highest RT
      let highestRT = -Infinity;
      Object.values(posRatings).forEach(rating => {
        if (typeof rating === 'number' && rating > highestRT) {
          highestRT = rating;
        }
      });
      
      // Format height
      const heightInches = p.height || 0;
      const feet = Math.floor(heightInches / 12);
      const inches = heightInches % 12;
      const heightDisplay = `${feet}'${inches}"`;
      
      return {
        _id: p._id,
        name: p.name || `${p.first_name || ''} ${p.last_name || ''}`.trim(),
        pos: p.position || getBestPosition(posRatings).pos || '--',
        year: p.year || '--',
        height: heightDisplay,
        heightRaw: heightInches,
        weight: p.weight || '--',
        attributes: attrs,
        highestRT: highestRT !== -Infinity ? highestRT : null
      };
    });
    
    // Default sort by RT descending
    rosterData.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));
    
    renderRoster();
  } catch (error) {
    console.error('Error loading roster:', error);
    document.getElementById('roster-body').innerHTML = `<tr><td colspan="18">Error loading roster: ${error.message}</td></tr>`;
  }
}

async function loadStats() {
  try {
    // Wait for roster to load first so we have player IDs
    if (rosterData.length === 0) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    const teamPlayerIds = rosterData.map(p => p._id);
    if (teamPlayerIds.length === 0) {
      document.getElementById('stats-body').innerHTML = '<tr><td colspan="23">No players found</td></tr>';
      return;
    }
    
    let url = '';
    if (mode === 'franchise' && franchiseId) {
      // For franchise mode, we need to resolve team_id (ObjectId) from team_name
      // First, try to get team document to resolve ObjectId
      if (teamId && teamId.match(/^[0-9a-fA-F]{24}$/)) {
        // teamId is already an ObjectId string, use it
        url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}/${encodeURIComponent(teamId)}?franchise_id=${franchiseId}&scope=season`;
      } else if (teamName) {
        // Resolve team_id from team_name by fetching team document
        try {
          const teamsResponse = await fetch(API_CONFIG.buildUrl('/teams'));
          const teams = await teamsResponse.json();
          const teamDoc = teams.find(t => t.name === teamName);
          if (teamDoc && teamDoc._id) {
            url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}/${encodeURIComponent(teamDoc._id)}?franchise_id=${franchiseId}&scope=season`;
          } else {
            // Fallback: use leaders endpoint and filter by team
            url = `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${franchiseId}&scope=season`;
          }
        } catch (e) {
          // Fallback: use leaders endpoint
          url = `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${franchiseId}&scope=season`;
        }
      } else {
        // Fallback: use user team endpoint
        url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}?franchise_id=${franchiseId}&scope=season`;
      }
    } else if (mode === 'tournament' && tournamentId) {
      // ✅ FIX: Tournament mode - use tournament state endpoint to get tournament document and merge stats
      // Matches Franchise mode pattern (fetch roster + tournament document, merge stats)
      url = `${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${tournamentId}`;
    } else {
      document.getElementById('stats-body').innerHTML = '<tr><td colspan="23">Invalid mode or missing IDs</td></tr>';
      return;
    }
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to load stats: ${response.status}`);
    const data = await response.json();
    
    statsData = [];
    
    if (mode === 'franchise') {
      if (url.includes('/team-player-stats/')) {
        // Direct team stats endpoint
        statsData = (data.players || []).map(p => ({
          _id: p.player_id,
          name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
          stats: p.stats || {}
        }));
      } else {
        // Leaders endpoint - need to filter by team and aggregate
        // Leaders endpoint returns stats by category, we need to extract all players
        const allPlayers = new Map();
        Object.values(data).forEach(category => {
          if (Array.isArray(category)) {
            category.forEach(player => {
              if (teamPlayerIds.includes(player._id)) {
                if (!allPlayers.has(player._id)) {
                  allPlayers.set(player._id, { _id: player._id, name: player.name, stats: {} });
                }
                const playerData = allPlayers.get(player._id);
                // Merge stats from this category
                Object.assign(playerData.stats, player.stats || {});
              }
            });
          }
        });
        statsData = Array.from(allPlayers.values());
      }
    } else if (mode === 'tournament') {
      // ✅ FIX: Tournament mode - merge stats from tournament document (matches Franchise mode pattern)
      // Tournament state endpoint returns full tournament document with players object
      const tournamentPlayers = data.players || {};
      
      // Map roster players to stats from tournament document
      statsData = teamPlayerIds.map(pid => {
        const tournamentPlayer = tournamentPlayers[pid];
        const rosterPlayer = rosterData.find(p => p._id === pid);
        
        if (tournamentPlayer && tournamentPlayer.season) {
          // Player has stats in tournament document
          return {
            _id: pid,
            name: rosterPlayer ? rosterPlayer.name : `${tournamentPlayer.meta?.first_name || ''} ${tournamentPlayer.meta?.last_name || ''}`.trim(),
            stats: tournamentPlayer.season || {}
          };
        } else {
          // Player doesn't have stats yet (team hasn't played)
          return {
            _id: pid,
            name: rosterPlayer ? rosterPlayer.name : '',
            stats: {}
          };
        }
      });
    }
    
    renderStats();
  } catch (error) {
    console.error('Error loading stats:', error);
    document.getElementById('stats-body').innerHTML = `<tr><td colspan="23">Error loading stats: ${error.message}</td></tr>`;
  }
}

function getBestPosition(positionRatings) {
  let bestPos = null;
  let bestRating = -Infinity;
  Object.entries(positionRatings || {}).forEach(([pos, rating]) => {
    if (typeof rating === 'number' && rating > bestRating) {
      bestRating = rating;
      bestPos = pos;
    }
  });
  return { pos: bestPos || '--', rating: bestRating !== -Infinity ? bestRating : null };
}

function renderRoster() {
  const tbody = document.getElementById('roster-body');
  tbody.innerHTML = '';
  
  rosterData.forEach(p => {
    const tr = document.createElement('tr');
    const attrs = p.attributes || {};
    
    // Format attributes: 0-9 displays 0, 10-19 displays 1, etc.
    const formatAttr = (attr) => {
      const rawVal = attrs[`anchor_${attr}`] ?? attrs[attr] ?? 0;
      return Math.floor(rawVal / 10);
    };
    
    // Name with link
    const nameTd = document.createElement('td');
    const nameLink = document.createElement('a');
    nameLink.href = `/player-detail.html?id=${p._id}`;
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
    
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    addCell(formatAttr('SC'));
    addCell(formatAttr('SH'));
    addCell(formatAttr('ID'));
    addCell(formatAttr('OD'));
    addCell(formatAttr('PS'));
    addCell(formatAttr('BH'));
    addCell(formatAttr('RB'));
    addCell(formatAttr('AG'));
    addCell(formatAttr('ST'));
    addCell(formatAttr('ND'));
    addCell(formatAttr('IQ'));
    addCell(formatAttr('FT'));
    addCell(p.highestRT !== null ? p.highestRT : '-');
    
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips if available
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

function renderStats() {
  const tbody = document.getElementById('stats-body');
  tbody.innerHTML = '';
  
  if (statsData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="23">No stats available</td></tr>';
    return;
  }
  
  // Match stats to roster by player ID
  const statsMap = new Map();
  statsData.forEach(s => {
    statsMap.set(s._id, s.stats || {});
  });
  
  rosterData.forEach(p => {
    const stats = statsMap.get(p._id) || {};
    const tr = document.createElement('tr');
    
    // Name
    const nameTd = document.createElement('td');
    const nameLink = document.createElement('a');
    nameLink.href = `/player-detail.html?id=${p._id}`;
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
    
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    // Map 3PTM/3PTA to TPM/TPA for display
    const tpm = stats['3PTM'] || stats.TPM || 0;
    const tpa = stats['3PTA'] || stats.TPA || 0;
    const fgm = stats.FGM || 0;
    const fga = stats.FGA || 0;
    const ftm = stats.FTM || 0;
    const fta = stats.FTA || 0;
    const defa = stats.DEF_A || 0;
    const defs = stats.DEF_S || 0;
    const scra = stats.SCR_A || 0;
    const scrs = stats.SCR_S || 0;
    
    addCell(stats.PTS || 0);
    addCell(fgm);
    addCell(fga);
    addCell(fga > 0 ? ((fgm / fga) * 100).toFixed(1) : '0.0');
    addCell(tpm);
    addCell(tpa);
    addCell(tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0');
    addCell(ftm);
    addCell(fta);
    addCell(fta > 0 ? ((ftm / fta) * 100).toFixed(1) : '0.0');
    addCell(stats.DREB || 0);
    addCell(stats.OREB || 0);
    addCell(stats.TREB || stats.REB || 0);
    addCell(stats.AST || 0);
    addCell(stats.STL || 0);
    addCell(stats.BLK || 0);
    addCell(stats.F || 0);
    addCell(stats.TO || 0);
    addCell(defa);
    addCell(defa > 0 ? ((defs / defa) * 100).toFixed(1) : '0.0');
    addCell(scra);
    addCell(scra > 0 ? ((scrs / scra) * 100).toFixed(1) : '0.0');
    
    tbody.appendChild(tr);
  });
}

function setupRosterSorting() {
  const headers = document.querySelectorAll('#roster-table thead th');
  headers.forEach(header => {
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const sortKey = header.dataset.sort;
      if (sortKey === rosterSortColumn) {
        rosterSortDirection = rosterSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        rosterSortColumn = sortKey;
        rosterSortDirection = 'desc';
      }
      sortRoster();
    });
  });
}

function sortRoster() {
  rosterData.sort((a, b) => {
    let val1, val2;
    
    if (rosterSortColumn === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return rosterSortDirection === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (rosterSortColumn === 'RT') {
      val1 = a.highestRT ?? -Infinity;
      val2 = b.highestRT ?? -Infinity;
    } else if (rosterSortColumn === 'year') {
      const yearOrder = { 'FR': 1, 'SO': 2, 'JR': 3, 'SR': 4 };
      val1 = yearOrder[a.year] || 0;
      val2 = yearOrder[b.year] || 0;
    } else if (rosterSortColumn === 'height') {
      val1 = a.heightRaw || 0;
      val2 = b.heightRaw || 0;
    } else if (rosterSortColumn === 'weight') {
      val1 = parseInt(a.weight) || 0;
      val2 = parseInt(b.weight) || 0;
    } else {
      // Attribute columns
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      const rawValA = attrsA[`anchor_${rosterSortColumn}`] ?? attrsA[rosterSortColumn] ?? 0;
      const rawValB = attrsB[`anchor_${rosterSortColumn}`] ?? attrsB[rosterSortColumn] ?? 0;
      val1 = Math.floor(rawValA / 10);
      val2 = Math.floor(rawValB / 10);
    }
    
    if (rosterSortDirection === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  renderRoster();
}

function setupStatsSorting() {
  const headers = document.querySelectorAll('#stats-table thead th');
  headers.forEach(header => {
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const sortKey = header.dataset.sort;
      if (sortKey === statsSortColumn) {
        statsSortDirection = statsSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        statsSortColumn = sortKey;
        statsSortDirection = 'desc';
      }
      sortStats();
    });
  });
}

function sortStats() {
  // Create a combined array for sorting
  const combined = rosterData.map(p => {
    const stats = statsData.find(s => s._id === p._id)?.stats || {};
    return { player: p, stats };
  });
  
  combined.sort((a, b) => {
    let val1, val2;
    
    if (statsSortColumn === 'name') {
      val1 = a.player.name || '';
      val2 = b.player.name || '';
      return statsSortDirection === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (statsSortColumn === 'FG%') {
      const fga1 = a.stats.FGA || 0;
      const fga2 = b.stats.FGA || 0;
      val1 = fga1 > 0 ? (a.stats.FGM || 0) / fga1 : 0;
      val2 = fga2 > 0 ? (b.stats.FGM || 0) / fga2 : 0;
    } else if (statsSortColumn === '3PT%') {
      const tpa1 = a.stats['3PTA'] || a.stats.TPA || 0;
      const tpa2 = b.stats['3PTA'] || b.stats.TPA || 0;
      const tpm1 = a.stats['3PTM'] || a.stats.TPM || 0;
      const tpm2 = b.stats['3PTM'] || b.stats.TPM || 0;
      val1 = tpa1 > 0 ? tpm1 / tpa1 : 0;
      val2 = tpa2 > 0 ? tpm2 / tpa2 : 0;
    } else if (statsSortColumn === 'FT%') {
      const fta1 = a.stats.FTA || 0;
      const fta2 = b.stats.FTA || 0;
      val1 = fta1 > 0 ? (a.stats.FTM || 0) / fta1 : 0;
      val2 = fta2 > 0 ? (b.stats.FTM || 0) / fta2 : 0;
    } else if (statsSortColumn === 'DEF%') {
      const defa1 = a.stats.DEF_A || 0;
      const defa2 = b.stats.DEF_A || 0;
      val1 = defa1 > 0 ? (a.stats.DEF_S || 0) / defa1 : 0;
      val2 = defa2 > 0 ? (b.stats.DEF_S || 0) / defa2 : 0;
    } else if (statsSortColumn === 'SCR%') {
      const scra1 = a.stats.SCR_A || 0;
      const scra2 = b.stats.SCR_A || 0;
      val1 = scra1 > 0 ? (a.stats.SCR_S || 0) / scra1 : 0;
      val2 = scra2 > 0 ? (b.stats.SCR_S || 0) / scra2 : 0;
    } else {
      val1 = a.stats[statsSortColumn] || 0;
      val2 = b.stats[statsSortColumn] || 0;
    }
    
    if (statsSortDirection === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  // Update rosterData order
  rosterData = combined.map(item => item.player);
  
  // Re-render both tables
  renderRoster();
  renderStats();
}

