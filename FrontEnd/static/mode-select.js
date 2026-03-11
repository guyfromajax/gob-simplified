function playSound(filename) {
  try {
    var a = new Audio('/sounds/' + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentPlayNowBtn = document.getElementById('tournament-play-now-btn');
const tournamentNewBtn = document.getElementById('tournament-new-btn');
const franchisePlayNowBtn = document.getElementById('franchise-play-now-btn');
const franchiseNewBtn = document.getElementById('franchise-new-btn');

// Current instance data (set after fetch in DOMContentLoaded)
let currentTournament = null;
let currentFranchise = null;

// Team name → square logo filename prefix (from images/square-logos/{code}_square.png)
const TEAM_LOGO_CODE = {
  'Bentley-Truman': 'bt',
  'Four Corners': 'fc',
  'Four-Corners': 'fc',
  'Lancaster': 'lan',
  'Little York': 'ly',
  'Little-York': 'ly',
  'Morristown': 'mor',
  'Ocean City': 'oc',
  'Ocean-City': 'oc',
  'South Lancaster': 'sl',
  'South-Lancaster': 'sl',
  'Xavien': 'xav'
};

function getSquareLogoPath(teamName) {
  if (typeof getTeamAssetPath === 'function') return getTeamAssetPath(teamName, 'banner_primary');
  return '/images/teams/general/general_banner_primary.jpg';
}

function tournamentRoundLabel(roundNum, completed) {
  if (completed) return 'Complete';
  if (roundNum === 1) return 'First Round';
  if (roundNum === 2) return 'Semis';
  if (roundNum === 3) return 'Championship';
  return 'First Round';
}

/**
 * One-time cleanup: see docs/To Do/local_storage_cleanup.md for a Console snippet to clear existing cruft.
 */

/**
 * Clear franchise-related keys from localStorage (one franchise per user).
 * Call after successful franchise delete so orphaned data does not accumulate.
 */
function clearFranchiseLocalStorage() {
  if (typeof localStorage === 'undefined') return;
  const toRemove = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
  ];
  toRemove.forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_franchise_')) localStorage.removeItem(k);
  });
  // Clear last-game state that may belong to the deleted franchise
  localStorage.removeItem('last_game_id');
  localStorage.removeItem('last_box_score_gameId');
  localStorage.removeItem('last_box_score_url');
  localStorage.removeItem('last_game_user_team_side');
  localStorage.removeItem('game_home');
  localStorage.removeItem('game_away');
}

/**
 * Clear tournament-related keys from localStorage.
 * Call after successful tournament delete so orphaned data does not accumulate.
 */
function clearTournamentLocalStorage() {
  if (typeof localStorage === 'undefined') return;
  const toRemove = ['activeTournament', 'userTeamId'];
  toRemove.forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_tournament_')) localStorage.removeItem(k);
  });
  localStorage.removeItem('last_game_id');
  localStorage.removeItem('last_box_score_gameId');
  localStorage.removeItem('last_box_score_url');
  localStorage.removeItem('last_game_user_team_side');
  localStorage.removeItem('game_home');
  localStorage.removeItem('game_away');
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
    playSound('click-strong.wav');
    window.location.href = './scrimmage-select.html';
  });
}

