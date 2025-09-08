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
import { DebugFlags } from '../utils/debugFlags.js';

export class AnimationRouter {
  constructor(scene, playerSprites, ballSprite, onUpdate) {
    this.scene = scene;
    this.playerSprites = playerSprites;
    this.ballSprite = ballSprite;
    this.onUpdate = onUpdate;
    
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

    try {
      console.log('🎬 AnimationRouter: Starting turn processing', {
        result_type: turnData.result_type,
        turn_index: turnData.index,
        hasAnimationEngine: !!this.animationEngine,
        hasBallController: !!this.ballController,
        hasPlayerSprites: !!this.playerSprites
      });

      // No state machine needed - just process the turn directly
      console.log('🎯 AnimationRouter: Processing turn directly (no state machine)');

      // Process the turn through the animation engine
      const context = {
        playerSprites: this.playerSprites,
        ballSprite: this.ballSprite,
        onUpdate: this.onUpdate,
        simData: this.scene.simData
      };
      
      console.log('🚀 AnimationRouter: Calling animationEngine.processTurn');
      await this.animationEngine.processTurn(turnData, context);
      console.log('✅ AnimationRouter: animationEngine.processTurn completed');

      // Handle any queued turns
      await this.processQueue();

      console.log('🎉 AnimationRouter: Turn processing completed successfully');

    } catch (error) {
      console.error('❌ AnimationRouter: Error processing turn', {
        error: error.message,
        stack: error.stack,
        result_type: turnData.result_type
      });
      throw error;
    } finally {
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