import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';

// ✅ STEP 1: Read tournament info from URL
const urlParams = new URLSearchParams(window.location.search);
const tournamentId = urlParams.get("tournament_id");
const homeTeam = urlParams.get("home");
const awayTeam = urlParams.get("away");

console.log("🏀 Tournament launch params:", {
  tournamentId,
  homeTeam,
  awayTeam
});

const GameScene = createGameScene(Phaser);  // ✅ Moved this up

async function fetchTeamRoster(teamName) {
  const res = await fetch(`/roster/${encodeURIComponent(teamName)}`);
  if (!res.ok) {
    throw new Error(`Failed to load roster for ${teamName}`);
  }
  return res.json();
}

async function initTournamentGame() {
  if (!homeTeam || !awayTeam) {
    console.error("Missing team data in URL");
    return;
  }

  const [homeRoster, awayRoster] = await Promise.all([
    fetchTeamRoster(homeTeam),
    fetchTeamRoster(awayTeam)
  ]);

  console.log("✅ Loaded rosters:", { homeRoster, awayRoster });

  new Phaser.Game({
    type: Phaser.AUTO,
    width: 1229,
    height: 768,
    backgroundColor: "#1e1e1e",
    parent: "phaser-container",
    scene: [GameScene],
    rosters: { homeRoster, awayRoster },
    tournamentId
  });
}

initTournamentGame();  // ✅ This stays last


// new Phaser.Game(config);



