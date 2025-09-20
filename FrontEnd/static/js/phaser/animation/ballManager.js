import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { generateBallTween } from "./generateBallTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { runInboundSetup as baseRunInboundSetup } from "./turnAnimation.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import {
  attachBallToPlayer as baseAttachBallToPlayer,
  detachBall,
  tweenBallTo,
  runPass as baseRunPass
} from "./ballTween.js";
import { States, getDebugTransitions, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import gameStore from "../../state/gameStore.js";
import {
  clearCurrentOwner,
  cancelBallTween,
  getCurrentOwner,
  getPendingOwner,
  setPendingOwner,
} from "../ball/ballController.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";

function attachBallToPlayer(scene, ballSprite, playerSprite, opts = {}) {
  if (scene.possessionFlipInProgress) return;

  let targetId = playerSprite?.playerId;
  if (targetId == null && scene?.playerSprites) {
    for (const [pid, sprite] of Object.entries(scene.playerSprites)) {
      if (sprite === playerSprite) {
        targetId = pid;
        break;
      }
    }
  }

  if (scene.stateMachine?.is(States.Rebound) && targetId !== scene.rebounderId) {
    return;
  }

  const debugEnabled = isAnimationDebugEnabled();
  if (debugEnabled && REBOUND_DEBUG) {
    if (
      scene?.currentBallOwnerRef &&
      scene.currentBallOwnerRef.value &&
      scene.currentBallOwnerRef.value !== playerSprite
    ) {
      const refId = scene.currentBallOwnerRef.value?.playerId;
      animationDebugWarn("ball:owner mismatch", {
        ref: refId,
        target: targetId
      });
    }

    const logPayload = {
      type: "ballAttach",
      shooterId: opts?.debugInfo?.shooterId ?? null,
      reboundSpot: opts?.debugInfo?.reboundSpot ?? null,
      playerId: targetId,
      team: playerSprite?.team_id ?? playerSprite?.team ?? null
    };
    animationDebugLog("ball:attach", logPayload);
  }

  if (scene?.currentBallOwnerRef) {
    scene.currentBallOwnerRef.value = playerSprite;
  }

  return baseAttachBallToPlayer(scene, ballSprite, playerSprite, opts);
}

function runInboundSetup(opts) {
  const scene = opts.scene;
  if (scene.possessionFlipInProgress || scene.stateMachine?.is(States.FastBreak)) return Promise.resolve();
  return baseRunInboundSetup(opts);
}

function runPass(scene, cfg = {}) {
  const debugEnabled = isAnimationDebugEnabled();

  // Debug logging for kickout passes
  if (debugEnabled && cfg.fromId && cfg.toId) {
    animationDebugLog('runPass called for kickout:', {
      fromId: cfg.fromId,
      toId: cfg.toId,
      currentState: scene.stateMachine?.state,
      possessionFlipInProgress: scene.possessionFlipInProgress,
      isFastBreak: scene.stateMachine?.is(States.FastBreak)
    });
  }

  // Allow kickout passes even during possession flip
  const isKickoutPass = cfg.fromId && cfg.toId;

  if ((scene.possessionFlipInProgress && !isKickoutPass) || scene.stateMachine?.is(States.FastBreak)) {
    if (debugEnabled) {
      animationDebugWarn('runPass blocked:', {
        reason: scene.possessionFlipInProgress ? 'possessionFlipInProgress' : 'FastBreak state',
        isKickoutPass
      });
    }
    return Promise.resolve();
  }

  if (debugEnabled) {
    animationDebugLog('runPass proceeding with baseRunPass');
  }
  return baseRunPass(scene, cfg);
}

export { attachBallToPlayer, detachBall, tweenBallTo, runPass, runInboundSetup };

// Debug flags for logging shot / rebound details
export const SHOT_DEBUG = false;
export const REBOUND_DEBUG = false;
export const INBOUND_DEBUG = false;



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
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: fromTimestamp,
    endTimestamp: toTimestamp,
    type: 'pass'
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
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  generateBallTween({
    scene,
    ballSprite,
    startCoords: fromCoords,
    endCoords: toCoords,
    startTimestamp: startTs,
    endTimestamp: endTs,
    type: 'inbound'
  });
}

