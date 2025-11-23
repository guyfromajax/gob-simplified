import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import animationConfig from "./animation_config.js";
import {
  setCurrentOwner,
  clearCurrentOwner,
  getCurrentOwner,
  getLastKnownOwner,
  setPendingOwner,
  cancelBallTween,
  getPendingOwner,
} from "../ball/ballController.js";
import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import { getBallController, attachBallToPlayer as attachBallToPlayerAdapter } from './BallControllerAdapter.js';
// ✅ NEW (Step 1): Import simple ball holder state functions
// ✅ STEP 3 MIGRATION: Import new ball animation function
import {
  clearBallHolder,
  setBallHolderId,
  animateBallToPosition,
} from "./ballAnimationSimple.js";

const BALL_DEPTH = 1000;
export const PASS_DEBUG = false;

// Animation speed constants (pixels per second)
// Based on learnings from WIP_GOB repository for smooth, consistent animations
// Speed can be changed dynamically via gameSpeedManager
const DEFAULT_BALL_SPEED = 350; // Default speed (Normal preset)
const MAX_BALL_DURATION = 1000; // ms - cap for very long passes

/**
 * Get current ball speed (can be changed dynamically)
 * @returns {number} Speed in pixels per second
 */
function getBallSpeed() {
  // Check for dynamic speed from gameSpeedManager
  if (typeof window !== 'undefined' && window.__GAME_SPEED) {
    return window.__GAME_SPEED;
  }
  return DEFAULT_BALL_SPEED;
}

/**
 * Calculate ball movement duration based on distance from current position to target
 * This ensures consistent pass speeds regardless of distance
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
  
  // Validate positions - if invalid, return default
  if (isNaN(currentX) || isNaN(currentY) || isNaN(targetX) || isNaN(targetY)) {
    console.warn('getBallDuration: Invalid positions, using default 300ms', {
      currentX, currentY, targetX, targetY
    });
    return 300;
  }
  
  const distance = Phaser.Math.Distance.Between(currentX, currentY, targetX, targetY);
  
  // If distance is 0 or very small, use minimum duration
  if (distance < 1) {
    return 50; // Minimum duration for very short distances
  }
  
  const speed = getBallSpeed();
  const duration = (distance / speed) * 1000; // Convert to milliseconds
  // Clamp between 50ms (minimum) and MAX_BALL_DURATION (maximum)
  const clampedDuration = Math.min(MAX_BALL_DURATION, Math.max(50, duration));
  
  // Final validation - ensure we return a valid number
  if (isNaN(clampedDuration) || clampedDuration <= 0) {
    console.warn('getBallDuration: Invalid calculated duration, using default 300ms', {
      distance, duration, clampedDuration
    });
    return 300;
  }
  
  return clampedDuration;
}

function resolveBallController(scene) {
  if (scene?.ballController) {
    return scene.ballController;
  }
  try {
    return getBallController();
  } catch (err) {
    return null;
  }
}

/**
 * ✅ PHASE 3.1: Removed local attachBallToPlayer function
 * Now using attachBallToPlayer from BallControllerAdapter.js
 * All call sites updated to use attachBallToPlayerAdapter
 */

/**
 * ✅ PHASE 4: Removed startBallFollowing() and stopBallFollowing() functions
 * BallController now handles ball following internally via startFollowingPlayer()/stopFollowingPlayer()
 * Old _ballFollowing system has been removed
 */

/**
 * Detach ball from any player and optionally hide it.
 * Currently just clears active tweens and ownership reference.
 */
export function detachBall(scene, ballSprite) {
  if (!scene || !ballSprite) return;
  
  // ✅ PHASE 4: Removed old ball following system - BallController handles following internally
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);
}

/**
 * Tween the ball to a specific position. Returns a promise that resolves when tween completes.
 * Supports optional arc motion via quadratic bezier.
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {{x:number, y:number}} target
 * @param {{duration?:number, easing?:string, arc?:{height?:number}|boolean}} opts
 */
