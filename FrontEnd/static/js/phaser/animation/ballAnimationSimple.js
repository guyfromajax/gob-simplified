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
 * This is Step 1 of the migration - new functions alongside existing code.
 * Old system still works, new system ready for gradual migration.
 */

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
  const ballHolderId = getBallHolderId(scene);
  const playerId = playerSprite?.playerId || null;
  
  if (ballHolderId && playerId === ballHolderId) {
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

