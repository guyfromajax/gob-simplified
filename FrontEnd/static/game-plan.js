// Parse URL parameters
const urlParams = new URLSearchParams(window.location.search);

// ✅ PHASE 1.3: Set telemetry context
if (window.StateTelemetry) {
  window.StateTelemetry.setContext('game-plan');
}

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
const franchiseId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('franchise_id', urlParams.get('franchise_id')) : urlParams.get('franchise_id');
const weekParam = urlParams.get('week');
const tournamentId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('tournament_id', urlParams.get('tournament_id')) : urlParams.get('tournament_id');
const modeParam = urlParams.get('mode');
const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
const periodLabel = urlParams.get('period') || `Q${quarter}`;
// ✅ PHASE 1.1: Remove localStorage fallback - game_id must come from URL params only
// game_id is required for Q2+ or timeout resume, optional for Q1 (will be created by init-game)
// ✅ PHASE 1.3: Instrument state read
const gameId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('game_id', urlParams.get('game_id') || null) : (urlParams.get('game_id') || null);
const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';

// ✅ PHASE 1.1: Fail loudly if game_id is required but missing
// For single mode, game_id is required for ALL quarters (Q1 must be created by init-game)
// For tournament/franchise mode, game_id is optional (may not exist yet)
const isGameIdRequired = (modeParam === 'single') || (quarter > 1) || resumeFromTimeout;
if (isGameIdRequired && !gameId) {
  const errorMsg = `game_id is required but missing from URL. Mode: ${modeParam}, Quarter: ${quarter}, Resume from timeout: ${resumeFromTimeout}. Please navigate from the lineup screen with a valid game_id (created by init-game).`;
  console.error(`❌ [GAME-PLAN] ${errorMsg}`);
  
  // Show error screen if errorHandler is available
  if (typeof window !== 'undefined' && window.ErrorHandler) {
    window.ErrorHandler.showMissingPointerError({
      missingPointer: 'game_id',
      message: errorMsg,
      mode: modeParam || 'single',
      recoveryOptions: {
        redirectTo: 'lineup',
        redirectParams: {
          home: homeTeam,
          away: awayTeam,
          home_id: homeId || '',
          away_id: awayId || '',
          my_team: myTeamSide || 'home',
          mode: modeParam || 'single',
          quarter: quarter,
          franchise_id: franchiseId || undefined,
          tournament_id: tournamentId || undefined
        },
        redirectLabel: 'Return to Lineup'
      }
    });
  } else {
    // Fallback if errorHandler not loaded
    alert(`Error: ${errorMsg}\n\nPlease return to the lineup screen and try again.`);
    // Redirect to lineup screen if possible
    if (homeTeam && awayTeam) {
      const lineupUrl = `/set-lineup.html?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&home_id=${encodeURIComponent(homeId || '')}&away_id=${encodeURIComponent(awayId || '')}&my_team=${encodeURIComponent(myTeamSide || 'home')}&mode=${encodeURIComponent(modeParam || 'single')}`;
      if (franchiseId) lineupUrl += `&franchise_id=${encodeURIComponent(franchiseId)}`;
      if (tournamentId) lineupUrl += `&tournament_id=${encodeURIComponent(tournamentId)}`;
      window.location.href = lineupUrl;
    }
  }
}

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
  strategy_settings: {}
};

// Track unsaved changes
let hasUnsavedChanges = false;
let lastSavedSettings = null;

