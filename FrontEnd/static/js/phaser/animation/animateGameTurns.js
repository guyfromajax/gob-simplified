import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
import runFreeThrowSequence from "./freeThrow.js";
import runFastBreakSequence from "./fastBreak.js";
import { handleTurnover } from "./turnoverAdapter.js";
import { States } from "../state/gameStateMachine.js";
import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
  isPossessionRunnerEnabled,
} from "../utils/debugFlags.js";
import { getSceneStepLogger } from "./debugStepLogger.js";

const DEBUG_FLOW =
  (typeof window !== 'undefined' && window.DEBUG_FLOW) ||
  (typeof process !== 'undefined' && process.env.DEBUG_FLOW) ||
  false;

const NON_STANDARD_RESULTS = new Set([
  "FREE_THROW",
  "TURNOVER",
  "FAST_BREAK",
  "SIDE_INBOUND",
]);

let normalizeTurnModulePromise = null;
let possessionRunnerModulePromise = null;

function getResultType(turn = {}) {
  return turn?.result_type ?? turn?.resultType ?? null;
}

function isStandardHalfCourtPossession(turn = {}) {
  if (!turn) return false;
  const animations = Array.isArray(turn?.animations) ? turn.animations : [];
  if (!animations.length) return false;
  if (turn.fast_break === true) return false;
  const resultType = getResultType(turn);
  if (resultType && NON_STANDARD_RESULTS.has(resultType)) return false;
  return true;
}

async function loadPossessionRunnerDependencies() {
  if (!normalizeTurnModulePromise) {
    normalizeTurnModulePromise = import("./possession/normalizeTurn.js");
  }
  if (!possessionRunnerModulePromise) {
    possessionRunnerModulePromise = import("./possession/PossessionRunner.js");
  }
  const [normalizerModule, runnerModule] = await Promise.all([
    normalizeTurnModulePromise,
    possessionRunnerModulePromise,
  ]);
  const normalizeTurnFn =
    normalizerModule?.normalizeTurn || normalizerModule?.default || null;
  const PossessionRunnerClass =
    runnerModule?.PossessionRunner || runnerModule?.default || null;
  return { normalizeTurnFn, PossessionRunnerClass };
}

