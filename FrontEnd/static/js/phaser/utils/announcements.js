/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 * Also triggers visual effects (red flash, sprite tint) for fouls/turnovers
 */

import { triggerFoulEffect, triggerTurnoverEffect, triggerMadeShotFlash } from '../animation/negativeActionEffects.js';

let currentAnnouncement = null;

/**
 * Trigger visual effects for fouls/turnovers
 * @param {Object} scene - Phaser scene
 * @param {string} playerId - Player ID to apply effect to
 * @param {string} effectType - 'foul' or 'turnover'
 */
function triggerVisualEffect(scene, playerId, effectType) {
  if (!scene || !playerId) return;
  
  const sprite = scene.playerSprites?.[playerId];
  if (!sprite) return;
  
  // Call the appropriate effect function
  if (effectType === 'foul') {
    triggerFoulEffect(scene, playerId);
  } else if (effectType === 'turnover') {
    triggerTurnoverEffect(scene, playerId);
  }
}

/**
 * Show AND-1 announcement with two rows (made shot + foul)
 * @param {string} team - Team that made the shot
 * @param {Object} shooterData - Shooter data { playerId, photo, teamName }
 * @param {Object} foulPlayerData - Fouling player data { playerId, photo, teamName }
 */
export function showAndOneAnnouncement(team, shooterData, foulPlayerData) {
  // Remove any existing announcement
  if (currentAnnouncement) {
    currentAnnouncement.remove();
    currentAnnouncement = null;
  }
  
  // Create announcement container with red background (foul overlay)
  const announcement = document.createElement('div');
  announcement.className = 'game-announcement and-one-announcement';
  announcement.style.display = 'flex';
  announcement.style.flexDirection = 'column';  // Vertical stacking
  announcement.style.alignItems = 'center';
  announcement.style.gap = '10px';
  announcement.style.backgroundColor = 'rgba(255, 0, 0, 0.85)';  // Red background at 85% opacity
  announcement.style.padding = '20px 30px';
  announcement.style.borderRadius = '12px';
  announcement.style.border = '3px solid rgba(255, 255, 255, 0.3)';  // Subtle white border
  announcement.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.5)';  // Strong shadow for depth
  if (team === 'home') {
    announcement.classList.add('home-team');
  } else if (team === 'away') {
    announcement.classList.add('away-team');
  }
  
  // Row 1: "IT'S GOOD!" + shooter headshot
  const row1 = document.createElement('div');
  row1.className = 'and-one-row-1';
  row1.style.display = 'flex';
  row1.style.alignItems = 'center';
  row1.style.justifyContent = 'center';
  row1.style.gap = '15px';
  
  const madeText = document.createElement('span');
  madeText.textContent = "IT'S GOOD!";
  madeText.style.fontSize = '2.5rem';
  madeText.style.fontWeight = 'bold';
  madeText.style.color = '#ffffff';  // White text on red background
  
  const shooterHeadshot = createHeadshotElement(shooterData, 1.0); // Full size
  
  row1.appendChild(madeText);
  row1.appendChild(shooterHeadshot);
  
  // Row 2: Foul player headshot + "←" + "FOUL" (yellow, smaller)
  const row2 = document.createElement('div');
  row2.className = 'and-one-row-2';
  row2.style.display = 'flex';
  row2.style.alignItems = 'center';
  row2.style.justifyContent = 'center';
  row2.style.gap = '10px';
  
  const foulHeadshot = createHeadshotElement(foulPlayerData, 1.0); // Full size (same as shooter)
  
  const arrow = document.createElement('span');
  arrow.textContent = '←';
  arrow.style.fontSize = '1.5rem';
  arrow.style.color = '#ffff00';
  arrow.style.fontWeight = 'bold';
  
  const foulText = document.createElement('span');
  foulText.textContent = "FOUL";
  foulText.style.fontSize = '1.5rem'; // 60% of 2.5rem
  foulText.style.fontWeight = 'bold';
  foulText.style.color = '#ffff00'; // Yellow
  
  row2.appendChild(foulHeadshot);
  row2.appendChild(arrow);
  row2.appendChild(foulText);
  
  announcement.appendChild(row1);
  announcement.appendChild(row2);
  
  // Add to body
  document.body.appendChild(announcement);
  currentAnnouncement = announcement;
  
  // Trigger animation
  requestAnimationFrame(() => {
    announcement.classList.add('active');
  });
  
  // Remove after animation completes
  setTimeout(() => {
    if (announcement.parentElement) {
      announcement.remove();
    }
    if (currentAnnouncement === announcement) {
      currentAnnouncement = null;
    }
  }, 2500);
}

