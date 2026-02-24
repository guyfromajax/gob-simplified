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

      // Clocks are backend-driven: display is updated only from turn data (syncWithBackend in updateScoreboard).
      // We never start the countdown interval so game clock and shot clock stay in sync with the backend and with each other.
      if (this.scene?.gameClock || this.scene?.shotClock) {
        const applyClockControl = (clockRef, { syncToThirty = false } = {}) => {
          if (!clockRef) return;
          if (syncToThirty) {
            clockRef.syncWithBackend?.(30);
          }
          // Pause/resume kept for API compatibility; no interval runs so display only changes on syncWithBackend.
          if (isNoImpactTurn) {
            clockRef.pause('no_impact_turn');
          } else {
            clockRef.resume('no_impact_turn');
            if (this.scene.isPaused) {
              clockRef.pause('user_pause');
            }
          }
        };

        applyClockControl(this.scene.gameClock, { syncToThirty: false });
        applyClockControl(this.scene.shotClock, { syncToThirty: isNoImpactTurn });
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

      // Note: HCO outlet pass step is now handled directly in ShotAnimationSystem.handleDefensiveRebound
      // using the same runDefensiveReboundSetup function that works for free throws
      
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
