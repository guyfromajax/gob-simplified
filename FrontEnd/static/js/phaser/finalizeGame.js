export async function finalizeGame({ simData, tournamentId, franchiseId, game }) {
  // Extract score and winner
  const homeTeamObj = simData.homeTeam || { name: simData.home_team };
  const awayTeamObj = simData.awayTeam || { name: simData.away_team };
  const scoreMap = simData.final_score || simData.score || {};
  const homeScore = homeTeamObj.score ?? scoreMap[homeTeamObj.name] ?? 0;
  const awayScore = awayTeamObj.score ?? scoreMap[awayTeamObj.name] ?? 0;
  const winner = homeScore > awayScore ? homeTeamObj.name : awayTeamObj.name;

  // POST to /tournament/save-result if needed
  if (tournamentId) {
    try {
      const res = await fetch("/tournament/save-result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_id: tournamentId,
          game_id: simData._id,
          winner: winner,
        }),
      });
      if (!res.ok) {
        console.error("❌ Failed to save tournament result:", await res.text());
      } else {
        console.log("✅ Tournament result saved.");
      }
    } catch (err) {
      console.error("🚨 Error during tournament result save:", err);
    }
  }

  // POST to /franchise/save-result if needed
  if (franchiseId) {
    try {
      const res = await fetch("/franchise/save-result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          franchise_id: franchiseId,
          game_id: simData._id,
          winner: winner,
        }),
      });
      if (!res.ok) {
        console.error("❌ Failed to save franchise result:", await res.text());
      } else {
        console.log("✅ Franchise result saved.");
      }
    } catch (err) {
      console.error("🚨 Error during franchise result save:", err);
    }
  }

  const finalScore = {
    homeTeam: homeTeamObj.name,
    awayTeam: awayTeamObj.name,
    homeScore,
    awayScore,
    winner,
    homeTeamData: homeTeamObj,
    awayTeamData: awayTeamObj,
  };

  if (game && game.events) {
    game.events.emit("gameComplete", finalScore);
  }

  return finalScore;
}
