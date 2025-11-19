import { gridToPixels } from '../utils/gridToPixels.js';
import animationConfig from './animation_config.js';
import { animateBallToPosition } from './ballAnimationSimple.js';

/**
 * Generate ball tween animation (STEP 3 MIGRATION)
 * Now uses animateBallToPosition() instead of direct scene.tweens.add()
 */
export async function generateBallTween({
    scene,
    ballSprite,
    startCoords,
    endCoords,
    startTimestamp,
    endTimestamp,
    type = 'pass'
  }) {
    if (!ballSprite || !scene) return;

    const startPixels = gridToPixels(startCoords.x, startCoords.y, scene.game.config.width, scene.game.config.height);
    const endPixels = gridToPixels(endCoords.x, endCoords.y, scene.game.config.width, scene.game.config.height);

    // Set starting position first
    ballSprite.setPosition(startPixels.x, startPixels.y);
    ballSprite.setVisible(true);

    if (!animationConfig.enableBallTween) {
      ballSprite.setPosition(endPixels.x, endPixels.y);
      return;
    }

    const cfg = animationConfig[type] || animationConfig.pass;
    const duration = Math.max(endTimestamp - startTimestamp, cfg.duration);

    // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of direct scene.tweens.add()
    // animateBallToPosition() handles BallController integration and distance-based duration
    await animateBallToPosition(scene, endPixels, {
      duration,
      easing: cfg.easing
    });
  }
  
