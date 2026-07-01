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
import { updatePlaycallCenter } from "../ui/playcallCenter.js";
import { announceFromTurnData } from "../utils/announcements.js";
import { syncSpriteAttributesFromPlayerEnergy } from "../utils/syncPlayerSpriteAttributes.js";
import { isBonusFreeThrowFoulTurn } from "../utils/foulAnnouncementClassifier.js";
import { resetSecondaryAnnounceCourtSfxDedup } from "../utils/gameSfx.js";
import {
  getBallController,
  getCurrentOwner,
  attachBallToPlayer,
  setCurrentOwner,
  clearPendingOwner,
} from "./BallControllerAdapter.js";
// ✅ TIMEOUT: Removed resetTimeoutQueue import - timeout queue persists until executed

function isHcoPlaycallTurn(turn) {
  if (!turn || typeof turn !== 'object') return false;
  const keys = ['offensive_state', 'current_turn', 'play_type'];
  return keys.some((key) => {
    const value = turn[key];
    return value != null && String(value).toUpperCase() === 'HCO';
  }) || turn.playcall === 'HCO';
}

function hidePlaycallStripAtInstigatingEvent(turn) {
  if (!isHcoPlaycallTurn(turn)) return;
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('gob:playcall-strip-hide', {
      detail: {
        reason: 'hco_instigating_event',
        resultType: turn.result_type || null,
        turnIndex: turn.index ?? null,
      },
    }));
  }
}