/**
 * Helper to create headshot element
 * @param {Object} playerData - { playerId, photo, teamName }
 * @param {number} scale - Size multiplier (1.0 = full, 0.6 = 60%)
 */
function createHeadshotElement(playerData, scale = 1.0) {
  const container = document.createElement('div');
  container.className = 'announcement-headshot';
  container.style.width = `${60 * scale}px`;
  container.style.height = `${60 * scale}px`;
  container.style.flexShrink = '0';
  
  if (playerData.teamName) {
    const teamNameNormalized = playerData.teamName.toLowerCase().replace(/\s+/g, '-');
    container.style.backgroundImage = `url(/static/images/team-backgrounds/${teamNameNormalized}-background.png)`;
    container.style.backgroundSize = 'cover';
    container.style.backgroundPosition = 'center';
  }
  
  const img = document.createElement('img');
  img.src = playerData.photo || `/static/images/players/${playerData.playerId}.png`;
  img.alt = 'Player';
  img.style.width = '100%';
  img.style.height = '100%';
  img.style.objectFit = 'cover';
  img.onerror = () => {
    img.style.display = 'none';
  };
  container.appendChild(img);
  
  return container;
}

/**
 * Show an announcement with pop-to-center animation
 * @param {string} text - Text to display (e.g., "Fast Break!", "It's Good!")
 * @param {string} team - 'home', 'away', 'defense', or 'neutral' for color styling
 * @param {Object} playerData - Optional player data { playerId, photo, teamName } to show headshot
 */
export function showAnnouncement(text, team = 'home', playerData = null) {
  // Remove any existing announcement
  if (currentAnnouncement) {
    currentAnnouncement.remove();
    currentAnnouncement = null;
  }
  
  // Create announcement element
  const announcement = document.createElement('div');
  announcement.className = 'game-announcement';
  
  // Apply team-specific styling
  if (team === 'home') {
    announcement.classList.add('home-team');
  } else if (team === 'away') {
    announcement.classList.add('away-team');
  } else if (team === 'defense') {
    announcement.classList.add('defense-team');
  } else {
    announcement.classList.add('neutral');
  }
  
  // Add text first (so image appears on the right)
  const textSpan = document.createElement('span');
  textSpan.textContent = text;
  
  // Special styling for "DOUBLE TEAM!" - red text
  if (text === "DOUBLE TEAM!") {
    textSpan.style.color = '#ff0000'; // Red text
    textSpan.style.fontWeight = 'bold';
    textSpan.style.fontSize = '2.5rem';
  }
  
  announcement.appendChild(textSpan);
  
  // Add player headshot if provided (will appear after text)
  if (playerData && (playerData.photo || playerData.playerId)) {
    const headshotContainer = document.createElement('div');
    headshotContainer.className = 'announcement-headshot';
    
    // Set team background
    if (playerData.teamName) {
      const teamNameNormalized = playerData.teamName.toLowerCase().replace(/\s+/g, '-');
      headshotContainer.style.backgroundImage = `url(/static/images/team-backgrounds/${teamNameNormalized}-background.png)`;
      headshotContainer.style.backgroundSize = 'cover';
      headshotContainer.style.backgroundPosition = 'center';
    }
    
    const img = document.createElement('img');
    img.src = playerData.photo || `/static/images/players/${playerData.playerId}.png`;
    img.alt = 'Player';
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'cover';
    img.onerror = () => {
      img.style.display = 'none';
    };
    headshotContainer.appendChild(img);
    
    announcement.appendChild(headshotContainer);
  }
  
  // Add to body
  document.body.appendChild(announcement);
  currentAnnouncement = announcement;
  
  // Trigger animation by adding active class after a frame
  requestAnimationFrame(() => {
    announcement.classList.add('active');
  });
  
  // Remove after animation completes (2500ms total)
  setTimeout(() => {
    if (announcement.parentElement) {
      announcement.remove();
    }
    if (currentAnnouncement === announcement) {
      currentAnnouncement = null;
    }
  }, 2500);
  
}

