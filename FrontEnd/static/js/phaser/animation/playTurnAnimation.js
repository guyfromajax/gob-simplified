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
      break; // Only one player should have the ball
    }
  }
}

/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  const maxSteps = Math.max(
    ...turnData.animations.map(anim => anim.movement.length)
  );

  // 🟠 Build player sprites at step 0 before any animation begins
  // for (const anim of turnData.animations) {
  //   const sprite = playerSprites[anim.playerId];
  //   const first = anim.movement[0];
  
  //   if (sprite && first) {
  //     const { x, y } = gridToPixels(
  //       first.coords.x,
  //       first.coords.y,
  //       scene.game.config.width,
  //       scene.game.config.height
  //     );
  //     sprite.setPosition(x, y);
  //   }
  // }

  // 🟠 Position the ball at step 0 before any animation begins
  updateBallOwnership({
    ballSprite,
    animations: turnData.animations,
    playerSprites,
    stepIndex: 0
  });
  

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    // 🔁 Update ball lock once per step
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
