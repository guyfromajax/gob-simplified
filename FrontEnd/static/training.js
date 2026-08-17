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
let currentSeason = 1;
let trainingNewswirePromise = null;
let trainingNewswireOverlayActive = false;
let trainingNewswireError = null;

/** @type {{ player_id: string, name: string, attrs: Record<string, number> }[]} */
let customFocusRoster = [];
/** @type {string[]} */
let customFocusRankingAttrs = [];
/** @type {Record<string, string[]>} playerId -> up to 3 distinct attr codes */
let customFocusDraft = {};
/** @type {Record<string, string[]>} committed picks after Assign */
let customFocusCommitted = {};

/** Session keys for Custom Training Playbook → training-playbooks.html */
const STORAGE_PLAYBOOK_FOCUS = 'gob_training_playbook_focus';
const STORAGE_PLAYBOOK_MODE = 'gob_playbook_training_mode';
const STORAGE_TEAM_DRILLS_SNAPSHOT = 'gob_training_team_drills_snapshot';

/** Franchise training form draft while visiting custom playbooks or recruiting (sessionStorage). */
function trainingFormDraftStorageKey(urlParams) {
  if (urlParams.get('mode') !== 'franchise') return null;
  const fid = urlParams.get('franchise_id');
  const tid = urlParams.get('team_id') || urlParams.get('user_team_id') || '';
  const st = urlParams.get('session_type') || 'in-season';
  if (!fid) return null;
  return `gob_training_form_draft_${fid}|${tid}|w${currentWeek}|${st}`;
}

function saveTrainingFormDraft() {
  const urlParams = new URLSearchParams(window.location.search);
  const key = trainingFormDraftStorageKey(urlParams);
  if (!key) return;
  const sliders = {};
  document.querySelectorAll('.slider').forEach(function (el) {
    if (el.id) sliders[el.id] = parseInt(el.value, 10) || 0;
  });
  const checked = document.querySelector('input[name="coaching-focus"]:checked');
  const payload = {
    v: 1,
    week: currentWeek,
    total_points_budget: TOTAL_POINTS,
    sliders: sliders,
    coaching_radio: checked ? checked.value : null,
    player_maximizer_resolved: playerMaximizerResolvedFocus,
    custom_focus_committed: JSON.parse(JSON.stringify(customFocusCommitted)),
  };
  try {
    sessionStorage.setItem(key, JSON.stringify(payload));
  } catch (_e) {}
}

function clearTrainingFormDraftForCurrentContext() {
  const urlParams = new URLSearchParams(window.location.search);
  const key = trainingFormDraftStorageKey(urlParams);
  if (!key) return;
  try {
    sessionStorage.removeItem(key);
  } catch (_e) {}
}

function clearTutorialResumeContext() {
  try {
    if (window.GOBTutorialAlertResume && window.GOBTutorialAlertResume.clearContext) {
      window.GOBTutorialAlertResume.clearContext();
    } else {
      sessionStorage.removeItem('gob_tut_alert_resume');
    }
  } catch (_e) {}
}

function currentTrainingReturnUrl() {
  return window.location.pathname + window.location.search + (window.location.hash || '');
}

function navigateToTrainingTutorial() {
  playSound('click-tiny.wav');
  saveTrainingFormDraft();
  const returnUrl = currentTrainingReturnUrl();
  if (window.GOBTutorialAlertResume && window.GOBTutorialAlertResume.setTrainingPageContext) {
    window.GOBTutorialAlertResume.setTrainingPageContext(returnUrl);
  } else {
    try {
      sessionStorage.setItem('gob_tut_alert_resume', JSON.stringify({
        entrySource: 'training-page',
        alertId: 'training',
        lessonId: 'training',
        returnUrl: returnUrl
      }));
    } catch (_e) {}
  }
  window.location.href = '/tutorial-training.html';
}

function wireTrainingTutorialButton() {
  const btn = document.getElementById('training-tutorial-btn');
  if (!btn) return;
  btn.addEventListener('click', navigateToTrainingTutorial);
}

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

function trainingNewswireCacheKey(franchiseId, season, week) {
  // v2 invalidates payloads cached before PTS/REB/AST moved to per-game values.
  return `gob_training_newswire_v2_${franchiseId}_s${season}_w${week}`;
}

function prefetchTrainingNewswire(franchiseId) {
  if (!franchiseId) return null;
  const key = trainingNewswireCacheKey(franchiseId, currentSeason, currentWeek);
  try {
    const cached = JSON.parse(sessionStorage.getItem(key) || 'null');
    if (cached && Number(cached.season) === currentSeason && Number(cached.current_week) === currentWeek) {
      trainingNewswireError = null;
      trainingNewswirePromise = Promise.resolve(cached);
      return trainingNewswirePromise;
    }
  } catch (_cacheError) {}
  const headers = typeof API_CONFIG.getAuthHeaders === 'function' ? API_CONFIG.getAuthHeaders() : {};
  trainingNewswireError = null;
  const url = `${API_CONFIG.buildUrl('/franchise/league-news')}?franchise_id=${encodeURIComponent(franchiseId)}`;
  trainingNewswirePromise = fetch(url, { headers }).then(async function(response) {
    if (!response.ok) throw new Error(`League news unavailable (${response.status})`);
    const payload = await response.json();
    try { sessionStorage.setItem(key, JSON.stringify(payload)); } catch (_cacheError) {}
    return payload;
  }).catch(function(error) {
    trainingNewswireError = error;
    return null;
  });
  return trainingNewswirePromise;
}

