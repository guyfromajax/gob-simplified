/**
 * Shared pass detection and handling utility
 * Used by playTurnAnimation, ShotAnimationSystem, and future animation systems
 * to ensure consistent pass animation across all turn types (HCO shots, fouls, turnovers, etc.)
 */

import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from '../utils/gridToPixels.js';

/**
 * Detect if a pass is happening at a specific step
 * @param {Array} animations - Player animation data
 * @param {number} stepIndex - Step index to check
 * @returns {Object|null} Pass info with passerId, receiverId, stepIndex, or null if no pass
 */
export function detectPassAtStep(animations, stepIndex) {
  // 🔍 DEBUG: Log pass detection attempt
  const debugInfo = {
    stepIndex,
    totalAnimations: animations.length,
    movementLengths: {},
    passersFound: [],
    receiversFound: []
  };
  
  for (const anim of animations) {
    const movement = anim.movement;
    if (!movement) {
      debugInfo.movementLengths[anim.playerId?.substring(0, 8) || 'unknown'] = 'NO_MOVEMENT';
      continue;
    }
    
    debugInfo.movementLengths[anim.playerId?.substring(0, 8) || 'unknown'] = movement.length;
    
    if (stepIndex >= movement.length) continue;
    
    const step = movement[stepIndex];
    const action = step?.action;
    
    if (action === "pass") {
      debugInfo.passersFound.push({
        playerId: anim.playerId?.substring(0, 8) || 'unknown',
        action,
        timestamp: step?.timestamp
      });
      
      const passTimestamp = step?.timestamp;

      // Primary lookup: receiver at same movement index
      let receiverStepIndex = stepIndex;
      let receiverAnim = animations.find(otherAnim => {
        if (otherAnim.playerId === anim.playerId) return false; // Skip passer
        const otherMovement = otherAnim.movement;
        if (!otherMovement || stepIndex >= otherMovement.length) return false;
        const otherStep = otherMovement[stepIndex];
        const otherAction = otherStep?.action;
        
        if (otherAction === "receive") {
          debugInfo.receiversFound.push({
            playerId: otherAnim.playerId?.substring(0, 8) || 'unknown',
            action: otherAction,
            timestamp: otherStep?.timestamp
          });
          return true;
        }
        return false;
      });

      // Fallback lookup for sparse movement arrays:
      // match receiver by the same timestamp as the passer's pass step.
      if (!receiverAnim && Number.isFinite(Number(passTimestamp))) {
        for (const otherAnim of animations) {
          if (otherAnim.playerId === anim.playerId) continue;
          const otherMovement = Array.isArray(otherAnim.movement) ? otherAnim.movement : [];
          const fallbackIdx = otherMovement.findIndex((ms) =>
            ms?.action === "receive" &&
            Number(ms?.timestamp) === Number(passTimestamp)
          );
          if (fallbackIdx >= 0) {
            receiverAnim = otherAnim;
            receiverStepIndex = fallbackIdx;
            debugInfo.receiversFound.push({
              playerId: otherAnim.playerId?.substring(0, 8) || 'unknown',
              action: "receive",
              timestamp: passTimestamp,
              via: "timestamp_fallback"
            });
            break;
          }
        }
      }
      
      if (receiverAnim) {
        const receiverMovement = Array.isArray(receiverAnim.movement) ? receiverAnim.movement : [];
        const receiverStep = receiverMovement[receiverStepIndex];
        const result = {
          passerId: anim.playerId,
          receiverId: receiverAnim.playerId,
          stepIndex,
          timestamp: step.timestamp,
          receiverStepIndex,
          receiverCoords: receiverStep?.coords || null
        };
        
        // 🔍 DEBUG: Log pass detection for step 16 (3-2 Motion bug)
        if (stepIndex === 16) {
          console.log(`🔍 [PASS DETECTION] Step ${stepIndex}: Found pass`, {
            passer: anim.playerId?.substring(0, 8),
            receiver: receiverAnim.playerId?.substring(0, 8),
            timestamp: step.timestamp,
            debugInfo,
            allPassersFound: debugInfo.passersFound,
            allReceiversFound: debugInfo.receiversFound
          });
        }
        
        return result;
      } else {
        // 🔍 DEBUG: Log when passer found but no receiver (step 16 bug)
        if (stepIndex === 16) {
          console.warn(`⚠️ [PASS DETECTION] Step ${stepIndex}: Passer found but NO receiver`, {
            passer: anim.playerId?.substring(0, 8),
            debugInfo,
            allReceiversFound: debugInfo.receiversFound
          });
        }
      }
    }
  }
  
  // No pass found
  // 🔍 DEBUG: Log when no pass found at step 16
  if (stepIndex === 16) {
    console.log(`❌ [PASS DETECTION] Step ${stepIndex}: No pass found`, debugInfo);
  }
  return null;
}

