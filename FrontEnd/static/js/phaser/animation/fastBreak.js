import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { tweenPlayerTo, runPass } from "./ballTween.js";
import { animateShotToRim } from "./ballAnimationSimple.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
import { States, safeTransition } from "../state/gameStateMachine.js";
import { getCurrentOwner } from "./BallControllerAdapter.js";
import { runInboundSetup, getPlayerDuration } from "./turnAnimation.js";
import { animationDebugLog, isAnimationDebugEnabled } from "../utils/debugFlags.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import {
  REBOUNDER_X_MIN,
  REBOUNDER_X_MAX,
  REBOUNDER_Y_RANGE,
  SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
  OUTLET_PASSER_MOVE_X,
  STEAL_ENTRY_MOVE_X_MIN,
  STEAL_ENTRY_MOVE_X_MAX,
  STEAL_ENTRY_MOVE_Y_RANGE,
  STEAL_ENTRY_Y_MIN,
  STEAL_ENTRY_Y_MAX,
} from "../constants/fastBreakConstants.js";

/**
 * Simplified Fast Break Animation System
 * 
 * Flow:
 * 1. Outlet Pass (if outlet_passer exists)
 * 2. Fast Break Resolution (shot, stop, foul, turnover, steal)
 * 3. Outcome handling and state transitions
 */

export async function runFastBreakSequence({
  scene,
  turnData,
  playerSprites,
  ballSprite,
  turnIndex = null,
}) {
  if (!scene || !turnData || scene.skipToEnd) {
    return;
  }
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const debugEnabled = isAnimationDebugEnabled();
  
  // Stop any existing timeline/tweens
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }
  
  const currentState = scene.stateMachine?.state;
  
  // ✅ Check current state before transitioning - avoid invalid transitions
  // For defensive stops after HCO, we're already in HalfCourt, so transition to FastBreak directly
  // For Fast Break from DREB, we should be in Rebound/OutletSetup, so can transition to FastBreakOutlet
  if (turnData.roles?.outlet_passer && currentState !== States.FastBreak && currentState !== States.FastBreakOutlet) {
    // Only transition to FastBreakOutlet if we have outlet pass and we're not already in Fast Break state
    // Check if we can transition (must be coming from Rebound or OutletSetup)
    if (currentState === States.Rebound || currentState === States.OutletSetup) {
      safeTransition(scene.stateMachine, States.FastBreakOutlet);
    } else {
      // Coming from HalfCourt (defensive stop scenario) - go directly to FastBreak
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (currentState !== States.FastBreak && currentState !== States.FastBreakOutlet) {
    // No outlet pass or already in Fast Break state - just ensure we're in FastBreak
    safeTransition(scene.stateMachine, States.FastBreak);
  }
  
  scene.events?.emit("fb:start");
  
  // ============================================================================
  // PHASE 1: OUTLET PASS (if applicable) - WITHOUT moving receiver toward basket
  // ============================================================================
  if (turnData.roles?.outlet_passer && turnData.roles?.outlet_receiver) {
    await animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height);
    
    // Transition to FastBreak state after outlet (only if not already there)
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (turnData.roles?.is_steal_entry || (!turnData.roles?.outlet_passer && !turnData.roles?.outlet_receiver)) {
    // ============================================================================
    // PHASE 1b: STEAL ENTRY (for steal-initiated Fast Breaks)
    // ============================================================================
    // Check is_steal_entry flag OR if there's no outlet pass (steal-initiated)
    await animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height);
    
    // Transition to FastBreak state after steal entry
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  }
  
  if (scene.skipToEnd) {
    return;
  }
  
  // ============================================================================
  // PHASE 2: FAST BREAK RESOLUTION - Check result BEFORE moving toward basket
  // ============================================================================
  const result = turnData.result_type;
  
  if (result === "MAKE" || result === "MISS") {
    // Shot attempt scenario
    // Check if ball handler beat the defender (skill check won)
    if (turnData.roles?.ball_handler_beats_defender && turnData.stopper_id) {
      // Ball handler won skill check - animate past stopper to shot spot
      await animateFastBreakShotWithStopper(scene, turnData, playerSprites, ballSprite, width, height);
    } else {
      // Normal shot attempt (no stopper or stopper not in position)
      await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height);
    }
  } else {
    // Defensive stop, foul, turnover, or steal - position for defensive stop (outlet receiver hasn't moved too far)
    await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
  }
  
  if (scene.skipToEnd) {
    return;
  }
  
  // ============================================================================
  // PHASE 3: CLEANUP & STATE TRANSITIONS
  // ============================================================================
  scene.events?.emit("fb:end");
}

/**
 * Phase 1: Outlet Pass Animation
 * - Outlet receiver moves to target spot
 * - Defenders chase (move toward basket)
 * - All other players hold position
 */
