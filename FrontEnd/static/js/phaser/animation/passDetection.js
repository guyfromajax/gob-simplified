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
  for (const anim of animations) {
    const movement = anim.movement;
    if (!movement || stepIndex >= movement.length) continue;
    
    const step = movement[stepIndex];
    if (step?.action === "pass") {
      // Find receiver (player with action === "receive" at same step)
      const receiverAnim = animations.find(otherAnim => {
        if (otherAnim.playerId === anim.playerId) return false; // Skip passer
        const otherMovement = otherAnim.movement;
        if (!otherMovement || stepIndex >= otherMovement.length) return false;
        const otherStep = otherMovement[stepIndex];
        return otherStep?.action === "receive";
      });
      
      if (receiverAnim) {
        return {
          passerId: anim.playerId,
          receiverId: receiverAnim.playerId,
          stepIndex,
          timestamp: step.timestamp
        };
      }
    }
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
  
  console.log('🏀 [PASS ANIMATION] Calling runPass', {
    fromId: passInfo.passerId,
    toId: passInfo.receiverId,
    passerPos: { x: passerSprite.x, y: passerSprite.y },
    receiverPos: { x: receiverSprite.x, y: receiverSprite.y }
  });
  
  // Calculate pass duration based on distance (like fast break outlet passes)
  const distance = Phaser.Math.Distance.Between(
    passerSprite.x, passerSprite.y,
    receiverSprite.x, receiverSprite.y
  );
  // Use same speed as fast break outlet passes (500ms default, or distance-based)
  const passDuration = distance > 0 ? Math.max(300, Math.min(800, (distance / 350) * 1000)) : 500;
  
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
  console.log('🏀 [PASS ANIMATION] runPass completed, keeping passInFlight=true for next step');
}


