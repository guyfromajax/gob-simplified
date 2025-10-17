/**
 * Announcement system for significant game events
 * Shows animated text that pops from scoreboard to center screen
 */

let currentAnnouncement = null;

/**
 * Show an announcement with pop-to-center animation
 * @param {string} text - Text to display (e.g., "Fast Break!", "It's Good!")
 */
export function showAnnouncement(text) {
  // Remove any existing announcement
  if (currentAnnouncement) {
    currentAnnouncement.remove();
    currentAnnouncement = null;
  }
  
  // Create announcement element
  const announcement = document.createElement('div');
  announcement.className = 'game-announcement';
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
  
  console.log('📢 Announcement:', text);
}

/**
 * Determine and show announcement based on turn data
 * @param {Object} turnData - Turn data from backend
 * @param {string} timing - 'start' or 'end' of turn
 */
export function announceFromTurnData(turnData, timing = 'start') {
  if (timing === 'start') {
    // Announcements at turn start
    if (turnData.fast_break) {
      showAnnouncement("Fast Break!");
      return;
    }
    
    if (turnData.offensive_state === 'FCP') {
      showAnnouncement("Press!");
      return;
    }
    
    if (turnData.offensive_state === 'HCT') {
      showAnnouncement("Trap!");
      return;
    }
  } else if (timing === 'end') {
    // Announcements at turn end (after animation)
    if (turnData.result_type === 'MAKE' || turnData.result_type === 'PUTBACK_MAKE') {
      showAnnouncement("It's Good!");
      return;
    }
    
    if (turnData.result_type === 'MISS' || turnData.result_type === 'PUTBACK_MISS') {
      showAnnouncement("Miss!");
      // Check for rebound announcement
      setTimeout(() => {
        if (turnData.rebound_type) {
          showAnnouncement("Rebound!");
        }
      }, 200); // Small delay so it shows after "Miss!"
      return;
    }
    
    if (turnData.result_type === 'TURNOVER' && turnData.text?.toLowerCase().includes('steal')) {
      showAnnouncement("Steal!");
      return;
    }
  }
}

