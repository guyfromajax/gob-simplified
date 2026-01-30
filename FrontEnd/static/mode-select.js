const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentBtn = document.getElementById('tournament-btn');
const franchiseBtn = document.getElementById('franchise-btn');

if (scrimmageBtn) {
  scrimmageBtn.addEventListener('click', () => {
    window.location.href = './scrimmage-select.html';
  });
}

if (tournamentBtn) {
  tournamentBtn.addEventListener('click', () => {
    window.location.href = './tournament-select.html';
  });
}

if (franchiseBtn) {
  franchiseBtn.addEventListener('click', () => {
    window.location.href = './franchise-select-team.html';
  });
}

// ⏸️ TABLED: Resume Last Game feature - Exact game state restoration
// TODO: Revisit after Phase 1.3+ and site go-live priorities complete
// See: docs/To Do/resume_last_game_exact_state.md
/*
// ✅ PHASE 1.2: Check for saved game and show Resume Last Game section
async function checkForSavedGame() {
  const resumeSection = document.getElementById('resume-game-section');
  const resumeTeams = document.getElementById('resume-teams');
  const resumeScore = document.getElementById('resume-score');
  const resumeQuarter = document.getElementById('resume-quarter');
  const resumeBtn = document.getElementById('resume-game-btn');
  
  if (!resumeSection || !resumeTeams || !resumeScore || !resumeQuarter || !resumeBtn) {
    return; // Elements not found, skip resume feature
  }
  
  // Check localStorage for saved game_id
  const lastGameId = typeof localStorage !== 'undefined' ? localStorage.getItem('last_game_id') : null;
  
  if (!lastGameId) {
    resumeSection.style.display = 'none';
    return; // No saved game
  }
  
  try {
    // Fetch game document to verify it exists and is active
    const gameRes = await fetch(API_CONFIG.buildUrl(`/api/game/${lastGameId}`));
    
    if (!gameRes.ok) {
      // Game not found or error - clear saved game_id and user_team_side
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('last_game_id');
        localStorage.removeItem('last_game_user_team_side');
      }
      resumeSection.style.display = 'none';
      return;
    }
    
    const gameData = await gameRes.json();
    
    // Extract game info
    const homeTeam = gameData.home_team?.name || gameData.teams?.[gameData.home_team_id]?.name || 'Home';
    const awayTeam = gameData.away_team?.name || gameData.teams?.[gameData.away_team_id]?.name || 'Away';
    
    // Get scores from score object (keys are team names)
    const homeScore = gameData.score?.[homeTeam] || gameData.home_team?.score || 0;
    const awayScore = gameData.score?.[awayTeam] || gameData.away_team?.score || 0;
    const quarter = gameData.quarter || 1;
    
    // Determine period label (Q1-Q4, OT1, OT2, etc.)
    let period = `Q${quarter}`;
    if (quarter > 4) {
      period = `OT${quarter - 4}`;
    }
    
    const clock = gameData.clock || '0:00';
    
    // Check if game is likely final (quarter > 4 and clock is 0:00, or quarter is very high)
    // Note: We can't reliably detect final from this endpoint, but we can make reasonable assumptions
    const isLikelyFinal = (quarter > 4 && clock === '0:00') || quarter > 10;
    
    if (isLikelyFinal) {
      // Game is likely complete - clear saved game_id and user_team_side
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('last_game_id');
        localStorage.removeItem('last_game_user_team_side');
      }
      resumeSection.style.display = 'none';
      return;
    }
    
    // Display game info
    resumeTeams.textContent = `${homeTeam} vs ${awayTeam}`;
    resumeScore.textContent = `${homeScore} - ${awayScore}`;
    resumeQuarter.textContent = `${period}, ${clock} remaining`;
    
    // Get user_team_side from localStorage (saved when game was quit)
    const userTeamSide = typeof localStorage !== 'undefined' ? localStorage.getItem('last_game_user_team_side') : null;
    
    // Set up resume button
    resumeBtn.onclick = () => {
      // Clear saved game_id and user_team_side (one-time use)
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('last_game_id');
        localStorage.removeItem('last_game_user_team_side');
      }
      // Build URL with all required parameters
      const params = new URLSearchParams({
        game_id: lastGameId,
        resume_from_timeout: 'true',
        mode: 'single',
        home: homeTeam,
        away: awayTeam,
        quarter: quarter.toString(),
        period: period
      });
      // Add user_team_side if we have it
      if (userTeamSide) {
        params.set('my_team', userTeamSide);
      }
      // Navigate to lineup screen
      window.location.href = `/set-lineup.html?${params.toString()}`;
    };
    
    // Show resume section
    resumeSection.style.display = 'block';
  } catch (error) {
    console.error('Error checking for saved game:', error);
    resumeSection.style.display = 'none';
    // Clear invalid saved game_id and user_team_side
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('last_game_id');
      localStorage.removeItem('last_game_user_team_side');
    }
  }
}
*/

