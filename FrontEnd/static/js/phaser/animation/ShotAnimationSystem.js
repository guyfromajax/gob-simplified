/**
 * ShotAnimationSystem - Universal Shot Animation Handler
 * 
 * Handles all shot types using the new Phase 1 components:
 * - Regular half-court shots
 * - Fast break shots  
 * - Free throw shots
 * - Putback shots
 * 
 * Key Benefits:
 * - Single system for all shot types
 * - Consistent ball behavior
 * - Proper state management
 * - No floating balls or teleports
 */

import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';
import { gridToPixels } from '../utils/gridToPixels.js';
import { animateStep } from './animateStep.js';
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, getMadeShotSweetSpotGrid } from './courtConstants.js';
import { getPlayerDuration } from './turnAnimation.js';
import animationConfig from './animation_config.js';
import { clampGridCoords } from './courtClamp.js';
import { enforceUnitCompletionContract } from './unitCompletionContract.js';
import { runPass } from './ballTween.js';
import { playShotLaunchSfx, playShotResultSfx, playGameSfx, playReboundSfx } from '../utils/gameSfx.js';
import { announceReboundHeadlineIfNeeded } from '../utils/announcements.js';
import { createBallTrail } from './createBallTrail.js';

export class ShotAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    this._getBackTweens = null; // Store get-back tween references
    // ✅ TEMP FIX: Track defensive player IDs from skeleton animation for tween cleanup
    // TODO: Remove if this fix doesn't resolve the animation sync issue
    this._skeletonDefensivePlayerIds = [];
    
    // Debug logging removed for cleaner console
    
    // Shot configuration
    this.shotConfig = {
      // Ball flight parameters
      flightDuration: 800, // ms
      flightEase: 'Power2',
      
      // Ball bounce parameters
      bounceDuration: 600, // ms
      bounceEase: 'Bounce',
      bounceDistance: 30, // pixels
      
      // Rim coordinates (from courtConstants.js)
      homeRim: HOME_RIM_COORDS,
      awayRim: AWAY_RIM_COORDS
    };
    
    // Active shot tracking
    this.activeShot = null;
    this.shotQueue = [];
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Initialized');
    }
  }

  async runStep0EntryPassIfNeeded(ballSprite, currentBallOwnerRef, liveOwnerId, step0OwnerId) {
    if (liveOwnerId == null || step0OwnerId == null) return false;
    const fromId = String(liveOwnerId);
    const toId = String(step0OwnerId);
    if (!fromId || !toId || fromId === toId) return false;
    const fromSprite = this.playerSprites?.[fromId];
    const toSprite = this.playerSprites?.[toId];
    if (!fromSprite || !toSprite) return false;

    const {
      attachBallToPlayer,
      setCurrentOwner,
      clearPendingOwner,
    } = await import('./BallControllerAdapter.js');
    const { setBallHolderId } = await import('./ballAnimationSimple.js');

    attachBallToPlayer(this.scene, ballSprite, fromSprite, { reason: 'final_turn_step0_entry_pass_start' });
    currentBallOwnerRef.value = fromSprite;
    setBallHolderId(this.scene, fromId);
    setCurrentOwner(this.scene, fromId);
    clearPendingOwner(this.scene);

    await runPass(this.scene, {
      fromId,
      toId,
      endCoords: { x: toSprite.x, y: toSprite.y },
      easing: 'Sine.easeInOut',
    });

    attachBallToPlayer(this.scene, ballSprite, toSprite, { reason: 'final_turn_step0_entry_pass_complete' });
    currentBallOwnerRef.value = toSprite;
    setBallHolderId(this.scene, toId);
    setCurrentOwner(this.scene, toId);
    clearPendingOwner(this.scene);
    return true;
  }

  resolveOrebContractMode() {
    const raw = String(
      (typeof window !== 'undefined' ? window.UESS_OREB_CONTRACT_MODE : null) ?? 'observe'
    )
      .trim()
      .toLowerCase();
    if (raw === 'off' || raw === 'observe' || raw === 'warn' || raw === 'throw') return raw;
    return 'observe';
  }

  getOrebBudgetGameSeconds(kind = 'decision') {
    const scope = typeof window !== 'undefined' ? window : globalThis;
    const generic =
      kind === 'decision'
        ? Number(scope?.UESS_OREB_DECISION_MAX_GAME_SECONDS)
        : Number(scope?.UESS_OREB_ACTION_MAX_GAME_SECONDS);
    if (Number.isFinite(generic) && generic > 0) return generic;
    return kind === 'decision' ? 2 : 3;
  }

  emitOrebContractTelemetry(turnData, event, payload = {}) {
    this.scene?.events?.emit?.('animTelemetry', {
      event,
      branchKind: 'oreb_phase_contract',
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: this.scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: this.scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? this.scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    });
  }

  enforceOrebUnitContract({
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
    const mode = this.resolveOrebContractMode();
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
      this.emitOrebContractTelemetry(turnData, 'oreb_phase_clock_overrun', {
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
        this.emitOrebContractTelemetry(turnData, event, payload),
      logger,
    });
    if (mode === 'throw' && overrun) {
      throw new Error(
        `[OREB contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
      );
    }
  }

  /**
   * Process a shot turn with complete player movement
   */
  async processShot(turnData) {
    // Shot processing (debug log removed)
    if (false) console.log('[Shot Debug]', {
      result_type: turnData.result_type,
      shooter_id: turnData.shooter_id,
      turn_index: turnData.index,
      hasPlayerSprites: !!this.playerSprites,
      playerSpritesCount: this.playerSprites ? Object.keys(this.playerSprites).length : 0
    });
    
    const isHCO = turnData.play_type === 'HCO' || turnData.playcall === 'HCO';
    // ✅ REMOVED: Shot attempt logging (cluttering console)
    
    if (this.activeShot) {
      console.warn('ShotAnimationSystem: Already processing a shot, queuing...');
      this.shotQueue.push(turnData);
      return;
    }

    this.activeShot = turnData;
    
    try {
      if (DebugFlags.SHOT_ANIMATION) {
        console.log('ShotAnimationSystem: Processing shot', {
          result_type: turnData.result_type,
          shooter_id: turnData.shooter_id,
          shot_type: turnData.shot_type
        });
      }

      // Validate shot data
      if (!this.validateShotData(turnData)) {
        console.error('❌ ShotAnimationSystem: Shot data validation failed', {
          result_type: turnData.result_type,
          shooter: turnData.shooter,
          ball_handler: turnData.ball_handler,
          hasResultType: !!turnData.result_type,
          isMakeOrMiss: turnData.result_type === 'MAKE' || turnData.result_type === 'MISS' || turnData.result_type === 'BLOCK',
          hasShooter: !!(turnData.shooter || turnData.ball_handler)
        });
        throw new Error('Invalid shot data');
      }

      // Execute complete shot sequence with player movement
      await this.executeCompleteShotSequence(turnData);

      // Process any queued shots
      await this.processShotQueue();

    } catch (error) {
      console.error('ShotAnimationSystem: Error processing shot', error);
      this.handleShotError(error, turnData);
    } finally {
      this.activeShot = null;
    }
  }

  /**
   * Execute complete shot sequence with player movement
   */
  async executeCompleteShotSequence(turnData) {
    this._applyDebugVariantOverride(turnData);
    const ballSprite = this.ballController.ballSprite;

    // ✅ MATCH playTurnAnimation EXACTLY: Initialize ball holder state
    const { initializeBallHolderState, clearBallHolder } = await import('./ballAnimationSimple.js');
    const { clearPendingOwner } = await import('./BallControllerAdapter.js');
    initializeBallHolderState(this.scene);
    
    // ✅ MATCH playTurnAnimation EXACTLY: Reset scene flags
    const fromInbound = this.scene._previousTurnWasInbound === true;
    const fromOpeningTip = this.scene._previousTurnWasOpeningTip === true;
    this.scene.passInFlight = false;
    this.scene.rebounderId = null;
    
    // ✅ MATCH playTurnAnimation EXACTLY: Clear ball state (if not from inbound/tip)
    if (!fromInbound && !fromOpeningTip) {
      clearPendingOwner(this.scene);
      clearBallHolder(this.scene);
    }
    
    const currentBallOwnerRef = { value: null };
    
    // ✅ MATCH playTurnAnimation EXACTLY: Store reference on scene
    this.scene.currentBallOwnerRef = currentBallOwnerRef;
    
    // ✅ MATCH playTurnAnimation EXACTLY: Calculate maxSteps (with same filtering)
    const maxSteps = turnData.animations && turnData.animations.length > 0
      ? Math.max(
          ...turnData.animations
            .filter(anim => anim.movement && Array.isArray(anim.movement))
            .map(anim => anim.movement.length)
        )
      : 0;
    let step0OwnerId = null;
    for (const anim of turnData.animations || []) {
      if (anim?.hasBallAtStep?.[0]) {
        step0OwnerId = anim.playerId != null ? String(anim.playerId) : null;
        break;
      }
    }
    const {
      getCurrentOwner,
      getPendingOwner,
      updateBallOwnership,
    } = await import('./BallControllerAdapter.js');
    const liveOwnerId = getCurrentOwner(this.scene) ?? getPendingOwner(this.scene) ?? null;
    const requiresStep0EntryPass =
      turnData.final_turn === true &&
      liveOwnerId != null &&
      step0OwnerId != null &&
      String(liveOwnerId) !== String(step0OwnerId);
    
    // 1. Setup: Move players to step 0 positions. Final Turn usually skips this because Phase 4
    // already aligned players, but we still run it when a real step-0 handoff is required.
    if (!turnData.final_turn || requiresStep0EntryPass) {
      await this.runSetupTween(turnData, ballSprite, currentBallOwnerRef);
    } else {
      const delayMs = animationConfig?.finalTurn?.moveDelayMs ?? 0;
      if (delayMs > 0) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
    
    // ✅ MATCH playTurnAnimation EXACTLY: Update ball ownership at step 0
    if (!requiresStep0EntryPass) {
      updateBallOwnership({
        scene: this.scene,
        ballSprite,
        animations: turnData.animations,
        playerSprites: this.playerSprites,
        stepIndex: 0,
        offenseTeamId: this.scene.offenseTeamId ?? turnData.possession_team_id,
        currentBallOwnerRef
      });
    }
    
    // ✅ CRITICAL FIX: Match playTurnAnimation's ball attachment logic exactly
    // Determine which player owns the ball at step 0
    // BUT: Skip this if the previous turn was a shot (MAKE or MISS)
    // After a shot, the ball should remain at the rim/bounce spot until the next turn's animation moves it
    const previousTurnWasShot = this.scene._previousTurnWasShot === true;
    if (previousTurnWasShot) {
      this.scene._previousTurnWasShot = false; // Clear the flag
    }
    
    // ✅ CRITICAL FIX: If we are coming directly from an inbound or opening tip, the ball should already be attached
    // to the inbound receiver or tip winner, so we don't re-derive or re-attach at step 0.
    // Phase 5: Final Turn — ball already attached to ball handler in runFinalTurnAlignment.
    let step0OwnerSprite = null;
    if (!previousTurnWasShot && !fromInbound && !fromOpeningTip && !turnData.final_turn && !requiresStep0EntryPass) {
      for (const anim of turnData.animations) {
        if (anim.hasBallAtStep?.[0]) {
          step0OwnerSprite = this.playerSprites[anim.playerId];
          break;
        }
      }
      
      if (step0OwnerSprite) {
        const step0OwnerId = step0OwnerSprite.playerId;
        const { setBallHolderId } = await import('./ballAnimationSimple.js');
        this.ballController.attachToPlayer(step0OwnerSprite);
        currentBallOwnerRef.value = step0OwnerSprite;
        
        // ✅ MATCH playTurnAnimation EXACTLY: Also set simple ball holder ID (WIP_GOB approach)
        setBallHolderId(this.scene, step0OwnerId);
      }
    } else {
      // Coming from inbound/tip or previous was shot - ball is already attached, don't re-attach
      // ✅ REMOVED: Step 0 ball attachment logging (cluttering console)
    }
    
    // ✅ MATCH playTurnAnimation EXACTLY: Clear inbound and opening tip flags after applying pre-step setup
    if (this.scene._previousTurnWasInbound) {
      this.scene._previousTurnWasInbound = false;
    }
    if (this.scene._previousTurnWasOpeningTip) {
      this.scene._previousTurnWasOpeningTip = false;
    }
    if (requiresStep0EntryPass) {
      await this.runStep0EntryPassIfNeeded(
        ballSprite,
        currentBallOwnerRef,
        liveOwnerId,
        step0OwnerId,
      );
    }
    
    // 3. Animate step-by-step player movement
    await this.animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps);
    
    // 4. Handle shot outcome (BLOCK treated like MISS for handling)
    const isMake = turnData.result_type === 'MAKE';
    // BLOCK: use block spot as reference for miss path so bounce/rebound stay on correct side (no snap to rim)
    const isBlock = turnData.result_type === 'BLOCK';
    const rimCoords = (isBlock && turnData.ball_bounce_x != null && turnData.ball_bounce_y != null)
      ? gridToPixels(turnData.ball_bounce_x, turnData.ball_bounce_y, this.scene.game.config.width, this.scene.game.config.height)
      : this.getRimCoordinates(turnData);

    // Variant-specific intermediate animation (rattle / backboard) between ball flight
    // landing and the standard make/miss resolution. Skipped for BLOCK.
    if (!isBlock) {
      await this.executeShotVariantAnimation(turnData);
    }

    // Execute make or miss handling (BLOCK goes to handleMissedShot)
    if (isMake) {
      await this.handleMadeShot(rimCoords, turnData);
    } else {
      await this.handleMissedShot(rimCoords, turnData);
    }
  }
  
  /**
   * Move all players to their step 0 positions
   */
  async runSetupTween(turnData, ballSprite, currentBallOwnerRef) {
    if (this.scene.skipToEnd) return;
    
    // getPlayerDuration is already imported at top of file
    const stepIndex = 0;
    const promises = [];
    
    for (const anim of turnData.animations) {
      if (this.scene.skipToEnd) break;
      const sprite = this.playerSprites[anim.playerId];
      const firstStep = anim.movement?.[stepIndex];
      if (!sprite || !firstStep) continue;
      
      const { x, y } = gridToPixels(
        firstStep.coords.x,
        firstStep.coords.y,
        this.scene.game.config.width,
        this.scene.game.config.height
      );
      
      // ✅ FIX: Use distance-based duration for consistent speed (matches step animations)
      // This ensures smooth transitions between turns and consistent speeds
      const duration = getPlayerDuration(sprite, x, y);
      
      promises.push(new Promise((resolve) => {
        const tween = this.scene.tweens.add({
          targets: [sprite],
          x,
          y,
          duration,
          ease: "Linear",
          // ✅ FIX: Removed manual ball positioning - BallController handles ball following automatically
          // When ball is attached via attachToPlayer(), it automatically follows the player
          // Manual setPosition() calls conflict with BallController's following system
          onComplete: resolve,
          onStop: resolve
        });
        if (this.scene.skipToEnd) {
          tween.stop();
        }
      }));
    }
    
    await Promise.all(promises);
  }
  
  /**
   * Animate player movement step by step
   */
  async animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps) {
    if (false) console.log('[Player Movement Debug]', {
      maxSteps,
      result_type: turnData.result_type,
      skipToEnd: this.scene.skipToEnd,
      hasBallSprite: !!ballSprite,
      hasTweens: !!this.scene.tweens
    });
    
    if (this.scene.skipToEnd) {
      console.log('⚠️ [ShotAnimationSystem.animatePlayerMovement] Skipping - skipToEnd is true');
      return;
    }

    // 🔍 [SHOT ANIM PAYLOAD] One-time log to compare "good" vs "bad" turns (e.g. MAKE/OREB vs MISS+DREB)
    const { detectPassAtStep } = await import('./passDetection.js');
    const passAtSteps = [];
    for (let si = 1; si < maxSteps; si++) {
      if (detectPassAtStep(turnData.animations, si)) passAtSteps.push(si);
    }
    const animSummary = (turnData.animations || []).map(a => ({
      id: (a.playerId || '').toString().substring(0, 8),
      movementLen: (a.movement && Array.isArray(a.movement)) ? a.movement.length : 0
    }));
    console.log('🔍 [SHOT ANIM PAYLOAD]', {
      result_type: turnData.result_type,
      rebound_type: turnData.rebound_type ?? null,
      animationsCount: (turnData.animations || []).length,
      maxSteps,
      passAtSteps,
      animSummary
    });

    // 🔍 [SHOT ANIM STATE] Cross-turn state at start of this shot turn (compare after DREB vs after MAKE/OREB)
    console.log('🔍 [SHOT ANIM STATE]', {
      result_type: turnData.result_type,
      rebound_type: turnData.rebound_type ?? null,
      passInFlight: this.scene.passInFlight === true,
      currentBallOwnerId: currentBallOwnerRef?.value?.playerId ?? null,
      _previousTurnWasShot: this.scene._previousTurnWasShot === true,
      sceneRebounderId: this.scene.rebounderId ?? null
    });

    // ✅ CRITICAL FIX: Kill all ball tweens before starting step loop
    // Lingering ball tweens from previous shots/passes can block the tween manager
    if (ballSprite && this.scene.tweens) {
      const ballActiveTweens = this.scene.tweens.getTweensOf ? this.scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        console.warn('🔧 [BALL TWEEN CLEANUP] Killing lingering ball tweens before step loop (ShotAnimationSystem)', {
          ballActiveTweensCount: ballActiveTweens.length,
          ballActiveTweenIds: ballActiveTweens.map(t => t._animateStepId || 'no-id')
        });
        this.scene.tweens.killTweensOf(ballSprite);
        // Also kill ball shadow tweens if they exist
        if (this.scene.ballShadowSprite) {
          this.scene.tweens.killTweensOf(this.scene.ballShadowSprite);
        }
      }
    }
    
    // ✅ REMOVED: Special FCP/HCT handling - FCP/HCT now uses exact same path as HCO
    // Skeletons are in same format, so no special handling needed
    
    // ✅ SS&S FIX: Resolve offenseTeamId once at turn start and classify all players
    // This ensures consistent player classification throughout the turn
    const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
    const offenseTeamId = resolveOffenseTeamId({
      scene: this.scene,
      turnData,
      playerSprites: this.playerSprites,
      passInfo: null // No passInfo at turn start, will be detected per step
    });
    
    // ✅ SS&S: Classify all players once at turn start
    const playerClassifications = {}; // Map: playerId -> 'offense' | 'defense'
    let offensiveCount = 0;
    let defensiveCount = 0;
    
    // ✅ TEMP FIX: Track defensive player IDs for tween cleanup before animatePlayerCollapse()
    // TODO: Remove if this fix doesn't resolve the animation sync issue
    this._skeletonDefensivePlayerIds = [];
    
    for (const anim of turnData.animations) {
      const sprite = this.playerSprites[anim.playerId];
      if (!sprite) {
        continue;
      }
      
      const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
      playerClassifications[anim.playerId] = isOffensivePlayer ? 'offense' : 'defense';
      
      if (isOffensivePlayer) {
        offensiveCount++;
      } else {
        defensiveCount++;
        // ✅ TEMP FIX: Store defensive player IDs for later tween cleanup
        this._skeletonDefensivePlayerIds.push(anim.playerId);
      }
    }
    
    // ✅ VALIDATION: Ensure we have exactly 5 offensive and 5 defensive players
    // only on full-roster turns. Embedded helper/synthetic paths may not include
    // all 10 animations and should not trigger false positives.
    const expectedFullRosterClassification =
      Array.isArray(turnData?.animations) && turnData.animations.length >= 10;
    if (expectedFullRosterClassification && (offensiveCount !== 5 || defensiveCount !== 5)) {
      console.warn('⚠️ [PLAYER CLASSIFICATION] Expected 5 offensive and 5 defensive players, but got:', {
        resultType: turnData?.result_type ?? null,
        animationCount: turnData?.animations?.length ?? 0,
        offensiveCount,
        defensiveCount
      });
    }
    
    for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
      if (this.scene.skipToEnd) break;
      
      // ✅ FIX: Match playTurnAnimation - detect pass BEFORE updateBallOwnership
      // This prevents updateBallOwnership from teleporting ball during pass animations
      const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
      const passHappeningAtThisStep = !!detectPassAtStep(turnData.animations, stepIndex);
      
      // ✅ FIX: Match playTurnAnimation - skip updateBallOwnership if pass is happening
      // or if pass just completed (passInFlight is still true from previous step)
      if (!passHappeningAtThisStep && !this.scene.passInFlight) {
        this.updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex);
      } else if (this.scene.passInFlight && !passHappeningAtThisStep) {
        // Pass just completed, clear the flag now that we've skipped updateBallOwnership
        this.scene.passInFlight = false;
        // ✅ COMMENTED OUT: Pass animation logs (cluttering console)
        // console.log('🏀 [PASS ANIMATION] Cleared passInFlight after skipping updateBallOwnership');
      }
      
      const promises = [];
      let shotInfo = null;
      
      // ✅ COMMENTED OUT: Starting pass detection log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Starting pass detection`, {
      //   turnId: turnData?.id?.substring(0, 8),
      //   totalAnimations: turnData.animations?.length,
      //   maxSteps: maxSteps
      // });
      
      // ✅ COMMENTED OUT: Movement array structure log (cluttering console)
      // const movementArrayInfo = turnData.animations.map(anim => ({
      //   playerId: anim.playerId?.substring(0, 8) || 'unknown',
      //   movementLength: anim.movement?.length || 0,
      //   hasStep: stepIndex < (anim.movement?.length || 0),
      //   stepAction: stepIndex < (anim.movement?.length || 0) ? anim.movement[stepIndex]?.action : 'N/A',
      //   stepTimestamp: stepIndex < (anim.movement?.length || 0) ? anim.movement[stepIndex]?.timestamp : 'N/A'
      // }));
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Movement array structure`, movementArrayInfo);
      
      // ✅ SCALABLE FIX: Use shared pass detection utility
      // This ensures passes work for HCO shots, fouls, turnovers, etc.
      const passInfo = detectPassAtStep(turnData.animations, stepIndex);
      // 🔍 [SHOT ANIM TIMING] Collect defender tween start times only on first step that has a pass
      const isFirstPassStep = passAtSteps.length > 0 && stepIndex === passAtSteps[0];
      const step4DefenderStarts = isFirstPassStep ? [] : null;

      // ✅ COMMENTED OUT: Pass detection result log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Pass detection result`, {
      //   passInfo: passInfo ? {
      //     passer: passInfo.passerId?.substring(0, 8),
      //     receiver: passInfo.receiverId?.substring(0, 8),
      //     stepIndex: passInfo.stepIndex
      //   } : null,
      //   passHappeningAtThisStep: !!passInfo
      // });
      
      // ✅ SS&S: Use pre-classified player roles (determined at turn start)
      // No need to re-resolve offenseTeamId or re-classify players per step
      const offensivePromises = [];
      const defensivePromises = [];
      let passerPromise = null;
      
      for (const anim of turnData.animations) {
        if (this.scene.skipToEnd) break;
        const sprite = this.playerSprites[anim.playerId];
        const movement = anim.movement;
        
        if (!sprite || stepIndex >= movement.length) continue;
        
        const prev = movement[stepIndex - 1];
        const curr = movement[stepIndex];
        const step = prev;
        const nextStep = curr;
        
        // ✅ FIX: Use distance-based duration calculation (matches old system)
        // This ensures consistent speeds, respects game speed settings, and matches transition animations
        const { x: targetX, y: targetY } = gridToPixels(
          nextStep.coords.x,
          nextStep.coords.y,
          this.scene.game.config.width,
          this.scene.game.config.height
        );
        const duration = getPlayerDuration(sprite, targetX, targetY);
        
        if (nextStep.action === "shoot") {
          shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        }
        
        // ✅ FIX: Match playTurnAnimation's animateStep call signature exactly
        // Pass step (prev) and nextStep (curr) separately, plus stepIndex
        // This ensures animateStep can properly calculate positions and handle actions
        
        // 🔍 TIMING: Track when animateStep() is called (tween starts immediately when called)
        const beforeAnimateStep = performance.now();
        const promise = animateStep({
          scene: this.scene,
          sprite,
          step: prev,  // Previous step (for position calculation)
          nextStep: curr,  // Current step target
          duration,
          ballSprite,
          currentBallOwnerRef,
          onAction: null, // We'll handle actions separately
          stepIndex  // Pass stepIndex to identify first step
        });
        const afterAnimateStep = performance.now();
        
        // ✅ SS&S: Use pre-classified player role (determined at turn start)
        // This ensures consistent classification throughout the turn
        const playerRole = playerClassifications[anim.playerId] || 'defense'; // Default to defense if not found
        const isOffensivePlayer = playerRole === 'offense';
        
        if (isOffensivePlayer) {
          offensivePromises.push(promise);
          // Track passer's promise separately so we can wait for it before starting pass
          if (passInfo && anim.playerId === passInfo.passerId) {
            passerPromise = promise;
          }
        } else {
          if (step4DefenderStarts) {
            step4DefenderStarts.push({
              id: (anim.playerId || '').toString().substring(0, 8),
              startTime: beforeAnimateStep
            });
          }
          defensivePromises.push({
            promise,
            playerId: anim.playerId
          });
        }
      }
      
      // ✅ COMMENTED OUT: Defensive animation decision log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Defensive animation decision`, {
      //   hasPassInfo: !!passInfo,
      //   defensivePromisesCount: defensivePromises.length,
      //   willStartInPhase2: true // ShotAnimationSystem always starts defenders in Phase 2
      // });
      
      // Phase 1 — Offense-gated: same as playTurnAnimation (defense tweens already running from loop).
      const phase1StartTime = performance.now();
      if (passInfo && passerPromise) {
        await passerPromise;
      } else if (offensivePromises.length > 0) {
        await Promise.all(offensivePromises);
      }

      // Phase 2 — Await pass only; do not gate the step on defensive completion.
      const phase2StartTime = performance.now();
      if (passInfo) {
        const passPromise = handlePassAnimation({
          scene: this.scene,
          passInfo,
          playerSprites: this.playerSprites,
          enablePassSfx: ["HCO", "HCT", "FCP"].includes(turnData?.current_turn),
        });
        await passPromise;
      }

      if (step4DefenderStarts && step4DefenderStarts.length > 0) {
        const earliest = Math.min(...step4DefenderStarts.map((d) => d.startTime));
        console.log("🔍 [SHOT ANIM TIMING]", {
          stepIndex,
          result_type: turnData.result_type,
          rebound_type: turnData.rebound_type ?? null,
          phase2StartTime,
          defenderStarts: step4DefenderStarts,
          earliestDefenderStart: earliest,
          msFromFirstDefenderToPhase2: Math.round(phase2StartTime - earliest),
        });
      }

      // Phase 3 — After pass, wait for all offensive step tweens (passer already resolved).
      if (passInfo && offensivePromises.length > 0) {
        await Promise.all(offensivePromises);
      }
      
      // Handle shot if this step contains one
      if (shotInfo) {
        currentBallOwnerRef.value = null;
        await this.handleShotAtStep(shotInfo, turnData);
      }
    }
    
    // ✅ REMOVED: Player movement completed logging (cluttering console)
  }
  
  /**
   * Update ball ownership for a specific step
   * Delegates to unified updateBallOwnership function
   */
  async updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex) {
    const { updateBallOwnership: unifiedUpdate } = await import('./BallControllerAdapter.js');
    return unifiedUpdate({
      scene: this.scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites: this.playerSprites,
      stepIndex,
      currentBallOwnerRef
    });
  }
  
  /**
   * Handle shot at a specific step
   */
  async handleShotAtStep(shotInfo, turnData) {
    const shooterSprite = this.playerSprites[shotInfo.playerId];
    // Variant-aware flight target. BLOCK keeps its existing block-spot path.
    const flightTargetGrid = this._getShotFlightTargetGrid(turnData);
    const flightTargetPixels = gridToPixels(
      flightTargetGrid.x,
      flightTargetGrid.y,
      this.scene.game.config.width,
      this.scene.game.config.height
    );
    
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Handling shot at step', {
    //   stepIndex: shotInfo.stepIndex,
    //   shooterId: shotInfo.playerId,
    //   isMake
    // });
    
    // ✅ PRIORITY 1 FIX: Use BallController lifecycle method instead of direct detach
    // This matches the pattern used in ballManager.js (line 233)
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Starting shot via lifecycle method', {
    //   shooterId: shotInfo.playerId,
    //   ballControllerState: this.ballController.getState()
    // });
    this.ballController.onShotStart({ 
      shooterId: shotInfo.playerId,
      isPutback: turnData.result_type === 'PUTBACK_MAKE' || turnData.result_type === 'PUTBACK_MISS'
    });
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Shot started, new state:', this.ballController.getState());
    
    // Animate ball flight
    await this.animateBallFlight(shooterSprite, flightTargetPixels, turnData);
  }

  /**
   * Animate ball flight from shooter to rim
   */
  async animateBallFlight(shooterSprite, rimCoords, turnData) {
    return new Promise((resolve) => {
      // Get ball sprite
      const ballSprite = this.ballController.ballSprite;
      if (!ballSprite) {
        console.warn('ShotAnimationSystem: No ball sprite available');
        resolve();
        return;
      }

      // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
      // console.log('🎯 ShotAnimationSystem: Starting ball flight', {
      //   from: { x: shooterSprite.x, y: shooterSprite.y },
      //   to: rimCoords,
      //   shooterId: turnData.shooter_id
      // });

      // ✅ PRIORITY 1 FIX: BallController manages ball position and visibility automatically
      // onShotStart() already detached the ball, so we just need to ensure it's visible
      // BallController will handle positioning during the tween
      if (ballSprite) {
        ballSprite.setVisible(true);
      }
      playShotLaunchSfx(this.scene, turnData);

      // ==================== ANIMATE PLAYERS DURING SHOT ====================
      // getPlayerDuration is already imported at top of file
      
      // Store get-back player tweens so we can stop them early if needed
      this._getBackTweens = [];
      
      // Defenders releasing for fast break
      if (turnData.defense_release && turnData.defense_release.length > 0) {
        turnData.defense_release.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            let targetX, targetY;
            
            // ✅ Backend calculates and stores release coordinates in defense_release_coords
            // Use backend coordinates (SS&S: backend is single source of truth)
            if (turnData.defense_release_coords && turnData.defense_release_coords[playerId]) {
              const storedCoords = turnData.defense_release_coords[playerId];
              targetX = storedCoords.x;
              targetY = storedCoords.y;
            } else {
              // Fallback: Use safe defaults if backend coordinates missing (shouldn't happen)
              console.error('⚠️ [DEFENSE RELEASE] Missing backend coordinates, using safe defaults', {
                playerId,
                hasDefenseReleaseCoords: !!turnData.defense_release_coords
              });
              targetX = 50; // Safe default: center court
              targetY = 25; // Safe default: mid-court
            }
            
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            // ✅ FIX: Use distance-based duration for consistent speed
            const duration = getPlayerDuration(sprite, targetPixel.x, targetPixel.y);
            
            this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration,
              ease: 'Linear' // Match other player movements
            });
          }
        });
      }
      
      // Offensive players getting back on defense
      if (turnData.offense_getback && turnData.offense_getback.length > 0) {
        turnData.offense_getback.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            // ✅ SS&S: Use stored coordinates from backend (single source of truth)
            // Backend calculates and stores get-back coordinates in offense_getback_coords
            let targetX, targetY;
            if (turnData.offense_getback_coords && turnData.offense_getback_coords[playerId]) {
              // Use stored coordinates from backend
              const storedCoords = turnData.offense_getback_coords[playerId];
              targetX = storedCoords.x;
              targetY = storedCoords.y;
            } else {
              // Fallback: Use safe defaults if backend coordinates missing (shouldn't happen)
              console.error('⚠️ [OFFENSE GET BACK] Missing backend coordinates, using safe defaults', {
                playerId,
                hasOffenseGetbackCoords: !!turnData.offense_getback_coords
              });
              targetX = 50; // Safe default: center court
              targetY = 25; // Safe default: mid-court
            }
            
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            // ✅ FIX: Use distance-based duration for consistent speed
            const duration = getPlayerDuration(sprite, targetPixel.x, targetPixel.y);
            
            const tween = this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration,
              ease: 'Linear' // Match other player movements
            });
            
            // Store tween reference for early termination
            this._getBackTweens.push(tween);
          }
        });
      }
      
      // ==================== REBOUND POSITIONING ====================
      // Animate potential rebounders (not shooter, defender, get-back, or release players)
      // into rebound position during shot flight
      
      // Build exclusion list
      const excludedPlayerIds = new Set();
      if (turnData.shooter_id) excludedPlayerIds.add(turnData.shooter_id); // Shooter
      if (turnData.defenderId) excludedPlayerIds.add(turnData.defenderId); // Shot defender
      if (turnData.defender_id) excludedPlayerIds.add(turnData.defender_id); // Alternative defender field
      if (turnData.defense_release) {
        turnData.defense_release.forEach(id => excludedPlayerIds.add(id)); // Release players
      }
      if (turnData.offense_getback) {
        turnData.offense_getback.forEach(id => excludedPlayerIds.add(id)); // Get back players
      }
      
      // Determine basket coordinates (which basket is being attacked)
      const shooterTeamId = shooterSprite?.team_id || turnData.possession_team_id;
      const homeTeamId = this.scene.simData?.home_team_id || this.scene.simData?.home_team?.team_id;
      const isHomeTeam = String(shooterTeamId) === String(homeTeamId);
      const basketX = isHomeTeam ? 91 : 9; // Home attacks away basket (91), away attacks home basket (9)
      const basketY = 25;
      
      // Animate all potential rebounders into rebound position
      const playerSprites = this.playerSprites || {};
      
      Object.keys(playerSprites).forEach(playerId => {
        if (excludedPlayerIds.has(playerId)) {
          return; // Skip excluded players
        }
        
        const sprite = playerSprites[playerId];
        if (!sprite) {
          return;
        }
        
        // Get player's current position in grid coordinates
        const currentPixelX = sprite.x;
        const currentPixelY = sprite.y;
        
        // Convert pixel to grid (reverse of gridToPixels)
        const canvasWidth = this.scene.game.config.width;
        const canvasHeight = this.scene.game.config.height;
        const currentGridX = (currentPixelX / canvasWidth) * 100;
        const currentGridY = 50 - (currentPixelY / canvasHeight) * 50;
        
        // Calculate target position based on rebound positioning rules
        let targetGridX = currentGridX;
        let targetGridY = currentGridY;
        
        // X movement: Move toward basket if > 3 spots away
        const distanceFromBasket = Math.abs(currentGridX - basketX);
        if (distanceFromBasket > 3) {
          const moveAmount = Phaser.Math.Between(3, 6);
          // Move closer to basket
          if (currentGridX > basketX) {
            targetGridX = currentGridX - moveAmount;
          } else {
            targetGridX = currentGridX + moveAmount;
          }
        }
        // Else: Keep x the same (already close to basket)
        
        // Y movement: Move toward center court (y = 25)
        if (currentGridY > 25) {
          // Move down (negative y)
          const moveAmount = Phaser.Math.Between(1, 6);
          targetGridY = currentGridY - moveAmount;
        } else if (currentGridY < 26) {
          // Move up (positive y)
          const moveAmount = Phaser.Math.Between(1, 6);
          targetGridY = currentGridY + moveAmount;
        }
        // Else: y is exactly 25 or 26, keep it the same (rare)
        
        const clampedReboundTarget = clampGridCoords(
          { x: targetGridX, y: targetGridY },
          turnData,
          { action: "shot_get_back_rebound_window", playerId }
        );
        targetGridX = clampedReboundTarget.x;
        targetGridY = clampedReboundTarget.y;
        
        // Convert target grid back to pixels
        const targetPixel = gridToPixels(targetGridX, targetGridY, canvasWidth, canvasHeight);
        
        // Animate to rebound position (same duration as ball flight)
        this.scene.tweens.add({
          targets: sprite,
          x: targetPixel.x,
          y: targetPixel.y,
          duration: this.shotConfig.flightDuration,
          ease: 'Linear' // Match get-back player ease
        });
      });
      
      // ==================== END REBOUND POSITIONING ====================
      // ==================== END PLAYER POSITIONING ====================

      // Animate ball to rim
      // Hot-shot flame trail: attach to the ball for the duration of the
      // flight tween when the pre-defense shot score crosses the same
      // "strong" threshold (>210) that gates `three-strong.wav` in the
      // launch SFX. Same helper used for outlet-pass flames. Self-cleans.
      const preDefenseScore = Number(turnData?.shot_score_pre_defense);
      if (Number.isFinite(preDefenseScore) && preDefenseScore > 210) {
        createBallTrail(this.scene, ballSprite, this.shotConfig.flightDuration);
      }

      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: this.shotConfig.flightDuration,
        ease: this.shotConfig.flightEase,
        onComplete: () => {
          playShotResultSfx(this.scene, turnData, turnData.result_type);
          // Ball flight completed - no need to call endFlight since we're managing the tween ourselves
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });

      if (DebugFlags.SHOT_ANIMATION) {
        console.log('ShotAnimationSystem: Ball flight started', {
          from: { x: shooterSprite.x, y: shooterSprite.y },
          to: rimCoords,
          duration: this.shotConfig.flightDuration
        });
      }
    });
  }

  /**
   * Handle made shot
   */
  async handleMadeShot(rimCoords, turnData) {
    // ✅ REMOVED: Made shot logging (cluttering console)
    const isPutbackMake = turnData.result_type === 'PUTBACK_MAKE';
    const isTerminalQuarterEndShot = turnData?.quarter_ends_after === true;
    
    // 🔍 STATE COMPARISON: Log state at start of handleMadeShot
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        return { total };
      } catch (error) {
        return { error: error.message };
      }
    };
    console.log(`🔍 [MAKE HANDLER] Start`, {
      _getBackTweensCount: this._getBackTweens ? this._getBackTweens.length : 0,
      tweenManager: getTweenManagerState(),
      ballControllerState: this.ballController ? {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight
      } : null
    });
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Shot made', {
        shooter_id: turnData.shooter_id,
        shot_type: turnData.shot_type
      });
    }

    // ✅ FIX: Ball is already at rim from animateBallFlight() - hold and show announcement in unison
    // Freeze clocks during rim hold + made-shot announcement window.
    const clockPauseReason = 'made_shot_hold';
    this.scene?.gameClock?.pause?.(clockPauseReason);
    this.scene?.shotClock?.pause?.(clockPauseReason);
    const ballSprite = this.ballController.ballSprite;
    const isFastBreak = turnData.fast_break === true;

    if (ballSprite) {
      ballSprite.setVisible(true);
    }

    // Show announcement and flash immediately so they run in unison with rim hold (single 1000ms period)
    if (!isPutbackMake) {
      const { showAnnouncement, showAndOneAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
      const shooterInfo = this.scene.playerInfo?.[turnData.shooter_id];
      const shooterSprite = this.playerSprites[turnData.shooter_id];
      const shooterTeamId = shooterSprite?.team_id;
      const homeTeamField = this.scene.simData?.home_team;
      const awayTeamField = this.scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const shooterTeamName = shooterTeamId === this.scene.simData?.home_team_id ? homeTeamName : awayTeamName;
      const shooterPlayerData = shooterInfo ? {
        playerId: turnData.shooter_id,
        photo: shooterSprite?.photo || null,
        teamName: shooterTeamName,
        secondaryColor: getSecondaryColorForTeam(this.scene, shooterTeamId)
      } : null;
      const isHomeOffense = shooterTeamId === this.scene.simData?.home_team_id;
      const teamStyle = isHomeOffense ? 'home' : 'away';
      const isAndOne = turnData.next_play_type === "FREE_THROW" &&
                       (turnData.foul_player_id || turnData.foul_player?.player_id);
      if (isAndOne) {
        const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
        if (foulPlayerId && shooterPlayerData) {
          const foulPlayerSprite = this.playerSprites[foulPlayerId];
          const foulPlayerTeamId = foulPlayerSprite?.team_id;
          const foulPlayerTeamName = foulPlayerTeamId === this.scene.simData?.home_team_id ? homeTeamName : awayTeamName;
          const foulPlayerData = {
            playerId: foulPlayerId,
            photo: foulPlayerSprite?.photo || null,
            teamName: foulPlayerTeamName,
            secondaryColor: getSecondaryColorForTeam(this.scene, foulPlayerTeamId)
          };
          showAndOneAnnouncement(teamStyle, shooterPlayerData, foulPlayerData);
        } else {
          showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
        }
      } else {
        showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
      }
    }

    // Single wait: rim hold and announcement in unison (use announcement hold so announcement stays 1000ms)
    const holdMs = !isPutbackMake
      ? (isTerminalQuarterEndShot ? 0 : (animationConfig.shot?.makeAnnouncementHoldMs ?? 1000))
      : (isFastBreak ? (animationConfig.fastBreak?.rimHoldMs ?? 1000) : (animationConfig.shot?.rimHoldMs ?? 1000));
    try {
      await new Promise(resolve => {
        if (this.scene.time?.delayedCall) {
          this.scene.time.delayedCall(holdMs, resolve);
        } else {
          setTimeout(resolve, holdMs);
        }
      });
    } finally {
      this.scene?.gameClock?.resume?.(clockPauseReason);
      this.scene?.shotClock?.resume?.(clockPauseReason);
    }

    if (ballSprite) {
      if (this._getBackTweens) {
        this._getBackTweens.forEach(tween => {
          if (tween && tween.isPlaying && this.scene.tweens) {
            this.scene.tweens.killTweensOf(tween.targets);
          }
        });
        this._getBackTweens = [];
      }
      if (!isTerminalQuarterEndShot) {
        ballSprite.setVisible(false);
      }
    }

    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'shot_made',
        shooter_id: turnData.shooter_id
      });
    }
    this.ballController.onShotEnd();

    if (!isPutbackMake) {
      const shouldFlipPossession = turnData.next_play_type === "BASELINE_INBOUND" &&
                                   (turnData.possession_flips !== false);
      if (shouldFlipPossession) {
        // BASELINE_INBOUND turn handles inbound setup
      }
    }
    
    // ✅ REMOVED: Made shot complete logging (cluttering console)
  }

  /**
   * Handle missed shot
   */
  async handleMissedShot(rimCoords, turnData) {
    // ✅ BLOCK: Announce "BLOCK!" when ball has reached block spot (before rebound) so order is Block → Rebound
    if (turnData.result_type === 'BLOCK') {
      turnData._blockAnnounced = true;
      const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
      announceGameEvent('BLOCK', turnData, this.scene, { blockerId: turnData.blocker_id || turnData.defenderId });
      console.log('🟡🟡🟡 [BLOCK/OREB BALL] handleMissedShot BLOCK | rimCoords (bounce target)', { rimCoords });
    }

    // Animate ball bounce from rim (or block spot when BLOCK - rimCoords set in executeCompleteShotSequence)
    await this.animateBallBounce(rimCoords, turnData);
    if (turnData.result_type === 'BLOCK' && this.ballController?.ballSprite) {
      const b = this.ballController.ballSprite;
      console.log('🟡🟡🟡 [BLOCK/OREB BALL] handleMissedShot after bounce | ball_bounce_x, ball_bounce_y', { ball_bounce_x: b.x, ball_bounce_y: b.y });
    }
    
    // ✅ FIX: Check for shooting foul on missed shot and show announcement (matches ballManager.js pattern)
    const hasFreeThrowsRemaining = (turnData?.free_throws_remaining ?? 0) > 0;
    const nextPlayTypeIsFreeThrow = turnData?.next_play_type === 'FREE_THROW';
    const isShootingFoul = hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow;
    
    if (isShootingFoul) {
      // Route shooting-foul miss announcements through the central dispatcher so whistle SFX is universal.
      const { announceGameEvent } = await import('../utils/gameAnnouncements.js');

      // Get foul player data from turnData (same pattern as AND-1)
      const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
      if (foulPlayerId && this.scene) {
        announceGameEvent('FOUL_SHOOTING', turnData, this.scene, { foulerId: foulPlayerId });
      } else {
        // Fallback if foulPlayerId not found (matches AND-1 pattern)
        announceGameEvent('FOUL_SHOOTING', turnData, this.scene, {});
      }
    }
    
    // ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state before rebound
    // This matches the pattern in ballManager.js (line 626)
    // The ball is no longer in flight, so clear the state to allow attachment to rebounder
    this.ballController.onShotEnd();
    
    // ✅ FIX: Stop get-back player animations when rebound is secured
    // Players may not have reached their destination, which is fine
    // This happens when rebounder secures the ball (in handleEmbeddedRebound)

    // ✅ PRIORITY 2 FIX: Add validation to ensure rebound_type is set
    // Check if this shot turn includes rebound data
    if (turnData.rebounderId && turnData.rebound_type) {
      // Handle the rebound within the shot turn
      await this.handleEmbeddedRebound(turnData);
    } else {
      // Rebound data missing - transition to REBOUNDING state (fallback)
      // Transition to REBOUNDING state (fallback)
      if (this.stateMachine) {
        this.stateMachine.transition(AnimationStates.REBOUNDING, {
          reason: 'shot_missed',
          shooter_id: turnData.shooter_id
        });
      }
    }
  }

  /**
   * Handle rebound that's embedded within a shot turn
   */
  async handleEmbeddedRebound(turnData) {
    const ballSprite = this.ballController?.ballSprite;
    console.log('🟡🟡🟡 [BLOCK/OREB BALL] handleEmbeddedRebound entry', {
      result_type: turnData.result_type,
      rebound_type: turnData.rebound_type,
      rebounderId: turnData.rebounderId,
      ballSprite_x: ballSprite?.x,
      ballSprite_y: ballSprite?.y,
    });

    // Get the rebounder sprite
    const rebounderSprite = this.playerSprites[turnData.rebounderId];
    if (!rebounderSprite) {
      console.error('ShotAnimationSystem: Rebounder sprite not found', turnData.rebounderId);
      return;
    }

    // Get the ball's current position (where it bounced)
    let ballBounceX = 0;
    let ballBounceY = 0;
    
    if (ballSprite) {
      // Make ball visible if it was hidden
      ballSprite.setVisible(true);
      
      // Get the ball's bounce position (where it currently is)
      ballBounceX = ballSprite.x;
      ballBounceY = ballSprite.y;
      
    }

    // ✅ FIX: Animate rebounder and non-rebounders simultaneously
    // Start both animations at the same time, but stop all when rebounder reaches ball
    // getPlayerDuration is already imported at top of file
    
    // ✅ FIX: Use distance-based duration for consistent speed
    const rebounderDuration = getPlayerDuration(rebounderSprite, ballBounceX, ballBounceY);
    
    // 🔍 STATE COMPARISON: Log before animatePlayerCollapse
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        return { total };
      } catch (error) {
        return { error: error.message };
      }
    };
    // Animate player collapse
    
    // ✅ TEMP FIX: Kill skeleton defensive tweens before animatePlayerCollapse() to prevent conflict
    // This addresses the animation sync issue where defenders move before passes in HCO MISS => DREB
    // TODO: Remove if this fix doesn't resolve the animation sync issue
    if (this._skeletonDefensivePlayerIds && this._skeletonDefensivePlayerIds.length > 0 && this.scene.tweens) {
      const beforeKillSkeleton = getTweenManagerState();
      let killedCount = 0;
      for (const defensivePlayerId of this._skeletonDefensivePlayerIds) {
        const defensiveSprite = this.playerSprites[defensivePlayerId];
        if (defensiveSprite) {
          this.scene.tweens.killTweensOf(defensiveSprite);
          killedCount++;
        }
      }
      // Clear the list after cleanup
      this._skeletonDefensivePlayerIds = [];
    }
    
    // Start non-rebounder animations first and store tween references
    const collapseTweens = await this.animatePlayerCollapse(rebounderSprite, { x: ballBounceX, y: ballBounceY }, turnData);
    
    const rebounderPromise = new Promise((resolve) => {
      this.scene.tweens.add({
        targets: rebounderSprite,
        x: ballBounceX,
        y: ballBounceY,
        duration: rebounderDuration,
        ease: 'Linear', // Match other player movements
        onComplete: () => {
          // ✅ FIX: Stop all collapse animations when rebounder reaches ball
          const beforeKillCollapse = getTweenManagerState();
          if (collapseTweens && collapseTweens.length > 0) {
            collapseTweens.forEach(tween => {
              if (tween && this.scene.tweens) {
                this.scene.tweens.killTweensOf(tween.targets);
              }
            });
          }
          
          // Attach ball to rebounder once they reach the bounce spot
          this.ballController.attachToPlayer(rebounderSprite, {
            offset: { x: 0, y: -10 }
          });
          playReboundSfx(this.scene, turnData.rebound_type);
          announceReboundHeadlineIfNeeded(
            this.scene,
            turnData,
            rebounderSprite,
            turnData.rebounderId
          );

          // ✅ FIX: Stop get-back player animations when rebound is secured
          const beforeKillGetBack = getTweenManagerState();
          if (this._getBackTweens) {
            this._getBackTweens.forEach(tween => {
              if (tween && tween.isPlaying && this.scene.tweens) {
                this.scene.tweens.killTweensOf(tween.targets);
              }
            });
            this._getBackTweens = [];
          }
          
          resolve();
        }
      });
    });

    // Wait only for rebounder to complete (collapse animations will be stopped)
    await rebounderPromise;

    // Determine next action based on rebound type
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Determining rebound action', {
    //   rebound_type: turnData.rebound_type,
    //   isDREB: turnData.rebound_type === 'DREB',
    //   isOREB: turnData.rebound_type === 'OREB',
    //   allKeys: Object.keys(turnData)
    // });
    
    if (turnData.rebound_type === 'DREB') {
      // ✅ TEMP FIX: Ensure collapseTweens are fully killed before outlet pass starts
      // This prevents collapse animations from interfering with outlet pass timing
      // TODO: Remove if this fix doesn't resolve the animation sync issue
      if (collapseTweens && collapseTweens.length > 0 && this.scene.tweens) {
        collapseTweens.forEach(tween => {
          if (tween && this.scene.tweens) {
            this.scene.tweens.killTweensOf(tween.targets);
          }
        });
      }
      
      // ✅ REVERTED: Back to embedded DREB handling (standalone step approach didn't fix animation sync issue)
      await this.handleDefensiveRebound(rebounderSprite, turnData);
    } else if (turnData.rebound_type === 'OREB') {
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.lead_in.from_miss',
        advanceTrigger: 'OREB committed',
        visualSettleTrigger: 'rebound secure + attach settled',
        authorizingEventReceived: true,
        visualSettled: !!rebounderSprite,
        unitStartMs: Date.now(),
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('decision'),
        context: {
          reboundType: turnData?.rebound_type ?? null,
          rebounderId: turnData?.rebounderId ?? null,
        },
      });
      await this.handleOffensiveRebound(rebounderSprite, turnData);
    } else {
      // ✅ REMOVED: Unknown rebound type logging (cluttering console)
    }

    // Transition to POSSESSION state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'rebound_complete',
        rebounder_id: turnData.rebounderId,
        rebound_type: turnData.rebound_type
      });
    }
  }

  /**
   * Animate players collapsing toward rebound spot
   * NEW: Only animate players who were rebounders (not those who released/got back)
   * Returns array of tween references so they can be stopped early
   */
  async animatePlayerCollapse(rebounderSprite, ballBounceCoords, turnData) {
    // getPlayerDuration is already imported at top of file
    
    // Store tween references so they can be stopped when rebounder reaches ball
    const collapseTweens = [];
    
    // Get lists of players involved in rebounding
    const offense_rebounders = turnData.offense_rebounders || [];
    const defense_rebounders = turnData.defense_rebounders || [];
    const all_rebounders = [...offense_rebounders, ...defense_rebounders];
    
    // ✅ FIX: Convert ball bounce coords (pixels) to grid coordinates correctly
    // gridToPixels uses: pixelY = ((50 - gridY) / 50) * height
    // So reverse: gridY = 50 - (pixelY / height) * 50
    const bounceGridX = Math.round((ballBounceCoords.x / this.scene.game.config.width) * 100);
    const bounceGridY = 50 - Math.round((ballBounceCoords.y / this.scene.game.config.height) * 50);
    
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Animating non-rebounders to ball bounce', {
    //   ballBounceCoordsPixels: { x: ballBounceCoords.x, y: ballBounceCoords.y },
    //   bounceGrid: { x: bounceGridX, y: bounceGridY },
    //   totalRebounders: all_rebounders.length,
    //   rebounderId: turnData.rebounderId,
    //   sceneDimensions: { width: this.scene.game.config.width, height: this.scene.game.config.height }
    // });
    
    // Animate each player who was attempting the rebound (but didn't get it)
    all_rebounders.forEach(playerId => {
      if (playerId === turnData.rebounderId) return; // Skip actual rebounder (handled separately)
      
      const playerSprite = this.playerSprites[playerId];
      if (!playerSprite) return;
      
      // Position near ball bounce: ±6y, ±4x (can stack)
      const offsetY = Phaser.Math.Between(-6, 6);
      const offsetX = Phaser.Math.Between(-4, 4);
      
      const clampedCollapseTarget = clampGridCoords(
        { x: bounceGridX + offsetX, y: bounceGridY + offsetY },
        turnData,
        { action: "shot_rebound_collapse", playerId }
      );
      const targetGridX = clampedCollapseTarget.x;
      const targetGridY = clampedCollapseTarget.y;
      
      const targetPixel = gridToPixels(targetGridX, targetGridY, this.scene.game.config.width, this.scene.game.config.height);
      
      // ✅ FIX: Use distance-based duration for consistent speed
      const collapseDuration = getPlayerDuration(playerSprite, targetPixel.x, targetPixel.y);
      
      // Create tween and store reference
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetPixel.x,
        y: targetPixel.y,
        duration: collapseDuration,
        ease: 'Linear', // Match other player movements
        onComplete: () => {
          // Animation completed (though it may be stopped early)
        }
      });
      
      collapseTweens.push(tween);
    });
    
    // Return tween references so they can be stopped when rebounder reaches ball
    return collapseTweens;
  }

  /**
   * Animate individual player to rebound spot (within 10 grid spots of ball)
   */
  async animatePlayerToReboundSpot(playerSprite, ballBounceCoords, bounceGridX, bounceGridY) {
    // getPlayerDuration is already imported at top of file
    
    return new Promise((resolve) => {
      // Generate random position within 10 grid spots of the ball bounce
      const maxDistance = 10;
      const angle = Math.random() * 2 * Math.PI;
      const distance = Math.random() * maxDistance;
      
      const clampedTargetGrid = clampGridCoords({
        x: bounceGridX + Math.cos(angle) * distance,
        y: bounceGridY + Math.sin(angle) * distance
      });
      
      // Convert back to pixel coordinates
      const targetX = clampedTargetGrid.x * (this.scene.game.config.width / 100);
      const targetY = clampedTargetGrid.y * (this.scene.game.config.height / 100);
      
      // ✅ REMOVED: Player moving to rebound spot logging (cluttering console)
      
      // ✅ FIX: Use distance-based duration for consistent speed
      const duration = getPlayerDuration(playerSprite, targetX, targetY);
      
      // Animate player movement
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetX,
        y: targetY,
        duration,
        ease: 'Linear', // Match other player movements
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Handle defensive rebound
   */
  async handleDefensiveRebound(rebounderSprite, turnData) {
    // ✅ PRIORITY 2 FIX: Enhanced logging to diagnose missing next_play_type
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Handling defensive rebound', {
    //   rebounderId: turnData.rebounderId,
    //   next_play_type: turnData.next_play_type,
    //   rebound_type: turnData.rebound_type,
    //   hasNextPlayType: !!turnData.next_play_type,
    //   turnDataKeys: Object.keys(turnData),
    //   fullTurnData: turnData // Log full object to see what's actually present
    // });
    
    // ✅ PRIORITY 2 FIX: Validate next_play_type is present for normal turns.
    // Final/terminal shot turns can legally omit a next route at quarter boundary.
    const isTerminalTurnContext =
      turnData?.is_final_turn_of_quarter === true ||
      turnData?.final_turn === true ||
      turnData?.quarter_complete === true;
    const gameClockZero =
      Number(turnData?.clock_end ?? turnData?.time_remaining ?? 1) <= 0;
    const shouldAllowMissingNextPlayType = isTerminalTurnContext && gameClockZero;

    if (!turnData.next_play_type) {
      if (shouldAllowMissingNextPlayType) {
        // Quarter-end terminal route: no inbound/outlet follow-up should be executed.
        if (this.stateMachine) {
          this.stateMachine.transition(AnimationStates.POSSESSION, {
            reason: 'rebound_terminal_turn',
            rebounder_id: turnData.rebounderId,
            quarter_complete: true,
          });
        }
        return;
      }
      // Diagnostic: Check if next_play_type is on the next turn (shouldn't be, but let's check)
      const currentTurnIndex = this.scene.currentTurn || 0;
      const nextTurn = this.scene.simData?.turns?.[currentTurnIndex + 1];
      
      console.error('❌ ShotAnimationSystem: next_play_type is missing from turnData!', {
        rebounderId: turnData.rebounderId,
        rebound_type: turnData.rebound_type,
        currentTurnIndex,
        currentTurnResultType: turnData.result_type,
        nextTurnResultType: nextTurn?.result_type,
        nextTurnNextPlayType: nextTurn?.next_play_type,
        sceneOffensiveState: this.scene.gameState?.offensive_state,
        turnData: turnData,
        note: 'This should come from backend on the MISS turn - investigate why it is missing'
      });
      
      // Don't proceed with outlet pass if we don't know what comes next
      // This will help us identify the root cause
      // The backend should set next_play_type on MISS turns with embedded rebounds (turn_manager.py line 1370)
      return;
    }
    
    const nextPlayType = turnData.next_play_type;

    // Diagnostic: which branch of the post-DREB routing are we taking?
    // Restored after "cluttering console" cleanup — silent skips here mask outlet-pass bugs.
    console.log('🏀 [DREB ROUTING] handleDefensiveRebound branch decision', {
      rebounderId: turnData.rebounderId,
      nextPlayType,
      force_foul_after_dreb: !!turnData.force_foul_after_dreb,
      result_type: turnData.result_type,
      rebound_type: turnData.rebound_type,
      branch:
        (nextPlayType === 'HCO' || nextPlayType === 'HCT' || nextPlayType === 'FCP') && !turnData.force_foul_after_dreb
          ? `runDefensiveReboundSetup (${nextPlayType})`
          : (nextPlayType === 'HCO' || nextPlayType === 'HCT' || nextPlayType === 'FCP') && turnData.force_foul_after_dreb
            ? `skipped: force_foul_after_dreb (${nextPlayType})`
            : nextPlayType === 'FAST_BREAK'
              ? 'skipped: FAST_BREAK handles its own outlet'
              : `skipped: unhandled nextPlayType="${nextPlayType}"`,
    });

    // Use the same defensive rebound setup for HCO, HCT, and FCP
    // Fast breaks handle outlet in their own turn
    // ✅ Force Foul after DREB: skip outlet — foul turn animates defender→rebounder and "Quick Foul"
    if ((nextPlayType === 'HCO' || nextPlayType === 'HCT' || nextPlayType === 'FCP') && !turnData.force_foul_after_dreb) {
      // ✅ REMOVED: Defensive rebound logging (cluttering console)
      // "Rebound!" fires at rebound secure in handleEmbeddedRebound (announceReboundHeadlineIfNeeded).

      try {
        // Import and use the same function that works for free throws
        const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
        // ✅ CRITICAL FIX: Pass turnData so runDefensiveReboundSetup can detect outlet pass from animation data
        await runDefensiveReboundSetup({
          scene: this.scene,
          ballSprite: this.ballController.ballSprite,
          playerSprites: this.playerSprites,
          rebounderId: turnData.rebounderId,
          nextPlayType: nextPlayType,
          turnData: turnData // ✅ FIX: Pass turnData to enable outlet pass detection from animation data
        });
        // ✅ REMOVED: runDefensiveReboundSetup completed logging (cluttering console)
      } catch (error) {
        console.error('❌ ShotAnimationSystem: runDefensiveReboundSetup failed', error);
        throw error; // Re-throw to trigger fallback
      }
    } else if (nextPlayType === 'FAST_BREAK') {
      // ✅ FIX: Fast Break outlet passes are handled in the Fast Break sequence itself
      // But we should still log that we're skipping outlet pass here
      // ✅ REMOVED: Fast break outlet pass logging (cluttering console)
    } else {
      // ✅ PRIORITY 2 FIX: Add defensive logging for skipped outlet pass
      // ✅ REMOVED: Defensive rebound outlet pass skipped logging (cluttering console)
      // Handle other cases if needed
    }
  }

  /**
   * Handle offensive rebound
   */
  async handleOffensiveRebound(rebounderSprite, turnData) {
    console.log('🟡🟡🟡 [BLOCK/OREB BALL] handleOffensiveRebound entry (OREB path)', {
      rebound_type: turnData.rebound_type,
      rebounderId: turnData.rebounderId,
    });
    // ✅ DEBUG: Check what turns are coming next
    const currentTurnIndex = this.scene.currentTurn || 0;
    const nextTurn = this.scene.simData?.turns?.[currentTurnIndex + 1];
    const otbNegatesOrebFollowup =
      Boolean(turnData?.suppress_oreb_putback_animation) ||
      (nextTurn?.result_type === 'FOUL' && Boolean(nextTurn?.otb_foul));
    
    // ✅ REMOVED: Offensive rebound logging (cluttering console)
    
    const holdStartMs = Date.now();
    const orebHoldSeconds = Number(turnData?.oreb_hold_seconds);
    const hasHoldWindow = Number.isFinite(orebHoldSeconds) && orebHoldSeconds > 0;
    if (hasHoldWindow && this.scene?.time) {
      const holdMs = Math.max(0, orebHoldSeconds * 350);
      await new Promise((resolve) => this.scene.time.delayedCall(holdMs, resolve));
    }
    this.enforceOrebUnitContract({
      turnData,
      unitId: 'oreb.phase.hold',
      advanceTrigger: 'hold boundary reached',
      visualSettleTrigger: 'no active attach/tween conflicts',
      authorizingEventReceived: true,
      visualSettled: this.scene?.passInFlight !== true,
      unitStartMs: holdStartMs,
      maxWaitGameSeconds: this.getOrebBudgetGameSeconds('decision'),
      context: {
        holdSeconds: hasHoldWindow ? orebHoldSeconds : 0,
        holdApplied: hasHoldWindow && !!this.scene?.time,
      },
    });

    const decisionStartMs = Date.now();
    const hasKickoutEvent =
      Array.isArray(turnData?.events) &&
      turnData.events.some((event) => event?.event_type === 'KICKOUT_RESET');
    const isPutbackAttempt = this.isPutbackAttempt(turnData);
    const decisionType = isPutbackAttempt ? 'putback' : hasKickoutEvent ? 'kickout' : 'forced_putback';
    this.enforceOrebUnitContract({
      turnData,
      unitId: 'oreb.phase.decision',
      advanceTrigger: 'decision event committed',
      visualSettleTrigger: 'decision prep visuals settled',
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: decisionStartMs,
      maxWaitGameSeconds: this.getOrebBudgetGameSeconds('decision'),
      context: {
        decisionType,
        hasKickoutEvent,
        isPutbackAttempt,
        otbNegatesOrebFollowup,
      },
    });

    const actionStartMs = Date.now();
    if (otbNegatesOrebFollowup) {
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.phase.otb_negates_putback_kickout',
        advanceTrigger: 'OTB foul follows; no putback or kickout',
        visualSettleTrigger: 'rebound secure only',
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: actionStartMs,
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('action'),
        context: {
          fromBackendFlag: Boolean(turnData?.suppress_oreb_putback_animation),
          nextTurnOtb: nextTurn?.result_type === 'FOUL' && Boolean(nextTurn?.otb_foul),
        },
      });
      return;
    }
    if (decisionType === 'kickout') {
      await this.executeKickoutPass(rebounderSprite, turnData);
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.phase.kickout_pass',
        advanceTrigger: 'pass received',
        visualSettleTrigger: 'ball flight + receiver settle',
        authorizingEventReceived: hasKickoutEvent,
        visualSettled: true,
        unitStartMs: actionStartMs,
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('action'),
        context: {
          decisionType,
          rebounderId: turnData?.rebounderId ?? null,
        },
      });
      const route = String(turnData?.next_play_type || 'HCO').toUpperCase();
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.out.to_*',
        advanceTrigger: 'route committed',
        visualSettleTrigger: 'OREB final settle complete',
        authorizingEventReceived: route.length > 0,
        visualSettled: true,
        unitStartMs: Date.now(),
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('action'),
        context: {
          route,
          branch: 'kickout',
        },
      });
      return;
    }
    try {
      // Current branch behavior remains unchanged: forced putback path.
      await this.executePutbackAttempt(rebounderSprite, turnData);
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.phase.putback_attempt',
        advanceTrigger: 'shot release/result committed',
        visualSettleTrigger: 'putback visuals settled',
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: actionStartMs,
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('action'),
        context: {
          decisionType,
          rebounderId: turnData?.rebounderId ?? null,
        },
      });
      const route = String(turnData?.next_play_type || 'HCO').toUpperCase();
      this.enforceOrebUnitContract({
        turnData,
        unitId: 'oreb.out.to_*',
        advanceTrigger: 'route committed',
        visualSettleTrigger: 'OREB final settle complete',
        authorizingEventReceived: route.length > 0,
        visualSettled: true,
        unitStartMs: Date.now(),
        maxWaitGameSeconds: this.getOrebBudgetGameSeconds('action'),
        context: {
          route,
          branch: 'putback',
        },
      });
    } catch (error) {
      console.error('🎬 ShotAnimationSystem: executePutbackAttempt failed', error);
      this.emitOrebContractTelemetry(turnData, 'oreb_phase_putback_failed', {
        decisionType,
        rebounderId: turnData?.rebounderId ?? null,
        error: error?.message ?? String(error),
      });
      throw error;
    }
    
    // Original logic (commented out for testing):
    // const isPutbackAttempt = this.isPutbackAttempt(turnData);
    // if (isPutbackAttempt) {
    //   console.log('🎬 ShotAnimationSystem: Executing putback attempt');
    //   await this.executePutbackAttempt(rebounderSprite, turnData);
    // } else {
    //   console.log('🎬 ShotAnimationSystem: Executing kickout pass');
    //   await this.executeKickoutPass(rebounderSprite, turnData);
    // }
  }

  /**
   * Check if this is a putback attempt
   */
  isPutbackAttempt(turnData) {
    // Check for putback attempt flag
    if (turnData.putback_attempt === true) {
      return true;
    }
    
    // Check for PUTBACK_ATTEMPT event
    if (turnData.events && Array.isArray(turnData.events)) {
      return turnData.events.some(event => event.event_type === 'PUTBACK_ATTEMPT');
    }
    
    return false;
  }

  /**
   * Execute putback attempt using standard shot animation
   */
  async executePutbackAttempt(rebounderSprite, turnData) {
    const ballSp = this.ballController?.ballSprite;
    console.log('🟡🟡🟡 [BLOCK/OREB BALL] executePutbackAttempt entry', {
      ball_x: ballSp?.x,
      ball_y: ballSp?.y,
      rebounderId: turnData.rebounderId,
    });
    // SIMPLE APPROACH: Use the old system that already works for regular shots
    const { playTurnAnimation } = await import('./turnAnimation.js');
    
    // Create a simple turn data object for the putback shot
    const putbackTurnData = {
      result_type: 'MISS', // Default to MISS for putbacks
      shooter: rebounderSprite.playerName || 'Unknown',
      shooter_id: turnData.rebounderId,
      ball_handler: rebounderSprite.playerName || 'Unknown',
      shot_type: 'putback',
      animations: [{
        type: 'shot',
        duration: 1000,
        result: 'MISS'
      }]
    };
    
    // Use the old system - it already works perfectly for regular shots
    await playTurnAnimation({
      scene: this.scene,
      simData: { turns: [] }, // Not needed for single turn
      playerSprites: this.playerSprites,
      turnData: putbackTurnData,
      ballSprite: this.ballController.ballSprite,
      onAction: () => {} // No callback needed
    });
    return { success: true };
  }

  /**
   * Execute kickout pass
   */
  async executeKickoutPass(rebounderSprite, turnData) {
    // ✅ REMOVED: Kickout pass logging (cluttering console)
    
    // Find the kickout event data
    const kickoutEvent = turnData.events?.find(event => event.event_type === 'KICKOUT_RESET');
    if (!kickoutEvent) {
      console.warn('🎬 ShotAnimationSystem: No kickout event found');
      return;
    }
    
    // Import and use the existing kickout animation function
    const { animateKickoutReset } = await import('./ballManager.js');
    
    // Execute kickout pass
    await animateKickoutReset(
      this.scene,
      this.ballController.ballSprite,
      turnData.rebounderId,
      kickoutEvent.pgId,
      kickoutEvent.pass
    );
    
    // The animateKickoutReset function already handles:
    // - Pass from rebounder to PG
    // - Ball attachment to PG
    // - State transition to HalfCourt
    // - HCO re-entry will be handled by the next turn
  }

  /**
   * Find point guard by team
   */
  findPointGuard(team) {
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.position === 'PG'
    );
  }

  /**
   * Animate PG to outlet position
   */
  async animatePGToOutlet(pgSprite, rebounderSprite) {
    return new Promise((resolve) => {
      // Calculate outlet position (near rebounder)
      const outletX = rebounderSprite.x + (Math.random() - 0.5) * 20;
      const outletY = rebounderSprite.y + (Math.random() - 0.5) * 20;
      
      const tween = this.scene.tweens.add({
        targets: pgSprite,
        x: outletX,
        y: outletY,
        duration: 600,
        ease: 'Power2',
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Execute outlet pass
   */
  async executeOutletPass(passerSprite, receiverSprite) {
    return new Promise((resolve) => {
      // ✅ PRIORITY 1 FIX: Use lifecycle method for pass instead of direct detach
      // This matches the pattern used elsewhere in the codebase
      this.ballController.onPassStart({ 
        passerId: passerSprite.playerId,
        receiverId: receiverSprite.playerId
      });
      
      // Start ball flight
      this.ballController.startFlight({
        x: receiverSprite.x,
        y: receiverSprite.y - 10
      });
      
      // Animate ball to receiver
      const ballSprite = this.ballController.ballSprite;
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: receiverSprite.x,
        y: receiverSprite.y - 10,
        duration: 400,
        ease: 'Power2',
        onComplete: () => {
          // ✅ PRIORITY 1 FIX: Use lifecycle method to complete pass
          // This matches the pattern in ballTween.js (line 437)
          this.ballController.onPassEnd(receiverSprite, { reason: 'outlet_pass' });
          resolve();
        },
        onUpdate: () => {
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Animate ball bounce from rim
   */
  async animateBallBounce(rimCoords, turnData) {
    return new Promise((resolve) => {
      const ballSprite = this.ballController.ballSprite;
      if (!ballSprite) {
        resolve();
        return;
      }

      // Calculate bounce destination
      const bounceCoords = this.calculateBounceCoords(rimCoords, turnData);

      const isTerminalQuarterEndShot = turnData?.quarter_ends_after === true;

      // Animate bounce
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: bounceCoords.x,
        y: bounceCoords.y,
        duration: this.shotConfig.bounceDuration,
        ease: this.shotConfig.bounceEase,
        onComplete: () => {
          if (!isTerminalQuarterEndShot) {
            // Hide ball after bounce
            ballSprite.setVisible(false);
          }
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });

      if (DebugFlags.SHOT_ANIMATION) {
        console.log('ShotAnimationSystem: Ball bounce', {
          from: rimCoords,
          to: bounceCoords
        });
      }
    });
  }

  /**
   * Calculate bounce coordinates. Backend stamps the canonical bounce spot
   * on miss-path turns; honor it as the single source of truth so the
   * rebounder lands where the resolution logic decided.
   */
  calculateBounceCoords(rimCoords, turnData) {
    if (turnData?.ball_bounce_x != null && turnData?.ball_bounce_y != null) {
      return gridToPixels(
        turnData.ball_bounce_x,
        turnData.ball_bounce_y,
        this.scene.game.config.width,
        this.scene.game.config.height
      );
    }

    // Fallback (shouldn't happen on standard miss turns) — frontend-rolled
    // variance preserved so paths without backend coords still animate.
    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    const rimGridX = Math.round(rimCoords.x / (this.scene.game.config.width / 100));
    const rimGridY = Math.round(rimCoords.y / (this.scene.game.config.height / 100));
    const yVariance = (Math.random() - 0.5) * 12;
    const bounceGridY = rimGridY + yVariance;
    const xVariance = Math.random() * 9 + 1;
    const bounceGridX = isHomeTeam ? rimGridX - xVariance : rimGridX + xVariance;
    const bounceX = bounceGridX * (this.scene.game.config.width / 100);
    const bounceY = bounceGridY * (this.scene.game.config.height / 100);
    
    // ✅ COMMENTED OUT: Verbose bounce calculation logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Bounce variance calculation', {
    //   rimGrid: { x: rimGridX, y: rimGridY },
    //   isHomeTeam,
    //   xVariance,
    //   yVariance,
    //   bounceGrid: { x: bounceGridX, y: bounceGridY },
    //   bouncePixels: { x: bounceX, y: bounceY }
    // });

    return { x: bounceX, y: bounceY };
  }

  /**
   * Get shooter sprite
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
    
    const sprite = this.playerSprites[shooterId] || null;
    return sprite;
  }

  findPlayerIdByName(playerName) {
    if (!playerName) return null;
    
    // Check home roster
    const homeRoster = this.gameStore.getHomeRoster();
    if (homeRoster && homeRoster.players) {
      for (const player of homeRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id || player.id;
        }
      }
    }
    
    // Check away roster
    const awayRoster = this.gameStore.getAwayRoster();
    if (awayRoster && awayRoster.players) {
      for (const player of awayRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id || player.id;
        }
      }
    }
    
    return null;
  }

  /**
   * Get rim coordinates based on shot context (converted to pixels)
   */
  getRimCoordinates(turnData) {
    // Get shooter sprite to determine team
    const shooterSprite = this.getShooterSprite(turnData);
    
    // Determine which rim based on shooter's team
    // Home team shoots at HOME_RIM_COORDS (x: 91, y: 25)
    // Away team shoots at AWAY_RIM_COORDS (x: 9, y: 25)
    const isHomeTeam = shooterSprite?.team === 'home';
    let gridRimCoords = isHomeTeam ? this.shotConfig.homeRim : this.shotConfig.awayRim;
    
    // Convert grid coordinates to pixel coordinates (like the old system does)
    const pixelRimCoords = gridToPixels(
      gridRimCoords.x,
      gridRimCoords.y,
      this.scene.game.config.width,
      this.scene.game.config.height
    );
    
    // Return pixel coordinates for rim
    return pixelRimCoords;
  }

  /**
   * Variant-aware ball flight target. Returns grid coords.
   * BLOCK keeps its existing block-spot path.
   */
  _getShotFlightTargetGrid(turnData) {
    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    const msss = getMadeShotSweetSpotGrid(isHomeTeam);
    const rim = isHomeTeam ? this.shotConfig.homeRim : this.shotConfig.awayRim;

    if (turnData.result_type === 'BLOCK'
        && turnData.ball_bounce_x != null
        && turnData.ball_bounce_y != null) {
      return { x: turnData.ball_bounce_x, y: turnData.ball_bounce_y };
    }

    const variant = turnData.shot_variant;
    const isMake = turnData.result_type === 'MAKE';

    switch (variant) {
      case 'SWISH':
      case 'BACK_OF_RIM':
        return isMake ? { ...msss } : { ...rim };
      case 'CLANK':
        return { ...rim };
      case 'LITTLE_RATTLE':
      case 'NORMAL_RATTLE':
      case 'HEAVY_RATTLE':
        return turnData.shot_variant_rattle_start === 'RIM' ? { ...rim } : { ...msss };
      case 'BANK_MAKE':
      case 'BANK_MISS': {
        const xSign = isHomeTeam ? +1 : -1;
        const yOffset = turnData.shot_variant_backboard_y_offset ?? 0;
        return { x: msss.x + (xSign * 3), y: msss.y + yOffset };
      }
      case 'AIRBALL': {
        // 2 grid units short of MSSS toward midcourt (animation only in step 2 —
        // backend resolution change comes in step 3).
        const xSign = isHomeTeam ? -1 : +1;
        return { x: msss.x + (xSign * 2), y: msss.y };
      }
      default:
        // Backend should always stamp shot_variant on non-block resolutions; fall
        // back to legacy MSSS/rim split if it didn't.
        return isMake ? { ...msss } : { ...rim };
    }
  }

  /**
   * Run any variant-specific animation between ball flight landing and the
   * standard make/miss resolution. No-op for variants without an intermediate
   * step (SWISH, CLANK, BACK_OF_RIM, AIRBALL in step 2).
   */
  async executeShotVariantAnimation(turnData) {
    switch (turnData.shot_variant) {
      case 'LITTLE_RATTLE':
      case 'NORMAL_RATTLE':
      case 'HEAVY_RATTLE':
        await this._animateRattle(turnData);
        return;
      case 'BANK_MAKE':
        await this._animateBackboardMake(turnData);
        return;
      case 'BANK_MISS':
        await this._animateBackboardMiss(turnData);
        return;
      default:
        return;
    }
  }

  async _animateRattle(turnData) {
    const ballSprite = this.ballController?.ballSprite;
    if (!ballSprite) return;

    const variant = turnData.shot_variant;
    const hopPairs = ({ LITTLE_RATTLE: 1, NORMAL_RATTLE: 2, HEAVY_RATTLE: 4 })[variant] ?? 0;
    if (hopPairs === 0) return;

    const startMode = turnData.shot_variant_rattle_start === 'RIM' ? 'RIM' : 'MSSS';
    const progression = turnData.shot_variant_rattle_progression === 'OPT_2' ? 'OPT_2' : 'OPT_1';

    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    const msss = getMadeShotSweetSpotGrid(isHomeTeam);

    // Two hop waypoints — MSSS-start oscillates in y, RIM-start oscillates in x.
    let pointA;
    let pointB;
    if (startMode === 'MSSS') {
      pointA = { x: msss.x, y: msss.y + 1 };
      pointB = { x: msss.x, y: msss.y - 1 };
    } else {
      pointA = { x: msss.x + 1, y: msss.y };
      pointB = { x: msss.x - 1, y: msss.y };
    }

    const first = progression === 'OPT_1' ? pointA : pointB;
    const second = progression === 'OPT_1' ? pointB : pointA;

    const waypoints = [];
    for (let i = 0; i < hopPairs; i++) {
      waypoints.push(first, second);
    }

    const w = this.scene.game.config.width;
    const h = this.scene.game.config.height;

    for (const wp of waypoints) {
      const pix = gridToPixels(wp.x, wp.y, w, h);
      playGameSfx(this.scene, 'rattle-leather.wav', undefined, {
        event: 'shot_result',
        result: turnData.result_type,
        variant,
        hop: true,
      });
      await this._tweenBallTo(ballSprite, pix, 40, 'Linear');
    }

    // Makes: smooth settle into MSSS, with a swish sound that follows the
    // rattles immediately. Misses: leave ball where it is — the standard miss
    // path's animateBallBounce will pick up from here.
    if (turnData.result_type === 'MAKE') {
      playGameSfx(this.scene, 'swish.wav', undefined, {
        event: 'shot_result',
        result: 'MAKE',
        variant,
        followup: 'rattle_swish',
      });
      const msssPix = gridToPixels(msss.x, msss.y, w, h);
      await this._tweenBallTo(ballSprite, msssPix, 150, 'Quad.easeOut');
    }
  }

  async _animateBackboardMake(turnData) {
    const ballSprite = this.ballController?.ballSprite;
    if (!ballSprite) return;
    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    const msss = getMadeShotSweetSpotGrid(isHomeTeam);
    const w = this.scene.game.config.width;
    const h = this.scene.game.config.height;
    const msssPix = gridToPixels(msss.x, msss.y, w, h);
    await this._tweenBallTo(ballSprite, msssPix, 250, 'Quad.easeOut');
  }

  async _animateBackboardMiss(turnData) {
    const ballSprite = this.ballController?.ballSprite;
    if (!ballSprite) return;
    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    const msss = getMadeShotSweetSpotGrid(isHomeTeam);
    const dx = turnData.shot_variant_backboard_miss_rim_offset_x ?? 0;
    const dy = turnData.shot_variant_backboard_miss_rim_offset_y ?? 0;
    const w = this.scene.game.config.width;
    const h = this.scene.game.config.height;
    const grazePix = gridToPixels(msss.x + dx, msss.y + dy, w, h);
    await this._tweenBallTo(ballSprite, grazePix, 200, 'Quad.easeOut');
  }

  _tweenBallTo(ballSprite, pix, duration, ease) {
    return new Promise((resolve) => {
      this.scene.tweens.add({
        targets: ballSprite,
        x: pix.x,
        y: pix.y,
        duration,
        ease,
        onUpdate: () => this.ballController?.updatePosition?.(ballSprite.x, ballSprite.y),
        onComplete: resolve,
      });
    });
  }

  /**
   * Dev affordance: ?debug_shot_variant=NAME forces every shot to use the
   * named variant. Fills in sensible defaults for any sub-roll fields the
   * variant needs but didn't come from the backend.
   */
  _applyDebugVariantOverride(turnData) {
    if (typeof window === 'undefined' || !window.location?.search) return;
    const params = new URLSearchParams(window.location.search);
    const forced = params.get('debug_shot_variant');
    if (!forced) return;

    const variant = forced.toUpperCase();
    turnData.shot_variant = variant;

    const isRattle = variant === 'LITTLE_RATTLE'
                  || variant === 'NORMAL_RATTLE'
                  || variant === 'HEAVY_RATTLE';
    if (isRattle) {
      if (!turnData.shot_variant_rattle_start) {
        turnData.shot_variant_rattle_start = Math.random() < 0.5 ? 'MSSS' : 'RIM';
      }
      if (!turnData.shot_variant_rattle_progression) {
        turnData.shot_variant_rattle_progression = Math.random() < 0.5 ? 'OPT_1' : 'OPT_2';
      }
    }
    if (variant === 'BANK_MAKE' || variant === 'BANK_MISS') {
      if (turnData.shot_variant_backboard_y_offset == null) {
        turnData.shot_variant_backboard_y_offset = Math.floor(Math.random() * 9) - 4;
      }
    }
    if (variant === 'BANK_MISS') {
      if (turnData.shot_variant_backboard_miss_rim_offset_x == null) {
        turnData.shot_variant_backboard_miss_rim_offset_x = Math.floor(Math.random() * 3) - 1;
      }
      if (turnData.shot_variant_backboard_miss_rim_offset_y == null) {
        turnData.shot_variant_backboard_miss_rim_offset_y = Math.floor(Math.random() * 3) - 1;
      }
    }
  }

  /**
   * Validate shot data
   */
  validateShotData(turnData) {
    return turnData && 
           turnData.result_type && 
           (turnData.result_type === 'MAKE' || turnData.result_type === 'MISS' || turnData.result_type === 'BLOCK') &&
           (turnData.shooter || turnData.ball_handler || turnData.shooter_id);
  }

  /**
   * Process queued shots
   */
  async processShotQueue() {
    if (this.shotQueue.length === 0) return;

    const nextShot = this.shotQueue.shift();
    if (nextShot) {
      await this.processShot(nextShot);
    }
  }

  /**
   * Handle shot errors
   */
  handleShotError(error, turnData) {
    console.error('ShotAnimationSystem: Shot error', {
      error: error.message,
      turnData,
      activeShot: this.activeShot
    });

    // Reset to safe state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'shot_error',
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
   * Get shot system status
   */
  getStatus() {
    return {
      activeShot: this.activeShot?.index || null,
      shotQueue: this.shotQueue.length,
      isProcessing: !!this.activeShot,
      shotConfig: this.shotConfig
    };
  }

  /**
   * Update shot configuration
   */
  updateConfig(newConfig) {
    this.shotConfig = { ...this.shotConfig, ...newConfig };
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Config updated', this.shotConfig);
    }
  }

  /**
   * Reset shot system
   */
  reset() {
    this.activeShot = null;
    this.shotQueue = [];
    
    // Hide ball
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      ballSprite.setVisible(false);
    }
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Reset');
    }
  }

}

export default ShotAnimationSystem;
