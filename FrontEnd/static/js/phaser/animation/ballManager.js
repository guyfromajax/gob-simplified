import { generateBallTween } from "./generateBallTween.js";

export function lockBallToPlayer(ballSprite, playerSprite) {
  if (!ballSprite || !playerSprite) {
    console.warn("⚠️ lockBallToPlayer skipped: missing sprite");
    return;
  }

  console.log("🔒 lockBallToPlayer invoked for:", playerSprite.name || playerSprite);

  const { x, y } = playerSprite;
  ballSprite.setPosition(x, y);
  ballSprite.setVisible(true);
}



/**
 * Animate the ball flying from one point to another.
 */
export function passBall({
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  fromTimestamp,
  toTimestamp
}) {
  generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: fromTimestamp,
    endTimestamp: toTimestamp
  });
}

/**
 * Hide the ball (e.g. post-shot, end of play)
 */
export function hideBall(ballSprite) {
  if (ballSprite) ballSprite.setVisible(false);
}

// import { lockBallToPlayer, passBall } from "./ballManager.js";

// // Lock to player
// lockBallToPlayer(ballSprite, playerSprites[playerId]);

// // Animate pass
// passBall({
//   scene,
//   ballSprite,
//   fromCoords: passStep.coords,
//   toCoords: receiveStep.coords,
//   fromTimestamp: passStep.timestamp,
//   toTimestamp: receiveStep.timestamp
// });
