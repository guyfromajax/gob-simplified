// Training Page JavaScript
const TOTAL_POINTS = 24;

// DOM Elements
const pointsRemainingEl = document.getElementById('points-remaining');
const submitBtn = document.getElementById('submit-btn');
const backBtn = document.getElementById('back-btn');
const allSliders = document.querySelectorAll('.slider');
const coachingRadios = document.querySelectorAll('input[name="coaching-focus"]');
const offensePlaysRadios = document.querySelectorAll('input[name="offense-plays"]');
const defensePlaysRadios = document.querySelectorAll('input[name="defense-plays"]');

// Track previous slider values to prevent over-allocation
allSliders.forEach(slider => {
  slider.dataset.prev = '0';
});

/**
 * Calculate total points allocated across all sliders
 */
function calculateTotalPoints() {
  let total = 0;
  allSliders.forEach(slider => {
    total += parseInt(slider.value) || 0;
  });
  return total;
}

/**
 * Check if coaching focus is selected
 */
function isCoachingFocusSelected() {
  const selectedFocus = document.querySelector('input[name="coaching-focus"]:checked');
  return selectedFocus !== null;
}

/**
 * Update points remaining display and submit button state
 */
function updatePointsRemaining() {
  const total = calculateTotalPoints();
  const remaining = TOTAL_POINTS - total;
  
  pointsRemainingEl.textContent = remaining;
  
  // Enable/disable submit button based on points allocation AND coaching focus selection
  const allPointsAllocated = remaining === 0;
  const focusSelected = isCoachingFocusSelected();
  
  if (allPointsAllocated && focusSelected) {
    submitBtn.disabled = false;
    submitBtn.style.opacity = '1';
  } else {
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.4';
  }
  
  return remaining;
}

/**
 * Handle slider input - prevent over-allocation
 */
allSliders.forEach(slider => {
  slider.addEventListener('input', function() {
    const currentValue = parseInt(this.value);
    const previousValue = parseInt(this.dataset.prev || '0');
    const currentTotal = calculateTotalPoints();
    const remaining = TOTAL_POINTS - currentTotal;
    
    // If trying to allocate more than available, revert to previous value
    if (remaining < 0) {
      this.value = this.dataset.prev;
      return;
    }
    
    // Update display
    const valueDisplay = this.parentElement.querySelector('.slider-value');
    if (valueDisplay) {
      valueDisplay.textContent = this.value;
    }
    
    // Store current value as previous
    this.dataset.prev = this.value;
    
    // Update points remaining
    updatePointsRemaining();
  });
  
  // Initialize slider value display
  const valueDisplay = slider.parentElement.querySelector('.slider-value');
  if (valueDisplay) {
    valueDisplay.textContent = slider.value;
  }
});

/**
 * Handle coaching focus radio button selection
 * All radios in this section are part of ONE global radio group
 */
coachingRadios.forEach(radio => {
  radio.addEventListener('change', function() {
    if (!this.checked) return;
    
    // Remove all active states
    document.querySelectorAll('.archetype-block').forEach(block => {
      block.classList.remove('active', 'header-selected', 'sub-option-selected');
    });
    
    // Determine which archetype this radio belongs to
    const value = this.value;
    let archetype = null;
    
    if (value.startsWith('authoritarian')) {
      archetype = 'authoritarian';
    } else if (value.startsWith('systems-coach')) {
      archetype = 'systems-coach';
    } else if (value.startsWith('player-maximizer')) {
      archetype = 'player-maximizer';
    } else if (value.startsWith('culture-builder')) {
      archetype = 'culture-builder';
    }
    
    if (!archetype) return;
    
    const archetypeBlock = document.querySelector(`[data-archetype="${archetype}"]`);
    if (!archetypeBlock) return;
    
    // Check if this is a header radio or sub-option radio
    const isHeaderRadio = value === archetype;
    
    if (isHeaderRadio) {
      // Header selected - highlight entire block
      archetypeBlock.classList.add('active', 'header-selected');
    } else {
      // Sub-option selected - subtle outline on block, highlight the radio
      archetypeBlock.classList.add('active', 'sub-option-selected');
    }
    
    // Update submit button state when focus is selected
    updatePointsRemaining();
  });
});

/**
 * Handle back button click
 */
backBtn.addEventListener('click', function() {
  // Get URL parameters to determine where to navigate back
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  const from = urlParams.get('from');
  
  // Determine back navigation based on mode/from parameter
  if (mode === 'franchise') {
    window.location.href = '/static/franchise-command-center.html?' + urlParams.toString();
  } else if (mode === 'tournament') {
    window.location.href = '/static/tournament-command-center.html?' + urlParams.toString();
  } else if (from === 'game-plan') {
    window.location.href = '/static/game-plan.html?' + urlParams.toString();
  } else {
    // Default fallback
    window.location.href = '/static/game-plan.html';
  }
});