/**
 * Hide the ball (e.g. post-shot, end of play)
 */
export function hideBall(ballSprite) {
  if (ballSprite) ballSprite.setVisible(false);
}

/**
 * Bounce a missed shot off the rim to a landing spot.
 * Resolves with the grid coordinates of the landing spot.
 */
export function bounceFromRim(
  scene,
  ballSprite,
  rimCoords,
  isHomeTeam,
  duration
) {
  return new Promise((resolve) => {
    const rebCfg = animationConfig.rebound;
    
    // For missed shots, ball should bounce toward the center of the court
    // Away basket (x=11): bounce right (increase x)
    // Home basket (x=89): bounce left (decrease x)
    const bounceGridX = rimCoords.x > 50 // Home basket
      ? rimCoords.x - rebCfg.bounceArea.x  // Bounce left toward center
      : rimCoords.x + rebCfg.bounceArea.x; // Bounce right toward center
      
    const bounceGridY =
      rimCoords.y + Phaser.Math.Between(-rebCfg.bounceArea.y, rebCfg.bounceArea.y);
      
    // Ensure bounce stays in bounds
    const clampedBounceX = Phaser.Math.Clamp(bounceGridX, 4, 97);
    const clampedBounceY = Phaser.Math.Clamp(bounceGridY, 1, 50);
    
    const bounce = gridToPixels(
      clampedBounceX,
      clampedBounceY,
      scene.game.config.width,
      scene.game.config.height
    );
    scene.tweens.add({
      targets: ballSprite,
      x: bounce.x,
      y: bounce.y,
      duration,
      ease: "Sine.easeOut",
      onComplete: () => resolve({ grid: { x: clampedBounceX, y: clampedBounceY } })
    });
  });
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
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);
  const stateMachine = scene.stateMachine;
  if (stateMachine) {
    const prevState = stateMachine.state;
    const legalState =
      stateMachine.is(States.HalfCourt) ||
      stateMachine.is(States.Rebound) ||
      stateMachine.is(States.FastBreak);
    if (legalState) {
      safeTransition(
        stateMachine,
        States.ShotAttempt,
        {
          stepIndex,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    } else {
      console.warn("shotBall: illegal state", {
        prevState,
        shooterId,
        stepIndex
      });
    }
  }
  const homeRoster = gameStore.getHomeRoster();
  const storeHomeId =
    homeRoster?.team_id || homeRoster?.teamId || homeRoster?.team_name || homeRoster?.team;
  const effectiveHomeId = homeTeamId ?? storeHomeId;
  const isHomeTeam = String(shooterTeamId) === String(effectiveHomeId);

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
          if (scene.stateMachine?.is(States.ShotAttempt)) {
            safeTransition(
              scene.stateMachine,
              States.Rebound,
              {
                shotResult: result,
                stepIndex,
                currentOwnerId: getCurrentOwner(scene),
                pendingOwnerId: getPendingOwner(scene),
              },
              ["shotResult"]
            );
          }
          scene.rebounderId = null;
          bounceFromRim(
            scene,
            ballSprite,
            rimCoords,
            isHomeTeam,
            duration / 3
          ).then((miss) => {
            if (SHOT_DEBUG) {
              console.log("shot:miss", {
                type: "miss",
                shooterId,
                reboundSpot: miss.grid,
                playerId: shooterId,
                team: shooterTeamId,
              });
            }
            resolve(miss);
          });
        } else {
          resolve();
        }
      }
    });
  });
}

