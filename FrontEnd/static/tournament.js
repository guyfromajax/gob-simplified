// Read URL parameters first (for navigation from training report, etc.)
const urlParams = new URLSearchParams(window.location.search);
const urlTournamentId = urlParams.get('tournament_id');
const urlTeamId = urlParams.get('team_id');

// Initialize tournament and userTeamId from URL params or localStorage
let tournament = null;
let userTeamId = ""; // ObjectId for API calls
let userTeamName = ""; // Team name for bracket comparisons
let userTeamNameForLeaders = null; // Store user team name for leaderboard highlighting (matches Franchise pattern)
let teamColorCache = null; // Cache for team primary colors
let teamMetaByNameCache = null;
let tournamentRosterData = null; // ✅ SS&S: Store roster data with merged stats (matches Franchise pattern)

function playSound(filename) {
  try {
    const base = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function() {});
  } catch (e) {}
}

function buildPlayerDetailUrl(playerId) {
  const qs = new URLSearchParams();
  qs.set('id', playerId);
  qs.set('mode', 'tournament');
  const tid = urlTournamentId || tournament?._id || '';
  if (tid) qs.set('tournament_id', tid);
  qs.set('return_url', window.location.pathname + window.location.search);
  return `/player-detail.html?${qs.toString()}`;
}

// If tournament_id is in URL, use it (overrides localStorage)
if (urlTournamentId) {
  // Will be loaded in loadTournament() using the URL param
  tournament = null; // Force reload from URL
} else {
  // Fall back to localStorage
  tournament = JSON.parse(localStorage.getItem("activeTournament")) || null;
}

// If team_id is in URL, use it (overrides localStorage)
if (urlTeamId) {
  userTeamId = urlTeamId;
  localStorage.setItem("userTeamId", userTeamId);
} else {
  // Fall back to localStorage
  userTeamId = localStorage.getItem("userTeamId") || "";
}

// Match franchise command center mapping
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

function isUserTeam(teamNameOrId) {
  return teamNameOrId === userTeamName || String(teamNameOrId) === String(userTeamId);
}

// Map full team names to bracket logo filenames
const logoMap = {
  "Bentley-Truman": "Bently-Horizontal.svg",
  "Four Corners": "Corners-Horizontal.svg",
  "Lancaster": "Lancaster-Horizontal.svg",
  "Little York": "York-Horizontal.svg",
  "Morristown": "Morristown-Horizontal.svg",
  "Ocean City": "Ocean-Horizontal (1).svg",
  "South Lancaster": "South-Horizontal.svg",
  "Xavien": "Xavien-Horizontal (1).svg",
};

// tournament is preloaded from localStorage above; always refreshed from API.
let roster = [];
let stats = [];
const ATTR_HEADERS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"];
const DEBUG_TEAM_STATS = window.DEBUG_TEAM_STATS || false;
const DEBUG_BRACKET = window.DEBUG_BRACKET || false;

const leaderBoards = [
  { title: "Points", key: "PTS", valueHeader: "Points" },
  { title: "3PTM", key: "3PTM", valueHeader: "3PT Made" },
  { title: "Rebound", key: "REB", valueHeader: "Rebounds" },
  { title: "Assists", key: "AST", valueHeader: "Assists" },
  { title: "Blocks", key: "BLK", valueHeader: "Blocks" },
  { title: "Steals", key: "STL", valueHeader: "Steals" }
];

let leaderData = {};

/** ID -> name map for schedule/bracket display (Franchise pattern). Populated from team-stats. */
const teamIdNameMap = {};

console.log("✅ tournament.js loaded");

function getLogo(teamName) {
  return typeof getTeamAssetPath === 'function' ? getTeamAssetPath(teamName, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
}

function getTeamTooltipText(teamName) {
  if (!teamName) return '';
  const meta = teamMetaByNameCache?.[teamName] || null;
  const mascot = String(meta?.mascot || '').trim();
  return mascot ? `${teamName} ${mascot}` : String(teamName);
}


function renderBracket() {
  if (!tournament) return;
  const bracket = document.getElementById("bracket");
  bracket.innerHTML = "";

  const round1 = tournament.bracket?.round1 || [];
  let round2 = tournament.bracket?.round2 || [];
  let finalRound = tournament.bracket?.final || [];
  const results = tournament.results || [];

  const seedMap = {};
  if (round1.length === 4) {
    seedMap[round1[0].home_team] = 1;
    seedMap[round1[0].away_team] = 8;
    seedMap[round1[1].home_team] = 4;
    seedMap[round1[1].away_team] = 5;
    seedMap[round1[2].home_team] = 2;
    seedMap[round1[2].away_team] = 7;
    seedMap[round1[3].home_team] = 3;
    seedMap[round1[3].away_team] = 6;
  }

  function getResult(round, index) {
    return results.find(r => r.round === round && r.match_index === index) || null;
  }

  function applyResults(matches, round) {
    matches.forEach((m, i) => {
      const res = getResult(round, i);
      if (res) {
        m.score = res.score || {};
        m.winner = res.winner ?? null;
      }
    });
  }

  // ensure existing bracket data reflects any recorded results
  applyResults(round1, 1);
  applyResults(round2, 2);
  applyResults(finalRound, 3);

  // Derive next-round matchups from results if bracket slots are missing
  if (!round2.length) {
    const r1Winners = round1
      .map((m, i) => m.winner ?? getResult(1, i)?.winner)
      .filter(Boolean);
    if (r1Winners.length === 4) {
      round2 = [
        { home_team: r1Winners[0], away_team: r1Winners[1], game_id: null, winner: null, score: {} },
        { home_team: r1Winners[2], away_team: r1Winners[3], game_id: null, winner: null, score: {} },
      ];
      tournament.bracket.round2 = round2;
      if (tournament.current_round < 2) tournament.current_round = 2;
    }
  }

  if (!finalRound.length && round2.length === 2) {
    const r2Winners = round2
      .map((m, i) => m.winner ?? getResult(2, i)?.winner)
      .filter(Boolean);
    if (r2Winners.length === 2) {
      finalRound = [
        { home_team: r2Winners[0], away_team: r2Winners[1], game_id: null, winner: null, score: {} },
      ];
      tournament.bracket.final = finalRound;
      if (tournament.current_round < 3) tournament.current_round = 3;
    }
  }

  // apply results to newly derived rounds, if any
  applyResults(round2, 2);
  applyResults(finalRound, 3);

  // persist any derived bracket updates
  localStorage.setItem("activeTournament", JSON.stringify(tournament));

  if (DEBUG_BRACKET) {
    console.log("[DebugBracket] renderBracket", {
      id: tournament._id,
      current_round: tournament.current_round,
    });
    const round1Winners = round1
      .map((m, i) => m.winner ?? getResult(1, i)?.winner)
      .filter(Boolean);
    const round2Winners = round2
      .map((m, i) => m.winner ?? getResult(2, i)?.winner)
      .filter(Boolean);
    const finalWinner = finalRound
      .map((m, i) => m.winner ?? getResult(3, i)?.winner)
      .filter(Boolean);
    const semifinalSlots = [
      round2[0]?.home_team,
      round2[0]?.away_team,
      round2[1]?.home_team,
      round2[1]?.away_team,
    ].filter(Boolean);
    const finalSlots = [
      finalRound[0]?.home_team,
      finalRound[0]?.away_team,
    ].filter(Boolean);
    console.log("[DebugBracket] winners", {
      round1: round1Winners,
      round2: round2Winners,
      final: finalWinner,
    });
    console.log("[DebugBracket] slots", {
      semifinals: semifinalSlots,
      final: finalSlots,
    });
  }

  // ✅ Shared bracket renderer (bracket.js) – same DOM for TCC and FCC
  if (typeof renderBracketShared === 'function') {
    renderBracketShared(bracket, { round1, round2, final: finalRound }, teamIdNameMap, {
      results,
      getLogo,
      isUserTeam,
      getTooltip: function (teamId, teamName) {
        const resolvedName = teamIdNameMap[String(teamId)] || teamName || '';
        return getTeamTooltipText(resolvedName);
      },
    });
  } else {
    console.warn('[TCC] renderBracketShared not found; bracket.js may not be loaded');
  }
  // ensure CTA buttons reflect latest bracket state
  updateCTA();
}

// Store roster data for sorting
let tournamentRosterDataForSorting = [];
let tournamentRosterSortColumn = 'RT';
let tournamentRosterSortDirection = 'desc';

// ✅ SS&S: Refactored to match Franchise renderTeam() pattern exactly
function renderRoster() {
  console.log('🔍 [DEBUG renderRoster] Starting renderRoster()');
  // Use tournamentRosterData if available (has merged stats), otherwise fall back to roster
  const data = tournamentRosterData || { players: roster || [] };
  console.log('🔍 [DEBUG renderRoster] Data source:', {
    usingTournamentRosterData: !!tournamentRosterData,
    hasData: !!data,
    playersCount: data.players?.length || 0,
    rosterLength: roster?.length || 0
  });
  
  const tbody = document.getElementById("roster-body");
  if (!tbody) {
    console.error("❌ [DEBUG renderRoster] roster-body element not found");
    return;
  }
  tbody.innerHTML = "";
  
  if (!data.players || data.players.length === 0) {
    console.warn("⚠️ [DEBUG renderRoster] No roster data to render");
    return;
  }
  
  // Map players to roster format (match Franchise pattern)
  let players = (data.players || []).map(p => {
    try {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      return {
        _id: p._id,
        name: fullName,
        jersey: p.jersey,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
        highestRT: best.rating ?? -Infinity,
        stats: p.stats || { season: {} } // ✅ SS&S: Preserve stats (matches Franchise)
      };
    } catch (error) {
      console.error('Error mapping player:', p, error);
      return null;
    }
  }).filter(p => p !== null);
  
  // Sort by RT (descending) by default
  players.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  
  // Store for sorting
  tournamentRosterDataForSorting = JSON.parse(JSON.stringify(players));
  
  players.forEach((p, index) => {
    const tr = document.createElement("tr");
    
    // Create player name as clickable link
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
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
      // Convert to 0-12 scale, except NG which stays as decimal
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.rt ?? '-');
    
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
  
  // Add click handlers to sortable headers
  const sortableHeaders = document.querySelectorAll('#roster-tab .roster-table thead th');
  sortableHeaders.forEach((header, index) => {
    // Remove existing listeners
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const columnNames = ['Name', 'POS', 'Year', 'Height', 'Weight', 'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT', 'RT'];
      const columnName = columnNames[index];
      
      // Toggle sort direction if clicking the same column
      if (tournamentRosterSortColumn === columnName) {
        tournamentRosterSortDirection = tournamentRosterSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        tournamentRosterSortColumn = columnName;
        tournamentRosterSortDirection = 'desc';
      }
      
      sortTournamentRoster(columnName, tournamentRosterSortDirection);
    });
  });
  
  // ✅ Phase 4.2: Roster stats rendering via shared RosterStatsRenderer
  if (typeof RosterStatsRenderer !== 'undefined') {
    RosterStatsRenderer.renderRosterStats(data.players || []);
  }
}

