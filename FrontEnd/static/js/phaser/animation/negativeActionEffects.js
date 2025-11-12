/**
 * Negative Action Effects - Visual feedback for fouls and turnovers
 * 
 * Provides tiered visual feedback:
 * - FOUL: Red tint (0.3) + pulse + "F" icon (1.0s)
 * - TURNOVER: Red tint (0.5) + shake + "TO" icon (1.0s)
 */

export function triggerNegativeAction(scene, playerId, actionType = 'foul') {
  console.log(`💥 triggerNegativeAction called:`, { playerId, actionType, hasPlayerSprites: !!scene.playerSprites });
  
  const sprite = scene.playerSprites?.[playerId];
  if (!sprite) {
    console.warn(`⚠️ Cannot trigger negative action: sprite not found for ${playerId}`);
    console.log(`Available sprites:`, Object.keys(scene.playerSprites || {}));
    return;
  }
  
  console.log(`💥 Sprite type:`, sprite.constructor.name, `Has setTint:`, typeof sprite.setTint, `Has tint:`, typeof sprite.tint);
  console.log(`💥 Sprite object keys:`, Object.keys(sprite));
  
  const isFoul = actionType === 'foul';
  const config = isFoul ? {
    tint: 0xff0000,      // BRIGHT RED tint
    tintAlpha: 0.6,      // More visible opacity
    duration: 3000,      // 3.0s
    iconText: 'F',
    iconDuration: 3000,  // 3.0s
    iconSize: '48px',    // Much larger text
    animation: 'pulse'   // Pulse effect
  } : {
    tint: 0xff0000,      // BRIGHT RED tint (same as foul)
    tintAlpha: 0.7,      // Even more visible for turnovers
    duration: 3000,      // 3.0s
    iconText: 'TO',
    iconDuration: 3000,  // 3.0s
    iconSize: '48px',    // Much larger text
    animation: 'shake'   // Shake effect
  };
  
  console.log(`💥 Triggering ${actionType} effect for player ${playerId}`);
  
  // Helper function to apply tint (handles both single sprites and containers)
  const applyTintToSprite = (target, tint, alpha) => {
    if (target.type === 'Container') {
      // For containers, apply to all children
      target.list.forEach(child => {
        if (child.setTint) {
          child.setTint(tint);
        }
        if (child.setAlpha) {
          child.setAlpha(alpha);
        }
      });
    } else if (target.setTint) {
      // For single sprites
      target.setTint(tint);
      target.setAlpha(alpha);
    }
  };
  
  // Store original state
  const originalState = {
    tints: [],
    alphas: [],
    isContainer: sprite.type === 'Container'
  };
  
  if (sprite.type === 'Container') {
    // Store original state of children
    sprite.list.forEach(child => {
      originalState.tints.push(child.tint || 0xffffff);
      originalState.alphas.push(child.alpha || 1.0);
    });
  } else {
    originalState.tints.push(sprite.tint || 0xffffff);
    originalState.alphas.push(sprite.alpha || 1.0);
  }
  
  // Apply red tint
  applyTintToSprite(sprite, config.tint, 1.0 - config.tintAlpha);
  
  // Add red screen flash effect
  const screenFlash = scene.add.rectangle(
    scene.game.config.width / 2,
    scene.game.config.height / 2,
    scene.game.config.width,
    scene.game.config.height,
    0xff0000,
    0.5  // 50% opacity red overlay (more visible)
  );
  screenFlash.setDepth(999); // Just below icon
  
  // Hold at full opacity for 1 second, then fade out slowly
  scene.tweens.add({
    targets: screenFlash,
    alpha: 0,
    duration: 1500,  // 1.5s fade out
    delay: 1000,     // Hold at 50% opacity for 1 second first
    ease: 'Cubic.easeOut',
    onComplete: () => {
      screenFlash.destroy();
    }
  });
  
  // Shake/pulse animations removed - rely on announcement system + screen flash + sprite tint
  
  // Restore original tint and alpha after duration
  scene.time.delayedCall(config.duration, () => {
    if (originalState.isContainer) {
      // Restore container children
      sprite.list.forEach((child, index) => {
        if (child.clearTint) {
          child.clearTint();
        }
        if (child.setAlpha && originalState.alphas[index] !== undefined) {
          child.setAlpha(originalState.alphas[index]);
        }
      });
    } else {
      // Restore single sprite
      if (sprite.clearTint) {
        sprite.clearTint();
      }
      if (sprite.setAlpha && originalState.alphas[0] !== undefined) {
        sprite.setAlpha(originalState.alphas[0]);
      }
    }
  });
}

/**
 * Trigger foul effect for a player
 */
export function triggerFoulEffect(scene, playerId) {
  triggerNegativeAction(scene, playerId, 'foul');
}

/**
 * Trigger turnover effect for a player
 */
export function triggerTurnoverEffect(scene, playerId) {
  triggerNegativeAction(scene, playerId, 'turnover');
}

/**
 * Trigger green flash for made shots (HCO, Fast Break, Putback)
 * No sprite effect - just screen flash
 * @param {boolean} hasAndOne - If true, creates diagonal split (green + red)
 */
export function triggerMadeShotFlash(scene, hasAndOne = false) {
  if (!scene) return;
  
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  
  if (hasAndOne) {
    // Diagonal split: Create TWO completely separate graphics at DIFFERENT positions
    // Offset red slightly to avoid edge overlap
    
    // Upper-right triangle (GREEN)
    const greenGraphics = scene.add.graphics();
    greenGraphics.fillStyle(0x00FF00, 1.0);  // Pure green, FULL opacity
    greenGraphics.fillTriangle(
      0, 0,              // Top-left
      width, 0,          // Top-right
      width, height      // Bottom-right
    );
    greenGraphics.setAlpha(0.6);  // Apply alpha to entire object
    greenGraphics.setDepth(998);
    
    // Lower-left triangle (RED) - offset by 1 pixel to avoid shared edge
    const redGraphics = scene.add.graphics();
    redGraphics.fillStyle(0xFF0000, 1.0);  // Pure red, FULL opacity
    redGraphics.fillTriangle(
      1, 1,              // Top-left (offset by 1px)
      1, height,         // Bottom-left (offset by 1px)
      width, height      // Bottom-right
    );
    redGraphics.setAlpha(0.6);  // Apply alpha to entire object
    redGraphics.setDepth(999);  // On top of green
    
    // Hold for 1s, then fade out
    scene.tweens.add({
      targets: [greenGraphics, redGraphics],
      alpha: 0,
      duration: 1500,
      delay: 1000,
      ease: 'Cubic.easeOut',
      onComplete: () => {
        greenGraphics.destroy();
        redGraphics.destroy();
      }
    });
  } else {
    // Regular green flash (full screen)
    const screenFlash = scene.add.rectangle(
      width / 2,
      height / 2,
      width,
      height,
      0x00ff00,  // GREEN
      0.4  // 40% opacity green overlay
    );
    screenFlash.setDepth(999);
    
    // Hold at full opacity for 0.5s, then fade out
    scene.tweens.add({
      targets: screenFlash,
      alpha: 0,
      duration: 1000,  // 1s fade out
      delay: 500,      // Hold at 40% opacity for 0.5s first
      ease: 'Cubic.easeOut',
      onComplete: () => {
        screenFlash.destroy();
      }
    });
  }
}

