export function animateMovementSequence({ scene, sprite, movement, onAction }) {
    if (!movement || movement.length < 2) return;
  
    for (let i = 1; i < movement.length; i++) {
      const prev = movement[i - 1];
      const curr = movement[i];
  
      const duration = curr.timestamp - prev.timestamp;
      const targetX = (curr.coords.x / 100) * scene.game.config.width;
      const targetY = ((50 - curr.coords.y) / 50) * scene.game.config.height;
  
      scene.tweens.add({
        targets: sprite,
        x: targetX,
        y: targetY,
        duration,
        ease: "Linear",
        onStart: () => {
          if (onAction) onAction(curr.action, sprite, curr.timestamp);
        },
      });
    }
  }
  