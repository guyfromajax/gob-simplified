// Training Page JavaScript
let TOTAL_POINTS = 24; // Will be updated from API for franchise mode

// DOM Elements
const pointsRemainingEl = document.getElementById('points-remaining');
const submitBtn = document.getElementById('submit-btn');
const autoTrainBtn = document.getElementById('auto-train-btn');
const recruitingInvitesBtn = document.getElementById('recruiting-invites-btn');
const backBtn = document.getElementById('back-btn');
const allSliders = document.querySelectorAll('.slider');
const coachingRadios = document.querySelectorAll('input[name="coaching-focus"]');
const offensePlaysRadios = document.querySelectorAll('input[name="offense-plays"]');
const defensePlaysRadios = document.querySelectorAll('input[name="defense-plays"]');
const autoTrainModal = document.getElementById('auto-train-modal');
const autoTrainModalMessage = document.getElementById('auto-train-modal-message');
const autoTrainModalClose = document.getElementById('auto-train-modal-close');
let currentWeek = 1;

// Track previous slider values to prevent over-allocation
allSliders.forEach(slider => {
  slider.dataset.prev = '0';
});

/**
 * Utility: set slider value and update display/cache
 */
function setSliderValue(slider, value) {
  slider.value = value;
  slider.dataset.prev = String(value);
  const valueDisplay = slider.parentElement.querySelector('.slider-value');
  if (valueDisplay) {
    valueDisplay.textContent = value;
  }
}

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
 * Get human-friendly label text for a selected focus radio
 */
function getFocusLabelText(radio) {
  if (!radio) return radio?.value || '';
  const label = radio.closest('label');
  if (label) return label.textContent.trim();
  return radio.value || '';
}

