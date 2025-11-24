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
  globalBallController.debug = true; // Enable debug logging for adapter
  
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
  if (scene.possessionFlipInProgress) {
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
    if (isPutbackAttempt || isPutbackScenario) {
      console.warn('🔍 [BALL ATTACH DEBUG] FAILED: Failed to attach ball', {
        targetPlayerId,
        reason: opts?.debugInfo?.reason || 'unknown',
        shotInProgress: scene._shotInProgress,
        sceneRebounderId: scene.rebounderId
      });
    } else {
      console.warn('BallControllerAdapter: Failed to attach ball to player', {
        playerId: playerSprite.playerId,
        team: playerSprite.team_id ?? playerSprite.team
      });
    }
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
  
  console.log('BallControllerAdapter: Ball detached');
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
  initializeBallController,
  getBallController
};
