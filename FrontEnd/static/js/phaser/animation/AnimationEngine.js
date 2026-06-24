/**
 * AnimationEngine - Centralized Animation System
 * 
 * This class replaces the scattered animation logic across multiple files
 * with a single, clean system for routing and executing animations.
 * 
 * Key Benefits:
 * - Single entry point for all animations
 * - Centralized ball ownership management
 * - Simplified state management
 * - No race conditions or conflicts
 */

import { States } from '../state/gameStateMachine.js';
import ShotAnimationSystem from './ShotAnimationSystem.js';
import ReboundAnimationSystem from './ReboundAnimationSystem.js';
import PassAnimationSystem from './PassAnimationSystem.js';
import FreeThrowAnimationSystem from './FreeThrowAnimationSystem.js';
import HCOAnimationSystem from './HCOAnimationSystem.js';
import { enforceUnitCompletionContract } from './unitCompletionContract.js';
import gameStore from '../../state/gameStore.js';
import { ensureConsistentHeartbeat, stopAllArrivalHeartbeats } from './arrivalHeartbeat.js';

export class AnimationEngine {
  constructor(scene) {
    this.scene = scene;
    this.ballController = null; // Will be injected
    this.stateMachine = null; // Will be injected
    this.playerSprites = null; // Will be injected
    this.animationHandlers = new Map();
    this.isProcessing = false;
    
    // Animation systems
    this.shotSystem = null; // Will be initialized after dependencies are injected
    this.reboundSystem = null; // Will be initialized after dependencies are injected
    this.passSystem = null; // Will be initialized after dependencies are injected
    this.freeThrowSystem = null; // Will be initialized after dependencies are injected
    this.hcoSystem = null; // Will be initialized after dependencies are injected
    
    // Initialize default handlers
    this.initializeDefaultHandlers();
  }

  resolveTimeoutContractMode() {
    const raw = String(
      (typeof window !== 'undefined' ? window.UESS_TIMEOUT_CONTRACT_MODE : null) ?? 'warn'
    )
      .trim()
      .toLowerCase();
    if (raw === 'off' || raw === 'observe' || raw === 'warn' || raw === 'throw') return raw;
    return 'warn';
  }

