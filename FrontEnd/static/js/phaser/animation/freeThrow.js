import { gridToPixels } from "../utils/gridToPixels.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";

const positionList = ["PG", "SG", "SF", "PF", "C"];

const HOME = {
  shooterSpot: { x: 74, y: 25 },
  offenseAlignList: [
    { x: 56, y: 44 },
    { x: 80, y: 32 },
    { x: 86, y: 19 },
    { x: 86, y: 32 },
  ],
  dDestinationDict: {
    PG: { x: 54, y: 37 },
    SG: { x: 83, y: 32 },
    SF: { x: 83, y: 19 },
    PF: { x: 89, y: 32 },
    C: { x: 89, y: 19 },
  },
  rim: HOME_RIM_COORDS,
};

const AWAY = {
  shooterSpot: { x: 27, y: 25 },
  offenseAlignList: [
    { x: 45, y: 44 },
    { x: 20, y: 32 },
    { x: 14, y: 19 },
    { x: 14, y: 32 },
  ],
  dDestinationDict: {
    PG: { x: 47, y: 37 },
    SG: { x: 17, y: 32 },
    SF: { x: 17, y: 19 },
    PF: { x: 11, y: 32 },
    C: { x: 11, y: 19 },
  },
  rim: AWAY_RIM_COORDS,
};

export function buildDestinations(offenseIsHome, shooterPos) {
  const cfg = offenseIsHome ? HOME : AWAY;
  const shooterSpot = cfg.shooterSpot;
  const oDestinationDict = {};
  oDestinationDict[shooterPos] = shooterSpot;
  const positionListMinusShooter = positionList.filter((p) => p !== shooterPos);
  for (let i = 0; i < positionListMinusShooter.length; i++) {
    const pos = positionListMinusShooter[i];
    oDestinationDict[pos] = cfg.offenseAlignList[i];
  }
  return {
    oDestinations: oDestinationDict,
    dDestinations: cfg.dDestinationDict,
    shooterSpot,
    rim: cfg.rim,
  };
}

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

  if (!scene || !playerSprites || !ballSprite || !turnData) return;

  scene.ftInProgress = true;
  if (scene.tweens) {
    for (const sprite of Object.values(playerSprites)) {
      scene.tweens.killTweensOf(sprite);
    }
    scene.tweens.killTweensOf(ballSprite);
  }

  const offenseIsHome = (() => {
    const shooterSprite = playerSprites[turnData.shooter_id];
    if (shooterSprite?.team) return shooterSprite.team === "home";
    if (turnData.offense_team_id && scene.simData) {
      return turnData.offense_team_id === scene.simData.home_team_id;
    }
    return true;
  })();

  const { oDestinations, dDestinations, shooterSpot, rim } = buildDestinations(
    offenseIsHome,
    turnData.shooter_pos
  );

  scene.events?.emit("ft:start", {
    team: offenseIsHome ? "home" : "away",
    shooter: turnData.shooter_id,
    oDestinations,
    dDestinations,
  });

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const shooterSprite = playerSprites[turnData.shooter_id];

  if (!turnData.no_lane) {
    const promises = [];
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      const dest =
        info.team_id === turnData.offense_team_id
          ? oDestinations[info.pos]
          : dDestinations[info.pos];
      if (!dest) continue;
      const px = gridToPixels(dest.x, dest.y, width, height);
      promises.push(
        new Promise((resolve) => {
          scene.tweens.add({
            targets: sprite,
            x: px.x,
            y: px.y,
            duration: animationConfig.freeThrow.lineupMoveMs,
            ease: "Linear",
            onStart: () =>
              scene.events?.emit("ft:tweenStart", {
                playerId: id,
                x: px.x,
                y: px.y,
              }),
            onComplete: () => {
              scene.events?.emit("ft:tweenEnd", {
                playerId: id,
                x: px.x,
                y: px.y,
              });
              resolve();
            },
            onStop: () => {
              scene.events?.emit("ft:tweenEnd", {
                playerId: id,
                x: px.x,
                y: px.y,
              });
              resolve();
            },
          });
        })
      );
    }
    await Promise.all(promises);
  } else if (shooterSprite) {
    const spotPx = gridToPixels(shooterSpot.x, shooterSpot.y, width, height);
    await new Promise((resolve) => {
      scene.tweens.add({
        targets: shooterSprite,
        x: spotPx.x,
        y: spotPx.y,
        duration: animationConfig.freeThrow.lineupMoveMs,
        ease: "Linear",
        onStart: () =>
          scene.events?.emit("ft:tweenStart", {
            playerId: turnData.shooter_id,
            x: spotPx.x,
            y: spotPx.y,
          }),
        onComplete: () => {
          scene.events?.emit("ft:tweenEnd", {
            playerId: turnData.shooter_id,
            x: spotPx.x,
            y: spotPx.y,
          });
          resolve();
        },
        onStop: () => {
          scene.events?.emit("ft:tweenEnd", {
            playerId: turnData.shooter_id,
            x: spotPx.x,
            y: spotPx.y,
          });
          resolve();
        },
      });
    });
  }

  if (shooterSprite) {
    attach(scene, ballSprite, shooterSprite);
  }
  scene.events?.emit("ft:lineupComplete", {});

  const attempts = turnData.attempts || [];
  for (let i = 0; i < attempts.length; i++) {
    const result = attempts[i];
    scene.events?.emit("ft:attempt", { attempt: i + 1, total: attempts.length });
    await wait(scene, animationConfig.freeThrow.shooterPrepMs);
    detach(scene, ballSprite);
    const rimPx = gridToPixels(rim.x, rim.y, width, height);
    scene.events?.emit("ft:shotStart");
    await tween(scene, ballSprite, rimPx, {
      duration: animationConfig.freeThrow.shotMs,
      easing: "Sine.easeInOut",
      arc: { height: animationConfig.freeThrow.arcHeight },
    });
    scene.events?.emit(result === "MAKE" ? "ft:make" : "ft:miss");
    await wait(scene, animationConfig.freeThrow.rimHoldMs);
    scene.events?.emit("ft:rimHoldEnd");

    const isLast = i === attempts.length - 1;
    if (result === "MAKE") {
      if (onUpdate) {
        try {
          onUpdate({ ...turnData, attempt: i, result });
        } catch (err) {
          console.error("Scoreboard update failed:", err);
        }
      }
      if (isLast) {
        scene.ftInProgress = false;
        const newOffenseSide = offenseIsHome ? "away" : "home";
        await inboundSetup({
          scene,
          ballSprite,
          playerSprites,
          newOffenseSide,
        });
      } else if (shooterSprite) {
        const spotPx = gridToPixels(
          shooterSpot.x,
          shooterSpot.y,
          width,
          height
        );
        await tween(scene, ballSprite, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut",
        });
        attach(scene, ballSprite, shooterSprite);
      }
    } else {
      if (isLast) {
        scene.ftInProgress = false;
        await rebound({
          scene,
          ballSprite,
          playerSprites,
          animations: [],
          rebounderId: null,
          ballSpot: rim,
          shooterId: turnData.shooter_id
        });
      } else if (shooterSprite) {
        const spotPx = gridToPixels(
          shooterSpot.x,
          shooterSpot.y,
          width,
          height
        );
        await tween(scene, ballSprite, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut",
        });
        attach(scene, ballSprite, shooterSprite);
      }
    }
    scene.events?.emit("ft:repeatOrExit");
  }

  scene.ftInProgress = false;
  scene.events?.emit("ft:end");
}

export default runFreeThrowSequence;
