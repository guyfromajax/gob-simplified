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
  
    const startX = (startCoords.x / 100) * scene.game.config.width;
    const startY = ((50 - startCoords.y) / 50) * scene.game.config.height;
    const endX = (endCoords.x / 100) * scene.game.config.width;
    const endY = ((50 - endCoords.y) / 50) * scene.game.config.height;
  
    // Set starting position first
    ballSprite.setPosition(startX, startY);
    ballSprite.setVisible(true);
  
    scene.tweens.add({
      targets: ballSprite,
      x: endX,
      y: endY,
      duration,
      ease: "Sine.easeInOut",
      onComplete: () => {
        // Optionally hide or lock ball to receiver after pass completes
      }
    });
  }
  