import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, attachBallToPlayer } from "./ballManager.js";
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

            const delta = receiveStep.timestamp - passStep.timestamp;
            const duration = delta > 0 ? delta : animationConfig.pass.duration;
            console.log(`⏱️ Resolved pass duration: ${duration}ms (delta=${delta})`);

            scene.events?.once('passStart', () => console.log('passStart'));
            scene.events?.once('tweenStart', () => console.log('tweenStart'));
            scene.events?.once('tweenEnd', () => console.log('tweenEnd'));
            scene.events?.once('ballDetached', () => console.log('ballDetached'));
            scene.events?.once('ballAttached', () => console.log('ballAttached'));
            scene.events?.once('passEnd', () => console.log('passEnd'));

            await runPass(scene, {
              fromId: playerId,
              toId: receiverAnim.playerId,
              endCoords,
              duration,
              easing: animationConfig.pass.easing
            });
          }
        }

        // if (action === "shoot" || sprite.playerId === shooterId) {
        //   console.log("🏀 Shot triggered. Hiding ball.");
        //   ballSprite.setVisible(false);
        // }
      }
    });

    const stealEvent = turn.events?.find(e => e.event_type === "STEAL");
    if (turn.result_type === "STEAL" || stealEvent) {
      const ballHandlerId = playerMap[turn.ball_handler] ?? turn.ball_handler;
      const stealerRaw =
        turn.stealerId ||
        turn.stealer_id ||
        stealEvent?.stealerId ||
        stealEvent?.stealer_id;
      const stealerId = stealerRaw ?? playerMap[turn.stealer_name];
      if (ballHandlerId != null && stealerId != null) {
        const cfg = animationConfig.steal || {};
        await runPass(scene, {
          fromId: ballHandlerId,
          toId: stealerId,
          duration: cfg.duration,
          easing: cfg.easing
        });
        const defenderSprite = playerSprites[stealerId];
        if (defenderSprite) {
          attachBallToPlayer(scene, ballSprite, defenderSprite);
          scene.events?.emit?.('possessionChange', { offenseTeamId: defenderSprite.team_id });
        }
      }
    }

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

