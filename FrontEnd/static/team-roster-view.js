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

// View toggle state
let currentView = 'grid'; // 'grid' or 'player'
const cardFlipState = {}; // Track flip state per player ID
const dropdownState = {}; // Track dropdown open state per player ID

function getRosterReturnStorageKey() {
  return [
    'roster_return_url',
    mode || 'base',
    franchiseId || '',
    tournamentId || '',
    teamId || teamName || ''
  ].join(':');
}

function resolveRosterReturnUrl() {
  const storageKey = getRosterReturnStorageKey();
  if (returnUrl) {
    sessionStorage.setItem(storageKey, returnUrl);
    return returnUrl;
  }

  const saved = sessionStorage.getItem(storageKey);
  if (saved) return saved;

  // Fallback for direct links that didn't include return_url.
  try {
    if (document.referrer) {
      const ref = new URL(document.referrer);
      if (ref.origin === window.location.origin && !ref.pathname.includes('player-detail.html')) {
        const relativeRef = `${ref.pathname}${ref.search}`;
        sessionStorage.setItem(storageKey, relativeRef);
        return relativeRef;
      }
    }
  } catch (e) {
    // Ignore referrer parse failures and continue to mode fallback.
  }

  return null;
}

function buildPlayerDetailUrl(playerId) {
  const qs = new URLSearchParams();
  qs.set('id', playerId);
  if (mode) qs.set('mode', mode);
  if (franchiseId) qs.set('franchise_id', franchiseId);
  if (tournamentId) qs.set('tournament_id', tournamentId);
  qs.set('return_url', window.location.pathname + window.location.search);
  return `/player-detail.html?${qs.toString()}`;
}

// Attribute groupings for card back
const ATTR_GROUPS = {
  'OFFENSE': ['SC', 'SH'],
  'DEFENSE': ['ID', 'OD'],
  'SKILLS': ['PS', 'BH'],
  'DIRTY WORK': ['RB', 'ST'],
  'PHYSICAL': ['AG', 'ND'],
  'MIND': ['IQ', 'FT']
};

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
  
  // Initialize view toggle
  initViewToggle();
  
  // Load roster and stats
  await loadRoster();
  await loadStats();
  
  // Setup sorting
  setupRosterSorting();
  setupStatsSorting();
});

function setupBackButton() {
  const backBtn = document.getElementById('back-button');
  const resolvedReturnUrl = resolveRosterReturnUrl();
  backBtn.addEventListener('click', () => {
    if (resolvedReturnUrl) {
      window.location.href = resolvedReturnUrl;
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
        // Base mode (from mode-select) - return to mode-select
        window.location.href = '/mode-select.html';
        return;
      }
      window.location.href = returnPath;
    }
  });
}

