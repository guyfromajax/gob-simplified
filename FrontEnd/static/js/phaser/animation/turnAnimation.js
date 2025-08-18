import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import {
  attachBallToPlayer,
  shootBall,
  SHOT_DEBUG,
  animateRebound,
  animatePutbackAttempt,
  animateKickoutReset
} from "./ballManager.js";
import { tweenBallTo, runPass, PASS_DEBUG } from "./ballTween.js";
import animationConfig from "./animation_config.js";

// Cap the time spent on any single movement step. Large timestamp gaps can
// otherwise produce multi‑second tweens that appear as animation stalls.
const MAX_STEP_DURATION = 1000; // ms

const HOME_RIM_COORDS = { x: 91, y: 25 };
const AWAY_RIM_COORDS = { x: 9, y: 25 };

/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
function updateBallOwnership({ scene, ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  if (scene?.skipToEnd) return;

  if (scene.passInFlight) return;

  if (scene.ballDetached) {
    if (PASS_DEBUG) console.log('ownershipSkipped', { stepIndex });
    return;
  }

  if (scene.pendingBallOwnerId != null) {
    const pendingId = scene.pendingBallOwnerId;
    const pendingSprite = playerSprites[pendingId];
    if (pendingSprite && ballSprite?.setPosition) {
      ballSprite.setPosition(pendingSprite.x, pendingSprite.y);
      ballSprite.setVisible(true);
      if (currentBallOwnerRef) currentBallOwnerRef.value = pendingSprite;
      if (PASS_DEBUG) console.log('ownershipUpdate', { target: pendingId, stepIndex });
    }
    scene.pendingBallOwnerId = null;
    return;
  }

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
      if (PASS_DEBUG) console.log('ownershipUpdate', { target: anim.playerId, stepIndex });
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

// Setup sideline inbound play
async function runSideInboundSetup({ scene, ballSprite, playerSprites, turnData }) {
  if (!turnData || scene?.skipToEnd || scene?.ftInProgress) return;

  const { ball_spot, oDestinations = {}, dDestinations = {}, possession_team_id } = turnData;

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const cfg = globalThis?.animation_config?.sideInbound || {};
  const duration = cfg.duration ?? 500;
  const ease = cfg.ease ?? "Sine.easeInOut";

  const offenseSprites = {};
  const defenseSprites = {};
  const offenseIds = {};

  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  if (!scene.ballSprite) scene.ballSprite = ballSprite;

  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (String(sprite.team_id) === String(possession_team_id)) {
      offenseSprites[info.pos] = sprite;
      offenseIds[info.pos] = id;
    } else {
      defenseSprites[info.pos] = sprite;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  const promises = [];
  const addTween = (sprite, coords, pos) => {
    if (!sprite || !coords) return;
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x,
          y,
          duration,
          ease,
          onStart: () => console.log(`tweenStart:${pos}`),
          onComplete: () => {
            console.log(`tweenEnd:${pos}`);
            resolve();
          },
          onStop: () => {
            console.log(`tweenEnd:${pos}`);
            resolve();
          }
        });
      })
    );
  };

  Object.entries(oDestinations).forEach(([pos, coords]) => addTween(offenseSprites[pos], coords, pos));
  Object.entries(dDestinations).forEach(([pos, coords]) => addTween(defenseSprites[pos], coords, pos));

  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
  }

  await Promise.all(promises);

  const sfSprite = offenseSprites["SF"];
  const pgSprite = offenseSprites["PG"];
  const sfId = offenseIds["SF"];
  const pgId = offenseIds["PG"];
  if (sfSprite) {
    attachBallToPlayer(scene, ballSprite, sfSprite);
    console.log("ballAttach(SF)");

    console.log(`[sideInbound][holdStart] sf:${sfId} pg:${pgId}`);
    await new Promise((resolve) => scene.time.delayedCall(1000, resolve));

    scene.events?.once('passStart', () => console.log('passStart'));
    scene.events?.once('tweenStart', () => console.log('tweenStart'));
    scene.events?.once('tweenEnd', () => console.log('tweenEnd'));
    scene.events?.once('passEnd', () => console.log('passEnd'));

    console.log(`[sideInbound][passStart] sf:${sfId} pg:${pgId}`);
    if (pgSprite && !scene.fastBreakInProgress) {
      await runPass(scene, { fromId: sfId, toId: pgId, duration, easing: ease });
    }
    console.log(`[sideInbound][passEnd] sf:${sfId} pg:${pgId}`);
    if (pgSprite) {
      console.log(`[sideInbound][pgAttach] sf:${sfId} pg:${pgId}`);
    }
  }
}

