// Parse URL parameters
const urlParams = new URLSearchParams(window.location.search);

// ✅ DEBUG: Log URL params when game-plan page loads
const pageLoadParams = {
  fullUrl: window.location.href,
  game_id: urlParams.get('game_id'),
  resume_from_timeout: urlParams.get('resume_from_timeout'),
  quarter: urlParams.get('quarter'),
  allParams: Object.fromEntries(urlParams.entries())
};
console.log('🔍 [GAME-PLAN] PAGE LOAD - URL params:', pageLoadParams);
console.warn('⚠️ [GAME-PLAN] PAGE LOAD CHECK - game_id:', pageLoadParams.game_id, 'resume_from_timeout:', pageLoadParams.resume_from_timeout);

// ✅ CRITICAL DEBUG: Alert if params are missing (can't be filtered/cleared)
if (!pageLoadParams.game_id || !pageLoadParams.resume_from_timeout) {
  console.error('❌ [GAME-PLAN] CRITICAL: game_id or resume_from_timeout is MISSING on page load!', pageLoadParams);
}

const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const homeId = urlParams.get('home_id');
const awayId = urlParams.get('away_id');
const myTeamSide = urlParams.get('my_team');
const userTeamIdParam = urlParams.get('user_team_id');
const franchiseId = urlParams.get('franchise_id');
const weekParam = urlParams.get('week');
const tournamentId = urlParams.get('tournament_id');
const modeParam = urlParams.get('mode');
const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
const periodLabel = urlParams.get('period') || `Q${quarter}`;
const gameId = urlParams.get('game_id') || (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
const DEBUG = urlParams.has('debug');

// Lineup params (passed from set-lineup)
// Only read if myTeamSide is set
const pgId = myTeamSide ? urlParams.get(`${myTeamSide}_pg`) : null;
const sgId = myTeamSide ? urlParams.get(`${myTeamSide}_sg`) : null;
const sfId = myTeamSide ? urlParams.get(`${myTeamSide}_sf`) : null;
const pfId = myTeamSide ? urlParams.get(`${myTeamSide}_pf`) : null;
const cId = myTeamSide ? urlParams.get(`${myTeamSide}_c`) : null;

// Determine team name and ID
// When coming from command center, use user_team_id; otherwise use lineup-based logic
let teamName = myTeamSide === 'home' ? homeTeam : awayTeam;
let teamId = myTeamSide === 'home' ? homeId : awayId;

// If coming from command center, use team_id or user_team_id parameter (Tournament/Franchise modes)
if (modeParam && (modeParam === 'tournament' || modeParam === 'franchise')) {
  // Check for team_id first (standardized format), then fallback to user_team_id (legacy)
  const teamIdParam = urlParams.get('team_id');
  if (teamIdParam) {
    teamId = teamIdParam;
    teamName = teamIdParam; // Will be resolved by backend if needed
  } else if (userTeamIdParam) {
    teamId = userTeamIdParam;
    teamName = userTeamIdParam; // Will be resolved by backend if needed
  }
}

// ✅ FIX: For Single Game mode, check for team_id parameter (team name format)
if (modeParam === 'single') {
  const teamIdParam = urlParams.get('team_id');
  if (teamIdParam) {
    teamId = teamIdParam;
    teamName = teamIdParam; // In single mode, team_id is the team name
  }
}

// State
let currentSettings = {
  playcall_settings: {},
  strategy_settings: {}
};

// Slider mappings (note: all go to strategy_settings now for unified backend handling)
const strategySliders = {
  'offense': 'slider-offense',
  'inside': 'slider-inside',
  'attack': 'slider-attack',
  'outside': 'slider-outside',
  'tempo': 'slider-tempo',
  'defense': 'slider-defense',
  'aggression': 'slider-aggression',
  'hc_trap': 'slider-hc-trap',
  'fc_press': 'slider-fc-press',
  'rebounding': 'slider-rebounding'
};

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2000);
}

function showModal(message) {
  const modal = document.getElementById('validation-modal');
  const modalMessage = document.getElementById('modal-message');
  if (modalMessage) modalMessage.textContent = message;
  if (modal) modal.hidden = false;
}

function hideModal() {
  const modal = document.getElementById('validation-modal');
  if (modal) modal.hidden = true;
}

function setHeader() {
  const title = document.getElementById('page-title');
  const subtitle = document.getElementById('team-subtitle');
  if (title) {
    title.textContent = 'Set Your Game Plan';
  }
  if (subtitle && teamName) {
    subtitle.textContent = teamName;
  }
  
  const logo = document.getElementById('team-logo');
  if (logo && teamName) {
    logo.src = `/static/images/homepage-logos/${teamName}.png`;
    logo.alt = `${teamName} logo`;
    logo.hidden = false;
    logo.onerror = () => { logo.hidden = true; };
  }
}

