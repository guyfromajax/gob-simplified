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
    this.animationHandlers.set('DEFAULT', this.handleDefault.bind(this));
  }

  /**
   * Main entry point for all animations
   * Routes turn data to the appropriate handler
   */
  async processTurn(turnData, context = {}) {
    if (this.isProcessing) {
      console.warn('AnimationEngine: Already processing a turn, skipping');
      return;
    }

    this.isProcessing = true;

    try {
      console.log('🎬 AnimationEngine: Processing turn', turnData.result_type);

      // Determine the appropriate handler
      const handler = this.determineHandler(turnData);
      console.log('🎯 AnimationEngine: Using handler for', turnData.result_type);
      
      // Execute the animation
      await handler(turnData, context);
      console.log('✅ AnimationEngine: Completed', turnData.result_type);

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
    if (turnData.fast_break === true || turnData.result_type === "FAST_BREAK") {
      return this.animationHandlers.get('FAST_BREAK');
    }

    // Specific result types (check handlers map first)
    if (turnData.result_type && this.animationHandlers.has(turnData.result_type)) {
      return this.animationHandlers.get(turnData.result_type);
    }

    // ✅ DEBUG: Exclude non-shot result types from shot attempt detection
    // FOUL, FREE_THROW, TURNOVER, etc. should not be treated as shot attempts
    const nonShotResultTypes = new Set([
      "FOUL", "FREE_THROW", "TURNOVER", "DEAD_BALL", 
      "SIDE_INBOUND", "BASELINE_INBOUND", "PUTBACK_MAKE", 
      "PUTBACK_MISS", "OREB_KICKOUT", "DEFENSIVE_STOP", "OPENING_TIP",
      "HCO" // ✅ FIX: HCO turns are setup turns, not shot attempts
    ]);
    
    // 🔍 DEBUG: Log routing decision for FOUL, HCO, and other non-shot types
    if (turnData.result_type === "FOUL" || turnData.result_type === "HCO" || nonShotResultTypes.has(turnData.result_type)) {
      const isInNonShotSet = nonShotResultTypes.has(turnData.result_type);
      const isShotAttempt = this.isShotAttempt(turnData);
      console.log('🔍 [ROUTING DEBUG]', {
        result_type: turnData.result_type,
        isInNonShotSet,
        isShotAttempt,
        willRouteToShot: !isInNonShotSet && isShotAttempt,
        willRouteToDefault: isInNonShotSet || !isShotAttempt,
        willRouteToHCO: turnData.result_type === "HCO"
      });
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
  }

  async handleSideInbound(turnData, context) {
    console.log('AnimationEngine: Handling side inbound with new PassAnimationSystem');
    
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
    console.log('AnimationEngine: Handling baseline inbound with new PassAnimationSystem');
    
    if (this.passSystem) {
      await this.passSystem.processPass(turnData, context);
      console.log('AnimationEngine: PassAnimationSystem completed for BASELINE_INBOUND');
    } else {
      console.warn('AnimationEngine: PassAnimationSystem not available, using fallback');
      // Fallback to old system - use the same logic as side inbound for now
      const { runSideInboundSetup } = await import('./turnAnimation.js');
      await runSideInboundSetup({
        scene: this.scene,
        ballSprite: context.ballSprite,
        playerSprites: context.playerSprites,
        turnData: turnData
      });
    }
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
    console.log('AnimationEngine: Handling fast break');
    // Import and use existing fast break handler for now
    const { runFastBreakSequence } = await import('./fastBreak.js');
    await runFastBreakSequence(this.scene, {
      playerSprites: context.playerSprites,
      ballSprite: context.ballSprite,
      turnData: turnData,
      onUpdate: context.onUpdate
    });
  }

  async handleShotAttempt(turnData, context) {
    console.log('AnimationEngine: Handling shot attempt with new ShotAnimationSystem');
    
    // Use new shot animation system if available
    if (this.shotSystem) {
      await this.shotSystem.processShot(turnData);
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
    console.log('AnimationEngine: Handling default animation');
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
      console.log('AnimationEngine: ShotAnimationSystem initialized');
      
      this.reboundSystem = new ReboundAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
      console.log('AnimationEngine: ReboundAnimationSystem initialized');
      
      this.passSystem = new PassAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
      console.log('AnimationEngine: PassAnimationSystem initialized');
      
      this.freeThrowSystem = new FreeThrowAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites,
        gameStore
      );
      console.log('AnimationEngine: FreeThrowAnimationSystem initialized');
      
      this.hcoSystem = new HCOAnimationSystem(
        this.scene,
        this.ballController,
        this.stateMachine,
        this.playerSprites
      );
      console.log('AnimationEngine: HCOAnimationSystem initialized');
    }
    
    console.log('AnimationEngine: Dependencies injected', {
      hasBallController: !!this.ballController,
      hasStateMachine: !!this.stateMachine,
      hasPlayerSprites: !!this.playerSprites,
      hasShotSystem: !!this.shotSystem,
      hasReboundSystem: !!this.reboundSystem,
      hasPassSystem: !!this.passSystem,
      hasFreeThrowSystem: !!this.freeThrowSystem
    });
  }
}

export default AnimationEngine;
