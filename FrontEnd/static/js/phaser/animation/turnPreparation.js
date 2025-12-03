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
 * Universal Turn Transition Handler
 * 
 * Handles possession flips and state transitions for ALL turn types.
 * This is the single source of truth for turn-to-turn transitions.
 * 
 * Backend provides authoritative transition data:
 * - possession_flips: bool - Whether possession changes
 * - possession_team_id: string - New offense team (AFTER flip)
 * - next_play_type: string - What comes next ("HCO", "FAST_BREAK", "BASELINE_INBOUND", etc.)
 * 
 * This function runs AFTER animation completes, ensuring possession is updated
 * before the next turn begins.
 * 
 * EXCEPTION: FREE_THROW possession flips happen DURING animation (before inbound pass),
 * so they set scene._possessionAlreadyFlipped to skip double-flipping here.
 * 
 * @param {Object} scene - Phaser scene
 * @param {Object} turnData - Turn data from backend
 */
function handleTurnTransition(scene, turnData) {
  // ✅ DEBUG: Always log transition handler entry
  console.log('🔍 [UNIVERSAL TRANSITION] Entry', {
    result_type: turnData.result_type,
    possession_flips: turnData.possession_flips,
    possession_team_id: turnData.possession_team_id,
    current_scene_offenseTeamId: scene.offenseTeamId,
    _possessionAlreadyFlipped: scene._possessionAlreadyFlipped
  });
  
  // ✅ EXCEPTION: Skip if FREE_THROW already flipped possession during animation
  // FREE_THROW flips BEFORE inbound (during animation), not after
  if (turnData.result_type === "FREE_THROW" && scene._possessionAlreadyFlipped) {
    console.log('🔄 [UNIVERSAL TRANSITION] Skipping possession flip - already handled during FREE_THROW animation');
    scene._possessionAlreadyFlipped = false; // Clear flag
    return;
  }
  
  // ✅ UNIVERSAL POSSESSION FLIP HANDLER
  // Works for ALL turn types: FOUL, STEAL, DEAD_BALL, HCO, MAKE/MISS, etc.
  if (turnData.possession_flips && turnData.possession_team_id) {
    const previousOffenseTeamId = scene.offenseTeamId;
    
    // Only flip if actually changing (avoid duplicate events)
    if (previousOffenseTeamId !== turnData.possession_team_id) {
      scene.offenseTeamId = turnData.possession_team_id;
      scene.events?.emit('possessionChange', { 
        offenseTeamId: turnData.possession_team_id 
      });
      console.log('✅ [UNIVERSAL TRANSITION] Possession flipped', {
        from: previousOffenseTeamId,
        to: turnData.possession_team_id,
        result_type: turnData.result_type,
        next_play_type: turnData.next_play_type
      });
    } else {
      console.log('⚠️ [UNIVERSAL TRANSITION] Possession flip requested but already correct', {
        current: previousOffenseTeamId,
        requested: turnData.possession_team_id,
        result_type: turnData.result_type
      });
    }
  } else {
    console.log('⏭️ [UNIVERSAL TRANSITION] No possession flip needed', {
      possession_flips: turnData.possession_flips,
      possession_team_id: turnData.possession_team_id,
      result_type: turnData.result_type
    });
  }
  
  // Note: next_play_type transitions are handled by the turn-by-turn loop
  // The next turn will be the appropriate type (BASELINE_INBOUND, HCO, FAST_BREAK, etc.)
  // We just need to ensure possession is correct before it starts
}

/**
 * Finalize a turn after animation by performing cleanup and updates.
 * 
 * This function handles all the cleanup that happens after calling playTurnAnimation,
 * including:
 * - Universal turn transition (possession flips, state updates)
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
  // ✅ UNIVERSAL TRANSITION HANDLER - Handle possession flips and state transitions
  // This runs FIRST to ensure possession is correct before other finalization steps
  handleTurnTransition(scene, turn);
  
  // ✅ DEBUG: Log finalization
  console.log('🔍 [FINALIZING TURN]', {
    turnIndex: turnIndex ?? turn.index,
    result_type: turn.result_type,
    willSetPreviousTurnWasShot: turn.result_type === "MAKE" || turn.result_type === "MISS",
    hasOnUpdate: !!onUpdate
  });
  
  // Set flag if this was a shot turn (MAKE or MISS) so the next turn knows to skip step 0 ball attachment
  if (turn.result_type === "MAKE" || turn.result_type === "MISS") {
    scene._previousTurnWasShot = true;
    console.log('🔍 [SET _previousTurnWasShot]', {
      turnIndex: turnIndex ?? turn.index,
      result_type: turn.result_type
    });
  }
  
  // Show announcements for shot results and rebounds (after animation)
  const homeTeamId = scene.simData?.home_team_id;
  announceFromTurnData(turn, 'end', homeTeamId, scene);
  
  // Call onUpdate callback if provided
  if (onUpdate) {
    try {
      onUpdate(turn);
      console.log('🔍 [CALLED onUpdate]', {
        turnIndex: turnIndex ?? turn.index,
        result_type: turn.result_type
      });
    } catch (err) {
      console.error('Scoreboard update failed:', err);
    }
  }
  
  // Update debug score if function provided
  if (updateDebugScore && turnIndex !== undefined) {
    updateDebugScore(turn, { turnIndex, possessionId });
  }
}

