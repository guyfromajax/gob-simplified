/**
 * AnimationRouter - Basic Routing System
 * 
 * Connects all Phase 1 components (AnimationEngine, SimplifiedStateMachine, BallController)
 * into a cohesive, working system that can replace the existing animation system.
 * 
 * Key Benefits:
 * - Single entry point for all animations
 * - Coordinated state management
 * - Proper ball ownership handling
 * - Event-driven architecture
 * - Easy integration with existing code
 */

import AnimationEngine from './AnimationEngine.js';
import SimplifiedStateMachine, { AnimationStates } from './SimplifiedStateMachine.js';
import BallController from './BallController.js';
import { DebugFlags } from '../utils/debugFlags.js';

export class AnimationRouter {
  constructor(scene, playerSprites, ballSprite, onUpdate) {
    this.scene = scene;
    this.playerSprites = playerSprites;
    this.ballSprite = ballSprite;
    this.onUpdate = onUpdate;
    
    // Initialize core components
    this.stateMachine = new SimplifiedStateMachine(AnimationStates.IDLE);
    this.ballController = new BallController(scene, ballSprite);
    this.animationEngine = new AnimationEngine(scene);
    
    // Inject dependencies into animation engine
    this.animationEngine.injectDependencies(this.ballController, this.stateMachine, playerSprites);
    
    // Router state
    this.isProcessing = false;
    this.currentTurn = null;
    this.animationQueue = [];
    this.isInitialized = false;
    
    // Event handlers
    this.setupEventHandlers();
    
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

    // Set up ball controller callbacks
    this.ballController.onAttachment((previousOwner, newOwner, options) => {
      this.handleBallAttachment(previousOwner, newOwner, options);
    });

    this.ballController.onDetachment((previousOwner, reason, options) => {
      this.handleBallDetachment(previousOwner, reason, options);
    });

    // Set up state machine listeners
    this.stateMachine.on('stateChange', (data) => {
      this.handleStateChange(data);
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
      if (DebugFlags.ANIMATION_ROUTER) {
        console.log('AnimationRouter: Processing turn', {
          index: turnData.index,
          result_type: turnData.result_type,
          currentState: this.stateMachine.state
        });
      }

      // Determine the appropriate state transition
      const nextState = this.determineNextState(turnData);
      
      // Transition to the new state
      if (nextState && this.stateMachine.canTransitionTo(nextState)) {
        this.stateMachine.transitionTo(nextState, { turnData });
      } else {
        console.warn('AnimationRouter: Cannot transition to state', nextState);
      }

      // Process the turn through the animation engine
      const context = {
        playerSprites: this.playerSprites,
        ballSprite: this.ballSprite,
        onUpdate: this.onUpdate,
        simData: this.scene.simData
      };
      await this.animationEngine.processTurn(turnData, context);

      // Handle any queued turns
      await this.processQueue();

    } catch (error) {
      console.error('AnimationRouter: Error processing turn', error);
      this.handleError(error, turnData);
    } finally {
      this.isProcessing = false;
      this.currentTurn = null;
    }
  }

  /**
   * Determine the next state based on turn data
   */
  determineNextState(turnData) {
    const currentState = this.stateMachine.state;
    
    // State transition logic based on turn type
    switch (turnData.result_type) {
      case 'FREE_THROW':
        return AnimationStates.SHOOTING;
        
      case 'FAST_BREAK':
        return AnimationStates.POSSESSION;
        
      case 'SIDE_INBOUND':
        return AnimationStates.POSSESSION;
        
      case 'TURNOVER':
        return AnimationStates.IDLE;
        
      case 'MAKE':
        if (currentState === AnimationStates.SHOOTING) {
          return AnimationStates.IDLE;
        }
        return AnimationStates.POSSESSION;
        
      case 'MISS':
        if (currentState === AnimationStates.SHOOTING) {
          return AnimationStates.REBOUNDING;
        }
        return AnimationStates.POSSESSION;
        
      case 'REBOUND':
        if (currentState === AnimationStates.REBOUNDING) {
          return AnimationStates.POSSESSION;
        }
        return AnimationStates.REBOUNDING;
        
      default:
        // For unknown turn types, try to maintain current state or go to POSSESSION
        if (currentState === AnimationStates.IDLE) {
          return AnimationStates.POSSESSION;
        }
        return currentState;
    }
  }

  /**
   * Handle ball attachment events
   */
  handleBallAttachment(previousOwner, newOwner, options) {
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Ball attached', {
        from: previousOwner?.playerId,
        to: newOwner?.playerId,
        state: this.stateMachine.state
      });
    }

    // Update state machine if needed
    if (this.stateMachine.state === AnimationStates.IDLE && newOwner) {
      this.stateMachine.transitionTo(AnimationStates.POSSESSION, { 
        reason: 'ball_attached',
        playerId: newOwner.playerId 
      });
    }
  }

  /**
   * Handle ball detachment events
   */
  handleBallDetachment(previousOwner, reason, options) {
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Ball detached', {
        from: previousOwner?.playerId,
        reason,
        state: this.stateMachine.state
      });
    }

    // Update state machine based on detachment reason
    switch (reason) {
      case 'shot':
        this.stateMachine.transitionTo(AnimationStates.SHOOTING, { 
          reason: 'ball_detached_for_shot',
          playerId: previousOwner?.playerId 
        });
        break;
        
      case 'pass':
        // Stay in POSSESSION for passes
        break;
        
      case 'turnover':
        this.stateMachine.transitionTo(AnimationStates.IDLE, { 
          reason: 'turnover',
          playerId: previousOwner?.playerId 
        });
        break;
        
      default:
        // For other reasons, maintain current state
        break;
    }
  }

  /**
   * Handle state machine changes
   */
  handleStateChange(data) {
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: State changed', {
        from: data.prevState,
        to: data.newState,
        context: data.context
      });
    }

    // Handle state-specific logic
    switch (data.newState) {
      case AnimationStates.IDLE:
        this.handleIdleState(data);
        break;
        
      case AnimationStates.POSSESSION:
        this.handlePossessionState(data);
        break;
        
      case AnimationStates.SHOOTING:
        this.handleShootingState(data);
        break;
        
      case AnimationStates.REBOUNDING:
        this.handleReboundingState(data);
        break;
    }
  }

  /**
   * Handle IDLE state
   */
  handleIdleState(data) {
    // Ball should be detached in IDLE state
    if (this.ballController.isBallAttached()) {
      this.ballController.detachFromPlayer('state_idle');
    }
  }

  /**
   * Handle POSSESSION state
   */
  handlePossessionState(data) {
    // Ensure ball is attached to a player
    if (!this.ballController.isBallAttached() && data.context?.playerId) {
      const playerSprite = this.findPlayerSprite(data.context.playerId);
      if (playerSprite) {
        this.ballController.attachToPlayer(playerSprite);
      }
    }
  }

  /**
   * Handle SHOOTING state
   */
  handleShootingState(data) {
    // Ball should be in flight for shots
    if (this.ballController.isBallAttached() && !this.ballController.isBallInFlight()) {
      // This will be handled by the specific shot animation
    }
  }

  /**
   * Handle REBOUNDING state
   */
  handleReboundingState(data) {
    // Ball should be detached for rebounds
    if (this.ballController.isBallAttached()) {
      this.ballController.detachFromPlayer('rebound');
    }
  }

  /**
   * Find player sprite by ID
   */
  findPlayerSprite(playerId) {
    return this.playerSprites[playerId] || null;
  }

  /**
   * Process queued animations
   */
  async processQueue() {
    if (this.animationQueue.length === 0) return;

    const nextTurn = this.animationQueue.shift();
    if (nextTurn) {
      await this.processTurn(nextTurn);
    }
  }

  /**
   * Handle errors gracefully
   */
  handleError(error, turnData) {
    console.error('AnimationRouter: Error occurred', {
      error: error.message,
      turnData,
      currentState: this.stateMachine.state,
      ballState: this.ballController.getState()
    });

    // Reset to a safe state
    this.stateMachine.transitionTo(AnimationStates.IDLE, { reason: 'error_recovery' });
    this.ballController.reset();
  }

  /**
   * Get current system status
   */
  getStatus() {
    return {
      isProcessing: this.isProcessing,
      currentTurn: this.currentTurn?.index || null,
      stateMachine: {
        state: this.stateMachine.state,
        canTransition: Object.values(AnimationStates).filter(state => 
          this.stateMachine.canTransitionTo(state)
        )
      },
      ballController: this.ballController.getState(),
      animationEngine: {
        isProcessing: this.animationEngine.isProcessingTurn
      },
      queue: {
        length: this.animationQueue.length,
        next: this.animationQueue[0]?.index || null
      },
      isInitialized: this.isInitialized
    };
  }

  /**
   * Reset the entire system
   */
  reset() {
    this.isProcessing = false;
    this.currentTurn = null;
    this.animationQueue = [];
    
    this.stateMachine.transitionTo(AnimationStates.IDLE, { reason: 'system_reset' });
    this.ballController.reset();
    
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: System reset');
    }
  }

  /**
   * Enable/disable debug logging
   */
  setDebug(enabled) {
    this.ballController.setDebug(enabled);
    if (DebugFlags.ANIMATION_ROUTER) {
      console.log('AnimationRouter: Debug mode', enabled ? 'enabled' : 'disabled');
    }
  }

  /**
   * Get comprehensive system information
   */
  getSystemInfo() {
    return {
      components: {
        stateMachine: 'SimplifiedStateMachine',
        ballController: 'BallController',
        animationEngine: 'AnimationEngine'
      },
      status: this.getStatus(),
      capabilities: {
        canProcessTurns: this.isInitialized && !this.isProcessing,
        canHandleStateTransitions: true,
        canManageBallOwnership: true,
        canQueueAnimations: true
      }
    };
  }
}

export default AnimationRouter;
