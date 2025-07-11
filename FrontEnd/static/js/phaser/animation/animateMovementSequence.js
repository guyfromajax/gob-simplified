import { gridToPixels } from "../utils/gridToPixels.js";

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
 * @param {string} position - Position label (e.g. PG, SG)
 * @param {object} currentBallOwnerRef - A shared ref passed from playTurnAnimation
 * @returns {Promise}
 */
export function animateMovementSequence({ 
  scene, 
  sprite, 
  movement, 
  onAction, 
  ballSprite, 
  hasBallAtStep, 
  position, 
  currentBallOwnerRef 
}) {
  return new Promise((resolve) => {
    if (!movement || movement.length < 2) return resolve();

    let stepIndex = 1;

    const animateNextStep = () => {
      if (stepIndex >= movement.length) return resolve();

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const duration = (curr.timestamp - prev.timestamp) * 3;

      const { x: targetX, y: targetY } = gridToPixels(
        curr.coords.x,
        curr.coords.y,
        scene.game.config.width,
        scene.game.config.height
      );

      const ownsBallThisStep = hasBallAtStep?.[stepIndex] === true;

      // If this player owns the ball this step, set them as the current owner
      if (ownsBallThisStep) {
        currentBallOwnerRef.value = sprite;
        if (ballSprite?.setVisible) {
          ballSprite.setVisible(true);
        }
      }

      scene.tweens.add({
        targets: [sprite],
        x: targetX,
        y: targetY,
        duration,
        ease: "Linear",
        onStart: () => {
          if (onAction) onAction(curr.action, sprite, curr.timestamp);
        },
        onUpdate: () => {
          // Only the current owner gets to update the ball
          if (currentBallOwnerRef.value === sprite && ballSprite?.setPosition) {
            ballSprite.setPosition(sprite.x, sprite.y);
          }
        },
        onComplete: () => {
          stepIndex++;
          animateNextStep();
        }
      });
    };

    // Handle step 0 before any tween begins
    if (hasBallAtStep?.[0]) {
      currentBallOwnerRef.value = sprite;
      if (ballSprite?.setPosition && ballSprite?.setVisible) {
        ballSprite.setPosition(sprite.x, sprite.y);
        ballSprite.setVisible(true);
      } else {
        console.warn("⚠️ ballSprite not ready at step 0 lock.");
      }
    }

    animateNextStep();
  });
}
