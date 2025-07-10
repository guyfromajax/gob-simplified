import { animateMovementSequence } from "./animateMovementSequence.js";
import { updateBallOwnership } from "./ballManager.js";
import { getPlayerIdByPosition } from "../utils/playerUtils.js"; 

export async function playTurnAnimation({ scene, playerSprites, turnData, ballSprite, onAction }) {
  const promises = [];

  console.log("✅ playTurnAnimation received:", { scene, playerSprites, turnData });
  const pgId = getPlayerIdByPosition("PG", scene.simData?.players || []);
  console.log("👤 PG ID:", pgId);

  const pgAnimation = turnData.animations.find(a => a.playerId === pgId);
  console.log("🧠 PG hasBallAtStep:", pgAnimation?.hasBallAtStep);

  for (const anim of turnData.animations) {
    console.log("👥 Players with animations:", turnData.animations.map(a => a.playerId));
    console.log("👤 PG ID:", playerSprites["PG"]?.playerId); // or however you're mapping positions
    const sprite = playerSprites[anim.playerId];
    const movement = anim.movement;

    // console.log("playerSprites:", playerSprites);

    if (!sprite || !movement) continue;

    const promise = new Promise((resolve) => {
      animateMovementSequence({
        scene,
        sprite,
        movement,
        hasBallAtStep: anim.hasBallAtStep,
        ballSprite,
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

