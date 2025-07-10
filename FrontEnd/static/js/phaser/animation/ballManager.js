import { generateBallTween } from "./generateBallTween.js";

/**
 * Attach the ball sprite to a given player container.
 */
export function lockBallToPlayer(ballSprite, playerSprite) {
  const { x, y } = playerSprite.getCenter();
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