// Slider mappings (note: all go to strategy_settings now for unified backend handling)
const strategySliders = {
  'offense': 'slider-offense',
  'inside': 'slider-inside',
  'attack': 'slider-attack',
  'outside': 'slider-outside',
  'fast_breaks': 'slider-fast_breaks',
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

function showSuccessPopup(message) {
  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.className = 'gameplan-success-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  `;
  
  // Create modal
  const modal = document.createElement('div');
  modal.className = 'gameplan-success-modal';
  modal.style.cssText = `
    background: #1a1a1a;
    border: 2px solid #00ff00;
    border-radius: 8px;
    padding: 24px;
    max-width: 400px;
    width: 90%;
    color: #fff;
    text-align: center;
  `;
  
  // Message
  const messageEl = document.createElement('p');
  messageEl.textContent = message;
  messageEl.style.cssText = `
    font-size: 1.125rem;
    margin-bottom: 20px;
    font-weight: 600;
    color: #00ff00;
  `;
  
  // OK button
  const okBtn = document.createElement('button');
  okBtn.textContent = 'OK';
  okBtn.style.cssText = `
    padding: 10px 30px;
    background: #00ff00;
    color: #000;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
  `;
  okBtn.addEventListener('click', () => {
    overlay.remove();
  });
  
  modal.appendChild(messageEl);
  modal.appendChild(okBtn);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
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
    logo.src = `/images/homepage-logos/${teamName}.png`;
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
        markUnsavedChanges();
      });
    }
  }
}