async function animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height) {
  const passerId = turnData.roles.outlet_passer;
  const receiverId = turnData.roles.outlet_receiver;
  const passerSprite = playerSprites[passerId];
  const receiverSprite = playerSprites[receiverId];
  
  if (!passerSprite || !receiverSprite) return;
  
  // Attach ball to rebounder/passer
  attachBallToPlayer(scene, ballSprite, passerSprite);
  
  // Determine offense team and basket
  const isHomeOffense = receiverSprite.team === "home";
  const targetBasket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const newOffenseTeam = isHomeOffense ? "home" : "away";
  
  // Find the original MISS turn to get offense_getback list
  let missTurn = null;
  const currentIndex = scene.currentTurn || 0;
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  const currentTurn = scene.simData?.turns?.[currentIndex];
  
  if (previousTurn?.result_type === "MISS") {
    missTurn = previousTurn;
  } else if (currentTurn?.result_type === "MISS") {
    missTurn = currentTurn;
  }
  
  const getBackList = missTurn?.offense_getback || [];
  
  // ✅ Outlet receiver receives pass at current position (NO MOVEMENT during outlet pass)
  // Ball handler will only move during defensive stop/shot attempt step
  const receiverCurrentGrid = {
    x: (receiverSprite.x / width) * 100,
    y: 50 - (receiverSprite.y / height) * 50
  };
  
  // Outlet receiver stays at current position (no movement)
  const outletTarget = receiverCurrentGrid;
  const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
  
  const promises = [];
  
  // Outlet receiver receives pass at current position (no movement animation needed)
  // Note: Ball will still animate from passer to receiver, but receiver doesn't move
  
  // ✅ Defenders stay at current position during outlet pass (NO MOVEMENT)
  // Defenders will only move during defensive stop/shot attempt step
  // Note: No animation needed for defenders during outlet pass
  
  // ✅ TEMPORARILY COMMENTED OUT: Advance other players during outlet step
  // For now, only animate the outlet pass - other players stay where they are
  // TODO: May want to re-enable this in the future for more organic fast break feel
  /*
  // ✅ SIMULTANEOUSLY advance all other players (except get-back, outlet passer, and outlet receiver)
  // This moves players up the court at the same time as the outlet pass
  let playersAdvanced = 0;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    const isGetBackPlayer = getBackList.includes(id);
    const isOutletPasser = id === passerId;
    const isOutletReceiver = id === receiverId;
    const isDefender = defendersSet.has(id);
    
    // Skip: get-back players, outlet passer/receiver, defenders (already handled above)
    if (!info || isGetBackPlayer || isOutletPasser || isOutletReceiver || isDefender) {
      continue;
    }
    
    // Calculate movement toward new offense basket
    const currentGridX = (sprite.x / width) * 100;
    const currentGridY = 50 - (sprite.y / height) * 50;
    
    // Move 20-30 grid spots toward new offense basket
    const distance = Phaser.Math.Between(20, 30);
    const directionAdvance = newOffenseTeam === "home" ? 1 : -1;
    
    const targetGrid = {
      x: Phaser.Math.Clamp(
        currentGridX + directionAdvance * distance,
        4,
        97
      ),
      y: Phaser.Math.Clamp(
        currentGridY + Phaser.Math.Between(-10, 10),
        10,
        40
      )
    };
    
    const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
    const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
    
    promises.push(
      tweenPlayerTo(scene, sprite, targetPx, {
        duration: playerDuration,
        easing: "Linear"
      })
    );
    playersAdvanced++;
  }
  */
  
  // Wait for receiver and defenders to complete (outlet pass happens after)
  await Promise.all(promises);
  
  // THEN outlet pass (happens after all players are in position, but visually flows with the movement)
  await runPass(scene, {
    fromId: passerId,
    toId: receiverId,
    duration: 500,
    easing: "Sine.easeInOut"
  });
  
  // ✅ PHASE 2.8: Defensive attachment verification for fast breaks
  // Wait a small delay to ensure pass animation is fully complete
  // Then verify and fix attachment if needed
  await new Promise(resolve => {
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(50, resolve); // Small delay to ensure pass completes
    } else {
      setTimeout(resolve, 50);
    }
  });
  
  const { getBallController, synchronizeBallState } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  // ✅ PHASE 2.9: Synchronize state to ensure consistency
  synchronizeBallState(scene, {
    clearPassState: true,
    allowAttachment: true
  });
  
  if (ballController && receiverSprite) {
    // ✅ DEFENSIVE: Multiple checks to ensure ball is properly attached
    const isAttachedToReceiver = ballController.isAttached && 
                                  ballController.currentOwner === receiverSprite;
    const isInFlight = ballController.isInFlight;
    const wrongOwner = ballController.isAttached && 
                       ballController.currentOwner !== receiverSprite;
    
    // Fix attachment if needed
    if (!isAttachedToReceiver || isInFlight || wrongOwner) {
      // Clear any in-flight state first
      if (isInFlight) {
        ballController.onPassEnd(receiverSprite, { reason: 'fast_break_outlet_fix' });
      } else {
        // Direct attachment if not in flight
        attachBallToPlayer(scene, ballSprite, receiverSprite, { 
          reason: 'fast_break_outlet_verify',
          debugInfo: { reason: 'fast_break_outlet_verify', wasInFlight: isInFlight }
        });
      }
    }
    
    // ✅ DEFENSIVE: Verify attachment succeeded with retry
    if (!ballController.isAttached || ballController.currentOwner !== receiverSprite) {
      console.warn('Fast break: Ball attachment verification failed, retrying...', {
        isAttached: ballController.isAttached,
        currentOwner: ballController.currentOwner?.playerId,
        expectedReceiver: receiverId,
        isInFlight: ballController.isInFlight,
        reason: ballController.reason
      });
      // Retry attachment with state sync
      synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
      attachBallToPlayer(scene, ballSprite, receiverSprite, { 
        reason: 'fast_break_outlet_retry',
        debugInfo: { reason: 'fast_break_outlet_retry' }
      });
    }
  }
}

/**
 * Phase 1b: Steal Entry Animation (for steal-initiated Fast Breaks)
 * - Stealer (ball handler) moves 5-10 x spots toward basket
 * - Stealer moves ±4 y spots (clamped to 3-47)
 * - Ball is already attached to stealer from the steal turn
 */
async function animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height) {
  // Get ball handler ID from roles (backend stores player object, frontend gets ID)
  const ballHandlerId = turnData.roles?.ball_handler_id ||
                        turnData.roles?.ball_handler?.player_id || 
                        turnData.ball_handler_id ||
                        turnData.stealer_id; // Fallback to stealer_id for steals
  const ballHandlerSprite = ballHandlerId ? playerSprites[ballHandlerId] : null;
  
  if (!ballHandlerSprite) {
    console.warn("Steal Entry: Ball handler sprite not found", { 
      ballHandlerId, 
      roles: turnData.roles,
      stealer_id: turnData.stealer_id 
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
      reason: 'steal_entry_verify'
    });
  }
  
  // Get stealer's current position
  const currentGrid = {
    x: ballHandlerSprite.gridX || 50,
    y: ballHandlerSprite.gridY || 25
  };
  
  // ✅ DETAILED LOGGING: Track frontend Steal Entry calculation
  console.warn("🏀 [FRONTEND STEAL ENTRY] Entry:", {
    ballHandlerId,
    currentSpritePosition: { x: ballHandlerSprite.gridX, y: ballHandlerSprite.gridY },
    roles: turnData.roles,
    backendOutletX: turnData.roles?.ball_handler_outlet_x,
    backendOutletY: turnData.roles?.ball_handler_outlet_y,
    backendMoveX: turnData.roles?.ball_handler_move_x,
    backendMoveY: turnData.roles?.ball_handler_move_y
  });
  
  // Determine offense team and direction
  const isHomeOffense = ballHandlerSprite.team === "home";
  const direction = isHomeOffense ? 1 : -1; // +1 for home (toward x=90), -1 for away (toward x=10)
  
  // Calculate steal entry movement (matches backend calculation)
  // Backend sends ball_handler_move_x and ball_handler_move_y in turnData.roles
  const moveX = turnData.roles?.ball_handler_move_x || 
                Phaser.Math.Between(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX);
  const moveY = turnData.roles?.ball_handler_move_y || 
                Phaser.Math.Between(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE);
  
  // ✅ FIX: Use backend-provided final coordinates if available (more accurate)
  // Otherwise, calculate from current position
  let targetGrid;
  if (turnData.roles?.ball_handler_outlet_x !== undefined && turnData.roles?.ball_handler_outlet_y !== undefined) {
    // Use backend-calculated final position (for steals, outlet_x/y is the position after steal entry)
    targetGrid = {
      x: turnData.roles.ball_handler_outlet_x,
      y: turnData.roles.ball_handler_outlet_y
    };
    console.warn("🏀 [FRONTEND STEAL ENTRY] Using backend final coordinates:", targetGrid);
  } else {
    // Fallback: Calculate from current position (shouldn't happen if backend is correct)
    targetGrid = {
      x: currentGrid.x + (direction * moveX),
      y: Phaser.Math.Clamp(
        currentGrid.y + moveY,
        STEAL_ENTRY_Y_MIN,
        STEAL_ENTRY_Y_MAX
      )
    };
    console.warn("⚠️ [FRONTEND STEAL ENTRY] Calculated target (backend coords missing):", targetGrid);
  }
  
  console.warn("🏀 [FRONTEND STEAL ENTRY] Movement Details:", {
    startingPosition: currentGrid,
    direction,
    moveX,
    moveY,
    targetPosition: targetGrid,
    calculation: `${currentGrid.x} + (${direction} * ${moveX}) = ${targetGrid.x}`
  });
  
  // Convert to pixel coordinates
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
      reason: 'steal_entry_post_movement'
    });
  }
}

