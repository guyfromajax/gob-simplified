/**
 * Countdown Animation Module
 * 
 * Animates players during the 5-second clipboard countdown window.
 * Creates organic, varied movements so players don't freeze during user decision time.
 */

import { gridToPixels } from '../utils/gridToPixels.js';

// Basketball court position targets (grid coordinates)
// Away offense attacks toward X=9, Home offense attacks toward X=91
const COURT_POSITIONS = {
  // Offensive target spots (spread around offensive end)
  offense: {
    topLane: { x: 42, y: 25 },
    upperWing: { x: 36, y: 15 },
    lowerWing: { x: 36, y: 35 },
    upperApex: { x: 30, y: 10 },
    lowerApex: { x: 30, y: 40 },
    upperHighPost: { x: 45, y: 18 },
    lowerHighPost: { x: 45, y: 32 },
    upperMidPost: { x: 38, y: 20 },
    lowerMidPost: { x: 38, y: 30 }
  },
  // Defensive target spots (near the basket they're protecting)
  defense: {
    rim: { x: 91, y: 25 },
    lowerLowPost: { x: 88, y: 30 },
    upperLowPost: { x: 88, y: 20 },
    lowerMidPost: { x: 85, y: 28 },
    upperMidPost: { x: 85, y: 22 },
    midLane: { x: 78, y: 25 }
  }
};

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
  
  // Debug: Log basket positions
  const targetBasket = isHomeOffense ? 9 : 91; // Home attacks X=9, Away attacks X=91
  console.log(`🏀 Target basket: ${isHomeOffense ? 'Home' : 'Away'} offense attacks X=${targetBasket}, ${isHomeOffense ? 'Away' : 'Home'} defense protects X=${targetBasket}`);
  
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
  
  // Ball handler advances up court toward offensive end
  const ballHandlerStartX = ballHandler.gridX || 50;
  const ballHandlerStartY = ballHandler.gridY || 25;
  
  // Target: About 3/4 court toward offensive basket
  const ballHandlerTargetX = isHomeOffense ? 30 : 70; // Move toward offensive end
  const ballHandlerTargetY = 25 + (Math.random() * 6 - 3); // Slight vertical drift
  
  const ballHandlerPixels = gridToPixels(ballHandlerTargetX, ballHandlerTargetY);
  
  // Animate ball handler
  scene.tweens.add({
    targets: ballHandler,
    x: ballHandlerPixels.x,
    y: ballHandlerPixels.y,
    duration: duration,
    ease: 'Linear'
  });
  
  // Animate ball with handler
  if (ballSprite) {
    scene.tweens.add({
      targets: ballSprite,
      x: ballHandlerPixels.x,
      y: ballHandlerPixels.y,
      duration: duration,
      ease: 'Linear'
    });
  }
  
  // Offensive teammates move to spots near offensive basket
  const offensiveTargets = Object.values(COURT_POSITIONS.offense);
  offensivePlayers.forEach((player, idx) => {
    if (player === ballHandler) return; // Skip ball handler
    
    // Pick a random offensive target spot
    const targetSpot = offensiveTargets[Math.floor(Math.random() * offensiveTargets.length)];
    
    // Move 1-10 X spots toward offensive basket from target
    const xOffset = 1 + Math.random() * 9;
    const yOffset = (Math.random() * 14) - 7; // ±7 Y from target
    
    let endX, endY;
    if (isHomeOffense) {
      // Home offense attacks left (toward X=9), so mirror X positions
      const mirroredTargetX = 100 - targetSpot.x;
      endX = mirroredTargetX - xOffset; // Move closer to X=9
      endY = targetSpot.y + yOffset;
    } else {
      // Away offense attacks right (toward X=91)
      endX = targetSpot.x + xOffset; // Move closer to X=91
      endY = targetSpot.y + yOffset;
    }
    
    const endPixels = gridToPixels(endX, endY);
    
    // Stagger animations for organic feel
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
  
  // Defensive players move to spots near THEIR basket (the one they're protecting)
  const defensiveTargetsList = ['rim', 'lowerLowPost', 'upperLowPost', 'lowerMidPost', 'upperMidPost', 'midLane'];
  
  defensivePlayers.forEach((player, idx) => {
    // Pick a random defensive spot name
    const targetSpotName = defensiveTargetsList[Math.floor(Math.random() * defensiveTargetsList.length)];
    const targetSpot = COURT_POSITIONS.defense[targetSpotName];
    
    // Move 1-10 X spots away from basket (toward center, to avoid out of bounds)
    const xOffset = 1 + Math.random() * 9;
    const yOffset = (Math.random() * 14) - 7; // ±7 Y from target
    
    let endX, endY;
    if (isHomeOffense) {
      // Home offense attacks X=9, so away defense protects X=9 (left side)
      // Use MIRRORED defensive positions (flip from X=91 to X=9)
      const awayBasketX = 9;
      const mirroredTargetX = 100 - targetSpot.x; // 91→9, 88→12, 85→15, 78→22
      endX = mirroredTargetX + xOffset; // Move away from X=9 toward center
      endY = targetSpot.y + yOffset;
      console.log(`🛡️ Defender ${idx}: target=${targetSpotName}, mirroredX=${mirroredTargetX}, offset=${xOffset.toFixed(1)}, finalX=${endX.toFixed(1)} (protecting X=9)`);
    } else {
      // Away offense attacks X=91, so home defense protects X=91 (right side)
      // Use original defensive positions (already at X=91)
      const homeBasketX = 91;
      endX = targetSpot.x - xOffset; // Move away from X=91 toward center
      endY = targetSpot.y + yOffset;
      console.log(`🛡️ Defender ${idx}: target=${targetSpotName}, targetX=${targetSpot.x}, offset=${xOffset.toFixed(1)}, finalX=${endX.toFixed(1)} (protecting X=91)`);
    }
    
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
 * Animate side inbound pass - ball handler surveys in backcourt, others move to positions
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
  
  // Ball handler stays in deep backcourt, surveys the situation
  const startX = ballHandler.gridX || 50;
  const startY = ballHandler.gridY || 25;
  
  // Stay in deep backcourt (can't cross half court line at X=50)
  let endX;
  if (isHomeOffense) {
    // Home offense: right side, stay right of center (X > 50)
    endX = Math.max(55, Math.min(70, startX + (Math.random() * 10 - 5)));
  } else {
    // Away offense: left side, stay left of center (X < 50)
    endX = Math.max(30, Math.min(45, startX + (Math.random() * 10 - 5)));
  }
  
  const endY = startY + (Math.random() * 8 - 4); // Vertical shuffle
  const ballHandlerPixels = gridToPixels(endX, endY);
  
  // Animate ball handler
  scene.tweens.add({
    targets: ballHandler,
    x: ballHandlerPixels.x,
    y: ballHandlerPixels.y,
    duration: duration,
    ease: 'Sine.easeInOut'
  });
  
  // Animate ball with handler
  if (ballSprite) {
    scene.tweens.add({
      targets: ballSprite,
      x: ballHandlerPixels.x,
      y: ballHandlerPixels.y,
      duration: duration,
      ease: 'Sine.easeInOut'
    });
  }
  
  // Offensive teammates move to spots near offensive basket (same as DREB/IP)
  const offensiveTargets = Object.values(COURT_POSITIONS.offense);
  offensivePlayers.forEach((player, idx) => {
    if (player === ballHandler) return; // Skip ball handler
    
    // Pick a random offensive target spot
    const targetSpot = offensiveTargets[Math.floor(Math.random() * offensiveTargets.length)];
    
    // Move 1-10 X spots toward offensive basket from target
    const xOffset = 1 + Math.random() * 9;
    const yOffset = (Math.random() * 14) - 7; // ±7 Y from target
    
    let endX, endY;
    if (isHomeOffense) {
      // Home offense attacks left (toward X=9), so mirror X positions
      const mirroredTargetX = 100 - targetSpot.x;
      endX = mirroredTargetX - xOffset; // Move closer to X=9
      endY = targetSpot.y + yOffset;
    } else {
      // Away offense attacks right (toward X=91)
      endX = targetSpot.x + xOffset; // Move closer to X=91
      endY = targetSpot.y + yOffset;
    }
    
    const endPixels = gridToPixels(endX, endY);
    
    // Stagger animations for organic feel
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
  
  // Defensive players move to spots near THEIR basket (same as DREB/IP)
  const defensiveTargetsList = ['rim', 'lowerLowPost', 'upperLowPost', 'lowerMidPost', 'upperMidPost', 'midLane'];
  
  defensivePlayers.forEach((player, idx) => {
    // Pick a random defensive spot name
    const targetSpotName = defensiveTargetsList[Math.floor(Math.random() * defensiveTargetsList.length)];
    const targetSpot = COURT_POSITIONS.defense[targetSpotName];
    
    // Move 1-10 X spots away from basket (toward center, to avoid out of bounds)
    const xOffset = 1 + Math.random() * 9;
    const yOffset = (Math.random() * 14) - 7; // ±7 Y from target
    
    let endX, endY;
    if (isHomeOffense) {
      // Home offense attacks X=9, so away defense protects X=9 (left side)
      // Use MIRRORED defensive positions (flip from X=91 to X=9)
      const awayBasketX = 9;
      const mirroredTargetX = 100 - targetSpot.x; // 91→9, 88→12, 85→15, 78→22
      endX = mirroredTargetX + xOffset; // Move away from X=9 toward center
      endY = targetSpot.y + yOffset;
      console.log(`🛡️ SIP Defender ${idx}: target=${targetSpotName}, mirroredX=${mirroredTargetX}, offset=${xOffset.toFixed(1)}, finalX=${endX.toFixed(1)} (protecting X=9)`);
    } else {
      // Away offense attacks X=91, so home defense protects X=91 (right side)
      // Use original defensive positions (already at X=91)
      const homeBasketX = 91;
      endX = targetSpot.x - xOffset; // Move away from X=91 toward center
      endY = targetSpot.y + yOffset;
      console.log(`🛡️ SIP Defender ${idx}: target=${targetSpotName}, targetX=${targetSpot.x}, offset=${xOffset.toFixed(1)}, finalX=${endX.toFixed(1)} (protecting X=91)`);
    }
    
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

