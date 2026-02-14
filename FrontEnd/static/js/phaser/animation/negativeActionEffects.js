/**
 * Negative Action Effects - Visual feedback for fouls and turnovers
 * 
 * Provides tiered visual feedback:
 * - FOUL: Red tint + screen flash + "F" icon
 * - TURNOVER: Red tint + screen flash + "TO" icon
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
    iconSize: '48px'     // Much larger text
  } : {
    tint: 0xff0000,      // BRIGHT RED tint (same as foul)
    tintAlpha: 0.7,      // Even more visible for turnovers
    duration: 3000,      // 3.0s
    iconText: 'TO',
    iconDuration: 3000,  // 3.0s
    iconSize: '48px'     // Much larger text
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
  
  // ✅ REMOVED: Red full screen overlay (user requested removal)
  // Red visual feedback now only comes from announcement containers (e.g., AND-1 red box)
  
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
 * Clear red foul tint for a player (e.g. when they foul out and we show the foul-out popup).
 * Prevents the sprite from staying "dead" / red when navigating to lineup.
 */
export function clearFoulTintForPlayer(scene, playerId) {
  if (!playerId || !scene?.playerSprites) return;
  const sprite = scene.playerSprites[playerId];
  if (!sprite) return;
  if (sprite.type === 'Container') {
    sprite.list.forEach(child => {
      if (child.clearTint) child.clearTint();
    });
  } else if (sprite.clearTint) {
    sprite.clearTint();
  }
}

/**
 * Trigger turnover effect for a player
 */
export function triggerTurnoverEffect(scene, playerId) {
  triggerNegativeAction(scene, playerId, 'turnover');
}

/**
 * Trigger green flash for made shots (HCO, Fast Break, Putback)
 * ✅ REMOVED: Full screen green overlay (user requested removal)
 * Visual feedback now only comes from announcement containers
 * @param {boolean} hasAndOne - Unused (kept for API compatibility)
 */
export function triggerMadeShotFlash(scene, hasAndOne = false) {
  // ✅ REMOVED: Green full screen overlay (user requested removal)
  // Green visual feedback now only comes from announcement containers
  // Red box for AND-1 is handled by showAndOneAnnouncement() in announcements.js
  return;
}

