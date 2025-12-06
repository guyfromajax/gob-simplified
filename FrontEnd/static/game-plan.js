// Parse URL parameters
const urlParams = new URLSearchParams(window.location.search);
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
let teamName = myTeamSide === 'home' ? homeTeam : awayTeam;
let teamId = myTeamSide === 'home' ? homeId : awayId;

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
    
    // ✅ TIMEOUT: Check for game_plan_settings in URL params first (same as quarter breaks)
    // This allows pre-populating settings when resuming from timeout
    const gamePlanSettingsParam = urlParams.get('game_plan_settings');
    if (gamePlanSettingsParam) {
      try {
        currentSettings = JSON.parse(gamePlanSettingsParam);
        console.log('✅ Loaded game plan settings from URL params (timeout resume):', currentSettings);
        // Update UI with loaded values
        for (const [key, sliderId] of Object.entries(strategySliders)) {
          const slider = document.getElementById(sliderId);
          const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
          const value = currentSettings.strategy_settings[key] || 2;
          if (slider) slider.value = value;
          if (valueDisplay) valueDisplay.textContent = value;
        }
        return; // Skip further loading if we got settings from URL
      } catch (e) {
        console.error('Error parsing game_plan_settings from URL:', e);
        // Fall through to normal loading
      }
    }
    
    // For single game mode, use localStorage (persist by team, not matchup)
    if (mode === 'single') {
      const storageKey = `gameplan_${teamName}`;
      const stored = localStorage.getItem(storageKey);
      
      if (stored) {
        currentSettings = JSON.parse(stored);
      } else {
        // Use defaults
        const defaults = {
          playcall_settings: {},
          strategy_settings: {
            'offense': 2, 'inside': 2, 'attack': 2, 'outside': 2, 'tempo': 2,
            'defense': 2, 'aggression': 2, 'hc_trap': 2, 'fc_press': 2, 'rebounding': 2
          }
        };
        currentSettings = defaults;
      }
    } else {
      // For franchise/tournament, fetch from database
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
      
      console.log('🔍 Gameplan API call params:', params.toString());
      const res = await fetch(`/api/gameplan?${params.toString()}`);
      if (!res.ok) {
        console.error('Failed to load game plan settings, status:', res.status);
        return;
      }
      
      const data = await res.json();
      currentSettings = data;
    }
    
    // Update UI with loaded values AND ensure currentSettings is fully populated
    for (const [key, sliderId] of Object.entries(strategySliders)) {
      const slider = document.getElementById(sliderId);
      const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
      const value = currentSettings.strategy_settings[key] || 2;
      
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
    
    // For single game mode, save to localStorage (persist by team, not matchup)
    if (mode === 'single') {
      const storageKey = `gameplan_${teamName}`;
      localStorage.setItem(storageKey, JSON.stringify(currentSettings));
      console.log('✅ Saved game plan to localStorage (quietly)');
    } else {
      // For franchise/tournament, save to database
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
      }
      
      const res = await fetch('/api/gameplan', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        console.warn('Failed to save game plan quietly:', await res.text());
        return false;
      }
      
      console.log('✅ Saved game plan to database (quietly)');
    }
    return true;
  } catch (err) {
    console.error('Error saving settings quietly:', err);
    return false;
  }
}

async function saveSettings() {
  try {
    // Validate offense settings
    if (!validateOffenseSettings()) {
      showModal("At least one Offense setting must be above 'Never'. Please increase any Offense slider.");
      return;
    }
    
    // Save the settings
    const saved = await saveSettingsQuietly();
    
    if (!saved) {
      showModal('Failed to save game plan. Please try again.');
      return;
    }
    
    showToast('Game plan saved!');
    
    // Redirect based on where user came from
    setTimeout(() => {
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get('from') || 'lineup';
      
      if (from === 'command_center') {
        // Return to command center
        navigateToCommandCenter();
      } else {
        // Go to court.html (start game)
        navigateToCourt();
      }
    }, 500);
  } catch (err) {
    console.error('Error saving settings:', err);
    showModal('An error occurred while saving. Please try again.');
  }
}