function sortTournamentRoster(columnName, direction) {
  const tbody = document.getElementById("roster-body");
  if (!tbody || !tournamentRosterDataForSorting.length) return;
  
  const columnMap = {
    'Name': 'name',
    'POS': 'pos',
    'Year': 'year',
    'Height': 'height',
    'Weight': 'weight',
    'SC': 'SC',
    'SH': 'SH',
    'ID': 'ID',
    'OD': 'OD',
    'PS': 'PS',
    'BH': 'BH',
    'RB': 'RB',
    'AG': 'AG',
    'ST': 'ST',
    'ND': 'ND',
    'IQ': 'IQ',
    'FT': 'FT',
    'RT': 'RT'
  };
  
  const dataKey = columnMap[columnName] || columnName;
  
  tournamentRosterDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (dataKey === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return direction === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (dataKey === 'RT') {
      val1 = a.highestRT ?? -Infinity;
      val2 = b.highestRT ?? -Infinity;
    } else if (dataKey === 'year') {
      const yearOrder = { 'FR': 1, 'SO': 2, 'JR': 3, 'SR': 4 };
      val1 = yearOrder[a.year] || 0;
      val2 = yearOrder[b.year] || 0;
    } else if (dataKey === 'height') {
      const parseHeight = (h) => {
        if (!h || h === '--') return 0;
        const match = h.match(/(\d+)'(\d+)"/);
        return match ? parseInt(match[1]) * 12 + parseInt(match[2]) : 0;
      };
      val1 = parseHeight(a.height);
      val2 = parseHeight(b.height);
    } else if (dataKey === 'weight') {
      val1 = parseInt(a.weight) || 0;
      val2 = parseInt(b.weight) || 0;
    } else {
      // Attribute columns
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      const rawValA = attrsA[`anchor_${dataKey}`] ?? attrsA[dataKey] ?? 0;
      const rawValB = attrsB[`anchor_${dataKey}`] ?? attrsB[dataKey] ?? 0;
      val1 = Math.floor(rawValA / 10);
      val2 = Math.floor(rawValB / 10);
    }
    
    if (direction === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  // Re-render the table
  tbody.innerHTML = "";
  tournamentRosterDataForSorting.forEach(p => {
    const tr = document.createElement("tr");
    
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
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
    
    ATTR_HEADERS.forEach(h => {
      const attrs = p.attributes || {};
      const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.highestRT !== -Infinity ? p.highestRT : '-');
    
    tbody.appendChild(tr);
  });
  
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

// ✅ SS&S: Removed old renderStats() and renderStatsTable() - now using renderRosterStats() pattern (matches Franchise)

function sortRosterStats(statKey) {
  // Map display stat names to data stat keys
  const statMap = {
    'name': 'name',
    'PTS': 'PTS',
    'FGM': 'FGM',
    'FGA': 'FGA',
    'FG%': 'FG%',
    '3PTM': '3PTM',
    '3PTA': '3PTA',
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
    'MIN': 'MIN',
    'TO': 'TO'
  };
  
  const dataKey = statMap[statKey] || statKey;
  
  // Sort players by the selected stat (descending order)
  tournamentPlayerStatsDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (dataKey === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return val2.localeCompare(val1); // Reverse for descending
    } else if (dataKey === 'FG%') {
      val1 = a.FGA > 0 ? (a.FGM || 0) / a.FGA : 0;
      val2 = b.FGA > 0 ? (b.FGM || 0) / b.FGA : 0;
    } else if (dataKey === '3PT%') {
      val1 = a["3PTA"] > 0 ? (a["3PTM"] || 0) / a["3PTA"] : 0;
      val2 = b["3PTA"] > 0 ? (b["3PTM"] || 0) / b["3PTA"] : 0;
    } else if (dataKey === 'FT%') {
      val1 = a.FTA > 0 ? (a.FTM || 0) / a.FTA : 0;
      val2 = b.FTA > 0 ? (b.FTM || 0) / b.FTA : 0;
    } else if (dataKey === 'TREB') {
      // Calculate TREB from DREB + OREB if not directly available
      val1 = a.TREB || (a.DREB || 0) + (a.OREB || 0);
      val2 = b.TREB || (b.DREB || 0) + (b.OREB || 0);
    } else {
      val1 = a[dataKey] || 0;
      val2 = b[dataKey] || 0;
    }
    
    return val2 - val1; // Descending order
  });
  
  // Re-render with sorted data
  renderStatsTable(tournamentPlayerStatsDataForSorting);
}

// Helper function to initialize team color cache
async function initializeTeamColorCache() {
  if (teamColorCache) return; // Already initialized
  
  try {
    const res = await fetch(API_CONFIG.buildUrl('/teams'));
    const teamData = await res.json();
    teamColorCache = {};
    teamMetaByNameCache = {};
    teamData.forEach(t => {
      teamColorCache[t.name] = t.primary_color;
      teamMetaByNameCache[t.name] = {
        mascot: t.mascot || '',
        primary_color: t.primary_color || null,
      };
    });
  } catch (err) {
    console.warn('Failed to load team colors:', err);
    teamColorCache = {};
    teamMetaByNameCache = {};
  }
}

// Helper function to get team primary color (synchronous, uses cache)
function getTeamPrimaryColor(teamName) {
  if (!teamName || !teamColorCache) return null;
  return teamColorCache[teamName] || null;
}

function renderLeaderboards() {
  const container = document.getElementById("leaderboards");
  container.innerHTML = "";
  // ✅ FIX: Use userTeamNameForLeaders (matches Franchise pattern)
  const primaryColor = getTeamPrimaryColor(userTeamNameForLeaders);
  
  leaderBoards.forEach(board => {
    const section = document.createElement("div");
    section.className = "leaderboard-section";
    const h3 = document.createElement("h3");
    h3.textContent = board.title;
    section.appendChild(h3);
    const div = document.createElement("div");
    div.className = "scroll-x";
    const table = document.createElement("table");
    table.className = "leaders-table";
    table.innerHTML = `<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>${board.valueHeader || 'Value'}</th></tr></thead>`;
    const body = document.createElement("tbody");
    const rows = (leaderData[board.key] || []);
    for (let i = 0; i < 10; i++) {
      const entry = rows[i];
      const tr = document.createElement("tr");
      if (entry) {
        // ✅ FIX: Use userTeamNameForLeaders (matches Franchise pattern)
        // Compare with team name (leaderboard uses team names, not ObjectIds)
        const isUserTeam = userTeamNameForLeaders && entry.team_name === userTeamNameForLeaders;
        
        // Create cells individually to apply styling
        const rankCell = document.createElement('td');
        rankCell.textContent = entry.rank || (i + 1);
        const playerCell = document.createElement('td');
        playerCell.textContent = `${entry.first_name} ${entry.last_name}`;
        const teamCell = document.createElement('td');
        teamCell.textContent = entry.team_name;
        const valueCell = document.createElement('td');
        valueCell.textContent = entry.value;
        
        // ✅ FIX: Apply bold and color to ALL columns if user team player (matches FCC format)
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
      } else {
        tr.innerHTML = `<td>${i + 1}</td><td>—</td><td>—</td><td>—</td>`;
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

// Store teams data for sorting (tournament)
let tournamentTeamsDataForSorting = [];

async function refreshLeaders() {
  if (!tournament || !tournament._id) return;
  try {
    const res = await fetch(`${API_CONFIG.buildUrl('/tournament/leaders')}?tournament_id=${encodeURIComponent(tournament._id)}`, { headers: API_CONFIG.getAuthHeaders() });
    leaderData = await res.json();
  } catch (err) {
    console.error("Failed to load leaders", err);
    leaderData = {};
  }
  renderLeaderboards();
  await refreshTeamStats();
}

async function refreshTeamStats() {
  console.log('🔍 [DEBUG refreshTeamStats] Starting refreshTeamStats()');
  if (!tournament || !tournament._id) {
    console.warn('⚠️ [DEBUG refreshTeamStats] Tournament not loaded');
    return;
  }
  try {
    const url = `${API_CONFIG.buildUrl('/tournament/team-stats')}?tournament_id=${encodeURIComponent(tournament._id)}`;
    console.log('🔍 [DEBUG refreshTeamStats] Fetching team stats from:', url);
    const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
    const data = await res.json();
    console.log('🔍 [DEBUG refreshTeamStats] Team stats API response:', {
      hasData: !!data,
      teamsCount: data?.teams?.length || 0,
      teams: data?.teams?.map(t => t.team) || []
    });
    renderTeamStats(data);
    // ✅ SS&S: Removed redundant roster refresh - already handled by handleTournamentUpdate()
  } catch (err) {
    console.error("❌ [DEBUG refreshTeamStats] Failed to load team stats", err);
  }
}

function renderTeamStats(data) {
  console.log('🔍 [DEBUG renderTeamStats] Starting renderTeamStats()');
  console.log('🔍 [DEBUG renderTeamStats] Data received:', {
    hasData: !!data,
    teamsCount: data?.teams?.length || 0,
    teams: data?.teams?.map(t => ({ team: t.team, team_id: t.team_id, hasStats: !!t.stats })) || []
  });

  if (!data) {
    console.warn('⚠️ [DEBUG renderTeamStats] No data provided');
    return;
  }
  tournamentTeamsDataForSorting = JSON.parse(JSON.stringify(data.teams || [])); // Deep copy for sorting

  for (const k of Object.keys(teamIdNameMap)) delete teamIdNameMap[k];
  (data.teams || []).forEach(t => {
    if (t.team_id != null && t.team != null) {
      teamIdNameMap[String(t.team_id)] = t.team;
    }
  });
  if (Object.keys(teamIdNameMap).length) {
    renderBracket();
    renderSchedule();
  }

  console.log('🔍 [DEBUG renderTeamStats] Calling TeamStatsTable.renderTeamStatsTable() with', tournamentTeamsDataForSorting.length, 'teams');
  TeamStatsTable.renderTeamStatsTable(tournamentTeamsDataForSorting);
  console.log('✅ [DEBUG renderTeamStats] TeamStatsTable.renderTeamStatsTable() called');
  
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
      TeamStatsTable.sortTeamStats(stat, tournamentTeamsDataForSorting);
    });
  });
}

// ✅ SS&S: Team stats table rendering now uses shared module (teamStatsTable.js)
// Removed ~160 lines of duplicate code

window.refreshLeaders = refreshLeaders;

function renderSchedule() {
  if (!tournament) return;
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';

  const round1 = tournament.bracket?.round1 || [];
  const round2 = tournament.bracket?.round2 || [];
  const finalRound = tournament.bracket?.final || [];
  const results = tournament.results || [];

  // Build seed map from round1
  const seedMap = {};
  if (round1.length === 4) {
    seedMap[round1[0].home_team] = 1;
    seedMap[round1[0].away_team] = 8;
    seedMap[round1[1].home_team] = 4;
    seedMap[round1[1].away_team] = 5;
    seedMap[round1[2].home_team] = 2;
    seedMap[round1[2].away_team] = 7;
    seedMap[round1[3].home_team] = 3;
    seedMap[round1[3].away_team] = 6;
  }

  function getResult(round, index) {
    return results.find(r => r.round === round && r.match_index === index) || null;
  }

  function teamName(id) {
    return (id != null && teamIdNameMap[String(id)]) || id;
  }

  const returnUrl = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
  const createTeamLink = (displayName, teamId, seed) => {
    const link = document.createElement('a');
    const q = new URLSearchParams({ mode: 'tournament', tournament_id: tournament._id, return_tab: 'schedule-tab', return_url: returnUrl });
    if (teamId) q.set('team_id', teamId);
    q.set('team_name', displayName);
    link.href = `/team-roster-view.html?${q.toString()}`;
    link.textContent = seed ? `Team ${seed} ${displayName}` : displayName;
    link.style.color = '#4a90e2';
    link.style.textDecoration = 'none';
    link.style.cursor = 'pointer';
    link.addEventListener('mouseenter', () => { link.style.textDecoration = 'underline'; });
    link.addEventListener('mouseleave', () => { link.style.textDecoration = 'none'; });
    return link;
  };

  // First Round
  const firstRoundDiv = document.createElement('div');
  firstRoundDiv.className = 'schedule-round';
  const firstRoundH3 = document.createElement('h3');
  firstRoundH3.textContent = 'First Round';
  firstRoundDiv.appendChild(firstRoundH3);

  round1.forEach((match, index) => {
    const res = getResult(1, index);
    const homeName = teamName(match.home_team);
    const awayName = teamName(match.away_team);
    const homeScore = res?.score?.[homeName] ?? match.score?.[homeName];
    const awayScore = res?.score?.[awayName] ?? match.score?.[awayName];
    const winner = res?.winner ?? match.winner ?? null;

    const gameDiv = document.createElement('div');
    gameDiv.className = 'schedule-game';
    const homeSeed = seedMap[match.home_team] || '';
    const awaySeed = seedMap[match.away_team] || '';

    const awayLink = createTeamLink(awayName, match.away_team, awaySeed);
    const homeLink = createTeamLink(homeName, match.home_team, homeSeed);
    const atText = document.createTextNode(' @ ');

    if (homeScore !== undefined && awayScore !== undefined) {
      const awayScoreText = document.createTextNode(` (${awayScore})`);
      const homeScoreText = document.createTextNode(` (${homeScore})`);
      const awayContainer = document.createElement('span');
      if (awayScore > homeScore) awayContainer.style.fontWeight = 'bold';
      awayContainer.appendChild(awayLink);
      awayContainer.appendChild(awayScoreText);
      const homeContainer = document.createElement('span');
      if (homeScore > awayScore) homeContainer.style.fontWeight = 'bold';
      homeContainer.appendChild(homeLink);
      homeContainer.appendChild(homeScoreText);
      gameDiv.appendChild(awayContainer);
      gameDiv.appendChild(atText);
      gameDiv.appendChild(homeContainer);
    } else {
      gameDiv.appendChild(awayLink);
      gameDiv.appendChild(atText);
      gameDiv.appendChild(homeLink);
    }

    const gameId = res?.game_id || match.game_id;
    if (gameId && homeScore !== undefined && awayScore !== undefined) {
      const boxScoreLink = document.createElement('a');
      const boxScoreParams = new URLSearchParams();
      boxScoreParams.set('mode', 'tournament');
      boxScoreParams.set('tournament_id', tournament._id);
      boxScoreParams.set('game_id', gameId);
      if (homeName) boxScoreParams.set('home', homeName);
      if (awayName) boxScoreParams.set('away', awayName);
      boxScoreLink.href = `/box-score.html?${boxScoreParams.toString()}`;
      boxScoreLink.textContent = ' [Box Score]';
      boxScoreLink.className = 'box-score-link';
      boxScoreLink.style.color = '#4a90e2';
      boxScoreLink.style.textDecoration = 'none';
      boxScoreLink.style.marginLeft = '8px';
      boxScoreLink.style.fontSize = 'calc(1em - 2px)';
      gameDiv.appendChild(boxScoreLink);
    }

    firstRoundDiv.appendChild(gameDiv);
  });
  container.appendChild(firstRoundDiv);

  // Semifinals
  const semiDiv = document.createElement('div');
  semiDiv.className = 'schedule-round';
  const semiH3 = document.createElement('h3');
  semiH3.textContent = 'Semifinals';
  semiDiv.appendChild(semiH3);

  for (let i = 0; i < 2; i++) {
    const gameDiv = document.createElement('div');
    gameDiv.className = 'schedule-game';

    if (round2[i]) {
      const match = round2[i];
      const res = getResult(2, i);
      const homeName = teamName(match.home_team);
      const awayName = teamName(match.away_team);
      const homeScore = res?.score?.[homeName] ?? match.score?.[homeName];
      const awayScore = res?.score?.[awayName] ?? match.score?.[awayName];
      const winner = res?.winner ?? match.winner ?? null;

      const awayLink = createTeamLink(awayName, match.away_team, '');
      const homeLink = createTeamLink(homeName, match.home_team, '');
      const atText = document.createTextNode(' @ ');

      if (homeScore !== undefined && awayScore !== undefined) {
        const awayScoreText = document.createTextNode(` (${awayScore})`);
        const homeScoreText = document.createTextNode(` (${homeScore})`);
        const awayContainer = document.createElement('span');
        if (awayScore > homeScore) awayContainer.style.fontWeight = 'bold';
        awayContainer.appendChild(awayLink);
        awayContainer.appendChild(awayScoreText);
        const homeContainer = document.createElement('span');
        if (homeScore > awayScore) homeContainer.style.fontWeight = 'bold';
        homeContainer.appendChild(homeLink);
        homeContainer.appendChild(homeScoreText);
        gameDiv.appendChild(awayContainer);
        gameDiv.appendChild(atText);
        gameDiv.appendChild(homeContainer);
      } else {
        gameDiv.appendChild(awayLink);
        gameDiv.appendChild(atText);
        gameDiv.appendChild(homeLink);
      }

      const gameId = res?.game_id || match.game_id;
      if (gameId && homeScore !== undefined && awayScore !== undefined) {
        const boxScoreLink = document.createElement('a');
        const boxScoreParams = new URLSearchParams();
        boxScoreParams.set('mode', 'tournament');
        boxScoreParams.set('tournament_id', tournament._id);
        boxScoreParams.set('game_id', gameId);
        if (homeName) boxScoreParams.set('home', homeName);
        if (awayName) boxScoreParams.set('away', awayName);
        boxScoreLink.href = `/box-score.html?${boxScoreParams.toString()}`;
        boxScoreLink.textContent = ' [Box Score]';
        boxScoreLink.className = 'box-score-link';
        boxScoreLink.style.color = '#4a90e2';
        boxScoreLink.style.textDecoration = 'none';
        boxScoreLink.style.marginLeft = '8px';
        boxScoreLink.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(boxScoreLink);
      }
    } else {
      gameDiv.innerHTML = 'TBD @ TBD';
    }

    semiDiv.appendChild(gameDiv);
  }
  container.appendChild(semiDiv);

  // Championship
  const champDiv = document.createElement('div');
  champDiv.className = 'schedule-round';
  const champH3 = document.createElement('h3');
  champH3.textContent = 'Championship';
  champDiv.appendChild(champH3);

  const champGameDiv = document.createElement('div');
  champGameDiv.className = 'schedule-game';
  
  if (finalRound[0]) {
    const match = finalRound[0];
    const res = getResult(3, 0);
    const homeName = teamName(match.home_team);
    const awayName = teamName(match.away_team);
    const homeScore = res?.score?.[homeName] ?? match.score?.[homeName];
    const awayScore = res?.score?.[awayName] ?? match.score?.[awayName];
    const winner = res?.winner ?? match.winner ?? null;

    const awayLink = createTeamLink(awayName, match.away_team, '');
    const homeLink = createTeamLink(homeName, match.home_team, '');
    const atText = document.createTextNode(' @ ');

    if (homeScore !== undefined && awayScore !== undefined) {
      const awayScoreText = document.createTextNode(` (${awayScore})`);
      const homeScoreText = document.createTextNode(` (${homeScore})`);
      const awayContainer = document.createElement('span');
      if (awayScore > homeScore) awayContainer.style.fontWeight = 'bold';
      awayContainer.appendChild(awayLink);
      awayContainer.appendChild(awayScoreText);
      const homeContainer = document.createElement('span');
      if (homeScore > awayScore) homeContainer.style.fontWeight = 'bold';
      homeContainer.appendChild(homeLink);
      homeContainer.appendChild(homeScoreText);
      champGameDiv.appendChild(awayContainer);
      champGameDiv.appendChild(atText);
      champGameDiv.appendChild(homeContainer);
    } else {
      champGameDiv.appendChild(awayLink);
      champGameDiv.appendChild(atText);
      champGameDiv.appendChild(homeLink);
    }

    const gameId = res?.game_id || match.game_id;
    if (gameId && homeScore !== undefined && awayScore !== undefined) {
      const boxScoreLink = document.createElement('a');
      const boxScoreParams = new URLSearchParams();
      boxScoreParams.set('mode', 'tournament');
      boxScoreParams.set('tournament_id', tournament._id);
      boxScoreParams.set('game_id', gameId);
      if (homeName) boxScoreParams.set('home', homeName);
      if (awayName) boxScoreParams.set('away', awayName);
      boxScoreLink.href = `/box-score.html?${boxScoreParams.toString()}`;
      boxScoreLink.textContent = ' [Box Score]';
      boxScoreLink.className = 'box-score-link';
      boxScoreLink.style.color = '#4a90e2';
      boxScoreLink.style.textDecoration = 'none';
      boxScoreLink.style.marginLeft = '8px';
      boxScoreLink.style.fontSize = 'calc(1em - 2px)';
      champGameDiv.appendChild(boxScoreLink);
    }
  } else {
    champGameDiv.innerHTML = 'TBD @ TBD';
  }
  
  champDiv.appendChild(champGameDiv);
  container.appendChild(champDiv);
}

// ✅ MIGRATION (Task 6.1): Update CTA button using structured data (aligns with Franchise pattern)
function updateCTA(data) {
  const playBtn = document.getElementById('play-now');
  const simBtn = document.getElementById('sim-remaining');
  const exitBtn = document.getElementById('exit-tournament');
  const container = document.querySelector('.play-now-container');
  
  if (!container || !playBtn || !simBtn || !exitBtn) return;
  
  // If data is provided, use it (from command center endpoint)
  // Otherwise, fall back to reading from tournament object (backward compatibility)
  const completed = data ? data.completed : (tournament?.completed || false);
  const currentRound = data ? data.current_round : (tournament?.current_round || 1);
  
  if (completed) {
    playBtn.style.display = 'none';
    simBtn.style.display = 'none';
    simBtn.disabled = true;
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';

  // Check if user is eliminated (need tournament object for bracket data)
  if (tournament) {
    const roundKey = currentRound === 3 ? 'final' : `round${currentRound}`;
    const matchups = tournament.bracket?.[roundKey] || [];
    const userMatch = matchups.find(m =>
      String(m.home_team) === String(userTeamId) || String(m.away_team) === String(userTeamId)
    );

    const eliminated = !userMatch || !!userMatch.winner;
    if (eliminated) {
      playBtn.style.display = 'none';
      simBtn.style.display = 'inline-block';
      simBtn.disabled = false;
      return;
    }
  }

  // ✅ REMOVED: Training is not used in Tournament mode - users go directly to gameplay
  // Always show "Play Next Game" button
  playBtn.textContent = 'Play Next Game';
  playBtn.style.display = 'inline-block';
  simBtn.style.display = 'none';
  simBtn.disabled = true;
}

// ✅ MIGRATION (Task 6.1): Populate top bar using structured data (aligns with Franchise pattern)
function populateTop(data) {
  if (!data) return;

  // Update team logo
  if (data.team) {
    const formattedTeam = formatTeamName(data.team);
    const logoSrc = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(data.team, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
    const logoEl = document.getElementById('user-team-logo');
    if (logoEl) {
      logoEl.src = logoSrc;
    }
    
    // Update coach images
    const abbr = teamMap[formattedTeam];
    const sammyEl = document.getElementById('coach-sammy');
    const dukeEl = document.getElementById('coach-duke');
    if (abbr) {
      if (sammyEl) sammyEl.src = `/images/coaches/${abbr}/Sammy-${abbr}.png`;
      if (dukeEl) dukeEl.src = `/images/coaches/${abbr}/Duke-${abbr}.png`;
    } else {
      if (sammyEl) sammyEl.removeAttribute('src');
      if (dukeEl) dukeEl.removeAttribute('src');
    }
  }
  
  // Update chemistry bar with proportional fill
  const chemistryBar = document.querySelector('.chemistry-bar');
  if (chemistryBar) {
    const chemistryValue = data.team_chemistry || 0;
    const fillElement = chemistryBar.querySelector('.chemistry-bar-fill');
    const textElement = chemistryBar.querySelector('.chemistry-bar-text');
    
    if (fillElement) {
      const percentage = (chemistryValue / 25) * 100;
      fillElement.style.width = `${percentage}%`;
    }
    
    if (textElement) {
      textElement.textContent = `${chemistryValue} / 25`;
    }
  }
  
  // Update team stats (align with Franchise structure)
  const statsContainer = document.querySelector('#top-center .team-stats');
  if (statsContainer) {
    const offenseEl = statsContainer.querySelector('div:nth-child(1)');
    const athleticismEl = statsContainer.querySelector('div:nth-child(2)');
    const prestigeEl = statsContainer.querySelector('div:nth-child(3)');
    const defenseEl = statsContainer.querySelector('div:nth-child(4)');
    const intangiblesEl = statsContainer.querySelector('div:nth-child(5)');
    const seedEl = statsContainer.querySelector('div:nth-child(6)');
    
    if (offenseEl) offenseEl.textContent = `Offense: ${data.offense || '--'}`;
    if (athleticismEl) athleticismEl.textContent = `Athleticism: ${data.athleticism || '--'}`;
    if (prestigeEl) prestigeEl.textContent = `Prestige: ${data.prestige || '--'}`;
    if (defenseEl) defenseEl.textContent = `Defense: ${data.defense || '--'}`;
    if (intangiblesEl) intangiblesEl.textContent = `Intangibles: ${data.intangibles || '--'}`;
    // Tournament mode shows seed instead of rank
    if (seedEl) {
      const seed = data.seed || tournament?.seed || '--';
      seedEl.textContent = `Seed: ${seed}`;
    }
  }
}

// Keep updateTeamChemistry for backward compatibility
function updateTeamChemistry() {
  if (!tournament) return;
  
  const chemistryBar = document.querySelector('.chemistry-bar');
  if (chemistryBar) {
    const chemistry = tournament.team_chemistry || 0;
    const fillElement = chemistryBar.querySelector('.chemistry-bar-fill');
    const textElement = chemistryBar.querySelector('.chemistry-bar-text');
    
    if (fillElement) {
      const percentage = (chemistry / 25) * 100;
      fillElement.style.width = `${percentage}%`;
    }
    
    if (textElement) {
      textElement.textContent = `${chemistry} / 25`;
    }
  }
  
  // Update other team stats if available
  const offenseEl = document.querySelector('#top-center .team-stats > div:nth-child(1)');
  const athleticismEl = document.querySelector('#top-center .team-stats > div:nth-child(2)');
  const defenseEl = document.querySelector('#top-center .team-stats > div:nth-child(3)');
  
  if (offenseEl && tournament.offense) {
    offenseEl.textContent = `Offense: ${tournament.offense}`;
  }
  if (athleticismEl && tournament.athleticism) {
    athleticismEl.textContent = `Athleticism: ${tournament.athleticism}`;
  }
  if (defenseEl && tournament.defense) {
    defenseEl.textContent = `Defense: ${tournament.defense}`;
  }
}

function initTopAssets(teamName) {
  const logoEl = document.getElementById("user-team-logo");
  if (logoEl) {
    logoEl.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(teamName || userTeamId || "", 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
  }
  const abbr = teamMap[formattedName] || "";
  const sammyEl = document.getElementById("coach-sammy");
  const dukeEl = document.getElementById("coach-duke");
  if (abbr) {
    if (sammyEl) sammyEl.src = `/images/coaches/${abbr}/Sammy-${abbr}.png`;
    if (dukeEl) dukeEl.src = `/images/coaches/${abbr}/Duke-${abbr}.png`;
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (dukeEl) dukeEl.removeAttribute('src');
  }
}

// ✅ MIGRATION (Task 6.1): Load command center data using structured endpoint (aligns with Franchise)
async function loadCommandCenterData() {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const urlTournamentId = urlParams.get('tournament_id');
    
    let tournamentId = urlTournamentId;
    if (!tournamentId && tournament && tournament._id) {
      tournamentId = tournament._id;
    }
    
    if (!tournamentId) {
      throw new Error("No tournament_id found");
    }
    
    // ✅ MIGRATION: Use command-center/data endpoint (aligns with Franchise pattern)
    const url = `${API_CONFIG.buildUrl('/tournament/command-center/data')}?tournament_id=${encodeURIComponent(tournamentId)}&_=${Date.now()}`;
    const res = await fetch(url, { cache: "no-store", headers: API_CONFIG.getAuthHeaders() });
    if (res.status === 401 || res.status === 403) {
      if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
        AccessDenied.checkAccessDenied(res);
      }
      return null;
    }
    if (!res.ok) {
      throw new Error(`Failed to load command center data: ${res.status} ${res.statusText}`);
    }
    const commandCenterData = await res.json();
    
    // Also load full tournament document for bracket and other detailed data
    const tournamentRes = await fetch(`${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${encodeURIComponent(tournamentId)}&_=${Date.now()}`, { cache: "no-store", headers: API_CONFIG.getAuthHeaders() });
    if (tournamentRes.ok) {
      tournament = await tournamentRes.json();
      localStorage.setItem("activeTournament", JSON.stringify(tournament));
    }
    
    // ✅ SS&S: Resolve and store team ObjectId and name for consistent navigation
    if (commandCenterData) {
      // Store team name for bracket comparisons
      if (commandCenterData.team) {
        userTeamName = commandCenterData.team; // Team name (e.g., "Morristown")
      }
      
      // Always use ObjectId for navigation anchor (Task 3.2: Navigation Anchor Set Consistency)
      if (commandCenterData.team_id) {
        userTeamId = commandCenterData.team_id;
        localStorage.setItem("userTeamId", userTeamId);
      }
    }
    
    return commandCenterData;
  } catch (err) {
    console.error("❌ Failed to load command center data", err);
    throw err;
  }
}

// Keep loadTournament for backward compatibility (used by refreshTeamStats, etc.)
async function loadTournament() {
  try {
    let url;
    let params;
    // Priority 1: tournament_id from URL (when navigating from training report, etc.)
    const urlParams = new URLSearchParams(window.location.search);
    const urlTournamentId = urlParams.get('tournament_id');
    
    if (urlTournamentId) {
      params = new URLSearchParams({ tournament_id: urlTournamentId });
      url = `${API_CONFIG.buildUrl('/tournament/state')}?${params.toString()}`;
    } else if (tournament && tournament._id) {
      // Priority 2: tournament from localStorage
      params = new URLSearchParams({ tournament_id: tournament._id });
      url = `${API_CONFIG.buildUrl('/tournament/state')}?${params.toString()}`;
    } else {
      // Priority 3: fallback to active tournament by user_team_id
      params = new URLSearchParams({ user_team_id: userTeamId });
      url = `${API_CONFIG.buildUrl('/tournament/active')}?${params.toString()}`;
    }
    
    // Add cache buster using & (not ?) since URL already has query params
    const res = await fetch(`${url}&_=${Date.now()}`, { cache: "no-store", headers: API_CONFIG.getAuthHeaders() });
    if (!res.ok) {
      throw new Error(`Failed to load tournament: ${res.status} ${res.statusText}`);
    }
    tournament = await res.json();
    localStorage.setItem("activeTournament", JSON.stringify(tournament));
    
    // ✅ SS&S: Resolve and store team ObjectId and name for consistent navigation
    // Navigation anchor set requires team_id to be ObjectId format (not team name)
    // But bracket comparisons need team name, so we store both
    if (tournament) {
      // Store team name for bracket comparisons
      if (tournament.user_team_id) {
        userTeamName = tournament.user_team_id; // Team name (e.g., "Morristown")
      }
      
      // Prefer ObjectId if available (from updated endpoint)
      if (tournament.user_team_object_id) {
        // Always use ObjectId for navigation anchor (Task 3.2: Navigation Anchor Set Consistency)
        userTeamId = tournament.user_team_object_id;
        localStorage.setItem("userTeamId", userTeamId);
      } else if (tournament.user_team_id && !userTeamId) {
        // Fallback: If ObjectId not available, store team name temporarily
        // Backend endpoints will resolve this, but we should prefer ObjectId
        // Note: This is backward compatibility - new tournaments should always have user_team_object_id
        userTeamId = tournament.user_team_id;
        localStorage.setItem("userTeamId", userTeamId);
      }
    }
    
    console.log("✅ Tournament loaded:", tournament._id);
  } catch (err) {
    console.error("❌ Failed to load tournament", err);
    // Don't throw - allow page to continue loading even if tournament fails
  }
}

async function loadRoster() {
  try {
    console.log('🔍 [DEBUG loadRoster] Starting loadRoster()');
    console.log('🔍 [DEBUG loadRoster] userTeamId:', userTeamId);
    console.log('🔍 [DEBUG loadRoster] tournament:', tournament?._id);
    
    if (!userTeamId) {
      console.error('❌ [DEBUG loadRoster] No userTeamId found - cannot load roster');
      return;
    }
    // Ensure tournament is loaded
    if (!tournament || !tournament._id) {
      console.error('❌ [DEBUG loadRoster] Tournament not loaded - cannot load roster');
      return;
    }
    // ✅ SS&S: Use team_id instead of team_name for roster endpoint
    // Get team_id from tournament document or userTeamId (which is set from commandCenterData in initializeTournament)
    let teamIdForRoster = null;
    if (tournament && tournament.user_team_object_id) {
      teamIdForRoster = tournament.user_team_object_id;
    } else if (userTeamId) {
      // userTeamId is already set from commandCenterData in initializeTournament()
      teamIdForRoster = userTeamId;
    }
    
    // Fallback to team_name for backward compatibility
    if (!teamIdForRoster && userTeamName) {
      teamIdForRoster = userTeamName;
    }
    
    if (!teamIdForRoster) {
      console.error('❌ [DEBUG loadRoster] No team_id or team_name found - cannot load roster');
      return;
    }
    
    let data = null;
    // ✅ SS&S: Pass team_id as query parameter (preferred), fallback to path param for backward compatibility
    let url = `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(teamIdForRoster)}`)}?team_id=${encodeURIComponent(teamIdForRoster)}&tournament_id=${encodeURIComponent(tournament._id)}`;
    console.log('🔍 [DEBUG loadRoster] Fetching roster from:', url, '(using team_id:', teamIdForRoster, ')');
    let res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
    let dataLoaded = false; // Track if data was loaded from retry
    
    // ✅ FIX: Handle 404 errors - stale userTeamId from localStorage
    if (!res.ok && res.status === 404) {
      console.error('❌ [DEBUG loadRoster] Roster endpoint returned 404 - userTeamId may be stale:', userTeamId);
      console.error('   Attempting to reload userTeamId from command center data or tournament document...');
      
      // Try to reload userTeamId from command center data
      try {
        const commandCenterRes = await fetch(`${API_CONFIG.buildUrl('/tournament/command-center/data')}?tournament_id=${encodeURIComponent(tournament._id)}&_=${Date.now()}`, { cache: "no-store", headers: API_CONFIG.getAuthHeaders() });
        if (commandCenterRes.ok) {
          const commandCenterData = await commandCenterRes.json();
          if (commandCenterData && commandCenterData.team_id) {
            console.log('✅ [DEBUG loadRoster] Reloaded userTeamId from command center data:', commandCenterData.team_id);
            userTeamId = commandCenterData.team_id;
            localStorage.setItem("userTeamId", userTeamId);
            
            // ✅ SS&S: Retry with team_id (preferred) or team_name (fallback)
            if (commandCenterData.team) {
              userTeamName = commandCenterData.team;
            }
            // Use team_id if available, otherwise fallback to team_name
            const retryTeamId = commandCenterData.team_id || userTeamName;
            url = `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(retryTeamId)}`)}?team_id=${encodeURIComponent(retryTeamId)}&tournament_id=${encodeURIComponent(tournament._id)}`;
            res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
            if (res.ok) {
              data = await res.json();
              dataLoaded = true; // Mark that data was loaded from retry
              console.log('✅ [DEBUG loadRoster] Retry successful with corrected userTeamId');
            } else {
              throw new Error(`Retry failed: ${res.status} ${res.statusText}`);
            }
          } else {
            throw new Error('commandCenterData.team_id not found');
          }
        } else {
          throw new Error(`Failed to load command center data: ${commandCenterRes.status}`);
        }
      } catch (error) {
        console.error('❌ [DEBUG loadRoster] Failed to reload userTeamId from command center:', error);
        console.error('   Falling back to tournament document...');
        
        // Fallback: Try to get userTeamId from tournament document
        if (tournament && tournament.user_team_object_id) {
          userTeamId = tournament.user_team_object_id;
          localStorage.setItem("userTeamId", userTeamId);
          console.log('✅ [DEBUG loadRoster] Using userTeamId from tournament document:', userTeamId);
          
          // ✅ SS&S: Retry with ObjectId (backend accepts ObjectId, team_id string, or team_name)
          const retryTeamId = tournament.user_team_object_id || tournament.user_team_id || userTeamName;
          url = `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(retryTeamId)}`)}?team_id=${encodeURIComponent(retryTeamId)}&tournament_id=${encodeURIComponent(tournament._id)}`;
          res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
          if (res.ok) {
            data = await res.json();
            dataLoaded = true; // Mark that data was loaded from retry
            console.log('✅ [DEBUG loadRoster] Retry successful with tournament document userTeamId');
          } else {
            console.error('❌ [DEBUG loadRoster] All retry attempts failed - cannot load roster');
            return;
          }
        } else {
          console.error('❌ [DEBUG loadRoster] Cannot recover - no valid userTeamId found');
          return;
        }
      }
    } else if (!res.ok) {
      console.error('❌ [DEBUG loadRoster] Roster endpoint error:', res.status, res.statusText);
      return;
    } else if (!dataLoaded) {
      // Only load data if it wasn't already loaded from a retry
      data = await res.json();
    }
    
    // Process roster data (common for both initial fetch and retry)
    if (!data) {
      console.error('❌ [DEBUG loadRoster] No data loaded - cannot process roster');
      return;
    }
    
    console.log('🔍 [DEBUG loadRoster] Roster API response:', {
      playersCount: data.players?.length || 0,
      hasPlayers: !!data.players,
      firstPlayer: data.players?.[0] ? { _id: data.players[0]._id, name: data.players[0].name || `${data.players[0].first_name} ${data.players[0].last_name}` } : null
    });
    
    // ✅ SS&S: Load tournament document and merge stats (match Franchise pattern exactly)
    let tournamentDoc = tournament;
    try {
      const tournamentStateUrl = `${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${encodeURIComponent(tournament._id)}`;
      console.log('🔍 [DEBUG loadRoster] Fetching tournament state from:', tournamentStateUrl);
      const tournamentStateRes = await fetch(tournamentStateUrl, { headers: API_CONFIG.getAuthHeaders() });
      if (tournamentStateRes.ok) {
        tournamentDoc = await tournamentStateRes.json();
        console.log('🔍 [DEBUG loadRoster] Tournament state loaded:', {
          hasPlayers: !!tournamentDoc.players,
          playersCount: tournamentDoc.players ? Object.keys(tournamentDoc.players).length : 0,
          samplePlayerId: tournamentDoc.players ? Object.keys(tournamentDoc.players)[0] : null,
          samplePlayerStats: tournamentDoc.players ? (() => {
            const firstId = Object.keys(tournamentDoc.players)[0];
            return firstId ? tournamentDoc.players[firstId] : null;
          })() : null
        });
      } else {
        console.warn('⚠️ [DEBUG loadRoster] Tournament state response not OK:', tournamentStateRes.status);
      }
    } catch (error) {
      console.warn('⚠️ [DEBUG loadRoster] Could not reload tournament document, using cached:', error);
    }
    
    // ✅ Phase 4.1: Merge stats via shared RosterLoader
    if (typeof RosterLoader !== 'undefined' && tournamentDoc && data.players) {
      const merged = RosterLoader.mergeRosterWithStateDoc(data, tournamentDoc);
      data.players = merged.players;
    }

    // ✅ SS&S: Store roster data with merged stats (matches Franchise pattern)
    tournamentRosterData = data;
    console.log('🔍 [DEBUG loadRoster] tournamentRosterData stored:', {
      hasData: !!tournamentRosterData,
      playersCount: tournamentRosterData?.players?.length || 0,
      firstPlayerHasStats: !!(tournamentRosterData?.players?.[0]?.stats?.season)
    });
    
    // Update roster array with merged stats
    roster = (data.players || []).map(p => {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      return {
        _id: p._id,
        name: fullName,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
        stats: p.stats || { season: {} } // ✅ SS&S: Include stats in roster data
      };
    });
    
    console.log('✅ [DEBUG loadRoster] Tournament roster loaded:', {
      rosterLength: roster.length,
      firstPlayer: roster[0] ? {
        _id: roster[0]._id,
        name: roster[0].name,
        hasStats: !!roster[0].stats,
        hasSeason: !!(roster[0].stats?.season),
        sampleStats: roster[0].stats?.season ? Object.keys(roster[0].stats.season).slice(0, 5) : []
      } : null
    });
  } catch (err) {
    console.error("❌ [DEBUG loadRoster] Failed to load roster", err);
  }
}

// ✅ SS&S: Removed duplicate refreshTeamStats() - using the one at line 737 that calls renderTeamStats()
// This function was overriding the correct one

function handleTournamentUpdate(doc) {
  if (DEBUG_BRACKET)
    console.log("[DebugBracket] handleTournamentUpdate", {
      id: doc?._id,
      current_round: doc?.current_round,
    });
  tournament = doc;
  localStorage.setItem("activeTournament", JSON.stringify(doc));
  updateTeamChemistry();
  renderBracket();
  renderSchedule();
  // ✅ SS&S: Reload roster and stats to ensure player stats populate after game completion (matches Franchise pattern)
  loadRoster().then(() => {
    renderRoster(); // renderRoster() now calls renderRosterStats() internally (matches Franchise)
  });
  // ✅ FIX: Reload team data to refresh player stats on Team tab
  loadTeamData();
  updateCTA();
}

window.handleTournamentUpdate = handleTournamentUpdate;

async function initializeTournament() {
  console.log('🔍 [TOURNAMENT INIT] initializeTournament() called, readyState:', document.readyState);

  try {
  // ✅ ALPHA: Initialize alpha banner (shows badge if IS_ALPHA=true)
  if (typeof AlphaBanner !== 'undefined') {
    await AlphaBanner.init();
  }

  // ✅ MIGRATION (Task 6.1): Use command center data endpoint (aligns with Franchise pattern)
  let commandCenterData = null;
  try {
    commandCenterData = await loadCommandCenterData();
    if (commandCenterData === null) return; // Access denied - redirect already triggered; finally will hide overlay
  } catch (err) {
    console.error("❌ Failed to load command center data", err);
    // Fallback to old method for backward compatibility
    await loadTournament();
  }

  // Ensure tournament loaded successfully before proceeding
  if (!tournament || !tournament._id) {
    console.error("❌ Tournament failed to load - cannot initialize page");
    // Show error message to user
    const container = document.getElementById("tournament-container");
    if (container) {
      container.innerHTML = "<div style='padding: 20px; text-align: center;'><h2>Failed to load tournament</h2><p>Please refresh the page or return to the tournament selection.</p></div>";
    }
    return;
  }
  
  // ✅ MIGRATION: Use command center data to populate top bar and resolve team IDs
  if (commandCenterData) {
    // ✅ FIX: Always prioritize commandCenterData.team_id over localStorage (fixes stale userTeamId bug)
    // Update userTeamId and userTeamName from command center data FIRST (needed for team-data fetch)
    if (commandCenterData.team) {
      userTeamName = commandCenterData.team; // Team name for bracket comparisons
    }
    if (commandCenterData.team_id) {
      // ✅ SS&S: commandCenterData.team_id is authoritative - always use it, even if localStorage has a different value
      userTeamId = commandCenterData.team_id; // ObjectId for API calls
      localStorage.setItem("userTeamId", userTeamId);
      console.log('✅ [TOURNAMENT INIT] Set userTeamId from commandCenterData:', userTeamId);
    } else {
      console.warn('⚠️ [TOURNAMENT INIT] commandCenterData.team_id not found - using existing userTeamId:', userTeamId);
    }
    
    // ✅ FIX: Use EXACT same source as Team tab - fetch team_chemistry from /tournament/team-data
    // This ensures 100% consistency between header and Team tab (matches FCC pattern)
    if (tournament && tournament._id && userTeamId) {
      try {
        const teamDataResponse = await fetch(`${API_CONFIG.buildUrl('/tournament/team-data')}?tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
        if (teamDataResponse.ok) {
          const teamData = await teamDataResponse.json();
          // Override team_chemistry with value from team-data endpoint (same as Team tab uses)
          if (teamData && teamData.team_attributes && teamData.team_attributes.team_chemistry !== undefined) {
            commandCenterData.team_chemistry = teamData.team_attributes.team_chemistry;
            console.log('📊 [TEAM CHEMISTRY] Top bar value (from team-data):', commandCenterData.team_chemistry);
          }
        }
      } catch (error) {
        console.warn('Could not fetch team_chemistry from team-data endpoint:', error);
      }
    }
    
    // Populate top bar using structured data (aligns with Franchise)
    populateTop(commandCenterData);
    
    // ✅ FIX: Store user team name for leaderboard highlighting (matches Franchise pattern)
    if (commandCenterData.team) {
      userTeamNameForLeaders = commandCenterData.team;
    }
  } else {
    // Fallback: Update from tournament object (backward compatibility)
    if (tournament.user_team_id) {
      userTeamName = tournament.user_team_id; // Team name for bracket comparisons
    }
    if (!userTeamId && tournament.user_team_object_id) {
      userTeamId = tournament.user_team_object_id; // ObjectId for API calls
      localStorage.setItem("userTeamId", userTeamId);
    } else if (!userTeamId && tournament.user_team_id) {
      // Fallback: use team name if ObjectId not available
      userTeamId = tournament.user_team_id;
      localStorage.setItem("userTeamId", userTeamId);
    }
    
    // Fallback: Update top bar from tournament object
    initTopAssets(userTeamId);
    updateTeamChemistry();
    
    // ✅ FIX: Fallback: Store user team name for leaderboard highlighting (matches Franchise pattern)
    if (tournament.user_team_id) {
      userTeamNameForLeaders = tournament.user_team_id;
    }
  }
  
  if (window.GOB_Analytics) window.GOB_Analytics.tournamentEntered();

  // Ensure userTeamId is set before proceeding
  if (!userTeamId) {
    console.error("❌ userTeamId not found - cannot load roster");
    return;
  }
  
  // Initialize team color cache for leaderboard highlighting
  await initializeTeamColorCache();
  
  await loadRoster();
  renderBracket();
  renderSchedule();
  renderRoster(); // ✅ SS&S: renderRoster() now calls renderRosterStats() internally (matches Franchise)
  await refreshLeaders();
  
  // ✅ FIX: Call renderTeamStats directly in DOMContentLoaded (matches Franchise pattern)
  // Franchise calls it directly in init(), not just in refreshLeaders()
  console.log('🔍 [DEBUG DOMContentLoaded] Loading team stats on initial page load');
  if (tournament && tournament._id) {
    try {
      const url = `${API_CONFIG.buildUrl('/tournament/team-stats')}?tournament_id=${encodeURIComponent(tournament._id)}`;
      console.log('🔍 [DEBUG DOMContentLoaded] Fetching team stats from:', url);
      const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
      const data = await res.json();
      console.log('🔍 [DEBUG DOMContentLoaded] Team stats response:', {
        hasData: !!data,
        teamsCount: data?.teams?.length || 0
      });
      renderTeamStats(data);
    } catch (err) {
      console.error("❌ [DEBUG DOMContentLoaded] Failed to load team stats", err);
    }
  } else {
    console.warn('⚠️ [DEBUG DOMContentLoaded] Tournament not loaded, cannot fetch team stats');
  }
  
  // ✅ MIGRATION: Update CTA using command center data (aligns with Franchise)
  updateCTA(commandCenterData);
  
  // Update scouting report button visibility
  updateScoutingButton(commandCenterData);
  
  // Initialize tooltips for table headers
  if (typeof initAttributeTooltips !== 'undefined') {
    const rosterTable = document.querySelector('#roster-tab .roster-table');
    if (rosterTable) {
      initAttributeTooltips(rosterTable, ['th']);
    }
  }
  
  // Load team data for Team tab
  await loadTeamData();

  const playBtn = document.getElementById('play-now');
  if (playBtn) {
    playBtn.addEventListener('click', async () => {
      playSound('confirm-1.mp3');
      if (!tournament || !tournament._id) {
        alert('Tournament not loaded');
        return;
      }
      playBtn.disabled = true;
      try {
        // ✅ REMOVED: Training is not used in Tournament mode - proceed directly to game
        const payload = { tournament_id: tournament._id };
        const res = await fetch(API_CONFIG.buildUrl('/tournament/simulate-round'), {
          method: 'POST',
          headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        console.log('[PlayNow] simulate round', { payload, response: data });
        if (!res.ok || data.error) {
          alert(data.detail || data.error || 'Unable to start game');
          playBtn.disabled = false;
          return;
        }
        if (data.already_played) {
          playBtn.disabled = false;
          await refreshTeamStats();
          await refreshLeaders();
          alert('This round has already been played.');
          return;
        }
        await refreshTeamStats();
        await refreshLeaders();
        const { home, away } = data;
        if (!home || !away) throw new Error('Matchup not found');
        // Compare with team name (bracket uses team names, not ObjectIds)
        const mySide = home === userTeamName ? 'home' : (away === userTeamName ? 'away' : '');
        // ✅ FIX: Add mode=tournament parameter (matches Franchise pattern)
        // This ensures mode is preserved through navigation chain: TCC → Lineup → Game Plan → Court
        let url = `/set-lineup.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
        // Add team IDs for gameplan API compatibility
        url += `&home_id=${encodeURIComponent(home)}&away_id=${encodeURIComponent(away)}`;
        if (userTeamId) url += `&user_team_id=${encodeURIComponent(userTeamId)}`;
        if (mySide) url += `&my_team=${mySide}`;
        window.location.href = url;
      } catch (err) {
        console.error('Failed to start game', err);
        alert('Unable to start game');
        playBtn.disabled = false;
      }
    });
  }

  // Game Plan and Playbooks buttons are wired in wireTccNavButtons() on DOMContentLoaded

  const simBtn = document.getElementById('sim-remaining');
  if (simBtn) {
    simBtn.addEventListener('click', async () => {
      if (simBtn.disabled) return;
      if (!tournament) {
        alert('Tournament not loaded');
        return;
      }
      if (tournament.completed) return;
      simBtn.disabled = true;
      if (!tournament._id) {
        alert('Tournament not loaded');
        simBtn.disabled = false;
        return;
      }
      console.log('#sim-remaining click start');
      try {
        const res = await fetch(API_CONFIG.buildUrl('/tournament/sim-remaining'), {
          method: 'POST',
          headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ tournament_id: tournament._id })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        tournament = data;
        localStorage.setItem('activeTournament', JSON.stringify(tournament));
        await loadRoster();
        renderRoster();
        renderBracket();
        console.log('#sim-remaining bracket refreshed');
        renderRoster(); // ✅ SS&S: renderRoster() now calls renderRosterStats() internally (matches Franchise)
        await refreshLeaders();
        updateCTA();
        console.log('#sim-remaining bracket update complete');
      } catch (err) {
        console.error('Sim remaining failed:', err.message);
        alert('Unable to simulate remaining games');
        simBtn.disabled = false;
      }
    });
  }

  const exitBtn = document.getElementById('exit-tournament');
  if (exitBtn) {
    exitBtn.addEventListener('click', () => {
      playSound('x-back.mp3');
      window.location.href = '/mode-select.html';
    });
  }
  } finally {
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
    if (typeof AccessDenied !== 'undefined' && AccessDenied.hideLoadingOverlay) AccessDenied.hideLoadingOverlay();
  }
}

// Scouting Report functionality
let upcomingOpponent = null;
let upcomingOpponentId = null;

function updateScoutingButton(data) {
  const scoutingBtn = document.getElementById('scouting-report-btn');
  if (!scoutingBtn) return;
  
  // For tournaments, show button if tournament is not completed and user is not eliminated
  const completed = data?.completed || tournament?.completed || false;
  const currentRound = data?.current_round || tournament?.current_round || 1;
  
  if (completed) {
    scoutingBtn.style.display = 'none';
    return;
  }
  
  // Check if user is eliminated (need tournament object for bracket data)
  if (tournament) {
    const roundKey = currentRound === 3 ? 'final' : `round${currentRound}`;
    const matchups = tournament.bracket?.[roundKey] || [];
    const userMatch = matchups.find(m =>
      String(m.home_team) === String(userTeamId) || String(m.away_team) === String(userTeamId)
    );

    const eliminated = !userMatch || !!userMatch.winner;
    if (eliminated) {
      scoutingBtn.style.display = 'none';
      return;
    }

    if (userMatch) {
      const isHome = String(userMatch.home_team) === String(userTeamId);
      upcomingOpponentId = isHome ? userMatch.away_team : userMatch.home_team;
      upcomingOpponent = (upcomingOpponentId != null && teamIdNameMap[String(upcomingOpponentId)]) || upcomingOpponentId;

      scoutingBtn.style.display = upcomingOpponent ? 'block' : 'none';
    } else {
      scoutingBtn.style.display = 'none';
    }
  } else {
    scoutingBtn.style.display = 'none';
  }
}

async function loadScoutingReport() {
  playSound('positive-slide.wav');
  if (!upcomingOpponent || !tournament || !tournament._id) {
    alert('No upcoming opponent found');
    return;
  }
  
  const modal = document.getElementById('scouting-report-modal');
  const loading = document.getElementById('scouting-loading');
  const content = document.getElementById('scouting-content');
  const title = document.getElementById('scouting-report-title');
  
  modal.style.display = 'flex';
  loading.style.display = 'block';
  content.style.display = 'none';
  title.textContent = `Scouting Report: ${upcomingOpponent}`;
  
  try {
    // Load opponent team data and last game play usage
    const authHeaders = API_CONFIG.getAuthHeaders();
    const [teamDataRes, playUsageRes] = await Promise.all([
      fetch(`${API_CONFIG.buildUrl('/tournament/team-data')}?tournament_id=${encodeURIComponent(tournament._id)}&team_name=${encodeURIComponent(upcomingOpponent)}`, { headers: authHeaders }),
      fetch(`${API_CONFIG.buildUrl('/tournament/scouting-report')}?tournament_id=${encodeURIComponent(tournament._id)}&team_name=${encodeURIComponent(upcomingOpponent)}`, { headers: authHeaders })
    ]);
    
    if (!teamDataRes.ok) throw new Error('Failed to load team data');
    if (!playUsageRes.ok) throw new Error('Failed to load play usage');
    
    const teamData = await teamDataRes.json();
    const playUsage = await playUsageRes.json();
    
    // ✅ SS&S: Use shared rendering functions
    if (typeof renderScoutingTeamReport === 'function' && typeof createTeamAttrItem === 'function') {
      renderScoutingTeamReport(teamData.team_attributes || {}, createTeamAttrItem);
    } else {
      console.error('Scouting report rendering functions not available');
    }
    
    if (typeof renderPlayUsage === 'function') {
      renderPlayUsage(playUsage.plays || [], 'No previous game data available. Opponent has not played a game yet this tournament.');
    } else {
      console.error('Play usage rendering function not available');
    }

    if (typeof setScoutingProjectedLineupData === 'function') {
      setScoutingProjectedLineupData(
        playUsage.projected_starting_five || [],
        playUsage.player_season_stats || {}
      );
    } else if (typeof renderProjectedStartingFive === 'function') {
      renderProjectedStartingFive(playUsage.projected_starting_five || []);
    }
    
    loading.style.display = 'none';
    content.style.display = 'block';
  } catch (error) {
    console.error('Error loading scouting report:', error);
    loading.textContent = `Error loading scouting report: ${error.message}`;
  }
}

// ✅ SS&S: Removed duplicate functions - now using shared functions from scoutingReport.js
// renderScoutingTeamReport, renderPlayUsage, and setupScoutingReport are now in /js/shared/scoutingReport.js

// ✅ FIX: Check readyState - if page is already loaded, run immediately
// Wire TCC Game Plan and Playbooks buttons as soon as DOM is ready (so sound + nav work; tournament/userTeamId set by init)
function wireTccNavButtons() {
  const setGameplanBtn = document.getElementById('set-gameplan-tournament');
  if (setGameplanBtn) {
    setGameplanBtn.addEventListener('click', () => {
      playSound('positive-beep.wav');
      if (!tournament || !tournament._id || !userTeamId) {
        alert('Tournament or user team not loaded');
        return;
      }
      const params = new URLSearchParams();
      params.set('mode', 'tournament');
      params.set('tournament_id', tournament._id);
      params.set('team_id', userTeamId);
      params.set('from', 'tournament-command-center');
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }
  const playbooksBtnEl = document.getElementById('playbooks-tournament');
  if (playbooksBtnEl) {
    playbooksBtnEl.addEventListener('click', () => {
      playSound('positive-beep.wav');
      if (!tournament || !tournament._id || !userTeamId) {
        alert('Tournament or user team not loaded');
        return;
      }
      const params = new URLSearchParams();
      params.set('mode', 'tournament');
      params.set('tournament_id', tournament._id);
      params.set('team_id', userTeamId);
      params.set('from', 'tournament-command-center');
      window.location.href = `/playbooks.html?${params.toString()}`;
    });
  }
}

// Otherwise wait for DOMContentLoaded (handles case where script loads late)
if (document.readyState === 'loading') {
  // DOM is still loading, wait for DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    wireTccNavButtons();
    initializeTournament();
    // ✅ SS&S: Initialize scouting report using shared function
    if (typeof setupScoutingReport === 'function') {
      setupScoutingReport(loadScoutingReport);
    }
  });
} else {
  // DOM is already loaded (interactive or complete), run immediately
  console.log('🚀 [TOURNAMENT] DOM already loaded, calling initializeTournament() immediately');
  wireTccNavButtons();
  initializeTournament();
  // ✅ SS&S: Initialize scouting report using shared function
  if (typeof setupScoutingReport === 'function') {
    setupScoutingReport(loadScoutingReport);
  }
}

// Team Report and Playbook Summary functions (adapted from training-report.js)
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Trap',
  'fight': 'Fight',
  'discipline': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'Press/Trap Breaks'
};

let teamData = null;

async function loadTeamData() {
  if (!tournament || !tournament._id || !userTeamId) return;
  
  try {
    // ✅ FIX: Reload tournament document fresh (like FCC does with /franchise/state)
    // This ensures we have the latest stats after games complete
    let freshTournamentDoc = null;
    try {
      const tournamentStateRes = await fetch(`${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${encodeURIComponent(tournament._id)}`, { headers: API_CONFIG.getAuthHeaders() });
      if (tournamentStateRes.ok) {
        freshTournamentDoc = await tournamentStateRes.json();
      }
    } catch (error) {
      console.warn('⚠️ [TCC] Could not reload tournament document, using cached:', error);
    }
    
    // Use fresh document if available, otherwise fall back to cached tournament
    const tournamentDoc = freshTournamentDoc || tournament;
    
    // First, ensure team objects exist (this will create them if missing)
    try {
      // Call ensure_team_objects_exist via get_gameplan endpoint (it calls ensure_team_objects_exist internally)
      await fetch(`${API_CONFIG.buildUrl('/api/gameplan')}?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
    } catch (error) {
      console.warn('Could not ensure team objects exist:', error);
    }
    
    // ✅ SS&S: Use ObjectId directly - backend accepts team_id parameter
    const response = await fetch(`${API_CONFIG.buildUrl('/tournament/team-data')}?tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
    
    if (!response.ok) {
      console.error('Failed to load team data:', response.status, response.statusText);
      return;
    }
    
    const data = await response.json();
    
    // ✅ FIX: Merge player stats from fresh tournament document (aligns with FCC pattern)
    let playersWithStats = [];
    if (roster && roster.length > 0 && tournamentDoc && tournamentDoc.players) {
      // ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
      const tournamentPlayers = tournamentDoc.players || tournamentDoc.player_stats || {}; // Backward compatibility
      
      let statsFound = 0;
      let statsMissing = 0;
      playersWithStats = roster.map(player => {
        const playerId = player.id || player._id;
        const tournamentPlayer = tournamentPlayers[playerId];
        
        if (tournamentPlayer && tournamentPlayer.season) {
          // Merge stats from tournament document
          player.stats = { season: tournamentPlayer.season };
          statsFound++;
        } else {
          // No stats found, use empty object
          player.stats = { season: {} };
          statsMissing++;
        }
        return player;
      });
    } else {
      playersWithStats = roster || [];
    }
    
    teamData = {
      team_attributes: data.team_attributes || {},
      plays_data: data.plays_data || {},
      scouting_data: data.scouting_data || {},
      players: playersWithStats
    };
    
    
    // ✅ FIX: Always render Team Report (matches FCC pattern)
    // FCC calls renderTeam() which always renders, not conditionally
    renderTeamReport();
    
    renderPlaybookSummary();
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
    'fight',
    'discipline',
    'momentum_score',
    'team_chemistry',
    'fb_opp_modifier',
    'pt_opp_modifier'
  ];
  
  attrOrder.forEach(attrKey => {
    const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], 0); // No changes in command center
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
    maxValue = 100; // Range is 10 to 210, center at 110, so max deviation is 100
    value = 110 - originalValue; // Invert: lower is better (positive/green), higher is worse (negative/red)
  } else if (attrKey === 'rebound_modifier') {
    maxValue = 0.2;
    value = originalValue - 0.2; // Center at 0.2 (new range: 0.0-0.4)
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

// ✅ Phase 4.2: Roster stats rendering delegated to RosterStatsRenderer (rosterStatsRenderer.js)

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
      const resolvedName = play_data.name || play_name;
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push({ ...play_data, name: resolvedName, display_name: resolvedName, play_key: play_name });
      } else if (play_type === 'set_play') {
        set_plays.push({ ...play_data, name: resolvedName, display_name: resolvedName, play_key: play_name });
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
  const players = teamData.players || roster || [];
  
  if (motion_plays.length > 0) {
    motion_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.display_name || play.name, play, null, players);
      offenseSection.appendChild(playRow);
    });
  }
  
  if (set_plays.length > 0) {
    set_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.display_name || play.name, play, null, players);
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

// ✅ Phase 4.4: Shared tab management (commandCenterTabs.js)
document.addEventListener('DOMContentLoaded', () => {
  if (typeof CommandCenterTabs !== 'undefined') {
    CommandCenterTabs.initCommandCenterTabs({
      defaultTab: 'bracket-tab',
      onTabShow: (tabName) => {
        if (tabName === 'bracket-tab') {
          renderBracket();
        } else if (tabName === 'roster-tab') {
          if (roster.length === 0) {
            loadRoster().then(() => renderRoster());
          } else {
            renderRoster();
          }
        } else if (tabName === 'team-tab') {
          loadTeamData();
        } else if (tabName === 'stats-tab') {
          renderLeaderboards();
          refreshTeamStats();
        } else if (tabName === 'schedule-tab') {
          renderSchedule();
        }
      }
    });
  }
});
