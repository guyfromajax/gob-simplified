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

export class FreeThrowAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
    // Free throw configuration
    this.ftConfig = {
      // Free throw positioning
      ftLine: { x: 50, y: 25 }, // Free throw line coordinates
      ftSpot: { x: 50, y: 20 }, // Free throw spot coordinates
      
      // Shot parameters (inherited from shot system)
      shotDuration: 1000, // ms
      shotEase: 'Power2',
      
      // Bounce parameters (inherited from shot system)
      bounceDuration: 600, // ms
      bounceEase: 'Bounce',
      bounceDistance: 30, // pixels
      
      // Setup parameters
      setupDuration: 800, // ms
      setupEase: 'Power2',
      
      // Rim coordinates (from courtConstants.js)
      homeRim: { x: 89, y: 25 },
      awayRim: { x: 11, y: 25 },
      
      // Court bounds
      courtBounds: {
        minX: 20,
        maxX: 780,
        minY: 20,
        maxY: 580
      }
    };
    
    // Free throw sequence tracking
    this.activeSequence = null;
    this.sequenceQueue = [];
    this.currentAttempt = 0;
    this.totalAttempts = 0;
    
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Initialized');
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
      if (DebugFlags.FREE_THROW_ANIMATION) {
        console.log('FreeThrowAnimationSystem: Processing free throw', {
          shooter_id: turnData.shooter_id,
          ft_context: turnData.ftContext,
          result_type: turnData.result_type
        });
      }

      // Validate free throw data
      console.log('🔍 FreeThrowAnimationSystem: Validating free throw data', {
        result_type: turnData.result_type,
        shooter_id: turnData.shooter_id,
        player_id: turnData.player_id,
        ftContext: turnData.ftContext,
        allKeys: Object.keys(turnData),
        fullTurnData: turnData
      });
      
      if (!this.validateFreeThrowData(turnData)) {
        console.error('❌ FreeThrowAnimationSystem: Free throw data validation failed', {
          result_type: turnData.result_type,
          shooter_id: turnData.shooter_id,
          player_id: turnData.player_id,
          hasResultType: !!turnData.result_type,
          isFreeThrow: turnData.result_type === 'FREE_THROW',
          hasShooterId: !!(turnData.shooter_id || turnData.player_id)
        });
        throw new Error('Invalid free throw data');
      }
      
      console.log('✅ FreeThrowAnimationSystem: Free throw data validation passed');

      // Get shooter sprite
      const shooterSprite = this.getShooterSprite(turnData);
      if (!shooterSprite) {
        throw new Error('Shooter sprite not found');
      }

      // Determine free throw context
      const ftContext = this.determineFreeThrowContext(turnData);

      // Execute free throw sequence
      await this.executeFreeThrowSequence(shooterSprite, turnData, ftContext);

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
    // 1. Setup free throw positioning
    await this.setupFreeThrowPositioning(shooterSprite, turnData);

    // 2. Execute the free throw shot
    await this.executeFreeThrowShot(shooterSprite, turnData, ftContext);

    // 3. Handle free throw outcome
    if (turnData.result_type === 'MAKE') {
      await this.handleMadeFreeThrow(turnData, ftContext);
    } else {
      await this.handleMissedFreeThrow(turnData, ftContext);
    }
  }

  /**
   * Setup free throw positioning
   */
  async setupFreeThrowPositioning(shooterSprite, turnData) {
    return new Promise((resolve) => {
      // Calculate free throw position
      const ftPosition = this.calculateFreeThrowPosition(turnData);
      
      // Move shooter to free throw line
      const tween = this.scene.tweens.add({
        targets: shooterSprite,
        x: ftPosition.x,
        y: ftPosition.y,
        duration: this.ftConfig.setupDuration,
        ease: this.ftConfig.setupEase,
        onComplete: () => {
          resolve();
        }
      });

      if (DebugFlags.FREE_THROW_ANIMATION) {
        console.log('FreeThrowAnimationSystem: Free throw positioning', {
          shooter_id: turnData.shooter_id,
          position: ftPosition
        });
      }
    });
  }

  /**
   * Execute the free throw shot
   */
  async executeFreeThrowShot(shooterSprite, turnData, ftContext) {
    // 1. Transition to SHOOTING state
    this.stateMachine.transition(AnimationStates.SHOOTING, {
      reason: 'free_throw_initiated',
      shooter_id: turnData.shooter_id,
      attempt: ftContext.attempt,
      total: ftContext.total
    });

    // 2. Detach ball from shooter
    this.ballController.detachFromPlayer('free_throw_shot');

    // 3. Animate ball to rim
    const rimCoords = this.getRimCoordinates(turnData);
    await this.animateBallToRim(shooterSprite, rimCoords, turnData);

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw shot executed', {
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }
  }

  /**
   * Animate ball to rim (similar to shot system but with free throw specifics)
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

      // Position ball at shooter
      ballSprite.setPosition(shooterSprite.x, shooterSprite.y - 10);
      ballSprite.setVisible(true);

      // Start flight
      this.ballController.startFlight(rimCoords, {
        duration: this.ftConfig.shotDuration,
        ease: this.ftConfig.shotEase
      });

      // Animate ball to rim
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: this.ftConfig.shotDuration,
        ease: this.ftConfig.shotEase,
        onComplete: () => {
          this.ballController.endFlight();
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Handle made free throw
   */
  async handleMadeFreeThrow(turnData, ftContext) {
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw made', {
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // Ball goes through rim (no bounce)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Animate ball going through rim
      this.scene.tweens.add({
        targets: ballSprite,
        y: ballSprite.y + 20, // Slight drop through rim
        duration: 200,
        ease: 'Power2',
        onComplete: () => {
          ballSprite.setVisible(false);
        }
      });
    }

    // Check if this is the final free throw
    if (ftContext.attempt >= ftContext.total) {
      // Final free throw made - transition to IDLE (end of possession)
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'free_throw_sequence_complete',
        shooter_id: turnData.shooter_id,
        made: true
      });
    } else {
      // More free throws to come - stay in POSSESSION
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'free_throw_made_more_to_come',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // Wait for ball to go through rim
    await new Promise(resolve => setTimeout(resolve, 200));
  }

  /**
   * Handle missed free throw
   */
  async handleMissedFreeThrow(turnData, ftContext) {
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw missed', {
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // Animate ball bounce from rim
    const rimCoords = this.getRimCoordinates(turnData);
    await this.animateBallBounce(rimCoords, turnData);

    // Transition to REBOUNDING state
    this.stateMachine.transition(AnimationStates.REBOUNDING, {
      reason: 'free_throw_missed',
      shooter_id: turnData.shooter_id,
      attempt: ftContext.attempt,
      total: ftContext.total
    });
  }

  /**
   * Animate ball bounce from rim (similar to shot system)
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

      // Animate bounce
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: bounceCoords.x,
        y: bounceCoords.y,
        duration: this.ftConfig.bounceDuration,
        ease: this.ftConfig.bounceEase,
        onComplete: () => {
          // Hide ball after bounce
          ballSprite.setVisible(false);
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Calculate free throw position
   */
  calculateFreeThrowPosition(turnData) {
    // Determine which free throw line to use
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    
    if (isHomeTeam) {
      return { x: this.ftConfig.ftLine.x, y: this.ftConfig.ftLine.y };
    } else {
      // Away team free throw line (opposite side)
      return { 
        x: this.scene.game.config.width - this.ftConfig.ftLine.x, 
        y: this.ftConfig.ftLine.y 
      };
    }
  }

  /**
   * Get rim coordinates based on free throw context
   */
  getRimCoordinates(turnData) {
    // Determine which rim based on team
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    return isHomeTeam ? this.ftConfig.homeRim : this.ftConfig.awayRim;
  }

  /**
   * Calculate bounce coordinates
   */
  calculateBounceCoords(rimCoords, turnData) {
    // Get court bounds
    const courtWidth = this.scene.game.config.width;
    const courtHeight = this.scene.game.config.height;

    // Calculate random bounce within bounds
    const bounceX = Math.max(this.ftConfig.courtBounds.minX, 
      Math.min(this.ftConfig.courtBounds.maxX, 
        rimCoords.x + (Math.random() - 0.5) * this.ftConfig.bounceDistance * 2));
    const bounceY = Math.max(this.ftConfig.courtBounds.minY, 
      Math.min(this.ftConfig.courtBounds.maxY,
        rimCoords.y + (Math.random() - 0.5) * this.ftConfig.bounceDistance * 2));

    return { x: bounceX, y: bounceY };
  }

  /**
   * Determine free throw context
   */
  determineFreeThrowContext(turnData) {
    const ftContext = turnData.ftContext || {};
    
    return {
      attempt: ftContext.attempt || 1,
      total: ftContext.total || 1,
      type: ftContext.type || 'single',
      isFinal: (ftContext.attempt || 1) >= (ftContext.total || 1)
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
           turnData.result_type === 'FREE_THROW';
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
    this.stateMachine.transition(AnimationStates.IDLE, {
      reason: 'free_throw_error',
      error: error.message
    });

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
    
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Reset');
    }
  }
}

export default FreeThrowAnimationSystem;
