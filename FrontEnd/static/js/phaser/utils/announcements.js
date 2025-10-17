/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 */

let currentAnnouncement = null;

/**
 * Show an announcement with pop-to-center animation
 * @param {string} text - Text to display (e.g., "Fast Break!", "It's Good!")
 * @param {string} team - 'home', 'away', 'defense', or 'neutral' for color styling
 */
export function showAnnouncement(text, team = 'home') {
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
  
  announcement.textContent = text;
  
  // Add to body
  document.body.appendChild(announcement);
  currentAnnouncement = announcement;
  
  // Trigger animation by adding active class after a frame
  requestAnimationFrame(() => {
    announcement.classList.add('active');
  });
  
  // Remove after animation completes (1000ms total)
  setTimeout(() => {
    if (announcement.parentElement) {
      announcement.remove();
    }
    if (currentAnnouncement === announcement) {
      currentAnnouncement = null;
    }
  }, 1000);
  
  console.log('📢 Announcement:', text, 'Team:', team);
}

/**
 * Determine and show announcement based on turn data
 * @param {Object} turnData - Turn data from backend
 * @param {string} timing - 'start' or 'end' of turn
 * @param {string} homeTeamId - Home team ID for determining team colors
 */
export function announceFromTurnData(turnData, timing = 'start', homeTeamId = null) {
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
      showAnnouncement("Foul!", 'neutral');
      return;
    }
    
    if (turnData.result_type === 'TURNOVER' && turnData.text?.toLowerCase().includes('steal')) {
      showAnnouncement("Steal!", defenseTeam);
      return;
    }
  }
}

