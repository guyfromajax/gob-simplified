import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import {
  STEAL_HCO_SETUP_MOVE_X_MIN,
  STEAL_HCO_SETUP_MOVE_X_MAX,
  STEAL_HCO_SETUP_MOVE_Y_RANGE,
  STEAL_HCO_SETUP_Y_MIN,
  STEAL_HCO_SETUP_Y_MAX,
} from "../constants/fastBreakConstants.js";
import {
  shootBall,
  SHOT_DEBUG,
  animateRebound,
  animateKickoutReset
} from "./ballManager.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { runPass, PASS_DEBUG, tweenPlayerTo } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { deriveOffenseContext, computeFastBreakOutletTarget } from "./outletUtils.js";
import { DEBUG } from "../utils/debug.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import {
  States,
  getDebugTransitions,
  safeTransition,
  createTransitionGuard,
  transitionWithDebug,
} from "../state/gameStateMachine.js";
import {
  ENABLE_TIMEOUT_BUTTON,
  initTimeoutButton,
  resetTimeoutQueue,
  checkTimeoutEligibility,
} from "../utils/timeoutButtonManager.js";
import {
  getPendingOwner,
  clearPendingOwner,
  setPendingOwner,
  setCurrentOwner,
  getCurrentOwner
} from "./BallControllerAdapter.js";
// ✅ NEW (Step 1): Import simple ball holder state functions
// ✅ STEP 3 MIGRATION: Import new ball animation function
import {
  initializeBallHolderState,
  setBallHolderId,
  clearBallHolder,
  animateBallToPosition,
} from "./ballAnimationSimple.js";

// Cap the time spent on any single movement step. Large timestamp gaps can
// otherwise produce multi‑second tweens that appear as animation stalls.
const MAX_STEP_DURATION = 1000; // ms - for HCO step movements
const MAX_TRANSITION_DURATION = 3000; // ms - for transition movements (DREB, inbound, etc.)

// Animation speed constants (pixels per second)
// Based on learnings from WIP_GOB repository for smooth, consistent animations
// These ensure consistent speeds regardless of distance, making animations feel natural
// Speed can be changed dynamically via gameSpeedManager
const DEFAULT_PLAYER_SPEED = 450; // Default speed (Normal preset)
const DEFAULT_BALL_SPEED = 450; // Default speed (Normal preset)

/**
 * Get current player speed (can be changed dynamically)
 * @returns {number} Speed in pixels per second
 */
function getPlayerSpeed() {
  // Check for dynamic speed from gameSpeedManager
  if (typeof window !== 'undefined' && window.__GAME_SPEED) {
    return window.__GAME_SPEED;
  }
  return DEFAULT_PLAYER_SPEED;
}

/**
 * Get current ball speed (can be changed dynamically)
 * @returns {number} Speed in pixels per second
 */
function getBallSpeed() {
  // Ball speed matches player speed for consistency
  return getPlayerSpeed();
}

/**
 * Calculate animation duration based on distance traveled
 * This ensures consistent speeds regardless of distance, making animations feel natural
 * 
 * @param {number} currentX - Current X position in pixels
 * @param {number} currentY - Current Y position in pixels
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @param {number} speed - Speed in pixels per second
 * @param {number} maxDuration - (Unused) maximum duration in milliseconds (kept for backwards compatibility)
 * @returns {number} Duration in milliseconds
 */
function getDurationFromDistance(currentX, currentY, targetX, targetY, speed, maxDuration = MAX_STEP_DURATION) {
  const distance = Phaser.Math.Distance.Between(currentX, currentY, targetX, targetY);
  const duration = (distance / speed) * 1000; // Convert to milliseconds
  // Clamp to a small minimum to avoid zero-length tweens; no upper cap so distance fully determines time
  return Math.max(50, duration);
}

/**
 * Calculate player movement duration based on distance from current sprite position to target
 * Uses the sprite's actual current position (sprite.x, sprite.y) as the starting point,
 * which ensures smooth transitions between turns without requiring setup tweens.
 * 
 * @param {Phaser.GameObjects.Sprite} sprite - The player sprite
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @param {boolean} isTransition - If true, use MAX_TRANSITION_DURATION instead of MAX_STEP_DURATION
 * @returns {number} Duration in milliseconds
 */
/**
 * Steal HCO Setup Animation
 * Moves the stealer (ball handler) back away from basket before HCO skeleton starts
 */
async function animateStealHCOSetup(scene, turnData, playerSprites, ballSprite) {
  const ballHandlerId = turnData.roles?.ball_handler_id;
  const ballHandlerSprite = ballHandlerId ? playerSprites[ballHandlerId] : null;
  
  if (!ballHandlerSprite) {
    console.warn("Steal HCO Setup: Ball handler sprite not found", { 
      ballHandlerId,
      roles: turnData.roles
    });
    return;
  }
  
  // Ball should already be attached to stealer from the steal turn
  // Verify attachment
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  if (!ballController?.isAttached || ballController.currentOwner !== ballHandlerSprite) {
    // Attach ball to stealer if not already attached
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_hco_setup_verify'
    });
  }
  
  // Get stealer's current position
  const currentGrid = {
    x: ballHandlerSprite.gridX || 50,
    y: ballHandlerSprite.gridY || 25
  };
  
  // ✅ DETAILED LOGGING: Track frontend HCO Setup calculation
  console.warn("🏀 [FRONTEND STEAL HCO SETUP] Entry:", {
    ballHandlerId,
    currentSpritePosition: { x: ballHandlerSprite.gridX, y: ballHandlerSprite.gridY },
    roles: turnData.roles,
    backendFinalX: turnData.roles?.ball_handler_hco_setup_x,
    backendFinalY: turnData.roles?.ball_handler_hco_setup_y,
    backendMoveX: turnData.roles?.ball_handler_hco_setup_move_x,
    backendMoveY: turnData.roles?.ball_handler_hco_setup_move_y
  });
  
  // Determine offense team and direction (away from basket)
  const isHomeOffense = ballHandlerSprite.team === "home";
  const direction = isHomeOffense ? -1 : 1; // -1 for home (away from x=90), +1 for away (away from x=10)
  
  // Calculate steal HCO setup movement (matches backend calculation)
  const moveX = turnData.roles?.ball_handler_hco_setup_move_x || 
                Phaser.Math.Between(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX);
  const moveY = turnData.roles?.ball_handler_hco_setup_move_y || 
                Phaser.Math.Between(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE);
  
  // ✅ FIX: Use backend-provided final coordinates if available (more accurate)
  // Otherwise, calculate from current position
  let targetGrid;
  if (turnData.roles?.ball_handler_hco_setup_x !== undefined && turnData.roles?.ball_handler_hco_setup_y !== undefined) {
    // Use backend-calculated final position
    targetGrid = {
      x: turnData.roles.ball_handler_hco_setup_x,
      y: turnData.roles.ball_handler_hco_setup_y
    };
    console.warn("🏀 [FRONTEND STEAL HCO SETUP] Using backend final coordinates:", targetGrid);
  } else {
    // Fallback: Calculate from current position (shouldn't happen if backend is correct)
    targetGrid = {
      x: currentGrid.x + (direction * moveX),
      y: Phaser.Math.Clamp(
        currentGrid.y + moveY,
        STEAL_HCO_SETUP_Y_MIN,
        STEAL_HCO_SETUP_Y_MAX
      )
    };
    console.warn("⚠️ [FRONTEND STEAL HCO SETUP] Calculated target (backend coords missing):", targetGrid);
  }
  
  console.warn("🏀 [FRONTEND STEAL HCO SETUP] Movement Details:", {
    startingPosition: currentGrid,
    direction,
    moveX,
    moveY,
    targetPosition: targetGrid,
    calculation: `${currentGrid.x} + (${direction} * ${moveX}) = ${targetGrid.x}`
  });
  
  // Convert to pixel coordinates
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
  
  // Get animation duration
  const playerDuration = getPlayerDuration(ballHandlerSprite, targetPx.x, targetPx.y, true);
  
  // Animate stealer movement
  await tweenPlayerTo(scene, ballHandlerSprite, targetPx, {
    duration: playerDuration,
    easing: "Linear"
  });
  
  // Update sprite grid coordinates
  ballHandlerSprite.gridX = targetGrid.x;
  ballHandlerSprite.gridY = targetGrid.y;
  
  // Verify ball remains attached after movement
  if (ballController && (!ballController.isAttached || ballController.currentOwner !== ballHandlerSprite)) {
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_hco_setup_post_movement'
    });
  }
  
  // Animate all 9 other players (toward the new offense basket)
  const otherPlayersMovements = turnData.roles?.other_players_hco_setup_movements || [];
  if (otherPlayersMovements.length > 0) {
    console.warn(`🏀 [FRONTEND STEAL HCO SETUP] Animating ${otherPlayersMovements.length} other players toward new offense basket`);
    
    const promises = [];
    for (const movement of otherPlayersMovements) {
      const playerSprite = playerSprites[movement.player_id];
      if (!playerSprite) {
        console.warn(`⚠️ [FRONTEND STEAL HCO SETUP] Player sprite not found: ${movement.player_id}`);
        continue;
      }
      
      // Get current position
      const currentGrid = {
        x: playerSprite.gridX || movement.start_x,
        y: playerSprite.gridY || movement.start_y
      };
      
      // Use backend-calculated final position
      const targetGrid = {
        x: movement.final_x,
        y: movement.final_y
      };
      
      // Convert to pixel coordinates
      const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
      
      // Get animation duration
      const duration = getPlayerDuration(playerSprite, targetPx.x, targetPx.y, true);
      
      // Animate player movement
      promises.push(
        tweenPlayerTo(scene, playerSprite, targetPx, {
          duration: duration,
          easing: "Linear"
        }).then(() => {
          // Update sprite grid coordinates
          playerSprite.gridX = targetGrid.x;
          playerSprite.gridY = targetGrid.y;
        })
      );
    }
    
    // Wait for all other players to finish animating
    await Promise.all(promises);
    console.warn(`🏀 [FRONTEND STEAL HCO SETUP] All ${otherPlayersMovements.length} other players finished animating`);
  }
}

function getPlayerDuration(sprite, targetX, targetY, isTransition = false) {
  const currentX = sprite.x;
  const currentY = sprite.y;
  const maxDuration = isTransition ? MAX_TRANSITION_DURATION : MAX_STEP_DURATION;
  const speed = getPlayerSpeed();
  return getDurationFromDistance(currentX, currentY, targetX, targetY, speed, maxDuration);
}

/**
 * Calculate ball movement duration based on distance from current sprite position to target
 * 
 * @param {Phaser.GameObjects.Sprite} ballSprite - The ball sprite
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @returns {number} Duration in milliseconds
 */
function getBallDuration(ballSprite, targetX, targetY) {
  if (!ballSprite) return 300; // Default fallback if ball sprite doesn't exist
  const currentX = ballSprite.x;
  const currentY = ballSprite.y;
  const speed = getBallSpeed();
  return getDurationFromDistance(currentX, currentY, targetX, targetY, speed);
}

function delayMs(scene, ms) {
  const safe = Math.max(0, Math.floor(Number(ms) || 0));
  if (!safe) return Promise.resolve();
  if (scene?.time?.delayedCall) {
    return new Promise((resolve) => scene.time.delayedCall(safe, resolve));
  }
  return new Promise((resolve) => setTimeout(resolve, safe));
}

function getStepBallHandlerId(animations, stepIndex) {
  if (!Array.isArray(animations)) return null;
  for (const anim of animations) {
    if (anim?.hasBallAtStep?.[stepIndex]) return anim.playerId;
  }
  for (const anim of animations) {
    const step = anim?.movement?.[stepIndex];
    const action = step?.action;
    if (action === "handle_ball" || action === "receive" || action === "pass" || action === "shoot" || action === "drive") {
      return anim.playerId;
    }
  }
  return null;
}


/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
/**
 * Update ball ownership (step-index based)
 * Delegates to unified updateBallOwnership function
 * @param {Object} options
 * @param {Phaser.Scene} options.scene
 * @param {Phaser.GameObjects.Sprite} options.ballSprite
 * @param {Array} options.animations
 * @param {Object} options.playerSprites
 * @param {number} options.stepIndex
 * @param {string} [options.offenseTeamId]
 * @param {Object} [options.currentBallOwnerRef]
 */
