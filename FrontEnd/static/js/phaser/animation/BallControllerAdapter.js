/**
 * BallController Adapter - Backward Compatibility Layer
 * 
 * This adapter makes the new BallController system backward compatible
 * with the old attachBallToPlayer function signature and behavior.
 * 
 * This allows gradual migration from the old system to the new system
 * without breaking existing code.
 */

import { BallController } from './BallController.js';
import { playerBallPos } from '../setup/markerConfig.js';

/**
 * Global BallController instance - single source of truth
 */
let globalBallController = null;

/**
 * Initialize the global BallController
 * This should be called once when the game scene is created
 */
function initializeBallController(scene, ballSprite) {
  if (globalBallController) {
    console.warn('BallControllerAdapter: Global BallController already initialized');
    return globalBallController;
  }
  
  globalBallController = new BallController(scene, ballSprite);
  globalBallController.debug = false; // Disable verbose debug logging by default
  
  console.log('BallControllerAdapter: Global BallController initialized');
  return globalBallController;
}

/**
 * Get the global BallController instance
 */
function getBallController() {
  if (!globalBallController) {
    console.error('BallControllerAdapter: Global BallController not initialized. Call initializeBallController() first.');
    return null;
  }
  return globalBallController;
}

/**
 * Backward compatible attachBallToPlayer function
 * 
 * This function maintains the exact same signature and behavior as the old
 * attachBallToPlayer function, but uses the new BallController internally.
 * 
 * @param {Phaser.Scene} scene - The game scene
 * @param {Phaser.GameObjects.Image} ballSprite - The ball sprite
 * @param {Phaser.GameObjects.Sprite} playerSprite - The player sprite to attach to
 * @param {Object} opts - Options object (depth, debugInfo, etc.)
 */
function attachBallToPlayer(scene, ballSprite, playerSprite, opts = {}) {
  const ballController = getBallController();
  
  if (!ballController) {
    console.error('BallControllerAdapter: Cannot attach ball - BallController not initialized');
    return;
  }
  
  const allowDuringPossessionFlip =
    opts?.allowDuringPossessionFlip === true || scene?.__drebOutletWindowActive === true;
  const targetPlayerId = playerSprite?.playerId;
  const isPutbackAttempt = opts?.debugInfo?.reason === 'putback_attempt';
  // Note: _putbackInProgress is never set anymore (Phase 4 cleanup), but kept for backward compatibility
  // This check will only be true if isPutbackAttempt is true
  const isPutbackScenario = scene._putbackInProgress || isPutbackAttempt;
  
  if (isPutbackAttempt || isPutbackScenario) {
    console.log('🔍 [BALL ATTACH DEBUG] attachBallToPlayer called', {
      targetPlayerId,
      reason: opts?.debugInfo?.reason || 'unknown',
      shotInProgress: scene._shotInProgress,
      sceneRebounderId: scene.rebounderId,
      ballDetached: scene.ballDetached,
      currentBallOwner: scene.currentBallOwnerRef?.value?.playerId || null,
      callStack: new Error().stack?.split('\n').slice(1, 5).map(s => s.trim())
    });
  }
  
  // BallController.attachToPlayer() handles all state checks internally

  // Handle possession flip in progress (old system behavior)
  if (scene.possessionFlipInProgress && !allowDuringPossessionFlip) {
    console.log('BallControllerAdapter: Skipping attach due to possessionFlipInProgress');
    return;
  }

  // Handle rebound state restrictions (old system behavior)
  if (scene.stateMachine?.is('Rebound') && playerSprite.playerId !== scene.rebounderId) {
    if (isPutbackScenario) {
      console.log('🔍 [BALL ATTACH DEBUG] BLOCKED: not the rebounder during rebound state', {
        targetPlayerId,
        sceneRebounderId: scene.rebounderId,
        state: scene.stateMachine?.state
      });
    } else {
      console.log('BallControllerAdapter: Skipping attach - not the rebounder during rebound state');
    }
    return;
  }

  // Handle possession flip restrictions (old system behavior)
  const targetTeamId = playerSprite.team_id;
  if (
    scene.possessionFlipInProgress &&
    !allowDuringPossessionFlip &&
    scene.offenseTeamId != null &&
    String(targetTeamId) !== String(scene.offenseTeamId)
  ) {
    const from = getCurrentOwner(scene);
    console.warn('BallControllerAdapter: Skipping attach due to possession flip', { 
      from: from?.playerId, 
      to: playerSprite.playerId, 
      reason: 'possessionFlipInProgress' 
    });
    return;
  }

  // Convert old system options to new system options
  const ballControllerOptions = {
    offset: { x: 0, y: 0 }, // Centered positioning
    debugInfo: opts.debugInfo || null
  };

  // Handle depth setting (old system behavior)
  if (opts.depth !== undefined) {
    if (ballSprite) {
      ballSprite.setDepth(opts.depth);
    }
  }

  // Use BallController to attach
  const success = ballController.attachToPlayer(playerSprite, ballControllerOptions);
  
  if (success) {
    // Update old system references for backward compatibility
    if (scene?.currentBallOwnerRef) {
      scene.currentBallOwnerRef.value = playerSprite;
    }
    
    // BallController manages state internally
    
    // Log for debugging (old system style)
    if (isPutbackAttempt || isPutbackScenario) {
      console.log('🔍 [BALL ATTACH DEBUG] SUCCESS: Ball attached', {
        targetPlayerId,
        reason: opts?.debugInfo?.reason || 'unknown',
        shotInProgress: scene._shotInProgress,
        sceneRebounderId: scene.rebounderId,
        currentBallOwner: scene.currentBallOwnerRef?.value?.playerId || null
      });
    } else if (opts.debugInfo) {
      console.log('BallControllerAdapter: Ball attached', {
        type: 'ballAttach',
        shooterId: opts.debugInfo.shooterId ?? null,
        reboundSpot: opts.debugInfo.reboundSpot ?? null,
        playerId: playerSprite.playerId,
        team: playerSprite.team_id ?? playerSprite.team ?? null
      });
    }
  } else {
    // Only log failures in debug mode or for putback attempts (which are edge cases)
    if (isPutbackAttempt || isPutbackScenario) {
      console.warn('🔍 [BALL ATTACH DEBUG] FAILED: Failed to attach ball', {
        targetPlayerId,
        reason: opts?.debugInfo?.reason || 'unknown',
        shotInProgress: scene._shotInProgress,
        sceneRebounderId: scene.rebounderId
      });
    }
    // Suppress normal "ball in flight" failures - this is expected behavior
  }
}

