/**
 * AnimationRouter - Simplified Routing System
 * 
 * Connects AnimationEngine and BallController into a cohesive, working system
 * that can replace the existing animation system.
 * 
 * Key Benefits:
 * - Single entry point for all animations
 * - Proper ball ownership handling
 * - Event-driven architecture
 * - Easy integration with existing code
 * - No complex state management
 */

import AnimationEngine from './AnimationEngine.js';
import { getBallController } from './BallControllerAdapter.js';
import { DebugFlags, animationDebugLog } from '../utils/debugFlags.js';
import { prepareTurnForAnimation, finalizeTurnAfterAnimation } from './turnPreparation.js';
import { ENABLE_TIMEOUT_BUTTON } from '../utils/timeoutButtonManager.js';
import { waitMsRespectingPause, waitWhileUserPaused } from './playbackPause.js';

export class AnimationRouter {
  constructor(scene, playerSprites, ballSprite, onUpdate, onAction = null, updateDebugScore = null) {
    this.scene = scene;
    this.playerSprites = playerSprites;
    this.ballSprite = ballSprite;
    this.onUpdate = onUpdate;
    this.onAction = onAction;
    this.updateDebugScore = updateDebugScore; // ✅ PHASE 2.3: Store updateDebugScore function
    
    // Initialize core components
    this.ballController = getBallController(); // Use the global BallController from adapter
    this.animationEngine = new AnimationEngine(scene);
    
    // Inject dependencies into animation engine (no state machine needed)
    this.animationEngine.injectDependencies(this.ballController, null, playerSprites);
    
    // Router state
    this.isProcessing = false;
    this.currentTurn = null;
    this.animationQueue = [];
    this.isInitialized = false;
    
    // Initialize the system
    this.initialize();
    this.installClockReconGlobalHelpers();
    
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Initialized with all components');
    }
  }

  /**
   * Initialize the animation system
   */
  initialize() {
    if (this.isInitialized) {
      console.warn('AnimationRouter: Already initialized');
      return;
    }

    // Set up ball controller event listeners
    this.ballController.onAttachment((previousOwner, newOwner, options) => {
      this.handleBallAttachment(previousOwner, newOwner, options);
    });

    this.ballController.onDetachment((previousOwner, reason, options) => {
      this.handleBallDetachment(previousOwner, reason, options);
    });

    // Mark as initialized
    this.isInitialized = true;

    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: System initialized successfully');
    }
  }

  installClockReconGlobalHelpers() {
    const scope = (typeof window !== "undefined" && window) || globalThis;
    if (!scope || scope.__clockReconHelpersInstalled) return;
    scope.__clockReconHelpersInstalled = true;

    const asNumber = (v, fallback, min = 0) => {
      const n = Number(v);
      if (!Number.isFinite(n) || n < min) return fallback;
      return n;
    };

    if (typeof scope.showClockReconConfig !== "function") {
      scope.showClockReconConfig = () => {
        const config = {
          mode: String(scope.UESS_CLOCK_AUTHORITY_MODE ?? "observe"),
          toleranceSeconds: asNumber(scope.UESS_CLOCK_RECON_TOLERANCE_SECONDS, 0.1, 0),
          summaryEvery: Math.floor(
            asNumber(scope.UESS_CLOCK_RECON_SUMMARY_EVERY, 10, 1)
          ),
          warnGate: {
            minRows: Math.floor(
              asNumber(scope.UESS_CLOCK_RECON_WARN_MIN_ROWS, 40, 1)
            ),
            outOfToleranceRateMax: asNumber(
              scope.UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX,
              0.02,
              0
            ),
            averageAbsDeltaSecondsMax: asNumber(
              scope.UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX,
              0.25,
              0
            ),
            maxAbsDeltaSecondsMax: asNumber(
              scope.UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX,
              1.0,
              0
            ),
          },
          latestSummary: scope.__CLOCK_RECON_SUMMARY_LAST__ ?? null,
        };
        console.log("[CLOCK RECON CONFIG]", config);
        return config;
      };
    }

    if (typeof scope.getClockReconSummaryLatest !== "function") {
      scope.getClockReconSummaryLatest = (n = 5) => {
        const count = Math.max(0, Math.floor(Number(n) || 0));
        const list = Array.isArray(scope.__CLOCK_RECON_SUMMARY_BUFFER__)
          ? scope.__CLOCK_RECON_SUMMARY_BUFFER__
          : [];
        return list.slice(-count);
      };
    }

    if (typeof scope.clearClockReconBuffers !== "function") {
      scope.clearClockReconBuffers = () => {
        scope.__CLOCK_RECON_LAST__ = undefined;
        scope.__CLOCK_RECON_SUMMARY_LAST__ = undefined;
        scope.__CLOCK_RECON_BUFFER__ = [];
        scope.__CLOCK_RECON_SUMMARY_BUFFER__ = [];
      };
    }

    if (typeof scope.getTurnBoundaryWaitLatest !== "function") {
      scope.getTurnBoundaryWaitLatest = (n = 20) => {
        const count = Math.max(0, Math.floor(Number(n) || 0));
        const list = Array.isArray(scope.__TURN_BOUNDARY_WAIT_BUFFER__)
          ? scope.__TURN_BOUNDARY_WAIT_BUFFER__
          : [];
        return list.slice(-count);
      };
    }

    if (typeof scope.clearTurnBoundaryWaitBuffer !== "function") {
      scope.clearTurnBoundaryWaitBuffer = () => {
        scope.__TURN_BOUNDARY_WAIT_LAST__ = undefined;
        scope.__TURN_BOUNDARY_WAIT_BUFFER__ = [];
      };
    }

    if (typeof scope.showTurnBoundaryWaitSummary !== "function") {
      scope.showTurnBoundaryWaitSummary = (n = 40) => {
        const count = Math.max(0, Math.floor(Number(n) || 0));
        const list = Array.isArray(scope.__TURN_BOUNDARY_WAIT_BUFFER__)
          ? scope.__TURN_BOUNDARY_WAIT_BUFFER__
          : [];
        const rows = list.slice(-count);
        const waits = rows
          .map((r) => Number(r?.waitedMs))
          .filter((v) => Number.isFinite(v) && v >= 0)
          .sort((a, b) => a - b);
        const total = waits.length;
        const avg = total
          ? waits.reduce((sum, v) => sum + v, 0) / total
          : 0;
        const percentile = (p) => {
          if (!total) return 0;
          const idx = Math.min(
            total - 1,
            Math.max(0, Math.ceil((p / 100) * total) - 1)
          );
          return waits[idx];
        };
        const byBranch = rows.reduce((acc, row) => {
          const key = String(row?.branch || "unknown");
          acc[key] = (acc[key] || 0) + 1;
          return acc;
        }, {});
        const summary = {
          sampleSize: total,
          avgWaitMs: Number(avg.toFixed(1)),
          p50WaitMs: Number(percentile(50).toFixed(1)),
          p95WaitMs: Number(percentile(95).toFixed(1)),
          maxWaitMs: Number((waits[total - 1] || 0).toFixed(1)),
          byBranch,
        };
        console.table(rows);
        console.log("[TURN BOUNDARY WAIT SUMMARY]", summary);
        return summary;
      };
    }
  }

  _clearClockInterpolationTracking() {
    if (!this.scene) return;
    this.scene._clockInterpolationTween = null;
    this.scene._clockInterpolationPromise = null;
    this.scene._clockInterpolationResolve = null;
    this.scene._clockInterpolationStartedAtMs = null;
    this.scene._clockInterpolationDurationMs = null;
  }

  _resolveClockInterpolationTracking() {
    if (!this.scene) return;
    const resolve = this.scene._clockInterpolationResolve;
    this._clearClockInterpolationTracking();
    if (typeof resolve === "function") {
      try {
        resolve();
      } catch (_) {
        // no-op
      }
    }
  }

  _isBoundaryWaitDebugEnabled() {
    const scope = typeof window !== "undefined" ? window : globalThis;
    return scope?.UESS_TURN_BOUNDARY_WAIT_DEBUG === true;
  }

  _emitBoundaryWaitTelemetry(turnData, payload = {}) {
    if (!this._isBoundaryWaitDebugEnabled()) return;
    const scope = typeof window !== "undefined" ? window : globalThis;
    const row = {
      event: "turn_boundary_clock_settle_wait",
      branchKind: "clock_boundary_wait",
      timestampMs: Date.now(),
      resultType: turnData?.result_type ?? null,
      turnIndex:
        turnData?.index ?? turnData?.turnIndex ?? this.scene?.currentTurn ?? null,
      ...payload,
    };
    this.scene?.events?.emit?.("animTelemetry", row);
    scope.__TURN_BOUNDARY_WAIT_LAST__ = row;
    if (!Array.isArray(scope.__TURN_BOUNDARY_WAIT_BUFFER__)) {
      scope.__TURN_BOUNDARY_WAIT_BUFFER__ = [];
    }
    scope.__TURN_BOUNDARY_WAIT_BUFFER__.push(row);
    if (scope.__TURN_BOUNDARY_WAIT_BUFFER__.length > 120) {
      scope.__TURN_BOUNDARY_WAIT_BUFFER__.splice(
        0,
        scope.__TURN_BOUNDARY_WAIT_BUFFER__.length - 120
      );
    }
  }

  _collectActiveBoundaryTweens() {
    if (!this.scene?.tweens?.getTweensOf) return [];
    const heartbeatStore = this.scene?.__arrivalHeartbeatStore;
    const ignoredTweens = new Set();
    if (heartbeatStore && typeof heartbeatStore.values === "function") {
      for (const entry of heartbeatStore.values()) {
        if (entry?.tween) ignoredTweens.add(entry.tween);
      }
    }
    const targets = [
      ...Object.values(this.playerSprites || {}),
      this.ballSprite,
      this.scene?.ballShadowSprite,
    ].filter(Boolean);
    const isNonBoundaryVisualTween = (tween) => {
      const allowedVisualKeys = new Set([
        "displayOriginX",
        "displayOriginY",
        "scaleX",
        "scaleY",
      ]);
      const data = Array.isArray(tween?.data) ? tween.data : [];
      if (!data.length) return false;
      const keys = data
        .map((d) => String(d?.key ?? ""))
        .filter((k) => k.length > 0);
      if (!keys.length) return false;
      // Heartbeat-like visual tweens only mutate origin/scale; they are intentionally
      // long-lived and should never gate turn-boundary progression.
      return keys.every((k) => allowedVisualKeys.has(k));
    };
    const seen = new Set();
    const activeTweens = [];
    for (const target of targets) {
      const tweens = this.scene.tweens.getTweensOf(target) || [];
      for (const tween of tweens) {
        if (!tween || seen.has(tween)) continue;
        if (ignoredTweens.has(tween)) continue;
        if (tween.__uessBoundaryIgnore === true) continue;
        if (isNonBoundaryVisualTween(tween)) continue;
        seen.add(tween);
        const isPlaying = typeof tween.isPlaying === "function"
          ? tween.isPlaying()
          : tween.isPlaying !== false;
        if (isPlaying) activeTweens.push(tween);
      }
    }
    return activeTweens;
  }

  _describeBoundaryTweens(maxItems = 10) {
    const activeTweens = this._collectActiveBoundaryTweens();
    const playerKeyBySprite = new Map();
    for (const [id, sprite] of Object.entries(this.playerSprites || {})) {
      if (sprite) playerKeyBySprite.set(sprite, String(id));
    }
    const describeTarget = (target) => {
      if (!target) return "unknown_target";
      if (playerKeyBySprite.has(target)) {
        return `player:${playerKeyBySprite.get(target)}`;
      }
      if (target === this.ballSprite) return "ballSprite";
      if (target === this.scene?.ballShadowSprite) return "ballShadowSprite";
      return String(
        target?.playerId ??
          target?.name ??
          target?.texture?.key ??
          target?.type ??
          "unknown_target"
      );
    };
    return activeTweens.slice(0, Math.max(0, Number(maxItems) || 0)).map((tween) => {
      const targets = Array.isArray(tween?.targets) ? tween.targets : [];
      const tweenKeys = (Array.isArray(tween?.data) ? tween.data : [])
        .map((d) => String(d?.key ?? ""))
        .filter((k) => k.length > 0);
      return {
        targets: targets.map(describeTarget),
        keys: tweenKeys,
        progress:
          typeof tween?.progress === "number"
            ? Number(tween.progress.toFixed(3))
            : null,
        totalDuration:
          Number.isFinite(Number(tween?.totalDuration))
            ? Math.round(Number(tween.totalDuration))
            : null,
      };
    });
  }

  _countActiveTweensForBoundary() {
    return this._collectActiveBoundaryTweens().length;
  }

  _forceStopBoundaryTweens() {
    const activeTweens = this._collectActiveBoundaryTweens();
    if (activeTweens.length > 0) {
      console.warn('[BOUNDARY TWEEN][FORCE STOP]', activeTweens.map((tween) => ({
        debugTag: tween?.__debugTag ?? null,
        debugPlayerId: tween?.__debugPlayerId ?? null,
        debugStart: tween?.__debugStart ?? null,
        debugTarget: tween?.__debugTarget ?? null,
        progress:
          typeof tween?.progress === "number"
            ? Number(tween.progress.toFixed(3))
            : null,
        totalDuration:
          Number.isFinite(Number(tween?.totalDuration))
            ? Math.round(Number(tween.totalDuration))
            : null,
      })));
    }
    let stopped = 0;
    for (const tween of activeTweens) {
      try {
        if (typeof tween.stop === "function") {
          tween.stop();
          stopped += 1;
        } else if (typeof tween.remove === "function") {
          tween.remove();
          stopped += 1;
        }
      } catch (_) {
        // no-op; boundary guard is best-effort cleanup
      }
    }
    return stopped;
  }

  async waitForBoundaryTweenDrain(maxWaitMs = 120, pollMs = 20) {
    const timeoutMs = Math.max(0, Number(maxWaitMs) || 0);
    const stepMs = Math.max(5, Number(pollMs) || 20);
    if (!this.scene?.tweens?.getTweensOf || timeoutMs <= 0) {
      return { waitedMs: 0, remainingTweens: this._countActiveTweensForBoundary() };
    }
    let elapsed = 0;
    let remaining = this._countActiveTweensForBoundary();
    while (remaining > 0 && elapsed < timeoutMs) {
      await waitWhileUserPaused(this.scene);
      await waitMsRespectingPause(this.scene, stepMs);
      if (!this.scene?.isPaused) {
        elapsed += stepMs;
        remaining = this._countActiveTweensForBoundary();
      }
    }
    return {
      waitedMs: Math.max(0, elapsed),
      remainingTweens: remaining,
    };
  }

  async waitForClockInterpolationSettle(maxWaitMs = 0) {
    const p = this.scene?._clockInterpolationPromise;
    if (!p || typeof p.then !== "function") return;
    const timeoutMs = Math.max(0, Number(maxWaitMs) || 0);
    const settleCapMs = Math.max(
      0,
      Number(
        (typeof window !== "undefined" && window.UESS_CLOCK_SETTLE_CAP_MS) ?? 120
      ) || 120
    );
    const nowMs =
      typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now();
    const startedAtMs = Number(this.scene?._clockInterpolationStartedAtMs);
    const durationMs = Number(this.scene?._clockInterpolationDurationMs);

    // If interpolation still has a long runway, do not block turn boundaries.
    if (
      Number.isFinite(startedAtMs) &&
      Number.isFinite(durationMs) &&
      durationMs > 0
    ) {
      const elapsedMs = Math.max(0, nowMs - startedAtMs);
      const remainingMs = Math.max(0, durationMs - elapsedMs);
      if (remainingMs > settleCapMs) return;
      const tailWaitMs = Math.min(timeoutMs || settleCapMs, remainingMs + 32);
      if (tailWaitMs <= 0) return;
      const waitStartMs =
        typeof performance !== "undefined" && typeof performance.now === "function"
          ? performance.now()
          : Date.now();
      await Promise.race([
        p,
        waitMsRespectingPause(this.scene, tailWaitMs),
      ]);
      const waitEndMs =
        typeof performance !== "undefined" && typeof performance.now === "function"
          ? performance.now()
          : Date.now();
      return {
        waitedMs: Math.max(0, waitEndMs - waitStartMs),
        settleCapMs,
        branch: "tail",
      };
    }

    // Fallback for cases without timing metadata.
    const fallbackWaitMs = Math.min(timeoutMs || settleCapMs, settleCapMs);
    if (fallbackWaitMs <= 0) {
      return { waitedMs: 0, settleCapMs, branch: "none" };
    }
    const waitStartMs =
      typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now();
    await Promise.race([
      p,
      waitMsRespectingPause(this.scene, fallbackWaitMs),
    ]);
    const waitEndMs =
      typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now();
    return {
      waitedMs: Math.max(0, waitEndMs - waitStartMs),
      settleCapMs,
      branch: "fallback",
    };
  }

  /**
   * Process a turn through the new animation system
   */
  async processTurn(turnData) {
    if (this.isProcessing) {
      console.warn('AnimationRouter: Already processing a turn, queuing...');
      this.animationQueue.push(turnData);
      return;
    }

    this.isProcessing = true;
    this.currentTurn = turnData;

    // ✅ PHASE 2.3: Variables for pre/post setup
    let turnIndex = null;
    let possessionId = null;

    const shouldLog =
      DebugFlags.ANIMATION_ROUTER ||
      Boolean(typeof window !== 'undefined' && window.ROUTER_DEBUG);

    // Check if this is a standard HCO turn (shot that's not a fast break)
    // Defined outside try block so it's accessible in finally block
    const isHCO = !turnData.fast_break && (turnData.result_type === "MAKE" || turnData.result_type === "MISS" || turnData.result_type === "BLOCK");

    try {
      // Clock control for no-impact turns:
      // Pause UX countdown when backend marks no time elapsed (or known no-impact result types),
      // then release that pause token for impact turns.
      const noImpactResultTypes = new Set([
        'FREE_THROW',
        'SIDE_INBOUND',
        'BASELINE_INBOUND',
        'TIMEOUT',
      ]);
      const elapsedValue = Number(turnData?.time_elapsed ?? turnData?.timeElapsed);
      const hasElapsedValue = Number.isFinite(elapsedValue);
      const isNoImpactTurn =
        (hasElapsedValue && elapsedValue === 0) ||
        noImpactResultTypes.has(turnData?.result_type);
      const isOpeningTipTurn = turnData?.result_type === 'OPENING_TIP';

      // Clocks: game clock never forced; shot clock uses contract only (backend authority — Real_Time_Clock_System §101–102).
      if (this.scene?.gameClock || this.scene?.shotClock) {
        const applyClockControl = (clockRef) => {
          if (!clockRef) return;
          if (isNoImpactTurn) clockRef.pause('no_impact_turn');
          else {
            clockRef.resume('no_impact_turn');
            if (this.scene.isPaused) clockRef.pause('user_pause');
          }
        };
        applyClockControl(this.scene.gameClock);
        applyClockControl(this.scene.shotClock);
      }

      // Contract fields (snake_case + camelCase)
      const clockStart = Number(turnData?.clock_start ?? turnData?.clockStart);
      const clockEnd = Number(turnData?.clock_end ?? turnData?.clockEnd);
      const shotClockStart = Number(turnData?.shot_clock_start ?? turnData?.shotClockStart);
      const shotClockEnd = Number(turnData?.shot_clock_end ?? turnData?.shotClockEnd);
      const durationMs = Math.max(0, Math.floor(Number(turnData?.real_time_elapsed_ms ?? turnData?.realTimeElapsedMs) || 0));
      const gameSecondsToCount = Number.isFinite(clockStart) && Number.isFinite(clockEnd) ? clockStart - clockEnd : 0;
      const shotSecondsToCount = Number.isFinite(shotClockStart) && Number.isFinite(shotClockEnd) ? shotClockStart - shotClockEnd : 0;
      const clockEventLedger = Array.isArray(turnData?.clock_event_ledger)
        ? turnData.clock_event_ledger
        : [];
      const clockAuthorityMode = String(
        turnData?.uess_clock_authority_mode ?? ""
      ).toLowerCase();
      // Sync diagnostics: compare backend real-time estimate to game time (1:1 would be game_seconds * 1000)
      const expectedRealMsIf1To1 = gameSecondsToCount * 1000;
      const ratioRealToGame = expectedRealMsIf1To1 > 0 ? (durationMs / expectedRealMsIf1To1) : null;

      console.log('⏱️ [CLOCK CONTRACT] Turn dict clock fields', {
        clock_start: turnData?.clock_start,
        clock_end: turnData?.clock_end,
        shot_clock_start: turnData?.shot_clock_start,
        shot_clock_end: turnData?.shot_clock_end,
        real_time_elapsed_ms: turnData?.real_time_elapsed_ms,
        result_type: turnData?.result_type,
        // Sync diagnostics: game/shot seconds vs backend real-time estimate
        game_seconds_elapsed: gameSecondsToCount,
        shot_seconds_elapsed: shotSecondsToCount,
        real_time_elapsed_ms_estimate: durationMs,
        expected_real_ms_if_1_to_1: expectedRealMsIf1To1,
        ratio_real_to_game: ratioRealToGame != null ? `${(ratioRealToGame * 100).toFixed(0)}%` : null,
        keys: typeof turnData === 'object' ? Object.keys(turnData).filter(k => k.includes('clock') || k === 'real_time_elapsed_ms') : [],
      });
      this.emitClockObserveParityTelemetry(turnData, {
        clockStart,
        clockEnd,
        shotClockStart,
        shotClockEnd,
        durationMs,
        clockEventLedger,
        clockAuthorityMode,
      });

      if (this.scene._clockInterpolationTween) {
        this.scene._clockInterpolationTween.remove();
        this._resolveClockInterpolationTracking();
      }

      // Turn start: same condition for both — when game clock has contract, sync both (shot uses shot keys, clamp 30)
      if (this.scene?.gameClock && this.scene?.shotClock && Number.isFinite(clockStart)) {
        this.scene.gameClock.syncWithBackend(clockStart);
        const shotStart = Number.isFinite(shotClockStart) ? Math.min(30, shotClockStart) : 30;
        this.scene.shotClock.syncWithBackend(shotStart);
      }

      // Tween: run when game clock runs (same condition). Two-phase when shot stops early: both in sync, then shot paused.
      const shouldRunClockTween = durationMs > 0 && gameSecondsToCount > 0 && this.scene?.gameClock && this.scene?.shotClock;
      if (shouldRunClockTween) {
        const gameClock = this.scene.gameClock;
        const shotClock = this.scene.shotClock;
        const startGame = Number.isFinite(clockStart) ? clockStart : 0;
        const endGame = Number.isFinite(clockEnd) ? clockEnd : 0;
        const startShot = Number.isFinite(shotClockStart) ? Math.min(30, shotClockStart) : 30;
        const endShot = Number.isFinite(shotClockEnd) ? Math.min(30, shotClockEnd) : 30;
        const shotSecondsToCount = Math.max(0, startShot - endShot);
        // When shot elapsed < game elapsed, phase 1 = both in sync for shotSecondsToCount, phase 2 = shot paused, game continues.
        const useTwoPhase = gameSecondsToCount > 0 && shotSecondsToCount < gameSecondsToCount;
        const ratio = useTwoPhase ? shotSecondsToCount / gameSecondsToCount : 1;
        const progressObj = { p: 0 };
        const tweenStartMs =
          typeof performance !== "undefined" && typeof performance.now === "function"
            ? performance.now()
            : Date.now();
        this.scene._clockInterpolationPromise = new Promise((resolve) => {
          this.scene._clockInterpolationResolve = resolve;
        });
        this.scene._clockInterpolationStartedAtMs = tweenStartMs;
        this.scene._clockInterpolationDurationMs = durationMs;
        this.scene._clockInterpolationTween = this.scene.tweens.add({
          targets: progressObj,
          p: 1,
          duration: durationMs,
          ease: 'Linear',
          onUpdate: () => {
            const progress = Math.min(1, Math.max(0, progressObj.p));
            let gameSeconds;
            let shotSeconds;
            if (useTwoPhase && ratio > 0) {
              if (progress <= ratio) {
                const phase1Progress = progress / ratio;
                gameSeconds = startGame - phase1Progress * shotSecondsToCount;
                shotSeconds = startShot - phase1Progress * shotSecondsToCount;
              } else {
                const phase2Progress = (progress - ratio) / (1 - ratio);
                gameSeconds = (startGame - shotSecondsToCount) - phase2Progress * (gameSecondsToCount - shotSecondsToCount);
                shotSeconds = endShot;
              }
            } else {
              gameSeconds = startGame - progress * gameSecondsToCount;
              shotSeconds = startShot + progress * (endShot - startShot);
            }
            gameClock.syncWithBackend(Math.max(endGame, Math.min(startGame, gameSeconds)));
            shotClock.syncWithBackend(Math.max(0, Math.min(30, shotSeconds)));
          },
          onComplete: () => {
            this._resolveClockInterpolationTracking();
          },
        });
      }

      // ✅ PHASE 2.3: Call prepareTurnForAnimation at the start
      // Extract turnIndex from turnData (will be set by prepareTurnForAnimation if not present)
      turnIndex = turnData.index ?? turnData.turnIndex ?? null;
      
      const homeTeamId = this.scene.simData?.home_team_id;
      const { possessionId: prepPossessionId } = await prepareTurnForAnimation({
        turn: turnData,
        scene: this.scene,
        turnIndex: turnIndex ?? 0, // Use 0 as fallback if not provided (prepareTurnForAnimation will set it)
        homeTeamId
      });
      possessionId = prepPossessionId;
      
      // ✅ PHASE 2.3: Get turnIndex from prepared turn (prepareTurnForAnimation sets turn.index)
      turnIndex = turnData.index ?? turnIndex;
      
      // ✅ TIMEOUT: Determine eligibility at start of each turn (single source of truth)
      // This eliminates stale data issues - eligibility is determined once with fresh turnData
      if (ENABLE_TIMEOUT_BUTTON) {
        const { checkTimeoutEligibility, checkAndExecuteQueuedTimeout } = await import('../utils/timeoutButtonManager.js');
        // Store current turn data for timeout eligibility check
        this.scene.currentTurnData = turnData;
        
        // ✅ Store previous turn data for DREB => HCO eligibility check
        // This is needed to check if previous turn was DREB when current turn is HCO
        // Note: previousTurnData is set at the end of each turn processing, so it contains the last processed turn
        // For the first turn, previousTurnData will be undefined (which is fine - first turn can't be DREB => HCO)
        
        // Set eligibility flag at start of turn (used by both button press and queued timeout check)
        this.scene.currentTurnTimeoutEligible = checkTimeoutEligibility(this.scene, turnData);
        
        // Check if queued timeout should execute (Scenario B: queued from ineligible turn)
        const timeoutExecuted = await checkAndExecuteQueuedTimeout(this.scene, turnData);
        if (timeoutExecuted) {
          // Timeout was executed (Scenario B: queued from ineligible turn, now executing at start of eligible turn)
          // Stop processing this turn - timeout popup is showing, user will navigate
          console.log('⏸️ TIMEOUT: Stopping turn processing - timeout executed at start of eligible turn');
          return;
        }
        // If timeout not executed, continue processing turn normally
      }
      
      if (shouldLog && isHCO) {
        console.log('🔍 HCO_ROUTER_START', {
          result_type: turnData.result_type,
          turn_index: turnIndex,
          fast_break: turnData.fast_break,
          hasAnimations: !!turnData.animations?.length,
          animationCount: turnData.animations?.length || 0,
          currentBallOwner: this.ballController?.currentOwner?.playerId ?? null
        });
      } else {
        if (false) console.log('[AnimationRouter]', {
          result_type: turnData.result_type,
          turn_index: turnIndex,
          hasAnimationEngine: !!this.animationEngine,
          hasBallController: !!this.ballController,
          hasPlayerSprites: !!this.playerSprites
        });
      }

      // Discrete DREB → HCO/HCT/FCP outlet: `runDefensiveReboundSetup` after DREB `playTurn`
      // (`AnimationEngine._maybeRunDiscreteDrebOutletLeadIn`). MISS turn may set `next_play_type`
      // to "DREB", so `ShotAnimationSystem.handleDefensiveRebound` does not run outlet on the shot turn.
      
      // No state machine needed - just process the turn directly
      if (!shouldLog) {
        // Processing (log removed)
      }

      // ✅ SIMPLIFIED: Timeouts only execute at start of eligible turns (checked in checkAndExecuteQueuedTimeout)
      // No need to kill turns mid-animation - timeouts wait for turn boundaries
      
      // ✅ PHASE 2.1: Enhanced context object with all required parameters
      // ✅ Force Foul: nextTurn so BIP/SIP can animate defender move in same turn when next is quick_foul
      const nextTurn = this.scene._currentTurnBatch?.[(turnData.index ?? turnIndex ?? 0) + 1];
      const context = {
        playerSprites: this.playerSprites,
        ballSprite: this.ballSprite,
        onUpdate: this.onUpdate,
        simData: this.scene.simData,
        onAction: this.onAction, // Pass onAction callback if provided
        turnIndex: turnIndex, // ✅ PHASE 2.1: Add turnIndex to context
        nextTurn: nextTurn ?? null
      };
      
      if (!shouldLog) {
        // Calling engine (log removed)
      }
      await this.animationEngine.processTurn(turnData, context);
      // Universal continuity guard: do not advance next turn until
      // this turn's clock interpolation window has settled.
      const boundaryWait = await this.waitForClockInterpolationSettle(
        Math.max(0, Number(durationMs) || 0) + 150
      );
      if (boundaryWait) {
        this._emitBoundaryWaitTelemetry(turnData, {
          waitedMs: Math.round(boundaryWait.waitedMs ?? 0),
          settleCapMs: boundaryWait.settleCapMs ?? null,
          branch: boundaryWait.branch ?? null,
          contractDurationMs: Math.max(0, Number(durationMs) || 0),
        });
      }
      const tweenDrain = await this.waitForBoundaryTweenDrain(
        Number(
          (typeof window !== "undefined"
            ? window.UESS_BOUNDARY_TWEEN_DRAIN_MAX_MS
            : globalThis?.UESS_BOUNDARY_TWEEN_DRAIN_MAX_MS) ?? 120
        ) || 120,
        Number(
          (typeof window !== "undefined"
            ? window.UESS_BOUNDARY_TWEEN_DRAIN_POLL_MS
            : globalThis?.UESS_BOUNDARY_TWEEN_DRAIN_POLL_MS) ?? 20
        ) || 20
      );
      if (tweenDrain?.remainingTweens > 0) {
        const leakTweenSample = this._describeBoundaryTweens(
          Number(
            (typeof window !== "undefined"
              ? window.UESS_BOUNDARY_TWEEN_LEAK_SAMPLE_SIZE
              : globalThis?.UESS_BOUNDARY_TWEEN_LEAK_SAMPLE_SIZE) ?? 8
          ) || 8
        );
        this._emitBoundaryWaitTelemetry(turnData, {
          event: "turn_boundary_active_tween_leak",
          waitedMs: Math.round(tweenDrain.waitedMs ?? 0),
          remainingTweens: tweenDrain.remainingTweens,
          leakTweenSample,
          branch: "tween_drain",
          contractDurationMs: Math.max(0, Number(durationMs) || 0),
        });
        const stoppedCount = this._forceStopBoundaryTweens();
        this._emitBoundaryWaitTelemetry(turnData, {
          event: "turn_boundary_force_stop_applied",
          waitedMs: 0,
          remainingTweensAfterStop: this._countActiveTweensForBoundary(),
          stoppedTweens: stoppedCount,
          branch: "tween_drain_force_stop",
          contractDurationMs: Math.max(0, Number(durationMs) || 0),
        });
      }
      if (!shouldLog) {
        // Completed (log removed)
      }

      // Handle any queued turns
      await this.processQueue();

      if (!shouldLog) {
        // Success (log removed)
      }

    } catch (error) {
      console.error('❌ AnimationRouter: Error processing turn', {
        error: error.message,
        stack: error.stack,
        result_type: turnData.result_type
      });
      throw error;
    } finally {
      // PHASE2: Stop bounded clock interpolation so final snap (updateScoreboard) is authoritative
      if (this.scene?._clockInterpolationTween) {
        this.scene._clockInterpolationTween.remove();
        this._resolveClockInterpolationTracking();
      }
      // ✅ PHASE 2.3: Call finalizeTurnAfterAnimation in finally block (always runs)
      try {
        // ✅ REMOVED: Finalize logging (cluttering console)

        await finalizeTurnAfterAnimation({
          turn: turnData,
          scene: this.scene,
          onUpdate: this.onUpdate,
          possessionId,
          turnIndex: turnIndex ?? turnData.index ?? null,
          updateDebugScore: this.updateDebugScore
        });
        
        // ✅ TIMEOUT: Store current turn as previous turn for next turn's eligibility check
        // This is used to check if previous turn was DREB when current turn is HCO
        this.scene.previousTurnData = turnData;
        if (shouldLog && isHCO) {
          console.log('🔍 HCO_ROUTER_END', {
            result_type: turnData.result_type,
            turn_index: turnIndex ?? turnData.index ?? null,
            fast_break: turnData.fast_break,
            hasAnimations: !!turnData.animations?.length,
            currentBallOwner: this.ballController?.currentOwner?.playerId ?? null
          });
        }
      } catch (finalizeError) {
        console.error('❌ AnimationRouter: Error in finalizeTurnAfterAnimation', {
          error: finalizeError.message,
          stack: finalizeError.stack
        });
        // Don't throw - we're in finally block, just log the error
      }
      
      this.isProcessing = false;
      this.currentTurn = null;
    }
  }

  /**
   * Process queued turns
   */
  async processQueue() {
    while (this.animationQueue.length > 0) {
      const queuedTurn = this.animationQueue.shift();
      await this.processTurn(queuedTurn);
    }
  }

  /**
   * Handle ball attachment events
   */
  handleBallAttachment(previousOwner, newOwner, options) {
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Ball attached', {
        from: previousOwner?.playerId,
        to: newOwner?.playerId
      });
    }

    // No state machine updates needed
  }

  /**
   * Handle ball detachment events
   */
  handleBallDetachment(previousOwner, reason, options) {
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Ball detached', {
        from: previousOwner?.playerId,
        reason
      });
    }

    // No state machine updates needed
  }

  /**
   * Get current system status
   */
  getStatus() {
    return {
      isProcessing: this.isProcessing,
      currentTurn: this.currentTurn,
      queueLength: this.animationQueue.length,
      isInitialized: this.isInitialized,
      hasBallController: !!this.ballController,
      hasAnimationEngine: !!this.animationEngine
    };
  }

  deriveClockElapsedFromLedger(clockEventLedger = []) {
    if (!Array.isArray(clockEventLedger)) return 0;
    let elapsed = 0;
    for (const row of clockEventLedger) {
      if (!row || row.event_type !== "game_clock_stop") continue;
      const before = Number(row.game_clock_before);
      const after = Number(row.game_clock_after);
      if (!Number.isFinite(before) || !Number.isFinite(after)) continue;
      elapsed += Math.max(0, before - after);
    }
    return elapsed;
  }

  resolveClockReconToleranceSeconds(turnData) {
    const scope = typeof window !== "undefined" ? window : globalThis;
    const globalRaw = Number(scope?.UESS_CLOCK_RECON_TOLERANCE_SECONDS);
    if (Number.isFinite(globalRaw) && globalRaw >= 0) return globalRaw;
    const turnRaw = Number(turnData?.uess_clock_reconciliation?.tolerance_seconds);
    if (Number.isFinite(turnRaw) && turnRaw >= 0) return turnRaw;
    return 0.1;
  }

  resolveClockAuthorityMode(turnData, contextMode = null) {
    const scope = typeof window !== "undefined" ? window : globalThis;
    const normalize = (raw) => {
      const v = String(raw ?? "").trim().toLowerCase();
      if (v === "observe" || v === "warn" || v === "throw" || v === "off") {
        return v;
      }
      return null;
    };
    const globalMode = normalize(scope?.UESS_CLOCK_AUTHORITY_MODE);
    if (globalMode) return globalMode;
    const ctxMode = normalize(contextMode);
    if (ctxMode) return ctxMode;
    const turnMode = normalize(
      turnData?.uess_clock_authority_mode ??
      turnData?.uess_clock_reconciliation?.mode
    );
    if (turnMode) return turnMode;
    return "observe";
  }

  resolveClockReconSummaryEvery() {
    const scope = typeof window !== "undefined" ? window : globalThis;
    const raw = Number(scope?.UESS_CLOCK_RECON_SUMMARY_EVERY);
    if (Number.isFinite(raw) && raw >= 1) return Math.floor(raw);
    return 10;
  }

  resolveClockReconWarnThresholds() {
    const scope = typeof window !== "undefined" ? window : globalThis;
    const asNumber = (v, fallback, min = 0) => {
      const n = Number(v);
      if (!Number.isFinite(n) || n < min) return fallback;
      return n;
    };
    return {
      minRows: Math.floor(
        asNumber(scope?.UESS_CLOCK_RECON_WARN_MIN_ROWS, 40, 1)
      ),
      outOfToleranceRateMax: asNumber(
        scope?.UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX,
        0.02,
        0
      ),
      averageAbsDeltaSecondsMax: asNumber(
        scope?.UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX,
        0.25,
        0
      ),
      maxAbsDeltaSecondsMax: asNumber(
        scope?.UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX,
        1.0,
        0
      ),
    };
  }

  getClockReconSession() {
    if (!this.scene.__clockReconSession) {
      this.scene.__clockReconSession = {
        rows: 0,
        withTolerance: 0,
        outOfTolerance: 0,
        missingCompare: 0,
        absDeltaSum: 0,
        maxAbsDelta: 0,
        byResultType: {},
      };
    }
    return this.scene.__clockReconSession;
  }

  emitClockReconSummaryIfNeeded(basePayload = {}) {
    const session = this.getClockReconSession();
    const every = this.resolveClockReconSummaryEvery();
    if (session.rows === 0 || session.rows % every !== 0) return;
    const avgAbsDelta =
      session.rows > 0 ? session.absDeltaSum / session.rows : 0;
    const thresholds = this.resolveClockReconWarnThresholds();
    const outOfToleranceRate =
      session.rows > 0 ? session.outOfTolerance / session.rows : 0;
    const hasEnoughRows = session.rows >= thresholds.minRows;
    const meetsWarnPromotionGate =
      hasEnoughRows &&
      outOfToleranceRate <= thresholds.outOfToleranceRateMax &&
      avgAbsDelta <= thresholds.averageAbsDeltaSecondsMax &&
      session.maxAbsDelta <= thresholds.maxAbsDeltaSecondsMax;
    const summary = {
      event: "clock_contract_reconciliation_summary",
      branchKind: "clock_contract",
      timestampMs: Date.now(),
      mode: basePayload.mode ?? "observe",
      rows: session.rows,
      withTolerance: session.withTolerance,
      outOfTolerance: session.outOfTolerance,
      missingCompare: session.missingCompare,
      withToleranceRate:
        session.rows > 0 ? session.withTolerance / session.rows : 0,
      outOfToleranceRate,
      averageAbsDeltaSeconds: Number(avgAbsDelta.toFixed(3)),
      maxAbsDeltaSeconds: Number(session.maxAbsDelta.toFixed(3)),
      thresholds,
      hasEnoughRows,
      meetsWarnPromotionGate,
      byResultType: { ...session.byResultType },
    };
    try {
      const scope = (typeof window !== "undefined" && window) || globalThis;
      scope.__CLOCK_RECON_SUMMARY_LAST__ = summary;
      if (!Array.isArray(scope.__CLOCK_RECON_SUMMARY_BUFFER__)) {
        scope.__CLOCK_RECON_SUMMARY_BUFFER__ = [];
      }
      scope.__CLOCK_RECON_SUMMARY_BUFFER__.push(summary);
      if (scope.__CLOCK_RECON_SUMMARY_BUFFER__.length > 50) {
        scope.__CLOCK_RECON_SUMMARY_BUFFER__.splice(
          0,
          scope.__CLOCK_RECON_SUMMARY_BUFFER__.length - 50
        );
      }
    } catch (_) {
      // no-op
    }
    const emit = this.scene?.events?.emit;
    if (typeof emit === "function") {
      emit.call(this.scene.events, "animTelemetry", summary);
      if (!summary.meetsWarnPromotionGate) {
        emit.call(this.scene.events, "animTelemetry", {
          ...summary,
          event: "clock_contract_reconciliation_threshold_breach",
        });
      }
    }
  }

  emitClockObserveParityTelemetry(turnData, context = {}) {
    const emit = this.scene?.events?.emit;
    if (typeof emit !== "function") return;
    const mode = this.resolveClockAuthorityMode(
      turnData,
      context.clockAuthorityMode
    );
    if (mode === "off") return;
    const clockEventLedger = Array.isArray(context.clockEventLedger)
      ? context.clockEventLedger
      : Array.isArray(turnData?.clock_event_ledger)
        ? turnData.clock_event_ledger
        : [];
    const hasValidLedger = clockEventLedger.length > 0;
    const feElapsedFromLedger = this.deriveClockElapsedFromLedger(clockEventLedger);
    const feElapsed = hasValidLedger ? feElapsedFromLedger : null;
    const beElapsed = Number(turnData?.uess_clock_elapsed_game_seconds);
    const legacyElapsed = Number(
      turnData?.uess_clock_elapsed_legacy_game_seconds ??
      turnData?.time_elapsed ??
      turnData?.timeElapsed ??
      0
    );
    const toleranceSeconds = this.resolveClockReconToleranceSeconds(turnData);
    const deltaSeconds =
      Number.isFinite(beElapsed) && Number.isFinite(feElapsed) ? feElapsed - beElapsed : null;
    const withinTolerance =
      Number.isFinite(deltaSeconds)
        ? Math.abs(deltaSeconds) <= toleranceSeconds
        : null;
    const basePayload = {
      event: "clock_contract_event_applied",
      branchKind: "clock_contract",
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: turnData?.index ?? this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: this.scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? this.scene?.quarter ?? null,
      timestampMs: Date.now(),
      mode,
      clockEventCount: clockEventLedger.length,
      feElapsedGameSeconds: Number.isFinite(feElapsed) ? Number(feElapsed) : null,
      beElapsedGameSeconds: Number.isFinite(beElapsed) ? Number(beElapsed) : null,
      legacyElapsedGameSeconds: Number.isFinite(legacyElapsed)
        ? Number(legacyElapsed)
        : null,
      deltaSeconds: Number.isFinite(deltaSeconds) ? Number(deltaSeconds) : null,
      toleranceSeconds: Number(toleranceSeconds),
      withinTolerance,
      feElapsedSource: hasValidLedger ? "clock_event_ledger" : "missing_clock_event_ledger",
      missingClockEventLedger: !hasValidLedger,
      clockStart: Number.isFinite(context.clockStart) ? Number(context.clockStart) : null,
      clockEnd: Number.isFinite(context.clockEnd) ? Number(context.clockEnd) : null,
      shotClockStart: Number.isFinite(context.shotClockStart)
        ? Number(context.shotClockStart)
        : null,
      shotClockEnd: Number.isFinite(context.shotClockEnd)
        ? Number(context.shotClockEnd)
        : null,
      realTimeElapsedMs: Number.isFinite(context.durationMs)
        ? Number(context.durationMs)
        : null,
    };
    const session = this.getClockReconSession();
    session.rows += 1;
    if (basePayload.withinTolerance === true) session.withTolerance += 1;
    else if (basePayload.withinTolerance === false) session.outOfTolerance += 1;
    else session.missingCompare += 1;
    const absDelta = Math.abs(Number(basePayload.deltaSeconds));
    if (Number.isFinite(absDelta)) {
      session.absDeltaSum += absDelta;
      session.maxAbsDelta = Math.max(session.maxAbsDelta, absDelta);
    }
    const rt = String(basePayload.resultType || "UNKNOWN");
    session.byResultType[rt] = (session.byResultType[rt] || 0) + 1;

    // Lightweight runtime mirror for local validation without event listeners.
    // This is observe/debug only and has no gameplay effect.
    const scope = (typeof window !== "undefined" && window) || globalThis;
    try {
      scope.__CLOCK_RECON_LAST__ = { ...basePayload };
      if (!Array.isArray(scope.__CLOCK_RECON_BUFFER__)) {
        scope.__CLOCK_RECON_BUFFER__ = [];
      }
      scope.__CLOCK_RECON_BUFFER__.push({ ...basePayload });
      if (scope.__CLOCK_RECON_BUFFER__.length > 50) {
        scope.__CLOCK_RECON_BUFFER__.splice(0, scope.__CLOCK_RECON_BUFFER__.length - 50);
      }

      // Ownership contract mirror/session summary is maintained here as well so
      // it is emitted from the same always-on path as clock reconciliation.
      // For BATCH wrappers, evaluate ownership per sub-turn row and skip wrapper-only rows.
      const ownershipRows =
        turnData?.result_type === "BATCH" && Array.isArray(turnData?.batch_turns)
          ? turnData.batch_turns
          : [turnData];
      const defaultOwnershipMode =
        turnData?.uess_ownership_contract_mode ??
        turnData?.uess_ownership_contract?.mode ??
        scope?.UESS_OWNERSHIP_CONTRACT_MODE ??
        "warn";

      for (const ownershipRow of ownershipRows) {
        if (!ownershipRow || typeof ownershipRow !== "object") continue;
        const ownershipContract = ownershipRow?.uess_ownership_contract;
        if (
          !ownershipContract &&
          String(ownershipRow?.result_type || "").toUpperCase() === "BATCH"
        ) {
          continue;
        }
        const resolvedOwnershipMode =
          ownershipRow?.uess_ownership_contract_mode ??
          ownershipContract?.mode ??
          defaultOwnershipMode ??
          "warn";
        const ownershipSnapshot = {
          resultType: ownershipRow?.result_type ?? null,
          mode: String(resolvedOwnershipMode ?? "warn"),
          applicable:
            typeof ownershipContract?.applicable === "boolean"
              ? ownershipContract.applicable
              : null,
          passLifecycleValid:
            typeof ownershipContract?.pass_lifecycle_valid === "boolean"
              ? ownershipContract.pass_lifecycle_valid
              : null,
          passEventCount: Number(ownershipContract?.pass_event_count ?? 0) || 0,
          validReceiptCount: Number(ownershipContract?.pass_receipt_valid_count ?? 0) || 0,
          terminalOwnerPos: ownershipContract?.terminal_owner_pos ?? null,
          timestampMs: Date.now(),
        };
        scope.__OWNERSHIP_CONTRACT_LAST__ = ownershipSnapshot;
        if (!Array.isArray(scope.__OWNERSHIP_CONTRACT_BUFFER__)) {
          scope.__OWNERSHIP_CONTRACT_BUFFER__ = [];
        }
        scope.__OWNERSHIP_CONTRACT_BUFFER__.push(ownershipSnapshot);
        if (scope.__OWNERSHIP_CONTRACT_BUFFER__.length > 100) {
          scope.__OWNERSHIP_CONTRACT_BUFFER__.splice(
            0,
            scope.__OWNERSHIP_CONTRACT_BUFFER__.length - 100
          );
        }

        const ownershipSummaryEvery = Math.max(
          1,
          Math.floor(Number(scope.UESS_OWNERSHIP_SUMMARY_EVERY ?? 10) || 10)
        );
        if (!scope.__OWNERSHIP_CONTRACT_SESSION__) {
          scope.__OWNERSHIP_CONTRACT_SESSION__ = {
            rows: 0,
            applicableRows: 0,
            invalidRows: 0,
            missingContractRows: 0,
          };
        }
        const ownershipSession = scope.__OWNERSHIP_CONTRACT_SESSION__;
        ownershipSession.rows += 1;
        if (ownershipSnapshot.applicable === true) {
          ownershipSession.applicableRows += 1;
          if (ownershipSnapshot.passLifecycleValid === false) {
            ownershipSession.invalidRows += 1;
          }
        } else if (ownershipSnapshot.applicable === null) {
          ownershipSession.missingContractRows += 1;
        }

        if (ownershipSession.rows % ownershipSummaryEvery === 0) {
          const applicableRows = ownershipSession.applicableRows;
          const invalidRows = ownershipSession.invalidRows;
          const invalidApplicableRate =
            applicableRows > 0 ? Number((invalidRows / applicableRows).toFixed(4)) : 0;
          const thresholds = {
            minRows: Math.max(
              1,
              Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MIN_ROWS ?? 40) || 40)
            ),
            invalidApplicableRateMax: Math.max(
              0,
              Number(scope.UESS_OWNERSHIP_WARN_INVALID_APPLICABLE_RATE_MAX ?? 0.02) || 0.02
            ),
            missingContractRowsMax: Math.max(
              0,
              Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MISSING_CONTRACT_ROWS_MAX ?? 0) || 0)
            ),
          };
          const hasEnoughRows = ownershipSession.rows >= thresholds.minRows;
          const meetsWarnPromotionGate =
            hasEnoughRows &&
            invalidApplicableRate <= thresholds.invalidApplicableRateMax &&
            ownershipSession.missingContractRows <= thresholds.missingContractRowsMax;
          const summary = {
            event: "ownership_contract_summary",
            mode: ownershipSnapshot.mode,
            rows: ownershipSession.rows,
            applicableRows,
            invalidRows,
            invalidApplicableRate,
            missingContractRows: ownershipSession.missingContractRows,
            thresholds,
            hasEnoughRows,
            meetsWarnPromotionGate,
            timestampMs: Date.now(),
          };
          scope.__OWNERSHIP_CONTRACT_SUMMARY_LAST__ = summary;
          if (!Array.isArray(scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__)) {
            scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__ = [];
          }
          scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.push(summary);
          if (scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length > 50) {
            scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.splice(
              0,
              scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length - 50
            );
          }
        }
      }
    } catch (_) {
      // no-op: debug mirror should never break animation flow
    }

    emit.call(this.scene.events, "animTelemetry", basePayload);

    if (!hasValidLedger) {
      emit.call(this.scene.events, "animTelemetry", {
        ...basePayload,
        event: "clock_contract_missing_ledger",
      });
      if (mode === "warn") {
        console.warn("[CLOCK CONTRACT] missing clock_event_ledger", {
          resultType: basePayload.resultType,
          turnId: basePayload.turnId,
          turnIndex: basePayload.turnIndex,
        });
      } else if (mode === "throw") {
        throw new Error(
          `[CLOCK contract] missing clock_event_ledger (result=${basePayload.resultType ?? "?"}, turn=${basePayload.turnId ?? "?"})`
        );
      }
    }

    if (withinTolerance === true) {
      emit.call(this.scene.events, "animTelemetry", {
        ...basePayload,
        event: "clock_contract_reconciliation_pass",
      });
    } else if (withinTolerance === false) {
      emit.call(this.scene.events, "animTelemetry", {
        ...basePayload,
        event: "clock_contract_reconciliation_fail",
      });
      if (mode === "warn") {
        console.warn(
          "[CLOCK CONTRACT] reconciliation fail",
          {
            resultType: basePayload.resultType,
            turnId: basePayload.turnId,
            turnIndex: basePayload.turnIndex,
            feElapsed: basePayload.feElapsedGameSeconds,
            beElapsed: basePayload.beElapsedGameSeconds,
            deltaSeconds: basePayload.deltaSeconds,
            toleranceSeconds: basePayload.toleranceSeconds,
          }
        );
      } else if (mode === "throw") {
        throw new Error(
          `[CLOCK contract] reconciliation fail (result=${basePayload.resultType ?? "?"}, turn=${basePayload.turnId ?? "?"}, feElapsed=${basePayload.feElapsedGameSeconds}, beElapsed=${basePayload.beElapsedGameSeconds}, delta=${basePayload.deltaSeconds}, tolerance=${basePayload.toleranceSeconds})`
        );
      }
    }
    this.emitClockReconSummaryIfNeeded(basePayload);
  }

  /**
   * Reset the animation system
   */
  reset() {
    this.isProcessing = false;
    this.currentTurn = null;
    this.animationQueue = [];
    
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: System reset');
    }
  }

  /**
   * Check if this is an HCO turn that needs outlet pass step
   */
  isHCOWithPositioning(turnData) {
    // HCO turns are shot attempts (MAKE/MISS) with next_play_type: "HCO"
    // that follow a defensive rebound
    return (turnData.result_type === 'MAKE' || turnData.result_type === 'MISS' || turnData.result_type === 'BLOCK') &&
           turnData.next_play_type === 'HCO' &&
           this.followsDefensiveRebound(turnData);
  }

  /**
   * Check if this HCO turn follows a defensive rebound
   */
  followsDefensiveRebound(turnData) {
    // Check if this turn has defensive rebound information
    // This indicates the shot was missed and resulted in a defensive rebound
    return turnData.rebound_type === 'DREB' || 
           turnData.rebounderId || 
           turnData.next_play_type === 'HCO';
  }

  /**
   * Execute HCO outlet pass step (Rebound HCO Outlet animation)
   */
  async executeHCOOutletPassStep(turnData) {
    console.log('🎬 AnimationRouter: Executing HCO outlet pass step');
    
    // Use the HCO animation system if available
    if (this.animationEngine && this.animationEngine.hcoSystem) {
      await this.animationEngine.hcoSystem.processHCO(turnData);
    } else {
      console.warn('🎬 AnimationRouter: HCOAnimationSystem not available, skipping outlet pass step');
    }
  }

  /**
   * Destroy the animation system
   */
  destroy() {
    this.reset();
    this.isInitialized = false;
    
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: System destroyed');
    }
  }
}
