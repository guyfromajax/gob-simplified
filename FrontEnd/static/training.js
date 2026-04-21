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
const autoTrainModalTitle = document.getElementById('auto-train-modal-title');
const autoTrainModalFocus = document.getElementById('auto-train-modal-focus');
const autoTrainModalClose = document.getElementById('auto-train-modal-close');
const customFocusModal = document.getElementById('custom-focus-modal');
const customFocusThead = document.getElementById('custom-focus-thead');
const customFocusTbody = document.getElementById('custom-focus-tbody');
const customFocusAssignBtn = document.getElementById('custom-focus-assign-btn');
const customFocusCancelBtn = document.getElementById('custom-focus-cancel-btn');
let currentWeek = 1;
let currentTeamName = '';

/** @type {{ player_id: string, name: string, attrs: Record<string, number> }[]} */
let customFocusRoster = [];
/** @type {string[]} */
let customFocusRankingAttrs = [];
/** @type {Record<string, string[]>} playerId -> up to 3 distinct attr codes */
let customFocusDraft = {};
/** @type {Record<string, string[]>} committed picks after Assign */
let customFocusCommitted = {};

/** Main PM radio value; modal assigns a concrete leaf here before submit */
const CHOOSE_ATTRIBUTES_VALUE = 'player-maximizer-choose-attributes';

/** Resolved leaf: top-3 | attributes-4-6 | positional-focus | custom — set when user taps Assign in modal (choose-attributes path only, or stays null until then) */
let playerMaximizerResolvedFocus = null;

const PM_POSITION_RT_ORDER = ['PG', 'SG', 'SF', 'PF', 'C'];
const PM_POSITIONAL_FOCUS_ATTRS = {
  PG: ['PS', 'BH', 'IQ'],
  SG: ['SH', 'OD', 'AG'],
  SF: ['SC', 'ST', 'AG'],
  PF: ['RB', 'ID', 'ST'],
  C: ['SC', 'ID', 'ST']
};

function primaryPositionFromRatings(ratings) {
  if (!ratings || typeof ratings !== 'object') return 'PG';
  let bestVal = -Infinity;
  let bestPos = 'PG';
  PM_POSITION_RT_ORDER.forEach(function (pos) {
    let raw = ratings[pos];
    if (raw === undefined || raw === null) {
      raw = ratings[pos.toUpperCase()];
    }
    const v = parseFloat(raw);
    const n = Number.isFinite(v) ? v : 0;
    if (n > bestVal) {
      bestVal = n;
      bestPos = pos;
    }
  });
  return bestPos;
}

function positionalFocusTripleForRow(row) {
  const pos = primaryPositionFromRatings(row.position_ratings || {});
  const triple = PM_POSITIONAL_FOCUS_ATTRS[pos] || PM_POSITIONAL_FOCUS_ATTRS.PG;
  return triple.slice();
}

function sortedAttrCodesByValue(row) {
  const attrs = row.attrs || {};
  return customFocusRankingAttrs.slice().sort(function (a, b) {
    const va = Number(attrs[a]) || 0;
    const vb = Number(attrs[b]) || 0;
    if (vb !== va) return vb - va;
    return a.localeCompare(b);
  });
}

function getPmModalMode() {
  const r = document.querySelector('input[name="pm-modal-mode"]:checked');
  return r ? r.value : 'top-3';
}

function resolvedFocusToModalMode(resolved) {
  if (resolved === 'player-maximizer-custom') return 'custom';
  if (resolved === 'player-maximizer-attributes-4-6') return 'attributes-4-6';
  if (resolved === 'player-maximizer-positional-focus') return 'positional';
  if (resolved === 'player-maximizer-top-3') return 'top-3';
  return 'top-3';
}

function modalModeToCoachingLeaf(mode) {
  if (mode === 'custom') return 'player-maximizer-custom';
  if (mode === 'attributes-4-6') return 'player-maximizer-attributes-4-6';
  if (mode === 'positional') return 'player-maximizer-positional-focus';
  return 'player-maximizer-top-3';
}

