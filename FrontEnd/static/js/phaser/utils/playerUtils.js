/**
 * Returns the playerId for a given position name (e.g., "PG") from the full player array.
 * @param {string} position - e.g., "PG", "SG", "C"
 * @param {Array} players - The simData.players array
 * @param {string} team - "home" or "away"
 * @returns {string | undefined}
 */
export function getPlayerIdByPosition(position, players, team = "home") {
    const player = players.find(p => p.pos === position && p.team === team);
    return player?.playerId;
  }
  