// Tournament: Play Now → TCC (or resolved TCC when completed; same URL)
if (tournamentPlayNowBtn) {
  tournamentPlayNowBtn.addEventListener('click', () => {
    playSound('click-strong.wav');
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
    playSound('click-beep.wav');
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
  newTournamentModalConfirm.addEventListener('click', async () => {
    if (newTournamentDontShowAgain && newTournamentDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_TOURNAMENT_WARNING_KEY, '1');
    }
    closeNewTournamentModal();
    // Delete current user's tournament so they can start a new one
    try {
      const res = await fetch(API_CONFIG.buildUrl('/tournament/delete-current'), {
        method: 'POST',
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) {
        console.warn('[mode-select] delete-current tournament failed:', res.status);
      } else {
        clearTournamentLocalStorage();
      }
    } catch (e) {
      console.warn('[mode-select] delete-current tournament error:', e);
    }
    goToNewTournament();
  });
}

// Franchise: Play Now → FCC (or resolved FCC when in end state; same URL)
if (franchisePlayNowBtn) {
  franchisePlayNowBtn.addEventListener('click', () => {
    playSound('click-strong.wav');
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
  franchiseNewBtn.addEventListener('click', async () => {
    playSound('click-beep.wav');
    const dontShow = typeof localStorage !== 'undefined' && localStorage.getItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY) === '1';
    const hasExistingFranchise = !!currentFranchise;
    if (hasExistingFranchise && !dontShow) {
      openNewFranchiseModal();
      return;
    }
    if (hasExistingFranchise && dontShow) {
      // User previously chose "don't show again" - still delete before redirecting
      try {
        const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
          method: 'POST',
          headers: API_CONFIG.getAuthHeaders(),
        });
        if (res.ok) clearFranchiseLocalStorage();
      } catch (e) {
        console.warn('[mode-select] delete-current franchise (dontShow path):', e);
      }
    }
    goToNewFranchise();
  });
}

if (newFranchiseModalCancel) {
  newFranchiseModalCancel.addEventListener('click', closeNewFranchiseModal);
}
if (newFranchiseModalConfirm) {
  newFranchiseModalConfirm.addEventListener('click', async () => {
    if (newFranchiseDontShowAgain && newFranchiseDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY, '1');
    }
    closeNewFranchiseModal();
    // Delete current user's franchise so they can start a new one (same pattern as New Tournament)
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
        method: 'POST',
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) {
        console.warn('[mode-select] delete-current franchise failed:', res.status);
      } else {
        clearFranchiseLocalStorage();
      }
    } catch (e) {
      console.warn('[mode-select] delete-current franchise error:', e);
    }
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
  // Looping lobby music on mode-select screen
  try {
    const lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(() => {});
  } catch (e) {}

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
      if (authUserEmail) authUserEmail.textContent = user.username || user.email;
      console.log('[AUTH] User logged in:', user.email);

      // Sync username from API; prompt is handled by FTE username modal (authBarInit) when fte: true
      const meRes = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (meData.username && meData.username.trim()) {
          if (authUserEmail) authUserEmail.textContent = meData.username;
          const stored = JSON.parse(authUser);
          stored.username = meData.username;
          localStorage.setItem('auth_user', JSON.stringify(stored));
        }
      } else if (meRes.status === 401) {
        // Token invalid/expired - clear and show logged-out state
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        if (authLoggedOut) authLoggedOut.style.display = 'flex';
        if (authLoggedIn) authLoggedIn.style.display = 'none';
      }
    } catch (e) {
      console.error('[AUTH] Failed to parse user:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
    }
  }

  // Username is now collected by the shared FTE username modal (authBarInit) when fte: true and no username.
  // The old set-username modal on mode-select is no longer shown.

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

      /* Scout team cards use neutral container (CSS); colorMap still used for Tournament/Franchise instance accents */
      teamButtons.forEach(btn => {
        const team = btn.dataset.team;
        if (colorMap[team]) {
          console.log(`Tile ${team} colors loaded (card uses neutral theme)`);
        }
      });

      // Render Tournament and Franchise instance cards from API data
      const tEl = document.getElementById('tournament-instance');
      const tTeamEl = document.getElementById('tournament-instance-team');
      const tRoundEl = document.getElementById('tournament-instance-round');
      const tLogo = document.getElementById('tournament-instance-logo');
      const tNo = document.getElementById('tournament-no-instance');
      const tPlay = document.getElementById('tournament-play-now-btn');
      if (currentTournament && tEl && tTeamEl && tRoundEl && tNo && tPlay) {
        const teamName = currentTournament.user_team_id || 'Team';
        tTeamEl.textContent = teamName;
        tRoundEl.textContent = tournamentRoundLabel(currentTournament.current_round, currentTournament.completed);
        const accent = (colorMap[teamName] && colorMap[teamName].primary) || '#1a237e';
        tEl.style.setProperty('--instance-accent', accent);
        tEl.style.display = 'flex';
        tNo.style.display = 'none';
        tPlay.style.display = 'block';
        if (tLogo) {
          const logoPath = getSquareLogoPath(teamName);
          if (logoPath) {
            tLogo.src = logoPath;
            tLogo.alt = teamName;
            tLogo.style.display = '';
          } else {
            tLogo.removeAttribute('src');
            tLogo.alt = '';
            tLogo.style.display = 'none';
          }
        }
      } else if (tNo && tEl && tPlay) {
        tEl.style.display = 'none';
        tNo.style.display = 'block';
        tPlay.style.display = 'none';
      }

      const fEl = document.getElementById('franchise-instance');
      const fTeamEl = document.getElementById('franchise-instance-team');
      const fStatusEl = document.getElementById('franchise-instance-status');
      const fLogo = document.getElementById('franchise-instance-logo');
      const fNo = document.getElementById('franchise-no-instance');
      const fPlay = document.getElementById('franchise-play-now-btn');
      if (currentFranchise && fEl && fTeamEl && fStatusEl && fNo && fPlay) {
        const teamName = currentFranchise.user_team_id || 'Team';
        fTeamEl.textContent = teamName;
        fStatusEl.textContent = franchiseStatusLabel(currentFranchise);
        const accent = (colorMap[teamName] && colorMap[teamName].primary) || '#1a237e';
        fEl.style.setProperty('--instance-accent', accent);
        fEl.style.display = 'flex';
        fNo.style.display = 'none';
        fPlay.style.display = 'block';
        if (fLogo) {
          const logoPath = getSquareLogoPath(teamName);
          if (logoPath) {
            fLogo.src = logoPath;
            fLogo.alt = teamName;
            fLogo.style.display = '';
          } else {
            fLogo.removeAttribute('src');
            fLogo.alt = '';
            fLogo.style.display = 'none';
          }
        }
      } else if (fNo && fEl && fPlay) {
        fEl.style.display = 'none';
        fNo.style.display = 'block';
        fPlay.style.display = 'none';
      }
    })
    .catch(() => {
      /* Scout team cards use neutral theme from CSS; no fallback needed */
      teamButtons.forEach(btn => {
        console.log(`Tile ${btn.dataset.team} (teams API failed, neutral theme)`);
      });
    });
});