/**
 * Animate a putback attempt after an offensive rebound.
 * Detaches the ball from the rebounder and tweens it to the rim.
 * Resolves after inbound setup (for makes) or after ball lands (for misses).
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {string} shooterId
 * @param {{x:number, y:number}} rimCoords - grid coordinates of the target rim
 * @param {number} duration - tween duration in ms
 * @param {string} result - "MAKE", "MISS", or "FOUL"
 */
export function animatePutbackAttempt(
  scene,
  ballSprite,
  shooterId,
  rimCoords,
  duration = animationConfig.putback.duration,
  result,
  easing = animationConfig.putback.easing
) {
  if (!scene || !ballSprite) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  const shooterSprite = scene.playerSprites?.[shooterId];
  if (!shooterSprite) return Promise.resolve();

  const stateMachine = scene.stateMachine;
  if (
    stateMachine &&
    (stateMachine.is(States.HalfCourt) ||
      stateMachine.is(States.Rebound) ||
      stateMachine.is(States.FastBreak))
  ) {
    safeTransition(stateMachine, States.ShotAttempt, {
      currentOwnerId: getCurrentOwner(scene),
      pendingOwnerId: getPendingOwner(scene),
    });
  }

  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  clearCurrentOwner(scene);
  ballSprite.setPosition(shooterSprite.x, shooterSprite.y);
  ballSprite.setVisible(true);

  const rim = gridToPixels(
    rimCoords.x,
    rimCoords.y,
    scene.game.config.width,
    scene.game.config.height
  );

  return new Promise((resolve) => {
    scene.tweens.add({
      targets: ballSprite,
      x: rim.x,
      y: rim.y,
      duration,
      ease: easing,
      onComplete: () => {
        const handleComplete = async () => {
          if (result === "MAKE") {
            const wait = () =>
              scene.time?.delayedCall
                ? new Promise((res) => scene.time.delayedCall(1000, res))
                : new Promise((res) => setTimeout(res, 1000));
            await wait();

            const shooterTeamKey = shooterSprite.team;
            const newOffenseSide = shooterTeamKey === "home" ? "away" : "home";
            const homeTeamId =
              gameStore.getHomeRoster()?.team_id || gameStore.getHomeRoster()?.teamId;
            const awayTeamId =
              gameStore.getAwayRoster()?.team_id || gameStore.getAwayRoster()?.teamId;

            const releaseGuard = createTransitionGuard(scene.stateMachine, [States.Rebound]);
            await runInboundSetup({
              scene,
              ballSprite,
              playerSprites: scene.playerSprites,
              newOffenseSide,
              homeTeamId,
              awayTeamId
            });
            releaseGuard?.();
            resolve();
            } else if (result === "MISS") {
              if (scene.stateMachine?.is(States.ShotAttempt)) {
                safeTransition(scene.stateMachine, States.Rebound, {
                  shotResult: result,
                });
              }

              // Bounce the ball from the rim for putback misses
              detachBall(scene, ballSprite);
              scene.rebounderId = null;
              
              // Determine if this is home team shooting (for bounce direction)
              const isHomeTeam = rimCoords.x > 50; // Home rim is at x=89, away rim is at x=11
              
              bounceFromRim(
                scene,
                ballSprite,
                rimCoords,
                isHomeTeam,
                duration / 3
              ).then((miss) => {
                resolve(miss);
              });
            } else if (result === "FOUL") {
              detachBall(scene, ballSprite);
              hideBall(ballSprite);
              scene.rebounderId = null;
              safeTransition(scene.stateMachine, States.FreeThrow, {
                shotResult: result,
              });
              resolve();
            } else {
              safeTransition(scene.stateMachine, States.FreeThrow, {
                shotResult: result,
              });
              // unrecognized result: backend will handle next steps
              resolve();
            }
        };

        handleComplete();
      }
    });
  });
}

function coerceFastBreakFlag(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return normalized === "true" || normalized === "1" || normalized === "fast_break";
  }
  return false;
}