/**
 * Phase 2a: Fast Break Shot Attempt
 * - Ball handler moves near rim
 * - Defender follows
 * - All others move to standard positions
 */
/**
 * Animate Fast Break shot when ball handler beats defender (skill check won)
 * Defender still animates to stopper position, but ball handler animates past them to shot spot
 */
async function animateFastBreakShotWithStopper(scene, turnData, playerSprites, ballSprite, width, height) {
  const shooterId = turnData.roles?.shooter?.player_id || turnData.shooter_id || turnData.roles?.ball_handler?.player_id || getCurrentOwner(scene);
  const shooterSprite = playerSprites[shooterId];
  
  if (!shooterSprite) return;
  
  const isHomeOffense = shooterSprite.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Ball handler moves to shot spot near rim (past the stopper)
  const shotSpot = {
    x: isHomeOffense
      ? basket.x - Phaser.Math.Between(2, 6)  // Home: basket - 2-6
      : basket.x + Phaser.Math.Between(2, 6), // Away: basket + 2-6
    y: basket.y + Phaser.Math.Between(-6, 6)  // ±6 from basket Y
  };
  
  // Clamp to bounds
  shotSpot.x = Phaser.Math.Clamp(shotSpot.x, 4, 97);
  shotSpot.y = Phaser.Math.Clamp(shotSpot.y, 1, 49);
  
  const shotPx = gridToPixels(shotSpot.x, shotSpot.y, width, height);
  
  const promises = [];
  
  // Move shooter (ball handler) past stopper to shot spot
  attachBallToPlayer(scene, ballSprite, shooterSprite);
  const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
  const shooterPromise = tweenPlayerTo(scene, shooterSprite, shotPx, {
    duration: shooterDuration,
    easing: "Linear"
  });
  promises.push(shooterPromise);
  
  // Move stopper to stopper position (between ball handler start and basket)
  const stopperId = turnData.stopper_id;
  const stopperSprite = stopperId ? playerSprites[stopperId] : null;
  let stopperPromise = null;
  
  if (stopperSprite) {
    // Get ball handler's starting position (from roles or current position)
    const ballHandlerStartX = turnData.roles?.ball_handler_outlet_x || shooterSprite.x;
    const ballHandlerStartY = turnData.roles?.ball_handler_outlet_y || shooterSprite.y;
    
    // Convert to grid if needed
    let startGridX, startGridY;
    if (typeof ballHandlerStartX === 'number' && ballHandlerStartX <= 100) {
      // Already in grid coordinates
      startGridX = ballHandlerStartX;
      startGridY = ballHandlerStartY;
    } else {
      // Convert from pixels to grid
      startGridX = (ballHandlerStartX / width) * 100;
      startGridY = 50 - (ballHandlerStartY / height) * 50;
    }
    
    // Stopper position: 1-3 spots in front of ball handler (toward basket)
    const stopperOffset = Phaser.Math.Between(1, 3);
    const stopperSpot = {
      x: isHomeOffense
        ? startGridX + stopperOffset  // Home: +X toward basket (x=90)
        : startGridX - stopperOffset, // Away: -X toward basket (x=10)
      y: startGridY
    };
    
    stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, 4, 97);
    stopperSpot.y = Phaser.Math.Clamp(stopperSpot.y, 1, 49);
    
    const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
    const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
    stopperPromise = tweenPlayerTo(scene, stopperSprite, stopperPx, {
      duration: stopperDuration,
      easing: "Linear"
    });
    promises.push(stopperPromise);
  }
  
  // Move primary defender (if different from stopper)
  let defenderId = turnData.defenderId || turnData.roles?.defender?.player_id;
  if (!defenderId && turnData.roles?.defense && turnData.roles.defense[0]) {
    const defenderData = turnData.roles.defense[0];
    defenderId = typeof defenderData === 'string' ? defenderData : (defenderData.player_id || defenderData.playerId);
  }
  
  const defenderSprite = defenderId && defenderId !== stopperId ? playerSprites[defenderId] : null;
  
  if (defenderSprite) {
    // Defender follows to position behind shooter
    const defenderSpot = {
      x: isHomeOffense
        ? shotSpot.x + 6  // Home: defender is +6 (behind shooter)
        : shotSpot.x - 6, // Away: defender is -6 (behind shooter)
      y: shotSpot.y + Phaser.Math.Between(-2, 2)
    };
    defenderSpot.x = Phaser.Math.Clamp(defenderSpot.x, 4, 97);
    defenderSpot.y = Phaser.Math.Clamp(defenderSpot.y, 1, 49);
    
    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: defenderDuration,
        easing: "Linear"
      })
    );
  }
  
  // Move all other players to standard positions
  const rebounderTweens = await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    shooterId,
    defenderId || stopperId,
    turnData,
    width,
    height,
    promises
  );
  
  // Wait for shooter to reach shot spot
  await shooterPromise;
  
  // Shoot the ball
  safeTransition(scene.stateMachine, States.ShotAttempt);
  
  const adjustedBasket = { ...basket };
  if (turnData.result_type === "MAKE") {
    adjustedBasket.x = isHomeOffense ? basket.x - 1 : basket.x + 1;
  }
  const rimPx = gridToPixels(adjustedBasket.x, adjustedBasket.y, width, height);
  await animateShotToRim(scene, rimPx, {
    duration: 400,
    easing: "Sine.easeInOut",
    arc: { height: 50 }
  });
  
  // Stop rebounder animations when ball hits rim (made shot)
  if (turnData.result_type === "MAKE") {
    rebounderTweens.forEach(tween => {
      if (tween && tween.isPlaying && scene.tweens) {
        scene.tweens.killTweensOf(tween.targets);
      }
    });
  }
  
  // Handle outcome (same as normal shot)
  if (turnData.result_type === "MAKE") {
    // Show announcement with shooter headshot
    const shooterInfo = scene.playerInfo?.[shooterId];
    const shooterTeamId = shooterSprite?.team_id;
    const homeTeamName = scene.simData?.home_team?.name || "Home";
    const awayTeamName = scene.simData?.away_team?.name || "Away";
    const shooterTeamName = shooterTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    
    if (shooterInfo) {
      const shooterPlayerData = {
        playerId: shooterId,
        photo: shooterSprite?.photo || null,
        teamName: shooterTeamName
      };
      showAnnouncement("Fast Break Score!", shooterTeamId === scene.homeTeamId ? "home" : "away", shooterPlayerData);
    }
  } else if (turnData.result_type === "MISS") {
    // Handle MISS → DREB transition
    const rebounderId = turnData.rebounder_id || turnData.roles?.rebounder?.player_id;
    if (rebounderId) {
      await runInboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId,
        nextPlayType: turnData.next_play_type || "HCO",
        turnData: turnData
      });
    }
  }
}