/**
 * Handle pass animation after player movements complete
 * @param {Object} params
 * @param {Phaser.Scene} params.scene
 * @param {Object} params.passInfo - Pass info from detectPassAtStep
 * @param {Object} params.playerSprites - Map of playerId -> sprite
 * @returns {Promise<void>}
 */
export async function handlePassAnimation({ scene, passInfo, playerSprites }) {
  if (!passInfo) return;
  
  const { runPass } = await import('./ballTween.js');
  const passerSprite = playerSprites[passInfo.passerId];
  const receiverSprite = playerSprites[passInfo.receiverId];
  
  if (!passerSprite || !receiverSprite) {
    console.error('❌ [PASS ANIMATION] Missing sprites!', {
      passerSprite: !!passerSprite,
      receiverSprite: !!receiverSprite,
      passerId: passInfo.passerId,
      receiverId: passInfo.receiverId
    });
    return;
  }
  
  // 🔍 DEBUG: Log pass animation for step 16 (3-2 Motion bug)
  if (passInfo.stepIndex === 16) {
    // Map all player IDs to their positions for debugging
    const allPlayerMappings = Object.keys(playerSprites).map(playerId => {
      const sprite = playerSprites[playerId];
      const playerInfo = scene.playerInfo?.[playerId];
      return {
        playerId: playerId?.substring(0, 8),
        fullPlayerId: playerId,
        position: playerInfo?.pos || sprite.position || 'unknown',
        name: playerInfo?.name || 'unknown',
        x: sprite.x,
        y: sprite.y
      };
    });
    
    // Get passer and receiver position info
    const passerInfo = scene.playerInfo?.[passInfo.passerId];
    const receiverInfo = scene.playerInfo?.[passInfo.receiverId];
    
    console.log('🏀 [PASS ANIMATION] Calling runPass for step 16', {
      fromId: passInfo.passerId,
      toId: passInfo.receiverId,
      passerPos: { 
        x: passerSprite.x, 
        y: passerSprite.y, 
        position: passerInfo?.pos || passerSprite.position || 'unknown',
        name: passerInfo?.name || 'unknown'
      },
      receiverPos: { 
        x: receiverSprite.x, 
        y: receiverSprite.y, 
        position: receiverInfo?.pos || receiverSprite.position || 'unknown',
        name: receiverInfo?.name || 'unknown'
      },
      stepIndex: passInfo.stepIndex,
      allPlayerMappings: allPlayerMappings
    });
  }
  
  // ✅ FIX: Use getBallDuration() to respect game speed settings
  // Import getBallDuration from ballTween.js which uses getBallSpeed() that checks window.__GAME_SPEED
  // Get ball sprite from scene (same way runPass gets it)
  const ballSprite = scene.ballSprite;
  
  if (!ballSprite) {
    console.warn('❌ [PASS ANIMATION] No ball sprite available for duration calculation');
    // Fallback to default duration
    await runPass(scene, {
      fromId: passInfo.passerId,
      toId: passInfo.receiverId,
      duration: 500, // Default fallback
      easing: "Sine.easeInOut"
    });
    return;
  }
  
  const { getBallDuration } = await import('./ballTween.js');
  const receiverGrid = passInfo?.receiverCoords;
  const receiverTargetPx =
    receiverGrid &&
    Number.isFinite(Number(receiverGrid.x)) &&
    Number.isFinite(Number(receiverGrid.y))
      ? gridToPixels(
          Number(receiverGrid.x),
          Number(receiverGrid.y),
          scene.game.config.width,
          scene.game.config.height
        )
      : { x: receiverSprite.x, y: receiverSprite.y };
  const passDuration = getBallDuration(
    ballSprite,
    receiverTargetPx.x,
    receiverTargetPx.y
  );
  
  await runPass(scene, {
    fromId: passInfo.passerId,
    toId: passInfo.receiverId,
    endCoords: receiverTargetPx,
    duration: passDuration,
    easing: "Sine.easeInOut",
    stepIndex: passInfo.stepIndex // 🔍 DEBUG: Pass stepIndex for debugging
  });
  
  // ✅ CRITICAL FIX: Keep passInFlight true for the NEXT step to prevent
  // updateBallOwnership from teleporting the ball immediately after pass completes
  // This matches fast break behavior - no updateBallOwnership during/after pass
  scene.passInFlight = true;
  // ✅ COMMENTED OUT: Pass animation logs (cluttering console)
  // console.log('🏀 [PASS ANIMATION] runPass completed, keeping passInFlight=true for next step');
}