/**
 * Determine and show announcement based on turn data
 * @param {Object} turnData - Turn data from backend
 * @param {string} timing - 'start' or 'end' of turn
 * @param {string} homeTeamId - Home team ID for determining team colors
 * @param {Object} scene - Optional scene object for accessing player data
 */
export function announceFromTurnData(turnData, timing = 'start', homeTeamId = null, scene = null) {
  // Determine which team triggered the event
  const offenseTeamId = turnData.possession_team_id || turnData.starting_possession_team_id;
  const isHomeTeamEvent = homeTeamId && String(offenseTeamId) === String(homeTeamId);
  const offenseTeam = isHomeTeamEvent ? 'home' : 'away';
  const defenseTeam = isHomeTeamEvent ? 'away' : 'home';
  
  if (timing === 'start') {
    // Announcements at turn start
    if (turnData.fast_break) {
      showAnnouncement("Fast Break!", offenseTeam);
      // Don't return - may have more announcements at end
    }
    
    // Check multiple ways FCP/HCT can be indicated
    // Note: Don't return after these - shots from Press/Trap should also announce results
    // ✅ FIX: Only announce when pressure is actually active, not when it's just being set up
    // next_defensive_setup indicates what will happen NEXT, not what's happening NOW
    // Only check next_defensive_setup for BASELINE_INBOUND turns (inbound passes that set up pressure)
    // For all other turns (HCO, MAKE, MISS, etc.), only check actual pressure flags (fcp_shot, hct_shot, fcp_foul, hct_foul)
    const isInboundSettingUpPressure = turnData.result_type === 'BASELINE_INBOUND';
    
    if (turnData.offensive_state === 'FCP' || turnData.fcp_foul || 
        turnData.result_type === 'FCP' || turnData.text?.includes('PRESS!') ||
        turnData.fcp_shot === true || (isInboundSettingUpPressure && turnData.next_defensive_setup === 'FCP')) {
      showAnnouncement("Press!", 'defense');
      // Don't return - may have shot result to announce later
    }
    
    if (turnData.offensive_state === 'HCT' || turnData.hct_foul || 
        turnData.result_type === 'HCT' || turnData.text?.includes('TRAP!') ||
        turnData.hct_shot === true || (isInboundSettingUpPressure && turnData.next_defensive_setup === 'HCT')) {
      showAnnouncement("Trap!", 'defense');
      // Don't return - may have shot result to announce later
    }
  } else if (timing === 'end') {
    // Announcements at turn end (after animation)
    // Note: "It's Good!" and "Rebound!" are now handled directly in ballManager.js
    // for precise timing when ball reaches rim/rebounder
    
    if (turnData.result_type === 'FOUL') {
      // Skip shooting fouls - they're already announced in ballManager.js with "And 1!" or "Shooting Foul!"
      const isShootingFoul = turnData?.text?.includes('AND-1') || 
                            (turnData?.text?.includes('fouls') && turnData?.text?.includes('on the shot'));
      
      if (!isShootingFoul) {
        // Non-shooting fouls: announce as "OFFENSIVE FOUL!" or "DEFENSIVE FOUL!"
        const foulTeam = turnData.foul_team || 'OFFENSE'; // Default to offense if not specified
        
        // Extract foul player data for headshot display
        let playerData = null;
        if (scene && turnData.foul_player_id) {
          const foulPlayerId = turnData.foul_player_id;
          const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
          const foulPlayerTeamId = foulPlayerSprite?.team_id;
          
          // Handle both new nested structure (object) and old flat structure (string)
          const homeTeamField = scene.simData?.home_team;
          const awayTeamField = scene.simData?.away_team;
          const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
          const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
          const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
          
          playerData = {
            playerId: foulPlayerId,
            photo: foulPlayerSprite?.photo || null,
            teamName: foulPlayerTeamName
          };
        }
        
        if (foulTeam === 'OFFENSE') {
          // Offensive foul - show in defense team color (they benefited)
          showAnnouncement("OFFENSIVE FOUL!", defenseTeam, playerData);
        } else {
          // Defensive foul - show in offense team color (they benefited)
          showAnnouncement("DEFENSIVE FOUL!", offenseTeam, playerData);
        }
        
        // Trigger visual effect on fouling player
        if (scene && turnData.foul_player_id) {
          triggerVisualEffect(scene, turnData.foul_player_id, 'foul');
        }
      }
      return;
    }
    
    // Handle STEAL announcements (result_type can be 'STEAL' from FCP/HCT or 'TURNOVER' from regular play)
    if (turnData.result_type === 'STEAL' || (turnData.result_type === 'TURNOVER' && turnData.text?.toLowerCase().includes('steal'))) {
      let playerData = null;
      
      if (scene && turnData.defender_id) {
        const stealerId = turnData.defender_id;
        const stealerSprite = scene.playerSprites?.[stealerId];
        const stealerTeamId = stealerSprite?.team_id;
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const stealerTeamName = stealerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
        
        playerData = {
          playerId: stealerId,
          photo: stealerSprite?.photo || null,
          teamName: stealerTeamName
        };
      }
      
      showAnnouncement("STEAL!", defenseTeam, playerData);
      
      // Trigger visual effect on turnover victim (ball handler who got stolen from)
      if (scene && turnData.victim_id) {
        triggerVisualEffect(scene, turnData.victim_id, 'turnover');
      }
      return;
    }
    
    // Handle all turnover types: TURNOVER, DEAD BALL (from HCT/FCP), and non-steal STEAL results
    if (turnData.result_type === 'TURNOVER' || turnData.result_type === 'DEAD BALL') {
      // Non-steal turnovers - show victim's photo in offense team color
      let playerData = null;
      
      if (scene && turnData.victim_id) {
        const victimId = turnData.victim_id;
        const victimSprite = scene.playerSprites?.[victimId];
        const victimTeamId = victimSprite?.team_id;
        
        // Handle both new nested structure (object) and old flat structure (string)
        const homeTeamField = scene.simData?.home_team;
        const awayTeamField = scene.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const victimTeamName = victimTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
        
        playerData = {
          playerId: victimId,
          photo: victimSprite?.photo || null,
          teamName: victimTeamName
        };
      }
      
      // Determine turnover type from dedicated field or text parsing
      let turnoverText = "TURNOVER!";
      
      // Check if backend provides specific turnover_type field
      if (turnData.turnover_type) {
        const typeMap = {
          "TRAVEL": "TRAVEL!",
          "DOUBLE_DRIBBLE": "DOUBLE DRIBBLE!",
          "OUT_OF_BOUNDS": "OUT OF BOUNDS!",
          "BAD_PASS": "BAD PASS!",
          "PALMING": "PALMING!",
          "ILLEGAL_DRIBBLE": "ILLEGAL DRIBBLE!",
          "SHOT_CLOCK": "SHOT CLOCK VIOLATION!",
          "BACKCOURT": "BACKCOURT VIOLATION!"
        };
        turnoverText = typeMap[turnData.turnover_type] || "TURNOVER!";
      } else {
        // Fallback: parse from text
        const textLower = turnData.text?.toLowerCase() || '';
        if (textLower.includes('travel')) {
          turnoverText = "TRAVEL!";
        } else if (textLower.includes('double dribble')) {
          turnoverText = "DOUBLE DRIBBLE!";
        } else if (textLower.includes('out of bounds')) {
          turnoverText = "OUT OF BOUNDS!";
        } else if (textLower.includes('errant pass') || textLower.includes('bad pass')) {
          turnoverText = "BAD PASS!";
        } else if (textLower.includes('dribbles it off his foot')) {
          turnoverText = "TURNOVER!";
        } else if (textLower.includes('shot clock')) {
          turnoverText = "SHOT CLOCK VIOLATION!";
        }
      }
      
      console.log(`📢 Announcing turnover: ${turnoverText} (result_type: ${turnData.result_type}, source: ${turnData.offensive_state || 'HCO'})`);
      showAnnouncement(turnoverText, offenseTeam, playerData);
      
      // Trigger visual effect on turnover victim
      if (scene && turnData.victim_id) {
        triggerVisualEffect(scene, turnData.victim_id, 'turnover');
      }
      return;
    }
  }
}

