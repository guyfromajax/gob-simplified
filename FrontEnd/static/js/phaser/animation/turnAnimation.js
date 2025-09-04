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
import { tweenBallTo, runPass, PASS_DEBUG, tweenPlayerTo } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { DEBUG } from "../utils/debug.js";
import { DebugFlags } from "../utils/debugFlags.js";
import { States, getDebugTransitions, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import {
  getPendingOwner,
  clearPendingOwner,
  setPendingOwner,
  setCurrentOwner,
  getCurrentOwner
} from "../ball/ballController.js";

// Cap the time spent on any single movement step. Large timestamp gaps can
// otherwise produce multi‑second tweens that appear as animation stalls.
const MAX_STEP_DURATION = 1000; // ms


/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
function updateBallOwnership({ scene, ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  if (scene?.skipToEnd || scene?.stateMachine?.is(States.FastBreak)) return;

  if (scene.passInFlight) return;

  if (scene.ballDetached) {
    if (PASS_DEBUG) console.log('ownershipSkipped', { stepIndex });
    return;
  }

  const pendingId = getPendingOwner(scene);
  if (pendingId != null) {
    const pendingSprite = playerSprites[pendingId];
    if (pendingSprite && ballSprite?.setPosition) {
      ballSprite.setPosition(pendingSprite.x, pendingSprite.y);
      ballSprite.setVisible(true);
      if (currentBallOwnerRef) currentBallOwnerRef.value = pendingSprite;
      setCurrentOwner(scene, pendingId);
      if (PASS_DEBUG) console.log('ownershipUpdate', { target: pendingId, stepIndex });
    } else {
      console.warn(`Missing sprite for pending ball owner ${pendingId}`);
      const fallback = currentBallOwnerRef?.value;
      if (fallback && ballSprite?.setPosition) {
        ballSprite.setPosition(fallback.x, fallback.y);
      } else if (ballSprite?.setVisible) {
        ballSprite.setVisible(false);
      }
    }
    clearPendingOwner(scene);
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
    if (hasBall && !sprite) {
      console.warn(`Missing sprite for player ${anim.playerId}`);
      if (ballSprite?.setVisible) ballSprite.setVisible(false);
      continue;
    }
    if (hasBall && sprite && ballSprite?.setPosition) {
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
  if (!turnData || scene?.skipToEnd || scene?.stateMachine?.is(States.FreeThrow) || scene?.stateMachine?.is(States.FastBreak)) return;

  scene.isInboundSetup = true;
  if (!scene.stateMachine?.is(States.Inbound)) {
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }

  const { ball_spot, oDestinations = {}, dDestinations = {}, possession_team_id } = turnData;
  const offenseTeamId = scene.currentOffenseTeamId ?? possession_team_id;

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
    if (String(sprite.team_id) === String(offenseTeamId)) {
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
    if (pgSprite && !scene.stateMachine?.is(States.FastBreak)) {
      await runPass(scene, { fromId: sfId, toId: pgId, duration, easing: ease });
    }
    console.log(`[sideInbound][passEnd] sf:${sfId} pg:${pgId}`);
    if (pgSprite) {
      console.log(`[sideInbound][pgAttach] sf:${sfId} pg:${pgId}`);
    }
    if (scene.stateMachine?.is(States.Inbound))
      safeTransition(
        scene.stateMachine,
        States.HalfCourt,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
  }
  scene.isInboundSetup = false;
  scene.passInFlight = false;
  scene.ballDetached = false;
}

// Setup positions after a defensive rebound before new half-court offense or fast break
async function runDefensiveReboundSetup({ scene, ballSprite, playerSprites, rebounderId, nextPlayType = "HCO" }) {
  console.log('runDefensiveReboundSetup called with:', { rebounderId, nextPlayType });
  if (!scene || !playerSprites || rebounderId == null) return;

  const rebounderSprite = playerSprites[rebounderId];
  if (!rebounderSprite) return;

  scene.possessionFlipInProgress = true;
  if (ballSprite) attachBallToPlayer(scene, ballSprite, rebounderSprite);

  if (scene.stateMachine?.is(States.Rebound)) {
    if (DebugFlags?.FSM) console.log('FSM: Rebound -> OutletSetup');
    safeTransition(
      scene.stateMachine,
      States.OutletSetup,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  const basketGrid =
    rebounderSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const rebGridX = (rebounderSprite.x / width) * 100;
  const rebGridY = 50 - (rebounderSprite.y / height) * 50;

  // Find the outlet pass receiver (PG for HCO, or outlet_receiver for Fast Break)
  let outletReceiverId = null;
  let outletReceiverSprite = null;
  
  if (nextPlayType === "FAST_BREAK") {
    // For fast break, find the outlet receiver (usually PG, SG, or SF)
    const outletPositions = ["PG", "SG", "SF"];
    for (const pos of outletPositions) {
      for (const [id, info] of Object.entries(scene.playerInfo || {})) {
        if (info.pos === pos && info.team === rebounderSprite.team) {
          outletReceiverId = id;
          outletReceiverSprite = playerSprites[id];
          break;
        }
      }
      if (outletReceiverId) break;
    }
  } else {
    // For HCO, find the PG
    for (const [id, info] of Object.entries(scene.playerInfo || {})) {
      if (info.pos === "PG" && info.team === rebounderSprite.team) {
        outletReceiverId = id;
        outletReceiverSprite = playerSprites[id];
        break;
      }
    }
  }
  
  // Debug logging for outlet pass setup
  if (DebugFlags?.OUTLET) {
    console.log('Outlet setup debug:', {
      rebounderId,
      nextPlayType,
      outletReceiverId,
      rebounderSprite: rebounderSprite ? {
        team: rebounderSprite.team
      } : null,
      playerInfo: scene.playerInfo,
      allPlayerIds: Object.keys(scene.playerInfo || {})
    });
  }

  const promises = [];
  let outletTarget = null;
  
  if (outletReceiverId && outletReceiverId !== rebounderId && outletReceiverSprite) {
    if (nextPlayType === "FAST_BREAK") {
      // For fast break: move outlet receiver 15-25 grid spots toward offense basket
      const offenseBasket = rebounderSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
      const distance = Phaser.Math.Between(15, 25);
      const direction = offenseBasket.x > rebGridX ? 1 : -1; // Move toward offense basket
      
      outletTarget = {
        x: Phaser.Math.Clamp(
          rebGridX + direction * distance,
          4,
          97
        ),
        y: Phaser.Math.Clamp(
          rebGridY + Phaser.Math.Between(-8, 8),
          1,
          50
        ),
      };
    } else {
      // For HCO: move PG near the rebounder (current behavior)
      const sign = basketGrid.x > rebGridX ? 1 : -1;
      outletTarget = {
        x: Phaser.Math.Clamp(
          rebGridX + sign * Phaser.Math.Between(3, 6),
          4,
          97
        ),
        y: Phaser.Math.Clamp(
          rebGridY + Phaser.Math.Between(-6, 6),
          1,
          50
        ),
      };
    }
    
    const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
    promises.push(
      tweenPlayerTo(scene, outletReceiverSprite, outletPx, {
        duration: animationConfig.outletSetup.playerMoveMs,
      })
    );
    
    if (DebugFlags?.BALL) console.log('outletTarget', { outletReceiverId, outletTarget, nextPlayType });
    if (DebugFlags?.OUTLET) console.log(`${nextPlayType} outlet receiver movement queued`);
  } else {
    if (DebugFlags?.OUTLET) {
      console.log('Outlet pass skipped:', { 
        outletReceiverId, 
        rebounderId, 
        samePerson: outletReceiverId === rebounderId,
        reason: !outletReceiverId ? 'No outlet receiver found' : 'Outlet receiver is rebounder'
      });
    }
  }

  // For HCO scenarios, move all other players toward the new offense basket
  if (nextPlayType === "HCO") {
    console.log('HCO scenario detected, moving other players toward new offense basket');
    // Determine the new offense basket (opposite of current rebounder's basket)
    // The rebounder is on defense, so the new offense team is the opposite team
    const newOffenseBasket = rebounderSprite.team === "home" ? AWAY_RIM_COORDS : HOME_RIM_COORDS;
    console.log('New offense basket:', newOffenseBasket, 'Rebounder team:', rebounderSprite.team, 'New offense team:', rebounderSprite.team === "home" ? "away" : "home");
    
    let playersMoved = 0;
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      console.log(`Checking player ${id}:`, { 
        hasInfo: !!info, 
        isRebounder: id === rebounderId, 
        isOutletReceiver: id === outletReceiverId,
        spriteTeam: sprite.team,
        rebounderTeam: rebounderSprite.team
      });
      
      if (!info || id === rebounderId || id === outletReceiverId) {
        console.log(`Skipping player ${id}`);
        continue;
      }
      
      // Calculate movement toward new offense basket
      const currentGridX = (sprite.x / width) * 100;
      const currentGridY = 50 - (sprite.y / height) * 50;
      
      // Move 20-30 grid spots toward new offense basket
      const distance = Phaser.Math.Between(20, 30);
      // Determine direction based on new offense team:
      // If new offense team is home (basket at x=89), all players move right (increase x)
      // If new offense team is away (basket at x=11), all players move left (decrease x)
      const newOffenseTeam = rebounderSprite.team === "home" ? "away" : "home";
      const direction = newOffenseTeam === "home" ? 1 : -1;
      
      const targetGrid = {
        x: Phaser.Math.Clamp(
          currentGridX + direction * distance,
          4,  // Stay in bounds
          97
        ),
        y: Phaser.Math.Clamp(
          currentGridY + Phaser.Math.Between(-10, 10),
          1,  // Stay in bounds
          50
        ),
      };
      
      const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: animationConfig.outletSetup.playerMoveMs,
        })
      );
      
      playersMoved++;
      console.log(`HCO player movement: ${id} from (${currentGridX.toFixed(1)}, ${currentGridY.toFixed(1)}) to (${targetGrid.x}, ${targetGrid.y}) [direction: ${direction}, newOffenseTeam: ${newOffenseTeam}]`);
    }
    console.log(`Total players moved for HCO: ${playersMoved}`);
  } else {
    console.log('Not HCO scenario, nextPlayType:', nextPlayType);
  }

  await Promise.all(promises);

  if (outletReceiverId && outletReceiverId !== rebounderId) {
    const outletLog = {
      event: 'OUTLET_PASS',
      from: rebounderId,
      to: outletReceiverId,
      outletTarget,
      nextPlayType,
      startedAt: Date.now(),
    };
    if (DebugFlags?.OUTLET) console.log(outletLog);
    if (DebugFlags?.OUTLET) console.log('Starting outlet pass animation...');
    await runPass(scene, {
      fromId: rebounderId,
      toId: outletReceiverId,
      duration: animationConfig.outletSetup.passMs,
      easing: animationConfig.outletSetup.easing,
      onComplete: () => {
        setPendingOwner(scene, outletReceiverId);
        setCurrentOwner(scene, outletReceiverId);
        outletLog.completedAt = Date.now();
        if (DebugFlags?.OUTLET) console.log(outletLog);
        if (DebugFlags?.OUTLET) console.log('Outlet pass completed!');
      }
    });
  } else {
    if (DebugFlags?.OUTLET) {
      console.log('Outlet pass not executed:', { 
        outletReceiverId, 
        rebounderId, 
        samePerson: outletReceiverId === rebounderId,
        reason: !outletReceiverId ? 'No outlet receiver found' : 'Outlet receiver is rebounder'
      });
    }
  }

  if (scene.stateMachine?.is(States.OutletSetup)) {
    if (DebugFlags?.FSM) console.log('FSM: OutletSetup -> HalfCourt');
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  scene.possessionFlipInProgress = false;

  if (typeof scene.startNextHalfCourtOffense === "function") {
    scene.startNextHalfCourtOffense();
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
  if (scene?.stateMachine?.is(States.FreeThrow)) return;
  scene.isInboundSetup = true;
  if (!scene.stateMachine?.is(States.Inbound)) {
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }
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
  if (!scene.stateMachine?.is(States.FastBreak)) {
    await runPass(scene, {
      fromId: sfId,
      toId: pgId,
      duration: 500,
      easing: "Sine.easeInOut"
    });
  }
  console.log(`[inbound][passEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  console.log(`[inbound][pgAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);

  if (scene.stateMachine?.is(States.Inbound))
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );

  scene.isInboundSetup = false;
  scene.passInFlight = false;
  scene.ballDetached = false;
}


/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  scene.passInFlight = false;
  scene.ballDetached = false;
  scene.rebounderId = null;
  clearPendingOwner(scene);

  const currentBallOwnerRef = { value: null };
  // Store a reference on the scene so other modules (e.g., runPass)
  // can update ball ownership consistently.
  scene.currentBallOwnerRef = currentBallOwnerRef;
  const maxSteps = Math.max(
    ...turnData.animations.map(anim => anim.movement.length)
  );

  if (scene.stateMachine?.is(States.FastBreak)) {
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
    if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) break;
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

  if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
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
    offenseTeamId: scene.currentOffenseTeamId ?? turnData.possession_team_id,
    currentBallOwnerRef
  });

  let eventsProcessed = false;

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) break;

    updateBallOwnership({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      stepIndex,
      offenseTeamId: scene.currentOffenseTeamId ?? turnData.possession_team_id,
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
      const step = prev;
      const nextStep = curr;
      const rawDuration = (nextStep.timestamp - step.timestamp) * 3;
      const duration = Math.min(MAX_STEP_DURATION, rawDuration);

      DEBUG && console.log('[turn]', turnData?.id, step.timestamp, nextStep.timestamp, duration);
      if (duration <= 0) {
        console.warn('[turn] Non-positive duration', { turnId: turnData?.id, step, nextStep });
        if (typeof window !== 'undefined') {
          window.__badStepPayloads = window.__badStepPayloads || [];
          window.__badStepPayloads.push({ turnId: turnData?.id, step, nextStep });
        }
      }

      if (nextStep.action === "shoot") {
        shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
      }

      const promise = animateStep({
        scene,
        sprite,
        step: nextStep,
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
        result: ["DREB", "OREB"].includes(
          turnData.rebound_type || turnData.result_type
        )
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
        const nextTurn = simData?.turns?.[scene.currentTurn + 1];
        const hasPendingFreeThrow =
          nextTurn?.result_type === "FREE_THROW";
        if (!hasPendingFreeThrow) {
          const shooterTeamIsHome =
            String(shooterTeamId) === String(homeTeamId);
          const newOffenseSide = shooterTeamIsHome ? "away" : "home";
          const releaseGuard = createTransitionGuard(scene.stateMachine, [States.Rebound]);
          await runInboundSetup({
            scene,
            ballSprite,
            playerSprites,
            newOffenseSide,
            homeTeamId,
            awayTeamId,
          });
          releaseGuard?.();
        }
      } else if (ballSpot) {
        const rebounderId =
          turnData.rebounder_player_id ||
          turnData.rebounderId ||
          turnData.rebounder_id ||
          null;
        if (rebounderId) {
          const rebounderSprite = playerSprites[rebounderId];
          if (rebounderSprite) {
            const spotPx = gridToPixels(
              ballSpot.x,
              ballSpot.y,
              scene.game.config.width,
              scene.game.config.height
            );
            const rebCfg = animationConfig.rebound;
            scene.rebounderId = rebounderId;
            await new Promise((resolve) => {
              scene.tweens.add({
                targets: rebounderSprite,
                x: spotPx.x,
                y: spotPx.y,
                duration: rebCfg.playerMoveMs,
                ease: "Linear",
                onComplete: () => {
                  attachBallToPlayer(scene, ballSprite, rebounderSprite, {
                    debugInfo: { shooterId: shotInfo?.playerId ?? null, reboundSpot: ballSpot }
                  });
                  scene.offenseTeamId = rebounderSprite.team_id;
                  scene.events?.emit?.("possessionChange", {
                    offenseTeamId: rebounderSprite.team_id
                  });
                    if (
                      turnData.rebound_type &&
                      turnData.rebound_type !== "DREB" &&
                      scene.stateMachine?.is(States.Rebound)
                    ) {
                      scene.stateMachine?.transition(
                        States.HalfCourt,
                        getDebugTransitions() && {
                          stepIndex: shotInfo?.stepIndex,
                          shotResult: turnData.result_type,
                        }
                      );
                    }
                  scene.rebounderId = null;
                  if (scene.time?.delayedCall) {
                    scene.time.delayedCall(rebCfg.attachDelayMs, resolve);
                  } else {
                    setTimeout(resolve, rebCfg.attachDelayMs);
                  }
                },
                onStop: resolve
              });
            });
            const isDreb = turnData.rebound_type
              ? turnData.rebound_type === "DREB"
              : rebounderSprite?.team_id !== turnData.possession_team_id;
            if (isDreb && !turnData.fast_break) {
              await runDefensiveReboundSetup({
                scene,
                ballSprite,
                playerSprites,
                rebounderId,
                nextPlayType: turnData.next_play_type || "HCO"
              });
            } else {
              const pause = animationConfig.offensiveRebound.pauseMs;
              await new Promise((res) =>
                scene.time?.delayedCall
                  ? scene.time.delayedCall(pause, res)
                  : setTimeout(res, pause)
              );
              if (!scene.skipToEnd && Array.isArray(turnData.events)) {
                eventsProcessed = true;
                for (const evt of turnData.events) {
                  if (scene.skipToEnd) break;
                  if (evt.event_type === "PUTBACK_ATTEMPT") {
                    const shooterId = evt.shooterId;
                    const rebounderSprite = playerSprites[shooterId];
                    if (!rebounderSprite) continue;
                    attachBallToPlayer(scene, ballSprite, rebounderSprite, {
                      debugInfo: { shooterId, reboundSpot: evt.rebound?.ballSpot || null }
                    });
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
                      const reboundData = evt.rebound;
                      const rebounderId =
                        reboundData.rebounder_player_id || reboundData.rebounderId;
                      await animateRebound({
                        scene,
                        ballSprite,
                        playerSprites,
                        animations: reboundData.animations || turnData.animations,
                        rebounderId,
                        ballSpot: putbackResult?.grid || reboundData.ballSpot,
                        shooterId: evt.shooterId
                      });
                      if (
                        reboundData.rebound_type === "DREB" &&
                        !turnData.fast_break
                      ) {
                        await runDefensiveReboundSetup({
                          scene,
                          ballSprite,
                          playerSprites,
                          rebounderId
                        });
                      }
                    }
                  } else if (evt.event_type === "KICKOUT_RESET") {
                    await animateKickoutReset(
                      scene,
                      ballSprite,
                      evt.rebounder_player_id || evt.rebounderId,
                      evt.pgId,
                      evt.pass
                    );
                    if (typeof scene.startNextHalfCourtOffense === "function") {
                      scene.startNextHalfCourtOffense();
                    }
                  }
                }
              }
            }
          }
        }
      }
      break;
    }
  }

  if (!eventsProcessed && !scene.skipToEnd && Array.isArray(turnData.events)) {
    for (const evt of turnData.events) {
      if (scene.skipToEnd) break;
      if (evt.event_type === "PUTBACK_ATTEMPT") {
        const shooterId = evt.shooterId;
        const rebounderSprite = playerSprites[shooterId];
        if (!rebounderSprite) continue;
        attachBallToPlayer(scene, ballSprite, rebounderSprite, {
          debugInfo: { shooterId, reboundSpot: evt.rebound?.ballSpot || null }
        });
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
          const reboundData = evt.rebound;
          const rebounderId =
            reboundData.rebounder_player_id || reboundData.rebounderId;
          await animateRebound({
            scene,
            ballSprite,
            playerSprites,
            animations: reboundData.animations || turnData.animations,
            rebounderId,
            ballSpot: putbackResult?.grid || reboundData.ballSpot,
            shooterId: evt.shooterId
          });
          if (
            reboundData.rebound_type === "DREB" &&
            !turnData.fast_break
          ) {
            await runDefensiveReboundSetup({
              scene,
              ballSprite,
              playerSprites,
              rebounderId,
              nextPlayType: turnData.next_play_type || "HCO"
            });
          }
        }
      } else if (evt.event_type === "KICKOUT_RESET") {
        await animateKickoutReset(
          scene,
          ballSprite,
          evt.rebounder_player_id || evt.rebounderId,
          evt.pgId,
          evt.pass
        );
        if (typeof scene.startNextHalfCourtOffense === "function") {
          scene.startNextHalfCourtOffense();
        }
      }
    }
  }
}

export { runInboundSetup, runSideInboundSetup, runDefensiveReboundSetup };

if (typeof window !== "undefined") {
  window.playTurnAnimation = playTurnAnimation;
}