function showTrainingNewswire(franchiseId) {
  trainingNewswireOverlayActive = true;
  const promise = trainingNewswirePromise || prefetchTrainingNewswire(franchiseId);
  if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
    window.PageLoadOverlay.show({ variant: 'newswire', data: null });
  }
  if (!promise) return Promise.resolve(null);
  return promise.then(function(payload) {
    if (!payload) throw trainingNewswireError || new Error('League news unavailable');
    if (trainingNewswireOverlayActive && window.PageLoadOverlay && window.PageLoadOverlay.show) {
      window.PageLoadOverlay.show({ variant: 'newswire', data: payload });
    }
    return payload;
  }).catch(function(error) {
    console.warn('[TRAINING] League news fallback:', error);
    if (trainingNewswireOverlayActive && window.PageLoadOverlay && window.PageLoadOverlay.show) {
      window.PageLoadOverlay.show({
        variant: 'pulse', title: '', subtitle: 'Training in progress',
        teamName: currentTeamName || '', assetKey: 'banner_primary'
      });
    }
    return null;
  });
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

/** Every slider notch costs exactly one whole budget point. */
function calculateTotalPoints() {
  let total = 0;
  allSliders.forEach(slider => {
    total += parseInt(slider.value, 10) || 0;
  });
  return total;
}

