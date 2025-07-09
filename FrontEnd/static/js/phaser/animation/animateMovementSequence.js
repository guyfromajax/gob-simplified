import { gridToPixels } from "../utils/gridToPixels.js";

export function animateMovementSequence({ scene, sprite, movement, onAction }) {
  if (!movement || movement.length < 2) return;

  for (let i = 1; i < movement.length; i++) {
    const prev = movement[i - 1];
    const curr = movement[i];

    const duration = curr.timestamp - prev.timestamp;

    const { x: targetX, y: targetY } = gridToPixels(
      curr.coords.x,
      curr.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

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

  