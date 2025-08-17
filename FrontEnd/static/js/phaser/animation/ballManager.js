import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { generateBallTween } from "./generateBallTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";

// Debug flags for logging shot / rebound details
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export const INBOUND_DEBUG = false;

// Hoop locations in grid coordinates for each team
const HOME_RIM_COORDS = { x: 91, y: 25 };
const AWAY_RIM_COORDS = { x: 9, y: 25 };
const BALL_SPRITE_DEPTH = 1000;

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

  if (ballSprite.setDepth) {
    ballSprite.setDepth(BALL_SPRITE_DEPTH);
  }

  // Track final ball owner on the scene if possible
  if (scene) {
    if (playerSprite.playerId) {
      scene.ballAttachedToPlayerId = playerSprite.playerId;
    } else if (scene.playerSprites) {
      for (const [pid, sprite] of Object.entries(scene.playerSprites)) {
        if (sprite === playerSprite) {
          scene.ballAttachedToPlayerId = pid;
          break;
        }
      }
    }
  }
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

// Baseline inbound pass from one coordinate to another
export function animateInboundPass(
  scene,
  ballSprite,
  fromCoords,
  toCoords,
  startTs,
  endTs
) {
  generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: startTs,
    endTimestamp: endTs
  });
}

/**
 * Hide the ball (e.g. post-shot, end of play)
 */
export function hideBall(ballSprite) {
  if (ballSprite) ballSprite.setVisible(false);
}

/**
 * Launches a shot toward the rim along a single tweened path.
 * Resolves after the ball reaches the rim.
*/
export function shootBall({
  scene,
  ballSprite,
  fromCoords,
  startTimestamp,
  result,
  shooterPos,
  shooterId,
  shooterTeamId,
  homeTeamId,
  stepIndex,
  turnIndex
}) {
  if (!scene || !ballSprite) return Promise.resolve();

  const isHomeTeam = shooterTeamId === homeTeamId;

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

  // Scale the flight duration based on shot distance for more natural pacing
  const baseDuration = 700; // minimum duration in ms
  const shotDistance = Phaser.Math.Distance.Between(start.x, start.y, rim.x, rim.y);
  const duration = Math.max(baseDuration, shotDistance * 3); // 3ms per pixel

  ballSprite.setPosition(start.x, start.y);
  ballSprite.setVisible(true);

  if (SHOT_DEBUG) {
    const endTs = startTimestamp + duration;
    const outcomeSource = result ? "explicit" : "inferred";
    console.log(
      `[shot] shooter=${shooterId} team=${shooterTeamId} ` +
        `(matches home? ${isHomeTeam}) ` +
        `pos=${shooterPos} start=(${start.x},${start.y}) ` +
        `rim=(${rim.x},${rim.y}) ` +
        `step=${stepIndex ?? "?"} turn=${turnIndex ?? "?"} ` +
        `ts=${startTimestamp}->${endTs} outcome=${result || "UNKNOWN"} source=${outcomeSource}`
    );
  }

  return new Promise((resolve) => {
    scene.tweens.add({
      targets: ballSprite,
      x: rim.x,
      y: rim.y,
      duration,
      ease: "Sine.easeInOut",
      onComplete: () => {
        if (result === "MAKE") {
          console.log("score");
          console.log("rimHoldStart");
          const finish = () => {
            console.log("rimHoldEnd");
            resolve();
          };
          if (scene.time?.delayedCall) {
            scene.time.delayedCall(1000, finish);
          } else {
            setTimeout(finish, 1000);
          }
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
            onComplete: () =>
              resolve({ grid: { x: bounceGridX, y: bounceGridY } })
          });
        } else {
          resolve();
        }
      }
    });
  });
}

