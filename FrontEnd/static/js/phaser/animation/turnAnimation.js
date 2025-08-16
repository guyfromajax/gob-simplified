import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import {
  lockBallToPlayer,
  shootBall,
  SHOT_DEBUG,
  animateRebound,
  animateInboundPass,
  INBOUND_DEBUG
} from "./ballManager.js";

// Cap the time spent on any single movement step. Large timestamp gaps can
// otherwise produce multi‑second tweens that appear as animation stalls.
const MAX_STEP_DURATION = 1000; // ms

/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
function updateBallOwnership({ scene, ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  if (scene?.skipToEnd) return;

  const passHappening = animations.some(
    anim => anim.movement?.[stepIndex]?.action === "pass"
  );
  if (passHappening) return;

  for (const anim of animations) {
    if (scene.skipToEnd) break;
    const sprite = playerSprites[anim.playerId];
    const hasBall = anim.hasBallAtStep?.[stepIndex];
    if (hasBall && ballSprite?.setPosition) {
      ballSprite.setPosition(sprite.x, sprite.y);
      ballSprite.setVisible(true);
      if (currentBallOwnerRef) currentBallOwnerRef.value = sprite;
      break;
    }

  }
}

/**
 * Smoothly move all players to their step 0 positions before possession begins.
 * Locks the ball to the player with hasBallAtStep[0] during this setup tween.
 */

async function runSetupTween({ scene, ballSprite, animations, playerSprites, currentBallOwnerRef }) {
  if (scene.skipToEnd) return;
  const stepIndex = 0;
  const promises = [];

  for (const anim of animations) {
    if (scene.skipToEnd) break;
    const sprite = playerSprites[anim.playerId];
    const firstStep = anim.movement?.[stepIndex];
    if (!sprite || !firstStep) continue;

    const { x, y } = gridToPixels(
      firstStep.coords.x,
      firstStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    promises.push(new Promise((resolve) => {
      const tween = scene.tweens.add({
        targets: [sprite],
        x,
        y,
        duration: 1000,
        ease: "Linear",
        onUpdate: () => {
          if (currentBallOwnerRef?.value === sprite && ballSprite?.setPosition) {
            ballSprite.setPosition(sprite.x, sprite.y);
            ballSprite.setVisible(true);
          }
        },
        onComplete: resolve,
        onStop: resolve
      });
      if (scene.skipToEnd) {
        tween.stop();
      }
    }));
  }

  await Promise.all(promises);
}

// Animate baseline inbound play after a made basket
async function animateInboundSequence({
  scene,
  ballSprite,
  playerSprites,
  scoringTeamId,
  homeTeamId
}) {
  const isHomeScoring = scoringTeamId === homeTeamId;
  const inboundTeamId = isHomeScoring ? "AWAY" : "HOME";
  const dir = inboundTeamId === "HOME" ? 1 : -1;

  const baselineX = inboundTeamId === "HOME" ? 6 : 94;
  const randY = 25 + Math.floor(Math.random() * 6) - 3;
  const ballSpot = { x: baselineX, y: randY };

  const oDestinationDict = {
    PG: { x: baselineX, y: randY },
    SG: { x: baselineX + dir * 4, y: randY + Math.floor(Math.random() * 4 - 2) },
    SF: { x: baselineX + dir * 8, y: randY + Math.floor(Math.random() * 4 - 2) },
    PF: { x: baselineX + dir * 12, y: randY + Math.floor(Math.random() * 4 - 2) },
    C: { x: baselineX + dir * 16, y: randY + Math.floor(Math.random() * 4 - 2) }
  };

  if (INBOUND_DEBUG) {
    console.log("[inbound]", { scoringTeamId, ballSpot, destinations: oDestinationDict });
  }

  const movePromises = [];
  let inbounderSprite = null;
  let receiverSprite = null;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (sprite.team_id === inboundTeamId) {
      const dest = oDestinationDict[info.pos];
      if (dest) {
        const px = gridToPixels(
          dest.x,
          dest.y,
          scene.game.config.width,
          scene.game.config.height
        );
        movePromises.push(
          new Promise((resolve) => {
            scene.tweens.add({
              targets: sprite,
              x: px.x,
              y: px.y,
              duration: 500,
              ease: "Sine.easeInOut",
              onComplete: resolve,
              onStop: resolve
            });
          })
        );
      }
      if (info.pos === "PG") inbounderSprite = sprite;
      if (info.pos === "SF") receiverSprite = sprite;
    } else if (sprite.team_id === scoringTeamId) {
      const targetX = gridToPixels(
        isHomeScoring ? 45 : 55,
        25,
        scene.game.config.width,
        scene.game.config.height
      ).x;
      movePromises.push(
        new Promise((resolve) => {
          scene.tweens.add({
            targets: sprite,
            x: targetX,
            y: sprite.y,
            duration: 500,
            ease: "Sine.easeInOut",
            onComplete: resolve,
            onStop: resolve
          });
        })
      );
    }
  }

  await Promise.all(movePromises);

  if (inbounderSprite && receiverSprite) {
    animateInboundPass(scene, ballSprite, ballSpot, oDestinationDict.SF, 0, 500);
    await new Promise((resolve) => {
      if (scene.time?.delayedCall) {
        scene.time.delayedCall(500, resolve);
      } else {
        setTimeout(resolve, 500);
      }
    });
    lockBallToPlayer(scene, ballSprite, receiverSprite);
  }
}

/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  const currentBallOwnerRef = { value: null };
  const maxSteps = Math.max(
    ...turnData.animations.map(anim => anim.movement.length)
  );

  if (ballSprite && scene?.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    ballSprite.setVisible(false);
  }

  // Determine which player owns the ball at step 0
  let step0OwnerSprite = null;
  for (const anim of turnData.animations) {
    if (scene.skipToEnd) break;
    if (anim.hasBallAtStep?.[0]) {
      step0OwnerSprite = playerSprites[anim.playerId];
      break;
    }
  }

  if (step0OwnerSprite) {
    lockBallToPlayer(scene, ballSprite, step0OwnerSprite);
    currentBallOwnerRef.value = step0OwnerSprite;
  }

  // 🔶 Pre-possession: Move players to their step 0 positions
  await runSetupTween({
    scene,
    ballSprite,
    animations: turnData.animations,
    playerSprites,
    currentBallOwnerRef
  });

  if (scene.skipToEnd) {
    return;
  }

  // ✅ NEW: Lock ball ownership to correct player at step
  console.log("🟡 inside playTurnAnimation → ");
  //print turnData here in the console logs
  console.log("turnData", turnData);
  // console.log("turnData.animations", turnData.animations);
  // console.log("turnData.possession_team_id", turnData.possession_team_id);
  // console.log("turnData.animations[0].hasBallAtStep", turnData.animations[0].hasBallAtStep);
  // console.log("turnData.animations[0].playerId", turnData.animations[0].playerId);
  // console.log("turnData.animations[0].movement", turnData.animations[0].movement);
  updateBallOwnership({
    scene,
    ballSprite,
    animations: turnData.animations,
    playerSprites,
    stepIndex: 0,
    offenseTeamId: turnData.possession_team_id,
    currentBallOwnerRef
  });

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    if (scene.skipToEnd) break;

    updateBallOwnership({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      stepIndex,
      offenseTeamId: turnData.possession_team_id,
      currentBallOwnerRef
    });

    const promises = [];
    let shotInfo = null;

    for (const anim of turnData.animations) {
      if (scene.skipToEnd) break;
      const sprite = playerSprites[anim.playerId];
      const movement = anim.movement;

      if (!sprite || stepIndex >= movement.length) continue;

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const rawDuration = (curr.timestamp - prev.timestamp) * 3;
      const duration = Math.min(MAX_STEP_DURATION, rawDuration);

      if (curr.action === "shoot") {
        shotInfo = { step: curr, playerId: anim.playerId, stepIndex };
      }

      const promise = animateStep({
        scene,
        sprite,
        step: curr,
        duration,
        ballSprite,
        currentBallOwnerRef,
        onAction
      });

      promises.push(promise);
    }

    await Promise.all(promises);

    if (shotInfo) {
      currentBallOwnerRef.value = null;
      const shooterPos = scene.playerInfo?.[shotInfo.playerId]?.pos;
      const shooterTeamId = playerSprites[shotInfo.playerId]?.team_id;
      const shootParams = {
        scene,
        ballSprite,
        fromCoords: shotInfo.step.coords,
        startTimestamp: shotInfo.step.timestamp,
        // Map rebound result types to "MISS" so shootBall returns a landing spot
        result: ["DREB", "OREB"].includes(turnData.result_type)
          ? "MISS"
          : turnData.result_type,
        shooterPos,
        shooterId: shotInfo.playerId,
        shooterTeamId,
        homeTeamId: simData.home_team_id
      };
      if (SHOT_DEBUG) {
        shootParams.stepIndex = shotInfo.stepIndex;
        shootParams.turnIndex = scene.currentTurn;
      }
      const shotResult = await shootBall(shootParams);
      const ballSpot = shotResult?.grid;
      if (turnData.result_type === "MAKE") {
        await animateInboundSequence({
          scene,
          ballSprite,
          playerSprites,
          scoringTeamId: shooterTeamId,
          homeTeamId: simData.home_team_id
        });
      } else if (ballSpot) {
        const rebounderName = turnData.ball_handler?.trim();
        let rebounderId = null;
        if (rebounderName) {
          rebounderId = scene.nameToId?.[rebounderName];
          if (!rebounderId && scene.playerInfo) {
            for (const [id, info] of Object.entries(scene.playerInfo)) {
              const fullName =
                info?.name || `${info.first_name ?? ""} ${info.last_name ?? ""}`.trim();
              if (fullName.toLowerCase() === rebounderName.toLowerCase()) {
                rebounderId = id;
                break;
              }
            }
          }
        }
        if (rebounderId) {
          await animateRebound({
            scene,
            ballSprite,
            playerSprites,
            animations: turnData.animations,
            rebounderId,
            ballSpot
          });
        }
      }
      break;
    }
  }
}

if (typeof window !== "undefined") {
  window.playTurnAnimation = playTurnAnimation;
}