async function animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height) {
  const shooterId = turnData.roles?.shooter?.player_id || turnData.shooter_id || getCurrentOwner(scene);
  const shooterSprite = playerSprites[shooterId];
  
  if (!shooterSprite) return;
  
  const isHomeOffense = shooterSprite.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Ball handler moves to shot spot near rim
  const shotSpot = {
    x: isHomeOffense
      ? basket.x - Phaser.Math.Between(2, 6)  // Home: basket - 2-6
      : basket.x + Phaser.Math.Between(2, 6), // Away: basket + 2-6
    y: basket.y + Phaser.Math.Between(-6, 6)  // ±6 from basket Y
  };
  
  // Clamp to bounds
  shotSpot.x = Phaser.Math.Clamp(shotSpot.x, 4, 97);
  shotSpot.y = Phaser.Math.Clamp(shotSpot.y, 1, 49);
  
  const shotPx = gridToPixels(shotSpot.x, shotSpot.y, width, height);
  
  const promises = [];
  
  // Move shooter
  attachBallToPlayer(scene, ballSprite, shooterSprite);
  // Use distance-based duration for consistent speed
  const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
  // ✅ Store shooter promise separately - we'll wait only for this before shooting
  const shooterPromise = tweenPlayerTo(scene, shooterSprite, shotPx, {
    duration: shooterDuration,
    easing: "Linear" // Match HCO step movements
  });
  promises.push(shooterPromise);
  
  // Move primary defender
  // Check top-level defender field first (from shot_manager), then roles.defense array
  // Use defenderId directly if available, otherwise try to extract from defender object/string
  let defenderId = turnData.defenderId;
  
  if (!defenderId) {
    let defenderData = turnData.defender || (turnData.roles?.defense && turnData.roles.defense[0]);
    if (defenderData) {
      if (typeof defenderData === 'string') {
        defenderId = defenderData;
      } else if (defenderData.player_id) {
        defenderId = defenderData.player_id;
      } else if (defenderData.playerId) {
        defenderId = defenderData.playerId;
      }
    }
  }
  
  const defenderSprite = defenderId ? playerSprites[defenderId] : null;
  
  // console.log("🏀 FB Shot - Defender lookup:", {
  //   defenderId,
  //   hasSprite: !!defenderSprite,
  //   turnDataDefenderId: turnData.defenderId,
  //   turnDataDefender: turnData.defender
  // });
  
  if (defenderSprite) {
    // Defender position: 3 spots closer to basket, ±2 Y from shooter
    const defenderSpot = {
      x: isHomeOffense
        ? shotSpot.x + 3  // Home attacking right (X=91): defender is +3 (toward basket)
        : shotSpot.x - 3, // Away attacking left (X=9): defender is -3 (toward basket)
      y: shotSpot.y + Phaser.Math.Between(-2, 2)  // ±2 Y range from shooter
    };
    defenderSpot.x = Phaser.Math.Clamp(defenderSpot.x, 4, 97);
    defenderSpot.y = Phaser.Math.Clamp(defenderSpot.y, 1, 49);
    
    // console.log("🏀 FB Shot - Defender position:", {
    //   defenderId,
    //   shotSpot,
    //   defenderSpot,
    //   isHomeOffense
    // });
    
    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    // Use distance-based duration for consistent speed
    const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
    // ✅ Defender animates in parallel - we don't wait for it before shooting
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: defenderDuration,
        easing: "Linear" // Match HCO step movements
      })
    );
  } else {
    console.warn("🏀 FB Shot - No defender sprite found!", {
      defenderId,
      turnDataDefenderId: turnData.defenderId,
      turnDataDefender: turnData.defender,
      availableSprites: Object.keys(playerSprites)
    });
  }
  
  // Move all other players to standard positions (same as defensive stop)
  // ✅ Capture rebounder tween references for early termination
  const rebounderTweens = await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    shooterId,
    defenderId,
    turnData,
    width,
    height,
    promises
  );
  
  // ✅ Wait only for shooter to reach basket - shoot immediately when he arrives
  // Defender and rebounders continue animating in parallel
  await shooterPromise;
  
  // Shoot the ball
  safeTransition(scene.stateMachine, States.ShotAttempt);
  
  // ✅ FIX: Adjust rim position for made shots (1 grid unit closer to shooter)
  // This matches the adjustment in ballManager.js and ShotAnimationSystem.js
  // Home team (shoots at x=91): reduce by 1 → 90
  // Away team (shoots at x=9): increase by 1 → 10
  const adjustedBasket = { ...basket };
  if (turnData.result_type === "MAKE") {
    adjustedBasket.x = isHomeOffense ? basket.x - 1 : basket.x + 1;
  }
  const rimPx = gridToPixels(adjustedBasket.x, adjustedBasket.y, width, height);
  // ✅ STEP 3 MIGRATION: Use new animateShotToRim() helper instead of manual detach + animate
  // animateShotToRim() handles ball detachment and shot animation in one call
  // Arc support added for fast break shots
  await animateShotToRim(scene, rimPx, {
    duration: 400,
    easing: "Sine.easeInOut",
    arc: { height: 50 }
  });
  
  // ✅ Stop rebounder animations when ball hits rim (made shot)
  if (turnData.result_type === "MAKE") {
    rebounderTweens.forEach(tween => {
      if (tween && tween.isPlaying && scene.tweens) {
        scene.tweens.killTweensOf(tween.targets);
      }
    });
  }
  
  // Handle outcome
  if (turnData.result_type === "MAKE") {
    // Show announcement with shooter headshot
    const { showAnnouncement } = await import('../utils/announcements.js');
    const shooterInfo = scene.playerInfo?.[shooterId];
    const shooterTeamId = shooterSprite?.team_id;
    
    // Handle both new nested structure (object) and old flat structure (string)
    const homeTeamField = scene.simData?.home_team;
    const awayTeamField = scene.simData?.away_team;
    const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
    const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
    const shooterTeamName = shooterTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    
    const shooterPlayerData = shooterInfo ? {
      playerId: shooterId,
      photo: shooterSprite?.photo || null,
      teamName: shooterTeamName
    } : null;
    
    const teamStyle = isHomeOffense ? 'home' : 'away';
    showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
    
    await new Promise(resolve => scene.time.delayedCall(1000, resolve));
    
    // ✅ OPTION 1 FIX: Ensure onShotEnd() is called before transitioning to inbound pass
    // This ensures ball state is cleared before inbound setup
    const { getBallController } = await import('./BallControllerAdapter.js');
    const ballController = getBallController();
    if (ballController && ballController.isInFlight) {
      ballController.onShotEnd();
    }
    
    // ✅ FIX: Don't call runInboundSetup() here if next_play_type === "BASELINE_INBOUND"
    // The BASELINE_INBOUND turn will handle the inbound setup via AnimationEngine.handleBaselineInbound()
    // Calling it here causes double inbound passes and double setup animations
    if (turnData.next_play_type === "BASELINE_INBOUND") {
      // ✅ REMOVED: runInboundSetup() call - BASELINE_INBOUND turn handles it
      // This prevents double inbound passes and double setup animations
      return;
    }
    
    // Inbound setup (only for non-BASELINE_INBOUND cases)
    const newOffenseSide = isHomeOffense ? "away" : "home";
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
    
    // ✅ SS&S: Possession flip removed from frontend (Fix 2 - Pattern A)
    // Backend now flips possession before creating BASELINE_INBOUND turn
    // Frontend just reads offense_team_id from turnData (handled by universal transition)
    
    await runInboundSetup({ 
      scene, 
      ballSprite, 
      playerSprites, 
      newOffenseSide,
      homeTeamId: scene.simData?.home_team_id,
      awayTeamId: scene.simData?.away_team_id,
      skipRetreat,
      pressureType
    });
  } else {
    // Miss - handle rebound
    appendToTextScroll("Missed!");
    safeTransition(scene.stateMachine, States.Rebound);
    
    const { bounceFromRim, animateRebound } = await import('./ballManager.js');
    const miss = await bounceFromRim(scene, ballSprite, basket, isHomeOffense, 300);
    
    // Find the original MISS turn that led to this Fast Break (for offense_getback list)
    // Also need the current Fast Break MISS turn (for animations)
    const currentIndex = scene.currentTurn || 0;
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    const currentTurn = scene.simData?.turns?.[currentIndex];
    
    // The current turnData is the Fast Break MISS turn - use it for animations
    // The previous HCO MISS turn is needed for offense_getback list
    // runDefensiveReboundSetup will use turnData for animations, and can find offense_getback
    // from the previous turn if needed
    const missTurnForGetback = previousTurn?.result_type === "MISS" ? previousTurn : null;
    
    // ✅ Get rebounderId - must be present for rebound animation
    const rebounderId = turnData.rebounderId || turnData.rebounder_player_id;
    
    if (false) console.log('🏀 [FAST BREAK MISS] Checking rebounderId', {
      rebounderId,
      fromRebounderId: turnData.rebounderId,
      fromRebounderPlayerId: turnData.rebounder_player_id,
      exists: !!rebounderId
    });
    
    if (!rebounderId) {
      console.error('⚠️ [FAST BREAK MISS] Missing rebounderId in turnData, cannot animate rebound', {
        turnDataKeys: Object.keys(turnData),
        hasRebounderId: !!turnData.rebounderId,
        hasRebounderPlayerId: !!turnData.rebounder_player_id,
        fullTurnData: turnData
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    const rebounderSprite = playerSprites[rebounderId];
    
    if (!rebounderSprite) {
      console.error('⚠️ [FAST BREAK MISS] Rebounder sprite not found', {
        rebounderId,
        availableSprites: Object.keys(playerSprites)
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    // ✅ Stop rebounder animations when rebounder grabs ball (missed shot)
    // Monitor rebounder position and stop tweens when rebounder gets close to ball bounce spot
    if (rebounderTweens.length > 0) {
      let monitoringActive = true;
      const ballBouncePx = gridToPixels(miss.grid.x, miss.grid.y, width, height);
      
      const checkRebounderReached = () => {
        if (!monitoringActive) return;
        
        const distanceToBall = Math.hypot(
          rebounderSprite.x - ballBouncePx.x,
          rebounderSprite.y - ballBouncePx.y
        );
        
        // If rebounder is within 30 pixels of ball bounce spot, stop all rebounder animations
        if (distanceToBall < 30) {
          monitoringActive = false;
          rebounderTweens.forEach(tween => {
            if (tween && tween.isPlaying && scene.tweens) {
              scene.tweens.killTweensOf(tween.targets);
            }
          });
          return;
        }
        
        // Continue checking until rebounder reaches ball or all tweens are stopped
        if (monitoringActive && rebounderTweens.some(t => t && t.isPlaying)) {
          scene.time.delayedCall(50, checkRebounderReached);
        } else {
          monitoringActive = false;
        }
      };
      
      // Start monitoring after a short delay to let rebounder start moving
      scene.time.delayedCall(100, checkRebounderReached);
    }
    
    await animateRebound({
      scene,
      ballSprite,
      playerSprites,
      animations: [],
      rebounderId,
      ballSpot: miss.grid,
      shooterId,
      turnData: missTurnForGetback // ✅ FIX: Pass previous HCO MISS turn (has offense_getback) so get-back players can be excluded
    });
    
    // Defensive rebound setup if needed
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId,
        nextPlayType: turnData.next_play_type || "HCO", // Use turnData.next_play_type instead of hardcoded "HCO"
        turnData: turnData // ✅ FIX: Pass current Fast Break MISS turn (has animations), not previous HCO MISS turn
        // runDefensiveReboundSetup will find offense_getback from previous turn if needed
      });
    }
  }
}

/**
 * Phase 2b: Defensive Stop / Foul / Turnover / Steal
 * - Ball handler moves to top of key
 * - Stopper defends ball handler
 * - Other defenders move closer to basket
 * - All other players scatter to half court
 */
async function animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height) {
  
  // ✅ Use backend animation end coords for positioning (matches other transitions like DREB -> HCO)
  // This ensures frontend sprite positions match backend player.coords for accurate distance calculations
  const animations = turnData.animations || [];
  const promises = [];
  
  // ⚠️ CRITICAL CHECK: For DEFENSIVE_STOP, we should NOT use backend animations if they move ball handler toward basket
  // Instead, force ball handler to top of key (defensive stop position)
  const ballHandlerId = turnData.roles?.ball_handler?.player_id || turnData.roles?.ball_handler || getCurrentOwner(scene);
  const ballHandlerSprite = playerSprites[ballHandlerId];
  const isDefensiveStop = turnData.result_type === "DEFENSIVE_STOP" || turnData.fast_break === true;
  let gotoStateTransition = false; // Flag to skip fallback logic if we've already handled positioning
  
  if (animations.length > 0 && isDefensiveStop && ballHandlerSprite) {
    // For defensive stops, check if backend animation would move ball handler toward basket incorrectly
    const ballHandlerAnim = animations.find(a => a.playerId === ballHandlerId);
    if (ballHandlerAnim && ballHandlerAnim.movement && ballHandlerAnim.movement.length >= 2) {
      const endStep = ballHandlerAnim.movement[ballHandlerAnim.movement.length - 1];
      const startStep = ballHandlerAnim.movement[0];
      
      if (endStep?.coords && startStep?.coords) {
        const ballHandlerSprite = playerSprites[ballHandlerId];
        const isHomeOffense = ballHandlerSprite?.team === "home";
        const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
        const topKey = isHomeOffense ? HOME_TOP_KEY : AWAY_TOP_KEY;
        
        // Check if end coords are closer to basket than top of key (indicating incorrect animation)
        const distanceToBasket = Math.abs(endStep.coords.x - basket.x);
        const distanceToTopKey = Math.abs(endStep.coords.x - topKey.x);
        
        // For away offense, coordinates in animation data are in HOME orientation
        // Flip them for display to match what the user sees
        let displayStartCoords = startStep.coords;
        let displayEndCoords = endStep.coords;
        if (!isHomeOffense) {
          // Away offense: flip coordinates for display
          displayStartCoords = { x: 100 - startStep.coords.x, y: startStep.coords.y };
          displayEndCoords = { x: 100 - endStep.coords.x, y: endStep.coords.y };
        }
        
        // ✅ REMOVED: Defensive stop animation check logging (cluttering console)
        
        if (distanceToBasket < distanceToTopKey) {
          // Backend animation incorrectly moves ball handler toward basket - use manual positioning instead
          console.warn("⚠️ Defensive Stop - Backend animation moves ball handler toward basket! Using manual positioning instead.");
          
          // Skip backend animations for ball handler, but use them for other players
          for (const anim of animations) {
            const sprite = playerSprites[anim.playerId];
            if (!sprite || !anim.movement || anim.movement.length < 2) continue;
            
            // Skip ball handler - we'll position manually to top of key
            if (anim.playerId === ballHandlerId) continue;
            
            const endStep = anim.movement[anim.movement.length - 1];
            if (!endStep || !endStep.coords) continue;
            
            const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
            const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
            
            promises.push(
              tweenPlayerTo(scene, sprite, endPixels, {
                duration,
                easing: "Linear"
              })
            );
          }
          
          // Manually position ball handler to top of key (override incorrect backend animation)
          attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
          const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
          const handlerDuration = getPlayerDuration(ballHandlerSprite, topKeyPx.x, topKeyPx.y);
          promises.push(
            tweenPlayerTo(scene, ballHandlerSprite, topKeyPx, {
              duration: handlerDuration,
              easing: "Linear"
            })
          );
          
          // Move stopper (if exists)
          const stopperId = turnData.stopper_id;
          const stopperSprite = stopperId ? playerSprites[stopperId] : null;
          if (stopperSprite) {
            const stopperSpot = {
              x: isHomeOffense ? topKey.x + 2 : topKey.x - 2,
              y: topKey.y
            };
            stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, 4, 97);
            const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
            const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
            promises.push(
              tweenPlayerTo(scene, stopperSprite, stopperPx, {
                duration: stopperDuration,
                easing: "Linear"
              })
            );
          }
          
          // Move other players to standard positions
          // ✅ Capture rebounder tween references for early termination
          const rebounderTweens = await moveOtherPlayersToStandardPositions(
            scene,
            playerSprites,
            ballHandlerId,
            turnData.stopper_id,
            turnData,
            width,
            height,
            promises
          );
          
          // ✅ Track ball handler and stopper promises for early termination
          const ballHandlerPromise = promises[promises.length - rebounderTweens.length - (stopperSprite ? 2 : 1)];
          const stopperPromise = stopperSprite ? promises[promises.length - rebounderTweens.length - 1] : null;
          
          // ✅ Stop rebounder animations when both ball handler and stopper reach their spots
          let handlerComplete = false;
          let stopperComplete = !stopperSprite; // If no stopper, consider it "complete"
          
          const checkAndStopRebounders = () => {
            if (handlerComplete && stopperComplete) {
              rebounderTweens.forEach(tween => {
                if (tween && tween.isPlaying && scene.tweens) {
                  scene.tweens.killTweensOf(tween.targets);
                }
              });
            }
          };
          
          // Set up completion handlers
          if (ballHandlerPromise && typeof ballHandlerPromise.then === 'function') {
            ballHandlerPromise.then(() => {
              handlerComplete = true;
              checkAndStopRebounders();
            });
          } else {
            handlerComplete = true;
            checkAndStopRebounders();
          }
          
          if (stopperPromise && typeof stopperPromise.then === 'function') {
            stopperPromise.then(() => {
              stopperComplete = true;
              checkAndStopRebounders();
            });
          } else if (stopperSprite) {
            stopperComplete = true;
            checkAndStopRebounders();
          }
          
          // Wait for all animations to complete (rebounders will stop early)
          await Promise.all(promises);
          // Skip to announcement/state transition (avoid fallback logic)
          gotoStateTransition = true;
        } else {
          // Backend animation looks correct (top of key or neutral) - use it
          // ✅ REMOVED: Defensive stop backend animations logging (cluttering console)
          
          for (const anim of animations) {
            const sprite = playerSprites[anim.playerId];
            if (!sprite || !anim.movement || anim.movement.length < 2) continue;
            
            const endStep = anim.movement[anim.movement.length - 1];
            if (!endStep || !endStep.coords) continue;
            
            const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
            const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
            
            const hasBall = anim.hasBallAtStep?.[anim.movement.length - 1] || false;
            if (hasBall) {
              attachBallToPlayer(scene, ballSprite, sprite);
            }
            
            promises.push(
              tweenPlayerTo(scene, sprite, endPixels, {
                duration,
                easing: "Linear"
              })
            );
          }
        }
      } else {
        // No valid animation coords - fall through to manual positioning
        console.warn("⚠️ Defensive Stop - Invalid animation coords, using manual positioning");
      }
    } else {
      // No ball handler animation found - fall through to manual positioning
      console.warn("⚠️ Defensive Stop - No ball handler animation found, using manual positioning");
    }
  } else if (animations.length > 0 && !isDefensiveStop) {
    // Not a defensive stop - use backend animations as normal
    // ✅ REMOVED: Using backend animations logging (cluttering console)
    for (const anim of animations) {
      const sprite = playerSprites[anim.playerId];
      if (!sprite || !anim.movement || anim.movement.length < 2) continue;
      
      const endStep = anim.movement[anim.movement.length - 1];
      if (!endStep || !endStep.coords) continue;
      
      const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
      const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
      
      const hasBall = anim.hasBallAtStep?.[anim.movement.length - 1] || false;
      if (hasBall) {
        attachBallToPlayer(scene, ballSprite, sprite);
      }
      
      promises.push(
        tweenPlayerTo(scene, sprite, endPixels, {
          duration,
          easing: "Linear"
        })
      );
    }
  }
  
  // Manual positioning fallback (if animations are missing or incorrect)
  if (!gotoStateTransition && promises.length === 0 && (animations.length === 0 || isDefensiveStop)) {
    // Fallback to manual positioning if animations are missing or incorrect (backwards compatibility)
    
    const ballHandlerData = turnData.roles?.ball_handler;
    const ballHandlerId = ballHandlerData?.player_id || ballHandlerData || getCurrentOwner(scene);
    const ballHandlerSprite = playerSprites[ballHandlerId];
    
    if (!ballHandlerSprite) {
      console.error("❌ animateDefensiveStop - EARLY RETURN: ballHandlerSprite not found!", {
        ballHandlerId,
        availableIds: Object.keys(playerSprites),
        ballHandlerData,
        fallbackOwner: getCurrentOwner(scene)
      });
      return;
    }
    
    const isHomeOffense = ballHandlerSprite.team === "home";
    const topKey = isHomeOffense ? HOME_TOP_KEY : AWAY_TOP_KEY;
    
    // Move ball handler to top of key
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
    const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
    const handlerDuration = getPlayerDuration(ballHandlerSprite, topKeyPx.x, topKeyPx.y);
    const ballHandlerPromise = tweenPlayerTo(scene, ballHandlerSprite, topKeyPx, {
      duration: handlerDuration,
      easing: "Linear"
    });
    promises.push(ballHandlerPromise);
    
    // Move stopper (if exists)
    const stopperId = turnData.stopper_id;
    const stopperSprite = stopperId ? playerSprites[stopperId] : null;
    let stopperPromise = null;
    
    if (stopperSprite) {
      // ✅ Position stopper DIRECTLY in front of ball handler (between ball handler and basket they're defending)
      // Home offense (attacking right): stopper x GREATER than ball handler (toward basket)
      // Away offense (attacking left): stopper x LESS than ball handler (toward basket)
      const stopperSpot = {
        x: isHomeOffense ? topKey.x + 2 : topKey.x - 2,  // 2 spots in front, directly between ball handler and basket
        y: topKey.y  // Same Y as ball handler (directly in front)
      };
      stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, 4, 97);
      
      const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
      const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
      stopperPromise = tweenPlayerTo(scene, stopperSprite, stopperPx, {
        duration: stopperDuration,
        easing: "Linear"
      });
      promises.push(stopperPromise);
    }
    
    // Move other defenders and non-involved players
    // ✅ Capture rebounder tween references for early termination
    const rebounderTweens = await moveOtherPlayersToStandardPositions(
      scene,
      playerSprites,
      ballHandlerId,
      stopperId,
      turnData,
      width,
      height,
      promises
    );
    
    // ✅ Stop rebounder animations when both ball handler and stopper reach their spots
    let handlerComplete = false;
    let stopperComplete = !stopperSprite; // If no stopper, consider it "complete"
    
    const checkAndStopRebounders = () => {
      if (handlerComplete && stopperComplete) {
        rebounderTweens.forEach(tween => {
          if (tween && tween.isPlaying && scene.tweens) {
            scene.tweens.killTweensOf(tween.targets);
          }
        });
      }
    };
    
    // Set up completion handlers
    if (ballHandlerPromise && typeof ballHandlerPromise.then === 'function') {
      ballHandlerPromise.then(() => {
        handlerComplete = true;
        checkAndStopRebounders();
      });
    } else {
      handlerComplete = true;
      checkAndStopRebounders();
    }
    
    if (stopperPromise && typeof stopperPromise.then === 'function') {
      stopperPromise.then(() => {
        stopperComplete = true;
        checkAndStopRebounders();
      });
    } else if (stopperSprite) {
      stopperComplete = true;
      checkAndStopRebounders();
    }
  }
  
  // Only wait for promises if we haven't already awaited them (manual positioning case)
  if (!gotoStateTransition) {
    await Promise.all(promises);
  }
  
  // ✅ Show "Great Stop!" announcement with stopper headshot (for Fast Break defensive stops)
  if (turnData.fast_break === true && turnData.stopper_id) {
    const stopperId = turnData.stopper_id;
    const stopperSprite = playerSprites[stopperId];
    
    if (stopperSprite) {
      const { showAnnouncement } = await import('../utils/announcements.js');
      const stopperInfo = scene.playerInfo?.[stopperId];
      const stopperTeamId = stopperSprite?.team_id;
      
      // Handle both new nested structure (object) and old flat structure (string)
      const homeTeamField = scene.simData?.home_team;
      const awayTeamField = scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const stopperTeamName = stopperTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
      
      // Determine offense side for defense team calculation
      const ballHandlerData = turnData.roles?.ball_handler;
      const ballHandlerId = ballHandlerData?.player_id || ballHandlerData || getCurrentOwner(scene);
      const ballHandlerSprite = playerSprites[ballHandlerId];
      const isHomeOffense = ballHandlerSprite?.team === "home";
      
      const stopperPlayerData = stopperInfo ? {
        playerId: stopperId,
        photo: stopperSprite?.photo || null,
        teamName: stopperTeamName
      } : null;
      
      // Defensive stop: show in defense team color (they benefited)
      const defenseTeam = isHomeOffense ? 'away' : 'home';
      showAnnouncement("Great Stop!", defenseTeam, stopperPlayerData);
      
      await new Promise(resolve => scene.time.delayedCall(1000, resolve));
    }
  } else {
    // Display outcome text for non-Fast Break stops
    if (turnData.hold_up) {
      appendToTextScroll("Defensive stop!");
    }
  }
  
  // Transition to HalfCourt for next possession
  // This is critical - if we don't transition, playTurnAnimation will return early
  // because it checks if state is FastBreak and skips animation
  const currentState = scene.stateMachine?.state;
  if (currentState !== States.HalfCourt) {
    safeTransition(scene.stateMachine, States.HalfCourt);
    
    // Verify transition succeeded
    const newState = scene.stateMachine?.state;
    if (newState !== States.HalfCourt) {
      console.error("❌ Fast Break Defensive Stop - State transition FAILED:", {
        expected: States.HalfCourt,
        actual: newState,
        current_state: currentState
      });
    }
  }
  
  // ✅ Ensure HCO setup is triggered after defensive stop transitions to HCO
  // This ensures players are properly positioned for the next HCO turn
  if (turnData.next_play_type === "HCO") {
    if (typeof scene.startNextHalfCourtOffense === "function") {
      scene.startNextHalfCourtOffense();
    }
  }
}

