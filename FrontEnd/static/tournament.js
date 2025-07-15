// Placeholder data for Tournament Mode
const userTeamId = "BENTLEY-TRUMAN";

// Map team names to actual logo filenames when they do not
// follow the standard <Team>-Horizontal.svg format
const logoMap = {
  "Ocean": "Ocean-Horizontal (1).svg",
  "Xavien": "Xavien-Horizontal (1).svg"
};

const bracketData = [
  { round: 1, matchups: [
      { teamA: "Bently", teamB: "Corners", winner: "Bently" },
      { teamA: "Lancaster", teamB: "Morristown", winner: "Lancaster" },
      { teamA: "Ocean", teamB: "South", upcoming: true },
      { teamA: "Xavien", teamB: "York" }
  ]},
  { round: 2, matchups: [
      { teamA: "Bently", teamB: "Lancaster" },
      { teamA: "South", teamB: "York" }
  ]},
  { round: 3, matchups: [
      { teamA: "Bently", teamB: "South", champion: true }
  ]}
];

const roster = Array.from({ length: 12 }, (_, i) => ({
  name: `Player ${i+1}`,
  SC: 70 + (i % 5), SH: 72 + (i % 5), ID: 68 + (i % 5), OD: 69 + (i % 5),
  PS: 70 + (i % 5), BH: 71 + (i % 5), RB: 65 + (i % 5), ST: 60 + (i % 5),
  AG: 75 + (i % 5), ND: 70 + (i % 5), IQ: 80 + (i % 5), FT: 75 + (i % 5)
}));

const stats = roster.map(p => ({ name: p.name, PTS: 0, FGM: 0, FGA: 0,
  TPM: 0, TPA: 0, FTM: 0, FTA: 0, REB: 0, AST: 0, STL: 0, BLK: 0,
  F: 0, MIN: 0, TO: 0 }));

const leaderBoards = [
  { title: "Points", key: "PTS" },
  { title: "3-Pointers Made", key: "TPM" },
  { title: "Rebounds", key: "REB" },
  { title: "Assists", key: "AST" },
  { title: "Steals", key: "STL" },
  { title: "Blocks", key: "BLK" }
];

function renderBracket() {
  const bracket = document.getElementById("bracket");
  bracket.innerHTML = "";
  bracketData.forEach(round => {
    const roundDiv = document.createElement("div");
    roundDiv.className = round.round === 1 ? "round quarterfinals" :
      round.round === 2 ? "round semifinals" : "round final";

    round.matchups.forEach(m => {
      const wrap = document.createElement("div");
      wrap.className = "matchup-wrapper";
      const matchup = document.createElement("div");
      matchup.className = "matchup";
      if (m.champion) matchup.classList.add("champion");

      const imgA = document.createElement("img");
      imgA.src = `images/bracket-logos/${logoMap[m.teamA] || `${m.teamA}-Horizontal.svg`}`;
      const imgB = document.createElement("img");
      imgB.src = `images/bracket-logos/${logoMap[m.teamB] || `${m.teamB}-Horizontal.svg`}`;

      if (m.winner === m.teamA) imgA.classList.add("winner");
      if (m.winner === m.teamB) imgB.classList.add("winner");
      if (m.upcoming) {
        imgA.classList.add("upcoming");
        imgB.classList.add("upcoming");
      }

      matchup.appendChild(imgA);
      matchup.appendChild(imgB);
      wrap.appendChild(matchup);
      roundDiv.appendChild(wrap);
    });
    bracket.appendChild(roundDiv);
  });
}

function renderRoster() {
  const tbody = document.getElementById("roster-body");
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

document.addEventListener("DOMContentLoaded", () => {
  renderBracket();
  renderRoster();
  renderStats();
  renderLeaderboards();

  const tbody = document.querySelector('#team-tab table.roster-table tbody');
  const testRow = `
    <tr>
      <td>Test Player</td>
      <td>80</td><td>75</td><td>70</td><td>72</td><td>68</td>
      <td>74</td><td>65</td><td>60</td><td>78</td><td>70</td>
      <td>85</td><td>76</td>
    </tr>`;
  tbody.innerHTML += testRow;
});