// ✅ LEGACY CODE COMMENTED OUT: Replaced by animateBallToPosition() in ballAnimationSimple.js
// This function is no longer used - all call sites have been migrated to the new system
// Kept for reference only - can be removed after full validation
/*
export function tweenBallTo(scene, ballSprite, target, opts = {}) {
  if (!scene || !ballSprite || !target) return Promise.resolve();
  const { duration = 300, easing = 'Linear', arc } = opts;
  
  // ✅ PHASE 4: Removed old ball following system - BallController handles following internally
  
  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  ballSprite.setDepth(BALL_DEPTH);
  ballSprite.setVisible(true);

  const ballController = resolveBallController(scene);
  let controllerStartedFlight = false;
  if (ballController && !ballController.isInFlight) {
    const flightOpts = { duration, ease: easing };
    controllerStartedFlight = ballController.startFlight(target, flightOpts) !== false;
  }

  return new Promise((resolve, reject) => {
    const arcEnabled =
      !!arc &&
      !(
        typeof arc === 'object' &&
        Object.prototype.hasOwnProperty.call(arc, 'enabled') &&
        arc.enabled === false
      );

    if (arcEnabled) {
      const startX = ballSprite.x;
      const startY = ballSprite.y;
      const controlX = (startX + target.x) / 2;
      const hasHeightProp =
        typeof arc === 'object' && Object.prototype.hasOwnProperty.call(arc, 'height');
      const height = hasHeightProp && arc.height != null && arc.height !== false ? arc.height : 50;
      const controlY = Math.min(startY, target.y) - height;
      const curve = new Phaser.Curves.QuadraticBezier(
        new Phaser.Math.Vector2(startX, startY),
        new Phaser.Math.Vector2(controlX, controlY),
        new Phaser.Math.Vector2(target.x, target.y)
      );
      const progress = { t: 0 };
      const tween = scene.tweens.add({
        targets: progress,
        t: 1,
        duration,
        ease: easing,
        onUpdate: () => {
          const p = curve.getPoint(progress.t);
          ballSprite.setPosition(p.x, p.y);
        },
        onComplete: () => {
          if (controllerStartedFlight && ballController) {
            ballController.endFlight(null, { keepVisible: true });
          }
          resolve();
        }
      });
      tween?.once?.('stop', () => reject(new Error('tween stopped')));
    } else {
      const tween = scene.tweens.add({
        targets: ballSprite,
        x: target.x,
        y: target.y,
        duration,
        ease: easing,
        onComplete: () => {
          if (controllerStartedFlight && ballController) {
            ballController.endFlight(null, { keepVisible: true });
          }
          resolve();
        }
      });
      tween?.once?.('stop', () => reject(new Error('tween stopped')));
    }
  });
}
*/

/**
 * Tween a player sprite to a target position. If the player currently has the
 * ball attached, keep the ball in sync during the movement.
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Sprite} sprite
 * @param {{x:number,y:number}} target
 * @param {{duration?:number, easing?:string}} opts
 */
