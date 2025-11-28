import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
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
const DEFAULT_PLAYER_SPEED = 350; // Default speed (Normal preset)
const DEFAULT_BALL_SPEED = 350; // Default speed (Normal preset)

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

async function runSetupTween({ scene, ballSprite, animations, playerSprites, currentBallOwnerRef }) {
  if (scene.skipToEnd) return;
  const stepIndex = 0;
  const promises = [];

  for (const anim of animations) {
    if (scene.skipToEnd) break;
    const sprite = playerSprites[anim.playerId];
    const firstStep = anim.movement?.[stepIndex];
    if (!sprite || !firstStep) continue;

    const { x, y } = gridToPixels(
      firstStep.coords.x,
      firstStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    promises.push(new Promise((resolve) => {
      const tween = scene.tweens.add({
        targets: [sprite],
        x,
        y,
        duration: 1000,
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
async function runSideInboundSetup({ scene, ballSprite, playerSprites, turnData }) {
  if (!turnData || scene?.skipToEnd || scene?.stateMachine?.is(States.FreeThrow) || scene?.stateMachine?.is(States.FastBreak)) return;

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
  const offenseTeamId = scene.currentOffenseTeamId ?? possession_team_id;

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

  const promises = [];
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
          onComplete: () => {
            animationDebugLog(`tweenEnd:${pos}`);
            resolve();
          },
          onStop: () => {
            animationDebugLog(`tweenEnd:${pos}`);
            resolve();
          }
        });
      })
    );
  };

  Object.entries(oDestinations).forEach(([pos, coords]) => addTween(offenseSprites[pos], coords, pos));
  Object.entries(dDestinations).forEach(([pos, coords]) => addTween(defenseSprites[pos], coords, pos));

  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
  }

  await Promise.all(promises);

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
  const sfSprite = offenseSprites["SF"];
  const pgSprite = offenseSprites["PG"];
  const sfId = offenseIds["SF"];
  const pgId = offenseIds["PG"];
  
  if (sfSprite) {
    attachBallToPlayer(scene, ballSprite, sfSprite);
    animationDebugLog("ballAttach(SF)");

    animationDebugLog(`[sideInbound][holdStart] sf:${sfId} pg:${pgId}`);
    // Removed 1000ms pause for smoother transitions

    scene.events?.once('passStart', () => animationDebugLog('passStart'));
    scene.events?.once('tweenStart', () => animationDebugLog('tweenStart'));
    scene.events?.once('tweenEnd', () => animationDebugLog('tweenEnd'));
    scene.events?.once('passEnd', () => animationDebugLog('passEnd'));

    animationDebugLog(`[sideInbound][passStart] sf:${sfId} pg:${pgId}`);
    
    if (!scene.stateMachine?.is(States.FastBreak)) {
      if (passInfo) {
        // ✅ Use dynamic pass from animation data
        console.log('🏀 [SIDE_INBOUND] Using dynamic pass from animation data', passInfo);
        await handlePassAnimation({
          scene,
          passInfo,
          playerSprites
        });
      } else if (pgSprite) {
        // Fallback to hardcoded SF→PG pass
        console.log('🏀 [SIDE_INBOUND] Using fallback hardcoded SF→PG pass');
        await runPass(scene, { fromId: sfId, toId: pgId, easing: ease });
      }
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
  // The turnData parameter should be the MISS turn, but if not provided, try to find it
  let missTurn = turnData;
  if (!missTurn) {
    // Try current turn first (most likely)
    const currentTurn = scene.simData?.turns?.[scene.currentTurn || 0];
    if (currentTurn?.result_type === "MISS") {
      missTurn = currentTurn;
    } else {
      // Fallback to previous turn
      missTurn = scene.simData?.turns?.[(scene.currentTurn || 0) - 1];
    }
  }
  
  const getBackList = missTurn?.offense_getback || [];
  
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
  } else if (isPutbackInProgress) {
    console.log('🔍 [PUTBACK DEBUG] runDefensiveReboundSetup: Skipping ball attachment - putback in progress', {
      rebounderId
    });
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
  for (const [id, info] of Object.entries(scene.playerInfo || {})) {
    if (info.pos === "PG" && info.team === rebounderSprite.team) {
      outletReceiverId = id;
      outletReceiverSprite = playerSprites[id];
      break;
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
    
    console.log('🏀 [OUTLET STEP DEBUG] Starting DREB outlet animation - player check', {
      totalPlayers: Object.keys(playerSprites).length,
      getBackListCount: getBackList.length,
      getBackList,
      rebounderId,
      outletReceiverId,
      nextPlayType
    });
    
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
          4,  // Stay in bounds
          97
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
    console.warn(`🏀 [OUTLET STEP DEBUG] ⚠️ Outlet step animation SKIPPED - nextPlayType is "${nextPlayType}" (expected "HCO" or "FAST_BREAK")`, {
      nextPlayType,
      nextPlayTypeType: typeof nextPlayType,
      nextPlayTypeIsHCO: nextPlayType === "HCO",
      nextPlayTypeIsFastBreak: nextPlayType === "FAST_BREAK",
      nextPlayTypeValue: JSON.stringify(nextPlayType),
      rebounderId,
      note: 'This is why no players animated during outlet step! Only HCO and FAST_BREAK scenarios animate players during outlet step.'
    });
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
  turnData = null        // ✅ NEW: Optional turnData for dynamic pass detection
}) {
  animationDebugLog('runInboundSetup called:', {
    newOffenseSide,
    currentState: scene.stateMachine?.state,
    isFreeThrow: scene?.stateMachine?.is(States.FreeThrow),
    skipRetreat,
    pressureType
  });
  
  // ✅ SS&S: Set FCP/HCT state when pressureType is provided (called inline from ShotAnimationSystem)
  // This ensures state is set even when runInboundSetup is called directly, not from a BASELINE_INBOUND turn
  if (pressureType === "FCP" || pressureType === "HCT") {
    scene.currentPressureType = pressureType;
    scene.pressureSequenceActive = true;
    console.log('🎯 [FCP/HCT STATE] Setting pressure type from runInboundSetup:', {
      pressureType,
      pressureSequenceActive: scene.pressureSequenceActive,
      source: 'runInboundSetup (inline from ShotAnimationSystem)'
    });
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
        const targetX = gridToPixels(
          isAwayOffense ? 45 : 55,
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

  const pgDestPx = gridToPixels(inboundDest.PG.x, inboundDest.PG.y, width, height);
  animationDebugLog(`inboundDest assigned for PG: (${pgDestPx.x},${pgDestPx.y})`);
  const sgDestPx = gridToPixels(inboundDest.SG.x, inboundDest.SG.y, width, height);
  animationDebugLog(`inboundDest assigned for SG: (${sgDestPx.x},${sgDestPx.y})`);
  const pfDestPx = gridToPixels(inboundDest.PF.x, inboundDest.PF.y, width, height);
  animationDebugLog(`inboundDest assigned for PF: (${pfDestPx.x},${pfDestPx.y})`);
  const cDestPx = gridToPixels(inboundDest.C.x, inboundDest.C.y, width, height);
  animationDebugLog(`inboundDest assigned for C: (${cDestPx.x},${cDestPx.y})`);

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
  if (animationConfig.enableBallTween) {
    // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of tweenBallTo()
    // animateBallToPosition() gets ballSprite from scene.ballSprite internally
    ballTween = animateBallToPosition(scene, spotPx, {
      duration: 500,
      easing: "Sine.easeInOut"
    }).then(() => {
      animationDebugLog(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    });
  } else {
    ballSprite.setPosition(spotPx.x, spotPx.y);
    animationDebugLog(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    ballTween = Promise.resolve();
  }

  const sfTween = new Promise((resolve) => {
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // Use regular speed (not transition) for inbound setup - should be faster
    const sfDuration = getPlayerDuration(sfSprite, spotPx.x, spotPx.y, false);
    scene.tweens.add({
      targets: sfSprite,
      x: spotPx.x,
      y: spotPx.y,
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

  animationDebugLog(`[inbound][ballAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  attachBallToPlayer(scene, ballSprite, sfSprite);

  animationDebugLog(`[inbound][holdStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  // Removed 1000ms pause for smoother transitions

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
  if (passInfo) {
    // ✅ Use dynamic pass from animation data
    console.log('🏀 [BASELINE_INBOUND] Using dynamic pass from animation data', passInfo);
    await handlePassAnimation({
      scene,
      passInfo,
      playerSprites
    });
  } else {
    // Fallback to hardcoded SF→PG pass
    console.log('🏀 [BASELINE_INBOUND] Using fallback hardcoded SF→PG pass');
    await runPass(scene, {
      fromId: sfId,
      toId: pgId,
      duration: 500,
      easing: "Sine.easeInOut"
    });
  }
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
  // ✅ DEBUG: Log FCP/HCT detection in playTurnAnimation
  // ✅ FIX: Also check scene.pressureSequenceActive to match routing logic in animateGameTurns.js
  // This ensures cleanup code runs for FCP/HCT setup turns that are routed based on state
  const isFCPHCT = turnData.fcp_shot === true || turnData.hct_shot === true || 
                   turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                   turnData.fcp_foul === true || turnData.hct_foul === true ||
                   scene.pressureSequenceActive === true;
  if (isFCPHCT) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.log('🎬 [playTurnAnimation - FCP/HCT DETECTED]', {
      turn_index: turnIndex,
      pressureType,
      result_type: turnData.result_type,
      has_animations: !!turnData.animations?.length,
      animation_count: turnData.animations?.length || 0,
      will_animate: !!turnData.animations
    });
    
    // ✅ DEBUG: Log when we enter playTurnAnimation to animate FCP/HCT skeleton
    const hasFCPHCTSkeleton = (turnData.result_type === "MAKE" || turnData.result_type === "MISS") &&
                              (turnData.fcp_shot === true || turnData.hct_shot === true) &&
                              turnData.animations && 
                              turnData.animations.length > 0;
    if (hasFCPHCTSkeleton) {
      console.log('🚀 [ENTERING FCP/HCT SKELETON ANIMATION] Starting playTurnAnimation to animate FCP/HCT skeleton', {
        turn_index: turnIndex,
        pressureType,
        result_type: turnData.result_type,
        fcp_shot: turnData.fcp_shot,
        hct_shot: turnData.hct_shot,
        animation_count: turnData.animations?.length || 0,
        movement_lengths: turnData.animations?.map(a => a.movement?.length || 0) || [],
        has_skeleton: !!turnData.skeleton
      });
    }
  }
  
  // Guard: Skip if this is an opening tip, putback, or if animations is missing
  // Putback turns are handled by handleOrebTurn in animateGameTurns.js
  if (turnData.result_type === "OPENING_TIP" || 
      turnData.result_type === "PUTBACK_MAKE" || 
      turnData.result_type === "PUTBACK_MISS" ||
      !turnData.animations) {
    if (isFCPHCT) {
      console.error('❌ [FCP/HCT SKIPPED - NO ANIMATIONS]', {
        turn_index: turnIndex,
        result_type: turnData.result_type,
        has_animations: false,
        reason: 'Missing animations array'
      });
    }
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
  
  // ✅ DEBUG: Log FCP/HCT step count
  if (isFCPHCT) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.log('🔍 [FCP/HCT STEP COUNT]', {
      turn_index: turnIndex,
      pressureType,
      result_type: turnData.result_type,
      maxSteps,
      animation_count: turnData.animations?.length || 0,
      movement_lengths: turnData.animations?.map(a => a.movement?.length || 0) || [],
      will_loop: maxSteps > 1
    });
  }

  // ✅ Allow HCO turns even if state is FastBreak (can happen after defensive stop transition fails)
  // Check if this is an HCO turn (not fast_break and has animations) - if so, allow it
  const isHCOAfterFastBreak = !turnData.fast_break && 
                               (turnData.result_type === "MAKE" || turnData.result_type === "MISS") &&
                               turnData.animations?.length > 0 &&
                               scene.stateMachine?.is(States.FastBreak);
  
  // ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
  // FCP/HCT turns can occur after fast breaks (e.g., press break after fast break shot)
  const isFCPHCTTurn = turnData.fcp_shot === true || turnData.hct_shot === true ||
                       turnData.fcp_foul === true || turnData.hct_foul === true ||
                       turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                       scene.pressureSequenceActive;
  
  if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak && !isFCPHCTTurn) {
    console.log("⚠️ playTurnAnimation: Skipping - state is FastBreak and turn is not HCO or FCP/HCT", {
      result_type: turnData.result_type,
      fast_break: turnData.fast_break,
      has_animations: !!turnData.animations?.length,
      isFCPHCTTurn
    });
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
  // After a shot, the ball should remain at the rim/bounce spot until the next turn's animation moves it
  const previousTurnWasShot = scene._previousTurnWasShot === true;
  if (previousTurnWasShot) {
    console.log('🏀 playTurnAnimation: Skipping step 0 ball attachment - previous turn was a shot');
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
        const isShotInProgress = ballController && ballController.isInFlight && (ballController.reason === 'shot' || ballController.reason === 'putback_shot');
        console.log('🔍 [PUTBACK DEBUG] playTurnAnimation: Step 0 ball attachment attempt for putback turn - BLOCKING', {
          step0OwnerId,
          result_type: turnData.result_type,
          turnDataRebounderId: turnData.rebounderId,
          shotInProgress: isShotInProgress,
          sceneRebounderId: scene.rebounderId,
          note: 'Putback turns are handled by handleOrebTurn - skipping step 0 attachment'
        });
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

  // ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
  // FCP/HCT turns can occur after fast breaks (e.g., press break after fast break shot)
  const isFCPHCTTurnForEarlyExit = turnData.fcp_shot === true || turnData.hct_shot === true ||
                                    turnData.fcp_foul === true || turnData.hct_foul === true ||
                                    turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                                    scene.pressureSequenceActive;
  
  if (scene.skipToEnd || (scene.stateMachine?.is(States.FastBreak) && !isFCPHCTTurnForEarlyExit)) {
    // ✅ DEBUG: Log if FCP/HCT is being skipped due to skipToEnd or FastBreak state
    if (isFCPHCT) {
      const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
      console.error('❌ [FCP/HCT SKIPPED - EARLY EXIT]', {
        turn_index: turnIndex,
        pressureType,
        result_type: turnData.result_type,
        skipToEnd: scene.skipToEnd,
        isFastBreak: scene.stateMachine?.is(States.FastBreak),
        reason: scene.skipToEnd ? 'skipToEnd flag' : 'FastBreak state'
      });
    }
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
    offenseTeamId: scene.currentOffenseTeamId ?? turnData.possession_team_id,
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

  // ✅ SIMPLER FIX: For FCP/HCT turns, run setup tween to move players to step 0 positions
  // This matches ShotAnimationSystem's approach and gives tween manager time to settle
  // after runInboundSetup() completes
  if (isFCPHCT && !scene.skipToEnd && maxSteps > 1) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.log('🔧 [FCP/HCT SETUP TWEEN] Moving players to step 0 positions before skeleton animation', {
      turn_index: turnIndex,
      pressureType,
      maxSteps,
      animation_count: turnData.animations?.length || 0
    });
    
    await runSetupTween({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      currentBallOwnerRef
    });
    
    console.log('✅ [FCP/HCT SETUP TWEEN COMPLETE] Players positioned at step 0, starting skeleton animation');
  }

  let eventsProcessed = false;
  
  // ✅ DEBUG: Log FCP/HCT step loop start
  if (isFCPHCT) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.log('🔍 [FCP/HCT STEP LOOP START]', {
      turn_index: turnIndex,
      pressureType,
      maxSteps,
      will_execute: maxSteps > 1,
      loop_range: maxSteps > 1 ? `stepIndex 1 to ${maxSteps - 1}` : 'NO LOOP (maxSteps <= 1)',
      animation_details: turnData.animations?.map(a => ({
        playerId: a.playerId,
        movement_length: a.movement?.length || 0,
        first_step_action: a.movement?.[0]?.action,
        last_step_action: a.movement?.[a.movement.length - 1]?.action
      })) || [],
      skipToEnd: scene.skipToEnd,
      isFastBreak: scene.stateMachine?.is(States.FastBreak)
    });
  }

  // ✅ DEBUG: Log immediately before loop starts
  console.log('🔍 [BEFORE STEP LOOP]', {
    maxSteps,
    will_enter_loop: maxSteps > 1,
    skipToEnd: scene.skipToEnd,
    isFastBreak: scene.stateMachine?.is(States.FastBreak),
    pressureSequenceActive: scene.pressureSequenceActive,
    currentPressureType: scene.currentPressureType,
    turnDataKeys: Object.keys(turnData).filter(k => k.includes('fcp') || k.includes('hct') || k.includes('defensive'))
  });

  // ✅ CRITICAL FIX: Kill all ball tweens before starting step loop
  // Lingering ball tweens from previous shots/passes can block the tween manager
  // This is especially important for FCP/HCT turns that come after shots
  if (ballSprite && scene.tweens) {
    const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
    if (ballActiveTweens.length > 0) {
      console.warn('🔧 [BALL TWEEN CLEANUP] Killing lingering ball tweens before step loop', {
        ballActiveTweensCount: ballActiveTweens.length,
        ballActiveTweenIds: ballActiveTweens.map(t => t._animateStepId || 'no-id'),
        isFCPHCT: isFCPHCT,
        pressureType: scene.currentPressureType
      });
      scene.tweens.killTweensOf(ballSprite);
      // Also kill ball shadow tweens if they exist
      if (scene.ballShadowSprite) {
        scene.tweens.killTweensOf(scene.ballShadowSprite);
      }
    }
  }

  // ✅ CRITICAL FIX: For FCP/HCT skeleton animations, kill ALL player sprite tweens
  // and add a small delay to allow the tween manager to settle after runInboundSetup()
  // This fixes the race condition where skeleton animation tweens don't progress
  if (isFCPHCT && scene.tweens && playerSprites) {
    let totalPlayerTweensKilled = 0;
    const playerTweenDetails = [];
    
    // Kill tweens on all player sprites
    for (const [playerId, sprite] of Object.entries(playerSprites)) {
      if (sprite && scene.tweens.getTweensOf) {
        const playerTweens = scene.tweens.getTweensOf(sprite);
        if (playerTweens.length > 0) {
          totalPlayerTweensKilled += playerTweens.length;
          playerTweenDetails.push({
            playerId,
            tweenCount: playerTweens.length,
            tweenIds: playerTweens.map(t => t._animateStepId || 'no-id')
          });
          scene.tweens.killTweensOf(sprite);
        }
      }
    }
    
    // Log tween manager state before FCP/HCT skeleton animation
    const tweenManagerState = {
      totalTweens: scene.tweens.getAll ? scene.tweens.getAll().length : 'N/A',
      isPaused: scene.tweens.isPaused ? scene.tweens.isPaused() : 'N/A',
      timeScale: scene.tweens.timeScale ?? 'N/A'
    };
    
    console.log('🔧 [FCP/HCT TWEEN CLEANUP] Killed player sprite tweens before skeleton animation', {
      totalPlayerTweensKilled,
      playerTweenDetails,
      tweenManagerState,
      pressureType: scene.currentPressureType,
      turn_index: turnIndex
    });
    
    // Add a small delay (50ms) to allow the tween manager to settle
    // This is the key fix for the race condition where skeleton animation tweens
    // are created immediately after runInboundSetup() but don't progress
    if (totalPlayerTweensKilled > 0 || tweenManagerState.totalTweens > 0) {
      console.log('🔧 [FCP/HCT TWEEN SETTLE] Waiting 50ms for tween manager to settle', {
        totalPlayerTweensKilled,
        remainingTweens: tweenManagerState.totalTweens,
        pressureType: scene.currentPressureType
      });
      await new Promise(resolve => {
        if (scene.time && scene.time.delayedCall) {
          scene.time.delayedCall(50, resolve);
        } else {
          setTimeout(resolve, 50);
        }
      });
      
      // Log tween manager state after delay
      const postDelayState = {
        totalTweens: scene.tweens.getAll ? scene.tweens.getAll().length : 'N/A',
        isPaused: scene.tweens.isPaused ? scene.tweens.isPaused() : 'N/A',
        timeScale: scene.tweens.timeScale ?? 'N/A'
      };
      console.log('🔧 [FCP/HCT TWEEN SETTLE COMPLETE] Tween manager state after delay', {
        postDelayState,
        pressureType: scene.currentPressureType
      });
    }
  }

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    // ✅ DEBUG: Log at the very start of each loop iteration
    console.log('🔍 [LOOP ITERATION START]', {
      stepIndex,
      maxSteps,
      condition: `${stepIndex} < ${maxSteps} = ${stepIndex < maxSteps}`,
      skipToEnd: scene.skipToEnd,
      isFastBreak: scene.stateMachine?.is(States.FastBreak)
    });
    // ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
    // FCP/HCT turns can occur after fast breaks (e.g., press break after fast break shot)
    const isFCPHCTTurnForStepLoop = turnData.fcp_shot === true || turnData.hct_shot === true ||
                                     turnData.fcp_foul === true || turnData.hct_foul === true ||
                                     turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                                     scene.pressureSequenceActive;
    
    // ✅ DEBUG: Log the early exit check details
    const willEarlyExit = scene.skipToEnd || (scene.stateMachine?.is(States.FastBreak) && !isFCPHCTTurnForStepLoop);
    console.log('🔍 [EARLY EXIT CHECK]', {
      stepIndex,
      skipToEnd: scene.skipToEnd,
      isFastBreak: scene.stateMachine?.is(States.FastBreak),
      isFCPHCTTurnForStepLoop,
      willEarlyExit,
      reason: scene.skipToEnd ? 'skipToEnd' : 
              (scene.stateMachine?.is(States.FastBreak) && !isFCPHCTTurnForStepLoop) ? 'FastBreak state and not FCP/HCT' : 
              'none'
    });
    
    // ✅ CRITICAL FIX: Kill ball tweens at the start of EACH step iteration
    // Passes within the step loop can leave lingering ball tweens that block subsequent steps
    if (ballSprite && scene.tweens && !willEarlyExit) {
      const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        console.warn('🔧 [BALL TWEEN CLEANUP - STEP ITERATION] Killing lingering ball tweens at start of step', {
          stepIndex,
          ballActiveTweensCount: ballActiveTweens.length,
          ballActiveTweenIds: ballActiveTweens.map(t => t._animateStepId || 'no-id'),
          isFCPHCT: isFCPHCT,
          pressureType: scene.currentPressureType
        });
        scene.tweens.killTweensOf(ballSprite);
        if (scene.ballShadowSprite) {
          scene.tweens.killTweensOf(scene.ballShadowSprite);
        }
      }
    }
    
    if (willEarlyExit) {
      // ✅ DEBUG: Log early exit for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        console.warn('⚠️ [FCP/HCT STEP LOOP EARLY EXIT]', {
          turn_index: turnIndex,
          pressureType,
          stepIndex,
          maxSteps,
          skipToEnd: scene.skipToEnd,
          isFastBreak: scene.stateMachine?.is(States.FastBreak),
          isFCPHCTTurnForStepLoop,
          pressureSequenceActive: scene.pressureSequenceActive,
          currentPressureType: scene.currentPressureType
        });
      }
      break;
    }
    
    // ✅ DEBUG: Log FCP/HCT step execution for ALL steps
    if (isFCPHCT) {
      const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
      console.log('🎬 [FCP/HCT STEP EXECUTING]', {
        turn_index: turnIndex,
        pressureType,
        stepIndex,
        maxSteps,
        is_animating: true,
        will_complete: stepIndex < maxSteps - 1
      });
    }

    // Trigger lean meter animation at middle step
    if (scene._leanScoreToAnimate !== null && 
        scene._leanAnimationStep === stepIndex && 
        !scene._leanAnimationTriggered) {
      const { animateLeanMeter } = await import('../ui/playcallCenter.js');
      animateLeanMeter(scene._leanScoreToAnimate);
      scene._leanAnimationTriggered = true;
    }

    // ✅ FIX: Skip updateBallOwnership if a pass is happening at this step OR
    // if a pass just completed (passInFlight is still true from previous step)
    // We'll handle the pass explicitly after movements complete (like shots)
    // ✅ REFACTOR: Use unified passDetection.js for consistency
    const { detectPassAtStep } = await import('./passDetection.js');
    const passHappeningAtThisStep = !!detectPassAtStep(turnData.animations, stepIndex);
    
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
        offenseTeamId: scene.currentOffenseTeamId ?? turnData.possession_team_id,
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

    const promises = [];
    let shotInfo = null;
    let passInfo = null;

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
      const duration = getPlayerDuration(sprite, targetX, targetY);
      
      // ✅ DEBUG: Log player movement animation for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        const distance = Phaser.Math.Distance.Between(sprite.x, sprite.y, targetX, targetY);
        console.log('👟 [FCP/HCT PLAYER MOVEMENT]', {
          turn_index: turnIndex,
          pressureType,
          stepIndex,
          playerId: anim.playerId,
          action: nextStep.action,
          currentPos: { x: sprite.x, y: sprite.y },
          targetPos: { x: targetX, y: targetY },
          distance,
          duration,
          will_animate: duration > 0
        });
      }

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

      // ✅ SCALABLE FIX: Use shared pass detection utility
      // This ensures passes work consistently across all turn types
      if (!passInfo) {
        const { detectPassAtStep } = await import('./passDetection.js');
        passInfo = detectPassAtStep(turnData.animations, stepIndex);
        // Removed verbose pass detection log
        // if (passInfo) {
        //   console.log('🏀 [PASS DETECTED]', { ... });
        // }
        if (passInfo) {
        }
      }

      if (nextStep.action === "shoot") {
        shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        // ✅ DEBUG: Log shot detection in FCP/HCT
        if (isFCPHCT) {
          const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
          console.log('🏀 [FCP/HCT SHOT DETECTED]', {
            turn_index: turnIndex,
            pressureType,
            stepIndex,
            shooterId: anim.playerId,
            result_type: turnData.result_type
          });
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

      promises.push(promise);
    }

    await Promise.all(promises);
    
    // ✅ DEBUG: Log step completion for FCP/HCT
    if (isFCPHCT) {
      const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
      const willContinue = stepIndex < maxSteps - 1;
      console.log('✅ [FCP/HCT STEP COMPLETE]', {
        turn_index: turnIndex,
        pressureType,
        stepIndex,
        maxSteps,
        has_shot: !!shotInfo,
        has_pass: !!passInfo,
        will_continue: willContinue,
        next_step: stepIndex + 1,
        loop_condition: `stepIndex (${stepIndex}) < maxSteps (${maxSteps})`,
        loop_will_continue: stepIndex < maxSteps
      });
      
      // ✅ DEBUG: Log if loop should continue
      if (!willContinue) {
        console.log('🛑 [FCP/HCT LOOP ENDING]', {
          turn_index: turnIndex,
          pressureType,
          stepIndex,
          maxSteps,
          reason: stepIndex >= maxSteps - 1 ? 'Reached maxSteps - 1' : 'Unknown'
        });
      }
    }

    // ✅ FIX: Handle passes explicitly (following shot pattern)
    // This ensures passes animate smoothly instead of teleporting
    if (passInfo) {
      const passerSprite = playerSprites[passInfo.passerId];
      const receiverSprite = playerSprites[passInfo.receiverId];
      
      // ✅ DEBUG: Log pass handling for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        console.log('🏀 [FCP/HCT PASS HANDLING]', {
          turn_index: turnIndex,
          pressureType,
          stepIndex,
          maxSteps,
          will_continue_after_pass: stepIndex < maxSteps - 1,
          next_step: stepIndex + 1
        });
      }
      
      // ✅ SCALABLE FIX: Handle passes using shared utility
      // This works for all turn types (HCO shots, fouls, turnovers, etc.)
      const { handlePassAnimation } = await import('./passDetection.js');
      await handlePassAnimation({
        scene,
        passInfo,
        playerSprites
      });
      
      // ✅ DEBUG: Log pass completion for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        console.log('✅ [FCP/HCT PASS COMPLETE]', {
          turn_index: turnIndex,
          pressureType,
          stepIndex,
          maxSteps,
          will_continue: stepIndex < maxSteps - 1,
          next_step: stepIndex + 1
        });
      }
    } else {
      // Debug: log when we DON'T have passInfo but might expect one
      const hasPassAction = turnData.animations.some(anim => 
        anim.movement?.some(step => step.action === "pass")
      );
      // Removed verbose pass debug warning
      // if (hasPassAction) {
      //   console.log('⚠️ [PASS DEBUG] Pass action exists but passInfo is null', { ... });
      // }
    }
    
    // ✅ DEBUG: Log step loop completion for FCP/HCT (after loop completes)
    if (isFCPHCT) {
      const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
      console.log('🏁 [FCP/HCT STEP LOOP FINISHED]', {
        turn_index: turnIndex,
        pressureType,
        maxSteps,
        completed_steps: maxSteps - 1,
        has_shot: !!shotInfo,
        has_pass: !!passInfo
      });
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
      
      // ✅ DEBUG: Log before calling shootBall for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        console.log('🏀 [FCP/HCT ABOUT TO SHOOT] Calling shootBall', {
          turn_index: turnIndex,
          pressureType,
          stepIndex: shotInfo.stepIndex,
          shooterId: shotInfo.playerId,
          result_type: turnData.result_type,
          fromCoords: shootParams.fromCoords
        });
      }
      
      const shotResult = await shootBall(shootParams);
      
      // ✅ DEBUG: Log after shootBall returns for FCP/HCT
      if (isFCPHCT) {
        const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
        console.log('🏀 [FCP/HCT SHOOT COMPLETE] shootBall returned', {
          turn_index: turnIndex,
          pressureType,
          result_type: turnData.result_type,
          ballSpot: shotResult?.grid,
          will_handle_made_miss: true
        });
      }
      
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
        
        if (!hasPendingFreeThrow && !hasPutbackMake && turnData.next_play_type === "BASELINE_INBOUND") {
          // ✅ CRITICAL: After a made shot, possession flips:
          // - Team that just scored (was on offense) is now on DEFENSE
          // - Team that was on defense is now on OFFENSE
          // - newOffenseSide is the team that is NOW on offense (the team that was defending)
          // - The defensive team (team that just scored) will apply FCP/HCT pressure
          // - Backend determines FCP/HCT based on the team that just scored (now on defense)
          // - Frontend receives next_defensive_setup from backend, so we use the correct team's settings
          const shooterTeamIsHome =
            String(shooterTeamId) === String(homeTeamId);
          const newOffenseSide = shooterTeamIsHome ? "away" : "home";
          
          // Check if FCP/HCT is coming next - if so, skip retreat animation
          const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
          const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
          
          // ✅ DEBUG: Log inbound setup for FCP/HCT shots
          if (isFCPHCT) {
            const fcpHctType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
            console.log('🏀 [FCP/HCT MADE SHOT] Calling runInboundSetup (matching HCO approach)', {
              turn_index: turnIndex,
              fcpHctType,
              result_type: turnData.result_type,
              next_play_type: turnData.next_play_type,
              next_defensive_setup: turnData.next_defensive_setup,
              skipRetreat,
              pressureType,
              newOffenseSide
            });
          }
          
          const releaseGuard = createTransitionGuard(scene.stateMachine, [States.Rebound]);
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
          releaseGuard?.();
          
          if (isFCPHCT) {
            console.log('🏀 [FCP/HCT MADE SHOT] Inbound setup completed - next turn should be FCP/HCT press break');
          }
        } else if (isFCPHCT && !hasPendingFreeThrow && !hasPutbackMake) {
          // ✅ DEBUG: Log when we skip runInboundSetup for FCP/HCT (e.g., if next_play_type is not BASELINE_INBOUND)
          const fcpHctType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
          console.log('🏀 [FCP/HCT MADE SHOT] Skipping runInboundSetup', {
            turn_index: turnIndex,
            fcpHctType,
            result_type: turnData.result_type,
            next_play_type: turnData.next_play_type,
            hasPendingFreeThrow,
            hasPutbackMake,
            reason: 'next_play_type is not BASELINE_INBOUND or has pending free throw/putback'
          });
        }
      } else if (ballSpot) {
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
          const isDreb = turnData.rebound_type
            ? turnData.rebound_type === "DREB"
            : rebounderSprite?.team_id !== turnData.possession_team_id;
          // ✅ Skip DREB setup if next play is Fast Break - player advancement happens in outlet phase
          if (isDreb && !turnData.fast_break && turnData.next_play_type !== "FAST_BREAK") {
            // Find the MISS turn that led to this DREB
            // In playTurnAnimation, turnData should be the MISS turn itself
            // Check if this turnData is a MISS turn first, otherwise look for it
            let missTurn = turnData?.result_type === "MISS" ? turnData : null;
            if (!missTurn) {
              // If not, look for it in previous turn or current turn
              const currentIndex = scene.currentTurn || 0;
              const previousTurn = scene.simData?.turns?.[currentIndex - 1];
              const currentTurn = scene.simData?.turns?.[currentIndex];
              
              if (previousTurn?.result_type === "MISS") {
                missTurn = previousTurn;
              } else if (currentTurn?.result_type === "MISS") {
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
                      // For putback events, find the MISS turn with offense_getback
                      // This is the turn containing this event (putback after original MISS)
                      let missTurn = turnData?.result_type === "MISS" ? turnData : null;
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
                      // For putback events, find the MISS turn with offense_getback
                      let missTurn = turnData?.result_type === "MISS" ? turnData : null;
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
  
  // ✅ DEBUG: Log FCP/HCT animation completion in playTurnAnimation
  const isFCPHCTComplete = turnData.fcp_shot === true || turnData.hct_shot === true || 
                           turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                           turnData.fcp_foul === true || turnData.hct_foul === true;
  if (isFCPHCTComplete) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.log('✅ [playTurnAnimation - FCP/HCT COMPLETE]', {
      turn_index: turnIndex,
      pressureType,
      result_type: turnData.result_type,
      outcome: turnData.result_type, // This is the outcome of the FCP/HCT step
      next_play_type: turnData.next_play_type,
      possession_flips: turnData.possession_flips,
      animation_completed: true
    });
  }
}

export { runInboundSetup, runSideInboundSetup, runDefensiveReboundSetup, getPlayerDuration };
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

