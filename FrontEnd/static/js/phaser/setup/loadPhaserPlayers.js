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
    playerSprites[player.playerId] = sprite;
  }

  return playerSprites;
}
