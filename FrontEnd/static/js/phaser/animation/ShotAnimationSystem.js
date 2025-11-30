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

import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { AnimationStates } from './SimplifiedStateMachine.js';
import { DebugFlags } from '../utils/debugFlags.js';
import { gridToPixels } from '../utils/gridToPixels.js';
import { animateStep } from './animateStep.js';
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from './courtConstants.js';
import { getPlayerDuration } from './turnAnimation.js';

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
    // ✅ DEBUG: Log shot attempt immediately - track shooter and shot details
    console.log('🎬 [ShotAnimationSystem.processShot] ENTERING', {
      result_type: turnData.result_type,
      shooter_id: turnData.shooter_id,
      turn_index: turnData.index,
      hasPlayerSprites: !!this.playerSprites,
      playerSpritesCount: this.playerSprites ? Object.keys(this.playerSprites).length : 0
    });
    
    const isHCO = turnData.play_type === 'HCO' || turnData.playcall === 'HCO';
    const shooterName = this.playerSprites[turnData.shooter_id]?.name || 'unknown';
    console.log(`🏀 SHOT ATTEMPT: ${shooterName} (${turnData.shooter_id}) - Result: ${turnData.result_type} - HCO: ${isHCO}`);
    
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
    
    // ✅ MATCH playTurnAnimation EXACTLY: Initialize ball holder state
    const { initializeBallHolderState, clearBallHolder } = await import('./ballAnimationSimple.js');
    const { clearPendingOwner } = await import('./BallControllerAdapter.js');
    initializeBallHolderState(this.scene);
    
    // ✅ MATCH playTurnAnimation EXACTLY: Reset scene flags
    const fromInbound = this.scene._previousTurnWasInbound === true;
    const fromOpeningTip = this.scene._previousTurnWasOpeningTip === true;
    this.scene.passInFlight = false;
    this.scene.rebounderId = null;
    
    // ✅ MATCH playTurnAnimation EXACTLY: Clear ball state (if not from inbound/tip)
    if (!fromInbound && !fromOpeningTip) {
      clearPendingOwner(this.scene);
      clearBallHolder(this.scene);
    }
    
    const currentBallOwnerRef = { value: null };
    
    // ✅ MATCH playTurnAnimation EXACTLY: Store reference on scene
    this.scene.currentBallOwnerRef = currentBallOwnerRef;
    
    // ✅ MATCH playTurnAnimation EXACTLY: Calculate maxSteps (with same filtering)
    const maxSteps = turnData.animations && turnData.animations.length > 0
      ? Math.max(
          ...turnData.animations
            .filter(anim => anim.movement && Array.isArray(anim.movement))
            .map(anim => anim.movement.length)
        )
      : 0;
    
    // 1. Setup: Move players to step 0 positions
    await this.runSetupTween(turnData, ballSprite, currentBallOwnerRef);
    
    // ✅ MATCH playTurnAnimation EXACTLY: Update ball ownership at step 0
    const { updateBallOwnership } = await import('./BallControllerAdapter.js');
    updateBallOwnership({
      scene: this.scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites: this.playerSprites,
      stepIndex: 0,
      offenseTeamId: this.scene.offenseTeamId ?? turnData.possession_team_id,
      currentBallOwnerRef
    });
    
    // ✅ CRITICAL FIX: Match playTurnAnimation's ball attachment logic exactly
    // Determine which player owns the ball at step 0
    // BUT: Skip this if the previous turn was a shot (MAKE or MISS)
    // After a shot, the ball should remain at the rim/bounce spot until the next turn's animation moves it
    const previousTurnWasShot = this.scene._previousTurnWasShot === true;
    if (previousTurnWasShot) {
      console.log('🏀 ShotAnimationSystem: Skipping step 0 ball attachment - previous turn was a shot');
      this.scene._previousTurnWasShot = false; // Clear the flag
    }
    
    // ✅ CRITICAL FIX: If we are coming directly from an inbound or opening tip, the ball should already be attached
    // to the inbound receiver or tip winner, so we don't re-derive or re-attach at step 0.
    // This is the key difference between HCO shots (don't come from inbound) and FCP/HCT shots (come from inbound)
    let step0OwnerSprite = null;
    if (!previousTurnWasShot && !fromInbound && !fromOpeningTip) {
      for (const anim of turnData.animations) {
        if (anim.hasBallAtStep?.[0]) {
          step0OwnerSprite = this.playerSprites[anim.playerId];
          break;
        }
      }
      
      if (step0OwnerSprite) {
        const step0OwnerId = step0OwnerSprite.playerId;
        const { setBallHolderId } = await import('./ballAnimationSimple.js');
        this.ballController.attachToPlayer(step0OwnerSprite);
        currentBallOwnerRef.value = step0OwnerSprite;
        
        // ✅ MATCH playTurnAnimation EXACTLY: Also set simple ball holder ID (WIP_GOB approach)
        setBallHolderId(this.scene, step0OwnerId);
      }
    } else {
      // Coming from inbound/tip or previous was shot - ball is already attached, don't re-attach
      console.log('🏀 ShotAnimationSystem: Skipping step 0 ball attachment', {
        previousTurnWasShot,
        fromInbound,
        fromOpeningTip,
        reason: previousTurnWasShot ? 'previous turn was shot' : 
                fromInbound ? 'coming from inbound' : 
                'coming from opening tip'
      });
    }
    
    // ✅ MATCH playTurnAnimation EXACTLY: Clear inbound and opening tip flags after applying pre-step setup
    if (this.scene._previousTurnWasInbound) {
      this.scene._previousTurnWasInbound = false;
    }
    if (this.scene._previousTurnWasOpeningTip) {
      this.scene._previousTurnWasOpeningTip = false;
    }
    
    // 3. Animate step-by-step player movement
    await this.animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps);
    
    // 4. Handle shot outcome
    const isMake = turnData.result_type === 'MAKE';
    const rimCoords = this.getRimCoordinates(turnData);
    
    // ✅ DEBUG: Log the result immediately when determined
    const shooterName = this.playerSprites[turnData.shooter_id]?.name || 'unknown';
    console.log(`🏀 SHOT RESULT: ${shooterName} - ${turnData.result_type}`);
    
    // ✅ VERY LOUD LOG: Impossible to miss when a shot is made
    if (isMake) {
      console.log('🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯');
      console.log('🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯');
      console.log(`🎯🎯🎯🎯🎯 SHOT MADE BY: ${shooterName.toUpperCase()} 🎯🎯🎯🎯🎯`);
      console.log(`🎯🎯🎯🎯🎯 RESULT: ${turnData.result_type} 🎯🎯🎯🎯🎯`);
      console.log(`🎯🎯🎯🎯🎯 SHOOTER ID: ${turnData.shooter_id} 🎯🎯🎯🎯🎯`);
      console.log('🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯');
      console.log('🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯');
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
          // ✅ FIX: Removed manual ball positioning - BallController handles ball following automatically
          // When ball is attached via attachToPlayer(), it automatically follows the player
          // Manual setPosition() calls conflict with BallController's following system
          onComplete: resolve,
          onStop: resolve
        });
        if (this.scene.skipToEnd) {
          tween.stop();
        }
      }));
    }
    
    await Promise.all(promises);
  }
  
  /**
   * Animate player movement step by step
   */
  async animatePlayerMovement(turnData, ballSprite, currentBallOwnerRef, maxSteps) {
    console.log('🎬 [ShotAnimationSystem.animatePlayerMovement] ENTERING', {
      maxSteps,
      result_type: turnData.result_type,
      skipToEnd: this.scene.skipToEnd,
      hasBallSprite: !!ballSprite,
      hasTweens: !!this.scene.tweens
    });
    
    if (this.scene.skipToEnd) {
      console.log('⚠️ [ShotAnimationSystem.animatePlayerMovement] Skipping - skipToEnd is true');
      return;
    }
    
    // ✅ CRITICAL FIX: Kill all ball tweens before starting step loop
    // Lingering ball tweens from previous shots/passes can block the tween manager
    if (ballSprite && this.scene.tweens) {
      const ballActiveTweens = this.scene.tweens.getTweensOf ? this.scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        console.warn('🔧 [BALL TWEEN CLEANUP] Killing lingering ball tweens before step loop (ShotAnimationSystem)', {
          ballActiveTweensCount: ballActiveTweens.length,
          ballActiveTweenIds: ballActiveTweens.map(t => t._animateStepId || 'no-id')
        });
        this.scene.tweens.killTweensOf(ballSprite);
        // Also kill ball shadow tweens if they exist
        if (this.scene.ballShadowSprite) {
          this.scene.tweens.killTweensOf(this.scene.ballShadowSprite);
        }
      }
    }
    
    // ✅ CRITICAL FIX: For FCP/HCT skeleton animations, kill ALL player sprite tweens
    // and add a small delay to allow the tween manager to settle after runInboundSetup()
    // This fixes the race condition where skeleton animation tweens don't progress
    // This matches the cleanup in playTurnAnimation for FCP/HCT turns
    const isFCPHCT = turnData.fcp_shot === true || turnData.hct_shot === true || 
                     turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                     turnData.fcp_foul === true || turnData.hct_foul === true ||
                     this.scene.pressureSequenceActive === true;
    
    
    if (isFCPHCT && this.scene.tweens && this.playerSprites) {
      let totalPlayerTweensKilled = 0;
      const playerTweenDetails = [];
      
      // Kill tweens on all player sprites
      for (const [playerId, sprite] of Object.entries(this.playerSprites)) {
        if (sprite && this.scene.tweens.getTweensOf) {
          const playerTweens = this.scene.tweens.getTweensOf(sprite);
          if (playerTweens.length > 0) {
            totalPlayerTweensKilled += playerTweens.length;
            playerTweenDetails.push({
              playerId,
              tweenCount: playerTweens.length,
              tweenIds: playerTweens.map(t => t._animateStepId || 'no-id')
            });
            this.scene.tweens.killTweensOf(sprite);
          }
        }
      }
      
      // Log tween manager state before FCP/HCT skeleton animation
      const tweenManagerState = {
        totalTweens: this.scene.tweens.getAll ? this.scene.tweens.getAll().length : 'N/A',
        isPaused: this.scene.tweens.isPaused ? this.scene.tweens.isPaused() : 'N/A',
        timeScale: this.scene.tweens.timeScale ?? 'N/A'
      };
      
      // Add a small delay (50ms) to allow the tween manager to settle
      // This is the key fix for the race condition where skeleton animation tweens
      // are created immediately after runInboundSetup() but don't progress
      if (totalPlayerTweensKilled > 0 || tweenManagerState.totalTweens > 0) {
        await new Promise(resolve => {
          if (this.scene.time && this.scene.time.delayedCall) {
            this.scene.time.delayedCall(50, resolve);
          } else {
            setTimeout(resolve, 50);
          }
        });
      }
    }
    
    for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
      if (this.scene.skipToEnd) break;
      
      // ✅ FIX: Match playTurnAnimation - detect pass BEFORE updateBallOwnership
      // This prevents updateBallOwnership from teleporting ball during pass animations
      const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
      const passHappeningAtThisStep = !!detectPassAtStep(turnData.animations, stepIndex);
      
      // ✅ FIX: Match playTurnAnimation - skip updateBallOwnership if pass is happening
      // or if pass just completed (passInFlight is still true from previous step)
      if (!passHappeningAtThisStep && !this.scene.passInFlight) {
        this.updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex);
      } else if (this.scene.passInFlight && !passHappeningAtThisStep) {
        // Pass just completed, clear the flag now that we've skipped updateBallOwnership
        this.scene.passInFlight = false;
        // ✅ COMMENTED OUT: Pass animation logs (cluttering console)
        // console.log('🏀 [PASS ANIMATION] Cleared passInFlight after skipping updateBallOwnership');
      }
      
      const promises = [];
      let shotInfo = null;
      
      // ✅ SCALABLE FIX: Use shared pass detection utility
      // This ensures passes work for HCO shots, fouls, turnovers, etc.
      const passInfo = detectPassAtStep(turnData.animations, stepIndex);
      
      // Get offense team ID to separate offensive and defensive players
      // ✅ CONSOLIDATED: Use scene.offenseTeamId as single source of truth (kept in sync by PossessionManager)
      const offenseTeamId = this.scene.offenseTeamId ?? turnData.possession_team_id;
      
      // ✅ DEBUG: Log team ID comparison to diagnose sync issues
      if (passInfo && stepIndex === passInfo.stepIndex) {
        console.log('🔍 [PASS SYNC DEBUG] Team ID comparison (ShotAnimationSystem):', {
          stepIndex,
          offenseTeamId,
          sceneOffenseTeamId: this.scene.offenseTeamId,
          turnDataPossessionTeamId: turnData.possession_team_id,
          homeTeamId: this.scene.simData?.home_team_id,
          awayTeamId: this.scene.simData?.away_team_id,
          passInfo: {
            passerId: passInfo.passerId,
            receiverId: passInfo.receiverId,
            stepIndex: passInfo.stepIndex
          }
        });
      }
      
      const offensivePromises = [];
      const defensivePromises = [];
      let passerPromise = null;
      
      for (const anim of turnData.animations) {
        if (this.scene.skipToEnd) break;
        const sprite = this.playerSprites[anim.playerId];
        const movement = anim.movement;
        
        if (!sprite || stepIndex >= movement.length) continue;
        
        const prev = movement[stepIndex - 1];
        const curr = movement[stepIndex];
        const step = prev;
        const nextStep = curr;
        
        // ✅ FIX: Use distance-based duration calculation (matches old system)
        // This ensures consistent speeds, respects game speed settings, and matches transition animations
        const { x: targetX, y: targetY } = gridToPixels(
          nextStep.coords.x,
          nextStep.coords.y,
          this.scene.game.config.width,
          this.scene.game.config.height
        );
        const duration = getPlayerDuration(sprite, targetX, targetY);
        
        if (nextStep.action === "shoot") {
          shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        }
        
        // ✅ FIX: Match playTurnAnimation's animateStep call signature exactly
        // Pass step (prev) and nextStep (curr) separately, plus stepIndex
        // This ensures animateStep can properly calculate positions and handle actions
        const promise = animateStep({
          scene: this.scene,
          sprite,
          step: prev,  // Previous step (for position calculation)
          nextStep: curr,  // Current step (for action checking)
          duration,
          ballSprite,
          currentBallOwnerRef,
          onAction: null, // We'll handle actions separately
          stepIndex  // Pass stepIndex to identify first step
        });
        
        // ✅ FIX: Separate offensive and defensive players for synchronized pass animation
        // Determine if player is on offense or defense
        // ✅ FIX: Ensure offenseTeamId is valid before comparison, and handle case where it might be undefined
        const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
        
        // ✅ DEBUG: Log player classification for pass steps
        if (passInfo && stepIndex === passInfo.stepIndex && (anim.playerId === passInfo.passerId || anim.playerId === passInfo.receiverId)) {
          console.log('🔍 [PASS SYNC DEBUG] Player classification (ShotAnimationSystem):', {
            playerId: anim.playerId,
            spriteTeamId: sprite.team_id,
            offenseTeamId,
            isOffensivePlayer,
            isPasser: anim.playerId === passInfo.passerId,
            isReceiver: anim.playerId === passInfo.receiverId
          });
        }
        
        if (isOffensivePlayer) {
          offensivePromises.push(promise);
          // Track passer's promise separately so we can wait for it before starting pass
          if (passInfo && anim.playerId === passInfo.passerId) {
            passerPromise = promise;
          }
        } else {
          defensivePromises.push(promise);
        }
      }
      
      // ✅ FIX: Phase 1 - Start all offensive players animating, wait for passer if there's a pass
      // This maintains the existing behavior where pass doesn't start until passer reaches their spot
      // All offensive players start animating simultaneously, but we only wait for the passer
      if (passInfo && passerPromise) {
        // Wait for passer to complete before starting pass animation
        // Other offensive players continue animating in the background
        await passerPromise;
      } else if (offensivePromises.length > 0) {
        // No pass, wait for all offensive players to complete
        await Promise.all(offensivePromises);
      }
      
      // ✅ FIX: Phase 2 - Animate pass and defensive players in parallel
      // This creates the natural feel of defensive players moving while ball is in the air
      // Other offensive players (non-passer) continue animating from Phase 1
      const passAndDefensePromises = [];
      
      if (passInfo) {
        // Add pass animation to the parallel batch
        passAndDefensePromises.push(
          handlePassAnimation({
            scene: this.scene,
            passInfo,
            playerSprites: this.playerSprites
          })
        );
      }
      
      // Add all defensive player movements to the parallel batch
      passAndDefensePromises.push(...defensivePromises);
      
      // Animate pass and defensive players simultaneously
      if (passAndDefensePromises.length > 0) {
        await Promise.all(passAndDefensePromises);
      }
      
      // ✅ FIX: Wait for any remaining offensive players (non-passer) to complete
      // This ensures all offensive players finish their movements
      // Note: If there was no pass, we already waited for all offensive players above
      if (passInfo && passerPromise) {
        const remainingOffensivePromises = offensivePromises.filter(p => p !== passerPromise);
        if (remainingOffensivePromises.length > 0) {
          await Promise.all(remainingOffensivePromises);
        }
      }
      
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
   * Delegates to unified updateBallOwnership function
   */
  async updateBallOwnership(turnData, ballSprite, currentBallOwnerRef, stepIndex) {
    const { updateBallOwnership: unifiedUpdate } = await import('./BallControllerAdapter.js');
    return unifiedUpdate({
      scene: this.scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites: this.playerSprites,
      stepIndex,
      currentBallOwnerRef
    });
  }
  
  /**
   * Handle shot at a specific step
   */
  async handleShotAtStep(shotInfo, turnData) {
    const shooterSprite = this.playerSprites[shotInfo.playerId];
    const rimCoords = this.getRimCoordinates(turnData);
    const isMake = turnData.result_type === 'MAKE';
    
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Handling shot at step', {
    //   stepIndex: shotInfo.stepIndex,
    //   shooterId: shotInfo.playerId,
    //   isMake
    // });
    
    // ✅ PRIORITY 1 FIX: Use BallController lifecycle method instead of direct detach
    // This matches the pattern used in ballManager.js (line 233)
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Starting shot via lifecycle method', {
    //   shooterId: shotInfo.playerId,
    //   ballControllerState: this.ballController.getState()
    // });
    this.ballController.onShotStart({ 
      shooterId: shotInfo.playerId,
      isPutback: turnData.result_type === 'PUTBACK_MAKE' || turnData.result_type === 'PUTBACK_MISS'
    });
    // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Shot started, new state:', this.ballController.getState());
    
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

      // ✅ COMMENTED OUT: Verbose shot handling logs (cluttering console)
      // console.log('🎯 ShotAnimationSystem: Starting ball flight', {
      //   from: { x: shooterSprite.x, y: shooterSprite.y },
      //   to: rimCoords,
      //   shooterId: turnData.shooter_id
      // });

      // ✅ PRIORITY 1 FIX: BallController manages ball position and visibility automatically
      // onShotStart() already detached the ball, so we just need to ensure it's visible
      // BallController will handle positioning during the tween
      if (ballSprite) {
        ballSprite.setVisible(true);
      }

      // ==================== ANIMATE PLAYERS DURING SHOT ====================
      // Defenders releasing for fast break
      if (turnData.defense_release && turnData.defense_release.length > 0) {
        turnData.defense_release.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            const targetY = Phaser.Math.Between(15, 35);
            const targetX = Phaser.Math.Between(45, 55);
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: this.shotConfig.flightDuration,
              ease: 'Power1'
            });
          }
        });
      }
      
      // Offensive players getting back on defense
      if (turnData.offense_getback && turnData.offense_getback.length > 0) {
        const isHomeTeamShooting = turnData.offense_team === this.scene.homeTeamId;
        
        turnData.offense_getback.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            const targetY = Phaser.Math.Between(14, 36);
            // Away team shooting → x: 50-60, Home team shooting → x: 40-50
            const targetX = isHomeTeamShooting ? Phaser.Math.Between(40, 50) : Phaser.Math.Between(50, 60);
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration: this.shotConfig.flightDuration,
              ease: 'Power1'
            });
          }
        });
      }
      // ==================== END PLAYER POSITIONING ====================

      // Animate ball to rim
      const tween = this.scene.tweens.add({
        targets: ballSprite,
        x: rimCoords.x,
        y: rimCoords.y,
        duration: this.shotConfig.flightDuration,
        ease: this.shotConfig.flightEase,
        onComplete: () => {
          // Ball flight completed - no need to call endFlight since we're managing the tween ourselves
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
    // ✅ DEBUG: Log made shot with shooter details
    const shooterName = this.playerSprites[turnData.shooter_id]?.name || 'unknown';
    const isPutbackMake = turnData.result_type === 'PUTBACK_MAKE';
    console.log(`🏀 MADE SHOT: ${shooterName} - Putback: ${isPutbackMake} - next_play_type: ${turnData.next_play_type || 'UNDEFINED'}`);
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Shot made', {
        shooter_id: turnData.shooter_id,
        shot_type: turnData.shot_type
      });
    }

    // ✅ FIX: Ball is already at rim from animateBallFlight() - just hold it there
    // Match the behavior of putback makes and free throws (no repositioning)
    const ballSprite = this.ballController.ballSprite;
    if (ballSprite) {
      // Keep ball visible and hold at rim for 1 second (like putbacks/free throws)
      ballSprite.setVisible(true);
      
      // Hold ball at rim for 1 second (allows announcement to display)
      await new Promise(resolve => {
        if (this.scene.time?.delayedCall) {
          this.scene.time.delayedCall(1000, resolve);
        } else {
          setTimeout(resolve, 1000);
        }
      });
      
      // Hide ball after hold
      ballSprite.setVisible(false);
    }

    // Transition to IDLE state (end of possession)
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'shot_made',
        shooter_id: turnData.shooter_id
      });
    }

    // Ball hold already handled above (1 second), no additional delay needed
    
    // ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state
    // This matches the pattern in ballManager.js (line 626)
    this.ballController.onShotEnd();
    
    // ✅ FIX: Show announcement for ALL made shots (like Fast Break does)
    // This includes both regular makes and AND-1 situations
    if (!isPutbackMake) {
      const { showAnnouncement, showAndOneAnnouncement } = await import('../utils/announcements.js');
      const { triggerMadeShotFlash } = await import('./negativeActionEffects.js');
      const shooterInfo = this.scene.playerInfo?.[turnData.shooter_id];
      const shooterSprite = this.playerSprites[turnData.shooter_id];
      const shooterTeamId = shooterSprite?.team_id;
      
      // Handle both new nested structure (object) and old flat structure (string)
      const homeTeamField = this.scene.simData?.home_team;
      const awayTeamField = this.scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const shooterTeamName = shooterTeamId === this.scene.simData?.home_team_id ? homeTeamName : awayTeamName;
      
      const shooterPlayerData = shooterInfo ? {
        playerId: turnData.shooter_id,
        photo: shooterSprite?.photo || null,
        teamName: shooterTeamName
      } : null;
      
      const isHomeOffense = shooterTeamId === this.scene.simData?.home_team_id;
      const teamStyle = isHomeOffense ? 'home' : 'away';
      
      // Check if this is an AND-1 situation (made shot with defensive foul)
      const isAndOne = turnData.next_play_type === "FREE_THROW" && 
                       (turnData.foul_player_id || turnData.foul_player?.player_id);
      
      // Trigger green flash (full screen for regular makes, same for AND-1)
      triggerMadeShotFlash(this.scene, isAndOne);
      
      if (isAndOne) {
        // AND-1 - Use special two-row announcement (red box with shooter + fouler)
        const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
        if (foulPlayerId && shooterPlayerData) {
          const foulPlayerSprite = this.playerSprites[foulPlayerId];
          const foulPlayerTeamId = foulPlayerSprite?.team_id;
          const foulPlayerTeamName = foulPlayerTeamId === this.scene.simData?.home_team_id ? homeTeamName : awayTeamName;
          
          const foulPlayerData = {
            playerId: foulPlayerId,
            photo: foulPlayerSprite?.photo || null,
            teamName: foulPlayerTeamName
          };
          
          showAndOneAnnouncement(teamStyle, shooterPlayerData, foulPlayerData);
        } else {
          // Fallback if data missing
          showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
        }
      } else {
        // Regular made shot
        showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
      }
      
      // Wait for announcement (like Fast Break)
      await new Promise(resolve => this.scene.time.delayedCall(1000, resolve));
      
      // ✅ FIX: Only call runInboundSetup if next_play_type is BASELINE_INBOUND
      // For AND-1 situations (next_play_type === "FREE_THROW"), let the free throw system handle the transition
      // ✅ CRITICAL: Also check possession_flips flag to prevent AND-1 from flipping possession
      const shouldFlipPossession = turnData.next_play_type === "BASELINE_INBOUND" && 
                                   (turnData.possession_flips !== false);
      if (shouldFlipPossession) {
        const { runInboundSetup } = await import('./turnAnimation.js');
        // ✅ CRITICAL: After a made shot, possession flips:
        // - Team that just scored (was on offense) is now on DEFENSE
        // - Team that was on defense is now on OFFENSE
        // - newOffenseSide is the team that is NOW on offense (the team that was defending)
        // - The defensive team (team that just scored) will apply FCP/HCT pressure
        // - Backend determines FCP/HCT based on the team that just scored (now on defense)
        // - Frontend receives next_defensive_setup from backend, so we use the correct team's settings
        const newOffenseSide = isHomeOffense ? "away" : "home";
        const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
        const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
        
        await runInboundSetup({
          scene: this.scene,
          ballSprite: this.ballController.ballSprite,
          playerSprites: this.playerSprites,
          newOffenseSide: newOffenseSide,
          homeTeamId: this.scene.simData?.home_team_id,
          awayTeamId: this.scene.simData?.away_team_id,
          skipRetreat: skipRetreat,
          pressureType: pressureType
        });
        
        console.log(`🔍 MADE SHOT - Inbound setup completed for BASELINE_INBOUND`);
      }
    }
    
    // ✅ DEBUG: Log completion of made shot
    console.log(`🔍 MADE SHOT COMPLETE - next_play_type: ${turnData.next_play_type || 'UNDEFINED'}`);
  }

  /**
   * Handle missed shot
   */
  async handleMissedShot(rimCoords, turnData) {
    // ✅ DEBUG: Log missed shot with shooter details
    const shooterName = this.playerSprites[turnData.shooter_id]?.name || 'unknown';
    const rebounderName = turnData.rebounderId ? (this.playerSprites[turnData.rebounderId]?.name || 'unknown') : null;
    const isOwnRebound = turnData.rebounderId === turnData.shooter_id;
    console.log(`🏀 MISSED SHOT: ${shooterName} - Rebounder: ${rebounderName || 'none'} - Own Rebound: ${isOwnRebound}`);

    // Animate ball bounce from rim
    await this.animateBallBounce(rimCoords, turnData);
    
    // ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state before rebound
    // This matches the pattern in ballManager.js (line 626)
    // The ball is no longer in flight, so clear the state to allow attachment to rebounder
    this.ballController.onShotEnd();

    // ✅ PRIORITY 2 FIX: Add validation to ensure rebound_type is set
    // Check if this shot turn includes rebound data
    if (turnData.rebounderId && turnData.rebound_type) {
      // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
      // console.log('🎬 ShotAnimationSystem: Handling embedded rebound', {
      //   rebounderId: turnData.rebounderId,
      //   rebound_type: turnData.rebound_type
      // });
      
      // Handle the rebound within the shot turn
      await this.handleEmbeddedRebound(turnData);
    } else {
      // ✅ PRIORITY 2 FIX: Add defensive logging when rebound data is missing
      console.warn('🎬 ShotAnimationSystem: Rebound data missing, skipping embedded rebound', {
        hasRebounderId: !!turnData.rebounderId,
        hasReboundType: !!turnData.rebound_type,
        rebounderId: turnData.rebounderId,
        rebound_type: turnData.rebound_type,
        note: 'This may cause DREB/outlet pass to be skipped'
      });
      // Transition to REBOUNDING state (fallback)
      if (this.stateMachine) {
        this.stateMachine.transition(AnimationStates.REBOUNDING, {
          reason: 'shot_missed',
          shooter_id: turnData.shooter_id
        });
      }
    }
  }

  /**
   * Handle rebound that's embedded within a shot turn
   */
  async handleEmbeddedRebound(turnData) {
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Processing embedded rebound', {
    //   rebounderId: turnData.rebounderId,
    //   rebound_type: turnData.rebound_type
    // });

    // Get the rebounder sprite
    const rebounderSprite = this.playerSprites[turnData.rebounderId];
    if (!rebounderSprite) {
      console.error('ShotAnimationSystem: Rebounder sprite not found', turnData.rebounderId);
      return;
    }

    // Get the ball's current position (where it bounced)
    const ballSprite = this.ballController.ballSprite;
    let ballBounceX = 0;
    let ballBounceY = 0;
    
    if (ballSprite) {
      // Make ball visible if it was hidden
      ballSprite.setVisible(true);
      
      // Get the ball's bounce position (where it currently is)
      ballBounceX = ballSprite.x;
      ballBounceY = ballSprite.y;
      
    }

    // ✅ FIX: Animate rebounder and non-rebounders simultaneously
    // Start both animations at the same time, then wait for both to complete
    const rebounderPromise = new Promise((resolve) => {
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

    // Start non-rebounder animation at the same time
    const nonRebounderPromise = this.animatePlayerCollapse(rebounderSprite, { x: ballBounceX, y: ballBounceY }, turnData);

    // Wait for both animations to complete simultaneously
    await Promise.all([rebounderPromise, nonRebounderPromise]);

    // Determine next action based on rebound type
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Determining rebound action', {
    //   rebound_type: turnData.rebound_type,
    //   isDREB: turnData.rebound_type === 'DREB',
    //   isOREB: turnData.rebound_type === 'OREB',
    //   allKeys: Object.keys(turnData)
    // });
    
    if (turnData.rebound_type === 'DREB') {
      console.log('🎬 ShotAnimationSystem: Calling handleDefensiveRebound');
      await this.handleDefensiveRebound(rebounderSprite, turnData);
    } else if (turnData.rebound_type === 'OREB') {
      // ✅ DEBUG: Track OREB handling to see if putback is coming
      const nextTurn = this.scene.simData?.turns?.[(this.scene.currentTurn || 0) + 1];
      const nextNextTurn = this.scene.simData?.turns?.[(this.scene.currentTurn || 0) + 2];
      console.log('🔍 [OREB HANDLING DEBUG]', {
        turnIndex: this.scene.currentTurn,
        rebounderId: turnData.rebounderId,
        nextTurnResult: nextTurn?.result_type || null,
        nextNextTurnResult: nextNextTurn?.result_type || null,
        willSeePutback: nextTurn?.result_type === 'PUTBACK_MAKE' || nextTurn?.result_type === 'PUTBACK_MISS',
        willSeePutbackAfterOREB: (nextTurn?.result_type === 'OREB' || nextTurn?.result_type === 'OREB_KICKOUT') && 
                                  (nextNextTurn?.result_type === 'PUTBACK_MAKE' || nextNextTurn?.result_type === 'PUTBACK_MISS')
      });
      console.log('🎬 ShotAnimationSystem: Calling handleOffensiveRebound');
      await this.handleOffensiveRebound(rebounderSprite, turnData);
    } else {
      console.log('🎬 ShotAnimationSystem: Unknown rebound type, skipping', {
        rebound_type: turnData.rebound_type
      });
    }

    // Transition to POSSESSION state
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.POSSESSION, {
        reason: 'rebound_complete',
        rebounder_id: turnData.rebounderId,
        rebound_type: turnData.rebound_type
      });
    }
  }

  /**
   * Animate players collapsing toward rebound spot
   * NEW: Only animate players who were rebounders (not those who released/got back)
   */
  async animatePlayerCollapse(rebounderSprite, ballBounceCoords, turnData) {
    return new Promise((resolve) => {
      const collapsePromises = [];
      
      // Get lists of players involved in rebounding
      const offense_rebounders = turnData.offense_rebounders || [];
      const defense_rebounders = turnData.defense_rebounders || [];
      const all_rebounders = [...offense_rebounders, ...defense_rebounders];
      
      // ✅ FIX: Convert ball bounce coords (pixels) to grid coordinates correctly
      // gridToPixels uses: pixelY = ((50 - gridY) / 50) * height
      // So reverse: gridY = 50 - (pixelY / height) * 50
      const bounceGridX = Math.round((ballBounceCoords.x / this.scene.game.config.width) * 100);
      const bounceGridY = 50 - Math.round((ballBounceCoords.y / this.scene.game.config.height) * 50);
      
      // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
      // console.log('🎬 ShotAnimationSystem: Animating non-rebounders to ball bounce', {
      //   ballBounceCoordsPixels: { x: ballBounceCoords.x, y: ballBounceCoords.y },
      //   bounceGrid: { x: bounceGridX, y: bounceGridY },
      //   totalRebounders: all_rebounders.length,
      //   rebounderId: turnData.rebounderId,
      //   sceneDimensions: { width: this.scene.game.config.width, height: this.scene.game.config.height }
      // });
      
      // Animate each player who was attempting the rebound (but didn't get it)
      all_rebounders.forEach(playerId => {
        if (playerId === turnData.rebounderId) return; // Skip actual rebounder (handled separately)
        
        const playerSprite = this.playerSprites[playerId];
        if (!playerSprite) return;
        
        // Position near ball bounce: ±6y, ±4x (can stack)
        const offsetY = Phaser.Math.Between(-6, 6);
        const offsetX = Phaser.Math.Between(-4, 4);
        
        // Apply offsets and clamp to bounds
        let targetGridX = bounceGridX + offsetX;
        let targetGridY = bounceGridY + offsetY;
        
        // Clamp to court bounds (0-100 x, 0-50 y)
        targetGridX = Math.max(0, Math.min(100, targetGridX));
        targetGridY = Math.max(0, Math.min(50, targetGridY));
        
        const targetPixel = gridToPixels(targetGridX, targetGridY, this.scene.game.config.width, this.scene.game.config.height);
        
        const collapsePromise = new Promise((playerResolve) => {
          this.scene.tweens.add({
            targets: playerSprite,
            x: targetPixel.x,
            y: targetPixel.y,
            duration: 400,
            ease: 'Power2',
            onComplete: () => playerResolve()
          });
        });
        
        collapsePromises.push(collapsePromise);
      });
      
      // Wait for all collapse animations to complete
      Promise.all(collapsePromises).then(() => {
        resolve();
      });
    });
  }

  /**
   * Animate individual player to rebound spot (within 10 grid spots of ball)
   */
  async animatePlayerToReboundSpot(playerSprite, ballBounceCoords, bounceGridX, bounceGridY) {
    return new Promise((resolve) => {
      // Generate random position within 10 grid spots of the ball bounce
      const maxDistance = 10;
      const angle = Math.random() * 2 * Math.PI;
      const distance = Math.random() * maxDistance;
      
      const targetGridX = bounceGridX + Math.cos(angle) * distance;
      const targetGridY = bounceGridY + Math.sin(angle) * distance;
      
      // Convert back to pixel coordinates
      const targetX = targetGridX * (this.scene.game.config.width / 100);
      const targetY = targetGridY * (this.scene.game.config.height / 100);
      
      // Ensure target is within court bounds
      const courtWidth = this.scene.game.config.width;
      const courtHeight = this.scene.game.config.height;
      const clampedX = Math.max(20, Math.min(courtWidth - 20, targetX));
      const clampedY = Math.max(20, Math.min(courtHeight - 20, targetY));
      
      console.log('🎬 ShotAnimationSystem: Player moving to rebound spot', {
        playerId: playerSprite.playerId,
        from: { x: playerSprite.x, y: playerSprite.y },
        to: { x: clampedX, y: clampedY },
        ballSpot: { x: ballBounceCoords.x, y: ballBounceCoords.y }
      });
      
      // Animate player movement
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: clampedX,
        y: clampedY,
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
    // ✅ PRIORITY 2 FIX: Enhanced logging to diagnose missing next_play_type
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Handling defensive rebound', {
    //   rebounderId: turnData.rebounderId,
    //   next_play_type: turnData.next_play_type,
    //   rebound_type: turnData.rebound_type,
    //   hasNextPlayType: !!turnData.next_play_type,
    //   turnDataKeys: Object.keys(turnData),
    //   fullTurnData: turnData // Log full object to see what's actually present
    // });
    
    // ✅ PRIORITY 2 FIX: Validate next_play_type is present (no fallback - must be correct)
    if (!turnData.next_play_type) {
      // Diagnostic: Check if next_play_type is on the next turn (shouldn't be, but let's check)
      const currentTurnIndex = this.scene.currentTurn || 0;
      const nextTurn = this.scene.simData?.turns?.[currentTurnIndex + 1];
      
      console.error('❌ ShotAnimationSystem: next_play_type is missing from turnData!', {
        rebounderId: turnData.rebounderId,
        rebound_type: turnData.rebound_type,
        currentTurnIndex,
        currentTurnResultType: turnData.result_type,
        nextTurnResultType: nextTurn?.result_type,
        nextTurnNextPlayType: nextTurn?.next_play_type,
        sceneOffensiveState: this.scene.gameState?.offensive_state,
        turnData: turnData,
        note: 'This should come from backend on the MISS turn - investigate why it is missing'
      });
      
      // Don't proceed with outlet pass if we don't know what comes next
      // This will help us identify the root cause
      // The backend should set next_play_type on MISS turns with embedded rebounds (turn_manager.py line 1370)
      return;
    }
    
    const nextPlayType = turnData.next_play_type;
    
    // Use the same defensive rebound setup for HCO, HCT, and FCP
    // Fast breaks handle outlet in their own turn
    if (nextPlayType === 'HCO' || nextPlayType === 'HCT' || nextPlayType === 'FCP') {
      console.log(`🎬 ShotAnimationSystem: Defensive rebound leads to ${nextPlayType} - using runDefensiveReboundSetup`);
      
      try {
        // Import and use the same function that works for free throws
        const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
        // ✅ CRITICAL FIX: Pass turnData so runDefensiveReboundSetup can detect outlet pass from animation data
        await runDefensiveReboundSetup({
          scene: this.scene,
          ballSprite: this.ballController.ballSprite,
          playerSprites: this.playerSprites,
          rebounderId: turnData.rebounderId,
          nextPlayType: nextPlayType,
          turnData: turnData // ✅ FIX: Pass turnData to enable outlet pass detection from animation data
        });
        console.log('✅ ShotAnimationSystem: runDefensiveReboundSetup completed successfully');
      } catch (error) {
        console.error('❌ ShotAnimationSystem: runDefensiveReboundSetup failed', error);
        throw error; // Re-throw to trigger fallback
      }
    } else if (nextPlayType === 'FAST_BREAK') {
      // ✅ FIX: Fast Break outlet passes are handled in the Fast Break sequence itself
      // But we should still log that we're skipping outlet pass here
      console.log('🎬 ShotAnimationSystem: Defensive rebound leads to FAST_BREAK - outlet pass handled in Fast Break sequence', {
        rebounderId: turnData.rebounderId,
        note: 'Fast Break sequence (fastBreak.js) will handle outlet pass in animateOutletPhase()'
      });
    } else {
      // ✅ PRIORITY 2 FIX: Add defensive logging for skipped outlet pass
      console.warn('🎬 ShotAnimationSystem: Defensive rebound outlet pass skipped', {
        nextPlayType: nextPlayType,
        rebounderId: turnData.rebounderId,
        reason: 'next_play_type is not HCO, HCT, FCP, or FAST_BREAK',
        note: 'Unknown next play type - outlet pass may be skipped'
      });
      // Handle other cases if needed
    }
  }

  /**
   * Handle offensive rebound
   */
  async handleOffensiveRebound(rebounderSprite, turnData) {
    // ✅ DEBUG: Check what turns are coming next
    const currentTurnIndex = this.scene.currentTurn || 0;
    const nextTurn = this.scene.simData?.turns?.[currentTurnIndex + 1];
    const nextNextTurn = this.scene.simData?.turns?.[currentTurnIndex + 2];
    
    console.log('🎬 ShotAnimationSystem: Handling offensive rebound', {
      rebounderId: turnData.rebounderId,
      putback_attempt: turnData.putback_attempt,
      events: turnData.events,
      currentTurnIndex,
      nextTurnResult: nextTurn?.result_type || null,
      nextNextTurnResult: nextNextTurn?.result_type || null,
      willSeePutbackTurn: nextTurn?.result_type === 'PUTBACK_MAKE' || nextTurn?.result_type === 'PUTBACK_MISS',
      willSeeOREBTurn: nextTurn?.result_type === 'OREB' || nextTurn?.result_type === 'OREB_KICKOUT'
    });
    
    try {
      // TEMPORARY: Force all offensive rebounds to be putback attempts for testing
      console.log('🎬 ShotAnimationSystem: TEMPORARY - Forcing all offensive rebounds to be putback attempts');
      await this.executePutbackAttempt(rebounderSprite, turnData);
      console.log('🎬 ShotAnimationSystem: executePutbackAttempt completed successfully');
      
      // ✅ DEBUG: After putback attempt, check if we should expect a PUTBACK_MAKE turn
      const afterPutbackNextTurn = this.scene.simData?.turns?.[currentTurnIndex + 1];
      console.log('🔍 [AFTER PUTBACK ATTEMPT]', {
        currentTurnIndex,
        nextTurnResult: afterPutbackNextTurn?.result_type || null,
        expectingPutbackTurn: afterPutbackNextTurn?.result_type === 'PUTBACK_MAKE' || afterPutbackNextTurn?.result_type === 'PUTBACK_MISS'
      });
    } catch (error) {
      console.error('🎬 ShotAnimationSystem: executePutbackAttempt failed', error);
      throw error;
    }
    
    // Original logic (commented out for testing):
    // const isPutbackAttempt = this.isPutbackAttempt(turnData);
    // if (isPutbackAttempt) {
    //   console.log('🎬 ShotAnimationSystem: Executing putback attempt');
    //   await this.executePutbackAttempt(rebounderSprite, turnData);
    // } else {
    //   console.log('🎬 ShotAnimationSystem: Executing kickout pass');
    //   await this.executeKickoutPass(rebounderSprite, turnData);
    // }
  }

  /**
   * Check if this is a putback attempt
   */
  isPutbackAttempt(turnData) {
    // Check for putback attempt flag
    if (turnData.putback_attempt === true) {
      return true;
    }
    
    // Check for PUTBACK_ATTEMPT event
    if (turnData.events && Array.isArray(turnData.events)) {
      return turnData.events.some(event => event.event_type === 'PUTBACK_ATTEMPT');
    }
    
    return false;
  }

  /**
   * Execute putback attempt using standard shot animation
   */
  async executePutbackAttempt(rebounderSprite, turnData) {
    console.log('🎬 ShotAnimationSystem: Executing putback attempt using OLD SYSTEM');
    
    // SIMPLE APPROACH: Use the old system that already works for regular shots
    const { playTurnAnimation } = await import('./turnAnimation.js');
    
    // Create a simple turn data object for the putback shot
    const putbackTurnData = {
      result_type: 'MISS', // Default to MISS for putbacks
      shooter: rebounderSprite.playerName || 'Unknown',
      shooter_id: turnData.rebounderId,
      ball_handler: rebounderSprite.playerName || 'Unknown',
      shot_type: 'putback',
      animations: [{
        type: 'shot',
        duration: 1000,
        result: 'MISS'
      }]
    };
    
    console.log('🎬 ShotAnimationSystem: Using old system for putback', putbackTurnData);
    
    // Use the old system - it already works perfectly for regular shots
    await playTurnAnimation({
      scene: this.scene,
      simData: { turns: [] }, // Not needed for single turn
      playerSprites: this.playerSprites,
      turnData: putbackTurnData,
      ballSprite: this.ballController.ballSprite,
      onAction: () => {} // No callback needed
    });
    
    console.log('🎬 ShotAnimationSystem: Putback completed using old system');
    return { success: true };
  }

  /**
   * Execute kickout pass
   */
  async executeKickoutPass(rebounderSprite, turnData) {
    console.log('🎬 ShotAnimationSystem: Executing kickout pass');
    
    // Find the kickout event data
    const kickoutEvent = turnData.events?.find(event => event.event_type === 'KICKOUT_RESET');
    if (!kickoutEvent) {
      console.warn('🎬 ShotAnimationSystem: No kickout event found');
      return;
    }
    
    // Import and use the existing kickout animation function
    const { animateKickoutReset } = await import('./ballManager.js');
    
    // Execute kickout pass
    await animateKickoutReset(
      this.scene,
      this.ballController.ballSprite,
      turnData.rebounderId,
      kickoutEvent.pgId,
      kickoutEvent.pass
    );
    
    console.log('🎬 ShotAnimationSystem: Kickout pass completed');
    
    // The animateKickoutReset function already handles:
    // - Pass from rebounder to PG
    // - Ball attachment to PG
    // - State transition to HalfCourt
    // - HCO re-entry will be handled by the next turn
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
      // ✅ PRIORITY 1 FIX: Use lifecycle method for pass instead of direct detach
      // This matches the pattern used elsewhere in the codebase
      this.ballController.onPassStart({ 
        passerId: passerSprite.playerId,
        receiverId: receiverSprite.playerId
      });
      
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
          // ✅ PRIORITY 1 FIX: Use lifecycle method to complete pass
          // This matches the pattern in ballTween.js (line 437)
          this.ballController.onPassEnd(receiverSprite, { reason: 'outlet_pass' });
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
   * Calculate bounce coordinates with realistic variance
   */
  calculateBounceCoords(rimCoords, turnData) {
    // Get shooter sprite to determine which basket
    const shooterSprite = this.getShooterSprite(turnData);
    const isHomeTeam = shooterSprite?.team === 'home';
    
    // Convert rim coords back to grid for calculations
    const rimGridX = Math.round(rimCoords.x / (this.scene.game.config.width / 100));
    const rimGridY = Math.round(rimCoords.y / (this.scene.game.config.height / 100));
    
    // Y variance: -6 to +6 from basket y coord
    const yVariance = (Math.random() - 0.5) * 12; // -6 to +6
    const bounceGridY = rimGridY + yVariance;
    
    // X variance: 1-9 from basket x coord
    // +1 to +9 for away team basket, -1 to -9 for home team basket
    const xVariance = Math.random() * 9 + 1; // 1 to 9
    const bounceGridX = isHomeTeam ? rimGridX - xVariance : rimGridX + xVariance;
    
    // Convert back to pixel coordinates
    const bounceX = bounceGridX * (this.scene.game.config.width / 100);
    const bounceY = bounceGridY * (this.scene.game.config.height / 100);
    
    // ✅ COMMENTED OUT: Verbose bounce calculation logs (cluttering console)
    // console.log('🎯 ShotAnimationSystem: Bounce variance calculation', {
    //   rimGrid: { x: rimGridX, y: rimGridY },
    //   isHomeTeam,
    //   xVariance,
    //   yVariance,
    //   bounceGrid: { x: bounceGridX, y: bounceGridY },
    //   bouncePixels: { x: bounceX, y: bounceY }
    // });

    return { x: bounceX, y: bounceY };
  }

  /**
   * Get shooter sprite
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
    
    const sprite = this.playerSprites[shooterId] || null;
    return sprite;
  }

  findPlayerIdByName(playerName) {
    if (!playerName) return null;
    
    // Check home roster
    const homeRoster = this.gameStore.getHomeRoster();
    if (homeRoster && homeRoster.players) {
      for (const player of homeRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id || player.id;
        }
      }
    }
    
    // Check away roster
    const awayRoster = this.gameStore.getAwayRoster();
    if (awayRoster && awayRoster.players) {
      for (const player of awayRoster.players) {
        if (player.name === playerName) {
          return player._id || player.playerId || player.player_id || player.id;
        }
      }
    }
    
    return null;
  }

  /**
   * Get rim coordinates based on shot context (converted to pixels)
   */
  getRimCoordinates(turnData) {
    // Get shooter sprite to determine team
    const shooterSprite = this.getShooterSprite(turnData);
    
    // Determine which rim based on shooter's team
    // Home team shoots at HOME_RIM_COORDS (x: 91, y: 25)
    // Away team shoots at AWAY_RIM_COORDS (x: 9, y: 25)
    const isHomeTeam = shooterSprite?.team === 'home';
    let gridRimCoords = isHomeTeam ? this.shotConfig.homeRim : this.shotConfig.awayRim;
    
    // ✅ FIX: Adjust rim position for made shots (1 grid unit closer to shooter)
    // This matches the adjustment in ballManager.js and fastBreak.js
    // Home team (shoots at x=91): reduce by 1 → 90
    // Away team (shoots at x=9): increase by 1 → 10
    const isMake = turnData.result_type === 'MAKE' || turnData.result_type === 'PUTBACK_MAKE';
    if (isMake) {
      gridRimCoords = {
        ...gridRimCoords,
        x: isHomeTeam ? gridRimCoords.x - 1 : gridRimCoords.x + 1
      };
    }
    
    // Convert grid coordinates to pixel coordinates (like the old system does)
    const pixelRimCoords = gridToPixels(
      gridRimCoords.x,
      gridRimCoords.y,
      this.scene.game.config.width,
      this.scene.game.config.height
    );
    
    // Return pixel coordinates for rim
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
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'shot_error',
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