/**
 * Animate rebounders (players who stayed near rim for shot attempt) to their target positions
 * - Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
 * - Shot Attempt: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
 * 
 * @param {Phaser.Scene} scene - Phaser scene
 * @param {Object} playerSprites - Dictionary of player sprites
 * @param {string} ballHandlerId - ID of ball handler (to skip)
 * @param {string} primaryDefenderId - ID of primary defender (to skip)
 * @param {Object} turnData - Turn data with result_type and roles
 * @param {number} width - Scene width
 * @param {number} height - Scene height
 * @param {Set} getbackPlayerIdsSet - Set of get-back player IDs (to skip)
 * @param {Set} releasePlayerIdsSet - Set of release player IDs (to skip)
 * @param {string} outletPasserId - ID of outlet passer (to skip)
 * @returns {Array} Array of tween references for rebounder animations (for early termination)
 */
function animateRebounders(
  scene,
  playerSprites,
  ballHandlerId,
  primaryDefenderId,
  turnData,
  width,
  height,
  getbackPlayerIdsSet,
  releasePlayerIdsSet,
  outletPasserId
) {
  const rebounderTweens = [];
  const isDefensiveStop = turnData.result_type === "DEFENSIVE_STOP";
  
  // Determine which basket is being attacked
  const shooterSprite = playerSprites[ballHandlerId];
  const isHomeOffense = shooterSprite?.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Convert sprite positions to grid for starting y calculation
  const pixelsToGrid = (pixelX, pixelY) => {
    const gridX = (pixelX / width) * 100;
    const gridY = 50 - (pixelY / height) * 50;
    return { x: gridX, y: gridY };
  };
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    // Skip shooter, primary defender, outlet passer, get-back players, and release players
    if (
      id === ballHandlerId ||
      id === primaryDefenderId ||
      id === outletPasserId ||
      getbackPlayerIdsSet.has(id) ||
      releasePlayerIdsSet.has(id)
    ) {
      continue;
    }
    
    // ✅ This is a rebounder (stayed near rim for shot attempt)
    // Get starting y coordinate from current sprite position
    const startingGrid = pixelsToGrid(sprite.x, sprite.y);
    const startingY = startingGrid.y;
    
    let targetSpot;
    
    if (isDefensiveStop) {
      // ✅ Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
      targetSpot = {
        x: Phaser.Math.Between(REBOUNDER_X_MIN, REBOUNDER_X_MAX),
        y: Phaser.Math.Clamp(startingY + Phaser.Math.Between(-REBOUNDER_Y_RANGE, REBOUNDER_Y_RANGE), 1, 49)
      };
    } else {
      // ✅ Shot Attempt: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
      // Home basket (x=91): 5-20 spots less = 71-86
      // Away basket (x=9): 5-20 spots more = 14-29
      const distanceFromBasket = Phaser.Math.Between(5, 20);
      const targetX = isHomeOffense 
        ? basket.x - distanceFromBasket  // Home: move left (toward center court)
        : basket.x + distanceFromBasket;  // Away: move right (toward center court)
      
      targetSpot = {
        x: Phaser.Math.Clamp(targetX, 4, 97), // Clamp to court bounds
        y: Phaser.Math.Clamp(basket.y + Phaser.Math.Between(-SHOT_ATTEMPT_REBOUNDER_Y_RANGE, SHOT_ATTEMPT_REBOUNDER_Y_RANGE), 1, 49)
      };
    }
    
    const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
    // ✅ Use distance-based duration for consistent speed
    // Players will stop at their current position if shot happens before they reach their spot
    // (Made shot: stops when ball hits rim; Missed shot: stops when rebounder grabs ball)
    const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
    
    // ✅ Create tween directly (not using tweenPlayerTo) so we can store reference for early termination
    const tween = scene.tweens.add({
      targets: sprite,
      x: targetPx.x,
      y: targetPx.y,
      duration: playerDuration,
      ease: "Linear",
      onComplete: () => {
        // Tween completed naturally (player reached destination)
      }
    });
    rebounderTweens.push(tween);
  }
  
  return rebounderTweens;
}