function getArchetypeLabelText(radio) {
  if (!radio) return '';
  const block = radio.closest('.archetype-block');
  if (!block) return '';
  const nameEl = block.querySelector('.archetype-name');
  return nameEl ? nameEl.textContent.trim() : '';
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
  slider.addEventListener('change', function() {
    playSound('click-tiny.wav');
  });
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
 * Auto-Train: assign all points and pick a random focus
 */
function autoAssignTraining() {
  playSound('chaotic-choice.wav');
  const sliders = Array.from(allSliders);
  if (sliders.length === 0) return;

  // 1) Set every slider to 1 (guarantees min 1 across 20 sliders = 20 points)
  sliders.forEach(slider => setSliderValue(slider, 1));

  // 2) Pick random unique sliders to set to 2 (adds remaining points)
  // For 24 points: 20 + 4 = 24 (pick 4 sliders)
  // For 30 points: 20 + 10 = 30 (pick 10 sliders)
  const remainingPoints = TOTAL_POINTS - 20;
  const shuffled = [...sliders].sort(() => Math.random() - 0.5);
  shuffled.slice(0, remainingPoints).forEach(slider => setSliderValue(slider, 2));

  // 3) Random coaching focus (only select from focus options, not archetype headers)
  let focusLabel = '';
  let archetypeLabel = '';
  if (coachingRadios.length > 0) {
    // Filter out archetype-level radio buttons - only allow focus options
    // Focus options have hyphens (e.g., "authoritarian-discipline"), archetype headers don't
    const archetypeValues = ['authoritarian', 'systems-coach', 'player-maximizer', 'culture-builder', 'culture'];
    const validFocusRadios = Array.from(coachingRadios).filter(radio => {
      const value = radio.value || '';
      // Only include radios with hyphens (focus options) and exclude archetype-only values
      return value.includes('-') && !archetypeValues.includes(value);
    });
    
    if (validFocusRadios.length > 0) {
      const randomRadio = validFocusRadios[Math.floor(Math.random() * validFocusRadios.length)];
      randomRadio.checked = true;
      if (typeof window !== 'undefined') window.__trainingAutoAssigning = true;
      randomRadio.dispatchEvent(new Event('change', { bubbles: true }));
      focusLabel = getFocusLabelText(randomRadio);
      archetypeLabel = getArchetypeLabelText(randomRadio);
    }
  }

  // 4) Update UI state (points + submit enabled)
  updatePointsRemaining();

  // 5) Show confirmation popup
  if (autoTrainModal && autoTrainModalMessage) {
    // Normalize archetype names to exact format required
    const archetypeMap = {
      'authoritarian': 'Authoritarian',
      'systems-coach': 'Systems Coach',
      'systems coach': 'Systems Coach',
      'player-maximizer': 'Player Maximizer',
      'player maximizer': 'Player Maximizer',
      'culture-builder': 'Culture Builder',
      'culture': 'Culture Builder',
      'culture builder': 'Culture Builder'
    };
    
    // Ensure archetype is in exact format (handle variations)
    let normalizedArchetype = '';
    if (archetypeLabel) {
      const archetypeLower = archetypeLabel.toLowerCase().trim();
      // Try direct match first
      if (archetypeMap[archetypeLower]) {
        normalizedArchetype = archetypeMap[archetypeLower];
      } else {
        // Try partial match
        for (const [key, value] of Object.entries(archetypeMap)) {
          if (archetypeLower.includes(key) || key.includes(archetypeLower)) {
            normalizedArchetype = value;
            break;
          }
        }
      }
    }
    
    // Clean focus label - remove any archetype prefix that might be included
    let cleanFocus = focusLabel || 'Focus';
    // Remove archetype names from focus if they appear at the start
    const archetypeNames = ['Authoritarian', 'Systems Coach', 'Player Maximizer', 'Culture Builder'];
    archetypeNames.forEach(arch => {
      const regex = new RegExp(`^${arch}\\s*-\\s*`, 'i');
      cleanFocus = cleanFocus.replace(regex, '').trim();
      // Also handle "Systems - Offense" pattern
      const regex2 = new RegExp(`^Systems\\s+-\\s+`, 'i');
      cleanFocus = cleanFocus.replace(regex2, '').trim();
    });
    
    // Format: focus (archetype) - focus outside, archetype inside parentheses
    // Archetype must be exactly: "Authoritarian", "Systems Coach", "Player Maximizer", or "Culture Builder"
    const focusText = normalizedArchetype ? `${cleanFocus} (${normalizedArchetype})` : cleanFocus;
    autoTrainModalMessage.innerHTML = `Training Points Assigned<br>${focusText} Focus Chosen`;
    autoTrainModal.style.display = 'flex';
  }
}

if (autoTrainBtn) {
  autoTrainBtn.addEventListener('click', autoAssignTraining);
}
if (autoTrainModalClose && autoTrainModal) {
  autoTrainModalClose.addEventListener('click', () => {
    playSound('click-tiny.wav');
    autoTrainModal.style.display = 'none';
  });
}

/**
 * Handle coaching focus radio button selection
 * All radios in this section are part of ONE global radio group
 */
coachingRadios.forEach(radio => {
  radio.addEventListener('change', function() {
    if (!this.checked) return;
    
    // SFX per coaching style — skip when Auto-Train triggered this change (avoid double sound with chaotic-choice)
    const value = this.value;
    const skipSound = typeof window !== 'undefined' && window.__trainingAutoAssigning;
    if (typeof window !== 'undefined') window.__trainingAutoAssigning = false;
    if (!skipSound) {
      if (value.startsWith('authoritarian')) {
        playSound('whistle-3.mp3');
      } else if (value.startsWith('systems-coach')) {
        playSound('positive-slide.wav');
      } else if (value.startsWith('player-maximizer')) {
        playSound('positive-plop.wav');
      } else if (value.startsWith('culture-builder')) {
        playSound('positive-beep.wav');
      }
    }
    
    // Remove all active states
    document.querySelectorAll('.archetype-block').forEach(block => {
      block.classList.remove('active', 'header-selected', 'sub-option-selected');
    });
    
    // Determine which archetype this radio belongs to
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
  
  // ✅ SS&S: Preserve team_id (ObjectId) in navigation for consistent flow
  // Determine back navigation based on mode/from parameter
  if (mode === 'franchise') {
    const franchiseId = urlParams.get('franchise_id');
    const teamId = urlParams.get('team_id');
    const url = `/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
    const finalUrl = teamId ? `${url}&team_id=${encodeURIComponent(teamId)}` : url;
    window.location.href = finalUrl;
  } else if (mode === 'tournament') {
    // Use same pattern as franchise mode - tournament.html is the command center
    const tournamentId = urlParams.get('tournament_id');
    const teamId = urlParams.get('team_id');
    const url = `/tournament.html?tournament_id=${encodeURIComponent(tournamentId)}`;
    const finalUrl = teamId ? `${url}&team_id=${encodeURIComponent(teamId)}` : url;
    window.location.href = finalUrl;
  } else if (from === 'game-plan') {
    window.location.href = '/game-plan.html?' + urlParams.toString();
  } else {
    // ✅ PHASE 2: Preserve URL params in fallback (includes game_id if present)
    window.location.href = '/game-plan.html?' + urlParams.toString();
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
        install: parseInt(document.getElementById('team-offense-install').value) || 0
      },
      team_defense: {
        install: parseInt(document.getElementById('team-defense-install').value) || 0
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
    coaching_focus: document.querySelector('input[name="coaching-focus"]:checked')?.value || null,
    
    // Playbook Training Mode
    playbook_training_mode: document.querySelector('input[name="playbook-training-mode"]:checked')?.value || 'all-plays-even'
  };
  
  console.log('🔋 [FRONTEND] Collected training data:', data);
  console.log('🔋 [FRONTEND] team_drills:', data.team_drills);
  console.log('🔋 [FRONTEND] team_drills keys:', Object.keys(data.team_drills));
  console.log('🔋 [FRONTEND] scrimmages in team_drills:', 'scrimmages' in data.team_drills);
  if ('scrimmages' in data.team_drills) {
    console.log('🔋 [FRONTEND] scrimmages value:', data.team_drills.scrimmages);
  } else {
    console.error('🔋 [FRONTEND] ERROR: scrimmages NOT in team_drills!');
    console.log('🔋 [FRONTEND] Checking element again:', document.getElementById('team-scrimmages'));
  }
  
  return data;
}

function playSound(filename) {
  try {
    const a = new Audio('/sounds/' + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function() {});
  } catch (e) {}
}

function showMessageModal(message, buttonLabel = 'Close') {
  if (!autoTrainModal || !autoTrainModalMessage || !autoTrainModalClose) {
    alert(message);
    return;
  }
  autoTrainModalMessage.textContent = message;
  autoTrainModalClose.textContent = buttonLabel;
  autoTrainModal.style.display = 'flex';
}

/**
 * Handle submit button click
 */
submitBtn.addEventListener('click', async function() {
  if (this.disabled) return;
  playSound('confirm-2.mp3');
  
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
    
    const url = API_CONFIG.buildUrl(endpoint) + (endpoint === '/franchise/run-training' ? '?profile=1' : '');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      let detail = `HTTP error! status: ${response.status}`;
      try {
        const err = await response.json();
        if (err && err.detail) detail = err.detail;
      } catch (_e) {}
      throw new Error(detail);
    }
    
    const result = await response.json();
    
    // Handle success - use redirect URL from backend if provided, otherwise navigate to command center
    if (result.redirect) {
      // ✅ FIX: Strip /static/ prefix from backend redirect URLs for Netlify compatibility
      const redirectUrl = result.redirect.replace(/^\/static\//, '/');
      window.location.href = redirectUrl;
    } else if (mode === 'franchise' && franchiseId) {
      window.location.href = `/franchise-command-center.html?franchise_id=${franchiseId}`;
    } else if (mode === 'tournament' && tournamentId) {
      // Use same pattern as franchise mode - tournament.html is the command center
      window.location.href = `/tournament.html?tournament_id=${tournamentId}`;
    } else {
      window.location.href = '/game-plan.html';
    }
    
  } catch (error) {
    console.error('Failed to submit training:', error);
    showMessageModal(error.message || 'Failed to submit training. Please try again.');
    this.disabled = false;
    this.textContent = 'Submit Training';
  }
});

/**
 * Fetch training points from API for franchise mode
 */
async function initializeTrainingPoints() {
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id');
  
  if (mode === 'franchise' && franchiseId) {
    try {
      const response = await fetch(`${API_CONFIG.buildUrl('/franchise/training-points')}?franchise_id=${franchiseId}`);
      if (response.ok) {
        const data = await response.json();
        TOTAL_POINTS = data.training_points;
        currentWeek = Number(data.week || 1);
        // Update points remaining display
        if (pointsRemainingEl) {
          pointsRemainingEl.textContent = TOTAL_POINTS;
        }
        if (recruitingInvitesBtn) {
          const showRecruitingInvites = currentWeek >= 20 && currentWeek <= 26;
          recruitingInvitesBtn.style.display = showRecruitingInvites ? 'inline-flex' : 'none';
          if (showRecruitingInvites) {
            recruitingInvitesBtn.onclick = function () {
              playSound('confirm-1.mp3');
              const params = new URLSearchParams();
              params.set('franchise_id', franchiseId);
              if (teamId) params.set('team_id', teamId);
              params.set('from', 'training');
              params.set('session_type', urlParams.get('session_type') || 'in-season');
              window.location.href = `/recruiting-orders.html?${params.toString()}`;
            };
          }
        }
        console.log(`🎯 [TRAINING] Training points set to ${TOTAL_POINTS} (first training: ${data.is_first_training})`);
      } else {
        console.warn('⚠️ [TRAINING] Failed to fetch training points, using default 24');
      }
    } catch (error) {
      console.error('❌ [TRAINING] Error fetching training points:', error);
    }
  }
  
  // Initialize points remaining display
  updatePointsRemaining();
}

// Initialize training points on page load
initializeTrainingPoints();

// Debug: Verify scrimmages element exists on page load
(function() {
  const scrimmagesElem = document.getElementById('team-scrimmages');
  console.log('🔋 [PAGE LOAD] team-scrimmages element:', scrimmagesElem);
  if (scrimmagesElem) {
    console.log('🔋 [PAGE LOAD] team-scrimmages value:', scrimmagesElem.value);
    console.log('🔋 [PAGE LOAD] team-scrimmages type:', scrimmagesElem.type);
    console.log('🔋 [PAGE LOAD] team-scrimmages id:', scrimmagesElem.id);
  } else {
    console.error('🔋 [PAGE LOAD] ERROR: team-scrimmages element NOT FOUND!');
    // Try to find it with different methods
    console.log('🔋 [PAGE LOAD] All elements with "scrimmages" in id:', document.querySelectorAll('[id*="scrimmages"]'));
    console.log('🔋 [PAGE LOAD] All sliders:', document.querySelectorAll('.slider[data-category="team-drills"]'));
  }
})();
