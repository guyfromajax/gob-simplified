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

function isUserTeam(teamName) {
  // Compare with team name (bracket uses team names, not ObjectIds)
  return teamName === userTeamName || teamName === userTeamId;
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
  { title: "Points", key: "PTS" },
  { title: "3-Pointers Made", key: "TPM" },
  { title: "Rebounds", key: "REB" },
  { title: "Assists", key: "AST" },
  { title: "Steals", key: "STL" },
  { title: "Blocks", key: "BLK" }
];

let leaderData = {};

console.log("✅ tournament.js loaded");

function getLogo(teamName) {
  const formatted = formatTeamName(teamName);
  return `/static/images/homepage-logos/${formatted}.png`;
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

  function createTeamEntry(team, side, score, isWinner) {
    const div = document.createElement("div");
    div.className = "team-entry";
    if (isWinner) div.classList.add("winner");
    const label = document.createElement("span");
    label.className = `seed-label ${side === "left" ? "seed-left" : "seed-right"}`;
    label.textContent = seedMap[team] ? `#${seedMap[team]}` : "";
    const img = document.createElement("img");
    img.src = getLogo(team);
    img.classList.add("team-logo", "bracket-logo");
    if (isUserTeam(team)) img.classList.add("user-team");
    const scoreSpan = document.createElement("span");
    scoreSpan.className = "score";
    scoreSpan.textContent = score !== undefined && score !== null ? score : "";
    if (side === "left") {
      div.appendChild(label);
      div.appendChild(img);
      div.appendChild(scoreSpan);
    } else {
      div.appendChild(scoreSpan);
      div.appendChild(img);
      div.appendChild(label);
    }
    return div;
  }

  function createMatchup(m, side, round, index) {
    const wrap = document.createElement("div");
    wrap.className = "matchup-wrapper";
    const matchup = document.createElement("div");
    matchup.className = "matchup";

    // Always prefer results pulled from ``tournament.results`` so the
    // bracket reflects finalized scores, even after the tournament is
    // completed.  Fall back to any score/winner information stored
    // directly on the matchup if results have not yet been recorded.
    const res = getResult(round, index);
    const homeScore = res?.score?.[m.home_team] ?? m.score?.[m.home_team];
    const awayScore = res?.score?.[m.away_team] ?? m.score?.[m.away_team];
    const winner = res?.winner ?? m.winner ?? null;

    if (side === "center") {
      matchup.appendChild(createTeamEntry(m.home_team, "left", homeScore, winner === m.home_team));
      matchup.appendChild(createTeamEntry(m.away_team, "right", awayScore, winner === m.away_team));
    } else {
      matchup.appendChild(createTeamEntry(m.home_team, side, homeScore, winner === m.home_team));
      matchup.appendChild(createTeamEntry(m.away_team, side, awayScore, winner === m.away_team));
    }
    wrap.appendChild(matchup);
    return wrap;
  }

  function createPlaceholder() {
    const wrap = document.createElement("div");
    wrap.className = "matchup-wrapper";
    const matchup = document.createElement("div");
    matchup.className = "matchup";
    const placeholder = document.createElement("div");
    placeholder.className = "placeholder";
    placeholder.textContent = "TBD";
    matchup.appendChild(placeholder);
    wrap.appendChild(matchup);
    return wrap;
  }

  const leftR1 = document.createElement("div");
  leftR1.className = "round round-1 quarterfinals";
  if (round1[0]) leftR1.appendChild(createMatchup(round1[0], "left", 1, 0));

  const leftSpacer = document.createElement("div");
  leftSpacer.style.height = "40px";
  leftSpacer.className = "bracket-spacer";
  leftR1.appendChild(leftSpacer);

  if (round1[1]) leftR1.appendChild(createMatchup(round1[1], "left", 1, 1));

  const leftSemi = document.createElement("div");
  leftSemi.className = "round round-2 semifinals";
  if (round2[0]) leftSemi.appendChild(createMatchup(round2[0], "left", 2, 0));
  else leftSemi.appendChild(createPlaceholder());

  const final = document.createElement("div");
  final.className = "round round-3 final";
  if (finalRound[0]) final.appendChild(createMatchup(finalRound[0], "center", 3, 0));
  else final.appendChild(createPlaceholder());

  const rightSemi = document.createElement("div");
  rightSemi.className = "round round-4 semifinals";
  if (round2[1]) rightSemi.appendChild(createMatchup(round2[1], "right", 2, 1));
  else rightSemi.appendChild(createPlaceholder());

  const rightR1 = document.createElement("div");
  rightR1.className = "round round-5 quarterfinals";
  if (round1[2]) rightR1.appendChild(createMatchup(round1[2], "right", 1, 2));

  const rightSpacer = document.createElement("div");
  rightSpacer.style.height = "40px";
  rightSpacer.className = "bracket-spacer";
  rightR1.appendChild(rightSpacer);

  if (round1[3]) rightR1.appendChild(createMatchup(round1[3], "right", 1, 3));

  bracket.appendChild(leftR1);
  bracket.appendChild(leftSemi);
  bracket.appendChild(final);
  bracket.appendChild(rightSemi);
  bracket.appendChild(rightR1);

  if (DEBUG_BRACKET) console.log("[DebugBracket] bracket render complete");
  // ensure CTA buttons reflect latest bracket state
  updateCTA();
}

