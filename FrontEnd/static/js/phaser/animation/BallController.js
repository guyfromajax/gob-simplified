/**
 * BallController - Single Source of Truth for Ball Ownership
 * 
 * Replaces the scattered ball ownership systems across multiple files
 * with a single, reliable system that prevents floating balls and conflicts.
 * 
 * Key Benefits:
 * - Single source of truth for ball ownership
 * - Proper attachment/detachment logic
 * - No floating ball issues
 * - Thread-safe ownership changes
 * - Comprehensive ball state tracking
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
      console.warn('BallController: Cannot attach - ball is in flight');
      return false;
    }
    
    // Don't attach during shot animations
    if (this.scene._shotInProgress) {
      if (this.debug) {
        console.log('BallController: Cannot attach - shot in progress');
      }
      return false;
    }

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

    // Position ball on player
    this.positionBallOnPlayer(playerSprite, options);

    // Start following the player during movements
    this.startFollowingPlayer(playerSprite, options);

    // Record ownership change
    this.recordOwnershipChange(previousOwner, playerSprite, 'attach', options);

    // Notify callbacks
    this.notifyAttachmentCallbacks(previousOwner, playerSprite, options);

    if (this.debug) {
      console.log('BallController: Ball attached to player', {
        playerId: playerSprite.playerId,
        team: playerSprite.team,
        position: { x: this.ballSprite.x, y: this.ballSprite.y }
      });
    }

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
    
    // Also stop old ball following system if it exists
    if (this.scene._ballFollowing) {
      this.stopOldBallFollowing();
    }
    
    // Update state
    this.currentOwner = null;
    this.isAttached = false;
    this.isDetached = true;

    // Hide ball if not in flight
    if (!this.isInFlight) {
      this.ballSprite.setVisible(false);
    }

    // Record ownership change
    this.recordOwnershipChange(previousOwner, null, reason, options);

    // Notify callbacks
    this.notifyDetachmentCallbacks(previousOwner, reason, options);

    if (this.debug) {
      console.log('BallController: Ball detached from player', {
        previousOwner: previousOwner?.playerId,
        reason,
        position: { x: this.ballSprite.x, y: this.ballSprite.y }
      });
    }

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

    if (this.debug) {
      console.log('BallController: Pending owner set', {
        playerId: playerSprite.playerId,
        team: playerSprite.team
      });
    }

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

    // Also stop old ball following system if it exists
    if (this.scene._ballFollowing) {
      this.stopOldBallFollowing();
    }

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

    if (this.debug) {
      console.log('BallController: Ball flight started', {
        from: this.lastPosition,
        to: targetPosition,
        currentOwner: this.currentOwner?.playerId
      });
    }

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

    if (this.debug) {
      console.log('BallController: Ball flight ended', {
        newOwner: newOwner?.playerId,
        position: { x: this.ballSprite.x, y: this.ballSprite.y }
      });
    }

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

    if (this.debug) {
      console.log('BallController: Started following player', {
        playerId: playerSprite.playerId,
        offset: this.followOffset
      });
    }
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

    if (this.debug) {
      console.log('BallController: Stopped following player');
    }
  }

  /**
   * Stop old ball following system (from ballTween.js)
   */
  stopOldBallFollowing() {
    if (this.scene._ballFollowing && this.scene._ballFollowing.callback && this.scene.events) {
      this.scene.events.off('update', this.scene._ballFollowing.callback);
    }
    
    this.scene._ballFollowing = null;

    if (this.debug) {
      console.log('BallController: Stopped old ball following system');
    }
  }

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
      visible: this.ballSprite.visible
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
}

export default BallController;
