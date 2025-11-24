/**
 * BallController - Single Source of Truth for Ball Ownership and State
 * 
 * Replaces the scattered ball ownership systems across multiple files
 * with a single, reliable system that prevents floating balls and conflicts.
 * 
 * Key Benefits:
 * - Single source of truth for ball ownership and state
 * - Proper attachment/detachment logic
 * - No floating ball issues
 * - Thread-safe ownership changes
 * - Comprehensive ball state tracking
 * - Lifecycle methods for shot, pass, and putback animations
 * - Automatic synchronization with WIP_GOB system (gameState.ballHolder)
 * 
 * Lifecycle Methods:
 * - onShotStart(options): Called when a shot animation begins
 * - onShotEnd(): Called when a shot animation completes
 * - onPassStart(options): Called when a pass animation begins
 * - onPassEnd(receiver): Called when a pass animation completes
 * - onPutbackStart(options): Called when a putback shot begins
 * - onPutbackEnd(): Called when a putback shot completes
 * 
 * State Management:
 * - isAttached: Ball is attached to a player
 * - isInFlight: Ball is in motion (shot, pass, etc.)
 * - isMoving: Ball is currently animating
 * - reason: Current reason for state (shot, pass, putback_shot, etc.)
 * - currentOwner: Player sprite that currently owns the ball
 * 
 * @class BallController
 */

import { AnimationStates } from './SimplifiedStateMachine.js';

export class BallController {
  constructor(scene, ballSprite) {
    this.scene = scene;
    this.ballSprite = ballSprite;
    this.currentOwner = null;
    this.pendingOwner = null;
    this.ownershipHistory = [];
    this.isAttached = false;
    this.isDetached = false;
    this.isInFlight = false;
    this.attachmentCallbacks = [];
    this.detachmentCallbacks = [];
    
    // Ball state tracking
    this.lastPosition = null;
    this.targetPosition = null;
    this.isMoving = false;
    
    // ✅ PHASE 1.1: Internal state tracking for lifecycle management
    // Track reason for current state (shot, pass, putback, etc.)
    this.reason = null;
    // Track previous state before transitions
    this.previousState = null;
    // Track state history for debugging
    this.stateHistory = [];
    
    // Debug logging
    this.debug = false;
    
    // Initialize ball sprite
    this.initializeBallSprite();
  }

  /**
   * Initialize the ball sprite
   */
  initializeBallSprite() {
    if (!this.ballSprite) {
      console.warn('BallController: No ball sprite provided');
      return;
    }

    // Set initial state
    this.ballSprite.setVisible(false);
    this.ballSprite.setDepth(1000); // High depth to appear on top
    
    if (this.debug) {
      console.log('BallController: Initialized ball sprite', {
        position: { x: this.ballSprite.x, y: this.ballSprite.y },
        visible: this.ballSprite.visible
      });
    }
  }

  /**
   * Attach ball to a player
   */
  attachToPlayer(playerSprite, options = {}) {
    if (!this.ballSprite || !playerSprite) {
      console.warn('BallController: Cannot attach - missing ball or player sprite');
      return false;
    }

    if (this.isInFlight) {
      // Only log in debug mode - this is expected behavior during passes/shots
      if (this.debug) {
        console.warn('BallController: Cannot attach - ball is in flight', {
          reason: this.reason
        });
      }
      return false;
    }
    
    // Don't attach during shot animations (unless this is a putback attempt)
    // Putback attempts need to attach the ball before the shot animation starts
    const isPutbackAttempt = options?.debugInfo?.reason === 'putback_attempt';
    
    // ✅ PHASE 1.3: Use internal state instead of old scene flags
    // Check if ball is in flight (from shot or pass)
    if (this.isInFlight && !isPutbackAttempt) {
      if (this.debug) {
        console.log('BallController: Cannot attach - ball is in flight', {
          reason: this.reason,
          isPutbackAttempt
        });
      }
      return false;
    }
    
    // Check if this is a putback shot in progress (using internal state)
    if (this.reason === 'putback_shot' && !isPutbackAttempt) {
      if (this.debug) {
        console.log('BallController: Cannot attach - putback shot in progress', {
          reason: this.reason,
          isPutbackAttempt
        });
      }
      return false;
    }
    
    // ✅ PHASE 4: Removed old flag checks - BallController is now the single source of truth
    // All state is managed internally via isInFlight, reason, and state fields

    // Validate player sprite
    if (!this.isValidPlayerSprite(playerSprite)) {
      console.warn('BallController: Invalid player sprite', playerSprite);
      return false;
    }

    // Record previous owner
    const previousOwner = this.currentOwner;
    
    // Update ownership
    this.currentOwner = playerSprite;
    this.pendingOwner = null;
    this.isAttached = true;
    this.isDetached = false;

    // ✅ SYNC WITH WIP_GOB: Set ball holder state when attaching directly
    // This ensures WIP_GOB system (getPlayerTweenTargets) knows who has the ball
    const playerId = playerSprite.playerId || (playerSprite.id ? String(playerSprite.id) : null);
    if (this.scene && this.scene.gameState && playerId) {
      this.scene.gameState.ballHolder = playerId;
    }
    
    // ✅ PHASE 1: Ensure ownership history is updated for getLastKnownOwnerId()
    // This is already done in recordOwnershipChange below, but we ensure it happens

    // Position ball on player
    this.positionBallOnPlayer(playerSprite, options);

    // Start following the player during movements
    this.startFollowingPlayer(playerSprite, options);

    // Record ownership change
    this.recordOwnershipChange(previousOwner, playerSprite, 'attach', options);

    // Notify callbacks
    this.notifyAttachmentCallbacks(previousOwner, playerSprite, options);

    // Removed verbose attachment logging - only log in debug mode if needed

    return true;
  }

