import { playTurnAnimation } from "./turnAnimation.js";
// ✅ PHASE 2.6 COMPLETE: Legacy imports no longer needed (all routes through AnimationRouter)
// import { runSideInboundSetup } from "./turnAnimation.js"; // ✅ Now handled by AnimationEngine.handleSideInbound()
import { onAction } from "./onAction.js";
import { AnimationRouter } from "./AnimationRouter.js?v=clock-observe-telemetry-2";
import { runPass, REBOUND_DEBUG } from "./ballManager.js";
import animationConfig from "./animation_config.js";
// ✅ PHASE 2.6 COMPLETE: Legacy imports no longer needed (all routes through AnimationRouter)
// import runFreeThrowSequence from "./freeThrow.js"; // ✅ Now handled by AnimationEngine.handleFreeThrow()
// import runFastBreakSequence from "./fastBreak.js"; // ✅ Now handled by AnimationEngine.handleFastBreak()
// import { runOpeningTipSequence } from "./openingTip.js"; // ✅ Now handled by AnimationEngine.handleOpeningTip()
import { animateStep } from "./animateStep.js";
// ✅ PHASE 2.6 COMPLETE: Legacy imports no longer needed (all routes through AnimationRouter)
// import { handleTurnover } from "./turnoverAdapter.js"; // ✅ Now handled by AnimationEngine.handleTurnover()
import { States } from "../state/gameStateMachine.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import { getCurrentOwner, getPendingOwner } from "./BallControllerAdapter.js";
import { enforceUnitCompletionContract } from "./unitCompletionContract.js";
// ✅ PHASE 2.6 COMPLETE: These are now handled by AnimationRouter via turnPreparation.js
// import { updatePlaycallDisplay } from "../utils/playcallDisplay.js"; // ✅ Used by prepareTurnForAnimation (called by AnimationRouter)
// import { updateStrategyBars } from "../utils/strategyBars.js"; // ✅ Used by prepareTurnForAnimation (called by AnimationRouter)
// import { updatePlaycallCenter } from "../ui/playcallCenter.js"; // ✅ Used by prepareTurnForAnimation (called by AnimationRouter)
import { announceFromTurnData } from "../utils/announcements.js";
import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import { getSceneStepLogger } from "./debugStepLogger.js";
import {
  createFbTelemetryDebugListener,
  flushFbTelemetryDebugSummary,
} from "../utils/fbTelemetryDebug.js";

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

function resolveOrebContractMode() {
  const raw = String(
    (typeof window !== "undefined" ? window.UESS_OREB_CONTRACT_MODE : null) ?? "observe"
  )
    .trim()
    .toLowerCase();
  if (raw === "off" || raw === "observe" || raw === "warn" || raw === "throw") return raw;
  return "observe";
}

function getOrebBudgetGameSeconds(kind = "decision") {
  const scope = typeof window !== "undefined" ? window : globalThis;
  const generic =
    kind === "decision"
      ? Number(scope?.UESS_OREB_DECISION_MAX_GAME_SECONDS)
      : Number(scope?.UESS_OREB_ACTION_MAX_GAME_SECONDS);
  if (Number.isFinite(generic) && generic > 0) return generic;
  return kind === "decision" ? 2 : 3;
}

function emitOrebContractTelemetry(scene, turnData, event, payload = {}) {
  scene?.events?.emit?.("animTelemetry", {
    event,
    branchKind: "oreb_phase_contract",
    turnId: turnData?.turn_count ?? turnData?.id ?? null,
    turnIndex: scene?.currentTurn ?? null,
    resultType: turnData?.result_type ?? null,
    gameClock: scene?.simData?.clock ?? null,
    quarter: turnData?.quarter ?? scene?.quarter ?? null,
    timestampMs: Date.now(),
    ...payload,
  });
}

