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
    // Shot processing (debug log removed)
    if (false) console.log('[Shot Debug]', {
      result_type: turnData.result_type,
      shooter_id: turnData.shooter_id,
      turn_index: turnData.index,
      hasPlayerSprites: !!this.playerSprites,
      playerSpritesCount: this.playerSprites ? Object.keys(this.playerSprites).length : 0
    });
    
    const isHCO = turnData.play_type === 'HCO' || turnData.playcall === 'HCO';
    // ✅ REMOVED: Shot attempt logging (cluttering console)
    
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
      // ✅ REMOVED: Step 0 ball attachment logging (cluttering console)
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
    
    // 🔍 STATE COMPARISON: Log tween manager and scene state before MAKE vs MISS handling
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        const paused = typeof this.scene.tweens.isPaused === 'function'
          ? this.scene.tweens.isPaused()
          : 'N/A';
        const timeScale = this.scene.tweens.timeScale || 'N/A';
        return { total, paused, timeScale };
      } catch (error) {
        return { error: error.message };
      }
    };
    
    const getBallControllerState = () => {
      if (!this.ballController) return null;
      return {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight,
        currentOwner: this.ballController.currentOwner?.playerId || null
      };
    };
    
    const getSceneFlags = () => {
      return {
        skipToEnd: this.scene.skipToEnd,
        _getBackTweens: this._getBackTweens ? this._getBackTweens.length : 0,
        _previousTurnWasInbound: this.scene._previousTurnWasInbound,
        _previousTurnWasOpeningTip: this.scene._previousTurnWasOpeningTip
      };
    };
    
    console.log(`🔍 [STATE COMPARISON] Before ${isMake ? 'MAKE' : 'MISS'} handling`, {
      resultType: turnData.result_type,
      tweenManager: getTweenManagerState(),
      ballController: getBallControllerState(),
      sceneFlags: getSceneFlags(),
      hasRebounderId: !!turnData.rebounderId,
      hasReboundType: !!turnData.rebound_type
    });
    
    // Execute make or miss handling
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
    
    // getPlayerDuration is already imported at top of file
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
      
      // ✅ FIX: Use distance-based duration for consistent speed (matches step animations)
      // This ensures smooth transitions between turns and consistent speeds
      const duration = getPlayerDuration(sprite, x, y);
      
      promises.push(new Promise((resolve) => {
        const tween = this.scene.tweens.add({
          targets: [sprite],
          x,
          y,
          duration,
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
    if (false) console.log('[Player Movement Debug]', {
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
    
    // ✅ REMOVED: Special FCP/HCT handling - FCP/HCT now uses exact same path as HCO
    // Skeletons are in same format, so no special handling needed
    
    // ✅ SS&S FIX: Resolve offenseTeamId once at turn start and classify all players
    // This ensures consistent player classification throughout the turn
    const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
    const offenseTeamId = resolveOffenseTeamId({
      scene: this.scene,
      turnData,
      playerSprites: this.playerSprites,
      passInfo: null // No passInfo at turn start, will be detected per step
    });
    
    // ✅ SS&S: Classify all players once at turn start
    const playerClassifications = {}; // Map: playerId -> 'offense' | 'defense'
    let offensiveCount = 0;
    let defensiveCount = 0;
    
    for (const anim of turnData.animations) {
      const sprite = this.playerSprites[anim.playerId];
      if (!sprite) continue;
      
      const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
      playerClassifications[anim.playerId] = isOffensivePlayer ? 'offense' : 'defense';
      
      if (isOffensivePlayer) {
        offensiveCount++;
      } else {
        defensiveCount++;
      }
    }
    
    // ✅ VALIDATION: Ensure we have exactly 5 offensive and 5 defensive players
    if (offensiveCount !== 5 || defensiveCount !== 5) {
      console.warn('⚠️ [PLAYER CLASSIFICATION] Expected 5 offensive and 5 defensive players, but got:', {
        offensiveCount,
        defensiveCount,
        offenseTeamId,
        turnDataId: turnData?.id,
        resultType: turnData?.result_type,
        totalAnimations: turnData.animations?.length
      });
    }
    
    for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
      if (this.scene.skipToEnd) break;
      
      // Trigger lean meter animation at middle step
      if (this.scene._leanScoreToAnimate !== null && 
          this.scene._leanAnimationStep === stepIndex && 
          !this.scene._leanAnimationTriggered) {
        // ✅ REMOVED: LEAN animation logging (cluttering console)
        const { animateLeanMeter } = await import('../ui/playcallCenter.js');
        animateLeanMeter(this.scene._leanScoreToAnimate);
        this.scene._leanAnimationTriggered = true;
      } else if (this.scene._leanScoreToAnimate !== null && stepIndex === this.scene._leanAnimationStep) {
        // ✅ REMOVED: LEAN animation mismatch logging (cluttering console)
      }
      
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
      
      // ✅ COMMENTED OUT: Starting pass detection log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Starting pass detection`, {
      //   turnId: turnData?.id?.substring(0, 8),
      //   totalAnimations: turnData.animations?.length,
      //   maxSteps: maxSteps
      // });
      
      // ✅ COMMENTED OUT: Movement array structure log (cluttering console)
      // const movementArrayInfo = turnData.animations.map(anim => ({
      //   playerId: anim.playerId?.substring(0, 8) || 'unknown',
      //   movementLength: anim.movement?.length || 0,
      //   hasStep: stepIndex < (anim.movement?.length || 0),
      //   stepAction: stepIndex < (anim.movement?.length || 0) ? anim.movement[stepIndex]?.action : 'N/A',
      //   stepTimestamp: stepIndex < (anim.movement?.length || 0) ? anim.movement[stepIndex]?.timestamp : 'N/A'
      // }));
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Movement array structure`, movementArrayInfo);
      
      // ✅ SCALABLE FIX: Use shared pass detection utility
      // This ensures passes work for HCO shots, fouls, turnovers, etc.
      const passInfo = detectPassAtStep(turnData.animations, stepIndex);
      
      // ✅ COMMENTED OUT: Pass detection result log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Pass detection result`, {
      //   passInfo: passInfo ? {
      //     passer: passInfo.passerId?.substring(0, 8),
      //     receiver: passInfo.receiverId?.substring(0, 8),
      //     stepIndex: passInfo.stepIndex
      //   } : null,
      //   passHappeningAtThisStep: !!passInfo
      // });
      
      // ✅ SS&S: Use pre-classified player roles (determined at turn start)
      // No need to re-resolve offenseTeamId or re-classify players per step
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
        
        // 🔍 TIMING: Track when animateStep() is called (tween starts immediately when called)
        const beforeAnimateStep = performance.now();
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
        const afterAnimateStep = performance.now();
        
        // ✅ SS&S: Use pre-classified player role (determined at turn start)
        // This ensures consistent classification throughout the turn
        const playerRole = playerClassifications[anim.playerId] || 'defense'; // Default to defense if not found
        const isOffensivePlayer = playerRole === 'offense';
        
        if (isOffensivePlayer) {
          offensivePromises.push(promise);
          // Track passer's promise separately so we can wait for it before starting pass
          if (passInfo && anim.playerId === passInfo.passerId) {
            passerPromise = promise;
          }
        } else {
          // ✅ COMMENTED OUT: Timing logs (didn't solve the issue)
          // const defensiveTweenStartTime = performance.now();
          // console.log(`⏱️ [TIMING] Step ${stepIndex}: Defensive tween CREATED and STARTED for ${anim.playerId?.substring(0, 8)}`, {
          //   playerId: anim.playerId?.substring(0, 8),
          //   animateStepCallDuration: afterAnimateStep - beforeAnimateStep,
          //   tweenStartTime: defensiveTweenStartTime,
          //   note: 'Tween starts immediately when animateStep() is called, not when Phase 2 begins'
          // });
          defensivePromises.push({
            promise,
            // startTime: defensiveTweenStartTime,
            playerId: anim.playerId
          });
        }
      }
      
      // ✅ COMMENTED OUT: Defensive animation decision log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Defensive animation decision`, {
      //   hasPassInfo: !!passInfo,
      //   defensivePromisesCount: defensivePromises.length,
      //   willStartInPhase2: true // ShotAnimationSystem always starts defenders in Phase 2
      // });
      
      // ✅ FIX: Phase 1 - Start all offensive players animating, wait for passer if there's a pass
      // This maintains the existing behavior where pass doesn't start until passer reaches their spot
      // All offensive players start animating simultaneously, but we only wait for the passer
      const phase1StartTime = performance.now();
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
      const phase2StartTime = performance.now();
      
      // ✅ COMMENTED OUT: Phase 2 start log (cluttering console)
      // console.log(`🔍 [SHOT ANIM] Step ${stepIndex}: Starting Phase 2`, {
      //   hasPassInfo: !!passInfo,
      //   defensivePromisesCount: defensivePromises.length,
      //   phase1Duration: phase2StartTime - phase1StartTime
      // });
      
      if (passInfo) {
        // Add pass animation to the parallel batch
        const passPromise = handlePassAnimation({
          scene: this.scene,
          passInfo,
          playerSprites: this.playerSprites
        });
        
        passAndDefensePromises.push(passPromise);
        // ✅ COMMENTED OUT: Pass animation start log (cluttering console)
        // console.log(`✅ [SHOT ANIM] Step ${stepIndex}: Starting pass animation + defensive animations in parallel`);
      } else {
        // ✅ COMMENTED OUT: No pass log (cluttering console)
        // console.log(`⚠️ [SHOT ANIM] Step ${stepIndex}: No pass - starting defensive animations in Phase 2`);
      }
      
      // Add all defensive player movements to the parallel batch
      // Extract promises from defensivePromises array (which now contains objects with {promise, playerId})
      const defensivePromiseArray = defensivePromises.map(dp => dp.promise);
      passAndDefensePromises.push(...defensivePromiseArray);
      // ✅ COMMENTED OUT: Defensive animations added log (cluttering console)
      // console.log(`✅ [SHOT ANIM] Step ${stepIndex}: Added ${defensivePromiseArray.length} defensive animations to Phase 2`);
      
      // ✅ COMMENTED OUT: Timing logs (didn't solve the issue)
      // if (defensivePromises.length > 0) {
      //   const earliestDefensiveStart = Math.min(...defensivePromises.map(dp => dp.startTime));
      //   const timeDiff = phase2StartTime - earliestDefensiveStart;
      //   console.log(`⏱️ [TIMING] Step ${stepIndex}: Time between defensive tween start and Phase 2 start`, {
      //     earliestDefensiveStart,
      //     phase2StartTime,
      //     timeDifferenceMs: timeDiff,
      //     note: timeDiff > 0 ? 'Defensive tweens started BEFORE Phase 2' : 'Defensive tweens started AFTER Phase 2 (unexpected)'
      //   });
      // }
      // 
      // const beforePromiseAll = performance.now();
      // console.log(`⏱️ [TIMING] Step ${stepIndex}: Promise.all() about to start waiting for pass + defensive animations`, {
      //   passAndDefensePromisesCount: passAndDefensePromises.length,
      //   hasPass: !!passInfo,
      //   defensiveCount: defensivePromiseArray.length
      // });
      
      // Animate pass and defensive players simultaneously
      if (passAndDefensePromises.length > 0) {
        await Promise.all(passAndDefensePromises);
      }
      
      // ✅ COMMENTED OUT: Timing logs (didn't solve the issue)
      // const afterPromiseAll = performance.now();
      // console.log(`⏱️ [TIMING] Step ${stepIndex}: Promise.all() completed`, {
      //   waitDuration: afterPromiseAll - beforePromiseAll
      // });
      
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
    
    // ✅ REMOVED: Player movement completed logging (cluttering console)
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
      // getPlayerDuration is already imported at top of file
      
      // Store get-back player tweens so we can stop them early if needed
      this._getBackTweens = [];
      
      // Defenders releasing for fast break
      if (turnData.defense_release && turnData.defense_release.length > 0) {
        turnData.defense_release.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            let targetX, targetY;
            
            // ✅ Backend calculates and stores release coordinates in defense_release_coords
            // Use backend coordinates (SS&S: backend is single source of truth)
            if (turnData.defense_release_coords && turnData.defense_release_coords[playerId]) {
              const storedCoords = turnData.defense_release_coords[playerId];
              targetX = storedCoords.x;
              targetY = storedCoords.y;
            } else {
              // Fallback: Use safe defaults if backend coordinates missing (shouldn't happen)
              console.error('⚠️ [DEFENSE RELEASE] Missing backend coordinates, using safe defaults', {
                playerId,
                hasDefenseReleaseCoords: !!turnData.defense_release_coords
              });
              targetX = 50; // Safe default: center court
              targetY = 25; // Safe default: mid-court
            }
            
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            // ✅ FIX: Use distance-based duration for consistent speed
            const duration = getPlayerDuration(sprite, targetPixel.x, targetPixel.y);
            
            this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration,
              ease: 'Linear' // Match other player movements
            });
          }
        });
      }
      
      // Offensive players getting back on defense
      if (turnData.offense_getback && turnData.offense_getback.length > 0) {
        turnData.offense_getback.forEach(playerId => {
          const sprite = this.playerSprites[playerId];
          if (sprite) {
            // ✅ SS&S: Use stored coordinates from backend (single source of truth)
            // Backend calculates and stores get-back coordinates in offense_getback_coords
            let targetX, targetY;
            if (turnData.offense_getback_coords && turnData.offense_getback_coords[playerId]) {
              // Use stored coordinates from backend
              const storedCoords = turnData.offense_getback_coords[playerId];
              targetX = storedCoords.x;
              targetY = storedCoords.y;
            } else {
              // Fallback: Use safe defaults if backend coordinates missing (shouldn't happen)
              console.error('⚠️ [OFFENSE GET BACK] Missing backend coordinates, using safe defaults', {
                playerId,
                hasOffenseGetbackCoords: !!turnData.offense_getback_coords
              });
              targetX = 50; // Safe default: center court
              targetY = 25; // Safe default: mid-court
            }
            
            const targetPixel = gridToPixels(targetX, targetY, this.scene.game.config.width, this.scene.game.config.height);
            
            // ✅ FIX: Use distance-based duration for consistent speed
            const duration = getPlayerDuration(sprite, targetPixel.x, targetPixel.y);
            
            const tween = this.scene.tweens.add({
              targets: sprite,
              x: targetPixel.x,
              y: targetPixel.y,
              duration,
              ease: 'Linear' // Match other player movements
            });
            
            // Store tween reference for early termination
            this._getBackTweens.push(tween);
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
    // ✅ REMOVED: Made shot logging (cluttering console)
    const isPutbackMake = turnData.result_type === 'PUTBACK_MAKE';
    
    // 🔍 STATE COMPARISON: Log state at start of handleMadeShot
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        return { total };
      } catch (error) {
        return { error: error.message };
      }
    };
    console.log(`🔍 [MAKE HANDLER] Start`, {
      _getBackTweensCount: this._getBackTweens ? this._getBackTweens.length : 0,
      tweenManager: getTweenManagerState(),
      ballControllerState: this.ballController ? {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight
      } : null
    });
    
    if (DebugFlags.SHOT_ANIMATION) {
      console.log('ShotAnimationSystem: Shot made', {
        shooter_id: turnData.shooter_id,
        shot_type: turnData.shot_type
      });
    }

    // ✅ FIX: Ball is already at rim from animateBallFlight() - just hold it there
    // Match the behavior of putback makes and free throws (no repositioning)
    const ballSprite = this.ballController.ballSprite;
    
    // Determine rim hold duration: 1 second for HCO, 2 seconds for fast break
    const isFastBreak = turnData.fast_break === true;
    const rimHoldDuration = isFastBreak ? 2000 : 1000;
    
    if (ballSprite) {
      // Keep ball visible and hold at rim
      ballSprite.setVisible(true);
      
      // Hold ball at rim (allows announcement to display)
      await new Promise(resolve => {
        if (this.scene.time?.delayedCall) {
          this.scene.time.delayedCall(rimHoldDuration, resolve);
        } else {
          setTimeout(resolve, rimHoldDuration);
        }
      });
      
      // ✅ FIX: Stop get-back player animations after rim hold completes
      // Players may not have reached their destination, which is fine
      if (this._getBackTweens) {
        const beforeKill = getTweenManagerState();
        this._getBackTweens.forEach(tween => {
          if (tween && tween.isPlaying && this.scene.tweens) {
            this.scene.tweens.killTweensOf(tween.targets);
          }
        });
        this._getBackTweens = [];
        const afterKill = getTweenManagerState();
        console.log(`🔍 [MAKE HANDLER] After killing _getBackTweens`, {
          beforeKill,
          afterKill,
          killedCount: this._getBackTweens ? 0 : 'N/A'
        });
      }
      
      // Hide ball after hold
      ballSprite.setVisible(false);
    }

    // Transition to IDLE state (end of possession)
    if (this.stateMachine) {
      this.stateMachine.transition(AnimationStates.IDLE, {
        reason: 'shot_made',
        shooter_id: turnData.shooter_id
      });
      console.log(`🔍 [MAKE HANDLER] After state transition to IDLE`, {
        currentState: this.stateMachine.state
      });
    }

    // Ball hold already handled above (1 second), no additional delay needed
    
    // ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state
    // This matches the pattern in ballManager.js (line 626)
    this.ballController.onShotEnd();
    console.log(`🔍 [MAKE HANDLER] After onShotEnd()`, {
      ballControllerState: {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight
      }
    });
    
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
      // ✅ FIX: Don't call runInboundSetup() here if next_play_type === "BASELINE_INBOUND"
      // The BASELINE_INBOUND turn will handle the inbound setup via AnimationEngine.handleBaselineInbound()
      // Calling it here causes double inbound passes and double setup animations
      const shouldFlipPossession = turnData.next_play_type === "BASELINE_INBOUND" && 
                                   (turnData.possession_flips !== false);
      if (shouldFlipPossession) {
        // ✅ REMOVED: runInboundSetup() call - BASELINE_INBOUND turn handles it
        // This prevents double inbound passes and double setup animations
      }
    }
    
    // ✅ REMOVED: Made shot complete logging (cluttering console)
  }

  /**
   * Handle missed shot
   */
  async handleMissedShot(rimCoords, turnData) {
    // ✅ REMOVED: Missed shot logging (cluttering console)

    // 🔍 STATE COMPARISON: Log state at start of handleMissedShot
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        return { total };
      } catch (error) {
        return { error: error.message };
      }
    };
    console.log(`🔍 [MISS HANDLER] Start`, {
      _getBackTweensCount: this._getBackTweens ? this._getBackTweens.length : 0,
      tweenManager: getTweenManagerState(),
      ballControllerState: this.ballController ? {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight
      } : null
    });

    // Animate ball bounce from rim
    await this.animateBallBounce(rimCoords, turnData);
    console.log(`🔍 [MISS HANDLER] After animateBallBounce()`, {
      tweenManager: getTweenManagerState()
    });
    
    // ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state before rebound
    // This matches the pattern in ballManager.js (line 626)
    // The ball is no longer in flight, so clear the state to allow attachment to rebounder
    this.ballController.onShotEnd();
    console.log(`🔍 [MISS HANDLER] After onShotEnd()`, {
      ballControllerState: {
        isAttached: this.ballController.isAttached,
        isInFlight: this.ballController.isInFlight
      },
      tweenManager: getTweenManagerState()
    });
    
    // ✅ FIX: Stop get-back player animations when rebound is secured
    // Players may not have reached their destination, which is fine
    // This happens when rebounder secures the ball (in handleEmbeddedRebound)

    // ✅ PRIORITY 2 FIX: Add validation to ensure rebound_type is set
    // Check if this shot turn includes rebound data
    if (turnData.rebounderId && turnData.rebound_type) {
      console.log(`🔍 [MISS HANDLER] Before handleEmbeddedRebound()`, {
        rebounderId: turnData.rebounderId,
        reboundType: turnData.rebound_type,
        tweenManager: getTweenManagerState(),
        _getBackTweensCount: this._getBackTweens ? this._getBackTweens.length : 0
      });
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
    // Start both animations at the same time, but stop all when rebounder reaches ball
    // getPlayerDuration is already imported at top of file
    
    // ✅ FIX: Use distance-based duration for consistent speed
    const rebounderDuration = getPlayerDuration(rebounderSprite, ballBounceX, ballBounceY);
    
    // 🔍 STATE COMPARISON: Log before animatePlayerCollapse
    const getTweenManagerState = () => {
      if (!this.scene.tweens) return null;
      try {
        const total = typeof this.scene.tweens.getAll === 'function' 
          ? this.scene.tweens.getAll().length 
          : 'N/A';
        return { total };
      } catch (error) {
        return { error: error.message };
      }
    };
    console.log(`🔍 [EMBEDDED REBOUND] Before animatePlayerCollapse()`, {
      _getBackTweensCount: this._getBackTweens ? this._getBackTweens.length : 0,
      tweenManager: getTweenManagerState()
    });
    
    // Start non-rebounder animations first and store tween references
    const collapseTweens = await this.animatePlayerCollapse(rebounderSprite, { x: ballBounceX, y: ballBounceY }, turnData);
    console.log(`🔍 [EMBEDDED REBOUND] After animatePlayerCollapse()`, {
      collapseTweensCount: collapseTweens ? collapseTweens.length : 0,
      tweenManager: getTweenManagerState()
    });
    
    const rebounderPromise = new Promise((resolve) => {
      this.scene.tweens.add({
        targets: rebounderSprite,
        x: ballBounceX,
        y: ballBounceY,
        duration: rebounderDuration,
        ease: 'Linear', // Match other player movements
        onComplete: () => {
          // ✅ FIX: Stop all collapse animations when rebounder reaches ball
          const beforeKillCollapse = getTweenManagerState();
          if (collapseTweens && collapseTweens.length > 0) {
            collapseTweens.forEach(tween => {
              if (tween && this.scene.tweens) {
                this.scene.tweens.killTweensOf(tween.targets);
              }
            });
          }
          const afterKillCollapse = getTweenManagerState();
          console.log(`🔍 [EMBEDDED REBOUND] After killing collapseTweens`, {
            beforeKillCollapse,
            afterKillCollapse,
            killedCollapseCount: collapseTweens ? collapseTweens.length : 0
          });
          
          // Attach ball to rebounder once they reach the bounce spot
          this.ballController.attachToPlayer(rebounderSprite, {
            offset: { x: 0, y: -10 }
          });
          
          // ✅ FIX: Stop get-back player animations when rebound is secured
          const beforeKillGetBack = getTweenManagerState();
          if (this._getBackTweens) {
            this._getBackTweens.forEach(tween => {
              if (tween && tween.isPlaying && this.scene.tweens) {
                this.scene.tweens.killTweensOf(tween.targets);
              }
            });
            this._getBackTweens = [];
          }
          const afterKillGetBack = getTweenManagerState();
          console.log(`🔍 [EMBEDDED REBOUND] After killing _getBackTweens`, {
            beforeKillGetBack,
            afterKillGetBack,
            killedGetBackCount: this._getBackTweens ? 0 : 'N/A'
          });
          
          resolve();
        }
      });
    });

    // Wait only for rebounder to complete (collapse animations will be stopped)
    await rebounderPromise;

    // Determine next action based on rebound type
    // ✅ COMMENTED OUT: Verbose rebound logs (cluttering console)
    // console.log('🎬 ShotAnimationSystem: Determining rebound action', {
    //   rebound_type: turnData.rebound_type,
    //   isDREB: turnData.rebound_type === 'DREB',
    //   isOREB: turnData.rebound_type === 'OREB',
    //   allKeys: Object.keys(turnData)
    // });
    
    if (turnData.rebound_type === 'DREB') {
      // ✅ REMOVED: Calling handleDefensiveRebound logging (cluttering console)
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
      // ✅ REMOVED: Calling handleOffensiveRebound logging (cluttering console)
      await this.handleOffensiveRebound(rebounderSprite, turnData);
    } else {
      // ✅ REMOVED: Unknown rebound type logging (cluttering console)
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
   * Returns array of tween references so they can be stopped early
   */
  async animatePlayerCollapse(rebounderSprite, ballBounceCoords, turnData) {
    // getPlayerDuration is already imported at top of file
    
    // Store tween references so they can be stopped when rebounder reaches ball
    const collapseTweens = [];
    
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
      
      // ✅ FIX: Use distance-based duration for consistent speed
      const collapseDuration = getPlayerDuration(playerSprite, targetPixel.x, targetPixel.y);
      
      // Create tween and store reference
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: targetPixel.x,
        y: targetPixel.y,
        duration: collapseDuration,
        ease: 'Linear', // Match other player movements
        onComplete: () => {
          // Animation completed (though it may be stopped early)
        }
      });
      
      collapseTweens.push(tween);
    });
    
    // Return tween references so they can be stopped when rebounder reaches ball
    return collapseTweens;
  }

  /**
   * Animate individual player to rebound spot (within 10 grid spots of ball)
   */
  async animatePlayerToReboundSpot(playerSprite, ballBounceCoords, bounceGridX, bounceGridY) {
    // getPlayerDuration is already imported at top of file
    
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
      
      // ✅ REMOVED: Player moving to rebound spot logging (cluttering console)
      
      // ✅ FIX: Use distance-based duration for consistent speed
      const duration = getPlayerDuration(playerSprite, clampedX, clampedY);
      
      // Animate player movement
      const tween = this.scene.tweens.add({
        targets: playerSprite,
        x: clampedX,
        y: clampedY,
        duration,
        ease: 'Linear', // Match other player movements
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
      // ✅ REMOVED: Defensive rebound logging (cluttering console)
      
      // ✅ FIX: Announce rebound before outlet animation
      // ballManager only announces rebounds for its own rebound positioning code
      // Outlet pass system needs to announce too
      const { showAnnouncement } = await import('../utils/announcements.js');
      const rebounderSprite = this.playerSprites[turnData.rebounderId];
      if (rebounderSprite) {
        const rebounderTeam = rebounderSprite.team; // "home" or "away"
        const playerData = {
          playerId: turnData.rebounderId,
          photo: rebounderSprite.photo || null,
          teamName: rebounderSprite.team_id
        };
        showAnnouncement("Rebound!", rebounderTeam, playerData);
      }
      
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
        // ✅ REMOVED: runDefensiveReboundSetup completed logging (cluttering console)
      } catch (error) {
        console.error('❌ ShotAnimationSystem: runDefensiveReboundSetup failed', error);
        throw error; // Re-throw to trigger fallback
      }
    } else if (nextPlayType === 'FAST_BREAK') {
      // ✅ FIX: Fast Break outlet passes are handled in the Fast Break sequence itself
      // But we should still log that we're skipping outlet pass here
      // ✅ REMOVED: Fast break outlet pass logging (cluttering console)
    } else {
      // ✅ PRIORITY 2 FIX: Add defensive logging for skipped outlet pass
      // ✅ REMOVED: Defensive rebound outlet pass skipped logging (cluttering console)
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
    
    // ✅ REMOVED: Offensive rebound logging (cluttering console)
    
    try {
      // TEMPORARY: Force all offensive rebounds to be putback attempts for testing
      await this.executePutbackAttempt(rebounderSprite, turnData);
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
    // ✅ REMOVED: Putback attempt logging (cluttering console)
    
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
    
    // Use the old system - it already works perfectly for regular shots
    await playTurnAnimation({
      scene: this.scene,
      simData: { turns: [] }, // Not needed for single turn
      playerSprites: this.playerSprites,
      turnData: putbackTurnData,
      ballSprite: this.ballController.ballSprite,
      onAction: () => {} // No callback needed
    });
    return { success: true };
  }

  /**
   * Execute kickout pass
   */
  async executeKickoutPass(rebounderSprite, turnData) {
    // ✅ REMOVED: Kickout pass logging (cluttering console)
    
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
