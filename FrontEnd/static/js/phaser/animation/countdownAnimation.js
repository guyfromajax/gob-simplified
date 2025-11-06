/**
 * Countdown Animation Module
 * 
 * Animates players during the 5-second clipboard countdown window.
 * Creates organic, varied movements so players don't freeze during user decision time.
 */

import { gridToPixels } from '../utils/gridToPixels.js';

/**
 * Animate players during countdown window based on transition type
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {Object} playerSprites - Map of player sprites
 * @param {Object} ballSprite - Ball sprite object
 * @param {string} transitionType - Type of transition ('DREB', 'INBOUND_PASS', 'SIDE_INBOUND')
 * @param {string} offenseTeamId - Team ID that will have offense next
 * @param {string} homeTeamId - Home team ID
 * @param {number} duration - Duration of countdown in ms (default 5000)
 */
export async function animateCountdownTransition({
  scene,
  playerSprites,
  ballSprite,
  transitionType,
  offenseTeamId,
  homeTeamId,
  duration = 5000
}) {
  
  console.log(`🎬 Starting countdown animation: ${transitionType}, offense: ${offenseTeamId}`);
  
  // Determine which team is on offense
  const isHomeOffense = String(offenseTeamId) === String(homeTeamId);
  const offenseSide = isHomeOffense ? 'home' : 'away';
  const defenseSide = isHomeOffense ? 'away' : 'home';
  
  // Get offensive and defensive players
  const offensivePlayers = Object.values(playerSprites).filter(p => p.team === offenseSide);
  const defensivePlayers = Object.values(playerSprites).filter(p => p.team === defenseSide);
  
  // Find ball handler (player with ball)
  const ballHandler = offensivePlayers.find(p => p.hasBall) || offensivePlayers[0];
  
  if (!ballHandler) {
    console.warn('⚠️ No ball handler found for countdown animation');
    return;
  }
  
  // Route to appropriate animation based on transition type
  switch (transitionType) {
    case 'DREB':
    case 'INBOUND_PASS':
      await animateAdvanceUpCourt({
        scene,
        offensivePlayers,
        defensivePlayers,
        ballHandler,
        ballSprite,
        isHomeOffense,
        duration
      });
      break;
      
    case 'SIDE_INBOUND':
      await animateSideInboundMovement({
        scene,
        offensivePlayers,
        defensivePlayers,
        ballHandler,
        ballSprite,
        isHomeOffense,
        duration
      });
      break;
      
    default:
      console.warn(`⚠️ Unknown transition type: ${transitionType}`);
  }
  
  console.log('✅ Countdown animation complete');
}

/**
 * Animate ball handler advancing up court, teammates moving to offensive positions
 */