  /**
   * Detach ball from current owner
   */
  detachFromPlayer(reason = 'detach', options = {}) {
    if (!this.isAttached) {
      console.warn('BallController: Cannot detach - ball is not attached');
      return false;
    }

    const previousOwner = this.currentOwner;
    
    // Stop following the player (new system)
    this.stopFollowingPlayer();
    
    // ✅ PHASE 4: Removed old _ballFollowing system - BallController handles following internally
    
    // Update state
    this.currentOwner = null;
    this.isAttached = false;
    this.isDetached = true;

    // ✅ SYNC WITH WIP_GOB: Clear ball holder state when detaching directly
    // This ensures WIP_GOB system (getPlayerTweenTargets) doesn't include ball in player tweens
    if (this.scene && this.scene.gameState) {
      this.scene.gameState.ballHolder = null;
    }

    // Hide ball if not in flight
    if (!this.isInFlight) {
      this.ballSprite.setVisible(false);
    }

    // Record ownership change (this updates ownershipHistory for getLastKnownOwnerId())
    this.recordOwnershipChange(previousOwner, null, reason, options);

    // Notify callbacks
    this.notifyDetachmentCallbacks(previousOwner, reason, options);

    // Removed verbose detachment logging - only log in debug mode if needed

    return true;
  }

  /**
   * Set pending owner (for passes, etc.)
   */
  setPendingOwner(playerSprite, options = {}) {
    if (!this.isValidPlayerSprite(playerSprite)) {
      console.warn('BallController: Invalid pending owner', playerSprite);
      return false;
    }

    this.pendingOwner = playerSprite;

    // Removed verbose pending owner logging

    return true;
  }

  /**
   * Clear pending owner
   */
  clearPendingOwner() {
    this.pendingOwner = null;
  }

  /**
   * Start ball in flight (for passes, shots, etc.)
   */
  startFlight(targetPosition, options = {}) {
    if (this.isInFlight) {
      console.warn('BallController: Ball is already in flight');
      return false;
    }

    // Stop following player when ball starts flight (new system)
    this.stopFollowingPlayer();

    // ✅ PHASE 4: Removed old _ballFollowing system - BallController handles following internally

    // ✅ PROACTIVE STATE MANAGEMENT: Clear ball holder state when BallController starts flight
    // This prevents ball from being included in player movement tweens (WIP_GOB system)
    // BallController is now managing the ball, so our simple ball holder state should reflect that
    // Direct state access to avoid circular dependencies
    if (this.scene && this.scene.gameState) {
      this.scene.gameState.ballHolder = null;
    }

    this.isInFlight = true;
    this.targetPosition = targetPosition;
    this.isMoving = true;

    // Show ball if it was hidden
    this.ballSprite.setVisible(true);

    // Removed verbose flight start logging

    return true;
  }

