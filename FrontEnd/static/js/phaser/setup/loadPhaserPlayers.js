import { createPhaserPlayer } from "./createPhaserPlayer.js";

/**
 * Creates Phaser player containers for all players and stores them by ID.
 * 
 * @param {Phaser.Scene} scene - The active Phaser scene
 * @param {Array} allPlayers - Array of player objects from simData
 * @param {Object} teamInfo - { home: { colors }, away: { colors } }
 * @returns {Object} Map of playerId -> Phaser container
 */
export function loadPhaserPlayers(scene, allPlayers, teamInfo, Phaser) {
  const playerSprites = {};

  for (const player of allPlayers) {
    const isHome = teamInfo.home.player_ids.includes(player.playerId);
    const teamColors = isHome ? teamInfo.home : teamInfo.away;
    
    const sprite = createPhaserPlayer({
      scene,
      player,
      teamInfo: {
        ...teamColors,
        isHome
      },
      position: player.pos,
      Phaser
    });
    // ✅ Attach team metadata for later logic
    sprite.team_id = player.team_id; // e.g., "MORRISTOWN"
    sprite.team = player.team;       // e.g., "home" or "away"
    
    playerSprites[player.playerId] = sprite;
  }
  // console.log("👾 playerSprites keys:", Object.keys(playerSprites));

  return playerSprites;
}
