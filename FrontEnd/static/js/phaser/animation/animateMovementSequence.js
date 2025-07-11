import { gridToPixels } from "../utils/gridToPixels.js";
import { lockBallToPlayer } from "./ballManager.js";

/**
 * Animates a player's movement over time using chained tweens.
 * Resolves only after the final tween completes.
 *
 * @param {object} scene - The Phaser scene
 * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
 * @param {Array} movement - Array of movement steps
 * @param {Function} onAction - Callback for animation events
 * @param {Phaser.GameObjects.Sprite} ballSprite - Ball sprite to attach when possessed
 * @param {Array} hasBallAtStep - Boolean array mapping possession per step
 * @returns {Promise} resolves when all tweens finish
 */
export function animateMovementSequence({ scene, sprite, movement, onAction, ballSprite, hasBallAtStep, position }) {

  console.log(`🧪 animateMovementSequence → Position: ${position}`);
  console.log("🎯 Step 0 possession check → hasBallAtStep[0]:", hasBallAtStep?.[0]);
  console.log("🎯 Sprite exists:", !!sprite);

  return new Promise((resolve) => {
    if (!movement || movement.length < 2) return resolve();

    let stepIndex = 1;

    console.log("🎯 ballSprite ready:", !!ballSprite, "| sprite:", sprite?.name || "[unknown]");
    if (hasBallAtStep?.[0] && sprite && ballSprite && ballSprite.setPosition) {
      console.log("🔒 Locking ball to starting player:", position);
      lockBallToPlayer(ballSprite, sprite);
    } else {
      console.warn("⚠️ Could not lock ball to starting player — check ballSprite and sprite validity");
    }    
    
    const animateNextStep = () => {
      if (stepIndex >= movement.length) {
        return resolve(); // done
      }

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const duration = (curr.timestamp - prev.timestamp) * 3;

      const { x: targetX, y: targetY } = gridToPixels(
        curr.coords.x,
        curr.coords.y,
        scene.game.config.width,
        scene.game.config.height
      );

      const targets = [sprite];

      if (hasBallAtStep?.[stepIndex]) {
        lockBallToPlayer(ballSprite, sprite); // lock immediately
        targets.push(ballSprite);             // tween ball with player
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
          if (hasBallAtStep?.[stepIndex]) {
            lockBallToPlayer(ballSprite, sprite);
          }
        },
        onComplete: () => {
          if (hasBallAtStep?.[stepIndex]) {
            lockBallToPlayer(ballSprite, sprite); // final lock after move
          }
          stepIndex++;
          animateNextStep();
        }
      });
    };

    // Initial check for starting possession
    if (hasBallAtStep?.[0]) {
      lockBallToPlayer(ballSprite, sprite);
    }

    animateNextStep();
  });
}