function enforceOrebUnitContract({
  scene,
  turnData,
  unitId,
  advanceTrigger,
  visualSettleTrigger,
  authorizingEventReceived,
  visualSettled,
  unitStartMs,
  maxWaitGameSeconds,
  context = {},
}) {
  const mode = resolveOrebContractMode();
  if (mode === "off") return;
  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const elapsedMs = Math.max(0, Date.now() - Number(unitStartMs || Date.now()));
  const elapsedGameSeconds = elapsedMs / clockSecondMs;
  const overrun =
    Number.isFinite(maxWaitGameSeconds) &&
    maxWaitGameSeconds > 0 &&
    elapsedGameSeconds > maxWaitGameSeconds;
  const contractContext = {
    elapsedMs,
    elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
    maxWaitGameSeconds,
    overrun,
    ...context,
  };
  if (overrun) {
    emitOrebContractTelemetry(scene, turnData, "oreb_phase_clock_overrun", {
      unitId,
      ...contractContext,
    });
  }
  const logger =
    mode === "observe"
      ? {
          warn: () => {},
        }
      : console;
  enforceUnitCompletionContract({
    contract: {
      unit_id: unitId,
      execution_mode: "dynamic_event",
      advance_trigger: advanceTrigger,
      visual_settle_trigger: visualSettleTrigger,
      failure_policy: mode === "throw" ? "throw" : "warn",
    },
    observed: {
      authorizingEventReceived: authorizingEventReceived === true,
      visualSettled: visualSettled === true && !overrun,
    },
    context: contractContext,
    emitTelemetry: (event, payload = {}) =>
      emitOrebContractTelemetry(scene, turnData, event, payload),
    logger,
  });
  if (mode === "throw" && overrun) {
    throw new Error(
      `[OREB contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
    );
  }
}

function getOrebUndeclaredHoldBudgetMs() {
  const scope = typeof window !== "undefined" ? window : globalThis;
  const raw = Number(scope?.UESS_OREB_UNDECLARED_HOLD_BUDGET_MS);
  if (Number.isFinite(raw) && raw > 0) return raw;
  return 900;
}

function createOrebIdleWatchdog(scene, turnData, unitId, options = {}) {
  const allowedInterrupts = Array.isArray(options.allowedInterrupts)
    ? options.allowedInterrupts
    : [];
  const stallBudgetMs =
    Number(options.stallBudgetMs) > 0
      ? Number(options.stallBudgetMs)
      : getOrebUndeclaredHoldBudgetMs();
  const activeInterrupts = new Set();
  let lastProgressAtMs = Date.now();
  let violationEmitted = false;
  const markProgress = () => {
    lastProgressAtMs = Date.now();
  };
  const setInterrupt = (interruptName, active) => {
    const key = String(interruptName || "").trim();
    if (!key) return;
    if (active) activeInterrupts.add(key);
    else activeInterrupts.delete(key);
    markProgress();
  };
  const onUpdate = () => {
    if (violationEmitted || activeInterrupts.size > 0) return;
    const idleMs = Date.now() - lastProgressAtMs;
    if (idleMs <= stallBudgetMs) return;
    violationEmitted = true;
    emitOrebContractTelemetry(scene, turnData, "oreb_undeclared_hold_violation", {
      unitId,
      violationType: "idle_without_declared_interrupt",
      idleMs: Number(idleMs.toFixed(1)),
      stallBudgetMs,
      allowedInterrupts,
      activeInterrupts: Array.from(activeInterrupts),
    });
  };
  scene?.events?.on?.("update", onUpdate);
  return {
    markProgress,
    setInterrupt,
    stop: () => {
      scene?.events?.off?.("update", onUpdate);
    },
  };
}

// PossessionRunner removed - using standard animation path only

/**
 * Handle offensive rebound turns (putbacks and kickouts)
 * ✅ PHASE 2.6: Exported for use by AnimationEngine handler
 */
export async function handleOrebTurn(scene, { playerSprites, ballSprite, turnData, onUpdate }) {
  const { shootBall } = await import('./ballManager.js');
  const { animateKickoutReset } = await import('./ballManager.js');
  const { runInboundSetup } = await import('./turnAnimation.js');
  
  appendToTextScroll(turnData.text);
  
  // ✅ FIX: Use shooter/ball_handler for putback shooter (like HCO shots use shooter_id)
  // Don't use rebounderId - it gets overwritten with the NEXT rebounder when rebound data is added
  // turnData.shooter and turnData.ball_handler are set by backend to the O Rebounder (putback shooter)
  // turnData.rebounderId is initially the putback shooter but gets overwritten with next rebounder
  const rebounderId = turnData.shooter || turnData.ball_handler?.player_id || turnData.rebounderId;
  const rebounderSprite = playerSprites[rebounderId];
  
  
  if (!rebounderSprite) return;
  const orebIdleWatchdog = createOrebIdleWatchdog(
    scene,
    turnData,
    "oreb.out.to_*",
    {
      allowedInterrupts: [
        "declared_hold",
        "shot_release_or_flight",
        "rebound_secure",
        "pass_in_flight",
        "route_transition",
      ],
    }
  );

  try {
    const leadInStartMs = Date.now();
    enforceOrebUnitContract({
      scene,
      turnData,
      unitId: "oreb.lead_in.from_miss",
      advanceTrigger: "OREB committed",
      visualSettleTrigger: "rebound secure + attach settled",
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: leadInStartMs,
      maxWaitGameSeconds: getOrebBudgetGameSeconds("decision"),
      context: {
        resultType: turnData?.result_type ?? null,
        rebounderId,
      },
    });
  
  if (turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS") {
    // Animate putback attempt using shootBall
    const result = turnData.result_type === "PUTBACK_MAKE" ? "MAKE" : "MISS";
    
    // CRITICAL: Clear scene.rebounderId BEFORE attaching ball for putback
    // This prevents premature attachment to the next rebounder
    if (scene.rebounderId) {
      scene.rebounderId = null;
    }
    
    // Start putback sequence
    
    // ✅ PHASE 2.5: Use BallController lifecycle methods for putback
    // ✅ PHASE 2.9: Add defensive state synchronization for putbacks
    const { getBallController, synchronizeBallState } = await import('./BallControllerAdapter.js');
    const ballController = getBallController();
    
    // ✅ DEFENSIVE: Comprehensive state clearing before putback
    // Clear any lingering state from previous shot/rebound
    synchronizeBallState(scene, {
      clearShotState: true,
      clearPutbackState: true,
      allowAttachment: false // Don't allow attachment yet - we'll position ball manually
    });
    
    // ✅ PHASE 4: Removed old _putbackInProgress flag - BallController manages state via lifecycle methods
    
    // Use lifecycle method to track putback start
    if (ballController) {
      ballController.onPutbackStart({ shooterId: rebounderId });
    }
    
    // ✅ DEFENSIVE: Ensure ball is NOT attached before positioning
    // This prevents the flash where ball briefly attaches to rebounder
    // Check both ballController (from adapter) and scene.ballController for redundancy
    if (ballController && ballController.isAttached) {
      ballController.detachFromPlayer('putback_prep', { reason: 'prevent_attachment_flash' });
    }
    // Also check scene.ballController as fallback (some code might use this directly)
    if (scene.ballController && scene.ballController.isAttached) {
      scene.ballController.detachFromPlayer('putback_prep');
    }
    
    // Also clear old system ball state
    if (scene.currentBallOwnerRef) {
      scene.currentBallOwnerRef.value = null;
    }
    // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
    
    // CRITICAL: Position ball at rebounder's location WITHOUT attaching
    // shootBall() will handle detachment and animation, so we just need to position the ball
    // This prevents the brief attachment flash before the shot animation
    // Get rebounder's current position for shot start
    const fromCoords = {
      x: (rebounderSprite.x / scene.game.config.width) * 100,
      y: 50 - (rebounderSprite.y / scene.game.config.height) * 50
    };
    
    // Position ball sprite at rebounder's location (but don't attach - shootBall will handle it)
    if (ballSprite) {
      console.log('🟡🟡🟡 [BLOCK/OREB BALL] handleOrebTurn setting ball to rebounder position', {
        rebounderId,
        rebounder_x: rebounderSprite.x,
        rebounder_y: rebounderSprite.y,
      });
      ballSprite.setPosition(rebounderSprite.x, rebounderSprite.y);
      ballSprite.setVisible(true);
    }

    // OREB hold: rebounder holds until 1 game s remains, then acts (1 game s = 350ms real)
    const holdStartMs = Date.now();
    const orebHoldSeconds = Number(turnData.oreb_hold_seconds);
    const hasHoldWindow = Number.isFinite(orebHoldSeconds) && orebHoldSeconds > 0;
    if (hasHoldWindow && scene.time) {
      const holdMs = orebHoldSeconds * 350;
      const holdStartedAt = Date.now();
      orebIdleWatchdog.setInterrupt("declared_hold", true);
      await new Promise((resolve) => scene.time.delayedCall(holdMs, resolve));
      orebIdleWatchdog.setInterrupt("declared_hold", false);
      const holdElapsedMs = Date.now() - holdStartedAt;
      if (holdElapsedMs > holdMs + 250) {
        emitOrebContractTelemetry(scene, turnData, "oreb_declared_hold_overrun", {
          unitId: "oreb.phase.hold",
          holdBudgetMs: Math.round(holdMs),
          holdElapsedMs: Math.round(holdElapsedMs),
        });
      }
    }
    orebIdleWatchdog.markProgress();
    enforceOrebUnitContract({
      scene,
      turnData,
      unitId: "oreb.phase.hold",
      advanceTrigger: "hold boundary reached",
      visualSettleTrigger: "no active attach/tween conflicts",
      authorizingEventReceived: true,
      visualSettled: scene?.passInFlight !== true,
      unitStartMs: holdStartMs,
      maxWaitGameSeconds: getOrebBudgetGameSeconds("decision"),
      context: {
        holdSeconds: hasHoldWindow ? orebHoldSeconds : 0,
        holdApplied: hasHoldWindow && !!scene?.time,
      },
    });

    orebIdleWatchdog.setInterrupt("shot_release_or_flight", true);
    const shotResult = await shootBall({
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
    orebIdleWatchdog.setInterrupt("shot_release_or_flight", false);
    orebIdleWatchdog.markProgress();
    
    // CRITICAL: Keep _putbackInProgress true until AFTER the rebound animation
    // This prevents runDefensiveReboundSetup from attaching the ball during the putback shot animation
    // We'll clear it right before calling runDefensiveReboundSetup (if DREB) or after animateRebound (if OREB)
    
    // Handle putback make - run inbound setup
    if (turnData.result_type === "PUTBACK_MAKE") {
      
      // ✅ FIX: Don't call runInboundSetup() here if next is BASELINE_INBOUND or FREE_THROW
      // BASELINE_INBOUND: next turn runs handleBaselineInbound() (avoids double BIP).
      // FREE_THROW: shooting foul / and-one after make — same as fastBreak.js; FT turn handles transition (no BIP between make and FT).
      if (turnData.next_play_type === "BASELINE_INBOUND" || turnData.next_play_type === "FREE_THROW") {
        // ✅ FIX: Call onPutbackEnd() to clear putback state (still needed even if skipping inbound setup)
        const { getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        if (ballController) {
          ballController.onPutbackEnd();
        }
        
        // ✅ REMOVED: runInboundSetup() — dedicated next turn handles inbound or free throws
        return;
      }
      
      const shooterTeamId = rebounderSprite.team_id;
      const homeTeamId = scene.simData?.home_team_id;
      const awayTeamId = scene.simData?.away_team_id;
      const shooterTeamIsHome = String(shooterTeamId) === String(homeTeamId);
      const newOffenseSide = shooterTeamIsHome ? "away" : "home";
      
      // ✅ FIX: Call onPutbackEnd() before inbound setup (state clearing pattern)
      // This ensures putback state is cleared before transitioning to inbound pass
      const { getBallController } = await import('./BallControllerAdapter.js');
      const ballController = getBallController();
      if (ballController) {
        ballController.onPutbackEnd();
      }
      
      // Check for defensive pressure
      const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
      const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
      
      orebIdleWatchdog.setInterrupt("route_transition", true);
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
      orebIdleWatchdog.setInterrupt("route_transition", false);
      orebIdleWatchdog.markProgress();
    }
    // Handle putback miss with rebound
    else if (turnData.rebound_type) {
      const { animateRebound } = await import('./ballManager.js');
      
      // CRITICAL: shootBall already handled the bounce for MISS shots
      // The ball is already at the bounce spot from shootBall's bounceFromRim
      // Use the bounce result from shootBall (which has the correct basket and position)
      // Do NOT use backend's ballSpot (which is rim coordinates) - that causes ball to snap to rim
      // Do NOT call bounceFromRim again - it causes double bounce and wrong basket issues
      const reboundBallSpot = shotResult?.grid || turnData.ballSpot || { x: 50, y: 25 };
      
      // CRITICAL: Clear _shotInProgress BEFORE calling animateRebound
      // ✅ PHASE 4: Removed old _shotInProgress flag - BallController manages state via lifecycle methods
      // The shot animation is complete, BallController state already cleared by onShotEnd()
      
      // CRITICAL: turnData.rebounderId contains the NEXT rebounder (the one who will get this rebound)
      // This is NOT the same as the putback shooter (rebounderId variable above)
      const nextRebounderId = turnData.rebounderId;
      
      orebIdleWatchdog.setInterrupt("rebound_secure", true);
      await animateRebound({
        scene,
        ballSprite,
        playerSprites,
        animations: [],
        rebounderId: nextRebounderId, // This is the NEXT rebounder who will get the ball
        ballSpot: reboundBallSpot,
        shooterId: rebounderId, // This is the putback shooter
        preserveBallPosition: true, // Ball is already at bounce spot from shootBall - don't reposition
        turnData: turnData // Pass turnData so get-back players can be excluded
      });
      orebIdleWatchdog.setInterrupt("rebound_secure", false);
      orebIdleWatchdog.markProgress();

      enforceOrebUnitContract({
        scene,
        turnData,
        unitId: "oreb.phase.putback_rebound_resolution",
        advanceTrigger: "rebound outcome committed",
        visualSettleTrigger: "rebound settle complete",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: Date.now(),
        maxWaitGameSeconds: getOrebBudgetGameSeconds("action"),
        context: {
          reboundType: turnData?.rebound_type ?? null,
          rebounderId: turnData?.rebounderId ?? null,
        },
      });
      
      
      // If DREB, set up next play (outlet pass for HCO only)
      // For FAST_BREAK, the outlet pass is handled in the fast break sequence itself
      // ✅ Force Foul after DREB: skip outlet — foul turn will animate defender→rebounder and "Quick Foul"
      if (turnData.rebound_type === "DREB" && turnData.next_play_type !== "FAST_BREAK" && !turnData.force_foul_after_dreb) {
        // For putback misses leading to DREB, find the original MISS turn that has offense_getback
        // This might be a previous turn (the original shot attempt) or the putback turn itself
        let missTurn = null;
        const currentIndex = scene.currentTurn || 0;
        // Check if previous turn is a MISS (original shot attempt)
        const previousTurn = scene.simData?.turns?.[currentIndex - 1];
        if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") {
          missTurn = previousTurn;
        } else {
          // Otherwise, check current turn (might be a MISS/BLOCK with putback)
          missTurn = scene.simData?.turns?.[currentIndex];
        }
        
        // ✅ DEBUG: Track DREB after putback miss
        // Putback miss => DREB
        
        // ✅ PHASE 2.5: Use BallController lifecycle method for putback end
        const { getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        if (ballController) {
          ballController.onPutbackEnd();
        }
        
        // ✅ TRANSITION PERIOD: Keep old flag for backward compatibility (will be removed in Phase 4)
        // ✅ PHASE 4: Removed old _putbackInProgress flag - BallController manages state via lifecycle methods
        // The putback shot animation is complete, BallController state already cleared by onPutbackEnd()
        
        const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
        orebIdleWatchdog.setInterrupt("route_transition", true);
        await runDefensiveReboundSetup({
          scene,
          ballSprite,
          playerSprites,
          rebounderId: turnData.rebounderId,
          nextPlayType: turnData.next_play_type || "HCO",
          turnData: missTurn, // get-back source
          authorityTurnData: turnData, // strict outlet contract source
        });
        orebIdleWatchdog.setInterrupt("route_transition", false);
        orebIdleWatchdog.markProgress();
      }
      // If another OREB, it will be handled by the next OREB turn
    }
    const outRoute = String(turnData?.next_play_type || "").toUpperCase();
    enforceOrebUnitContract({
      scene,
      turnData,
      unitId: "oreb.out.to_*",
      advanceTrigger: "route committed",
      visualSettleTrigger: "OREB final settle complete",
      authorizingEventReceived: outRoute.length > 0,
      visualSettled: true,
      unitStartMs: Date.now(),
      maxWaitGameSeconds: getOrebBudgetGameSeconds("action"),
      context: {
        route: outRoute || null,
        sourceResultType: turnData?.result_type ?? null,
      },
    });
  } else if (turnData.result_type === "OREB_KICKOUT") {
    // Handle kickout with outlet animation step
    orebIdleWatchdog.setInterrupt("route_transition", true);
    await handleOrebKickout(scene, {
      playerSprites,
      ballSprite,
      rebounderId,
      turnData
    });
    orebIdleWatchdog.setInterrupt("route_transition", false);
    orebIdleWatchdog.markProgress();
    const outRoute = String(turnData?.next_play_type || "").toUpperCase();
    enforceOrebUnitContract({
      scene,
      turnData,
      unitId: "oreb.out.to_*",
      advanceTrigger: "route committed",
      visualSettleTrigger: "OREB final settle complete",
      authorizingEventReceived: outRoute.length > 0,
      visualSettled: true,
      unitStartMs: Date.now(),
      maxWaitGameSeconds: getOrebBudgetGameSeconds("action"),
      context: {
        route: outRoute || null,
        sourceResultType: turnData?.result_type ?? null,
      },
    });
  }
  } finally {
    orebIdleWatchdog.stop();
  }
}

/**
 * Handle OREB kickout with outlet animation step
 * Similar to DREB outlet setup, but for offensive rebounds
 * 
 * Flow: Rebound animation → Outlet positioning → Pass to PG → HCO
 */
async function handleOrebKickout(scene, { playerSprites, ballSprite, rebounderId, turnData }) {
  const { animateKickoutReset } = await import('./ballManager.js');
  const { runOffensiveReboundKickoutSetup } = await import('./turnAnimation.js');
  
  const pgId = turnData.pgId;
  if (!pgId) {
    console.warn('handleOrebKickout: No PG ID provided', turnData);
    return;
  }

  // OREB hold: rebounder holds until 1 game s remains, then acts (1 game s = 350ms real)
  const holdStartMs = Date.now();
  const orebHoldSeconds = Number(turnData.oreb_hold_seconds);
  const hasHoldWindow = Number.isFinite(orebHoldSeconds) && orebHoldSeconds > 0;
  if (hasHoldWindow && scene.time) {
    const holdMs = orebHoldSeconds * 350;
    await new Promise((resolve) => scene.time.delayedCall(holdMs, resolve));
  }
  enforceOrebUnitContract({
    scene,
    turnData,
    unitId: "oreb.phase.hold",
    advanceTrigger: "hold boundary reached",
    visualSettleTrigger: "no active attach/tween conflicts",
    authorizingEventReceived: true,
    visualSettled: scene?.passInFlight !== true,
    unitStartMs: holdStartMs,
    maxWaitGameSeconds: getOrebBudgetGameSeconds("decision"),
    context: {
      holdSeconds: hasHoldWindow ? orebHoldSeconds : 0,
      holdApplied: hasHoldWindow && !!scene?.time,
      branch: "oreb_kickout",
    },
  });

  // Step 1: Run outlet positioning animation (PG and rebounder move to outlet spots)
  await runOffensiveReboundKickoutSetup({
    scene,
    ballSprite,
    playerSprites,
    rebounderId,
    pgId,
    turnData  // ✅ Pass turnData to determine offense team for coordinate flipping
  });

  // Step 2: Execute kickout pass to PG
  await animateKickoutReset(
    scene,
    ballSprite,
    rebounderId,
    pgId,
    turnData.pass || {},
    500
  );
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

// PossessionRunner functions removed - using standard animation path only

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
  // Removed verbose startup log
  
  // console.log('🎬 animateGameTurns: Starting animation system');
  const turns = simData.turns || [];
  if (scene) scene.simData = simData;
  
  // ✅ INITIALIZE FCP/HCT STATE TRACKING (SS&S Pattern: Scene-level state)
  // This provides a single source of truth for pressure state, matching BallController pattern
  if (!scene.currentPressureType) {
    scene.currentPressureType = null; // "FCP" | "HCT" | null
    scene.pressureSequenceActive = false; // Track if we're in a pressure sequence
  }
  annotateFreeThrowTurns(turns);
  const allPlayers = simData.players || [];
  const debugEnabled = isAnimationDebugEnabled();
  const stepLogger = debugEnabled ? getSceneStepLogger(scene) : null;
  
  const logVerbose = (...args) => {
    if (isAnimationDebugEnabled()) {
      animationDebugLog(...args);
      return;
    }
    if (DEBUG_FLOW) {
      console.log(...args);
    }
  };

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

  // ✅ PHASE 2.4: Initialize AnimationRouter for FCP/HCT foul turns (and future migrations)
  const animationRouter = new AnimationRouter(
    scene,
    playerSprites,
    ballSprite,
    onUpdate,
    onAction,
    updateDebugScore // Pass updateDebugScore function
  );

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
  const handleFbTelemetry = createFbTelemetryDebugListener(scene);
  if (scene?.__fbTelemetryDebugHandler) {
    scene.events?.off?.("animTelemetry", scene.__fbTelemetryDebugHandler);
    scene.__fbTelemetryDebugHandler = null;
  }
  if (handleFbTelemetry) {
    scene.events?.on?.("animTelemetry", handleFbTelemetry);
    scene.__fbTelemetryDebugHandler = handleFbTelemetry;
  }

  // console.log('🎬 animateGameTurns: Starting turn processing loop', { totalTurns: turns.length });
  
  // Removed verbose loop start log
  // ✅ Force Foul: Expose current batch so router can pass nextTurn to BIP/SIP (same-turn defender move)
  scene._currentTurnBatch = turns;

  try {
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
    
    // ✅ DEBUG: Log state at start of each turn (to trace state persistence)
    if (i > 0 && (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK")) {
      console.log('🔍 [TURN START - STATE CHECK]', {
        turn_index: i,
        result_type: turn.result_type,
        currentPressureType: scene.currentPressureType,
        pressureSequenceActive: scene.pressureSequenceActive,
        previous_turn_index: i - 1,
        previous_turn_result_type: turns[i - 1]?.result_type
      });
    }
    if (scene.skipToEnd) break;
    
    // Removed verbose turn processing log
    
    // Keep turn index available for any embedded paths that read scene.currentTurn early.
    scene.currentTurn = i;
    turn.index = i;
    const possessionId =
      turn.possession_id ?? turn.possessionId ?? turn.possessionID ?? null;
    
    const animations = turn.animations || [];
    const shouldLogLegacySteps =
      debugEnabled && stepLogger;

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
      // ✅ PHASE 2.6: Route FREE_THROW through AnimationRouter
      // Active player display, free throw sequence, and text scroll are handled by handler
      // AnimationRouter handles pre/post setup (prepareTurnForAnimation, finalizeTurnAfterAnimation)
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: onUpdate and updateDebugScore handled by AnimationRouter
      // Note: onUpdate is already called inside runFreeThrowSequence for each FT attempt
      continue;
    }

    // ✅ CHARGE: Route through AnimationRouter so finalizeTurnAfterAnimation announces "Charge!" (not "Offensive Foul!")
    if (turn.result_type === "CHARGE") {
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
    }

    if (turn.result_type === "FOUL") {
      // ✅ DEBUG: Log FOUL routing decision
      console.log('🔍 [FOUL ROUTING]', {
        turn_index: i,
        has_animations: !!turn.animations?.length,
        animation_count: turn.animations?.length || 0,
        fcp_foul: turn.fcp_foul,
        hct_foul: turn.hct_foul,
        foul_team: turn.foul_team,
        pressureSequenceActive: scene.pressureSequenceActive,
        will_route_to_router: !!(turn.animations && turn.animations.length > 0)
      });
      
      // ✅ FIX: Route ALL fouls with animations through AnimationRouter
      // This includes FCP/HCT fouls (fcp_foul/hct_foul flags) and regular HCO fouls (when we add them)
      if (turn.animations && turn.animations.length > 0) {
        // Foul with animations - route through AnimationRouter
        turn.index = i;
        await animationRouter.processTurn(turn);
        continue;
      } else {
        // Non-animated foul - just do announcements and updates
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
    }
    
    if (turn.result_type === "DEAD BALL") {
      // ✅ DEBUG: Log DEAD BALL routing decision
      console.log('🔍 [DEAD_BALL ROUTING]', {
        turn_index: i,
        has_animations: !!turn.animations?.length,
        animation_count: turn.animations?.length || 0,
        pressureSequenceActive: scene.pressureSequenceActive,
        possession_flips: turn.possession_flips,
        possession_team_id: turn.possession_team_id,
        will_route_to_router: !!(turn.animations && turn.animations.length > 0)
      });
      
      // ✅ FIX: Route ALL dead ball with animations through AnimationRouter
      // This includes FCP/HCT dead ball turnovers and regular HCO dead ball (when we add them)
      if (turn.animations && turn.animations.length > 0) {
        // Dead ball with animations - route through AnimationRouter
        turn.index = i;
        await animationRouter.processTurn(turn);
        continue;
      } else {
        // Dead ball without animations - just do announcements and updates
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
    }

    if (turn.result_type === "SIDE_INBOUND") {
      // ✅ PHASE 2.6: Route SIDE_INBOUND through AnimationRouter (always run full SIP)
      // Fix: Run SIP even when in FastBreak (e.g. BATCH [CHARGE, SIDE_INBOUND] or [FOUL, SIDE_INBOUND])
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
    }

    if (turn.result_type === "BASELINE_INBOUND") {
      // ✅ PHASE 2.6: Route BASELINE_INBOUND through AnimationRouter
      // FCP/HCT state tracking, player animations, and state transitions are handled by handler
      // AnimationRouter handles pre/post setup (prepareTurnForAnimation, finalizeTurnAfterAnimation)
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: onUpdate and updateDebugScore handled by AnimationRouter
      continue;
    }

    // ✅ PHASE 2.6: Handle DEFENSIVE_STOP - route through AnimationRouter
    if (turn.result_type === "DEFENSIVE_STOP") {
      // Fast Break defensive stop routes to handleFastBreak(), non-Fast Break uses handleDefensiveStop()
      // Text scroll, announcements, and score updates are handled by handler
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: onUpdate and updateDebugScore handled by AnimationRouter
      continue;
    }

    // ✅ Discrete defensive rebound row (MISS → DREB → HCO): backend emits `result_type === "DREB"` as its
    // own turn with `animation_steps`. Without this branch the loop falls through and never calls
    // AnimationEngine — so `playTurn` + `_maybeRunDiscreteDrebOutletLeadIn` never run (outlet skipped).
    if (turn.result_type === "DREB") {
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
    }

    // ✅ TIMEOUT: Handle TIMEOUT turns - route through AnimationRouter
    if (turn.result_type === "TIMEOUT") {
      turn.index = i;
      await animationRouter.processTurn(turn);
      console.log('⏸️ TIMEOUT: Stopping animation loop - user will navigate to lineup screen');
      break; // Exit the loop - don't process any more turns
    }

    // ✅ PHASE 2.6: Handle OREB turns (putback attempts and kickouts) - route through AnimationRouter
    // ✅ DEBUG: Track putback/OREB path to identify skipped turns
    if (turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT") {
      const previousTurn = i > 0 ? turns[i - 1] : null;
      const previousTurnResult = previousTurn?.result_type;
      const wasMISS = previousTurnResult === "MISS";
      const wasOREB = previousTurnResult === "OREB" || previousTurnResult === "OREB_KICKOUT";
      const twoTurnsAgo = i > 1 ? turns[i - 2] : null;
      
      const rebounderName = turn.rebounderId ? (playerSprites[turn.rebounderId]?.name || 'unknown') : null;
      const previousShooterId = previousTurn?.shooter_id || null;
      const previousShooterName = previousShooterId ? (playerSprites[previousShooterId]?.name || 'unknown') : null;
      
      // Process putback/OREB turn
      const { getBallController } = await import('./BallControllerAdapter.js');
      const ballController = getBallController();
      
      // ✅ PHASE 2.6: Route through AnimationRouter
      // handleOrebTurn, announcements, and score updates are handled by handler
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: Announcements, onUpdate, and updateDebugScore handled by AnimationRouter
      continue;
    }

    // ✅ COMMENTED OUT: FCP/HCT now routes through AnimationRouter (same as HCO)
    // FCP/HCT skeletons are different data (press break sequences), but use the same animation system
    // They now route to SHOT_ATTEMPT handler (for MAKE/MISS) or their respective handlers (FOUL, TURNOVER, etc.)
    // This block is kept for reference in case we need to revert
    /*
    // ✅ SS&S PATTERN: Simple state-based FCP/HCT detection (replaces complex flag inheritance)
    // Use scene state as single source of truth - matches BallController pattern
    const previousTurn = i > 0 ? turns[i - 1] : null;
    
    // ✅ SS&S: Only detect FCP/HCT if turn has explicit defensive setup flags or FCP/HCT outcome flags
    // The source of truth is the turn data (next_defensive_setup from backend), not scene state
    // Backend only sets next_defensive_setup to "FCP" or "HCT" if the defensive team has those settings enabled
    // 
    // ✅ CRITICAL FIX: next_defensive_setup indicates the NEXT turn's setup, not the current turn's
    // - For BASELINE_INBOUND: Use next_defensive_setup to detect FCP/HCT setup turns (result_type === "BASELINE_INBOUND")
    // - For MAKE/MISS: NEVER use next_defensive_setup (it's for the NEXT turn) - only use fcp_shot/hct_shot flags
    // - For other outcomes: Use fcp_foul/hct_foul flags or next_defensive_setup if it's a setup turn
    const isBaselineInbound = turn.result_type === "BASELINE_INBOUND"; // ✅ FIX: Check result_type, not next_play_type
    const hasExplicitFCPHCTFlags = turn.fcp_shot === true || turn.hct_shot === true ||
                                   turn.fcp_foul === true || turn.hct_foul === true ||
                                   (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));
    
    // For HCO/TURNOVER/STEAL/DEAD BALL/FOUL outcomes, only detect as FCP/HCT if we're in an active pressure sequence
    // (these are press break outcomes, not regular HCO shots)
    // ✅ FIX: Include STEAL, DEAD BALL, and offensive FOUL in press break outcomes - FCP/HCT turns should show skeleton animation
    const isPressBreakOutcome = (turn.result_type === "HCO" || turn.result_type === "TURNOVER" || 
                                 turn.result_type === "STEAL" || turn.result_type === "DEAD BALL" ||
                                 (turn.result_type === "FOUL" && !turn.fcp_foul && !turn.hct_foul)) && 
                                scene.pressureSequenceActive;
    
    // ✅ CRITICAL FIX: Only detect shot attempts as FCP/HCT if they have explicit flags
    // Since SHOT was removed from FCP/HCT outcomes in the backend, regular shots should NOT
    // be detected as FCP/HCT just because pressureSequenceActive is true
    // Only detect as FCP/HCT if: explicit flags OR press break outcome (HCO/TURNOVER)
    const isPressBreakShotAttempt = scene.pressureSequenceActive && 
                                     (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") &&
                                     (turn.fcp_shot === true || turn.hct_shot === true); // Require explicit flags
    
    const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;
    
    // ✅ FIX: Skip FCP/HCT check if this is a FOUL that was already handled by AnimationRouter
    // FCP/HCT fouls (both Full Court Press and Half Court Trap) with animations are routed through 
    // AnimationRouter (line 586), which calls playTurnAnimation. We don't want to route them again 
    // through the FCP/HCT check below, which would cause duplicate skeleton animations.
    const isFCPHCTFoulAlreadyHandled = turn.result_type === "FOUL" && 
                                        (turn.fcp_foul === true || turn.hct_foul === true) && 
                                        turn.animations && turn.animations.length > 0;
    
    // ✅ FIX: Skip FCP/HCT check for MAKE/MISS turns that don't have explicit fcp_shot/hct_shot flags
    // These should be routed as regular HCO shots, not FCP/HCT shots. The pressureSequenceActive state
    // is for tracking the sequence, not for routing individual shot attempts.
    const isMakeMissWithoutExplicitFlags = (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") &&
                                            !turn.fcp_shot && !turn.hct_shot;
    
    if (isFCPHCT && !isFCPHCTFoulAlreadyHandled && !isMakeMissWithoutExplicitFlags) {
      // ✅ SS&S: Use turn.next_defensive_setup as primary source (calculated by backend from defensive team's strategy settings)
      // Fallback to scene state (set from previous turn's next_defensive_setup) for subsequent turns in sequence
      // Final fallback to turn flags if neither is available
      const pressureType = turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT" 
                           ? turn.next_defensive_setup  // Backend calculation (source of truth)
                           : scene.currentPressureType ||  // Scene state (from previous turn)
                           (turn.fcp_shot || turn.fcp_foul ? 'FCP' : 
                            turn.hct_shot || turn.hct_foul ? 'HCT' : null);
      
      // ✅ SS&S: Simple state-based shot attempt detection
      // Since SHOT was removed from FCP/HCT outcomes in the backend, only detect shot attempts
      // as FCP/HCT if they have explicit fcp_shot/hct_shot flags
      // Regular shots during an active pressure sequence should NOT be detected as FCP/HCT
      const isFCPHCTShotAttempt = (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") &&
                                   (turn.fcp_shot === true || turn.hct_shot === true);
      
      
      // ✅ CRITICAL FIX: Route ALL FCP/HCT turns (setup AND shot attempts) through playTurnAnimation
      // playTurnAnimation has runSetupTween() which moves players to step 0 before skeleton animation
      // This is why setup turns work but shot attempts fail (they were routing to ShotAnimationSystem)
      // Both setup turns and shot attempts need the same setup tween logic
      if (isFCPHCTShotAttempt) {
        
        // Route to playTurnAnimation (same as setup turns) - it handles shots via shootBall()
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
        
        // Call the same functions that OREB calls after playTurnAnimation completes
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
      } else {
        // FCP/HCT setup turns (FOUL, HCO, etc.) route through playTurnAnimation
        animationDebugLog(`${pressureType} SETUP TURN - routing to playTurnAnimation:`, {
          result_type: turn.result_type,
          turn_index: i,
          fcp_shot: turn.fcp_shot,
          hct_shot: turn.hct_shot,
          next_defensive_setup: turn.next_defensive_setup
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
      }
      
      const nextTurn = i + 1 < turns.length ? turns[i + 1] : null;
      
      // ✅ FIX: Only clear pressure state when next turn doesn't have FCP/HCT flags
      // Don't clear on current turn's result_type === "HCO" - that's just the outcome, not the end of sequence
      // The sequence ends when the NEXT turn doesn't have FCP/HCT flags
      const nextTurnIsFCPHCT = nextTurn && (
        nextTurn.fcp_shot === true || nextTurn.hct_shot === true ||
        nextTurn.fcp_foul === true || nextTurn.hct_foul === true ||
        nextTurn.next_defensive_setup === "FCP" || nextTurn.next_defensive_setup === "HCT"
      );
      
      // ✅ SS&S: Clear pressure state when sequence completes
      // Clear state when: shot attempt completes (and next turn isn't FCP/HCT), foul occurs, turnover occurs, OR transition to HCO (next turn isn't FCP/HCT)
      // ✅ CRITICAL FIX: Don't clear state on MADE/MISS if turn has next_defensive_setup === "FCP"/"HCT"
      // This means the made shot is setting up the next FCP/HCT turn (via runInboundSetup), so keep state active
      const isSettingUpNextFCPHCT = (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") &&
                                     (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT");
      const shouldClearPressureState = 
        ((turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") && !nextTurnIsFCPHCT && !isSettingUpNextFCPHCT) || // Shot attempt completed, but next turn isn't FCP/HCT AND not setting up next FCP/HCT
        (turn.result_type === "HCO" && !nextTurnIsFCPHCT) || // Pressure broken, transition to HCO (next turn isn't FCP/HCT)
        turn.fcp_foul === true || turn.hct_foul === true || // Foul occurred
        turn.result_type === "TURNOVER"; // Turnover occurred
      
      if (shouldClearPressureState && scene.pressureSequenceActive) {
        scene.currentPressureType = null;
        scene.pressureSequenceActive = false;
      }
      
      // ✅ CRITICAL FIX: Replicate OREB putback flow exactly
      // After playTurnAnimation() completes for FCP/HCT, call the same functions that OREB calls
      // This provides the natural delay that allows the tween manager to fully process all tweens
      // before the next turn starts
      announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
      if (onUpdate) {
        try {
          onUpdate(turn);
        } catch (err) {
          console.error('Scoreboard update failed:', err);
        }
      }
      updateDebugScore(turn, { turnIndex: i, possessionId });
      
      // ✅ DEBUG: Explicitly log next turn FCP/HCT status for visibility
      if (nextTurn) {
        // Debug logging can be added here if needed
      }
      
      continue;
    }
    */
    
    if (turn.result_type === "TURNOVER") {
      // ✅ PHASE 2.6: Route TURNOVER through AnimationRouter
      // ✅ DEBUG: Log TURNOVER detection to verify it's not catching FCP/HCT turns
      console.log('🔍 [TURNOVER DETECTED]', {
        turn_index: i,
        result_type: turn.result_type,
        fcp_shot: turn.fcp_shot,
        hct_shot: turn.hct_shot,
        next_defensive_setup: turn.next_defensive_setup,
        isFCPHCT: false, // Should be false since we checked above
        willRouteToRouter: true
      });
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: announceFromTurnData, onUpdate, and updateDebugScore are handled by AnimationRouter
      continue;
    }

    // Opening tip at start of Q1 and OT ONLY
    // Guard against opening tip appearing mid-game (should only happen at Q1 or OT start)
    // ✅ PHASE 2.6: Handle OPENING_TIP - route through AnimationRouter
    if (turn.result_type === "OPENING_TIP") {
      const turnQuarter = turn.quarter ?? scene.quarter ?? 1;
      const isQ1Start = turnQuarter === 1 && i === 0;
      const isOTStart = turnQuarter > 4 && i === 0;
      
      animationDebugLog('OPENING TIP DETECTED - routing through AnimationRouter:', {
        result_type: turn.result_type,
        winner: turn.winner,
        home_wins: turn.home_wins,
        turn_index: i,
        quarter: turnQuarter,
        isQ1Start,
        isOTStart
      });
      
      // ✅ PHASE 2.6: Route through AnimationRouter
      // runOpeningTipSequence, state transition, announcements, and score updates are handled by handler
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: Validation, opening tip sequence, state transition, onUpdate, and updateDebugScore handled by AnimationRouter
      continue;
    }

    // ✅ PHASE 2.6: Fast break shots now route through AnimationRouter (same as HCO shots)
    // Fast break detection happens in AnimationEngine.determineHandler() (checks fast_break flag or result_type === "FAST_BREAK")
    // Active player display, fast break sequence, and _previousTurnWasShot flag are handled by handler
    // AnimationRouter handles pre/post setup (prepareTurnForAnimation, finalizeTurnAfterAnimation)
    // Note: Fast break shots (MAKE/MISS with fast_break === true) are detected in AnimationEngine and routed to handleFastBreak()
    // This check is kept here for explicit fast break turns (result_type === "FAST_BREAK")
    // ✅ FIX: Only check fast_break flag for current turn - next_play_type indicates what comes NEXT, not what this turn is
    if (turn.result_type === "FAST_BREAK" || 
        (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK") && turn.fast_break === true) {
      console.log('⚡ [FAST BREAK ROUTING] Routing to AnimationRouter', {
        turn_index: i,
        result_type: turn.result_type,
        fast_break: turn.fast_break,
        next_play_type: turn.next_play_type
      });
      turn.index = i;
      await animationRouter.processTurn(turn);
      // Note: Announcements, onUpdate, and updateDebugScore handled by AnimationRouter
      continue;
    }

    const shooterName = turn.shooter || "";

    const playerMap = Object.fromEntries(
      allPlayers.map(p => [p.name, p.playerId])
    );

    const shooterId = playerMap[shooterName];

    // ✅ DEBUG: Log HCO routing decision
    if (turn.result_type === "HCO") {
      
      // ✅ FIX: Route ALL HCO result_type turns with animations through AnimationRouter
      // This includes FCP/HCT → HCO transitions (press break) and regular HCO setup turns
      if (turn.animations && turn.animations.length > 0) {
        // HCO with animations - route through AnimationRouter
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
      } else {
        // HCO without animations - just do announcements and updates
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
    }

    // ✅ Phase 4: Final Turn — route FINAL_HOLD to AnimationRouter (clock out, then quarter/game end)
    if (turn.result_type === "FINAL_HOLD") {
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
    }

    // ✅ Phase 4: Final Turn shot (blocking foul) — route FOUL with final_turn to AnimationRouter
    if (turn.final_turn === true && turn.result_type === "FOUL") {
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
    }

    const shouldDebugHCO =
      DEBUG_FLOW ||
      debugEnabled ||
      Boolean(typeof window !== 'undefined' && window.ROUTER_DEBUG);

    // 🔍 DIAGNOSTIC: Always log when window.ROUTER_DEBUG is set (moved outside block for visibility)
    if (typeof window !== 'undefined' && window.ROUTER_DEBUG) {
    }

    // ✅ PHASE 2.5: Standard HCO turns now route through AnimationRouter
    // This includes all MAKE/MISS turns that are not fast breaks
    {
      // ✅ Debug log for HCO turns after Fast Break defensive stop
      const previousTurn = i > 0 ? turns[i - 1] : null;
      const wasDefensiveStop = previousTurn?.result_type === "DEFENSIVE_STOP" && previousTurn?.fast_break === true;
      // ✅ CRITICAL FIX: DO NOT exclude FCP/HCT from routing through AnimationRouter
      // FCP/HCT shot attempts (MAKE/MISS with fcp_shot/hct_shot flags) should route through AnimationRouter
      // same as HCO - AnimationEngine.determineHandler() will route them to SHOT_ATTEMPT handler
      // ✅ FIX: Exclude Fast Break from HCO routing - only check fast_break flag for current turn
      // next_play_type indicates what comes NEXT, not what this turn is (e.g., HCO miss → fast break)
      const isFastBreak = turn.fast_break === true;
      const isHCO = !isFastBreak && (turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK");
      
      // ✅ DEBUG: Log when entering shot instance (HCO or FCP/HCT)
      if (isHCO) {
        console.log('🎆🎆🎆 ENTERING SHOT INSTANCE 🎆🎆🎆', {
          turn_index: i,
          result_type: turn.result_type,
          fast_break: turn.fast_break,
          fcp_shot: turn.fcp_shot,
          hct_shot: turn.hct_shot,
          willRouteToAnimationRouter: true
        });
      }
      
      // 🔍 DIAGNOSTIC: Log HCO-specific info
      if (typeof window !== 'undefined' && window.ROUTER_DEBUG) {
        console.log('🔍 [DIAGNOSTIC HCO] Turn', i, {
          isHCO,
          willLog: shouldDebugHCO && isHCO,
          routing: 'AnimationRouter'
        });
      }
      
      // Enhanced debug for HCO detection after defensive stop
      if (wasDefensiveStop) {
        console.log("🔍 HCO Detection After Defensive Stop:", {
          turn_index: i,
          previous_turn_result: previousTurn?.result_type,
          previous_turn_fast_break: previousTurn?.fast_break,
          current_turn_result: turn.result_type,
          current_turn_fast_break: turn.fast_break,
          current_turn_next_play_type: turn.next_play_type,
          current_turn_offensive_state: turn.offensive_state,
          isHCO_criteria: {
            not_fast_break: !turn.fast_break,
            is_shot: turn.result_type === "MAKE" || turn.result_type === "MISS" || turn.result_type === "BLOCK",
            matches_criteria: isHCO
          },
          current_state: scene.stateMachine?.state,
          has_animations: !!turn.animations?.length,
          animation_count: turn.animations?.length || 0,
          routing: 'AnimationRouter'
        });
      }
      
      if (shouldDebugHCO && isHCO) {
        console.log('🔍 HCO_ROUTER_START', {
          turn_index: i,
          result_type: turn.result_type,
          fast_break: turn.fast_break,
          hasAnimations: !!turn.animations?.length,
          animationCount: turn.animations?.length || 0,
          currentBallOwner: scene.ballController?.currentOwner?.playerId ?? null,
          state: scene.stateMachine?.state
        });
      }

      // ✅ PHASE 2.5: Route standard HCO turns through AnimationRouter
      // ✅ FIX (Bug 3 REAL FIX): Only route if isHCO (was executing for ALL turns!)
      if (isHCO) {
      // Ensure turn.index is set (AnimationRouter will use it for context)
      turn.index = i;
      
      // Removed verbose before/after process turn logs
      
      // AnimationRouter handles pre/post setup (prepareTurnForAnimation, finalizeTurnAfterAnimation)
      // Note: prepareTurnForAnimation was already called at line 479, but AnimationRouter will call it again
      // This is safe (idempotent) but we could optimize later by skipping the first call for HCO turns
      await animationRouter.processTurn(turn);

      // Removed verbose after process turn log

        if (shouldDebugHCO) {
        console.log('🔍 HCO_ROUTER_END', {
          turn_index: i,
          result_type: turn.result_type,
          fast_break: turn.fast_break,
          currentBallOwner: scene.ballController?.currentOwner?.playerId ?? null,
          previousTurnWasShot: scene._previousTurnWasShot === true,
          state: scene.stateMachine?.state
        });
      }
        
        continue;  // ✅ Skip rest of loop after processing HCO
      }
    }

    // ✅ DEBUG: Log STEAL routing decision
    if (turn.result_type === "STEAL") {
      console.log('🔍 [STEAL ROUTING]', {
        turn_index: i,
        has_animations: !!turn.animations?.length,
        animation_count: turn.animations?.length || 0,
        pressureSequenceActive: scene.pressureSequenceActive,
        possession_flips: turn.possession_flips,
        possession_team_id: turn.possession_team_id,
        next_play_type: turn.next_play_type,
        will_route_to_router: !!(turn.animations && turn.animations.length > 0)
      });
      
      // ✅ FIX: Route ALL steals with animations through AnimationRouter
      // This includes FCP/HCT steals and regular HCO steals (when we add them)
      if (turn.animations && turn.animations.length > 0) {
        // Steal with animations - route through AnimationRouter
      turn.index = i;
      await animationRouter.processTurn(turn);
      continue;
      } else {
        // Steal without animations - check if it's a steal event within another turn
        const stealEvent = turn.events?.find(e => e.event_type === "STEAL");
        if (!scene.stateMachine?.is(States.FastBreak) && stealEvent) {
      // STEAL event within another turn - handle inline (not a standalone turn)
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
        // Steal event handled inline - continue to next turn
        continue;
      }
    }
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
  } finally {
    scene.events?.off?.('possessionChange', handlePossessionFlip);
    if (scene?.__fbTelemetryDebugHandler) {
      scene.events?.off?.("animTelemetry", scene.__fbTelemetryDebugHandler);
      scene.__fbTelemetryDebugHandler = null;
    }
    flushFbTelemetryDebugSummary(scene);
  }
}
