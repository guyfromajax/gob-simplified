import { gridToPixels } from "../utils/gridToPixels.js";

/**
 * Animates a single step of a player's movement.
 * Called by the centralized step loop in turnAnimation.js.
 *
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
 * @param {object} step - The movement step { timestamp, coords, action }
 * @param {number} duration - Milliseconds for tween duration
 * @returns {Promise} resolves when tween completes
 */
import { PASS_DEBUG } from "./ballTween.js";
import {
  getPendingOwner,
  getCurrentOwner,
} from "./BallControllerAdapter.js";
import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
// ✅ NEW (Step 1): Import simple ball holder state functions
import {
  getPlayerTweenTargets,
  isBallHolder,
  initializeBallHolderState,
  setBallHolderId,
  clearBallHolder,
  getBallHolderId,
} from "./ballAnimationSimple.js";

export const PLAYER_TWEEN_DEBUG = false;

export function animateStep({ scene, sprite, step, duration, ballSprite, currentBallOwnerRef, onAction, stepIndex = null, nextStep = null, turnData = null }) {
  // 🔍 DEBUG: Log step entry for FCP/HCT skeleton animations
  const isFCPHCT = turnData?.play_type === 'FCP' || turnData?.play_type === 'HCT';
  if (isFCPHCT && stepIndex !== null) {
    const info = scene.playerInfo?.[sprite?.playerId];
    console.log(`🔍 [${turnData.play_type} STEP ${stepIndex}] ${info?.pos || 'UNKNOWN'} (${sprite?.playerId?.substring(0, 8)}) animating:`, {
      from: { x: sprite.x, y: sprite.y },
      to: step.coords,
      action: step.action,
      has_ball: step.has_ball
    });
  }

  if (scene.skipToEnd) return Promise.resolve();
  return new Promise((resolve) => {
    let tween = null;
    let tweenCompleted = false;
    // Safety timeout: if tween doesn't complete within reasonable time, force resolve
    const timeoutMs = Math.max(duration * 2, 5000); // At least 2x duration or 5 seconds
    const timeoutId = setTimeout(() => {
      if (tweenCompleted) {
        // Tween already completed, just clear timeout
        return;
      }
      const distance = Math.hypot(sprite.x - targetX, sprite.y - targetY);
      let tweenManagerState = null;
      if (scene.tweens) {
        try {
          const total = typeof scene.tweens.getAll === 'function' 
            ? scene.tweens.getAll().length 
            : 'N/A';
          const paused = typeof scene.tweens.isPaused === 'function'
            ? scene.tweens.isPaused()
            : 'N/A';
          tweenManagerState = {
            total,
            paused,
            timeScale: scene.tweens.timeScale || 'N/A'
          };
        } catch (error) {
          tweenManagerState = { error: error.message };
        }
      }
      // Check if this is a step before a shot (common cause of pauses)
      const isBeforeShot = step.action === 'guard_ball' || step.action === 'receive' || 
                          (scene.currentTurnData?.animations?.some(anim => 
                            anim.movement?.some(m => m.action === 'shoot' && m.timestamp > step.timestamp)
                          ));
      
      // ✅ COMMENTED OUT: Timeout logs (cluttering console)
      // console.warn('animateStep: Timeout - forcing resolve', {
      //   playerId: sprite?.playerId,
      //   action: step.action,
      //   duration,
      //   timeoutMs,
      //   tweenActive: tween?.isPlaying !== false,
      //   tweenProgress: tween?.progress,
      //   spritePos: { x: sprite.x, y: sprite.y },
      //   targetPos: { x: targetX, y: targetY },
      //   distanceToTarget: distance,
      //   tweenManagerState,
      //   scenePaused: scene.scene?.isPaused(),
      //   skipToEnd: scene.skipToEnd,
      //   isBeforeShot,
      //   stepTimestamp: step.timestamp
      // });
      if (tween) {
        scene.tweens?.killTweensOf(tween);
      }
      tweenCompleted = true;
      resolve();
    }, timeoutMs);
    // Use nextStep.coords if available (for movement target), otherwise step.coords
    const targetStep = nextStep || step;
    const isInboundSpot = targetStep.coords.x <= 5 || targetStep.coords.x >= 95;
    const shouldClampXToRims =
      !isInboundSpot &&
      turnData?.result_type !== "SIDE_INBOUND" &&
      turnData?.result_type !== "BASELINE_INBOUND";
    const targetGridX = shouldClampXToRims
      ? Math.max(9, Math.min(91, targetStep.coords.x))
      : targetStep.coords.x;
    const { x: targetX, y: targetY } = gridToPixels(
      targetGridX,
      targetStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    const startPosition = { x: sprite.x, y: sprite.y };
    const plannedDistance = Math.hypot(targetX - startPosition.x, targetY - startPosition.y);

    const emitSummary = (status) => {
      if (!isAnimationDebugEnabled()) return;
      const ownerId = getCurrentOwner(scene);
      const pendingOwnerId = getPendingOwner(scene);
      const actualDistance = Math.hypot(sprite.x - startPosition.x, sprite.y - startPosition.y);
      const summary = {
        type: 'step',
        status,
        playerId: sprite?.playerId ?? null,
        action: step.action ?? null,
        timestamp: step.timestamp,
        plannedDistance,
        actualDistance,
        ownerId,
        pendingOwnerId,
        passInFlight: !!scene?.passInFlight,
        ballDetached: !!scene?.ballDetached,
        scoreDelta: scene?.__debugScoreDelta ?? null,
        position: { x: sprite.x, y: sprite.y },
      };
      animationDebugLog('ANIM step summary', summary);
      const tolerance = 2;
      if (actualDistance - plannedDistance > tolerance) {
        animationDebugWarn('ANIM teleport suspicion', {
          playerId: sprite?.playerId ?? null,
          plannedDistance,
          actualDistance,
          start: startPosition,
          target: { x: targetX, y: targetY },
        });
      }
    };

    let startPromise = Promise.resolve();

    // ✅ NEW (Step 2): Use WIP_GOB approach - conditional target arrays
    // Check ball holder state BEFORE creating tween (matches WIP_GOB pattern)
    // This ensures ball is only included if player actually has ball at tween creation time
    
    // ✅ PROACTIVE STATE MANAGEMENT: Clear ball holder state when pass action detected
    // This ensures state is correct before creating tween (prevents ball from being in passer's tween)
    // This matches WIP_GOB: ball holder state is updated before tween targets are calculated
    const currentAction = nextStep ? nextStep.action : step.action;
    const isPassing = currentAction === 'pass' || scene.passInFlight;
    if (currentAction === 'pass') {
      clearBallHolder(scene);
    }
    
    // ✅ PROACTIVE STATE MANAGEMENT: Clear ball holder state for receive actions
    // Ball is being attached by runPass(), so we shouldn't include it in receiver's tween
    // We'll set ball holder state after receive action completes
    const isReceiving = currentAction === 'receive';
    if (isReceiving) {
      clearBallHolder(scene);  // Clear state so ball isn't included in receiver's tween
    }
    
    // ✅ WIP_GOB APPROACH: Use getPlayerTweenTargets() for ALL movements (including passes)
    // This matches WIP_GOB: targets are calculated based on ball holder state at creation time
    // If ball holder state was cleared above, ball won't be included (no need for explicit exclusion)
    const jerseyNo = sprite.jerseyNo || null;
    const targets = getPlayerTweenTargets(scene, sprite, jerseyNo);
    
    // Filter out any null/invalid targets
    let tweenTargets = targets.filter(target => 
      target && 
      target.scene && 
      target.active !== false && 
      !target.destroyed
    );
    
    // Fallback to old system if new system didn't return valid targets
    if (tweenTargets.length === 0) {
      tweenTargets = [sprite];
    }
    
    // ✅ SAFETY: For pass/receive actions, ensure ball is not in tween targets
    // This is a defensive check - ball holder state should already be cleared, but just in case
    // Remove ball from targets if it's there (shouldn't be, but safety first)
    if ((isPassing || isReceiving) && tweenTargets.includes(ballSprite)) {
      tweenTargets = tweenTargets.filter(t => t !== ballSprite && t !== scene.ballShadowSprite);
      console.warn('animateStep: Ball was in tween targets for pass/receive action, removing it', {
        playerId: sprite?.playerId,
        action: step.action,
        ballHolderId: getBallHolderId(scene)
      });
    }

    // Filter out any null/invalid targets before creating tween
    let validTargets = tweenTargets.filter(target => 
      target && 
      target.scene && 
      target.active !== false && 
      !target.destroyed
    );
    
    // ✅ CRITICAL FIX: Remove ball from targets if it's already being tweened
    // If ball is in targets but has active tweens, Phaser won't start the new tween
    if (ballSprite && validTargets.includes(ballSprite)) {
      const ballActiveTweens = scene.tweens?.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        console.warn('🔍 [TWEEN CONFLICT] Ball has active tweens, removing from targets', {
          playerId: sprite?.playerId,
          action: step.action,
          ballActiveTweensCount: ballActiveTweens.length,
          ballActiveTweenIds: ballActiveTweens.map(t => t._animateStepId || 'no-id')
        });
        validTargets = validTargets.filter(t => t !== ballSprite && t !== scene.ballShadowSprite);
      }
    }

    // If no valid targets, resolve immediately
    if (validTargets.length === 0) {
      console.warn('animateStep: No valid targets for tween', {
        playerId: sprite?.playerId,
        action: step.action,
        tweenTargetsCount: tweenTargets.length,
        validTargetsCount: validTargets.length,
        spriteValid: sprite && sprite.scene && sprite.active !== false && !sprite.destroyed,
        ballValid: ballIsValid
      });
      tweenCompleted = true;
      clearTimeout(timeoutId);
      resolve();
      return;
    }
    
    // Check if distance is effectively zero (sprite already at target)
    const distance = Math.hypot(sprite.x - targetX, sprite.y - targetY);
    if (distance < 1) {
      // Sprite is already at target, resolve immediately
      // Call onAction if needed (fire and forget for zero-distance moves)
      // currentAction already declared above
      if (currentAction && onAction) {
        try {
          onAction(currentAction, sprite, nextStep?.timestamp || step.timestamp);
        } catch (error) {
          console.error('animateStep: Error in onAction for zero-distance step', { error, playerId: sprite?.playerId });
        }
      }
      tweenCompleted = true;
      clearTimeout(timeoutId);
      emitSummary('complete');
      resolve();
      return;
    }

    // Track tween creation for debugging long pauses
    const tweenId = `tween_${sprite?.playerId}_${Date.now()}`;
    
    // Check if this is the first step of HCO and the action is a pass
    // For HCO entry, we want to delay the pass until the ball handler reaches their destination
    // stepIndex === 1 means it's the first step in the animation loop (loop starts at 1)
    // nextStep.action === 'pass' means the current step's action is a pass
    // Also check if timestamp is 0 (first step) to catch edge cases like post-opening-tip
    const isFirstStepHCO = (stepIndex === 1 || (nextStep && nextStep.timestamp === 0)) && nextStep && nextStep.action === 'pass';
    const shouldDelayPass = isFirstStepHCO;
    
    // 🔍 DEBUG: Log pass timing for HCO entry
    if (nextStep && nextStep.action === 'pass') {
      if (false) console.log('🔍 [PASS TIMING DEBUG]', {
        playerId: sprite?.playerId,
        action: nextStep.action,
        stepIndex,
        stepTimestamp: step.timestamp,
        nextStepTimestamp: nextStep.timestamp,
        isFirstStepHCO,
        shouldDelayPass,
        currentPos: { x: sprite.x, y: sprite.y },
        targetPos: { x: targetX, y: targetY },
        distance: Math.hypot(targetX - sprite.x, targetY - sprite.y),
        duration
      });
    }
    
    const tweenConfig = {
      targets: validTargets,
      x: targetX,
      y: targetY,
      duration,
      ease: "Linear",
      onStart: async () => {
        if (PLAYER_TWEEN_DEBUG || duration > 2000) {
          const team = sprite?.team_id ?? sprite?.team ?? null;
          console.log("animateStep: Tween started", {
            tweenId,
            playerId: sprite?.playerId ?? null,
            action: step.action,
            duration,
            team
          });
        }
        // For first step HCO passes, delay the pass action until player reaches destination
        // Use nextStep.action since that's the action for the current step being animated
        const currentAction = nextStep ? nextStep.action : step.action;
        if (currentAction && onAction && !shouldDelayPass) {
          if (PASS_DEBUG && currentAction === 'pass') {
            console.log('passStart', { fromId: sprite?.playerId, timestamp: nextStep?.timestamp || step.timestamp });
          }
          // 🔍 DEBUG: Log when pass is triggered in onStart
          if (currentAction === 'pass') {
            if (false) console.log('🔍 [PASS TIMING DEBUG] Pass triggered in onStart (not delayed)', {
              playerId: sprite?.playerId,
              timestamp: nextStep?.timestamp || step.timestamp,
              stepIndex,
              shouldDelayPass
            });
          }
          startPromise = onAction(currentAction, sprite, nextStep?.timestamp || step.timestamp);
          await startPromise;
        } else if (currentAction === 'pass' && shouldDelayPass) {
          // 🔍 DEBUG: Log when pass is being delayed
          if (false) console.log('🔍 [PASS TIMING DEBUG] Pass delayed - will trigger in onComplete', {
            playerId: sprite?.playerId,
            timestamp: nextStep?.timestamp || step.timestamp,
            stepIndex
          });
        }
      },
      onUpdate: () => {
        // ✅ NEW (Step 2): Handle ball shadow offset when using WIP_GOB approach
        // When ball shadow is in targets, it should be offset from ball position
        const ballSpriteInTargets = validTargets.find(t => t === ballSprite);
        const ballShadowSpriteInTargets = validTargets.find(t => t === scene.ballShadowSprite);
        
        if (ballSpriteInTargets && ballShadowSpriteInTargets) {
          // Ball and shadow are in targets - offset shadow from ball (WIP_GOB approach)
          const ballSpriteObj = ballSprite;
          const ballShadowSprite = scene.ballShadowSprite;
          if (ballSpriteObj && ballShadowSprite) {
            ballShadowSprite.x = ballSpriteObj.x + 4;
            ballShadowSprite.y = ballSpriteObj.y + 4;
          }
        } else {
          // Fallback: Old system - update ball position manually if not in targets
          if (
            currentBallOwnerRef?.value === sprite &&
            ballSprite?.setPosition &&
            !getPendingOwner(scene) &&
            !validTargets.includes(ballSprite)
          ) {
            ballSprite.setPosition(sprite.x, sprite.y);
          }
        }
      },
      onComplete: async () => {
        if (tweenCompleted) {
          // Already resolved via timeout, don't resolve again
          return;
        }
        tweenCompleted = true;
        clearTimeout(timeoutId);
        
        // ✅ FIX: For first step HCO passes, trigger the pass action after player reaches destination
        const currentAction = nextStep ? nextStep.action : step.action;
        if (shouldDelayPass && currentAction && onAction) {
          // 🔍 DEBUG: Log when delayed pass is triggered
          if (false) console.log('🔍 [PASS TIMING DEBUG] Delayed pass triggered in onComplete', {
            playerId: sprite?.playerId,
            timestamp: nextStep?.timestamp || step.timestamp,
            stepIndex,
            finalPos: { x: sprite.x, y: sprite.y },
            targetPos: { x: targetX, y: targetY }
          });
          if (PASS_DEBUG && currentAction === 'pass') {
            console.log('passStart (delayed for HCO entry)', { fromId: sprite?.playerId, timestamp: nextStep?.timestamp || step.timestamp });
          }
          try {
            await onAction(currentAction, sprite, nextStep?.timestamp || step.timestamp);
          } catch (error) {
            console.error('animateStep: Error in delayed onAction for first step pass', { error, playerId: sprite?.playerId });
          }
        }
        
        // ✅ FIX: Set ball holder state after receive action completes
        // Don't set it during receive (conflicts with pass cleanup), but set it after receive completes
        // This ensures receiver's subsequent movements will include ball in targets
        // currentAction already declared above in onComplete
        if (currentAction === 'receive' && sprite.playerId) {
          // Always set ball holder state after receive completes (ball is now with receiver)
          // The pass might still be completing, but the ball is attached to receiver now
          // Setting it here ensures receiver's subsequent movements will include ball in targets
          setBallHolderId(scene, sprite.playerId);
        }
        if (duration > 2000) {
          console.log('animateStep: Tween completed', {
            tweenId,
            playerId: sprite?.playerId,
            action: step.action,
            duration
          });
        }
        try {
          await startPromise;
        } catch (error) {
          console.error('animateStep: Error in startPromise', { error, playerId: sprite?.playerId });
        }
        emitSummary('complete');
        resolve();
      },
      onStop: async () => {
        if (tweenCompleted) {
          // Already resolved via timeout, don't resolve again
          return;
        }
        tweenCompleted = true;
        clearTimeout(timeoutId);
        try {
          await startPromise;
        } catch (error) {
          console.error('animateStep: Error in startPromise', { error, playerId: sprite?.playerId });
        }
        emitSummary('stop');
        resolve();
      }
    };
    
    // Log tween creation for debugging
    if (duration > 4000) {
      console.warn('animateStep: Creating tween with unusually long duration', {
        playerId: sprite?.playerId,
        action: step.action,
        duration,
        distance: Math.hypot(sprite.x - targetX, sprite.y - targetY),
        from: { x: sprite.x, y: sprite.y },
        to: { x: targetX, y: targetY }
      });
    }
    
    // ✅ DEBUG: Log tween targets before creation
    const ballInTargets = validTargets.includes(ballSprite);
    const ballHasActiveTween = ballSprite && scene.tweens?.getTweensOf ? scene.tweens.getTweensOf(ballSprite).length > 0 : false;
    if (ballInTargets || ballHasActiveTween) {
      if (false && stepIndex > 0) console.log('🔍 [TWEEN TARGETS DEBUG]', {
        playerId: sprite?.playerId,
        action: step.action,
        validTargetsCount: validTargets.length,
        ballInTargets,
        ballHasActiveTween,
        ballHolderId: getBallHolderId(scene),
        passInFlight: scene.passInFlight,
        ballControllerInFlight: scene.ballController?.isInFlight
      });
    }
    
    tween = scene.tweens.add(tweenConfig);
    tween._animateStepId = tweenId;
    
    // Verify tween was created and started
    if (!tween) {
      console.error('animateStep: Failed to create tween', {
        playerId: sprite?.playerId,
        action: step.action,
        validTargetsCount: validTargets.length
      });
      tweenCompleted = true;
      clearTimeout(timeoutId);
      resolve();
      return;
    }
    
    // ✅ DEBUG: Check if tween started immediately
    const tweenStartedImmediately = typeof tween.isPlaying === 'function' ? tween.isPlaying() : null;
    const tweenProgressImmediately = tween.progress || 0;
    if (tweenStartedImmediately === false || tweenProgressImmediately === 0) {
      // Check scene and tween manager state
      const scenePaused = scene.scene?.isPaused ? scene.scene.isPaused() : 'N/A';
      const tweenManagerState = scene.tweens ? {
        totalTweens: typeof scene.tweens.getAll === 'function' ? scene.tweens.getAll().length : 'N/A',
        isPaused: typeof scene.tweens.isPaused === 'function' ? scene.tweens.isPaused() : 'N/A',
        timeScale: scene.tweens.timeScale ?? 'N/A'
      } : null;
      
      // ✅ COMMENTED OUT: Tween start check logs (cluttering console)
      // console.warn('🔍 [TWEEN START CHECK] Tween created but not playing immediately', {
      //   playerId: sprite?.playerId,
      //   action: step.action,
      //   tweenStartedImmediately,
      //   tweenProgressImmediately,
      //   validTargetsCount: validTargets.length,
      //   ballInTargets,
      //   ballHasActiveTween,
      //   scenePaused,
      //   tweenManagerState
      // });
    }
    
    // Ensure tween starts immediately (Phaser tweens should auto-start, but verify)
    // Check if tween manager is paused or if tween needs explicit start
    if (scene.tweens && typeof scene.tweens.isPaused === 'function' && scene.tweens.isPaused()) {
      console.warn('animateStep: Tween manager is paused!', {
        playerId: sprite?.playerId,
        action: step.action
      });
    }
    
    // Verify tween is actually playing after creation
    let tweenStarted = false;
    if (typeof tween.isPlaying === 'function') {
      tweenStarted = tween.isPlaying();
    }
    
    if (!tweenStarted && typeof tween.play === 'function') {
      tween.play();
      // Verify it started
      if (typeof tween.isPlaying === 'function') {
        tweenStarted = tween.isPlaying();
      }
      
      // Log if we had to manually start it (especially for receive actions which are problematic)
      if (!tweenStarted || step.action === 'receive' || step.action === 'guard_ball') {
        console.warn('animateStep: Tween not playing after creation/play()', {
          playerId: sprite?.playerId,
          action: step.action,
          wasPlaying: false,
          nowPlaying: tweenStarted,
          tweenState: {
            isPlaying: typeof tween.isPlaying === 'function' ? tween.isPlaying() : 'N/A',
            isPaused: typeof tween.isPaused === 'function' ? tween.isPaused() : 'N/A',
            progress: tween.progress,
            totalProgress: tween.totalProgress
          },
          spriteState: {
            active: sprite?.active,
            visible: sprite?.visible,
            x: sprite?.x,
            y: sprite?.y
          }
        });
      }
    }
    
    // For receive/guard_ball actions specifically, add a safety check after a short delay
    // These actions are prone to getting stuck, so we monitor them more closely
    if (step.action === 'receive' || step.action === 'guard_ball') {
      let checkCount = 0;
      const maxChecks = 10; // Check 10 times over 1 second
      const checkInterval = scene.time.addEvent({
        delay: 100,
        repeat: maxChecks - 1,
        callback: () => {
          checkCount++;
          if (tweenCompleted) {
            checkInterval.destroy();
            return;
          }
          
          const isPlaying = typeof tween.isPlaying === 'function' ? tween.isPlaying() : false;
          const progress = tween?.progress || 0;
          
          if (!isPlaying && progress === 0 && checkCount >= 3) {
            // Tween still not playing after 300ms, try to force it
            console.warn(`animateStep: ${step.action} tween still not playing after ${checkCount * 100}ms, forcing start`, {
              playerId: sprite?.playerId,
              action: step.action,
              checkCount,
              tweenProgress: progress,
              isPlaying
            });
            
            // Try multiple methods to start the tween
            if (typeof tween.play === 'function') {
              tween.play();
            }
            if (typeof tween.restart === 'function') {
              tween.restart();
            }
            
            // If still not playing after all attempts, resolve to prevent infinite wait
            if (checkCount >= maxChecks) {
              console.error(`animateStep: ${step.action} tween failed to start after ${maxChecks * 100}ms, forcing resolve`, {
                playerId: sprite?.playerId,
                action: step.action
              });
              if (tween) {
                scene.tweens?.killTweensOf(tween);
              }
              tweenCompleted = true;
              clearTimeout(timeoutId);
              resolve();
              checkInterval.destroy();
            }
          } else if (isPlaying || progress > 0) {
            // Tween is working, stop checking
            checkInterval.destroy();
          }
        }
      });
    }
    
    // Removed verbose tween creation log
    // if (duration > 2000 || Math.hypot(sprite.x - targetX, sprite.y - targetY) > 500) {
    //   console.log('animateStep: Created tween', { ... });
    // }

    if (scene.skipToEnd) {
      tween.stop();
    }
  });
}