async function updateBallOwnership({ scene, ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  const { updateBallOwnership: unifiedUpdate } = await import('./BallControllerAdapter.js');
  return unifiedUpdate({
    scene,
    ballSprite,
    animations,
    playerSprites,
    stepIndex,
    offenseTeamId,
    currentBallOwnerRef
  });
}

/**
 * Smoothly move all players to their step 0 positions before possession begins.
 * Locks the ball to the player with hasBallAtStep[0] during this setup tween.
 */

async function runSetupTween({ scene, ballSprite, animations, playerSprites, currentBallOwnerRef, turnData = null, stepDurationMs = null }) {
  if (scene.skipToEnd) return;
  const stepIndex = 0;
  const promises = [];
  const shouldClampXToRims =
    turnData?.result_type !== "SIDE_INBOUND" &&
    turnData?.result_type !== "BASELINE_INBOUND";

  for (const anim of animations) {
    if (scene.skipToEnd) break;
    const sprite = playerSprites[anim.playerId];
    const firstStep = anim.movement?.[stepIndex];
    if (!sprite || !firstStep) continue;

    const targetGridX = shouldClampXToRims
      ? Phaser.Math.Clamp(firstStep.coords.x, 9, 91)
      : firstStep.coords.x;

    const { x, y } = gridToPixels(
      targetGridX,
      firstStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    // ✅ FIX: Use distance-based duration for consistent speed (matches step animations)
    // This ensures smooth transitions between turns and consistent speeds
    const duration = getPlayerDuration(sprite, x, y);

    promises.push(new Promise((resolve) => {
      const tween = scene.tweens.add({
        targets: [sprite],
        x,
        y,
        duration,
        ease: "Linear",
        onUpdate: () => {
          if (currentBallOwnerRef?.value === sprite && ballSprite?.setPosition) {
            ballSprite.setPosition(sprite.x, sprite.y);
            ballSprite.setVisible(true);
          }
        },
        onComplete: resolve,
        onStop: resolve
      });
      if (scene.skipToEnd) {
        tween.stop();
      }
    }));
  }

  await Promise.all(promises);
}

// Setup sideline inbound play
async function runSideInboundSetup({ scene, ballSprite, playerSprites, turnData, context = null }) {
  if (!turnData || scene?.skipToEnd || scene?.stateMachine?.is(States.FreeThrow)) return;

  scene.isInboundSetup = true;
  
  // Allow transition from HalfCourt (after fouls) or other states
  // Only transition if not already in Inbound state
  if (!scene.stateMachine?.is(States.Inbound)) {
    // If coming from HalfCourt (e.g., after a foul), transition through Turnover first
    if (scene.stateMachine?.is(States.HalfCourt)) {
      safeTransition(
        scene.stateMachine,
        States.Turnover,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    }
    
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }

  const { ball_spot, oDestinations = {}, dDestinations = {}, possession_team_id } = turnData;
  const offenseTeamId = scene.offenseTeamId ?? possession_team_id;

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const cfg = globalThis?.animation_config?.sideInbound || {};
  const ease = cfg.ease ?? "Linear"; // Use Linear to match HCO step movements

  const offenseSprites = {};
  const defenseSprites = {};
  const offenseIds = {};

  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  if (!scene.ballSprite) scene.ballSprite = ballSprite;

  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (String(sprite.team_id) === String(offenseTeamId)) {
      offenseSprites[info.pos] = sprite;
      offenseIds[info.pos] = id;
    } else {
      defenseSprites[info.pos] = sprite;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  // ✅ Move ball to inbound spot immediately (matching BIP behavior)
  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
    // Kill any existing ball tweens to ensure it stays at the spot
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  }

  // ✅ Move ball to inbound spot immediately (matching BIP behavior)
  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
    // Kill any existing ball tweens to ensure it stays at the spot
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  }

  const promises = [];
  const sfSprite = offenseSprites["SF"];
  const sfId = offenseIds["SF"];
  
  const addTween = (sprite, coords, pos) => {
    if (!sprite || !coords) return;
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    // Use distance-based duration for consistent speed
    const duration = getPlayerDuration(sprite, x, y);
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x,
          y,
          duration,
          ease,
          onStart: () => animationDebugLog(`tweenStart:${pos}`),
            onComplete: async () => {
            animationDebugLog(`tweenEnd:${pos}`);
            // ✅ Attach ball to SF when SF reaches the inbound spot (matching BIP behavior)
            if (pos === "SF" && sfSprite && ballSprite && ball_spot) {
              attachBallToPlayer(scene, ballSprite, sfSprite);
              animationDebugLog(`[sideInbound][ballAttach][SF] sf:${sfId}`);
              const holdMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
              await new Promise(resolve => setTimeout(resolve, holdMs));
            }
            resolve();
          },
          onStop: async () => {
            animationDebugLog(`tweenEnd:${pos}`);
            // ✅ Also attach on stop (in case tween is interrupted)
            if (pos === "SF" && sfSprite && ballSprite && ball_spot) {
              attachBallToPlayer(scene, ballSprite, sfSprite);
              animationDebugLog(`[sideInbound][ballAttach][SF] sf:${sfId}`);
              const holdMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
              await new Promise(resolve => setTimeout(resolve, holdMs));
            }
            resolve();
          }
        });
      })
    );
  };

  Object.entries(oDestinations).forEach(([pos, coords]) => addTween(offenseSprites[pos], coords, pos));
  Object.entries(dDestinations).forEach(([pos, coords]) => addTween(defenseSprites[pos], coords, pos));

  await Promise.all(promises);
  
  // ✅ TIMEOUT: Removed 2-second pause - timeout button is now always live

  // ✅ REFACTOR: Use passDetection.js for dynamic passes, fallback to hardcoded SF→PG
  const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
  
  // Check if turnData has animations with pass actions
  let passInfo = null;
  if (turnData.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
    // Find the step index where the pass happens (typically the last step after positioning)
    const maxSteps = Math.max(...turnData.animations.map(anim => anim.movement?.length || 0));
    // Check the last step for pass actions
    if (maxSteps > 0) {
      passInfo = detectPassAtStep(turnData.animations, maxSteps - 1);
    }
  }
  
  // Fallback to hardcoded SF→PG if no pass detected in animation data
  // ✅ Note: Ball is already attached to SF when SF reached the inbound spot (above)
  const pgSprite = offenseSprites["PG"];
  const pgId = offenseIds["PG"];
  
  if (sfSprite) {
    // ✅ Ball attachment already happened when SF reached the spot (in tween onComplete)
    // Only attach here as a safety fallback if attachment didn't happen
    const ballController = scene.ballController || (scene.ballSprite?.ballController);
    if (!ballController?.isAttached || ballController?.currentOwner !== sfSprite) {
      attachBallToPlayer(scene, ballSprite, sfSprite);
      animationDebugLog("ballAttach(SF) - fallback");
    }

    animationDebugLog(`[sideInbound][holdStart] sf:${sfId} pg:${pgId}`);
    // Removed 1000ms pause for smoother transitions

    scene.events?.once('passStart', () => animationDebugLog('passStart'));
    scene.events?.once('tweenStart', () => animationDebugLog('tweenStart'));
    scene.events?.once('tweenEnd', () => animationDebugLog('tweenEnd'));
    scene.events?.once('passEnd', () => animationDebugLog('passEnd'));

    animationDebugLog(`[sideInbound][passStart] sf:${sfId} pg:${pgId}`);
    
    // ✅ TIMEOUT: Removed markInboundPassStarted - button is always live now
    
    if (!scene.stateMachine?.is(States.FastBreak)) {
      // ✅ Force Foul: when next turn is Quick Foul, animate defender to receiver in same step as the pass
      const nextTurn = context?.nextTurn;
      const isQuickFoulNext = nextTurn?.quick_foul && nextTurn?.result_type === 'FOUL';
      const passPromise = passInfo
        ? (console.log('🏀 [SIDE_INBOUND] Using dynamic pass from animation data', passInfo),
           handlePassAnimation({ scene, passInfo, playerSprites }))
        : pgSprite
          ? (console.log('🏀 [SIDE_INBOUND] Using fallback hardcoded SF→PG pass'),
             runPass(scene, { fromId: sfId, toId: pgId, easing: ease }))
          : Promise.resolve();

      let defenderPromise = Promise.resolve();
      if (isQuickFoulNext) {
        const receiverId = passInfo?.receiverId ?? pgId;
        const receiverSprite = playerSprites[receiverId];
        const defenderSprite = nextTurn.foul_player_id ? playerSprites[nextTurn.foul_player_id] : null;
        if (receiverSprite && defenderSprite) {
          defenderPromise = animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite);
          nextTurn._quickFoulAnimatedDuringInbound = true;
        }
      }
      await Promise.all([passPromise, defenderPromise]);
    }

    animationDebugLog(`[sideInbound][passEnd] sf:${sfId} pg:${pgId}`);
    if (pgSprite) {
      animationDebugLog(`[sideInbound][pgAttach] sf:${sfId} pg:${pgId}`);
    }
    if (scene.stateMachine?.is(States.Inbound))
      safeTransition(
        scene.stateMachine,
        States.HalfCourt,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
  }
  scene.isInboundSetup = false;
  scene.passInFlight = false;
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
}

