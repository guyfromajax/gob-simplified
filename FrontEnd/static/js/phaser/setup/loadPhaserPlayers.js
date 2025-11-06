import { createPhaserPlayer } from "./createPhaserPlayer.js";
import gameStore from "../../state/gameStore.js";

/**
 * Creates Phaser player containers for all players and stores them by ID.
 * 
 * @param {Phaser.Scene} scene - The active Phaser scene
 * @param {Array} allPlayers - Array of player objects from simData
 * @param {Object} [teamInfo] - Optional colors; defaults to gameStore values
 * @returns {Object} Map of playerId -> Phaser container
 */
export function loadPhaserPlayers(
  scene,
  allPlayers,
  teamInfoOrPhaser,
  maybePhaser
) {
  let teamInfo = teamInfoOrPhaser;
  let PhaserLib = maybePhaser;
  if (typeof maybePhaser === "undefined") {
    PhaserLib = teamInfoOrPhaser;
    teamInfo = null;
  }

  if (!teamInfo) {
    const colors = gameStore.getColors();
    teamInfo = {
      home: {
        player_ids: allPlayers
          .filter(p => p.team === "home")
          .map(p => p.playerId ?? p.player_id),
        ...colors.home,
      },
      away: {
        player_ids: allPlayers
          .filter(p => p.team === "away")
          .map(p => p.playerId ?? p.player_id),
        ...colors.away,
      },
    };
  }

  const playerSprites = {};

  console.log('loadPhaserPlayers DEBUG:', {
    totalPlayers: allPlayers.length,
    allPlayers: allPlayers.map(p => ({ 
      id: p.playerId ?? p.player_id, 
      name: p.name, 
      team: p.team, 
      pos: p.pos 
    }))
  });

  for (const player of allPlayers) {
    const id = player.playerId ?? player.player_id;
    
    // Skip the ball - it shouldn't be a player sprite
    if (id === "ball" || id === "Ball" || player.name === "ball" || player.name === "Ball") {
      console.warn(`Skipping ball object from player sprites: ${id}`, player);
      continue;
    }
    
    const isHome = teamInfo.home.player_ids.includes(id) || player.team === "home";
    const teamColors = isHome ? teamInfo.home : teamInfo.away;

    console.log(`Creating sprite for player: ${id}`, {
      name: player.name,
      team: player.team,
      pos: player.pos,
      isHome,
      teamColors: teamColors.primary_color
    });

    const sprite = createPhaserPlayer({
      scene,
      player,
      teamInfo: {
        ...teamColors,
        isHome
      },
      position: player.pos,
      Phaser: PhaserLib
    });
    // ✅ Attach team metadata for later logic
    sprite.team_id = player.team_id; // e.g., "MORRISTOWN"
    sprite.team = player.team;       // e.g., "home" or "away"
    sprite.playerId = id;
    sprite.jersey = player.jersey;   // Jersey number
    sprite.name = player.name;       // Full name

    playerSprites[id] = sprite;
  }
  console.log("👾 playerSprites keys:", Object.keys(playerSprites));

  return playerSprites;
}
