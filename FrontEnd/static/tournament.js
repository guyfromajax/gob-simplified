const userTeamId = "BENTLEY-TRUMAN";

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

let tournament = null;
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
  return `images/bracket-logos/${logoMap[teamName] || `${teamName}-Horizontal.svg`}`;
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
  const r1Div = document.createElement("div");
  r1Div.className = "round quarterfinals";

  round1.forEach(m => {
    const wrap = document.createElement("div");
    wrap.className = "matchup-wrapper";
    const matchup = document.createElement("div");
    matchup.className = "matchup";

    const imgA = document.createElement("img");
    imgA.src = getLogo(m.home_team);
    imgA.classList.add("upcoming");

    const imgB = document.createElement("img");
    imgB.src = getLogo(m.away_team);
    imgB.classList.add("upcoming");

    matchup.appendChild(imgA);
    matchup.appendChild(imgB);
    wrap.appendChild(matchup);
    r1Div.appendChild(wrap);
  });

  bracket.appendChild(r1Div);

  const round2Count = Math.ceil(round1.length / 2);
  addTbdRound(bracket, round2Count, "semifinals");
  addTbdRound(bracket, 1, "final");
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

async function loadTournament() {
  try {
    const res = await fetch(`/tournament/active`);
    tournament = await res.json();
    console.log("Bracket data arrives", tournament);
  } catch (err) {
    console.error("Failed to load tournament", err);
  }
}

async function loadRoster() {
  try {
    const res = await fetch(`/teams/${userTeamId}/players`);
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
  await loadTournament();
  await loadRoster();
  renderBracket();
  renderRoster();
  renderStats();
  renderLeaderboards();
});