function markUnsavedChanges() {
  hasUnsavedChanges = true;
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
    // ✅ PHASE 2: Validate game_id before loading settings
    if (gameId && modeParam === 'single' && window.PointerValidation) {
      try {
        await window.PointerValidation.validateGameId(gameId);
        console.log(`✅ [GAME-PLAN] game_id validated: ${gameId}`);
      } catch (error) {
        console.error(`❌ [GAME-PLAN] Invalid game_id: ${error.message}`);
        if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
          window.ErrorHandler.showMissingPointerError({
            missingPointer: 'game_id',
            message: `Invalid game_id: ${gameId}. ${error.message}`,
            mode: modeParam,
            recoveryAction: 'redirect_to_lineup'
          });
        }
        return; // Don't proceed with loading
      }
    }
    
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
    const res = await fetch(`${API_CONFIG.buildUrl('/api/gameplan')}?${params.toString()}`);
    if (!res.ok) {
      console.error('❌ [GAME-PLAN] Failed to load game plan settings, status:', res.status);
      // Use defaults if API fails
      currentSettings = {
        strategy_settings: {
          'offense': 2, 'inside': 2, 'attack': 2, 'outside': 2, 'fast_breaks': 2,
          'defense': 2, 'aggression': 2, 'hc_trap': 2, 'fc_press': 2, 'rebounding': 2
        }
      };
      return;
    }
    
    const data = await res.json();
    // ✅ PHASE 1.3: Log backend read
    if (window.StateTelemetry) {
      window.StateTelemetry.logBackendRead('strategy_settings', data, '/api/gameplan');
    }
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
    
    // Store last saved settings for comparison
    lastSavedSettings = JSON.parse(JSON.stringify(currentSettings));
    hasUnsavedChanges = false;
    
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
      strategy_settings: currentSettings.strategy_settings
    };
    
    if (mode === 'franchise' && franchiseId) {
      payload.franchise_id = franchiseId;
    } else if (mode === 'tournament' && tournamentId) {
      payload.tournament_id = tournamentId;
    } else if (mode === 'single' && gameId) {
      payload.game_id = gameId;
    }
    
    // ✅ PHASE 1.3: Log backend write
    if (window.StateTelemetry) {
      window.StateTelemetry.logBackendWrite('strategy_settings', payload, '/api/gameplan');
    }
    
    const res = await fetch(API_CONFIG.buildUrl('/api/gameplan'), {
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

async function saveGamePlan() {
  console.log('🚀 [GAME-PLAN] saveGamePlan() CALLED');
  console.log('🚀 [GAME-PLAN] saveGamePlan() - Current URL:', window.location.href);
  try {
    // Validate offense settings
    if (!validateOffenseSettings()) {
      console.warn('⚠️ [GAME-PLAN] saveGamePlan() - Validation failed');
      showModal("At least one Offense setting must be above 'Never'. Please increase any Offense slider.");
      return;
    }
    console.log('✅ [GAME-PLAN] saveGamePlan() - Validation passed, saving...');
    
    // Save the settings
    const saved = await saveSettingsQuietly();
    
    if (!saved) {
      showModal('Failed to save game plan. Please try again.');
      return;
    }
    
    // ✅ FIX: Reset unsaved changes flag after successful save
    lastSavedSettings = JSON.parse(JSON.stringify(currentSettings));
    hasUnsavedChanges = false;
    
    showSuccessPopup('Game Plan Successfully Saved');
  } catch (err) {
    console.error('Error saving settings:', err);
    showModal('An error occurred while saving. Please try again.');
  }
}

function navigateToCourt() {
  // Check for unsaved changes before navigating
  if (hasUnsavedChanges) {
    showUnsavedChangesWarning(() => {
      executeNavigateToCourt();
    });
    return;
  }
  executeNavigateToCourt();
}

function executeNavigateToCourt() {
  console.log('🚀 [GAME-PLAN] executeNavigateToCourt() CALLED');
  console.log('🚀 [GAME-PLAN] Current URL:', window.location.href);
  
  // ✅ TASK 0: Commented out save logic - nav-only button
  // await saveSettingsQuietly();
  
  // ✅ CRITICAL FIX: Read URL params directly from window.location.search
  // Don't rely on module-level urlParams which might be stale
  const currentUrlParams = new URLSearchParams(window.location.search);
  const currentParamsObj = Object.fromEntries(currentUrlParams.entries());
  console.log('🚀 [GAME-PLAN] Current URL params:', currentParamsObj);
  console.error('🚀🚀🚀 [GAME-PLAN] executeNavigateToCourt() - game_id:', currentUrlParams.get('game_id'), 'resume_from_timeout:', currentUrlParams.get('resume_from_timeout'));
  
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
  const currentMode = currentUrlParams.get('mode') || 'single';
  
  // ✅ PHASE 1.1: Fail loudly if game_id is required but missing before navigating
  const isGameIdRequired = (currentMode === 'single') || (currentQuarter > 1) || resumeFromTimeout;
  if (isGameIdRequired && !currentGameId) {
    const errorMsg = `Cannot navigate to court: game_id is required but missing. Mode: ${currentMode}, Quarter: ${currentQuarter}, Resume from timeout: ${resumeFromTimeout}. Please ensure game_id exists in URL.`;
    console.error(`❌ [GAME-PLAN] ${errorMsg}`);
    alert(`Error: ${errorMsg}\n\nPlease return to the lineup screen and try again.`);
    return;
  }
  
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
  // ✅ PHASE 1.1: Removed localStorage.game_id read - URL is the source of truth
  console.log('🔍 [GAME-PLAN] executeNavigateToCourt() timeout state:', {
    currentGameId,
    currentQuarter,
    resumeFromTimeout,
    urlGameId: currentUrlParams.get('game_id')
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
  console.log('🔍 [GAME-PLAN] executeNavigateToCourt() FINAL URL:', finalUrl);
  console.log('🔍 [GAME-PLAN] executeNavigateToCourt() URL params:', {
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

function navigateBack() {
  // Check for unsaved changes before navigating
  if (hasUnsavedChanges) {
    showUnsavedChangesWarning(() => {
      executeNavigateBack();
    });
    return;
  }
  executeNavigateBack();
}

function executeNavigateBack() {
  // ✅ TASK 0: Commented out save logic - nav-only button
  // await saveSettingsQuietly();
  
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
  
  console.log('[executeNavigateBack] Passing lineup params:', { pgId, sgId, sfId, pfId, cId, myTeamSide });
  
  window.location.href = `/set-lineup.html?${params.toString()}`;
}

function navigateToCommandCenter() {
  // Check for unsaved changes before navigating
  if (hasUnsavedChanges) {
    showUnsavedChangesWarning(() => {
      executeNavigateToCommandCenter();
    });
    return;
  }
  executeNavigateToCommandCenter();
}

function executeNavigateToCommandCenter() {
  // ✅ TASK 0: Commented out save logic - nav-only button
  // await saveSettingsQuietly();
  
  // Return to command center (tournament or franchise)
  const mode = modeParam || 'single';
  
  if (mode === 'tournament' && tournamentId) {
    // Include team_id in URL for tournament command center
    const teamIdParam = teamId || userTeamIdParam || teamName;
    const url = `/tournament.html?tournament_id=${encodeURIComponent(tournamentId)}`;
    const finalUrl = teamIdParam ? `${url}&team_id=${encodeURIComponent(teamIdParam)}` : url;
    window.location.href = finalUrl;
  } else if (mode === 'franchise' && franchiseId) {
    // Include team_id in URL for franchise command center
    const teamIdParam = teamId || userTeamIdParam || teamName;
    const url = `/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
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

function showUnsavedChangesWarning(onContinue) {
  // Check if user has suppressed this warning
  if (sessionStorage.getItem('gameplan_suppress_warning') === 'true') {
    onContinue();
    return;
  }
  
  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.className = 'gameplan-warning-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  `;
  
  // Create modal
  const modal = document.createElement('div');
  modal.className = 'gameplan-warning-modal';
  modal.style.cssText = `
    background: #1a1a1a;
    border: 2px solid #ff7a00;
    border-radius: 8px;
    padding: 24px;
    max-width: 500px;
    width: 90%;
    color: #fff;
  `;
  
  // Message
  const message = document.createElement('p');
  message.textContent = "You haven't saved game plan changes.";
  message.style.cssText = `
    font-size: 1.125rem;
    margin-bottom: 20px;
    font-weight: 600;
  `;
  
  // Checkbox
  const checkboxContainer = document.createElement('div');
  checkboxContainer.style.cssText = 'margin-bottom: 20px;';
  
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = 'gameplan-suppress-warning';
  checkbox.style.cssText = 'margin-right: 8px;';
  
  const checkboxLabel = document.createElement('label');
  checkboxLabel.htmlFor = 'gameplan-suppress-warning';
  checkboxLabel.textContent = "Don't show this message again";
  checkboxLabel.style.cssText = 'color: #fff; cursor: pointer;';
  
  checkboxContainer.appendChild(checkbox);
  checkboxContainer.appendChild(checkboxLabel);
  
  // Buttons container
  const buttonsContainer = document.createElement('div');
  buttonsContainer.style.cssText = `
    display: flex;
    gap: 12px;
    justify-content: flex-end;
  `;
  
  // Save Game Plan button
  const saveBtn = document.createElement('button');
  saveBtn.textContent = 'Save Game Plan';
  saveBtn.style.cssText = `
    padding: 10px 20px;
    background: #ff7a00;
    color: #000;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
  `;
  saveBtn.addEventListener('click', async () => {
    if (checkbox.checked) {
      sessionStorage.setItem('gameplan_suppress_warning', 'true');
    }
    overlay.remove();
    await saveGamePlan();
    // After successful save, continue with navigation
    if (!hasUnsavedChanges) {
      onContinue();
    }
  });
  
  // Leave Without Saving button
  const leaveBtn = document.createElement('button');
  leaveBtn.textContent = 'Leave Without Saving';
  leaveBtn.style.cssText = `
    padding: 10px 20px;
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
  `;
  leaveBtn.addEventListener('click', () => {
    if (checkbox.checked) {
      sessionStorage.setItem('gameplan_suppress_warning', 'true');
    }
    overlay.remove();
    hasUnsavedChanges = false;
    onContinue();
  });
  
  buttonsContainer.appendChild(saveBtn);
  buttonsContainer.appendChild(leaveBtn);
  
  modal.appendChild(message);
  modal.appendChild(checkboxContainer);
  modal.appendChild(buttonsContainer);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

async function init() {
  setHeader();
  setupSliders();
  await loadSettings();
  
  // Check where user came from (command_center vs lineup)
  const urlParams = new URLSearchParams(window.location.search);
  const from = urlParams.get('from') || 'lineup';  // Default to lineup for backwards compatibility
  
  // Button event listeners
  // ✅ TASK 0: Updated button IDs
  const btnSaveGamePlan = document.getElementById('btn-save-game-plan');
  const btnNavPrimary = document.getElementById('btn-nav-primary'); // "Play Game" or "Back To Locker Room"
  const btnCancel = document.getElementById('btn-cancel');
  const btnBackToLineup = document.getElementById('btn-back-to-lineup');
  const modalClose = document.getElementById('modal-close');
  
  // Check if lineup is valid (all 5 positions filled)
  const lineupValid = pgId && sgId && sfId && pfId && cId;
  
  // Show/hide buttons based on where user came from
  // ✅ FIX: Check for all command center variations (command_center, tournament-command-center, franchise-command-center)
  const isFromCommandCenter = from === 'command_center' || 
                               from === 'tournament-command-center' || 
                               from === 'franchise-command-center';
  
  if (isFromCommandCenter) {
    // From command center (FCC/TCC): show "Back To Locker Room" button, hide "Back To Lineup" and "Cancel"
    if (btnNavPrimary) {
      btnNavPrimary.textContent = 'Back To Locker Room';
      btnNavPrimary.style.display = 'inline-block';
      btnNavPrimary.addEventListener('click', () => {
        console.log('🚀 [GAME-PLAN] btnNavPrimary (Back To Locker Room) CLICKED!');
        navigateToCommandCenter();
      });
    }
    if (btnBackToLineup) btnBackToLineup.style.display = 'none';
    if (btnCancel) btnCancel.style.display = 'none';
  } else {
    // From lineup: show "Play Game" button and "Back To Lineup" button, hide "Cancel"
    if (btnNavPrimary) {
      btnNavPrimary.textContent = 'Play Game';
      btnNavPrimary.style.display = 'inline-block';
      
      // Disable "Play Game" if lineup is invalid
      if (!lineupValid) {
        btnNavPrimary.disabled = true;
        btnNavPrimary.style.opacity = '0.5';
        btnNavPrimary.style.cursor = 'not-allowed';
        btnNavPrimary.title = 'Please complete your lineup first (Back To Lineup)';
      } else {
        btnNavPrimary.disabled = false;
        btnNavPrimary.style.opacity = '1';
        btnNavPrimary.style.cursor = 'pointer';
        btnNavPrimary.title = '';
      }
      
      btnNavPrimary.addEventListener('click', () => {
        console.log('🚀 [GAME-PLAN] btnNavPrimary (Play Game) CLICKED! About to call navigateToCourt()');
        navigateToCourt();
      });
    }
    if (btnBackToLineup) {
      btnBackToLineup.style.display = 'inline-block';
      btnBackToLineup.addEventListener('click', () => {
        console.log('🚀 [GAME-PLAN] btnBackToLineup CLICKED! About to call navigateBack()');
        navigateBack();
      });
    }
    if (btnCancel) btnCancel.style.display = 'none';
  }
  
  // ✅ TASK 0: Save Game Plan button (only button that saves to DB)
  if (btnSaveGamePlan) {
    console.log('🔍 [GAME-PLAN] init() - btnSaveGamePlan found, adding click listener');
    btnSaveGamePlan.addEventListener('click', () => {
      console.log('🚀 [GAME-PLAN] btnSaveGamePlan CLICKED! About to call saveGamePlan()');
      saveGamePlan();
    });
  } else {
    console.error('❌ [GAME-PLAN] init() - btnSaveGamePlan NOT FOUND!');
  }
  
  if (btnCancel) {
    btnCancel.addEventListener('click', navigateToCommandCenter);
  }
  
  if (modalClose) {
    modalClose.addEventListener('click', hideModal);
  }
}

document.addEventListener('DOMContentLoaded', init);