function isUpcomingFastBreak(scene, explicitFlag) {
  if (explicitFlag != null) {
    return coerceFastBreakFlag(explicitFlag);
  }
  const currentIndex = typeof scene?.currentTurn === "number" ? scene.currentTurn : null;
  if (currentIndex == null) return false;
  const nextTurn = scene?.simData?.turns?.[currentIndex + 1];
  if (!nextTurn) return false;
  if (coerceFastBreakFlag(nextTurn.fast_break)) return true;
  const resultType = typeof nextTurn.result_type === "string"
    ? nextTurn.result_type.toUpperCase()
    : null;
  return resultType === "FAST_BREAK";
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
  ballSpot,
  shooterId,
  upcomingFastBreak,
}) {
  if (!scene || !ballSprite || !ballSpot) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();
  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);

  const debugEnabled = isAnimationDebugEnabled();
  const shouldHoldForFastBreak = () => isUpcomingFastBreak(scene, upcomingFastBreak);

  scene.rebounderId = rebounderId;
  const rebCfg = animationConfig.rebound;
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
  if (debugEnabled && REBOUND_DEBUG) {
    const team = rebounderSprite?.team_id ?? rebounderSprite?.team;
    animationDebugLog("reb:event", {
      type: "rebound",
      shooterId,
      reboundSpot: ballSpot,
      playerId: rebounderId,
      team
    });
  }
  if (rebounderSprite) {
    const teamId = rebounderSprite.team_id;
    scene.offenseTeamId = teamId;
    scene.events?.emit?.("possessionChange", { offenseTeamId: teamId });
    finalPositions.push({ playerId: rebounderId, grid: { ...ballSpot } });
    if (debugEnabled && REBOUND_DEBUG) {
      animationDebugLog("reb:moveStart", {
        playerId: rebounderId,
        from: { x: rebounderSprite.x, y: rebounderSprite.y },
        to: { x: spotPx.x, y: spotPx.y },
        duration: rebCfg.playerMoveMs
      });
    }
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: rebounderSprite,
          x: spotPx.x,
          y: spotPx.y,
          duration: rebCfg.playerMoveMs,
          ease: "Linear",
          onComplete: () => {
            if (debugEnabled && REBOUND_DEBUG) {
              animationDebugLog("reb:moveEnd", {
                playerId: rebounderId,
                x: spotPx.x,
                y: spotPx.y
              });
            }
            attachBallToPlayer(scene, ballSprite, rebounderSprite, {
              debugInfo: { shooterId, reboundSpot: ballSpot }
            });
            scene.offenseTeamId = rebounderSprite.team_id;
            scene.events?.emit("possessionChange", {
              offenseTeamId: rebounderSprite.team_id
            });
            if (scene.stateMachine?.is(States.Rebound)) {
              const holdReboundState = shouldHoldForFastBreak();
              if (holdReboundState) {
                if (debugEnabled && getDebugTransitions()) {
                  animationDebugLog(
                    "animateRebound: holding Rebound state for fast break handoff",
                    {
                      rebounderId,
                      currentTurn: scene.currentTurn,
                    }
                  );
                }
              } else {
                safeTransition(scene.stateMachine, States.HalfCourt, {
                  currentOwnerId: getCurrentOwner(scene),
                  pendingOwnerId: getPendingOwner(scene),
                });
              }
            }
            scene.rebounderId = null;
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
          duration: rebCfg.playerMoveMs,
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
        if (debugEnabled && REBOUND_DEBUG) {
          animationDebugLog("[rebound]", logPayload);
        }
        if (scene.time?.delayedCall) {
          scene.time.delayedCall(rebCfg.attachDelayMs, resolve);
        } else {
          setTimeout(resolve, rebCfg.attachDelayMs);
        }
      })
  );
}

/**
 * Animate an offensive rebound kickout pass to reset the half‑court offense.
 * Attaches the ball to the rebounder, tweens the pass to the point guard,
 * then locks the ball to the PG on completion.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {string} rebounderId
 * @param {string} pgId
 * @param {{fromCoords:{x:number,y:number}, toCoords:{x:number,y:number}, duration?:number}} pass
 * @param {number} [duration]
 */