// Setup positions after a defensive rebound before new half-court offense or fast break
async function runDefensiveReboundSetup({ scene, ballSprite, playerSprites, rebounderId, nextPlayType = "HCO", turnData = null }) {
  // Get the offense_getback list from the MISS turn that led to this DREB
  // For Fast Break MISS → DREB, the offense_getback is from the previous HCO MISS turn
  // For regular HCO MISS → DREB, the offense_getback is from the current MISS turn
  // The turnData parameter is the current turn (for animations), but we may need to look
  // at the previous turn for offense_getback if this is a Fast Break MISS
  let missTurnForGetback = turnData;
  if (!missTurnForGetback || !missTurnForGetback.offense_getback) {
    // Try previous turn if current turn doesn't have offense_getback (Fast Break case)
    const currentIndex = scene.currentTurn || 0;
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    if ((previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") && previousTurn.offense_getback) {
      missTurnForGetback = previousTurn;
    } else if (!missTurnForGetback) {
      // Fallback: try current turn
      const currentTurn = scene.simData?.turns?.[currentIndex];
      if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") {
        missTurnForGetback = currentTurn;
      }
    }
  }
  
  const getBackList = missTurnForGetback?.offense_getback || [];
  
  // runDefensiveReboundSetup called
  
  animationDebugLog('runDefensiveReboundSetup called with:', { rebounderId, nextPlayType });
  if (!scene || !playerSprites || rebounderId == null) return;

  const rebounderSprite = playerSprites[rebounderId];
  if (!rebounderSprite) return;

  scene.possessionFlipInProgress = true;
  
  // CRITICAL: Don't attach ball if a putback is in progress
  // The putback shot animation is still running, and attaching the ball here
  // causes a flash before the shot animation completes
  // ✅ PHASE 4: Check BallController state instead of old _putbackInProgress flag
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  const isPutbackInProgress = ballController && (ballController.reason === 'putback_shot' || ballController.state === 'PUTBACK_ATTEMPT');
  if (!isPutbackInProgress && ballSprite) {
    attachBallToPlayer(scene, ballSprite, rebounderSprite);
  }

  if (scene.stateMachine?.is(States.Rebound)) {
    if (DebugFlags?.FSM) animationDebugLog('FSM: Rebound -> OutletSetup');
    safeTransition(
      scene.stateMachine,
      States.OutletSetup,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  const rebounderTeamKey = rebounderSprite.team;
  const { newOffenseTeam, newOffenseBasket } = deriveOffenseContext(rebounderTeamKey);
  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const rebGridX = (rebounderSprite.x / width) * 100;
  const rebGridY = 50 - (rebounderSprite.y / height) * 50;

  // Find the outlet pass receiver
  // For fast breaks that came from a previous turn (not a separate fast break turn),
  // we don't have outlet_receiver data, so we find the PG
  let outletReceiverId = null;
  let outletReceiverSprite = null;
  
  // For HCO, always find the PG
  // CRITICAL: This must find the PG for the outlet pass to execute
  // First try scene.playerInfo (preferred, has position data)
  for (const [id, info] of Object.entries(scene.playerInfo || {})) {
    if (info.pos === "PG" && info.team === rebounderSprite.team) {
      outletReceiverId = id;
      outletReceiverSprite = playerSprites[id];
      break;
    }
  }
  
  // ✅ FALLBACK: If scene.playerInfo lookup failed, try finding PG from playerSprites
  // This can happen when runDefensiveReboundSetup() is called before scene.playerInfo is fully populated
  if (!outletReceiverId) {
    console.warn('🏀 [DREB OUTLET] PG not found in scene.playerInfo, trying fallback lookup from playerSprites', {
      rebounderTeam: rebounderSprite.team,
      playerInfoCount: Object.keys(scene.playerInfo || {}).length,
      playerSpritesCount: Object.keys(playerSprites).length
    });
    
    // Try to find PG by checking sprite properties or by position
    // Look for a sprite on the rebounder's team that might be the PG
    // We'll use the first player on the rebounder's team as a fallback
    for (const [id, sprite] of Object.entries(playerSprites)) {
      if (sprite.team === rebounderSprite.team && id !== rebounderId) {
        // Check if sprite has position info
        if (sprite.pos === "PG" || sprite.position === "PG") {
          outletReceiverId = id;
          outletReceiverSprite = sprite;
          console.log('🏀 [DREB OUTLET] Found PG via fallback lookup', { outletReceiverId: id });
          break;
        }
      }
    }
    
    // If still not found, use the first non-rebounder player on the rebounder's team as a last resort
    if (!outletReceiverId) {
      for (const [id, sprite] of Object.entries(playerSprites)) {
        if (sprite.team === rebounderSprite.team && id !== rebounderId) {
          outletReceiverId = id;
          outletReceiverSprite = sprite;
          console.warn('🏀 [DREB OUTLET] Using fallback: first non-rebounder player as outlet receiver', { outletReceiverId: id });
          break;
        }
      }
    }
  }
  
  // Always log outlet receiver lookup (not just when DebugFlags?.OUTLET is enabled)
  console.log('🏀 runDefensiveReboundSetup: Outlet receiver lookup', {
    rebounderId,
    rebounderTeam: rebounderSprite.team,
    nextPlayType,
    outletReceiverId,
    hasOutletReceiverSprite: !!outletReceiverSprite,
    playerInfoCount: Object.keys(scene.playerInfo || {}).length,
    playerInfoKeys: Object.keys(scene.playerInfo || {}),
    playerInfoEntries: Object.entries(scene.playerInfo || {}).map(([id, info]) => ({
      id,
      pos: info.pos,
      team: info.team
    }))
  });
  
  // Debug logging for outlet pass setup
  if (DebugFlags?.OUTLET) {
    animationDebugLog('Outlet setup debug:', {
      rebounderId,
      nextPlayType,
      outletReceiverId,
      rebounderSprite: rebounderSprite ? {
        team: rebounderSprite.team
      } : null,
      playerInfo: scene.playerInfo,
      allPlayerIds: Object.keys(scene.playerInfo || {})
    });
  }

  const promises = [];
  let outletTarget = null;
  let outletContext = null;

  // Set up outlet receiver movement and outlet pass for HCO ONLY
  // FAST_BREAK has its own outlet pass in the fast break sequence (animateOutletPhase in fastBreak.js)
  // These two outlet steps are MUTUALLY EXCLUSIVE - never run together
  if (outletReceiverId && outletReceiverId !== rebounderId && outletReceiverSprite && nextPlayType === "HCO") {
    
    // Move PG near the rebounder for outlet pass
    const sign = newOffenseBasket.x > rebGridX ? 1 : -1;
    outletTarget = {
      x: Phaser.Math.Clamp(
        rebGridX + sign * Phaser.Math.Between(3, 6),
        4,
        97
      ),
      y: Phaser.Math.Clamp(
        rebGridY + Phaser.Math.Between(-6, 6),
        1,
        50
      ),
    };
    outletContext = {
      newOffenseTeam,
      newOffenseBasket,
      direction: sign,
    };

    const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // isTransition=true allows longer durations for transition movements
    const outletDuration = getPlayerDuration(outletReceiverSprite, outletPx.x, outletPx.y, true);
    promises.push(
      tweenPlayerTo(scene, outletReceiverSprite, outletPx, {
        duration: outletDuration,
        easing: 'Linear', // Match HCO step movements for consistent feel
      })
    );
    
    if (DebugFlags?.BALL) {
      animationDebugLog('outletTarget', {
        outletReceiverId,
        outletTarget,
        nextPlayType,
        newOffenseTeam,
        rebounderTeam: rebounderSprite.team,
        attackRimX: newOffenseBasket.x,
        bounds: outletContext?.bounds,
      });
    }
    if (DebugFlags?.OUTLET) animationDebugLog(`${nextPlayType} outlet receiver movement queued`);
  } else if (nextPlayType === "HCO") {
    // Log why outlet receiver movement was skipped (for debugging)
    console.warn('🏀 runDefensiveReboundSetup: Outlet receiver movement skipped', {
      outletReceiverId,
      rebounderId,
      hasOutletReceiverSprite: !!outletReceiverSprite,
      nextPlayType,
      reason: !outletReceiverId ? 'No outlet receiver found' : 
              outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' :
              !outletReceiverSprite ? 'Outlet receiver sprite not found' :
              'Unknown reason'
    });
  }

  // For HCO and FAST_BREAK scenarios, move all other players toward the new offense basket
  // The difference is: HCO executes outlet pass here, FAST_BREAK handles outlet pass in its own sequence
  // But BOTH need players to animate into position during the outlet step
  if (nextPlayType === "HCO" || nextPlayType === "FAST_BREAK") {
    animationDebugLog('HCO scenario detected, moving other players toward new offense basket');
    // Determine the new offense basket
    // In defensive rebound: rebounder's team becomes the new offense team
    animationDebugLog('New offense basket:', newOffenseBasket, 'Rebounder team:', rebounderSprite.team, 'New offense team:', newOffenseTeam);
    
    // Debug: Check for extra sprites without playerInfo
    animationDebugLog('Player sprites keys:', Object.keys(playerSprites));
    animationDebugLog('Scene playerInfo keys:', Object.keys(scene.playerInfo || {}));
    const extraSprites = Object.keys(playerSprites).filter(id => !scene.playerInfo?.[id]);
    if (extraSprites.length > 0) {
      animationDebugWarn('EXTRA SPRITES DETECTED (no playerInfo):', extraSprites);
      // Hide these extra sprites
      extraSprites.forEach(id => {
        const sprite = playerSprites[id];
        if (sprite) {
          animationDebugLog(`Hiding extra sprite: ${id}`, { team: sprite.team, position: { x: sprite.x, y: sprite.y } });
          sprite.setVisible(false);
        }
      });
    }
    
    let playersMoved = 0;
    let playersSkipped = 0;
    let playersSkippedReasons = {
      noInfo: 0,
      isRebounder: 0,
      isOutletReceiver: 0,
      isGetBackPlayer: 0
    };
    
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      const isGetBackPlayer = getBackList.includes(id);
      
      // Collect skip reasons for debugging
      let skipReason = null;
      if (!info) {
        skipReason = 'noInfo';
        playersSkippedReasons.noInfo++;
      } else if (id === rebounderId) {
        skipReason = 'isRebounder';
        playersSkippedReasons.isRebounder++;
      } else if (id === outletReceiverId) {
        skipReason = 'isOutletReceiver';
        playersSkippedReasons.isOutletReceiver++;
      } else if (isGetBackPlayer) {
        skipReason = 'isGetBackPlayer';
        playersSkippedReasons.isGetBackPlayer++;
      }
      
      // CRITICAL: Exclude get-back players from DREB animation
      // These players already animated back during the shot attempt, so animating them again
      // causes the extra animation step bug. They should already be in position.
      // 
      // BUG CHECK: If only get-back player animates, it means ALL OTHER players have a skipReason.
      // This suggests a condition might be inverted or all players are being incorrectly skipped.
      if (skipReason) {
        playersSkipped++;
        continue;
      }
      
      // Calculate movement toward new offense basket
      const currentGridX = (sprite.x / width) * 100;
      const currentGridY = 50 - (sprite.y / height) * 50;
      
      // Move 20-30 grid spots toward new offense basket
      const distance = Phaser.Math.Between(20, 30);
      // Determine direction based on new offense team:
      // In defensive rebound: rebounder's team becomes the new offense team
      // If new offense team is home (basket at x=89), all players move right (increase x)
      // If new offense team is away (basket at x=11), all players move left (decrease x)
      const direction = newOffenseTeam === "home" ? 1 : -1;
      
      const targetGrid = {
        x: Phaser.Math.Clamp(
          currentGridX + direction * distance,
          9,  // Stay between rims
          91
        ),
        y: Phaser.Math.Clamp(
          currentGridY + Phaser.Math.Between(-10, 10),
          10,  // Keep players well inside court
          40   // Keep players well inside court
        ),
      };
      
      const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
      // Use distance-based duration for consistent speed (same as HCO step movements)
      // isTransition=true allows longer durations for transition movements
      const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
      
      // Animate player in DREB outlet step
      
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: playerDuration,
          easing: 'Linear', // Match HCO step movements for consistent feel
        }).then(() => {
          playersMoved++;
        })
      );
      
      animationDebugLog(`HCO player movement: ${id} from (${currentGridX.toFixed(1)}, ${currentGridY.toFixed(1)}) to (${targetGrid.x}, ${targetGrid.y}) [direction: ${direction}, newOffenseTeam: ${newOffenseTeam}]`);
    }
    
    if (playersMoved === 0 || playersMoved === 1) {
      console.warn('⚠️ [OUTLET STEP] Few players animated:', {
        totalPlayers: Object.keys(playerSprites).length,
        playersAnimated: playersMoved,
        playersSkipped,
        playersSkippedReasons
      });
    }
    animationDebugLog(`Total players moved for HCO: ${playersMoved}`);
  } else {
    animationDebugLog('Not HCO or FAST_BREAK scenario, nextPlayType:', nextPlayType);
  }

  await Promise.all(promises);

  // Do outlet pass for HCO ONLY
  // FAST_BREAK outlet pass is handled separately in fastBreak.js (animateOutletPhase)
  // These two outlet steps are MUTUALLY EXCLUSIVE - never run together
  // For FCP/HCT: No outlet pass - players go directly to press positions
  // CRITICAL: This outlet pass step is required for smooth DREB -> HCO transitions
  // The outlet pass MUST execute if we have an outletReceiverId, even if receiver movement was skipped
  if (nextPlayType === "HCO" && outletReceiverId && outletReceiverId !== rebounderId) {
    // If outletReceiverSprite is missing, try to get it from playerSprites
    if (!outletReceiverSprite && outletReceiverId) {
      outletReceiverSprite = playerSprites[outletReceiverId];
      console.log('🏀 runDefensiveReboundSetup: Re-fetched outlet receiver sprite', {
        outletReceiverId,
        hasSprite: !!outletReceiverSprite
      });
    }
    
    // If outletTarget wasn't set (receiver movement was skipped), use receiver's current position
    if (!outletTarget && outletReceiverSprite) {
      outletTarget = {
        x: (outletReceiverSprite.x / width) * 100,
        y: 50 - (outletReceiverSprite.y / height) * 50
      };
      console.log('🏀 runDefensiveReboundSetup: Using receiver current position as outlet target', outletTarget);
    } else if (!outletTarget) {
      // If we still don't have outletTarget and no sprite, log a warning but proceed anyway
      // runPass will use the receiver's current position from playerSprites
      console.warn('🏀 runDefensiveReboundSetup: No outletTarget and no sprite, but proceeding with outlet pass', {
        outletReceiverId,
        outletTarget,
        hasOutletReceiverSprite: !!outletReceiverSprite
      });
    }
    const outletLog = {
      event: 'OUTLET_PASS',
      from: rebounderId,
      to: outletReceiverId,
      outletTarget,
      nextPlayType,
      startedAt: Date.now(),
    };
    if (outletContext) {
      outletLog.newOffenseTeam = outletContext.newOffenseTeam;
      outletLog.attackRim = outletContext.newOffenseBasket;
    } else {
      outletLog.newOffenseTeam = newOffenseTeam;
      outletLog.attackRim = newOffenseBasket;
    }
    // Always log outlet pass execution (not just when DebugFlags?.OUTLET is enabled)
    console.log('🏀 runDefensiveReboundSetup: Executing outlet pass', {
      from: rebounderId,
      to: outletReceiverId,
      nextPlayType,
      outletTarget: outletTarget ? `(${outletTarget.x}, ${outletTarget.y})` : 'null (will use receiver current position)'
    });
    if (DebugFlags?.OUTLET) animationDebugLog(outletLog);
    if (DebugFlags?.OUTLET) animationDebugLog('Starting outlet pass animation...');
    
    // ✅ REFACTOR: Use centralized passDetection.js system for consistency
    // Check if turnData has animations with pass actions, otherwise create synthetic passInfo
    const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
    let passInfo = null;
    
    if (turnData?.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
      // Check if there's a pass action in the animation data
      const maxSteps = Math.max(...turnData.animations.map(anim => anim.movement?.length || 0));
      if (maxSteps > 0) {
        passInfo = detectPassAtStep(turnData.animations, maxSteps - 1);
      }
    }
    
    if (passInfo) {
      // ✅ Use dynamic pass from animation data
      console.log('🏀 [DREB OUTLET] Using dynamic pass from animation data', passInfo);
      await handlePassAnimation({
        scene,
        passInfo,
        playerSprites
      });
    } else {
      // Fallback: Create synthetic passInfo for hardcoded outlet pass
      console.log('🏀 [DREB OUTLET] Using synthetic passInfo for hardcoded outlet pass');
      const syntheticPassInfo = {
        passerId: rebounderId,
        receiverId: outletReceiverId,
        stepIndex: 0,
        timestamp: Date.now()
      };
      await handlePassAnimation({
        scene,
        passInfo: syntheticPassInfo,
        playerSprites
      });
    }
    
    // Update ball ownership after pass completes
    setPendingOwner(scene, outletReceiverId);
    setCurrentOwner(scene, outletReceiverId);
    outletLog.completedAt = Date.now();
    console.log('🏀 runDefensiveReboundSetup: Outlet pass completed', {
      from: rebounderId,
      to: outletReceiverId
    });
    if (DebugFlags?.OUTLET) animationDebugLog(outletLog);
    if (DebugFlags?.OUTLET) animationDebugLog('Outlet pass completed!');
  } else {
    // Always log when outlet pass is skipped (not just when DebugFlags?.OUTLET is enabled)
    console.warn('🏀 runDefensiveReboundSetup: Outlet pass skipped', { 
      outletReceiverId, 
      rebounderId,
      nextPlayType,
      reason: !outletReceiverId ? 'No outlet receiver found' : 
              outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' : 
              nextPlayType === "FAST_BREAK" ? 'FAST_BREAK - outlet pass handled in fast break sequence (fastBreak.js)' :
              nextPlayType !== "HCO" ? `nextPlayType is "${nextPlayType}" (only HCO executes outlet pass here)` :
              'Unknown reason'
    });
    if (DebugFlags?.OUTLET) {
      animationDebugLog('Outlet pass skipped:', { 
        outletReceiverId, 
        rebounderId,
        nextPlayType,
        reason: !outletReceiverId ? 'No outlet receiver found' : 
                outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' : 
                nextPlayType === "FAST_BREAK" ? 'FAST_BREAK - outlet pass handled in fast break sequence' :
                nextPlayType !== "HCO" ? `nextPlayType is "${nextPlayType}"` : 
                'Unknown reason'
      });
    }
  }

  if (scene.stateMachine?.is(States.OutletSetup)) {
    if (DebugFlags?.FSM) animationDebugLog('FSM: OutletSetup -> HalfCourt');
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  scene.possessionFlipInProgress = false;

  if (typeof scene.startNextHalfCourtOffense === "function") {
    scene.startNextHalfCourtOffense();
  }
}

/**
 * Run offensive rebound kickout outlet setup animation
 * Similar to runDefensiveReboundSetup but for OREB kickout scenarios
 * 
 * @param {Object} params
 * @param {Object} params.scene - Phaser scene
 * @param {Object} params.ballSprite - Ball sprite
 * @param {Object} params.playerSprites - Player sprites dict
 * @param {string} params.rebounderId - Rebounder player ID
 * @param {string} params.pgId - Point guard player ID
 * @param {Object} [params.turnData] - Turn data (optional, for determining offense team)
 */
