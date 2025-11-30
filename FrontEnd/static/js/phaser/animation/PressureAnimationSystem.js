/**
 * PressureAnimationSystem - FCP/HCT Animation Handler
 * 
 * Handles Full Court Press (FCP) and Half Court Trap (HCT) animations using
 * a structured approach similar to ShotAnimationSystem.
 * 
 * Key Benefits:
 * - Single system for all FCP/HCT result types
 * - Consistent skeleton animation
 * - Structured result handling (can be applied to HCO later)
 * - Routes through AnimationRouter (same as HCO)
 * 
 * Result Types Handled:
 * - MAKE/MISS (shot attempts during pressure)
 * - FOUL (defensive and offensive)
 * - TURNOVER/STEAL/DEAD_BALL
 * - HCO (press break to HCO)
 */

import { playTurnAnimation, runInboundSetup } from './turnAnimation.js';
import { announceFromTurnData } from '../utils/announcements.js';

/**
 * PressureAnimationSystem - FCP/HCT Animation Handler
 * 
 * Handles Full Court Press (FCP) and Half Court Trap (HCT) animations using
 * a structured approach similar to ShotAnimationSystem.
 * 
 * Key Benefits:
 * - Single system for all FCP/HCT result types
 * - Consistent skeleton animation
 * - Structured result handling (can be applied to HCO later)
 * - Routes through AnimationRouter (same as HCO)
 * 
 * Result Types Handled:
 * - MAKE/MISS (shot attempts during pressure)
 * - FOUL (defensive and offensive)
 * - TURNOVER/STEAL/DEAD_BALL
 * - HCO (press break to HCO)
 */

export class PressureAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
    // Active pressure tracking
    this.activePressure = null;
    this.pressureQueue = [];
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
   */
  async executeCompletePressureSequence(turnData, pressureType) {
    // Step 1: Animate skeleton (player movements)
    await this.animateSkeleton(turnData, pressureType);
    
    // Step 2: Handle result based on result_type
    await this.handleResult(turnData, pressureType);
  }

  /**
   * Animate the pressure skeleton (player movements)
   * 
   * This reuses playTurnAnimation() which handles:
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
      onUpdate: null, // Will be handled in handleResult
      turnIndex: turnData.index
    });
  }

  /**
   * Handle result based on result_type
   * 
   * Structured result handling (similar to ShotAnimationSystem.processShot())
   */
  async handleResult(turnData, pressureType) {
    const resultType = turnData.result_type;
    
    console.log('🎬 [PressureAnimationSystem] Handling result', {
      resultType,
      pressureType
    });
    
    switch (resultType) {
      case 'MAKE':
      case 'MISS':
        await this.handleShotResult(turnData, pressureType);
        break;
        
      case 'FOUL':
        await this.handleFoulResult(turnData, pressureType);
        break;
        
      case 'TURNOVER':
      case 'STEAL':
      case 'DEAD_BALL':
      case 'DEAD_BALL_TURNOVER':
        await this.handleTurnoverResult(turnData, pressureType);
        break;
        
      case 'HCO':
        await this.handleHCOResult(turnData, pressureType);
        break;
        
      default:
        console.warn('PressureAnimationSystem: Unknown result type', resultType);
        // Default: just show announcement
        announceFromTurnData(turnData, 'end', this.scene.simData?.home_team_id, this.scene);
    }
  }

  /**
   * Handle shot result (MAKE/MISS during pressure)
   * 
   * For shot attempts, we need to:
   * 1. Animate the shot (reuse ShotAnimationSystem logic if available)
   * 2. Handle rebound if MISS
   * 3. Handle transition (inbound pass if MAKE, or free throw if AND-1)
   */
  async handleShotResult(turnData, pressureType) {
    console.log('🎬 [PressureAnimationSystem] Handling shot result', {
      result_type: turnData.result_type,
      shooter_id: turnData.shooter_id
    });
    
    // TODO: For now, shot animation is handled inline in playTurnAnimation
    // In the future, we can extract this to reuse ShotAnimationSystem logic
    // For Phase 1, we'll rely on playTurnAnimation's existing shot handling
    
    // Show announcement
    announceFromTurnData(turnData, 'end', this.scene.simData?.home_team_id, this.scene);
    
    // Handle transition based on next_play_type
    if (turnData.next_play_type === 'BASELINE_INBOUND' && turnData.possession_flips !== false) {
      // Made shot - transition to inbound pass
      await runInboundSetup({
        scene: this.scene,
        simData: this.scene.simData,
        playerSprites: this.playerSprites,
        turnData: turnData,
        ballSprite: this.ballController.ballSprite,
        pressureType: turnData.next_defensive_setup === 'FCP' || turnData.next_defensive_setup === 'HCT' 
          ? turnData.next_defensive_setup 
          : null
      });
    }
    // For AND-1 (next_play_type === 'FREE_THROW'), let the free throw system handle it
  }

  /**
   * Handle foul result (defensive or offensive foul during pressure)
   */
  async handleFoulResult(turnData, pressureType) {
    console.log('🎬 [PressureAnimationSystem] Handling foul result', {
      fcp_foul: turnData.fcp_foul,
      hct_foul: turnData.hct_foul
    });
    
    // Show announcement
    announceFromTurnData(turnData, 'end', this.scene.simData?.home_team_id, this.scene);
    
    // Foul handling is typically done by the backend
    // Frontend just needs to show the announcement and transition
    // The next turn will be a FREE_THROW or HCO (side inbound)
  }

  /**
   * Handle turnover result (STEAL, DEAD_BALL, etc.)
   */
  async handleTurnoverResult(turnData, pressureType) {
    console.log('🎬 [PressureAnimationSystem] Handling turnover result', {
      result_type: turnData.result_type
    });
    
    // Show announcement
    announceFromTurnData(turnData, 'end', this.scene.simData?.home_team_id, this.scene);
    
    // Turnover handling is typically done by the backend
    // Frontend just needs to show the announcement
    // The next turn will be an HCO for the stealing team
  }

  /**
   * Handle HCO result (press break to HCO)
   */
  async handleHCOResult(turnData, pressureType) {
    console.log('🎬 [PressureAnimationSystem] Handling HCO result (press break)');
    
    // Show announcement
    announceFromTurnData(turnData, 'end', this.scene.simData?.home_team_id, this.scene);
    
    // HCO result means the offense broke the press
    // The next turn will be a regular HCO shot attempt
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

