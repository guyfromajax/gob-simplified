import { playTurnAnimation } from "./playTurnAnimation.js";
import { onAction } from "./onAction.js";
import { passBall, lockBallToPlayer } from "./ballManager.js";

/**
 * Animate all turns from simData.turns using real backend structure.
 */
export async function animateGameTurns({ //hasBallAtStep
  scene,
  simData,
  playerSprites,
  ballSprite
}) {
  const turns = simData.turns || [];
  const allPlayers = simData.players || [];

  for (let i = 0; i < turns.length; i++) {
    const turn = turns[i];
    console.log(`🔁 Turn ${i + 1}`, turn);

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
      onAction: (action, sprite, timestamp) => {
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
            a.movement?.some(m => m.action === "receive" && m.timestamp >= passStep.timestamp)
          );
          const receiveStep = receiverAnim?.movement.find(
            m => m.action === "receive" && m.timestamp >= passStep.timestamp
          );

          if (passStep && receiveStep) {
            console.log("📤 Pass triggered");
            passBall({
              scene,
              ballSprite,
              fromCoords: passStep.coords,
              toCoords: receiveStep.coords,
              fromTimestamp: passStep.timestamp,
              toTimestamp: receiveStep.timestamp
            });
          }
        }

        if (action === "receive") {
          console.log("📥 Ball received by:", playerId);
          lockBallToPlayer(scene, ballSprite, sprite);
        }

        // if (action === "shoot" || sprite.playerId === shooterId) {
        //   console.log("🏀 Shot triggered. Hiding ball.");
        //   ballSprite.setVisible(false);
        // }
      }
    });
  }
}

