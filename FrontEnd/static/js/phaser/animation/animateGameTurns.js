import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, lockBallToPlayer } from "./ballManager.js";
import animationConfig from "./animation_config.js";

/**
 * Animate all turns from simData.turns using real backend structure.
 */
export async function animateGameTurns({ //hasBallAtStep
  scene,
  simData,
  playerSprites,
  ballSprite,
  onUpdate
}) {
  const turns = simData.turns || [];
  const allPlayers = simData.players || [];

  for (let i = 0; i < turns.length; i++) {
    scene.currentTurn = i;
    const turn = turns[i];
    turn.index = i;
    if (scene.skipToEnd) break;
    console.log(`🔁 Turn ${i + 1}`, turn);

    if (turn.result_type === "SIDE_INBOUND") {
      await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      continue;
    }

    const shooterName = turn.shooter || "";
    const animations = turn.animations || [];

    const playerMap = Object.fromEntries(
      allPlayers.map(p => [p.name, p.playerId])
    );

    const shooterId = playerMap[shooterName];

    await playTurnAnimation({
      scene,
      simData,
      playerSprites,
      turnData: turn,
      ballSprite,
      onAction: async (action, sprite, timestamp) => {
        console.log(`🎬 Action "${action}" fired at ${timestamp}ms for sprite:`, sprite);
        onAction(action, sprite, timestamp);

        const playerId = Object.keys(playerSprites).find(
          key => playerSprites[key] === sprite
        );

        const anim = animations.find(a => a.playerId === playerId);
        const movement = anim?.movement || [];

        if (action === "handle_ball" && anim?.hasBallAtStep?.length) {
          console.log("🔒 Locking ball to ball handler:", playerId);
          lockBallToPlayer(scene, ballSprite, sprite);
        }

        if (action === "pass") {
          const passStep = movement.find(m => m.action === "pass");
          if (!passStep) return;

          const receiverAnim = animations.find(a =>
            a.movement?.some(m => m.action === "receive" && m.timestamp === passStep.timestamp)
          );
          const receiveStep = receiverAnim?.movement.find(
            m => m.action === "receive" && m.timestamp === passStep.timestamp
          );

          if (passStep && receiveStep && receiverAnim?.playerId != null) {
            console.log("📤 Pass triggered");
            const receiverSprite = playerSprites[receiverAnim.playerId];
            const endCoords = receiverSprite
              ? { x: receiverSprite.x, y: receiverSprite.y }
              : undefined;

            if (animationConfig.enableBallTween) {
              await runPass(scene, {
                fromId: playerId,
                toId: receiverAnim.playerId,
                endCoords,
                duration: receiveStep.timestamp - passStep.timestamp,
                easing: animationConfig.pass.easing
              });
            } else if (receiverSprite) {
              lockBallToPlayer(scene, ballSprite, receiverSprite);
            }
          }
        }

        // if (action === "shoot" || sprite.playerId === shooterId) {
        //   console.log("🏀 Shot triggered. Hiding ball.");
        //   ballSprite.setVisible(false);
        // }
      }
    });

    if (onUpdate) {
      try {
        onUpdate(turn);
      } catch (err) {
        console.error('Scoreboard update failed:', err);
      }
    }
    if (scene.skipToEnd) {
      for (let j = i + 1; j < turns.length; j++) {
        try {
          turns[j].index = j;
          if (onUpdate) onUpdate(turns[j]);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      break;
    }
  }
}

