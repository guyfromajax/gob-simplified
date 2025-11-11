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
    tint: 0xff6666,      // Light red tint
    tintAlpha: 0.3,      // Lower opacity for fouls
    duration: 3000,      // 3.0s - long enough to notice
    iconText: 'F',
    iconDuration: 3000,  // 3.0s - matches tint duration
    animation: 'pulse'   // Pulse effect
  } : {
    tint: 0xff3333,      // Darker red tint
    tintAlpha: 0.5,      // Higher opacity for turnovers
    duration: 3000,      // 3.0s - long enough to notice
    iconText: 'TO',
    iconDuration: 3000,  // 3.0s - matches tint duration
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
  
  // Apply animation (pulse or shake)
  if (config.animation === 'pulse') {
    // Pulse: Scale up and down
    scene.tweens.add({
      targets: sprite,
      scaleX: 1.15,
      scaleY: 1.15,
      duration: 150,
      yoyo: true,
      repeat: 1,
      ease: 'Sine.easeInOut'
    });
  } else if (config.animation === 'shake') {
    // Shake: Horizontal wobble (3-4 small wobbles)
    const originalX = sprite.x;
    scene.tweens.add({
      targets: sprite,
      x: originalX + 3,
      duration: 50,
      yoyo: true,
      repeat: 3,
      ease: 'Sine.easeInOut',
      onComplete: () => {
        sprite.x = originalX; // Ensure exact position restoration
      }
    });
  }
  
  // Create icon above sprite
  const iconText = scene.add.text(sprite.x, sprite.y - 40, config.iconText, {
    fontSize: '24px',
    fontStyle: 'bold',
    color: '#ffffff',
    stroke: '#ff0000',
    strokeThickness: 4,
    shadow: {
      offsetX: 2,
      offsetY: 2,
      color: '#000000',
      blur: 4,
      fill: true
    }
  });
  iconText.setOrigin(0.5, 0.5);
  iconText.setDepth(1000); // Ensure it's above all other sprites
  
  // Fade out icon
  scene.tweens.add({
    targets: iconText,
    alpha: 0,
    y: sprite.y - 60, // Float upward
    duration: config.iconDuration,
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

