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
  
  // ✅ PHASE 1.4: Removed duplicate flag checks - BallController now handles these internally
  // BallController.attachToPlayer() will check isInFlight and reason fields
  // Old flags are still checked as fallback during transition period

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
    
    // Set old system ball state
    scene.ballDetached = false;
    
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
  
  // Update old system references
  scene.ballDetached = true;
  
  console.log('BallControllerAdapter: Ball detached');
}

/**
 * Backward compatible tweenBallTo function
 * 
 * @param {Phaser.Scene} scene - The game scene
 * @param {Phaser.GameObjects.Image} ballSprite - The ball sprite
 * @param {Object} targetCoords - Target coordinates
 * @param {Object} options - Tween options
 */
function tweenBallTo(scene, ballSprite, targetCoords, options = {}) {
  const ballController = getBallController();
  
  if (!ballController) {
    console.error('BallControllerAdapter: Cannot tween ball - BallController not initialized');
    return Promise.resolve();
  }

  // Use BallController to start flight
  ballController.startFlight(targetCoords, options);
  
  // Return a promise that resolves when the tween completes
  return new Promise((resolve) => {
    if (options.duration) {
      setTimeout(resolve, options.duration);
    } else {
      resolve();
    }
  });
}

/**
 * Helper function to get current ball owner (old system compatibility)
 */
function getCurrentOwner(scene) {
  const ballController = getBallController();
  return ballController ? ballController.currentOwner : null;
}

/**
 * Helper function to set current ball owner (old system compatibility)
 */
function setCurrentOwner(scene, playerId) {
  const ballController = getBallController();
  if (ballController && scene.playerSprites && scene.playerSprites[playerId]) {
    ballController.attachToPlayer(scene.playerSprites[playerId]);
  }
}

/**
 * Helper function to clear current ball owner (old system compatibility)
 */
function clearCurrentOwner(scene) {
  const ballController = getBallController();
  if (ballController) {
    ballController.detachFromPlayer('clear');
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
  
  // Synchronize old flags with BallController state
  // If BallController says ball is in flight, set old flags accordingly
  if (ballController.isInFlight) {
    if (ballController.reason === 'shot' || ballController.reason === 'putback_shot') {
      scene._shotInProgress = true;
    } else if (ballController.reason === 'pass') {
      scene.passInFlight = true;
    }
  } else {
    // Ball is not in flight, clear old flags
    scene._shotInProgress = false;
    scene.passInFlight = false;
  }
  
  // Sync putback state
  if (ballController.reason === 'putback_shot') {
    scene._putbackInProgress = true;
  } else {
    scene._putbackInProgress = false;
  }
  
  // Sync attachment state
  if (ballController.isAttached) {
    scene.ballDetached = false;
  } else if (!ballController.isInFlight && allowAttachment) {
    // Only set ballDetached if not in flight and attachment is allowed
    scene.ballDetached = true;
  }
}

// Named exports for individual functions
// ✅ NOTE: tweenBallTo removed from exports (legacy code - replaced by animateBallToPosition)
export {
  attachBallToPlayer,
  detachBall,
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner,
  synchronizeBallState,
  initializeBallController,
  getBallController
};

// Default export for backward compatibility
// ✅ NOTE: tweenBallTo removed from default export (legacy code - replaced by animateBallToPosition)
export default {
  attachBallToPlayer,
  detachBall,
  getCurrentOwner,
  setCurrentOwner,
  clearCurrentOwner,
  initializeBallController,
  getBallController
};
