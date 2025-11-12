import { playTurnAnimation, runSideInboundSetup } from "./turnAnimation.js";
import { onAction } from "./onAction.js";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
import runFreeThrowSequence from "./freeThrow.js";
import runFastBreakSequence from "./fastBreak.js";
import { runOpeningTipSequence } from "./openingTip.js";
import { animateStep } from "./animateStep.js";
import { handleTurnover } from "./turnoverAdapter.js";
import { States } from "../state/gameStateMachine.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import { getCurrentOwner, getPendingOwner } from "../ball/ballController.js";
import { updatePlaycallDisplay } from "../utils/playcallDisplay.js";
import { announceFromTurnData } from "../utils/announcements.js";
import { updateStrategyBars } from "../utils/strategyBars.js";
import { updatePlaycallCenter, animateLeanMeter, parseLeanScoreFromText } from "../ui/playcallCenter.js";
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
  "PUTBACK_MAKE",
  "PUTBACK_MISS",
  "OREB_KICKOUT",
  "DEFENSIVE_STOP",
  "OPENING_TIP",
]);

let normalizeTurnModulePromise = null;
let possessionRunnerModulePromise = null;

/**
 * Handle offensive rebound turns (putbacks and kickouts)
 */
async function handleOrebTurn(scene, { playerSprites, ballSprite, turnData, onUpdate }) {
  const { shootBall } = await import('./ballManager.js');
  const { animateKickoutReset } = await import('./ballManager.js');
  const { runInboundSetup } = await import('./turnAnimation.js');
  const { HOME_RIM_COORDS, AWAY_RIM_COORDS } = await import('./courtConstants.js');
  
  appendToTextScroll(turnData.text);
  
  const rebounderId = turnData.rebounderId || turnData.ball_handler?.player_id;
  const rebounderSprite = playerSprites[rebounderId];
  
  if (!rebounderSprite) return;
  
  if (turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS") {
    // Animate putback attempt using shootBall
    const isHomeTeam = rebounderSprite.team === "home";
    const rimCoords = isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const result = turnData.result_type === "PUTBACK_MAKE" ? "MAKE" : "MISS";
    
    // Get rebounder's current position for shot start
    const fromCoords = {
      x: (rebounderSprite.x / scene.game.config.width) * 100,
      y: 50 - (rebounderSprite.y / scene.game.config.height) * 50
    };
    
    await shootBall({
      scene,
      ballSprite,
      fromCoords,
      startTimestamp: Date.now(),
      result,
      shooterId: rebounderId,
      shooterTeamId: turnData.shooter_team_id || rebounderSprite.team_id,
      homeTeamId: scene.simData?.home_team_id,
      stepIndex: 0,
      turnIndex: scene.currentTurn,
      turnData: turnData
    });
    
    // Handle putback make - run inbound setup
    if (turnData.result_type === "PUTBACK_MAKE") {
      const shooterTeamId = rebounderSprite.team_id;
      const homeTeamId = scene.simData?.home_team_id;
      const awayTeamId = scene.simData?.away_team_id;
      const shooterTeamIsHome = String(shooterTeamId) === String(homeTeamId);
      const newOffenseSide = shooterTeamIsHome ? "away" : "home";
      
      // Check for defensive pressure
      const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
      const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
      
      await runInboundSetup({
        scene,
        ballSprite,
        playerSprites,
        newOffenseSide,
        homeTeamId,
        awayTeamId,
        skipRetreat,
        pressureType,
      });
    }
    // Handle putback miss with rebound
    else if (turnData.rebound_type) {
      const { animateRebound } = await import('./ballManager.js');
      const { bounceFromRim } = await import('./ballManager.js');
      
      const isHomeOffense = rebounderSprite.team === "home";
      const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
      const miss = await bounceFromRim(scene, ballSprite, basket, isHomeOffense, 300);
      
      // Use backend's ballSpot if provided (ensures DREB animates at correct basket)
      // Otherwise fall back to frontend's calculated bounce spot
      const reboundBallSpot = turnData.ballSpot || miss.grid;
      
      await animateRebound({
        scene,
        ballSprite,
        playerSprites,
        animations: [],
        rebounderId: turnData.rebounderId,
        ballSpot: reboundBallSpot,
        shooterId: rebounderId
      });
      
      // If DREB, set up next play
      if (turnData.rebound_type === "DREB" && turnData.next_play_type !== "FAST_BREAK") {
        const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
        await runDefensiveReboundSetup({
          scene,
          ballSprite,
          playerSprites,
          rebounderId: turnData.rebounderId,
          nextPlayType: turnData.next_play_type || "HCO"
        });
      }
      // If another OREB, it will be handled by the next OREB turn
    }
  } else if (turnData.result_type === "OREB_KICKOUT") {
    // Animate kickout pass to PG
    const pgId = turnData.pgId;
    await animateKickoutReset(
      scene,
      ballSprite,
      rebounderId,
      pgId,
      turnData.pass || {},
      500
    );
  }
}

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
  // console.log('🎬 animateGameTurns: Starting animation system');
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
      return; // Ignore duplicate possession changes
    }
    
    scene.possessionFlipInProgress = true;
    scene.offenseTeamId = newOffenseTeamId;
    if (REBOUND_DEBUG) {
      animationDebugLog("reb:flip", { newPossession: payload.offenseTeamId });
    }
    scene.time.delayedCall(0, () => (scene.possessionFlipInProgress = false));
  };
  scene.events?.on?.('possessionChange', handlePossessionFlip);

  // console.log('🎬 animateGameTurns: Starting turn processing loop', { totalTurns: turns.length });
  
  for (let i = 0; i < turns.length; i++) {
    scene.currentTurn = i;
    const turn = turns[i];
    turn.index = i;
    if (scene.skipToEnd) break;
    
    // Update playcall display before animating the turn
    updatePlaycallDisplay(turn, scene.simData?.home_team_id);
    
    // Update strategy bars at start of turn
    updateStrategyBars(turn, scene.simData?.home_team_id);
    
    // Update Playcall Center (panels and reset lean meter)
    updatePlaycallCenter(turn, scene.simData?.home_team_id);
    
    // Parse lean score for later animation (at middle step)
    const leanScore = parseLeanScoreFromText(turn);
    const animations = turn.animations || [];
    
    // Calculate middle step for lean meter animation
    if (leanScore !== null && animations.length > 0) {
      // Find the max number of steps across all player animations
      const maxSteps = Math.max(
        0,
        ...animations.map(anim => anim.movement?.length || 0)
      );
      
      // Calculate middle step (round up for even numbers)
      const middleStep = Math.ceil(maxSteps / 2);
      
      // Store for use during animation
      scene._leanScoreToAnimate = leanScore;
      scene._leanAnimationStep = middleStep;
      scene._leanAnimationTriggered = false;
    } else {
      scene._leanScoreToAnimate = null;
    }
    
    // Show announcement for turn start events (Fast Break, Press, Trap)
    announceFromTurnData(turn, 'start', scene.simData?.home_team_id, scene);
    
    const possessionId =
      turn.possession_id ?? turn.possessionId ?? turn.possessionID ?? null;
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
      // Update active player display for free throw
      const { getBallHandlerIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
      const shooterId = getBallHandlerIdFromTurn(turn, 0);
      if (shooterId) {
        updateActivePlayers(shooterId, null, scene.simData?.home_team_id, playerSprites);
      }
      
      await runFreeThrowSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, ftContext: turn.ftContext });
      
      // Display free throw result text
      appendToTextScroll(turn.text || "Free throw attempt");
      
      // NOTE: onUpdate is already called inside runFreeThrowSequence for each FT attempt
      // Do NOT call it again here or stats will be double counted
      
      updateDebugScore(turn, { turnIndex: i, possessionId });
      continue;
    }

    if (turn.result_type === "FOUL") {
      // Check if this is an FCP or HCT foul with animations
      if ((turn.fcp_foul === true || turn.hct_foul === true) && turn.animations && turn.animations.length > 0) {
        // FCP/HCT foul with animations - animate it like a standard turn
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
      
      // Announce foul (visual effects now handled by announcement system)
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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
    
    if (turn.result_type === "DEAD BALL") {
      // DEAD BALL turnover (from FCP/HCT) - visual effects handled by announcement system
      // Announce turnover
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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

    if (turn.result_type === "BASELINE_INBOUND") {
      // console.log('🏀 Quarter start BASELINE_INBOUND detected, animating all players');
      
      // Animate all players to their positions
      const { tweenPlayerTo } = await import('./ballTween.js');
      const { gridToPixels } = await import('../utils/gridToPixels.js');
      
      await Promise.all(
        (turn.animations || []).map(anim => {
          const sprite = playerSprites[anim.playerId];
          if (!sprite || !anim.movement || anim.movement.length < 2) return Promise.resolve();
          
          const endStep = anim.movement[anim.movement.length - 1];
          const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, scene.game.config.width, scene.game.config.height);
          
          // tweenPlayerTo returns a Promise that resolves when complete
          return tweenPlayerTo(scene, sprite, endPixels, { duration: 800 });
        })
      );
      
      
      // Transition to HalfCourt state
      const { safeTransition } = await import('../state/gameStateMachine.js');
      safeTransition(scene.stateMachine, States.HalfCourt, 'after quarter start inbound');
      
      appendToTextScroll(turn.text || "Inbound pass");
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
      // console.log('🏀 Continuing to next turn after BASELINE_INBOUND');
      continue;
    }

    if (turn.result_type === "DEFENSIVE_STOP") {
      // Fast break was stopped by defense - just display text and continue to next turn (HCO)
      appendToTextScroll(turn.text || "Defense stops the break!");
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

    // Handle OREB turns (putback attempts and kickouts)
    if (turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT") {
      await handleOrebTurn(scene, { playerSprites, ballSprite, turnData: turn, onUpdate });
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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

    // Opening tip at start of Q1 and OT
    if (turn.result_type === "OPENING_TIP") {
      animationDebugLog('OPENING TIP DETECTED - routing to runOpeningTipSequence:', {
        result_type: turn.result_type,
        winner: turn.winner,
        home_wins: turn.home_wins,
        turn_index: i
      });
      await new Promise(resolve => {
        runOpeningTipSequence(scene, {
          playerSprites,
          ballSprite,
          turnData: turn,
          onComplete: resolve
        });
      });
      
      // Transition to HalfCourt state after opening tip completes
      // This ensures the next turn (first possession) starts in correct state
      if (scene.stateMachine && !scene.stateMachine.is(States.HalfCourt)) {
        const { safeTransition } = await import('../state/gameStateMachine.js');
        safeTransition(scene.stateMachine, States.HalfCourt, {
          reason: 'opening_tip_complete',
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene)
        });
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
      
      // Update active player display for fast break
      const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
      const ballHandlerId = getBallHandlerIdFromTurn(turn, 0);
      const defenderId = getDefenderIdFromTurn(turn);
      if (ballHandlerId) {
        updateActivePlayers(ballHandlerId, defenderId, scene.simData?.home_team_id, playerSprites);
      }
      
      await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, turnIndex: i });
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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
    
    // Check for FCP/HCT shots - route to standard shot animation
    if (turn.fcp_shot === true || turn.hct_shot === true) {
      const pressureType = turn.fcp_shot ? 'FCP' : 'HCT';
      animationDebugLog(`${pressureType} SHOT TURN - routing to standard shot animation:`, {
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
      
      // Announce result (visual effects now handled by announcement/ballManager)
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
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
      
      // Fast break shots now use the new system (same as HCO shots)
      if (turn.fast_break === true) {
        animationDebugLog('FAST BREAK TURN DETECTED - routing to runFastBreakSequence');
        
        // Update active player display for fast break
        const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
        const ballHandlerId = getBallHandlerIdFromTurn(turn, 0);
        const defenderId = getDefenderIdFromTurn(turn);
        if (ballHandlerId) {
          updateActivePlayers(ballHandlerId, defenderId, scene.simData?.home_team_id, playerSprites);
        }
        
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
        
        // Visual effects handled by announcement system
        const defenderSprite = playerSprites[stealerId];
        // runPass reattaches the ball after the tween resolves, so only emit
        // possession change once that handoff has finished.
        if (!scene.stateMachine?.is(States.FastBreak) && defenderSprite) {
          scene.events?.emit?.('possessionChange', { offenseTeamId: defenderSprite.team_id });
        }
      }
    }

    // Show announcements for shot results and rebounds (after animation)
    announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
    
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