function formatPointsDisplay(n) {
  return String(Math.round(n));
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

function canAllocateMore() {
  const spent = calculateTotalPoints();
  for (const slider of allSliders) {
    const cur = parseInt(slider.value, 10) || 0;
    if (cur >= parseInt(slider.max || '5', 10)) continue;
    if (spent + 1 <= TOTAL_POINTS) return true;
  }
  return false;
}

/**
 * Update points remaining display and submit button state
 */
function updatePointsRemaining() {
  const total = calculateTotalPoints();
  const remaining = TOTAL_POINTS - total;
  
  pointsRemainingEl.textContent = formatPointsDisplay(Math.max(0, remaining));
  const pointsDisplay = pointsRemainingEl.closest('.points-display');
  if (pointsDisplay) {
    pointsDisplay.classList.remove('is-low', 'is-empty');
    if (remaining <= 1e-6) {
      pointsDisplay.classList.add('is-empty');
    } else if (remaining <= 5) {
      pointsDisplay.classList.add('is-low');
    }
  }
  
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

  updateRequirementsBar();

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
 * Auto-Train: assign whole points under the flat budget and pick a random focus
 */
function autoAssignTraining() {
  playSound('chaotic-choice.wav');
  const sliders = Array.from(allSliders);
  if (sliders.length === 0) return;

  sliders.forEach(slider => setSliderValue(slider, 0));

  const ranked = sliders.slice();

  // Pass 1: put 1 on as many sliders as fit.
  ranked.forEach(function (slider) {
    if (calculateTotalPoints() + 1 <= TOTAL_POINTS) {
      setSliderValue(slider, 1);
    }
  });

  // Pass 2: bump random affordable sliders until the budget is full.
  const bumpPool = ranked.filter(function (s) {
    return (parseInt(s.value, 10) || 0) < parseInt(s.max || '5', 10);
  });
  for (let guard = 0; guard < 200 && canAllocateMore(); guard++) {
    const shuffled = bumpPool.slice().sort(function () { return Math.random() - 0.5; });
    let bumped = false;
    for (let i = 0; i < shuffled.length; i++) {
      const slider = shuffled[i];
      const cur = parseInt(slider.value, 10) || 0;
      const maxV = parseInt(slider.max || '5', 10);
      if (cur >= maxV) continue;
      if (calculateTotalPoints() + 1 <= TOTAL_POINTS) {
        setSliderValue(slider, cur + 1);
        bumped = true;
        break;
      }
    }
    if (!bumped) break;
  }

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

function findCoachingFocusRadioByValue(value) {
  let found = null;
  coachingRadios.forEach(function (r) {
    if (r.value === value) found = r;
  });
  return found;
}

/** Archetype block highlight only (no sound, no PM modal). */
function applyCoachingFocusArchetypeUi(value) {
  document.querySelectorAll('.archetype-block').forEach(function (block) {
    block.classList.remove('active', 'header-selected', 'sub-option-selected');
  });
  let archetype = null;
  if (value.startsWith('authoritarian')) archetype = 'authoritarian';
  else if (value.startsWith('systems-coach')) archetype = 'systems-coach';
  else if (value.startsWith('player-maximizer')) archetype = 'player-maximizer';
  else if (value.startsWith('culture-builder')) archetype = 'culture-builder';
  if (!archetype) return;
  const archetypeBlock = document.querySelector(`[data-archetype="${archetype}"]`);
  if (!archetypeBlock) return;
  const isHeaderRadio = value === archetype;
  if (isHeaderRadio) archetypeBlock.classList.add('active', 'header-selected');
  else archetypeBlock.classList.add('active', 'sub-option-selected');
}

function restoreTrainingFormDraft() {
  const urlParams = new URLSearchParams(window.location.search);
  const key = trainingFormDraftStorageKey(urlParams);
  if (!key) return;
  let raw;
  try {
    raw = sessionStorage.getItem(key);
  } catch (_e) {
    return;
  }
  if (!raw) return;
  let o;
  try {
    o = JSON.parse(raw);
  } catch (_e) {
    return;
  }
  if (!o || o.v !== 1) return;
  if (Number(o.week) !== Number(currentWeek)) return;
  if (Number(o.total_points_budget) !== Number(TOTAL_POINTS)) return;

  if (o.sliders && typeof o.sliders === 'object') {
    Object.keys(o.sliders).forEach(function (id) {
      const el = document.getElementById(id);
      if (el && el.classList && el.classList.contains('slider')) {
        const v = Math.max(0, Math.min(5, parseInt(o.sliders[id], 10) || 0));
        setSliderValue(el, v);
      }
    });
  }

  playerMaximizerResolvedFocus = o.player_maximizer_resolved || null;
  customFocusCommitted =
    o.custom_focus_committed && typeof o.custom_focus_committed === 'object'
      ? Object.assign({}, o.custom_focus_committed)
      : {};

  const radioVal = o.coaching_radio;
  if (radioVal) {
    const inp = findCoachingFocusRadioByValue(radioVal);
    if (inp) {
      inp.checked = true;
      applyCoachingFocusArchetypeUi(radioVal);
    }
  }
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
    
    applyCoachingFocusArchetypeUi(value);

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
    playSound('confirm-1-lowervol.wav');
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
  clearTutorialResumeContext();
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
  const pageParams = new URLSearchParams(window.location.search);
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
    
    // Playbook Training Mode (+ optional custom CMD focus for franchise)
    playbook_training_mode: (function () {
      if (pageParams.get('mode') === 'franchise') {
        const sm = sessionStorage.getItem(STORAGE_PLAYBOOK_MODE);
        if (sm === 'custom' && sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS)) {
          return 'custom';
        }
        return 'current-playbooks';
      }
      return document.querySelector('input[name="playbook-training-mode"]:checked')?.value || 'current-playbooks';
    })(),
    training_playbook_focus: (function () {
      if (pageParams.get('mode') !== 'franchise') return null;
      if (sessionStorage.getItem(STORAGE_PLAYBOOK_MODE) !== 'custom') return null;
      const raw = sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS);
      if (!raw) return null;
      try {
        return JSON.parse(raw);
      } catch (_e) {
        return null;
      }
    })(),
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
  playSound('confirm-2-lowervol.wav');
  
  const trainingData = collectTrainingData();
  
  // Flat integer budget: every slider notch costs exactly one point.
  const remaining = TOTAL_POINTS - calculateTotalPoints();
  if (remaining !== 0) {
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
    if (mode === 'franchise' && franchiseId) {
      showTrainingNewswire(franchiseId);
    } else if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
      window.PageLoadOverlay.show({ variant: 'pulse', subtitle: 'Training in progress' });
    }

    const jsonHeaders = Object.assign(
      { 'Content-Type': 'application/json' },
      (typeof API_CONFIG.getAuthHeaders === 'function' ? API_CONFIG.getAuthHeaders() : {})
    );

    let result;

    if (mode === 'franchise' && franchiseId) {
      console.log('🔍 [TRAINING] Phase 1 (user) payload:', payload);
      const userUrl = API_CONFIG.buildUrl('/franchise/run-training/user');
      let userRes = await fetch(userUrl, {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify(payload)
      });
      let userResult = null;
      try {
        userResult = await userRes.json();
      } catch (_e) {}
      if (userResult && userResult.status === 'already_completed' && userResult.redirect) {
        result = userResult;
      } else if (!userRes.ok) {
        let detail = `HTTP error! status: ${userRes.status}`;
        if (userResult && userResult.detail) detail = userResult.detail;
        throw new Error(detail);
      } else {
          const cpuTrainingUrl = API_CONFIG.buildUrl('/franchise/run-training/cpu-train');
          do {
            const cpuTrainingRes = await fetch(cpuTrainingUrl, {
              method: 'POST',
              headers: jsonHeaders,
              body: JSON.stringify({ franchise_id: franchiseId })
            });
            try {
              result = await cpuTrainingRes.json();
            } catch (_e) {
              result = null;
            }
            if (!cpuTrainingRes.ok) {
              let detail = `HTTP error! status: ${cpuTrainingRes.status}`;
              if (result && result.detail) detail = result.detail;
              throw new Error(detail);
            }
            if (result && result.status === 'processing') {
              const retryAfterMs = Math.max(250, Number(result.retry_after_ms || 1000));
              await new Promise(resolve => window.setTimeout(resolve, retryAfterMs));
            }
          } while (result && result.status === 'processing');
          if (!result || !['success', 'already_completed'].includes(result.status)) {
            throw new Error((result && result.detail) || 'Training did not reach a terminal state.');
          }
      }
    } else {
      console.log('🔍 [TRAINING] Submitting to endpoint:', endpoint);
      console.log('🔍 [TRAINING] Payload:', payload);
      const response = await fetch(API_CONFIG.buildUrl(endpoint), {
        method: 'POST',
        headers: jsonHeaders,
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
      result = await response.json();
    }

    try {
      sessionStorage.removeItem(STORAGE_PLAYBOOK_FOCUS);
      sessionStorage.removeItem(STORAGE_PLAYBOOK_MODE);
      sessionStorage.removeItem(STORAGE_TEAM_DRILLS_SNAPSHOT);
      clearTrainingFormDraftForCurrentContext();
      clearTutorialResumeContext();
    } catch (_clearErr) {}

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
    trainingNewswireOverlayActive = false;
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
      window.PageLoadOverlay.hide();
    }
    showMessageModal(error.message || 'Failed to submit training. Please try again.');
    this.disabled = false;
    this.textContent = 'Submit Training';
  }
});