async function runOffensiveReboundKickoutSetup({ scene, ballSprite, playerSprites, rebounderId, pgId, turnData }) {
  animationDebugLog('runOffensiveReboundKickoutSetup called with:', { rebounderId, pgId });
  if (!scene || !playerSprites || rebounderId == null || pgId == null) return;

  const rebounderSprite = playerSprites[rebounderId];
  const pgSprite = playerSprites[pgId];
  if (!rebounderSprite || !pgSprite) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Missing sprites', {
      rebounderId,
      pgId,
      hasRebounder: !!rebounderSprite,
      hasPG: !!pgSprite
    });
    return;
  }

  // Attach ball to rebounder
  if (ballSprite) {
    attachBallToPlayer(scene, ballSprite, rebounderSprite);
  }

  // ✅ Determine if away team is on offense
  const offenseTeamId = turnData?.offense_team_id || turnData?.possession_team_id || scene.offenseTeamId;
  const homeTeamId = scene.simData?.home_team_id;
  const isAwayOffense = offenseTeamId && homeTeamId && offenseTeamId !== homeTeamId;

  // ✅ Helper function to flip coordinates for away team offense
  const flipCoords = (coords) => {
    return { x: 101 - coords.x, y: coords.y };
  };

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const { HCO_STRING_SPOTS } = await import('../../utils/courtPositions.js');

  // PG moves to one of: key, deep key, upper midWing, deep upper wing, lower midWing, deep lower wing (randomized)
  const pgSpotOptions = [
    "key",
    "deep key",
    "upper midWing",
    "deep upper wing",
    "lower midWing",
    "deep lower wing"
  ];
  const selectedPGSpot = pgSpotOptions[Math.floor(Math.random() * pgSpotOptions.length)];
  let pgSpot = HCO_STRING_SPOTS[selectedPGSpot];
  
  if (!pgSpot) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Invalid PG spot selected', { selectedPGSpot });
    return;
  }

  // ✅ Apply coordinate flipping for away team offense
  if (isAwayOffense) {
    pgSpot = flipCoords(pgSpot);
  }

  // Determine PG's vertical half for rebounder constraint (based on original spot name, not flipped coords)
  const isPGUpperHalf = selectedPGSpot.includes("upper");
  const isPGLowerHalf = selectedPGSpot.includes("lower");
  const isPGCentral = selectedPGSpot === "key" || selectedPGSpot === "deep key";

  // Rebounder moves to: topLane, upper apex, lower apex, or key (if PG not at key)
  // Constraint: Rebounder must be on same vertical half as PG (or central)
  let rebounderSpotOptions = [];
  
  // Always allow topLane and key (vertically central)
  rebounderSpotOptions.push("topLane");
  if (selectedPGSpot !== "key") {
    rebounderSpotOptions.push("key");
  }

  // Add vertical half options based on PG position
  // If PG is central (key/deep key), rebounder can go to any vertical spot
  // If PG is upper half, rebounder can't go to lower apex
  // If PG is lower half, rebounder can't go to upper apex
  if (isPGCentral || isPGUpperHalf) {
    rebounderSpotOptions.push("upper apex");
  }
  if (isPGCentral || isPGLowerHalf) {
    rebounderSpotOptions.push("lower apex");
  }

  // Select random rebounder spot from valid options
  const selectedRebounderSpot = rebounderSpotOptions[Math.floor(Math.random() * rebounderSpotOptions.length)];
  let rebounderSpot = HCO_STRING_SPOTS[selectedRebounderSpot];
  
  if (!rebounderSpot) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Invalid rebounder spot selected', { selectedRebounderSpot });
    return;
  }

  // ✅ Apply coordinate flipping for away team offense
  if (isAwayOffense) {
    rebounderSpot = flipCoords(rebounderSpot);
  }

  animationDebugLog('runOffensiveReboundKickoutSetup: Selected spots', {
    pgSpot: selectedPGSpot,
    pgCoords: pgSpot,
    rebounderSpot: selectedRebounderSpot,
    rebounderCoords: rebounderSpot,
    isAwayOffense,
    offenseTeamId,
    homeTeamId
  });

  // Animate both players to their spots
  const promises = [];
  
  // Animate PG to outlet position
  const pgPx = gridToPixels(pgSpot.x, pgSpot.y, width, height);
  const pgDuration = getPlayerDuration(pgSprite, pgPx.x, pgPx.y, true);
  promises.push(
    tweenPlayerTo(scene, pgSprite, pgPx, {
      duration: pgDuration,
      easing: 'Linear',
    })
  );

  // Animate rebounder to outlet position
  const rebounderPx = gridToPixels(rebounderSpot.x, rebounderSpot.y, width, height);
  const rebounderDuration = getPlayerDuration(rebounderSprite, rebounderPx.x, rebounderPx.y, true);
  promises.push(
    tweenPlayerTo(scene, rebounderSprite, rebounderPx, {
      duration: rebounderDuration,
      easing: 'Linear',
    })
  );

  // Wait for both animations to complete
  await Promise.all(promises);

  animationDebugLog('runOffensiveReboundKickoutSetup: Outlet positioning complete');
}

/**
 * Animate the fouling defender moving to within 1-2 x spots and ±1 y spots of the receiver (Quick Foul after BIP/SIP).
 * Used in the same turn as the inbound pass so ball and defender move together.
 */
function animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite) {
  if (!scene?.tweens || !defenderSprite || !receiverSprite) return Promise.resolve();
  const w = scene.game.config?.width ?? 1229;
  const h = scene.game.config?.height ?? 768;
  const spotW = w / 100;
  const spotH = h / 50;
  const offsetX = spotW * (Math.random() < 0.5 ? 1 : 2);
  const offsetY = spotH * (Math.random() * 2 - 1); // -1 to 1
  const target = { x: receiverSprite.x + offsetX, y: receiverSprite.y + offsetY };
  return tweenPlayerTo(scene, defenderSprite, target, { duration: 400, easing: 'Linear' });
}

