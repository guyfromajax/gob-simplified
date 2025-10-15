import { gridToPixels } from '../utils/gridToPixels.js';
import animationConfig from './animation_config.js';
import { getBallController } from './BallControllerAdapter.js';

export function generateBallTween({
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

    const ballController = getBallController();
    let controllerStartedFlight = false;
    if (ballController && !ballController.isInFlight) {
      const flightOpts = { duration, ease: cfg.easing };
      controllerStartedFlight = ballController.startFlight(endPixels, flightOpts) !== false;
    }

    scene.tweens.add({
      targets: ballSprite,
      x: endPixels.x,
      y: endPixels.y,
      duration,
      ease: cfg.easing,
      onComplete: () => {
        if (controllerStartedFlight && ballController) {
          ballController.endFlight(null, { keepVisible: true });
        }
        // Optionally hide or lock ball to receiver after pass completes
      }
    });
  }
  
