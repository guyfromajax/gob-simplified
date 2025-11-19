/**
 * Simple Ball Animation System (WIP_GOB Approach)
 * 
 * This module provides simple ball holder state tracking and helper functions
 * based on the WIP_GOB approach. It uses a single source of truth (string ID)
 * instead of multiple competing systems.
 * 
 * Key Principles:
 * - Ball holder stored as simple string ID (playerId) on scene
 * - Ball and player included in same tween targets when player has ball
 * - No update callbacks or following systems needed
 * - Distance-based duration for consistent speeds
 * 
 * Steps:
 * - Step 1: Ball holder state tracking (initializeBallHolderState, getBallHolderId, etc.)
 * - Step 2: Ball attachment via conditional target arrays (getPlayerTweenTargets)
 * - Step 3: Simple ball movement functions (animateBallToPosition, animateBallToPlayer)
 */

import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js';
// Lazy import detachBall to avoid circular dependency (imported dynamically in animateShotToRim)

/**
 * Initialize ball holder state on scene
 * @param {Phaser.Scene} scene - The Phaser scene
 */
export function initializeBallHolderState(scene) {
  if (!scene.gameState) {
    scene.gameState = {};
  }
  if (scene.gameState.ballHolder === undefined) {
    scene.gameState.ballHolder = null; // String ID of player who has the ball
  }
}

/**
 * Get the current ball holder ID (string)
 * @param {Phaser.Scene} scene - The Phaser scene
 * @returns {string|null} Player ID who has the ball, or null
 */
export function getBallHolderId(scene) {
  if (!scene.gameState) {
    return null;
  }
  return scene.gameState.ballHolder || null;
}

/**
 * Set the current ball holder ID (string)
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {string|null} playerId - Player ID who has the ball, or null to clear
 */
export function setBallHolderId(scene, playerId) {
  if (!scene.gameState) {
    scene.gameState = {};
  }
  scene.gameState.ballHolder = playerId || null;
}

/**
 * Clear the ball holder state
 * @param {Phaser.Scene} scene - The Phaser scene
 */
export function clearBallHolder(scene) {
  if (scene.gameState) {
    scene.gameState.ballHolder = null;
  }
}

/**
 * Check if a player is the ball holder
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {string} playerId - Player ID to check
 * @returns {boolean} True if this player is the ball holder
 */
export function isBallHolder(scene, playerId) {
  return getBallHolderId(scene) === playerId;
}

/**
 * Get ball holder sprite from player sprites map
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Object} playerSprites - Map of playerId → sprite
 * @returns {Object|null} { sprite, jerseyNo, ballSprite, ballShadowSprite } or null
 */
export function getBallHolderSprite(scene, playerSprites) {
  const ballHolderId = getBallHolderId(scene);
  if (!ballHolderId) {
    return null;
  }
  
  const sprite = playerSprites[ballHolderId];
  if (!sprite) {
    return null;
  }
  
  const jerseyNo = sprite.jerseyNo || null;
  const ballSprite = scene.ballSprite || null;
  const ballShadowSprite = scene.ballShadowSprite || null;
  
  return { sprite, jerseyNo, ballSprite, ballShadowSprite };
}

/**
 * Get tween targets array for a player (includes ball/shadow if player has ball)
 * This is the KEY function that enables WIP_GOB approach - conditional target arrays
 * 
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Object} playerSprite - The player sprite
 * @param {Object|null} jerseyNo - The player's jersey number text sprite (optional)
 * @returns {Array} Array of targets for tween (player, jerseyNo, ball, ballShadow)
 */