/**
 * Backward compatible detachBall function
 * 
 * @param {Phaser.Scene} scene - The game scene
 * @param {Phaser.GameObjects.Image} ballSprite - The ball sprite
 */
function detachBall(scene, ballSprite, options={}) {
  const ballController = getBallController();
  
  if (!ballController) {
    console.error('BallControllerAdapter: Cannot detach ball - BallController not initialized');
    return;
  }

  // Use BallController to detach
  ballController.detachFromPlayer('detach', options);
  
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
  // Removed verbose detachment logging
}

/**
 * Legacy tweenBallTo function removed (Phase 5 cleanup)
 * Replaced by animateBallToPosition() in ballAnimationSimple.js
 */

/**
 * Get current owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
function getCurrentOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getCurrentOwnerId();
}

/**
 * Set current owner by ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {string} playerId
 */
function setCurrentOwner(scene, playerId) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.setCurrentOwnerById(playerId);
}

/**
 * Clear current owner - replaces old ballController.js
 * @param {Phaser.Scene} scene
 */
function clearCurrentOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.clearCurrentOwner();
}

/**
 * Get last known owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
function getLastKnownOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getLastKnownOwnerId();
}

/**
 * Get pending owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
function getPendingOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getPendingOwnerId();
}

/**
 * Set pending owner by ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {string} playerId
 */
function setPendingOwner(scene, playerId) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.setPendingOwnerById(playerId);
}

/**
 * Clear pending owner - replaces old ballController.js
 * @param {Phaser.Scene} scene
 */
function clearPendingOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.clearPendingOwner();
}

/**
 * Cancel ball tween - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Sprite} ballSpriteOverride
 */
function cancelBallTween(scene, ballSpriteOverride) {
  const ballController = getBallController();
  if (!ballController) return;
  
  // Clear pending owner
  ballController.clearPendingOwner();
  
  // Kill ball tweens
  const ballSprite = ballSpriteOverride || scene.ballSprite;
  if (scene?.tweens && ballSprite) {
    scene.tweens.killTweensOf(ballSprite);
  }
}

