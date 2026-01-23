/**
 * Active Player Display Utility
 * 
 * Manages the scoreboard headshot displays showing current ball handler and defender.
 * Works across all play types (HCO, Fast Break, Free Throws, Rebounds, FCP, HCT).
 */

/**
 * Extract defender ID from turn data (handles multiple formats)
 * @param {Object} turnData - Turn data from backend
 * @returns {string|null} - Defender player ID
 */
export function getDefenderIdFromTurn(turnData) {
  if (!turnData) return null;
  
  // Debug: Log what we're receiving
  if (turnData.defender_id || turnData.defender) {
    if (false && defenderId) console.log('🛡️ DEFENDER DATA:', {
      defender_id: turnData.defender_id,
      defender: turnData.defender,
      defender_type: typeof turnData.defender,
      has_player_id: turnData.defender?.player_id,
      result_type: turnData.result_type,
      offensive_state: turnData.offensive_state
    });
  }
  
  // Try multiple formats:
  // 1. defender_id (FCP/HCT format)
  if (turnData.defender_id) return turnData.defender_id;
  
  // 2. defender as string (direct player_id)
  if (typeof turnData.defender === 'string') return turnData.defender;
  
  // 3. defender as object (converted Player object)
  if (turnData.defender?.player_id) return turnData.defender.player_id;
  
  // 4. No defender found (expected for some turn types)
  return null;
}

/**
 * Extract ball handler ID from turn data or animations
 * @param {Object} turnData - Turn data
 * @param {number} stepIndex - Current animation step
 * @returns {string|null} - Ball handler player ID
 */
export function getBallHandlerIdFromTurn(turnData, stepIndex = 0) {
  if (!turnData) return null;
  
  // Try animations first (most accurate for current step)
  if (turnData.animations) {
    for (const anim of turnData.animations) {
      if (anim.hasBallAtStep?.[stepIndex]) {
        return anim.playerId;
      }
    }
  }
  
  // Fallback to ball_handler or shooter from turnData
  if (turnData.ball_handler?.player_id) return turnData.ball_handler.player_id;
  if (typeof turnData.ball_handler === 'string') return turnData.ball_handler;
  if (turnData.shooter?.player_id) return turnData.shooter.player_id;
  if (typeof turnData.shooter === 'string') return turnData.shooter;
  
  return null;
}

/**
 * Update active player displays (wrapper for window function)
 * @param {string} ballHandlerId - Ball handler player ID
 * @param {string} defenderId - Defender player ID
 * @param {string} homeTeamId - Home team ID
 * @param {Object} playerSprites - Phaser player sprites
 * @param {string} audibleText - Optional "AUDIBLE!" or "HOT READ!" text
 */
export function updateActivePlayers(ballHandlerId, defenderId, homeTeamId, playerSprites, audibleText = null) {
  if (typeof window.updateActivePlayersDisplay === 'function') {
    window.updateActivePlayersDisplay(ballHandlerId, defenderId, homeTeamId, playerSprites, audibleText);
  }
}