  getTimeoutBudgetGameSeconds(kind = 'pause') {
    const scope = typeof window !== 'undefined' ? window : globalThis;
    const raw =
      kind === 'pause'
        ? Number(scope?.UESS_TIMEOUT_PAUSE_BARRIER_MAX_GAME_SECONDS)
        : Number(scope?.UESS_TIMEOUT_RESUME_PREP_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return kind === 'pause' ? 1 : 6;
  }

  emitTimeoutContractTelemetry(turnData, event, payload = {}) {
    this.scene?.events?.emit?.('animTelemetry', {
      event,
      branchKind: 'timeout_phase_contract',
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: this.scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? this.scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    });
  }

  enforceTimeoutUnitContract({
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
    const mode = this.resolveTimeoutContractMode();
    if (mode === 'off') return;
    const clockSecondMs = this.scene?.gameClock?.getState?.().tickMs || 350;
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
      this.emitTimeoutContractTelemetry(turnData, 'timeout_phase_clock_overrun', {
        unitId,
        ...contractContext,
      });
    }
    const logger =
      mode === 'observe'
        ? {
            warn: () => {},
          }
        : console;
    enforceUnitCompletionContract({
      contract: {
        unit_id: unitId,
        execution_mode: 'dynamic_event',
        advance_trigger: advanceTrigger,
        visual_settle_trigger: visualSettleTrigger,
        failure_policy: mode === 'throw' ? 'throw' : 'warn',
      },
      observed: {
        authorizingEventReceived: authorizingEventReceived === true,
        visualSettled: visualSettled === true && !overrun,
      },
      context: contractContext,
      emitTelemetry: (event, payload = {}) =>
        this.emitTimeoutContractTelemetry(turnData, event, payload),
      logger,
    });
    if (mode === 'throw' && overrun) {
      throw new Error(
        `[TIMEOUT contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
      );
    }
  }

  resolveTipContractMode() {
    const raw = String(
      (typeof window !== 'undefined' ? window.UESS_TIP_CONTRACT_MODE : null) ?? 'observe'
    )
      .trim()
      .toLowerCase();
    if (raw === 'off' || raw === 'observe' || raw === 'warn' || raw === 'throw') return raw;
    return 'observe';
  }

  getTipBudgetGameSeconds(kind = 'jump') {
    const scope = typeof window !== 'undefined' ? window : globalThis;
    const raw =
      kind === 'jump'
        ? Number(scope?.UESS_TIP_JUMP_MAX_GAME_SECONDS)
        : Number(scope?.UESS_TIP_CONTROL_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return kind === 'jump' ? 2 : 2;
  }

  emitTipContractTelemetry(turnData, event, payload = {}) {
    this.scene?.events?.emit?.('animTelemetry', {
      event,
      branchKind: 'tip_phase_contract',
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: this.scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? this.scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    });
  }

  enforceTipUnitContract({
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
    const mode = this.resolveTipContractMode();
    if (mode === 'off') return;
    const clockSecondMs = this.scene?.gameClock?.getState?.().tickMs || 350;
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
      this.emitTipContractTelemetry(turnData, 'tip_phase_clock_overrun', {
        unitId,
        ...contractContext,
      });
    }
    const logger =
      mode === 'observe'
        ? {
            warn: () => {},
          }
        : console;
    enforceUnitCompletionContract({
      contract: {
        unit_id: unitId,
        execution_mode: 'dynamic_event',
        advance_trigger: advanceTrigger,
        visual_settle_trigger: visualSettleTrigger,
        failure_policy: mode === 'throw' ? 'throw' : 'warn',
      },
      observed: {
        authorizingEventReceived: authorizingEventReceived === true,
        visualSettled: visualSettled === true && !overrun,
      },
      context: contractContext,
      emitTelemetry: (event, payload = {}) =>
        this.emitTipContractTelemetry(turnData, event, payload),
      logger,
    });
    if (mode === 'throw' && overrun) {
      throw new Error(
        `[TIP contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
      );
    }
  }

  /**
   * Initialize default animation handlers
   * These will be replaced by the new simplified handlers
   */
  initializeDefaultHandlers() {
    // For now, we'll use the existing handlers as fallbacks
    // This ensures backward compatibility during transition
    this.animationHandlers.set('FREE_THROW', this.handleFreeThrow.bind(this));
    this.animationHandlers.set('SIDE_INBOUND', this.handleSideInbound.bind(this));
    this.animationHandlers.set('BASELINE_INBOUND', this.handleBaselineInbound.bind(this));
    this.animationHandlers.set('TURNOVER', this.handleTurnover.bind(this));
    this.animationHandlers.set('FAST_BREAK', this.handleFastBreak.bind(this));
    this.animationHandlers.set('SHOT_ATTEMPT', this.handleShotAttempt.bind(this));
    this.animationHandlers.set('REBOUND', this.handleRebound.bind(this));
    this.animationHandlers.set('PASS', this.handlePass.bind(this));
    this.animationHandlers.set('HCO', this.handleDefault.bind(this)); // ✅ HCO with animations uses skeleton
    this.animationHandlers.set('FOUL', this.handleDefault.bind(this)); // ✅ FOUL with animations uses skeleton
    this.animationHandlers.set('CHARGE', this.handleDefault.bind(this)); // ✅ CHARGE (offensive foul) same as FOUL → skeleton animation, no shot
    this.animationHandlers.set('DEAD_BALL', this.handleDefault.bind(this)); // ✅ DEAD_BALL with animations uses skeleton
    this.animationHandlers.set('DEAD BALL', this.handleDefault.bind(this)); // ✅ FIX: Backend sends "DEAD BALL" with space, not underscore
    this.animationHandlers.set('STEAL', this.handleSteal.bind(this)); // ✅ STEAL uses hybrid handler (skeleton + steal action)
    this.animationHandlers.set('DEFAULT', this.handleDefault.bind(this));
    // ✅ PHASE 2.6: Add handlers for PUTBACK and OPENING_TIP
    this.animationHandlers.set('PUTBACK_MAKE', this.handlePutback.bind(this));
    this.animationHandlers.set('PUTBACK_MISS', this.handlePutback.bind(this));
    this.animationHandlers.set('OREB_KICKOUT', this.handlePutback.bind(this));
    this.animationHandlers.set('OPENING_TIP', this.handleOpeningTip.bind(this));
    // ✅ PHASE 2.6: Add handler for DEFENSIVE_STOP
    this.animationHandlers.set('DEFENSIVE_STOP', this.handleDefensiveStop.bind(this));
    // ✅ TIMEOUT: Add handler for TIMEOUT turns
    this.animationHandlers.set('TIMEOUT', this.handleTimeout.bind(this));
    // ✅ Phase 4: Final Turn — FINAL_HOLD (clock out, quarter end) and Final Turn shot (alignment then shot)
    this.animationHandlers.set('FINAL_HOLD', this.handleFinalHold.bind(this));
    this.animationHandlers.set('FINAL_TURN_SHOT', this.handleFinalTurnShot.bind(this));
  }

  /**
   * UESS schema playback (`animationPlayback.playTurn`). Returns true when
   * steps were rendered; false when this turn should use a legacy handler.
   */
  async runSchemaPlaybackTurn(turnData, context = {}) {
    const steps = turnData?.animation_steps;
    if (!Array.isArray(steps) || steps.length === 0) {
      return false;
    }
    const currentTurnNorm = String(turnData?.current_turn || "").toUpperCase();
    const MIGRATED_FB_PLAYS = new Set(["covert_release", "rim_runner", "triangle", "after_steal"]);
    const isMigratedFbVariant =
      currentTurnNorm === "FAST_BREAK"
      && MIGRATED_FB_PLAYS.has(turnData?.fast_break_play);
    if (currentTurnNorm === "FAST_BREAK" && !isMigratedFbVariant) {
      return false;
    }

    const { playTurn, dispatchTurnStop } = await import("./animationPlayback.js?v=uess-timeline-probes-1");
    const sprites = context.playerSprites
      || this.playerSprites
      || this.scene?.playerSprites
      || {};
    const ballSprite = context.ballSprite || this.scene?.ballSprite;
    if (this.scene) {
      this.scene.__uessTracePlayback = true;
    }
    const isFinalTurnShot = this._isFinalTurnSchemaShot(turnData);
    let stepsToPlay = steps;

    console.warn("[UESS PLAYBACK] schema:enter", {
      turnIndex: turnData?.index ?? this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      currentTurn: turnData?.current_turn ?? null,
      nextPlayType: turnData?.next_play_type ?? null,
      steps: steps.length,
      finalTurnShot: isFinalTurnShot,
      spriteCount: Object.keys(sprites || {}).length,
      hasBallSprite: Boolean(ballSprite),
      ballVisible: ballSprite?.visible ?? null,
      isPaused: this.scene?.isPaused ?? null,
      skipToEnd: this.scene?.skipToEnd ?? null,
    });

    if (isFinalTurnShot) {
      const { runFinalTurnAlignment } = await import('./turnAnimation.js');
      await runFinalTurnAlignment({
        scene: this.scene,
        playerSprites: sprites,
        ballSprite,
        turnData,
      });
      await this._runFinalTurnStep0EntryPassIfNeeded(turnData, sprites, ballSprite);
      await this._holdFinalTurnBallUntilShotWindow(turnData);
      if (steps.length > 1) {
        stepsToPlay = steps.slice(1);
      }
    }

    const turnStop = await playTurn(
      this.scene,
      stepsToPlay,
      sprites,
      ballSprite,
      { turnData },
    );
    if (turnStop) {
      await dispatchTurnStop(this.scene, turnStop, {
        sprites,
        ballSprite,
        turnData,
      });
    }
    console.warn("[UESS PLAYBACK] schema:exit", {
      turnIndex: turnData?.index ?? this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      currentTurn: turnData?.current_turn ?? null,
      turnStop: turnStop ?? null,
      ballVisible: ballSprite?.visible ?? null,
      isPaused: this.scene?.isPaused ?? null,
      skipToEnd: this.scene?.skipToEnd ?? null,
    });

    // NOTE: legacy `_maybeRunDiscreteDrebOutletLeadIn` removed — it called
    // `runDefensiveReboundSetup` (legacy outlet pass / handoff / walk-up)
    // AFTER the schema DREB turn. With the schema DREB turn now handling
    // rebound capture and the HCO entry orchestrator handling the
    // BH → PG handoff + walk-up directly, this lead-in caused double
    // execution (legacy outlet pass then schema handoff teleporting players
    // back). The helper method is retained below so the function symbol
    // remains importable in case any test/legacy caller still references
    // it, but the schema playback path no longer invokes it.

    // §14.7 — HCT batted-out-of-bounds polish. The schema steps render the
    // players (and the defensive collapse on the passer), but the schema
    // pipeline can't fly a deflected ball off the court. After the steps
    // settle, fly the ball passer→contact→nearest sideline by reusing Rim
    // Runner's imperative OOB ball-send (Path B). Gated on `turnData.bat_oob`.
    if (turnData?.bat_oob) {
      await this._runHctBatOobBallSend(turnData, sprites, ballSprite);
    } else if (turnData?.rim_runner_bat_oob) {
      await this._runSchemaBatOobBallSend(turnData, stepsToPlay, sprites, ballSprite);
    }

    if (isFinalTurnShot && turnData?.quarter_ends_after) {
      await this._finishFinalTurnQuarterEnd(turnData, context);
    }

    return true;
  }

  /**
   * Schema Rim Runner / Triangle bat-OOB: players move via steps; overlay the
   * shared deflection ball path using step metadata contact/oob coords.
   */
  async _runSchemaBatOobBallSend(turnData, steps, sprites = {}, ballSprite = null) {
    const scene = this.scene;
    const ball = ballSprite || scene?.ballSprite;
    if (!scene || !ball || !Array.isArray(steps)) {
      return;
    }

    let contactGrid = null;
    let oobGrid = null;
    let defId = turnData?.defender_id ?? turnData?.defenderId ?? null;
    let approachFromGrid = null;

    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const meta = steps[i]?.start?.advance_trigger?.metadata;
      if (!meta?.contact_coords || !meta?.oob_coords) {
        continue;
      }
      contactGrid = meta.contact_coords;
      oobGrid = meta.oob_coords;
      if (meta.to_player_id != null) {
        defId = meta.to_player_id;
      }
      const fromId = meta.from_player_id;
      if (fromId != null && steps[i]?.start?.coords?.[String(fromId)]) {
        approachFromGrid = steps[i].start.coords[String(fromId)];
      }
      break;
    }

    if (!contactGrid || !oobGrid) {
      return;
    }

    const width = scene.game?.config?.width ?? 1229;
    const height = scene.game?.config?.height ?? 768;
    const defSp = defId != null ? sprites[String(defId)] : null;
    const { animateBattedBallOutOfBounds } = await import("./batOobAnimation.js");

    await animateBattedBallOutOfBounds(scene, {
      contactGrid,
      oobGrid,
      approachFromGrid,
      defSprite: defSp,
      width,
      height,
    });
  }

  /**
   * §14.7 — imperative ball-send for an HCT batted-out-of-bounds pass.
   * Reuses Rim Runner's OOB helpers (animateBallToPosition + the
   * nearest-sideline resolver): the deflector (if known) slides onto the
   * contact point, then the ball flies passer→contact→nearest sideline.
   * No-op (safe) if geometry/sprites are missing — the dead-ball / side
   * inbound finalize still runs normally.
   */
  async _runHctBatOobBallSend(turnData, sprites = {}, ballSprite = null) {
    const scene = this.scene;
    const ball = ballSprite || scene?.ballSprite;
    const contact = turnData?.bat_oob_contact;
    if (
      !scene
      || !ball
      || !contact
      || typeof contact.x !== "number"
      || typeof contact.y !== "number"
    ) {
      return;
    }

    const width = scene.game?.config?.width ?? 1229;
    const height = scene.game?.config?.height ?? 768;

    const approachFromGrid = ball?.x != null && ball?.y != null
      ? {
          x: (ball.x / width) * 100,
          y: 50 - (ball.y / height) * 50,
        }
      : null;

    let gridToPixels;
    let tweenPlayerTo;
    let resolveNearestOutOfBoundsGrid;
    try {
      [{ gridToPixels }, { tweenPlayerTo }, { resolveNearestOutOfBoundsGrid }] = await Promise.all([
        import("../utils/gridToPixels.js"),
        import("./ballTween.js"),
        import("./fastBreak.js"),
      ]);
    } catch (err) {
      console.warn("[HCT BAT_OOB] helper import failed; skipping ball-send", err);
      return;
    }

    const contactPx = gridToPixels(contact.x, contact.y, width, height);

    // Slide the deflecting defender onto the contact point so the bat reads as
    // a defender knocking it away (optional — skipped if the sprite is absent).
    const defId =
      turnData?.bat_oob_deflector_id != null
        ? String(turnData.bat_oob_deflector_id)
        : null;
    const defSp = defId ? sprites[defId] : null;
    if (defSp && typeof tweenPlayerTo === "function") {
      try {
        const { getPlayerDuration } = await import("./turnAnimation.js");
        await tweenPlayerTo(scene, defSp, contactPx, {
          duration: getPlayerDuration(defSp, contactPx.x, contactPx.y, true),
          easing: "Quad.easeOut",
        });
      } catch (err) {
        // Defender slide is cosmetic — never block the ball-send on it.
      }
    }

    const oobGrid = resolveNearestOutOfBoundsGrid(contact);
    const { animateBattedBallOutOfBounds } = await import("./batOobAnimation.js");

    await animateBattedBallOutOfBounds(scene, {
      contactGrid: contact,
      oobGrid,
      approachFromGrid,
      defSprite: defSp,
      width,
      height,
    });
  }

  /**
   * Post-schema hooks for FREE_THROW (announcements, scroll, pressure after final make).
   * Rebound capture / outlet are discrete DREB / OREB turns — not embedded here.
   */
  async _finishSchemaFreeThrowTurn(turnData, context = {}) {
    const { getBallHandlerIdFromTurn, updateActivePlayers } = await import(
      "../utils/activePlayerDisplay.js"
    );
    const shooterId = getBallHandlerIdFromTurn(turnData, 0);
    const sprites =
      context.playerSprites || this.playerSprites || this.scene?.playerSprites;
    if (shooterId && sprites) {
      updateActivePlayers(
        shooterId,
        null,
        this.scene?.simData?.home_team_id,
        sprites,
      );
    }

    const { appendToTextScroll } = await import("../utils/textScroll.js");
    appendToTextScroll(turnData?.text || "Free throw attempt");

    const attempt = (turnData?.attempts || [])[0];
    const isMake = String(attempt || "").toUpperCase() === "MAKE";
    const ftRemaining = Number(turnData?.free_throws_remaining ?? 0);
    const isFinal = ftRemaining <= 0;

    if (isMake) {
      const { announceGameEvent } = await import("../utils/gameAnnouncements.js");
      announceGameEvent("FT_MAKE", turnData, this.scene, {
        shooterId: turnData?.shooter_id ?? shooterId,
      });
      if (isFinal) {
        if (turnData?.next_defensive_setup === "FCP") {
          announceGameEvent("PRESSURE_FCP", turnData, this.scene);
        } else if (turnData?.next_defensive_setup === "HCT") {
          announceGameEvent("PRESSURE_HCT", turnData, this.scene);
        }
      }
    }

    if (turnData?.quarter_ends_after) {
      if (context.onUpdate) context.onUpdate({ clock: "0:00" });
      const animationConfig = (await import("./animation_config.js")).default;
      const holdMs = animationConfig?.finalTurn?.holdFinalShotMs ?? 3000;
      await new Promise((resolve) => setTimeout(resolve, holdMs));
    }
  }

  /**
   * Main entry point for all animations
   * Routes turn data to the appropriate handler
   */
  async processTurn(turnData, context = {}) {
    // ✅ COMMENTED OUT: Redundant guard - AnimationRouter already prevents concurrent calls
    // AnimationRouter.processTurn() queues turns if already processing, and uses await,
    // so AnimationEngine.processTurn() will never be called concurrently.
    // If unforeseen issues arise, uncomment this guard.
    // if (this.isProcessing) {
    //   console.warn('AnimationEngine: Already processing a turn, skipping');
    //   return;
    // }

    this.isProcessing = true;
    ensureConsistentHeartbeat(this.scene, context.playerSprites || this.playerSprites || this.scene?.playerSprites || null);

    try {
      // Processing (log removed)

      // SS&S animation refactor: HCO, HCT, and DREB turns route through
      // the unified step-based playback engine when their backend payload
      // carries `animation_steps`. FAST_BREAK is gated per-variant to avoid
      // routing un-migrated variants (Triangle / After Steal) through the
      // new engine prematurely — currently Covert Release and Rim Runner
      // are migrated. Other turn types fall through to the legacy handler
      // dispatch below. See:
      // _documentation_master/projects/Animation_System_Updated.md
      const MIGRATED_FB_PLAYS = new Set(["covert_release", "rim_runner", "triangle", "after_steal"]);
      const isMigratedFbVariant =
        turnData?.current_turn === "FAST_BREAK"
        && MIGRATED_FB_PLAYS.has(turnData?.fast_break_play);
      const hasAnimationSteps = Array.isArray(turnData?.animation_steps)
        && turnData.animation_steps.length > 0;

      // FB diagnostic: log every Fast Break turn at the dispatch point so we
      // can confirm which variant fired and which rendering path it took.
      if (turnData?.current_turn === "FAST_BREAK") {
        const willUseNewEngine = hasAnimationSteps && isMigratedFbVariant;
        const _burstPhase = turnData?.roles?.rim_runner_burst_phase || {};
        console.warn(
          "🏀 [FB DISPATCH]",
          {
            fast_break_play: turnData?.fast_break_play ?? "(none)",
            result_type: turnData?.result_type,
            fast_break_flag: turnData?.fast_break,
            has_animation_steps: hasAnimationSteps,
            steps_count: hasAnimationSteps ? turnData.animation_steps.length : 0,
            path: willUseNewEngine ? "NEW_PLAYBACK_ENGINE" : "LEGACY_HANDLER",
            skip_outlet_pass: _burstPhase.skip_outlet_pass ?? "(not set)",
            outlet_passer_id: _burstPhase.outlet_passer_id ?? turnData?.roles?.outlet_passer ?? "(none)",
            outlet_receiver_id: _burstPhase.outlet_receiver_id ?? turnData?.roles?.outlet_receiver ?? "(none)",
          }
        );
      }

      // BIP diagnostic: log every BIP at the dispatch point so we can confirm
      // unified vs legacy routing during the BIP migration.
      if (turnData?.current_turn === "BASELINE_INBOUND") {
        console.warn(
          "🏠 [BIP DISPATCH]",
          {
            result_type: turnData?.result_type,
            next_play_type: turnData?.next_play_type,
            has_animation_steps: hasAnimationSteps,
            steps_count: hasAnimationSteps ? turnData.animation_steps.length : 0,
            path: hasAnimationSteps ? "NEW_PLAYBACK_ENGINE" : "LEGACY_HANDLER",
          }
        );
        // Pressure-state plumbing: legacy handleBaselineInbound sets
        // scene.currentPressureType / pressureSequenceActive so subsequent
        // FCP/HCT turns render in the right state. Replicate here so the
        // unified path doesn't drop the contract.
        const hasFCPHCTSetup = turnData?.next_defensive_setup === "FCP"
          || turnData?.next_defensive_setup === "HCT";
        if (hasFCPHCTSetup) {
          this.scene.currentPressureType = turnData.next_defensive_setup;
          this.scene.pressureSequenceActive = true;
        } else {
          this.scene.currentPressureType = null;
          this.scene.pressureSequenceActive = false;
        }
      }

      // SIP diagnostic: log SIDE_INBOUND turns at the dispatch point so we
      // can confirm new playback engine vs. legacy routing during the SIP
      // migration. No pressure-state plumbing — SIP always transitions to HCO.
      if (turnData?.current_turn === "SIDE_INBOUND") {
        console.warn(
          "🏠 [SIP DISPATCH]",
          {
            result_type: turnData?.result_type,
            next_play_type: turnData?.next_play_type,
            has_animation_steps: hasAnimationSteps,
            steps_count: hasAnimationSteps ? turnData.animation_steps.length : 0,
            path: hasAnimationSteps ? "NEW_PLAYBACK_ENGINE" : "LEGACY_HANDLER",
          }
        );
      }

      if (
        turnData?.current_turn === "FREE_THROW"
        || turnData?.result_type === "FREE_THROW"
      ) {
        console.warn("🏀 [FT DISPATCH]", {
          result_type: turnData?.result_type,
          attempts: turnData?.attempts,
          free_throws_remaining: turnData?.free_throws_remaining,
          rebound_type: turnData?.rebound_type,
          next_play_type: turnData?.next_play_type,
          has_animation_steps: hasAnimationSteps,
          steps_count: hasAnimationSteps ? turnData.animation_steps.length : 0,
          path: hasAnimationSteps ? "NEW_PLAYBACK_ENGINE" : "LEGACY_HANDLER",
        });
      }

      const currentTurnNorm = String(turnData?.current_turn || "").toUpperCase();
      const resultTypeNorm = String(turnData?.result_type || "").toUpperCase();
      // Any turn that carries animation_steps uses schema playback except
      // un-migrated Fast Break variants (Triangle / After Steal). Do not
      // gate on current_turn alone — MAKE/MISS HCO rows must not fall through
      // to ShotAnimationSystem / playTurnAnimation when steps are present.
      const isUnmigratedFastBreak =
        currentTurnNorm === "FAST_BREAK" && !isMigratedFbVariant;
      const useNewPlaybackEngine = hasAnimationSteps && !isUnmigratedFastBreak;

      if (turnData?.current_turn === "HCO") {
        console.warn("🏠 [HCO DISPATCH]", {
          result_type: turnData?.result_type,
          current_turn: turnData?.current_turn,
          has_animation_steps: hasAnimationSteps,
          steps_count: hasAnimationSteps ? turnData.animation_steps.length : 0,
          path: useNewPlaybackEngine ? "NEW_PLAYBACK_ENGINE" : "LEGACY_HANDLER",
          has_hco_setup: Boolean(turnData?.hco_setup?.inbound_pass),
        });
      }

      if (useNewPlaybackEngine) {
        if (resultTypeNorm === "DREB" || currentTurnNorm === "DREB") {
          console.warn("[DREB OUTLET LEAD-IN] discrete DREB entered new playback (playTurn)", {
            current_turn: turnData?.current_turn,
            result_type: turnData?.result_type,
            next_play_type: turnData?.next_play_type,
            turn_index: turnData?.index ?? this.scene?.currentTurn,
            rebounderId: turnData?.rebounderId,
            steps: turnData?.animation_steps?.length ?? 0,
          });
        }
        await this.runSchemaPlaybackTurn(turnData, context);
        if (
          currentTurnNorm === "FREE_THROW"
          || resultTypeNorm === "FREE_THROW"
        ) {
          await this._finishSchemaFreeThrowTurn(turnData, context);
        }
        return;
      }

      if (hasAnimationSteps && isUnmigratedFastBreak) {
        console.warn(
          "[UESS DISPATCH] animation_steps present but Fast Break variant uses legacy handler",
          { fast_break_play: turnData?.fast_break_play },
        );
      }

      const isHcoFamily =
        currentTurnNorm === "HCO"
        || resultTypeNorm === "HCO"
        || (["MAKE", "MISS", "BLOCK"].includes(resultTypeNorm) && !turnData?.fast_break);
      if (isHcoFamily && !hasAnimationSteps) {
        console.warn(
          "[UESS DISPATCH] HCO-family turn has NO animation_steps — legacy playTurnAnimation / ShotAnimationSystem",
          {
            current_turn: turnData?.current_turn,
            result_type: turnData?.result_type,
            has_legacy_animations: Boolean(turnData?.animations?.length),
          },
        );
      }

      if (
        (resultTypeNorm === "DREB" || currentTurnNorm === "DREB") &&
        !hasAnimationSteps
      ) {
        console.warn(
          "[DREB OUTLET LEAD-IN] discrete DREB turn has NO animation_steps — falling through to legacy handler; outlet hook will NOT run",
          {
            current_turn: turnData?.current_turn,
            result_type: turnData?.result_type,
            next_play_type: turnData?.next_play_type,
            turn_index: turnData?.index ?? this.scene?.currentTurn,
          }
        );
      }

      // Determine the appropriate handler
      const handler = this.determineHandler(turnData);
      // Handler routing (log removed)

      // Execute the animation
      await handler(turnData, context);
      // Completed (log removed)

    } catch (error) {
      console.error('❌ AnimationEngine: Error processing turn', {
        error: error.message,
        stack: error.stack,
        result_type: turnData.result_type
      });
      throw error;
    } finally {
      // Keep heartbeat running consistently across turns; only full-cleanup on teardown.
      this.isProcessing = false;
    }
  }

  /**
   * After discrete DREB `animation_steps` playback, run half-court outlet lead-in when the
   * next route is HCO/HCT/FCP. Authority + get-back live on the prior MISS/BLOCK turn
   * (`dreb_outlet_pass`, `offense_getback`). Skips FAST_BREAK (outlet lives in FB sequence)
   * and `force_foul_after_dreb` on the shot turn.
   */
  async _maybeRunDiscreteDrebOutletLeadIn(turnData, context, sprites, ballSprite) {
    const tag = "[DREB OUTLET LEAD-IN]";
    if (turnData?._drebOutletLeadInDone) {
      console.warn(tag, "skip: already_done", {
        turn_index: turnData?.index ?? this.scene?.currentTurn,
        next_play_type: turnData?.next_play_type,
      });
      return;
    }

    const nextRaw = turnData?.next_play_type;
    const next = typeof nextRaw === "string" ? nextRaw.toUpperCase() : "";
    if (next === "FAST_BREAK") {
      console.warn(tag, "skip: next_is_FAST_BREAK", {
        turn_index: turnData?.index ?? this.scene?.currentTurn,
      });
      return;
    }
    if (!next || !["HCO", "HCT", "FCP"].includes(next)) {
      console.warn(tag, "skip: next_not_halfcourt_route", {
        next_play_type_raw: nextRaw,
        next_normalized: next || null,
        turn_index: turnData?.index ?? this.scene?.currentTurn,
      });
      return;
    }

    const scene = this.scene;
    const idx =
      typeof turnData?.index === "number"
        ? turnData.index
        : typeof scene?.currentTurn === "number"
          ? scene.currentTurn
          : null;

    const turnsArr = scene?.simData?.turns;
    const priorFromChain =
      context?.simData?.__priorAnimatedTurn ??
      scene?.simData?.__priorAnimatedTurn ??
      null;

    const isPriorShotMissFamily = (row) => {
      if (!row) return false;
      const rt = String(row.result_type || "").toUpperCase();
      if (rt === "MISS" || rt === "BLOCK") return true;
      if (rt !== "FREE_THROW") return false;
      const att = (row.attempts || [])[0];
      return (
        String(att || "").toUpperCase() === "MISS"
        && Number(row.free_throws_remaining ?? 0) <= 0
      );
    };

    let missTurn = null;
    if (priorFromChain && isPriorShotMissFamily(priorFromChain)) {
      missTurn = priorFromChain;
    } else if (
      Array.isArray(turnsArr) &&
      typeof idx === "number" &&
      idx >= 1 &&
      idx - 1 < turnsArr.length
    ) {
      const cand = turnsArr[idx - 1];
      if (isPriorShotMissFamily(cand)) {
        missTurn = cand;
      }
    }

    if (!missTurn) {
      console.warn(tag, "skip: prior_turn_not_MISS_BLOCK_FT", {
        turnData_index: turnData?.index,
        scene_currentTurn: scene?.currentTurn,
        resolved_idx: idx,
        has_prior_chain:
          !!priorFromChain && !!priorFromChain.result_type,
        prior_chain_result_type: priorFromChain?.result_type ?? null,
        turns_batch_len: turnsArr?.length ?? 0,
      });
      return;
    }
    if (missTurn.force_foul_after_dreb) {
      console.warn(tag, "skip: force_foul_after_dreb on shot turn", { idx });
      return;
    }

    const playerSprites =
      sprites ||
      context?.playerSprites ||
      this.playerSprites ||
      scene?.playerSprites ||
      {};
    const bs =
      ballSprite || context?.ballSprite || scene?.ballSprite;

    console.warn(tag, "invoke runDefensiveReboundSetup", {
      rebounderId: turnData.rebounderId,
      nextPlayType: nextRaw || next,
      dreb_turn_index: idx,
      miss_turn_index: idx - 1,
      miss_result_type: missTurn.result_type,
      has_dreb_outlet_pass: !!missTurn.dreb_outlet_pass,
    });

    const { runDefensiveReboundSetup } = await import("./turnAnimation.js");
    try {
      await runDefensiveReboundSetup({
        scene,
        ballSprite: bs,
        playerSprites,
        rebounderId: turnData.rebounderId,
        nextPlayType: nextRaw || next,
        turnData: missTurn,
        authorityTurnData: missTurn,
      });
    } catch (err) {
      console.error(tag, "runDefensiveReboundSetup threw", {
        message: err?.message,
        rebounderId: turnData.rebounderId,
      });
      throw err;
    }
    turnData._drebOutletLeadInDone = true;
    console.warn(tag, "complete", { dreb_turn_index: idx });
  }

  /**
   * Determine which handler to use for a turn
   */
  determineHandler(turnData) {
    // Fast break detection (highest priority)
    // ✅ FIX: Only check fast_break flag and result_type - next_play_type indicates what comes NEXT, not what this turn is
    // The backend should set fast_break=true on the actual fast break turn, not rely on next_play_type
    // ✅ CRITICAL: Check fast_break flag FIRST, even for DEFENSIVE_STOP turns (fast break defensive stops have fast_break=true)
    // ✅ FIX: Also check for string "true" in case JSON serialization converts boolean to string
    const isFastBreak = turnData.fast_break === true || 
                        turnData.fast_break === "true" ||
                        turnData.result_type === "FAST_BREAK";
    if (isFastBreak) {
      return this.animationHandlers.get('FAST_BREAK');
    }

    // ✅ Phase 4: Final Turn — route FINAL_HOLD and Final Turn shot to dedicated handlers
    if (turnData.result_type === 'FINAL_HOLD') {
      return this.animationHandlers.get('FINAL_HOLD');
    }
    if (turnData.final_turn === true && this.isShotAttempt(turnData)) {
      return this.animationHandlers.get('FINAL_TURN_SHOT');
    }

    // ✅ SS&S: FCP/HCT routes through same handlers as HCO
    // Skeletons are different (press break vs playcall), but animation system is the same
    // FCP/HCT shots → SHOT_ATTEMPT handler (same as HCO)
    // FCP/HCT other results → their respective handlers (FOUL, TURNOVER, etc.)
    // No special routing needed - let normal handler detection work

    // Specific result types (check handlers map first)
    if (turnData.result_type && this.animationHandlers.has(turnData.result_type)) {
      // ✅ DEBUG: Log when routing to specific handler (especially DEFENSIVE_STOP and DEAD_BALL)
      if (turnData.result_type === "DEFENSIVE_STOP" || turnData.result_type === "DEAD_BALL" || turnData.result_type === "DEAD BALL") {
        console.log(`🔍 [${turnData.result_type} ROUTING] Found in handlers map, routing to specific handler`, {
          result_type: turnData.result_type,
          has_animations: !!turnData.animations?.length,
          handler_exists: this.animationHandlers.has(turnData.result_type)
        });
      }
      const handler = this.animationHandlers.get(turnData.result_type);
      return handler;
    }
    
    // ✅ DEBUG: Log when result_type NOT found in handlers map
    if (turnData.result_type === "DEAD_BALL" || turnData.result_type === "DEAD BALL") {
      console.warn(`⚠️ [${turnData.result_type} ROUTING] NOT found in handlers map!`, {
        result_type: turnData.result_type,
        has_animations: !!turnData.animations?.length,
        handlers_keys: Array.from(this.animationHandlers.keys()),
        will_fall_through_to_shot_detection: true
      });
    }

    // ✅ DEBUG: Exclude non-shot result types from shot attempt detection
    // FOUL, FREE_THROW, TURNOVER, etc. should not be treated as shot attempts
    // ✅ FIX: Add STEAL and DEAD_BALL to non-shot types
    const nonShotResultTypes = new Set([
      "FOUL", "FREE_THROW", "TURNOVER", "DEAD_BALL", "DEAD_BALL_TURNOVER",
      "SIDE_INBOUND", "BASELINE_INBOUND", "PUTBACK_MAKE", 
      "PUTBACK_MISS", "OREB_KICKOUT", "DEFENSIVE_STOP", "OPENING_TIP",
      "HCO", // ✅ FIX: HCO turns are setup turns, not shot attempts
      "STEAL" // ✅ FIX: STEAL is not a shot attempt
    ]);
    
    
    // Shot attempt detection (only if not a non-shot result type)
    if (!nonShotResultTypes.has(turnData.result_type) && this.isShotAttempt(turnData)) {
      return this.animationHandlers.get('SHOT_ATTEMPT');
    }

    // Rebound detection
    if (this.isRebound(turnData)) {
      return this.animationHandlers.get('REBOUND');
    }

    // Pass detection
    if (this.isPass(turnData)) {
      return this.animationHandlers.get('PASS');
    }

    // Default handler
    return this.animationHandlers.get('DEFAULT');
  }

  /**
   * Check if this is a shot attempt
   */
  isShotAttempt(turnData) {
    return turnData.result_type === "MAKE" || 
           turnData.result_type === "MISS" ||
           turnData.result_type === "BLOCK" ||
           turnData.shooter ||
           turnData.shot_score !== undefined;
  }

  /**
   * Check if this is a rebound
   */
  isRebound(turnData) {
    return turnData.rebounderId ||
           turnData.rebound_type ||
           turnData.result_type === "OREB" ||
           turnData.result_type === "DREB";
  }

  /**
   * Check if this is a pass
   */
  isPass(turnData) {
    return turnData.passer_id ||
           turnData.receiver_id ||
           turnData.pass_type ||
           turnData.result_type === "PASS" ||
           (turnData.result_type === "MAKE" && turnData.pass_type);
  }

  /**
   * Animation Handlers
   * Each handler is responsible for a specific type of animation
   */

  async handleFreeThrow(turnData, context) {
    const hasSchemaSteps =
      Array.isArray(turnData?.animation_steps)
      && turnData.animation_steps.length > 0;
    if (hasSchemaSteps) {
      console.warn(
        "AnimationEngine: FREE_THROW has animation_steps — should use schema path in processTurn",
      );
      await this._finishSchemaFreeThrowTurn(turnData, context);
      return;
    }

    console.log('AnimationEngine: Handling free throw with new FreeThrowAnimationSystem');
    
    // ✅ PHASE 2.6: Update active player display (moved from animateGameTurns.js)
    const { getBallHandlerIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
    const shooterId = getBallHandlerIdFromTurn(turnData, 0);
    if (shooterId && context.playerSprites) {
      updateActivePlayers(shooterId, null, this.scene.simData?.home_team_id, context.playerSprites);
    }
    
    // Use new free throw animation system if available
    if (this.freeThrowSystem) {
      await this.freeThrowSystem.processFreeThrow(turnData);
    } else {
      // Fallback to existing system
      console.warn('AnimationEngine: FreeThrowAnimationSystem not available, using fallback');
      const { runFreeThrowSequence } = await import('./freeThrow.js');
      await runFreeThrowSequence(this.scene, {
        playerSprites: context.playerSprites,
        ballSprite: context.ballSprite,
        turnData: turnData,
        onUpdate: context.onUpdate,
        ftContext: turnData.ftContext
      });
    }
    
    // ✅ PHASE 2.6: Display free throw result text (moved from animateGameTurns.js)
    const { appendToTextScroll } = await import('../utils/textScroll.js');
    appendToTextScroll(turnData.text || "Free throw attempt");
    
    // Final play of quarter (e.g. Final Turn shooting foul → FTs): show 0:00, hold then quarter end (no BIP)
    if (turnData.quarter_ends_after) {
      if (context.onUpdate) context.onUpdate({ clock: '0:00' });
      const animationConfig = (await import('./animation_config.js')).default;
      const holdMs = animationConfig?.finalTurn?.holdFinalShotMs ?? 3000;
      await new Promise(resolve => setTimeout(resolve, holdMs));
    }
    // Note: onUpdate is already called inside runFreeThrowSequence for each FT attempt
    // Do NOT call it again here or stats will be double counted
  }

  async handleSideInbound(turnData, context) {
    if (this.passSystem) {
      await this.passSystem.processPass(turnData, context);
      console.log('AnimationEngine: PassAnimationSystem completed for SIDE_INBOUND');
    } else {
      console.warn('AnimationEngine: PassAnimationSystem not available, using fallback');
      // Fallback to old system
      const { runSideInboundSetup } = await import('./turnAnimation.js');
      await runSideInboundSetup({
        scene: this.scene,
        ballSprite: context.ballSprite,
        playerSprites: context.playerSprites,
        turnData: turnData
      });
    }
    // Mark inbound source so next HCO lead-in can validate source-scoped contract.
    this.scene._previousTurnWasInbound = true;
    this.scene._previousInboundTurnType = 'SIDE_INBOUND';
  }

  async handleBaselineInbound(turnData, context) {
    // ✅ PHASE 2.6: Set FCP/HCT state when pressure setup detected (moved from animateGameTurns.js)
    // This is the single source of truth for pressure state - replaces complex flag detection
    const hasFCPHCTSetup = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    if (hasFCPHCTSetup) {
      this.scene.currentPressureType = turnData.next_defensive_setup; // "FCP" or "HCT"
      this.scene.pressureSequenceActive = true;
      // ✅ NEW APPROACH: Animate the inbound pass HERE (using skeleton step 0 positions)
      // Skeleton will start from old step 1 (after the pass is complete)
    } else {
      // Clear state if no pressure setup (normal inbound)
      this.scene.currentPressureType = null;
      this.scene.pressureSequenceActive = false;
    }
    
    // ✅ PHASE 2.6: Animate all players to their positions using distance-based duration
    // This ensures consistent speed matching HCO step movements
    // (moved from animateGameTurns.js)
    const { tweenPlayerTo } = await import('./ballTween.js');
    const { gridToPixels } = await import('../utils/gridToPixels.js');
    const { getPlayerDuration } = await import('./turnAnimation.js');
    
    await Promise.all(
      (turnData.animations || []).map(anim => {
        const sprite = context.playerSprites[anim.playerId];
        if (!sprite || !anim.movement || anim.movement.length < 2) return Promise.resolve();
        
        const endStep = anim.movement[anim.movement.length - 1];
        const endPixels = gridToPixels(
          endStep.coords.x, 
          endStep.coords.y, 
          this.scene.game.config.width, 
          this.scene.game.config.height
        );
        
        // Use distance-based duration for consistent speed (not transition - should match inbound setup speed)
        const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y, false);
        
        // tweenPlayerTo returns a Promise that resolves when complete
        return tweenPlayerTo(this.scene, sprite, endPixels, { duration, easing: 'Linear' });
      })
    );
    
    // ✅ NEW APPROACH: For FCP/HCT, continue to animate the inbound pass (don't skip)
    // Players are now at skeleton step 0 positions, pass animation creates the hold beat
    // Skeleton will start from old step 1 (new step 0) after this turn completes
    
    // ✅ FIX: Animate the inbound pass after positioning players
    // Use PassAnimationSystem directly since this.passSystem might not be initialized
    const { PassAnimationSystem: PassSys } = await import('./PassAnimationSystem.js');
    const passSystem = this.passSystem || new PassSys(this.scene, null, null, context.playerSprites);
    await passSystem.executeInboundSequence(turnData, context);
    
    // ✅ CRITICAL FIX: Explicitly wait for pass animation to fully complete
    // This ensures BIP animation finishes before the next turn (HCT/FCP) starts
    // Check passInFlight flag and wait for passEnd event if needed
    if (this.scene.passInFlight) {
      const PASS_COMPLETION_POLL_MS = 25;
      const PASS_COMPLETION_GRACE_MS = 16;
      const PASS_COMPLETION_MAX_WAIT_MS = 600;
      // Wait for passInFlight to be cleared (indicates pass animation is complete)
      await new Promise((resolve) => {
        // If already cleared, resolve immediately
        if (!this.scene.passInFlight) {
          resolve();
          return;
        }
        
        // Otherwise, wait for passEnd event or check periodically
        const checkPassComplete = () => {
          if (!this.scene.passInFlight) {
            this.scene.events?.off('passEnd', onPassEnd);
            clearInterval(intervalId);
            resolve();
          }
        };
        
        const onPassEnd = () => {
          // Allow a single frame for pass cleanup to settle.
          setTimeout(() => {
            checkPassComplete();
          }, PASS_COMPLETION_GRACE_MS);
        };
        
        // Listen for passEnd event
        this.scene.events?.on('passEnd', onPassEnd);
        
        // Also poll periodically as a fallback (in case event doesn't fire)
        const intervalId = setInterval(checkPassComplete, PASS_COMPLETION_POLL_MS);
        
        // Safety timeout - short bound to avoid introducing long boundary stalls.
        setTimeout(() => {
          this.scene.events?.off('passEnd', onPassEnd);
          clearInterval(intervalId);
          console.warn('⚠️ [BIP] Pass completion timeout - proceeding anyway');
          resolve();
        }, PASS_COMPLETION_MAX_WAIT_MS);
      });
    }
    
    // ✅ PHASE 2.6: Transition to HalfCourt state (moved from animateGameTurns.js)
    const { safeTransition } = await import('../state/gameStateMachine.js');
    const { States } = await import('../state/gameStateMachine.js');
    safeTransition(this.scene.stateMachine, States.HalfCourt, 'after quarter start inbound');
    
    // ✅ PHASE 2.6: Mark that previous turn was inbound so HCO pre-step setup can use uncapped durations
    this.scene._previousTurnWasInbound = true;
    this.scene._previousInboundTurnType = 'BASELINE_INBOUND';
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handleTurnover(turnData, context) {
    console.log('AnimationEngine: Handling turnover');
    // Import and use existing turnover handler for now
    const { handleTurnover } = await import('./turnoverAdapter.js');
    await handleTurnover(this.scene, {
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnData: turnData,
      onUpdate: context.onUpdate
    });
  }

  async handleFastBreak(turnData, context) {
    // ✅ PHASE 2.6: Update active player display (moved from animateGameTurns.js)
    const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
    const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
    const defenderId = getDefenderIdFromTurn(turnData);
    if (ballHandlerId && context.playerSprites) {
      updateActivePlayers(ballHandlerId, defenderId, this.scene.simData?.home_team_id, context.playerSprites);
    }
    
    // Import and use existing fast break handler for now
    const { runFastBreakSequence } = await import('./fastBreak.js');
    await runFastBreakSequence({
      scene: this.scene,
      turnData: turnData,
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnIndex: context.turnIndex // ✅ PHASE 2.6: Pass turnIndex from context
    });
    
    // ✅ PHASE 2.6: Set flag if this was a shot turn (moved from animateGameTurns.js)
    if (turnData.result_type === "MAKE" || turnData.result_type === "MISS" || turnData.result_type === "BLOCK") {
      this.scene._previousTurnWasShot = true;
    }
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handlePutback(turnData, context) {
    if (
      turnData?.result_type === "OREB_KICKOUT"
      && (!Array.isArray(turnData?.animation_steps) || turnData.animation_steps.length === 0)
    ) {
      console.error(
        "[UESS CONTRACT] OREB_KICKOUT reached the legacy handler without animation_steps",
        {
          rebounderId: turnData?.rebounderId ?? null,
          pgId: turnData?.pgId ?? null,
          turn_index: turnData?.index ?? this.scene?.currentTurn ?? null,
        },
      );
      return;
    }
    // ✅ PHASE 2.6: Use existing handleOrebTurn function (moved from animateGameTurns.js)
    // OREB_KICKOUT is schema-only; this fallback handles putback outcomes.
    const { handleOrebTurn } = await import('./animateGameTurns.js');
    await handleOrebTurn(this.scene, {
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnData: turnData,
      onUpdate: context.onUpdate
    });
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handleTimeout(turnData, context) {
    const timeoutStartMs = Date.now();
    const enforceTimeoutOut = ({
      route,
      routeCommitted,
      visualSettled = true,
      contextExtra = {},
    } = {}) => {
      this.enforceTimeoutUnitContract({
        turnData,
        unitId: 'timeout.out.to_next',
        advanceTrigger: 'pending route committed',
        visualSettleTrigger: 'timeout exit settle complete',
        authorizingEventReceived: routeCommitted === true,
        visualSettled: visualSettled === true,
        unitStartMs: timeoutStartMs,
        maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
        context: {
          timeoutReason: turnData?.timeout_reason ?? null,
          route: route ?? null,
          ...contextExtra,
        },
      });
      if (this.resolveTimeoutContractMode() === 'throw' && routeCommitted !== true) {
        throw new Error(
          `[TIMEOUT contract] missing committed out route (reason=${turnData?.timeout_reason ?? "unknown"})`
        );
      }
    };
    console.log('⏸️ AnimationEngine: Handling timeout', {
      timeout_reason: turnData.timeout_reason,
      foul_out_player: turnData.foul_out_player,
      calling_team: turnData.timeout_calling_team
    });
    
    // ✅ TIMEOUT: Pause all tweens immediately when timeout is called
    let pauseBarrierSatisfied = true;
    if (this.scene.tweens) {
      try {
        this.scene.tweens.pauseAll();
      } catch (_) {
        pauseBarrierSatisfied = false;
      }
      console.log('⏸️ AnimationEngine: Paused all tweens for timeout');
    }
    // ✅ TIMEOUT: Set a flag to stop the main animation loop
    this.scene.timeoutCalled = true;
    this.enforceTimeoutUnitContract({
      turnData,
      unitId: 'timeout.phase.pause_barrier',
      advanceTrigger: 'timeout state committed',
      visualSettleTrigger: 'active tweens/flows paused to barrier',
      authorizingEventReceived: true,
      visualSettled: pauseBarrierSatisfied && this.scene.timeoutCalled === true,
      unitStartMs: timeoutStartMs,
      maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('pause'),
      context: {
        timeoutReason: turnData?.timeout_reason ?? null,
        timeoutCalled: this.scene.timeoutCalled === true,
        pauseBarrierSatisfied,
      },
    });
    
    // Append timeout text to text scroll
    if (turnData.text && this.scene.events) {
      this.scene.events.emit('textScroll', turnData.text);
    }
    
    // ✅ USER TIMEOUT: Skip navigation - showUserTimeoutPopup already handled it
    // User timeouts are handled by timeoutButtonManager.js:
    // 1. User presses timeout button → handleTimeoutButtonClick() is called
    // 2. API is called → showUserTimeoutPopup() displays popup with "Go To Timeout" button
    // 3. User clicks button → showTimeoutPopup() is called with computerTimeout=false
    // 4. AnimationEngine.handleTimeout() is called for the timeout turn
    // 5. We skip navigation here because user timeout navigation is handled by the popup button click
    if (turnData.timeout_reason === 'USER') {
      this.enforceTimeoutUnitContract({
        turnData,
        unitId: 'timeout.phase.resume_prepare',
        advanceTrigger: 'resume route/context committed',
        visualSettleTrigger: 'resume setup settled',
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: timeoutStartMs,
        maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
        context: {
          timeoutReason: 'USER',
          route: 'user_popup_managed',
        },
      });
      enforceTimeoutOut({
        route: 'user_popup_managed',
        routeCommitted: true,
        contextExtra: { gameIdPresent: true },
      });
      console.log('⏸️ USER TIMEOUT: Skipping navigation - already handled by timeoutButtonManager');
      return; // Don't navigate - showUserTimeoutPopup already handled it
    }

    // ✅ FOUL OUT: Always show foul-out popup and let it handle navigation (never fall through to computer timeout).
    // Use placeholder player if backend didn't send foul_out_player (contract: backend now always sends one).
    if (turnData.timeout_reason === 'FOUL_OUT') {
      const gameId = this.scene.gameId || this.scene.simData?.game_id;
      const rawPlayer = turnData.foul_out_player || { name: 'Unknown', player_id: null, team: null, photo: null };
      if (!turnData.foul_out_player) {
        console.warn('⚠️ [FOUL OUT] TIMEOUT turn has timeout_reason=FOUL_OUT but no foul_out_player; showing popup with placeholder.');
      }
      // Resolve fouled-out player from simData by id so we always show the player who fouled out (not the player who was fouled)
      const foulOutPlayerId = rawPlayer?.player_id ?? rawPlayer?.playerId;
      const player = (foulOutPlayerId && this.scene.simData?.players)
        ? (this.scene.simData.players.find(p => (p.playerId ?? p.player_id) === foulOutPlayerId) || rawPlayer)
        : rawPlayer;
      if (gameId) {
        let foulOutPopupAttempted = false;
        try {
          const { showFoulOutPopup } = await import('../utils/foulOutPopup.js');
          foulOutPopupAttempted = true;
          const responseData = turnData._responseData || {};
          const clock = responseData.clock || turnData.clock || this.scene.simData?.clock;
          const mode = this.scene.mode || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('mode') : null) || 'single';
          const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : { get: () => null };
          const tournamentId = urlParams.get?.('tournament_id') || null;
          const franchiseId = urlParams.get?.('franchise_id') || null;
          const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
          const homeId = this.scene.homeTeamId || urlParams.get?.('home_id');
          const awayId = this.scene.awayTeamId || urlParams.get?.('away_id');
          const myTeamSide = urlParams.get?.('my_team');
          const userTeamId = urlParams.get?.('user_team_id');
          const quarter = turnData.quarter ?? this.scene.quarter ?? 1;
          showFoulOutPopup({
            player,
            foulOutPlayerId: foulOutPlayerId,
            gameId,
            mode,
            quarter,
            clock,
            tournamentId,
            franchiseId,
            homeTeam,
            awayTeam,
            homeId,
            awayId,
            myTeamSide,
            userTeamId
          });
        } catch (err) {
          console.error('❌ FOUL OUT: Failed to show foul-out popup:', err);
        }
        this.enforceTimeoutUnitContract({
          turnData,
          unitId: 'timeout.phase.resume_prepare',
          advanceTrigger: 'resume route/context committed',
          visualSettleTrigger: 'resume setup settled',
          authorizingEventReceived: foulOutPopupAttempted,
          visualSettled: true,
          unitStartMs: timeoutStartMs,
          maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
          context: {
            timeoutReason: 'FOUL_OUT',
            route: 'foul_out_popup',
            gameIdPresent: true,
          },
        });
        enforceTimeoutOut({
          route: 'foul_out_popup',
          routeCommitted: true,
          contextExtra: { gameIdPresent: true },
        });
      } else {
        console.error('❌ FOUL OUT: Cannot show popup - game_id missing for navigation.');
        this.enforceTimeoutUnitContract({
          turnData,
          unitId: 'timeout.phase.resume_prepare',
          advanceTrigger: 'resume route/context committed',
          visualSettleTrigger: 'resume setup settled',
          authorizingEventReceived: false,
          visualSettled: false,
          unitStartMs: timeoutStartMs,
          maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
          context: {
            timeoutReason: 'FOUL_OUT',
            route: 'foul_out_popup',
            gameIdPresent: false,
          },
        });
        enforceTimeoutOut({
          route: 'foul_out_popup',
          routeCommitted: false,
          visualSettled: false,
          contextExtra: { gameIdPresent: false },
        });
      }
      return;
    }

    // ✅ COMPUTER TIMEOUT: Show popup first, then navigate on explicit button click
    const gameId = this.scene.gameId || this.scene.simData?.game_id;
    if (gameId) {
      // Import and call computer-timeout popup flow
      let computerPopupAttempted = false;
      try {
        const { showComputerTimeoutPopup } = await import('../utils/timeoutButtonManager.js');
        computerPopupAttempted = true;
        // ✅ UNIFIED: Extract clock/time_remaining from API response (same as user timeout)
        // The response from /api/simulate-turn includes clock and time_remaining
        // For computer timeouts, this is stored in turnData._responseData (set in gameScene.js)
        // Fallback to turnData fields for backward compatibility
        const responseData = turnData._responseData || {};
        const responseClock = responseData.clock || turnData.clock || this.scene.simData?.clock;
        const responseTimeRemaining = responseData.time_remaining || turnData.time_remaining;
        
        // Store clock in scene so showTimeoutPopup can access it
        if (this.scene.simData && responseClock) {
          this.scene.simData.clock = responseClock;
        }
        
        // Create timeoutResult object with clock/time_remaining from response (unified with user timeout)
        const timeoutResult = {
          message: turnData.text || `${turnData.timeout_calling_team?.name || 'Team'} Calls a Timeout`,
          calling_team: turnData.timeout_calling_team?.name || 'Unknown',
          timeouts_remaining: responseData.home_team_timeouts || responseData.away_team_timeouts || turnData.home_team_timeouts || turnData.away_team_timeouts || 0,
          home_team_timeouts: responseData.home_team_timeouts || turnData.home_team_timeouts || 0,
          away_team_timeouts: responseData.away_team_timeouts || turnData.away_team_timeouts || 0,
          clock: responseClock,  // ✅ UNIFIED: Use clock from API response (same as user timeout)
          time_remaining: responseTimeRemaining,  // ✅ UNIFIED: Use time_remaining from API response
          timeout_trace_id: responseData.timeout_trace_id || turnData.timeout_trace_id
        };
        // Show popup; navigation occurs when user clicks "Go To Timeout"
        const computerTeamName = turnData.timeout_calling_team?.name || 
                                 (typeof turnData.timeout_calling_team === 'string' ? turnData.timeout_calling_team : null) ||
                                 null;
        console.log('⏸️ COMPUTER TIMEOUT: Extracting team name', {
          timeout_calling_team: turnData.timeout_calling_team,
          computerTeamName: computerTeamName,
          timeout_reason: turnData.timeout_reason
        });
        await showComputerTimeoutPopup(timeoutResult, gameId, this.scene, computerTeamName);
      } catch (error) {
        console.error('❌ COMPUTER TIMEOUT: Failed to show timeout popup:', error);
        // Fallback: Show alert and let user navigate manually
        alert(`${turnData.timeout_calling_team?.name || 'Team'} called a timeout. Please return to the game.`);
      }
      this.enforceTimeoutUnitContract({
        turnData,
        unitId: 'timeout.phase.resume_prepare',
        advanceTrigger: 'resume route/context committed',
        visualSettleTrigger: 'resume setup settled',
        authorizingEventReceived: computerPopupAttempted,
        visualSettled: true,
        unitStartMs: timeoutStartMs,
        maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
        context: {
          timeoutReason: turnData?.timeout_reason ?? 'COMPUTER',
          route: 'computer_timeout_popup',
          gameIdPresent: true,
        },
      });
      enforceTimeoutOut({
        route: 'computer_timeout_popup',
        routeCommitted: true,
        contextExtra: { gameIdPresent: true },
      });
    } else {
      console.error('❌ COMPUTER TIMEOUT: Cannot determine game_id for navigation');
      this.enforceTimeoutUnitContract({
        turnData,
        unitId: 'timeout.phase.resume_prepare',
        advanceTrigger: 'resume route/context committed',
        visualSettleTrigger: 'resume setup settled',
        authorizingEventReceived: false,
        visualSettled: false,
        unitStartMs: timeoutStartMs,
        maxWaitGameSeconds: this.getTimeoutBudgetGameSeconds('resume'),
        context: {
          timeoutReason: turnData?.timeout_reason ?? 'COMPUTER',
          route: 'computer_timeout_popup',
          gameIdPresent: false,
        },
      });
      enforceTimeoutOut({
        route: 'computer_timeout_popup',
        routeCommitted: false,
        visualSettled: false,
        contextExtra: { gameIdPresent: false },
      });
    }
  }

  async handleOpeningTip(turnData, context) {
    const tipJumpStartMs = Date.now();
    // Opening tip handler (log removed)
    
    // ✅ PHASE 2.6: Validate opening tip timing (moved from animateGameTurns.js)
    const turnQuarter = turnData.quarter ?? this.scene.quarter ?? 1;
    const turnIndex = context.turnIndex ?? 0;
    const isQ1Start = turnQuarter === 1 && turnIndex === 0;
    const isOTStart = turnQuarter > 4 && turnIndex === 0;
    
    if (!isQ1Start && !isOTStart) {
      console.error('⚠️ OPENING_TIP detected mid-game! This should not happen.', {
        turnIndex: turnIndex,
        quarter: turnQuarter,
        sceneQuarter: this.scene.quarter,
        turn: turnData
      });
      // Skip opening tip if it's not at the start of Q1 or OT
      return;
    }
    
    // ✅ PHASE 2.6: Run opening tip sequence (moved from animateGameTurns.js)
    const { runOpeningTipSequence } = await import('./openingTip.js');
    await new Promise(resolve => {
      runOpeningTipSequence(this.scene, {
        playerSprites: context.playerSprites,
        ballSprite: context.ballSprite,
        turnData: turnData,
        onComplete: resolve
      });
    });
    this.enforceTipUnitContract({
      turnData,
      unitId: 'tip.phase.jump',
      advanceTrigger: 'tip outcome committed',
      visualSettleTrigger: 'jump visuals settled',
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: tipJumpStartMs,
      maxWaitGameSeconds: this.getTipBudgetGameSeconds('jump'),
      context: {
        phase: 'jump',
        quarter: turnQuarter,
        turnIndex,
      },
    });
    
    // ✅ PHASE 2.6: Transition to HalfCourt state (moved from animateGameTurns.js)
    const { States, safeTransition } = await import('../state/gameStateMachine.js');
    const { getCurrentOwner, getPendingOwner } = await import('./BallControllerAdapter.js');
    const tipControlStartMs = Date.now();
    const currentOwnerId = getCurrentOwner(this.scene);
    const pendingOwnerId = getPendingOwner(this.scene);
    const hasOwner = !!(currentOwnerId || pendingOwnerId);
    this.enforceTipUnitContract({
      turnData,
      unitId: 'tip.phase.control',
      advanceTrigger: 'possession control committed',
      visualSettleTrigger: 'control pass/attach settled',
      authorizingEventReceived: hasOwner,
      visualSettled: hasOwner,
      unitStartMs: tipControlStartMs,
      maxWaitGameSeconds: this.getTipBudgetGameSeconds('control'),
      context: {
        phase: 'control',
        currentOwnerId: currentOwnerId ?? null,
        pendingOwnerId: pendingOwnerId ?? null,
      },
    });
    if (this.scene.stateMachine && !this.scene.stateMachine.is(States.HalfCourt)) {
      safeTransition(this.scene.stateMachine, States.HalfCourt, {
        reason: 'opening_tip_complete',
        currentOwnerId,
        pendingOwnerId
      });
    }
    this.enforceTipUnitContract({
      turnData,
      unitId: 'tip.out.to_hco',
      advanceTrigger: 'hco route committed',
      visualSettleTrigger: 'tip boundary settle complete',
      authorizingEventReceived: this.scene?.stateMachine?.is(States.HalfCourt) === true,
      visualSettled: this.scene?.stateMachine?.is(States.HalfCourt) === true,
      unitStartMs: tipControlStartMs,
      maxWaitGameSeconds: this.getTipBudgetGameSeconds('control'),
      context: {
        phase: 'transition_out',
        nextStateIsHalfCourt: this.scene?.stateMachine?.is(States.HalfCourt) === true,
      },
    });
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  _parseClockTextToSeconds(clockText) {
    if (typeof clockText !== 'string') return null;
    const parts = clockText.trim().split(':');
    if (parts.length !== 2) return null;
    const minutes = Number(parts[0]);
    const seconds = Number(parts[1]);
    if (!Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;
    return Math.max(0, Math.floor(minutes * 60 + seconds));
  }

  _isFinalTurnSchemaShot(turnData) {
    if (turnData?.final_turn !== true) return false;
    const resultType = String(turnData?.result_type || '').toUpperCase();
    return resultType === 'MAKE' || resultType === 'MISS' || resultType === 'BLOCK';
  }

  async _getFinalTurnShotWindowTargetSec(turnData) {
    const animationConfig = (await import('./animation_config.js')).default;
    const playcall = String(
      turnData?.offensive_playcall
      ?? turnData?.current_playcall
      ?? turnData?.offensive_play_focus
      ?? ''
    ).trim().toLowerCase();
    if (playcall === 'attack') {
      return Number(animationConfig?.finalTurn?.latePassTargetSecAttack ?? 4);
    }
    return Number(animationConfig?.finalTurn?.latePassTargetSecOutside ?? 3);
  }

  _resolveFinalTurnStep0OwnerId(turnData) {
    for (const anim of turnData?.animations || []) {
      if (anim?.hasBallAtStep?.[0] && anim.playerId != null) {
        return String(anim.playerId);
      }
    }
    const step0Ball = turnData?.animation_steps?.[0]?.start?.ball;
    if (step0Ball?.owner_player_id != null && step0Ball.owner_player_id !== '') {
      return String(step0Ball.owner_player_id);
    }
    const bhId = turnData?.ball_handler_id ?? turnData?.roles?.ball_handler_id;
    return bhId != null ? String(bhId) : null;
  }

  async _runFinalTurnStep0EntryPassIfNeeded(turnData, sprites, ballSprite) {
    if (!ballSprite || !this._isFinalTurnSchemaShot(turnData)) return;
    const step0OwnerId = this._resolveFinalTurnStep0OwnerId(turnData);
    const {
      getCurrentOwner,
      getPendingOwner,
    } = await import('./BallControllerAdapter.js');
    const liveOwnerId = getCurrentOwner(this.scene) ?? getPendingOwner(this.scene) ?? null;
    if (!step0OwnerId || !liveOwnerId || String(liveOwnerId) === String(step0OwnerId)) {
      return;
    }
    if (!this.shotSystem) {
      if (!this.ballController) return;
      this.shotSystem = new ShotAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        sprites,
        gameStore,
      );
    } else {
      this.shotSystem.playerSprites = sprites;
    }
    await this.shotSystem.runStep0EntryPassIfNeeded(
      ballSprite,
      { value: null },
      liveOwnerId,
      step0OwnerId,
    );
  }

  async _holdFinalTurnBallUntilShotWindow(turnData) {
    if (this.scene?.skipToEnd) return;
    const targetRemainingSec = await this._getFinalTurnShotWindowTargetSec(turnData);

    const contractStart = Number(turnData?.clock_start ?? turnData?.clockStart);
    const contractEnd = Number(turnData?.clock_end ?? turnData?.clockEnd);
    const gameSecondsToCount = Number.isFinite(contractStart) && Number.isFinite(contractEnd)
      ? Math.max(0, contractStart - contractEnd)
      : 0;
    const durationMs = Math.max(0, Math.floor(Number(turnData?.real_time_elapsed_ms ?? turnData?.realTimeElapsedMs) || 0));

    const liveClockSec = Number(this.scene?.gameClock?.getState?.()?.timeRemaining);
    const fallbackClockFromText = this._parseClockTextToSeconds(turnData?.clock ?? turnData?.game_clock);
    const currentRemainingSec = Number.isFinite(liveClockSec)
      ? liveClockSec
      : (Number.isFinite(contractStart) ? contractStart : fallbackClockFromText);

    if (!Number.isFinite(currentRemainingSec) || currentRemainingSec <= targetRemainingSec) {
      return;
    }
    if (durationMs <= 0 || gameSecondsToCount <= 0) {
      return;
    }

    const gameSecondsToWait = Math.max(0, currentRemainingSec - targetRemainingSec);
    const waitMs = Math.max(0, Math.round((gameSecondsToWait / gameSecondsToCount) * durationMs));
    if (waitMs <= 0) return;

    await new Promise(resolve => setTimeout(resolve, waitMs));
  }

  async _finishFinalTurnQuarterEnd(turnData, context) {
    if (context.onUpdate) {
      context.onUpdate({
        home_score: turnData.home_score,
        away_score: turnData.away_score,
        clock: '0:00',
        time_remaining: 0,
        shot_clock_remaining: 0,
      });
    }
    const animationConfig = (await import('./animation_config.js')).default;
    const holdMs = animationConfig?.finalTurn?.holdFinalShotMs ?? 2000;
    if (turnData.result_type === 'MAKE') {
      const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
      announceGameEvent('SHOT_MAKE', turnData, this.scene, context);
    }
    await new Promise(resolve => setTimeout(resolve, holdMs));
  }

  /**
   * Phase 4: FINAL_HOLD — no shot, run clock out (short delay), then complete.
   * Quarter/game end is triggered by the API when quarter_complete is true.
   */
  async handleFinalHold(turnData, context) {
    if (turnData.text && this.scene.events) {
      this.scene.events.emit('textScroll', turnData.text);
    }
    const animationConfig = (await import('./animation_config.js')).default;
    const holdMs = animationConfig?.finalTurn?.holdClockOutMs ?? 1800;
    await new Promise(resolve => setTimeout(resolve, holdMs));
  }

  /**
   * Phase 4: Final Turn shot — tween offense/defense to oDestinations/dDestinations (alignment),
   * then run standard shot animation (ShotAnimationSystem or playTurnAnimation).
   */
  async handleFinalTurnShot(turnData, context) {
    const { runFinalTurnAlignment } = await import('./turnAnimation.js');
    await runFinalTurnAlignment({
      scene: this.scene,
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnData
    });
    await this._holdFinalTurnBallUntilShotWindow(turnData);
    if (this.shotSystem) {
      await this.shotSystem.processShot(turnData);
    } else {
      const { playTurnAnimation } = await import('./turnAnimation.js');
      await playTurnAnimation({
        scene: this.scene,
        simData: context.simData,
        playerSprites: context.playerSprites,
        turnData,
        ballSprite: context.ballSprite,
        onAction: context.onAction,
        turnIndex: context.turnIndex,
        onUpdate: context.onUpdate
      });
    }
    if (turnData.result_type === "MAKE" || turnData.result_type === "MISS" || turnData.result_type === "BLOCK") {
      this.scene._previousTurnWasShot = true;
    }
    // Final play of quarter: hold ball at rim (make) or bounce (miss), announce "It's Good" on make, then quarter end (no BIP/rebound)
    if (turnData.quarter_ends_after) {
      await this._finishFinalTurnQuarterEnd(turnData, context);
    }
  }

  async handleDefensiveStop(turnData, context) {
    console.log('AnimationEngine: Handling defensive stop', {
      result_type: turnData.result_type,
      fast_break: turnData.fast_break,
      fast_break_type: typeof turnData.fast_break,
      has_roles: !!turnData.roles,
      outlet_passer: turnData.roles?.outlet_passer,
      outlet_receiver: turnData.roles?.outlet_receiver
    });
    
    // ✅ PHASE 2.6: Check if this is a Fast Break defensive stop (moved from animateGameTurns.js)
    // ✅ FIX: Also check for string "true" in case JSON serialization converts boolean to string
    if (turnData.fast_break === true || turnData.fast_break === "true") {
      // Fast Break defensive stop - route to Fast Break animation sequence
      // This will animate outlet pass (if applicable) then defensive stop
      const { runFastBreakSequence } = await import('./fastBreak.js');
      await runFastBreakSequence({
        scene: this.scene,
        playerSprites: context.playerSprites,
        ballSprite: context.ballSprite,
        turnData: turnData,
        onUpdate: context.onUpdate,
        turnIndex: context.turnIndex
      });
    } else {
      // Non-Fast Break defensive stop - use standard defensive stop transition
      const { runDefensiveStopTransition } = await import('./turnAnimation.js');
      await runDefensiveStopTransition({
        scene: this.scene,
        playerSprites: context.playerSprites,
        ballSprite: context.ballSprite
      });
    }
    
    // ✅ PHASE 2.6: Display text (moved from animateGameTurns.js)
    const { appendToTextScroll } = await import('../utils/textScroll.js');
    const { isFastBreakEntryAnnouncementsEnabled } = await import('../constants/fastBreakConstants.js');
    const fbStopFallback =
      turnData.fast_break && isFastBreakEntryAnnouncementsEnabled()
        ? "Fast Break! Defense stops the break!"
        : "Defense stops the break!";
    appendToTextScroll(turnData.text || fbStopFallback);
    
    // Note: onUpdate and updateDebugScore are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handleSteal(turnData, context) {
    console.log('🔍 [STEAL HANDLER] Entry', {
      result_type: turnData.result_type,
      has_animations: !!turnData.animations?.length,
      animation_count: turnData.animations?.length || 0,
      stealer_id: turnData.stealer_id || turnData.stealerId,
      victim_id: turnData.victim_id
    });
    
    // ✅ HYBRID APPROACH: Parallels shot attempt handling
    // 1. Play skeleton animation (if exists) - shows press break sequence
    // 2. Animate steal result action - ball changes hands
    // 3. Universal transition handles possession flip
    
    // STEP 1: Play skeleton animation (FCP/HCT press break sequence)
    if (turnData.animations && turnData.animations.length > 0) {
      console.log('✅ [STEAL HANDLER] Playing skeleton animation');
      const { playTurnAnimation } = await import('./turnAnimation.js');
      await playTurnAnimation({
        scene: this.scene,
        simData: context.simData,
        playerSprites: context.playerSprites,
        turnData: turnData,
        ballSprite: context.ballSprite,
        onAction: context.onAction,
        turnIndex: context.turnIndex,
        onUpdate: context.onUpdate
      });
      console.log('✅ [STEAL HANDLER] Skeleton animation completed - steal action included in skeleton');
      
      // ✅ FIX: Attach ball to stealer after skeleton animation completes
      // This ensures ball is attached before next turn (HCO or Fast Break) starts
      const resolveSpriteById = (rawId) => {
        if (rawId == null) return null;
        if (context.playerSprites?.[rawId]) return context.playerSprites[rawId];
        const want = String(rawId);
        for (const [id, sprite] of Object.entries(context.playerSprites || {})) {
          if (String(id) === want) return sprite;
          if (String(sprite?.playerId ?? "") === want) return sprite;
        }
        return null;
      };
      const stealEvent =
        turnData.events?.find((e) => String(e?.event_type || "").toUpperCase() === "STEAL") || null;
      const stealerCandidates = [
        turnData.stealerId,
        turnData.stealer_id,
        turnData.roles?.ball_handler_id,
        turnData.roles?.ball_handler?.player_id,
        stealEvent?.stealerId,
        stealEvent?.stealer_id,
      ].filter((v) => v != null);
      let stealerRaw = stealerCandidates[0] ?? null;
      let stealerSprite = stealerRaw != null ? resolveSpriteById(stealerRaw) : null;
      if (!stealerSprite && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
        const maxStep = Math.max(0, ...turnData.animations.map((a) => a?.movement?.length || 0)) - 1;
        const inferred = turnData.animations.find((a) => {
          if (!a) return false;
          if (Array.isArray(a.hasBallAtStep) && a.hasBallAtStep[maxStep] === true) return true;
          const lastAction = a?.movement?.[maxStep]?.action;
          return lastAction === "steal" || lastAction === "handle";
        });
        stealerRaw = inferred?.playerId ?? stealerRaw;
        stealerSprite = stealerRaw != null ? resolveSpriteById(stealerRaw) : null;
      }

      if (stealerRaw && stealerSprite) {
        if (stealerSprite) {
          const {
            attachBallToPlayer,
            setCurrentOwner,
            clearPendingOwner,
          } = await import('./BallControllerAdapter.js');
          const { setBallHolderId } = await import('./ballAnimationSimple.js');
          attachBallToPlayer(this.scene, context.ballSprite, stealerSprite, {
            reason: 'steal_handler_post_skeleton'
          });
          // Steal SFX now tied to the "STEAL!" announce appearance, not the
          // ball-attach moment (SFX_System.md §Steal Announce).
          // Make STEAL end ownership authoritative so stale pass pending owner
          // cannot reclaim the victim at turn boundary.
          setCurrentOwner(this.scene, String(stealerRaw));
          clearPendingOwner(this.scene);
          setBallHolderId(this.scene, String(stealerRaw));
          this.scene.passInFlight = false;
          console.log('✅ [STEAL HANDLER] Ball attached to stealer after skeleton animation', {
            stealerId: stealerRaw
          });
        } else {
          console.warn('⚠️ [STEAL HANDLER] Stealer sprite not found for ball attachment', {
            stealerId: stealerRaw,
            availableSprites: Object.keys(context.playerSprites)
          });
        }
      } else {
        console.warn('⚠️ [STEAL HANDLER] Could not determine stealer ID for ball attachment', {
          turnData: {
            stealerId: turnData.stealerId,
            stealer_id: turnData.stealer_id,
            ball_handler_id: turnData.roles?.ball_handler_id,
            ball_handler_player_id: turnData.roles?.ball_handler?.player_id,
            events: turnData.events,
            inferredFromAnimations: stealerRaw ?? null,
          }
        });
      }
      
      // ✅ FIX (Bug 3): Skeleton animation includes steal action in final step
      // Skip Step 2 to avoid double animation and double announcement
      return;
    }
    
    // STEP 2: Animate steal result action (ball changes hands)
    // ✅ Only runs if NO skeleton (standalone steal without press break sequence)
    const { States } = await import('../state/gameStateMachine.js');
    if (this.scene.stateMachine?.is(States.FastBreak)) {
      // Skip steal action animation if in FastBreak state
      console.log('⏭️ [STEAL HANDLER] Skipping steal action - FastBreak state');
      return;
    }
    
    // Get player IDs
    const allPlayers = this.scene.simData?.players || [];
    const playerMap = Object.fromEntries(
      allPlayers.map(p => [p.name, p.playerId])
    );
    const ballHandlerId = playerMap[turnData.ball_handler] ?? turnData.ball_handler;
    const stealEvent = turnData.events?.find(e => e.event_type === "STEAL");
    const stealerRaw =
      turnData.stealerId ||
      turnData.stealer_id ||
      stealEvent?.stealerId ||
      stealEvent?.stealer_id;
    const stealerId = stealerRaw ?? playerMap[turnData.stealer_name];
    
    if (ballHandlerId != null && stealerId != null) {
      console.log('✅ [STEAL HANDLER] Animating steal action (ball changes hands)', {
        from: ballHandlerId,
        to: stealerId
      });
      
      const { runPass } = await import('./ballManager.js');
      const animationConfig = (await import('./animation_config.js')).default;
      const cfg = animationConfig.steal || {};
      
      if (this.scene.__activePass) {
        console.warn('Active pass tween detected before steal; cancelling previous tween');
      }
      
      await runPass(this.scene, {
        fromId: ballHandlerId,
        toId: stealerId,
        duration: cfg.duration,
        easing: cfg.easing
      });
      
      // ✅ FIX: Ensure ball is attached to stealer after pass completes
      // runPass should handle attachment, but verify to ensure consistency
      const stealerSprite = context.playerSprites[stealerId];
      if (stealerSprite) {
        const { attachBallToPlayer, getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        if (!ballController?.isAttached || ballController.currentOwner !== stealerSprite) {
          attachBallToPlayer(this.scene, context.ballSprite, stealerSprite, {
            reason: 'steal_handler_post_pass'
          });
          console.log('✅ [STEAL HANDLER] Ball attached to stealer after pass (no skeleton path)', {
            stealerId: stealerId
          });
        }
      }
      
      console.log('✅ [STEAL HANDLER] Steal action completed');
    }
    
    // STEP 3: Possession flip handled by universal transition in finalizeTurnAfterAnimation
    // Note: Don't emit possessionChange here - universal handler does it based on backend data
  }

  async handleShotAttempt(turnData, context) {
    if (await this.runSchemaPlaybackTurn(turnData, context)) {
      return;
    }

    // Use new shot animation system if available
    if (this.shotSystem) {
      await this.shotSystem.processShot(turnData);
      // Shot system completed (log removed)
    } else {
      // Fallback to existing system
      console.warn('AnimationEngine: ShotAnimationSystem not available, using fallback');
      const { playTurnAnimation } = await import('./turnAnimation.js');
      // ✅ PHASE 2.1: Pass full context including turnIndex and onUpdate
      await playTurnAnimation({
        scene: this.scene,
        simData: context.simData,
        playerSprites: context.playerSprites,
        turnData: turnData,
        ballSprite: context.ballSprite,
        onAction: context.onAction,
        turnIndex: context.turnIndex, // ✅ PHASE 2.1: Pass turnIndex
        onUpdate: context.onUpdate // ✅ PHASE 2.1: Pass onUpdate (for future use)
      });
    }
  }

  async handleRebound(turnData, context) {
    console.log('AnimationEngine: Handling rebound with new ReboundAnimationSystem', {
      result_type: turnData.result_type,
      rebounder_id: turnData.rebounder_id,
      rebounderId: turnData.rebounderId,
      rebound_type: turnData.rebound_type,
      hasReboundSystem: !!this.reboundSystem
    });
    
    // Use new rebound animation system if available
    if (this.reboundSystem) {
      await this.reboundSystem.processRebound(turnData);
    } else {
      // Fallback to existing system
      console.warn('AnimationEngine: ReboundAnimationSystem not available, using fallback');
      const { playTurnAnimation } = await import('./turnAnimation.js');
      // ✅ PHASE 2.1: Pass full context including turnIndex and onUpdate
      await playTurnAnimation({
        scene: this.scene,
        simData: context.simData,
        playerSprites: context.playerSprites,
        turnData: turnData,
        ballSprite: context.ballSprite,
        onAction: context.onAction,
        turnIndex: context.turnIndex, // ✅ PHASE 2.1: Pass turnIndex
        onUpdate: context.onUpdate // ✅ PHASE 2.1: Pass onUpdate (for future use)
      });
    }
  }

  async handlePass(turnData, context) {
    console.log('AnimationEngine: Handling pass with new PassAnimationSystem');
    
    // Use new pass animation system if available
    if (this.passSystem) {
      await this.passSystem.processPass(turnData);
    } else {
      // Fallback to existing system
      console.warn('AnimationEngine: PassAnimationSystem not available, using fallback');
      const { playTurnAnimation } = await import('./turnAnimation.js');
      // ✅ PHASE 2.1: Pass full context including turnIndex and onUpdate
      await playTurnAnimation({
        scene: this.scene,
        simData: context.simData,
        playerSprites: context.playerSprites,
        turnData: turnData,
        ballSprite: context.ballSprite,
        onAction: context.onAction,
        turnIndex: context.turnIndex, // ✅ PHASE 2.1: Pass turnIndex
        onUpdate: context.onUpdate // ✅ PHASE 2.1: Pass onUpdate (for future use)
      });
    }
  }

  async handleDefault(turnData, context) {
    // ✅ Force Foul: animation (reach-in + announce) was already done during BIP/SIP turn
    if (turnData.result_type === 'FOUL' && turnData._quickFoulAnimatedDuringInbound) {
      return;
    }

    // ✅ Quick Foul after DREB or Final Turn: sprint → reach_in → announce (clock runs via turn contract)
    if (
      turnData.result_type === 'FOUL'
      && turnData.quick_foul
      && (turnData.force_foul_after_dreb || turnData.force_foul_final_turn)
    ) {
      const victimId = turnData.victim_id ?? turnData.ball_handler ?? turnData.shooter;
      const foulPlayerId = turnData.foul_player_id;
      const victimSprite = context.playerSprites?.[victimId];
      const defenderSprite = context.playerSprites?.[foulPlayerId];
      if (victimSprite && defenderSprite) {
        const { runQuickFoulSprintSequence } = await import('./quickFoulAnimation.js');
        await runQuickFoulSprintSequence(this.scene, {
          defenderSprite,
          victimSprite,
          ballSprite: context.ballSprite,
          turnData,
          clockBudgetMs: this.scene._clockInterpolationDurationMs,
        });
      }
      return;
    }

    if (await this.runSchemaPlaybackTurn(turnData, context)) {
      return;
    }

    // Legacy HCO setup / stopper turns without animation_steps.
    const { playTurnAnimation } = await import('./turnAnimation.js');
    // ✅ PHASE 2.1: Pass full context including turnIndex and onUpdate
    await playTurnAnimation({
      scene: this.scene,
      simData: context.simData,
      playerSprites: context.playerSprites,
      turnData: turnData,
      ballSprite: context.ballSprite,
      onAction: context.onAction,
      turnIndex: context.turnIndex, // ✅ PHASE 2.1: Pass turnIndex
      onUpdate: context.onUpdate // ✅ PHASE 2.1: Pass onUpdate (for future use)
    });
  }

  /**
   * Register a custom animation handler
   */
  registerHandler(type, handler) {
    this.animationHandlers.set(type, handler);
  }

  /**
   * Get current processing status
   */
  getStatus() {
    return {
      isProcessing: this.isProcessing,
      registeredHandlers: Array.from(this.animationHandlers.keys()),
      hasBallController: !!this.ballController,
      hasStateMachine: !!this.stateMachine
    };
  }

  /**
   * Inject dependencies (will be called after other components are created)
   */
  injectDependencies(ballController, stateMachine, playerSprites) {
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    ensureConsistentHeartbeat(this.scene, this.playerSprites);
    this.scene?.events?.once?.('shutdown', () => stopAllArrivalHeartbeats(this.scene));
    this.scene?.events?.once?.('destroy', () => stopAllArrivalHeartbeats(this.scene));
    
    // Initialize animation systems (stateMachine is optional)
    if (this.ballController && this.playerSprites) {
      this.shotSystem = new ShotAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites,
        gameStore
      );
      // Removed verbose initialization logs
      
      this.reboundSystem = new ReboundAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
      
      this.passSystem = new PassAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
      
      this.freeThrowSystem = new FreeThrowAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites,
        gameStore
      );
      
      this.hcoSystem = new HCOAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
    }
    
    // Removed verbose dependencies injected log
  }
}

export default AnimationEngine;
