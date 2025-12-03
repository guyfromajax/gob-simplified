/**
 * Negative Action Effects - Visual feedback for fouls and turnovers
 * 
 * Provides tiered visual feedback:
 * - FOUL: Red tint (0.3) + pulse + "F" icon (1.0s)
 * - TURNOVER: Red tint (0.5) + shake + "TO" icon (1.0s)
 */

export function triggerNegativeAction(scene, playerId, actionType = 'foul', skipScreenFlash = false) {
  const sprite = scene.playerSprites?.[playerId];
  if (!sprite) {
    console.warn(`⚠️ Cannot trigger negative action: sprite not found for ${playerId}`);
    return;
  }
  
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
  
  // Helper function to apply tint (handles both single sprites and containers)
  // ✅ FIX: Removed opacity reduction - it was sticking and making sprites invisible
  const applyTintToSprite = (target, tint) => {
    if (target.type === 'Container') {
      // For containers, apply to all children
      target.list.forEach(child => {
        if (child.setTint) {
          child.setTint(tint);
        }
        // Removed setAlpha - keep sprites at full opacity
      });
    } else if (target.setTint) {
      // For single sprites
      target.setTint(tint);
      // Removed setAlpha - keep sprites at full opacity
    }
  };
  
  // Store original state
  const originalState = {
    tints: [],
    isContainer: sprite.type === 'Container'
  };
  
  if (sprite.type === 'Container') {
    // Store original state of children
    sprite.list.forEach(child => {
      originalState.tints.push(child.tint || 0xffffff);
    });
  } else {
    originalState.tints.push(sprite.tint || 0xffffff);
  }
  
  // Apply red tint (without opacity reduction)
  applyTintToSprite(sprite, config.tint);
  
  // Add red screen flash effect (skip for AND-1 to avoid mixing with green flash)
  if (!skipScreenFlash) {
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
  }
  
  // Shake/pulse animations removed - rely on announcement system + screen flash + sprite tint
  
  // Restore original tint after duration (no alpha restoration needed - we never changed it)
  scene.time.delayedCall(config.duration, () => {
    if (originalState.isContainer) {
      // Restore container children
      sprite.list.forEach((child, index) => {
        if (child.clearTint) {
          child.clearTint();
        }
        // No alpha restoration - we never changed it
      });
    } else {
      // Restore single sprite
      if (sprite.clearTint) {
        sprite.clearTint();
      }
      // No alpha restoration - we never changed it
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
    // AND-1: Full screen green flash (made shot)
    // Red tint will be applied to announcement container in announcements.js
    const screenFlash = scene.add.rectangle(
      width / 2,
      height / 2,
      width,
      height,
      0x00ff00,  // Bright green
      0.5        // 50% opacity
    );
    screenFlash.setOrigin(0.5, 0.5);
    screenFlash.setDepth(998);
    
    // Hold for 1s, then fade out
    scene.tweens.add({
      targets: screenFlash,
      alpha: 0,
      duration: 1500,  // 1.5s fade out
      delay: 1000,     // Hold at 50% opacity for 1s first
      ease: 'Cubic.easeOut',
      onComplete: () => {
        screenFlash.destroy();
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