/**
 * Animate players collapsing toward a missed shot for a rebound.
 *
 * @param {Object} opts
 * @param {Phaser.Scene} opts.scene
 * @param {Phaser.GameObjects.Image} opts.ballSprite
 * @param {Object} opts.playerSprites - map of playerId -> sprite
 * @param {Array} opts.animations - original turn animations
 * @param {string} opts.rebounderId - playerId of the rebounder
 * @param {{x:number, y:number}} opts.ballSpot - grid coordinates where ball landed
 */
export function animateRebound({
  scene,
  ballSprite,
  playerSprites,
  animations,
  rebounderId,
  ballSpot
}) {
  if (!scene || !ballSprite || !ballSpot) return Promise.resolve();

  const promises = [];
  const finalPositions = [];
  const MIN_X_SEP = 3;
  const MIN_Y_SEP = 2;
  const spotPx = gridToPixels(
    ballSpot.x,
    ballSpot.y,
    scene.game.config.width,
    scene.game.config.height
  );

  ballSprite.setPosition(spotPx.x, spotPx.y);
  ballSprite.setVisible(true);

  const rebounderSprite = playerSprites[rebounderId];
  if (rebounderSprite) {
    finalPositions.push({ playerId: rebounderId, grid: { ...ballSpot } });
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: rebounderSprite,
          x: spotPx.x,
          y: spotPx.y,
          duration: 300,
          ease: "Linear",
          onComplete: () => {
            lockBallToPlayer(scene, ballSprite, rebounderSprite);
            resolve();
          },
          onStop: resolve
        });
      })
    );
  }

  const offsets = [
    { x: 1, y: 0 },
    { x: -1, y: 0 },
    { x: 0, y: 1 },
    { x: 0, y: -1 },
    { x: 1, y: 1 },
    { x: -1, y: 1 },
    { x: 1, y: -1 },
    { x: -1, y: -1 }
  ];
  let offsetIndex = 0;

  for (const anim of animations || []) {
    if (anim.playerId === rebounderId) continue;
    const sprite = playerSprites[anim.playerId];
    const lastStep = anim.movement?.[anim.movement.length - 1];
    if (!sprite || !lastStep) continue;

    const dist =
      Math.abs(lastStep.coords.x - ballSpot.x) +
      Math.abs(lastStep.coords.y - ballSpot.y);
    if (dist > 15) continue;

    const offset = offsets[offsetIndex++] || { x: 0, y: 0 };
    let targetGrid = { x: ballSpot.x + offset.x, y: ballSpot.y + offset.y };

    // Ensure minimum spacing from rebounder and other players
    let adjusted = false;
    while (!adjusted) {
      adjusted = true;
      for (const pos of finalPositions) {
        if (Math.abs(targetGrid.x - pos.grid.x) < MIN_X_SEP) {
          const dirX = targetGrid.x >= pos.grid.x ? 1 : -1;
          targetGrid.x = pos.grid.x + dirX * MIN_X_SEP;
          adjusted = false;
        }
        if (Math.abs(targetGrid.y - pos.grid.y) < MIN_Y_SEP) {
          const dirY = targetGrid.y >= pos.grid.y ? 1 : -1;
          targetGrid.y = pos.grid.y + dirY * MIN_Y_SEP;
          adjusted = false;
        }
      }
    }

    finalPositions.push({ playerId: anim.playerId, grid: { ...targetGrid } });
    const targetPx = gridToPixels(
      targetGrid.x,
      targetGrid.y,
      scene.game.config.width,
      scene.game.config.height
    );

    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x: targetPx.x,
          y: targetPx.y,
          duration: 300,
          ease: "Linear",
          onComplete: resolve,
          onStop: resolve
        });
      })
    );
  }

  return Promise.all(promises).then(
    () =>
      new Promise((resolve) => {
        const logPayload = {
          rebounderId,
          ballSpot,
          positions: finalPositions
        };
        if (REBOUND_DEBUG) {
          console.log("[rebound]", logPayload);
        }
        if (scene.time?.delayedCall) {
          scene.time.delayedCall(1000, resolve);
        } else {
          setTimeout(resolve, 1000);
        }
      })
  );
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
