
async function simulateGame() {
    const mode = document.getElementById("modeSelect").value;
    const gamesToPlay = mode === "bo3" ? 3 : 1;

    console.log("Selected mode:", mode);
    console.log("Games to play:", gamesToPlay);

    let wins = { Lancaster: 0, "Bentley-Truman": 0 };
    let latestGameData = null;
  
    // Clear previous UI
    document.getElementById("teamStatsLancaster").innerHTML = "";
    document.getElementById("teamStatsBT").innerHTML = "";
    document.getElementById("lancasterBox").innerHTML = "";
    document.getElementById("btBox").innerHTML = "";
    document.getElementById("quarterScores").innerHTML = "";
    document.getElementById("logContainer").innerHTML = "";

  
    for (let i = 0; i < gamesToPlay; i++) {
      console.log(`Simulating game ${i + 1}...`);
      document.getElementById("logContainer").innerHTML += `<div>🟢 Game ${i + 1} starting...</div>`;

      const res = await fetch("https://gob-simplified-production.up.railway.app/simulate", {
        method: "POST"
      });
      const data = await res.json();
      latestGameData = data;
      
      const lScore = data.final_score.Lancaster;
      const btScore = data.final_score["Bentley-Truman"];
      if (lScore > btScore) wins.Lancaster++;
      else if (btScore > lScore) wins["Bentley-Truman"]++;
      console.log(`Lancaster: ${lScore} | Bentley-Truman: ${btScore}`);
      document.getElementById("logContainer").innerHTML += `<div>🏀 Final Score: Lancaster ${lScore} – Bentley-Truman ${btScore}</div>`;
      const logContainer = document.getElementById("logContainer");
      logContainer.scrollTop = logContainer.scrollHeight;


    }
    console.log("Final series result:", wins);
    document.getElementById("logContainer").innerHTML += `<div><strong>🏆 Series Result: Lancaster ${wins.Lancaster} – Bentley-Truman ${wins["Bentley-Truman"]}</strong></div>`;

  
    const data = latestGameData;
  
    // Show result summary
    const scoreText = gamesToPlay > 1
      ? `Series Result: Lancaster ${wins.Lancaster} - Bentley-Truman ${wins["Bentley-Truman"]}`
      : `Lancaster: ${data.final_score.Lancaster} | Bentley-Truman: ${data.final_score["Bentley-Truman"]}`;
  
    document.getElementById("score").innerText = scoreText;
  
    // Render final game only
    const quarters = data.points_by_quarter;
    const tbody = document.getElementById("quarterScores");
    for (let team in quarters) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${team}</td>
        <td>${quarters[team][0]}</td>
        <td>${quarters[team][1]}</td>
        <td>${quarters[team][2]}</td>
        <td>${quarters[team][3]}</td>
      `;
      tbody.appendChild(row);
    }
  
    renderBoxScore(data.box_score.Lancaster, "lancasterBox");
    renderBoxScore(data.box_score["Bentley-Truman"], "btBox");
  
    renderTeamStats(data.box_score.Lancaster, "teamStatsLancaster");
    renderTeamStats(data.box_score["Bentley-Truman"], "teamStatsBT");
  
    renderScoutingReport(data.scouting.Lancaster, "Lancaster", "scoutingLancaster");
    renderScoutingReport(data.scouting["Bentley-Truman"], "Bentley-Truman", "scoutingBT");
  }
  

function renderBoxScore(boxData, tableId) {
    const tbody = document.getElementById(tableId);
    tbody.innerHTML = "";
    for (let player in boxData) {
      const stats = boxData[player];
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${player}</td>
        <td>${stats.PTS}</td>
        <td>${stats.REB}</td>
        <td>${stats.AST}</td>
        <td>${stats.FGA}</td>
        <td>${stats.FGM}</td>
      `;
      tbody.appendChild(row);
    }
  } 

function renderTeamStats(boxData, tableId) {
    const totals = {
        FGM: 0, FGA: 0, "3PTM": 0, "3PTA": 0,
        FTM: 0, FTA: 0, OREB: 0, DREB: 0, REB: 0, AST: 0
    };

    const tbody = document.getElementById(tableId);
    tbody.innerHTML = ""; // 🧼 Clear it before rendering

    for (let player in boxData) {
        for (let key in totals) {
        totals[key] += boxData[player][key] || 0;
        }
    }

    const row = document.createElement("tr");
    row.innerHTML = Object.values(totals).map(v => `<td>${v}</td>`).join("");
    tbody.appendChild(row);
  }
  

function renderScoutingReport(data, teamName, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<h3>${teamName}</h3>`;

    const table = document.createElement("table");
    table.classList.add("scouting-table");

    const header = document.createElement("tr");
    header.innerHTML = "<th>Playcall</th><th>Used</th><th>Success</th>";
    table.appendChild(header);

    for (let play in data.offense.Playcalls) {
        const row = document.createElement("tr");
        row.innerHTML = `
        <td>${play}</td>
        <td>${data.offense.Playcalls[play].used}</td>
        <td>${data.offense.Playcalls[play].success}</td>
        `;
        table.appendChild(row);
    }

    const fbRow = document.createElement("tr");
    fbRow.innerHTML = `
        <td>Fast Break</td>
        <td>${data.offense.Fast_Break_Entries}</td>
        <td>${data.offense.Fast_Break_Success}</td>
    `;
    table.appendChild(fbRow);

    container.appendChild(table);
    }
  
async function fetchPastGames() {
    const res = await fetch("https://gob-simplified-production.up.railway.app/games");
    const games = await res.json();

    const container = document.getElementById("pastGamesContainer");
    container.innerHTML = "";
    games.forEach((game, i) => {
        container.innerHTML += `<p><strong>Game ${i + 1}</strong>: ${game.final_score.Lancaster} - ${game.final_score["Bentley-Truman"]}</p>`;
    });
    }

window.onload = () => {
    fetchPastGames();
    };
      

  
  