export function getPlayerTweenTargets(scene, playerSprite, jerseyNo = null) {
  const targets = [];
  
  // Always include player sprite
  if (playerSprite) {
    targets.push(playerSprite);
  }
  
  // Include jersey number if provided
  if (jerseyNo) {
    targets.push(jerseyNo);
  }
  
  // If player has ball, include ball and shadow in targets
  // This makes Phaser keep them in sync automatically
  // ✅ SAFETY GUARDS: Don't include ball if pass is in flight OR BallController has flight in progress
  // This is defensive programming - even if state wasn't cleared proactively, this prevents conflicts
  const ballHolderId = getBallHolderId(scene);
  const playerId = playerSprite?.playerId || null;
  const passInFlight = scene.passInFlight === true;
  
  // Check if BallController has a flight in progress (passes, shots, rebounds, etc.)
  const ballControllerInFlight = scene.ballController?.isInFlight === true;
  
  if (ballHolderId && playerId === ballHolderId && !passInFlight && !ballControllerInFlight) {
    const ballSprite = scene.ballSprite;
    const ballShadowSprite = scene.ballShadowSprite;
    
    if (ballSprite && ballSprite.scene && ballSprite.active !== false && !ballSprite.destroyed) {
      targets.push(ballSprite);
    }
    if (ballShadowSprite && ballShadowSprite.scene && ballShadowSprite.active !== false && !ballShadowSprite.destroyed) {
      targets.push(ballShadowSprite);
    }
  }
  
  return targets;
}

// ==================== STEP 3: SIMPLE BALL MOVEMENT FUNCTIONS ====================

// Animation speed constants (pixels per second)
// Based on WIP_GOB approach for consistent speeds
// Ball speed: 350 pixels per second (can be changed dynamically via gameSpeedManager)
const DEFAULT_BALL_SPEED = 350;
const MAX_BALL_DURATION = 1000; // ms - cap for very long passes
const MIN_BALL_DURATION = 50; // ms - minimum duration
const BALL_DEPTH = 1000; // Depth for ball sprite

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
 * This ensures consistent ball speeds regardless of distance (WIP_GOB approach)
 * 
 * @param {Phaser.GameObjects.Image} ballSprite - The ball sprite
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @returns {number} Duration in milliseconds
 */
function calculateBallDuration(ballSprite, targetX, targetY) {
  if (!ballSprite) return 300; // Default fallback
  
  const currentX = ballSprite.x;
  const currentY = ballSprite.y;
  
  // Validate positions
  if (isNaN(currentX) || isNaN(currentY) || isNaN(targetX) || isNaN(targetY)) {
    console.warn('calculateBallDuration: Invalid positions, using default 300ms', {
      currentX, currentY, targetX, targetY
    });
    return 300;
  }
  
  const distance = Phaser.Math.Distance.Between(currentX, currentY, targetX, targetY);
  
  // If distance is 0 or very small, use minimum duration
  if (distance < 1) {
    return MIN_BALL_DURATION;
  }
  
  const speed = getBallSpeed();
  const duration = (distance / speed) * 1000; // Convert to milliseconds
  // Clamp between minimum and maximum
  const clampedDuration = Math.min(MAX_BALL_DURATION, Math.max(MIN_BALL_DURATION, duration));
  
  // Final validation
  if (isNaN(clampedDuration) || clampedDuration <= 0) {
    console.warn('calculateBallDuration: Invalid calculated duration, using default 300ms', {
      distance, duration, clampedDuration
    });
    return 300;
  }
  
  return clampedDuration;
}

/**
 * Get BallController instance from scene
 * @param {Phaser.Scene} scene - The Phaser scene
 * @returns {Object|null} BallController instance or null
 */
function getBallControllerFromScene(scene) {
  // Use scene.ballController (most common case - set up during scene creation)
  // If not available, BallController integration is skipped (functions still work)
  return scene?.ballController || null;
}

/**
 * Animate ball to a specific position (Step 3 - WIP_GOB approach)
 * 
 * Simple, clean function that animates the ball to a position using:
 * - Distance-based duration (consistent speeds)
 * - BallController integration (flight state management)
 * - Optional arc support via QuadraticBezier curve
 * 
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {{x: number, y: number}} targetPosition - Target position in pixels
 * @param {Object} options - Optional parameters
 * @param {number} options.duration - Duration in ms (if not provided, calculated from distance)
 * @param {string} options.easing - Easing function (default: 'Linear')
 * @param {Object|boolean} options.arc - Arc options: {height: number} or true/false (default: false)
 * @returns {Promise} Resolves when animation completes
 */
