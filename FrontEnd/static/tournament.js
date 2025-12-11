let tournament = JSON.parse(localStorage.getItem("activeTournament")) || null;
let userTeamId = localStorage.getItem("userTeamId") || "";

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
  return teamName === userTeamId;
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
}

function renderStats() {
  const tbody = document.getElementById("stats-body");
  console.log("Inside renderStats");
  tbody.innerHTML = "";
  stats.forEach(s => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.name}</td><td>${s.PTS}</td><td>${s.FGM}/${s.FGA}</td>
      <td>${s.TPM}/${s.TPA}</td><td>${s.FTM}/${s.FTA}</td><td>${s.REB}</td>
      <td>${s.AST}</td><td>${s.STL}</td><td>${s.BLK}</td><td>${s.F}</td>
      <td>${s.MIN}</td><td>${s.TO}</td>`;
    tbody.appendChild(tr);
  });
}

function renderLeaderboards() {
  const container = document.getElementById("leaderboards");
  container.innerHTML = "";
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
        tr.innerHTML = `<td>${entry.rank}</td><td>${entry.first_name} ${entry.last_name}</td><td>${entry.team_name}</td><td>${entry.value}</td>`;
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
}

window.refreshLeaders = refreshLeaders;

function updateCTA() {
  const playBtn = document.getElementById('play-now');
  const simBtn = document.getElementById('sim-remaining');
  const exitBtn = document.getElementById('exit-tournament');
  const container = document.querySelector ? document.querySelector('.play-now-container') : null;
  const opponentEl = document.getElementById('play-now-opponent');
  if (!container || !playBtn || !simBtn || !exitBtn || !tournament || !opponentEl) return;

  if (tournament.completed) {
    playBtn.style.display = 'none';
    simBtn.style.display = 'none';
    simBtn.disabled = true;
    container.style.display = 'none';
    exitBtn.style.display = 'inline-block';
    opponentEl.textContent = '';
    return;
  }

  exitBtn.style.display = 'none';
  container.style.display = 'block';

  const roundKey = tournament.current_round === 3 ? 'final' : `round${tournament.current_round}`;
  const matchups = tournament.bracket?.[roundKey] || [];
  const userMatch = matchups.find(m => m.home_team === userTeamId || m.away_team === userTeamId);

  // user is out of the tournament when no matchup exists or their matchup is finished
  const eliminated = !userMatch || !!userMatch.winner;
  if (eliminated) {
    playBtn.style.display = 'none';
    opponentEl.textContent = '';
    simBtn.style.display = 'inline-block';
    simBtn.disabled = false;
    return;
  }

  if (!userMatch.game_id) {
    const opponent = userMatch.home_team === userTeamId ? userMatch.away_team : userMatch.home_team;
    playBtn.style.display = 'inline-flex';
    opponentEl.textContent = `vs ${opponent}`;
    simBtn.style.display = 'none';
    simBtn.disabled = true;
  } else {
    playBtn.style.display = 'none';
    opponentEl.textContent = '';
    simBtn.style.display = 'inline-block';
    simBtn.disabled = false;
  }
}

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

async function loadTournament() {
  try {
    let url;
    if (tournament && tournament._id) {
      url = `/tournament/state/${encodeURIComponent(tournament._id)}`;
    } else {
      url = `/tournament/active?user_team_id=${encodeURIComponent(userTeamId)}`;
    }
    const res = await fetch(`${url}?_=${Date.now()}`, { cache: "no-store" });
    tournament = await res.json();
    localStorage.setItem("activeTournament", JSON.stringify(tournament));
    console.log("Bracket data arrives", tournament);
  } catch (err) {
    console.error("Failed to load tournament", err);
  }
}

async function loadRoster() {
  try {
    console.log('Loading tournament roster for userTeamId:', userTeamId);
    if (!userTeamId) {
      console.error('No userTeamId found - cannot load roster');
      return;
    }
    // Include tournament_id if available to load tournament-specific attributes
    const tournamentId = tournament?._id;
    const url = tournamentId 
      ? `/teams/${encodeURIComponent(formatTeamName(userTeamId))}/players?tournament_id=${encodeURIComponent(tournamentId)}`
      : `/teams/${encodeURIComponent(formatTeamName(userTeamId))}/players`;
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
    const pstats = tournament?.player_stats || {};
    stats = roster.map(p => {
      const season = pstats[p.id]?.stats?.Season || {};
      const row = { name: p.name };
      statKeys.forEach(k => {
        const val = season[k];
        row[k] = typeof val === 'number' ? val : 0;
      });
      return row;
    });
    if (DEBUG_TEAM_STATS && roster[0]) {
      const first = roster[0];
      const s = pstats[first.id]?.stats?.Season || {};
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
  renderRoster();
  renderStats();
  updateCTA();
}

window.handleTournamentUpdate = handleTournamentUpdate;

document.addEventListener("DOMContentLoaded", async () => {
  await loadTournament();
  if (!userTeamId && tournament && tournament.user_team_id) {
    userTeamId = tournament.user_team_id;
    localStorage.setItem("userTeamId", tournament.user_team_id);
  }
  initTopAssets(userTeamId);
  updateTeamChemistry();
  await loadRoster();
  renderBracket();
  renderRoster();
  renderStats();
  await refreshLeaders();
  updateCTA();

  const playBtn = document.getElementById('play-now');
  if (playBtn) {
    playBtn.addEventListener('click', async () => {
      if (!tournament || !tournament._id) {
        alert('Tournament not loaded');
        return;
      }
      playBtn.disabled = true;
      try {
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
        const mySide = home === userTeamId ? 'home' : (away === userTeamId ? 'away' : '');
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
      
      // Redirect to Game Plan screen with tournament context
      const url = `/game-plan.html?mode=tournament&tournament_id=${encodeURIComponent(tournament._id)}&user_team_id=${encodeURIComponent(userTeamId)}&from=command_center`;
      window.location.href = url;
    });
  }

  // Playbooks button (Tournament Command Center)
  const playbooksBtn = document.getElementById('playbooks-tournament');
  if (playbooksBtn) {
    playbooksBtn.addEventListener('click', () => {
      window.location.href = '/static/play-builder-v2.html';
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