function setupSliders() {
  // Setup all sliders (all save to strategy_settings)
  for (const [key, sliderId] of Object.entries(strategySliders)) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
    
    if (slider && valueDisplay) {
      slider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value, 10);
        valueDisplay.textContent = value;
        currentSettings.strategy_settings[key] = value;
      });
    }
  }
}

function validateOffenseSettings() {
  // Check offense-related settings (offense, inside, attack, outside)
  const offenseValues = ['offense', 'inside', 'attack', 'outside'].map(
    key => currentSettings.strategy_settings[key] || 0
  );
  if (offenseValues.every(v => v === 0)) {
    return false;
  }
  return true;
}

async function loadSettings() {
  try {
    let mode = modeParam || 'single';
    
    // ✅ SS&S: Always load from database (single source of truth for all modes)
    const params = new URLSearchParams();
    params.set('mode', mode);
    params.set('team_id', teamId);
    
    if (mode === 'franchise' && franchiseId) {
      params.set('franchise_id', franchiseId);
    } else if (mode === 'tournament' && tournamentId) {
      params.set('tournament_id', tournamentId);
    } else if (mode === 'single' && gameId) {
      params.set('game_id', gameId);
    }
    
    console.log('🔍 [GAME-PLAN] Loading settings from database:', params.toString());
    const res = await fetch(`/api/gameplan?${params.toString()}`);
    if (!res.ok) {
      console.error('❌ [GAME-PLAN] Failed to load game plan settings, status:', res.status);
      // Use defaults if API fails
      currentSettings = {
        playcall_settings: {},
        strategy_settings: {
          'offense': 2, 'inside': 2, 'attack': 2, 'outside': 2, 'tempo': 2,
          'defense': 2, 'aggression': 2, 'hc_trap': 2, 'fc_press': 2, 'rebounding': 2
        }
      };
      return;
    }
    
    const data = await res.json();
    currentSettings = data;
    console.log('✅ [GAME-PLAN] Loaded settings from database:', currentSettings);
    
    // Update UI with loaded values AND ensure currentSettings is fully populated
    for (const [key, sliderId] of Object.entries(strategySliders)) {
      const slider = document.getElementById(sliderId);
      const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
      // ✅ FIX: Use nullish coalescing to preserve 0 values (|| treats 0 as falsy)
      const value = currentSettings.strategy_settings[key] ?? 2;
      
      // Ensure value is in currentSettings (in case it wasn't loaded)
      currentSettings.strategy_settings[key] = value;
      
      if (slider) slider.value = value;
      if (valueDisplay) valueDisplay.textContent = value;
    }
    
    console.log('✅ Loaded game plan settings:', currentSettings);
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

// Save settings silently (no validation, no navigation, no toast)
async function saveSettingsQuietly() {
  try {
    let mode = modeParam || 'single';
    
    // ✅ SS&S: Always save to database (single source of truth for all modes)
    const payload = {
      mode,
      team_id: teamId,
      playcall_settings: currentSettings.playcall_settings,
      strategy_settings: currentSettings.strategy_settings
    };
    
    if (mode === 'franchise' && franchiseId) {
      payload.franchise_id = franchiseId;
    } else if (mode === 'tournament' && tournamentId) {
      payload.tournament_id = tournamentId;
    } else if (mode === 'single' && gameId) {
      payload.game_id = gameId;
    }
    
    const res = await fetch('/api/gameplan', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (!res.ok) {
      console.warn('❌ [GAME-PLAN] Failed to save game plan quietly:', await res.text());
      return false;
    }
    
    console.log('✅ [GAME-PLAN] Saved game plan to database (quietly)');
    return true;
  } catch (err) {
    console.error('❌ [GAME-PLAN] Error saving settings quietly:', err);
    return false;
  }
}

async function saveSettings() {
  console.log('🚀 [GAME-PLAN] saveSettings() CALLED');
  console.log('🚀 [GAME-PLAN] saveSettings() - Current URL:', window.location.href);
  try {
    // Validate offense settings
    if (!validateOffenseSettings()) {
      console.warn('⚠️ [GAME-PLAN] saveSettings() - Validation failed');
      showModal("At least one Offense setting must be above 'Never'. Please increase any Offense slider.");
      return;
    }
    console.log('✅ [GAME-PLAN] saveSettings() - Validation passed, saving...');
    
    // Save the settings
    const saved = await saveSettingsQuietly();
    
    if (!saved) {
      showModal('Failed to save game plan. Please try again.');
      return;
    }
    
    showToast('Game plan saved!');
    
    // Redirect based on where user came from
    setTimeout(() => {
      console.log('🚀 [GAME-PLAN] saveSettings() - About to navigate (after 500ms delay)');
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get('from') || 'lineup';
      console.log('🚀 [GAME-PLAN] saveSettings() - from param:', from);
      
      // ✅ FIX: Check for all command center variations
      const isFromCommandCenter = from === 'command_center' || 
                                   from === 'tournament-command-center' || 
                                   from === 'franchise-command-center';
      
      if (isFromCommandCenter) {
        // Return to command center
        console.log('🚀 [GAME-PLAN] saveSettings() - Navigating to command center');
        navigateToCommandCenter();
      } else {
        // Go to court.html (start game)
        console.log('🚀 [GAME-PLAN] saveSettings() - About to call navigateToCourt()');
        navigateToCourt();
      }
    }, 500);
  } catch (err) {
    console.error('Error saving settings:', err);
    showModal('An error occurred while saving. Please try again.');
  }
}

function navigateToCourt() {
  console.log('🚀 [GAME-PLAN] navigateToCourt() CALLED');
  console.log('🚀 [GAME-PLAN] Current URL:', window.location.href);
  
  // ✅ CRITICAL FIX: Read URL params directly from window.location.search
  // Don't rely on module-level urlParams which might be stale
  const currentUrlParams = new URLSearchParams(window.location.search);
  const currentParamsObj = Object.fromEntries(currentUrlParams.entries());
  console.log('🚀 [GAME-PLAN] Current URL params:', currentParamsObj);
  console.error('🚀🚀🚀 [GAME-PLAN] navigateToCourt() - game_id:', currentUrlParams.get('game_id'), 'resume_from_timeout:', currentUrlParams.get('resume_from_timeout'));
  
  // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
  const helper = window.TimeoutNavigationHelper;
  if (!helper) {
    console.error('❌ [GAME-PLAN] TimeoutNavigationHelper not loaded!');
    return;
  }
  
  const currentQuarter = parseInt(currentUrlParams.get('quarter'), 10) || 1;
  const currentGameId = helper.getGameId(currentUrlParams);
  const resumeFromTimeout = helper.getResumeFromTimeout(currentUrlParams);
  const currentMyTeamSide = currentUrlParams.get('my_team');
  
  // Build lineup object from URL params
  const lineup = {};
  const currentPgId = currentMyTeamSide ? currentUrlParams.get(`${currentMyTeamSide}_pg`) : null;
  const currentSgId = currentMyTeamSide ? currentUrlParams.get(`${currentMyTeamSide}_sg`) : null;
  const currentSfId = currentMyTeamSide ? currentUrlParams.get(`${currentMyTeamSide}_sf`) : null;
  const currentPfId = currentMyTeamSide ? currentUrlParams.get(`${currentMyTeamSide}_pf`) : null;
  const currentCId = currentMyTeamSide ? currentUrlParams.get(`${currentMyTeamSide}_c`) : null;
  
  if (currentPgId) lineup['PG'] = currentPgId;
  if (currentSgId) lineup['SG'] = currentSgId;
  if (currentSfId) lineup['SF'] = currentSfId;
  if (currentPfId) lineup['PF'] = currentPfId;
  if (currentCId) lineup['C'] = currentCId;
  
  // ✅ DEBUG: Log timeout resume state
  console.log('🔍 [GAME-PLAN] navigateToCourt() timeout state:', {
    currentGameId,
    currentQuarter,
    resumeFromTimeout,
    urlGameId: currentUrlParams.get('game_id'),
    localStorageGameId: typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null
  });
  
  const params = helper.buildGameNavigationParams({
    sourceParams: currentUrlParams,
    targetQuarter: currentQuarter,
    gameId: currentGameId,
    resumeFromTimeout: resumeFromTimeout, // ✅ SS&S: Supports any quarter (backend supports this)
    lineup: lineup,
    myTeamSide: currentMyTeamSide,
    clock: currentUrlParams.get('clock')
  });
  
  if (DEBUG) {
    params.set('debug', '1');
    // optional: params.set('debug_flow', '1');
  }
  
  // ✅ DEBUG: Log final URL before navigation
  const finalUrl = `/court.html?${params.toString()}`;
  console.log('🔍 [GAME-PLAN] navigateToCourt() FINAL URL:', finalUrl);
  console.log('🔍 [GAME-PLAN] navigateToCourt() URL params:', {
    game_id: params.get('game_id'),
    resume_from_timeout: params.get('resume_from_timeout'),
    quarter: params.get('quarter'),
    allParams: Object.fromEntries(params.entries())
  });
  
  if (DEBUG) {
    console.debug('🔀 Redirecting to court.html (bypassing game plan)', { home: homeTeam, away: awayTeam, gameId: currentGameId });
  }
  window.location.href = finalUrl;
}

async function navigateBack() {
  // Save settings quietly before navigating back to lineup
  await saveSettingsQuietly();
  
  // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
  const helper = window.TimeoutNavigationHelper;
  if (!helper) {
    console.error('❌ [GAME-PLAN] TimeoutNavigationHelper not loaded!');
    return;
  }
  
  // ✅ CRITICAL FIX: Read URL params directly from window.location.search
  // Don't rely on module-level urlParams which might be stale
  const currentUrlParams = new URLSearchParams(window.location.search);
  
  const currentGameId = helper.getGameId(currentUrlParams);
  const resumeFromTimeout = helper.getResumeFromTimeout(currentUrlParams);
  
  // Build lineup object from current selections
  const lineup = {};
  if (pgId) lineup['PG'] = pgId;
  if (sgId) lineup['SG'] = sgId;
  if (sfId) lineup['SF'] = sfId;
  if (pfId) lineup['PF'] = pfId;
  if (cId) lineup['C'] = cId;
  
  const params = helper.buildGameNavigationParams({
    sourceParams: currentUrlParams,
    targetQuarter: quarter,
    gameId: currentGameId,
    resumeFromTimeout: resumeFromTimeout, // ✅ SS&S: Supports any quarter (backend supports this)
    lineup: lineup,
    myTeamSide: myTeamSide
  });
  
  console.log('[navigateBack] Passing lineup params:', { pgId, sgId, sfId, pfId, cId, myTeamSide });
  
  window.location.href = `/static/set-lineup.html?${params.toString()}`;
}

async function navigateToCommandCenter() {
  // Save settings quietly before navigating back to command center
  await saveSettingsQuietly();
  
  // Return to command center (tournament or franchise)
  const mode = modeParam || 'single';
  
  if (mode === 'tournament' && tournamentId) {
    // Include team_id in URL for tournament command center
    const teamIdParam = teamId || userTeamIdParam || teamName;
    const url = `/static/tournament.html?tournament_id=${encodeURIComponent(tournamentId)}`;
    const finalUrl = teamIdParam ? `${url}&team_id=${encodeURIComponent(teamIdParam)}` : url;
    window.location.href = finalUrl;
  } else if (mode === 'franchise' && franchiseId) {
    // Include team_id in URL for franchise command center
    const teamIdParam = teamId || userTeamIdParam || teamName;
    const url = `/static/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
    const finalUrl = teamIdParam ? `${url}&team_id=${encodeURIComponent(teamIdParam)}` : url;
    window.location.href = finalUrl;
  } else {
    // Fallback to home
    window.location.href = '/';
  }
}

async function resetSettings() {
  await loadSettings();
  showToast('Settings reset');
}

async function init() {
  setHeader();
  setupSliders();
  await loadSettings();
  
  // Check where user came from (command_center vs lineup)
  const urlParams = new URLSearchParams(window.location.search);
  const from = urlParams.get('from') || 'lineup';  // Default to lineup for backwards compatibility
  
  // Button event listeners
  const btnSave = document.getElementById('btn-save');
  const btnPlaybooks = document.getElementById('btn-playbooks');
  const btnCancel = document.getElementById('btn-cancel');
  const btnBackToLineup = document.getElementById('btn-back-to-lineup');
  const btnBackToLockerRoom = document.getElementById('btn-back-to-locker-room');
  const modalClose = document.getElementById('modal-close');
  
  // Check if lineup is valid (all 5 positions filled)
  const lineupValid = pgId && sgId && sfId && pfId && cId;
  
  // Show/hide buttons based on where user came from
  // ✅ FIX: Check for all command center variations (command_center, tournament-command-center, franchise-command-center)
  const isFromCommandCenter = from === 'command_center' || 
                               from === 'tournament-command-center' || 
                               from === 'franchise-command-center';
  
  if (isFromCommandCenter) {
    // From command center: show Back To Locker Room, hide Back To Lineup and Cancel
    if (btnBackToLockerRoom) btnBackToLockerRoom.style.display = 'inline-block';
    if (btnBackToLineup) btnBackToLineup.style.display = 'none';
    if (btnCancel) btnCancel.style.display = 'none';
    if (btnSave) btnSave.textContent = 'Save Game Plan';  // Save and return to command center
  } else {
    // From lineup: show Back To Lineup, hide Back To Locker Room and Cancel
    if (btnBackToLineup) btnBackToLineup.style.display = 'inline-block';
    if (btnBackToLockerRoom) btnBackToLockerRoom.style.display = 'none';
    if (btnCancel) btnCancel.style.display = 'none';
    if (btnSave) {
      btnSave.textContent = 'Play Game';  // Save and go to court
      
      // Disable "Play Game" if lineup is invalid
      if (!lineupValid) {
        btnSave.disabled = true;
        btnSave.style.opacity = '0.5';
        btnSave.style.cursor = 'not-allowed';
        btnSave.title = 'Please complete your lineup first (Back To Lineup)';
      } else {
        btnSave.disabled = false;
        btnSave.style.opacity = '1';
        btnSave.style.cursor = 'pointer';
        btnSave.title = '';
      }
    }
  }
  
  if (btnSave) {
    console.log('🔍 [GAME-PLAN] init() - btnSave found, adding click listener');
    btnSave.addEventListener('click', () => {
      console.log('🚀 [GAME-PLAN] btnSave CLICKED! About to call saveSettings()');
      saveSettings();
    });
  } else {
    console.error('❌ [GAME-PLAN] init() - btnSave NOT FOUND!');
  }
  
  if (btnPlaybooks) {
    btnPlaybooks.addEventListener('click', () => {
      // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
      const helper = window.TimeoutNavigationHelper;
      if (!helper) {
        console.error('❌ [GAME-PLAN] TimeoutNavigationHelper not loaded!');
        return;
      }
      
      const currentUrlParams = new URLSearchParams(window.location.search);
      const currentGameId = helper.getGameId(currentUrlParams);
      const resumeFromTimeout = helper.getResumeFromTimeout(currentUrlParams);
      const currentQuarter = parseInt(currentUrlParams.get('quarter'), 10) || 1;
      const currentMyTeamSide = currentUrlParams.get('my_team');
      
      // Build lineup object from URL params
      const lineup = {};
      if (currentMyTeamSide) {
        const currentPgId = currentUrlParams.get(`${currentMyTeamSide}_pg`);
        const currentSgId = currentUrlParams.get(`${currentMyTeamSide}_sg`);
        const currentSfId = currentUrlParams.get(`${currentMyTeamSide}_sf`);
        const currentPfId = currentUrlParams.get(`${currentMyTeamSide}_pf`);
        const currentCId = currentUrlParams.get(`${currentMyTeamSide}_c`);
        
        if (currentPgId) lineup['PG'] = currentPgId;
        if (currentSgId) lineup['SG'] = currentSgId;
        if (currentSfId) lineup['SF'] = currentSfId;
        if (currentPfId) lineup['PF'] = currentPfId;
        if (currentCId) lineup['C'] = currentCId;
      }
      
      // ✅ SS&S: Use TimeoutNavigationHelper to preserve all game context (including resume_from_timeout and clock)
      const params = helper.buildGameNavigationParams({
        sourceParams: currentUrlParams,
        targetQuarter: currentQuarter,
        gameId: currentGameId,
        resumeFromTimeout: resumeFromTimeout,
        lineup: lineup,
        myTeamSide: currentMyTeamSide
      });
      
      // ✅ FIX: Preserve original 'from' parameter if it indicates command center navigation
      // This ensures that when navigating back from Playbooks, Game Plan knows the original source
      const originalFrom = currentUrlParams.get('from');
      if (originalFrom === 'command_center' || originalFrom === 'tournament-command-center' || originalFrom === 'franchise-command-center') {
        // Preserve original command center source
        params.set('from', originalFrom);
      } else {
        // Otherwise, set to 'game-plan' to indicate we came from Game Plan
        params.set('from', 'game-plan');
      }
      
      if (DEBUG) {
        params.set('debug', '1');
      }
      
      console.log('🔍 [GAME-PLAN] Navigating to playbooks with params:', params.toString());
      window.location.href = `/static/playbooks.html?${params.toString()}`;
    });
  }
  
  if (btnCancel) {
    btnCancel.addEventListener('click', navigateToCommandCenter);
  }
  
  if (btnBackToLineup) {
    btnBackToLineup.addEventListener('click', navigateBack);
  }
  
  if (btnBackToLockerRoom) {
    btnBackToLockerRoom.addEventListener('click', navigateToCommandCenter);
  }
  
  if (modalClose) {
    modalClose.addEventListener('click', hideModal);
  }
}

document.addEventListener('DOMContentLoaded', init);

