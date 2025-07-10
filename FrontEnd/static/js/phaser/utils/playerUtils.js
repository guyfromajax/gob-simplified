/**
 * Returns the playerId for a given position name (e.g., "PG") from the full player array.
 * @param {string} position - e.g., "PG", "SG", "C"
 * @param {Array} players - The simData.players array
 * @returns {string | undefined}
 */
export function getPlayerIdByPosition(position, players) {
    const player = players.find(p => p.positionName === position);
    return player?.playerId;
  }
  