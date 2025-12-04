import { DebugFlags } from '../utils/debugFlags.js';

/**
 * HCO Animation System
 * Handles Half Court Offense positioning and setup animations
 */
export class HCOAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.isProcessing = false;
    this.activeHCO = null;
    this.hcoQueue = [];

    if (DebugFlags.HCO_ANIMATION) {
      console.log('HCOAnimationSystem: Initialized');
    }
  }

  /**
   * Process HCO outlet pass step
   */
  async processHCO(turnData, context = {}) {
    console.log('🎬 HCOAnimationSystem: Starting HCO outlet pass processing', {
      result_type: turnData.result_type,
      offensive_state: turnData.offensive_state,
      activeHCO: !!this.activeHCO
    });
    
    if (this.isProcessing) {
      console.warn('HCOAnimationSystem: Already processing HCO, queuing...');
      this.hcoQueue.push(turnData);
      return;
    }

    this.isProcessing = true;
    this.activeHCO = turnData;
    
    try {
      console.log('🎬 HCOAnimationSystem: Processing HCO outlet pass step');
      
      // Execute HCO outlet pass step (Rebound HCO Outlet animation)
      await this.executeHCOOutletPassStep(turnData, context);

      // Process any queued HCO animations
      await this.processHCOQueue();

    } catch (error) {
      console.error('HCOAnimationSystem: Error processing HCO', error);
      this.handleHCOError(error, turnData);
    } finally {
      this.isProcessing = false;
      this.activeHCO = null;
    }
  }

  /**
   * Execute HCO outlet pass step (Rebound HCO Outlet animation)
   */
  async executeHCOOutletPassStep(turnData, context = {}) {
    console.log('🎬 HCOAnimationSystem: Executing HCO outlet pass step');
    
    // Find the rebounder (should be the current ball holder)
    const rebounderSprite = this.findRebounder(turnData);
    if (!rebounderSprite) {
      console.warn('🎬 No rebounder found for HCO outlet pass');
      return;
    }

    // 1. Move PG to outlet position
    const pgSprite = this.findPointGuard(rebounderSprite.team);
    console.log('🎬 HCO Outlet Pass: PG found:', !!pgSprite, 'Team:', rebounderSprite.team);
    
    if (pgSprite) {
      console.log('🎬 HCO Outlet Pass: Moving PG to outlet position');
      await this.animatePGToOutlet(pgSprite, rebounderSprite);
    } else {
      console.warn('🎬 HCO Outlet Pass: No PG found for team:', rebounderSprite.team);
    }

    // 2. Move other 8 players toward offense basket
    console.log('🎬 HCO Outlet Pass: Moving other players toward offense basket');
    await this.animatePlayersToOffenseBasket(rebounderSprite, turnData);

    // 3. Execute outlet pass from rebounder to PG
    if (pgSprite) {
      console.log('🎬 HCO Outlet Pass: Executing outlet pass from rebounder to PG');
      await this.executeOutletPass(rebounderSprite, pgSprite, turnData);
      console.log('🎬 HCO Outlet Pass: Outlet pass completed');
    } else {
      console.warn('🎬 HCO Outlet Pass: Cannot execute outlet pass - no PG found');
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
        duration: 500,
        ease: 'Power2',
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
      
      // ✅ FIX: Use offense_team_id (SS&S possession system)
      const newOffenseTeam = turnData.offense_team_id === this.scene.homeTeamId ? 'home' : 'away';
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
        duration: 500,
        ease: 'Power2',
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
      this.ballController.detachFromPlayer('outlet_pass', { keepVisible: true });
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
        duration: 400,
        ease: 'Power2',
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

  /**
   * Process queued HCO animations
   */
  async processHCOQueue() {
    while (this.hcoQueue.length > 0) {
      const queuedHCO = this.hcoQueue.shift();
      await this.processHCO(queuedHCO);
    }
  }

  /**
   * Handle HCO processing errors
   */
  handleHCOError(error, turnData) {
    console.error('HCOAnimationSystem: HCO processing failed', {
      error: error.message,
      turnData: turnData
    });
    
    // Clear any active tweens
    this.scene.tweens?.killAll?.();
  }

  /**
   * Reset the HCO animation system
   */
  reset() {
    this.isProcessing = false;
    this.activeHCO = null;
    this.hcoQueue = [];
    
    // Clear any active tweens
    this.scene.tweens?.killAll?.();
    
    if (DebugFlags.HCO_ANIMATION) {
      console.log('HCOAnimationSystem: Reset');
    }
  }
}

export default HCOAnimationSystem;
