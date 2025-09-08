/**
 * PassAnimationSystem - Universal Pass Animation Handler
 * 
 * Handles all pass scenarios using the new Phase 1 components:
 * - Regular passes (assists, kickouts, outlet passes)
 * - Fast break passes
 * - Inbound passes
 * - Pass animations with proper ball flight
 * - Receiver positioning and ball attachment
 * 
 * Key Benefits:
 * - Single system for all pass types
 * - Consistent ball flight behavior
 * - Proper receiver positioning
 * - No teleports or floating balls
 */

import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';

export class PassAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    
    // Pass configuration
    this.passConfig = {
      // Ball flight parameters
      flightDuration: 500, // ms
      flightEase: 'Power2',
      
      // Pass types and their specific settings
      passTypes: {
        'assist': { duration: 400, ease: 'Power2' },
        'outlet': { duration: 300, ease: 'Power2' },
        'kickout': { duration: 350, ease: 'Power2' },
        'inbound': { duration: 600, ease: 'Power2' },
        'fast_break': { duration: 250, ease: 'Power2' },
        'default': { duration: 500, ease: 'Power2' }
      },
      
      // Receiver positioning
      receiverOffset: { x: 0, y: -10 }, // Ball position relative to receiver
      
      // Pass trajectory
      arcHeight: 20, // pixels for curved passes
      useArc: true, // whether to use curved trajectory
      
      // Court bounds
      courtBounds: {
        minX: 20,
        maxX: 780,
        minY: 20,
        maxY: 580
      }
    };
    
    // Active pass tracking
    this.activePass = null;
    this.passQueue = [];
    
    if (DebugFlags.PASS_ANIMATION) {
      console.log('PassAnimationSystem: Initialized');
    }
  }

  /**
   * Process a pass turn
   */
  async processPass(turnData, context = {}) {
    console.log('🎬 PassAnimationSystem: Starting pass processing', {
      result_type: turnData.result_type,
      activePass: !!this.activePass
    });
    
    if (this.activePass) {
      console.warn('PassAnimationSystem: Already processing a pass, queuing...');
      this.passQueue.push(turnData);
      return;
    }

    this.activePass = turnData;
    
    try {
      console.log('PassAnimationSystem: Processing pass', {
        passer_id: turnData.passer_id,
        receiver_id: turnData.receiver_id,
        pass_type: turnData.pass_type,
        result_type: turnData.result_type,
        allKeys: Object.keys(turnData)
      });

      // Validate pass data
      if (!this.validatePassData(turnData)) {
        throw new Error('Invalid pass data');
      }

      // Handle different pass types
      if (turnData.result_type === 'SIDE_INBOUND' || turnData.result_type === 'BASELINE_INBOUND') {
        console.log('🎬 PassAnimationSystem: Processing inbound pass with positioning data');
        await this.executeInboundSequence(turnData, context);
      } else if (this.isHCOPass(turnData)) {
        console.log('🎬 PassAnimationSystem: Processing HCO pass with positioning');
        await this.executeHCOSequence(turnData, context);
      } else {
        // Regular pass logic
        const passerSprite = this.getPasserSprite(turnData);
        const receiverSprite = this.getReceiverSprite(turnData);
        
        if (!passerSprite) {
          throw new Error('Passer sprite not found');
        }
        if (!receiverSprite) {
          throw new Error('Receiver sprite not found');
        }

        // Execute pass sequence
        await this.executePassSequence(passerSprite, receiverSprite, turnData);
      }

      // Process any queued passes
      await this.processPassQueue();

    } catch (error) {
      console.error('PassAnimationSystem: Error processing pass', error);
      this.handlePassError(error, turnData);
    } finally {
      this.activePass = null;
    }
  }

  /**
   * Execute the complete pass sequence
   */
  async executePassSequence(passerSprite, receiverSprite, turnData) {
    // 1. Ensure we're in POSSESSION state
    if (this.stateMachine && !this.stateMachine.is(AnimationStates.POSSESSION)) {
      if (this.stateMachine) {
        this.stateMachine.transition(AnimationStates.POSSESSION, {
          reason: 'pass_initiated',
          passer_id: turnData.passer_id
        });
      }
    }

    // 2. Position receiver if needed
    await this.positionReceiver(receiverSprite, turnData);

    // 3. Execute the pass
    await this.executePass(passerSprite, receiverSprite, turnData);

    // 4. Handle pass outcome
    if (turnData.result_type === 'MAKE') {
      await this.handleSuccessfulPass(receiverSprite, turnData);
    } else {
      await this.handleFailedPass(turnData);
    }
  }

  /**
   * Position receiver for the pass
   */
  async positionReceiver(receiverSprite, turnData) {
    // Check if receiver needs to move to a specific position
    if (turnData.receiver_target_position) {
      return new Promise((resolve) => {
        const targetPos = turnData.receiver_target_position;
        
        const tween = this.scene.tweens.add({
          targets: receiverSprite,
          x: targetPos.x,
          y: targetPos.y,
          duration: 300,
          ease: 'Power2',
          onComplete: () => {
            resolve();
          }
        });
      });
    }
    
    // For inbound passes, position receiver at inbound spot
    if (turnData.pass_type === 'inbound') {
      return new Promise((resolve) => {
        const inboundPosition = this.calculateInboundPosition(turnData);
        
        const tween = this.scene.tweens.add({
          targets: receiverSprite,
          x: inboundPosition.x,
          y: inboundPosition.y,
          duration: 400,
          ease: 'Power2',
          onComplete: () => {
            resolve();
          }
        });
      });
    }
    
    // For fast break passes, position receiver for fast break
    if (turnData.pass_type === 'fast_break') {
      return new Promise((resolve) => {
        const fastBreakPosition = this.calculateFastBreakPosition(receiverSprite, turnData);
        
        const tween = this.scene.tweens.add({
          targets: receiverSprite,
          x: fastBreakPosition.x,
          y: fastBreakPosition.y,
          duration: 200,
          ease: 'Power2',
          onComplete: () => {
            resolve();
          }
        });
      });
    }
  }

  /**
   * Execute the actual pass animation
   */
  async executePass(passerSprite, receiverSprite, turnData) {
    return new Promise((resolve) => {
      // Get pass configuration
      const passType = turnData.pass_type || 'default';
      const passConfig = this.passConfig.passTypes[passType] || this.passConfig.passTypes.default;
      
      // Detach ball from passer
      this.ballController.detachFromPlayer('pass');
      
      // Start ball flight
      const targetPosition = {
        x: receiverSprite.x + this.passConfig.receiverOffset.x,
        y: receiverSprite.y + this.passConfig.receiverOffset.y
      };
      
      this.ballController.startFlight(targetPosition, {
        duration: passConfig.duration,
        ease: passConfig.ease
      });
      
      // Animate ball to receiver
      const ballSprite = this.ballController.ballSprite;
      if (!ballSprite) {
        console.warn('PassAnimationSystem: No ball sprite available');
        resolve();
        return;
      }
      
      // Position ball at passer
      ballSprite.setPosition(passerSprite.x, passerSprite.y - 10);
      ballSprite.setVisible(true);
      
      // Create pass animation
      const tweenConfig = {
        targets: ballSprite,
        x: targetPosition.x,
        y: targetPosition.y,
        duration: passConfig.duration,
        ease: passConfig.ease,
        onComplete: () => {
          // Attach ball to receiver
          this.ballController.endFlight(receiverSprite, {
            offset: this.passConfig.receiverOffset
          });
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
          
          // Add arc effect if enabled
          if (this.passConfig.useArc) {
            this.addArcEffect(ballSprite, passerSprite, receiverSprite, passConfig.duration);
          }
        }
      };
      
      // Add arc effect if enabled
      if (this.passConfig.useArc) {
        tweenConfig.yoyo = false;
        tweenConfig.repeat = 0;
      }
      
      const tween = this.scene.tweens.add(tweenConfig);
      
      if (DebugFlags.PASS_ANIMATION) {
        console.log('PassAnimationSystem: Pass animation started', {
          from: { x: passerSprite.x, y: passerSprite.y },
          to: targetPosition,
          pass_type: passType,
          duration: passConfig.duration
        });
      }
    });
  }

  /**
   * Add arc effect to pass animation
   */
  addArcEffect(ballSprite, passerSprite, receiverSprite, duration) {
    // Calculate arc height based on pass distance
    const dx = receiverSprite.x - passerSprite.x;
    const dy = receiverSprite.y - passerSprite.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    // Arc height proportional to distance
    const arcHeight = Math.min(distance * 0.1, this.passConfig.arcHeight);
    
    // Apply arc effect using sine wave
    const progress = this.calculateTweenProgress(ballSprite, passerSprite, receiverSprite);
    const arcOffset = Math.sin(progress * Math.PI) * arcHeight;
    
    // Update ball Y position with arc
    const baseY = ballSprite.y;
    ballSprite.setPosition(ballSprite.x, baseY - arcOffset);
  }

  /**
   * Calculate tween progress for arc effect
   */
  calculateTweenProgress(ballSprite, passerSprite, receiverSprite) {
    const totalDistance = Math.sqrt(
      Math.pow(receiverSprite.x - passerSprite.x, 2) + 
      Math.pow(receiverSprite.y - passerSprite.y, 2)
    );
    
    const currentDistance = Math.sqrt(
      Math.pow(ballSprite.x - passerSprite.x, 2) + 
      Math.pow(ballSprite.y - passerSprite.y, 2)
    );
    
    return Math.min(currentDistance / totalDistance, 1);
  }

  /**
   * Handle successful pass
   */
  async handleSuccessfulPass(receiverSprite, turnData) {
    if (DebugFlags.PASS_ANIMATION) {
      console.log('PassAnimationSystem: Pass successful', {
        receiver_id: turnData.receiver_id,
        pass_type: turnData.pass_type
      });
    }

    // Ball is already attached to receiver by executePass
    // Stay in POSSESSION state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'pass_successful',
        receiver_id: turnData.receiver_id
      });
    }
  }

  /**
   * Execute inbound pass sequence using positioning data
   */
  async executeInboundSequence(turnData, context = {}) {
    console.log('🎬 PassAnimationSystem: Executing inbound sequence', {
      result_type: turnData.result_type,
      oDestinations: turnData.oDestinations,
      dDestinations: turnData.dDestinations,
      ball_spot: turnData.ball_spot,
      possession_team_id: turnData.possession_team_id,
      fullTurnData: turnData
    });

    try {
      // For now, we'll use the old system's inbound logic as a fallback
      // This ensures we get working animations while we develop the new system
      console.log('🔄 PassAnimationSystem: Using fallback inbound animation');
      
      // Import and use the correct inbound setup based on type
      const { runSideInboundSetup, runInboundSetup } = await import('./turnAnimation.js');
      
      if (turnData.result_type === 'BASELINE_INBOUND') {
        // For baseline inbound passes (after made shots), use runInboundSetup
        console.log('🎯 PassAnimationSystem: Using runInboundSetup for baseline inbound');
        
        // Determine the new offense side based on possession_team_id
        const isHomeOffense = turnData.possession_team_id === this.scene.homeTeamId;
        const newOffenseSide = isHomeOffense ? 'home' : 'away';
        
        await runInboundSetup({
          scene: this.scene,
          ballSprite: context.ballSprite,
          playerSprites: this.playerSprites,
          newOffenseSide: newOffenseSide,
          homeTeamId: this.scene.homeTeamId,
          awayTeamId: this.scene.awayTeamId
        });
      } else {
        // For side inbound passes (after dead balls/fouls), use runSideInboundSetup
        console.log('🎯 PassAnimationSystem: Using runSideInboundSetup for side inbound');
        await runSideInboundSetup({
          scene: this.scene,
          ballSprite: context.ballSprite,
          playerSprites: this.playerSprites,
          turnData: turnData
        });
      }
      
      console.log('✅ PassAnimationSystem: Inbound sequence completed');
      
    } catch (error) {
      console.error('❌ PassAnimationSystem: Inbound sequence failed', error);
      throw error;
    }
  }

  /**
   * Handle failed pass (turnover)
   */
  async handleFailedPass(turnData) {
    if (DebugFlags.PASS_ANIMATION) {
      console.log('PassAnimationSystem: Pass failed', {
        passer_id: turnData.passer_id,
        pass_type: turnData.pass_type
      });
    }

    // Ball should be detached (handled by executePass)
    // Transition to IDLE state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'pass_failed',
        passer_id: turnData.passer_id
      });
    }
  }

  /**
   * Calculate inbound position for receiver
   */
  calculateInboundPosition(turnData) {
    // Get court bounds
    const courtWidth = this.scene.game.config.width;
    const courtHeight = this.scene.game.config.height;
    
    // Determine inbound side
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    const inboundX = isHomeTeam ? 50 : courtWidth - 50; // Near baseline
    const inboundY = courtHeight / 2; // Middle of court
    
    return { x: inboundX, y: inboundY };
  }

  /**
   * Calculate fast break position for receiver
   */
  calculateFastBreakPosition(receiverSprite, turnData) {
    // Move receiver further down court for fast break
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    const fastBreakX = isHomeTeam ? 
      Math.min(receiverSprite.x + 40, this.passConfig.courtBounds.maxX) :
      Math.max(receiverSprite.x - 40, this.passConfig.courtBounds.minX);
    
    const fastBreakY = receiverSprite.y + (Math.random() - 0.5) * 20;
    
    return { 
      x: fastBreakX, 
      y: Math.max(this.passConfig.courtBounds.minY, 
        Math.min(this.passConfig.courtBounds.maxY, fastBreakY))
    };
  }

  /**
   * Helper methods
   */
  getPasserSprite(turnData) {
    const passerId = turnData.passer_id || turnData.player_id;
    return this.playerSprites[passerId] || null;
  }

  getReceiverSprite(turnData) {
    const receiverId = turnData.receiver_id;
    return this.playerSprites[receiverId] || null;
  }

  validatePassData(turnData) {
    console.log('🔍 PassAnimationSystem: Validating pass data', {
      result_type: turnData.result_type,
      passer_id: turnData.passer_id,
      player_id: turnData.player_id,
      receiver_id: turnData.receiver_id,
      oDestinations: turnData.oDestinations,
      dDestinations: turnData.dDestinations,
      ball_spot: turnData.ball_spot,
      allKeys: Object.keys(turnData),
      fullTurnData: turnData
    });
    
    // For regular passes (MAKE/MISS), check for passer and receiver
    if (turnData.result_type === 'MAKE' || turnData.result_type === 'MISS') {
      const isValid = turnData && 
             (turnData.passer_id || turnData.player_id) &&
             turnData.receiver_id;
      console.log('✅ PassAnimationSystem: Regular pass validation result:', isValid);
      return isValid;
    }
    
    // For inbound passes (SIDE_INBOUND/BASELINE_INBOUND), check for positioning data
    if (turnData.result_type === 'SIDE_INBOUND' || turnData.result_type === 'BASELINE_INBOUND') {
      const isValid = turnData && 
             turnData.oDestinations &&
             turnData.dDestinations &&
             turnData.ball_spot &&
             turnData.possession_team_id;
      console.log('✅ PassAnimationSystem: Inbound pass validation result:', isValid);
      return isValid;
    }
    
    console.log('✅ PassAnimationSystem: Unknown pass type validation result: false');
    return false;
  }

  /**
   * Process queued passes
   */
  async processPassQueue() {
    if (this.passQueue.length === 0) return;

    const nextPass = this.passQueue.shift();
    if (nextPass) {
      await this.processPass(nextPass);
    }
  }

  /**
   * Handle pass errors
   */
  handlePassError(error, turnData) {
    console.error('PassAnimationSystem: Pass error', {
      error: error.message,
      turnData,
      activePass: this.activePass
    });

    // Reset to safe state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'pass_error',
        error: error.message
      });
    }

    // Hide ball if visible
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      ballSprite.setVisible(false);
    }
  }

  /**
   * Get pass system status
   */
  getStatus() {
    return {
      activePass: this.activePass?.index || null,
      passQueue: this.passQueue.length,
      isProcessing: !!this.activePass,
      passConfig: this.passConfig
    };
  }

  /**
   * Update pass configuration
   */
  updateConfig(newConfig) {
    this.passConfig = { ...this.passConfig, ...newConfig };
    
    if (DebugFlags.PASS_ANIMATION) {
      console.log('PassAnimationSystem: Config updated', this.passConfig);
    }
  }

  /**
   * Reset pass system
   */
  reset() {
    this.activePass = null;
    this.passQueue = [];
    
    // Hide ball
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      ballSprite.setVisible(false);
    }
    
    if (DebugFlags.PASS_ANIMATION) {
      console.log('PassAnimationSystem: Reset');
    }
  }

  /**
   * Check if this is an HCO pass that needs positioning
   */
  isHCOPass(turnData) {
    // Check if this is an HCO pass following a defensive rebound
    return turnData.result_type === 'HCO' || 
           (turnData.pass_type === 'HCO' && turnData.follows_defensive_rebound);
  }

  /**
   * Execute HCO sequence with positioning step
   */
  async executeHCOSequence(turnData, context = {}) {
    console.log('🎬 PassAnimationSystem: Executing HCO sequence with positioning');
    
    // Check if this follows a defensive rebound (needs positioning step)
    if (this.followsDefensiveRebound(turnData)) {
      console.log('🎬 HCO follows defensive rebound - executing positioning step');
      await this.executeHCOPositioningStep(turnData);
    }
    
    // Now execute the actual HCO pass
    const passerSprite = this.getPasserSprite(turnData);
    const receiverSprite = this.getReceiverSprite(turnData);
    
    if (!passerSprite) {
      throw new Error('HCO passer sprite not found');
    }
    if (!receiverSprite) {
      throw new Error('HCO receiver sprite not found');
    }

    // Execute the actual HCO pass
    await this.executePassSequence(passerSprite, receiverSprite, turnData);
  }

  /**
   * Check if this HCO pass follows a defensive rebound
   */
  followsDefensiveRebound(turnData) {
    // This could be determined by checking the previous turn or a flag
    // For now, we'll assume HCO passes need positioning
    return true;
  }

  /**
   * Execute HCO positioning step (Rebound HCO Outlet animation)
   */
  async executeHCOPositioningStep(turnData) {
    console.log('🎬 Executing HCO positioning step');
    
    // Find the rebounder (should be the current ball holder)
    const rebounderSprite = this.findRebounder(turnData);
    if (!rebounderSprite) {
      console.warn('🎬 No rebounder found for HCO positioning');
      return;
    }

    // 1. Move PG to outlet position
    const pgSprite = this.findPointGuard(rebounderSprite.team);
    console.log('🎬 HCO Positioning: PG found:', !!pgSprite, 'Team:', rebounderSprite.team);
    
    if (pgSprite) {
      console.log('🎬 HCO Positioning: Moving PG to outlet position');
      await this.animatePGToOutlet(pgSprite, rebounderSprite);
    } else {
      console.warn('🎬 HCO Positioning: No PG found for team:', rebounderSprite.team);
    }

    // 2. Move other 8 players toward offense basket
    console.log('🎬 HCO Positioning: Moving other players toward offense basket');
    await this.animatePlayersToOffenseBasket(rebounderSprite, turnData);

    // 3. Execute outlet pass from rebounder to PG
    if (pgSprite) {
      console.log('🎬 HCO Positioning: Executing outlet pass from rebounder to PG');
      await this.executeOutletPass(rebounderSprite, pgSprite, turnData);
      console.log('🎬 HCO Positioning: Outlet pass completed');
    } else {
      console.warn('🎬 HCO Positioning: Cannot execute outlet pass - no PG found');
    }
  }

  /**
   * Find the rebounder (current ball holder)
   */
  findRebounder(turnData) {
    // Try to find the rebounder from turn data or current ball holder
    const rebounderId = turnData.rebounder_id || turnData.passer_id;
    if (rebounderId) {
      return this.playerSprites[rebounderId];
    }
    
    // Fallback: find any player with the ball
    return Object.values(this.playerSprites).find(sprite => 
      sprite.hasBall || sprite.isBallHolder
    );
  }

  /**
   * Find point guard for a team
   */
  findPointGuard(team) {
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.position === 'PG'
    );
  }

  /**
   * Animate PG to outlet position (authentic basketball positioning)
   */
  async animatePGToOutlet(pgSprite, rebounderSprite) {
    return new Promise((resolve) => {
      // Convert to grid coordinates for precise positioning
      const width = this.scene.game.config.width;
      const height = this.scene.game.config.height;
      
      const rebGridX = (rebounderSprite.x / width) * 100;
      const rebGridY = 50 - (rebounderSprite.y / height) * 50;
      
      // Get basket coordinates to determine direction
      const basketGrid = { x: 89, y: 25 }; // Home basket
      if (rebounderSprite.team === 'away') {
        basketGrid.x = 11; // Away basket
      }
      
      // For HCO: move PG near the rebounder (authentic basketball positioning)
      // PG moves 3-6 grid spots toward the basket from rebounder position
      const sign = basketGrid.x > rebGridX ? 1 : -1;
      const outletTarget = {
        x: Phaser.Math.Clamp(
          rebGridX + sign * Phaser.Math.Between(3, 6),
          4,
          97
        ),
        y: Phaser.Math.Clamp(
          rebGridY + Phaser.Math.Between(-6, 6),
          1,
          50
        ),
      };
      
      // Convert back to pixel coordinates
      const outletPx = this.gridToPixels(outletTarget.x, outletTarget.y, width, height);
      
      const tween = this.scene.tweens.add({
        targets: pgSprite,
        x: outletPx.x,
        y: outletPx.y,
        duration: this.passConfig.movementDuration || 500,
        ease: this.passConfig.movementEase || 'Power2',
        onComplete: () => {
          resolve();
        }
      });
      
      console.log('🎬 PG outlet positioning:', {
        rebounderGrid: { x: rebGridX, y: rebGridY },
        outletTarget,
        outletPx,
        direction: sign
      });
    });
  }

  /**
   * Animate players to offense basket (authentic basketball positioning)
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
   * Animate individual player to offense basket (authentic basketball positioning)
   */
  async animatePlayerToOffenseBasket(playerSprite, turnData) {
    return new Promise((resolve) => {
      // Convert to grid coordinates for precise positioning
      const width = this.scene.game.config.width;
      const height = this.scene.game.config.height;
      
      const currentGridX = (playerSprite.x / width) * 100;
      const currentGridY = 50 - (playerSprite.y / height) * 50;
      
      // Move 20-30 grid spots toward new offense basket (authentic basketball)
      const distance = Phaser.Math.Between(20, 30);
      
      // Determine direction based on new offense team
      const newOffenseTeam = turnData.possession_team_id === this.scene.homeTeamId ? 'home' : 'away';
      const direction = newOffenseTeam === "home" ? 1 : -1;
      
      const targetGrid = {
        x: Phaser.Math.Clamp(
          currentGridX + direction * distance,
          4,  // Stay in bounds
          97
        ),
        y: Phaser.Math.Clamp(
          currentGridY + Phaser.Math.Between(-10, 10),
          1,  // Stay in bounds
          50
        ),
      };
      
      // Convert back to pixel coordinates
      const targetPx = this.gridToPixels(targetGrid.x, targetGrid.y, width, height);
      
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetPx.x,
        y: targetPx.y,
        duration: this.passConfig.movementDuration || 500,
        ease: this.passConfig.movementEase || 'Power2',
        onComplete: () => {
          resolve();
        }
      });
      
      console.log(`HCO player movement: ${playerSprite.id || 'unknown'} from (${currentGridX.toFixed(1)}, ${currentGridY.toFixed(1)}) to (${targetGrid.x}, ${targetGrid.y}) [direction: ${direction}, newOffenseTeam: ${newOffenseTeam}]`);
    });
  }

  /**
   * Execute outlet pass from rebounder to PG
   */
  async executeOutletPass(passerSprite, receiverSprite, turnData) {
    console.log('🎬 Executing outlet pass from rebounder to PG');
    return new Promise((resolve) => {
      // Detach ball from passer
      this.ballController.detachFromPlayer('outlet_pass');
      console.log('🎬 Ball detached from rebounder');
      
      // Start ball flight
      this.ballController.startFlight({
        x: receiverSprite.x,
        y: receiverSprite.y - 10
      });
      console.log('🎬 Ball flight started to PG position');
      
      // Animate ball to receiver
      const ballSprite = this.ballController.ballSprite;
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: receiverSprite.x,
        y: receiverSprite.y - 10,
        duration: this.passConfig.outletPassDuration || 400,
        ease: this.passConfig.outletPassEase || 'Power2',
        onComplete: () => {
          // Attach ball to receiver
          this.ballController.endFlight(receiverSprite);
          console.log('🎬 Outlet pass completed - ball attached to PG');
          resolve();
        },
        onUpdate: () => {
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });
    });
  }

  /**
   * Convert grid coordinates to pixel coordinates
   */
  gridToPixels(gridX, gridY, width, height) {
    const x = (gridX / 100) * width;
    const y = height - ((gridY / 50) * height);
    return { x, y };
  }
}

export default PassAnimationSystem;