export function tweenPlayerTo(scene, sprite, target, opts = {}) {
  if (!scene || !sprite || !target) return Promise.resolve();
  const { duration = 300, easing = 'Linear' } = opts;

  return new Promise((resolve, reject) => {
    const startPosition = { x: sprite.x, y: sprite.y };
    const plannedDistance = Math.hypot(target.x - startPosition.x, target.y - startPosition.y);
    let settled = false;

    const finalize = (status, err) => {
      if (settled) return;
      settled = true;
      if (isAnimationDebugEnabled()) {
        const ownerId = getCurrentOwner(scene);
        const pendingOwnerId = getPendingOwner(scene);
        const actualDistance = Math.hypot(sprite.x - startPosition.x, sprite.y - startPosition.y);
        const summary = {
          type: 'tweenPlayerTo',
          status,
          playerId: sprite?.playerId ?? null,
          duration,
          easing,
          plannedDistance,
          actualDistance,
          ownerId,
          pendingOwnerId,
          passInFlight: !!scene?.passInFlight,
          ballDetached: !!scene?.ballDetached,
          scoreDelta: scene?.__debugScoreDelta ?? null,
          start: startPosition,
          target: { x: target.x, y: target.y },
          final: { x: sprite.x, y: sprite.y },
        };
        animationDebugLog('ANIM tween summary', summary);
        const tolerance = 2;
        if (actualDistance - plannedDistance > tolerance) {
          animationDebugWarn('ANIM teleport suspicion', {
            playerId: sprite?.playerId ?? null,
            plannedDistance,
            actualDistance,
            start: startPosition,
            target,
          });
        }
      }
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    };

    const tween = scene.tweens.add({
      targets: sprite,
      x: target.x,
      y: target.y,
      duration,
      ease: easing,
      onUpdate: () => {
        const ballSprite = scene.ballSprite;
        if (
          ballSprite &&
          getCurrentOwner(scene) === sprite.playerId &&
          ballSprite.setPosition
        ) {
          ballSprite.setPosition(sprite.x, sprite.y);
          ballSprite.setVisible(true);
        }
      },
      onComplete: () => finalize('complete')
    });
    tween?.once?.('stop', () => finalize('stop', new Error('tween stopped')));
  });
}

/**
 * Execute a full pass animation between players or coordinates.
 * Uses scene.ballSprite and scene.playerSprites to resolve sprites by id.
 * @param {Phaser.Scene} scene
 * @param {{fromId?:string|number, toId?:string|number, startCoords?:{x:number,y:number}, endCoords?:{x:number,y:number}, duration?:number, easing?:string}} cfg
 */
