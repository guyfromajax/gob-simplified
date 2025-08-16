export async function finalizeGame({ simData, tournamentId, franchiseId, game }) {
  // Extract score and winner
  const homeTeamObj = simData.homeTeam || { name: simData.home_team };
  const awayTeamObj = simData.awayTeam || { name: simData.away_team };
  const scoreMap = simData.final_score || simData.score || {};
  const homeScore = homeTeamObj.score ?? scoreMap[homeTeamObj.name] ?? 0;
  const awayScore = awayTeamObj.score ?? scoreMap[awayTeamObj.name] ?? 0;
  const winner = homeScore > awayScore ? homeTeamObj.name : awayTeamObj.name;
  const params = new URLSearchParams(window.location.search);
  let week = parseInt(params.get('week'), 10);
  const homeIdParam = params.get('home_id');
  const awayIdParam = params.get('away_id');
  if (!week || Number.isNaN(week)) {
    if (typeof localStorage !== 'undefined') {
      week = parseInt(localStorage.getItem('franchise_week'), 10);
    }
  }
  if (!week || Number.isNaN(week)) {
    if (simData && simData.week) {
      week = parseInt(simData.week, 10);
    }
  }

  // POST to /tournament/save-result if needed
  if (tournamentId) {
    try {
      const res = await fetch("/tournament/save-result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_id: tournamentId,
          game_id: simData.game_id || simData._id,
          winner: winner,
        }),
      });
      if (!res.ok) {
        console.error("❌ Failed to save tournament result:", await res.text());
      } else {
        console.log("✅ Tournament result saved.");
        try {
          const updated = await fetch(`/tournament/state/${tournamentId}`).then((r) =>
            r.json()
          );
          localStorage.setItem("activeTournament", JSON.stringify(updated));
          if (window && window.opener) {
            if (typeof window.opener.refreshTeamStats === "function") {
              window.opener.refreshTeamStats();
            }
            if (typeof window.opener.refreshLeaders === "function") {
              window.opener.refreshLeaders();
            }
          } else {
            if (typeof window.refreshTeamStats === "function") {
              window.refreshTeamStats();
            } else {
              window.location.href = "/static/tournament.html";
            }
          }
        } catch (e) {
          console.error("Failed to trigger parent refresh", e);
        }
      }
    } catch (err) {
      console.error("🚨 Error during tournament result save:", err);
    }
  }

  // POST to /franchise/complete-week if needed
  if (franchiseId && Number.isInteger(week) && week >= 1) {
    try {
      const team1Id =
        awayIdParam ||
        awayTeamObj.team_id ||
        awayTeamObj.teamId ||
        simData.away_team_id ||
        simData.awayTeamId ||
        awayTeamObj.name ||
        simData.away_team;
      const team2Id =
        homeIdParam ||
        homeTeamObj.team_id ||
        homeTeamObj.teamId ||
        simData.home_team_id ||
        simData.homeTeamId ||
        homeTeamObj.name ||
        simData.home_team;
      console.log(
        `📡 Saving franchise game: franchiseId=${franchiseId}, week=${week}, away=${awayTeamObj.name}, home=${homeTeamObj.name}`
      );
      const res = await fetch("/franchise/complete-week", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          franchise_id: franchiseId,
          week: week,
          result: {
            team1_id: team1Id,
            team2_id: team2Id,
            team1_score: awayScore,
            team2_score: homeScore,
          },
        }),
      });
      if (!res.ok) {
        console.error("❌ Failed to complete franchise week:", await res.text());
      } else {
        console.log("✅ Franchise week completed.");
      }
    } catch (err) {
      console.error("🚨 Error during franchise week completion:", err);
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
