const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentPlayNowBtn = document.getElementById('tournament-play-now-btn');
const tournamentNewBtn = document.getElementById('tournament-new-btn');
const franchisePlayNowBtn = document.getElementById('franchise-play-now-btn');
const franchiseNewBtn = document.getElementById('franchise-new-btn');

// Current instance data (set after fetch in DOMContentLoaded)
let currentTournament = null;
let currentFranchise = null;

function tournamentRoundLabel(roundNum, completed) {
  if (completed) return 'Complete';
  if (roundNum === 1) return 'First Round';
  if (roundNum === 2) return 'Semis';
  if (roundNum === 3) return 'Championship';
  return 'First Round';
}

function franchiseStatusLabel(data) {
  if (!data) return '--';
  if (data.eos_tournament_active) {
    if (data.eos_completed) return 'Offseason';
    const r = data.eos_current_round || 1;
    if (r === 1) return 'First Round';
    if (r === 2) return 'Semis';
    if (r === 3) return 'Championship';
    return 'First Round';
  }
  const week = data.week != null ? data.week : 1;
  return `Week ${week}`;
}

if (scrimmageBtn) {
  scrimmageBtn.addEventListener('click', () => {
    window.location.href = './scrimmage-select.html';
  });
}

// Tournament: Play Now → TCC (or resolved TCC when completed; same URL)
if (tournamentPlayNowBtn) {
  tournamentPlayNowBtn.addEventListener('click', () => {
    if (currentTournament && currentTournament._id) {
      window.location.href = `./tournament.html?tournament_id=${encodeURIComponent(currentTournament._id)}`;
    } else {
      window.location.href = './tournament-select.html';
    }
  });
}

// Tournament: New Tournament — show confirmation if user has existing tournament (functionality wired later)
const newTournamentModal = document.getElementById('new-tournament-modal');
const newTournamentDontShowAgain = document.getElementById('new-tournament-dont-show-again');
const newTournamentModalCancel = document.getElementById('new-tournament-modal-cancel');
const newTournamentModalConfirm = document.getElementById('new-tournament-modal-confirm');
const DONT_SHOW_NEW_TOURNAMENT_WARNING_KEY = 'gob_dont_show_new_tournament_warning';

function openNewTournamentModal() {
  if (newTournamentModal) newTournamentModal.style.display = 'flex';
}
function closeNewTournamentModal() {
  if (newTournamentModal) newTournamentModal.style.display = 'none';
}
function goToNewTournament() {
  window.location.href = './tournament-select.html';
}

if (tournamentNewBtn) {
  tournamentNewBtn.addEventListener('click', () => {
    const dontShow = typeof localStorage !== 'undefined' && localStorage.getItem(DONT_SHOW_NEW_TOURNAMENT_WARNING_KEY) === '1';
    const hasExistingTournament = !!currentTournament;
    if (hasExistingTournament && !dontShow) {
      openNewTournamentModal();
    } else {
      goToNewTournament();
    }
  });
}

if (newTournamentModalCancel) {
  newTournamentModalCancel.addEventListener('click', closeNewTournamentModal);
}
if (newTournamentModalConfirm) {
  newTournamentModalConfirm.addEventListener('click', () => {
    if (newTournamentDontShowAgain && newTournamentDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_TOURNAMENT_WARNING_KEY, '1');
    }
    closeNewTournamentModal();
    goToNewTournament();
  });
}

// Franchise: Play Now → FCC (or resolved FCC when in end state; same URL)
if (franchisePlayNowBtn) {
  franchisePlayNowBtn.addEventListener('click', () => {
    if (currentFranchise && currentFranchise.franchise_id) {
      window.location.href = `./franchise-command-center.html?franchise_id=${encodeURIComponent(currentFranchise.franchise_id)}`;
    } else {
      window.location.href = './franchise-select-team.html';
    }
  });
}

// Franchise: New Franchise — show confirmation if user has existing franchise
const newFranchiseModal = document.getElementById('new-franchise-modal');
const newFranchiseDontShowAgain = document.getElementById('new-franchise-dont-show-again');
const newFranchiseModalCancel = document.getElementById('new-franchise-modal-cancel');
const newFranchiseModalConfirm = document.getElementById('new-franchise-modal-confirm');
const DONT_SHOW_NEW_FRANCHISE_WARNING_KEY = 'gob_dont_show_new_franchise_warning';

function openNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'flex';
}
function closeNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'none';
}
function goToNewFranchise() {
  window.location.href = './franchise-select-team.html';
}

if (franchiseNewBtn) {
  franchiseNewBtn.addEventListener('click', () => {
    const dontShow = typeof localStorage !== 'undefined' && localStorage.getItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY) === '1';
    const hasExistingFranchise = !!currentFranchise;
    if (hasExistingFranchise && !dontShow) {
      openNewFranchiseModal();
    } else {
      goToNewFranchise();
    }
  });
}

