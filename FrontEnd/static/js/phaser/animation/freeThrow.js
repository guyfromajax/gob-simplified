import { gridToPixels } from "../utils/gridToPixels.js";
import animationConfig, {
  FT_BETWEEN_SHOTS_DELAY_MS,
} from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { bounceFromRim } from "./ballManager.js";
import { States, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import { getCurrentOwner, getPendingOwner } from "../ball/ballController.js";
import { DebugFlags } from "../utils/debugFlags.js";

function wait(scene, ms) {
  if (!ms) return Promise.resolve();
  return scene.time?.delayedCall
    ? new Promise((res) => scene.time.delayedCall(ms, res))
    : new Promise((res) => setTimeout(res, ms));
}

export async function runFreeThrowSequence(
  scene,
  {
    playerSprites,
    ballSprite,
    turnData,
    onUpdate,
    helpers = {},
    ftContext = {},
  }
) {
  const attach =
    helpers.attachBallToPlayer ||
    (await import("./ballTween.js")).attachBallToPlayer;
  const detach =
    helpers.detachBall || (await import("./ballTween.js")).detachBall;
  const tween =
    helpers.tweenBallTo || (await import("./ballTween.js")).tweenBallTo;
  const inboundSetup =
    helpers.runInboundSetup || (await import("./turnAnimation.js")).runInboundSetup;
  const rebound =
    helpers.animateRebound || (await import("./ballManager.js")).animateRebound;

  const { ftIndex = 1, ftTotal = 1, bonusType } = ftContext || {};
  const isFinalTurn = ftIndex >= ftTotal;

  const releaseGuard =
    !isFinalTurn && scene.stateMachine
      ? createTransitionGuard(scene.stateMachine, [States.Inbound, 'DeadBall'])
      : null;

  if (!scene || !playerSprites || !ballSprite || !turnData) {
    releaseGuard?.();
    return;
  }

  if (!scene.stateMachine?.is(States.FreeThrow)) {
    safeTransition(
      scene.stateMachine,
      States.FreeThrow,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }
  if (scene.tweens) {
    for (const sprite of Object.values(playerSprites)) {
      scene.tweens.killTweensOf(sprite);
    }
    scene.tweens.killTweensOf(ballSprite);
  }

  const animations = turnData.animations || [];
  const playerAnims = animations.filter((a) => a.playerId !== "ball");
  const ballAnim = animations.find((a) => a.playerId === "ball");
  const width = scene.game.config.width;
  const height = scene.game.config.height;

  if (!turnData.no_lane) {
    const promises = [];
    for (const anim of playerAnims) {
      const sprite = playerSprites[anim.playerId];
      const end = anim.movement?.[1]?.coords;
      if (!sprite || !end) continue;
      const px = gridToPixels(end.x, end.y, width, height);
      promises.push(
        new Promise((resolve) => {
          scene.tweens.add({
            targets: sprite,
            x: px.x,
            y: px.y,
            duration: anim.duration || animationConfig.freeThrow.lineupMoveMs,
            ease: "Linear",
            onComplete: resolve,
            onStop: resolve,
          });
        })
      );
    }
    await Promise.all(promises);
  } else {
    const shooterAnim = playerAnims.find(
      (a) => a.playerId === turnData.shooter_id
    );
    const sprite = playerSprites[turnData.shooter_id];
    const end = shooterAnim?.movement?.[1]?.coords;
    if (sprite && end) {
      const px = gridToPixels(end.x, end.y, width, height);
      await new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x: px.x,
          y: px.y,
          duration: shooterAnim.duration || animationConfig.freeThrow.lineupMoveMs,
          ease: "Linear",
          onComplete: resolve,
          onStop: resolve,
        });
      });
    }
  }

  const shooterSprite = playerSprites[turnData.shooter_id];
  if (shooterSprite) attach(scene, ballSprite, shooterSprite);
  scene.events?.emit("ft:lineupComplete", {});

  const attempts = turnData.attempts || [];
  const moves = ballAnim?.movement || [];
  let moveIndex = 1;

  for (let i = 0; i < attempts.length; i++) {
    const result = attempts[i];
    scene.events?.emit("ft:attempt", { attempt: i + 1, total: attempts.length });
    await wait(scene, animationConfig.freeThrow.shooterPrepMs);
    detach(scene, ballSprite);

    const shotStep = moves[moveIndex];
    moveIndex++;
    const rimGrid =
      shotStep?.coords ||
      (turnData.offense_team_id === scene.simData?.home_team_id
        ? HOME_RIM_COORDS
        : AWAY_RIM_COORDS);
    const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
    scene.events?.emit("ft:shotStart");
    await tween(scene, ballSprite, rimPx, {
      duration: animationConfig.freeThrow.shotMs,
      easing: "Sine.easeInOut",
      arc: null, // Straight line path instead of arc
    });

    scene.events?.emit(result === "MAKE" ? "ft:make" : "ft:miss");
    await wait(scene, animationConfig.freeThrow.rimHoldMs);
    scene.events?.emit("ft:rimHoldEnd");

    const isLastAttempt = i === attempts.length - 1;
    const isFinalFT = isLastAttempt && isFinalTurn;
    const earlyExit = bonusType === 'ONE_AND_ONE' && result === 'MISS';
    let nextStateResolved = States.FreeThrow;
    if (result === "MAKE") {
      if (onUpdate) {
        try {
          onUpdate({ ...turnData, attempt: i, result });
        } catch (err) {
          console.error("Scoreboard update failed:", err);
        }
      }
      if (isFinalFT) {
        const possessionChanged = turnData.possession_flips;
        if (possessionChanged) {
          safeTransition(
            scene.stateMachine,
            States.Inbound,
            {
              shotResult: result,
              currentOwnerId: getCurrentOwner(scene),
              pendingOwnerId: getPendingOwner(scene),
            },
            ["shotResult"]
          );
          const resolveOffenseSide =
            helpers.getOffenseSide ||
            ((scene, teamId) =>
              teamId === scene.simData?.home_team_id ? "home" : "away");
          
          // When possession flips after a made free throw, the NEW offense team
          // (the team that was previously on defense) should do the inbound
          const newOffenseSide = resolveOffenseSide(
            scene,
            turnData.offense_team_id === scene.simData?.home_team_id 
              ? scene.simData?.away_team_id 
              : scene.simData?.home_team_id
          );
          await inboundSetup({
            scene,
            ballSprite,
            playerSprites,
            newOffenseSide,
          });
          scene.events?.emit?.("possessionChange", {
            offenseTeamId: turnData.possession_team_id,
          });
          nextStateResolved = States.Inbound;
        } else {
          safeTransition(
            scene.stateMachine,
            States.HalfCourt,
            {
              shotResult: result,
              currentOwnerId: getCurrentOwner(scene),
              pendingOwnerId: getPendingOwner(scene),
            },
            ["shotResult"]
          );
          nextStateResolved = States.HalfCourt;
        }
      } else {
        if (scene.tweens) {
          for (const sprite of Object.values(playerSprites))
            scene.tweens.killTweensOf(sprite);
          scene.tweens.killTweensOf(ballSprite);
        }
        await wait(scene, FT_BETWEEN_SHOTS_DELAY_MS);
        const resetStep = moves[moveIndex];
        moveIndex++;
        const resetGrid = resetStep?.coords || rimGrid;
        const spotPx = gridToPixels(
          resetGrid.x,
          resetGrid.y,
          width,
          height
        );
        await tween(scene, ballSprite, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut",
        });
        if (shooterSprite) attach(scene, ballSprite, shooterSprite);
      }
    } else {
      if (isFinalFT || earlyExit) {
        safeTransition(
          scene.stateMachine,
          States.Rebound,
          {
            shotResult: result,
            currentOwnerId: getCurrentOwner(scene),
            pendingOwnerId: getPendingOwner(scene),
          },
          ["shotResult"]
        );
        const miss = await bounceFromRim(
          scene,
          ballSprite,
          rimGrid,
          turnData.offense_team_id === scene.simData?.home_team_id,
          animationConfig.freeThrow.shotMs / 3
        );
        await rebound({
          scene,
          ballSprite,
          playerSprites,
          animations: [],
          rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
          ballSpot: miss.grid,
          shooterId: turnData.shooter_id,
        });
        nextStateResolved = States.Rebound;
      } else {
        if (scene.tweens) {
          for (const sprite of Object.values(playerSprites))
            scene.tweens.killTweensOf(sprite);
          scene.tweens.killTweensOf(ballSprite);
        }
        await wait(scene, FT_BETWEEN_SHOTS_DELAY_MS);
        const resetStep = moves[moveIndex];
        moveIndex++;
        const resetGrid = resetStep?.coords || rimGrid;
        const spotPx = gridToPixels(
          resetGrid.x,
          resetGrid.y,
          width,
          height
        );
        await tween(scene, ballSprite, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut",
        });
        if (shooterSprite) attach(scene, ballSprite, shooterSprite);
      }
    }
    if (DebugFlags?.FSM) {
      console.log({
        state: States.FreeThrow,
        ftIndex,
        ftTotal,
        bonusType,
        shotResult: result,
        isFinalFT,
        nextStateResolved,
      }); // remove when stable
    }
    scene.events?.emit("ft:repeatOrExit");
  }

  releaseGuard?.();

  if (isFinalTurn && scene.stateMachine?.is(States.FreeThrow))
    safeTransition(scene.stateMachine, States.HalfCourt, {
      currentOwnerId: getCurrentOwner(scene),
      pendingOwnerId: getPendingOwner(scene),
    });
  scene.events?.emit("ft:end");
}

export default runFreeThrowSequence;