// import { gridToPixels } from "../utils/gridToPixels.js";

// /**
//  * Animates a player's movement over time using chained tweens.
//  * Resolves only after the final tween completes.
//  *
//  * @param {object} scene - The Phaser scene
//  * @param {Phaser.GameObjects.Sprite} sprite - The player's sprite
//  * @param {Array} movement - Array of movement steps
//  * @param {Function} onAction - Callback for animation events
//  * @param {Phaser.GameObjects.Sprite} ballSprite - Ball sprite to attach when possessed
//  * @param {Array} hasBallAtStep - Boolean array mapping possession per step
//  * @param {string} position - Position label (e.g. PG, SG)
//  * @param {object} currentBallOwnerRef - A shared ref passed from playTurnAnimation
//  * @returns {Promise}
//  */
// export function animateMovementSequence({ 
//   scene, 
//   sprite, 
//   movement, 
//   onAction, 
//   ballSprite, 
//   hasBallAtStep, 
//   position, 
//   currentBallOwnerRef 
// }) {
//   return new Promise((resolve) => {
//     if (!movement || movement.length < 2) return resolve();

//     let stepIndex = 1;

//     const animateNextStep = () => {
//       if (stepIndex >= movement.length) return resolve();

//       const prev = movement[stepIndex - 1];
//       const curr = movement[stepIndex];
//       const duration = (curr.timestamp - prev.timestamp) * 3;

