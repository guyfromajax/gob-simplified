import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { lockBallToPlayer } from "./ballManager.js";

/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
function updateBallOwnership({ ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  console.log("🟡 inside updateBallOwnership → stepIndex:", stepIndex);
  for (const anim of animations) {
    const sprite = playerSprites[anim.playerId];
    const hasBall = anim.hasBallAtStep?.[stepIndex];
    const team = sprite?.team_id;

    if (hasBall && sprite && team === offenseTeamId && ballSprite?.setPosition) {
      console.log("All four conditions are met")
      ballSprite.setPosition(sprite.x, sprite.y);
      ballSprite.setVisible(true);
      if (currentBallOwnerRef) currentBallOwnerRef.value = sprite;

      console.log("🟡 also inside updateBallOwnership → Ball assigned at step", stepIndex, {
        playerId: anim.playerId,
        hasBall,
        team: sprite?.team_id,
        offenseTeamId
      });
    } else {
      console.log("🟡 all four conditions are not met at step", stepIndex);
    }
      

      break;
    }
  }


/**
 * Smoothly move all players to their step 0 positions before possession begins.
 * Locks the ball to the player with hasBallAtStep[0] during this setup tween.
 */

async function runSetupTween({ scene, ballSprite, animations, playerSprites, currentBallOwnerRef }) {
  const stepIndex = 0;
  const promises = [];

  for (const anim of animations) {
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
      scene.tweens.add({
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
        onComplete: resolve
      });
    }));
  }

  await Promise.all(promises);
}


// Previous verions as of July 11, 2025
// async function runSetupTween({ scene, ballSprite, animations, playerSprites, offenseTeamId }) {
//   const stepIndex = 0;
//   const promises = [];
//   console.log("🟡 runSetupTween → ballSprite defined?", !!ballSprite);

//   // ✅ Find ball owner from offensive team before tweening
//   let ballOwnerSprite = null;
//   for (const anim of animations) {
//     const sprite = playerSprites[anim.playerId];
//     const hasBall = anim.hasBallAtStep?.[stepIndex];
//     console.log("🔍 Checking sprite team match →", {
//       spriteTeam: sprite?.team_id,
//       offenseTeamId
//     });
//     if (hasBall && sprite?.team_id === offenseTeamId) {
//       ballOwnerSprite = sprite;
//       break;
//     }
//   }

//   // ✅ Pre-place the ball at correct start location
//   if (ballOwnerSprite && ballSprite?.setPosition) {
//     ballSprite.setPosition(ballOwnerSprite.x, ballOwnerSprite.y);
//     ballSprite.setVisible(true);
//   } else if (ballSprite) {
//     ballSprite.setVisible(false);
//   }

//   for (const anim of animations) {
//     const sprite = playerSprites[anim.playerId];
//     const firstStep = anim.movement?.[0];

//     if (!sprite || !firstStep) continue;

//     const { x, y } = gridToPixels(
//       firstStep.coords.x,
//       firstStep.coords.y,
//       scene.game.config.width,
//       scene.game.config.height
//     );

//     promises.push(new Promise((resolve) => {
//       scene.tweens.add({
//         targets: [sprite],
//         x,
//         y,
//         duration: 2000,
//         ease: "Linear",
//         onUpdate: () => {
//           if (sprite === ballOwnerSprite && ballSprite?.setPosition) {
//             ballSprite.setPosition(sprite.x, sprite.y);
//             ballSprite.setVisible(true);
//           }
//         },
//         onComplete: resolve
//       });
//     }));
//   }

//   // Final snap just in case
//   if (ballOwnerSprite && ballSprite?.setPosition) {
//     ballSprite.setPosition(ballOwnerSprite.x, ballOwnerSprite.y);
//   }
// }

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
    if (anim.hasBallAtStep?.[0]) {
      step0OwnerSprite = playerSprites[anim.playerId];
      break;
    }
  }

  if (step0OwnerSprite) {
    lockBallToPlayer(ballSprite, step0OwnerSprite);
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

  // ✅ NEW: Lock ball ownership to correct player at step 
  updateBallOwnership({
    ballSprite,
    animations: turnData.animations,
    playerSprites,
    stepIndex: 0,
    offenseTeamId: turnData.possession_team_id,
    currentBallOwnerRef
  });

  for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
    updateBallOwnership({
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      stepIndex,
      offenseTeamId: turnData.possession_team_id,
      currentBallOwnerRef
    });

    const promises = [];

    for (const anim of turnData.animations) {
      const sprite = playerSprites[anim.playerId];
      const movement = anim.movement;

      if (!sprite || stepIndex >= movement.length) continue;

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const duration = (curr.timestamp - prev.timestamp) * 3;

      const promise = animateStep({
        scene,
        sprite,
        step: curr,
        duration,
        ballSprite,
        currentBallOwnerRef
      });

      promises.push(promise);
    }

    await Promise.all(promises);
  }
}
