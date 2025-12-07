/**
 * Playcall Center Module
 * 
 * Updates the offense/defense panels and lean meter at the bottom of the court.
 * Shows play calls, defense type, and animated lean score visualization.
 */

/**
 * Clear playcall center highlights (selected buttons)
 * Called when a play is used or override is cleared
 */
export function clearPlaycallHighlights() {
  // Clear offense play highlights
  const playOptions = document.querySelectorAll('.play-option');
  playOptions.forEach(opt => opt.classList.remove('selected'));
  
  // Clear defense highlights
  const defenseButtons = document.querySelectorAll('.defense-override-btn');
  defenseButtons.forEach(btn => btn.classList.remove('selected'));
}

/**
 * Update playcall center at the start of each turn
 * @param {Object} turnData - Turn data from backend containing playcalls
 * @param {string} homeTeamId - Home team ID for determining sides
 */
export function updatePlaycallCenter(turnData, homeTeamId) {
  if (!turnData) return;

  const offenseTeamId = turnData.possession_team_id;
  const isHomeOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);

  // Get playcall center
  const playcallCenter = document.getElementById('playcall-center');
  if (!playcallCenter) {
    console.warn('⚠️ Playcall Center not found');
    return;
  }

  // ✅ SS&S: Clear highlights if this turn used a user override
  // Check if the turn's playcall matches a selected playcall button
  const offensivePlaycall = turnData.offensive_playcall || turnData.current_playcall;
  const defensivePlaycall = turnData.defensive_playcall || turnData.defense_playcall;
  
  // Get user team side from URL params
  const urlParams = new URLSearchParams(window.location.search);
  const userTeamSide = urlParams.get('my_team'); // "home" or "away"
  const isUserTeamOnOffense = (userTeamSide === 'home' && isHomeOffense) || 
                               (userTeamSide === 'away' && !isHomeOffense);
  const isUserTeamOnDefense = (userTeamSide === 'home' && !isHomeOffense) || 
                               (userTeamSide === 'away' && isHomeOffense);
  
  // Check if offense playcall matches a selected button
  if (isUserTeamOnOffense && offensivePlaycall) {
    // ✅ LOUD DEBUG: Check all selected buttons and compare
    const allSelectedButtons = document.querySelectorAll('.play-option.selected');
    const selectedPlayNames = Array.from(allSelectedButtons).map(btn => btn.dataset.play);
    
    // ✅ LOUD DEBUG: Frontend comparison
    const hasMatch = selectedPlayNames.some(name => {
      const btnName = name?.trim();
      const turnName = offensivePlaycall?.trim();
      return btnName && turnName && btnName.toLowerCase() === turnName.toLowerCase();
    });
    
    if (hasMatch) {
      console.log("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢");
      console.log("🟢 [PLAYCALL MATCH] TRUE - Frontend found matching selected button!");
      console.log(`🟢 Turn playcall: '${offensivePlaycall}' | Selected:`, selectedPlayNames);
      console.log("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢");
    } else {
      console.warn("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴");
      console.warn("🔴 [PLAYCALL MATCH] FALSE - Frontend did NOT find matching selected button!");
      console.warn(`🔴 Turn playcall: '${offensivePlaycall}' | Selected:`, selectedPlayNames);
      console.warn("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴");
    }
    
    console.log(`🎮 [PLAYCALL] Checking if offense playcall matches selected: ${offensivePlaycall}`, {
      isUserTeamOnOffense,
      offensivePlaycall,
      userTeamSide,
      selectedPlayNames
    });
    
    // Try exact match first
    let selectedOffenseBtn = document.querySelector(`.play-option.selected[data-play="${offensivePlaycall}"]`);
    
    // If no exact match, try to find by checking all selected buttons
    if (!selectedOffenseBtn && selectedPlayNames.length > 0) {
      console.log(`🔍 [PLAYCALL] No exact match, checking all selected buttons:`, selectedPlayNames);
      // Check if any selected button matches (case-insensitive, trim whitespace)
      for (const btn of allSelectedButtons) {
        const btnPlayName = btn.dataset.play?.trim();
        const turnPlayName = offensivePlaycall?.trim();
        if (btnPlayName && turnPlayName && btnPlayName.toLowerCase() === turnPlayName.toLowerCase()) {
          selectedOffenseBtn = btn;
          console.log(`✅ [PLAYCALL] Found match (case-insensitive): '${btnPlayName}' === '${turnPlayName}'`);
          break;
        }
      }
    }
    
    if (selectedOffenseBtn) {
      // This play was selected and is now being used - clear the highlight
      selectedOffenseBtn.classList.remove('selected');
      console.log(`✅ [PLAYCALL] Cleared offense highlight for used play: ${offensivePlaycall}`);
    } else {
      console.log(`🔍 [PLAYCALL] No matching selected button found for: ${offensivePlaycall}`);
      console.log(`🔍 [PLAYCALL] Available selected plays:`, selectedPlayNames);
    }
  }
  
  // Check if defense playcall matches a selected button
  if (isUserTeamOnDefense && defensivePlaycall) {
    // Check for specific zone types (2-3 Zone, 3-2 Zone, 1-3-1 Zone) or generic "Zone"
    const defenseType = defensivePlaycall.includes('Zone') ? 'Zone' : defensivePlaycall;
    console.log(`🎮 [PLAYCALL] Checking if defense playcall matches selected: ${defensivePlaycall} (type: ${defenseType})`, {
      isUserTeamOnDefense,
      defensivePlaycall,
      defenseType,
      userTeamSide
    });
    const selectedDefenseBtn = document.querySelector(`.defense-override-btn.selected[data-defense="${defenseType}"]`);
    if (selectedDefenseBtn) {
      // This defense was selected and is now being used - clear the highlight
      selectedDefenseBtn.classList.remove('selected');
      console.log(`✅ [PLAYCALL] Cleared defense highlight for used defense: ${defensivePlaycall}`);
    } else {
      console.log(`🔍 [PLAYCALL] No matching selected button found for: ${defensivePlaycall} (type: ${defenseType})`);
    }
  }

  // Panel flipping removed - offense always left, defense always right

  // Update top row status displays
  const offenseStatusText = document.getElementById('offense-status-text');
  const defenseStatusText = document.getElementById('defense-status-text');
  
  if (offenseStatusText && turnData.offensive_play_type && turnData.offensive_play_focus) {
    const type = turnData.offensive_play_type === 'motion' ? 'Motion' : 'Set';
    const focus = turnData.offensive_play_focus.charAt(0).toUpperCase() + turnData.offensive_play_focus.slice(1);
    offenseStatusText.textContent = `${type} → ${focus}`;
  }
  
  if (defenseStatusText) {
    // Use defensive_playcall if available (contains full name like "2-3 Zone" or "3-2 Zone")
    // Otherwise fall back to defensive_play_type (just "Man" or "Zone")
    const defPlaycall = turnData.defensive_playcall || turnData.defense_playcall;
    const defType = defPlaycall || turnData.defensive_play_type;
    if (defType) {
      const formattedDefType = defType.charAt(0).toUpperCase() + defType.slice(1);
    const aggr = turnData.aggression || 'Normal';
      defenseStatusText.textContent = `${formattedDefType} ${aggr}`;
    }
  }

  // Reset lean meter to neutral
  resetLeanMeter();

  // ✅ Update playcall center headshot for the play being used (use intended_shooter_id)
  if (isUserTeamOnOffense && offensivePlaycall && turnData.intended_shooter_id) {
    const playOption = document.querySelector(`.play-option[data-play="${offensivePlaycall}"]`);
    if (playOption) {
      const headshotImg = playOption.querySelector('.play-headshot');
      if (headshotImg) {
        const imgPath = `/static/images/players/${turnData.intended_shooter_id}.png`;
        headshotImg.src = imgPath;
        headshotImg.setAttribute('data-player-id', turnData.intended_shooter_id);
        headshotImg.onerror = () => {
          console.warn(`⚠️ Headshot failed to load: ${imgPath}, using default`);
          headshotImg.src = '/static/images/players/default.png';
        };
        console.log(`✅ [PLAYCALL CENTER] Updated headshot for '${offensivePlaycall}' using intended_shooter_id: ${turnData.intended_shooter_id}`);
      }
    }
  }

  // ==================== TRIGGER PLAYCALL REVEAL HUD ====================
  // Show transient HUD overlay with playcall info
  const playType = turnData.offensive_play_type;
  const playFocus = turnData.offensive_play_focus;
  // Use defensive_playcall if available (contains full name like "2-3 Zone" or "3-2 Zone")
  // Otherwise fall back to defensive_play_type (just "Man" or "Zone")
  const defensePlaycall = turnData.defensive_playcall || turnData.defense_playcall;
  const defenseType = defensePlaycall || turnData.defensive_play_type;
  const aggression = turnData.aggression || 'normal';
  
  if (typeof window.showPlaycallReveal === 'function' && playType && playFocus && defenseType) {
    // Get EV from backend calculation (if available), otherwise fallback to random
    // Backend now returns EV as percentage (-99 to +99), so we use it directly
    const ev = turnData.ev !== undefined ? parseFloat(turnData.ev) : ((Math.random() * 4) - 2) * 50; // Fallback: convert old range to percentage
    
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
      ev: ev, // Pass as number, formatting will happen in showPlaycallReveal
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
 * @param {number} leanScore - Score from -1.0 to 1.0
 */
export function animateLeanMeter(leanScore) {
  console.log(`📊 [LEAN METER] animateLeanMeter called with score: ${leanScore}`);

  if (leanScore == null || isNaN(leanScore)) {
    console.warn('⚠️ Invalid lean score, keeping meter neutral');
    return;
  }

  // Clamp to -1 to 1 range
  const clampedScore = Math.max(-1, Math.min(1, leanScore));

  const posFill = document.getElementById('lean-fill-positive');
  const negFill = document.getElementById('lean-fill-negative');

  if (!posFill || !negFill) {
    console.warn('⚠️ Lean meter elements not found');
    return;
  }

  if (clampedScore > 0) {
    // Positive score: fill upward (green)
    // Fill percentage of the space from center (50%) to top (100%)
    // So 0.47 fills 47% of the 50% space = 23.5% of container height
    const fillPercentage = Math.abs(clampedScore) * 50; // 0-50% of container
    posFill.style.height = `${fillPercentage}%`;
    negFill.style.height = '0%';
  } else if (clampedScore < 0) {
    // Negative score: fill downward (red)
    // Fill percentage of the space from center (50%) to bottom (0%)
    // So -0.88 fills 88% of the 50% space = 44% of container height
    const fillPercentage = Math.abs(clampedScore) * 50; // 0-50% of container
    posFill.style.height = '0%';
    negFill.style.height = `${fillPercentage}%`;
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
  if (!turnData || !turnData.text) {
    console.log('🔍 [LEAN] No turnData or text field');
    return null;
  }

  const text = turnData.text;
  const leanMatch = text.match(/lean:([-+]?\d+\.?\d*)/);
  
  if (leanMatch && leanMatch[1]) {
    const leanScore = parseFloat(leanMatch[1]);
    console.log(`✅ [LEAN] Parsed lean score: ${leanScore} from text: "${text.substring(0, 100)}"`);
    return leanScore;
  }

  console.log(`⚠️ [LEAN] No lean score found in text: "${text.substring(0, 100)}"`);
  return null;
}