/**
 * Collect all training data for submission
 */
function collectTrainingData() {
  const data = {
    // Player Drills
    player_drills: {
      offense: {
        inside: parseInt(document.getElementById('offense-inside').value) || 0,
        outside: parseInt(document.getElementById('offense-outside').value) || 0
      },
      defense: {
        inside: parseInt(document.getElementById('defense-inside').value) || 0,
        outside: parseInt(document.getElementById('defense-outside').value) || 0
      },
      technical: {
        passing: parseInt(document.getElementById('technical-passing').value) || 0,
        ball_handling: parseInt(document.getElementById('technical-ball-handling').value) || 0,
        rebounding: parseInt(document.getElementById('technical-rebounding').value) || 0
      },
      weight_room: {
        strength: parseInt(document.getElementById('weight-strength').value) || 0,
        agility: parseInt(document.getElementById('weight-agility').value) || 0
      }
    },
    
    // Team Drills
    team_drills: {
      team_offense: {
        install: parseInt(document.getElementById('team-offense-install').value) || 0,
        plays: document.querySelector('input[name="offense-plays"]:checked')?.value || 'current-playbook'
      },
      team_defense: {
        install: parseInt(document.getElementById('team-defense-install').value) || 0,
        plays: document.querySelector('input[name="defense-plays"]:checked')?.value || 'current-playbook'
      },
      fast_breaks: {
        offense_install: parseInt(document.getElementById('fast-break-offense-install').value) || 0,
        defense_install: parseInt(document.getElementById('fast-break-defense-install').value) || 0
      },
      scrimmages: parseInt(document.getElementById('team-scrimmages').value) || 0,
      presses_traps: {
        defense_install: parseInt(document.getElementById('press-defense-install').value) || 0,
        offense_install: parseInt(document.getElementById('press-offense-install').value) || 0
      }
    },
    
    // General
    general: {
      conditioning: parseInt(document.getElementById('general-conditioning').value) || 0,
      free_throws: parseInt(document.getElementById('general-free-throws').value) || 0,
      film_study: parseInt(document.getElementById('general-film-study').value) || 0,
      breaks: parseInt(document.getElementById('general-breaks').value) || 0
    },
    
    // Coaching Focus
    coaching_focus: document.querySelector('input[name="coaching-focus"]:checked')?.value || null
  };
  
  return data;
}

/**
 * Handle submit button click
 */
submitBtn.addEventListener('click', async function() {
  if (this.disabled) return;
  
  const trainingData = collectTrainingData();
  
  // Validate that all 24 points are allocated
  const total = calculateTotalPoints();
  if (total !== TOTAL_POINTS) {
    alert(`Please allocate all ${TOTAL_POINTS} training points before submitting.`);
    return;
  }
  
  // Validate that coaching focus is selected
  if (!isCoachingFocusSelected()) {
    alert('Please select a Coaching Style / Focus before submitting.');
    return;
  }
  
  // Get URL parameters for context
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  const franchiseId = urlParams.get('franchise_id');
  const tournamentId = urlParams.get('tournament_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id');
  
  // Prepare payload based on mode
  let payload = {};
  let endpoint = '/api/training';
  
  if (mode === 'franchise' && franchiseId) {
    payload = {
      franchise_id: franchiseId,
      training_data: trainingData
    };
    // Only include team_id if it's not null/undefined
    if (teamId) {
      payload.team_id = teamId;
    }
    endpoint = '/franchise/run-training';
  } else if (mode === 'tournament' && tournamentId) {
    payload = {
      tournament_id: tournamentId,
      training_data: trainingData
    };
    // Only include team_id if it's not null/undefined
    if (teamId) {
      payload.team_id = teamId;
    }
    endpoint = '/tournament/run-training';
  } else {
    // Single game mode or default
    payload = {
      team_id: teamId,
      training_data: trainingData
    };
  }
  
  try {
    this.disabled = true;
    this.textContent = 'Submitting...';
    
    console.log('🔍 [TRAINING] Submitting to endpoint:', endpoint);
    console.log('🔍 [TRAINING] Payload:', payload);
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    
    // Handle success - use redirect URL from backend if provided, otherwise navigate to command center
    if (result.redirect) {
      window.location.href = result.redirect;
    } else if (mode === 'franchise' && franchiseId) {
      window.location.href = `/static/franchise-command-center.html?franchise_id=${franchiseId}`;
    } else if (mode === 'tournament' && tournamentId) {
      window.location.href = `/static/tournament-command-center.html?tournament_id=${tournamentId}`;
    } else {
      window.location.href = '/static/game-plan.html';
    }
    
  } catch (error) {
    console.error('Failed to submit training:', error);
    alert('Failed to submit training. Please try again.');
    this.disabled = false;
    this.textContent = 'Submit Training';
  }
});

// Initialize points remaining on page load
updatePointsRemaining();