async function resumeCpuTraining(franchiseId) {
  if (!franchiseId) return;
  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    (typeof API_CONFIG.getAuthHeaders === 'function' ? API_CONFIG.getAuthHeaders() : {})
  );
  showTrainingNewswire(franchiseId);
  let result = null;
  do {
    const response = await fetch(API_CONFIG.buildUrl('/franchise/run-training/cpu-train'), {
      method: 'POST',
      headers,
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    try {
      result = await response.json();
    } catch (_e) {
      result = null;
    }
    if (!response.ok) {
      throw new Error((result && result.detail) || `HTTP error! status: ${response.status}`);
    }
    if (result && result.status === 'processing') {
      const retryAfterMs = Math.max(250, Number(result.retry_after_ms || 1000));
      await new Promise(resolve => window.setTimeout(resolve, retryAfterMs));
    }
  } while (result && result.status === 'processing');

  if (!result || !['success', 'already_completed'].includes(result.status)) {
    throw new Error((result && result.detail) || 'Training did not reach a terminal state.');
  }

  if (result && result.redirect) {
    window.location.href = result.redirect.replace(/^\/static\//, '/');
  }
}

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
        currentSeason = Number(data.season || 1);
        currentTeamName = data.user_team_name || currentTeamName || '';
        prefetchTrainingNewswire(franchiseId);
        if (Array.isArray(data.custom_focus_roster)) {
          customFocusRoster = data.custom_focus_roster;
        }
        if (Array.isArray(data.player_maximizer_ranking_attrs)) {
          customFocusRankingAttrs = data.player_maximizer_ranking_attrs;
        }
        if (data.cpu_training_resume && data.cpu_training_resume.required) {
          try {
            await resumeCpuTraining(franchiseId);
          } catch (resumeError) {
            console.error('Failed to resume CPU training:', resumeError);
            trainingNewswireOverlayActive = false;
            if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
              window.PageLoadOverlay.hide();
            }
            showMessageModal(resumeError.message || 'Failed to resume training. Please try again.');
          }
          return;
        }
        // Update points remaining display
        if (pointsRemainingEl) {
          pointsRemainingEl.textContent = TOTAL_POINTS;
        }
        // Training ends at training (ux-build-plan §5.1). Recruiting is reached from
        // the FCC — secondary hero button, tab badge, or the week-20 gate — not by
        // routing out of Run Training.
        //
        // IMPORTANT: this removes only the ROUTE. The invite itself still fires on
        // week advance using whatever board exists, exactly as before, so no week can
        // be silently lost. Decoupling the EXECUTION was tried and reversed once
        // because Run Training was the only guaranteed weekly trigger — don't.
        if (recruitingInvitesBtn) {
          recruitingInvitesBtn.style.display = 'none';
          recruitingInvitesBtn.onclick = null;
        }
        restoreTrainingFormDraft();
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

function syncPlaybookModeToggleUi() {
  try {
    if (
      sessionStorage.getItem(STORAGE_PLAYBOOK_MODE) === 'custom' &&
      !sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS)
    ) {
      sessionStorage.removeItem(STORAGE_PLAYBOOK_MODE);
    }
  } catch (_e) {}
  const banner = document.getElementById('custom-playbook-banner');
  const btnCurrent = document.getElementById('playbook-mode-current-btn');
  const btnCustom = document.getElementById('playbook-mode-custom-btn');
  const customOn =
    sessionStorage.getItem(STORAGE_PLAYBOOK_MODE) === 'custom' &&
    sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS);
  if (banner) banner.hidden = !customOn;
  if (btnCurrent && btnCustom) {
    btnCurrent.classList.toggle('is-selected', !customOn);
    btnCurrent.classList.toggle('is-ghost', !!customOn);
    btnCurrent.setAttribute('aria-pressed', customOn ? 'false' : 'true');
    btnCustom.classList.toggle('is-selected', !!customOn);
    btnCustom.classList.toggle('is-ghost', !customOn);
    btnCustom.setAttribute('aria-pressed', customOn ? 'true' : 'false');
  }
}

