import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";

/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
function updateBallOwnership({ ballSprite, animations, playerSprites, stepIndex }) {
  for (const anim of animations) {
    const sprite = playerSprites[anim.playerId];
    const hasBall = anim.hasBallAtStep?.[stepIndex];

    if (hasBall && sprite && ballSprite?.setPosition) {
      ballSprite.setPosition(sprite.x, sprite.y);
      ballSprite.setVisible(true);
      break;
    }
  }
}

/**
 * Smoothly move all players to their step 0 positions before possession begins.
 * Locks the ball to the player with hasBallAtStep[0] during this setup tween.
 */
async function runSetupTween({ scene, ballSprite, animations, playerSprites }) {
  const stepIndex = 0;
  const promises = [];

  let ballOwnerSprite = null;

  for (const anim of animations) {
    const sprite = playerSprites[anim.playerId];
    const firstStep = anim.movement?.[0];
    const hasBall = anim.hasBallAtStep?.[0];

    if (!sprite || !firstStep) continue;

    const { x, y } = gridToPixels(
      firstStep.coords.x,
      firstStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    if (hasBall) ballOwnerSprite = sprite;

    promises.push(new Promise((resolve) => {
      scene.tweens.add({
        targets: [sprite],
        x,
        y,
        duration: 500,
        ease: "Linear",
        onUpdate: () => {
          if (sprite === ballOwnerSprite && ballSprite?.setPosition) {
            ballSprite.setPosition(sprite.x, sprite.y);
            ballSprite.setVisible(true);
          }
        },
        onComplete: resolve
      });
    }));
  }

  await Promise.all(promises);

  // Snap ball to final location after setup tween completes
  updateBallOwnership({
    ballSprite,
    animations,
    playerSprites,
    stepIndex: 0
  });
}

/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  const maxSteps = Math.max(
    ...turnData.animations.map(anim => anim.movement.length)
  );

  // 🔶 Pre-possession: Move players to their step 0 positions
  await runSetupTween({
    scene,
    ballSprite,
    animations: turnData.animations,
    playerSprites
  });

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    updateBallOwnership({
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      stepIndex
    });

    const promises = [];

    for (const anim of turnData.animations) {
      const sprite = playerSprites[anim.playerId];
      const movement = anim.movement;

      if (!sprite || stepIndex >= movement.length) continue;

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const duration = (curr.timestamp - prev.timestamp) * 3;

      const promise = animateStep({
        scene,
        sprite,
        step: curr,
        duration
      });

      promises.push(promise);
    }

    await Promise.all(promises);
  }
}