  /**
   * End ball flight
   */
  endFlight(newOwner = null, options = {}) {
    if (!this.isInFlight) {
      console.warn('BallController: Ball is not in flight');
      return false;
    }

    this.isInFlight = false;
    this.isMoving = false;
    this.targetPosition = null;

    // Attach to new owner if provided
    if (newOwner) {
      // ✅ PROACTIVE STATE MANAGEMENT: Set ball holder state to new owner when flight ends
      // This ensures ball holder state reflects reality (new owner now has the ball)
      // This enables new owner's tween to include ball in targets (WIP_GOB approach)
      const newOwnerId = newOwner.playerId || (newOwner.id ? String(newOwner.id) : null);
      if (this.scene && this.scene.gameState && newOwnerId) {
        this.scene.gameState.ballHolder = newOwnerId;
      }
      this.attachToPlayer(newOwner, options);
    } else if (!options.keepVisible) {
      // Hide ball if no new owner (unless keepVisible is set)
      this.ballSprite.setVisible(false);
    }
    // If keepVisible is true, leave ball visible at current position

    // Removed verbose flight end logging

    return true;
  }

  /**
   * Update ball position (called during animations)
   */
  updatePosition(x, y) {
    if (!this.ballSprite) return;

    this.lastPosition = { x: this.ballSprite.x, y: this.ballSprite.y };
    this.ballSprite.setPosition(x, y);

    // If attached to a player, ensure ball follows player
    if (this.isAttached && this.currentOwner) {
      this.positionBallOnPlayer(this.currentOwner);
    }
  }

  /**
   * Position ball on player sprite
   */
  positionBallOnPlayer(playerSprite, options = {}) {
    if (!this.ballSprite || !playerSprite) return;

    const offset = options.offset || { x: 0, y: 0 };
    const x = playerSprite.x + offset.x;
    const y = playerSprite.y + offset.y;

    this.ballSprite.setPosition(x, y);
    this.ballSprite.setVisible(true);
    this.ballSprite.setDepth(playerSprite.depth + 1);
  }

  /**
   * Start following a player during movement animations
   */
  startFollowingPlayer(playerSprite, options = {}) {
    if (!this.ballSprite || !playerSprite) return;

    this.stopFollowingPlayer(); // Stop any existing following

    this.followingPlayer = playerSprite;
    this.followOffset = options.offset || { x: 0, y: 0 };
    this.followCallback = () => {
      if (this.followingPlayer && this.ballSprite && this.isAttached) {
        const x = this.followingPlayer.x + this.followOffset.x;
        const y = this.followingPlayer.y + this.followOffset.y;
        this.ballSprite.setPosition(x, y);
      }
    };

    // Add update callback to scene
    if (this.scene && this.scene.events) {
      this.scene.events.on('update', this.followCallback);
    }

    // Removed verbose following start logging
  }

  /**
   * Stop following player
   */
  stopFollowingPlayer() {
    if (this.followCallback && this.scene && this.scene.events) {
      this.scene.events.off('update', this.followCallback);
    }

    this.followingPlayer = null;
    this.followOffset = null;
    this.followCallback = null;

    // Removed verbose following stop logging
  }

  /**
   * ✅ PHASE 4: Removed stopOldBallFollowing() method
   * Old _ballFollowing system has been removed - BallController handles following internally
   */

  /**
   * Validate player sprite
   */
  isValidPlayerSprite(playerSprite) {
    return playerSprite && 
           typeof playerSprite.x === 'number' && 
           typeof playerSprite.y === 'number' &&
           playerSprite.playerId;
  }

  /**
   * Record ownership change in history
   */
  recordOwnershipChange(from, to, reason, options = {}) {
    this.ownershipHistory.push({
      from: from?.playerId || null,
      to: to?.playerId || null,
      reason,
      timestamp: Date.now(),
      position: { x: this.ballSprite.x, y: this.ballSprite.y },
      options
    });

    // Keep only last 50 changes to prevent memory leaks
    if (this.ownershipHistory.length > 50) {
      this.ownershipHistory = this.ownershipHistory.slice(-50);
    }
  }

  /**
   * Notify attachment callbacks
   */
  notifyAttachmentCallbacks(previousOwner, newOwner, options) {
    this.attachmentCallbacks.forEach(callback => {
      try {
        callback(previousOwner, newOwner, options);
      } catch (error) {
        console.error('BallController: Attachment callback error', error);
      }
    });
  }

  /**
   * Notify detachment callbacks
   */
  notifyDetachmentCallbacks(previousOwner, reason, options) {
    this.detachmentCallbacks.forEach(callback => {
      try {
        callback(previousOwner, reason, options);
      } catch (error) {
        console.error('BallController: Detachment callback error', error);
      }
    });
  }

