import { animateMovementSequence } from "./animateMovementSequence.js";
import { updateBallOwnership } from "./ballManager.js";

export async function playTurnAnimation({ scene, playerSprites, turnData, onAction }) {
  const promises = [];

  console.log("✅ playTurnAnimation received:", { scene, playerSprites, turnData });
  for (const anim of turnData.animations) {
    const sprite = playerSprites[anim.playerId];
    const movement = anim.movement;

    // console.log("playerSprites:", playerSprites);

    if (!sprite || !movement) continue;

    const promise = new Promise((resolve) => {
      animateMovementSequence({
        scene,
        sprite,
        movement,
        onAction: (action, sprite, timestamp) => {
          if (onAction) onAction(action, sprite, timestamp);
        },
      });

      // estimate final timestamp duration for setTimeout fallback
      const totalDuration =
        movement.at(-1).timestamp - movement[0].timestamp;

      setTimeout(resolve, totalDuration + 50); // small buffer
    });

    promises.push(promise);
  }

  await Promise.all(promises);
  // Get latest timestamp across all players in this turn
  const latestTimestamp = Math.max(
    ...turnData.animations.flatMap(anim => anim.movement.map(m => m.timestamp))
  );

  // Track elapsed time for this turn
  let currentTimestamp = 0;
  const tickInterval = 33; // approx 30 FPS
  const timer = scene.time.addEvent({
    delay: tickInterval,
    callback: () => {
      currentTimestamp += tickInterval;

      updateBallOwnership(scene.ballSprite, turnData.animations, playerSprites, currentTimestamp);

      if (currentTimestamp >= latestTimestamp + 100) {
        timer.remove(); // stop this timer
      }
    },
    loop: true,
  });

}

// import { onAction } from "./onAction.js";

// Pass it into animateMovementSequence()
// animateMovementSequence({
//   scene,
//   sprite,
//   movement,
//   onAction: onAction, // <—
// });