function wireCustomTrainingPlaybook() {
  const pageParams = new URLSearchParams(window.location.search);
  if (pageParams.get('mode') !== 'franchise') {
    const wrap = document.querySelector('.playbook-mode-selection');
    if (wrap) wrap.style.display = 'none';
    return;
  }
  const btnCurrent = document.getElementById('playbook-mode-current-btn');
  const btnCustom = document.getElementById('playbook-mode-custom-btn');
  if (btnCurrent) {
    btnCurrent.addEventListener('click', function () {
      playSound('click-tiny.wav');
      try {
        sessionStorage.removeItem(STORAGE_PLAYBOOK_FOCUS);
        sessionStorage.removeItem(STORAGE_PLAYBOOK_MODE);
      } catch (_e) {}
      syncPlaybookModeToggleUi();
    });
  }
  if (btnCustom) {
    btnCustom.addEventListener('click', function () {
      playSound('click-tiny.wav');
      saveTrainingFormDraft();
      const snap = collectTrainingData();
      try {
        sessionStorage.setItem(
          STORAGE_TEAM_DRILLS_SNAPSHOT,
          JSON.stringify({
            team_offense: snap.team_drills.team_offense || {},
            team_defense: snap.team_drills.team_defense || {},
          })
        );
      } catch (_e) {}
      const p = new URLSearchParams(window.location.search);
      const q = new URLSearchParams();
      q.set('mode', p.get('mode') || 'franchise');
      if (p.get('franchise_id')) q.set('franchise_id', p.get('franchise_id'));
      const tid = p.get('team_id') || p.get('user_team_id');
      if (tid) q.set('team_id', tid);
      if (p.get('session_type')) q.set('session_type', p.get('session_type'));
      window.location.href = `/training-playbooks.html?${q.toString()}`;
    });
  }
  syncPlaybookModeToggleUi();
}

/* ============================================================
   Training polish: tooltips, attribute chips, requirements bar
   ============================================================ */

const ARCH_COLORS = {
  'authoritarian': '#C0392B',
  'systems-coach': '#D4A017',
  'player-maximizer': '#3A8C4A',
  'culture-builder': '#7B5EA7'
};
const ARCH_NAMES = {
  'authoritarian': 'Authoritarian',
  'systems-coach': 'Systems Coach',
  'player-maximizer': 'Player Maximizer',
  'culture-builder': 'Culture Builder'
};
const PM_LEAF_NAMES = {
  'player-maximizer-top-3': 'Top 3',
  'player-maximizer-attributes-4-6': 'Attributes 4–6',
  'player-maximizer-positional-focus': 'Positional Focus',
  'player-maximizer-custom': 'Custom'
};

function archKeyFromValue(value) {
  if (!value) return null;
  if (value.startsWith('authoritarian')) return 'authoritarian';
  if (value.startsWith('systems-coach')) return 'systems-coach';
  if (value.startsWith('player-maximizer')) return 'player-maximizer';
  if (value.startsWith('culture-builder')) return 'culture-builder';
  return null;
}