  /**
   * Add attachment callback
   */
  onAttachment(callback) {
    this.attachmentCallbacks.push(callback);
  }

  /**
   * Add detachment callback
   */
  onDetachment(callback) {
    this.detachmentCallbacks.push(callback);
  }

  /**
   * Get current ball state
   */
  getState() {
    return {
      currentOwner: this.currentOwner?.playerId || null,
      pendingOwner: this.pendingOwner?.playerId || null,
      isAttached: this.isAttached,
      isDetached: this.isDetached,
      isInFlight: this.isInFlight,
      isMoving: this.isMoving,
      position: { x: this.ballSprite.x, y: this.ballSprite.y },
      visible: this.ballSprite.visible,
      // ✅ PHASE 1.1: Include new state tracking fields
      reason: this.reason,
      previousState: this.previousState,
      lastStateChange: this.stateHistory.length > 0 ? this.stateHistory[this.stateHistory.length - 1] : null
    };
  }

  /**
   * Get ownership history
   */
  getOwnershipHistory(limit = 10) {
    return this.ownershipHistory.slice(-limit);
  }

  /**
   * Get current owner
   */
  getCurrentOwner() {
    return this.currentOwner;
  }

  /**
   * Get pending owner
   */
  getPendingOwner() {
    return this.pendingOwner;
  }

  /**
   * Check if ball is attached
   */
  isBallAttached() {
    return this.isAttached;
  }

  // ==================== PHASE 1: COMPATIBILITY METHODS ====================
  // These methods provide compatibility with old ballController.js system
  // They return/accept player IDs (strings) instead of sprites

  /**
   * Get current owner ID (string) - for compatibility with old system
   * @returns {string|null} Player ID or null
   */
  getCurrentOwnerId() {
    if (!this.currentOwner) return null;
    return this.currentOwner.playerId || (this.currentOwner.id ? String(this.currentOwner.id) : null);
  }

  /**
   * Set current owner by ID (string) - for compatibility with old system
   * @param {string} playerId - Player ID
   * @returns {boolean} Success
   */
  setCurrentOwnerById(playerId) {
    if (!this.scene || !this.scene.playerSprites || !playerId) {
      if (this.debug) {
        console.warn('BallController: Cannot set current owner by ID - missing scene, playerSprites, or playerId', {
          hasScene: !!this.scene,
          hasPlayerSprites: !!this.scene?.playerSprites,
          playerId
        });
      }
      return false;
    }
    const playerSprite = this.scene.playerSprites[playerId];
    if (!playerSprite) {
      console.warn('BallController: Player sprite not found for ID', playerId);
      return false;
    }
    return this.attachToPlayer(playerSprite);
  }

  /**
   * Clear current owner
   */
  clearCurrentOwner() {
    if (this.isAttached) {
      this.detachFromPlayer('clear');
    } else {
      // Even if not attached, clear the current owner reference
      this.currentOwner = null;
    }
  }

  /**
   * Get last known owner ID (string)
   * @returns {string|null} Player ID or null
   */
  getLastKnownOwnerId() {
    if (this.ownershipHistory.length === 0) {
      // If no history but we have a current owner, return that
      if (this.currentOwner) {
        return this.getCurrentOwnerId();
      }
      return null;
    }
    // Find the last entry where 'to' is not null
    for (let i = this.ownershipHistory.length - 1; i >= 0; i--) {
      const entry = this.ownershipHistory[i];
      if (entry.to) {
        return entry.to;
      }
    }
    // Fallback: return current owner ID if available
    return this.getCurrentOwnerId();
  }

  /**
   * Get pending owner ID (string) - for compatibility
   * @returns {string|null} Player ID or null
   */
  getPendingOwnerId() {
    if (!this.pendingOwner) return null;
    return this.pendingOwner.playerId || (this.pendingOwner.id ? String(this.pendingOwner.id) : null);
  }

  /**
   * Set pending owner by ID (string) - for compatibility
   * @param {string} playerId - Player ID
   * @returns {boolean} Success
   */
  setPendingOwnerById(playerId) {
    if (!this.scene || !this.scene.playerSprites || !playerId) {
      if (this.debug) {
        console.warn('BallController: Cannot set pending owner by ID - missing scene, playerSprites, or playerId', {
          hasScene: !!this.scene,
          hasPlayerSprites: !!this.scene?.playerSprites,
          playerId
        });
      }
      return false;
    }
    const playerSprite = this.scene.playerSprites[playerId];
    if (!playerSprite) {
      console.warn('BallController: Pending owner sprite not found for ID', playerId);
      return false;
    }
    this.setPendingOwner(playerSprite);
    return true;
  }