async function maybeRunPossession({
  scene,
  ballSprite,
  playerSprites,
  simData,
  turn,
  turnIndex,
  possessionId,
  debugEnabled,
}) {
  if (!isStandardHalfCourtPossession(turn)) {
    return false;
  }

  try {
  const { normalizeTurnFn, PossessionRunnerClass } =
      await loadPossessionRunnerDependencies();
    if (typeof normalizeTurnFn !== "function") return false;
    if (typeof PossessionRunnerClass !== "function") return false;

    const graph = normalizeTurnFn(turn, simData, { turnIndex });
    if (!graph) return false;
    if (graph?.context?.fastBreak) return false;

    const frames = Array.isArray(graph?.timeline?.frames)
      ? graph.timeline.frames
      : [];
    if (!frames.length) return false;

    const homeTeamId =
      simData?.home_team_id ?? simData?.homeTeamId ?? graph?.context?.homeTeamId ?? null;
    const awayTeamId =
      simData?.away_team_id ?? simData?.awayTeamId ?? graph?.context?.awayTeamId ?? null;
    if (graph.context) {
      if (typeof graph.context.homeTeamId === "undefined") {
        graph.context.homeTeamId = homeTeamId;
      }
      if (typeof graph.context.awayTeamId === "undefined") {
        graph.context.awayTeamId = awayTeamId;
      }
    }

    if (graph.context) {
      if (typeof graph.context.turnIndex === "undefined") {
        graph.context.turnIndex = turnIndex;
      }
      if (typeof graph.context.possessionId === "undefined") {
        graph.context.possessionId = possessionId ?? null;
      }
    }

    const runner = new PossessionRunnerClass({
      scene,
      ballSprite,
      playerSprites,
      graph,
      config: {
        turnIndex,
        homeTeamId,
        awayTeamId,
      },
    });
    await runner.run();

    if (debugEnabled) {
      const parts = [`Turn ${turnIndex + 1}`];
      const resultType = graph.context?.resultType || getResultType(turn);
      if (resultType) parts.push(`result=${resultType}`);
      if (possessionId != null) parts.push(`possession=${possessionId}`);
      animationDebugLog(
        `ANIM: PossessionRunner handled ${parts.join(" ")}`
      );
    }

    return true;
  } catch (error) {
    animationDebugWarn(
      "PossessionRunner failed, falling back to legacy animation",
      error
    );
    return false;
  }
}

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
  if (scene) scene.simData = simData;
  annotateFreeThrowTurns(turns);
  const allPlayers = simData.players || [];
  const debugEnabled = isAnimationDebugEnabled();
  const stepLogger = debugEnabled ? getSceneStepLogger(scene) : null;

  const clone = value => {
    if (!value) return value;
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (err) {
      return { ...value };
    }
  };

  if (debugEnabled && scene) {
    const baseScore = clone(simData.score || {});
    scene.__debugScoreSnapshot = {
      ...(scene.__debugScoreSnapshot || {}),
      ...baseScore,
    };
    if (typeof scene.__debugScoreDelta === "undefined") {
      scene.__debugScoreDelta = null;
    }
  }

  const updateDebugScore = (turn, meta = {}) => {
    if (!debugEnabled || !scene || !turn?.score) {
      if (debugEnabled && scene) scene.__debugScoreDelta = null;
      return;
    }
    const previous = scene.__debugScoreSnapshot || {};
    const next = turn.score || {};
    const teamKeys = new Set([
      ...Object.keys(previous || {}),
      ...Object.keys(next || {}),
    ]);
    const delta = {};
    for (const key of teamKeys) {
      const before = typeof previous?.[key] === "number" ? previous[key] : 0;
      const after = typeof next?.[key] === "number" ? next[key] : before;
      delta[key] = after - before;
    }
    scene.__debugScoreSnapshot = {
      ...previous,
      ...clone(next),
    };
    scene.__debugScoreDelta = delta;
    animationDebugLog("ANIM: score update", {
      ...meta,
      delta,
      score: clone(scene.__debugScoreSnapshot),
    });
  };

  const logVerbose = (...args) => {
    if (isAnimationDebugEnabled()) {
      animationDebugLog(...args);
      return;
    }
    if (DEBUG_FLOW) {
      console.log(...args);
    }
  };
  if (DEBUG_FLOW || debugEnabled) {
    const stepCount = turns.reduce((acc, t) => {
      const turnSteps = (t.animations || []).reduce(
        (sum, a) => sum + (a.movement?.length || 0),
        0
      );
      return acc + turnSteps;
    }, 0);
    logVerbose(`🟢 animateGameTurns start: ${turns.length} turns, ${stepCount} steps`);
  }

  const handlePossessionFlip = (payload = {}) => {
    if (scene.stateMachine?.is(States.FastBreak)) return;
    
    const previousOffenseTeamId = scene.offenseTeamId;
    const newOffenseTeamId = payload.offenseTeamId;
    
    animationDebugLog('POSSESSION CHANGE EVENT:', {
      previousOffenseTeamId,
      newOffenseTeamId,
      currentState: scene.stateMachine?.state,
      possessionFlipInProgress: scene.possessionFlipInProgress,
      currentTurn: scene.currentTurn,
      stackTrace: new Error().stack?.split('\n').slice(1, 6)
    });

    // Check if this is a duplicate possession change
    if (previousOffenseTeamId === newOffenseTeamId) {
      animationDebugWarn('DUPLICATE POSSESSION CHANGE DETECTED - same team!', {
        teamId: newOffenseTeamId,
        stackTrace: new Error().stack?.split('\n').slice(1, 6)
      });
    }
    
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = newOffenseTeamId;
    if (REBOUND_DEBUG) {
      animationDebugLog("reb:flip", { newPossession: payload.offenseTeamId });
    }
    scene.time.delayedCall(0, () => (scene.possessionFlipInProgress = false));
  };
  scene.events?.on?.('possessionChange', handlePossessionFlip);

  for (let i = 0; i < turns.length; i++) {
    scene.currentTurn = i;
    const turn = turns[i];
    turn.index = i;
    if (scene.skipToEnd) break;
    const possessionId =
      turn.possession_id ?? turn.possessionId ?? turn.possessionID ?? null;
    const animations = turn.animations || [];
    const shouldLogLegacySteps =
      debugEnabled &&
      stepLogger &&
      (!isPossessionRunnerEnabled() || !isStandardHalfCourtPossession(turn));

    if (shouldLogLegacySteps) {
      const maxSteps = Math.max(
        0,
        ...animations.map(anim => anim.movement?.length || 0)
      );
      for (let stepIndex = 0; stepIndex < maxSteps; stepIndex++) {
        const stepPayload = {
          turnIndex: i,
          turnId: turn.id ?? turn.turn_id ?? null,
          possessionId,
          possessionTeamId:
            turn.possession_team_id ?? turn.possessionTeamId ?? null,
          stepIndex,
          timestamp: null,
          actions: [],
        };
        for (const anim of animations) {
          const step = anim.movement?.[stepIndex];
          if (!step) continue;
          if (
            stepPayload.timestamp == null &&
            typeof step.timestamp === "number"
          ) {
            stepPayload.timestamp = step.timestamp;
          }
          stepPayload.actions.push({
            playerId: anim.playerId ?? anim.player_id ?? null,
            action: step.action || null,
          });
        }
        if (stepPayload.actions.length) {
          stepLogger.logStep(stepPayload);
        }
      }
    }
    if (DEBUG_FLOW || debugEnabled) logVerbose(`🔁 Turn ${i + 1}`, turn);

    if (turn.result_type === "FREE_THROW") {
      await runFreeThrowSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, ftContext: turn.ftContext });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
      continue;
    }

    if (turn.result_type === "FOUL") {
      // Check if this is an FCP foul with animations
      if (turn.fcp_foul === true && turn.animations && turn.animations.length > 0) {
        // FCP foul with animations - animate it like a standard turn
        await playTurnAnimation({
          scene,
          simData,
          playerSprites,
          turnData: turn,
          ballSprite,
          onUpdate,
          turnIndex: i,
          onAction: async (action, sprite, timestamp) => {
            if (DEBUG_FLOW || debugEnabled)
              logVerbose(
                `🎬 Action "${action}" fired at ${timestamp}ms for sprite:`,
                sprite
              );
            if (onAction) onAction(action, sprite, timestamp);
          },
        });
      }
      // Update scoreboard for all fouls (FCP or not)
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
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
      updateDebugScore(turn, { turnIndex: i, possessionId });
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
      updateDebugScore(turn, { turnIndex: i, possessionId });
      continue;
    }

    // Debug fast break routing
    // NOTE: next_play_type indicates what the NEXT turn will be, not this turn
    // Only route to fast break if THIS turn is actually a fast break
    if (turn.fast_break === true || turn.result_type === "FAST_BREAK") {
      animationDebugLog('FAST BREAK TURN DETECTED - routing to runFastBreakSequence:', {
        fast_break: turn.fast_break,
        result_type: turn.result_type,
        next_play_type: turn.next_play_type,
        turn_index: i
      });
      await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, turnIndex: i });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
      continue;
    }
    
    // Check for FCP shots - route to standard shot animation
    if (turn.fcp_shot === true) {
      animationDebugLog('FCP SHOT TURN - routing to standard shot animation:', {
        result_type: turn.result_type,
        turn_index: i
      });
      await playTurnAnimation({
        scene,
        simData,
        playerSprites,
        turnData: turn,
        ballSprite,
        onUpdate,
        turnIndex: i,
        onAction: async (action, sprite, timestamp) => {
          if (DEBUG_FLOW || debugEnabled)
            logVerbose(
              `🎬 Action "${action}" fired at ${timestamp}ms for sprite:`,
              sprite
            );
          if (onAction) onAction(action, sprite, timestamp);
        },
      });
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
      continue;
    }
    
    // Debug: Check if this should be a fast break but isn't being detected
    if (turn.result_type === "MAKE" || turn.result_type === "MISS") {
      animationDebugLog('SHOT TURN - checking for fast break indicators:', {
        result_type: turn.result_type,
        fast_break: turn.fast_break,
        turn_index: i,
        all_turn_keys: Object.keys(turn),
        full_turn_data: turn
      });
      
      // Check if this is a fast break turn (now properly flagged by backend)
      if (turn.fast_break === true) {
        animationDebugLog('FAST BREAK TURN DETECTED - routing to runFastBreakSequence');
        await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, turnIndex: i });
        if (onUpdate) {
          try {
            onUpdate(turn);
          } catch (err) {
            console.error('Scoreboard update failed:', err);
          }
        }
        updateDebugScore(turn, { turnIndex: i, possessionId });
        continue;
      }
    }

    const shooterName = turn.shooter || "";

    const playerMap = Object.fromEntries(
      allPlayers.map(p => [p.name, p.playerId])
    );

    const shooterId = playerMap[shooterName];

    const handledByRunner =
      isPossessionRunnerEnabled() &&
      (await maybeRunPossession({
        scene,
        ballSprite,
        playerSprites,
        simData,
        turn,
        turnIndex: i,
        possessionId,
        debugEnabled,
      }));

    if (!handledByRunner) {
      await playTurnAnimation({
        scene,
        simData,
        playerSprites,
        turnData: turn,
        ballSprite,
        onAction: async (action, sprite, timestamp) => {
          if (DEBUG_FLOW || debugEnabled)
            logVerbose(
              `🎬 Action "${action}" fired at ${timestamp}ms for sprite:`,
              sprite
            );
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
              if (DEBUG_FLOW || debugEnabled) logVerbose("📤 Pass triggered");
              const receiverSprite = playerSprites[receiverAnim.playerId];
              const endCoords = receiverSprite
                ? { x: receiverSprite.x, y: receiverSprite.y }
                : undefined;

              const delta = receiveStep.timestamp - timestamp;
              const duration =
                delta > 0 ? delta : animationConfig.pass.duration;
              if (DEBUG_FLOW || debugEnabled)
                logVerbose(
                  `⏱️ Resolved pass duration: ${duration}ms (delta=${delta})`
                );

              if (DEBUG_FLOW || debugEnabled) {
                scene.events?.once('passStart', () => logVerbose('passStart'));
                scene.events?.once('tweenStart', () => logVerbose('tweenStart'));
                scene.events?.once('tweenEnd', () => logVerbose('tweenEnd'));
                scene.events?.once('ballAttached', () => logVerbose('ballAttached'));
                scene.events?.once('passEnd', () => logVerbose('passEnd'));
              }

              if (scene.__activePass) {
                animationDebugWarn(
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
          animationDebugWarn('Active pass tween detected before steal; cancelling previous tween');
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
    updateDebugScore(turn, { turnIndex: i, possessionId });
    if (scene.skipToEnd) {
      for (let j = i + 1; j < turns.length; j++) {
        try {
          const futureTurn = turns[j];
          futureTurn.index = j;
          if (onUpdate) onUpdate(futureTurn);
          if (debugEnabled) {
            const futurePossession =
              futureTurn.possession_id ??
              futureTurn.possessionId ??
              futureTurn.possessionID ??
              null;
            updateDebugScore(futureTurn, {
              turnIndex: j,
              possessionId: futurePossession,
            });
          }
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      break;
    }
    if ((DEBUG_FLOW || debugEnabled) && i === turns.length - 1) {
      logVerbose('🔚 animateGameTurns last turn complete');
    }
  }

  scene.events?.off?.('possessionChange', handlePossessionFlip);
}
