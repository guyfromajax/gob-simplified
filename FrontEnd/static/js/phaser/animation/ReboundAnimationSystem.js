/**
 * ReboundAnimationSystem - Universal Rebound Animation Handler
 * 
 * Handles all rebound scenarios using the new Phase 1 components:
 * - Defensive rebounds (regular shots, free throws, fast breaks)
 * - Offensive rebounds (putbacks, kickouts)
 * - Rebound positioning and player movement
 * - Follow-up actions (HCO, fast break, putback)
 * 
 * Key Benefits:
 * - Single system for all rebound types
 * - Proper player positioning
 * - Coordinated with shot system
 * - No teleports or floating balls
 */

import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';

export class ReboundAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    
    // Rebound configuration
    this.reboundConfig = {
      // Player movement parameters
      movementDuration: 600, // ms
      movementEase: 'Power2',
      
      // Rebound positioning
      rebounderOffset: { x: 0, y: -5 }, // Ball position relative to rebounder
      
      // Player collapse parameters
      collapseDistance: 40, // pixels
      collapseDuration: 500, // ms
      
      // Outlet pass parameters
      outletPassDuration: 400, // ms
      outletPassEase: 'Power2',
      
      // Court bounds
      courtBounds: {
        minX: 20,
        maxX: 780,
        minY: 20,
        maxY: 580
      }
    };
    
    // Active rebound tracking
    this.activeRebound = null;
    this.reboundQueue = [];
    
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Initialized');
    }
  }

  /**
   * Process a rebound turn
   */
  async processRebound(turnData) {
    console.log('ReboundAnimationSystem: processRebound called', {
      result_type: turnData.result_type,
      rebounder_id: turnData.rebounder_id,
      rebounderId: turnData.rebounderId,
      rebound_type: turnData.rebound_type,
      allKeys: Object.keys(turnData)
    });

    if (this.activeRebound) {
      console.warn('ReboundAnimationSystem: Already processing a rebound, queuing...');
      this.reboundQueue.push(turnData);
      return;
    }

    this.activeRebound = turnData;
    
    try {
      console.log('ReboundAnimationSystem: Processing rebound', {
        rebounder_id: turnData.rebounder_id,
        rebound_type: turnData.rebound_type,
        result_type: turnData.result_type
      });

      // Validate rebound data
      if (!this.validateReboundData(turnData)) {
        console.error('ReboundAnimationSystem: Validation failed', turnData);
        throw new Error('Invalid rebound data');
      }

      // Get rebounder sprite
      const rebounderSprite = this.getRebounderSprite(turnData);
      if (!rebounderSprite) {
        throw new Error('Rebounder sprite not found');
      }

      // Determine rebound type and execute appropriate sequence
      const reboundType = this.determineReboundType(turnData);
      
      switch (reboundType) {
        case 'defensive':
          await this.executeDefensiveReboundSequence(rebounderSprite, turnData);
          break;
        case 'offensive':
          await this.executeOffensiveReboundSequence(rebounderSprite, turnData);
          break;
        default:
          throw new Error(`Unknown rebound type: ${reboundType}`);
      }

      // Process any queued rebounds
      await this.processReboundQueue();

    } catch (error) {
      console.error('ReboundAnimationSystem: Error processing rebound', error);
      this.handleReboundError(error, turnData);
    } finally {
      this.activeRebound = null;
    }
  }

  /**
   * Execute defensive rebound sequence
   */
  async executeDefensiveReboundSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing defensive rebound sequence');
    }

    // 1. Animate players collapsing for rebound
    await this.animatePlayerCollapse(rebounderSprite, turnData);

    // 2. Attach ball to rebounder
    this.ballController.attachToPlayer(rebounderSprite, {
      offset: this.reboundConfig.rebounderOffset
    });

    // 3. Determine next play type and execute
    const nextPlayType = this.determineNextPlayType(turnData);
    
    switch (nextPlayType) {
      case 'HCO':
        await this.executeHCOSequence(rebounderSprite, turnData);
        break;
      case 'FAST_BREAK':
        await this.executeFastBreakSequence(rebounderSprite, turnData);
        break;
      default:
        console.warn('ReboundAnimationSystem: Unknown next play type', nextPlayType);
    }

    // 4. Transition to POSSESSION state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'defensive_rebound_complete',
        rebounder_id: turnData.rebounder_id,
        next_play_type: nextPlayType
      });
    }
  }

  /**
   * Execute offensive rebound sequence
   */
  async executeOffensiveReboundSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing offensive rebound sequence');
    }

    // 1. Animate players collapsing for rebound
    await this.animatePlayerCollapse(rebounderSprite, turnData);

    // 2. Attach ball to rebounder
    this.ballController.attachToPlayer(rebounderSprite, {
      offset: this.reboundConfig.rebounderOffset
    });

    // 3. Determine offensive rebound outcome
    const outcome = this.determineOffensiveReboundOutcome(turnData);
    
    switch (outcome) {
      case 'putback':
        await this.executePutbackSequence(rebounderSprite, turnData);
        break;
      case 'kickout':
        await this.executeKickoutSequence(rebounderSprite, turnData);
        break;
      default:
        console.warn('ReboundAnimationSystem: Unknown offensive rebound outcome', outcome);
    }

    // 4. Transition to POSSESSION state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'offensive_rebound_complete',
        rebounder_id: turnData.rebounder_id,
        outcome: outcome
      });
    }
  }

  /**
   * Animate players collapsing for rebound
   */
  async animatePlayerCollapse(rebounderSprite, turnData) {
    return new Promise((resolve) => {
      const collapsePromises = [];
      
      // Get all player sprites
      const allPlayers = Object.values(this.playerSprites);
      
      // Animate each player moving toward rebounder
      allPlayers.forEach(playerSprite => {
        if (playerSprite === rebounderSprite) return; // Skip rebounder
        
        const collapsePromise = this.animatePlayerCollapseToRebounder(playerSprite, rebounderSprite);
        collapsePromises.push(collapsePromise);
      });
      
      // Wait for all collapse animations to complete
      Promise.all(collapsePromises).then(() => {
        resolve();
      });
    });
  }

  /**
   * Animate individual player collapse to rebounder
   */
  async animatePlayerCollapseToRebounder(playerSprite, rebounderSprite) {
    return new Promise((resolve) => {
      // Calculate collapse direction
      const dx = rebounderSprite.x - playerSprite.x;
      const dy = rebounderSprite.y - playerSprite.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      // Limit collapse distance
      const collapseDistance = Math.min(distance * 0.3, this.reboundConfig.collapseDistance);
      const collapseRatio = collapseDistance / distance;
      
      const targetX = playerSprite.x + (dx * collapseRatio);
      const targetY = playerSprite.y + (dy * collapseRatio);
      
      // Ensure target is within court bounds
      const clampedX = Math.max(this.reboundConfig.courtBounds.minX, 
        Math.min(this.reboundConfig.courtBounds.maxX, targetX));
      const clampedY = Math.max(this.reboundConfig.courtBounds.minY, 
        Math.min(this.reboundConfig.courtBounds.maxY, targetY));
      
      // Animate player movement
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: clampedX,
        y: clampedY,
        duration: this.reboundConfig.collapseDuration,
        ease: this.reboundConfig.movementEase,
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Execute Half Court Offense (HCO) sequence
   */
  async executeHCOSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing HCO sequence');
    }

    // 1. Move PG to outlet position
    const pgSprite = this.findPointGuard(rebounderSprite.team);
    if (pgSprite) {
      await this.animatePGToOutlet(pgSprite, rebounderSprite);
    }

    // 2. Move other 8 players toward offense basket
    await this.animatePlayersToOffenseBasket(rebounderSprite, turnData);

    // 3. Execute outlet pass
    if (pgSprite) {
      await this.executeOutletPass(rebounderSprite, pgSprite, turnData);
    }
  }

  /**
   * Execute Fast Break sequence
   */
  async executeFastBreakSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing Fast Break sequence');
    }

    // 1. Move outlet receiver to fast break position
    const outletReceiver = this.findOutletReceiver(rebounderSprite.team);
    if (outletReceiver) {
      await this.animateOutletReceiverToFastBreak(outletReceiver, turnData);
    }

    // 2. Move defenders back on defense
    await this.animateDefendersBackOnDefense(rebounderSprite, turnData);

    // 3. Execute outlet pass
    if (outletReceiver) {
      await this.executeOutletPass(rebounderSprite, outletReceiver, turnData);
    }
  }

  /**
   * Execute putback sequence
   */
  async executePutbackSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing putback sequence');
    }

    // Putback is handled by the shot system
    // This is just a placeholder for future putback-specific logic
    console.log('ReboundAnimationSystem: Putback sequence - handled by shot system');
  }

  /**
   * Execute kickout sequence
   */
  async executeKickoutSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing kickout sequence');
    }

    // 1. Find kickout target (usually PG)
    const kickoutTarget = this.findKickoutTarget(rebounderSprite.team);
    if (!kickoutTarget) {
      console.warn('ReboundAnimationSystem: No kickout target found');
      return;
    }

    // 2. Execute kickout pass
    await this.executeKickoutPass(rebounderSprite, kickoutTarget, turnData);
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
        duration: this.reboundConfig.movementDuration,
        ease: this.reboundConfig.movementEase,
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Animate players to offense basket
   */
  async animatePlayersToOffenseBasket(rebounderSprite, turnData) {
    return new Promise((resolve) => {
      const movementPromises = [];
      
      // Get all players except rebounder and PG
      const allPlayers = Object.values(this.playerSprites);
      const pgSprite = this.findPointGuard(rebounderSprite.team);
      
      allPlayers.forEach(playerSprite => {
        if (playerSprite === rebounderSprite || playerSprite === pgSprite) return;
        
        const movementPromise = this.animatePlayerToOffenseBasket(playerSprite, turnData);
        movementPromises.push(movementPromise);
      });
      
      Promise.all(movementPromises).then(() => {
        resolve();
      });
    });
  }

  /**
   * Animate individual player to offense basket
   */
  async animatePlayerToOffenseBasket(playerSprite, turnData) {
    return new Promise((resolve) => {
      // Determine offense basket direction
      const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
      const offenseBasketX = isHomeTeam ? 89 : 11; // From courtConstants.js
      
      // Calculate movement direction
      const currentX = playerSprite.x;
      const direction = offenseBasketX > 50 ? 1 : -1; // Move toward offense basket
      
      // Random movement amount (20-30 x spots, ±10 y spots)
      const moveX = direction * (20 + Math.random() * 10);
      const moveY = (Math.random() - 0.5) * 20;
      
      const targetX = Math.max(this.reboundConfig.courtBounds.minX,
        Math.min(this.reboundConfig.courtBounds.maxX, currentX + moveX));
      const targetY = Math.max(this.reboundConfig.courtBounds.minY,
        Math.min(this.reboundConfig.courtBounds.maxY, playerSprite.y + moveY));
      
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetX,
        y: targetY,
        duration: this.reboundConfig.movementDuration,
        ease: this.reboundConfig.movementEase,
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Execute outlet pass
   */
  async executeOutletPass(passerSprite, receiverSprite, turnData) {
    return new Promise((resolve) => {
      // Detach ball from passer
      this.ballController.detachFromPlayer('outlet_pass');
      
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
        duration: this.reboundConfig.outletPassDuration,
        ease: this.reboundConfig.outletPassEase,
        onComplete: () => {
          // Attach ball to receiver
          this.ballController.endFlight(receiverSprite);
          resolve();
        },
        onUpdate: () => {
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Execute kickout pass
   */
  async executeKickoutPass(passerSprite, receiverSprite, turnData) {
    return new Promise((resolve) => {
      // Detach ball from passer
      this.ballController.detachFromPlayer('kickout_pass');
      
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
        duration: this.reboundConfig.outletPassDuration,
        ease: this.reboundConfig.outletPassEase,
        onComplete: () => {
          // Attach ball to receiver
          this.ballController.endFlight(receiverSprite);
          resolve();
        },
        onUpdate: () => {
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Helper methods
   */
  getRebounderSprite(turnData) {
    const rebounderId = turnData.rebounder_id || turnData.player_id;
    return this.playerSprites[rebounderId] || null;
  }

  determineReboundType(turnData) {
    if (turnData.rebound_type) {
      return turnData.rebound_type.toLowerCase().includes('defensive') ? 'defensive' : 'offensive';
    }
    
    // Fallback logic based on result type
    if (turnData.result_type === 'DREB') return 'defensive';
    if (turnData.result_type === 'OREB') return 'offensive';
    
    // Default to defensive
    return 'defensive';
  }

  determineNextPlayType(turnData) {
    // Check if fast break is available
    if (turnData.fast_break_available === true) {
      return 'FAST_BREAK';
    }
    
    // Check if fast break is disabled (e.g., after missed fast break shot)
    if (turnData.fast_break_disabled === true) {
      return 'HCO';
    }
    
    // Default to HCO
    return 'HCO';
  }

  determineOffensiveReboundOutcome(turnData) {
    // Check for putback attempt
    if (turnData.putback_attempt === true) {
      return 'putback';
    }
    
    // Default to kickout
    return 'kickout';
  }

  findPointGuard(team) {
    // Find PG by team and position
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.position === 'PG'
    );
  }

  findOutletReceiver(team) {
    // For fast breaks, find the designated outlet receiver
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.isOutletReceiver === true
    ) || this.findPointGuard(team);
  }

  findKickoutTarget(team) {
    // Usually the PG for kickouts
    return this.findPointGuard(team);
  }

  validateReboundData(turnData) {
    return turnData && 
           (turnData.rebounder_id || turnData.player_id) &&
           (turnData.rebound_type || turnData.result_type);
  }

  /**
   * Process queued rebounds
   */
  async processReboundQueue() {
    if (this.reboundQueue.length === 0) return;

    const nextRebound = this.reboundQueue.shift();
    if (nextRebound) {
      await this.processRebound(nextRebound);
    }
  }

  /**
   * Handle rebound errors
   */
  handleReboundError(error, turnData) {
    console.error('ReboundAnimationSystem: Rebound error', {
      error: error.message,
      turnData,
      activeRebound: this.activeRebound
    });

    // Reset to safe state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'rebound_error',
        error: error.message
      });
    }
  }

  /**
   * Get rebound system status
   */
  getStatus() {
    return {
      activeRebound: this.activeRebound?.index || null,
      reboundQueue: this.reboundQueue.length,
      isProcessing: !!this.activeRebound,
      reboundConfig: this.reboundConfig
    };
  }

  /**
   * Update rebound configuration
   */
  updateConfig(newConfig) {
    this.reboundConfig = { ...this.reboundConfig, ...newConfig };
    
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Config updated', this.reboundConfig);
    }
  }

  /**
   * Reset rebound system
   */
  reset() {
    this.activeRebound = null;
    this.reboundQueue = [];
    
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Reset');
    }
  }
}

export default ReboundAnimationSystem;