  /**
   * Get ball holder ID (string) - WIP_GOB compatibility
   * @returns {string|null} Player ID or null
   */
  getBallHolderId() {
    if (!this.scene || !this.scene.gameState) return null;
    return this.scene.gameState.ballHolder || null;
  }

  /**
   * Set ball holder ID (string) - WIP_GOB compatibility
   * @param {string} playerId - Player ID
   */
  setBallHolderId(playerId) {
    if (!this.scene) return;
    if (!this.scene.gameState) {
      this.scene.gameState = {};
    }
    this.scene.gameState.ballHolder = playerId || null;
    
    // Removed verbose ball holder ID logging
  }

  /**
   * Clear ball holder ID - WIP_GOB compatibility
   */
  clearBallHolderId() {
    if (this.scene && this.scene.gameState) {
      this.scene.gameState.ballHolder = null;
      
      // Removed verbose clear ball holder ID logging
    }
  }

  /**
   * Check if ball is in flight
   */
  isBallInFlight() {
    return this.isInFlight;
  }

  /**
   * Check if ball is moving
   */
  isBallMoving() {
    return this.isMoving;
  }

  /**
   * Reset ball to initial state
   */
  reset() {
    this.stopFollowingPlayer();
    this.currentOwner = null;
    this.pendingOwner = null;
    this.isAttached = false;
    this.isDetached = false;
    this.isInFlight = false;
    this.isMoving = false;
    this.targetPosition = null;
    this.ownershipHistory = [];
    // ✅ PHASE 1.1: Reset new state tracking fields
    this.reason = null;
    this.previousState = null;
    this.stateHistory = [];
    
    if (this.ballSprite) {
      this.ballSprite.setVisible(false);
    }
  }

  /**
   * Enable/disable debug logging
   */
  setDebug(enabled) {
    this.debug = enabled;
  }

  /**
   * Get comprehensive status
   */
  getStatus() {
    return {
      state: this.getState(),
      ownershipHistory: this.getOwnershipHistory(5),
      callbacks: {
        attachment: this.attachmentCallbacks.length,
        detachment: this.detachmentCallbacks.length
      },
      debug: this.debug
    };
  }

  /**
   * Cleanup method - call when destroying the controller
   */
  destroy() {
    this.stopFollowingPlayer();
    this.attachmentCallbacks = [];
    this.detachmentCallbacks = [];
  }

  // ==================== PHASE 1.2: LIFECYCLE METHODS ====================
  // These methods provide a clean API for managing ball state transitions
  // They will eventually replace direct manipulation of scene flags

  /**
   * Lifecycle: Shot animation started
   * Sets ball to in-flight state and detaches from current owner
   * @param {Object} options - Options object
   * @param {string} options.shooterId - ID of the shooter
   * @param {boolean} options.isPutback - Whether this is a putback attempt
   */
  onShotStart(options = {}) {
    const { shooterId, isPutback = false } = options;
    
    // Save previous state
    this.previousState = {
      isAttached: this.isAttached,
      isInFlight: this.isInFlight,
      currentOwner: this.currentOwner?.playerId || null,
      reason: this.reason
    };

    // Set ball to in-flight state
    this.isInFlight = true;
    this.reason = isPutback ? 'putback_shot' : 'shot';
    
    // Detach from current owner if attached
    if (this.isAttached) {
      this.detachFromPlayer('shot_start', { reason: this.reason, shooterId });
    }

    // Record state change
    this.stateHistory.push({
      state: 'IN_FLIGHT',
      reason: this.reason,
      shooterId,
      timestamp: Date.now(),
      previousState: this.previousState
    });

    // Keep only last 50 state changes
    if (this.stateHistory.length > 50) {
      this.stateHistory = this.stateHistory.slice(-50);
    }

    // Removed verbose lifecycle logging - only log errors
  }

