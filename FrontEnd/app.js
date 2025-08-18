
const MAX_LOG_LINES = 500;

async function simulateGame() {
  const team1 = document.getElementById("team1").value;
  const team2 = document.getElementById("team2").value;
  const logContainer = document.getElementById("logContainer");
  const scoreDisplay = document.getElementById("score");

  function addTurnText(text, { prepend = false } = {}) {
    const newNode = document.createElement("div");
    newNode.className = "turn-line";
    newNode.textContent = text;

    if (prepend) {
      const pinned = logContainer.scrollTop <= 5;
      logContainer.insertBefore(newNode, logContainer.firstChild);
      if (pinned) {
        logContainer.scrollTop = 0;
      } else {
        logContainer.scrollTop += newNode.offsetHeight;
      }
    } else {
      logContainer.appendChild(newNode);
    }

    if (MAX_LOG_LINES && logContainer.childElementCount > MAX_LOG_LINES) {
      logContainer.removeChild(logContainer.lastChild);
    }

    return newNode;
  }

  logContainer.innerHTML = "🔄 Simulating game...\n";
  scoreDisplay.textContent = "";

  try {
    const response = await fetch("https://gob-simplified-production.up.railway.app/simulate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        home_team: team1,
        away_team: team2
      })
    });

    if (!response.ok) {
      const error = await response.json();
      logContainer.innerHTML = `❌ Error: ${error.detail || 'Unknown error occurred'}`;
      return;
    }

    const data = await response.json();
    console.log("📦 Full response from backend:", data);
    
    const text_log = data.text_log || [];
    logContainer.innerHTML = ""; // clear previous
    text_log.forEach((turn) => {
      addTurnText(turn.text || JSON.stringify(turn), { prepend: true });
    });


    // text_log.forEach((turn, i) => {
    //   const text = turn.text || `${turn.ball_handler} performs an action.`;
    //   logContainer.innerHTML += `Turn ${i + 1}: ${text}\n`;
    // });

    const score = data.final_score || {};
    scoreDisplay.textContent = `🏁 Final Score — ${team1}: ${score[team1] || 0} | ${team2}: ${score[team2] || 0}`;
  } catch (error) {
    logContainer.innerHTML = `❌ Unexpected error: ${error.message || error}`;
    console.error(error);
  }
}



// function renderBoxScore(boxData, tableId) {
//     const tbody = document.getElementById(tableId);
//     tbody.innerHTML = "";
//     for (let player in boxData) {
//       const stats = boxData[player];
//       const row = document.createElement("tr");
//       row.innerHTML = `
//         <td>${player}</td>
//         <td>${stats.PTS}</td>
//         <td>${stats.REB}</td>
//         <td>${stats.AST}</td>
//         <td>${stats.FGA}</td>
//         <td>${stats.FGM}</td>
//       `;
//       tbody.appendChild(row);
//     }
//   } 

// function renderTeamStats(boxData, tableId) {
//     const totals = {
//         FGM: 0, FGA: 0, "3PTM": 0, "3PTA": 0,
//         FTM: 0, FTA: 0, OREB: 0, DREB: 0, REB: 0, AST: 0
//     };

//     const tbody = document.getElementById(tableId);
//     tbody.innerHTML = ""; // 🧼 Clear it before rendering

//     for (let player in boxData) {
//         for (let key in totals) {
//         totals[key] += boxData[player][key] || 0;
//         }
//     }

//     const row = document.createElement("tr");
//     row.innerHTML = Object.values(totals).map(v => `<td>${v}</td>`).join("");
//     tbody.appendChild(row);
//   }
  

// function renderScoutingReport(data, teamName, containerId) {
//     const container = document.getElementById(containerId);
//     container.innerHTML = `<h3>${teamName}</h3>`;

//     const table = document.createElement("table");
//     table.classList.add("scouting-table");

//     const header = document.createElement("tr");
//     header.innerHTML = "<th>Playcall</th><th>Used</th><th>Success</th>";
//     table.appendChild(header);

//     for (let play in data.offense.Playcalls) {
//         const row = document.createElement("tr");
//         row.innerHTML = `
//         <td>${play}</td>
//         <td>${data.offense.Playcalls[play].used}</td>
//         <td>${data.offense.Playcalls[play].success}</td>
//         `;
//         table.appendChild(row);
//     }

//     const fbRow = document.createElement("tr");
//     fbRow.innerHTML = `
//         <td>Fast Break</td>
//         <td>${data.offense.Fast_Break_Entries}</td>
//         <td>${data.offense.Fast_Break_Success}</td>
//     `;
//     table.appendChild(fbRow);

//     container.appendChild(table);
//     }
  

// async function loadPastGames() {
//     console.log("Fetching past games...");
    
//     try {
//         const response = await fetch("https://gob-simplified-production.up.railway.app/games");
//         console.log("Response:", response);
    
//         const games = await response.json();
//         console.log("Games:", games);
    
//         const container = document.getElementById("pastGamesContainer");
//         container.innerHTML = ""; // Clear loading text
    
//         games.forEach((game, index) => {
//         const p = document.createElement("p");
//         p.innerText = `Game ${index + 1}: Lancaster ${game.final_score.Lancaster} - Bentley-Truman ${game.final_score["Bentley-Truman"]}`;
//         container.appendChild(p);
//         });
//     } catch (error) {
//         console.error("Failed to load past games:", error);
//     }
//     }
      

// if (window.location.pathname.includes("games.html")) {
//     loadPastGames();
//       }
      
      

  
  