export async function runPass(scene, cfg = {}) {
  if (!scene) return;
  const { fromId, toId, startCoords, endCoords, duration, easing } = cfg;
  // Duration will be calculated based on distance if not explicitly provided
  // This ensures consistent pass speeds (based on WIP_GOB learnings)
  const usedEasing = easing ?? 'Linear';
  const deferOwnership = typeof cfg.onComplete === 'function';
  const ballSprite = scene.ballSprite;
  if (!ballSprite) return;
  const fromSprite = fromId != null ? scene.playerSprites?.[fromId] : null;
  const toSprite = toId != null ? scene.playerSprites?.[toId] : null;

  const frame = scene.game?.loop?.frame ?? 0;
  const key = `${fromId ?? ''}-${toId ?? ''}`;

  if (scene.__activePass && scene.__activePass.key === key && scene.__activePass.frame === frame) {
    if (PASS_DEBUG) animationDebugLog('duplicate runPass ignored', { fromId, toId, frame });
    return Promise.resolve();
  }

  if (scene.__activePass) {
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
    const lastId = getLastKnownOwner(scene);
    const lastSprite = lastId != null ? scene.playerSprites?.[lastId] : null;
    if (lastSprite) {
      attachBallToPlayerAdapter(scene, ballSprite, lastSprite);
    }
    scene.__activePass.reject?.(new Error('pass cancelled'));
    scene.__activePass = null;
  }

  cancelBallTween(scene, ballSprite);
  // ✅ PHASE 4: Check BallController state instead of old ballDetached flag
  const ballController = getBallController();
  if (ballController && !ballController.isAttached && !ballController.isInFlight && getLastKnownOwner(scene) != null) {
    const owner = scene.playerSprites?.[getLastKnownOwner(scene)];
    if (owner) attachBallToPlayerAdapter(scene, ballSprite, owner);
  }

  let resolveFn, rejectFn;
  const promise = new Promise((resolve, reject) => {
    resolveFn = resolve;
    rejectFn = reject;
  });
  scene.__activePass = { key, frame, promise, reject: rejectFn };

  scene.passInFlight = true;
  if (!deferOwnership) setPendingOwner(scene, toId);
  
  // ✅ PHASE 2.4: Use BallController lifecycle method for pass start
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  if (ballController) {
    ballController.onPassStart({ 
      passerId: fromId, 
      receiverId: toId 
    });
  }
  
  // ✅ PROACTIVE STATE MANAGEMENT: Clear ball holder state when pass starts
  // This ensures ball holder state reflects reality (ball is in flight, not with any player)
  // This prevents conflicts where passer's tween might still include ball
  clearBallHolder(scene);

  let startPosition = null;
  let endPosition = null;
  let plannedDistance = 0;
  let summaryEmitted = false;
  // Duration will be calculated after we know the end position
  // Initialize with provided duration or default, will be updated with distance-based calculation
  let usedDuration = duration ?? 300;
  const emitSummary = (status, extra = {}) => {
    if (summaryEmitted) return;
    summaryEmitted = true;
    if (!isAnimationDebugEnabled()) return;
    const ownerId = getCurrentOwner(scene);
    const pendingOwnerId = getPendingOwner(scene);
    const finalPosition = { x: ballSprite.x, y: ballSprite.y };
    const actualDistance = startPosition
      ? Math.hypot(finalPosition.x - startPosition.x, finalPosition.y - startPosition.y)
      : 0;
    const summary = {
      type: 'pass',
      status,
      fromId,
      toId,
      duration: usedDuration,
      easing: usedEasing,
      plannedDistance,
      actualDistance,
      ownerId,
      pendingOwnerId,
      passInFlight: !!scene.passInFlight,
      ballDetached: !!scene.ballDetached,
      scoreDelta: scene.__debugScoreDelta ?? null,
      start: startPosition,
      target: endPosition,
      final: finalPosition,
      ...extra,
    };
    animationDebugLog('ANIM pass summary', summary);
    const tolerance = 2;
    if (plannedDistance && actualDistance - plannedDistance > tolerance) {
      animationDebugWarn('ANIM teleport suspicion', {
        fromId,
        toId,
        plannedDistance,
        actualDistance,
        start: startPosition,
        target: endPosition,
      });
    }
  };

  (async () => {
    try {
      scene.events?.emit('passStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
      if (PASS_DEBUG) animationDebugLog('passStart', { fromId, toId, duration: usedDuration, easing: usedEasing });

      if (fromSprite) {
        attachBallToPlayerAdapter(scene, ballSprite, fromSprite);
        if (startCoords) {
          ballSprite.setPosition(startCoords.x, startCoords.y);
        }
      } else if (startCoords) {
        if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
        ballSprite.setPosition(startCoords.x, startCoords.y);
        ballSprite.setVisible(true);
        ballSprite.setDepth(BALL_DEPTH);
      }

      if (!startPosition) {
        startPosition = { x: ballSprite.x, y: ballSprite.y };
      }

      // Capture ball position BEFORE detaching (detach might change position)
      const ballStartX = ballSprite.x;
      const ballStartY = ballSprite.y;

      detachBall(scene, ballSprite);
      // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
      scene.events?.emit('ballDetached');
      if (PASS_DEBUG) animationDebugLog('detach(A)', { fromId });

      const end = endCoords || (toSprite ? { x: toSprite.x, y: toSprite.y } : null);
      if (!end) {
        emitSummary('skipped');
        resolveFn();
        return;
      }
      endPosition = { ...end };
      if (startPosition) {
        plannedDistance = Math.hypot(end.x - startPosition.x, end.y - startPosition.y);
      }
      
      // Calculate duration based on distance if not explicitly provided
      // Use startPosition (captured before detach) for accurate calculation
      if (!duration) {
        // Validate positions
        if (!startPosition || isNaN(startPosition.x) || isNaN(startPosition.y) || isNaN(end.x) || isNaN(end.y)) {
          console.warn('runPass: Invalid positions for duration calculation, using default 300ms', {
            startPosition, end
          });
          usedDuration = 300;
        } else {
          // Calculate distance from startPosition to end
          const distance = Phaser.Math.Distance.Between(startPosition.x, startPosition.y, end.x, end.y);
          
          // If distance is 0 or very small, use minimum duration
          if (distance < 1) {
            usedDuration = 50;
          } else {
            // Calculate duration based on distance
            const speed = getBallSpeed();
            const calculatedDuration = (distance / speed) * 1000;
            const clampedDuration = Math.min(MAX_BALL_DURATION, Math.max(50, calculatedDuration));
            
            // Validate duration
            if (clampedDuration && clampedDuration > 0 && !isNaN(clampedDuration)) {
              usedDuration = clampedDuration;
            } else {
              console.warn('runPass: Invalid duration calculated, using default 300ms', {
                distance, calculatedDuration, clampedDuration
              });
              usedDuration = 300;
            }
          }
        }
      }

      const doTween = animationConfig.enableBallTween !== false;
      if (doTween) {
        scene.events?.emit('tweenStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
        if (PASS_DEBUG) animationDebugLog('tweenStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
        // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of tweenBallTo()
        // animateBallToPosition() gets ballSprite from scene.ballSprite internally
        await animateBallToPosition(scene, end, { duration: usedDuration, easing: usedEasing });
        scene.events?.emit('tweenEnd', { toId });
        if (PASS_DEBUG) animationDebugLog('tweenEnd', { toId });
      } else {
        scene.events?.emit('tweenStart', { fromId, toId, skipped: true });
        if (PASS_DEBUG) animationDebugLog('tweenStart', { fromId, toId, skipped: true });
        if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
        ballSprite.setPosition(end.x, end.y);
        ballSprite.setVisible(true);
        ballSprite.setDepth(BALL_DEPTH);
        scene.events?.emit('tweenEnd', { toId, skipped: true });
        if (PASS_DEBUG) animationDebugLog('tweenEnd', { toId, skipped: true });
      }
      if (toSprite) {
        // ✅ PHASE 2.4: Use BallController lifecycle method for pass end
        if (ballController) {
          ballController.onPassEnd(toSprite, { reason: 'pass_complete' });
        } else {
          // Fallback to direct attachment if BallController not available
          attachBallToPlayerAdapter(scene, ballSprite, toSprite);
        }
        if (scene.currentBallOwnerRef) {
          scene.currentBallOwnerRef.value = toSprite;
        }
        // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
        
        // ✅ NOTE: Don't set ball holder state here for "receive" actions
        // The receiver's "receive" action step will set it after the receive tween completes
        // Setting it here causes the receive tween to include ball in targets, which conflicts with pass cleanup
        // Only set it if this isn't a receive action (e.g., inbound passes, outlet passes)
        // For regular passes, the receive action will handle setting the state
        // For now, we'll set it conditionally - receive actions handle their own state
        // We can detect if this is a receive pass by checking if passInFlight will be cleared soon
        // Actually, simpler: only set it for non-receive passes, receive actions will handle their own state
        // For now, don't set it here - let the receive action handle it after its tween completes
      }

      scene.events?.emit('passEnd', { toId });
      if (PASS_DEBUG) animationDebugLog('passEnd', { toId });
      emitSummary('complete');
      cfg.onComplete?.();
      resolveFn();
    } catch (err) {
      const lastId = getLastKnownOwner(scene);
      const lastSprite = lastId != null ? scene.playerSprites?.[lastId] : null;
      if (lastSprite) {
        attachBallToPlayerAdapter(scene, ballSprite, lastSprite);
      }
      emitSummary('error', { error: err?.message });
      rejectFn(err);
    } finally {
      if (scene.__activePass && scene.__activePass.key === key && scene.__activePass.frame === frame) {
        scene.__activePass = null;
        scene.passInFlight = false;
        // Allow pending owner to persist so updateBallOwnership can consume it
      }
    }
  })();

  return promise;
}

// ✅ PHASE 3.1: Removed attachBallToPlayer from exports (now using BallControllerAdapter)
// ✅ NOTE: tweenBallTo removed from default export (legacy code - replaced by animateBallToPosition)
export default {
  detachBall,
  // tweenBallTo, // ✅ REMOVED: Legacy code - replaced by animateBallToPosition() in ballAnimationSimple.js
  tweenPlayerTo,
  runPass
};