// Setup baseline inbound play after a made basket
async function runInboundSetup({
  scene,
  ballSprite,
  playerSprites,
  newOffenseSide,
  homeTeamId,
  awayTeamId,
  skipRetreat = false,  // Allow skipping retreat for FCP/HCT
  pressureType = null,   // "FCP" or "HCT" to determine defensive positioning
  turnData = null,       // ✅ NEW: Optional turnData for dynamic pass detection
  context = null        // ✅ Force Foul: nextTurn so we can animate defender move in same turn
}) {
  // ✅ CRITICAL: ALWAYS set scene.offenseTeamId to match newOffenseSide BEFORE doing anything else
  // This ensures that any code that reads scene.offenseTeamId will get the correct value
  const expectedOffenseTeamId = newOffenseSide === "home" ? homeTeamId : awayTeamId;
  if (!expectedOffenseTeamId) {
    console.error('❌ [INBOUND SETUP] Cannot determine expectedOffenseTeamId!', {
      newOffenseSide,
      homeTeamId,
      awayTeamId
    });
  }
  
  // ✅ SS&S: Possession flip removed from frontend (Fix 2 - Pattern A)
  // Backend now flips possession before creating BASELINE_INBOUND turn
  // Frontend just reads offense_team_id from turnData (handled by universal transition in turnPreparation.js)
  // This defensive check is no longer needed - backend is authoritative
  
  // ✅ SS&S: Set FCP/HCT state when pressureType is provided (called inline from ShotAnimationSystem)
  // This ensures state is set even when runInboundSetup is called directly, not from a BASELINE_INBOUND turn
  if (pressureType === "FCP" || pressureType === "HCT") {
    scene.currentPressureType = pressureType;
    scene.pressureSequenceActive = true;
  } else if (pressureType === null) {
    // Clear state if no pressure (normal inbound)
    scene.currentPressureType = null;
    scene.pressureSequenceActive = false;
  }
  
  if (scene?.stateMachine?.is(States.FreeThrow)) {
    animationDebugLog('runInboundSetup blocked - FreeThrow state');
    return;
  }
  
  animationDebugLog('runInboundSetup proceeding - not blocked by FreeThrow state');
  scene.isInboundSetup = true;
  if (!scene.stateMachine?.is(States.Inbound)) {
    // ✅ FIX: If coming from HalfCourt (e.g., after a made shot), transition through Turnover first
    // This matches the pattern in runSideInboundSetup() and prevents "Invalid transition: HalfCourt -> Inbound" warning
    if (scene.stateMachine?.is(States.HalfCourt)) {
      safeTransition(
        scene.stateMachine,
        States.Turnover,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    }
    
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  const isAwayOffense = newOffenseSide === "away";

  // Derive missing team IDs from sprite metadata
  if (!homeTeamId || !awayTeamId) {
    const sprites = Object.values(playerSprites);
    if (!homeTeamId) {
      homeTeamId = sprites.find(s => s.team === "home")?.team_id;
    }
    if (!awayTeamId) {
      awayTeamId = sprites.find(s => s.team === "away")?.team_id;
    }
  }

  const inboundTeamKey = isAwayOffense ? "away" : "home";
  const scoringTeamKey = isAwayOffense ? "home" : "away";
  const inboundTeamId = isAwayOffense ? awayTeamId : homeTeamId;
  const scoringTeamId = isAwayOffense ? homeTeamId : awayTeamId;
  const ballSpot = isAwayOffense ? { x: 98, y: 16 } : { x: 3, y: 16 };

  const homeOffsetRanges = {
    PG: { x: [8, 12], y: [-2, 2] },
    SG: { x: [12, 16], y: [-4, 4] },
    PF: { x: [10, 14], y: [6, 10] },
    C: { x: [10, 14], y: [-10, -6] }
  };
  const awayOffsetRanges = {
    PG: { x: [-12, -8], y: [-2, 2] },
    SG: { x: [-16, -12], y: [-4, 4] },
    PF: { x: [-14, -10], y: [6, 10] },
    C: { x: [-14, -10], y: [-10, -6] }
  };
  const ranges = isAwayOffense ? awayOffsetRanges : homeOffsetRanges;
  const inboundDest = {};
  for (const pos of ["PG", "SG", "PF", "C"]) {
    if (pos === "PF" || pos === "C") {
      // PF and C go to half court area
      inboundDest[pos] = {
        x: Phaser.Math.Between(40, 60),
        y: Phaser.Math.Between(15, 35)
      };
    } else {
      // PG and SG use offset-based positioning
      inboundDest[pos] = {
        x: ballSpot.x + Phaser.Math.Between(ranges[pos].x[0], ranges[pos].x[1]),
        y: ballSpot.y + Phaser.Math.Between(ranges[pos].y[0], ranges[pos].y[1])
      };
    }
  }

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  // If FCP/HCT is next, position defenders in press formation
  const fcpDefensiveSetup = {};
  if (skipRetreat) {
    // Define defensive positions based on pressure type
    // FCP (Full Court Press): Aggressive full court pressure
    // HCT (Half Court Trap): Trap at half court line
    
    let basePositions;
    if (pressureType === "HCT") {
      // HCT: Half court trap positions (defenders closer to midcourt)
      basePositions = {
        PG: { x: 60, y: 25 },   // Just past midcourt
        SG: { x: 55, y: 35 },   // Upper side of half court
        SF: { x: 55, y: 15 },   // Lower side of half court
        PF: { x: 45, y: 30 },   // Opposite side upper
        C: { x: 45, y: 20 }     // Opposite side lower
      };
    } else {
      // FCP: Full court press positions (defenders spread across court)
      basePositions = {
        PG: { x: 80, y: 25 },   // Deep in offensive zone
        SG: { x: 73, y: 40 },   // Upper wing
        SF: { x: 73, y: 10 },   // Lower wing
        PF: { x: 37, y: 36 },   // Protecting opposite end
        C: { x: 35, y: 15 }     // Protecting opposite end
      };
    }

    // Apply positioning logic based on which team is defending
    // Midcourt is X=50
    // Left basket (away) is X=9, Right basket (home) is X=91
    for (const pos of ['PG', 'SG', 'SF', 'PF', 'C']) {
      let coords = basePositions[pos];
      
      if (isAwayOffense) {
        // AWAY on offense (attacking LEFT basket X=9), HOME defending LEFT basket
        // No flip needed - positions are already oriented correctly
        fcpDefensiveSetup[pos] = coords;
      } else {
        // HOME on offense (attacking RIGHT basket X=91), AWAY defending RIGHT basket
        // Flip X coordinates: 101 - x
        fcpDefensiveSetup[pos] = { x: 101 - coords.x, y: coords.y };
      }
    }
  }

  // Retreat scoring team toward midcourt (unless FCP is next)
  const retreatPromises = [];
  if (!skipRetreat) {
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      if (
        sprite.team_id === scoringTeamId ||
        (!scoringTeamId && sprite.team === scoringTeamKey)
      ) {
        // Base x-coord for midcourt retreat (uniform for all defensive players)
        const baseX = isAwayOffense ? 45 : 55;
        // Randomize x-coord by ±10 from base for more organic feel
        const xOffset = Phaser.Math.Between(-10, 10);
        const targetXGrid = baseX + xOffset;
        // Clamp to valid court bounds (1-99)
        const clampedXGrid = Phaser.Math.Clamp(targetXGrid, 1, 99);
        const targetX = gridToPixels(
          clampedXGrid,
          25,
          width,
          height
        ).x;
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for retreat - should match inbound setup speed
        const retreatDuration = getPlayerDuration(sprite, targetX, sprite.y, false);
        retreatPromises.push(
          new Promise((resolve) => {
            let timeoutId;
            const tween = scene.tweens.add({
              targets: sprite,
              x: targetX,
              y: sprite.y,
              duration: retreatDuration,
              ease: "Linear", // Match HCO step movements for consistent feel
              onComplete: () => {
                if (timeoutId) clearTimeout(timeoutId);
                resolve();
              },
              onStop: () => {
                if (timeoutId) clearTimeout(timeoutId);
                resolve();
              }
            });
            
            // Timeout safety: force resolve after 2x duration + buffer
            const timeoutMs = Math.max(retreatDuration * 2, 1000);
            timeoutId = setTimeout(() => {
              if (tween && tween.isPlaying && tween.isPlaying()) {
                scene.tweens.killTweensOf(sprite);
              }
              resolve();
            }, timeoutMs);
          })
        );
      }
    }
  } else if (Object.keys(fcpDefensiveSetup).length > 0) {
    // Move defending players to FCP press positions
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      
      // Check if this is a defending player
      if (
        sprite.team_id === scoringTeamId ||
        (!scoringTeamId && sprite.team === scoringTeamKey)
      ) {
        const targetPos = fcpDefensiveSetup[info.pos];
        if (targetPos) {
          const targetPx = gridToPixels(targetPos.x, targetPos.y, width, height);
          // Use distance-based duration for consistent speed (same as HCO step movements)
          // isTransition=true allows longer durations for transition movements
          const fcpDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
          retreatPromises.push(
            new Promise((resolve) => {
              let timeoutId;
              const tween = scene.tweens.add({
                targets: sprite,
                x: targetPx.x,
                y: targetPx.y,
                duration: fcpDuration,
                ease: "Linear", // Match HCO step movements for consistent feel
                onComplete: () => {
                  if (timeoutId) clearTimeout(timeoutId);
                  resolve();
                },
                onStop: () => {
                  if (timeoutId) clearTimeout(timeoutId);
                  resolve();
                }
              });
              
              // Timeout safety: force resolve after 2x duration + buffer
              const timeoutMs = Math.max(fcpDuration * 2, 1000);
              timeoutId = setTimeout(() => {
                if (tween && tween.isPlaying && tween.isPlaying()) {
                  scene.tweens.killTweensOf(sprite);
                }
                resolve();
              }, timeoutMs);
            })
          );
        }
      }
    }
  }

  // Identify SF/PG/SG/PF/C and freeze other inbound players
  let sfSprite = null;
  let pgSprite = null;
  let sgSprite = null;
  let pfSprite = null;
  let cSprite = null;
  let sfId = null;
  let pgId = null;
  let sgId = null;
  let pfId = null;
  let cId = null;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (
      !info ||
      (sprite.team_id !== inboundTeamId &&
        !(inboundTeamId === undefined && sprite.team === inboundTeamKey))
    )
      continue;
    if (info.pos === "SF") {
      sfSprite = sprite;
      sfId = id;
    } else if (info.pos === "PG") {
      pgSprite = sprite;
      pgId = id;
    } else if (info.pos === "SG") {
      sgSprite = sprite;
      sgId = id;
    } else if (info.pos === "PF") {
      pfSprite = sprite;
      pfId = id;
    } else if (info.pos === "C") {
      cSprite = sprite;
      cId = id;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  if (!sfSprite || !pgSprite) {
    scene.isInboundSetup = false;
    return;
  }
  animationDebugLog(
    `[inbound][score][${newOffenseSide}] sf:${sfId} pg:${pgId} sg:${sgId} pf:${pfId} c:${cId}`
  );

  const rimGrid = isAwayOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
  const spotPx = gridToPixels(ballSpot.x, ballSpot.y, width, height);

  // ✅ SS&S: For FCP/HCT, use step 0 positions from backend-provided skeleton data
  // Backend includes offense_setup_positions in BASELINE_INBOUND turn when next_defensive_setup is FCP/HCT
  // This positions offensive players in their press-break formation from the start
  let useSkeletonPositions = false;
  let skeletonPositions = {};
  
  if (skipRetreat && pressureType && turnData?.offense_setup_positions) {
    // Backend provided skeleton step 0 positions - convert to coords format
    const posActions = turnData.offense_setup_positions;
    
    // ✅ FIX: Helper function to flip coordinates for away team offense
    const flipCoords = (coords) => {
      return { x: 101 - coords.x, y: coords.y };
    };
    
    for (const [pos, actionData] of Object.entries(posActions)) {
      // ✅ FIX: Check coords first (has opp logic applied by backend), then fall back to location
      if (actionData.coords) {
        // Backend already applied opp logic and coordinate flipping - use as-is
        skeletonPositions[pos] = actionData.coords;
      } else if (actionData.location) {
        // Convert location string to coords (using HCO_STRING_SPOTS)
        const { HCO_STRING_SPOTS } = await import('../../utils/courtPositions.js');
        let coords = HCO_STRING_SPOTS[actionData.location];
        if (coords) {
          // ✅ FIX: Apply opp logic if opp field is set
          const hasOpp = actionData.opp === true;
          if (hasOpp) {
            // Player with opp=True should be on opposite side (defensive side)
            if (!isAwayOffense) {
              // Home team offense - ball handlers go to away side (defensive side)
              coords = flipCoords(coords);
            }
            // Away team offense - ball handlers stay on home side (no flip needed)
          } else {
            // Player without opp field stays on same side as normal offense
            if (isAwayOffense) {
              // Away team offense - outlet players go to away side (offensive side)
              coords = flipCoords(coords);
            }
            // Home team offense - outlet players stay on home side (no flip needed)
          }
          skeletonPositions[pos] = coords;
        }
      }
    }
    
    // Only use skeleton positions if we have positions for key players (SF and PG at minimum)
    if (skeletonPositions.SF && skeletonPositions.PG) {
      useSkeletonPositions = true;
    }
  }
  
  // ✅ NEW APPROACH: Don't skip inbound pass for FCP/HCT anymore
  // Players are positioned at skeleton step 0 locations (from backend setup positions)
  // We'll animate the inbound pass here, then skeleton starts from old step 1

  // Use skeleton positions if available, otherwise fall back to baseline inbound positions
  const pgDest = useSkeletonPositions && skeletonPositions.PG ? skeletonPositions.PG : inboundDest.PG;
  const sgDest = useSkeletonPositions && skeletonPositions.SG ? skeletonPositions.SG : inboundDest.SG;
  const pfDest = useSkeletonPositions && skeletonPositions.PF ? skeletonPositions.PF : inboundDest.PF;
  const cDest = useSkeletonPositions && skeletonPositions.C ? skeletonPositions.C : inboundDest.C;
  const sfDest = useSkeletonPositions && skeletonPositions.SF ? skeletonPositions.SF : ballSpot;

  // 🔍 DEBUG: Log offensive player destinations (HCO only now - FCP/HCT returns above)
  // COMMENTED OUT: Verbose log - uncomment if needed for debugging
  // console.log('🔍 [HCO INBOUND] Offensive player destinations:', {
  //   newOffenseSide,
  //   positions: {
  //     PG: { grid: pgDest, source: 'baseline' },
  //     SG: { grid: sgDest, source: 'baseline' },
  //     SF: { grid: sfDest, source: 'baseline' },
  //     PF: { grid: pfDest, source: 'baseline' },
  //     C: { grid: cDest, source: 'baseline' }
  //   }
  // });

  const pgDestPx = gridToPixels(pgDest.x, pgDest.y, width, height);
  animationDebugLog(`inboundDest assigned for PG: (${pgDestPx.x},${pgDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const sgDestPx = gridToPixels(sgDest.x, sgDest.y, width, height);
  animationDebugLog(`inboundDest assigned for SG: (${sgDestPx.x},${sgDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const pfDestPx = gridToPixels(pfDest.x, pfDest.y, width, height);
  animationDebugLog(`inboundDest assigned for PF: (${pfDestPx.x},${pfDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const cDestPx = gridToPixels(cDest.x, cDest.y, width, height);
  animationDebugLog(`inboundDest assigned for C: (${cDestPx.x},${cDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const sfDestPx = gridToPixels(sfDest.x, sfDest.y, width, height);
  animationDebugLog(`inboundDest assigned for SF: (${sfDestPx.x},${sfDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(sfSprite);
    scene.tweens.killTweensOf(pgSprite);
    if (sgSprite) scene.tweens.killTweensOf(sgSprite);
    if (pfSprite) scene.tweens.killTweensOf(pfSprite);
    if (cSprite) scene.tweens.killTweensOf(cSprite);
  }

  ballSprite.setPosition(rimPx.x, rimPx.y);
  ballSprite.setVisible(true);
  animationDebugLog(`[inbound][rimHoldEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  animationDebugLog(`[inbound][ballTweenStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  let ballTween;
  // Use SF's destination for ball position (SF receives inbound pass)
  const ballDestPx = useSkeletonPositions ? sfDestPx : spotPx;
  if (animationConfig.enableBallTween) {
    // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of tweenBallTo()
    // animateBallToPosition() gets ballSprite from scene.ballSprite internally
    ballTween = animateBallToPosition(scene, ballDestPx, {
      duration: 500,
      easing: "Sine.easeInOut"
    }).then(() => {
      animationDebugLog(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    });
  } else {
    ballSprite.setPosition(ballDestPx.x, ballDestPx.y);
    animationDebugLog(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    ballTween = Promise.resolve();
  }

  const sfTween = new Promise((resolve) => {
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // Use regular speed (not transition) for inbound setup - should be faster
    const sfDuration = getPlayerDuration(sfSprite, sfDestPx.x, sfDestPx.y, false);
    scene.tweens.add({
      targets: sfSprite,
      x: sfDestPx.x,
      y: sfDestPx.y,
      duration: sfDuration,
      ease: "Linear", // Match HCO step movements for consistent feel
      onComplete: () => {
        animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
        resolve();
      },
      onStop: () => {
        animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
        resolve();
      }
    });
  });

  const pgTween = new Promise((resolve) => {
    animationDebugLog("pgTween start");
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // Use regular speed (not transition) for inbound setup - should be faster
    const pgDuration = getPlayerDuration(pgSprite, pgDestPx.x, pgDestPx.y, false);
    scene.tweens.add({
      targets: pgSprite,
      x: pgDestPx.x,
      y: pgDestPx.y,
      duration: pgDuration,
      ease: "Linear", // Match HCO step movements for consistent feel
      onComplete: () => {
        animationDebugLog("pgTween end");
        resolve();
      },
      onStop: () => {
        animationDebugLog("pgTween end");
        resolve();
      }
    });
  });

  const sgTween = sgSprite
    ? new Promise((resolve) => {
        animationDebugLog("sgTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const sgDuration = getPlayerDuration(sgSprite, sgDestPx.x, sgDestPx.y, false);
        scene.tweens.add({
          targets: sgSprite,
          x: sgDestPx.x,
          y: sgDestPx.y,
          duration: sgDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("sgTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("sgTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const pfTween = pfSprite
    ? new Promise((resolve) => {
        animationDebugLog("pfTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const pfDuration = getPlayerDuration(pfSprite, pfDestPx.x, pfDestPx.y, false);
        scene.tweens.add({
          targets: pfSprite,
          x: pfDestPx.x,
          y: pfDestPx.y,
          duration: pfDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("pfTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("pfTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const cTween = cSprite
    ? new Promise((resolve) => {
        animationDebugLog("cTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const cDuration = getPlayerDuration(cSprite, cDestPx.x, cDestPx.y, false);
        scene.tweens.add({
          targets: cSprite,
          x: cDestPx.x,
          y: cDestPx.y,
          duration: cDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("cTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("cTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  await Promise.all([
    ...retreatPromises,
    ballTween,
    sfTween,
    pgTween,
    sgTween,
    pfTween,
    cTween
  ]);
  
  // ✅ TIMEOUT: Removed 2-second pause - timeout button is now always live

  animationDebugLog(`[inbound][ballAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  attachBallToPlayer(scene, ballSprite, sfSprite);
  
  const inboundHoldMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
  await new Promise(resolve => setTimeout(resolve, inboundHoldMs));
  await new Promise(resolve => setTimeout(resolve, inboundHoldMs));

  animationDebugLog(`[inbound][holdStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  // Removed 1000ms pause for smoother transitions
  
  // ✅ TIMEOUT: Removed markInboundPassStarted - button is always live now

  // ✅ BIP → FCP/HCT: Skip inbound pass here; skeleton will animate it (avoids double inbound).
  // SIP (side inbound) always uses runSideInboundSetup() and never calls this function, so SIP is unaffected.
  if (pressureType === "FCP" || pressureType === "HCT") {
    if (scene.stateMachine?.is(States.Inbound)) {
      safeTransition(
        scene.stateMachine,
        States.HalfCourt,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    }
    scene.isInboundSetup = false;
    scene.passInFlight = false;
    return;
  }

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(pgSprite);
  }

  scene.events?.once('passStart', () => animationDebugLog('passStart'));
  scene.events?.once('tweenStart', () => animationDebugLog('tweenStart'));
  scene.events?.once('tweenEnd', () => animationDebugLog('tweenEnd'));
  scene.events?.once('passEnd', () => animationDebugLog('passEnd'));

  animationDebugLog(`[inbound][passStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  animationDebugLog(`[inbound][stateCheck] current state: ${scene.stateMachine?.state}, isFastBreak: ${scene.stateMachine?.is(States.FastBreak)}`);
  
  // ✅ REFACTOR: Use passDetection.js for dynamic passes, fallback to hardcoded SF→PG
  const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
  
  // Check if turnData has animations with pass actions
  let passInfo = null;
  if (turnData?.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
    // Find the step index where the pass happens (typically the last step after positioning)
    const maxSteps = Math.max(...turnData.animations.map(anim => anim.movement?.length || 0));
    // Check the last step for pass actions
    if (maxSteps > 0) {
      passInfo = detectPassAtStep(turnData.animations, maxSteps - 1);
    }
  }
  
  // Allow inbound pass regardless of current state (including FastBreak)
  // ✅ Force Foul: when next turn is Quick Foul, animate defender to receiver in same step as the pass
  const nextTurn = context?.nextTurn;
  const isQuickFoulNext = nextTurn?.quick_foul && nextTurn?.result_type === 'FOUL';
  const passPromise = passInfo
    ? (console.log('🏀 [BASELINE_INBOUND] Using dynamic pass from animation data', passInfo),
       handlePassAnimation({ scene, passInfo, playerSprites }))
    : runPass(scene, { fromId: sfId, toId: pgId, duration: 500, easing: "Sine.easeInOut" });

  let defenderPromise = Promise.resolve();
  if (isQuickFoulNext) {
    const receiverId = passInfo?.receiverId ?? pgId;
    const receiverSprite = playerSprites[receiverId];
    const defenderSprite = nextTurn.foul_player_id ? playerSprites[nextTurn.foul_player_id] : null;
    if (receiverSprite && defenderSprite) {
      defenderPromise = animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite);
      nextTurn._quickFoulAnimatedDuringInbound = true;
    }
  }
  await Promise.all([passPromise, defenderPromise]);

  animationDebugLog(`[inbound][passEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  animationDebugLog(`[inbound][pgAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);

  if (scene.stateMachine?.is(States.Inbound))
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );

  scene.isInboundSetup = false;
  scene.passInFlight = false;
  
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
}


/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 * 
 * @param {Object} params - Animation parameters
 * @param {Object} params.scene - Phaser scene
 * @param {Object} params.simData - Simulation data
 * @param {Object} params.playerSprites - Player sprite map
 * @param {Object} params.turnData - Turn data object
 * @param {Object} params.ballSprite - Ball sprite
 * @param {Function} params.onAction - Action callback (optional)
 * @param {number} params.turnIndex - Turn index (optional, uses scene.currentTurn if not provided)
 * @param {Function} params.onUpdate - Update callback (optional, for future use)
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction, turnIndex, onUpdate }) {
  
  // ✅ SS&S: Use current_turn to detect FCP/HCT (replaces fragmented flags)
  const isFCPHCT = turnData?.current_turn === 'FCP' || turnData?.current_turn === 'HCT';
  
  // ✅ REMOVED: Step-by-step animation logging (cluttering console)
  
  // Guard: Skip if this is an opening tip, putback, or if animations is missing
  // Putback turns are handled by handleOrebTurn in animateGameTurns.js
  if (turnData.result_type === "OPENING_TIP" || 
      turnData.result_type === "PUTBACK_MAKE" || 
      turnData.result_type === "PUTBACK_MISS" ||
      !turnData.animations) {
    if (turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS") {
      console.warn('⚠️ playTurnAnimation called for putback turn - this should be handled by handleOrebTurn:', turnData.result_type);
    } else {
    console.warn('⚠️ playTurnAnimation called for turn without animations:', turnData.result_type);
    }
    return;
  }

  // ✅ NEW (Step 1): Initialize simple ball holder state (WIP_GOB approach)
  initializeBallHolderState(scene);

  const fromInbound = scene._previousTurnWasInbound === true;
  const fromOpeningTip = scene._previousTurnWasOpeningTip === true;

  scene.passInFlight = false;
  scene.rebounderId = null;
  // Only clear ball attachment/ownership when NOT coming directly from an inbound or opening tip,
  // so the ball can carry over with the inbound receiver or tip winner into HCO.
  if (!fromInbound && !fromOpeningTip) {
    // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
    clearPendingOwner(scene);
    // ✅ NEW (Step 1): Also clear simple ball holder state
    clearBallHolder(scene);
  }

  const currentBallOwnerRef = { value: null };
  // Store a reference on the scene so other modules (e.g., runPass)
  // can update ball ownership consistently.
  scene.currentBallOwnerRef = currentBallOwnerRef;
  const maxSteps = turnData.animations && turnData.animations.length > 0
    ? Math.max(
        ...turnData.animations
          .filter(anim => anim.movement && Array.isArray(anim.movement))
          .map(anim => anim.movement.length)
      )
    : 0;
  

  // ✅ Allow HCO turns even if state is FastBreak (can happen after defensive stop transition fails)
  // Check if this is an HCO turn (not fast_break and has animations) - if so, allow it
  const isHCOAfterFastBreak = !turnData.fast_break && 
                               (turnData.result_type === "MAKE" || turnData.result_type === "MISS" || turnData.result_type === "BLOCK") &&
                               turnData.animations?.length > 0 &&
                               scene.stateMachine?.is(States.FastBreak);
  
  // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
  if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak) {
    return;
  }
  
  // If we're allowing HCO after FastBreak, force transition to HalfCourt
  if (isHCOAfterFastBreak) {
    console.log("🔄 playTurnAnimation: Forcing transition from FastBreak to HalfCourt for HCO turn");
    const { safeTransition, States: StateMachineStates } = await import('../state/gameStateMachine.js');
    safeTransition(scene.stateMachine, StateMachineStates.HalfCourt);
  }

  if (ballSprite && scene?.tweens) {
    // Always clear any stray tweens, but don't hide the ball if we're carrying over from inbound or opening tip
    scene.tweens.killTweensOf(ballSprite);
    if (!fromInbound && !fromOpeningTip) {
      ballSprite.setVisible(false);
    }
  }

  const homeTeamId = simData.home_team_id;
  let awayTeamId = simData.away_team_id;
  if (!awayTeamId) {
    const awaySprite = Object.values(playerSprites).find(s => s.team === "away");
    awayTeamId = awaySprite?.team_id;
    if (awayTeamId) simData.away_team_id = awayTeamId;
  }

  // Determine which player owns the ball at step 0
  // BUT: Skip this if the previous turn was a shot (MAKE or MISS)
  // EXCEPT: For FCP/HCT, we NEED step 0 ball attachment (SF holds ball at inbound spot)
  // isFCPHCT already declared above
  const previousTurnWasShot = scene._previousTurnWasShot === true;
  if (previousTurnWasShot && !isFCPHCT) {
    console.log('🏀 playTurnAnimation: Skipping step 0 ball attachment - previous turn was a shot (HCO only)');
    scene._previousTurnWasShot = false; // Clear the flag
  } else if (previousTurnWasShot && isFCPHCT) {
    console.log('🏀 playTurnAnimation: NOT skipping step 0 for FCP/HCT - need to attach ball to inbounder');
    scene._previousTurnWasShot = false; // Clear the flag
  }
  
  let step0OwnerSprite = null;
  // If we are coming directly from an inbound or opening tip, the ball should already be attached
  // to the inbound receiver or tip winner, so we don't re-derive or re-attach at step 0.
  if (!previousTurnWasShot && !fromInbound && !fromOpeningTip) {
    for (const anim of turnData.animations) {
      if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) break;
      if (anim.hasBallAtStep?.[0]) {
        step0OwnerSprite = playerSprites[anim.playerId];
        break;
      }
    }

    if (step0OwnerSprite) {
      const step0OwnerId = step0OwnerSprite.playerId;
      const isPutbackTurn = turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS";
      
      if (isPutbackTurn) {
        // ✅ PHASE 4: Check BallController state instead of old _shotInProgress flag
        const { getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        // CRITICAL: Don't attach ball for putback turns - handleOrebTurn handles it
        // This prevents the brief attachment flash before the putback shot
      } else {
      attachBallToPlayer(scene, ballSprite, step0OwnerSprite);
      currentBallOwnerRef.value = step0OwnerSprite;
      
      // ✅ NEW (Step 1): Also set simple ball holder ID (WIP_GOB approach)
      // This enables the new simple ball animation system to track ball holder
      setBallHolderId(scene, step0OwnerId);
      }
    }
  }

  // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
  // AnimationRouter handles routing, so no special state checks needed here
  if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
    return;
  }

  // ✅ NEW: Lock ball ownership to correct player at step
  animationDebugLog("🟡 inside playTurnAnimation → ");
  //print turnData here in the console logs
  animationDebugLog("turnData", turnData);
  // animationDebugLog("turnData.animations", turnData.animations);
  // animationDebugLog("turnData.possession_team_id", turnData.possession_team_id);
  // animationDebugLog("turnData.animations[0].hasBallAtStep", turnData.animations[0].hasBallAtStep);
  // animationDebugLog("turnData.animations[0].playerId", turnData.animations[0].playerId);
  // animationDebugLog("turnData.animations[0].movement", turnData.animations[0].movement);
  updateBallOwnership({
    scene,
    ballSprite,
    animations: turnData.animations,
    playerSprites,
    stepIndex: 0,
    offenseTeamId: scene.offenseTeamId ?? turnData.possession_team_id,
    currentBallOwnerRef
  });

  // Initial active player display update
  if (!scene.skipToEnd) {
    const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
    const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
    const defenderId = getDefenderIdFromTurn(turnData);
    const homeTeamId = scene.simData?.home_team_id || null;
    if (ballHandlerId && homeTeamId) {
      updateActivePlayers(ballHandlerId, defenderId, homeTeamId, playerSprites);
    }
  }

  // Clear inbound and opening tip flags after applying pre-step setup
  if (scene._previousTurnWasInbound) {
    scene._previousTurnWasInbound = false;
  }
  if (scene._previousTurnWasOpeningTip) {
    scene._previousTurnWasOpeningTip = false;
  }

  // ✅ REMOVED: Special FCP/HCT setup tween - FCP/HCT now routes through ShotAnimationSystem (same as HCO)
  // ShotAnimationSystem.runSetupTween() handles setup for all skeleton animations, including FCP/HCT

  let eventsProcessed = false;
  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 450;
  const stepClockSeconds = Array.isArray(turnData?.step_clock_seconds)
    ? turnData.step_clock_seconds
    : null;
  const getContractStepDurationMs = (stepIndex, fallbackDurationMs) => {
    const stepSeconds = stepClockSeconds?.[stepIndex];
    if (Number.isFinite(stepSeconds) && stepSeconds > 0) {
      return Math.max(50, Math.round(stepSeconds * clockSecondMs));
    }
    return fallbackDurationMs;
  };

  // ✅ CRITICAL FIX: Kill all ball tweens before starting step loop
  // Lingering ball tweens from previous shots/passes can block the tween manager
  // This is especially important for FCP/HCT turns that come after shots
  if (ballSprite && scene.tweens) {
    const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
    if (ballActiveTweens.length > 0) {
      scene.tweens.killTweensOf(ballSprite);
      // Also kill ball shadow tweens if they exist
      if (scene.ballShadowSprite) {
        scene.tweens.killTweensOf(scene.ballShadowSprite);
      }
    }
  }

  // ✅ REMOVED: Special FCP/HCT tween cleanup - FCP/HCT now uses exact same path as HCO
  // ShotAnimationSystem handles all skeleton animations identically

  // ✅ SS&S FIX: Resolve offenseTeamId once at turn start and classify all players
  // This ensures consistent player classification throughout the turn
  const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
  const offenseTeamId = resolveOffenseTeamId({
    scene,
    turnData,
    playerSprites,
    passInfo: null // No passInfo at turn start, will be detected per step
  });
  
  // ✅ SS&S: Classify all players once at turn start
  const playerClassifications = {}; // Map: playerId -> 'offense' | 'defense'
  let offensiveCount = 0;
  let defensiveCount = 0;
  
  // 🔍 DEBUG: Log team_id format mismatch detection
  // Classify players as offense or defense
  
  for (const anim of turnData.animations) {
    const sprite = playerSprites[anim.playerId];
    if (!sprite) {
      continue;
    }
    
    const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
    playerClassifications[anim.playerId] = isOffensivePlayer ? 'offense' : 'defense';
    
    if (isOffensivePlayer) {
      offensiveCount++;
    } else {
      defensiveCount++;
    }
  }
  
  // ✅ VALIDATION: Ensure we have exactly 5 offensive and 5 defensive players
  if (offensiveCount !== 5 || defensiveCount !== 5) {
    console.warn('⚠️ [PLAYER CLASSIFICATION] Expected 5 offensive and 5 defensive players, but got:', {
      offensiveCount,
      defensiveCount
    });
  }

  // ============================================================================
  // STEAL HCO SETUP: Animate stealer moving back before HCO skeleton starts
  // ============================================================================
  if (turnData.roles?.is_steal_hco_setup) {
    await animateStealHCOSetup(scene, turnData, playerSprites, ballSprite);
  }

  // ✅ CRITICAL FIX: Run setup tween to move players to step 0 positions before skeleton animation
  // This ensures players are correctly positioned before step 1 (first pass) starts
  // Without this, truncated skeletons (o foul, d foul, dead ball turnover, steal) start
  // the step loop before players reach step 0 positions, causing slow/fast first pass animations
  // Shot attempts work correctly because ShotAnimationSystem calls runSetupTween() before animatePlayerMovement()
  // ✅ SS&S FIX: Skip setup tween if coming from BIP for FCP/HCT - players are already at step 0 positions
  // BIP (BASELINE_INBOUND) already positioned players at skeleton step 0 positions, so this is redundant
  // and can cause timing conflicts if the inbound pass animation is still completing
  if (!fromInbound || !isFCPHCT) {
    await runSetupTween({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      currentBallOwnerRef,
      turnData,
      stepDurationMs: getContractStepDurationMs(0, null),
    });
  } else {
    console.log('⏭️ [FCP/HCT] Skipping runSetupTween() - players already positioned at step 0 from BIP');
  }

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    
    // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
    const willEarlyExit = scene.skipToEnd || scene.stateMachine?.is(States.FastBreak);
    
    // ✅ CRITICAL FIX: Kill ball tweens at the start of EACH step iteration
    // Passes within the step loop can leave lingering ball tweens that block subsequent steps
    if (ballSprite && scene.tweens && !willEarlyExit) {
      const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        scene.tweens.killTweensOf(ballSprite);
        if (scene.ballShadowSprite) {
          scene.tweens.killTweensOf(scene.ballShadowSprite);
        }
      }
    }
    
    if (willEarlyExit) {
      break;
    }

    // Trigger lean meter animation at middle step
    if (scene._leanScoreToAnimate !== null && 
        scene._leanAnimationStep === stepIndex && 
        !scene._leanAnimationTriggered) {
      // ✅ REMOVED: LEAN animation logging (cluttering console)
      const { animateLeanMeter } = await import('../ui/playcallCenter.js');
      animateLeanMeter(scene._leanScoreToAnimate);
      scene._leanAnimationTriggered = true;
    } else if (scene._leanScoreToAnimate !== null && stepIndex === scene._leanAnimationStep) {
      // ✅ REMOVED: LEAN animation mismatch logging (cluttering console)
    }

    // ✅ FIX: Skip updateBallOwnership if a pass is happening at this step OR
    // if a pass just completed (passInFlight is still true from previous step)
    // We'll handle the pass explicitly after movements complete (like shots)
    // ✅ REFACTOR: Use unified passDetection.js for consistency
    // ✅ FIX: Detect pass early to determine animation sequence (reused below)
    const { detectPassAtStep } = await import('./passDetection.js');
    
    const passInfo = detectPassAtStep(turnData.animations, stepIndex);
    const passHappeningAtThisStep = !!passInfo;
    
    // 🔍 DEBUG: Log step processing for step 16 (3-2 Motion bug)
    if (stepIndex === 16) {
      const step = turnData.animations?.[0]?.movement?.[stepIndex];
      console.log('📋 [STEP PROCESSING] Step 16', {
        timestamp: step?.timestamp,
        passHappening: passHappeningAtThisStep,
        passInfo: passInfo ? {
          passerId: passInfo.passerId?.substring(0, 8),
          receiverId: passInfo.receiverId?.substring(0, 8)
        } : null,
        allPlayerPositions: Object.keys(playerSprites).map(playerId => {
          const sprite = playerSprites[playerId];
          const anim = turnData.animations?.find(a => a.playerId === playerId);
          const stepData = anim?.movement?.[stepIndex];
          return {
            playerId: playerId?.substring(0, 8),
            x: sprite.x,
            y: sprite.y,
            action: stepData?.action,
            location: stepData?.location
          };
        })
      });
    }
    
    // ✅ OLD CODE (commented out - replaced with unified passDetection.js):
    // const passHappeningAtThisStep = turnData.animations.some(
    //   anim => anim.movement?.[stepIndex]?.action === "pass"
    // );
    
    // ✅ CRITICAL FIX: Also skip if passInFlight is true (pass just completed)
    // This prevents updateBallOwnership from teleporting the ball immediately after runPass() completes
    // The passInFlight flag will be cleared by runPass()'s finally block, but we keep it true
    // for one more step to ensure the ball is properly attached before updateBallOwnership runs
    if (!passHappeningAtThisStep && !scene.passInFlight) {
      updateBallOwnership({
        scene,
        ballSprite,
        animations: turnData.animations,
        playerSprites,
        stepIndex,
        offenseTeamId: scene.offenseTeamId ?? turnData.possession_team_id,
        currentBallOwnerRef
      });
    } else if (scene.passInFlight && !passHappeningAtThisStep) {
      // Pass just completed, clear the flag now that we've skipped updateBallOwnership
      // This allows updateBallOwnership to run normally for subsequent steps
      scene.passInFlight = false;
      console.log('🏀 [PASS ANIMATION] Cleared passInFlight after skipping updateBallOwnership');
    }

    // Update active player displays in scoreboard
    if (!scene.skipToEnd) {
      const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
      const ballHandlerId = getBallHandlerIdFromTurn(turnData, stepIndex);
      const defenderId = getDefenderIdFromTurn(turnData);
      const homeTeamId = scene.simData?.home_team_id || null;
      if (ballHandlerId && homeTeamId) {
        updateActivePlayers(ballHandlerId, defenderId, homeTeamId, playerSprites);
      }
    }

    // ✅ SS&S: Use pre-classified player roles (determined at turn start)
    // No need to re-resolve offenseTeamId or re-classify players per step
    const offensivePromises = [];
    const defensiveStarters = []; // defer starting defensive tweens when a pass exists
    let passerPromise = null;
    let shotInfo = null;

    // Separate offensive and defensive players using pre-classified roles
    for (const anim of turnData.animations) {
      if (scene.skipToEnd) break;
      const sprite = playerSprites[anim.playerId];
      const movement = anim.movement;

      if (!sprite || stepIndex >= movement.length) continue;

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const step = prev;
      const nextStep = curr;
      
      // Calculate target position in pixels
      const { x: targetX, y: targetY } = gridToPixels(
        nextStep.coords.x,
        nextStep.coords.y,
        scene.game.config.width,
        scene.game.config.height
      );
      
      // Use distance-based duration calculation (from current sprite position to target)
      // This ensures smooth transitions between turns and consistent speeds
      // The sprite's current position (sprite.x, sprite.y) is where it actually is,
      // which may be from the end of the previous turn or from a previous step
      const distanceDuration = getPlayerDuration(sprite, targetX, targetY);
      const duration = distanceDuration;
      

      DEBUG && animationDebugLog('[turn]', turnData?.id, step.timestamp, nextStep.timestamp, duration, {
        currentPos: { x: sprite.x, y: sprite.y },
        targetPos: { x: targetX, y: targetY },
        distance: Phaser.Math.Distance.Between(sprite.x, sprite.y, targetX, targetY),
        method: 'distance-based'
      });
      if (duration <= 0) {
        animationDebugWarn('[turn] Non-positive duration', { turnId: turnData?.id, step, nextStep });
        if (typeof window !== 'undefined') {
          window.__badStepPayloads = window.__badStepPayloads || [];
          window.__badStepPayloads.push({ turnId: turnData?.id, step, nextStep });
        }
      }

      if (nextStep.action === "shoot") {
        // Option A: Don't animate shot attempt for Charge or Blocking Foul — keep ball on ball handler
        const isChargeOrBlockingFoul = turnData.result_type === 'CHARGE' ||
          (turnData.result_type === 'FOUL' && turnData.text?.toLowerCase().includes('blocking foul'));
        if (!isChargeOrBlockingFoul) {
          shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        }
      }

      const promise = animateStep({
        scene,
        sprite,
        step: prev,  // Previous step (for position calculation)
        nextStep: curr,  // Current step (for action checking)
        duration,
        ballSprite,
        currentBallOwnerRef,
        onAction,
        stepIndex  // Pass stepIndex to identify first step
      });

      // ✅ SS&S: Use pre-classified player role (determined at turn start)
      // This ensures consistent classification throughout the turn
      const playerRole = playerClassifications[anim.playerId] || 'defense'; // Default to defense if not found
      const isOffensivePlayer = playerRole === 'offense';
      
      if (isOffensivePlayer) {
        offensivePromises.push(promise);
        // Track passer's promise separately so we can wait for it before starting pass
        if (passInfo && anim.playerId === passInfo.passerId) {
          passerPromise = promise;
        }
      } else {
        // Defer starting defensive tweens when a pass exists so we can sync them with the pass
        defensiveStarters.push(() => animateStep({
          scene,
          sprite,
          step: prev,
          nextStep: curr,
          duration,
          ballSprite,
          currentBallOwnerRef,
          onAction,
          stepIndex
        }));
      }
    }

    // Start defensive tweens immediately only when there is no pass; when there is a pass,
    // we'll start them alongside the pass to keep them in sync.
    let defensivePromiseArray = [];
    
    if (!passInfo && defensiveStarters.length > 0) {
      defensivePromiseArray = defensiveStarters.map(start => start());
    }

    // ✅ FIX: Phase 1 - Start all offensive players animating, wait for passer if there's a pass
    // This maintains the existing behavior where pass doesn't start until passer reaches their spot
    // All offensive players start animating simultaneously, but we only wait for the passer
    const phase1StartTime = performance.now();
    if (passInfo && passerPromise) {
      // Wait for passer to complete before starting pass animation
      // Other offensive players continue animating in the background
      await passerPromise;
    } else if (offensivePromises.length > 0) {
      // No pass, wait for all offensive players to complete
      await Promise.all(offensivePromises);
    }

    // ✅ FIX: Phase 2 - Animate pass and defensive players in parallel
    // This creates the natural feel of defensive players moving while ball is in the air
    // Other offensive players (non-passer) continue animating from Phase 1
    const passAndDefensePromises = [];
    const phase2StartTime = performance.now();
    
    if (passInfo) {
      // Add pass animation to the parallel batch
      const { handlePassAnimation } = await import('./passDetection.js');
      const passPromise = handlePassAnimation({
        scene,
        passInfo,
        playerSprites
      });
      
      passAndDefensePromises.push(passPromise);

      // Start defensive tweens now (in sync with pass start)
      if (defensiveStarters.length > 0) {
        defensivePromiseArray = defensiveStarters.map(start => start());
        passAndDefensePromises.push(...defensivePromiseArray);
      }
    } else {
      // No pass: defensive tweens (if any) already started above
      passAndDefensePromises.push(...defensivePromiseArray);
    }
    
    // Animate pass and defensive players simultaneously
    if (passAndDefensePromises.length > 0) {
      await Promise.all(passAndDefensePromises);
    }
    
    // ✅ FIX: Wait for any remaining offensive players (non-passer) to complete
    // This ensures all offensive players finish their movements
    // Note: If there was no pass, we already waited for all offensive players above
    if (passInfo && passerPromise) {
      const remainingOffensivePromises = offensivePromises.filter(p => p !== passerPromise);
      if (remainingOffensivePromises.length > 0) {
        await Promise.all(remainingOffensivePromises);
      }
    }

    if (shotInfo) {
      currentBallOwnerRef.value = null;
      const shooterPos = scene.playerInfo?.[shotInfo.playerId]?.pos;
      const shooterTeamId = playerSprites[shotInfo.playerId]?.team_id;
      const shootParams = {
        scene,
        ballSprite,
        fromCoords: shotInfo.step.coords,
        startTimestamp: shotInfo.step.timestamp,
        // Map rebound result types to "MISS" so shootBall returns a landing spot
        result: ["DREB", "OREB"].includes(
          turnData.rebound_type || turnData.result_type
        )
          ? "MISS"
          : turnData.result_type,
        shooterPos,
        shooterId: shotInfo.playerId,
        shooterTeamId,
        homeTeamId,
        stepIndex: shotInfo.stepIndex,
        turnIndex: scene.currentTurn,
        turnData: turnData
      };
      if (SHOT_DEBUG) {
        animationDebugLog("shootParams", {
          stepIndex: shootParams.stepIndex,
          turnIndex: shootParams.turnIndex,
          shooterId: shootParams.shooterId,
          result: shootParams.result,
        });
      }
      // console.log("🏀 HCO SHOT - About to call shootBall", {
      //   currentState: scene.stateMachine?.state,
      //   shooterId: shootParams.shooterId,
      //   result: shootParams.result,
      //   fromCoords: shootParams.fromCoords
      // });
      
      // Check if this is an audible/hot read (shooter different from intended)
      let isAudible = false;
      if (turnData.shooter_pos && 
          turnData.intended_shooter_pos && 
          turnData.shooter_pos !== turnData.intended_shooter_pos) {
        
        console.log('🔥 AUDIBLE DETECTED:', {
          shooter_pos: turnData.shooter_pos,
          intended_shooter_pos: turnData.intended_shooter_pos,
          shooter_id: shotInfo.playerId
        });
        
        // Get shooter info
        const shooterInfo = scene.playerInfo?.[shotInfo.playerId];
        const shooterMO = shooterInfo?.attributes?.MO || 5;
        
        console.log('🔥 Shooter MO:', shooterMO, 'Info:', shooterInfo);
        
        // Determine audible text based on MO attribute
        const audibleText = shooterMO >= 7 ? "HOT READ!" : "AUDIBLE!";
        
        console.log('🔥 Audible text:', audibleText);
        
        // Update scoreboard with audible text next to ball icon (stays visible until shot completes)
        const { getBallHandlerIdFromTurn, getDefenderIdFromTurn } = await import('../utils/activePlayerDisplay.js');
        const defenderId = getDefenderIdFromTurn(turnData);
        const homeTeamId = scene.simData?.home_team_id || null;
        
        if (typeof window.updateActivePlayersDisplay === 'function') {
          console.log('🔥 Calling updateActivePlayersDisplay with audibleText:', audibleText);
          window.updateActivePlayersDisplay(shotInfo.playerId, defenderId, homeTeamId, playerSprites, audibleText);
        } else {
          console.warn('⚠️ window.updateActivePlayersDisplay not found');
        }
        
        isAudible = true;
      }
      
      const shotResult = await shootBall(shootParams);
      
      // Clear audible text after shot animation completes
      if (isAudible && typeof window.updateActivePlayersDisplay === 'function') {
        const { getBallHandlerIdFromTurn, getDefenderIdFromTurn } = await import('../utils/activePlayerDisplay.js');
        const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
        const defenderId = getDefenderIdFromTurn(turnData);
        const homeTeamId = scene.simData?.home_team_id || null;
        // Call without audibleText to clear it
        window.updateActivePlayersDisplay(ballHandlerId, defenderId, homeTeamId, playerSprites, null);
      }
      
      // console.log("🏀 HCO SHOT - shootBall returned", shotResult);
      const ballSpot = shotResult?.grid;
      // console.log("result_type", turnData.result_type);
      
      // Check if this MAKE is from a putback
      // With new OREB turn architecture, putbacks are separate turns, not events
      // But keep this check for backward compatibility
      const hasPutbackMake = turnData.events?.some(evt => 
        evt.event_type === "PUTBACK_ATTEMPT" && evt.result === "MAKE"
      );
      
      if (turnData.result_type === "MAKE") {
        // Visual effects for AND-1 now handled in ballManager.js when "And 1!" is announced
        
        // ✅ OPTION 1 FIX: Ensure onShotEnd() is called before transitioning to next operation
        // This ensures ball state is cleared before free throw or inbound pass
        const { getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        if (ballController && ballController.isInFlight) {
          ballController.onShotEnd();
        }
        
        // ✅ FIX: Match HCO's approach - call runInboundSetup() if next_play_type is BASELINE_INBOUND
        // This works for both HCO shots and FCP/HCT shots
        // For AND-1 situations (next_play_type === "FREE_THROW"), let the free throw system handle the transition
        const nextTurn = simData?.turns?.[scene.currentTurn + 1];
        const hasPendingFreeThrow =
          nextTurn?.result_type === "FREE_THROW" ||
          (turnData.free_throws_remaining && turnData.free_throws_remaining > 0);
        
        // ✅ FIX: Don't call runInboundSetup() here if next_play_type === "BASELINE_INBOUND"
        // The BASELINE_INBOUND turn will handle the inbound setup via AnimationEngine.handleBaselineInbound()
        // Calling it here causes double inbound passes and double setup animations
        if (!hasPendingFreeThrow && !hasPutbackMake && turnData.next_play_type === "BASELINE_INBOUND") {
          // ✅ REMOVED: runInboundSetup() call - BASELINE_INBOUND turn handles it
          // This prevents double inbound passes and double setup animations
        }
        
        // ✅ REMOVED: Special FCP/HCT handling - FCP/HCT now routes through AnimationRouter (same as HCO)
        // AnimationRouter handles announcements and updates via finalizeTurnAfterAnimation
      } else if (ballSpot) {
        if (turnData.result_type === 'BLOCK' || turnData.rebound_type === 'OREB') {
          console.log('🟡🟡🟡 [BLOCK/OREB BALL] playTurnAnimation calling animateRebound', {
            result_type: turnData.result_type,
            rebound_type: turnData.rebound_type,
            ballSpot,
          });
        }
        const rebounderId =
          turnData.rebounder_player_id ||
          turnData.rebounderId ||
          turnData.rebounder_id ||
          null;
        if (rebounderId) {
          // Use the unified animateRebound function for all rebounds
          await animateRebound({
            scene,
            ballSprite,
            playerSprites,
            animations: turnData.animations || [],
            rebounderId,
            ballSpot,
            shooterId: shotInfo?.playerId ?? null,
            upcomingFastBreak: turnData.fast_break || false,
            turnData: turnData // Pass turnData so get-back players can be excluded
          });
          
          const rebounderSprite = playerSprites[rebounderId];
          // ✅ FIX: Use offense_team_id (SS&S possession system)
          const isDreb = turnData.rebound_type
            ? turnData.rebound_type === "DREB"
            : rebounderSprite?.team_id !== turnData.offense_team_id;
          // ✅ Skip DREB setup if next play is Fast Break - player advancement happens in outlet phase
          if (isDreb && !turnData.fast_break && turnData.next_play_type !== "FAST_BREAK") {
            // Find the MISS/BLOCK turn that led to this DREB
            // In playTurnAnimation, turnData should be the MISS/BLOCK turn itself
            // Check if this turnData is a MISS or BLOCK turn first, otherwise look for it
            const isMissOrBlock = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
            let missTurn = isMissOrBlock ? turnData : null;
            if (!missTurn) {
              // If not, look for it in previous turn or current turn
              const currentIndex = scene.currentTurn || 0;
              const previousTurn = scene.simData?.turns?.[currentIndex - 1];
              const currentTurn = scene.simData?.turns?.[currentIndex];
              
              if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") {
                missTurn = previousTurn;
              } else if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") {
                missTurn = currentTurn;
              }
              
              console.log('🔍 [GET BACK DEBUG] Searching for MISS turn', {
                turnDataResultType: turnData?.result_type,
                currentTurnIndex: currentIndex,
                previousTurnResultType: previousTurn?.result_type,
                currentTurnResultType: currentTurn?.result_type,
                foundMissTurn: !!missTurn,
                missTurnHasGetBack: !!missTurn?.offense_getback
              });
            } else {
              console.log('🔍 [GET BACK DEBUG] Using current turnData as MISS turn', {
                turnDataResultType: turnData?.result_type,
                hasOffenseGetBack: !!turnData?.offense_getback,
                offenseGetBackCount: turnData?.offense_getback?.length || 0
              });
            }
            
            await runDefensiveReboundSetup({
              scene,
              ballSprite,
              playerSprites,
              rebounderId,
              nextPlayType: turnData.next_play_type || "HCO",
              turnData: missTurn // Pass the MISS turn so we can get offense_getback list
            });
          } else {
            const pause = animationConfig.offensiveRebound.pauseMs;
            await new Promise((res) =>
              scene.time?.delayedCall
                ? scene.time.delayedCall(pause, res)
                : setTimeout(res, pause)
            );
            if (!scene.skipToEnd && Array.isArray(turnData.events)) {
              eventsProcessed = true;
              for (const evt of turnData.events) {
                if (scene.skipToEnd) break;
                if (evt.event_type === "PUTBACK_ATTEMPT") {
                  // SKIP: Putback attempts are handled by handleOrebTurn() in animateGameTurns.js
                  // This event processing happens during step-by-step animation, but putbacks
                  // should be handled as a separate turn type, not as an event in the animation sequence.
                  // Attaching the ball here causes it to briefly attach before the shot animation.
                  // The handleOrebTurn function already properly handles ball attachment and shot animation.
                  continue;
                  if (evt.result === "MISS" && evt.rebound) {
                    const reboundData = evt.rebound;
                    const rebounderId =
                      reboundData.rebounder_player_id || reboundData.rebounderId;
                    await animateRebound({
                      scene,
                      ballSprite,
                      playerSprites,
                      animations: reboundData.animations || turnData.animations,
                      rebounderId,
                      ballSpot: putbackResult?.grid || reboundData.ballSpot,
                      shooterId: evt.shooterId,
                      turnData: turnData // Pass turnData so get-back players can be excluded
                    });
                    if (
                      reboundData.rebound_type === "DREB" &&
                      !turnData.fast_break
                    ) {
                      // For putback events, find the MISS/BLOCK turn with offense_getback
                      const isMissOrBlockEvt = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
                      let missTurn = isMissOrBlockEvt ? turnData : null;
                      if (!missTurn) {
                        const currentIndex = scene.currentTurn || 0;
                        missTurn = scene.simData?.turns?.[currentIndex - 1];
                      }
                      
                      await runDefensiveReboundSetup({
                        scene,
                        ballSprite,
                        playerSprites,
                        rebounderId,
                        nextPlayType: turnData.next_play_type || "HCO",
                        turnData: missTurn
                      });
                    }
                  }
                } else if (evt.event_type === "KICKOUT_RESET") {
                  await animateKickoutReset(
                    scene,
                    ballSprite,
                    evt.rebounder_player_id || evt.rebounderId,
                    evt.pgId,
                    evt.pass
                  );
                  if (typeof scene.startNextHalfCourtOffense === "function") {
                    scene.startNextHalfCourtOffense();
                  }
                }
              }
            }
          }
        }
      }
      break;
    }
  }

  if (!eventsProcessed && !scene.skipToEnd && Array.isArray(turnData.events)) {
    for (const evt of turnData.events) {
      if (scene.skipToEnd) break;
                if (evt.event_type === "PUTBACK_ATTEMPT") {
                  const shooterId = evt.shooterId;
                  const rebounderSprite = playerSprites[shooterId];
                  if (!rebounderSprite) continue;
                  attachBallToPlayer(scene, ballSprite, rebounderSprite, {
                    debugInfo: { shooterId, reboundSpot: evt.rebound?.ballSpot || null }
                  });
                  const rimCoords =
                    rebounderSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
                  const putbackResult = await animatePutbackAttempt(
                    scene,
                    ballSprite,
                    shooterId,
                    rimCoords,
                    evt.duration || 500,
                    evt.result
                  );
                  
                  // Handle made putbacks
                  if (evt.result === "MAKE") {
                    // Possession flips after made putback
                    const shooterTeamId = rebounderSprite.team_id;
                    const shooterTeamIsHome = String(shooterTeamId) === String(homeTeamId);
                    const newOffenseSide = shooterTeamIsHome ? "away" : "home";
                    
                    // Check for defensive pressure
                    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
                    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
                    if (skipRetreat) {
                      // Skip defensive retreat for FCP/HCT after putback
                    }
                    
                    await runInboundSetup({
                      scene,
                      ballSprite,
                      playerSprites,
                      newOffenseSide,
                      homeTeamId,
                      awayTeamId,
                      skipRetreat,
                      pressureType,
                    });
                  }
                  // Handle missed putbacks
                  else if (evt.result === "MISS" && evt.rebound) {
                    const reboundData = evt.rebound;
                    const rebounderId =
                      reboundData.rebounder_player_id || reboundData.rebounderId;
                    const putbackMissBallSpot = putbackResult?.grid || reboundData.ballSpot;
                    console.log('🟡🟡🟡 [BLOCK/OREB BALL] putback-miss path calling animateRebound', {
                      ballSpot: putbackMissBallSpot,
                      from_putbackResult: !!putbackResult?.grid,
                      from_reboundData: !!reboundData.ballSpot,
                    });
                    await animateRebound({
                      scene,
                      ballSprite,
                      playerSprites,
                      animations: reboundData.animations || turnData.animations,
                      rebounderId,
                      ballSpot: putbackMissBallSpot,
                      shooterId: evt.shooterId,
                      turnData: turnData // Pass turnData so get-back players can be excluded
                    });
                    if (
                      reboundData.rebound_type === "DREB" &&
                      !turnData.fast_break
                    ) {
                      // For putback events, find the MISS/BLOCK turn with offense_getback
                      const isMissOrBlockPutback = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
                      let missTurn = isMissOrBlockPutback ? turnData : null;
                      if (!missTurn) {
                        const currentIndex = scene.currentTurn || 0;
                        missTurn = scene.simData?.turns?.[currentIndex - 1];
                      }
                      
                      await runDefensiveReboundSetup({
                        scene,
                        ballSprite,
                        playerSprites,
                        rebounderId,
                        nextPlayType: turnData.next_play_type || "HCO",
                        turnData: missTurn
                      });
                    }
                  }
                } else if (evt.event_type === "KICKOUT_RESET") {
        await animateKickoutReset(
          scene,
          ballSprite,
          evt.rebounder_player_id || evt.rebounderId,
          evt.pgId,
          evt.pass
        );
        if (typeof scene.startNextHalfCourtOffense === "function") {
          scene.startNextHalfCourtOffense();
        }
      }
    }

  }
}

/**
 * Phase 4: Final Turn alignment — tween offense and defense to oDestinations/dDestinations.
 * When away team is on offense, flip both offense and defense coords so the whole setup is on the
 * away (attacking) half; backend sends home-side coords. Attaches ball to ball handler when done.
 */
export async function runFinalTurnAlignment({ scene, playerSprites, ballSprite, turnData }) {
  if (scene?.skipToEnd || !turnData) return;
  const oDestinations = turnData.oDestinations || turnData.o_destinations || {};
  const dDestinations = turnData.dDestinations || turnData.d_destinations || {};
  const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
  const offenseTeamId = resolveOffenseTeamId({ scene, turnData, playerSprites });
  const homeTeamId = scene.simData?.home_team_id;
  const isAwayOffense = offenseTeamId && homeTeamId && String(offenseTeamId) !== String(homeTeamId);
  const flipCoords = (coords) => ({ x: 101 - coords.x, y: coords.y });

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const cfg = animationConfig?.finalTurn?.alignment || {};
  const ease = cfg.ease ?? "Linear";

  const offenseSprites = {};
  const defenseSprites = {};
  let ballHandlerSprite = null;

  if (scene.tweens && ballSprite) scene.tweens.killTweensOf(ballSprite);
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
    if (String(sprite.team_id) === String(offenseTeamId)) {
      offenseSprites[info.pos] = sprite;
    } else {
      defenseSprites[info.pos] = sprite;
    }
  }

  const addTween = (sprite, coords, pos) => {
    if (!sprite || !coords) return Promise.resolve();
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    const duration = getPlayerDuration(sprite, x, y);
    return new Promise((resolve) => {
      scene.tweens.add({
        targets: sprite,
        x, y, duration, ease,
        onComplete: resolve,
        onStop: resolve
      });
    });
  };

  const promises = [];
  Object.entries(oDestinations).forEach(([pos, coords]) => {
    const c = isAwayOffense ? flipCoords(coords) : coords;
    promises.push(addTween(offenseSprites[pos], c, pos));
  });
  Object.entries(dDestinations).forEach(([pos, coords]) => {
    const c = isAwayOffense ? flipCoords(coords) : coords;
    promises.push(addTween(defenseSprites[pos], c, pos));
  });

  await Promise.all(promises);

  const ballHandlerId = turnData.ball_handler_id ?? turnData.roles?.ball_handler_id ?? turnData.ball_handler?.player_id;
  if (!ballHandlerId && turnData.animations?.length) {
    const animWithBall = turnData.animations.find(a => a.hasBallAtStep?.[0]);
    if (animWithBall) ballHandlerSprite = playerSprites[animWithBall.playerId];
  } else if (ballHandlerId) {
    ballHandlerSprite = playerSprites[ballHandlerId];
  }
  if (ballSprite && ballHandlerSprite) {
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
  }
}

export { runInboundSetup, runSideInboundSetup, runDefensiveReboundSetup, runOffensiveReboundKickoutSetup, getPlayerDuration, animateQuickFoulDefenderToReceiver };
// Provide an uncapped duration helper for long transitions (e.g., inbound -> HCO)
export function getPlayerDurationUncapped(sprite, targetX, targetY) {
  const currentX = sprite.x;
  const currentY = sprite.y;
  const distance = Phaser.Math.Distance.Between(currentX, currentY, targetX, targetY);
  const duration = (distance / PLAYER_SPEED) * 1000;
  // Keep a small lower bound to avoid zero-duration tweens; no upper cap
  return Math.max(50, duration);
}

// Animate a short defensive stop resolution and transition to HalfCourt
export async function runDefensiveStopTransition({ scene, playerSprites, ballSprite }) {
  try {
    const width = scene.game.config.width;
    const height = scene.game.config.height;
    const isHomeOffense = (scene.offenseTeamId && scene.simData?.home_team_id === scene.offenseTeamId) || false;
    // Choose a generic "top of key" on offense side
    const targetGrid = isHomeOffense ? { x: 86, y: 25 } : { x: 14, y: 25 };
    const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);

    const currentOwnerId = getCurrentOwner(scene);
    const handlerSprite = currentOwnerId ? playerSprites[currentOwnerId] : null;

    const promises = [];
    if (handlerSprite) {
      const handlerDuration = getPlayerDuration(handlerSprite, targetPx.x, targetPx.y, true);
      promises.push(
        tweenPlayerTo(scene, handlerSprite, targetPx, { duration: handlerDuration, easing: 'Linear' })
      );
      // Attach ball if not attached so it follows visually
      if (ballSprite) attachBallToPlayer(scene, ballSprite, handlerSprite);
    }

    // Move nearest defender to contest
    let nearestDefender = null;
    let nearestDist = Infinity;
    for (const [id, sprite] of Object.entries(playerSprites)) {
      if (!sprite || !scene.playerInfo?.[id]) continue;
      const info = scene.playerInfo[id];
      // Opposite team of offense
      const isDefender = info.team !== (isHomeOffense ? 'home' : 'away');
      if (!isDefender) continue;
      const d = Phaser.Math.Distance.Between(sprite.x, sprite.y, targetPx.x, targetPx.y);
      if (d < nearestDist) {
        nearestDist = d;
        nearestDefender = sprite;
      }
    }
    if (nearestDefender) {
      // Slight offset to indicate contest
      const contestPx = { x: targetPx.x + (isHomeOffense ? -18 : 18), y: targetPx.y };
      const defDuration = getPlayerDuration(nearestDefender, contestPx.x, contestPx.y, true);
      promises.push(
        tweenPlayerTo(scene, nearestDefender, contestPx, { duration: defDuration, easing: 'Linear' })
      );
    }

    if (promises.length) await Promise.all(promises);

    // Transition to HalfCourt for next possession
    if (scene.stateMachine) {
      safeTransition(scene.stateMachine, States.HalfCourt, 'defensive_stop_to_halfcourt');
    }
  } catch (err) {
    console.warn('runDefensiveStopTransition failed', err);
  }
}

if (typeof window !== "undefined") {
  window.playTurnAnimation = playTurnAnimation;
}
