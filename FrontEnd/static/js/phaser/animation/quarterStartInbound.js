/**
 * Quarter start inbound pass animation
 * Used for Q2, Q3, Q4 to establish possession at the start of the quarter
 */

import { animateStep } from './animateStep.js';
import { tweenBallTo } from './ballTween.js';

const INBOUND_DURATION = 800;
const PASS_DURATION = 400;

/**
 * Animate quarter start inbound pass
 * @param {Phaser.Scene} scene - Game scene
 * @param {Object} params - Animation parameters
 * @param {Object} params.playerSprites - Player sprites by ID
 * @param {Phaser.GameObjects.Sprite} params.ballSprite - Ball sprite
 * @param {Object} params.turnData - Turn data with animations
 */
export async function animateQuarterStartInbound(scene, { playerSprites, ballSprite, turnData }) {
  console.log('🏀 Animating quarter start inbound:', turnData);
  
  if (!turnData.animations || turnData.animations.length === 0) {
    console.warn('⚠️ Quarter start inbound has no animations');
    return;
  }
  
  // Animate all players moving to their inbound positions simultaneously
  await Promise.all(
    turnData.animations.map(anim => 
      animateStep(scene, playerSprites, anim, { ballSprite, hasBall: anim.playerId === turnData.inbounderId })
    )
  );
  
  console.log('✅ Players positioned for quarter start inbound');
  
  // Animate the inbound pass from PG to receiver
  const inbounderSprite = playerSprites[turnData.inbounderId];
  const receiverSprite = playerSprites[turnData.receiverId];
  
  if (!inbounderSprite || !receiverSprite) {
    console.warn('⚠️ Missing inbounder or receiver sprite for quarter start pass');
    return;
  }
  
  // Ball starts with inbounder
  if (ballSprite) {
    ballSprite.x = inbounderSprite.x;
    ballSprite.y = inbounderSprite.y;
    ballSprite.setVisible(true);
  }
  
  // Animate pass to receiver
  await new Promise(resolve => {
    if (ballSprite) {
      tweenBallTo(
        scene,
        ballSprite,
        { x: receiverSprite.x, y: receiverSprite.y },
        PASS_DURATION,
        resolve
      );
    } else {
      resolve();
    }
  });
  
  console.log('✅ Quarter start inbound pass completed');
}

