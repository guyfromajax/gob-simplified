import Phaser from "phaser";
import { generateBallTween } from "./generateBallTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";

// Debug flag for logging shot details
const SHOT_DEBUG = false;

// Hoop locations in grid coordinates for each team
const HOME_RIM_COORDS = { x: 94, y: 25 };
const AWAY_RIM_COORDS = { x: 6, y: 25 };

export function lockBallToPlayer(scene, ballSprite, playerSprite) {
  if (!ballSprite || !playerSprite) {
    console.warn("⚠️ lockBallToPlayer skipped: missing sprite");
    return;
  }

  console.log(
    "🔒 lockBallToPlayer invoked for:",
    playerSprite.name || playerSprite
  );

  if (scene?.tweens) {
    scene.tweens.killTweensOf(ballSprite);
  }

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

/**
 * Launches a shot toward the rim with a simple two-part arc.
 * Resolves after the ball reaches the rim.
 */
export function shootBall({
  scene,
  ballSprite,
  fromCoords,
  startTimestamp,
  result,
  shooterPos,
  isHomeTeam
}) {
  if (!scene || !ballSprite) return Promise.resolve();
  const start = gridToPixels(
    fromCoords.x,
    fromCoords.y,
    scene.game.config.width,
    scene.game.config.height
  );
  const rimCoords = isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const rim = gridToPixels(
    rimCoords.x,
    rimCoords.y,
    scene.game.config.width,
    scene.game.config.height
  );
  const mid = {
    x: (start.x + rim.x) / 2,
    y: Math.min(start.y, rim.y) - 40
  };

  // Scale the flight duration based on shot distance for more natural pacing
  const baseDuration = 1000; // minimum duration in ms
  const shotDistance = Phaser.Math.Distance.Between(start.x, start.y, rim.x, rim.y);
  const duration = Math.max(baseDuration, shotDistance * 5); // 5ms per pixel

  ballSprite.setPosition(start.x, start.y);
  ballSprite.setVisible(true);

  if (SHOT_DEBUG) {
    const endTs = startTimestamp + duration;
    const outcomeSource = result ? "explicit" : "inferred";
    console.log(
      `[shot] pos=${shooterPos} start=(${start.x},${start.y}) rim=(${rim.x},${rim.y}) ` +
        `ts=${startTimestamp}->${endTs} outcome=${result || "UNKNOWN"} source=${outcomeSource}`
    );
  }

  return new Promise((resolve) => {
    scene.tweens.add({
      targets: ballSprite,
      x: mid.x,
      y: mid.y,
      duration: duration / 2,
      ease: "Sine.easeOut",
      onComplete: () => {
        scene.tweens.add({
          targets: ballSprite,
          x: rim.x,
          y: rim.y,
          duration: duration / 2,
          ease: "Sine.easeIn",
          onComplete: () => {
            if (result === "MAKE") {
              // Slight pause before hiding to trigger existing make flow
              scene.time.delayedCall(250, () => {
                ballSprite.setVisible(false);
                resolve();
              });
            } else if (result === "MISS") {
              // Bounce the ball off the rim
              const bounceGridX = isHomeTeam
                ? rimCoords.x - 6
                : rimCoords.x + 6;
              const bounceGridY =
                rimCoords.y + Phaser.Math.Between(-6, 6);
              const bounce = gridToPixels(
                bounceGridX,
                bounceGridY,
                scene.game.config.width,
                scene.game.config.height
              );

              scene.tweens.add({
                targets: ballSprite,
                x: bounce.x,
                y: bounce.y,
                duration: duration / 3,
                ease: "Sine.easeOut",
                onComplete: resolve
              });
            } else {
              resolve();
            }
          }
        });
      }
    });
  });
}

/**
 * Checks which player has the ball at the current animation step
 * and locks the ball to that player's sprite.
 *
 * @param {Phaser.GameObjects.Image} ballSprite - The Phaser ball image
 * @param {Array} animations - Array of player animation objects for the current turn
 * @param {Object} playerSprites - Map of playerId → Phaser sprite
 * @param {number} currentTimestamp - The current animation timestamp (ms)
 */
export function updateBallOwnership(scene, ballSprite, animations, playerSprites, currentTimestamp) {
  for (const anim of animations) {
    const { playerId, hasBallAtStep, movement } = anim;
    if (!hasBallAtStep || !movement || !movement.length) continue;

    // Find current step index based on timestamp
    let stepIndex = 0;
    while (
      stepIndex < movement.length - 1 &&
      currentTimestamp >= movement[stepIndex + 1].timestamp
    ) {
      stepIndex++;
    }

    if (hasBallAtStep[stepIndex]) {
      const playerSprite = playerSprites[playerId];
      if (playerSprite) {
        lockBallToPlayer(scene, ballSprite, playerSprite);
      }
      break; // Only one player can have the ball
    }
  }
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
