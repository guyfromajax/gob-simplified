/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 */

let currentAnnouncement = null;

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
  
  console.log('📢 Announcement:', text, 'Team:', team, 'Player:', playerData?.playerId || 'none');
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
  console.log('🔔 announceFromTurnData:', { 
    timing, 
    result_type: turnData.result_type,
    offensive_state: turnData.offensive_state,
    fast_break: turnData.fast_break,
    fcp_foul: turnData.fcp_foul,
    hct_foul: turnData.hct_foul,
    fcp_shot: turnData.fcp_shot,
    hct_shot: turnData.hct_shot
  });
  
  if (timing === 'start') {
    // Announcements at turn start
    if (turnData.fast_break) {
      showAnnouncement("Fast Break!", offenseTeam);
      // Don't return - may have more announcements at end
    }
    
    // Check multiple ways FCP/HCT can be indicated
    // Note: Don't return after these - shots from Press/Trap should also announce results
    if (turnData.offensive_state === 'FCP' || turnData.fcp_foul || 
        turnData.result_type === 'FCP' || turnData.text?.includes('PRESS!')) {
      showAnnouncement("Press!", 'defense');
      // Don't return - may have shot result to announce later
    }
    
    if (turnData.offensive_state === 'HCT' || turnData.hct_foul || 
        turnData.result_type === 'HCT' || turnData.text?.includes('TRAP!')) {
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
        
        if (foulTeam === 'OFFENSE') {
          // Offensive foul - show in defense team color (they benefited)
          showAnnouncement("OFFENSIVE FOUL!", defenseTeam);
        } else {
          // Defensive foul - show in offense team color (they benefited)
          showAnnouncement("DEFENSIVE FOUL!", offenseTeam);
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
        const stealerTeamName = stealerTeamId === scene.homeTeamId ? scene.simData?.home_team : scene.simData?.away_team;
        
        playerData = {
          playerId: stealerId,
          photo: stealerSprite?.photo || null,
          teamName: stealerTeamName
        };
      }
      
      showAnnouncement("STEAL!", defenseTeam, playerData);
      return;
    }
    
    if (turnData.result_type === 'TURNOVER') {
      // Non-steal turnovers only from here on
      
      // Non-steal turnovers (TRAVEL, DOUBLE DRIBBLE, etc.) - show victim's photo in offense team color
      let playerData = null;
      
      if (scene && turnData.victim_id) {
        const victimId = turnData.victim_id;
        const victimSprite = scene.playerSprites?.[victimId];
        const victimTeamId = victimSprite?.team_id;
        const victimTeamName = victimTeamId === scene.homeTeamId ? scene.simData?.home_team : scene.simData?.away_team;
        
        playerData = {
          playerId: victimId,
          photo: victimSprite?.photo || null,
          teamName: victimTeamName
        };
      }
      
      // Determine turnover type from text
      let turnoverText = "TURNOVER!";
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
      }
      
      showAnnouncement(turnoverText, offenseTeam, playerData);
      return;
    }
  }
}

