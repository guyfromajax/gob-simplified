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
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from './courtConstants.js';
import { gridToPixels } from '../utils/gridToPixels.js';

export class FreeThrowAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites, gameStore) {
    this.scene = scene;
    this.ballController = ballController;
    this.stateMachine = stateMachine;
    this.playerSprites = playerSprites;
    this.gameStore = gameStore;
    
    // Free throw configuration
    this.ftConfig = {
      // Shot parameters (fallback values, will use animation data when available)
      shotDuration: 1000, // ms
      shotEase: 'Sine.easeInOut',
      
      // Bounce parameters (used by existing bounce system)
      bounceDuration: 600, // ms
      
      // Setup parameters (fallback values, will use animation data when available)
      setupDuration: 800, // ms
      setupEase: 'Linear'
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

      // Adapt backend data structure to new system format
      const adaptedTurnData = this.adaptBackendData(turnData);
      
      // Validate free throw data
      console.log('🔍 FreeThrowAnimationSystem: Validating free throw data', {
        result_type: adaptedTurnData.result_type,
        shooter_id: adaptedTurnData.shooter_id,
        player_id: adaptedTurnData.player_id,
        ftContext: adaptedTurnData.ftContext,
        allKeys: Object.keys(adaptedTurnData),
        fullTurnData: adaptedTurnData
      });
      
      if (!this.validateFreeThrowData(adaptedTurnData)) {
        console.error('❌ FreeThrowAnimationSystem: Free throw data validation failed', {
          result_type: adaptedTurnData.result_type,
          shooter_id: adaptedTurnData.shooter_id,
          player_id: adaptedTurnData.player_id,
          hasResultType: !!adaptedTurnData.result_type,
          isFreeThrow: adaptedTurnData.result_type === 'FREE_THROW',
          hasShooterId: !!(adaptedTurnData.shooter_id || adaptedTurnData.player_id)
        });
        throw new Error('Invalid free throw data');
      }
      
      console.log('✅ FreeThrowAnimationSystem: Free throw data validation passed');

      // Get shooter sprite
      const shooterSprite = this.getShooterSprite(adaptedTurnData);
      if (!shooterSprite) {
        throw new Error('Shooter sprite not found');
      }

      // Determine free throw context
      const ftContext = this.determineFreeThrowContext(adaptedTurnData);

      // Execute free throw sequence
      await this.executeFreeThrowSequence(shooterSprite, adaptedTurnData, ftContext);

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
    if (turnData.actual_result === 'MAKE') {
      await this.handleMadeFreeThrow(turnData, ftContext);
    } else {
      await this.handleMissedFreeThrow(turnData, ftContext);
    }
  }