function navigateToCourt() {
  // ✅ EXACT SAME CODE as set-lineup.js working re-entry path (lines 827-871)
  const currentGameId = urlParams.get('game_id') ||
    (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
  const params = new URLSearchParams();
  params.set('home', homeTeam);
  params.set('away', awayTeam);
  if (homeId) params.set('home_id', homeId);
  if (awayId) params.set('away_id', awayId);
  if (myTeamSide) params.set('my_team', myTeamSide);
  if (userTeamIdParam) params.set('user_team_id', userTeamIdParam);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (weekParam) params.set('week', weekParam);
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (modeParam) params.set('mode', modeParam);
  params.set('quarter', String(quarter));
  params.set('period', periodLabel);
  if (quarter > 1 && currentGameId) params.set('game_id', currentGameId);
  
  // ✅ Preserve clock time if present (from foul out navigation)
  const clock = urlParams.get('clock');
  if (clock) params.set('clock', clock);
  
  // Build lineup object from URL params (matching set-lineup.js pattern)
  const lineup = {};
  if (pgId) lineup['PG'] = pgId;
  if (sgId) lineup['SG'] = sgId;
  if (sfId) lineup['SF'] = sfId;
  if (pfId) lineup['PF'] = pfId;
  if (cId) lineup['C'] = cId;
  
  ['PG','SG','SF','PF','C'].forEach(pos => {
    const id = lineup[pos];
    if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
  });
  
  // Carry forward start_with_inbound and starting_possession if present (from Sim to 4th Quarter)
  const startWithInbound = urlParams.get('start_with_inbound');
  const startingPossession = urlParams.get('starting_possession');
  if (startWithInbound) params.set('start_with_inbound', startWithInbound);
  if (startingPossession) params.set('starting_possession', startingPossession);
  
  // ✅ TIMEOUT: Carry forward resume_from_timeout flag
  const resumeFromTimeout = urlParams.get('resume_from_timeout');
  if (resumeFromTimeout) params.set('resume_from_timeout', resumeFromTimeout);
  
  if (DEBUG) {
    params.set('debug', '1');
    // optional: params.set('debug_flow', '1');
  }
  if (DEBUG) {
    console.debug('🔀 Redirecting to court.html (bypassing game plan)', { home: homeTeam, away: awayTeam, gameId: currentGameId });
  }
  window.location.href = `/court.html?${params.toString()}`;
}

async function navigateBack() {
  // Save settings quietly before navigating back to lineup
  await saveSettingsQuietly();
  
  // Go back to lineup selection
  const params = new URLSearchParams();
  params.set('home', homeTeam);
  params.set('away', awayTeam);
  if (homeId) params.set('home_id', homeId);
  if (awayId) params.set('away_id', awayId);
  if (myTeamSide) params.set('my_team', myTeamSide);
  if (userTeamIdParam) params.set('user_team_id', userTeamIdParam);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (weekParam) params.set('week', weekParam);
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (modeParam) params.set('mode', modeParam);
  params.set('quarter', String(quarter));
  params.set('period', periodLabel);
  
  // Pass lineup params back to preserve lineup when navigating back
  if (myTeamSide) {
    if (pgId) params.set(`${myTeamSide}_pg`, pgId);
    if (sgId) params.set(`${myTeamSide}_sg`, sgId);
    if (sfId) params.set(`${myTeamSide}_sf`, sfId);
    if (pfId) params.set(`${myTeamSide}_pf`, pfId);
    if (cId) params.set(`${myTeamSide}_c`, cId);
    console.log('[navigateBack] Passing lineup params:', { pgId, sgId, sfId, pfId, cId, myTeamSide });
  } else {
    console.warn('[navigateBack] myTeamSide not set, cannot pass lineup params');
  }
  
  window.location.href = `/static/set-lineup.html?${params.toString()}`;
}

async function navigateToCommandCenter() {
  // Save settings quietly before navigating back to command center
  await saveSettingsQuietly();
  
  // Return to command center (tournament or franchise)
  const mode = modeParam || 'single';
  
  if (mode === 'tournament' && tournamentId) {
    window.location.href = `/static/tournament.html?tournament_id=${encodeURIComponent(tournamentId)}`;
  } else if (mode === 'franchise' && franchiseId) {
    window.location.href = `/static/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`;
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
  const modalClose = document.getElementById('modal-close');
  
  // Check if lineup is valid (all 5 positions filled)
  const lineupValid = pgId && sgId && sfId && pfId && cId;
  
  // Show/hide buttons based on where user came from
  if (from === 'command_center') {
    // From command center: show Cancel (→ command center), hide Back To Lineup
    if (btnCancel) btnCancel.style.display = 'inline-block';
    if (btnBackToLineup) btnBackToLineup.style.display = 'none';
    if (btnSave) btnSave.textContent = 'Save';  // Just save, return to command center
  } else {
    // From lineup: show Back To Lineup, hide Cancel
    if (btnCancel) btnCancel.style.display = 'none';
    if (btnBackToLineup) btnBackToLineup.style.display = 'inline-block';
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
    btnSave.addEventListener('click', saveSettings);
  }
  
  if (btnPlaybooks) {
    btnPlaybooks.addEventListener('click', () => {
      window.location.href = '/static/play-builder-v2.html';
    });
  }
  
  if (btnCancel) {
    btnCancel.addEventListener('click', navigateToCommandCenter);
  }
  
  if (btnBackToLineup) {
    btnBackToLineup.addEventListener('click', navigateBack);
  }
  
  if (modalClose) {
    modalClose.addEventListener('click', hideModal);
  }
}

document.addEventListener('DOMContentLoaded', init);