/**
 * Helper: Move all non-involved players to their positions
 * - Outlet passer: moves forward 7 x-coords toward basket (+7 for home offense, -7 for away offense)
 * - Get-back players: chase toward basket (X: 50 to basket-15, Y: 15-35)
 * - Rebounders: handled by animateRebounders() function
 * - Distance-based animation - stops when ball hits rim (made) or rebounder grabs ball (missed)
 * - Rebounders stop early when defensive stop is made (ball handler and stopper reach their spots)
 * 
 * @returns {Array} Array of tween references for rebounder animations (for early termination)
 */
async function moveOtherPlayersToStandardPositions(
  scene,
  playerSprites,
  ballHandlerId,
  primaryDefenderId,
  turnData,
  width,
  height,
  promises
) {
  // ✅ Find the most recent MISS/MAKE turn to get get-back and release player lists
  let getbackPlayerIds = [];
  let releasePlayerIds = [];
  const currentIndex = scene.currentTurn || 0;
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  const currentTurn = scene.simData?.turns?.[currentIndex];
  
  if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "MAKE") {
    getbackPlayerIds = previousTurn?.offense_getback || [];
    releasePlayerIds = previousTurn?.defense_release || [];
  } else if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "MAKE") {
    getbackPlayerIds = currentTurn?.offense_getback || [];
    releasePlayerIds = currentTurn?.defense_release || [];
  }
  
  const getbackPlayerIdsSet = new Set(getbackPlayerIds);
  const releasePlayerIdsSet = new Set(releasePlayerIds);
  
  // ✅ Get outlet passer ID - they move forward 7 x-coords toward basket
  const outletPasserId = turnData.roles?.outlet_passer;
  
  // Determine which basket is being attacked and if this is a defensive stop or shot attempt
  const shooterSprite = playerSprites[ballHandlerId];
  const isHomeOffense = shooterSprite?.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const isDefensiveStop = turnData.result_type === "DEFENSIVE_STOP";
  
  // Convert sprite positions to grid for starting y calculation
  const pixelsToGrid = (pixelX, pixelY) => {
    const gridX = (pixelX / width) * 100;
    const gridY = 50 - (pixelY / height) * 50;
    return { x: gridX, y: gridY };
  };
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    // Skip shooter and primary defender (already animated)
    if (id === ballHandlerId || id === primaryDefenderId) {
      continue;
    }
    
    // ✅ Outlet passer moves forward 7 x-coords toward basket
    if (id === outletPasserId) {
      const passerCurrentGrid = pixelsToGrid(sprite.x, sprite.y);
      const passerTargetX = isHomeOffense 
        ? Phaser.Math.Clamp(passerCurrentGrid.x + OUTLET_PASSER_MOVE_X, 4, 97)  // Home: +7 (toward x=90)
        : Phaser.Math.Clamp(passerCurrentGrid.x - OUTLET_PASSER_MOVE_X, 4, 97); // Away: -7 (toward x=10)
      
      const targetSpot = {
        x: passerTargetX,
        y: passerCurrentGrid.y  // Keep same y-coord
      };
      
      const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
      const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
      
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: playerDuration,
          easing: "Linear"
        })
      );
      continue;
    }
    
    // ✅ Skip release players (they're the ball handler, already animated)
    if (releasePlayerIdsSet.has(id)) {
      continue;
    }
    
    // ✅ Only animate get-back players as defenders (not all players in defense list)
    // Rebounders are handled separately by animateRebounders() function
    if (getbackPlayerIdsSet.has(id)) {
      // Get-back defenders chase: X between 50 and 15 spots closer to basket
      const minX = isHomeOffense ? 50 : basket.x + 2;
      const maxX = isHomeOffense ? basket.x - 2 : 50;
      
      const targetSpot = {
        x: Phaser.Math.Between(Math.min(minX, maxX), Math.max(minX, maxX)),
        y: Phaser.Math.Between(15, 35)
      };
      
      const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
      const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
      
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: playerDuration,
          easing: "Linear"
        })
      );
    }
    // Note: Rebounders are handled by animateRebounders() function (called after this loop)
  }
  
  // ✅ Animate rebounders using extracted function
  const rebounderTweens = animateRebounders(
    scene,
    playerSprites,
    ballHandlerId,
    primaryDefenderId,
    turnData,
    width,
    height,
    getbackPlayerIdsSet,
    releasePlayerIdsSet,
    outletPasserId
  );
  
  // Add rebounder tween promises for awaiting
  rebounderTweens.forEach(tween => {
    promises.push(
      new Promise((resolve) => {
        tween.once('complete', resolve);
        tween.once('stop', resolve);
      })
    );
  });
  
  return rebounderTweens; // Return tween references for early termination
}

// Export for backwards compatibility
export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
