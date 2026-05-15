/**
 * ReboundAnimationSystem - Rebound Positioning Handler
 * 
 * Handles rebound positioning and player movement:
 * - Defensive rebounds (positioning and HCO outlet setup)
 * - Offensive rebounds (positioning only)
 * - Player collapse animations
 * - Ball attachment to rebounders
 * 
 * Note: Shot attempts (putbacks) and passes (kickouts) are handled by ShotAnimationSystem
 * 
 * Key Benefits:
 * - Focused on rebound positioning only
 * - Proper player movement and ball attachment
 * - Coordinated with shot system for follow-up actions
 * - No conflicts with shot/pass animations
 */

import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';
import { gridToPixels } from '../utils/gridToPixels.js';
import { playReboundSfx } from '../utils/gameSfx.js';
import { announceReboundHeadlineIfNeeded } from '../utils/announcements.js';

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
   * Execute defensive rebound sequence (pure rebound only)
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
    playReboundSfx(this.scene, 'DREB');
    announceReboundHeadlineIfNeeded(
      this.scene,
      turnData,
      rebounderSprite,
      turnData.rebounder_id ?? turnData.rebounderId ?? turnData.rebounder_player_id
    );

    // 3. Determine next play type (for logging only - actual handling done by next turn)
    const nextPlayType = this.determineNextPlayType(turnData);
    console.log('🎬 ReboundAnimationSystem: Defensive rebound complete, next play type:', nextPlayType);

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
   * Execute offensive rebound sequence (positioning only)
   * Note: Shot attempts (putbacks) are handled by ShotAnimationSystem
   */
  async executeOffensiveReboundSequence(rebounderSprite, turnData) {
    if (DebugFlags.REBOUND_ANIMATION) {
      console.log('ReboundAnimationSystem: Executing offensive rebound sequence (positioning only)');
    }

    // 1. Animate players collapsing for rebound
    await this.animatePlayerCollapse(rebounderSprite, turnData);

    // 2. Attach ball to rebounder
    this.ballController.attachToPlayer(rebounderSprite, {
      offset: this.reboundConfig.rebounderOffset
    });
    playReboundSfx(this.scene, 'OREB');
    announceReboundHeadlineIfNeeded(
      this.scene,
      turnData,
      rebounderSprite,
      turnData.rebounder_id ?? turnData.rebounderId ?? turnData.rebounder_player_id
    );

    // 3. Determine offensive rebound outcome for logging only
    const outcome = this.determineOffensiveReboundOutcome(turnData);
    console.log('ReboundAnimationSystem: Offensive rebound outcome determined:', outcome);
    console.log('ReboundAnimationSystem: Shot attempts will be handled by ShotAnimationSystem');

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

  // HCO sequence methods moved to HCOAnimationSystem

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

  // Note: Putback and kickout sequences are now handled by ShotAnimationSystem

  // HCO positioning methods moved to HCOAnimationSystem

  // Note: Kickout passes are now handled by ShotAnimationSystem

  /**
   * Helper methods
   */
  getRebounderSprite(turnData) {
    const rebounderId =
      turnData.rebounder_id ||
      turnData.rebounderId ||
      turnData.rebounder_player_id ||
      turnData.player_id;
    if (rebounderId == null || rebounderId === '') return null;
    const sid = String(rebounderId);
    return this.playerSprites[sid] || this.playerSprites[rebounderId] || null;
  }

  determineReboundType(turnData) {
    if (turnData.rebound_type) {
      const rt = String(turnData.rebound_type).toUpperCase();
      if (rt === 'DREB' || rt.includes('DEFENSIVE')) return 'defensive';
      if (rt === 'OREB' || rt.includes('OFFENSIVE')) return 'offensive';
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

  // findPointGuard method moved to HCOAnimationSystem

  findOutletReceiver(team) {
    // For fast breaks, find the designated outlet receiver
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.isOutletReceiver === true
    ) || this.findPointGuard(team);
  }

  // Note: findKickoutTarget removed - kickouts handled by ShotAnimationSystem

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
