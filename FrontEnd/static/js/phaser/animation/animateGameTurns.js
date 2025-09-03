import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
import runFreeThrowSequence from "./freeThrow.js";
import runFastBreakSequence from "./fastBreak.js";
import { States } from "../state/gameStateMachine.js";

const DEBUG_FLOW =
  (typeof window !== 'undefined' && window.DEBUG_FLOW) ||
  (typeof process !== 'undefined' && process.env.DEBUG_FLOW) ||
  false;

function annotateFreeThrowTurns(turns = []) {
  let group = null;
  const flush = () => {
    if (!group) return;
    const total = group.turns.length;
    group.turns.forEach((t, idx) => {
      t.ftContext = {
        ftIndex: idx + 1,
        ftTotal: total,
        bonusType: group.bonusType,
      };
    });
    group = null;
  };
  for (const turn of turns) {
    if (turn.result_type === "FREE_THROW") {
      if (!group) {
        group = {
          turns: [],
          bonusType: turn.bonus_type || turn.bonusType,
        };
      }
      group.turns.push(turn);
    } else {
      flush();
    }
  }
  flush();
}

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
  annotateFreeThrowTurns(turns);
  const allPlayers = simData.players || [];
  if (DEBUG_FLOW) {
    const stepCount = turns.reduce((acc, t) => {
      const turnSteps = (t.animations || []).reduce(
        (sum, a) => sum + (a.movement?.length || 0),
        0
      );
      return acc + turnSteps;
    }, 0);
    console.log(`🟢 animateGameTurns start: ${turns.length} turns, ${stepCount} steps`);
  }

  const handlePossessionFlip = (payload = {}) => {
    if (scene.stateMachine?.is(States.FastBreak)) return;
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = payload.offenseTeamId;
    if (REBOUND_DEBUG) {
      console.log("reb:flip", { newPossession: payload.offenseTeamId });
    }
    scene.time.delayedCall(0, () => (scene.possessionFlipInProgress = false));
  };
  scene.events?.on?.('possessionChange', handlePossessionFlip);

  for (let i = 0; i < turns.length; i++) {
    scene.currentTurn = i;
    const turn = turns[i];
    turn.index = i;
    if (scene.skipToEnd) break;
    if (DEBUG_FLOW) console.log(`🔁 Turn ${i + 1}`, turn);

    if (turn.result_type === "FREE_THROW") {
      await runFreeThrowSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, ftContext: turn.ftContext });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      continue;
    }

    if (turn.result_type === "SIDE_INBOUND") {
      if (!scene.stateMachine?.is(States.FastBreak)) {
        await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
      }
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      continue;
    }

    if (turn.fast_break === true || turn.result_type === "FAST_BREAK") {
      await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate });
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
        if (DEBUG_FLOW) console.log(`🎬 Action "${action}" fired at ${timestamp}ms for sprite:`, sprite);
        onAction(action, sprite, timestamp);

        const playerId = Object.keys(playerSprites).find(
          key => playerSprites[key] === sprite
        );

        const anim = animations.find(a => a.playerId === playerId);
        const movement = anim?.movement || [];

        if (action === "pass") {
          if (scene.stateMachine?.is(States.FastBreak)) return;
          const passStep = movement.find(
            m => m.action === "pass" && m.timestamp === timestamp
          );
          if (!passStep) return;

          const receiverAnim = animations.find(a =>
            a.movement?.some(
              m => m.action === "receive" && m.timestamp === timestamp
            )
          );
          const receiveStep = receiverAnim?.movement.find(
            m => m.action === "receive" && m.timestamp === timestamp
          );

          if (passStep && receiveStep && receiverAnim?.playerId != null) {
            if (DEBUG_FLOW) console.log("📤 Pass triggered");
            const receiverSprite = playerSprites[receiverAnim.playerId];
            const endCoords = receiverSprite
              ? { x: receiverSprite.x, y: receiverSprite.y }
              : undefined;

            const delta = receiveStep.timestamp - timestamp;
            const duration = delta > 0 ? delta : animationConfig.pass.duration;
            if (DEBUG_FLOW) console.log(`⏱️ Resolved pass duration: ${duration}ms (delta=${delta})`);

            if (DEBUG_FLOW) {
              scene.events?.once('passStart', () => console.log('passStart'));
              scene.events?.once('tweenStart', () => console.log('tweenStart'));
              scene.events?.once('tweenEnd', () => console.log('tweenEnd'));
              scene.events?.once('ballAttached', () => console.log('ballAttached'));
              scene.events?.once('passEnd', () => console.log('passEnd'));
            }

            if (scene.__activePass) {
          console.warn(
            'Active pass tween detected before runPass call; cancelling previous tween'
          );
            }

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
    if (!scene.stateMachine?.is(States.FastBreak) && (turn.result_type === "STEAL" || stealEvent)) {
      const ballHandlerId = playerMap[turn.ball_handler] ?? turn.ball_handler;
      const stealerRaw =
        turn.stealerId ||
        turn.stealer_id ||
        stealEvent?.stealerId ||
        stealEvent?.stealer_id;
      const stealerId = stealerRaw ?? playerMap[turn.stealer_name];
      if (ballHandlerId != null && stealerId != null) {
        const cfg = animationConfig.steal || {};
        if (scene.__activePass) {
            console.warn('Active pass tween detected before steal; cancelling previous tween');
        }
        await runPass(scene, {
          fromId: ballHandlerId,
          toId: stealerId,
          duration: cfg.duration,
          easing: cfg.easing
        });
        const defenderSprite = playerSprites[stealerId];
        // runPass reattaches the ball after the tween resolves, so only emit
        // possession change once that handoff has finished.
        if (!scene.stateMachine?.is(States.FastBreak) && defenderSprite) {
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
    if (DEBUG_FLOW && i === turns.length - 1) {
      console.log('🔚 animateGameTurns last turn complete');
    }
  }

  scene.events?.off?.('possessionChange', handlePossessionFlip);
}