/**
 * Prepare a turn for animation by setting up all required state and UI updates.
 * 
 * This function handles all the setup that happens before calling playTurnAnimation,
 * including:
 * - Setting scene.currentTurn and turn.index
 * - Updating playcall display
 * - Updating strategy bars
 * - Updating playcall center
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
  resetSecondaryAnnounceCourtSfxDedup();

  // Steal ownership continuity probe (next turn start).
  // If a previous STEAL turn saved a checkpoint, compare owner continuity before this turn runs.
  if (scene?.__stealOwnershipCheckpoint) {
    let controllerOwnerId = null;
    let controllerOwnerPlayerId = null;
    let controllerAttached = null;
    let controllerInFlight = null;
    try {
      const ballController = getBallController();
      controllerOwnerId = ballController?.getCurrentOwnerId?.() ?? null;
      controllerOwnerPlayerId = ballController?.currentOwner?.playerId ?? null;
      controllerAttached = ballController?.isAttached ?? null;
      controllerInFlight = ballController?.isInFlight ?? null;
    } catch (_) {
      // Best-effort debug probe; never affect flow.
    }
    const ownerByAdapter = getCurrentOwner(scene);
    const checkpoint = scene.__stealOwnershipCheckpoint;
    console.log("[STEAL OWNERSHIP][NEXT TURN START]", {
      previousStealTurnId: checkpoint.turnId ?? null,
      previousStealTurnIndex: checkpoint.turnIndex ?? null,
      expectedStealerId: checkpoint.expectedStealerId ?? null,
      ownerAtStealTurnEnd: checkpoint.ownerAtStealTurnEnd ?? null,
      ownerAtNextTurnStart: ownerByAdapter ?? null,
      ownerAtNextTurnStartController: controllerOwnerId ?? controllerOwnerPlayerId ?? null,
      continuityOk:
        checkpoint.expectedStealerId != null
          ? String(ownerByAdapter ?? "") === String(checkpoint.expectedStealerId)
          : null,
      currentTurnId: turn?.turn_count ?? turn?.id ?? null,
      currentTurnIndex: turnIndex ?? null,
      currentResultType: turn?.result_type ?? null,
      currentPlayType: turn?.current_turn ?? turn?.play_type ?? null,
      currentNextPlayType: turn?.next_play_type ?? null,
      currentOffenseTeamId: turn?.offense_team_id ?? null,
      currentPossessionTeamId: turn?.possession_team_id ?? null,
      sceneOffenseTeamId: scene?.offenseTeamId ?? null,
      passInFlight: scene?.passInFlight ?? null,
      ballControllerAttached: controllerAttached,
      ballControllerInFlight: controllerInFlight,
    });
    scene.__stealOwnershipCheckpoint = null;
  }

  // AG-based movement: align sprite.attributes.AG with this turn’s NG (engine rescaling) before tweens run
  if (turn.player_energy && scene.playerSprites) {
    syncSpriteAttributesFromPlayerEnergy(scene.playerSprites, turn.player_energy);
  }
  
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
  
  // Scoreboard strategy stacks (tempo / aggr / alt) — reveal on first turn with call fields
  updateStrategyBars(turn, homeTeamId, scene?.simData);
  
  // Update Playcall Center panels
  updatePlaycallCenter(turn, homeTeamId);
  
  scene._leanScoreToAnimate = null;
  
  // ✅ SS&S: Use central announcement dispatcher
  // Check turn context and announce appropriately
  if (!turn._contextAnnouncementsShown) {
    const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
    
    // Context announcements (situation being entered)
    // ✅ FIX: Don't announce Fast Break if this turn is a steal OR if it came from a steal (steal announcement takes priority)
    // Check: 1) Not a STEAL turn itself, 2) Text doesn't mention steal, 3) Not a steal-initiated Fast Break (is_steal_entry flag)
    // Intent: announce when entering a FAST_BREAK turn (fast_break flag and/or current_turn) — Rim Runner, Covert Release, etc.
    const isStealInitiatedFastBreak = turn.roles?.is_steal_entry;
    const fastBreakIntent =
      turn.fast_break === true ||
      turn.current_turn === 'FAST_BREAK' ||
      turn.roles?.rim_runner_sequence === true;
    if (
      fastBreakIntent &&
      turn.result_type !== 'STEAL' &&
      !turn.text?.toLowerCase().includes('steal') &&
      !isStealInitiatedFastBreak
    ) {
      announceGameEvent('FAST_BREAK', turn, scene);
    }
    if (turn.rim_runner_bat_oob) {
      announceGameEvent('RIM_RUNNER_BATTED_OOB', turn, scene);
    } else if (turn.bat_oob) {
      // Generic batted-OOB (e.g. HCT §14 pass contest) — offense retains.
      announceGameEvent('BATTED_OOB', turn, scene);
    }
    
    // Pressure announcements (only for BASELINE_INBOUND setting up pressure)
    if (turn.result_type === 'BASELINE_INBOUND') {
      if (turn.next_defensive_setup === 'FCP') {
        announceGameEvent('PRESSURE_FCP', turn, scene);
      } else if (turn.next_defensive_setup === 'HCT') {
        announceGameEvent('PRESSURE_HCT', turn, scene);
      }
    }

    // Situational Logic (Q4/OT): announce Slow It Down / Quick Shot at start of HCO turn
    const isHCOTurn = turn.current_turn === 'HCO' || turn.play_type === 'HCO';
    if (isHCOTurn) {
      if (turn.slow_it_down) {
        announceGameEvent('SLOW_IT_DOWN', turn, scene);
      } else if (turn.quick_shot) {
        announceGameEvent('QUICK_SHOT', turn, scene);
      }
    }

    // Final Turn / FLSS: announce "Final Shot" at start of terminal EOQ shot attempts.
    const isTerminalFinalShotAttempt =
      (turn.final_turn || turn.flss || turn.final_shot_possession)
      && turn.result_type !== 'FINAL_HOLD';
    if (isTerminalFinalShotAttempt) {
      announceGameEvent('FINAL_SHOT', turn, scene, {
        suppressCourtSfx: turn.suppress_final_shot_sfx === true,
      });
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
  hidePlaycallStripAtInstigatingEvent(turn);
  
  // ✅ UNIVERSAL TRANSITION HANDLER - Handle possession flips and state transitions
  // This runs FIRST to ensure possession is correct before other finalization steps
  handleTurnTransition(scene, turn);
  
  // Set flag if this was a shot turn (MAKE or MISS) so the next turn knows to skip step 0 ball attachment
  if (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") {
    scene._previousTurnWasShot = true;
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
    // FOUL turns should always announce foul type, including bonus fouls that lead to free throws.
    // True shooting fouls are emitted as shot result turns (MAKE/MISS) and are announced there.
    const isBonusFoul = isBonusFreeThrowFoulTurn(turn);
    const isSchemaDrebOtb = (
      turn.current_turn === 'DREB' &&
      Boolean(turn.otb_foul) &&
      Array.isArray(turn.animation_steps) &&
      turn.animation_steps.length > 0
    );
    const isBlockingFoul = turn.foul_team === 'DEFENSE' && turn.text?.toLowerCase().includes('blocking foul');
    if (turn._quickFoulAnnounceDone) {
      // Quick Foul: announce already fired after reach-in (BIP/SIP, DREB, or Final Turn path).
    } else if (isSchemaDrebOtb) {
      // Backend schema step announces OTB after the rebounder reaches/attaches the ball.
    } else if (isBlockingFoul) {
      announceGameEvent('BLOCKING_FOUL', turn, scene, { foulerId: turn.foul_player_id || turn.defenderId });
    } else {
      const foulTeam = turn.foul_team || 'OFFENSE';
      const eventType = foulTeam === 'OFFENSE' ? 'FOUL_OFFENSIVE' : 'FOUL_DEFENSIVE';
      announceGameEvent(eventType, turn, scene, { foulerId: turn.foul_player_id, isBonusFoul });
    }
  } else if (turn.result_type === 'BLOCK' && !turn._blockAnnounced) {
    // Block: announce "BLOCK!" with blocker image (only if not already announced in ShotAnimationSystem)
    announceGameEvent('BLOCK', turn, scene, { blockerId: turn.blocker_id || turn.defenderId });
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
  } else if (
    (turn.result_type === 'DEAD BALL' || turn.result_type === 'TURNOVER') &&
    !turn.bat_oob &&
    !turn.rim_runner_bat_oob &&
    !turn.suppress_turn_prep_turnover_announce
  ) {
    // Batted-OOB is a DEAD BALL where the offense RETAINS — not a turnover. Its
    // headline is announced at turn start (BATTED_OOB), so skip the turnover one.
    announceGameEvent('TURNOVER', turn, scene, { 
      victimId: turn.victim_id,
      turnoverType: turn.turnover_type 
    });
  }
  // Note: MAKE, MISS, FREE_THROW rebounds — result headlines in animation layers (ballManager, ShotAnimationSystem, announceReboundHeadlineIfNeeded); standalone REBOUND in ReboundAnimationSystem.
  
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

  // Steal ownership continuity probe (turn end).
  // Save authoritative owner snapshot at the STEAL boundary for the next turn-start comparison.
  if (turn?.result_type === "STEAL") {
    let controllerOwnerId = null;
    let controllerOwnerPlayerId = null;
    let controllerAttached = null;
    let controllerInFlight = null;
    try {
      const ballController = getBallController();
      controllerOwnerId = ballController?.getCurrentOwnerId?.() ?? null;
      controllerOwnerPlayerId = ballController?.currentOwner?.playerId ?? null;
      controllerAttached = ballController?.isAttached ?? null;
      controllerInFlight = ballController?.isInFlight ?? null;
    } catch (_) {
      // Best-effort debug probe; never affect flow.
    }
    const expectedStealerId =
      turn?.stealerId ??
      turn?.stealer_id ??
      turn?.defender_id ??
      turn?.events?.find?.((e) => String(e?.event_type || "").toUpperCase() === "STEAL")?.stealer_id ??
      turn?.events?.find?.((e) => String(e?.event_type || "").toUpperCase() === "STEAL")?.stealerId ??
      null;
    let ownerByAdapter = getCurrentOwner(scene);
    // Steal boundary guard: if ownership drifted off the stealer by turn end,
    // force authoritative ownership now to prevent next-turn teleport.
    if (expectedStealerId != null && String(ownerByAdapter ?? "") !== String(expectedStealerId)) {
      const stealerSprite = scene?.playerSprites?.[String(expectedStealerId)] || null;
      if (stealerSprite && scene?.ballSprite) {
        attachBallToPlayer(scene, scene.ballSprite, stealerSprite, {
          reason: "steal_turn_end_guard",
        });
        setCurrentOwner(scene, String(expectedStealerId));
        clearPendingOwner(scene);
        scene.passInFlight = false;
        try {
          const { setBallHolderId } = await import('./ballAnimationSimple.js');
          setBallHolderId(scene, String(expectedStealerId));
        } catch (_) {
          // best-effort state mirror
        }
        ownerByAdapter = getCurrentOwner(scene);
      }
    }
    const snapshot = {
      turnId: turn?.turn_count ?? turn?.id ?? null,
      turnIndex: turnIndex ?? turn?.index ?? null,
      expectedStealerId: expectedStealerId != null ? String(expectedStealerId) : null,
      ownerAtStealTurnEnd: ownerByAdapter ?? null,
      ownerAtStealTurnEndController: controllerOwnerId ?? controllerOwnerPlayerId ?? null,
      resultType: turn?.result_type ?? null,
      nextPlayType: turn?.next_play_type ?? null,
      offenseTeamId: turn?.offense_team_id ?? null,
      possessionTeamId: turn?.possession_team_id ?? null,
      sceneOffenseTeamId: scene?.offenseTeamId ?? null,
      passInFlight: scene?.passInFlight ?? null,
      ballControllerAttached: controllerAttached,
      ballControllerInFlight: controllerInFlight,
    };
    scene.__stealOwnershipCheckpoint = snapshot;
    console.log("[STEAL OWNERSHIP][TURN END]", snapshot);
  }
}