document.addEventListener('DOMContentLoaded', async () => {
  // ============================================================================
  // ALPHA MODE CONFIGURATION
  // ============================================================================
  // Load app config and show alpha badge/disclaimer if in alpha mode
  try {
    const appConfig = await API_CONFIG.loadAppConfig();
    if (appConfig.isAlpha) {
      const alphaBadge = document.getElementById('alpha-badge');
      const alphaDisclaimer = document.getElementById('alpha-disclaimer');
      if (alphaBadge) alphaBadge.classList.add('visible');
      if (alphaDisclaimer) alphaDisclaimer.classList.add('visible');
      console.log('[ALPHA] Alpha mode enabled');
    }
  } catch (error) {
    console.error('[ALPHA] Failed to load app config:', error);
  }
  
  // ============================================================================
  // AUTHENTICATION STATE
  // ============================================================================
  const authLoggedOut = document.getElementById('auth-logged-out');
  const authLoggedIn = document.getElementById('auth-logged-in');
  const authUserEmail = document.getElementById('auth-user-email');
  const logoutBtn = document.getElementById('logout-btn');
  
  // Check if user is logged in
  const authToken = localStorage.getItem('auth_token');
  const authUser = localStorage.getItem('auth_user');
  
  if (authToken && authUser) {
    try {
      const user = JSON.parse(authUser);
      // Show logged-in state
      if (authLoggedOut) authLoggedOut.style.display = 'none';
      if (authLoggedIn) authLoggedIn.style.display = 'flex';
      if (authUserEmail) authUserEmail.textContent = user.email;
      console.log('[AUTH] User logged in:', user.email);
    } catch (e) {
      console.error('[AUTH] Failed to parse user:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
    }
  }
  
  // Handle logout
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        // Call logout endpoint (optional, since JWT is stateless)
        await fetch(API_CONFIG.buildUrl('/api/auth/logout'), { method: 'POST' });
      } catch (e) {
        // Ignore errors - logout should work client-side regardless
      }
      
      // Clear local storage
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      
      // Update UI
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
      
      console.log('[AUTH] User logged out');
    });
  }
  
  // ⏸️ TABLED: Resume Last Game feature - Exact game state restoration
  // TODO: Revisit after Phase 1.3+ and site go-live priorities complete
  // See: docs/To Do/resume_last_game_exact_state.md
  // checkForSavedGame();
  
  const teamButtons = document.querySelectorAll('.team-button');
  const modeContainer = document.querySelector('.mode-container');
  const teamGrid = document.getElementById('team-grid');
  const syncTeamGridWidth = () => {
    if (modeContainer && teamGrid) {
      teamGrid.style.width = `${modeContainer.offsetWidth}px`;
    }
  };
  window.addEventListener('resize', syncTeamGridWidth);
  syncTeamGridWidth();
  const taglines = {
    'Bentley-Truman': 'Top-Shelf Talent',
    'Lancaster': 'Muscle & Defense',
    'Four Corners': 'Hustle & Attitude',
    'Ocean City': 'Sharpshooters Galore',
    'Morristown': 'Perfectly Balanced',
    'Little York': 'Wicked Smart',
    'Xavien': 'Youthful Exuberance',
    'South Lancaster': 'Us vs The World'
  };

  teamButtons.forEach(btn => {
    const team = btn.dataset.team;

    const taglineEl = btn.querySelector('.team-tagline');
    if (taglineEl && taglines[team]) {
      taglineEl.textContent = taglines[team];
    }

    btn.addEventListener('click', () => {
      // Link to team roster view page with Grid/Player view toggle
      window.location.href = `/team-roster-view.html?team_name=${encodeURIComponent(team)}&return_url=${encodeURIComponent(window.location.pathname)}`;
    });
  });

  const fallbackColor = '#ccc';
  fetch(API_CONFIG.buildUrl('/teams'))
    .then(resp => resp.json())
    .then(teamData => {
      const colorMap = {};
      teamData.forEach(t => {
        colorMap[t.name] = {
          primary: t.primary_color,
          secondary: t.secondary_color
        };
      });

      teamButtons.forEach(btn => {
        const team = btn.dataset.team;
        const taglineEl = btn.querySelector('.team-tagline');
        const colors = colorMap[team] || {};
        const bgColor = colors.primary || fallbackColor;
        const borderColor = colors.secondary || fallbackColor;
        const taglineColor = colors.primary ? '#fff' : '#000';
        btn.style.backgroundColor = bgColor;
        btn.style.borderColor = borderColor;
        if (taglineEl) taglineEl.style.color = taglineColor;
        console.log(`Tile ${team} bgColor: ${bgColor} borderColor: ${borderColor}`);
      });
    })
    .catch(() => {
      teamButtons.forEach(btn => {
        const taglineEl = btn.querySelector('.team-tagline');
        btn.style.borderColor = fallbackColor;
        btn.style.backgroundColor = fallbackColor;
        if (taglineEl) taglineEl.style.color = '#000';
        console.log(`Tile ${btn.dataset.team} bgColor: ${fallbackColor} (fallback)`);
      });
    });
});
