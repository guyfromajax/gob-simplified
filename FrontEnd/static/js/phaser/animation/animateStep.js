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
    // Safety timeout: if tween doesn't complete within reasonable time, force resolve
    const timeoutMs = Math.max(duration * 2, 5000); // At least 2x duration or 5 seconds
    const timeoutId = setTimeout(() => {
      console.warn('animateStep: Timeout - forcing resolve', {
        playerId: sprite?.playerId,
        action: step.action,
        duration,
        timeoutMs
      });
      if (tween) {
        scene.tweens?.killTweensOf(tween);
      }
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
      clearTimeout(timeoutId);
      resolve();
      return;
    }

    tween = scene.tweens.add({
      targets: validTargets,
      x: targetX,
      y: targetY,
      duration,
      ease: "Linear",
      onStart: async () => {
        if (PLAYER_TWEEN_DEBUG) {
          const team = sprite?.team_id ?? sprite?.team ?? null;
          console.log("player:tweenStart", {
            type: "playerTweenStart",
            shooterId: null,
            reboundSpot: null,
            playerId: sprite?.playerId ?? null,
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
        clearTimeout(timeoutId);
        await startPromise;
        emitSummary('complete');
        resolve();
      },
      onStop: async () => {
        clearTimeout(timeoutId);
        await startPromise;
        emitSummary('stop');
        resolve();
      }
    });

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
