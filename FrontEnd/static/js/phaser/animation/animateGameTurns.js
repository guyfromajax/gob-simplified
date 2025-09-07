import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
import runFreeThrowSequence from "./freeThrow.js";
import runFastBreakSequence from "./fastBreak.js";
import { handleTurnover } from "./turnoverAdapter.js";
import { States } from "../state/gameStateMachine.js";
import { AnimationRouter } from "./AnimationRouter.js";

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
  console.log('🎬 animateGameTurns: Starting animation system');
  const turns = simData.turns || [];
  console.log('🎬 animateGameTurns: Processing turns', { turnCount: turns.length });
  annotateFreeThrowTurns(turns);
  const allPlayers = simData.players || [];
  
  // Initialize new animation router
  console.log('🎬 animateGameTurns: Creating AnimationRouter');
  const animationRouter = new AnimationRouter(scene, playerSprites, ballSprite, onUpdate);
  console.log('🎬 animateGameTurns: AnimationRouter created successfully');
  
  if (DEBUG_FLOW) {
    const stepCount = turns.reduce((acc, t) => {
      const turnSteps = (t.animations || []).reduce(
        (sum, a) => sum + (a.movement?.length || 0),
        0
      );
      return acc + turnSteps;
    }, 0);
    console.log(`🟢 animateGameTurns start: ${turns.length} turns, ${stepCount} steps`);
    console.log('🆕 Using new AnimationRouter system');
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
      stackTrace: new Error().stack?.split('\n').slice(1, 6)
    });
    
    // Check if this is a duplicate possession change
    if (previousOffenseTeamId === newOffenseTeamId) {
      console.warn('DUPLICATE POSSESSION CHANGE DETECTED - same team! Ignoring...', {
        teamId: newOffenseTeamId,
        stackTrace: new Error().stack?.split('\n').slice(1, 6)
      });
      return; // Ignore duplicate possession changes
    }
    
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = newOffenseTeamId;
    if (REBOUND_DEBUG) {
      console.log("reb:flip", { newPossession: payload.offenseTeamId });
    }
    scene.time.delayedCall(0, () => (scene.possessionFlipInProgress = false));
  };
  scene.events?.on?.('possessionChange', handlePossessionFlip);

  console.log('🎬 animateGameTurns: Starting turn processing loop', { totalTurns: turns.length });
  
  for (let i = 0; i < turns.length; i++) {
    scene.currentTurn = i;
    const turn = turns[i];
    turn.index = i;
    console.log(`🎬 animateGameTurns: Processing turn ${i + 1}/${turns.length}`, { 
      result_type: turn.result_type,
      skipToEnd: scene.skipToEnd 
    });
    
    if (scene.skipToEnd) {
      console.log('🎬 animateGameTurns: Skipping to end, breaking loop');
      break;
    }
    if (DEBUG_FLOW) console.log(`🔁 Turn ${i + 1}`, turn);

    if (turn.result_type === "FREE_THROW") {
      console.log('🎬 Using proven playTurnAnimation for FREE_THROW');
      try {
        const { playTurnAnimation } = await import('./turnAnimation.js');
        await playTurnAnimation({
          scene: scene,
          simData: simData,
          playerSprites: playerSprites,
          turnData: turn,
          ballSprite: ballSprite,
          onAction: onUpdate
        });
        console.log('✅ playTurnAnimation completed for FREE_THROW');
      } catch (error) {
        console.error('❌ playTurnAnimation failed for FREE_THROW:', error);
        console.log('🔄 Falling back to new AnimationRouter for FREE_THROW');
        try {
          await animationRouter.processTurn(turn);
          console.log('✅ AnimationRouter fallback completed for FREE_THROW');
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for FREE_THROW:', fallbackError);
        }
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

    if (turn.result_type === "SIDE_INBOUND") {
      console.log('🎬 Using new PassAnimationSystem for SIDE_INBOUND');
      
      try {
        // Use the new PassAnimationSystem for inbound passes
        await animationRouter.processTurn(turn);
        console.log('✅ PassAnimationSystem completed for SIDE_INBOUND');
      } catch (error) {
        console.error('❌ PassAnimationSystem failed for SIDE_INBOUND:', error);
        
        // Fallback to old system if new system fails
        console.log('🔄 Falling back to runSideInboundSetup for SIDE_INBOUND');
        try {
          if (!scene.stateMachine?.is(States.FastBreak)) {
            await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
          }
          console.log('✅ runSideInboundSetup fallback completed for SIDE_INBOUND');
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for SIDE_INBOUND:', fallbackError);
        }
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

    if (turn.result_type === "BASELINE_INBOUND") {
      console.log('🎬 Using new PassAnimationSystem for BASELINE_INBOUND');
      
      try {
        // Use the new PassAnimationSystem for baseline inbound passes
        await animationRouter.processTurn(turn);
        console.log('✅ PassAnimationSystem completed for BASELINE_INBOUND');
      } catch (error) {
        console.error('❌ PassAnimationSystem failed for BASELINE_INBOUND:', error);
        
        // Fallback to old system if new system fails
        console.log('🔄 Falling back to runSideInboundSetup for BASELINE_INBOUND');
        try {
          if (!scene.stateMachine?.is(States.FastBreak)) {
            await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
          }
          console.log('✅ runSideInboundSetup fallback completed for BASELINE_INBOUND');
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for BASELINE_INBOUND:', fallbackError);
        }
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
      console.log('🆕 Using new AnimationRouter for FAST_BREAK:', {
        fast_break: turn.fast_break,
        result_type: turn.result_type,
        turn_index: i
      });
      await animationRouter.processTurn(turn);
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
      
      // Fast break shots now use the new system (same as HCO shots)
      if (turn.fast_break === true) {
        console.log('🎬 Using new ShotAnimationSystem for FAST_BREAK shot');
        try {
          // Use the new ShotAnimationSystem for fast break shots
          await animationRouter.processTurn(turn);
          console.log('✅ ShotAnimationSystem completed for FAST_BREAK');
        } catch (error) {
          console.error('❌ ShotAnimationSystem failed for FAST_BREAK:', error);
          
          // Fallback to old system if new system fails
          console.log('🔄 Falling back to playTurnAnimation for FAST_BREAK');
          try {
            const { playTurnAnimation } = await import('./turnAnimation.js');
            await playTurnAnimation({
              scene: scene,
              simData: simData,
              playerSprites: playerSprites,
              turnData: turn,
              ballSprite: ballSprite,
              onAction: onUpdate
            });
            console.log('✅ playTurnAnimation fallback completed for FAST_BREAK');
          } catch (fallbackError) {
            console.error('❌ Both animation systems failed for FAST_BREAK:', fallbackError);
          }
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
    }

    const shooterName = turn.shooter || "";
    const animations = turn.animations || [];

    const playerMap = Object.fromEntries(
      allPlayers.map(p => [p.name, p.playerId])
    );

    const shooterId = playerMap[shooterName];

    // 🎯 HYBRID APPROACH: Use new system for shots, old system for everything else
    if (turn.result_type === 'MAKE' || turn.result_type === 'MISS') {
      console.log('🎬 Using new ShotAnimationSystem for shot:', turn.result_type);
      
      try {
        // Use the new ShotAnimationSystem for shot animations
        await animationRouter.processTurn(turn);
        console.log('✅ ShotAnimationSystem completed for shot:', turn.result_type);
      } catch (error) {
        console.error('❌ ShotAnimationSystem failed for shot:', turn.result_type, error);
        
        // Fallback to old system if new system fails
        console.log('🔄 Falling back to playTurnAnimation for shot:', turn.result_type);
        try {
          const { playTurnAnimation } = await import('./turnAnimation.js');
          await playTurnAnimation({
            scene: scene,
            simData: simData,
            playerSprites: playerSprites,
            turnData: turn,
            ballSprite: ballSprite,
            onAction: onUpdate
          });
          console.log('✅ playTurnAnimation fallback completed for shot:', turn.result_type);
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for shot:', turn.result_type, fallbackError);
        }
      }
    } else if (turn.result_type === 'DREB' || turn.result_type === 'OREB') {
      // Use new system for rebounds
      console.log('🎬 Using new ReboundAnimationSystem for rebound:', turn.result_type);
      
      try {
        // Use the new ReboundAnimationSystem for rebound animations
        await animationRouter.processTurn(turn);
        console.log('✅ ReboundAnimationSystem completed for rebound:', turn.result_type);
      } catch (error) {
        console.error('❌ ReboundAnimationSystem failed for rebound:', turn.result_type, error);
        
        // Fallback to old system if new system fails
        console.log('🔄 Falling back to playTurnAnimation for rebound:', turn.result_type);
        try {
          const { playTurnAnimation } = await import('./turnAnimation.js');
          await playTurnAnimation({
            scene: scene,
            simData: simData,
            playerSprites: playerSprites,
            turnData: turn,
            ballSprite: ballSprite,
            onAction: onUpdate
          });
          console.log('✅ playTurnAnimation fallback completed for rebound:', turn.result_type);
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for rebound:', turn.result_type, fallbackError);
        }
      }
    } else {
      // Use old system for other non-shot turns
      console.log('🎬 Using proven playTurnAnimation for turn:', turn.result_type);
      
      try {
        const { playTurnAnimation } = await import('./turnAnimation.js');
        await playTurnAnimation({
          scene: scene,
          simData: simData,
          playerSprites: playerSprites,
          turnData: turn,
          ballSprite: ballSprite,
          onAction: onUpdate
        });
        console.log('✅ playTurnAnimation completed for turn:', turn.result_type);
      } catch (error) {
        console.error('❌ playTurnAnimation failed for turn:', turn.result_type, error);
        
        // Fallback to new system if old system fails
        console.log('🔄 Falling back to new AnimationRouter for turn:', turn.result_type);
        try {
          await animationRouter.processTurn(turn);
          console.log('✅ AnimationRouter fallback completed for turn:', turn.result_type);
        } catch (fallbackError) {
          console.error('❌ Both animation systems failed for turn:', turn.result_type, fallbackError);
        }
      }
    }

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
  console.log('🎬 animateGameTurns: Animation system completed');
}

