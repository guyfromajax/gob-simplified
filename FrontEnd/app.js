
async function simulateGame() {
    const res = await fetch("http://localhost:8000/simulate", {
      method: "POST"
    });
    const data = await res.json();
  
    document.getElementById("score").innerText = 
      `Lancaster: ${data.final_score.Lancaster} | Bentley-Truman: ${data.final_score["Bentley-Truman"]}`;
  
    document.getElementById("quarters").innerText = JSON.stringify(data.points_by_quarter, null, 2);
  
    const lancasterStats = data.box_score.Lancaster;
    let statsText = "";
  
    for (const player in lancasterStats) {
      const stats = lancasterStats[player];
      statsText += `${player} — PTS: ${stats.PTS}, AST: ${stats.AST}, REB: ${stats.REB}, FGA: ${stats.FGA}, FGM: ${stats.FGM}\n`;
    }
  
    document.getElementById("boxScore").innerText = statsText;
  }
  