async function animateAdvanceUpCourt({
  scene,
  offensivePlayers,
  defensivePlayers,
  ballHandler,
  ballSprite,
  isHomeOffense,
  duration
}) {
  
  // Target Y for ball handler (about 3/4 court)
  const targetY = isHomeOffense ? 20 : 30;
  
  // Ball handler advances steadily
  const ballHandlerStartX = ballHandler.x;
  const ballHandlerStartY = ballHandler.y;
  const ballHandlerEndX = ballHandlerStartX + (Math.random() * 6 - 3); // Slight horizontal drift
  const ballHandlerEndY = gridToPixels(50, targetY).y;
  
  // Animate ball handler
  scene.tweens.add({
    targets: ballHandler,
    x: ballHandlerEndX,
    y: ballHandlerEndY,
    duration: duration,
    ease: 'Linear'
  });
  
  // Animate ball with handler
  if (ballSprite) {
    scene.tweens.add({
      targets: ballSprite,
      x: ballHandlerEndX,
      y: ballHandlerEndY,
      duration: duration,
      ease: 'Linear'
    });
  }
  
  // Teammates move toward offensive basket with varied paths
  offensivePlayers.forEach((player, idx) => {
    if (player === ballHandler) return; // Skip ball handler
    
    const startX = player.gridX || 50;
    const startY = player.gridY || 25;
    
    // Generate random offensive position
    const endX = 35 + Math.random() * 30; // 35-65 (spread across court width)
    const endY = isHomeOffense ? (15 + Math.random() * 15) : (20 + Math.random() * 15);
    
    const endPixels = gridToPixels(endX, endY);
    
    // Stagger animations slightly for organic feel
    const delay = idx * 100;
    
    scene.tweens.add({
      targets: player,
      x: endPixels.x,
      y: endPixels.y,
      duration: duration - delay,
      delay: delay,
      ease: 'Sine.easeInOut'
    });
  });
  
  // Defensive players backpedal/adjust
  defensivePlayers.forEach((player, idx) => {
    const startX = player.gridX || 50;
    const startY = player.gridY || 25;
    
    // Drift back toward defensive basket
    const endX = startX + (Math.random() * 8 - 4); // Slight drift
    const endY = isHomeOffense ? (startY + 5 + Math.random() * 5) : (startY - 5 - Math.random() * 5);
    
    const endPixels = gridToPixels(endX, endY);
    
    const delay = idx * 150;
    
    scene.tweens.add({
      targets: player,
      x: endPixels.x,
      y: endPixels.y,
      duration: duration - delay,
      delay: delay,
      ease: 'Sine.easeInOut'
    });
  });
  
  // Wait for animations to complete
  await new Promise(resolve => setTimeout(resolve, duration));
}

/**
 * Animate side inbound pass - ball handler moves in backcourt, others shuffle
 */
async function animateSideInboundMovement({
  scene,
  offensivePlayers,
  defensivePlayers,
  ballHandler,
  ballSprite,
  isHomeOffense,
  duration
}) {
  
  // Ball handler moves in deep backcourt (can't cross half court line at X=50)
  const startX = ballHandler.gridX || 50;
  const startY = ballHandler.gridY || 25;
  
  // Constrain to deep backcourt
  let endX;
  if (isHomeOffense) {
    // Home offense: right side, max X = 49 (can't go left of center)
    endX = Math.max(51, Math.min(65, startX + (Math.random() * 10 - 5)));
  } else {
    // Away offense: left side, min X = 51 (can't go right of center)
    endX = Math.max(35, Math.min(49, startX + (Math.random() * 10 - 5)));
  }
  
  const endY = startY + (Math.random() * 8 - 4); // Vertical shuffle
  const endPixels = gridToPixels(endX, endY);
  
  // Animate ball handler
  scene.tweens.add({
    targets: ballHandler,
    x: endPixels.x,
    y: endPixels.y,
    duration: duration,
    ease: 'Sine.easeInOut'
  });
  
  // Animate ball with handler
  if (ballSprite) {
    scene.tweens.add({
      targets: ballSprite,
      x: endPixels.x,
      y: endPixels.y,
      duration: duration,
      ease: 'Sine.easeInOut'
    });
  }
  
  // Other 9 players shuffle organically (small random movements)
  const allOtherPlayers = [
    ...offensivePlayers.filter(p => p !== ballHandler),
    ...defensivePlayers
  ];
  
  allOtherPlayers.forEach((player, idx) => {
    const startPX = player.gridX || 50;
    const startPY = player.gridY || 25;
    
    // Small random shuffle
    const endPX = startPX + (Math.random() * 6 - 3);
    const endPY = startPY + (Math.random() * 6 - 3);
    
    const shufflePixels = gridToPixels(endPX, endPY);
    
    // Stagger for organic feel
    const delay = idx * 80;
    
    scene.tweens.add({
      targets: player,
      x: shufflePixels.x,
      y: shufflePixels.y,
      duration: duration - delay,
      delay: delay,
      ease: 'Sine.easeInOut'
    });
  });
  
  // Wait for animations to complete
  await new Promise(resolve => setTimeout(resolve, duration));
}

