/**
 * Playcall Center Module
 * 
 * Updates the offense/defense panels at the bottom of the court.
 * Shows play calls and defense type.
 */

/**
 * Clear playcall center highlights (selected buttons)
 * Called when a play is used or override is cleared
 */
export function clearPlaycallHighlights() {
  const playOptions = document.querySelectorAll('.play-option');
  playOptions.forEach(opt => opt.classList.remove('selected'));
  const stackZone = document.getElementById('pcc-stacks-zone');
  if (stackZone) {
    stackZone.querySelectorAll('.pcc-stack-btn').forEach(btn => btn.classList.remove('selected'));
  }
}

/**
 * Update playcall center at the start of each turn
 * @param {Object} turnData - Turn data from backend containing playcalls
 * @param {string} homeTeamId - Home team ID for determining sides
 */
export function updatePlaycallCenter(turnData, homeTeamId) {
  if (!turnData) return;

  const offenseTeamId = turnData.offense_team_id || turnData.possession_team_id;
  const isHomeOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);

  // Get playcall center
  const playcallCenter = document.getElementById('playcall-center');
  if (!playcallCenter) {
    return;
  }

  // ✅ SS&S: Clear highlights if backend cleared the offense override
  // Backend sets offense_override_cleared: true when user team's override was used and cleared
  // This is simpler and more reliable than matching playcall names or checking team sides
  if (turnData.offense_override_cleared === true) {
    const allSelectedButtons = document.querySelectorAll('.play-option.selected');
    if (allSelectedButtons.length > 0) {
      // Un-highlight the selected button (there should only be one selected at a time)
      const selectedButton = allSelectedButtons[0];
      selectedButton.classList.remove('selected');
    }
  }
  
  // ✅ Defense and aggression buttons remain highlighted until manually cleared by user
  // (via red X buttons or clicking different buttons)
  // Only offense playcall buttons clear automatically after use

  // Panel flipping removed - offense always left, defense always right

  // Update top row status displays
  const offenseStatusText = document.getElementById('offense-status-text');
  const defenseStatusText = document.getElementById('defense-status-text');
  
  // ✅ FIX: Display play name instead of Play Type => Play Focus
  if (offenseStatusText) {
    const playName = turnData.offensive_playcall || turnData.current_playcall;
    if (playName) {
      offenseStatusText.textContent = playName;
    } else {
      // Fallback to type → focus if play name not available
      if (turnData.offensive_play_type && turnData.offensive_play_focus) {
        const type = turnData.offensive_play_type === 'motion' ? 'Motion' : 'Set';
        const focus = turnData.offensive_play_focus.charAt(0).toUpperCase() + turnData.offensive_play_focus.slice(1);
        offenseStatusText.textContent = `${type} → ${focus}`;
      }
    }
  }
  
  if (defenseStatusText) {
    // Use defensive_playcall if available (contains full name like "Man Normal", "2-3 Zone", etc.)
    // Otherwise fall back to defensive_play_type (just "Man" or "Zone")
    const defPlaycall = turnData.defensive_playcall || turnData.defense_playcall;
    const defType = defPlaycall || turnData.defensive_play_type;
    if (defType) {
      const formattedDefType = defType.charAt(0).toUpperCase() + defType.slice(1);
      // ✅ SS&S: Use defense_aggression_call from backend (set by set_strategy_calls)
      const aggrRaw = turnData.defense_aggression_call || turnData.aggression || 'normal';
      const aggr = aggrRaw.charAt(0).toUpperCase() + aggrRaw.slice(1); // Capitalize first letter
      defenseStatusText.textContent = `${formattedDefType} ${aggr}`;
    }
  }

  // Sync stack button .selected state from turn data (guarded — no-op if fields missing)
  const stackZone = document.getElementById('pcc-stacks-zone');
  if (stackZone) {
    if (turnData.offense_tempo_call || turnData.tempo_call) {
      const tempo = (turnData.offense_tempo_call || turnData.tempo_call || '').toLowerCase();
      stackZone.querySelectorAll('.pcc-stack.tempo .pcc-stack-btn').forEach(btn => {
        const v = btn.id === 'tempo-fast' ? 'fast' : btn.id === 'tempo-slow' ? 'slow' : 'normal';
        btn.classList.toggle('selected', v === tempo);
      });
    }
    if (turnData.defense_aggression_call || turnData.aggression) {
      const aggr = (turnData.defense_aggression_call || turnData.aggression || '').toLowerCase();
      stackZone.querySelectorAll('.pcc-stack.aggression .pcc-stack-btn').forEach(btn => {
        const v = btn.id === 'aggr-passive' ? 'passive' : btn.id === 'aggr-aggressive' ? 'aggressive' : 'normal';
        btn.classList.toggle('selected', v === aggr);
      });
    }
    if (turnData.press_trap_override != null) {
      const pt = (turnData.press_trap_override || '').toLowerCase();
      stackZone.querySelectorAll('.pcc-stack.press-trap .pcc-stack-btn').forEach(btn => {
        const v = btn.id === 'press-btn' ? 'press' : btn.id === 'trap-btn' ? 'trap' : 'none';
        btn.classList.toggle('selected', v === pt);
      });
    }
  }

  // ✅ SS&S: Headshots are set once on page load via populatePlayHeadshots() in court.html
  // Do NOT update headshots dynamically during gameplay - this causes images to change mid-game
  // and can show computer team players. Images remain static based on user's lineup.

  // ==================== TRIGGER PLAYCALL REVEAL HUD ====================
  // Show transient HUD overlay with playcall info
  // ✅ FIX: Use play name instead of Play Type => Play Focus
  const playName = turnData.offensive_playcall || turnData.current_playcall;
  // Use defensive_playcall if available (contains full name like "2-3 Zone" or "3-2 Zone")
  // Otherwise fall back to defensive_play_type (just "Man" or "Zone")
  const defensePlaycall = turnData.defensive_playcall || turnData.defense_playcall;
  const defenseType = defensePlaycall || turnData.defensive_play_type;
  // ✅ SS&S: Use defense_aggression_call from backend (set by set_strategy_calls)
  const aggression = turnData.defense_aggression_call || turnData.aggression || 'normal';
  
  if (typeof window.showPlaycallReveal === 'function' && playName && defenseType) {
    // Get EV from backend calculation (if available), otherwise fallback to random
    // Backend now returns EV as percentage (-99 to +99), so we use it directly
    const ev = turnData.ev !== undefined ? parseFloat(turnData.ev) : ((Math.random() * 4) - 2) * 50; // Fallback: convert old range to percentage
    
    // Get intended shooter info (from turnData if available)
    const intendedShooterId = turnData.intended_shooter_id || null;
    
    window.showPlaycallReveal({
      offense: {
        name: playName  // ✅ FIX: Pass play name instead of type and focus
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
 * Legacy no-op retained so existing imports remain safe after lean meter removal.
 */
export function resetLeanMeter() {
  return;
}

/**
 * Legacy no-op retained so existing imports remain safe after lean meter removal.
 * @param {number} leanScore - Score from -100 to 100 (raw result value)
 */
export function animateLeanMeter(leanScore) {
  void leanScore;
  return;
}

/**
 * Parse lean score from turn data text
 * Looks for "lean:X.XX" pattern in the text
 * @param {Object} turnData - Turn data with text field
 * @returns {number|null} - Lean score or null if not found
 */
export function parseLeanScoreFromText(turnData) {
  if (!turnData || !turnData.text) {
    return null;
  }

  const text = turnData.text;
  const leanMatch = text.match(/lean:([-+]?\d+\.?\d*)/);
  
  if (leanMatch && leanMatch[1]) {
    const leanScore = parseFloat(leanMatch[1]);
    return leanScore;
  }

  return null;
}
