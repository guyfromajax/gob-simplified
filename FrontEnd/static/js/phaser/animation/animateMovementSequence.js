import { gridToPixels } from "../utils/gridToPixels.js";

export function animateMovementSequence({ scene, sprite, movement, onAction }) {
  if (!movement || movement.length < 2) return;

  for (let i = 1; i < movement.length; i++) {
    const prev = movement[i - 1];
    const curr = movement[i];

    const duration = curr.timestamp - prev.timestamp;

    // 🔍 Log movement and coordinates
    console.log("🔁 Tweening sprite:", sprite.name || sprite.playerId || "unknown");
    console.log("  → From:", JSON.stringify(prev.coords), "To:", JSON.stringify(curr.coords), "Duration:", duration);

    const { x: targetX, y: targetY } = gridToPixels(
      curr.coords.x,
      curr.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    console.log("  → Target pixels:", { targetX, targetY });

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


  