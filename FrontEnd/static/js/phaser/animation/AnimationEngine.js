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
import gameStore from '../../state/gameStore.js';

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

    try {
      // Processing (log removed)

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
      this.isProcessing = false;
    }
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
      console.log('⚡ [FAST BREAK DETECTED]', {
        fast_break: turnData.fast_break,
        fast_break_type: typeof turnData.fast_break,
        result_type: turnData.result_type,
        next_play_type: turnData.next_play_type,
        has_roles: !!turnData.roles,
        has_outlet_passer: !!turnData.roles?.outlet_passer,
        has_outlet_receiver: !!turnData.roles?.outlet_receiver,
        outlet_passer: turnData.roles?.outlet_passer,
        outlet_receiver: turnData.roles?.outlet_receiver,
        reason: turnData.fast_break === true || turnData.fast_break === "true" ? 'fast_break flag' :
                turnData.result_type === "FAST_BREAK" ? 'result_type' :
                'unknown'
      });
      return this.animationHandlers.get('FAST_BREAK');
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
    
    // 🔍 DEBUG: Log routing decision for FOUL, HCO, STEAL, and other non-shot types
    if (turnData.result_type === "FOUL" || turnData.result_type === "HCO" || 
        turnData.result_type === "STEAL" || turnData.result_type === "DEAD_BALL" ||
        turnData.result_type === "DEAD_BALL_TURNOVER" || nonShotResultTypes.has(turnData.result_type)) {
      const isInNonShotSet = nonShotResultTypes.has(turnData.result_type);
      const isShotAttempt = this.isShotAttempt(turnData);
      const willRouteToShot = !isInNonShotSet && isShotAttempt;
      const willRouteToDefault = isInNonShotSet || !isShotAttempt;
      
    }
    
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
    
    // Note: onUpdate is already called inside runFreeThrowSequence for each FT attempt
    // Do NOT call it again here or stats will be double counted
  }

  async handleSideInbound(turnData, context) {
    // Side inbound handler (log removed)
    
    // ✅ PHASE 2.6: Check FastBreak state (matches original logic in animateGameTurns.js)
    const { States } = await import('../state/gameStateMachine.js');
    if (this.scene.stateMachine?.is(States.FastBreak)) {
      console.log('AnimationEngine: Skipping SIDE_INBOUND animation - state is FastBreak');
      return;
    }
    
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
  }

  async handleBaselineInbound(turnData, context) {
    // Baseline inbound handler (log removed)
    
    // ✅ PHASE 2.6: Set FCP/HCT state when pressure setup detected (moved from animateGameTurns.js)
    // This is the single source of truth for pressure state - replaces complex flag detection
    const hasFCPHCTSetup = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    if (hasFCPHCTSetup) {
      this.scene.currentPressureType = turnData.next_defensive_setup; // "FCP" or "HCT"
      this.scene.pressureSequenceActive = true;
      console.log('🎯 [FCP/HCT SETUP DETECTED] Positioning players and animating inbound pass', {
        pressureType: this.scene.currentPressureType,
        pressureSequenceActive: this.scene.pressureSequenceActive,
        result_type: turnData.result_type,
        next_defensive_setup: turnData.next_defensive_setup
      });
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
    
    // ✅ PHASE 2.6: Transition to HalfCourt state (moved from animateGameTurns.js)
    const { safeTransition } = await import('../state/gameStateMachine.js');
    const { States } = await import('../state/gameStateMachine.js');
    safeTransition(this.scene.stateMachine, States.HalfCourt, 'after quarter start inbound');
    
    // ✅ PHASE 2.6: Mark that previous turn was inbound so HCO pre-step setup can use uncapped durations
    this.scene._previousTurnWasInbound = true;
    
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
    console.log('⚡ AnimationEngine: Handling fast break', {
      result_type: turnData.result_type,
      fast_break: turnData.fast_break,
      has_roles: !!turnData.roles,
      outlet_passer: turnData.roles?.outlet_passer,
      outlet_receiver: turnData.roles?.outlet_receiver,
      has_animations: !!turnData.animations,
      animation_count: turnData.animations?.length || 0
    });
    
    // ✅ PHASE 2.6: Update active player display (moved from animateGameTurns.js)
    const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
    const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
    const defenderId = getDefenderIdFromTurn(turnData);
    if (ballHandlerId && context.playerSprites) {
      updateActivePlayers(ballHandlerId, defenderId, this.scene.simData?.home_team_id, context.playerSprites);
    }
    
    // Import and use existing fast break handler for now
    console.log('⚡ About to call runFastBreakSequence');
    const { runFastBreakSequence } = await import('./fastBreak.js');
    await runFastBreakSequence({
      scene: this.scene,
      turnData: turnData,
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnIndex: context.turnIndex // ✅ PHASE 2.6: Pass turnIndex from context
    });
    console.log('⚡ runFastBreakSequence completed');
    
    // ✅ PHASE 2.6: Set flag if this was a shot turn (moved from animateGameTurns.js)
    if (turnData.result_type === "MAKE" || turnData.result_type === "MISS") {
      this.scene._previousTurnWasShot = true;
    }
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handlePutback(turnData, context) {
    if (false) console.log('[Putback Handler]', {
      result_type: turnData.result_type,
      rebounderId: turnData.rebounderId
    });
    
    // ✅ PHASE 2.6: Use existing handleOrebTurn function (moved from animateGameTurns.js)
    // handleOrebTurn handles PUTBACK_MAKE, PUTBACK_MISS, and OREB_KICKOUT
    const { handleOrebTurn } = await import('./animateGameTurns.js');
    await handleOrebTurn(this.scene, {
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnData: turnData,
      onUpdate: context.onUpdate
    });
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handleOpeningTip(turnData, context) {
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
    
    // ✅ PHASE 2.6: Transition to HalfCourt state (moved from animateGameTurns.js)
    const { States, safeTransition } = await import('../state/gameStateMachine.js');
    const { getCurrentOwner, getPendingOwner } = await import('./BallControllerAdapter.js');
    if (this.scene.stateMachine && !this.scene.stateMachine.is(States.HalfCourt)) {
      safeTransition(this.scene.stateMachine, States.HalfCourt, {
        reason: 'opening_tip_complete',
        currentOwnerId: getCurrentOwner(this.scene),
        pendingOwnerId: getPendingOwner(this.scene)
      });
    }
    
    // Note: Announcements and score updates are handled by AnimationRouter (finalizeTurnAfterAnimation)
  }

  async handleDefensiveStop(turnData, context) {
    // ✅ DEBUG: Log full turnData to verify fast_break flag is present
    console.log('🛑 [DEFENSIVE_STOP DEBUG] Full turnData received:', JSON.stringify(turnData, null, 2));
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
    appendToTextScroll(turnData.text || (turnData.fast_break ? "Fast Break! Defense stops the break!" : "Defense stops the break!"));
    
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
      console.log('✅ [STEAL HANDLER] Skeleton animation completed');
    }
    
    // STEP 2: Animate steal result action (ball changes hands)
    // This happens AFTER skeleton animation (like shot result after skeleton)
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
      
      console.log('✅ [STEAL HANDLER] Steal action completed');
    }
    
    // STEP 3: Possession flip handled by universal transition in finalizeTurnAfterAnimation
    // Note: Don't emit possessionChange here - universal handler does it based on backend data
  }

  async handleShotAttempt(turnData, context) {
    if (false) console.log('[Shot Handler]', {
      hasShotSystem: !!this.shotSystem,
      result_type: turnData.result_type,
      turn_index: turnData.index
    });
    
    // Use new shot animation system if available
    if (this.shotSystem) {
      if (false) console.log('[Calling Shot System]', {
        result_type: turnData.result_type,
        shooter_id: turnData.shooter_id,
        turn_index: turnData.index
      });
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
    if (false) console.log('[Default Handler]', {
      result_type: turnData.result_type,
      has_animations: !!turnData.animations?.length,
      animation_count: turnData.animations?.length || 0,
      fcp_foul: turnData.fcp_foul,
      hct_foul: turnData.hct_foul,
      pressureSequenceActive: this.scene.pressureSequenceActive
    });
    
    // ✅ PHASE 2.3: Note: Pre/post setup is handled by AnimationRouter
    // This handler only needs to call playTurnAnimation with the provided context
    // Import and use existing turn animation handler for now
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
    
    if (false) console.log('[Default Complete]', {
      result_type: turnData.result_type
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