/**
 * ✅ PHASE 2.9: State synchronization helper
 * Keeps old flags and new BallController state in sync during transition period
 * This prevents race conditions and inconsistent state
 * 
 * @param {Phaser.Scene} scene - The game scene
 * @param {Object} options - Options object
 * @param {boolean} options.clearShotState - Clear shot-related state
 * @param {boolean} options.clearPassState - Clear pass-related state
 * @param {boolean} options.clearPutbackState - Clear putback-related state
 * @param {boolean} options.allowAttachment - Whether to allow ball attachment after clearing
 */
function synchronizeBallState(scene, options = {}) {
  const ballController = getBallController();
  if (!ballController) return;
  
  const { 
    clearShotState = false, 
    clearPassState = false, 
    clearPutbackState = false,
    allowAttachment = true
  } = options;
  
  // Clear BallController state based on options
  if (clearShotState) {
    if (ballController.isInFlight && (ballController.reason === 'shot' || ballController.reason === 'putback_shot')) {
      ballController.onShotEnd();
    }
  }
  
  if (clearPassState) {
    if (ballController.isInFlight && ballController.reason === 'pass') {
      ballController.onPassEnd(null, { reason: 'sync_clear' });
    }
  }
  
  if (clearPutbackState) {
    if (ballController.reason === 'putback_shot') {
      ballController.onPutbackEnd();
    }
  }
  
  // ✅ PHASE 4: Removed old flag synchronization - flags are no longer used
  // BallController is now the single source of truth for ball state
  // All code should check BallController state directly instead of old flags
}

// Named exports for individual functions
// Note: updateBallOwnership is exported as a function declaration below, not included here
export {
  attachBallToPlayer,
  detachBall,
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner,
  getLastKnownOwner,
  getPendingOwner,
  setPendingOwner,
  clearPendingOwner,
  cancelBallTween,
  synchronizeBallState,
  initializeBallController,
  getBallController
};

/**
 * Unified ball ownership update function
 * Handles both timestamp-based and step-index-based updates
 * 
 * This function consolidates the three different updateBallOwnership implementations:
 * - ballManager.js: Timestamp-based lookup
 * - turnAnimation.js: Step-index based with pending owner handling
 * - ShotAnimationSystem.js: Step-index based with BallController direct usage
 * 
 * @param {Object} options
 * @param {Phaser.Scene} options.scene
 * @param {Phaser.GameObjects.Sprite} options.ballSprite
 * @param {Array} options.animations - Player animation data
 * @param {Object} options.playerSprites - Map of playerId -> sprite
 * @param {Object} [options.currentBallOwnerRef] - Reference object for current owner
 * @param {number} [options.stepIndex] - Step index (if provided, uses this)
 * @param {number} [options.currentTimestamp] - Timestamp in ms (if provided, calculates stepIndex)
 * @param {string} [options.offenseTeamId] - Offense team ID
 * @returns {Promise<void>}
 */
