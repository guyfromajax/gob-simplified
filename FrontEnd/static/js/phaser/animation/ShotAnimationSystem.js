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
import { gridToPixels } from '../utils/gridToPixels.js';
import { animateStep } from './animateStep.js';
import { attachBallToPlayer } from './ballManager.js';
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from './courtConstants.js';

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
      homeRim: HOME_RIM_COORDS,
      awayRim: AWAY_RIM_COORDS
    };
    
    // Active shot tracking
    this.activeShot = null;
    this.shotQueue = [];
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Initialized');
    }
  }

  /**
   * Process a shot turn with complete player movement
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

      // Execute complete shot sequence with player movement
      await this.executeCompleteShotSequence(turnData);

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
   * Execute complete shot sequence with player movement
   */
  async executeCompleteShotSequence(turnData) {
    const ballSprite = this.ballController.ballSprite;
    const currentBallOwnerRef = { value: null };
    
    // Store reference on scene for other modules
    this.scene.currentBallOwnerRef = currentBallOwnerRef;
    
    // Get maximum steps across all animations
    const maxSteps = Math.max(
      ...turnData.animations.map(anim => anim.movement.length)
    );
    
    console.log('🎬 ShotAnimationSystem: Starting complete shot sequence', {
      maxSteps,
      animationCount: turnData.animations.length
    });
    
    // 1. Setup: Move players to step 0 positions
    await this.runSetupTween(turnData, ballSprite, currentBallOwnerRef);
    
    // 2. Determine ball owner at step 0
    let step0OwnerSprite = null;
    for (const anim of turnData.animations) {
      if (anim.hasBallAtStep?.[0]) {
        step0OwnerSprite = this.playerSprites[anim.playerId];
        break;
      }
    }
    
    if (step0OwnerSprite) {
      attachBallToPlayer(this.scene, ballSprite, step0OwnerSprite);
      currentBallOwnerRef.value = step0OwnerSprite;
    }
    
    // 3. Animate step-by-step player movement
    await this.animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps);
    
    // 4. Handle shot outcome
    const isMake = turnData.result_type === 'MAKE';
    const rimCoords = this.getRimCoordinates(turnData);
    
    if (isMake) {
      await this.handleMadeShot(rimCoords, turnData);
    } else {
      await this.handleMissedShot(rimCoords, turnData);
    }
  }
  
  /**
   * Move all players to their step 0 positions
   */
  async runSetupTween(turnData, ballSprite, currentBallOwnerRef) {
    if (this.scene.skipToEnd) return;
    
    const stepIndex = 0;
    const promises = [];
    
    console.log('🎬 ShotAnimationSystem: Running setup tween for step 0');
    
    for (const anim of turnData.animations) {
      if (this.scene.skipToEnd) break;
      const sprite = this.playerSprites[anim.playerId];
      const firstStep = anim.movement?.[stepIndex];
      if (!sprite || !firstStep) continue;
      
      const { x, y } = gridToPixels(
        firstStep.coords.x,
        firstStep.coords.y,
        this.scene.game.config.width,
        this.scene.game.config.height
      );
      
      promises.push(new Promise((resolve) => {
        const tween = this.scene.tweens.add({
          targets: [sprite],
          x,
          y,
          duration: 1000,
          ease: "Linear",
          onUpdate: () => {
            if (currentBallOwnerRef?.value === sprite && ballSprite?.setPosition) {
              ballSprite.setPosition(sprite.x, sprite.y);
              ballSprite.setVisible(true);
            }
          },
          onComplete: resolve,
          onStop: resolve
        });
        if (this.scene.skipToEnd) {
          tween.stop();
        }
      }));
    }
    
    await Promise.all(promises);
    console.log('✅ ShotAnimationSystem: Setup tween completed');
  }
  
  /**
   * Animate player movement step by step
   */
  async animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps) {
    if (this.scene.skipToEnd) return;
    
    console.log('🎬 ShotAnimationSystem: Starting player movement animation');
    
    for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
      if (this.scene.skipToEnd) break;
      
      // Update ball ownership for this step
      this.updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex);
      
      const promises = [];
      let shotInfo = null;
      
      for (const anim of turnData.animations) {
        if (this.scene.skipToEnd) break;
        const sprite = this.playerSprites[anim.playerId];
        const movement = anim.movement;
        
        if (!sprite || stepIndex >= movement.length) continue;
        
        const prev = movement[stepIndex - 1];
        const curr = movement[stepIndex];
        const step = prev;
        const nextStep = curr;
        const rawDuration = (nextStep.timestamp - step.timestamp) * 3;
        const duration = Math.min(1000, rawDuration); // Cap at 1 second
        
        if (nextStep.action === "shoot") {
          shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        }
        
        const promise = animateStep({
          scene: this.scene,
          sprite,
          step: nextStep,
          duration,
          ballSprite,
          currentBallOwnerRef,
          onAction: null // We'll handle actions separately
        });
        
        promises.push(promise);
      }
      
      await Promise.all(promises);
      
      // Handle shot if this step contains one
      if (shotInfo) {
        currentBallOwnerRef.value = null;
        await this.handleShotAtStep(shotInfo, turnData);
      }
    }
    
    console.log('✅ ShotAnimationSystem: Player movement animation completed');
  }
  
  /**
   * Update ball ownership for a specific step
   */
  updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex) {
    // Find who should have the ball at this step
    for (const anim of turnData.animations) {
      if (anim.hasBallAtStep?.[stepIndex]) {
        const newOwnerSprite = this.playerSprites[anim.playerId];
        if (newOwnerSprite && newOwnerSprite !== currentBallOwnerRef.value) {
          console.log('🔄 ShotAnimationSystem: Transferring ball ownership', {
            from: currentBallOwnerRef.value?.playerId || 'none',
            to: anim.playerId,
            stepIndex
          });
          
          // Transfer ball to new owner
          attachBallToPlayer(this.scene, ballSprite, newOwnerSprite);
          currentBallOwnerRef.value = newOwnerSprite;
        }
        break;
      }
    }
  }
  
  /**
   * Handle shot at a specific step
   */
  async handleShotAtStep(shotInfo, turnData) {
    const shooterSprite = this.playerSprites[shotInfo.playerId];
    const rimCoords = this.getRimCoordinates(turnData);
    const isMake = turnData.result_type === 'MAKE';
    
    console.log('🎯 ShotAnimationSystem: Handling shot at step', {
      stepIndex: shotInfo.stepIndex,
      shooterId: shotInfo.playerId,
      isMake
    });
    
    // Detach ball from shooter
    this.ballController.detachFromPlayer('shot');
    
    // Animate ball flight
    await this.animateBallFlight(shooterSprite, rimCoords, turnData);
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

      console.log('🎯 ShotAnimationSystem: Starting ball flight', {
        from: { x: shooterSprite.x, y: shooterSprite.y },
        to: rimCoords,
        shooterId: turnData.shooter_id
      });

      // Position ball at shooter
      ballSprite.setPosition(shooterSprite.x, shooterSprite.y - 10);
      ballSprite.setVisible(true);

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
    console.log('ShotAnimationSystem: Shot missed', {
      shooter_id: turnData.shooter_id,
      shot_type: turnData.shot_type,
      rebounderId: turnData.rebounderId,
      rebound_type: turnData.rebound_type
    });

    // Animate ball bounce from rim
    await this.animateBallBounce(rimCoords, turnData);

    // Check if this shot turn includes rebound data
    if (turnData.rebounderId && turnData.rebound_type) {
      console.log('🎬 ShotAnimationSystem: Handling embedded rebound', {
        rebounderId: turnData.rebounderId,
        rebound_type: turnData.rebound_type
      });
      
      // Handle the rebound within the shot turn
      await this.handleEmbeddedRebound(turnData);
    } else {
      // Transition to REBOUNDING state (fallback)
      this.stateMachine.transition(AnimationStates.REBOUNDING, {
        reason: 'shot_missed',
        shooter_id: turnData.shooter_id
      });
    }
  }

  /**
   * Handle rebound that's embedded within a shot turn
   */
  async handleEmbeddedRebound(turnData) {
    console.log('🎬 ShotAnimationSystem: Processing embedded rebound', {
      rebounderId: turnData.rebounderId,
      rebound_type: turnData.rebound_type
    });

    // Get the rebounder sprite
    const rebounderSprite = this.playerSprites[turnData.rebounderId];
    if (!rebounderSprite) {
      console.error('ShotAnimationSystem: Rebounder sprite not found', turnData.rebounderId);
      return;
    }

    // Get the ball's current position (where it bounced)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Make ball visible if it was hidden
      ballSprite.setVisible(true);
      
      // Get the ball's bounce position (where it currently is)
      const ballBounceX = ballSprite.x;
      const ballBounceY = ballSprite.y;
      
      console.log('🎬 ShotAnimationSystem: Ball bounce position', {
        ballX: ballBounceX,
        ballY: ballBounceY,
        rebounderX: rebounderSprite.x,
        rebounderY: rebounderSprite.y
      });
      
      // Animate rebounder to the ball's bounce position
      await new Promise((resolve) => {
        this.scene.tweens.add({
          targets: rebounderSprite,
          x: ballBounceX,
          y: ballBounceY,
          duration: 400,
          ease: 'Power2',
          onComplete: () => {
            // Attach ball to rebounder once they reach the bounce spot
            this.ballController.attachToPlayer(rebounderSprite, {
              offset: { x: 0, y: -10 }
            });
            resolve();
          }
        });
      });
    }

    // Animate players collapsing toward rebounder (after rebounder gets the ball)
    await this.animatePlayerCollapse(rebounderSprite);

    // Determine next action based on rebound type
    if (turnData.rebound_type === 'DREB') {
      await this.handleDefensiveRebound(rebounderSprite, turnData);
    } else if (turnData.rebound_type === 'OREB') {
      await this.handleOffensiveRebound(rebounderSprite, turnData);
    }

    // Transition to POSSESSION state
    this.stateMachine.transition(AnimationStates.POSSESSION, {
      reason: 'rebound_complete',
      rebounder_id: turnData.rebounderId,
      rebound_type: turnData.rebound_type
    });
  }

  /**
   * Animate players collapsing toward rebounder
   */
  async animatePlayerCollapse(rebounderSprite) {
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
      const collapseDistance = Math.min(distance * 0.3, 40);
      const collapseRatio = collapseDistance / distance;
      
      const targetX = playerSprite.x + (dx * collapseRatio);
      const targetY = playerSprite.y + (dy * collapseRatio);
      
      // Animate player movement
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetX,
        y: targetY,
        duration: 500,
        ease: 'Power2',
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Handle defensive rebound
   */
  async handleDefensiveRebound(rebounderSprite, turnData) {
    console.log('🎬 ShotAnimationSystem: Handling defensive rebound');
    
    // Move PG to outlet position
    const pgSprite = this.findPointGuard(rebounderSprite.team);
    if (pgSprite) {
      await this.animatePGToOutlet(pgSprite, rebounderSprite);
      
      // Execute outlet pass
      await this.executeOutletPass(rebounderSprite, pgSprite);
    }
  }

  /**
   * Handle offensive rebound
   */
  async handleOffensiveRebound(rebounderSprite, turnData) {
    console.log('🎬 ShotAnimationSystem: Handling offensive rebound');
    
    // For now, just keep the ball with the rebounder
    // Future: handle putback attempts or kickouts
  }

  /**
   * Find point guard by team
   */
  findPointGuard(team) {
    return Object.values(this.playerSprites).find(sprite => 
      sprite.team === team && sprite.position === 'PG'
    );
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
        duration: 600,
        ease: 'Power2',
        onComplete: () => {
          resolve();
        }
      });
    });
  }

  /**
   * Execute outlet pass
   */
  async executeOutletPass(passerSprite, receiverSprite) {
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
        duration: 400,
        ease: 'Power2',
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
   * Get rim coordinates based on shot context (converted to pixels)
   */
  getRimCoordinates(turnData) {
    // Get shooter sprite to determine team
    const shooterSprite = this.getShooterSprite(turnData);
    
    // Determine which rim based on shooter's team (like the old system)
    const isHomeTeam = shooterSprite?.team === 'home';
    const gridRimCoords = isHomeTeam ? this.shotConfig.homeRim : this.shotConfig.awayRim;
    
    // Convert grid coordinates to pixel coordinates (like the old system does)
    const pixelRimCoords = gridToPixels(
      gridRimCoords.x,
      gridRimCoords.y,
      this.scene.game.config.width,
      this.scene.game.config.height
    );
    
    console.log('🎯 ShotAnimationSystem: Getting rim coordinates', {
      shooter_id: turnData.shooter_id,
      shooter_team: shooterSprite?.team,
      isHomeTeam,
      gridRimCoords,
      pixelRimCoords,
      homeRim: this.shotConfig.homeRim,
      awayRim: this.shotConfig.awayRim
    });
    
    return pixelRimCoords;
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
