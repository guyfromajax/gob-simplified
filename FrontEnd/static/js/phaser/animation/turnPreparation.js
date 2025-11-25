/**
 * Turn Preparation Utilities
 * 
 * Functions for preparing turns before animation and finalizing them after animation.
 * These functions extract the pre/post setup logic from animateGameTurns.js to make
 * it reusable when routing through AnimationRouter.
 * 
 * ✅ PHASE 2.2: Extracted from animateGameTurns.js
 */

import { updatePlaycallDisplay } from "../utils/playcallDisplay.js";
import { updateStrategyBars } from "../utils/strategyBars.js";
import { updatePlaycallCenter, parseLeanScoreFromText } from "../ui/playcallCenter.js";
import { announceFromTurnData } from "../utils/announcements.js";

/**
 * Prepare a turn for animation by setting up all required state and UI updates.
 * 
 * This function handles all the setup that happens before calling playTurnAnimation,
 * including:
 * - Setting scene.currentTurn and turn.index
 * - Updating playcall display
 * - Updating strategy bars
 * - Updating playcall center (including lean score parsing)
 * - Calculating lean meter animation step
 * - Showing turn start announcements
 * 
 * @param {Object} params - Preparation parameters
 * @param {Object} params.turn - Turn data object
 * @param {Object} params.scene - Phaser scene
 * @param {number} params.turnIndex - Turn index (loop index)
 * @param {string} params.homeTeamId - Home team ID
 * @returns {Object} Prepared turn object with calculated properties
 */
export function prepareTurnForAnimation({ turn, scene, turnIndex, homeTeamId }) {
  // Set scene.currentTurn (required by playTurnAnimation)
  scene.currentTurn = turnIndex;
  
  // Set turn.index (required for context)
  turn.index = turnIndex;
  
  // Update playcall display before animating the turn
  updatePlaycallDisplay(turn, homeTeamId);
  
  // Update strategy bars at start of turn
  updateStrategyBars(turn, homeTeamId);
  
  // Update Playcall Center (panels and reset lean meter)
  updatePlaycallCenter(turn, homeTeamId);
  
  // Parse lean score for later animation (at middle step)
  const leanScore = parseLeanScoreFromText(turn);
  const animations = turn.animations || [];
  
  // Calculate middle step for lean meter animation
  if (leanScore !== null && animations.length > 0) {
    // Find the max number of steps across all player animations
    const maxSteps = Math.max(
      0,
      ...animations.map(anim => anim.movement?.length || 0)
    );
    
    // Calculate middle step (round up for even numbers)
    const middleStep = Math.ceil(maxSteps / 2);
    
    // Store for use during animation
    scene._leanScoreToAnimate = leanScore;
    scene._leanAnimationStep = middleStep;
    scene._leanAnimationTriggered = false;
  } else {
    scene._leanScoreToAnimate = null;
  }
  
  // Show announcement for turn start events (Fast Break, Press, Trap)
  announceFromTurnData(turn, 'start', homeTeamId, scene);
  
  // Calculate possession ID (used for post-animation cleanup)
  const possessionId =
    turn.possession_id ?? turn.possessionId ?? turn.possessionID ?? null;
  
  return {
    turn,
    possessionId
  };
}

/**
 * Finalize a turn after animation by performing cleanup and updates.
 * 
 * This function handles all the cleanup that happens after calling playTurnAnimation,
 * including:
 * - Setting scene._previousTurnWasShot flag for shot turns
 * - Calling onUpdate callback
 * - Updating debug score
 * - Showing turn end announcements
 * 
 * @param {Object} params - Finalization parameters
 * @param {Object} params.turn - Turn data object
 * @param {Object} params.scene - Phaser scene
 * @param {Function} params.onUpdate - Update callback (optional)
 * @param {string} params.possessionId - Possession ID (optional)
 * @param {number} params.turnIndex - Turn index (optional, for debug score)
 * @param {Function} params.updateDebugScore - Debug score update function (optional)
 */
export function finalizeTurnAfterAnimation({ 
  turn, 
  scene, 
  onUpdate, 
  possessionId, 
  turnIndex,
  updateDebugScore 
}) {
  // Set flag if this was a shot turn (MAKE or MISS) so the next turn knows to skip step 0 ball attachment
  if (turn.result_type === "MAKE" || turn.result_type === "MISS") {
    scene._previousTurnWasShot = true;
  }
  
  // Show announcements for shot results and rebounds (after animation)
  const homeTeamId = scene.simData?.home_team_id;
  announceFromTurnData(turn, 'end', homeTeamId, scene);
  
  // Call onUpdate callback if provided
  if (onUpdate) {
    try {
      onUpdate(turn);
    } catch (err) {
      console.error('Scoreboard update failed:', err);
    }
  }
  
  // Update debug score if function provided
  if (updateDebugScore && turnIndex !== undefined) {
    updateDebugScore(turn, { turnIndex, possessionId });
  }
}