async function loadRoster() {
  try {
    // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
    if (!teamName && !teamId) {
      document.getElementById('roster-body').innerHTML = '<tr><td colspan="18">Team name required</td></tr>';
      return;
    }
    
    const displayTeamName = teamName || teamId;
    let url = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(displayTeamName)}`);
    const params = new URLSearchParams();
    
    // Support franchise, tournament, or base mode (no mode parameter)
    if (mode === 'franchise' && franchiseId) {
      params.append('franchise_id', franchiseId);
    } else if (mode === 'tournament' && tournamentId) {
      params.append('tournament_id', tournamentId);
    }
    params.append('profile', '1');
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to load roster: ${response.status}`);
    const data = await response.json();
    
    rosterData = (data.players || []).map(p => {
      const attrs = p.attributes || {};
      const posRatings = p.position_ratings || {};
      
      // Calculate highest RT
      let highestRT = -Infinity;
      let highestPos = null;
      Object.entries(posRatings).forEach(([pos, rating]) => {
        if (typeof rating === 'number' && rating > highestRT) {
          highestRT = rating;
          highestPos = pos;
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
        jersey: p.jersey,
        pos: p.position || getBestPosition(posRatings).pos || '--',
        year: p.year || '--',
        height: heightDisplay,
        heightRaw: heightInches,
        weight: p.weight || '--',
        attributes: attrs,
        position_ratings: posRatings, // Store full position ratings for player view
        highestRT: highestRT !== -Infinity ? highestRT : null,
        highestPos: highestPos || (p.position || '--'),
        photo: p.photo || null,
        hasPlayingTimePromise: !!p.has_playing_time_promise,
        isGraduating: !!p.is_graduating
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
    // Skip stats loading if in base mode (no franchise/tournament)
    if (!mode) {
      // Hide stats section for base roster view
      const statsSection = document.getElementById('stats-section');
      if (statsSection) {
        statsSection.style.display = 'none';
      }
      return;
    }
    
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
    nameLink.href = buildPlayerDetailUrl(p._id);
    nameLink.textContent =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    if (p.hasPlayingTimePromise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.isGraduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
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
  
  // If player view is active, re-render it when roster changes
  if (currentView === 'player') {
    renderPlayerView();
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
    nameLink.href = buildPlayerDetailUrl(p._id);
    nameLink.textContent =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    if (p.hasPlayingTimePromise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.isGraduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
    tr.appendChild(nameTd);
    
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    // Use 3PTM/3PTA directly (standardized field names)
    const tpm = stats['3PTM'] || 0;
    const tpa = stats['3PTA'] || 0;
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
      const tpa1 = a.stats['3PTA'] || 0;
      const tpa2 = b.stats['3PTA'] || 0;
      const tpm1 = a.stats['3PTM'] || 0;
      const tpm2 = b.stats['3PTM'] || 0;
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
  
  // If player view is active, re-render it when stats are sorted
  if (currentView === 'player') {
    renderPlayerView();
  }
}

// ========== VIEW TOGGLE FUNCTIONS ==========

function initViewToggle() {
  // Restore saved view from sessionStorage
  const savedView = sessionStorage.getItem('rosterView');
  if (savedView === 'player') {
    currentView = 'player';
  }
  
  const toggleBtns = document.querySelectorAll('.view-toggle-btn');
  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      switchView(view);
    });
    
    // Set active state based on current view
    if (btn.dataset.view === currentView) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Initialize view
  switchView(currentView);
}

function switchView(view) {
  currentView = view;
  sessionStorage.setItem('rosterView', view);
  
  // Update toggle buttons
  document.querySelectorAll('.view-toggle-btn').forEach(btn => {
    if (btn.dataset.view === view) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Show/hide view containers
  const gridContainer = document.getElementById('roster-table-container');
  const playerContainer = document.getElementById('player-view-container');
  
  if (view === 'grid') {
    gridContainer?.classList.add('active');
    playerContainer?.classList.remove('active');
  } else {
    gridContainer?.classList.remove('active');
    playerContainer?.classList.add('active');
    renderPlayerView();
  }
}

function renderPlayerView() {
  const container = document.querySelector('.players-grid');
  if (!container) return;
  
  container.innerHTML = '';
  
  // Sort players by their HIGHEST position rating
  const sortedPlayers = rosterData
    .map(p => {
      const posRatings = p.position_ratings || {};
      const entries = Object.entries(posRatings);
      
      let highestPos = p.highestPos || p.pos || '--';
      let highestRating = p.highestRT ?? -1;
      
      if (entries.length > 0) {
        const sorted = entries.sort((a, b) => b[1] - a[1]);
        highestPos = sorted[0][0];
        highestRating = sorted[0][1];
      }
      
      return { 
        ...p, 
        highestPos,
        highestRating 
      };
    })
    .sort((a, b) => {
      // Sort by highest rating desc
      if (b.highestRating !== a.highestRating) return b.highestRating - a.highestRating;
      // Then by name asc
      return (a.name || '').localeCompare(b.name || '');
    });
  
  sortedPlayers.forEach(player => {
    const card = createPlayerCard(player);
    container.appendChild(card);
  });
  
  // Initialize tooltips for player cards
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(container, ['.attr-label']);
  }
}

function createPlayerCard(player) {
  const card = document.createElement('div');
  card.className = 'player-card';
  card.dataset.playerId = player._id;
  
  const inner = document.createElement('div');
  inner.className = 'player-card-inner';
  
  // Front side
  const front = createCardFront(player);
  inner.appendChild(front);
  
  // Back side
  const back = createCardBack(player);
  inner.appendChild(back);
  
  card.appendChild(inner);
  
  return card;
}

function createCardFront(player) {
  const front = document.createElement('div');
  front.className = 'player-card-front';
  
  // Headshot container (clickable link to player detail)
  const headshotLink = document.createElement('a');
  headshotLink.href = buildPlayerDetailUrl(player._id);
  headshotLink.style.display = 'block';
  headshotLink.style.textDecoration = 'none';
  
  const headshotContainer = document.createElement('div');
  headshotContainer.className = 'player-headshot-container';
  
  // Set team background image
  const teamNameNormalized = (teamName || '').toLowerCase().replace(/\s+/g, '-');
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const staticPrefix = isLocalhost ? '/static' : '';
  headshotContainer.style.backgroundImage = `url(${(typeof getTeamAssetPath === 'function' ? getTeamAssetPath(teamName, 'background') : staticPrefix + '/images/teams/general/general_background.png')})`;
  headshotContainer.style.backgroundSize = 'cover';
  headshotContainer.style.backgroundPosition = 'center';
  
  // Add energy-based border (NG from attributes)
  const attrs = player.attributes || {};
  const ng = attrs.NG ?? 1.0;
  let borderColor;
  if (ng > 0.89) borderColor = '#00aa00';      // Green
  else if (ng >= 0.8) borderColor = '#cccc00'; // Yellow
  else if (ng >= 0.7) borderColor = '#ff8800'; // Orange
  else borderColor = '#cc0000';                // Red
  
  headshotContainer.style.border = `4px solid ${borderColor}`;
  headshotContainer.style.cursor = 'pointer';
  headshotContainer.style.transition = 'transform 0.2s ease';
  
  // Add hover effect
  headshotContainer.addEventListener('mouseenter', () => {
    headshotContainer.style.transform = 'scale(1.05)';
  });
  headshotContainer.addEventListener('mouseleave', () => {
    headshotContainer.style.transform = 'scale(1)';
  });
  
  // Player image
  const img = document.createElement('img');
  img.className = 'player-headshot';
  img.src = player.photo || `${staticPrefix}/images/players/${player._id}.png`;
  img.alt = player.name;
  img.onerror = () => {
    img.src = `${staticPrefix}/images/players/generic_headshot.png`;
  };
  headshotContainer.appendChild(img);
  
  // Year display (top center)
  if (player.year) {
    const yearDisplay = document.createElement('div');
    yearDisplay.className = 'player-year-display';
    // Format: capitalize first letter, rest lowercase
    const yearText = player.year.toLowerCase();
    const yearFormatted = yearText.charAt(0).toUpperCase() + yearText.slice(1);
    yearDisplay.textContent = yearFormatted;
    
    // Custom colors by year
    let yearColor;
    if (yearText === 'senior') {
      yearColor = '#FFD700'; // Bright gold
    } else if (yearText === 'junior') {
      yearColor = '#C0C0C0'; // Bright silver
    } else if (yearText === 'sophomore') {
      yearColor = '#32CD32'; // Bright lime green
    } else if (yearText === 'freshman') {
      yearColor = '#FF69B4'; // Bright pink
    } else {
      yearColor = '#C0C0C0'; // Default to silver
    }
    
    yearDisplay.style.cssText = `
      position: absolute;
      top: 8px;
      left: 50%;
      transform: translateX(-50%);
      color: ${yearColor};
      opacity: 1.0;
      font-weight: 600;
      font-size: 14px;
      text-transform: capitalize;
      z-index: 10;
      pointer-events: none;
      text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    `;
    headshotContainer.appendChild(yearDisplay);
  }
  
  headshotLink.appendChild(headshotContainer);
  front.appendChild(headshotLink);
  
  // Flip button (outside the link so it doesn't navigate)
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(player._id);
  });
  front.appendChild(flipBtn);
  
  // Position rating circle (top-left, opposite flip button)
  const ratingCircle = createPositionRatingCircle(player);
  front.appendChild(ratingCircle);
  
  // Info bar
  const infoBar = document.createElement('div');
  infoBar.className = 'player-info-bar';
  
  // Left side: name and physical stats
  const leftInfo = document.createElement('div');
  leftInfo.className = 'player-info-left';
  
  const name = document.createElement('div');
  name.className = 'player-name';
  name.textContent =
    typeof formatNameWithJersey === 'function' ? formatNameWithJersey(player.jersey, player.name) : player.name;
  leftInfo.appendChild(name);
  
  const physical = document.createElement('div');
  physical.className = 'player-physical';
  // Format height from raw inches or display string
  let heightDisplay = player.height;
  if (typeof player.heightRaw === 'number') {
    const feet = Math.floor(player.heightRaw / 12);
    const inches = player.heightRaw % 12;
    heightDisplay = `${feet}'${inches}"`;
  }
  physical.textContent = `${heightDisplay} ${player.weight || '--'} lbs`;
  leftInfo.appendChild(physical);
  
  infoBar.appendChild(leftInfo);
  
  // Right side: energy percentage
  const energyDisplay = document.createElement('div');
  energyDisplay.className = 'player-energy-display';
  const ngPercent = Math.round(ng * 100);
  energyDisplay.textContent = `${ngPercent}%`;
  energyDisplay.style.color = borderColor;  // Match border color
  energyDisplay.style.fontWeight = 'bold';
  energyDisplay.style.fontSize = '18px';
  infoBar.appendChild(energyDisplay);
  
  front.appendChild(infoBar);
  
  return front;
}

function createPositionRatingCircle(player) {
  const circle = document.createElement('div');
  circle.className = 'position-rating-circle';
  
  const posRatings = player.position_ratings || {};
  const entries = Object.entries(posRatings)
    .sort((a, b) => b[1] - a[1]); // Sort by rating desc
  
  if (entries.length === 0) {
    circle.style.display = 'none';
    return circle;
  }
  
  // Use player's highest position rating
  const topRating = player.highestRT ?? entries[0][1];
  
  // Display only the highest rating integer value
  circle.textContent = topRating;
  circle.setAttribute('aria-label', 'Position rating');
  
  // Create tooltip content with all 5 position ratings in descending order
  const tooltipContent = entries
    .map(([pos, rating]) => `${pos}: ${rating}`)
    .join('\n');
  
  // Setup tooltip on hover
  setupPositionRatingTooltip(circle, tooltipContent);
  
  return circle;
}

function setupPositionRatingTooltip(element, tooltipText) {
  let tooltip = null;
  
  element.addEventListener('mouseenter', (e) => {
    // Create tooltip element
    tooltip = document.createElement('div');
    tooltip.className = 'position-rating-tooltip';
    tooltip.style.cssText = `
      position: absolute;
      padding: 8px 12px;
      background: rgba(0, 0, 0, 0.95);
      color: #fff;
      font-size: 12px;
      white-space: pre-line;
      border-radius: 6px;
      pointer-events: none;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.2s, visibility 0.2s;
      z-index: 10000;
      font-family: 'Inter', sans-serif;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
      line-height: 1.6;
      text-align: left;
    `;
    tooltip.textContent = tooltipText;
    document.body.appendChild(tooltip);
    
    // Position tooltip near the circle
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    // Position to the right of the circle
    tooltip.style.left = `${rect.right + 8}px`;
    tooltip.style.top = `${rect.top + rect.height / 2 - tooltipRect.height / 2}px`;
    tooltip.style.opacity = '0';
    tooltip.style.visibility = 'visible';
    
    // Force reflow, then show
    tooltip.offsetHeight;
    tooltip.style.opacity = '1';
  });
  
  element.addEventListener('mouseleave', () => {
    if (tooltip) {
      tooltip.style.opacity = '0';
      tooltip.style.visibility = 'hidden';
      // Remove tooltip after transition
      setTimeout(() => {
        if (tooltip && tooltip.parentNode) {
          tooltip.parentNode.removeChild(tooltip);
        }
        tooltip = null;
      }, 200);
    }
  });
  
  element.addEventListener('mousemove', (e) => {
    if (tooltip && tooltip.style.visibility === 'visible') {
      const rect = element.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      
      // Update position to stay near circle
      tooltip.style.left = `${rect.right + 8}px`;
      tooltip.style.top = `${rect.top + rect.height / 2 - tooltipRect.height / 2}px`;
    }
  });
}

function createCardBack(player) {
  const back = document.createElement('div');
  back.className = 'player-card-back';
  
  // Flip button (on back) - exactly like front button
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card back');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(player._id);
  });
  back.appendChild(flipBtn);
  
  // Two-column container
  const columnsContainer = document.createElement('div');
  columnsContainer.className = 'attr-columns-container';
  
  // Column 1
  const column1 = document.createElement('div');
  column1.className = 'attr-column';
  
  // Column 2
  const column2 = document.createElement('div');
  column2.className = 'attr-column';
  
  // Attribute sections - use anchor attributes (not energy-scaled)
  const attrs = player.attributes || {};
  
  // Helper function to create an attribute pill
  function createAttrPill(key, attrs) {
    const pill = document.createElement('div');
    pill.className = 'attr-pill';
    
    const label = document.createElement('span');
    label.className = 'attr-label';
    label.textContent = key;
    // Add tooltip for attribute abbreviation
    if (typeof addTooltip !== 'undefined') {
      addTooltip(label, key);
    }
    pill.appendChild(label);
    
    const value = document.createElement('span');
    value.className = 'attr-value';
    // Use anchor attribute (base value, not energy-scaled)
    const rawVal = attrs[`anchor_${key}`] ?? attrs[key];
    const displayVal = rawVal != null ? Math.floor(rawVal / 10) : '--';
    value.textContent = displayVal;
    
    // Set gold bar fill percentage (0-10 scale, max at 100%)
    if (displayVal !== '--') {
      const fillPercentage = Math.min(displayVal * 10, 100);
      pill.style.setProperty('--attr-fill', `${fillPercentage}%`);
    }
    
    pill.appendChild(value);
    return pill;
  }
  
  // Helper function to create a section with header and pills
  function createSection(headerText, attrKeys) {
    const section = document.createElement('div');
    section.className = 'attr-section';
    
    const title = document.createElement('div');
    title.className = 'attr-section-title';
    title.textContent = headerText;
    section.appendChild(title);
    
    attrKeys.forEach(key => {
      const pill = createAttrPill(key, attrs);
      section.appendChild(pill);
    });
    
    return section;
  }
  
  // Column 1: Offense, Skills, Physical
  column1.appendChild(createSection('Offense', ['SC', 'SH']));
  column1.appendChild(createSection('Skills', ['PS', 'BH']));
  column1.appendChild(createSection('Physical', ['AG', 'ND']));
  
  // Column 2: Defense, Dirty Work, Mind
  column2.appendChild(createSection('Defense', ['ID', 'OD']));
  column2.appendChild(createSection('Dirty Work', ['RB', 'ST']));
  column2.appendChild(createSection('Mind', ['IQ', 'FT']));
  
  columnsContainer.appendChild(column1);
  columnsContainer.appendChild(column2);
  back.appendChild(columnsContainer);
  
  return back;
}

function toggleCardFlip(playerId) {
  const card = document.querySelector(`.player-card[data-player-id="${playerId}"]`);
  if (!card) return;
  
  card.classList.toggle('flipped');
  cardFlipState[playerId] = card.classList.contains('flipped');
}
