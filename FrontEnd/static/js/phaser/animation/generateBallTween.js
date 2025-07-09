import { gridToPixels } from '../utils/gridToPixels.js';

export function generateBallTween({
    scene,
    ballSprite,
    startCoords,
    endCoords,
    startTimestamp,
    endTimestamp
  }) {
    if (!ballSprite || !scene) return;
  
    const duration = endTimestamp - startTimestamp;
  
    const startPixels = gridToPixels(startCoords.x, startCoords.y, scene.game.config.width, scene.game.config.height);
    const endPixels = gridToPixels(endCoords.x, endCoords.y, scene.game.config.width, scene.game.config.height);
  
    // Set starting position first
    ballSprite.setPosition(startPixels.x, startPixels.y);
    ballSprite.setVisible(true);
  
    scene.tweens.add({
      targets: ballSprite,
      x: endPixels.x,
      y: endPixels.y,
      duration,
      ease: "Sine.easeInOut",
      onComplete: () => {
        // Optionally hide or lock ball to receiver after pass completes
      }
    });
  }
  