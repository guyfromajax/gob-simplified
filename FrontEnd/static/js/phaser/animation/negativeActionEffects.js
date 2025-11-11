/**
 * Negative Action Effects - Visual feedback for fouls and turnovers
 * 
 * Provides tiered visual feedback:
 * - FOUL: Red tint (0.3) + pulse + "F" icon (1.0s)
 * - TURNOVER: Red tint (0.5) + shake + "TO" icon (1.0s)
 */

export function triggerNegativeAction(scene, playerId, actionType = 'foul') {
  const sprite = scene.playerSprites?.[playerId];
  if (!sprite) {
    console.warn(`⚠️ Cannot trigger negative action: sprite not found for ${playerId}`);
    return;
  }
  
  const isFoul = actionType === 'foul';
  const config = isFoul ? {
    tint: 0xff6666,      // Light red tint
    tintAlpha: 0.3,      // Lower opacity for fouls
    duration: 600,       // 0.6s
    iconText: 'F',
    iconDuration: 1000,  // 1.0s
    animation: 'pulse'   // Pulse effect
  } : {
    tint: 0xff3333,      // Darker red tint
    tintAlpha: 0.5,      // Higher opacity for turnovers
    duration: 800,       // 0.8s
    iconText: 'TO',
    iconDuration: 1000,  // 1.0s
    animation: 'shake'   // Shake effect
  };
  
  console.log(`💥 Triggering ${actionType} effect for player ${playerId}`);
  
  // Store original tint to restore later
  const originalTint = sprite.tint;
  const originalAlpha = sprite.alpha;
  
  // Apply red tint
  sprite.setTint(config.tint);
  sprite.setAlpha(1.0 - config.tintAlpha); // Reduce alpha to simulate overlay
  
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
    sprite.clearTint();
    sprite.setAlpha(originalAlpha);
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