export async function updateBallOwnership(options) {
  const {
    scene,
    ballSprite,
    animations,
    playerSprites,
    currentBallOwnerRef,
    stepIndex: providedStepIndex,
    currentTimestamp,
    offenseTeamId
  } = options;

  // Early returns
  // Check for FastBreak state (using string comparison to avoid importing States)
  if (scene?.skipToEnd || scene?.stateMachine?.is?.('FastBreak') || scene?.stateMachine?.state === 'FastBreak') return;
  if (scene.passInFlight) return;

  // Get BallController
  const ballController = getBallController();
  if (ballController && !ballController.isAttached && !ballController.isInFlight) {
    return; // Ball is detached and not in flight, skip update
  }

  // Calculate stepIndex if timestamp provided
  let stepIndex = providedStepIndex;
  if (currentTimestamp !== undefined && stepIndex === undefined) {
    stepIndex = calculateStepIndexFromTimestamp(animations, currentTimestamp);
  }

  // Handle pending owner first (from turnAnimation.js logic)
  const pendingId = getPendingOwner(scene);
  if (pendingId != null) {
    const pendingSprite = playerSprites[pendingId];
    if (pendingSprite) {
      // Update ball position
      if (ballSprite?.setPosition) {
        const pendingPos = playerBallPos(pendingSprite);
        ballSprite.setPosition(pendingPos.x, pendingPos.y);
        ballSprite.setVisible(true);
      }

      // Update references
      if (currentBallOwnerRef) {
        currentBallOwnerRef.value = pendingSprite;
      }
      
      // Update BallController state
      setCurrentOwner(scene, pendingId);
      
      // Update WIP_GOB ball holder state
      const { setBallHolderId } = await import('./ballAnimationSimple.js');
      setBallHolderId(scene, pendingId);
      
      // Clear pending owner
      clearPendingOwner(scene);
    }
    return;
  }

  // Check if pass is happening at this step (from turnAnimation.js logic)
  if (stepIndex !== undefined) {
    // ✅ REFACTOR: Use unified passDetection.js for consistency
    const { detectPassAtStep } = await import('./passDetection.js');
    const passHappening = !!detectPassAtStep(animations, stepIndex);
    if (passHappening) return;
    
    // ✅ OLD CODE (commented out - replaced with unified passDetection.js):
    // const passHappening = animations.some(
    //   anim => anim.movement?.[stepIndex]?.action === "pass"
    // );
    // if (passHappening) return;
  }

  // Find player who should have ball at this step (unified logic)
  for (const anim of animations) {
    if (!anim.hasBallAtStep) continue;
    
    let hasBall = false;
    
    if (stepIndex !== undefined) {
      // Step-index based (turnAnimation.js, ShotAnimationSystem.js)
      hasBall = anim.hasBallAtStep[stepIndex];
    } else if (currentTimestamp !== undefined) {
      // Timestamp-based (ballManager.js)
      if (!anim.movement || !anim.movement.length) continue;
      
      // Find step index from timestamp
      let calculatedStepIndex = 0;
      while (
        calculatedStepIndex < anim.movement.length - 1 &&
        currentTimestamp >= anim.movement[calculatedStepIndex + 1].timestamp
      ) {
        calculatedStepIndex++;
      }
      hasBall = anim.hasBallAtStep[calculatedStepIndex];
    } else {
      // No step index or timestamp provided - skip
      continue;
    }
    
    if (hasBall) {
      const playerSprite = playerSprites[anim.playerId];
      if (!playerSprite) {
        if (ballSprite?.setVisible) ballSprite.setVisible(false);
        continue;
      }
      
      // Update ball position
      if (ballSprite?.setPosition) {
        const holderPos = playerBallPos(playerSprite);
        ballSprite.setPosition(holderPos.x, holderPos.y);
        ballSprite.setVisible(true);
      }

      // Update references
      if (currentBallOwnerRef) {
        currentBallOwnerRef.value = playerSprite;
      }
      
      // Attach ball using BallController (unified approach)
      attachBallToPlayer(scene, ballSprite, playerSprite);
      
      // Update WIP_GOB ball holder state
      if (playerSprite.playerId) {
        const { setBallHolderId } = await import('./ballAnimationSimple.js');
        setBallHolderId(scene, playerSprite.playerId);
      }
      
      break; // Only one player can have the ball
    }
  }
}

/**
 * Calculate step index from timestamp (helper for timestamp-based updates)
 * @param {Array} animations - Player animation data
 * @param {number} timestamp - Timestamp in ms
 * @returns {number} Step index
 */
function calculateStepIndexFromTimestamp(animations, timestamp) {
  for (const anim of animations) {
    if (!anim.movement || !anim.movement.length) continue;
    
    let stepIndex = 0;
    while (
      stepIndex < anim.movement.length - 1 &&
      timestamp >= anim.movement[stepIndex + 1].timestamp
    ) {
      stepIndex++;
    }
    
    if (anim.hasBallAtStep?.[stepIndex]) {
      return stepIndex;
    }
  }
  return 0; // Default to first step
}

// Default export for backward compatibility
export default {
  attachBallToPlayer,
  detachBall,
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner,
  getLastKnownOwner,
  getPendingOwner,
  setPendingOwner,
  clearPendingOwner,
  cancelBallTween,
  updateBallOwnership,
  initializeBallController,
  getBallController
};