function syncPmModalCustomHint() {
  const el = document.getElementById('pm-modal-custom-hint');
  if (!el) return;
  el.hidden = getPmModalMode() !== 'custom';
}

function getRowHighlightPicks(row) {
  const mode = getPmModalMode();
  if (mode === 'custom') {
    return customFocusDraft[row.player_id] || [];
  }
  if (mode === 'top-3') {
    return sortedAttrCodesByValue(row).slice(0, 3);
  }
  if (mode === 'attributes-4-6') {
    return sortedAttrCodesByValue(row).slice(3, 6);
  }
  if (mode === 'positional') {
    return positionalFocusTripleForRow(row);
  }
  return [];
}

function resetPlayerMaximizerResolvedState() {
  playerMaximizerResolvedFocus = null;
  resetCustomFocusCommitted();
}

async function fetchFranchiseCommandCenterData(franchiseId) {
  const response = await fetch(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${encodeURIComponent(franchiseId)}`, {
    headers: API_CONFIG.getAuthHeaders()
  });
  if (!response.ok) throw new Error(`Failed loading franchise command center data (${response.status})`);
  return response.json();
}

async function redirectIfTrainingAlreadyCommitted() {
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id');
  if (mode !== 'franchise' || !franchiseId) return false;

  try {
    const data = await fetchFranchiseCommandCenterData(franchiseId);
    if (!data || !data.training_completed) return false;
    const params = new URLSearchParams();
    params.set('mode', 'franchise');
    params.set('franchise_id', franchiseId);
    if (teamId) params.set('team_id', teamId);
    params.set('week', String(Number(data.week || 1)));
    params.set('from', 'training');
    window.location.replace(`/training-report.html?${params.toString()}`);
    return true;
  } catch (error) {
    console.warn('⚠️ [TRAINING] Unable to verify committed training state:', error);
    return false;
  }
}

// Track previous slider values to prevent over-allocation
allSliders.forEach(slider => {
  slider.dataset.prev = '0';
});

function ensureTrainingSliderVisual(slider) {
  const wrapper = slider?.closest('.slider-container');
  if (!wrapper) return null;
  let shell = wrapper.querySelector('.training-slider-shell');
  if (shell) return shell;

  shell = document.createElement('div');
  shell.className = 'training-slider-shell';
  shell.setAttribute('aria-hidden', 'true');
  shell.innerHTML = `
    <div class="training-slider-track"></div>
    <div class="training-slider-nodes">
      <span class="training-slider-node"></span>
      <span class="training-slider-node"></span>
      <span class="training-slider-node"></span>
      <span class="training-slider-node"></span>
      <span class="training-slider-node"></span>
      <span class="training-slider-node"></span>
    </div>
    <div class="training-slider-scale">
      <span class="training-slider-scale-value">0</span>
      <span class="training-slider-scale-value">1</span>
      <span class="training-slider-scale-value">2</span>
      <span class="training-slider-scale-value">3</span>
      <span class="training-slider-scale-value">4</span>
      <span class="training-slider-scale-value">5</span>
    </div>
  `;
  wrapper.appendChild(shell);
  return shell;
}

function updateTrainingSliderVisual(slider, rawValue) {
  const shell = ensureTrainingSliderVisual(slider);
  if (!shell) return;
  const value = Math.max(0, Math.min(5, Number(rawValue) || 0));
  shell.querySelectorAll('.training-slider-node').forEach((node, index) => {
    node.classList.toggle('is-selected', index === value);
  });
}

function updateTrainingSliderValuePosition(slider) {
  const wrapper = slider?.closest('.slider-container');
  if (!wrapper) return;
  const valueSpan = wrapper.querySelector('.slider-value');
  if (!valueSpan) return;
  const min = Number(slider.min || 0);
  const max = Number(slider.max || 0);
  const current = Number(slider.value || 0);
  const range = max - min;
  const percent = range > 0 ? (current - min) / range : 0;
  const thumbOffset = percent * slider.offsetWidth;
  valueSpan.style.left = `${thumbOffset}px`;
  valueSpan.style.transform = 'translateX(-50%)';
}

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
  updateTrainingSliderVisual(slider, value);
  updateTrainingSliderValuePosition(slider);
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

function isCustomFocusThreeDistinct(picks) {
  if (!Array.isArray(picks) || picks.length !== 3) return false;
  return picks[0] !== picks[1] && picks[0] !== picks[2] && picks[1] !== picks[2];
}

function isCustomFocusComplete() {
  if (!customFocusRoster.length) return false;
  return customFocusRoster.every(function (row) {
    const picks = customFocusCommitted[row.player_id];
    return isCustomFocusThreeDistinct(picks);
  });
}

/** Submit enabled when PM hidden leaf is selected, or Choose Attributes + resolved leaf (custom → committed complete). */
function isPlayerMaximizerSubmitReady() {
  const sel = document.querySelector('input[name="coaching-focus"]:checked');
  if (!sel || !sel.value.startsWith('player-maximizer')) return true;
  if (sel.value === CHOOSE_ATTRIBUTES_VALUE) {
    if (!playerMaximizerResolvedFocus) return false;
    if (playerMaximizerResolvedFocus === 'player-maximizer-custom') {
      return isCustomFocusComplete();
    }
    return true;
  }
  return true;
}

function resetCustomFocusCommitted() {
  customFocusCommitted = {};
  customFocusDraft = {};
}

function openCustomFocusModal() {
  if (!customFocusModal || !customFocusThead || !customFocusTbody) return;
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('mode') !== 'franchise' || !urlParams.get('franchise_id')) {
    showMessageModal('Choose Attributes is available in franchise mode after roster data loads.');
    return;
  }
  if (!customFocusRoster.length) {
    showMessageModal('Roster data is still loading. Try again in a moment.');
    return;
  }
  const mode = resolvedFocusToModalMode(playerMaximizerResolvedFocus);
  const modeInput = document.querySelector(`input[name="pm-modal-mode"][value="${mode}"]`);
  if (modeInput) modeInput.checked = true;

  customFocusDraft = {};
  customFocusRoster.forEach(function (row) {
    const pid = row.player_id;
    if (mode === 'custom') {
      const c = customFocusCommitted[pid];
      customFocusDraft[pid] = c && c.length === 3 ? [c[0], c[1], c[2]] : [];
    } else {
      customFocusDraft[pid] = [];
    }
  });
  syncPmModalCustomHint();
  renderCustomFocusTable();
  syncCustomFocusAssignButton();
  customFocusModal.style.display = 'flex';
  customFocusModal.setAttribute('aria-hidden', 'false');
}

function closeCustomFocusModal() {
  if (!customFocusModal) return;
  customFocusModal.style.display = 'none';
  customFocusModal.setAttribute('aria-hidden', 'true');
}

function syncCustomFocusAssignButton() {
  if (!customFocusAssignBtn) return;
  if (!customFocusRoster.length) {
    customFocusAssignBtn.disabled = true;
    return;
  }
  const mode = getPmModalMode();
  let complete = false;
  if (mode === 'custom') {
    complete = customFocusRoster.every(function (row) {
      const picks = customFocusDraft[row.player_id];
      return isCustomFocusThreeDistinct(picks);
    });
  } else {
    complete = true;
  }
  customFocusAssignBtn.disabled = !complete;
}

function renderCustomFocusTable() {
  if (!customFocusThead || !customFocusTbody) return;
  customFocusThead.innerHTML = '';
  customFocusTbody.innerHTML = '';
  const headRow = document.createElement('tr');
  const corner = document.createElement('th');
  corner.textContent = 'Player';
  headRow.appendChild(corner);
  customFocusRankingAttrs.forEach(function (code) {
    const th = document.createElement('th');
    th.textContent = code;
    headRow.appendChild(th);
  });
  customFocusThead.appendChild(headRow);

  customFocusRoster.forEach(function (row) {
    const tr = document.createElement('tr');
    const nameTd = document.createElement('td');
    nameTd.className = 'player-cell';
    nameTd.textContent = row.name || row.player_id;
    tr.appendChild(nameTd);

    const pid = row.player_id;
    const picks = getRowHighlightPicks(row);
    const modalMode = getPmModalMode();
    const clickable = modalMode === 'custom';

    customFocusRankingAttrs.forEach(function (code) {
      const td = document.createElement('td');
      td.className = 'custom-focus-cell' + (clickable ? '' : ' is-readonly');
      const val = row.attrs && typeof row.attrs[code] === 'number' ? row.attrs[code] : '';
      td.textContent = val === '' ? '—' : String(val);
      if (picks.indexOf(code) !== -1) td.classList.add('selected');
      if (clickable) {
        td.addEventListener('click', function () {
          onCustomFocusCellClick(pid, code);
        });
      }
      tr.appendChild(td);
    });
    customFocusTbody.appendChild(tr);
  });
}

function onCustomFocusCellClick(playerId, attrCode) {
  if (getPmModalMode() !== 'custom') return;
  playSound('click-tiny.wav');
  if (!customFocusDraft[playerId]) customFocusDraft[playerId] = [];
  const sel = customFocusDraft[playerId];
  const idx = sel.indexOf(attrCode);
  if (idx !== -1) {
    sel.splice(idx, 1);
  } else if (sel.length < 3) {
    sel.push(attrCode);
  } else {
    sel[2] = attrCode;
  }
  renderCustomFocusTable();
  syncCustomFocusAssignButton();
}

function commitCustomFocusFromModal() {
  const mode = getPmModalMode();
  if (mode === 'custom') {
    customFocusCommitted = {};
    customFocusRoster.forEach(function (row) {
      const pid = row.player_id;
      const picks = customFocusDraft[pid];
      if (isCustomFocusThreeDistinct(picks)) {
        customFocusCommitted[pid] = [picks[0], picks[1], picks[2]];
      }
    });
    playerMaximizerResolvedFocus = 'player-maximizer-custom';
  } else {
    customFocusCommitted = {};
    customFocusDraft = {};
    playerMaximizerResolvedFocus = modalModeToCoachingLeaf(mode);
  }
  closeCustomFocusModal();
  updatePointsRemaining();
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
  const pointsDisplay = pointsRemainingEl.closest('.points-display');
  if (pointsDisplay) {
    pointsDisplay.classList.remove('is-low', 'is-empty');
    if (remaining === 0) {
      pointsDisplay.classList.add('is-empty');
    } else if (remaining <= 5) {
      pointsDisplay.classList.add('is-low');
    }
  }
  
  // Enable/disable submit button based on points allocation AND coaching focus selection
  const allPointsAllocated = remaining === 0;
  const focusSelected = isCoachingFocusSelected();
  const pmOk = isPlayerMaximizerSubmitReady();

  if (allPointsAllocated && focusSelected && pmOk) {
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
  ensureTrainingSliderVisual(slider);
  updateTrainingSliderVisual(slider, slider.value);
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
    updateTrainingSliderVisual(this, this.value);
    updateTrainingSliderValuePosition(this);
    
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
  updateTrainingSliderValuePosition(slider);
});

window.addEventListener('resize', function () {
  allSliders.forEach(function (slider) {
    updateTrainingSliderValuePosition(slider);
  });
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
      // Custom requires modal picks — exclude from random Auto-Train
      return (
        value.includes('-') &&
        !archetypeValues.includes(value) &&
        value !== 'player-maximizer-choose-attributes' &&
        value !== 'player-maximizer-custom'
      );
    });
    
    if (validFocusRadios.length > 0) {
      const randomRadio = validFocusRadios[Math.floor(Math.random() * validFocusRadios.length)];
      randomRadio.checked = true;
      if (typeof window !== 'undefined') window.__trainingAutoAssigning = true;
      randomRadio.dispatchEvent(new Event('change', { bubbles: true }));
      focusLabel = getFocusLabelText(randomRadio);
      // Hidden PM leaf radios have no label — use same wording as the modal row
      const autoTrainPmLeafLabels = {
        'player-maximizer-top-3': 'Top 3',
        'player-maximizer-attributes-4-6': 'Attributes 4–6',
        'player-maximizer-positional-focus': 'Positional Focus'
      };
      const rv = randomRadio.value || '';
      if (autoTrainPmLeafLabels[rv]) {
        focusLabel = autoTrainPmLeafLabels[rv];
      }
      archetypeLabel = getArchetypeLabelText(randomRadio);
    }
  }

  // 4) Update UI state (points + submit enabled)
  updatePointsRemaining();

  // 5) Show confirmation popup
  if (autoTrainModal && autoTrainModalTitle && autoTrainModalFocus) {
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
    autoTrainModalTitle.textContent = 'Training Lock In';
    autoTrainModalFocus.textContent = `Focus: ${focusText}`;
    autoTrainModalFocus.hidden = false;
    autoTrainModal.classList.add('is-visible');
  }
}

if (autoTrainBtn) {
  autoTrainBtn.addEventListener('click', autoAssignTraining);
}
if (autoTrainModalClose && autoTrainModal) {
  autoTrainModalClose.addEventListener('click', () => {
    playSound('click-tiny.wav');
    autoTrainModal.classList.remove('is-visible');
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

    if (value.startsWith('player-maximizer')) {
      if (value === CHOOSE_ATTRIBUTES_VALUE) {
        openCustomFocusModal();
      } else {
        playerMaximizerResolvedFocus = null;
        resetCustomFocusCommitted();
      }
    } else {
      resetPlayerMaximizerResolvedState();
    }

    // Update submit button state when focus is selected
    updatePointsRemaining();
  });
});

document.querySelectorAll('input[name="pm-modal-mode"]').forEach(function (radio) {
  radio.addEventListener('change', function () {
    if (!this.checked) return;
    playSound('click-tiny.wav');
    syncPmModalCustomHint();
    const mode = getPmModalMode();
    if (mode !== 'custom') {
      customFocusDraft = {};
      customFocusRoster.forEach(function (row) {
        customFocusDraft[row.player_id] = [];
      });
    } else {
      customFocusRoster.forEach(function (row) {
        const pid = row.player_id;
        const c = customFocusCommitted[pid];
        customFocusDraft[pid] = c && c.length === 3 ? [c[0], c[1], c[2]] : [];
      });
    }
    renderCustomFocusTable();
    syncCustomFocusAssignButton();
  });
});

const chooseAttrsRadio = document.querySelector(
  `input[name="coaching-focus"][value="${CHOOSE_ATTRIBUTES_VALUE}"]`
);
if (chooseAttrsRadio) {
  chooseAttrsRadio.addEventListener('click', function () {
    if (this.checked) openCustomFocusModal();
  });
}

if (customFocusAssignBtn) {
  customFocusAssignBtn.addEventListener('click', function () {
    playSound('confirm-1.mp3');
    commitCustomFocusFromModal();
  });
}
if (customFocusCancelBtn) {
  customFocusCancelBtn.addEventListener('click', function () {
    playSound('click-tiny.wav');
    closeCustomFocusModal();
  });
}

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
    const finalUrl = (typeof resolveFranchiseLockerRoomUrl === 'function')
      ? resolveFranchiseLockerRoomUrl({
          params: urlParams,
          franchiseId: franchiseId,
          teamId: teamId
        })
      : `/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}${teamId ? `&team_id=${encodeURIComponent(teamId)}` : ''}`;
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
    
    // Coaching Focus (Choose Attributes → concrete leaf from modal Assign)
    coaching_focus: (function () {
      let cf = document.querySelector('input[name="coaching-focus"]:checked')?.value || null;
      if (cf === CHOOSE_ATTRIBUTES_VALUE) {
        cf = playerMaximizerResolvedFocus;
      }
      return cf;
    })(),
    
    // Playbook Training Mode
    playbook_training_mode: document.querySelector('input[name="playbook-training-mode"]:checked')?.value || 'current-playbooks'
  };

  if (data.coaching_focus === 'player-maximizer-custom') {
    data.coaching_focus_custom_by_player = {};
    Object.keys(customFocusCommitted).forEach(function (pid) {
      const picks = customFocusCommitted[pid];
      if (isCustomFocusThreeDistinct(picks)) {
        data.coaching_focus_custom_by_player[pid] = [picks[0], picks[1], picks[2]];
      }
    });
  }

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
  if (!autoTrainModal || !autoTrainModalTitle || !autoTrainModalFocus || !autoTrainModalClose) {
    alert(message);
    return;
  }
  autoTrainModalTitle.textContent = message;
  autoTrainModalFocus.textContent = '';
  autoTrainModalFocus.hidden = true;
  autoTrainModalClose.textContent = buttonLabel;
  autoTrainModal.classList.add('is-visible');
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

  const cfRadio = document.querySelector('input[name="coaching-focus"]:checked')?.value;
  if (cfRadio === CHOOSE_ATTRIBUTES_VALUE && !isPlayerMaximizerSubmitReady()) {
    alert('Player Maximizer: open Choose Attributes, pick a mode, and tap Assign Focus Attributes (for Custom, pick three distinct attributes per player).');
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
    if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
      const overlayTeamName = currentTeamName || 'Your team';
      window.PageLoadOverlay.show({
        variant: 'pulse',
        subtitle: `${overlayTeamName} is executing training.`,
        teamName: currentTeamName || '',
        assetKey: 'banner_primary'
      });
    }
    
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
      let redirectUrl = result.redirect.replace(/^\/static\//, '/');
      const returnUrl = urlParams.get('return_url');
      if (mode === 'franchise' && returnUrl) {
        const safeReturnUrl = typeof getSafeReturnUrl === 'function' ? getSafeReturnUrl(returnUrl) : returnUrl;
        if (safeReturnUrl) {
          const redirect = new URL(redirectUrl, window.location.origin);
          redirect.searchParams.set('return_url', safeReturnUrl);
          redirectUrl = `${redirect.pathname}${redirect.search}${redirect.hash || ''}`;
        }
      }
      window.location.href = redirectUrl;
    } else if (mode === 'franchise' && franchiseId) {
      window.location.href = (typeof resolveFranchiseLockerRoomUrl === 'function')
        ? resolveFranchiseLockerRoomUrl({
            params: urlParams,
            franchiseId: franchiseId,
            teamId: urlParams.get('team_id')
          })
        : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}`;
    } else if (mode === 'tournament' && tournamentId) {
      // Use same pattern as franchise mode - tournament.html is the command center
      window.location.href = `/tournament.html?tournament_id=${tournamentId}`;
    } else {
      window.location.href = '/game-plan.html';
    }
    
  } catch (error) {
    console.error('Failed to submit training:', error);
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
      window.PageLoadOverlay.hide();
    }
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
        currentTeamName = data.user_team_name || currentTeamName || '';
        if (Array.isArray(data.custom_focus_roster)) {
          customFocusRoster = data.custom_focus_roster;
        }
        if (Array.isArray(data.player_maximizer_ranking_attrs)) {
          customFocusRankingAttrs = data.player_maximizer_ranking_attrs;
        }
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


window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    window.location.reload();
  }
});

// Initialize training points on page load
(async function initTrainingPage() {
  const redirected = await redirectIfTrainingAlreadyCommitted();
  if (redirected) return;
  await initializeTrainingPoints();
})();

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
