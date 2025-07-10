import { animateMovementSequence } from "./animateMovementSequence.js";

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
}

// import { onAction } from "./onAction.js";

// Pass it into animateMovementSequence()
// animateMovementSequence({
//   scene,
//   sprite,
//   movement,
//   onAction: onAction, // <—
// });

