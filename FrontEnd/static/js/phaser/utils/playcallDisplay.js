/**
 * Updates the playcall display in the scoreboard
 * @param {Object} turnData - The current turn data
 * @param {string} homeTeamId - Home team ID
 */
export function updatePlaycallDisplay(turnData, homeTeamId) {
  const offensivePlaycallEl = document.getElementById('offensive-playcall');
  const defensivePlaycallEl = document.getElementById('defensive-playcall');
  const offensiveFocusDotsEl = document.getElementById('offensive-playcall-focus-dots');
  const defensiveFocusDotsEl = document.getElementById('defensive-playcall-focus-dots');
  
  if (!offensivePlaycallEl || !defensivePlaycallEl) {
    return;
  }
  
  // Only show playcalls for HCO turns
  const isHCO = turnData.offensive_state === 'HCO' || 
                (!turnData.offensive_state && !turnData.fast_break && turnData.result_type !== 'OPENING_TIP');
  
  if (!isHCO) {
    offensivePlaycallEl.textContent = '-';
    defensivePlaycallEl.textContent = '-';
    // Clear focus dots
    if (offensiveFocusDotsEl) clearFocusDots(offensiveFocusDotsEl);
    if (defensiveFocusDotsEl) clearFocusDots(defensiveFocusDotsEl);
    return;
  }
  
  // Get playcalls from turn data
  const offensivePlaycall = turnData.offensive_playcall || turnData.current_playcall;
  const defensivePlaycall = turnData.defensive_playcall || turnData.defense_playcall;
  
  // Get play type and focus directly from turn data if available, otherwise extract from playcall name
  const offensivePlayType = turnData.offensive_play_type || getPlayType(offensivePlaycall);
  const offensivePlayFocus = turnData.offensive_play_focus || getPlayFocus(offensivePlaycall);
  const defensivePlayType = turnData.defensive_play_type || getPlayType(defensivePlaycall);
  const defensivePlayFocus = turnData.defensive_play_focus || getPlayFocus(defensivePlaycall);
  
  // Determine which team is on offense
  const offenseTeamId = turnData.possession_team_id;
  const isHomeOnOffense = String(offenseTeamId) === String(homeTeamId);
  
  // Display playcalls based on possession
  // Note: offensive-playcall element is on HOME side, defensive-playcall element is on AWAY side
  if (isHomeOnOffense) {
    // Home on offense - show defensive playcall on home side (right), offensive on away side (left)
    offensivePlaycallEl.textContent = defensivePlayType || "-"; // Show Man/Zone for defense
    // ✅ FIX: Display full playcall name (e.g., "3-2 Motion") instead of just play type ("Motion")
    defensivePlaycallEl.textContent = offensivePlaycall || offensivePlayType || "-";
    
    // Update focus dots (only for offense - away side)
    if (offensiveFocusDotsEl) clearFocusDots(offensiveFocusDotsEl); // Clear defense dots
    if (defensiveFocusDotsEl) updateFocusDots(defensiveFocusDotsEl, offensivePlayFocus);
  } else {
    // Away on offense - show defensive playcall on away side (left), offensive on home side (right)
    defensivePlaycallEl.textContent = defensivePlayType || "-"; // Show Man/Zone for defense
    // ✅ FIX: Display full playcall name (e.g., "3-2 Motion") instead of just play type ("Motion")
    offensivePlaycallEl.textContent = offensivePlaycall || offensivePlayType || "-";
    
    // Update focus dots (only for offense - home side)
    if (defensiveFocusDotsEl) clearFocusDots(defensiveFocusDotsEl); // Clear defense dots
    if (offensiveFocusDotsEl) updateFocusDots(offensiveFocusDotsEl, offensivePlayFocus);
  }
}

/**
 * Get play type (motion or set) from playcall name
 * @param {string} playcall - Raw playcall name
 * @returns {string} Play type
 */
function getPlayType(playcall) {
  if (!playcall) return '-';
  
  // Check if playcall contains "motion" or "set"
  const lowerPlaycall = playcall.toLowerCase();
  if (lowerPlaycall.includes('motion')) {
    return 'Motion';
  } else if (lowerPlaycall.includes('set') || lowerPlaycall.includes('pick') || lowerPlaycall.includes('screen') || lowerPlaycall.includes('post')) {
    return 'Set';
  }
  
  return '-';
}

/**
 * Get play focus (inside, attack, outside) from playcall name
 * @param {string} playcall - Raw playcall name
 * @returns {string} Play focus
 */
function getPlayFocus(playcall) {
  if (!playcall) return null;
  
  // Check if playcall contains focus keywords
  const lowerPlaycall = playcall.toLowerCase();
  if (lowerPlaycall.includes('inside') || lowerPlaycall.includes('post') || lowerPlaycall.includes('low post')) {
    return 'inside';
  } else if (lowerPlaycall.includes('attack') || lowerPlaycall.includes('pick') || lowerPlaycall.includes('roll')) {
    return 'attack';
  } else if (lowerPlaycall.includes('outside') || lowerPlaycall.includes('wing') || lowerPlaycall.includes('corner')) {
    return 'outside';
  }
  
  return null;
}

/**
 * Update focus dots to highlight the active focus
 * @param {HTMLElement} container - Container element with focus dots
 * @param {string} focus - Active focus (inside, attack, outside)
 */
function updateFocusDots(container, focus) {
  if (!container || !focus) {
    clearFocusDots(container);
    return;
  }
  
  const dots = container.querySelectorAll('.focus-dot');
  dots.forEach(dot => {
    const dotFocus = dot.getAttribute('data-focus');
    if (dotFocus === focus) {
      dot.classList.add('active');
    } else {
      dot.classList.remove('active');
    }
  });
}

/**
 * Clear all focus dots
 * @param {HTMLElement} container - Container element with focus dots
 */
function clearFocusDots(container) {
  if (!container) return;
  
  const dots = container.querySelectorAll('.focus-dot');
  dots.forEach(dot => {
    dot.classList.remove('active');
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
  const offensiveFocusDotsEl = document.getElementById('offensive-playcall-focus-dots');
  const defensiveFocusDotsEl = document.getElementById('defensive-playcall-focus-dots');
  
  if (offensivePlaycallEl) offensivePlaycallEl.textContent = '-';
  if (defensivePlaycallEl) defensivePlaycallEl.textContent = '-';
  if (offensiveFocusDotsEl) clearFocusDots(offensiveFocusDotsEl);
  if (defensiveFocusDotsEl) clearFocusDots(defensiveFocusDotsEl);
}

