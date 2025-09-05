import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
import runFreeThrowSequence from "./freeThrow.js";
import runFastBreakSequence from "./fastBreak.js";
import { handleTurnover } from "./turnoverAdapter.js";
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
    
    const previousOffenseTeamId = scene.offenseTeamId;
    const newOffenseTeamId = payload.offenseTeamId;
    
    console.log('POSSESSION CHANGE EVENT:', {
      previousOffenseTeamId,
      newOffenseTeamId,
      currentState: scene.stateMachine?.state,
      possessionFlipInProgress: scene.possessionFlipInProgress,
      currentTurn: scene.currentTurn,
      stackTrace: new Error().stack?.split('\n').slice(1, 4)
    });
    
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = newOffenseTeamId;
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

    if (turn.result_type === "TURNOVER") {
      await handleTurnover(scene, { playerSprites, ballSprite, turnData: turn, onUpdate });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      continue;
    }

    // Debug fast break routing
    if (turn.fast_break === true || turn.result_type === "FAST_BREAK") {
      console.log('FAST BREAK TURN DETECTED - routing to runFastBreakSequence:', {
        fast_break: turn.fast_break,
        result_type: turn.result_type,
        turn_index: i
      });
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
    
    // Debug: Check if this should be a fast break but isn't being detected
    if (turn.result_type === "MAKE" || turn.result_type === "MISS") {
      console.log('SHOT TURN - checking for fast break indicators:', {
        result_type: turn.result_type,
        fast_break: turn.fast_break,
        turn_index: i,
        all_turn_keys: Object.keys(turn),
        full_turn_data: turn
      });
      
      // TEMPORARY FIX: If this is a shot after a fast break defensive rebound setup, treat it as a fast break
      const isAfterFastBreakSetup = scene.stateMachine?.is(States.FastBreak) || 
                                   (i > 0 && turns[i-1]?.result_type === "FAST_BREAK") ||
                                   turn.fast_break === true;
      
      console.log('FAST BREAK DETECTION CHECK:', {
        isAfterFastBreakSetup,
        currentState: scene.stateMachine?.state,
        previousTurnResultType: i > 0 ? turns[i-1]?.result_type : 'none',
        turnFastBreak: turn.fast_break,
        willForce: isAfterFastBreakSetup && !turn.fast_break
      });
      
      if (isAfterFastBreakSetup && !turn.fast_break) {
        console.log('FORCING FAST BREAK DETECTION for shot after fast break setup');
        turn.fast_break = true;
        // Re-route to fast break sequence
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
      
      // ADDITIONAL FIX: If we see a shot turn that should be a fast break based on context
      // Check if the previous turn was a defensive rebound setup that led to fast break
      const previousTurn = i > 0 ? turns[i-1] : null;
      const isShotAfterDefensiveRebound = previousTurn && 
                                        (previousTurn.result_type === "MISS" || 
                                         previousTurn.result_type === "DREB") &&
                                        (turn.result_type === "MAKE" || turn.result_type === "MISS");
      
      if (isShotAfterDefensiveRebound && !turn.fast_break) {
        console.log('FORCING FAST BREAK DETECTION for shot after defensive rebound');
        turn.fast_break = true;
        // Re-route to fast break sequence
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
      
      // COMPREHENSIVE FIX: Check for fast break indicators in the turn data itself
      const hasFastBreakRoles = turn.roles && (
        turn.roles.outlet_passer || 
        turn.roles.outlet_receiver ||
        turn.roles.fast_break_players
      );
      
      const hasFastBreakText = turn.text && turn.text.toLowerCase().includes('fast break');
      
      const isFastBreakShot = hasFastBreakRoles || hasFastBreakText;
      
      console.log('COMPREHENSIVE FAST BREAK CHECK:', {
        hasFastBreakRoles,
        hasFastBreakText,
        isFastBreakShot,
        roles: turn.roles,
        text: turn.text
      });
      
      if (isFastBreakShot && !turn.fast_break) {
        console.log('FORCING FAST BREAK DETECTION based on turn data');
        turn.fast_break = true;
        // Re-route to fast break sequence
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

