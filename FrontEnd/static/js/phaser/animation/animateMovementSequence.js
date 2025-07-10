import { gridToPixels } from "../utils/gridToPixels.js";
import { lockBallToPlayer } from "./ballManager.js";

/**
 * Animates a player's movement over time using Phaser tweens.
 * If the player has the ball during a step, the ballSprite moves with them.
 *
 * @param {object} scene - The Phaser scene
 * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
 * @param {Array} movement - Array of movement steps for this player
 * @param {Function} onAction - Callback fired when an action occurs
 * @param {Phaser.GameObjects.Sprite} ballSprite - The ball sprite
 * @param {Array} hasBallAtStep - Boolean array indicating ball possession per step
 */
export function animateMovementSequence({ scene, sprite, movement, onAction, ballSprite, hasBallAtStep }) {
  if (!movement || movement.length < 2) return;

  if (hasBallAtStep?.[0]) {
    lockBallToPlayer(ballSprite, sprite);
  }
  console.log("🎯 Sprite:", sprite.name, "| hasBallAtStep:", hasBallAtStep);

  
  for (let i = 1; i < movement.length; i++) {
    const prev = movement[i - 1];
    const curr = movement[i];
    const duration = (curr.timestamp - prev.timestamp) * 3;

    const { x: targetX, y: targetY } = gridToPixels(
      curr.coords.x,
      curr.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    const targets = [sprite];

    // If player has ball at this step, animate the ball with them
    if (hasBallAtStep?.[i]) {
      lockBallToPlayer(ballSprite, sprite); // Lock position now
      targets.push(ballSprite);
    }

    scene.tweens.add({
      targets,
      x: targetX,
      y: targetY,
      duration,
      ease: "Linear",
      onStart: () => {
        if (onAction) onAction(curr.action, sprite, curr.timestamp);
      },
      onUpdate: () => {
        if (hasBallAtStep?.[i]) {
          lockBallToPlayer(ballSprite, sprite);
        }
      },
      onComplete: () => {
        // If this was the final step where player had the ball, leave ball locked
        if (hasBallAtStep?.[i]) {
          lockBallToPlayer(ballSprite, sprite);
        }
      }
    });
  }
}




// export function animateMovementSequence({ scene, sprite, movement, onAction }) {
//   if (!movement || movement.length < 2) return;

//   for (let i = 1; i < movement.length; i++) {
//     const prev = movement[i - 1];
//     const curr = movement[i];

//     const duration = (curr.timestamp - prev.timestamp) * 3;

//     // 🔍 Log movement and coordinates
//     // console.log("🔁 Tweening sprite:", sprite.name || sprite.playerId || "unknown");
//     // console.log("  → From:", JSON.stringify(prev.coords), "To:", JSON.stringify(curr.coords), "Duration:", duration);

//     const { x: targetX, y: targetY } = gridToPixels(
//       curr.coords.x,
//       curr.coords.y,
//       scene.game.config.width,
//       scene.game.config.height
//     );

//     console.log("  → Target pixels:", { targetX, targetY });

//     scene.tweens.add({
//       targets: sprite,
//       x: targetX,
//       y: targetY,
//       duration,
//       ease: "Linear",
//       onStart: () => {
//         if (onAction) onAction(curr.action, sprite, curr.timestamp);
//       },
//     });
//   }
// }


  