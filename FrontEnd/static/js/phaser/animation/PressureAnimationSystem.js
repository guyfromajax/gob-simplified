/**
 * PressureAnimationSystem - FCP/HCT Animation Handler
 * 
 * SS&S Approach: Thin wrapper that handles ONLY the unique FCP/HCT skeleton animation.
 * Result handling is delegated to existing systems (ShotAnimationSystem, etc.) to avoid duplication.
 * 
 * Key Benefits:
 * - Reuses existing systems for result handling (no code duplication)
 * - Handles only the unique skeleton animation for FCP/HCT
 * - Routes through AnimationRouter (same as HCO)
 * 
 * Architecture:
 * 1. Sets up pressure state (currentPressureType, pressureSequenceActive)
 * 2. Animates skeleton via playTurnAnimation()
 * 3. Routes to existing systems for result handling:
 *    - ShotAnimationSystem for MAKE/MISS
 *    - AnimationRouter handlers for FOUL, TURNOVER, etc.
 * 4. Clears pressure state when sequence completes
 */

import { playTurnAnimation } from './turnAnimation.js';

export class PressureAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
    // Reference to other systems (injected by AnimationEngine)
    this.shotSystem = null; // Will be injected
    this.animationEngine = null; // Will be injected
    
    // Active pressure tracking
    this.activePressure = null;
    this.pressureQueue = [];
  }
  
  /**
   * Inject dependencies on other systems (called by AnimationEngine)
   */
  injectDependencies(shotSystem, animationEngine) {
    this.shotSystem = shotSystem;
    this.animationEngine = animationEngine;
  }

  /**
   * Process a pressure turn (FCP/HCT) with complete skeleton animation
   * 
   * This is the main entry point, similar to ShotAnimationSystem.processShot()
   */
  async processPressure(turnData) {
    console.log('🎬 [PressureAnimationSystem.processPressure] ENTERING', {
      result_type: turnData.result_type,
      fcp_shot: turnData.fcp_shot,
      hct_shot: turnData.hct_shot,
      fcp_foul: turnData.fcp_foul,
      hct_foul: turnData.hct_foul,
      next_defensive_setup: turnData.next_defensive_setup,
      turn_index: turnData.index
    });
    
    if (this.activePressure) {
      console.warn('PressureAnimationSystem: Already processing pressure, queuing...');
      this.pressureQueue.push(turnData);
      return;
    }

    this.activePressure = turnData;
    
    try {
      // Determine pressure type (FCP or HCT)
      const pressureType = this.determinePressureType(turnData);
      
      // Update scene state for pressure sequence
      this.scene.currentPressureType = pressureType;
      this.scene.pressureSequenceActive = true;
      
      // Execute complete pressure sequence with skeleton animation
      await this.executeCompletePressureSequence(turnData, pressureType);
      
      // Process any queued pressure turns
      await this.processPressureQueue();
      
      // Clear pressure state if sequence is complete
      this.clearPressureStateIfComplete(turnData);
      
    } catch (error) {
      console.error('PressureAnimationSystem: Error processing pressure', error);
      this.handlePressureError(error, turnData);
    } finally {
      this.activePressure = null;
    }
  }

  /**
   * Determine pressure type (FCP or HCT) from turn data
   */
  determinePressureType(turnData) {
    // Priority 1: Explicit flags
    if (turnData.fcp_shot || turnData.fcp_foul) return 'FCP';
    if (turnData.hct_shot || turnData.hct_foul) return 'HCT';
    
    // Priority 2: next_defensive_setup (from backend)
    if (turnData.next_defensive_setup === 'FCP') return 'FCP';
    if (turnData.next_defensive_setup === 'HCT') return 'HCT';
    
    // Priority 3: Scene state (from previous turn)
    if (this.scene.currentPressureType) return this.scene.currentPressureType;
    
    // Default: FCP (should rarely reach here)
    console.warn('PressureAnimationSystem: Could not determine pressure type, defaulting to FCP', turnData);
    return 'FCP';
  }

  /**
   * Execute complete pressure sequence with skeleton animation
   * 
   * SS&S: Only handles skeleton animation. Result handling is delegated to existing systems.
   */
  async executeCompletePressureSequence(turnData, pressureType) {
    // Step 1: Animate skeleton (player movements) - this is the unique FCP/HCT behavior
    await this.animateSkeleton(turnData, pressureType);
    
    // Step 2: Route to existing systems for result handling (no duplication)
    await this.routeToExistingSystem(turnData, pressureType);
  }

  /**
   * Animate the pressure skeleton (player movements)
   * 
   * This is the ONLY unique behavior for FCP/HCT - the skeleton animation.
   * Reuses playTurnAnimation() which handles:
   * - runSetupTween() (step 0 positioning)
   * - Step-by-step player movements
   * - Pass animations
   * - Ball ownership management
   */
  async animateSkeleton(turnData, pressureType) {
    console.log('🎬 [PressureAnimationSystem] Animating skeleton', {
      pressureType,
      result_type: turnData.result_type,
      hasAnimations: !!turnData.animations?.length
    });
    
    // Reuse playTurnAnimation for skeleton animation
    // This handles all the step-by-step player movements
    await playTurnAnimation({
      scene: this.scene,
      simData: this.scene.simData,
      playerSprites: this.playerSprites,
      turnData: turnData,
      ballSprite: this.ballController.ballSprite,
      onUpdate: null, // Will be handled by routed system
      turnIndex: turnData.index
    });
  }

  /**
   * Route to existing systems for result handling (SS&S: reuse, don't duplicate)
   * 
   * For shot attempts: Route to ShotAnimationSystem (reuses existing shot handling)
   * For other results: Let AnimationRouter handle them (they're already set up)
   */
  async routeToExistingSystem(turnData, pressureType) {
    const resultType = turnData.result_type;
    
    console.log('🎬 [PressureAnimationSystem] Routing to existing system', {
      resultType,
      pressureType
    });
    
    // For shot attempts, route to ShotAnimationSystem (reuse existing system)
    if (resultType === 'MAKE' || resultType === 'MISS') {
      if (this.shotSystem) {
        console.log('🎬 [PressureAnimationSystem] Routing shot result to ShotAnimationSystem');
        // Note: ShotAnimationSystem will handle announcements, rebounds, transitions, etc.
        // We don't duplicate that logic here
        await this.shotSystem.processShot(turnData);
      } else {
        console.warn('PressureAnimationSystem: ShotSystem not available, result handling may be incomplete');
      }
    }
    // For other results (FOUL, TURNOVER, STEAL, HCO, etc.):
    // AnimationRouter's finalizeTurnAfterAnimation() will handle announcements
    // No need to duplicate that logic here
  }

  /**
   * Clear pressure state if sequence is complete
   */
  clearPressureStateIfComplete(turnData) {
    const nextTurn = this.scene.simData?.turns?.[turnData.index + 1];
    
    // Check if next turn has FCP/HCT flags
    const nextTurnIsFCPHCT = nextTurn && (
      nextTurn.fcp_shot === true || nextTurn.hct_shot === true ||
      nextTurn.fcp_foul === true || nextTurn.hct_foul === true ||
      nextTurn.next_defensive_setup === 'FCP' || nextTurn.next_defensive_setup === 'HCT'
    );
    
    // Check if current turn is setting up next FCP/HCT
    const isSettingUpNextFCPHCT = (turnData.result_type === 'MAKE' || turnData.result_type === 'MISS') &&
                                   (turnData.next_defensive_setup === 'FCP' || turnData.next_defensive_setup === 'HCT');
    
    // Determine if we should clear pressure state
    const shouldClearPressureState = 
      ((turnData.result_type === 'MAKE' || turnData.result_type === 'MISS') && !nextTurnIsFCPHCT && !isSettingUpNextFCPHCT) ||
      (turnData.result_type === 'HCO' && !nextTurnIsFCPHCT) ||
      turnData.fcp_foul === true || turnData.hct_foul === true ||
      turnData.result_type === 'TURNOVER';
    
    if (shouldClearPressureState && this.scene.pressureSequenceActive) {
      console.log('🎬 [PressureAnimationSystem] Clearing pressure state', {
        result_type: turnData.result_type,
        nextTurnIsFCPHCT
      });
      this.scene.currentPressureType = null;
      this.scene.pressureSequenceActive = false;
    }
  }

  /**
   * Process queued pressure turns
   */
  async processPressureQueue() {
    while (this.pressureQueue.length > 0) {
      const queuedTurn = this.pressureQueue.shift();
      await this.processPressure(queuedTurn);
    }
  }

  /**
   * Handle errors during pressure processing
   */
  handlePressureError(error, turnData) {
    console.error('PressureAnimationSystem: Error details', {
      error: error.message,
      stack: error.stack,
      turnData: {
        result_type: turnData.result_type,
        index: turnData.index
      }
    });
    
    // Clear pressure state on error
    this.scene.currentPressureType = null;
    this.scene.pressureSequenceActive = false;
  }

  /**
   * Validate pressure data
   */
  validatePressureData(turnData) {
    // Must have either FCP/HCT flags or next_defensive_setup
    const hasFCPHCTFlags = turnData.fcp_shot || turnData.hct_shot || 
                           turnData.fcp_foul || turnData.hct_foul;
    const hasDefensiveSetup = turnData.next_defensive_setup === 'FCP' || 
                              turnData.next_defensive_setup === 'HCT';
    const hasSceneState = this.scene.pressureSequenceActive;
    
    if (!hasFCPHCTFlags && !hasDefensiveSetup && !hasSceneState) {
      console.warn('PressureAnimationSystem: Turn data does not indicate FCP/HCT', turnData);
      return false;
    }
    
    return true;
  }
}

