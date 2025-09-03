import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./ballManager.js";
import { tweenBallTo, tweenPlayerTo, runPass } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
import { States, getDebugTransitions } from "../state/gameStateMachine.js";
import { getCurrentOwner } from "../ball/ballController.js";
import { createAnimationTimeline } from "./animationTimeline.js";
import { runInboundSetup } from "./turnAnimation.js";

// Timeline-driven fast break sequence. Handles the initial sprint phase via a
// Phaser timeline so all player movements can be cancelled together if
// necessary. Subsequent passes and shots reuse existing tween helpers.

export async function runFastBreakSequence({ scene, turnData, playerSprites, ballSprite }) {
  if (!scene || !turnData || scene.skipToEnd) return;
  if (!scene.ballSprite) scene.ballSprite = ballSprite;

  scene.stateMachine?.transition(States.FastBreak, getDebugTransitions() && { stepIndex: 0 });
  scene.events?.emit("fb:start");

  // stop any existing timeline/tweens
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }

  // Build sprint timeline
  const animations = turnData.animations || [];
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const sprintDuration = animationConfig.fastBreak?.sprintDuration ?? 800;
  const timeline = createAnimationTimeline(scene);

  const ownerAnim = animations.find(a => a.hasBallAtStep?.[0]);
  if (ownerAnim) {
    const ownerSprite = playerSprites[ownerAnim.playerId];
    if (ownerSprite) attachBallToPlayer(scene, ballSprite, ownerSprite);
  }

  for (const anim of animations) {
    const sprite = playerSprites[anim.playerId];
    if (!sprite) continue;
    const start = anim.start || anim.movement?.[0]?.coords;
    const end = anim.end || anim.movement?.[anim.movement.length - 1]?.coords;
    if (!start || !end) continue;
    const startPx = gridToPixels(start.x, start.y, width, height);
    const endPx = gridToPixels(end.x, end.y, width, height);
    sprite.setPosition(startPx.x, startPx.y);
    timeline.add({
      targets: sprite,
      x: endPx.x,
      y: endPx.y,
      duration: sprintDuration,
      ease: "Sine.easeInOut"
    }, 0);
  }

  scene.__activeTimeline = timeline;

  await new Promise(resolve => {
    timeline.once("complete", resolve);
    timeline.play();
  });

  scene.__activeTimeline = null;
  if (scene.skipToEnd) return;

  // Handle passes after sprint
  const passes = turnData.passes || [];
  if (passes.length > 0) {
    for (const p of passes) {
      if (scene.skipToEnd) break;
      await runPass(scene, {
        fromId: p.fromId || p.from_id,
        toId: p.toId || p.to_id,
        duration: p.duration || animationConfig.pass.duration,
        easing: animationConfig.pass.easing
      });
    }
  } else {
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
  }

  if (scene.skipToEnd) return;

  // Hold-up scenario mirrors previous implementation
  if (turnData.hold_up) {
    const bhId = getCurrentOwner(scene);
    const bhSprite = bhId != null ? playerSprites[bhId] : null;
    const stopperId = turnData.stopper_id;
    const stopperSprite = stopperId != null ? playerSprites[stopperId] : null;
    const promises = [];

    if (bhSprite) {
      attachBallToPlayer(scene, ballSprite, bhSprite);
      const topKey = bhSprite.team === "home" ? HOME_TOP_KEY : AWAY_TOP_KEY;
      const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
      promises.push(
        tweenPlayerTo(scene, bhSprite, topKeyPx, {
          duration: sprintDuration / 2,
          easing: "Sine.easeInOut"
        })
      );

      const rim = bhSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;

      if (stopperSprite) {
        const offsetX = bhSprite.team === "home" ? 6 : -6;
        const stopGrid = {
          x: topKey.x + offsetX,
          y: topKey.y + Phaser.Math.Between(-3, 3)
        };
        const stopPx = gridToPixels(stopGrid.x, stopGrid.y, width, height);
        promises.push(
          tweenPlayerTo(scene, stopperSprite, stopPx, {
            duration: sprintDuration / 2,
            easing: "Sine.easeInOut"
          })
        );
      }

      const inPlayDef = new Set((turnData.roles?.defense || []).map(id => String(id)));
      for (const [id, sprite] of Object.entries(playerSprites)) {
        if (sprite === bhSprite || sprite === stopperSprite) continue;
        if (sprite.team === bhSprite.team) {
          const spotGrid = {
            x: Phaser.Math.Between(50, 51),
            y: Phaser.Math.Between(10, 40)
          };
          const spotPx = gridToPixels(spotGrid.x, spotGrid.y, width, height);
          promises.push(
            tweenPlayerTo(scene, sprite, spotPx, {
              duration: sprintDuration / 2,
              easing: "Sine.easeInOut"
            })
          );
        } else {
          if (inPlayDef.has(String(id))) {
            const laneGrid = {
              x: Phaser.Math.Between(
                Math.min(topKey.x, rim.x) + 1,
                Math.max(topKey.x, rim.x) - 1
              ),
              y: Phaser.Math.Between(10, 40)
            };
            const lanePx = gridToPixels(laneGrid.x, laneGrid.y, width, height);
            promises.push(
              tweenPlayerTo(scene, sprite, lanePx, {
                duration: sprintDuration / 2,
                easing: "Sine.easeInOut"
              })
            );
          } else {
            const halfGrid = {
              x: Phaser.Math.Between(50, 51),
              y: Phaser.Math.Between(10, 40)
            };
            const halfPx = gridToPixels(halfGrid.x, halfGrid.y, width, height);
            promises.push(
              tweenPlayerTo(scene, sprite, halfPx, {
                duration: sprintDuration / 2,
                easing: "Sine.easeInOut"
              })
            );
          }
        }
      }
    }

    await Promise.all(promises);
    if (typeof scene.startNextHalfCourtOffense === "function") {
      scene.startNextHalfCourtOffense();
    }
    return;
  }

  const shooterId = turnData.shooterId || turnData.shooter_id || getCurrentOwner(scene);
  const shooterSprite = shooterId != null ? playerSprites[shooterId] : null;
  if (shooterSprite) {
    attachBallToPlayer(scene, ballSprite, shooterSprite);
    const rimGrid = shooterSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
    await tweenPlayerTo(scene, shooterSprite, rimPx, {
      duration: sprintDuration / 2,
      easing: "Sine.easeInOut"
    });
    const arcHeight = animationConfig.fastBreak?.arcHeight ?? 50;
    await tweenBallTo(scene, ballSprite, rimPx, {
      duration: animationConfig.inbound.duration,
      easing: animationConfig.inbound.easing,
      arc: { height: arcHeight }
    });
    if (turnData.result_type === "MAKE") {
      const rimHoldMs = animationConfig.fastBreak?.rimHoldMs ?? 2000;
      await new Promise(resolve => scene.time.delayedCall(rimHoldMs, resolve));
      const newOffenseSide = shooterSprite.team === "home" ? "away" : "home";
      await runInboundSetup({ scene, ballSprite, playerSprites, newOffenseSide });
    }
  }
}

export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
