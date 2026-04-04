/**
 * FreeThrowAnimationSystem - Universal Free Throw Animation Handler
 * 
 * Handles all free throw scenarios using the new Phase 1 components:
 * - Single free throws
 * - Multiple free throw sequences (1+1, 2+1, 3+1)
 * - Free throw positioning and setup
 * - Free throw shot animations
 * - Follow-up actions (rebounds, inbound passes)
 * 
 * Key Benefits:
 * - Single system for all free throw types
 * - Proper sequence management
 * - Consistent with shot system
 * - No teleports or floating balls
 */

import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from './courtConstants.js';
import { gridToPixels } from '../utils/gridToPixels.js';
import animationConfig from './animation_config.js';
import { enforceUnitCompletionContract } from './unitCompletionContract.js';

export class FreeThrowAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
    // Free throw configuration
    this.ftConfig = {
      // Shot parameters (fallback values, will use animation data when available)
      shotDuration: 1000, // ms
      shotEase: 'Sine.easeInOut',
      
      // Bounce parameters (used by existing bounce system)
      bounceDuration: 600, // ms
      
      // Setup parameters (fallback values, will use animation data when available)
      setupDuration: 800, // ms
      setupEase: 'Linear'
    };
    
    // Free throw sequence tracking
    this.activeSequence = null;
    this.sequenceQueue = [];
    this.currentAttempt = 0;
    this.totalAttempts = 0;
    
    // ✅ REMOVED: Free throw initialization logging (cluttering console)
  }

  resolveFtContractMode() {
    const raw = String(
      (typeof window !== 'undefined' ? window.UESS_FT_CONTRACT_MODE : null) ?? 'observe'
    )
      .trim()
      .toLowerCase();
    if (raw === 'off' || raw === 'observe' || raw === 'warn' || raw === 'throw') return raw;
    return 'observe';
  }

  getFtBudgetGameSeconds(kind = 'attempt') {
    const scope = typeof window !== 'undefined' ? window : globalThis;
    const raw =
      kind === 'attempt'
        ? Number(scope?.UESS_FT_ATTEMPT_MAX_GAME_SECONDS)
        : Number(scope?.UESS_FT_SEQUENCE_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return kind === 'attempt' ? 3 : 2;
  }

  emitFtContractTelemetry(turnData, event, payload = {}) {
    this.scene?.events?.emit?.('animTelemetry', {
      event,
      branchKind: 'ft_phase_contract',
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: this.scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? this.scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    });
  }

  enforceFtUnitContract({
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
    const mode = this.resolveFtContractMode();
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
      this.emitFtContractTelemetry(turnData, 'ft_phase_clock_overrun', {
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
        this.emitFtContractTelemetry(turnData, event, payload),
      logger,
    });
    if (mode === 'throw' && overrun) {
      throw new Error(
        `[FT contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
      );
    }
  }

  /**
   * Process a free throw turn
   */
  async processFreeThrow(turnData) {
    if (this.activeSequence) {
      console.warn('FreeThrowAnimationSystem: Already processing a free throw sequence, queuing...');
      this.sequenceQueue.push(turnData);
      return;
    }

    this.activeSequence = turnData;
    
    try {
      // ✅ REMOVED: Free throw processing logging (cluttering console)

      // Adapt backend data structure to new system format
      const adaptedTurnData = this.adaptBackendData(turnData);
      
      // Validate free throw data
      if (!this.validateFreeThrowData(adaptedTurnData)) {
        console.error('❌ FreeThrowAnimationSystem: Free throw data validation failed', {
          result_type: adaptedTurnData.result_type,
          shooter_id: adaptedTurnData.shooter_id,
          player_id: adaptedTurnData.player_id,
          hasResultType: !!adaptedTurnData.result_type,
          isFreeThrow: adaptedTurnData.result_type === 'FREE_THROW',
          hasShooterId: !!(adaptedTurnData.shooter_id || adaptedTurnData.player_id)
        });
        throw new Error('Invalid free throw data');
      }

      // Get shooter sprite
      const shooterSprite = this.getShooterSprite(adaptedTurnData);
      if (!shooterSprite) {
        throw new Error('Shooter sprite not found');
      }

      // Determine free throw context
      const ftContext = this.determineFreeThrowContext(adaptedTurnData);

      // FT entry contract: route is in FT family and shooter is resolved.
      this.enforceFtUnitContract({
        turnData: adaptedTurnData,
        unitId: 'ft.lead_in.entry',
        advanceTrigger: 'FT route committed + shooter resolved',
        visualSettleTrigger: 'lane setup settled',
        authorizingEventReceived: adaptedTurnData?.result_type === 'FREE_THROW' && !!shooterSprite,
        visualSettled: !!shooterSprite,
        unitStartMs: Date.now(),
        maxWaitGameSeconds: this.getFtBudgetGameSeconds('sequence'),
        context: {
          phase: 'lead_in_entry',
          shooterId: adaptedTurnData?.shooter_id ?? adaptedTurnData?.player_id ?? null,
          resultType: adaptedTurnData?.result_type ?? null,
        },
      });

      // Execute free throw sequence
      await this.executeFreeThrowSequence(shooterSprite, adaptedTurnData, ftContext);

      // Process any queued sequences
      await this.processSequenceQueue();

    } catch (error) {
      console.error('FreeThrowAnimationSystem: Error processing free throw', error);
      this.handleFreeThrowError(error, turnData);
    } finally {
      this.activeSequence = null;
    }
  }

  /**
   * Execute the complete free throw sequence
   */
  async executeFreeThrowSequence(shooterSprite, turnData, ftContext) {
    const attemptStartMs = Date.now();
    // 1. Setup free throw positioning
    await this.setupFreeThrowPositioning(shooterSprite, turnData);

    // 2. Execute the free throw shot
    await this.executeFreeThrowShot(shooterSprite, turnData, ftContext);

    // 3. Handle free throw outcome
    if (turnData.actual_result === 'MAKE') {
      await this.handleMadeFreeThrow(turnData, ftContext);
    } else {
      await this.handleMissedFreeThrow(turnData, ftContext);
    }
    this.enforceFtUnitContract({
      turnData,
      unitId: 'ft.phase.attempt[n]',
      advanceTrigger: 'shot release/result committed',
      visualSettleTrigger: 'ball/rim/announcement settled',
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: attemptStartMs,
      maxWaitGameSeconds: this.getFtBudgetGameSeconds('attempt'),
      context: {
        attempt: ftContext?.attempt ?? null,
        total: ftContext?.total ?? null,
        isFinal: ftContext?.isFinal === true,
        actualResult: turnData?.actual_result ?? null,
      },
    });

    const sequenceStartMs = Date.now();
    const hasAuthoritativeRemaining = turnData?.free_throws_remaining !== undefined;
    const expectedIsFinal = hasAuthoritativeRemaining
      ? Number(turnData.free_throws_remaining) === 0
      : Number(ftContext?.attempt ?? 1) >= Number(ftContext?.total ?? 1);
    const sequenceConsistent = Boolean(ftContext?.isFinal) === expectedIsFinal;
    this.enforceFtUnitContract({
      turnData,
      unitId: 'ft.phase.sequence_control',
      advanceTrigger: 'remaining-attempt decision committed',
      visualSettleTrigger: 'sequence state settled',
      authorizingEventReceived: true,
      visualSettled: sequenceConsistent,
      unitStartMs: sequenceStartMs,
      maxWaitGameSeconds: this.getFtBudgetGameSeconds('sequence'),
      context: {
        attempt: ftContext?.attempt ?? null,
        total: ftContext?.total ?? null,
        isFinal: ftContext?.isFinal === true,
        expectedIsFinal,
        freeThrowsRemaining:
          turnData?.free_throws_remaining !== undefined
            ? Number(turnData.free_throws_remaining)
            : null,
      },
    });
    if (this.resolveFtContractMode() === 'throw' && !sequenceConsistent) {
      throw new Error(
        `[FT contract] sequence mismatch (attempt=${ftContext?.attempt ?? "?"}, total=${ftContext?.total ?? "?"}, isFinal=${String(ftContext?.isFinal)}, expectedIsFinal=${String(expectedIsFinal)})`
      );
    }

    // FT transition-out contract applies only on final attempt in sequence.
    if (ftContext?.isFinal === true) {
      const outStartMs = Date.now();
      const route = String(turnData?.next_play_type || turnData?.next_turn || '').toUpperCase();
      this.enforceFtUnitContract({
        turnData,
        unitId: 'ft.out.to_*',
        advanceTrigger: 'route committed',
        visualSettleTrigger: 'FT final settle complete',
        authorizingEventReceived: route.length > 0,
        visualSettled: true,
        unitStartMs: outStartMs,
        maxWaitGameSeconds: this.getFtBudgetGameSeconds('sequence'),
        context: {
          phase: 'transition_out',
          route: route || null,
          reboundType: turnData?.rebound_type ?? null,
          actualResult: turnData?.actual_result ?? null,
        },
      });
      if (this.resolveFtContractMode() === 'throw' && route.length === 0) {
        throw new Error('[FT contract] missing committed route at sequence exit');
      }
    }
  }

  /**
   * Setup free throw positioning using backend animation data
   */
  async setupFreeThrowPositioning(shooterSprite, turnData) {
    const animations = turnData.animations || [];
    const playerAnims = animations.filter((a) => a.playerId !== "ball");
    const width = this.scene.game.config.width;
    const height = this.scene.game.config.height;

    // ✅ REMOVED: Free throw positioning logging (cluttering console)

    if (!turnData.no_lane) {
      // Move all players to their free throw positions
      const promises = [];
      for (const anim of playerAnims) {
        const sprite = this.playerSprites[anim.playerId];
        const end = anim.movement?.[1]?.coords;
        if (!sprite || !end) continue;
        
        const px = gridToPixels(end.x, end.y, width, height);
        promises.push(
          new Promise((resolve) => {
            this.scene.tweens.add({
              targets: sprite,
              x: px.x,
              y: px.y,
              duration: anim.duration || this.ftConfig.setupDuration,
              ease: "Linear",
              onComplete: resolve,
              onStop: resolve,
            });
          })
        );
      }
      await Promise.all(promises);
    } else {
      // Only move the shooter to the free throw line
      const shooterAnim = playerAnims.find(
        (a) => a.playerId === turnData.shooter_id
      );
      const sprite = this.playerSprites[turnData.shooter_id];
      const end = shooterAnim?.movement?.[1]?.coords;
      if (sprite && end) {
        const px = gridToPixels(end.x, end.y, width, height);
        await new Promise((resolve) => {
          this.scene.tweens.add({
            targets: sprite,
            x: px.x,
            y: px.y,
            duration: shooterAnim.duration || this.ftConfig.setupDuration,
            ease: "Linear",
            onComplete: resolve,
            onStop: resolve,
          });
        });
      }
    }

    // Attach ball to shooter
    if (shooterSprite) {
      this.ballController.attachToPlayer(shooterSprite);
    }

    // ✅ REMOVED: Free throw positioning complete logging (cluttering console)
  }

  /**
   * Execute the free throw shot
   */
  async executeFreeThrowShot(shooterSprite, turnData, ftContext) {
    // 1. Transition to SHOOTING state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.SHOOTING, {
        reason: 'free_throw_initiated',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // 2. Detach ball from shooter
    this.ballController.detachFromPlayer('free_throw_shot', { keepVisible: true });

    // 3. Get rim coordinates from animation data
    const rimCoords = this.getRimCoordinatesFromAnimation(turnData);
    await this.animateBallToRim(shooterSprite, rimCoords, turnData);

    // ✅ REMOVED: Free throw shot executed logging (cluttering console)
  }

  /**
   * Animate ball to rim using animation data
   */
  async animateBallToRim(shooterSprite, rimCoords, turnData) {
    return new Promise((resolve) => {
      // Get ball sprite
      const ballSprite = this.ballController.ballSprite;
      if (!ballSprite) {
        console.warn('FreeThrowAnimationSystem: No ball sprite available');
        resolve();
        return;
      }

      // Get shot duration from animation data
      const animations = turnData.animations || [];
      const ballAnim = animations.find((a) => a.playerId === "ball");
      const shotDuration = ballAnim?.duration || this.ftConfig.shotDuration;

      // Position ball at shooter
      ballSprite.setPosition(shooterSprite.x, shooterSprite.y - 10);
      ballSprite.setVisible(true);

      // Start flight
      this.ballController.startFlight(rimCoords, {
        duration: shotDuration,
        ease: this.ftConfig.shotEase
      });

      // Animate ball to rim
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: shotDuration,
        ease: "Sine.easeInOut", // Use same easing as old system
        onComplete: () => {
          this.ballController.endFlight();
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });

      // ✅ REMOVED: Free throw ball animation logging (cluttering console)
    });
  }

  /**
   * Handle made free throw
   */
  async handleMadeFreeThrow(turnData, ftContext) {
    // ✅ REMOVED: Free throw debug logging (cluttering console)
    
    // ✅ REMOVED: Free throw made logging (cluttering console)

    // ✅ SS&S: Announce FT make using central dispatcher
    const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
    announceGameEvent('FT_MAKE', turnData, this.scene, { 
      shooterId: turnData.shooter_id 
    });

    // Ball holds in rim for 1 second (authentic basketball feel)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Keep ball visible during hold
      ballSprite.setVisible(true);
      
      // Hold ball at rim (announcement hold from config)
      const makeRimHoldMs = animationConfig.freeThrow?.makeRimHoldMs ?? 1000;
      await new Promise(resolve => {
        if (this.scene.time?.delayedCall) {
          this.scene.time.delayedCall(makeRimHoldMs, resolve);
        } else {
          setTimeout(resolve, makeRimHoldMs);
        }
      });

      // For non-final free throws, just hide the ball after the hold
      // (no slide animation - ball stays at rim coords)
      if (!ftContext.isFinal) {
        ballSprite.setVisible(false);
        }
    }

    // Check if this is the final free throw
    // ✅ FIX: Use ftContext.isFinal instead of recalculating, as it includes the free_throws_remaining safety check
    if (ftContext.isFinal) {
      // ✅ SS&S: Announce pressure if next_defensive_setup is FCP/HCT
      // (No BASELINE_INBOUND turn is created for FTs, so announce here)
      if (turnData.next_defensive_setup === 'FCP') {
        announceGameEvent('PRESSURE_FCP', turnData, this.scene);
      } else if (turnData.next_defensive_setup === 'HCT') {
        announceGameEvent('PRESSURE_HCT', turnData, this.scene);
      }
      
      // Final free throw made - execute inbound pass
      await this.handleFinalMadeFreeThrow(turnData);
    } else {
      // More free throws to come - stay in POSSESSION
      if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'free_throw_made_more_to_come',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
      }
    }
  }

  /**
   * Handle missed free throw
   */
  async handleMissedFreeThrow(turnData, ftContext) {
    // ✅ REMOVED: Free throw missed logging (cluttering console)

    // Use existing bounce system for authentic basketball feel
    const rimGridCoords = this.getRimGridCoordinates(turnData);
    const miss = await this.animateBallBounceFromRim(rimGridCoords, turnData);

    // Check if this is the final free throw
    // ✅ FIX: Use ftContext.isFinal instead of recalculating, as it includes the free_throws_remaining safety check
    if (ftContext.isFinal) {
      // Final free throw missed - execute rebound system
      // ✅ FIX: Pass the bounce result so we don't bounce twice
      await this.handleFinalMissedFreeThrow(turnData, miss);
    } else {
      // More free throws to come - stay in POSSESSION
      if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'free_throw_missed_more_to_come',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
      }
    }
  }

  /**
   * Animate ball bounce from rim using existing bounce system
   */
  async animateBallBounceFromRim(rimCoords, turnData) {
    const ballSprite = this.ballController.ballSprite;
    if (!ballSprite) {
      return;
    }

    // Import the existing bounce system
    const { bounceFromRim } = await import('./ballManager.js');
    
    // Determine if this is home team shooting (for bounce direction)
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    
    // Get rim grid coordinates (bounceFromRim expects grid coordinates, not pixels)
    const rimGridCoords = this.getRimGridCoordinates(turnData);
    
    // Use existing bounce system for authentic basketball feel
    const miss = await bounceFromRim(
      this.scene,
      ballSprite,
      rimGridCoords, // Pass grid coordinates, not pixel coordinates
      isHomeTeam,
      this.ftConfig.bounceDuration
    );

    // ✅ REMOVED: Free throw bounce logging (cluttering console)

    return miss;
  }

  /**
   * Handle final made free throw - execute inbound pass
   */
  async handleFinalMadeFreeThrow(turnData) {
    // ✅ REMOVED: Free throw inbound pass logging (cluttering console)

    // Transition to IDLE state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'free_throw_sequence_complete',
        shooter_id: turnData.shooter_id,
        made: true
      });
    }

    // ✅ EXACT HCO PATTERN: Use shooter sprite to determine newOffenseSide
    // Copied from ShotAnimationSystem.handleMadeShot line 725-776
    const shooterSprite = this.playerSprites[turnData.shooter_id];
    const shooterTeamId = shooterSprite?.team_id;
    const isHomeOffense = shooterTeamId === this.scene.simData?.home_team_id;
    // After made shot/FT, possession flips to opposite team
    const newOffenseSide = isHomeOffense ? 'away' : 'home';
    
    // Execute inbound pass using the existing system
    const { runInboundSetup } = await import('./turnAnimation.js');
    
    // ✅ FIX: Check for FCP/HCT setup after free throw (same logic as freeThrow.js)
    // This ensures pressureSequenceActive is set so subsequent STEAL turns are recognized as FCP/HCT
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
    
    // ✅ FIX: Don't call runInboundSetup() here if next_play_type === "BASELINE_INBOUND"
    // The BASELINE_INBOUND turn will handle the inbound setup via AnimationEngine.handleBaselineInbound()
    // Calling it here causes double inbound passes and double setup animations
    if (turnData.next_play_type === "BASELINE_INBOUND") {
      // ✅ REMOVED: runInboundSetup() call - BASELINE_INBOUND turn handles it
      // This prevents double inbound passes and double setup animations
      return;
    }
    
    await runInboundSetup({
      scene: this.scene,
      ballSprite: this.ballController.ballSprite,
      playerSprites: this.playerSprites,
      newOffenseSide: newOffenseSide,
      homeTeamId: this.scene.simData?.home_team_id,
      awayTeamId: this.scene.simData?.away_team_id,
      skipRetreat,
      pressureType,
      turnData: turnData
    });

    // ✅ REMOVED: Free throw inbound pass completed logging (cluttering console)
  }

  /**
   * Handle final missed free throw - execute rebound system
   * @param {Object} turnData - Turn data
   * @param {Object} miss - Bounce result from animateBallBounceFromRim (contains grid coordinates)
   */
  async handleFinalMissedFreeThrow(turnData, miss) {
    // ✅ REMOVED: Free throw rebound logging (cluttering console)

    // Transition to REBOUNDING state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.REBOUNDING, {
        reason: 'free_throw_missed',
        shooter_id: turnData.shooter_id
      });
    }

    // ✅ FIX: Use the bounce result from handleMissedFreeThrow instead of bouncing again
    // The ball has already bounced to the bounce spot, now players animate to it
    if (!miss || !miss.grid) {
      // Fallback: if miss wasn't passed, get it (shouldn't happen)
      const rimGridCoords = this.getRimGridCoordinates(turnData);
      miss = await this.animateBallBounceFromRim(rimGridCoords, turnData);
    }

    // Execute rebound system using existing system
    const { animateRebound } = await import('./ballManager.js');
    
    // Execute the rebound animation - ball is already at bounce spot, players animate to it
    await animateRebound({
      scene: this.scene,
      ballSprite: this.ballController.ballSprite,
      playerSprites: this.playerSprites,
      animations: [],
      rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
      ballSpot: miss.grid,
      shooterId: turnData.shooter_id,
      preserveBallPosition: true  // ✅ FIX: Ball is already at bounce spot, don't move it
    });

    // Handle defensive rebound setup if needed
    // Only call runDefensiveReboundSetup for HCO/HCT/FCP, not for FAST_BREAK
    // Fast Break handles its own outlet pass in fastBreak.js (animateOutletPhase)
    if (turnData.rebound_type === "DREB") {
      const nextPlayType = turnData.next_play_type || "HCO";
      if (nextPlayType === 'HCO' || nextPlayType === 'HCT' || nextPlayType === 'FCP') {
        const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
        await runDefensiveReboundSetup({
          scene: this.scene,
          ballSprite: this.ballController.ballSprite,
          playerSprites: this.playerSprites,
          rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
          nextPlayType: nextPlayType
        });
      } else if (nextPlayType === 'FAST_BREAK') {
        // Fast Break outlet passes are handled in the Fast Break sequence itself
        // No need to call runDefensiveReboundSetup here
      }
    }

    // ✅ REMOVED: Free throw rebound completed logging (cluttering console)
  }

  /**
   * Get rim coordinates from animation data (pixel coordinates for ball animation)
   */
  getRimCoordinatesFromAnimation(turnData) {
    const animations = turnData.animations || [];
    const ballAnim = animations.find((a) => a.playerId === "ball");
    const moves = ballAnim?.movement || [];
    
    if (moves.length > 1) {
      // Get the shot step (usually the second movement)
      const shotStep = moves[1];
      if (shotStep?.coords) {
        const width = this.scene.game.config.width;
        const height = this.scene.game.config.height;
        return gridToPixels(shotStep.coords.x, shotStep.coords.y, width, height);
      }
    }
    
    // Fallback to team-based rim coordinates
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    const rimGrid = isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const width = this.scene.game.config.width;
    const height = this.scene.game.config.height;
    return gridToPixels(rimGrid.x, rimGrid.y, width, height);
  }

  /**
   * Get rim grid coordinates (for bounce system)
   */
  getRimGridCoordinates(turnData) {
    const animations = turnData.animations || [];
    const ballAnim = animations.find((a) => a.playerId === "ball");
    const moves = ballAnim?.movement || [];
    
    if (moves.length > 1) {
      // Get the shot step (usually the second movement)
      const shotStep = moves[1];
      if (shotStep?.coords) {
        return shotStep.coords; // Return grid coordinates directly
      }
    }
    
    // Fallback to team-based rim coordinates
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    return isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  }

  /**
   * Get rim coordinates based on free throw context (legacy method)
   */
  getRimCoordinates(turnData) {
    // Determine which rim based on team
    // ✅ FIX: Use offense_team_id (SS&S possession system)
    const isHomeTeam = turnData.offense_team_id === this.scene.homeTeamId;
    return isHomeTeam ? this.ftConfig.homeRim : this.ftConfig.awayRim;
  }


  /**
   * Adapt backend data structure to new system format
   */
  adaptBackendData(backendData) {
    // Backend provides: attempts: ["MAKE"] or ["MISS"]
    // New system expects: actual_result: "MAKE" or "MISS"
    
    const attempts = backendData.attempts || [];
    const actualResult = attempts.length > 0 ? attempts[0] : 'MISS';
    
    // Backend provides: ftContext from annotateFreeThrowTurns
    // New system expects: ftContext with attempt/total structure
    // ✅ FIX: Do NOT set isFinal here - let determineFreeThrowContext() be the single source of truth
    // isFinal must be calculated using free_throws_remaining, not just ftIndex/ftTotal
    
    const ftContext = backendData.ftContext || {};
    const adaptedFtContext = {
      attempt: ftContext.ftIndex || 1,
      total: ftContext.ftTotal || 1,
      type: ftContext.bonusType || 'single',
      // ✅ FIX: Do not set isFinal here - it will be calculated correctly in determineFreeThrowContext()
      // based on free_throws_remaining from backend
    };
    
    return {
      ...backendData,
      actual_result: actualResult,
      ftContext: adaptedFtContext
    };
  }

  /**
   * Determine free throw context
   */
  determineFreeThrowContext(turnData) {
    const ftContext = turnData.ftContext || {};
    
    // ✅ FIX: Support both naming conventions (ftIndex/ftTotal from annotateFreeThrowTurns, attempt/total from backend)
    // annotateFreeThrowTurns sets ftIndex/ftTotal, but we were looking for attempt/total
    const attempt = ftContext.ftIndex || ftContext.attempt || 1;
    const total = ftContext.ftTotal || ftContext.total || 1;
    
    // ✅ FIX: free_throws_remaining is the AUTHORITATIVE source for determining if this is the final FT
    // free_throws_remaining is AFTER this shot, so:
    // - If free_throws_remaining > 0: More FTs remain, this is NOT final
    // - If free_throws_remaining === 0: No more FTs remain, this IS final
    // - If free_throws_remaining is undefined: Fall back to ftIndex/ftTotal (batch mode)
    // Phase 5: Final Turn blocking foul — backend sends exactly 2 FTs; do not override (use as-is).
    let isFinal;
    if (turnData.free_throws_remaining !== undefined) {
      // Turn-by-turn mode: Use free_throws_remaining as authoritative
      isFinal = turnData.free_throws_remaining === 0;
    } else {
      // Batch mode: Fall back to ftIndex/ftTotal (legacy support)
      isFinal = (attempt >= total);
    }
    
    return {
      attempt: attempt,
      total: total,
      type: ftContext.type || 'single',
      isFinal: isFinal
    };
  }

  /**
   * Helper methods
   */
  getShooterSprite(turnData) {
    // Try to get shooter ID from the turn data
    let shooterId = turnData.shooter_id || turnData.player_id;
    
    // If no ID, try to find by name using rosters
    if (!shooterId) {
      const shooterName = turnData.shooter || turnData.ball_handler;
      if (shooterName) {
        shooterId = this.findPlayerIdByName(shooterName);
      }
    }
    
    return this.playerSprites[shooterId] || null;
  }

  findPlayerIdByName(playerName) {
    if (!playerName) return null;
    
    // Check home roster
    const homeRoster = this.gameStore.getHomeRoster();
    if (homeRoster && homeRoster.players) {
      for (const player of homeRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id;
        }
      }
    }
    
    // Check away roster
    const awayRoster = this.gameStore.getAwayRoster();
    if (awayRoster && awayRoster.players) {
      for (const player of awayRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id;
        }
      }
    }
    
    return null;
  }

  validateFreeThrowData(turnData) {
    return turnData && 
           (turnData.shooter || turnData.ball_handler || turnData.shooter_id) &&
           turnData.result_type === 'FREE_THROW' &&
           (turnData.actual_result === 'MAKE' || turnData.actual_result === 'MISS');
  }

  /**
   * Process queued free throw sequences
   */
  async processSequenceQueue() {
    if (this.sequenceQueue.length === 0) return;

    const nextSequence = this.sequenceQueue.shift();
    if (nextSequence) {
      await this.processFreeThrow(nextSequence);
    }
  }

  /**
   * Handle free throw errors
   */
  handleFreeThrowError(error, turnData) {
    console.error('FreeThrowAnimationSystem: Free throw error', {
      error: error.message,
      turnData,
      activeSequence: this.activeSequence
    });

    // Reset to safe state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'free_throw_error',
        error: error.message
      });
    }

    // Hide ball if visible
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      ballSprite.setVisible(false);
    }
  }

  /**
   * Get free throw system status
   */
  getStatus() {
    return {
      activeSequence: this.activeSequence?.index || null,
      sequenceQueue: this.sequenceQueue.length,
      isProcessing: !!this.activeSequence,
      currentAttempt: this.currentAttempt,
      totalAttempts: this.totalAttempts,
      ftConfig: this.ftConfig
    };
  }

  /**
   * Update free throw configuration
   */
  updateConfig(newConfig) {
    this.ftConfig = { ...this.ftConfig, ...newConfig };
    
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Config updated', this.ftConfig);
    }
  }

  /**
   * Reset free throw system
   */
  reset() {
    this.activeSequence = null;
    this.sequenceQueue = [];
    this.currentAttempt = 0;
    this.totalAttempts = 0;
    
    // Hide ball
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      ballSprite.setVisible(false);
    }
    
    // ✅ REMOVED: Free throw reset logging (cluttering console)
  }
}

export default FreeThrowAnimationSystem;