if (newFranchiseModalCancel) {
  newFranchiseModalCancel.addEventListener('click', closeNewFranchiseModal);
}
if (newFranchiseModalConfirm) {
  newFranchiseModalConfirm.addEventListener('click', () => {
    if (newFranchiseDontShowAgain && newFranchiseDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY, '1');
    }
    closeNewFranchiseModal();
    goToNewFranchise();
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
    const gameRes = await fetch(API_CONFIG.buildUrl(`/api/game/${lastGameId}`), { headers: API_CONFIG.getAuthHeaders() });
    
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
  let needsUsername = false;

  if (authToken && authUser) {
    try {
      const user = JSON.parse(authUser);
      // Show logged-in state
      if (authLoggedOut) authLoggedOut.style.display = 'none';
      if (authLoggedIn) authLoggedIn.style.display = 'flex';
      if (authUserEmail) authUserEmail.textContent = user.username || user.email;
      console.log('[AUTH] User logged in:', user.email);

      // Check if user needs to set username (fetch fresh from API)
      const meRes = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (!meData.username || meData.username.trim() === '') {
          needsUsername = true;
        } else {
          if (authUserEmail) authUserEmail.textContent = meData.username;
          const stored = JSON.parse(authUser);
          stored.username = meData.username;
          localStorage.setItem('auth_user', JSON.stringify(stored));
        }
      }
    } catch (e) {
      console.error('[AUTH] Failed to parse user:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
    }
  }

  // Show set-username modal if needed (blocks mode-select until username is set)
  const setUsernameModal = document.getElementById('set-username-modal');
  const setUsernameInput = document.getElementById('set-username-input');
  const setUsernameSubmit = document.getElementById('set-username-submit');
  const setUsernameError = document.getElementById('set-username-error');

  if (needsUsername && setUsernameModal) {
    setUsernameModal.style.display = 'flex';

    const submitUsername = async () => {
      const raw = setUsernameInput.value.trim();
      if (!raw) {
        setUsernameError.textContent = 'Please enter a username';
        return;
      }
      if (/\s/.test(raw)) {
        setUsernameError.textContent = 'Username cannot contain spaces';
        return;
      }
      if (raw.length < 3) {
        setUsernameError.textContent = 'Username must be at least 3 characters';
        return;
      }
      if (raw.length > 24) {
        setUsernameError.textContent = 'Username must be at most 24 characters';
        return;
      }
      if (!/^[a-zA-Z0-9_]+$/.test(raw)) {
        setUsernameError.textContent = 'Username can only contain letters, numbers, and underscores';
        return;
      }

      setUsernameError.textContent = '';
      setUsernameSubmit.disabled = true;

      try {
        const res = await fetch(API_CONFIG.buildUrl('/api/auth/set-username'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...API_CONFIG.getAuthHeaders() },
          body: JSON.stringify({ username: raw })
        });
        const data = await res.json();

        if (!res.ok) {
          setUsernameError.textContent = data.detail || 'Could not set username';
          setUsernameSubmit.disabled = false;
          return;
        }

        // Update localStorage and auth bar
        const stored = JSON.parse(localStorage.getItem('auth_user') || '{}');
        stored.username = data.username;
        localStorage.setItem('auth_user', JSON.stringify(stored));
        if (authUserEmail) authUserEmail.textContent = data.username;

        setUsernameModal.style.display = 'none';
      } catch (err) {
        setUsernameError.textContent = err.message || 'Something went wrong';
      } finally {
        setUsernameSubmit.disabled = false;
      }
    };

    setUsernameSubmit.addEventListener('click', submitUsername);
    setUsernameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitUsername();
    });
    setUsernameInput.focus();
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

  // Fetch current tournament and franchise (auth required; 404 = none)
  const headers = API_CONFIG.getAuthHeaders();
  const [tournamentRes, franchiseRes] = await Promise.all([
    fetch(API_CONFIG.buildUrl('/tournament/current'), { headers }).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(API_CONFIG.buildUrl('/franchise/current'), { headers }).then(r => r.ok ? r.json() : null).catch(() => null)
  ]);
  currentTournament = tournamentRes;
  currentFranchise = franchiseRes;

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

      // Render Tournament and Franchise instance cards from API data
      const tEl = document.getElementById('tournament-instance');
      const tTeamEl = document.getElementById('tournament-instance-team');
      const tRoundEl = document.getElementById('tournament-instance-round');
      const tNo = document.getElementById('tournament-no-instance');
      const tPlay = document.getElementById('tournament-play-now-btn');
      if (currentTournament && tEl && tTeamEl && tRoundEl && tNo && tPlay) {
        const teamName = currentTournament.user_team_id || 'Team';
        tTeamEl.textContent = teamName;
        tRoundEl.textContent = tournamentRoundLabel(currentTournament.current_round, currentTournament.completed);
        const accent = (colorMap[teamName] && colorMap[teamName].primary) || '#1a237e';
        tEl.style.setProperty('--instance-accent', accent);
        tEl.style.display = 'block';
        tNo.style.display = 'none';
        tPlay.style.display = 'block';
      } else if (tNo && tEl && tPlay) {
        tEl.style.display = 'none';
        tNo.style.display = 'block';
        tPlay.style.display = 'none';
      }

      const fEl = document.getElementById('franchise-instance');
      const fTeamEl = document.getElementById('franchise-instance-team');
      const fStatusEl = document.getElementById('franchise-instance-status');
      const fNo = document.getElementById('franchise-no-instance');
      const fPlay = document.getElementById('franchise-play-now-btn');
      if (currentFranchise && fEl && fTeamEl && fStatusEl && fNo && fPlay) {
        const teamName = currentFranchise.user_team_id || 'Team';
        fTeamEl.textContent = teamName;
        fStatusEl.textContent = franchiseStatusLabel(currentFranchise);
        const accent = (colorMap[teamName] && colorMap[teamName].primary) || '#1a237e';
        fEl.style.setProperty('--instance-accent', accent);
        fEl.style.display = 'block';
        fNo.style.display = 'none';
        fPlay.style.display = 'block';
      } else if (fNo && fEl && fPlay) {
        fEl.style.display = 'none';
        fNo.style.display = 'block';
        fPlay.style.display = 'none';
      }
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
