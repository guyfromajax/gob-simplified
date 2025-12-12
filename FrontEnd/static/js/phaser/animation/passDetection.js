/**
 * Shared pass detection and handling utility
 * Used by playTurnAnimation, ShotAnimationSystem, and future animation systems
 * to ensure consistent pass animation across all turn types (HCO shots, fouls, turnovers, etc.)
 */

import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";

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
      
      // Find receiver (player with action === "receive" at same step)
      const receiverAnim = animations.find(otherAnim => {
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
      
      if (receiverAnim) {
        const result = {
          passerId: anim.playerId,
          receiverId: receiverAnim.playerId,
          stepIndex,
          timestamp: step.timestamp
        };
        
        // ✅ COMMENTED OUT: Pass detection logs (cluttering console)
        // console.log(`✅ [PASS DETECT] Step ${stepIndex}: Found pass`, {
        //   passer: anim.playerId?.substring(0, 8),
        //   receiver: receiverAnim.playerId?.substring(0, 8),
        //   timestamp: step.timestamp,
        //   debugInfo
        // });
        
        return result;
      } else {
        // ✅ COMMENTED OUT: Pass detection warning (cluttering console)
        // console.warn(`⚠️ [PASS DETECT] Step ${stepIndex}: Passer found but NO receiver`, {
        //   passer: anim.playerId?.substring(0, 8),
        //   debugInfo
        // });
      }
    }
  }
  
  // No pass found
  // ✅ COMMENTED OUT: Pass detection logs (cluttering console)
  // console.log(`❌ [PASS DETECT] Step ${stepIndex}: No pass found`, debugInfo);
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
  
  // ✅ COMMENTED OUT: Pass animation logs (cluttering console)
  // console.log('🏀 [PASS ANIMATION] Calling runPass', {
  //   fromId: passInfo.passerId,
  //   toId: passInfo.receiverId,
  //   passerPos: { x: passerSprite.x, y: passerSprite.y },
  //   receiverPos: { x: receiverSprite.x, y: receiverSprite.y }
  // });
  
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
  const passDuration = getBallDuration(
    ballSprite,
    receiverSprite.x,
    receiverSprite.y
  );
  
  await runPass(scene, {
    fromId: passInfo.passerId,
    toId: passInfo.receiverId,
    duration: passDuration,
    easing: "Sine.easeInOut"
  });
  
  // ✅ CRITICAL FIX: Keep passInFlight true for the NEXT step to prevent
  // updateBallOwnership from teleporting the ball immediately after pass completes
  // This matches fast break behavior - no updateBallOwnership during/after pass
  scene.passInFlight = true;
  // ✅ COMMENTED OUT: Pass animation logs (cluttering console)
  // console.log('🏀 [PASS ANIMATION] runPass completed, keeping passInFlight=true for next step');
}