function renderRoster() {
  const tbody = document.getElementById("roster-body");
  console.log("Inside renderRoster, roster data:", roster);
  if (!tbody) {
    console.log("roster-body element not found");
    return;
  }
  tbody.innerHTML = "";
  if (!roster || roster.length === 0) {
    console.log("No roster data to render");
    return;
  }
  roster.forEach(p => {
    const tr = document.createElement("tr");
    
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
}

// Store player stats data for sorting (tournament)
let tournamentPlayerStatsDataForSorting = [];

function renderStats() {
  tournamentPlayerStatsDataForSorting = JSON.parse(JSON.stringify(stats || [])); // Deep copy for sorting
  renderStatsTable(tournamentPlayerStatsDataForSorting);
  
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
        sortPlayerStats(stat);
      });
    });
  }
}

function renderStatsTable(playerStats) {
  const tbody = document.getElementById("stats-body");
  if (!tbody) {
    console.error("❌ [RENDER-STATS-TABLE] stats-body tbody not found");
    return;
  }
  
  tbody.innerHTML = "";
  
  playerStats.forEach((s) => {
    // Calculate percentages
    const fgPct = s.FGA > 0 ? ((s.FGM || 0) / s.FGA * 100).toFixed(1) : '0.0';
    const threePct = s.TPA > 0 ? ((s.TPM || 0) / s.TPA * 100).toFixed(1) : '0.0';
    const ftPct = s.FTA > 0 ? ((s.FTM || 0) / s.FTA * 100).toFixed(1) : '0.0';
    
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.name}</td>
      <td>${s.PTS || 0}</td>
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
      <td>${s.TREB || (s.DREB || 0) + (s.OREB || 0)}</td>
      <td>${s.AST || 0}</td>
      <td>${s.STL || 0}</td>
      <td>${s.BLK || 0}</td>
      <td>${s.F || 0}</td>
      <td>${s.MIN || 0}</td>
      <td>${s.TO || 0}</td>`;
    tbody.appendChild(tr);
  });
}

function sortPlayerStats(statKey) {
  // Map display stat names to data stat keys
  const statMap = {
    'name': 'name',
    'PTS': 'PTS',
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
      val1 = a.TPA > 0 ? (a.TPM || 0) / a.TPA : 0;
      val2 = b.TPA > 0 ? (b.TPM || 0) / b.TPA : 0;
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
    table.innerHTML = `<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>Value</th></tr></thead>`;
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
    const res = await fetch(`/tournament/leaders?tournament_id=${encodeURIComponent(tournament._id)}`);
    leaderData = await res.json();
  } catch (err) {
    console.error("Failed to load leaders", err);
    leaderData = {};
  }
  renderLeaderboards();
  await refreshTeamStats();
}

async function refreshTeamStats() {
  if (!tournament || !tournament._id) return;
  try {
    const res = await fetch(`/tournament/team-stats?tournament_id=${encodeURIComponent(tournament._id)}`);
    const data = await res.json();
    renderTeamStats(data);
  } catch (err) {
    console.error("Failed to load team stats", err);
  }
}

function renderTeamStats(data) {
  if (!data) return;
  tournamentTeamsDataForSorting = JSON.parse(JSON.stringify(data.teams || [])); // Deep copy for sorting
  renderTeamStatsTable(tournamentTeamsDataForSorting);
  
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
  
  // Calculate totals for all teams
  const totals = {
    PF: 0, PA: 0, FGM: 0, FGA: 0, TPM: 0, TPA: 0, FTM: 0, FTA: 0,
    DREB: 0, OREB: 0, TREB: 0, AST: 0, STL: 0, BLK: 0, F: 0, TO: 0,
    DEF_A: 0, DEF_S: 0, SCR_A: 0, SCR_S: 0
  };
  
  teams.forEach(t => {
    const tr = document.createElement('tr');
    const s = t.stats || {};
    
    // Accumulate totals
    totals.PF += s.PF || 0;
    totals.PA += s.PA || 0;
    totals.FGM += s.FGM || 0;
    totals.FGA += s.FGA || 0;
    totals.TPM += s.TPM || 0;
    totals.TPA += s.TPA || 0;
    totals.FTM += s.FTM || 0;
    totals.FTA += s.FTA || 0;
    totals.DREB += s.DREB || 0;
    totals.OREB += s.OREB || 0;
    totals.TREB += s.TREB || 0;
    totals.AST += s.AST || 0;
    totals.STL += s.STL || 0;
    totals.BLK += s.BLK || 0;
    totals.F += s.F || 0;
    totals.TO += s.TO || 0;
    totals.DEF_A += s.DEF_A || 0;
    totals.DEF_S += s.DEF_S || 0;
    totals.SCR_A += s.SCR_A || 0;
    totals.SCR_S += s.SCR_S || 0;
    
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
  
  // Add totals row
  const totalsTr = document.createElement('tr');
  totalsTr.className = 'totals-row';
  totalsTr.style.fontWeight = 'bold';
  totalsTr.style.pointerEvents = 'none'; // Prevent any click interactions
  
  // Calculate total percentages
  const totalFgPct = totals.FGA > 0 ? (totals.FGM / totals.FGA * 100).toFixed(1) : '0.0';
  const totalThreePct = totals.TPA > 0 ? (totals.TPM / totals.TPA * 100).toFixed(1) : '0.0';
  const totalFtPct = totals.FTA > 0 ? (totals.FTM / totals.FTA * 100).toFixed(1) : '0.0';
  const totalDefPct = totals.DEF_A > 0 ? (totals.DEF_S / totals.DEF_A * 100).toFixed(1) : '0.0';
  const totalScrPct = totals.SCR_A > 0 ? (totals.SCR_S / totals.SCR_A * 100).toFixed(1) : '0.0';
  
  totalsTr.innerHTML = `
    <td>TOTALS</td>
    <td>${totals.PF}</td>
    <td>${totals.PA}</td>
    <td>${totals.FGM}</td>
    <td>${totals.FGA}</td>
    <td>${totalFgPct}%</td>
    <td>${totals.TPM}</td>
    <td>${totals.TPA}</td>
    <td>${totalThreePct}%</td>
    <td>${totals.FTM}</td>
    <td>${totals.FTA}</td>
    <td>${totalFtPct}%</td>
    <td>${totals.DREB}</td>
    <td>${totals.OREB}</td>
    <td>${totals.TREB}</td>
    <td>${totals.AST}</td>
    <td>${totals.STL}</td>
    <td>${totals.BLK}</td>
    <td>${totals.F}</td>
    <td>${totals.TO}</td>
    <td>${totals.DEF_A}</td>
    <td>${totalDefPct}%</td>
    <td>${totals.SCR_A}</td>
    <td>${totalScrPct}%</td>
  `;
  tbody.appendChild(totalsTr);
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
  tournamentTeamsDataForSorting.sort((a, b) => {
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
  renderTeamStatsTable(tournamentTeamsDataForSorting);
}

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

  // First Round
  const firstRoundDiv = document.createElement('div');
  firstRoundDiv.className = 'schedule-round';
  const firstRoundH3 = document.createElement('h3');
  firstRoundH3.textContent = 'First Round';
  firstRoundDiv.appendChild(firstRoundH3);

  round1.forEach((match, index) => {
    const res = getResult(1, index);
    const homeScore = res?.score?.[match.home_team] ?? match.score?.[match.home_team];
    const awayScore = res?.score?.[match.away_team] ?? match.score?.[match.away_team];
    const winner = res?.winner ?? match.winner ?? null;

    const gameDiv = document.createElement('div');
    gameDiv.className = 'schedule-game';
    const homeSeed = seedMap[match.home_team] || '';
    const awaySeed = seedMap[match.away_team] || '';
    
    let text = `Team ${awaySeed} ${match.away_team} @ Team ${homeSeed} ${match.home_team}`;
    if (homeScore !== undefined && awayScore !== undefined) {
      text = `Team ${awaySeed} ${match.away_team} (${awayScore}) @ Team ${homeSeed} ${match.home_team} (${homeScore})`;
    }
    
    gameDiv.innerHTML = text;
    
    // ✅ FIX: Add box score link for completed games (aligns with FCC)
    const gameId = res?.game_id || match.game_id;
    if (gameId && homeScore !== undefined && awayScore !== undefined) {
      const boxScoreLink = document.createElement('a');
      boxScoreLink.href = `/static/box-score.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&game_id=${encodeURIComponent(gameId)}`;
      boxScoreLink.textContent = ' [Box Score]';
      boxScoreLink.className = 'box-score-link';
      boxScoreLink.style.color = '#4a90e2';
      boxScoreLink.style.textDecoration = 'none';
      boxScoreLink.style.marginLeft = '8px';
      boxScoreLink.style.fontSize = 'calc(1em - 2px)';
      gameDiv.appendChild(boxScoreLink);
    }
    
    // Add training report link if this is user's matchup and training has been run
    // Compare with team name (bracket uses team names, not ObjectIds)
    const isUserMatch = match.home_team === userTeamName || match.away_team === userTeamName;
    if (isUserMatch && tournament.training_status?.training_completed && tournament.training_status?.round === 1) {
      const link = document.createElement('a');
      link.href = `/static/training-report.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&round=1`;
      link.textContent = ' [Training Report]';
      link.className = 'training-report-link';
      link.style.color = '#4a90e2';
      link.style.textDecoration = 'none';
      link.style.marginLeft = '8px';
      link.style.fontSize = 'calc(1em - 2px)';
      gameDiv.appendChild(link);
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
      const homeScore = res?.score?.[match.home_team] ?? match.score?.[match.home_team];
      const awayScore = res?.score?.[match.away_team] ?? match.score?.[match.away_team];
      const winner = res?.winner ?? match.winner ?? null;

      let text = `${match.away_team} @ ${match.home_team}`;
      if (homeScore !== undefined && awayScore !== undefined) {
        text = `${match.away_team} (${awayScore}) @ ${match.home_team} (${homeScore})`;
      }
      gameDiv.innerHTML = text;
      
      // ✅ FIX: Add box score link for completed games (aligns with FCC)
      const gameId = res?.game_id || match.game_id;
      if (gameId && homeScore !== undefined && awayScore !== undefined) {
        const boxScoreLink = document.createElement('a');
        boxScoreLink.href = `/static/box-score.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&game_id=${encodeURIComponent(gameId)}`;
        boxScoreLink.textContent = ' [Box Score]';
        boxScoreLink.className = 'box-score-link';
        boxScoreLink.style.color = '#4a90e2';
        boxScoreLink.style.textDecoration = 'none';
        boxScoreLink.style.marginLeft = '8px';
        boxScoreLink.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(boxScoreLink);
      }
      
      // Add training report link if this is user's matchup and training has been run
      // Compare with team name (bracket uses team names, not ObjectIds)
      const isUserMatch = match.home_team === userTeamName || match.away_team === userTeamName;
      if (isUserMatch && tournament.training_status?.training_completed && tournament.training_status?.round === 2) {
        const link = document.createElement('a');
        link.href = `/static/training-report.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&round=2`;
        link.textContent = ' [Training Report]';
        link.className = 'training-report-link';
        link.style.color = '#4a90e2';
        link.style.textDecoration = 'none';
        link.style.marginLeft = '8px';
        link.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(link);
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
    const homeScore = res?.score?.[match.home_team] ?? match.score?.[match.home_team];
    const awayScore = res?.score?.[match.away_team] ?? match.score?.[match.away_team];
    const winner = res?.winner ?? match.winner ?? null;

    let text = `${match.away_team} @ ${match.home_team}`;
    if (homeScore !== undefined && awayScore !== undefined) {
      text = `${match.away_team} (${awayScore}) @ ${match.home_team} (${homeScore})`;
    }
    champGameDiv.innerHTML = text;
    
    // ✅ FIX: Add box score link for completed games (aligns with FCC)
    const gameId = res?.game_id || match.game_id;
    if (gameId && homeScore !== undefined && awayScore !== undefined) {
      const boxScoreLink = document.createElement('a');
      boxScoreLink.href = `/static/box-score.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&game_id=${encodeURIComponent(gameId)}`;
      boxScoreLink.textContent = ' [Box Score]';
      boxScoreLink.className = 'box-score-link';
      boxScoreLink.style.color = '#4a90e2';
      boxScoreLink.style.textDecoration = 'none';
      boxScoreLink.style.marginLeft = '8px';
      boxScoreLink.style.fontSize = 'calc(1em - 2px)';
      champGameDiv.appendChild(boxScoreLink);
    }
    
    // Add training report link if this is user's matchup and training has been run
    // Compare with team name (bracket uses team names, not ObjectIds)
    const isUserMatch = match.home_team === userTeamName || match.away_team === userTeamName;
    if (isUserMatch && tournament.training_status?.training_completed && tournament.training_status?.round === 3) {
      const link = document.createElement('a');
      link.href = `/static/training-report.html?mode=tournament&tournament_id=${tournament._id}&team_id=${userTeamId}&round=3`;
      link.textContent = ' [Training Report]';
      link.className = 'training-report-link';
      link.style.color = '#4a90e2';
      link.style.textDecoration = 'none';
      link.style.marginLeft = '8px';
      link.style.fontSize = 'calc(1em - 2px)';
      champGameDiv.appendChild(link);
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
  const trainingCompleted = data ? data.training_completed : (tournament?.training_status?.training_completed || false);
  const currentRound = data ? data.current_round : (tournament?.current_round || 1);
  const sessionType = data ? data.session_type : (tournament?.training_status?.session_type || 'in-season');
  
  if (completed) {
    playBtn.style.display = 'none';
    simBtn.style.display = 'none';
    simBtn.disabled = true;
    container.style.display = 'none';
    exitBtn.style.display = 'inline-block';
    return;
  }

  exitBtn.style.display = 'none';
  container.style.display = 'block';

  // Check if user is eliminated (need tournament object for bracket data)
  if (tournament) {
    const roundKey = currentRound === 3 ? 'final' : `round${currentRound}`;
    const matchups = tournament.bracket?.[roundKey] || [];
    // Compare with team name (bracket uses team names, not ObjectIds)
    const userMatch = matchups.find(m => m.home_team === userTeamName || m.away_team === userTeamName);

    // user is out of the tournament when no matchup exists or their matchup is finished
    const eliminated = !userMatch || !!userMatch.winner;
    if (eliminated) {
      playBtn.style.display = 'none';
      simBtn.style.display = 'inline-block';
      simBtn.disabled = false;
      return;
    }
  }

  // Update button based on training status (aligns with Franchise pattern)
  if (!trainingCompleted) {
    // Training not completed, show "Run Training" or "Run Training Camp"
    playBtn.textContent = sessionType === 'preseason' ? 'Run Training Camp' : 'Run Training';
    playBtn.style.display = 'inline-block';
    simBtn.style.display = 'none';
    simBtn.disabled = true;
  } else {
    // Training completed, show "Play Next Game"
    playBtn.textContent = 'Play Next Game';
    playBtn.style.display = 'inline-block';
    simBtn.style.display = 'none';
    simBtn.disabled = true;
  }
}

// ✅ MIGRATION (Task 6.1): Populate top bar using structured data (aligns with Franchise pattern)
function populateTop(data) {
  if (!data) return;
  
  // Update username (placeholder for tournament mode)
  const usernameEl = document.querySelector('.username');
  if (usernameEl) {
    usernameEl.textContent = data.username || 'Coach';
  }
  
  // Update team logo
  if (data.team) {
    const formattedTeam = formatTeamName(data.team);
    const logoSrc = `/static/images/homepage-logos/${formattedTeam}.png`;
    const logoEl = document.getElementById('user-team-logo');
    if (logoEl) {
      logoEl.src = logoSrc;
    }
    
    // Update coach images
    const abbr = teamMap[formattedTeam];
    const sammyEl = document.getElementById('coach-sammy');
    const dukeEl = document.getElementById('coach-duke');
    if (abbr) {
      if (sammyEl) sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
      if (dukeEl) dukeEl.src = `/static/images/coaches/${abbr}/Duke-${abbr}.png`;
    } else {
      if (sammyEl) sammyEl.removeAttribute('src');
      if (dukeEl) dukeEl.removeAttribute('src');
    }
  }
  
  // Update chemistry bar
  const chemistryBar = document.querySelector('.chemistry-bar');
  if (chemistryBar) {
    chemistryBar.textContent = `${data.team_chemistry || 0} / 25`;
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
    chemistryBar.textContent = `${chemistry} / 25`;
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
  const formattedName = formatTeamName(teamName || userTeamId || "");
  const logoEl = document.getElementById("user-team-logo");
  if (logoEl) {
    logoEl.src = `/static/images/homepage-logos/${formattedName}.png`;
  }
  const abbr = teamMap[formattedName] || "";
  const sammyEl = document.getElementById("coach-sammy");
  const dukeEl = document.getElementById("coach-duke");
  if (abbr) {
    if (sammyEl) sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
    if (dukeEl) dukeEl.src = `/static/images/coaches/${abbr}/Duke-${abbr}.png`;
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
    const url = `/tournament/command-center/data?tournament_id=${encodeURIComponent(tournamentId)}&_=${Date.now()}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Failed to load command center data: ${res.status} ${res.statusText}`);
    }
    const commandCenterData = await res.json();
    
    // Also load full tournament document for bracket and other detailed data
    const tournamentRes = await fetch(`/tournament/state?tournament_id=${encodeURIComponent(tournamentId)}&_=${Date.now()}`, { cache: "no-store" });
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
      url = `/tournament/state?${params.toString()}`;
    } else if (tournament && tournament._id) {
      // Priority 2: tournament from localStorage
      params = new URLSearchParams({ tournament_id: tournament._id });
      url = `/tournament/state?${params.toString()}`;
    } else {
      // Priority 3: fallback to active tournament by user_team_id
      params = new URLSearchParams({ user_team_id: userTeamId });
      url = `/tournament/active?${params.toString()}`;
    }
    
    // Add cache buster using & (not ?) since URL already has query params
    const res = await fetch(`${url}&_=${Date.now()}`, { cache: "no-store" });
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
    console.log('Loading tournament roster for userTeamId:', userTeamId);
    if (!userTeamId) {
      console.error('No userTeamId found - cannot load roster');
      return;
    }
    // Ensure tournament is loaded
    if (!tournament || !tournament._id) {
      console.error('Tournament not loaded - cannot load roster');
      return;
    }
    // Use tournament roster endpoint (similar to franchise/roster)
    // Use userTeamId directly (not formatted) - backend handles name resolution
    const url = `/tournament/roster?tournament_id=${encodeURIComponent(tournament._id)}&team_name=${encodeURIComponent(userTeamId)}`;
    const res = await fetch(url);
    const data = await res.json();
    console.log("Tournament team player data:", data);
    roster = (data.players || []).map(p => {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      return {
        _id: p._id, // Use _id consistently for player detail links
        id: p._id, // Keep id for stats mapping
        name: fullName,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
      };
    });
    const statKeys = ["PTS","FGM","FGA","TPM","TPA","FTM","FTA","REB","AST","STL","BLK","F","MIN","TO"];
    // ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
    const pstats = tournament?.players || tournament?.player_stats || {};  // Backward compatibility
    stats = roster.map(p => {
      // ✅ MIGRATION: Use players key structure (aligns with Franchise)
      // Player structure: { meta: {...}, season: {...}, attributes: {...}, position_ratings: {...} }
      const playerStats = pstats[p.id] || pstats[p._id] || {};
      // ✅ MIGRATION: Read from season key (not stats.Season or stats.season)
      const season = playerStats?.season || playerStats?.stats?.Season || playerStats?.stats?.season || playerStats?.Season || {};
      const row = { name: p.name };
      statKeys.forEach(k => {
        const val = season[k];
        row[k] = typeof val === 'number' ? val : 0;
      });
      return row;
    });
    console.log('Tournament stats loaded:', stats.length, 'players');
    if (DEBUG_TEAM_STATS && roster[0]) {
      const first = roster[0];
      // ✅ MIGRATION: Read from season key (aligns with Franchise)
      const s = pstats[first.id]?.season || pstats[first.id]?.stats?.Season || {};
      console.log("[DebugTournamentStats]", {
        tournamentId: tournament?._id,
        teamId: userTeamId,
        playerId: first.id,
        fgm: s.FGM || 0,
        fga: s.FGA || 0,
        pts: s.PTS || 0,
      });
    }
  } catch (err) {
    console.error("Failed to load roster", err);
  }
}

async function refreshTeamStats() {
  await loadTournament();
  await loadRoster();
  renderRoster();
  renderStats();
  renderBracket();
  renderSchedule();
  updateCTA();
}

window.refreshTeamStats = refreshTeamStats;

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
  renderRoster();
  renderStats();
  // ✅ FIX: Reload team data to refresh player stats on Team tab
  loadTeamData();
  updateCTA();
}

window.handleTournamentUpdate = handleTournamentUpdate;

document.addEventListener("DOMContentLoaded", async () => {
  // ✅ MIGRATION (Task 6.1): Use command center data endpoint (aligns with Franchise pattern)
  let commandCenterData = null;
  try {
    commandCenterData = await loadCommandCenterData();
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
    // Populate top bar using structured data (aligns with Franchise)
    populateTop(commandCenterData);
    
    // Update userTeamId and userTeamName from command center data
    if (commandCenterData.team) {
      userTeamName = commandCenterData.team; // Team name for bracket comparisons
    }
    if (commandCenterData.team_id) {
      userTeamId = commandCenterData.team_id; // ObjectId for API calls
      localStorage.setItem("userTeamId", userTeamId);
    }
    
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
  renderRoster();
  renderStats();
  await refreshLeaders();
  
  // ✅ FIX: Call renderTeamStats directly in DOMContentLoaded (matches Franchise pattern)
  // Franchise calls it directly in init(), not just in refreshLeaders()
  if (tournament && tournament._id) {
    try {
      const res = await fetch(`/tournament/team-stats?tournament_id=${encodeURIComponent(tournament._id)}`);
      const data = await res.json();
      renderTeamStats(data);
    } catch (err) {
      console.error("Failed to load team stats", err);
    }
  }
  
  // ✅ MIGRATION: Update CTA using command center data (aligns with Franchise)
  updateCTA(commandCenterData);
  
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
      if (!tournament || !tournament._id) {
        alert('Tournament not loaded');
        return;
      }
      playBtn.disabled = true;
      try {
        // Check if training has been completed
        const trainingStatus = tournament.training_status || {};
        const trainingCompleted = trainingStatus.training_completed && trainingStatus.round === tournament.current_round;
        
        if (!trainingCompleted) {
          // Navigate to training page
          const url = `/static/training.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}&round=${tournament.current_round}`;
          window.location.href = url;
          return;
        }
        
        // Training completed, proceed to game
        const payload = { tournament_id: tournament._id };
        const res = await fetch('/simulate-tournament-round', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        let url = `/static/set-lineup.html?tournament_id=${encodeURIComponent(tournament._id)}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
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

  // Set Game Plan button (Tournament Command Center)
  const setGameplanBtn = document.getElementById('set-gameplan-tournament');
  if (setGameplanBtn) {
    setGameplanBtn.addEventListener('click', () => {
      if (!tournament || !tournament._id || !userTeamId) {
        alert('Tournament or user team not loaded');
        return;
      }
      
      // ✅ MIGRATION (Task 6.1): Use team_id parameter (aligns with Franchise pattern)
      // ✅ SS&S: Redirect to Game Plan screen with ObjectId for consistent navigation
      const params = new URLSearchParams();
      params.set('mode', 'tournament');
      params.set('tournament_id', tournament._id);
      params.set('team_id', userTeamId); // Use team_id (not user_team_id) for consistency
      params.set('from', 'tournament-command-center'); // Track navigation source
      
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }

  // Playbooks button (Tournament Command Center)
  const playbooksBtn = document.getElementById('playbooks-tournament');
  if (playbooksBtn) {
    playbooksBtn.addEventListener('click', () => {
      if (!tournament || !tournament._id || !userTeamId) {
        alert('Tournament or user team not loaded');
        return;
      }
      
      // ✅ SS&S: Build playbooks URL with ObjectId for consistent navigation
      const params = new URLSearchParams();
      params.set('mode', 'tournament');
      params.set('tournament_id', tournament._id);
      params.set('team_id', userTeamId);
      params.set('from', 'tournament-command-center'); // Track navigation source
      
      window.location.href = `/static/playbooks.html?${params.toString()}`;
    });
  }

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
        const res = await fetch('/tournament/sim-remaining', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        renderStats();
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
      window.location.href = '/static/mode-select.html';
    });
  }
});

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
      const tournamentStateRes = await fetch(`/tournament/state?tournament_id=${encodeURIComponent(tournament._id)}`);
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
      await fetch(`/api/gameplan?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}`);
    } catch (error) {
      console.warn('Could not ensure team objects exist:', error);
    }
    
    // ✅ SS&S: Use ObjectId directly - backend accepts team_id parameter
    const response = await fetch(`/tournament/team-data?tournament_id=${encodeURIComponent(tournament._id)}&team_id=${encodeURIComponent(userTeamId)}`);
    
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
    maxValue = 100; // Range is -10 to 190, center at 90, so max deviation is 100
    value = 90 - originalValue; // Invert: lower is better (positive/green), higher is worse (negative/red)
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

