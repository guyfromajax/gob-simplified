/**
 * Auto-set lineup utility for simulations
 * Reusable logic for automatically generating optimal lineups
 */

/**
 * Generate an auto-set lineup for a team
 * @param {Array} roster - Array of player objects with position_ratings
 * @returns {Object} Lineup object with position keys (PG, SG, SF, PF, C) mapped to player IDs
 */
export function generateAutoSetLineup(roster) {
  if (!roster || roster.length === 0) {
    console.warn('⚠️ generateAutoSetLineup: No roster provided');
    return {};
  }
  
  const lineup = {};
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  
  // Randomize position order for variety
  const shuffledPositions = positions.sort(() => Math.random() - 0.5);
  
  // Track which players have been assigned
  const assignedPlayers = new Set();
  
  // For each position in random order
  shuffledPositions.forEach(pos => {
    // Get available players (not already assigned AND NG >= 0.8 AND not ineligible)
    const availablePlayers = roster.filter(p => {
      const playerId = p._id || p.player_id || p.playerId;
      const ng = p.NG ?? p.attributes?.NG ?? 1.0;
      const isIneligible = p.ineligible || p.fouled_out;
      return !assignedPlayers.has(playerId) && ng >= 0.8 && !isIneligible;
    });
    
    // Get players with ratings for this position, sorted by rating desc
    const playersWithRating = availablePlayers
      .map(p => ({
        player: p,
        rating: p.position_ratings?.[pos] ?? -Infinity
      }))
      .filter(({ rating }) => rating !== -Infinity)
      .sort((a, b) => b.rating - a.rating);
    
    // Take top 3 (or all if fewer than 3)
    const topCandidates = playersWithRating.slice(0, 3);
    
    // Randomly pick one from top candidates
    if (topCandidates.length > 0) {
      const randomIndex = Math.floor(Math.random() * topCandidates.length);
      const { player } = topCandidates[randomIndex];
      
      const playerId = player._id || player.player_id || player.playerId;
      lineup[pos] = playerId;
      assignedPlayers.add(playerId);
    } else if (availablePlayers.length > 0) {
      // Fallback: if no ratings available, pick first available player
      const player = availablePlayers[0];
      const playerId = player._id || player.player_id || player.playerId;
      lineup[pos] = playerId;
      assignedPlayers.add(playerId);
    }
  });
  
  console.log('🤖 Auto-set lineup generated:', lineup);
  return lineup;
}

/**
 * Generate auto-set lineups for both teams
 * @param {Object} homeRoster - Home team roster
 * @param {Object} awayRoster - Away team roster
 * @returns {Object} { home_lineup, away_lineup }
 */
export function generateBothLineups(homeRoster, awayRoster) {
  const homeLineup = generateAutoSetLineup(homeRoster?.players || homeRoster);
  const awayLineup = generateAutoSetLineup(awayRoster?.players || awayRoster);
  
  return {
    home_lineup: homeLineup,
    away_lineup: awayLineup
  };
}