/* --- Tooltip copy registries (source of truth: training tutorial) --- */
const DRILL_TOOLTIPS = {
  'offense-inside':      { code: 'SC', color: '#f79420', attr: 'Inside Scoring',   desc: "Sharpens scoring around the rim and in the post." },
  'offense-outside':     { code: 'SH', color: '#f79420', attr: 'Outside Shooting', desc: "Develops perimeter and mid-range shooting touch." },
  'defense-inside':      { code: 'ID', color: '#4a90d9', attr: 'Inside Defense',   desc: "Builds post defense, rim protection and interior toughness." },
  'defense-outside':     { code: 'OD', color: '#4a90d9', attr: 'Outside Defense',  desc: "Hones on-ball perimeter defense and closeouts." },
  'technical-passing':   { code: 'PS', color: '#7b5ea7', attr: 'Passing',          desc: "Improves court vision, timing and passing accuracy." },
  'technical-ball-handling': { code: 'BH', color: '#7b5ea7', attr: 'Ball Handling', desc: "Tightens handle and ball security under pressure." },
  'technical-rebounding':{ code: 'RB', color: '#7b5ea7', attr: 'Rebounding',       desc: "Drills boxing out and finishing on the glass." },
  'weight-strength':     { code: 'ST', color: '#aeb8cc', attr: 'Strength',         desc: "Adds physical strength for finishing and holding position." },
  'weight-agility':      { code: 'AG', color: '#aeb8cc', attr: 'Agility',          desc: "Builds quickness, lateral speed and body control." },
  'general-conditioning':{ code: 'ND', color: '#aeb8cc', attr: 'Conditioning',     desc: "Builds team-wide stamina so legs stay fresh deep into games." },
  'general-free-throws': { code: 'FT', color: '#d4a017', attr: 'Free Throws',      desc: "Reps from the line to convert when it matters most." },
  'general-film-study':  { code: 'IQ', color: '#d4a017', attr: 'Basketball IQ',    desc: "Film Study gives coaches better insight into upcoming opponents — especially tendencies from their most recent game." },
  'general-breaks':      { desc: "Breaks boost the effectiveness of all drills and reduce fatigue heading into the next game. But too many run the risk of straining team chemistry and weakening your team's Fight and Discipline attributes. Strong-chemistry teams absorb more downtime with less risk." },
  'team-offense-install':       { desc: "Walk through new or existing offensive plays — no active defense. Pairs well with Film Study to tailor your sets to an opponent's defensive tendencies." },
  'team-defense-install':       { desc: "Walk through new or existing defensive schemes — no active offense. Pairs well with Film Study to tailor your coverage to an opponent's offensive tendencies." },
  'fast-break-offense-install': { desc: "Walk through new or existing fast break plays — no active defense. Pairs well with Film Study to attack an opponent's transition defense." },
  'fast-break-defense-install': { desc: "Walk through new or existing fast break defenses — no active offense. Pairs well with Film Study to counter an opponent's fast break tendencies." },
  'press-defense-install':      { desc: "Walk through new or existing press and trap schemes — no active offense. Pairs well with Film Study to exploit an opponent's press-break tendencies." },
  'press-offense-install':      { desc: "Walk through new or existing press and trap breaks — no active defense. Pairs well with Film Study to counter an opponent's pressing tendencies." },
  'team-scrimmages':            { desc: "Scrimmages sharpen execution and reinforce system cohesion — a multiplying effect on the Installs you run. They tend to lift chemistry, but an intense scrimmage can occasionally boil over, and over-scrimmaging risks fatigue." }
};

const FOCUS_TOOLTIPS = {
  'authoritarian-discipline': { name: 'Discipline', desc: "Demand structure and accountability, with zero tolerance for slippage." },
  'authoritarian-rebounding': { name: 'Rebounding', desc: "Make dominating the glass a non-negotiable team identity." },
  'authoritarian-execution':  { name: 'Execution',  desc: "Accept nothing less than precision and total attention to detail." },
  'authoritarian-teamwork':   { name: 'Teamwork',   desc: "Subordinate every ego to the team's success." },
  'systems-coach-offense':     { name: 'Offense',      desc: "Drill offensive execution into the team's DNA." },
  'systems-coach-defense':     { name: 'Defense',      desc: "Make disciplined defensive execution the team's standard." },
  'systems-coach-fast-breaks': { name: 'Fast Breaks',  desc: "Master transition on both ends as a tactical edge." },
  'systems-coach-press-trap':  { name: 'Press / Trap', desc: "Make pressure defense and press-breaks a system strength." },
  'culture-builder-inspire':    { name: 'Inspire',              desc: "Convince every player they can exceed their own ceiling." },
  'culture-builder-confidence': { name: 'Confidence',           desc: "Build unshakable self-belief through relentless positivity." },
  'culture-builder-community':  { name: 'Community Engagement', desc: "Root the team in its community and rally collective passion." },
  'culture-builder-teamwork':   { name: 'Team Building',        desc: "Forge a brotherhood that plays for each other." },
  'player-maximizer-choose-attributes': {
    name: 'Choose Attributes',
    desc: "Opens a per-player attribute picker. Pick a development mode for the whole roster:",
    modes: [
      ['Top 3', "Sharpen what each player already does best."],
      ['Attributes 4–6', "Take each player from good to great in emerging skills."],
      ['Positional Focus', "Build positional identity around each player's core strengths."],
      ['Custom', "Develop each player around the attributes you choose."]
    ]
  }
};

/* --- Shared tooltip element + positioning --- */
let trainingTooltipEl = null;
let trainingTooltipTrigger = null;
let lastPointerType = 'mouse';

document.addEventListener('pointerdown', function (e) {
  lastPointerType = e.pointerType || 'mouse';
}, true);

function ensureTrainingTooltipEl() {
  if (trainingTooltipEl) return trainingTooltipEl;
  trainingTooltipEl = document.createElement('div');
  trainingTooltipEl.className = 'training-tooltip';
  trainingTooltipEl.setAttribute('role', 'tooltip');
  document.body.appendChild(trainingTooltipEl);
  return trainingTooltipEl;
}

