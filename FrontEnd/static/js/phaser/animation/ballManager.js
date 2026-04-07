import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { generateBallTween } from "./generateBallTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { runInboundSetup as baseRunInboundSetup } from "./turnAnimation.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import {
  detachBall,
  runPass as baseRunPass,
  tweenPlayerTo,
} from "./ballTween.js";
// ✅ STEP 3 MIGRATION: Import new ball animation functions
import { animateShotToRim, animateBallToPosition } from "./ballAnimationSimple.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { States, getDebugTransitions, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import gameStore from "../../state/gameStore.js";
import {
  clearCurrentOwner,
  cancelBallTween,
  getCurrentOwner,
  getPendingOwner,
  setPendingOwner,
} from "./BallControllerAdapter.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import { CLAMP_BOUNDS } from "./courtClamp.js";

/**
 * ✅ PHASE 3.3: Removed wrapper function
 * Now using attachBallToPlayer directly from BallControllerAdapter.js
 * BallControllerAdapter already handles:
 * - possessionFlipInProgress checks
 * - rebound state restrictions
 * - currentBallOwnerRef updates
 * - debug logging
 */

function runInboundSetup(opts) {
  const scene = opts.scene;
  if (scene.possessionFlipInProgress || scene.stateMachine?.is(States.FastBreak)) return Promise.resolve();
  return baseRunInboundSetup(opts);
}

function runPass(scene, cfg = {}) {
  const debugEnabled = isAnimationDebugEnabled();

  // Debug logging for kickout passes
  if (debugEnabled && cfg.fromId && cfg.toId) {
    animationDebugLog('runPass called for kickout:', {
      fromId: cfg.fromId,
      toId: cfg.toId,
      currentState: scene.stateMachine?.state,
      possessionFlipInProgress: scene.possessionFlipInProgress,
      isFastBreak: scene.stateMachine?.is(States.FastBreak)
    });
  }

  // Allow kickout passes even during possession flip
  const isKickoutPass = cfg.fromId && cfg.toId;

  if ((scene.possessionFlipInProgress && !isKickoutPass) || scene.stateMachine?.is(States.FastBreak)) {
    if (debugEnabled) {
      animationDebugWarn('runPass blocked:', {
        reason: scene.possessionFlipInProgress ? 'possessionFlipInProgress' : 'FastBreak state',
        isKickoutPass
      });
    }
    return Promise.resolve();
  }

  if (debugEnabled) {
    animationDebugLog('runPass proceeding with baseRunPass');
  }
  return baseRunPass(scene, cfg);
}

// ✅ STEP 3 MIGRATION: Removed tweenBallTo from exports (now using animateBallToPosition/animateShotToRim)
export { attachBallToPlayer, detachBall, runPass, runInboundSetup };

// Debug flags for logging shot / rebound details
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export const INBOUND_DEBUG = false;



/**
 * Animate the ball flying from one point to another.
 */
export async function passBall({
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  fromTimestamp,
  toTimestamp
}) {
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  await generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: fromTimestamp,
    endTimestamp: toTimestamp,
    type: 'pass'
  });
}

// Baseline inbound pass from one coordinate to another
export async function animateInboundPass(
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  startTs,
  endTs
) {
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  await generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: startTs,
    endTimestamp: endTs,
    type: 'inbound'
  });
}

/**
 * Hide the ball (e.g. post-shot, end of play)
 */
export function hideBall(ballSprite) {
  if (ballSprite) ballSprite.setVisible(false);
}

/**
 * Bounce a missed shot off the rim to a landing spot.
 * Resolves with the grid coordinates of the landing spot.
 */
/**
 * Bounce ball from rim (migrated to new system - Step 3)
 * 
 * For missed shots, animates the ball bouncing from the rim toward the center of the court.
 * Uses animateBallToPosition() with Sine.easeOut easing for realistic bounce effect.
 */
export async function bounceFromRim(
  scene,
  ballSprite,
  rimCoords,
  isHomeTeam,
  duration
) {
  const rebCfg = animationConfig.rebound;
  
  // For missed shots, ball should bounce toward the center of the court
  // Away basket (x=11): bounce right (increase x)
  // Home basket (x=89): bounce left (decrease x)
  const bounceGridX = rimCoords.x > 50 // Home basket
    ? rimCoords.x - rebCfg.bounceArea.x  // Bounce left toward center
    : rimCoords.x + rebCfg.bounceArea.x; // Bounce right toward center
    
  const bounceGridY =
    rimCoords.y + Phaser.Math.Between(-rebCfg.bounceArea.y, rebCfg.bounceArea.y);
    
  // Ensure bounce stays in bounds
  const clampedBounceX = Phaser.Math.Clamp(
    bounceGridX,
    CLAMP_BOUNDS.minX,
    CLAMP_BOUNDS.maxX
  );
  const clampedBounceY = Phaser.Math.Clamp(bounceGridY, 1, 50);
  
  const bounce = gridToPixels(
    clampedBounceX,
    clampedBounceY,
    scene.game.config.width,
    scene.game.config.height
  );
  
  // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of direct scene.tweens.add()
  // Preserve Sine.easeOut easing for realistic bounce effect
  await animateBallToPosition(scene, bounce, {
    duration,
    easing: "Sine.easeOut"
  });
  
  // Return grid coordinates for rebound logic
  return { grid: { x: clampedBounceX, y: clampedBounceY } };
}

