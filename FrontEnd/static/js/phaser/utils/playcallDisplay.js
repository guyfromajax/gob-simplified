/**
 * Updates the playcall display in the scoreboard
 * @param {Object} turnData - The current turn data
 * @param {string} homeTeamId - Home team ID
 */
export function updatePlaycallDisplay(turnData, homeTeamId) {
  const offensivePlaycallEl = document.getElementById('offensive-playcall');
  const defensivePlaycallEl = document.getElementById('defensive-playcall');
  
  if (!offensivePlaycallEl || !defensivePlaycallEl) {
    return;
  }
  
  // Only show playcalls for HCO turns
  const isHCO = turnData.offensive_state === 'HCO' || 
                (!turnData.offensive_state && !turnData.fast_break && turnData.result_type !== 'OPENING_TIP');
  
  if (!isHCO) {
    offensivePlaycallEl.textContent = '-';
    defensivePlaycallEl.textContent = '-';
    return;
  }
  
  // Get playcalls from turn data
  const offensivePlaycall = turnData.offensive_playcall || turnData.current_playcall;
  const defensivePlaycall = turnData.defensive_playcall || turnData.defense_playcall;
  
  // Determine which team is on offense
  const offenseTeamId = turnData.possession_team_id || turnData.starting_possession_team_id;
  const isHomeOnOffense = String(offenseTeamId) === String(homeTeamId);
  
  // Display playcalls based on possession
  if (isHomeOnOffense) {
    // Home on offense - offensive playcall on home side (right), defensive on away side (left)
    offensivePlaycallEl.textContent = formatPlaycall(offensivePlaycall);
    defensivePlaycallEl.textContent = formatPlaycall(defensivePlaycall);
  } else {
    // Away on offense - offensive playcall on away side (left), defensive on home side (right)
    defensivePlaycallEl.textContent = formatPlaycall(offensivePlaycall);
    offensivePlaycallEl.textContent = formatPlaycall(defensivePlaycall);
  }
  
  console.log('🎯 Playcalls updated:', {
    offense: offensivePlaycall,
    defense: defensivePlaycall,
    isHomeOnOffense,
    turnType: turnData.result_type
  });
}

/**
 * Format playcall name for display
 * @param {string} playcall - Raw playcall name
 * @returns {string} Formatted playcall
 */
function formatPlaycall(playcall) {
  if (!playcall) return '-';
  
  // Convert from snake_case or other formats to Title Case
  return playcall
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Clear playcall display
 */
export function clearPlaycallDisplay() {
  const offensivePlaycallEl = document.getElementById('offensive-playcall');
  const defensivePlaycallEl = document.getElementById('defensive-playcall');
  
  if (offensivePlaycallEl) offensivePlaycallEl.textContent = '-';
  if (defensivePlaycallEl) defensivePlaycallEl.textContent = '-';
}