  /**
   * Setup free throw positioning using backend animation data
   */
  async setupFreeThrowPositioning(shooterSprite, turnData) {
    const animations = turnData.animations || [];
    const playerAnims = animations.filter((a) => a.playerId !== "ball");
    const width = this.scene.game.config.width;
    const height = this.scene.game.config.height;

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Setting up free throw positioning', {
        shooter_id: turnData.shooter_id,
        animations_count: animations.length,
        player_anims_count: playerAnims.length,
        no_lane: turnData.no_lane
      });
    }

    if (!turnData.no_lane) {
      // Move all players to their free throw positions
      const promises = [];
      for (const anim of playerAnims) {
        const sprite = this.playerSprites[anim.playerId];
        const end = anim.movement?.[1]?.coords;
        if (!sprite || !end) continue;
        
        const px = gridToPixels(end.x, end.y, width, height);
        promises.push(
          new Promise((resolve) => {
            this.scene.tweens.add({
              targets: sprite,
              x: px.x,
              y: px.y,
              duration: anim.duration || this.ftConfig.setupDuration,
              ease: "Linear",
              onComplete: resolve,
              onStop: resolve,
            });
          })
        );
      }
      await Promise.all(promises);
    } else {
      // Only move the shooter to the free throw line
      const shooterAnim = playerAnims.find(
        (a) => a.playerId === turnData.shooter_id
      );
      const sprite = this.playerSprites[turnData.shooter_id];
      const end = shooterAnim?.movement?.[1]?.coords;
      if (sprite && end) {
        const px = gridToPixels(end.x, end.y, width, height);
        await new Promise((resolve) => {
          this.scene.tweens.add({
            targets: sprite,
            x: px.x,
            y: px.y,
            duration: shooterAnim.duration || this.ftConfig.setupDuration,
            ease: "Linear",
            onComplete: resolve,
            onStop: resolve,
          });
        });
      }
    }

    // Attach ball to shooter
    if (shooterSprite) {
      this.ballController.attachToPlayer(shooterSprite);
    }

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw positioning complete');
    }
  }

  /**
   * Execute the free throw shot
   */
  async executeFreeThrowShot(shooterSprite, turnData, ftContext) {
    // 1. Transition to SHOOTING state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.SHOOTING, {
        reason: 'free_throw_initiated',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // 2. Detach ball from shooter
    this.ballController.detachFromPlayer('free_throw_shot', { keepVisible: true });

    // 3. Get rim coordinates from animation data
    const rimCoords = this.getRimCoordinatesFromAnimation(turnData);
    await this.animateBallToRim(shooterSprite, rimCoords, turnData);

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw shot executed', {
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total,
        rimCoords: rimCoords
      });
    }
  }

  /**
   * Animate ball to rim using animation data
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

      // Get shot duration from animation data
      const animations = turnData.animations || [];
      const ballAnim = animations.find((a) => a.playerId === "ball");
      const shotDuration = ballAnim?.duration || this.ftConfig.shotDuration;

      // Position ball at shooter
      ballSprite.setPosition(shooterSprite.x, shooterSprite.y - 10);
      ballSprite.setVisible(true);

      // Start flight
      this.ballController.startFlight(rimCoords, {
        duration: shotDuration,
        ease: this.ftConfig.shotEase
      });

      // Animate ball to rim
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: shotDuration,
        ease: "Sine.easeInOut", // Use same easing as old system
        onComplete: () => {
          this.ballController.endFlight();
          resolve();
        },
        onUpdate: () => {
          // Update ball controller position
          this.ballController.updatePosition(ballSprite.x, ballSprite.y);
        }
      });

      if (DebugFlags.FREE_THROW_ANIMATION) {
        console.log('FreeThrowAnimationSystem: Ball animation to rim', {
          from: { x: shooterSprite.x, y: shooterSprite.y - 10 },
          to: rimCoords,
          duration: shotDuration
        });
      }
    });
  }

  /**
   * Handle made free throw
   */
  async handleMadeFreeThrow(turnData, ftContext) {
    // ✅ DEBUG: Log free throw context to diagnose inbound pass issue
    console.log('🏀 [FREE THROW DEBUG] handleMadeFreeThrow', {
      shooter_id: turnData.shooter_id,
      attempt: ftContext.attempt,
      total: ftContext.total,
      isFinal: ftContext.isFinal,
      free_throws_remaining: turnData.free_throws_remaining,
      ftContext_keys: Object.keys(turnData.ftContext || {}),
      ftContext_full: turnData.ftContext
    });
    
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Free throw made', {
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
    }

    // Ball holds in rim for 1 second (authentic basketball feel)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Keep ball visible during hold
      ballSprite.setVisible(true);
      
      // Hold ball at rim for 1 second (no sliding down for non-final free throws)
      await new Promise(resolve => {
        if (this.scene.time?.delayedCall) {
          this.scene.time.delayedCall(1000, resolve);
        } else {
          setTimeout(resolve, 1000);
        }
      });

      // For non-final free throws, just hide the ball after the hold
      // (no slide animation - ball stays at rim coords)
      if (!ftContext.isFinal) {
        ballSprite.setVisible(false);
        }
    }

    // Check if this is the final free throw
    // ✅ FIX: Use ftContext.isFinal instead of recalculating, as it includes the free_throws_remaining safety check
    if (ftContext.isFinal) {
      // Final free throw made - execute inbound pass
      await this.handleFinalMadeFreeThrow(turnData);
    } else {
      // More free throws to come - stay in POSSESSION
      if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'free_throw_made_more_to_come',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
      }
    }
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

    // Use existing bounce system for authentic basketball feel
    const rimGridCoords = this.getRimGridCoordinates(turnData);
    const miss = await this.animateBallBounceFromRim(rimGridCoords, turnData);

    // Check if this is the final free throw
    // ✅ FIX: Use ftContext.isFinal instead of recalculating, as it includes the free_throws_remaining safety check
    if (ftContext.isFinal) {
      // Final free throw missed - execute rebound system
      // ✅ FIX: Pass the bounce result so we don't bounce twice
      await this.handleFinalMissedFreeThrow(turnData, miss);
    } else {
      // More free throws to come - stay in POSSESSION
      if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'free_throw_missed_more_to_come',
        shooter_id: turnData.shooter_id,
        attempt: ftContext.attempt,
        total: ftContext.total
      });
      }
    }
  }

  /**
   * Animate ball bounce from rim using existing bounce system
   */
  async animateBallBounceFromRim(rimCoords, turnData) {
    const ballSprite = this.ballController.ballSprite;
    if (!ballSprite) {
      return;
    }

    // Import the existing bounce system
    const { bounceFromRim } = await import('./ballManager.js');
    
    // Determine if this is home team shooting (for bounce direction)
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    
    // Get rim grid coordinates (bounceFromRim expects grid coordinates, not pixels)
    const rimGridCoords = this.getRimGridCoordinates(turnData);
    
    // Use existing bounce system for authentic basketball feel
    const miss = await bounceFromRim(
      this.scene,
      ballSprite,
      rimGridCoords, // Pass grid coordinates, not pixel coordinates
      isHomeTeam,
      this.ftConfig.bounceDuration
    );

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Ball bounced from rim', {
        rimGridCoords,
        bounceSpot: miss.grid,
        isHomeTeam
      });
    }

    return miss;
  }

  /**
   * Handle final made free throw - execute inbound pass
   */
  async handleFinalMadeFreeThrow(turnData) {
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Final free throw made - executing inbound pass', {
        shooter_id: turnData.shooter_id,
        possession_team_id: turnData.possession_team_id,
        possession_flips: turnData.possession_flips
      });
    }

    // Transition to IDLE state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'free_throw_sequence_complete',
        shooter_id: turnData.shooter_id,
        made: true
      });
    }

    // ✅ FIX: Flip possession BEFORE inbound pass (matches fastBreak.js pattern)
    // After final free throw is made, possession flips - the team that was on defense is now on offense
    // Use possession_team_id from turnData (authoritative backend value)
    const newOffenseTeamId = turnData.possession_team_id;
    if (newOffenseTeamId && turnData.possession_flips !== false) {
      this.scene.offenseTeamId = newOffenseTeamId;
      // Emit possession change event to update other systems
      this.scene.events?.emit('possessionChange', { offenseTeamId: newOffenseTeamId });
      console.log('🏀 [FREE THROW MAKE] Updated offense team ID after possession flip', {
        newOffenseTeamId,
        possession_team_id: turnData.possession_team_id,
        possession_flips: turnData.possession_flips
      });
    }

    // Execute inbound pass using the existing system
    // The key is to use the correct possession_team_id to prevent double possession flips
    const { runInboundSetup } = await import('./turnAnimation.js');
    
    // Determine the new offense side based on possession_team_id (now correctly set above)
    const isHomeOffense = newOffenseTeamId === this.scene.simData?.home_team_id;
    const newOffenseSide = isHomeOffense ? 'home' : 'away';
    
    // ✅ FIX: Check for FCP/HCT setup after free throw (same logic as freeThrow.js)
    // This ensures pressureSequenceActive is set so subsequent STEAL turns are recognized as FCP/HCT
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
    if (skipRetreat) {
      console.log(`🎯 [FCP/HCT DETECTED] ${turnData.next_defensive_setup} detected after FT - setting pressure state`);
    }
    
    console.log('FreeThrowAnimationSystem: Executing inbound pass after final made free throw', {
      possession_team_id: turnData.possession_team_id,
      newOffenseSide,
      home_team_id: this.scene.simData?.home_team_id,
      next_defensive_setup: turnData.next_defensive_setup,
      pressureType,
      skipRetreat
    });
    
    await runInboundSetup({
      scene: this.scene,
      ballSprite: this.ballController.ballSprite,
      playerSprites: this.playerSprites,
      newOffenseSide: newOffenseSide,
      homeTeamId: this.scene.simData?.home_team_id,
      awayTeamId: this.scene.simData?.away_team_id,
      skipRetreat,
      pressureType,
      turnData: turnData
    });

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Inbound pass completed after final made free throw');
    }
  }

  /**
   * Handle final missed free throw - execute rebound system
   * @param {Object} turnData - Turn data
   * @param {Object} miss - Bounce result from animateBallBounceFromRim (contains grid coordinates)
   */
  async handleFinalMissedFreeThrow(turnData, miss) {
    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Final free throw missed - executing rebound system', {
        shooter_id: turnData.shooter_id,
        rebounderId: turnData.rebounderId,
        rebound_type: turnData.rebound_type,
        bounceSpot: miss?.grid
      });
    }

    // Transition to REBOUNDING state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.REBOUNDING, {
        reason: 'free_throw_missed',
        shooter_id: turnData.shooter_id
      });
    }

    // ✅ FIX: Use the bounce result from handleMissedFreeThrow instead of bouncing again
    // The ball has already bounced to the bounce spot, now players animate to it
    if (!miss || !miss.grid) {
      // Fallback: if miss wasn't passed, get it (shouldn't happen)
      const rimGridCoords = this.getRimGridCoordinates(turnData);
      miss = await this.animateBallBounceFromRim(rimGridCoords, turnData);
    }

    // Execute rebound system using existing system
    const { animateRebound } = await import('./ballManager.js');
    
    // Execute the rebound animation - ball is already at bounce spot, players animate to it
    await animateRebound({
      scene: this.scene,
      ballSprite: this.ballController.ballSprite,
      playerSprites: this.playerSprites,
      animations: [],
      rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
      ballSpot: miss.grid,
      shooterId: turnData.shooter_id,
      preserveBallPosition: true  // ✅ FIX: Ball is already at bounce spot, don't move it
    });

    // Handle defensive rebound setup if needed
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene: this.scene,
        ballSprite: this.ballController.ballSprite,
        playerSprites: this.playerSprites,
        rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
        nextPlayType: turnData.next_play_type || "HCO"
      });
    }

    if (DebugFlags.FREE_THROW_ANIMATION) {
      console.log('FreeThrowAnimationSystem: Rebound system completed after final missed free throw');
    }
  }

  /**
   * Get rim coordinates from animation data (pixel coordinates for ball animation)
   */
  getRimCoordinatesFromAnimation(turnData) {
    const animations = turnData.animations || [];
    const ballAnim = animations.find((a) => a.playerId === "ball");
    const moves = ballAnim?.movement || [];
    
    if (moves.length > 1) {
      // Get the shot step (usually the second movement)
      const shotStep = moves[1];
      if (shotStep?.coords) {
        const width = this.scene.game.config.width;
        const height = this.scene.game.config.height;
        return gridToPixels(shotStep.coords.x, shotStep.coords.y, width, height);
      }
    }
    
    // Fallback to team-based rim coordinates
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    const rimGrid = isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const width = this.scene.game.config.width;
    const height = this.scene.game.config.height;
    return gridToPixels(rimGrid.x, rimGrid.y, width, height);
  }

  /**
   * Get rim grid coordinates (for bounce system)
   */
  getRimGridCoordinates(turnData) {
    const animations = turnData.animations || [];
    const ballAnim = animations.find((a) => a.playerId === "ball");
    const moves = ballAnim?.movement || [];
    
    if (moves.length > 1) {
      // Get the shot step (usually the second movement)
      const shotStep = moves[1];
      if (shotStep?.coords) {
        return shotStep.coords; // Return grid coordinates directly
      }
    }
    
    // Fallback to team-based rim coordinates
    const isHomeTeam = turnData.offense_team_id === this.scene.simData?.home_team_id;
    return isHomeTeam ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  }

  /**
   * Get rim coordinates based on free throw context (legacy method)
   */
  getRimCoordinates(turnData) {
    // Determine which rim based on team
    const isHomeTeam = turnData.possession_team_id === this.scene.homeTeamId;
    return isHomeTeam ? this.ftConfig.homeRim : this.ftConfig.awayRim;
  }


  /**
   * Adapt backend data structure to new system format
   */
  adaptBackendData(backendData) {
    // Backend provides: attempts: ["MAKE"] or ["MISS"]
    // New system expects: actual_result: "MAKE" or "MISS"
    
    const attempts = backendData.attempts || [];
    const actualResult = attempts.length > 0 ? attempts[0] : 'MISS';
    
    // Backend provides: ftContext from annotateFreeThrowTurns
    // New system expects: ftContext with attempt/total structure
    // ✅ FIX: Do NOT set isFinal here - let determineFreeThrowContext() be the single source of truth
    // isFinal must be calculated using free_throws_remaining, not just ftIndex/ftTotal
    
    const ftContext = backendData.ftContext || {};
    const adaptedFtContext = {
      attempt: ftContext.ftIndex || 1,
      total: ftContext.ftTotal || 1,
      type: ftContext.bonusType || 'single',
      // ✅ FIX: Do not set isFinal here - it will be calculated correctly in determineFreeThrowContext()
      // based on free_throws_remaining from backend
    };
    
    return {
      ...backendData,
      actual_result: actualResult,
      ftContext: adaptedFtContext
    };
  }

  /**
   * Determine free throw context
   */
  determineFreeThrowContext(turnData) {
    const ftContext = turnData.ftContext || {};
    
    // ✅ FIX: Support both naming conventions (ftIndex/ftTotal from annotateFreeThrowTurns, attempt/total from backend)
    // annotateFreeThrowTurns sets ftIndex/ftTotal, but we were looking for attempt/total
    const attempt = ftContext.ftIndex || ftContext.attempt || 1;
    const total = ftContext.ftTotal || ftContext.total || 1;
    
    // ✅ FIX: free_throws_remaining is the AUTHORITATIVE source for determining if this is the final FT
    // free_throws_remaining is AFTER this shot, so:
    // - If free_throws_remaining > 0: More FTs remain, this is NOT final
    // - If free_throws_remaining === 0: No more FTs remain, this IS final
    // - If free_throws_remaining is undefined: Fall back to ftIndex/ftTotal (batch mode)
    let isFinal;
    if (turnData.free_throws_remaining !== undefined) {
      // Turn-by-turn mode: Use free_throws_remaining as authoritative
      isFinal = turnData.free_throws_remaining === 0;
    } else {
      // Batch mode: Fall back to ftIndex/ftTotal (legacy support)
      isFinal = (attempt >= total);
    }
    
    return {
      attempt: attempt,
      total: total,
      type: ftContext.type || 'single',
      isFinal: isFinal
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
           turnData.result_type === 'FREE_THROW' &&
           (turnData.actual_result === 'MAKE' || turnData.actual_result === 'MISS');
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
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'free_throw_error',
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
