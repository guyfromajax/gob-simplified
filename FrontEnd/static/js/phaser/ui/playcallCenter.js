/**
 * Playcall Center Module
 * 
 * Updates the offense/defense panels and lean meter at the bottom of the court.
 * Shows play calls, defense type, and animated lean score visualization.
 */

/**
 * Update playcall panels at the start of each turn
 * @param {Object} turnData - Turn data from backend containing playcalls
 * @param {string} homeTeamId - Home team ID for determining sides
 */
export function updatePlaycallCenter(turnData, homeTeamId) {
  if (!turnData) return;

  const offenseTeamId = turnData.possession_team_id || turnData.starting_possession_team_id;
  const isHomeOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);

  // Get panels
  const offensePanel = document.getElementById('offense-panel');
  const defensePanel = document.getElementById('defense-panel');
  const playcallCenter = document.getElementById('playcall-center');

  if (!offensePanel || !defensePanel || !playcallCenter) {
    console.warn('⚠️ Playcall Center elements not found');
    return;
  }

  // Switch panel sides based on possession
  // Away offense = offense on LEFT, defense on RIGHT
  // Home offense = offense on RIGHT, defense on LEFT
  playcallCenter.style.flexDirection = isHomeOffense ? 'row-reverse' : 'row';

  // Clear all active states
  document.querySelectorAll('.playcall-option').forEach(opt => {
    opt.classList.remove('active');
  });

  // Highlight offense play type
  // Backend sends "Motion" or "Set_Play" (title case)
  const playType = turnData.offensive_play_type;
  if (playType) {
    const typeNormalized = playType.toLowerCase().replace('_', ' '); // "set_play" → "set play"
    let typeSelector = null;
    
    if (typeNormalized === 'motion') {
      typeSelector = 'motion';
    } else if (typeNormalized === 'set play' || typeNormalized.includes('set')) {
      typeSelector = 'set_play';
    }
    
    if (typeSelector) {
      const typeElement = offensePanel.querySelector(`.playcall-option[data-type="${typeSelector}"]`);
      if (typeElement) {
        typeElement.classList.add('active');
      }
    }
  }

  // Highlight offense focus
  const playFocus = turnData.offensive_play_focus?.toLowerCase();
  if (playFocus && ['inside', 'attack', 'outside'].includes(playFocus)) {
    const focusElement = offensePanel.querySelector(`.playcall-option[data-focus="${playFocus}"]`);
    if (focusElement) {
      focusElement.classList.add('active');
    }
  }

  // Highlight defense type
  const defenseType = turnData.defensive_play_type?.toLowerCase();
  if (defenseType === 'man' || defenseType === 'zone') {
    const defElement = defensePanel.querySelector(`.playcall-option[data-defense="${defenseType}"]`);
    if (defElement) {
      defElement.classList.add('active');
    }
  }

  // Highlight aggression (from turnData if available)
  // For now, default to 'normal' - can be wired to actual aggression data later
  const aggression = turnData.aggression?.toLowerCase() || 'normal';
  const aggrElement = defensePanel.querySelector(`.playcall-option[data-aggression="${aggression}"]`);
  if (aggrElement) {
    aggrElement.classList.add('active');
  }

  // Reset lean meter to neutral
  resetLeanMeter();
  
  // ==================== SHOW OVERRIDE INDICATOR ====================
  // Check if this turn used a user override
  const overrideIndicator = document.getElementById('override-indicator');
  if (overrideIndicator) {
    if (turnData.offense_type === 'User') {
      overrideIndicator.style.display = 'block';
      console.log('🎮 OVERRIDE indicator displayed');
    } else {
      overrideIndicator.style.display = 'none';
    }
  }

  // ==================== TRIGGER PLAYCALL REVEAL HUD ====================
  // Show transient HUD overlay with playcall info
  if (typeof window.showPlaycallReveal === 'function' && playType && playFocus && defenseType) {
    // Calculate random EV placeholder from -2 to +2 (will be replaced with real logic later)
    const ev = (Math.random() * 4) - 2; // -2.0 to +2.0
    
    // Get intended shooter info (from turnData if available)
    const intendedShooterId = turnData.intended_shooter_id || null;
    
    window.showPlaycallReveal({
      offense: {
        type: playType,
        focus: playFocus
      },
      defense: {
        type: defenseType,
        aggression: aggression
      },
      ev: ev.toFixed(1),
      intendedShooterId: intendedShooterId,  // For headshot display
      // hotPlayer can be added later if available in turnData
      hotPlayer: null
    });
  }
}

/**
 * Reset lean meter to neutral (just yellow center line)
 */
export function resetLeanMeter() {
  const posFill = document.getElementById('lean-fill-positive');
  const negFill = document.getElementById('lean-fill-negative');

  if (posFill) posFill.style.height = '0%';
  if (negFill) negFill.style.height = '0%';
}

/**
 * Animate lean meter based on lean score
 * @param {number} leanScore - Score from -2.0 to 2.0
 */
export function animateLeanMeter(leanScore) {

  if (leanScore == null || isNaN(leanScore)) {
    console.warn('⚠️ Invalid lean score, keeping meter neutral');
    return;
  }

  // Clamp to -2 to 2 range
  const clampedScore = Math.max(-2, Math.min(2, leanScore));

  const posFill = document.getElementById('lean-fill-positive');
  const negFill = document.getElementById('lean-fill-negative');

  if (!posFill || !negFill) {
    console.warn('⚠️ Lean meter elements not found');
    return;
  }

  if (clampedScore > 0) {
    // Positive score: fill upward (green)
    const percentage = (clampedScore / 2) * 100; // 0-100%
    posFill.style.height = `${percentage}%`;
    negFill.style.height = '0%';
  } else if (clampedScore < 0) {
    // Negative score: fill downward (red)
    const percentage = (Math.abs(clampedScore) / 2) * 100; // 0-100%
    posFill.style.height = '0%';
    negFill.style.height = `${percentage}%`;
  } else {
    // Exactly 0: neutral (just yellow line)
    posFill.style.height = '0%';
    negFill.style.height = '0%';
  }
}

/**
 * Parse lean score from turn data text
 * Looks for "lean:X.XX" pattern in the text
 * @param {Object} turnData - Turn data with text field
 * @returns {number|null} - Lean score or null if not found
 */
export function parseLeanScoreFromText(turnData) {
  if (!turnData || !turnData.text) return null;

  const text = turnData.text;
  const leanMatch = text.match(/lean:([-+]?\d+\.?\d*)/);
  
  if (leanMatch && leanMatch[1]) {
    const leanScore = parseFloat(leanMatch[1]);
    return leanScore;
  }

  return null;
}

