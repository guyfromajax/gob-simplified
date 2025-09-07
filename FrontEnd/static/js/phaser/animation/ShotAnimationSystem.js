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

import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';

export class ShotAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
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
      homeRim: { x: 89, y: 25 },
      awayRim: { x: 11, y: 25 }
    };
    
    // Active shot tracking
    this.activeShot = null;
    this.shotQueue = [];
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Initialized');
    }
  }

  /**
   * Process a shot turn
   */
  async processShot(turnData) {
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
      console.log('🔍 ShotAnimationSystem: Validating shot data', {
        result_type: turnData.result_type,
        shooter_id: turnData.shooter_id,
        player_id: turnData.player_id,
        shot_type: turnData.shot_type,
        allKeys: Object.keys(turnData),
        fullTurnData: turnData
      });
      
      if (!this.validateShotData(turnData)) {
        console.error('❌ ShotAnimationSystem: Shot data validation failed', {
          result_type: turnData.result_type,
          shooter: turnData.shooter,
          ball_handler: turnData.ball_handler,
          hasResultType: !!turnData.result_type,
          isMakeOrMiss: turnData.result_type === 'MAKE' || turnData.result_type === 'MISS',
          hasShooter: !!(turnData.shooter || turnData.ball_handler)
        });
        throw new Error('Invalid shot data');
      }
      
      console.log('✅ ShotAnimationSystem: Shot data validation passed');

      // Get shooter sprite
      const shooterSprite = this.getShooterSprite(turnData);
      if (!shooterSprite) {
        throw new Error('Shooter sprite not found');
      }
      
      // Determine shot outcome
      const isMake = turnData.result_type === 'MAKE';
      const rimCoords = this.getRimCoordinates(turnData);

      // Execute shot sequence
      await this.executeShotSequence(shooterSprite, rimCoords, isMake, turnData);

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
   * Execute the complete shot sequence
   */
  async executeShotSequence(shooterSprite, rimCoords, isMake, turnData) {
    // 1. Transition to SHOOTING state
    this.stateMachine.transition(AnimationStates.SHOOTING, {
      reason: 'shot_initiated',
      shooter_id: turnData.shooter_id,
      shot_type: turnData.shot_type
    });

    // 2. Detach ball from shooter
    this.ballController.detachFromPlayer('shot');

    // 3. Start ball flight to rim
    await this.animateBallFlight(shooterSprite, rimCoords, turnData);

    // 4. Handle shot outcome
    if (isMake) {
      await this.handleMadeShot(rimCoords, turnData);
    } else {
      await this.handleMissedShot(rimCoords, turnData);
    }
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

      // Position ball at shooter
      ballSprite.setPosition(shooterSprite.x, shooterSprite.y - 10);
      ballSprite.setVisible(true);

      // Start flight
      this.ballController.startFlight(rimCoords, {
        duration: this.shotConfig.flightDuration,
        ease: this.shotConfig.flightEase
      });

      // Animate ball to rim
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: this.shotConfig.flightDuration,
        ease: this.shotConfig.flightEase,
        onComplete: () => {
          this.ballController.endFlight();
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
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Shot made', {
        shooter_id: turnData.shooter_id,
        shot_type: turnData.shot_type
      });
    }

    // Ball goes through rim (no bounce)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Animate ball going through rim
      this.scene.tweens.add({
        targets: ballSprite,
        y: rimCoords.y + 20, // Slight drop through rim
        duration: 200,
        ease: 'Power2',
        onComplete: () => {
          ballSprite.setVisible(false);
        }
      });
    }

    // Transition to IDLE state (end of possession)
    this.stateMachine.transition(AnimationStates.IDLE, {
      reason: 'shot_made',
      shooter_id: turnData.shooter_id
    });

    // Wait for ball to go through rim
    await new Promise(resolve => setTimeout(resolve, 200));
  }

  /**
   * Handle missed shot
   */
  async handleMissedShot(rimCoords, turnData) {
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Shot missed', {
        shooter_id: turnData.shooter_id,
        shot_type: turnData.shot_type
      });
    }

    // Animate ball bounce from rim
    await this.animateBallBounce(rimCoords, turnData);

    // Transition to REBOUNDING state
    this.stateMachine.transition(AnimationStates.REBOUNDING, {
      reason: 'shot_missed',
      shooter_id: turnData.shooter_id
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

      // Animate bounce
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: bounceCoords.x,
        y: bounceCoords.y,
        duration: this.shotConfig.bounceDuration,
        ease: this.shotConfig.bounceEase,
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

      if (DebugFlags.SHOT_ANIMATION) {
        console.log('ShotAnimationSystem: Ball bounce', {
          from: rimCoords,
          to: bounceCoords
        });
      }
    });
  }

  /**
   * Calculate bounce coordinates
   */
  calculateBounceCoords(rimCoords, turnData) {
    // Get court bounds
    const courtWidth = this.scene.game.config.width;
    const courtHeight = this.scene.game.config.height;

    // Calculate random bounce within bounds
    const bounceX = Math.max(20, Math.min(courtWidth - 20, 
      rimCoords.x + (Math.random() - 0.5) * this.shotConfig.bounceDistance * 2));
    const bounceY = Math.max(20, Math.min(courtHeight - 20,
      rimCoords.y + (Math.random() - 0.5) * this.shotConfig.bounceDistance * 2));

    return { x: bounceX, y: bounceY };
  }

  /**
   * Get shooter sprite
   */
  getShooterSprite(turnData) {
    console.log('🔍 ShotAnimationSystem: getShooterSprite called with turnData:', turnData);
    
    // Try to get shooter ID from the turn data
    let shooterId = turnData.shooter_id || turnData.player_id;
    console.log('🔍 ShotAnimationSystem: Initial shooterId:', shooterId);
    
    // If no ID, try to find by name using rosters
    if (!shooterId) {
      const shooterName = turnData.shooter || turnData.ball_handler;
      console.log('🔍 ShotAnimationSystem: Looking up by name:', shooterName);
      if (shooterName) {
        shooterId = this.findPlayerIdByName(shooterName);
        console.log('🔍 ShotAnimationSystem: Found shooterId by name:', shooterId);
      }
    }
    
    console.log('🔍 ShotAnimationSystem: Final shooterId:', shooterId);
    console.log('🔍 ShotAnimationSystem: Available playerSprites keys:', Object.keys(this.playerSprites));
    console.log('🔍 ShotAnimationSystem: Looking for sprite with key:', shooterId);
    
    const sprite = this.playerSprites[shooterId] || null;
    console.log('🔍 ShotAnimationSystem: Found sprite:', sprite);
    
    return sprite;
  }

  findPlayerIdByName(playerName) {
    console.log('🔍 ShotAnimationSystem: findPlayerIdByName called with:', playerName);
    
    if (!playerName) return null;
    
    // Check home roster
    const homeRoster = this.gameStore.getHomeRoster();
    console.log('🔍 ShotAnimationSystem: Home roster:', homeRoster);
    if (homeRoster && homeRoster.players) {
      console.log('🔍 ShotAnimationSystem: Home roster players:', homeRoster.players);
      for (const player of homeRoster.players) {
        console.log('🔍 ShotAnimationSystem: Checking home player:', player.name, 'vs', playerName);
        if (player.name === playerName) {
          console.log('🔍 ShotAnimationSystem: Found matching player, full object:', player);
          console.log('🔍 ShotAnimationSystem: Player keys:', Object.keys(player));
          console.log('🔍 ShotAnimationSystem: player._id:', player._id);
          console.log('🔍 ShotAnimationSystem: player.playerId:', player.playerId);
          console.log('🔍 ShotAnimationSystem: player.player_id:', player.player_id);
          console.log('🔍 ShotAnimationSystem: player.id:', player.id);
          const foundId = player._id || player.playerId || player.player_id || player.id;
          console.log('🔍 ShotAnimationSystem: Found in home roster with ID:', foundId);
          return foundId;
        }
      }
    }
    
    // Check away roster
    const awayRoster = this.gameStore.getAwayRoster();
    console.log('🔍 ShotAnimationSystem: Away roster:', awayRoster);
    if (awayRoster && awayRoster.players) {
      console.log('🔍 ShotAnimationSystem: Away roster players:', awayRoster.players);
      for (const player of awayRoster.players) {
        console.log('🔍 ShotAnimationSystem: Checking away player:', player.name, 'vs', playerName);
        if (player.name === playerName) {
          console.log('🔍 ShotAnimationSystem: Found matching player, full object:', player);
          console.log('🔍 ShotAnimationSystem: Player keys:', Object.keys(player));
          console.log('🔍 ShotAnimationSystem: player._id:', player._id);
          console.log('🔍 ShotAnimationSystem: player.playerId:', player.playerId);
          console.log('🔍 ShotAnimationSystem: player.player_id:', player.player_id);
          console.log('🔍 ShotAnimationSystem: player.id:', player.id);
          const foundId = player._id || player.playerId || player.player_id || player.id;
          console.log('🔍 ShotAnimationSystem: Found in away roster with ID:', foundId);
          return foundId;
        }
      }
    }
    
    console.log('🔍 ShotAnimationSystem: Player not found in any roster');
    return null;
  }

  /**
   * Get rim coordinates based on shot context
   */
  getRimCoordinates(turnData) {
    // Determine which rim based on shot context
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    return isHomeTeam ? this.shotConfig.homeRim : this.shotConfig.awayRim;
  }

  /**
   * Validate shot data
   */
  validateShotData(turnData) {
    return turnData && 
           turnData.result_type && 
           (turnData.result_type === 'MAKE' || turnData.result_type === 'MISS') &&
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
    this.stateMachine.transition(AnimationStates.IDLE, {
      reason: 'shot_error',
      error: error.message
    });

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