/**
 * Launches a shot toward the rim along a single tweened path.
 * Resolves after the ball reaches the rim.
*/
export async function shootBall({
  scene,
  ballSprite,
  fromCoords,
  startTimestamp,
  result,
  shooterPos,
  shooterId,
  shooterTeamId,
  homeTeamId,
  stepIndex,
  turnIndex,
  turnData = null
}) {
  if (!scene || !ballSprite) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);
  
  // CRITICAL: Stop BallController from following player during shot animation
  // Without this, the ball will be repositioned to player's position every frame,
  // overriding the tween and making the shot appear as a teleport
  // console.log('🏀 shootBall: Attempting to stop BallController', {
  //   hasBallController: !!scene.ballController,
  //   hasStopMethod: !!(scene.ballController && typeof scene.ballController.stopFollowingPlayer === 'function'),
  //   currentIsAttached: scene.ballController?.isAttached,
  //   shotInProgress: scene._shotInProgress
  // });
  
  // ✅ PHASE 2.3: Use BallController lifecycle methods instead of direct flag manipulation
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
  
  // Use BallController lifecycle method for shot start
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  if (ballController) {
    // Use lifecycle method to manage shot state
    ballController.onShotStart({ 
      shooterId, 
      isPutback: turnData?.result_type === 'PUTBACK_MAKE' || turnData?.result_type === 'PUTBACK_MISS' 
    });
  }
  
  // ✅ PHASE 4: Removed old _shotInProgress flag - BallController manages state internally
  // BallController lifecycle methods (onShotStart/onShotEnd) handle state management
  const stateMachine = scene.stateMachine;
  if (stateMachine) {
    const prevState = stateMachine.state;
    const alreadyInShotAttempt = stateMachine.is(States.ShotAttempt);
    const legalState =
      alreadyInShotAttempt ||
      stateMachine.is(States.HalfCourt) ||
      stateMachine.is(States.Rebound) ||
      stateMachine.is(States.FastBreak) ||
      stateMachine.is(States.Inbound);
    if (alreadyInShotAttempt) {
      if (isAnimationDebugEnabled()) {
        animationDebugLog("shotBall: already in ShotAttempt", {
          prevState,
          shooterId,
          stepIndex,
        });
      }
    } else if (legalState) {
      safeTransition(
        stateMachine,
        States.ShotAttempt,
        {
          stepIndex,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    } else {
      console.warn("shotBall: illegal state", {
        prevState,
        shooterId,
        stepIndex
      });
    }
  }
  const homeRoster = gameStore.getHomeRoster();
  const storeHomeId =
    homeRoster?.team_id || homeRoster?.teamId || homeRoster?.team_name || homeRoster?.team;
  const effectiveHomeId = homeTeamId ?? storeHomeId;
  const isHomeTeam = String(shooterTeamId) === String(effectiveHomeId);

  const start = gridToPixels(
    fromCoords.x,
    fromCoords.y,
    scene.game.config.width,
    scene.game.config.height
  );
  
  // console.log('🏀 shootBall: gridToPixels conversion', {
  //   inputGridCoords: fromCoords,
  //   outputPixelCoords: start,
  //   canvasSize: { w: scene.game.config.width, h: scene.game.config.height }
  // });
  
  const rimCoords = isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Check for double team and show announcement (before shot animation)
  if (turnData?.has_double_team || turnData?.second_defender_id) {
    // Import and show announcement immediately
    const { showAnnouncement } = await import('../utils/announcements.js');
    // Show "DOUBLE TEAM!" in red text with no player images
    showAnnouncement("DOUBLE TEAM!", 'neutral', null);
  }
  
  // Adjust landing position for made shots
  // Home team (attacks away basket x=91): reduce by 1 → 90
  // Away team (attacks home basket x=9): increase by 1 → 10
  const adjustedRimCoords = { ...rimCoords };
  if (result === "MAKE") {
    adjustedRimCoords.x = isHomeTeam ? rimCoords.x - 1 : rimCoords.x + 1;
  }
  
  const rim = gridToPixels(
    adjustedRimCoords.x,
    adjustedRimCoords.y,
    scene.game.config.width,
    scene.game.config.height
  );

  // Scale the flight duration based on shot distance for more natural pacing
  const baseDuration = 700; // minimum duration in ms
  const shotDistance = Phaser.Math.Distance.Between(start.x, start.y, rim.x, rim.y);
  const duration = Math.max(baseDuration, shotDistance * 3); // 3ms per pixel

  // Create a position tracker to catch any unexpected repositioning
  let lastLoggedX = start.x;
  let lastLoggedY = start.y;
  let watcherRemoved = false;
  const positionWatcher = () => {
    if (watcherRemoved) return;
    const deltaX = Math.abs(ballSprite.x - lastLoggedX);
    const deltaY = Math.abs(ballSprite.y - lastLoggedY);
    if (deltaX > 30 || deltaY > 30) {  // Lowered threshold to catch smaller jumps
      console.warn('🚨 BALL TELEPORT DETECTED!', {
        from: { x: lastLoggedX.toFixed(0), y: lastLoggedY.toFixed(0) },
        to: { x: ballSprite.x.toFixed(0), y: ballSprite.y.toFixed(0) },
        delta: { x: deltaX.toFixed(0), y: deltaY.toFixed(0) },
        timestamp: Date.now()
      });
      // Log what player is at this position
      const playersNearby = Object.values(scene.playerSprites || {}).filter(p => {
        const dist = Math.hypot(p.x - ballSprite.x, p.y - ballSprite.y);
        return dist < 50;
      });
      console.log('🔍 Players near ball teleport position:', playersNearby.map(p => ({
        id: p.playerId,
        pos: { x: p.x.toFixed(0), y: p.y.toFixed(0) },
        distance: Math.hypot(p.x - ballSprite.x, p.y - ballSprite.y).toFixed(0)
      })));
    }
    lastLoggedX = ballSprite.x;
    lastLoggedY = ballSprite.y;
  };
  scene.events.on('update', positionWatcher);
  
  ballSprite.setPosition(start.x, start.y);
  ballSprite.setVisible(true);
  
  // console.log('🏀 shootBall: Ball positioned and visible', {
  //   position: { x: start.x, y: start.y },
  //   visible: ballSprite.visible,
  //   rimTarget: rim,
  //   duration,
  //   result
  // });

  if (SHOT_DEBUG) {
    const endTs = startTimestamp + duration;
    const outcomeSource = result ? "explicit" : "inferred";
    console.log(
      `[shot] shooter=${shooterId} team=${shooterTeamId} ` +
        `(matches home? ${isHomeTeam}) ` +
        `pos=${shooterPos} start=(${start.x},${start.y}) ` +
        `rim=(${rim.x},${rim.y}) ` +
        `step=${stepIndex ?? "?"} turn=${turnIndex ?? "?"} ` +
        `ts=${startTimestamp}->${endTs} outcome=${result || "UNKNOWN"} source=${outcomeSource}`
    );
  }
  
  // console.log('🏀 shootBall: Creating tween for ball flight');

  const tweenStartTime = Date.now();
  
  return new Promise(async (resolve) => {
    
    // ==================== ANIMATE PLAYERS DURING SHOT ====================
    // Defenders releasing for fast break + Offensive players getting back on defense
    if (turnData) {
      
      // Defenders releasing for fast break
      if (turnData.defense_release && turnData.defense_release.length > 0) {
        turnData.defense_release.forEach(playerId => {
          const sprite = scene.playerSprites[playerId];
          if (sprite) {
            const targetY = Phaser.Math.Between(15, 35);
            const targetX = Phaser.Math.Between(45, 55);
            const targetPixel = gridToPixels(targetX, targetY, scene.game.config.width, scene.game.config.height);
            
            scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: duration, // Same duration as ball flight
              ease: 'Power1'
            });
          } else {
            console.warn(`🏃 ⚠️ Defender sprite not found for player ${playerId}`);
          }
        });
      }
      
      // Offensive players getting back on defense
      if (turnData.offense_getback && turnData.offense_getback.length > 0) {
        turnData.offense_getback.forEach(playerId => {
          const sprite = scene.playerSprites[playerId];
          if (sprite) {
            // ✅ SS&S: Use stored coordinates from backend (single source of truth)
            let targetX, targetY;
            if (turnData.offense_getback_coords && turnData.offense_getback_coords[playerId]) {
              // Use stored coordinates from backend
              const storedCoords = turnData.offense_getback_coords[playerId];
              targetX = storedCoords.x;
              targetY = storedCoords.y;
            } else {
              // Fallback: Use safe defaults if backend coordinates missing (shouldn't happen)
              console.error('⚠️ [OFFENSE GET BACK] Missing backend coordinates in ballManager, using safe defaults', {
                playerId,
                hasOffenseGetbackCoords: !!turnData.offense_getback_coords
              });
              targetX = 50; // Safe default: center court
              targetY = 25; // Safe default: mid-court
            }
            
            const targetPixel = gridToPixels(targetX, targetY, scene.game.config.width, scene.game.config.height);
            
            scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: duration, // Same duration as ball flight
              ease: 'Power1'
            });
          } else {
            console.warn(`🏃 ⚠️ Offensive sprite not found for player ${playerId}`);
          }
        });
      }
      
      // ==================== REBOUND POSITIONING ====================
      // Note: Rebounder animation is now handled in ShotAnimationSystem.js
      // This section is kept for backward compatibility but is not actively used
      // ==================== END REBOUND POSITIONING ====================
    }
    // ==================== END PLAYER POSITIONING ====================
    
    // ✅ STEP 3 MIGRATION: Use new animateShotToRim() instead of direct scene.tweens.add()
    // animateShotToRim() handles ball detachment and shot animation
    // Note: Ball is already detached above (lines 254-265), but animateShotToRim() will handle it safely
    const rimPosition = { x: rim.x, y: rim.y };
    
    // Animate shot to rim (async, so we need to handle completion after it resolves)
    (async () => {
      try {
        await animateShotToRim(scene, rimPosition, {
          duration,
          easing: "Sine.easeInOut"
        });
        
        // Handle completion (same logic as before, but now after animateShotToRim completes)
        const actualDuration = Date.now() - tweenStartTime;
        // console.log(`🏀 shootBall: Tween COMPLETE | Result: ${result} | Actual: ${actualDuration}ms / Expected: ${duration}ms | Ratio: ${(actualDuration / duration).toFixed(2)}x`);
        
        // Announce shot result when ball reaches rim
        const { showAnnouncement, showAndOneAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
        const { triggerFoulEffect, triggerMadeShotFlash } = await import('./negativeActionEffects.js');
        const teamStyle = isHomeTeam ? 'home' : 'away';
        
        // Check if this is a shooting foul (AND-1 or foul on shot)
        // ✅ FIX: Use reliable detection - check for next_play_type or free_throws_remaining (matches backend fields)
        // For AND-1 (MAKE + foul): text includes "AND-1" OR (foul_player_id exists + result === "MAKE" + foul_team === "DEFENSE")
        // For shooting foul on MISS: next_play_type === "FREE_THROW" OR free_throws_remaining > 0 (now set by backend)
        const hasFreeThrowsRemaining = (turnData?.free_throws_remaining ?? 0) > 0;
        const nextPlayTypeIsFreeThrow = turnData?.next_play_type === 'FREE_THROW';
        const hasFoulPlayer = !!(turnData?.foul_player_id || turnData?.foul_player?.player_id);
        const isAndOne = turnData?.text?.includes('AND-1') || 
                        (hasFoulPlayer && result === "MAKE" && turnData?.foul_team === "DEFENSE");
        const isShootingFoulOnMiss = result === "MISS" && (hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow);
        const isShootingFoul = isAndOne || isShootingFoulOnMiss;
        
        // 🔍 DEBUG: Log shooting foul detection for missed shots
        if (result === "MISS") {
          console.warn('🔍 [SHOOTING FOUL MISS DEBUG] ballManager.js detection:', {
            result,
            hasFreeThrowsRemaining,
            free_throws_remaining: turnData?.free_throws_remaining,
            nextPlayTypeIsFreeThrow,
            next_play_type: turnData?.next_play_type,
            hasFoulPlayer,
            foul_player_id: turnData?.foul_player_id,
            foul_team: turnData?.foul_team,
            isShootingFoulOnMiss,
            isShootingFoul
          });
        }
        
        // Get shooter/foul player data for announcements
        const shooterSprite = scene.playerSprites?.[shooterId];
        const shooterInfo = scene.playerInfo?.[shooterId];
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const shooterTeamName = shooterTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
        
        const shooterPlayerData = shooterInfo ? {
          playerId: shooterId,
          photo: shooterSprite?.photo || null,
          teamName: shooterTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, shooterTeamId)
        } : null;
        
        if (result === "MAKE") {
          // Trigger flash - diagonal split for AND-1, full green for regular makes
          triggerMadeShotFlash(scene, isShootingFoul);
          
          if (isShootingFoul) {
            // AND-1 - Use special two-row announcement
            const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
            if (foulPlayerId && shooterPlayerData) {
              const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
              const foulPlayerTeamId = foulPlayerSprite?.team_id;
              const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
              
              const foulPlayerData = {
                playerId: foulPlayerId,
                photo: foulPlayerSprite?.photo || null,
                teamName: foulPlayerTeamName,
                secondaryColor: getSecondaryColorForTeam(scene, foulPlayerTeamId)
              };

              showAndOneAnnouncement(teamStyle, shooterPlayerData, foulPlayerData);
              
              // NOTE: Red visual is handled by announcement box styling
              // No need for separate red flash (would mix with green flash)
            } else {
              // Fallback if data missing
              showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
            }
          } else {
            // Regular made shot
            showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
          }
        } else if (result === "MISS" && isShootingFoul) {
          // ✅ FIX: Replicate AND-1 announcement pattern exactly (matches made shot flow)
          // Get foul player data from turnData (same pattern as AND-1)
          const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
          if (foulPlayerId && scene) {
            const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
            if (foulPlayerSprite) {
              const foulPlayerTeamId = foulPlayerSprite?.team_id;
              const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
              
              const foulPlayerData = {
                playerId: foulPlayerId,
                photo: foulPlayerSprite?.photo || null,
                teamName: foulPlayerTeamName,
                secondaryColor: getSecondaryColorForTeam(scene, foulPlayerTeamId)
              };

              // Trigger foul effect
              const { triggerFoulEffect } = await import('./negativeActionEffects.js');
              triggerFoulEffect(scene, foulPlayerId);

              // Show announcement with player data (matches AND-1 pattern)
              showAnnouncement("Shooting Foul!", 'neutral', foulPlayerData);
            } else {
              // Fallback if sprite not found (matches AND-1 pattern)
              const { triggerFoulEffect } = await import('./negativeActionEffects.js');
              triggerFoulEffect(scene, foulPlayerId);
              showAnnouncement("Shooting Foul!", 'neutral', null);
            }
          } else {
            // Fallback if foulPlayerId not found (matches AND-1 pattern)
            showAnnouncement("Shooting Foul!", 'neutral', null);
          }
        }
        
        // ✅ PHASE 2.3: Use BallController lifecycle method for shot end
        // ✅ PHASE 4: Removed old _shotInProgress flag assignment
        if (ballController) {
          ballController.onShotEnd();
        }
        
        if (result === "MAKE") {
          console.log("score");
          console.log("rimHoldStart");
          // console.log(`🏀 shootBall: Rim hold starting - ball at (${ballSprite.x.toFixed(0)}, ${ballSprite.y.toFixed(0)})`);
          const finish = () => {
            console.log("rimHoldEnd");
            // console.log(`🏀 shootBall: Rim hold ending - ball at (${ballSprite.x.toFixed(0)}, ${ballSprite.y.toFixed(0)})`);
            // Keep watcher running a bit longer to catch post-shot teleports
            watcherRemoved = true;
            scene.time.delayedCall(200, () => {
              scene.events.off('update', positionWatcher);
            });
            // Small delay to ensure watcher is fully removed before re-enabling
            scene.time.delayedCall(50, () => {
              // ✅ PHASE 4: Removed old flag assignments - BallController manages state
              // console.log('🏀 shootBall: BallController state managed internally');
              resolve();
            });
          };
          // Keep rim hold delay for made shots (announcement hold from config)
          const madeRimHoldMs = animationConfig.shot?.madeRimHoldMs ?? 1000;
          if (scene.time?.delayedCall) {
            scene.time.delayedCall(madeRimHoldMs, finish);
          } else {
            setTimeout(finish, madeRimHoldMs);
          }
        } else if (result === "MISS") {
          if (scene.stateMachine?.is(States.ShotAttempt)) {
            safeTransition(
              scene.stateMachine,
              States.Rebound,
              {
                shotResult: result,
                stepIndex,
                currentOwnerId: getCurrentOwner(scene),
                pendingOwnerId: getPendingOwner(scene),
              },
              ["shotResult"]
            );
          }
          scene.rebounderId = null;
          // console.log(`🏀 shootBall: Starting bounce - ball at (${ballSprite.x.toFixed(0)}, ${ballSprite.y.toFixed(0)})`);
          bounceFromRim(
            scene,
            ballSprite,
            rimCoords,
            isHomeTeam,
            duration / 3
          ).then((miss) => {
            // console.log(`🏀 shootBall: Bounce complete - ball at (${ballSprite.x.toFixed(0)}, ${ballSprite.y.toFixed(0)})`);
            if (SHOT_DEBUG) {
              console.log("shot:miss", {
                type: "miss",
                shooterId,
                reboundSpot: miss.grid,
                playerId: shooterId,
                team: shooterTeamId,
              });
            }
            // Keep watcher running a bit longer to catch post-shot teleports
            watcherRemoved = true;
            scene.time.delayedCall(200, () => {
              scene.events.off('update', positionWatcher);
            });
            // Small delay to ensure watcher is fully removed before re-enabling
            // CRITICAL: Do NOT set ballDetached = false after MISS shots
            // The ball should remain detached until the rebound is handled
            // Setting it to false would re-enable ball following and might re-attach to shooter
            scene.time.delayedCall(50, () => {
              // ✅ PHASE 4: Removed old _shotInProgress flag assignment
              // BallController state already cleared by onShotEnd() above
              // BallController manages attachment state internally
              // scene.ballDetached = false; // REMOVED - prevents ball from re-attaching to shooter
              resolve(miss);
            });
          });
        } else {
          resolve();
        }
      } catch (error) {
        console.error('shootBall: Error during shot animation', error);
        resolve(); // Resolve anyway to prevent hanging
      }
    })();
  });
}