//       const { x: targetX, y: targetY } = gridToPixels(
//         curr.coords.x,
//         curr.coords.y,
//         scene.game.config.width,
//         scene.game.config.height
//       );

//       const ownsBallThisStep = hasBallAtStep?.[stepIndex] === true;

//       // If this player owns the ball this step, set them as the current owner
//       if (ownsBallThisStep) {
//         currentBallOwnerRef.value = sprite;
//         if (ballSprite?.setVisible) {
//           ballSprite.setVisible(true);
//         }
//       }

//       scene.tweens.add({
//         targets: [sprite],
//         x: targetX,
//         y: targetY,
//         duration,
//         ease: "Linear",
//         onStart: () => {
//           if (onAction) onAction(curr.action, sprite, curr.timestamp);
//         },
//         onUpdate: () => {
//           // Only the current owner gets to update the ball
//           if (currentBallOwnerRef.value === sprite && ballSprite?.setPosition) {
//             ballSprite.setPosition(sprite.x, sprite.y);
//           }
//         },
//         onComplete: () => {
//           stepIndex++;
//           animateNextStep();
//         }
//       });
//     };

//     // Handle step 0 before any tween begins
//     if (hasBallAtStep?.[0]) {
//       currentBallOwnerRef.value = sprite;
//       if (ballSprite?.setPosition && ballSprite?.setVisible) {
//         ballSprite.setPosition(sprite.x, sprite.y);
//         ballSprite.setVisible(true);
//       } else {
//         console.warn("⚠️ ballSprite not ready at step 0 lock.");
//       }
//     }

//     animateNextStep();
//   });
// }
