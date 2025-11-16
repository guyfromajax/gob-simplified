import { gridToPixels } from "../utils/gridToPixels.js";

/**
 * Animates a single step of a player's movement.
 * Called by the centralized step loop in turnAnimation.js.
 *
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
 * @param {object} step - The movement step { timestamp, coords, action }
 * @param {number} duration - Milliseconds for tween duration
 * @returns {Promise} resolves when tween completes
 */
import { PASS_DEBUG } from "./ballTween.js";
import {
  getPendingOwner,
  getCurrentOwner,
} from "../ball/ballController.js";
import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";

export const PLAYER_TWEEN_DEBUG = false;

export function animateStep({ scene, sprite, step, duration, ballSprite, currentBallOwnerRef, onAction }) {
  if (scene.skipToEnd) return Promise.resolve();
  return new Promise((resolve) => {
    let tween = null;
    let tweenCompleted = false;
    // Safety timeout: if tween doesn't complete within reasonable time, force resolve
    const timeoutMs = Math.max(duration * 2, 5000); // At least 2x duration or 5 seconds
    const timeoutId = setTimeout(() => {
      if (tweenCompleted) {
        // Tween already completed, just clear timeout
        return;
      }
      const distance = Math.hypot(sprite.x - targetX, sprite.y - targetY);
      let tweenManagerState = null;
      if (scene.tweens) {
        try {
          const total = typeof scene.tweens.getAll === 'function' 
            ? scene.tweens.getAll().length 
            : 'N/A';
          const paused = typeof scene.tweens.isPaused === 'function'
            ? scene.tweens.isPaused()
            : 'N/A';
          tweenManagerState = {
            total,
            paused,
            timeScale: scene.tweens.timeScale || 'N/A'
          };
        } catch (error) {
          tweenManagerState = { error: error.message };
        }
      }
      // Check if this is a step before a shot (common cause of pauses)
      const isBeforeShot = step.action === 'guard_ball' || step.action === 'receive' || 
                          (scene.currentTurnData?.animations?.some(anim => 
                            anim.movement?.some(m => m.action === 'shoot' && m.timestamp > step.timestamp)
                          ));
      
      console.warn('animateStep: Timeout - forcing resolve', {
        playerId: sprite?.playerId,
        action: step.action,
        duration,
        timeoutMs,
        tweenActive: tween?.isPlaying !== false,
        tweenProgress: tween?.progress,
        spritePos: { x: sprite.x, y: sprite.y },
        targetPos: { x: targetX, y: targetY },
        distanceToTarget: distance,
        tweenManagerState,
        scenePaused: scene.scene?.isPaused(),
        skipToEnd: scene.skipToEnd,
        isBeforeShot,
        stepTimestamp: step.timestamp
      });
      if (tween) {
        scene.tweens?.killTweensOf(tween);
      }
      tweenCompleted = true;
      resolve();
    }, timeoutMs);
    const { x: targetX, y: targetY } = gridToPixels(
      step.coords.x,
      step.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    const startPosition = { x: sprite.x, y: sprite.y };
    const plannedDistance = Math.hypot(targetX - startPosition.x, targetY - startPosition.y);

    const emitSummary = (status) => {
      if (!isAnimationDebugEnabled()) return;
      const ownerId = getCurrentOwner(scene);
      const pendingOwnerId = getPendingOwner(scene);
      const actualDistance = Math.hypot(sprite.x - startPosition.x, sprite.y - startPosition.y);
      const summary = {
        type: 'step',
        status,
        playerId: sprite?.playerId ?? null,
        action: step.action ?? null,
        timestamp: step.timestamp,
        plannedDistance,
        actualDistance,
        ownerId,
        pendingOwnerId,
        passInFlight: !!scene?.passInFlight,
        ballDetached: !!scene?.ballDetached,
        scoreDelta: scene?.__debugScoreDelta ?? null,
        position: { x: sprite.x, y: sprite.y },
      };
      animationDebugLog('ANIM step summary', summary);
      const tolerance = 2;
      if (actualDistance - plannedDistance > tolerance) {
        animationDebugWarn('ANIM teleport suspicion', {
          playerId: sprite?.playerId ?? null,
          plannedDistance,
          actualDistance,
          start: startPosition,
          target: { x: targetX, y: targetY },
        });
      }
    };

    let startPromise = Promise.resolve();

    // Determine if this player has the ball - if so, include ball in tween targets
    // This ensures ball and player move together smoothly (based on WIP_GOB learnings)
    // Must check that ballSprite exists and is a valid Phaser object before including it
    // Also exclude ball if a pass is happening (ball will be detached)
    const playerHasBall = currentBallOwnerRef?.value === sprite && !getPendingOwner(scene);
    const isPassing = step.action === 'pass' || scene.passInFlight;
    const ballIsValid = ballSprite && 
                       ballSprite.scene && 
                       ballSprite.active !== false && 
                       !ballSprite.destroyed &&
                       !isPassing;  // Don't include ball if pass is happening
    const tweenTargets = playerHasBall && ballIsValid
      ? [sprite, ballSprite]  // Ball moves WITH player
      : [sprite];             // Player only

    // Filter out any null/invalid targets before creating tween
    const validTargets = tweenTargets.filter(target => 
      target && 
      target.scene && 
      target.active !== false && 
      !target.destroyed
    );

    // If no valid targets, resolve immediately
    if (validTargets.length === 0) {
      console.warn('animateStep: No valid targets for tween', {
        playerId: sprite?.playerId,
        action: step.action,
        tweenTargetsCount: tweenTargets.length,
        validTargetsCount: validTargets.length,
        spriteValid: sprite && sprite.scene && sprite.active !== false && !sprite.destroyed,
        ballValid: ballIsValid
      });
      tweenCompleted = true;
      clearTimeout(timeoutId);
      resolve();
      return;
    }
    
    // Check if distance is effectively zero (sprite already at target)
    const distance = Math.hypot(sprite.x - targetX, sprite.y - targetY);
    if (distance < 1) {
      // Sprite is already at target, resolve immediately
      // Call onAction if needed (fire and forget for zero-distance moves)
      if (step.action && onAction) {
        try {
          onAction(step.action, sprite, step.timestamp);
        } catch (error) {
          console.error('animateStep: Error in onAction for zero-distance step', { error, playerId: sprite?.playerId });
        }
      }
      tweenCompleted = true;
      clearTimeout(timeoutId);
      emitSummary('complete');
      resolve();
      return;
    }

    // Track tween creation for debugging long pauses
    const tweenId = `tween_${sprite?.playerId}_${Date.now()}`;
    
    const tweenConfig = {
      targets: validTargets,
      x: targetX,
      y: targetY,
      duration,
      ease: "Linear",
      onStart: async () => {
        if (PLAYER_TWEEN_DEBUG || duration > 2000) {
          const team = sprite?.team_id ?? sprite?.team ?? null;
          console.log("animateStep: Tween started", {
            tweenId,
            playerId: sprite?.playerId ?? null,
            action: step.action,
            duration,
            team
          });
        }
        if (step.action && onAction) {
          if (PASS_DEBUG && step.action === 'pass') {
            console.log('passStart', { fromId: sprite?.playerId, timestamp: step.timestamp });
          }
          startPromise = onAction(step.action, sprite, step.timestamp);
          await startPromise;
        }
      },
      onUpdate: () => {
        // Ball position is now handled by tween targets, but keep this as fallback
        // for cases where ball might not be in targets array
        if (
          currentBallOwnerRef?.value === sprite &&
          ballSprite?.setPosition &&
          !getPendingOwner(scene) &&
          !tweenTargets.includes(ballSprite)
        ) {
          ballSprite.setPosition(sprite.x, sprite.y);
        }
      },
      onComplete: async () => {
        if (tweenCompleted) {
          // Already resolved via timeout, don't resolve again
          return;
        }
        tweenCompleted = true;
        clearTimeout(timeoutId);
        if (duration > 2000) {
          console.log('animateStep: Tween completed', {
            tweenId,
            playerId: sprite?.playerId,
            action: step.action,
            duration
          });
        }
        try {
          await startPromise;
        } catch (error) {
          console.error('animateStep: Error in startPromise', { error, playerId: sprite?.playerId });
        }
        emitSummary('complete');
        resolve();
      },
      onStop: async () => {
        if (tweenCompleted) {
          // Already resolved via timeout, don't resolve again
          return;
        }
        tweenCompleted = true;
        clearTimeout(timeoutId);
        try {
          await startPromise;
        } catch (error) {
          console.error('animateStep: Error in startPromise', { error, playerId: sprite?.playerId });
        }
        emitSummary('stop');
        resolve();
      }
    };
    
    // Log tween creation for debugging
    if (duration > 4000) {
      console.warn('animateStep: Creating tween with unusually long duration', {
        playerId: sprite?.playerId,
        action: step.action,
        duration,
        distance: Math.hypot(sprite.x - targetX, sprite.y - targetY),
        from: { x: sprite.x, y: sprite.y },
        to: { x: targetX, y: targetY }
      });
    }
    
    tween = scene.tweens.add(tweenConfig);
    tween._animateStepId = tweenId;
    
    // Verify tween was created and started
    if (!tween) {
      console.error('animateStep: Failed to create tween', {
        playerId: sprite?.playerId,
        action: step.action,
        validTargetsCount: validTargets.length
      });
      tweenCompleted = true;
      clearTimeout(timeoutId);
      resolve();
      return;
    }
    
    // Ensure tween starts immediately (Phaser tweens should auto-start, but verify)
    // Check if tween manager is paused or if tween needs explicit start
    if (scene.tweens && typeof scene.tweens.isPaused === 'function' && scene.tweens.isPaused()) {
      console.warn('animateStep: Tween manager is paused!', {
        playerId: sprite?.playerId,
        action: step.action
      });
    }
    
    // Verify tween is actually playing after creation
    let tweenStarted = false;
    if (typeof tween.isPlaying === 'function') {
      tweenStarted = tween.isPlaying();
    }
    
    if (!tweenStarted && typeof tween.play === 'function') {
      tween.play();
      // Verify it started
      if (typeof tween.isPlaying === 'function') {
        tweenStarted = tween.isPlaying();
      }
      
      // Log if we had to manually start it (especially for receive actions which are problematic)
      if (!tweenStarted || step.action === 'receive' || step.action === 'guard_ball') {
        console.warn('animateStep: Tween not playing after creation/play()', {
          playerId: sprite?.playerId,
          action: step.action,
          wasPlaying: false,
          nowPlaying: tweenStarted,
          tweenState: {
            isPlaying: typeof tween.isPlaying === 'function' ? tween.isPlaying() : 'N/A',
            isPaused: typeof tween.isPaused === 'function' ? tween.isPaused() : 'N/A',
            progress: tween.progress,
            totalProgress: tween.totalProgress
          },
          spriteState: {
            active: sprite?.active,
            visible: sprite?.visible,
            x: sprite?.x,
            y: sprite?.y
          }
        });
      }
    }
    
    // For receive/guard_ball actions specifically, add a safety check after a short delay
    // These actions are prone to getting stuck, so we monitor them more closely
    if (step.action === 'receive' || step.action === 'guard_ball') {
      let checkCount = 0;
      const maxChecks = 10; // Check 10 times over 1 second
      const checkInterval = scene.time.addEvent({
        delay: 100,
        repeat: maxChecks - 1,
        callback: () => {
          checkCount++;
          if (tweenCompleted) {
            checkInterval.destroy();
            return;
          }
          
          const isPlaying = typeof tween.isPlaying === 'function' ? tween.isPlaying() : false;
          const progress = tween?.progress || 0;
          
          if (!isPlaying && progress === 0 && checkCount >= 3) {
            // Tween still not playing after 300ms, try to force it
            console.warn(`animateStep: ${step.action} tween still not playing after ${checkCount * 100}ms, forcing start`, {
              playerId: sprite?.playerId,
              action: step.action,
              checkCount,
              tweenProgress: progress,
              isPlaying
            });
            
            // Try multiple methods to start the tween
            if (typeof tween.play === 'function') {
              tween.play();
            }
            if (typeof tween.restart === 'function') {
              tween.restart();
            }
            
            // If still not playing after all attempts, resolve to prevent infinite wait
            if (checkCount >= maxChecks) {
              console.error(`animateStep: ${step.action} tween failed to start after ${maxChecks * 100}ms, forcing resolve`, {
                playerId: sprite?.playerId,
                action: step.action
              });
              if (tween) {
                scene.tweens?.killTweensOf(tween);
              }
              tweenCompleted = true;
              clearTimeout(timeoutId);
              resolve();
              checkInterval.destroy();
            }
          } else if (isPlaying || progress > 0) {
            // Tween is working, stop checking
            checkInterval.destroy();
          }
        }
      });
    }
    
    if (duration > 2000 || Math.hypot(sprite.x - targetX, sprite.y - targetY) > 500) {
      console.log('animateStep: Created tween', {
        tweenId,
        playerId: sprite?.playerId,
        action: step.action,
        duration,
        distance: Math.hypot(sprite.x - targetX, sprite.y - targetY),
        from: { x: sprite.x, y: sprite.y },
        to: { x: targetX, y: targetY },
        isPlaying: tween.isPlaying(),
        isPaused: tween.isPaused ? tween.isPaused() : 'N/A'
      });
    }

    if (scene.skipToEnd) {
      tween.stop();
    }
  });
}



// import { gridToPixels } from "../utils/gridToPixels.js";

// /**
//  * Animates a player's movement over time using chained tweens.
//  * Resolves only after the final tween completes.
//  *
//  * @param {object} scene - The Phaser scene
//  * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
//  * @param {Array} movement - Array of movement steps
//  * @param {Function} onAction - Callback for animation events
//  * @param {Phaser.GameObjects.Sprite} ballSprite - Ball sprite to attach when possessed
//  * @param {Array} hasBallAtStep - Boolean array mapping possession per step
//  * @param {string} position - Position label (e.g. PG, SG)
//  * @param {object} currentBallOwnerRef - A shared ref passed from playTurnAnimation
//  * @returns {Promise}
//  */
// export function animateMovementSequence({ 
//   scene, 
//   sprite, 
//   movement, 
//   onAction, 
//   ballSprite, 
//   hasBallAtStep, 
//   position, 
//   currentBallOwnerRef 
// }) {
//   return new Promise((resolve) => {
//     if (!movement || movement.length < 2) return resolve();

//     let stepIndex = 1;

//     const animateNextStep = () => {
//       if (stepIndex >= movement.length) return resolve();

//       const prev = movement[stepIndex - 1];
//       const curr = movement[stepIndex];
//       const duration = (curr.timestamp - prev.timestamp) * 3;

//       const { x: targetX, y: targetY } = gridToPixels(
//         curr.coords.x,
//         curr.coords.y,
//         scene.game.config.width,
//         scene.game.config.height
//       );

//       const ownsBallThisStep = hasBallAtStep?.[stepIndex] === true;

//       // If this player owns the ball this step, set them as the current owner
//       if (ownsBallThisStep) {
//         currentBallOwnerRef.value = sprite;
//         if (ballSprite?.setVisible) {
//           ballSprite.setVisible(true);
//         }
//       }

//       scene.tweens.add({
//         targets: [sprite],
//         x: targetX,
//         y: targetY,
//         duration,
//         ease: "Linear",
//         onStart: () => {
//           if (onAction) onAction(curr.action, sprite, curr.timestamp);
//         },
//         onUpdate: () => {
//           // Only the current owner gets to update the ball
//           if (currentBallOwnerRef.value === sprite && ballSprite?.setPosition) {
//             ballSprite.setPosition(sprite.x, sprite.y);
//           }
//         },
//         onComplete: () => {
//           stepIndex++;
//           animateNextStep();
//         }
//       });
//     };

//     // Handle step 0 before any tween begins
//     if (hasBallAtStep?.[0]) {
//       currentBallOwnerRef.value = sprite;
//       if (ballSprite?.setPosition && ballSprite?.setVisible) {
//         ballSprite.setPosition(sprite.x, sprite.y);
//         ballSprite.setVisible(true);
//       } else {
//         console.warn("⚠️ ballSprite not ready at step 0 lock.");
//       }
//     }

//     animateNextStep();
//   });
// }