// Setup baseline inbound play after a made basket
async function runInboundSetup({
  scene,
  ballSprite,
  playerSprites,
  newOffenseSide,
  homeTeamId,
  awayTeamId
}) {
  if (scene?.ftInProgress) return;
  scene.isInboundSetup = true;
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  const isAwayOffense = newOffenseSide === "away";

  // Derive missing team IDs from sprite metadata
  if (!homeTeamId || !awayTeamId) {
    const sprites = Object.values(playerSprites);
    if (!homeTeamId) {
      homeTeamId = sprites.find(s => s.team === "home")?.team_id;
    }
    if (!awayTeamId) {
      awayTeamId = sprites.find(s => s.team === "away")?.team_id;
    }
  }

  const inboundTeamKey = isAwayOffense ? "away" : "home";
  const scoringTeamKey = isAwayOffense ? "home" : "away";
  const inboundTeamId = isAwayOffense ? awayTeamId : homeTeamId;
  const scoringTeamId = isAwayOffense ? homeTeamId : awayTeamId;
  const ballSpot = isAwayOffense ? { x: 98, y: 16 } : { x: 3, y: 16 };

  const homeOffsetRanges = {
    PG: { x: [8, 12], y: [-2, 2] },
    SG: { x: [12, 16], y: [-4, 4] },
    PF: { x: [10, 14], y: [6, 10] },
    C: { x: [10, 14], y: [-10, -6] }
  };
  const awayOffsetRanges = {
    PG: { x: [-12, -8], y: [-2, 2] },
    SG: { x: [-16, -12], y: [-4, 4] },
    PF: { x: [-14, -10], y: [6, 10] },
    C: { x: [-14, -10], y: [-10, -6] }
  };
  const ranges = isAwayOffense ? awayOffsetRanges : homeOffsetRanges;
  const inboundDest = {};
  for (const pos of ["PG", "SG", "PF", "C"]) {
    inboundDest[pos] = {
      x: ballSpot.x + Phaser.Math.Between(ranges[pos].x[0], ranges[pos].x[1]),
      y: ballSpot.y + Phaser.Math.Between(ranges[pos].y[0], ranges[pos].y[1])
    };
  }

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  // Retreat scoring team toward midcourt
  const retreatPromises = [];
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (
      sprite.team_id === scoringTeamId ||
      (!scoringTeamId && sprite.team === scoringTeamKey)
    ) {
      const targetX = gridToPixels(
        isAwayOffense ? 45 : 55,
        25,
        width,
        height
      ).x;
      retreatPromises.push(
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

  // Identify SF/PG/SG/PF/C and freeze other inbound players
  let sfSprite = null;
  let pgSprite = null;
  let sgSprite = null;
  let pfSprite = null;
  let cSprite = null;
  let sfId = null;
  let pgId = null;
  let sgId = null;
  let pfId = null;
  let cId = null;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (
      !info ||
      (sprite.team_id !== inboundTeamId &&
        !(inboundTeamId === undefined && sprite.team === inboundTeamKey))
    )
      continue;
    if (info.pos === "SF") {
      sfSprite = sprite;
      sfId = id;
    } else if (info.pos === "PG") {
      pgSprite = sprite;
      pgId = id;
    } else if (info.pos === "SG") {
      sgSprite = sprite;
      sgId = id;
    } else if (info.pos === "PF") {
      pfSprite = sprite;
      pfId = id;
    } else if (info.pos === "C") {
      cSprite = sprite;
      cId = id;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  if (!sfSprite || !pgSprite) {
    scene.isInboundSetup = false;
    return;
  }
  console.log(
    `[inbound][score][${newOffenseSide}] sf:${sfId} pg:${pgId} sg:${sgId} pf:${pfId} c:${cId}`
  );

  const rimGrid = isAwayOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
  const spotPx = gridToPixels(ballSpot.x, ballSpot.y, width, height);

  const pgDestPx = gridToPixels(inboundDest.PG.x, inboundDest.PG.y, width, height);
  console.log(`inboundDest assigned for PG: (${pgDestPx.x},${pgDestPx.y})`);
  const sgDestPx = gridToPixels(inboundDest.SG.x, inboundDest.SG.y, width, height);
  console.log(`inboundDest assigned for SG: (${sgDestPx.x},${sgDestPx.y})`);
  const pfDestPx = gridToPixels(inboundDest.PF.x, inboundDest.PF.y, width, height);
  console.log(`inboundDest assigned for PF: (${pfDestPx.x},${pfDestPx.y})`);
  const cDestPx = gridToPixels(inboundDest.C.x, inboundDest.C.y, width, height);
  console.log(`inboundDest assigned for C: (${cDestPx.x},${cDestPx.y})`);

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(sfSprite);
    scene.tweens.killTweensOf(pgSprite);
    if (sgSprite) scene.tweens.killTweensOf(sgSprite);
    if (pfSprite) scene.tweens.killTweensOf(pfSprite);
    if (cSprite) scene.tweens.killTweensOf(cSprite);
  }

  ballSprite.setPosition(rimPx.x, rimPx.y);
  ballSprite.setVisible(true);
  console.log(`[inbound][rimHoldEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  console.log(`[inbound][ballTweenStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  let ballTween;
  if (animationConfig.enableBallTween) {
    ballTween = tweenBallTo(scene, ballSprite, spotPx, {
      duration: 500,
      easing: "Sine.easeInOut"
    }).then(() => {
      console.log(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    });
  } else {
    ballSprite.setPosition(spotPx.x, spotPx.y);
    console.log(`[inbound][ballTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
    ballTween = Promise.resolve();
  }

  const sfTween = new Promise((resolve) => {
    scene.tweens.add({
      targets: sfSprite,
      x: spotPx.x,
      y: spotPx.y,
      duration: 500,
      ease: "Sine.easeInOut",
      onComplete: () => {
        console.log(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
        resolve();
      },
      onStop: () => {
        console.log(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
        resolve();
      }
    });
  });

  const pgTween = new Promise((resolve) => {
    console.log("pgTween start");
    scene.tweens.add({
      targets: pgSprite,
      x: pgDestPx.x,
      y: pgDestPx.y,
      duration: 500,
      ease: "Sine.easeInOut",
      onComplete: () => {
        console.log("pgTween end");
        resolve();
      },
      onStop: () => {
        console.log("pgTween end");
        resolve();
      }
    });
  });

  const sgTween = sgSprite
    ? new Promise((resolve) => {
        console.log("sgTween start");
        scene.tweens.add({
          targets: sgSprite,
          x: sgDestPx.x,
          y: sgDestPx.y,
          duration: 500,
          ease: "Sine.easeInOut",
          onComplete: () => {
            console.log("sgTween end");
            resolve();
          },
          onStop: () => {
            console.log("sgTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const pfTween = pfSprite
    ? new Promise((resolve) => {
        console.log("pfTween start");
        scene.tweens.add({
          targets: pfSprite,
          x: pfDestPx.x,
          y: pfDestPx.y,
          duration: 500,
          ease: "Sine.easeInOut",
          onComplete: () => {
            console.log("pfTween end");
            resolve();
          },
          onStop: () => {
            console.log("pfTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const cTween = cSprite
    ? new Promise((resolve) => {
        console.log("cTween start");
        scene.tweens.add({
          targets: cSprite,
          x: cDestPx.x,
          y: cDestPx.y,
          duration: 500,
          ease: "Sine.easeInOut",
          onComplete: () => {
            console.log("cTween end");
            resolve();
          },
          onStop: () => {
            console.log("cTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  await Promise.all([
    ...retreatPromises,
    ballTween,
    sfTween,
    pgTween,
    sgTween,
    pfTween,
    cTween
  ]);

  console.log(`[inbound][ballAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  attachBallToPlayer(scene, ballSprite, sfSprite);

  console.log(`[inbound][holdStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  await new Promise((resolve) => scene.time.delayedCall(1000, resolve));

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(pgSprite);
  }

  scene.events?.once('passStart', () => console.log('passStart'));
  scene.events?.once('tweenStart', () => console.log('tweenStart'));
  scene.events?.once('tweenEnd', () => console.log('tweenEnd'));
  scene.events?.once('passEnd', () => console.log('passEnd'));

  console.log(`[inbound][passStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  if (!scene.fastBreakInProgress) {
    await runPass(scene, {
      fromId: sfId,
      toId: pgId,
      duration: 500,
      easing: "Sine.easeInOut"
    });
  }
  console.log(`[inbound][passEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  console.log(`[inbound][pgAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);

  scene.isInboundSetup = false;
}

async function runFastBreakSequence({ scene, turnData, playerSprites, ballSprite }) {
  if (!scene || !turnData || scene.skipToEnd) return;
  if (!scene.ballSprite) scene.ballSprite = ballSprite;

  scene.fastBreakInProgress = true;
  scene.events?.emit("fb:start");

  if (scene.tweens) {
    for (const sprite of Object.values(playerSprites)) {
      scene.tweens.killTweensOf(sprite);
    }
  }

  try {
    const animations = turnData.animations || [];
    const width = scene.game.config.width;
    const height = scene.game.config.height;
    const sprintDuration =
      animationConfig.fastBreak?.sprintDuration ?? 800;

    const ownerAnim = animations.find(a => a.hasBallAtStep?.[0]);
    if (ownerAnim) {
      const ownerSprite = playerSprites[ownerAnim.playerId];
      if (ownerSprite) attachBallToPlayer(scene, ballSprite, ownerSprite);
    }

    const sprintPromises = [];
    for (const anim of animations) {
      const sprite = playerSprites[anim.playerId];
      if (!sprite) continue;
      const start = anim.start || anim.movement?.[0]?.coords;
      const end = anim.end || anim.movement?.[anim.movement.length - 1]?.coords;
      if (!start || !end) continue;
      const startPx = gridToPixels(start.x, start.y, width, height);
      const endPx = gridToPixels(end.x, end.y, width, height);
      sprite.setPosition(startPx.x, startPx.y);
      sprintPromises.push(
        new Promise(resolve => {
          scene.tweens.add({
            targets: sprite,
            x: endPx.x,
            y: endPx.y,
            duration: sprintDuration,
            ease: "Sine.easeInOut",
            onUpdate: () => {
              if (
                scene.ballAttachedToPlayerId === anim.playerId &&
                ballSprite?.setPosition
              ) {
                ballSprite.setPosition(sprite.x, sprite.y);
                ballSprite.setVisible(true);
              }
            },
            onComplete: resolve,
            onStop: resolve
          });
        })
      );
    }
    await Promise.all(sprintPromises);
    if (scene.skipToEnd) return;

    const passEvents = [];
    for (const anim of animations) {
      const moves = anim.movement || [];
      for (const step of moves) {
        if (step.action === "pass") {
          const ts = step.timestamp;
          const receiverAnim = animations.find(a =>
            a.movement?.some(m => m.action === "receive" && m.timestamp === ts)
          );
          const receiveStep = receiverAnim?.movement.find(
            m => m.action === "receive" && m.timestamp === ts
          );
          const delta = receiveStep
            ? receiveStep.timestamp - ts
            : animationConfig.pass.duration;
          passEvents.push({
            timestamp: ts,
            fromId: anim.playerId,
            toId: receiverAnim?.playerId,
            duration: delta
          });
        }
      }
    }
    passEvents.sort((a, b) => a.timestamp - b.timestamp);
    for (const evt of passEvents) {
      if (scene.skipToEnd) break;
      await runPass(scene, {
        fromId: evt.fromId,
        toId: evt.toId,
        duration: evt.duration,
        easing: animationConfig.pass.easing
      });
    }
    if (scene.skipToEnd) return;

    if (turnData.hold_up) {
      const center = gridToPixels(50, 25, width, height);
      const spacing = 10;
      const holdPromises = [];
      let idx = 0;
      for (const anim of animations) {
        const sprite = playerSprites[anim.playerId];
        if (!sprite) continue;
        const targetX = center.x + (idx - animations.length / 2) * spacing;
        const targetY = sprite.y;
        idx++;
        holdPromises.push(
          new Promise(resolve => {
            scene.tweens.add({
              targets: sprite,
              x: targetX,
              y: targetY,
              duration: sprintDuration / 2,
              ease: "Sine.easeInOut",
              onComplete: resolve,
              onStop: resolve
            });
          })
        );
      }
      await Promise.all(holdPromises);
      if (typeof scene.startNextHalfCourtOffense === "function") {
        scene.startNextHalfCourtOffense();
      }
      return;
    }

  const shooterId = turnData.shooterId || turnData.shooter_id;
  const shooterSprite = shooterId != null ? playerSprites[shooterId] : null;
  if (shooterSprite) {
    attachBallToPlayer(scene, ballSprite, shooterSprite);
    const rimGrid =
      shooterSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
    const arcHeight = animationConfig.fastBreak?.arcHeight ?? 50;
    await tweenBallTo(scene, ballSprite, rimPx, {
      duration: animationConfig.inbound.duration,
      easing: animationConfig.inbound.easing,
      arc: { height: arcHeight }
    });
    if (turnData.result_type === "MAKE") {
      const newOffenseSide =
        shooterSprite.team === "home" ? "away" : "home";
      await runInboundSetup({
        scene,
        ballSprite,
        playerSprites,
        newOffenseSide
      });
    } else {
      await animateRebound({
        scene,
        ballSprite,
        playerSprites,
        animations,
        rebounderId: turnData.rebounderId || turnData.rebounder_id,
        ballSpot: turnData.ballSpot || turnData.ball_spot
      });
    }
  }
  } finally {
    scene.fastBreakInProgress = false;
    scene.events?.emit("fb:end");
  }
}

/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  const currentBallOwnerRef = { value: null };
  // Store a reference on the scene so other modules (e.g., runPass)
  // can update ball ownership consistently.
  scene.currentBallOwnerRef = currentBallOwnerRef;
  const maxSteps = Math.max(
    ...turnData.animations.map(anim => anim.movement.length)
  );

  if (scene.fastBreakInProgress) {
    return;
  }

  if (ballSprite && scene?.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    ballSprite.setVisible(false);
  }

  const homeTeamId = simData.home_team_id;
  let awayTeamId = simData.away_team_id;
  if (!awayTeamId) {
    const awaySprite = Object.values(playerSprites).find(s => s.team === "away");
    awayTeamId = awaySprite?.team_id;
    if (awayTeamId) simData.away_team_id = awayTeamId;
  }

  // Determine which player owns the ball at step 0
  let step0OwnerSprite = null;
  for (const anim of turnData.animations) {
    if (scene.skipToEnd || scene.fastBreakInProgress) break;
    if (anim.hasBallAtStep?.[0]) {
      step0OwnerSprite = playerSprites[anim.playerId];
      break;
    }
  }

  if (step0OwnerSprite) {
    attachBallToPlayer(scene, ballSprite, step0OwnerSprite);
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

  if (scene.skipToEnd || scene.fastBreakInProgress) {
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
    if (scene.skipToEnd || scene.fastBreakInProgress) break;

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
        homeTeamId
      };
      if (SHOT_DEBUG) {
        shootParams.stepIndex = shotInfo.stepIndex;
        shootParams.turnIndex = scene.currentTurn;
      }
      const shotResult = await shootBall(shootParams);
      const ballSpot = shotResult?.grid;
      if (turnData.result_type === "MAKE") {
        const shooterTeamIsHome =
          String(shooterTeamId) === String(homeTeamId);
        const newOffenseSide = shooterTeamIsHome ? "away" : "home";
        await runInboundSetup({
          scene,
          ballSprite,
          playerSprites,
          newOffenseSide,
          homeTeamId,
          awayTeamId
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

  // Process additional events (e.g., putback attempts)
  if (!scene.skipToEnd && Array.isArray(turnData.events)) {
    for (const evt of turnData.events) {
      if (scene.skipToEnd) break;
      if (evt.event_type === "PUTBACK_ATTEMPT") {
        const shooterId = evt.shooterId;
        const rebounderSprite = playerSprites[shooterId];
        if (!rebounderSprite) continue;
        attachBallToPlayer(scene, ballSprite, rebounderSprite);
        const rimCoords =
          rebounderSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
        const putbackResult = await animatePutbackAttempt(
          scene,
          ballSprite,
          shooterId,
          rimCoords,
          evt.duration || 500,
          evt.result
        );
        if (evt.result === "MISS" && evt.rebound) {
          await animateRebound({
            scene,
            ballSprite,
            playerSprites,
            animations: evt.rebound.animations || turnData.animations,
            rebounderId: evt.rebound.rebounderId,
            ballSpot: putbackResult?.grid || evt.rebound.ballSpot
          });
        }
      } else if (evt.event_type === "KICKOUT_RESET") {
        await animateKickoutReset(
          scene,
          ballSprite,
          evt.rebounderId,
          evt.pgId,
          evt.pass,
          evt.pass?.duration
        );
        if (typeof scene.startNextHalfCourtOffense === "function") {
          scene.startNextHalfCourtOffense();
        }
      }
    }
  }
}

export { runInboundSetup, runSideInboundSetup, runFastBreakSequence };

if (typeof window !== "undefined") {
  window.playTurnAnimation = playTurnAnimation;
}