// Note: animatePutbackAttempt function removed - putbacks now use standard shootBall function

function coerceFastBreakFlag(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return normalized === "true" || normalized === "1" || normalized === "fast_break";
  }
  return false;
}

function isUpcomingFastBreak(scene, explicitFlag) {
  if (explicitFlag != null) {
    return coerceFastBreakFlag(explicitFlag);
  }
  const currentIndex = typeof scene?.currentTurn === "number" ? scene.currentTurn : null;
  if (currentIndex == null) return false;
  const nextTurn = scene?.simData?.turns?.[currentIndex + 1];
  if (!nextTurn) return false;
  if (coerceFastBreakFlag(nextTurn.fast_break)) return true;
  const resultType = typeof nextTurn.result_type === "string"
    ? nextTurn.result_type.toUpperCase()
    : null;
  return resultType === "FAST_BREAK";
}

/**
 * Animate players collapsing toward a missed shot for a rebound.
 *
 * @param {Object} opts
 * @param {Phaser.Scene} opts.scene
 * @param {Phaser.GameObjects.Image} opts.ballSprite
 * @param {Object} opts.playerSprites - map of playerId -> sprite
 * @param {Array} opts.animations - original turn animations
 * @param {string} opts.rebounderId - playerId of the rebounder
 * @param {{x:number, y:number}} opts.ballSpot - grid coordinates where ball landed
 */