export async function animateBallToPosition(scene, targetPosition, options = {}) {
  if (!scene || !scene.ballSprite || !targetPosition) {
    return Promise.resolve();
  }
  
  const ballSprite = scene.ballSprite;
  const { duration, easing = 'Linear', arc } = options;
  
  // Calculate duration from distance if not provided
  const calculatedDuration = duration || calculateBallDuration(ballSprite, targetPosition.x, targetPosition.y);
  
  // Stop any existing tweens on the ball
  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
  }
  
  // Set up ball sprite
  ballSprite.setDepth(BALL_DEPTH);
  ballSprite.setVisible(true);
  
  // ✅ BALL CONTROLLER INTEGRATION: Start flight state
  // This ensures ball holder state is cleared and flight state is tracked
  const ballController = getBallControllerFromScene(scene);
  let controllerStartedFlight = false;
  if (ballController && !ballController.isInFlight) {
    const flightOpts = { duration: calculatedDuration, ease: easing };
    controllerStartedFlight = ballController.startFlight(targetPosition, flightOpts) !== false;
  }
  
  return new Promise((resolve, reject) => {
    // Check if arc is enabled
    const arcEnabled =
      !!arc &&
      !(
        typeof arc === 'object' &&
        Object.prototype.hasOwnProperty.call(arc, 'enabled') &&
        arc.enabled === false
      );

    if (arcEnabled) {
      // ✅ ARC SUPPORT: Use QuadraticBezier curve for arced motion
      const startX = ballSprite.x;
      const startY = ballSprite.y;
      const controlX = (startX + targetPosition.x) / 2;
      const hasHeightProp =
        typeof arc === 'object' && Object.prototype.hasOwnProperty.call(arc, 'height');
      const height = hasHeightProp && arc.height != null && arc.height !== false ? arc.height : 50;
      const controlY = Math.min(startY, targetPosition.y) - height;
      
      const curve = new Phaser.Curves.QuadraticBezier(
        new Phaser.Math.Vector2(startX, startY),
        new Phaser.Math.Vector2(controlX, controlY),
        new Phaser.Math.Vector2(targetPosition.x, targetPosition.y)
      );
      
      const progress = { t: 0 };
      const tween = scene.tweens.add({
        targets: progress,
        t: 1,
        duration: calculatedDuration,
        ease: easing,
        onUpdate: () => {
          const p = curve.getPoint(progress.t);
          ballSprite.setPosition(p.x, p.y);
        },
        onComplete: () => {
          // ✅ BALL CONTROLLER INTEGRATION: End flight state
          if (controllerStartedFlight && ballController) {
            ballController.endFlight(null, { keepVisible: true });
          }
          resolve();
        }
      });
      tween?.once?.('stop', () => reject(new Error('tween stopped')));
    } else {
      // ✅ STRAIGHT LINE: Simple tween for straight ball motion
      const tween = scene.tweens.add({
        targets: ballSprite,
        x: targetPosition.x,
        y: targetPosition.y,
        duration: calculatedDuration,
        ease: easing,
        onComplete: () => {
          // ✅ BALL CONTROLLER INTEGRATION: End flight state
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

/**
 * Animate ball to a player (Step 3 - WIP_GOB approach)
 * 
 * Simple, clean function that animates the ball to a player using:
 * - Distance-based duration (consistent speeds)
 * - BallController integration (flight state management)
 * - Simple Phaser tween (no complex arc logic)
 * 
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Object} playerSprite - The target player sprite
 * @param {Object} options - Optional parameters
 * @param {number} options.duration - Duration in ms (if not provided, calculated from distance)
 * @param {string} options.easing - Easing function (default: 'Linear')
 * @param {Object} options.offset - Offset from player position {x, y} (default: {x: 0, y: -10})
 * @returns {Promise} Resolves when animation completes
 */
export async function animateBallToPlayer(scene, playerSprite, options = {}) {
  if (!scene || !scene.ballSprite || !playerSprite) {
    return Promise.resolve();
  }
  
  const ballSprite = scene.ballSprite;
  const { duration, easing = 'Linear', offset = { x: 0, y: -10 } } = options;
  
  // Calculate target position (player position + offset)
  const targetPosition = {
    x: playerSprite.x + offset.x,
    y: playerSprite.y + offset.y
  };
  
  // Calculate duration from distance if not provided
  const calculatedDuration = duration || calculateBallDuration(ballSprite, targetPosition.x, targetPosition.y);
  
  // Stop any existing tweens on the ball
  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
  }
  
  // Set up ball sprite
  ballSprite.setDepth(BALL_DEPTH);
  ballSprite.setVisible(true);
  
  // ✅ BALL CONTROLLER INTEGRATION: Start flight state
  // This ensures ball holder state is cleared and flight state is tracked
  const ballController = getBallControllerFromScene(scene);
  let controllerStartedFlight = false;
  if (ballController && !ballController.isInFlight) {
    const flightOpts = { duration: calculatedDuration, ease: easing };
    controllerStartedFlight = ballController.startFlight(targetPosition, flightOpts) !== false;
  }
  
  return new Promise((resolve, reject) => {
    // Create simple tween (no arc support - can add later if needed)
    const tween = scene.tweens.add({
      targets: ballSprite,
      x: targetPosition.x,
      y: targetPosition.y,
      duration: calculatedDuration,
      ease: easing,
      onComplete: () => {
        // ✅ BALL CONTROLLER INTEGRATION: End flight state and attach to player
        if (controllerStartedFlight && ballController) {
          ballController.endFlight(playerSprite, { keepVisible: true });
          
          // ✅ STEP 1 INTEGRATION: Update ball holder state to new owner
          if (playerSprite?.playerId) {
            setBallHolderId(scene, playerSprite.playerId);
          }
        } else if (playerSprite?.playerId) {
          // If BallController wasn't used, still update ball holder state
          setBallHolderId(scene, playerSprite.playerId);
        }
        resolve();
      }
    });
    
    tween?.once?.('stop', () => reject(new Error('tween stopped')));
  });
}

/**
 * Animate shot to rim (high-level helper)
 * 
 * Handles ball detachment and shot animation - use this for all shot scenarios
 * (fast break shots, free throws, putbacks, etc.)
 * 
 * This is a high-level helper that:
 * - Detaches ball from player before animating
 * - Prevents ball from following player during shot
 * - Animates ball to rim with optional arc support
 * - Cleans up shot flags after animation completes
 * 
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {{x: number, y: number}} rimPosition - Rim position in pixels
 * @param {Object} options - Optional parameters (same as animateBallToPosition)
 * @param {number} options.duration - Duration in ms (if not provided, calculated from distance)
 * @param {string} options.easing - Easing function (default: 'Linear')
 * @param {Object|boolean} options.arc - Arc options: {height: number} or true/false (default: false)
 * @returns {Promise} Resolves when animation completes
 */
export async function animateShotToRim(scene, rimPosition, options = {}) {
  if (!scene || !scene.ballSprite || !rimPosition) {
    return Promise.resolve();
  }
  
  const ballSprite = scene.ballSprite;
  
  // ✅ DETACH BALL: Must detach ball from player before animating shot
  // Similar to shootBall() in ballManager.js - prevents ball from following player during shot
  // This ensures the ball animates to the rim instead of staying with the player
  // Use dynamic import to avoid circular dependency with ballTween.js
  let detachBall;
  try {
    const ballTweenModule = await import('./ballTween.js');
    detachBall = ballTweenModule.detachBall;
    detachBall(scene, ballSprite);
  } catch (err) {
    // Fallback: manual detachment if import fails (shouldn't happen, but defensive)
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
    if (scene.ballController && typeof scene.ballController.stopFollowingPlayer === 'function') {
      scene.ballController.stopFollowingPlayer();
    }
  }
  
  // Stop old ball following system
  scene.ballDetached = true;
  
  // Stop BallController from following player during shot
  if (scene.ballController) {
    if (typeof scene.ballController.stopFollowingPlayer === 'function') {
      scene.ballController.stopFollowingPlayer();
    }
    scene.ballController.isAttached = false;
    scene._shotInProgress = true; // Prevent re-attachment during shot
  }
  
  // Animate ball to rim
  await animateBallToPosition(scene, rimPosition, options);
  
  // Clear shot in progress flag after animation completes
  if (scene.ballController) {
    scene._shotInProgress = false;
  }
}

