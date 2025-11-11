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
  
  // Apply animation (pulse or shake) - MORE DRAMATIC
  if (config.animation === 'pulse') {
    // Pulse: Bigger scale change, multiple pulses
    scene.tweens.add({
      targets: sprite,
      scaleX: 1.3,
      scaleY: 1.3,
      duration: 300,
      yoyo: true,
      repeat: 3,  // Pulse 3 times
      ease: 'Sine.easeInOut'
    });
  } else if (config.animation === 'shake') {
    // Shake: Much more violent horizontal wobble
    const originalX = sprite.x;
    scene.tweens.add({
      targets: sprite,
      x: originalX + 10,  // Increased from 3 to 10
      duration: 80,
      yoyo: true,
      repeat: 6,  // More shakes
      ease: 'Sine.easeInOut',
      onComplete: () => {
        sprite.x = originalX; // Ensure exact position restoration
      }
    });
  }
  
  // Create LARGE icon above sprite
  const iconText = scene.add.text(sprite.x, sprite.y - 60, config.iconText, {
    fontSize: config.iconSize,  // Now 48px
    fontStyle: 'bold',
    color: '#ffff00',  // YELLOW text (more visible than white)
    stroke: '#ff0000',  // Red outline
    strokeThickness: 8,  // Thicker stroke
    shadow: {
      offsetX: 4,
      offsetY: 4,
      color: '#000000',
      blur: 8,
      fill: true
    }
  });
  iconText.setOrigin(0.5, 0.5);
  iconText.setDepth(1000); // Ensure it's above all other sprites
  
  // Pulse the icon while it's visible
  scene.tweens.add({
    targets: iconText,
    scale: 1.2,
    duration: 400,
    yoyo: true,
    repeat: -1,  // Infinite pulse
    ease: 'Sine.easeInOut'
  });
  
  // Fade out icon after duration
  scene.tweens.add({
    targets: iconText,
    alpha: 0,
    y: sprite.y - 100, // Float upward more
    duration: config.iconDuration,
    delay: 2500,  // Stay visible for most of the duration, then fade
    ease: 'Cubic.easeOut',
    onComplete: () => {
      iconText.destroy();
    }
  });
  
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