// ✅ FIX: Add player stats rendering to Team tab (aligns with FCC)
// Note: renderRosterStats() removed - player stats are only on Roster tab, not Team tab

// Store roster stats data for sorting
let rosterPlayersDataForSorting = [];

function renderRosterStatsTable(players) {
  const tbody = document.getElementById('roster-stats-body');
  if (!tbody) {
    console.error('❌ [RENDER-ROSTER-STATS-TABLE] tbody element not found');
    return;
  }
  
  tbody.innerHTML = '';
  rosterPlayersDataForSorting = JSON.parse(JSON.stringify(players)); // Deep copy for sorting
  
  players.forEach((p) => {
    const stats = p.stats?.season || {};
    // ✅ FIX: Map 3PTM/3PTA to TPM/TPA for display (database stores as 3PTM/3PTA, frontend expects TPM/TPA)
    const tpm = stats['3PTM'] || stats.TPM || 0;
    const tpa = stats['3PTA'] || stats.TPA || 0;
    
    // Calculate percentages
    const fgPct = stats.FGA > 0 ? ((stats.FGM || 0) / stats.FGA * 100).toFixed(1) : '0.0';
    const threePct = tpa > 0 ? (tpm / tpa * 100).toFixed(1) : '0.0';
    const ftPct = stats.FTA > 0 ? ((stats.FTM || 0) / stats.FTA * 100).toFixed(1) : '0.0';
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name || `${p.first_name || ''} ${p.last_name || ''}`.trim()}</td>
      <td>${stats.PTS || 0}</td>
      <td>${stats.FGM || 0}</td>
      <td>${stats.FGA || 0}</td>
      <td>${fgPct}%</td>
      <td>${tpm}</td>
      <td>${tpa}</td>
      <td>${threePct}%</td>
      <td>${stats.FTM || 0}</td>
      <td>${stats.FTA || 0}</td>
      <td>${ftPct}%</td>
      <td>${stats.DREB || 0}</td>
      <td>${stats.OREB || 0}</td>
      <td>${stats.TREB || (stats.DREB || 0) + (stats.OREB || 0)}</td>
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
    'MIN': 'MIN',
    'TO': 'TO'
  };
  
  const dataKey = statMap[statKey] || statKey;
  
  // Sort players by the selected stat (descending order)
  rosterPlayersDataForSorting.sort((a, b) => {
    let val1, val2;
    const statsA = a.stats?.season || {};
    const statsB = b.stats?.season || {};
    
    if (dataKey === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return val2.localeCompare(val1); // Reverse for descending
    } else if (dataKey === 'FG%') {
      val1 = statsA.FGA > 0 ? (statsA.FGM || 0) / statsA.FGA : 0;
      val2 = statsB.FGA > 0 ? (statsB.FGM || 0) / statsB.FGA : 0;
    } else if (dataKey === '3PT%') {
      const tpaA = statsA['3PTA'] || statsA.TPA || 0;
      const tpaB = statsB['3PTA'] || statsB.TPA || 0;
      val1 = tpaA > 0 ? ((statsA['3PTM'] || statsA.TPM || 0) / tpaA) : 0;
      val2 = tpaB > 0 ? ((statsB['3PTM'] || statsB.TPM || 0) / tpaB) : 0;
    } else if (dataKey === 'FT%') {
      val1 = statsA.FTA > 0 ? (statsA.FTM || 0) / statsA.FTA : 0;
      val2 = statsB.FTA > 0 ? (statsB.FTM || 0) / statsB.FTA : 0;
    } else if (dataKey === 'TREB') {
      val1 = statsA.TREB || (statsA.DREB || 0) + (statsA.OREB || 0);
      val2 = statsB.TREB || (statsB.DREB || 0) + (statsB.OREB || 0);
    } else {
      val1 = statsA[dataKey] || 0;
      val2 = statsB[dataKey] || 0;
    }
    
    return val2 - val1; // Descending order
  });
  
  // Re-render with sorted data
  renderRosterStatsTable(rosterPlayersDataForSorting);
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
  const players = teamData.players || roster || [];
  
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

// Listen for tab changes to render Team Report when Team tab is opened
document.addEventListener('DOMContentLoaded', () => {
  const tabButtons = document.querySelectorAll('.tab-buttons button');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === 'team-tab') {
        // Load and render team data when Team tab is opened
        if (!teamData) {
          loadTeamData();
        } else {
          // ✅ FIX: Always reload to ensure fresh data (don't use stale teamData)
          loadTeamData();
        }
      }
    });
  });
});
