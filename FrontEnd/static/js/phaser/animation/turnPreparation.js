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
// ✅ TIMEOUT: Removed resetTimeoutQueue import - timeout queue persists until executed

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
export async function prepareTurnForAnimation({ turn, scene, turnIndex, homeTeamId }) {
  // ✅ TIMEOUT: Removed reset - timeout queue persists until executed or cancelled
  
  // Set scene.currentTurn (required by playTurnAnimation)
  scene.currentTurn = turnIndex;
  
  // Set turn.index (required for context)
  turn.index = turnIndex;
  
  // ✅ FIX (Bug 1): Update offense_team_id BEFORE turn executes (not after)
  // SIP and other turns need correct offense_team_id at START, not END
  if (turn.offense_team_id && turn.offense_team_id !== scene.offenseTeamId) {
    scene.offenseTeamId = turn.offense_team_id;
    scene.events?.emit('possessionChange', { 
      offenseTeamId: turn.offense_team_id 
    });
  }
  
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
  
  // ✅ SS&S: Use central announcement dispatcher
  // Check turn context and announce appropriately
  if (!turn._contextAnnouncementsShown) {
    const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
    
    // Context announcements (situation being entered)
    // ✅ FIX: Don't announce Fast Break if this turn is a steal OR if it came from a steal (steal announcement takes priority)
    // Check: 1) Not a STEAL turn itself, 2) Text doesn't mention steal, 3) Not a steal-initiated Fast Break (is_steal_entry flag)
    const isStealInitiatedFastBreak = turn.roles?.is_steal_entry;
    if (turn.fast_break && turn.result_type !== 'STEAL' && !turn.text?.toLowerCase().includes('steal') && !isStealInitiatedFastBreak) {
      announceGameEvent('FAST_BREAK', turn, scene);
    }
    
    // Pressure announcements (only for BASELINE_INBOUND setting up pressure)
    if (turn.result_type === 'BASELINE_INBOUND') {
      if (turn.next_defensive_setup === 'FCP') {
        announceGameEvent('PRESSURE_FCP', turn, scene);
      } else if (turn.next_defensive_setup === 'HCT') {
        announceGameEvent('PRESSURE_HCT', turn, scene);
      }
    }
    
    turn._contextAnnouncementsShown = true;
  }
  
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
  // ✅ REMOVED: Transition logging (cluttering console)
  
  // ✅ SS&S: Backend provides offense_team_id for each turn (single source of truth)
  // Frontend just sets scene.offenseTeamId to that value (no flip logic, just assignment)
  // Each turn knows its offense team, frontend displays it
  if (turnData.offense_team_id) {
    const previousOffenseTeamId = scene.offenseTeamId;
    const newOffenseTeamId = turnData.offense_team_id;
    
    // Update if different (avoid duplicate events)
    if (previousOffenseTeamId !== newOffenseTeamId) {
      scene.offenseTeamId = newOffenseTeamId;
      scene.events?.emit('possessionChange', { 
        offenseTeamId: newOffenseTeamId 
      });
      if (false) console.log('[Offense Updated]', {
        from: previousOffenseTeamId,
        to: newOffenseTeamId,
        result_type: turnData.result_type
      });
    } else {
      if (false) console.log('[Offense Unchanged]', {
        offenseTeamId: scene.offenseTeamId,
        result_type: turnData.result_type
      });
    }
  } else {
    // No offense_team_id provided - keep current (shouldn't happen in normal flow)
    // ✅ REMOVED: Universal transition warning logging (cluttering console)
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
export async function finalizeTurnAfterAnimation({ 
  turn, 
  scene, 
  onUpdate, 
  possessionId, 
  turnIndex,
  updateDebugScore 
}) {
  // ✅ TIMEOUT: Removed deferred execution path
  // Scenario A: Executes immediately in handleTimeoutButtonClick when button is pressed during eligible turn
  // Scenario B: Executes immediately in checkAndExecuteQueuedTimeout when eligible turn is reached
  // No need to wait for turn completion - popup appears immediately in both scenarios
  
  // ✅ UNIVERSAL TRANSITION HANDLER - Handle possession flips and state transitions
  // This runs FIRST to ensure possession is correct before other finalization steps
  handleTurnTransition(scene, turn);
  
  // ✅ DEBUG: Log finalization
  if (false) console.log('[Finalizing]', {
    turnIndex: turnIndex ?? turn.index,
    result_type: turn.result_type,
    willSetPreviousTurnWasShot: turn.result_type === "MAKE" || turn.result_type === "MISS",
    hasOnUpdate: !!onUpdate
  });
  
  // Set flag if this was a shot turn (MAKE or MISS) so the next turn knows to skip step 0 ball attachment
  if (turn.result_type === "MAKE" || turn.result_type === "MISS") {
    scene._previousTurnWasShot = true;
    if (false) console.log('[Previous Turn Shot]', {
      turnIndex: turnIndex ?? turn.index,
      result_type: turn.result_type
    });
  }
  
  // ✅ SS&S: Use central announcement dispatcher for result announcements
  const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
  const homeTeamId = scene.simData?.home_team_id;
  
  // Route to appropriate announcement based on result_type
  if (turn.result_type === 'CHARGE') {
    // Charge: offensive foul on drive
    announceGameEvent('CHARGE', turn, scene, { 
      foulerId: turn.foul_player_id || turn.shooter_id 
    });
  } else if (turn.result_type === 'FOUL') {
    // ✅ FIX: Skip shooting fouls - they're already announced in ballManager.js
    // Shooting fouls result in free throws, so check for FREE_THROW next_play_type or free_throws_remaining
    // This is more reliable than text parsing which can fail
    const hasFreeThrowsRemaining = (turn.free_throws_remaining ?? 0) > 0;
    const nextPlayTypeIsFreeThrow = turn.next_play_type === 'FREE_THROW';
    const isShootingFoul = hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow;
    
    if (!isShootingFoul) {
      // Non-shooting fouls: announce as "OFFENSIVE FOUL!" or "DEFENSIVE FOUL!"
      const foulTeam = turn.foul_team || 'OFFENSE';
      const eventType = foulTeam === 'OFFENSE' ? 'FOUL_OFFENSIVE' : 'FOUL_DEFENSIVE';
      announceGameEvent(eventType, turn, scene, { foulerId: turn.foul_player_id });
    }
    // Note: Shooting fouls on misses are announced in ballManager.js with "Shooting Foul!"
    // AND-1 situations (result_type === "MAKE" with defensive foul) never reach this block
  } else if ((turn.result_type === 'MAKE' || turn.result_type === 'MISS') && 
             turn.foul_team === 'DEFENSE' && 
             turn.foul_player_id &&
             turn.text?.toLowerCase().includes('blocking foul')) {
    // Blocking foul: defensive foul on drive (detected by text containing "blocking foul")
    announceGameEvent('BLOCKING_FOUL', turn, scene, { 
      foulerId: turn.foul_player_id || turn.defenderId 
    });
  } else if (turn.result_type === 'STEAL') {
    announceGameEvent('STEAL', turn, scene, { 
      stealerId: turn.stealer_id || turn.defender_id,
      victimId: turn.victim_id 
    });
  } else if (turn.result_type === 'DEAD BALL' || turn.result_type === 'TURNOVER') {
    announceGameEvent('TURNOVER', turn, scene, { 
      victimId: turn.victim_id,
      turnoverType: turn.turnover_type 
    });
  }
  // Note: MAKE, MISS, FREE_THROW, REBOUND announced in their respective animation systems (ballManager, FreeThrowAnimationSystem)
  
  // Call onUpdate callback if provided
  if (onUpdate) {
    try {
      onUpdate(turn);
      if (false) console.log('[onUpdate]', {
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

