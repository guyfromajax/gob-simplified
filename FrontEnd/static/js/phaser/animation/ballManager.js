import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { generateBallTween } from "./generateBallTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { runInboundSetup as baseRunInboundSetup } from "./turnAnimation.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import {
  detachBall,
  tweenBallTo,
  runPass as baseRunPass
} from "./ballTween.js";
import { attachBallToPlayer as baseAttachBallToPlayer } from "./BallControllerAdapter.js";
import { States, getDebugTransitions, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import gameStore from "../../state/gameStore.js";
import {
  clearCurrentOwner,
  cancelBallTween,
  getCurrentOwner,
  getPendingOwner,
  setPendingOwner,
} from "../ball/ballController.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";

function attachBallToPlayer(scene, ballSprite, playerSprite, opts = {}) {
  if (scene.possessionFlipInProgress) return;

  let targetId = playerSprite?.playerId;
  if (targetId == null && scene?.playerSprites) {
    for (const [pid, sprite] of Object.entries(scene.playerSprites)) {
      if (sprite === playerSprite) {
        targetId = pid;
        break;
      }
    }
  }

  if (scene.stateMachine?.is(States.Rebound) && targetId !== scene.rebounderId) {
    return;
  }

  const debugEnabled = isAnimationDebugEnabled();
  if (debugEnabled && REBOUND_DEBUG) {
    if (
      scene?.currentBallOwnerRef &&
      scene.currentBallOwnerRef.value &&
      scene.currentBallOwnerRef.value !== playerSprite
    ) {
      const refId = scene.currentBallOwnerRef.value?.playerId;
      animationDebugWarn("ball:owner mismatch", {
        ref: refId,
        target: targetId
      });
    }

    const logPayload = {
      type: "ballAttach",
      shooterId: opts?.debugInfo?.shooterId ?? null,
      reboundSpot: opts?.debugInfo?.reboundSpot ?? null,
      playerId: targetId,
      team: playerSprite?.team_id ?? playerSprite?.team ?? null
    };
    animationDebugLog("ball:attach", logPayload);
  }

  if (scene?.currentBallOwnerRef) {
    scene.currentBallOwnerRef.value = playerSprite;
  }

  return baseAttachBallToPlayer(scene, ballSprite, playerSprite, opts);
}

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

export { attachBallToPlayer, detachBall, tweenBallTo, runPass, runInboundSetup };

// Debug flags for logging shot / rebound details
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export const INBOUND_DEBUG = false;



/**
 * Animate the ball flying from one point to another.
 */
export function passBall({
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  fromTimestamp,
  toTimestamp
}) {
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  generateBallTween({
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
export function animateInboundPass(
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  startTs,
  endTs
) {
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  generateBallTween({
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
export function bounceFromRim(
  scene,
  ballSprite,
  rimCoords,
  isHomeTeam,
  duration
) {
  return new Promise((resolve) => {
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
    const clampedBounceX = Phaser.Math.Clamp(bounceGridX, 4, 97);
    const clampedBounceY = Phaser.Math.Clamp(bounceGridY, 1, 50);
    
    const bounce = gridToPixels(
      clampedBounceX,
      clampedBounceY,
      scene.game.config.width,
      scene.game.config.height
    );
    scene.tweens.add({
      targets: ballSprite,
      x: bounce.x,
      y: bounce.y,
      duration,
      ease: "Sine.easeOut",
      onComplete: () => resolve({ grid: { x: clampedBounceX, y: clampedBounceY } })
    });
  });
}

/**
 * Launches a shot toward the rim along a single tweened path.
 * Resolves after the ball reaches the rim.
*/
export function shootBall({
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
  
  // Stop BOTH old and new ball following systems
  scene.ballDetached = true; // Stop old system (scene._ballFollowing callback checks this)
  if (scene.ballController) {
    if (typeof scene.ballController.stopFollowingPlayer === 'function') {
      scene.ballController.stopFollowingPlayer();
    }
    // Also set isAttached to false to prevent followCallback from running
    scene.ballController.isAttached = false;
    
    // Set a flag to prevent re-attachment during shot
    scene._shotInProgress = true;
  }
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
      const playersNearby = Object.values(playerSprites).filter(p => {
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

  return new Promise((resolve) => {
    // console.log('🏀 shootBall: About to call scene.tweens.add', {
    //   hasTweens: !!scene.tweens,
    //   ballSpritePos: { x: ballSprite.x, y: ballSprite.y },
    //   targetPos: { x: rim.x, y: rim.y },
    //   distance: Phaser.Math.Distance.Between(ballSprite.x, ballSprite.y, rim.x, rim.y),
    //   duration
    // });
    
    const tweenStartTime = Date.now();
    
    // ==================== ANIMATE PLAYERS DURING SHOT ====================
    // Defenders releasing for fast break + Offensive players getting back on defense
    if (turnData) {
      console.log('🏃 Checking player positioning data:', {
        defense_release: turnData.defense_release,
        offense_getback: turnData.offense_getback
      });
      
      // Defenders releasing for fast break
      if (turnData.defense_release && turnData.defense_release.length > 0) {
        console.log('🏃 Animating', turnData.defense_release.length, 'defenders releasing for fast break');
        turnData.defense_release.forEach(playerId => {
          const sprite = scene.playerSprites[playerId];
          if (sprite) {
            const targetY = Phaser.Math.Between(15, 35);
            const targetX = Phaser.Math.Between(45, 55);
            const targetPixel = gridToPixels(targetX, targetY, scene.game.config.width, scene.game.config.height);
            
            console.log(`🏃 DEFENDER ${playerId} releasing: from (${sprite.x}, ${sprite.y}) → to (${targetPixel.x}, ${targetPixel.y})`);
            
            scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: duration, // Same duration as ball flight
              ease: 'Power1',
              onStart: () => {
                console.log(`🏃 STARTED: Defender ${playerId} moving to fast break spot`);
              },
              onComplete: () => {
                console.log(`🏃 COMPLETED: Defender ${playerId} reached fast break spot`);
              }
            });
          } else {
            console.warn(`🏃 ⚠️ Defender sprite not found for player ${playerId}`);
          }
        });
      }
      
      // Offensive players getting back on defense
      if (turnData.offense_getback && turnData.offense_getback.length > 0) {
        console.log('🏃 Animating', turnData.offense_getback.length, 'offensive players getting back');
        
        turnData.offense_getback.forEach(playerId => {
          const sprite = scene.playerSprites[playerId];
          if (sprite) {
            const targetY = Phaser.Math.Between(14, 36);
            // Away team shooting → x: 50-60, Home team shooting → x: 40-50
            const targetX = isHomeTeam ? Phaser.Math.Between(40, 50) : Phaser.Math.Between(50, 60);
            const targetPixel = gridToPixels(targetX, targetY, scene.game.config.width, scene.game.config.height);
            
            console.log(`🏃 OFFENSE ${playerId} getting back: from (${sprite.x}, ${sprite.y}) → to (${targetPixel.x}, ${targetPixel.y})`);
            
            scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: duration, // Same duration as ball flight
              ease: 'Power1',
              onStart: () => {
                console.log(`🏃 STARTED: Offense ${playerId} getting back on defense`);
              },
              onComplete: () => {
                console.log(`🏃 COMPLETED: Offense ${playerId} back on defense`);
              }
            });
          } else {
            console.warn(`🏃 ⚠️ Offensive sprite not found for player ${playerId}`);
          }
        });
      }
      
      // ==================== REBOUND POSITIONING ====================
      // Animate all other players (not shooter, defender, release, get back) 
      // into rebound position during shot flight
      
      // Build exclusion list
      const excludedPlayerIds = new Set();
      excludedPlayerIds.add(shooterId); // Shooter
      if (turnData.defenderId) excludedPlayerIds.add(turnData.defenderId); // Shot defender
      if (turnData.defender_id) excludedPlayerIds.add(turnData.defender_id); // Alternative defender field
      if (turnData.defense_release) {
        turnData.defense_release.forEach(id => excludedPlayerIds.add(id)); // Release players
      }
      if (turnData.offense_getback) {
        turnData.offense_getback.forEach(id => excludedPlayerIds.add(id)); // Get back players
      }
      
      // Determine basket x coordinate (which basket is being attacked)
      const basketX = isHomeTeam ? 91 : 9; // Home attacks away basket (91), away attacks home basket (9)
      
      // Animate all other players into rebound position
      const playerSprites = scene.playerSprites || {};
      let reboundPositionCount = 0;
      
      Object.keys(playerSprites).forEach(playerId => {
        if (excludedPlayerIds.has(playerId)) {
          return; // Skip excluded players
        }
        
        const sprite = playerSprites[playerId];
        if (!sprite) return;
        
        // Get player's current position in grid coordinates
        const currentPixelX = sprite.x;
        const currentPixelY = sprite.y;
        
        // Convert pixel to grid (reverse of gridToPixels)
        const canvasWidth = scene.game.config.width;
        const canvasHeight = scene.game.config.height;
        const currentGridX = (currentPixelX / canvasWidth) * 100;
        const currentGridY = 50 - (currentPixelY / canvasHeight) * 50;
        
        // Calculate target position based on rebound positioning rules
        let targetGridX = currentGridX;
        let targetGridY = currentGridY;
        
        // X movement: Move toward basket if > 3 spots away
        const distanceFromBasket = Math.abs(currentGridX - basketX);
        if (distanceFromBasket > 3) {
          const moveAmount = Phaser.Math.Between(3, 6);
          // Move closer to basket
          if (currentGridX > basketX) {
            targetGridX = currentGridX - moveAmount;
          } else {
            targetGridX = currentGridX + moveAmount;
          }
        }
        // Else: Keep x the same (already close to basket)
        
        // Y movement: Move toward center court (y = 25)
        if (currentGridY > 25) {
          // Move down (negative y)
          const moveAmount = Phaser.Math.Between(1, 6);
          targetGridY = currentGridY - moveAmount;
        } else if (currentGridY < 26) {
          // Move up (positive y)
          const moveAmount = Phaser.Math.Between(1, 6);
          targetGridY = currentGridY + moveAmount;
        }
        // Else: y is exactly 25 or 26, keep it the same (rare)
        
        // Convert target grid back to pixels
        const targetPixel = gridToPixels(targetGridX, targetGridY, canvasWidth, canvasHeight);
        
        // Animate to rebound position
        scene.tweens.add({
          targets: sprite,
          x: targetPixel.x,
          y: targetPixel.y,
          duration: duration, // Same duration as ball flight
          ease: 'Power1'
        });
        
        reboundPositionCount++;
      });
      
      console.log(`🏀 Animating ${reboundPositionCount} players into rebound position during shot`);
      // ==================== END REBOUND POSITIONING ====================
    }
    // ==================== END PLAYER POSITIONING ====================
    
    const tween = scene.tweens.add({
      targets: ballSprite,
      x: rim.x,
      y: rim.y,
      duration,
      ease: "Sine.easeInOut",
      onStart: () => {
        // console.log('🏀 shootBall: Tween STARTED!', {
        //   timestamp: Date.now(),
        //   elapsedSinceCreate: Date.now() - tweenStartTime
        // });
      },
      onUpdate: (tween) => {
        if (tween.progress === 0 || tween.progress === 0.5 || tween.progress === 1) {
          const elapsed = Date.now() - tweenStartTime;
          // console.log(`🏀 shootBall: Tween ${(tween.progress * 100).toFixed(0)}% | Elapsed: ${elapsed}ms / ${duration}ms | Ball at (${ballSprite.x.toFixed(0)}, ${ballSprite.y.toFixed(0)}) | Visible: ${ballSprite.visible}`);
        }
      },
      onComplete: async () => {
        const actualDuration = Date.now() - tweenStartTime;
        // console.log(`🏀 shootBall: Tween COMPLETE | Result: ${result} | Actual: ${actualDuration}ms / Expected: ${duration}ms | Ratio: ${(actualDuration / duration).toFixed(2)}x`);
        
        // Announce shot result when ball reaches rim
        const { showAnnouncement } = await import('../utils/announcements.js');
        const teamStyle = isHomeTeam ? 'home' : 'away';
        
        // Check if this is a shooting foul (AND-1 or foul on shot)
        const isShootingFoul = turnData?.text?.includes('AND-1') || 
                              turnData?.text?.includes('fouls') && turnData?.text?.includes('on the shot');
        
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
          teamName: shooterTeamName
        } : null;
        
        if (result === "MAKE") {
          if (isShootingFoul) {
            showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
            
            // Trigger visual effect on fouling player for AND-1
            const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
            if (foulPlayerId) {
              const { triggerFoulEffect } = await import('./negativeActionEffects.js');
              triggerFoulEffect(scene, foulPlayerId);
            }
          } else {
            showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
          }
        } else if (result === "MISS" && isShootingFoul) {
          // Get foul player data from turnData
          let foulPlayerData = null;
          if (turnData?.foul_player_id) {
            const foulPlayerId = turnData.foul_player_id;
            const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
            const foulPlayerTeamId = foulPlayerSprite?.team_id;
            const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
            
            foulPlayerData = {
              playerId: foulPlayerId,
              photo: foulPlayerSprite?.photo || null,
              teamName: foulPlayerTeamName
            };
            
            // Trigger foul effect
            const { triggerFoulEffect } = await import('./negativeActionEffects.js');
            triggerFoulEffect(scene, foulPlayerId);
          }
          
          showAnnouncement("Shooting Foul!", 'neutral', foulPlayerData);
        }
        
        // Clear shot in progress flag
        scene._shotInProgress = false;
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
              scene._shotInProgress = false;
              scene.ballDetached = false;
              // console.log('🏀 shootBall: Flags reset, ball following re-enabled');
              resolve();
            });
          };
          if (scene.time?.delayedCall) {
            scene.time.delayedCall(1000, finish);
          } else {
            setTimeout(finish, 1000);
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
            scene.time.delayedCall(50, () => {
              scene._shotInProgress = false;
              scene.ballDetached = false;
              resolve(miss);
            });
          });
        } else {
          resolve();
        }
      }
    });
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
}) {
  if (!scene || !ballSprite || !ballSpot) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);

  const debugEnabled = isAnimationDebugEnabled();
  const shouldHoldForFastBreak = () => isUpcomingFastBreak(scene, upcomingFastBreak);

  scene.rebounderId = rebounderId;
  const rebCfg = animationConfig.rebound;
  const promises = [];
  const finalPositions = [];
  const MIN_X_SEP = 3;
  const MIN_Y_SEP = 2;
  const spotPx = gridToPixels(
    ballSpot.x,
    ballSpot.y,
    scene.game.config.width,
    scene.game.config.height
  );

  ballSprite.setPosition(spotPx.x, spotPx.y);
  ballSprite.setVisible(true);

  const rebounderSprite = playerSprites[rebounderId];
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
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: rebounderSprite,
          x: spotPx.x,
          y: spotPx.y,
          duration: rebCfg.playerMoveMs,
          ease: "Linear",
          onComplete: async () => {
            if (debugEnabled && REBOUND_DEBUG) {
              animationDebugLog("reb:moveEnd", {
                playerId: rebounderId,
                x: spotPx.x,
                y: spotPx.y
              });
            }
            
            // Announce rebound when rebounder reaches the ball
            const { showAnnouncement } = await import('../utils/announcements.js');
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
              teamName: rebounderTeamName
            };
            
            showAnnouncement("Rebound!", rebounderTeam, playerData);
            
            attachBallToPlayer(scene, ballSprite, rebounderSprite, {
              debugInfo: { shooterId, reboundSpot: ballSpot }
            });
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
            resolve();
          },
          onStop: resolve
        });
      })
    );
  }

  // Determine shooting team to apply proximity criteria
  const shooterSprite = playerSprites[shooterId];
  const shootingTeam = shooterSprite?.team; // "home" or "away"
  const isHomeTeamShot = shootingTeam === "home";

  // console.log('REBOUND ANIMATION DEBUG:', {
  //   shooterId,
  //   shootingTeam,
  //   isHomeTeamShot,
  //   rebounderId,
  //   ballSpot,
  //   totalPlayers: Object.keys(playerSprites).length
  // });

  // Animate other players attempting to rebound
  for (const sprite of Object.values(playerSprites)) {
    if (!sprite || sprite.playerId === rebounderId) continue;

    // Get current position in grid coordinates
    const currentGridX = (sprite.x / scene.game.config.width) * 100;
    const currentGridY = 50 - (sprite.y / scene.game.config.height) * 50;

    // Apply proximity criteria based on shooting team
    // Home team shot (attacking right, X=91): only players with X >= 74 can rebound
    // Away team shot (attacking left, X=9): only players with X <= 25 can rebound
    const meetsProximityCriteria = isHomeTeamShot 
      ? currentGridX >= 74 
      : currentGridX <= 25;

    // console.log('Player proximity check:', {
    //   playerId: sprite.playerId,
    //   currentGridX,
    //   currentGridY,
    //   meetsProximityCriteria,
    //   isHomeTeamShot,
    //   threshold: isHomeTeamShot ? '>=74' : '<=25'
    // });

    if (!meetsProximityCriteria) continue;

    // Random spot within 6 X and 8 Y of ball, staying in bounds
    const targetX = Phaser.Math.Clamp(
      ballSpot.x + Phaser.Math.Between(-6, 6),
      9,
      92
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

    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x: targetPx.x,
          y: targetPx.y,
          duration: rebCfg.playerMoveMs,
          ease: "Linear",
          onComplete: resolve,
          onStop: resolve
        });
      })
    );
  }

  return Promise.all(promises).then(
    () =>
      new Promise((resolve) => {
        const logPayload = {
          rebounderId,
          ballSpot,
          positions: finalPositions
        };
        if (debugEnabled && REBOUND_DEBUG) {
          animationDebugLog("[rebound]", logPayload);
        }
        if (scene.time?.delayedCall) {
          scene.time.delayedCall(rebCfg.attachDelayMs, resolve);
        } else {
          setTimeout(resolve, rebCfg.attachDelayMs);
        }
      })
  );
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
export function updateBallOwnership(scene, ballSprite, animations, playerSprites, currentTimestamp) {
  for (const anim of animations) {
    const { playerId, hasBallAtStep, movement } = anim;
    if (!hasBallAtStep || !movement || !movement.length) continue;

    // Find current step index based on timestamp
    let stepIndex = 0;
    while (
      stepIndex < movement.length - 1 &&
      currentTimestamp >= movement[stepIndex + 1].timestamp
    ) {
      stepIndex++;
    }

    if (hasBallAtStep[stepIndex]) {
      const playerSprite = playerSprites[playerId];
      if (playerSprite) {
        attachBallToPlayer(scene, ballSprite, playerSprite);
      }
      break; // Only one player can have the ball
    }
  }
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