function positionTrainingTooltip(trigger) {
  const tt = ensureTrainingTooltipEl();
  const r = trigger.getBoundingClientRect();
  const tw = tt.offsetWidth;
  const th = tt.offsetHeight;
  const gap = 10;
  const margin = 8;
  let left = r.left + r.width / 2 - tw / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - margin - tw));
  let top = r.top - th - gap;
  let flip = false;
  if (top < margin) {
    top = r.bottom + gap;
    flip = true;
  }
  tt.style.left = Math.round(left) + 'px';
  tt.style.top = Math.round(top) + 'px';
  tt.classList.toggle('flip', flip);
  const arrowLeft = (r.left + r.width / 2) - left;
  tt.style.setProperty('--arrow-left', Math.round(Math.max(12, Math.min(tw - 12, arrowLeft))) + 'px');
}

function showTrainingTooltip(trigger) {
  const html = trigger && trigger.__ttHtml;
  if (!html) return;
  const tt = ensureTrainingTooltipEl();
  tt.innerHTML = html;
  trainingTooltipTrigger = trigger;
  positionTrainingTooltip(trigger);
  requestAnimationFrame(function () {
    if (trainingTooltipTrigger === trigger) tt.classList.add('is-visible');
  });
}

function hideTrainingTooltip() {
  if (!trainingTooltipEl) return;
  trainingTooltipEl.classList.remove('is-visible');
  trainingTooltipTrigger = null;
}

function registerTrainingTooltip(trigger, html, focusEl) {
  if (!trigger || !html) return;
  trigger.__ttHtml = html;
  trigger.classList.add('has-tooltip');
  trigger.addEventListener('pointerenter', function (e) {
    if (e.pointerType !== 'touch') showTrainingTooltip(trigger);
  });
  trigger.addEventListener('pointerleave', function (e) {
    if (e.pointerType !== 'touch') hideTrainingTooltip();
  });
  trigger.addEventListener('click', function () {
    if (lastPointerType === 'touch') {
      if (trainingTooltipTrigger === trigger) hideTrainingTooltip();
      else showTrainingTooltip(trigger);
    }
  });
  if (focusEl) {
    focusEl.addEventListener('focus', function () { showTrainingTooltip(trigger); });
    focusEl.addEventListener('blur', function () { hideTrainingTooltip(); });
  }
}

// Dismiss on scroll and on outside tap
window.addEventListener('scroll', hideTrainingTooltip, true);
document.addEventListener('click', function (e) {
  if (lastPointerType === 'touch' && trainingTooltipTrigger && !trainingTooltipTrigger.contains(e.target)) {
    hideTrainingTooltip();
  }
}, true);

function buildDrillTooltipHtml(d) {
  let head = '';
  if (d.code) {
    head = '<div class="tt-head"><span class="attr-chip" style="background:' + d.color + '">' + d.code +
      '</span><span class="tt-attr">' + d.attr + '</span></div>';
  }
  return head + '<div class="tt-desc">' + d.desc + '</div>';
}

function buildFocusTooltipHtml(value, f) {
  const archKey = archKeyFromValue(value);
  const archColor = ARCH_COLORS[archKey] || '#f79420';
  const archName = ARCH_NAMES[archKey] || '';
  let modes = '';
  if (f.modes) {
    modes = '<ul class="tt-modes">' + f.modes.map(function (m) {
      return '<li class="tt-mode"><b>' + m[0] + '</b> — ' + m[1] + '</li>';
    }).join('') + '</ul>';
  }
  return '<div class="tt-eyebrow" style="color:' + archColor + '">' + archName + '</div>' +
    '<div class="tt-name">' + f.name + '</div>' +
    '<div class="tt-desc">' + f.desc + '</div>' + modes;
}

/* --- Attribute code chips on single-attribute drills --- */
function injectAttributeChip(slider, d) {
  if (!d || !d.code) return;
  const label = slider.closest('.slider-label');
  const lt = label && label.querySelector('.label-text');
  if (!lt || lt.querySelector('.attr-chip')) return;
  const chip = document.createElement('span');
  chip.className = 'attr-chip';
  chip.style.background = d.color;
  chip.textContent = d.code;
  chip.setAttribute('aria-hidden', 'true');
  lt.appendChild(chip);
}

/* Hover/tap target for a drill row — its label text, or the drill title for bare installs. */
function triggerForSlider(slider) {
  const label = slider.closest('.slider-label');
  const lt = label && label.querySelector('.label-text');
  if (lt && lt.textContent.trim()) return lt;
  const group = slider.closest('.drill-group');
  const title = group && group.querySelector('.drill-title');
  return title || label;
}

function setupTrainingTooltips() {
  Object.keys(DRILL_TOOLTIPS).forEach(function (id) {
    const slider = document.getElementById(id);
    if (!slider) return;
    const d = DRILL_TOOLTIPS[id];
    injectAttributeChip(slider, d);
    const trigger = triggerForSlider(slider);
    if (trigger) registerTrainingTooltip(trigger, buildDrillTooltipHtml(d), slider);
  });

  document.querySelectorAll('.archetype-option').forEach(function (opt) {
    const radio = opt.querySelector('input[name="coaching-focus"]');
    if (!radio) return;
    const f = FOCUS_TOOLTIPS[radio.value];
    if (!f) return;
    registerTrainingTooltip(opt, buildFocusTooltipHtml(radio.value, f), radio);
  });
}