  /**
   * Lifecycle: Shot animation ended
   * 
   * Called when a shot animation completes. Clears in-flight state,
   * allowing the ball to be attached to a new owner (e.g., rebounder).
   * 
   * @example
   * ballController.onShotEnd();
   */
  onShotEnd() {
    // Save previous state
    this.previousState = {
      isAttached: this.isAttached,
      isInFlight: this.isInFlight,
      currentOwner: this.currentOwner?.playerId || null,
      reason: this.reason
    };

    // Clear in-flight state
    this.isInFlight = false;
    const previousReason = this.reason;
    this.reason = null;

    // Record state change
    this.stateHistory.push({
      state: 'READY',
      reason: 'shot_end',
      previousReason,
      timestamp: Date.now(),
      previousState: this.previousState
    });

    // Keep only last 50 state changes
    if (this.stateHistory.length > 50) {
      this.stateHistory = this.stateHistory.slice(-50);
    }

    // Removed verbose lifecycle logging
  }

  /**
   * Lifecycle: Pass animation started
   * Sets ball to in-flight state and detaches from passer
   * @param {Object} options - Options object
   * @param {string} options.passerId - ID of the passer
   * @param {string} options.receiverId - ID of the receiver (optional)
   */
  onPassStart(options = {}) {
    const { passerId, receiverId } = options;
    
    // Save previous state
    this.previousState = {
      isAttached: this.isAttached,
      isInFlight: this.isInFlight,
      currentOwner: this.currentOwner?.playerId || null,
      reason: this.reason
    };

    // Set ball to in-flight state
    this.isInFlight = true;
    this.reason = 'pass';
    
    // Set pending owner if receiver is known
    if (receiverId && this.scene && this.scene.playerSprites) {
      const receiverSprite = this.scene.playerSprites[receiverId];
      if (receiverSprite) {
        this.setPendingOwner(receiverSprite, { reason: 'pass', receiverId });
      }
    }
    
    // Detach from current owner if attached
    if (this.isAttached) {
      this.detachFromPlayer('pass_start', { reason: 'pass', passerId, receiverId });
    }

    // Record state change
    this.stateHistory.push({
      state: 'IN_FLIGHT',
      reason: 'pass',
      passerId,
      receiverId,
      timestamp: Date.now(),
      previousState: this.previousState
    });

    // Keep only last 50 state changes
    if (this.stateHistory.length > 50) {
      this.stateHistory = this.stateHistory.slice(-50);
    }

    // Removed verbose lifecycle logging
  }

  /**
   * Lifecycle: Pass animation ended
   * Clears in-flight state and attaches to receiver if provided
   * @param {Object} receiverSprite - Sprite of the receiver (optional)
   * @param {Object} options - Options object
   */
  /**
   * Lifecycle: Pass animation ended
   * 
   * Called when a pass animation completes. Clears in-flight state
   * and optionally attaches ball to receiver.
   * 
   * @param {Phaser.GameObjects.Sprite} [receiverSprite=null] - Sprite of the receiver
   * @param {Object} [options={}] - Options object
   * @param {string} [options.reason='pass_complete'] - Reason for pass end
   * 
   * @example
   * ballController.onPassEnd(receiverSprite, { reason: 'pass_complete' });
   */
  onPassEnd(receiverSprite = null, options = {}) {
    // Save previous state
    this.previousState = {
      isAttached: this.isAttached,
      isInFlight: this.isInFlight,
      currentOwner: this.currentOwner?.playerId || null,
      reason: this.reason
    };

    // Clear in-flight state
    this.isInFlight = false;
    const previousReason = this.reason;
    this.reason = null;

    // Attach to receiver if provided
    if (receiverSprite) {
      this.attachToPlayer(receiverSprite, { ...options, reason: 'pass_end' });
    }

    // Record state change
    this.stateHistory.push({
      state: receiverSprite ? 'ATTACHED' : 'DETACHED',
      reason: 'pass_end',
      previousReason,
      receiverId: receiverSprite?.playerId || null,
      timestamp: Date.now(),
      previousState: this.previousState
    });

    // Keep only last 50 state changes
    if (this.stateHistory.length > 50) {
      this.stateHistory = this.stateHistory.slice(-50);
    }

    // Removed verbose lifecycle logging
  }

  /**
   * Lifecycle: Putback shot started
   * Wrapper around onShotStart with isPutback flag
   * @param {Object} options - Options object
   * @param {string} options.shooterId - ID of the shooter
   */
  onPutbackStart(options = {}) {
    this.onShotStart({ ...options, isPutback: true });
  }

  /**
   * Lifecycle: Putback shot ended
   * Wrapper around onShotEnd
   */
  onPutbackEnd() {
    this.onShotEnd();
  }
}

export default BallController;
