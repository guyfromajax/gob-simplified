/**
 * Shared batted-out-of-bounds ball animation: pass flight → defender collision
 * pop → deflected trajectory off the nearest sideline/baseline.
 */

import { animateBallToPosition } from "./ballAnimationSimple.js";
import { cancelBallTweenAndClearOwner, getBallDuration } from "./ballTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { playGameSfx } from "../utils/gameSfx.js";

const GRID_MIN_X = 0;
const GRID_MAX_X = 100;
const GRID_MIN_Y = 0;
const GRID_MAX_Y = 50;

function clampGrid(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function pixelsToGrid(pixelX, pixelY, width, height) {
  return {
    x: clampGrid((pixelX / width) * 100, GRID_MIN_X, GRID_MAX_X),
    y: clampGrid(50 - (pixelY / height) * 50, GRID_MIN_Y, GRID_MAX_Y),
  };
}

function markBoundaryIgnored(tween) {
  if (tween) tween.__uessBoundaryIgnore = true;
  return tween;
}

/**
 * Midpoint grid for the post-contact "pop" — bends away from the incoming pass
 * line while still trending toward the OOB target.
 */
export function computeBatDeflectKickGrid(contactGrid, oobGrid, approachFromGrid) {
  const contact = {
    x: Number(contactGrid.x),
    y: Number(contactGrid.y),
  };
  const oob = {
    x: Number(oobGrid.x),
    y: Number(oobGrid.y),
  };
  const from = approachFromGrid
    ? { x: Number(approachFromGrid.x), y: Number(approachFromGrid.y) }
    : { x: contact.x, y: contact.y };

  const toOobX = oob.x - contact.x;
  const toOobY = oob.y - contact.y;
  const oobLen = Math.hypot(toOobX, toOobY) || 1;
  const oobDir = { x: toOobX / oobLen, y: toOobY / oobLen };

  const inX = contact.x - from.x;
  const inY = contact.y - from.y;
  const inLen = Math.hypot(inX, inY) || 1;
  const inDir = { x: inX / inLen, y: inY / inLen };

  const cross = inDir.x * oobDir.y - inDir.y * oobDir.x;
  const perpX = cross >= 0 ? -inDir.y : inDir.y;
  const perpY = cross >= 0 ? inDir.x : -inDir.x;

  const kickDist = 5;
  const deflectX = oobDir.x * 0.5 + perpX * 0.85;
  const deflectY = oobDir.y * 0.5 + perpY * 0.85;
  const dLen = Math.hypot(deflectX, deflectY) || 1;

  return {
    x: clampGrid(contact.x + (deflectX / dLen) * kickDist, GRID_MIN_X, GRID_MAX_X),
    y: clampGrid(contact.y + (deflectY / dLen) * kickDist, GRID_MIN_Y, GRID_MAX_Y),
  };
}

/**
 * Brief defender + ball impact read when the pass meets the bat.
 */
export function playBatCollisionEffect(scene, defSprite, ballSprite, contactPx) {
  if (!scene?.tweens) {
    return Promise.resolve();
  }

  playGameSfx(scene, "block1.wav", 0.42, { event: "bat_oob_contact" });

  if (ballSprite) {
    scene.tweens.killTweensOf(ballSprite);
    ballSprite.setPosition(contactPx.x, contactPx.y);
    const baseScale = ballSprite.scaleX ?? 1;
    markBoundaryIgnored(
      scene.tweens.add({
        targets: ballSprite,
        scaleX: baseScale * 0.72,
        scaleY: baseScale * 0.72,
        duration: 45,
        yoyo: true,
        ease: "Quad.easeOut",
        onComplete: () => {
          markBoundaryIgnored(
            scene.tweens.add({
              targets: ballSprite,
              scaleX: baseScale * 1.12,
              scaleY: baseScale * 1.12,
              duration: 55,
              yoyo: true,
              ease: "Quad.easeOut",
              onComplete: () => {
                ballSprite.setScale(baseScale);
              },
            })
          );
        },
      })
    );
  }

  if (defSprite) {
    const baseAngle = defSprite.angle ?? 0;
    markBoundaryIgnored(
      scene.tweens.add({
        targets: defSprite,
        angle: baseAngle + 11,
        duration: 50,
        yoyo: true,
        repeat: 1,
        ease: "Quad.easeOut",
        onComplete: () => {
          defSprite.setAngle(baseAngle);
        },
      })
    );
    const sx = defSprite.scaleX ?? 1;
    const sy = defSprite.scaleY ?? 1;
    markBoundaryIgnored(
      scene.tweens.add({
        targets: defSprite,
        scaleX: sx * 1.07,
        scaleY: sy * 1.07,
        duration: 70,
        yoyo: true,
        ease: "Sine.easeOut",
        onComplete: () => {
          defSprite.setScale(sx, sy);
        },
      })
    );
  }

  return new Promise((resolve) => {
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(130, resolve);
    } else {
      setTimeout(resolve, 130);
    }
  });
}

function delay(scene, ms) {
  return new Promise((resolve) => {
    if (scene?.time?.delayedCall) scene.time.delayedCall(ms, resolve);
    else setTimeout(resolve, ms);
  });
}

/**
 * Three-phase bat-OOB ball path: inbound pass → collision pop → deflected drift OOB.
 */
export async function animateBattedBallOutOfBounds(scene, {
  contactGrid,
  oobGrid,
  approachFromGrid = null,
  defSprite = null,
  width,
  height,
}) {
  const ballSprite = scene?.ballSprite;
  if (!scene || !ballSprite || !contactGrid || !oobGrid) {
    return;
  }

  const contactPx = gridToPixels(contactGrid.x, contactGrid.y, width, height);
  const resolvedApproach =
    approachFromGrid
    ?? pixelsToGrid(ballSprite.x, ballSprite.y, width, height);
  const kickGrid = computeBatDeflectKickGrid(contactGrid, oobGrid, resolvedApproach);
  const kickPx = gridToPixels(kickGrid.x, kickGrid.y, width, height);
  const oobPx = gridToPixels(oobGrid.x, oobGrid.y, width, height);

  cancelBallTweenAndClearOwner(scene, ballSprite);

  let impactFx = Promise.resolve();
  await animateBallToPosition(scene, contactPx, {
    duration: getBallDuration(ballSprite, contactPx.x, contactPx.y),
    easing: "Sine.easeIn",
    onArrive: () => {
      impactFx = playBatCollisionEffect(scene, defSprite, ballSprite, contactPx);
    },
  });
  await impactFx;
  await delay(scene, 35);

  await animateBallToPosition(scene, kickPx, {
    duration: Math.max(85, Math.round(getBallDuration(ballSprite, kickPx.x, kickPx.y) * 0.32)),
    easing: "Quad.easeOut",
    arc: { height: 18 },
  });

  await animateBallToPosition(scene, oobPx, {
    duration: Math.max(
      120,
      Math.round(getBallDuration(ballSprite, oobPx.x, oobPx.y) * 0.78),
    ),
    easing: "Cubic.easeOut",
    arc: { height: 12 },
  });
}