/* --- Requirements bar --- */
const reqBarEl = document.getElementById('requirements-bar');
const reqPointsChip = document.getElementById('req-points');
const reqPointsUsedEl = document.getElementById('req-points-used');
const reqPointsTotalEl = document.getElementById('req-points-total');
const reqPointsMeterEl = document.getElementById('req-points-meter');
const reqFocusChip = document.getElementById('req-focus');
const reqFocusValueEl = document.getElementById('req-focus-value');
const reqFocusNudgeBtn = document.getElementById('req-focus-nudge');
const reqReadoutEl = document.getElementById('req-readout');

function friendlyFocusName(radio) {
  const v = radio.value;
  if (v === CHOOSE_ATTRIBUTES_VALUE) {
    if (playerMaximizerResolvedFocus && PM_LEAF_NAMES[playerMaximizerResolvedFocus]) {
      return PM_LEAF_NAMES[playerMaximizerResolvedFocus];
    }
    return 'Choose Attributes';
  }
  if (PM_LEAF_NAMES[v]) return PM_LEAF_NAMES[v];
  return getFocusLabelText(radio) || v;
}

function updateRequirementsBar() {
  if (!reqBarEl) return;
  const total = TOTAL_POINTS;
  const used = calculateTotalPoints();
  const remaining = total - used;
  const pointsComplete = remaining === 0;

  if (reqPointsUsedEl) reqPointsUsedEl.textContent = formatPointsDisplay(used);
  if (reqPointsTotalEl) reqPointsTotalEl.textContent = formatPointsDisplay(total);
  if (reqPointsMeterEl) {
    const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
    reqPointsMeterEl.style.width = pct + '%';
  }
  if (reqPointsChip) reqPointsChip.classList.toggle('is-complete', pointsComplete);

  const checked = document.querySelector('input[name="coaching-focus"]:checked');
  const focusSelected = !!checked;
  const focusComplete = focusSelected && isPlayerMaximizerSubmitReady();

  if (focusSelected) {
    const archKey = archKeyFromValue(checked.value);
    const archColor = ARCH_COLORS[archKey] || '#f79420';
    const archName = ARCH_NAMES[archKey] || '';
    const focusName = friendlyFocusName(checked);
    if (reqFocusValueEl) reqFocusValueEl.textContent = archName ? (focusName + ' · ' + archName) : focusName;
    if (reqFocusChip) reqFocusChip.style.setProperty('--arch', archColor);
  } else {
    if (reqFocusValueEl) reqFocusValueEl.textContent = 'Not selected';
    if (reqFocusChip) reqFocusChip.style.removeProperty('--arch');
  }
  if (reqFocusChip) reqFocusChip.classList.toggle('is-selected', focusComplete);

  const nudge = pointsComplete && !focusSelected;
  if (reqFocusChip) reqFocusChip.classList.toggle('is-nudge', nudge);
  if (reqFocusNudgeBtn) reqFocusNudgeBtn.hidden = !nudge;

  const readyCount = (pointsComplete ? 1 : 0) + (focusComplete ? 1 : 0);
  if (reqReadoutEl) {
    reqReadoutEl.textContent = readyCount === 2 ? 'Ready to submit' : (readyCount + ' of 2 ready');
    reqReadoutEl.classList.toggle('is-ready', readyCount === 2);
  }
}

function scrollToCoachingFocus() {
  const sec = document.querySelector('.coaching-section');
  if (!sec) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  sec.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  sec.classList.remove('coaching-flash');
  void sec.offsetWidth; // restart animation
  sec.classList.add('coaching-flash');
  window.setTimeout(function () { sec.classList.remove('coaching-flash'); }, 1600);
}

if (reqFocusNudgeBtn) {
  reqFocusNudgeBtn.addEventListener('click', function () {
    playSound('click-tiny.wav');
    scrollToCoachingFocus();
  });
}

/* Keep the requirements bar docked just below the sticky header. */
function positionRequirementsBar() {
  const header = document.querySelector('.training-header');
  if (!reqBarEl || !header) return;
  const headerTop = parseFloat(getComputedStyle(header).top) || 0;
  reqBarEl.style.top = Math.round(headerTop + header.offsetHeight + 8) + 'px';
}

window.addEventListener('resize', positionRequirementsBar);
if (typeof ResizeObserver !== 'undefined') {
  const headerForObserve = document.querySelector('.training-header');
  if (headerForObserve) {
    new ResizeObserver(positionRequirementsBar).observe(headerForObserve);
  }
}

// Wire up tooltips/chips and prime the requirements bar
setupTrainingTooltips();
positionRequirementsBar();
updateRequirementsBar();

// Initialize training points on page load
(async function initTrainingPage() {
  const redirected = await redirectIfTrainingAlreadyCommitted();
  if (redirected) return;
  wireTrainingTutorialButton();
  await initializeTrainingPoints();
  wireCustomTrainingPlaybook();
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