export function animateKickoutReset(
  scene,
  ballSprite,
  rebounderId,
  pgId,
  pass = {},
  duration
) {
  if (!scene || !ballSprite) return Promise.resolve();
  if (scene?.stateMachine?.is(States.FreeThrow)) return Promise.resolve();

  const debugEnabled = isAnimationDebugEnabled();
  const rebounderSprite = scene.playerSprites?.[rebounderId];
  const pgSprite = scene.playerSprites?.[pgId];
  if (!rebounderSprite || !pgSprite) {
    if (debugEnabled) {
      animationDebugWarn('animateKickoutReset: Missing sprites', {
        rebounderId,
        pgId,
        rebounderSprite: !!rebounderSprite,
        pgSprite: !!pgSprite,
      });
    }
    return Promise.resolve();
  }

  // Ensure runPass can locate the ball sprite on the scene
  if (!scene.ballSprite) {
    scene.ballSprite = ballSprite;
  }

  // Attach to the rebounder before starting the pass
  attachBallToPlayer(scene, ballSprite, rebounderSprite);

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const cfg = animationConfig.kickout;
  const raw = duration ?? pass.duration;
  const usedDuration = raw != null && raw >= cfg.duration ? raw : cfg.duration;

  const opts = {
    fromId: rebounderId,
    toId: pgId,
    duration: usedDuration,
    easing: cfg.easing
  };

  if (pass.fromCoords) {
    opts.startCoords = gridToPixels(
      pass.fromCoords.x,
      pass.fromCoords.y,
      width,
      height
    );
  } else {
    opts.startCoords = { x: rebounderSprite.x, y: rebounderSprite.y };
  }
  if (pass.toCoords) {
    opts.endCoords = gridToPixels(
      pass.toCoords.x,
      pass.toCoords.y,
      width,
      height
    );
  } else {
    opts.endCoords = { x: pgSprite.x, y: pgSprite.y };
  }

  if (scene.stateMachine?.is(States.FastBreak)) {
    return Promise.resolve();
  }

  const ownerBefore = getCurrentOwner(scene);
  detachBall(scene, ballSprite);

  if (debugEnabled) {
    animationDebugLog('animateKickoutReset: Starting pass', { rebounderId, pgId, opts });
  }

  return runPass(scene, opts).then(() => {
    if (debugEnabled) {
      animationDebugLog('animateKickoutReset: Pass completed, attaching ball to PG');
    }
    attachBallToPlayer(scene, ballSprite, pgSprite);
    setPendingOwner(scene, pgId);
    const ownerAfter = getCurrentOwner(scene);

    if (scene.stateMachine?.is(States.Rebound)) {
      safeTransition(scene.stateMachine, States.HalfCourt);
    }

    if (debugEnabled && (DebugFlags?.BALL || DebugFlags?.FSM)) {
      animationDebugLog({
        event: 'KICK_OUT_PASS',
        from: rebounderId,
        to: pgId,
        ownerBefore,
        ownerAfter
      });
    }
  }).catch((error) => {
    if (debugEnabled) {
      animationDebugWarn('animateKickoutReset: Pass failed', error);
    }
    // Fallback: just attach ball to PG
    attachBallToPlayer(scene, ballSprite, pgSprite);
    setPendingOwner(scene, pgId);
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
        attachBallToPlayer(scene, ballSprite, playerSprite);
      }
      break; // Only one player can have the ball
    }
  }
}


// import { attachBallToPlayer, passBall } from "./ballManager.js";

// // Lock to player
// attachBallToPlayer(ballSprite, playerSprites[playerId]);

// // Animate pass
// passBall({
//   scene,
//   ballSprite,
//   fromCoords: passStep.coords,
//   toCoords: receiveStep.coords,
//   fromTimestamp: passStep.timestamp,
//   toTimestamp: receiveStep.timestamp
// });
