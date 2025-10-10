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
const pgId = urlParams.get(`${myTeamSide}_pg`);
const sgId = urlParams.get(`${myTeamSide}_sg`);
const sfId = urlParams.get(`${myTeamSide}_sf`);
const pfId = urlParams.get(`${myTeamSide}_pf`);
const cId = urlParams.get(`${myTeamSide}_c`);

// Determine team name and ID
let teamName = myTeamSide === 'home' ? homeTeam : awayTeam;
let teamId = myTeamSide === 'home' ? homeId : awayId;

// State
let currentSettings = {
  playcall_settings: {},
  strategy_settings: {}
};

// Slider mappings
const offenseSliders = {
  'Base': 'slider-base',
  'Freelance': 'slider-freelance',
  'Inside': 'slider-inside',
  'Attack': 'slider-attack',
  'Outside': 'slider-outside',
  'Set': 'slider-set'
};

const strategySliders = {
  'defense': 'slider-defense',
  'tempo': 'slider-tempo',
  'aggression': 'slider-aggression',
  'fast_break': 'slider-fast-break',
  'half_court_trap': 'slider-hc-trap',
  'full_court_press': 'slider-fc-press'
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
  // Setup offense sliders
  for (const [key, sliderId] of Object.entries(offenseSliders)) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
    
    if (slider && valueDisplay) {
      slider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value, 10);
        valueDisplay.textContent = value;
        currentSettings.playcall_settings[key] = value;
      });
    }
  }
  
  // Setup strategy sliders
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
  const values = Object.values(currentSettings.playcall_settings);
  if (values.every(v => v === 0)) {
    return false;
  }
  return true;
}

async function loadSettings() {
  try {
    // Determine mode and construct query params
    let mode = modeParam || 'single';
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
    
    const res = await fetch(`/api/gameplan?${params.toString()}`);
    if (!res.ok) {
      console.error('Failed to load game plan settings');
      return;
    }
    
    const data = await res.json();
    currentSettings = data;
    
    // Update UI with loaded values
    for (const [key, sliderId] of Object.entries(offenseSliders)) {
      const slider = document.getElementById(sliderId);
      const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
      const value = currentSettings.playcall_settings[key] || 2;
      
      if (slider) slider.value = value;
      if (valueDisplay) valueDisplay.textContent = value;
    }
    
    for (const [key, sliderId] of Object.entries(strategySliders)) {
      const slider = document.getElementById(sliderId);
      const valueDisplay = document.getElementById(`value-${sliderId.replace('slider-', '')}`);
      const value = currentSettings.strategy_settings[key] || 2;
      
      if (slider) slider.value = value;
      if (valueDisplay) valueDisplay.textContent = value;
    }
    
    console.log('✅ Loaded game plan settings:', currentSettings);
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function saveSettings() {
  try {
    // Validate offense settings
    if (!validateOffenseSettings()) {
      showModal("At least one Offense setting must be above 'Never'. Please increase any Offense slider.");
      return;
    }
    
    // Determine mode
    let mode = modeParam || 'single';
    
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
      const error = await res.json();
      showModal(error.detail || 'Failed to save game plan');
      return;
    }
    
    showToast('Game plan saved!');
    
    // Redirect to court.html after short delay
    setTimeout(() => {
      navigateToCourt();
    }, 500);
  } catch (err) {
    console.error('Error saving settings:', err);
    showModal('An error occurred while saving. Please try again.');
  }
}

function navigateToCourt() {
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
  if (quarter > 1 && gameId) params.set('game_id', gameId);
  
  // Add lineup params
  if (pgId) params.set(`${myTeamSide}_pg`, pgId);
  if (sgId) params.set(`${myTeamSide}_sg`, sgId);
  if (sfId) params.set(`${myTeamSide}_sf`, sfId);
  if (pfId) params.set(`${myTeamSide}_pf`, pfId);
  if (cId) params.set(`${myTeamSide}_c`, cId);
  
  if (DEBUG) params.set('debug', '1');
  
  window.location.href = `/court.html?${params.toString()}`;
}

function navigateBack() {
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
  
  window.location.href = `/set-lineup.html?${params.toString()}`;
}

async function resetSettings() {
  await loadSettings();
  showToast('Settings reset');
}

async function init() {
  setHeader();
  setupSliders();
  await loadSettings();
  
  // Button event listeners
  const btnSave = document.getElementById('btn-save');
  const btnReset = document.getElementById('btn-reset');
  const btnCancel = document.getElementById('btn-cancel');
  const modalClose = document.getElementById('modal-close');
  
  if (btnSave) {
    btnSave.addEventListener('click', saveSettings);
  }
  
  if (btnReset) {
    btnReset.addEventListener('click', resetSettings);
  }
  
  if (btnCancel) {
    btnCancel.addEventListener('click', navigateBack);
  }
  
  if (modalClose) {
    modalClose.addEventListener('click', hideModal);
  }
}

document.addEventListener('DOMContentLoaded', init);