export function animateRebound({
  scene,
  ballSprite,
  playerSprites,
  animations,
  rebounderId,
  ballSpot,
  shooterId,
  upcomingFastBreak,
  preserveBallPosition = false, // If true, don't move ball - it's already at correct position
  turnData = null, // Turn data with offense_getback list to exclude get-back players
}) {
  if (!scene || !ballSprite || !ballSpot) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);

  const debugEnabled = isAnimationDebugEnabled();
  const shouldHoldForFastBreak = () => isUpcomingFastBreak(scene, upcomingFastBreak);

  // Identify if this is OREB or DREB BEFORE setting scene.rebounderId
  const rebounderSprite = playerSprites[rebounderId];
  const shooterSprite = playerSprites[shooterId];
  const rebounderTeamId = rebounderSprite?.team_id;
  const shooterTeamId = shooterSprite?.team_id;
  const isOREB = rebounderTeamId === shooterTeamId;
  const reboundType = isOREB ? 'OREB' : 'DREB';

  console.log('🟡🟡🟡 [BLOCK/OREB BALL] animateRebound entry', {
    ballSpot,
    preserveBallPosition,
    rebounderId,
    reboundType,
  });
  
  scene.rebounderId = rebounderId;
  const rebCfg = animationConfig.rebound;
  const promises = []; // For other players' rebound animations (non-blocking)
  const reboundParticipantSprites = [];
  const finalPositions = [];
  const MIN_X_SEP = 3;
  const MIN_Y_SEP = 2;
  const spotPx = gridToPixels(
    ballSpot.x,
    ballSpot.y,
    scene.game.config.width,
    scene.game.config.height
  );

  // CRITICAL: For putback misses, the ball is already at the bounce spot from shootBall
  // Do NOT reposition the ball - it will cause it to snap to rim/rebounder position
  // Only set position if preserveBallPosition is false (for regular rebounds)
  if (!preserveBallPosition) {
    console.log('🟡🟡🟡 [BLOCK/OREB BALL] animateRebound setting ball position', { ballSpot, spotPx: { x: spotPx.x, y: spotPx.y } });
    ballSprite.setPosition(spotPx.x, spotPx.y);
  }
  ballSprite.setVisible(true);

  // rebounderSprite already declared earlier for OREB/DREB detection
  if (debugEnabled && REBOUND_DEBUG) {
    const team = rebounderSprite?.team_id ?? rebounderSprite?.team;
    animationDebugLog("reb:event", {
      type: "rebound",
      shooterId,
      reboundSpot: ballSpot,
      playerId: rebounderId,
      team
    });
  }
  
  // ✅ Store rebounder promise separately - this is what we'll wait for
  let rebounderPromise = null;
  
  if (rebounderSprite) {
    const teamId = rebounderSprite.team_id;
    finalPositions.push({ playerId: rebounderId, grid: { ...ballSpot } });
    if (debugEnabled && REBOUND_DEBUG) {
      animationDebugLog("reb:moveStart", {
        playerId: rebounderId,
        from: { x: rebounderSprite.x, y: rebounderSprite.y },
        to: { x: spotPx.x, y: spotPx.y },
        duration: rebCfg.playerMoveMs
      });
    }
    rebounderPromise = new Promise((resolve) => {
      tweenPlayerTo(scene, rebounderSprite, spotPx, {
        duration: rebCfg.playerMoveMs,
        easing: "Linear",
      })
        .then(async () => {
          console.log('🟡 [animateRebound] rebounder tween onComplete', { rebounderId });
          try {
            if (debugEnabled && REBOUND_DEBUG) {
              animationDebugLog("reb:moveEnd", {
                playerId: rebounderId,
                x: spotPx.x,
                y: spotPx.y
              });
            }
            
            // Announce rebound when rebounder reaches the ball
            const { showAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
            const rebounderTeam = rebounderSprite.team; // "home" or "away"
            const rebounderTeamId = rebounderSprite.team_id;

            // Handle both new nested structure (object) and old flat structure (string)
            const homeTeamField = scene.simData?.home_team;
            const awayTeamField = scene.simData?.away_team;
            const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
            const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
            const rebounderTeamName = rebounderTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;

            const playerData = {
              playerId: rebounderId,
              photo: rebounderSprite?.photo || null,
              teamName: rebounderTeamName,
              secondaryColor: getSecondaryColorForTeam(scene, rebounderTeamId)
            };

            showAnnouncement("Rebound!", rebounderTeam, playerData);
            
            // Identify if this is OREB or DREB (rebounderTeamId already declared above on line 911)
            // Use outer scope variables or re-declare only what we need
            const shooterSpriteInner = playerSprites[shooterId];
            const shooterTeamIdInner = shooterSpriteInner?.team_id;
            const isOREBInner = rebounderTeamId === shooterTeamIdInner;
            const reboundType = isOREBInner ? 'OREB' : 'DREB';
            
            // CRITICAL: Don't attach ball if a putback is in progress
            // The putback turn will handle ball positioning and shooting
            // ✅ PHASE 4: Check BallController state instead of old _putbackInProgress flag
            const { getBallController } = await import('./BallControllerAdapter.js');
            const ballController = getBallController();
            const isPutbackInProgress = ballController && (ballController.reason === 'putback_shot' || ballController.state === 'PUTBACK_ATTEMPT');
            if (isPutbackInProgress) {
              if (debugEnabled && REBOUND_DEBUG) {
                animationDebugLog("reb:skipAttach", {
                  reason: 'putback_in_progress',
                  rebounderId,
                  reboundType
                });
              }
            } else {
              attachBallToPlayer(scene, ballSprite, rebounderSprite, {
                debugInfo: { shooterId, reboundSpot: ballSpot, reboundType }
              });
            }
            
            const newOffenseId = rebounderSprite.team_id;
            const previousOffenseId = scene.offenseTeamId;
            scene.offenseTeamId = newOffenseId;
            const changed =
              newOffenseId != null &&
              (previousOffenseId == null || String(previousOffenseId) !== String(newOffenseId));
            if (changed) {
              scene.events?.emit?.("possessionChange", {
                offenseTeamId: newOffenseId,
              });
            }
            if (scene.stateMachine?.is(States.Rebound)) {
              const holdReboundState = shouldHoldForFastBreak();
              if (holdReboundState) {
                if (debugEnabled && getDebugTransitions()) {
                  animationDebugLog(
                    "animateRebound: holding Rebound state for fast break handoff",
                    {
                      rebounderId,
                      currentTurn: scene.currentTurn,
                    }
                  );
                }
              } else {
                safeTransition(scene.stateMachine, States.HalfCourt, {
                  currentOwnerId: getCurrentOwner(scene),
                  pendingOwnerId: getPendingOwner(scene),
                });
              }
            }
            scene.rebounderId = null;
          } catch (e) {
            console.error('❌ [animateRebound] Error in rebounder tween onComplete', {
              rebounderId,
              error: e?.message ?? String(e),
              stack: e?.stack
            });
          } finally {
            resolve();
          }
        })
        .catch(() => {
          console.log('🟡 [animateRebound] rebounder tween onStop', { rebounderId });
          resolve();
        });
    });
    // Add rebounder promise to promises array for other players' animations (non-blocking)
    promises.push(rebounderPromise);
  }

  // Determine shooting team to apply proximity criteria
  // shooterSprite already declared earlier on line 819
  const shootingTeam = shooterSprite?.team; // "home" or "away"
  const isHomeTeamShot = shootingTeam === "home";

  // Get offense_getback list to exclude get-back players from rebound animation
  // These players already animated back during the shot attempt, so they shouldn't
  // animate toward the rebound spot - they're already back on defense
  let offenseGetBackList = [];
  if (turnData?.offense_getback) {
    offenseGetBackList = turnData.offense_getback;
  } else {
    // Try to find the MISS turn from scene.simData
    const currentIndex = scene.currentTurn || 0;
    const currentTurn = scene.simData?.turns?.[currentIndex];
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    
    // Check current turn first (if this turn is the rebound turn after a MISS)
    if ((currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") && currentTurn?.offense_getback) {
      offenseGetBackList = currentTurn.offense_getback;
    } else if ((previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") && previousTurn?.offense_getback) {
      // Otherwise, check previous turn
      offenseGetBackList = previousTurn.offense_getback;
    }
  }
  

  // console.log('REBOUND ANIMATION DEBUG:', {
  //   shooterId,
  //   shootingTeam,
  //   isHomeTeamShot,
  //   rebounderId,
  //   ballSpot,
  //   totalPlayers: Object.keys(playerSprites).length
  // });

  // Animate other players attempting to rebound
  // CRITICAL: Exclude get-back players - they already animated back during the shot
  for (const sprite of Object.values(playerSprites)) {
    if (!sprite || sprite.playerId === rebounderId) continue;
    
    // Exclude get-back players - they already moved back during the shot attempt
    if (offenseGetBackList.includes(sprite.playerId)) {
      continue;
    }

    // Get current position in grid coordinates
    const currentGridX = (sprite.x / scene.game.config.width) * 100;
    const currentGridY = 50 - (sprite.y / scene.game.config.height) * 50;

    // Apply proximity criteria based on shooting team
    // Home team shot (attacking right, X=91): only players with X >= 74 can rebound
    // Away team shot (attacking left, X=9): only players with X <= 25 can rebound
    const meetsProximityCriteria = isHomeTeamShot 
      ? currentGridX >= 74 
      : currentGridX <= 25;

    if (!meetsProximityCriteria) {
      continue;
    }

    // Random spot within 6 X and 8 Y of ball, staying in bounds
    const targetX = Phaser.Math.Clamp(
      ballSpot.x + Phaser.Math.Between(-6, 6),
      9,
      91
    );
    const targetY = Phaser.Math.Clamp(
      ballSpot.y + Phaser.Math.Between(-8, 8),
      5,
      45
    );

    const targetGrid = { x: targetX, y: targetY };
    finalPositions.push({ playerId: sprite.playerId, grid: { ...targetGrid } });

    const targetPx = gridToPixels(
      targetGrid.x,
      targetGrid.y,
      scene.game.config.width,
      scene.game.config.height
    );

    reboundParticipantSprites.push(sprite);
    promises.push(
      tweenPlayerTo(scene, sprite, targetPx, {
        duration: rebCfg.playerMoveMs,
        easing: "Linear",
      }).catch(() => {})
    );
  }

  // ✅ FIX: Resolve when rebounder secures the ball, not when all animations complete
  // Other players' rebound animations continue in background but don't block resolution
  if (rebounderPromise) {
    return rebounderPromise.then(
    () =>
      new Promise((resolve) => {
        // End-of-rebound boundary: stop non-rebounder rebound tweens so they
        // do not leak into the next turn and cause transition hitching.
        if (scene?.tweens && reboundParticipantSprites.length > 0) {
          reboundParticipantSprites.forEach((sprite) => {
            if (sprite) scene.tweens.killTweensOf(sprite);
          });
        }
        const logPayload = {
          rebounderId,
          ballSpot,
          positions: finalPositions
        };
        if (debugEnabled && REBOUND_DEBUG) {
          animationDebugLog("[rebound]", logPayload);
        }
        const attachDelayCapMs = Math.max(
          0,
          Number(
            (typeof window !== "undefined"
              ? window.UESS_REBOUND_ATTACH_DELAY_CAP_MS
              : globalThis?.UESS_REBOUND_ATTACH_DELAY_CAP_MS) ?? 180
          ) || 180
        );
        const effectiveAttachDelayMs = Math.min(
          Math.max(0, Number(rebCfg.attachDelayMs) || 0),
          attachDelayCapMs
        );
        if (scene.time?.delayedCall) {
          scene.time.delayedCall(effectiveAttachDelayMs, resolve);
        } else {
          setTimeout(resolve, effectiveAttachDelayMs);
        }
      })
  );
  } else {
    // Fallback: If no rebounder sprite, resolve immediately
    return Promise.resolve();
  }
}

/**
 * Animate an offensive rebound kickout pass to reset the half‑court offense.
 * Attaches the ball to the rebounder, tweens the pass to the point guard,
 * then locks the ball to the PG on completion.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {string} rebounderId
 * @param {string} pgId
 * @param {{fromCoords:{x:number,y:number}, toCoords:{x:number,y:number}, duration?:number}} pass
 * @param {number} [duration]
 */
export function animateKickoutReset(
  scene,
  ballSprite,
  rebounderId,
  pgId,
  pass = {},
  duration
) {
  if (!scene || !ballSprite) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();

  const debugEnabled = isAnimationDebugEnabled();
  const rebounderSprite = scene.playerSprites?.[rebounderId];
  const pgSprite = scene.playerSprites?.[pgId];
  if (!rebounderSprite || !pgSprite) {
    if (debugEnabled) {
      animationDebugWarn('animateKickoutReset: Missing sprites', {
        rebounderId,
        pgId,
        rebounderSprite: !!rebounderSprite,
        pgSprite: !!pgSprite,
      });
    }
    return Promise.resolve();
  }

  // Ensure runPass can locate the ball sprite on the scene
  if (!scene.ballSprite) {
    scene.ballSprite = ballSprite;
  }

  // Attach to the rebounder before starting the pass
  attachBallToPlayer(scene, ballSprite, rebounderSprite);

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const cfg = animationConfig.kickout;
  const raw = duration ?? pass.duration;
  const usedDuration = raw != null && raw >= cfg.duration ? raw : cfg.duration;

  const opts = {
    fromId: rebounderId,
    toId: pgId,
    duration: usedDuration,
    easing: cfg.easing
  };

  // ALWAYS use actual sprite positions for kickout passes (ignore backend coords)
  // Backend coords may be stale after rebound animation moves players
  opts.startCoords = { x: rebounderSprite.x, y: rebounderSprite.y };
  opts.endCoords = { x: pgSprite.x, y: pgSprite.y };
  
  if (debugEnabled) {
    animationDebugLog('animateKickoutReset: Using sprite positions', {
      from: opts.startCoords,
      to: opts.endCoords,
      rebounderPos: { x: rebounderSprite.x, y: rebounderSprite.y },
      pgPos: { x: pgSprite.x, y: pgSprite.y }
    });
  }

  if (scene.stateMachine?.is(States.FastBreak)) {
    return Promise.resolve();
  }

  const ownerBefore = getCurrentOwner(scene);
  detachBall(scene, ballSprite);

  if (debugEnabled) {
    animationDebugLog('animateKickoutReset: Starting pass', { rebounderId, pgId, opts });
  }

  return runPass(scene, opts).then(() => {
    if (debugEnabled) {
      animationDebugLog('animateKickoutReset: Pass completed, attaching ball to PG');
    }
    attachBallToPlayer(scene, ballSprite, pgSprite);
    setPendingOwner(scene, pgId);
    const ownerAfter = getCurrentOwner(scene);

    if (scene.stateMachine?.is(States.Rebound)) {
      safeTransition(scene.stateMachine, States.HalfCourt);
    }

    if (debugEnabled && (DebugFlags?.BALL || DebugFlags?.FSM)) {
      animationDebugLog({
        event: 'KICK_OUT_PASS',
        from: rebounderId,
        to: pgId,
        ownerBefore,
        ownerAfter
      });
    }
  }).catch((error) => {
    if (debugEnabled) {
      animationDebugWarn('animateKickoutReset: Pass failed', error);
    }
    // Fallback: just attach ball to PG
    attachBallToPlayer(scene, ballSprite, pgSprite);
    setPendingOwner(scene, pgId);
  });
}

/**
 * Checks which player has the ball at the current animation step
 * and locks the ball to that player's sprite.
 *
 * @param {Phaser.GameObjects.Image} ballSprite - The Phaser ball image
 * @param {Array} animations - Array of player animation objects for the current turn
 * @param {Object} playerSprites - Map of playerId → Phaser sprite
 * @param {number} currentTimestamp - The current animation timestamp (ms)
 */
/**
 * Update ball ownership (timestamp-based)
 * Delegates to unified updateBallOwnership function
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Sprite} ballSprite
 * @param {Array} animations
 * @param {Object} playerSprites
 * @param {number} currentTimestamp
 */
export async function updateBallOwnership(scene, ballSprite, animations, playerSprites, currentTimestamp) {
  const { updateBallOwnership: unifiedUpdate } = await import('./BallControllerAdapter.js');
  return unifiedUpdate({
    scene,
    ballSprite,
    animations,
    playerSprites,
    currentTimestamp
  });
}


// import { attachBallToPlayer, passBall } from "./ballManager.js";

// // Lock to player
// attachBallToPlayer(ballSprite, playerSprites[playerId]);

// // Animate pass
// passBall({
//   scene,
//   ballSprite,
//   fromCoords: passStep.coords,
//   toCoords: receiveStep.coords,
//   fromTimestamp: passStep.timestamp,
//   toTimestamp: receiveStep.timestamp
// });
