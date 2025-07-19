let tournament = JSON.parse(localStorage.getItem("activeTournament")) || null;
const userTeamId = (localStorage.getItem("userTeamId") || "").toUpperCase();

const teamAbbreviations = {
  "BENTLEY-TRUMAN": "BT",
  "FOUR CORNERS": "FC",
  "LANCASTER": "Lan",
  "LITTLE YORK": "LY",
  "MORRISTOWN": "Mor",
  "OCEAN CITY": "OC",
  "SOUTH LANCASTER": "SL",
  "XAVIEN": "Xav",
};

function formatTeamName(name) {
  if (!name) return "";
  return name
    .toLowerCase()
    .split(" ")
    .map(w => w.split("-").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join("-"))
    .join(" ");
}

function isUserTeam(teamName) {
  return teamName.toUpperCase() === userTeamId;
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

// tournament is preloaded from localStorage above; will be
// overwritten if fetched again.
// let tournament = null; (replaced)
let roster = [];
let stats = [];

const leaderBoards = [
  { title: "Points", key: "PTS" },
  { title: "3-Pointers Made", key: "TPM" },
  { title: "Rebounds", key: "REB" },
  { title: "Assists", key: "AST" },
  { title: "Steals", key: "STL" },
  { title: "Blocks", key: "BLK" }
];

console.log("✅ tournament.js loaded");

function getLogo(teamName) {
  const formatted = formatTeamName(teamName);
  return `images/homepage-logos/${formatted}.png`;
}

function addTbdRound(bracketEl, count, cls) {
  const div = document.createElement("div");
  div.className = `round ${cls}`;
  for (let i = 0; i < count; i++) {
    const wrap = document.createElement("div");
    wrap.className = "matchup-wrapper";
    const matchup = document.createElement("div");
    matchup.className = "matchup";
    const placeholder = document.createElement("div");
    placeholder.className = "placeholder";
    placeholder.textContent = "TBD";
    matchup.appendChild(placeholder);
    wrap.appendChild(matchup);
    div.appendChild(wrap);
  }
  bracketEl.appendChild(div);
}

function renderBracket() {
  if (!tournament) return;
  const bracket = document.getElementById("bracket");
  bracket.innerHTML = "";

  const round1 = tournament.bracket?.round1 || [];

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

  function createTeamEntry(team, side) {
    const div = document.createElement("div");
    div.className = "team-entry";
    const label = document.createElement("span");
    label.className = `seed-label ${side === "left" ? "seed-left" : "seed-right"}`;
    label.textContent = `#${seedMap[team]}`;
    const img = document.createElement("img");
    img.src = getLogo(team);
    img.classList.add("team-logo", "bracket-logo");
    if (isUserTeam(team)) img.classList.add("user-team");
    if (side === "left") {
      div.appendChild(label);
      div.appendChild(img);
    } else {
      div.appendChild(img);
      div.appendChild(label);
    }
    return div;
  }

  function createMatchup(m, side) {
    const wrap = document.createElement("div");
    wrap.className = "matchup-wrapper";
    const matchup = document.createElement("div");
    matchup.className = "matchup";

    matchup.appendChild(createTeamEntry(m.home_team, side));
    matchup.appendChild(createTeamEntry(m.away_team, side));
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

  leftR1.appendChild(createMatchup(round1[0], "left"));

  // ✨ Insert vertical spacer between matchups
  const leftSpacer = document.createElement("div");
  leftSpacer.style.height = "40px";
  leftSpacer.className = "bracket-spacer";
  leftR1.appendChild(leftSpacer);

  leftR1.appendChild(createMatchup(round1[1], "left"));


  const leftSemi = document.createElement("div");
  leftSemi.className = "round round-2 semifinals";
  leftSemi.appendChild(createPlaceholder());

  const final = document.createElement("div");
  final.className = "round round-3 final";
  final.appendChild(createPlaceholder());

  const rightSemi = document.createElement("div");
  rightSemi.className = "round round-4 semifinals";
  rightSemi.appendChild(createPlaceholder());

  const rightR1 = document.createElement("div");
  rightR1.className = "round round-5 quarterfinals";

  rightR1.appendChild(createMatchup(round1[2], "right"));

  const rightSpacer = document.createElement("div");
  rightSpacer.style.height = "40px";
  rightSpacer.className = "bracket-spacer";
  rightR1.appendChild(rightSpacer);

  rightR1.appendChild(createMatchup(round1[3], "right"));



  bracket.appendChild(leftR1);
  bracket.appendChild(leftSemi);
  bracket.appendChild(final);
  bracket.appendChild(rightSemi);
  bracket.appendChild(rightR1);
}

function renderRoster() {
  const tbody = document.getElementById("roster-body");
  console.log("Inside renderRoster");
  tbody.innerHTML = "";
  roster.forEach(p => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${p.SC}</td><td>${p.SH}</td><td>${p.ID}</td><td>${p.OD}</td>
      <td>${p.PS}</td><td>${p.BH}</td><td>${p.RB}</td><td>${p.ST}</td>
      <td>${p.AG}</td><td>${p.ND}</td><td>${p.IQ}</td><td>${p.FT}</td>`;
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
    for (let i=1;i<=10;i++) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${i}</td><td>Player ${i}</td><td>Team ${String.fromCharCode(64+i)}</td><td>${(20-i).toFixed(1)}</td>`;
      body.appendChild(tr);
    }
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

function initTopAssets() {
  const formattedTeamName = formatTeamName(userTeamId);
  const logoEl = document.getElementById("user-team-logo");
  if (logoEl) {
    logoEl.src = `images/homepage-logos/${formattedTeamName}.png`;
  }
  const abbr = teamAbbreviations[userTeamId] || "";
  const sammy = document.getElementById("coach-sammy");
  const mary = document.getElementById("coach-mary");
  if (sammy) sammy.src = `images/coaches/${abbr}/Sammy-${abbr}.png`;
  if (mary) mary.src = `images/coaches/${abbr}/Mary-${abbr}.png`;
}

async function loadTournament() {
  if (tournament) return;
  try {
    const res = await fetch(`/tournament/active?user_team_id=${encodeURIComponent(userTeamId)}`);
    tournament = await res.json();
    console.log("Bracket data arrives", tournament);
  } catch (err) {
    console.error("Failed to load tournament", err);
  }
}

async function loadRoster() {
  try {
    const res = await fetch(`/teams/${encodeURIComponent(formatTeamName(userTeamId))}/players`);
    const data = await res.json();
    console.log("Team player data loads", data);
    roster = data.players.map(p => Object.assign({ name: p.name }, p.attributes));
    stats = roster.map(p => ({
      name: p.name,
      PTS: 0, FGM: 0, FGA: 0, TPM: 0, TPA: 0,
      FTM: 0, FTA: 0, REB: 0, AST: 0,
      STL: 0, BLK: 0, F: 0, MIN: 0, TO: 0,
    }));
  } catch (err) {
    console.error("Failed to load roster", err);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTopAssets();
  await loadTournament();
  await loadRoster();
  renderBracket();
  renderRoster();
  renderStats();
  renderLeaderboards();

  const playBtn = document.getElementById('play-now');
  if (playBtn) {
    playBtn.addEventListener('click', () => {
      console.log('Play Now clicked (tournament)');
    });
  }
});
