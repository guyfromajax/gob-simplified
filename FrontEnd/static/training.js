import { TRAINING_SHELL } from '/training-shell.js';

function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

let root = null;
let started = false;
let _onPageShow = null;
let _onResizeSliders = null;
let _onResizeReq = null;
let _onScrollTip = null;
let _reqObserver = null;
let _tabShown = null;
let _onKeyModal = null;

function byId(id) {
  if (id === 'play-now') return document.getElementById(id);
  if (root) {
    if (root.id === id) return root;
    const found = root.querySelector('#' + CSS.escape(id));
    if (found) return found;
  }
  return document.getElementById(id);
}

function qsa(sel) {
  return root ? root.querySelectorAll(sel) : document.querySelectorAll(sel);
}

function rootQuery(sel) {
  return root ? root.querySelector(sel) : document.querySelector(sel);
}

function inAppShell() {
  return !!(root && (root.id === 'training-view' || (root.closest && root.closest('#training-view'))));
}

function bindDom() {
  pointsRemainingEl = byId('points-remaining');
  submitBtn = byId('submit-btn');
  autoTrainBtn = byId('auto-train-btn');
  recruitingInvitesBtn = byId('recruiting-invites-btn');
  backBtn = byId('back-btn');
  allSliders = qsa('.slider');
  coachingRadios = qsa('input[name="coaching-focus"]');
  offensePlaysRadios = qsa('input[name="offense-plays"]');
  defensePlaysRadios = qsa('input[name="defense-plays"]');
  autoTrainModal = byId('auto-train-modal');
  autoTrainModalTitle = byId('auto-train-modal-title');
  autoTrainModalFocus = byId('auto-train-modal-focus');
  autoTrainModalClose = byId('auto-train-modal-close');
  customFocusModal = byId('custom-focus-modal');
  customFocusThead = byId('custom-focus-thead');
  customFocusTbody = byId('custom-focus-tbody');
  customFocusAssignBtn = byId('custom-focus-assign-btn');
  customFocusCancelBtn = byId('custom-focus-cancel-btn');
  reqBarEl = byId('requirements-bar');
  reqPointsChip = byId('req-points');
  reqPointsUsedEl = byId('req-points-used');
  reqPointsTotalEl = byId('req-points-total');
  reqPointsMeterEl = byId('req-points-meter');
  reqFocusChip = byId('req-focus');
  reqFocusValueEl = byId('req-focus-value');
  reqFocusNudgeBtn = byId('req-focus-nudge');
  playerDevSection = byId('player-dev-section');
}

// Training Page JavaScript
let TOTAL_POINTS = 24; // Will be updated from API for franchise mode

// DOM Elements — bound in bindDom() after the shell is in `root`.
let pointsRemainingEl = null;
let submitBtn = null;
let autoTrainBtn = null;
let recruitingInvitesBtn = null;
let backBtn = null;
let allSliders = [];
let coachingRadios = [];
let offensePlaysRadios = [];
let defensePlaysRadios = [];
let autoTrainModal = null;
let autoTrainModalTitle = null;
let autoTrainModalFocus = null;
let autoTrainModalClose = null;
let customFocusModal = null;
let customFocusThead = null;
let customFocusTbody = null;
let customFocusAssignBtn = null;
let customFocusCancelBtn = null;
let reqBarEl = null;
let reqPointsChip = null;
let reqPointsUsedEl = null;
let reqPointsTotalEl = null;
let reqPointsMeterEl = null;
let reqFocusChip = null;
let reqFocusValueEl = null;
let reqFocusNudgeBtn = null;
let playerDevSection = null;
let currentWeek = 1;
let currentTeamName = '';
let currentSeason = 1;
let trainingNewswirePromise = null;
let trainingNewswireOverlayActive = false;
let trainingNewswireError = null;

/** @type {{ player_id: string, name: string, attrs: Record<string, number> }[]} */
let customFocusRoster = [];
let positionTallies = null;
let focusTallies = null;
/** @type {string[]} */
let customFocusRankingAttrs = [];
/** @type {Record<string, string[]>} playerId -> up to 3 distinct attr codes */
let customFocusDraft = {};
/** @type {Record<string, string[]>} committed picks after Assign */
let customFocusCommitted = {};
let trainingDirty = false;
// True after applyTrainingWeekState hides the weekly allocation (submitted week or
// tournament). The focus page must not enable Submit Training on those weeks.
let trainingAllocationClosed = false;
/** 'weekly' (Advance focus page) or 'player-dev' (Prep › Player Training). */
let trainingSections = 'weekly';
let trainingFormSnapshot = null;

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
  const urlParams = liveParams();
  const key = trainingFormDraftStorageKey(urlParams);
  if (!key) return;
  const sliders = {};
  qsa('.slider').forEach(function (el) {
    if (el.id) sliders[el.id] = parseInt(el.value, 10) || 0;
  });
  const checked = rootQuery('input[name="coaching-focus"]:checked');
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

function isWeekly() {
  return trainingSections === 'weekly';
}

function resolveSections(options) {
  if (options && (options.sections === 'weekly' || options.sections === 'player-dev')) {
    return options.sections;
  }
  return inAppShell() ? 'player-dev' : 'weekly';
}

function captureTrainingFormSnapshot() {
  const sliders = {};
  qsa('.slider').forEach(function (el) {
    if (el.id) sliders[el.id] = parseInt(el.value, 10) || 0;
  });
  const checked = rootQuery('input[name="coaching-focus"]:checked');
  trainingFormSnapshot = {
    sliders: sliders,
    coaching_radio: checked ? checked.value : null,
    player_maximizer_resolved: playerMaximizerResolvedFocus,
    custom_focus_committed: JSON.parse(JSON.stringify(customFocusCommitted || {})),
  };
}

function applyTrainingFormState(o) {
  if (!o) return;
  if (o.sliders && typeof o.sliders === 'object') {
    Object.keys(o.sliders).forEach(function (id) {
      const el = byId(id);
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
  let radioVal = o.coaching_radio || null;
  if (radioVal === LEGACY_CHOOSE_ATTRIBUTES_VALUE) radioVal = playerMaximizerResolvedFocus;
  committedCoachingValue = radioVal;
  setCoachingFocusRadio(radioVal);
  updatePointsRemaining();
}

function restoreTrainingFormSnapshot() {
  applyTrainingFormState(trainingFormSnapshot);
}

function confirmTrainingLeave(proceed) {
  if (!window.GOBLeaveConfirm) {
    proceed();
    return;
  }
  window.GOBLeaveConfirm.open({
    title: 'Unsaved Training',
    copy: 'Leave without submitting this week\'s allocation? Your draft is kept until you submit.',
    saveLabel: 'Keep Draft',
    onSave: function () {
      trainingDirty = false;
      return true;
    },
    onDiscard: function () {
      restoreTrainingFormSnapshot();
      clearTrainingFormDraftForCurrentContext();
      trainingDirty = false;
    },
    proceed: proceed,
  });
}

function applySections() {
  const weekly = isWeekly();
  ['.main-content-grid', '.coaching-section'].forEach(function (sel) {
    const el = rootQuery(sel);
    if (el) el.hidden = !weekly;
  });
  ['requirements-bar', 'auto-train-btn', 'submit-btn', 'training-tutorial-btn'].forEach(function (id) {
    const el = byId(id);
    if (el) el.hidden = !weekly;
  });
  const header = rootQuery('.training-header');
  if (header) header.hidden = !weekly;
  const note = byId('training-state-note');
  if (note && !weekly) note.hidden = true;
  // Player Development shows in both modes once the roster is in (renderPlayerDevelopment):
  // under Coaching Focus on the weekly page, and as the whole tab in Prep.
  const pointer = byId('training-advance-pointer');
  if (pointer) pointer.hidden = weekly;
  if (backBtn) {
    backBtn.textContent = 'Back to Locker Room';
    backBtn.hidden = !weekly;
  }
  if (root) root.setAttribute('data-training-sections', trainingSections);
  document.body.classList.toggle('training-weekly', weekly);
  document.body.classList.toggle('training-player-dev', !weekly);
}

// Draft persists; dirty stays true so leave-confirm can fire on the focus page.
function noteTrainingEdit() {
  trainingDirty = true;
  saveTrainingFormDraft();
}

function clearTrainingFormDraftForCurrentContext() {
  const urlParams = liveParams();
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
  return window.location.pathname + currentSearch() + (window.location.hash || '');
}

function navigateToTrainingTutorial() {
  playSound('SFX_SELECT');
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
  const btn = byId('training-tutorial-btn');
  if (!btn) return;
  btn.addEventListener('click', navigateToTrainingTutorial);
}

/**
 * Player Development: the 12 active players, their training position and focus.
 *
 * Rendering lives in js/shared/playerDevelopmentGrid.js. It has two hosts and both are this
 * module: the weekly training page (under Coaching Focus) and Prep › Player Training.
 * This function's whole job is adapting `custom_focus_roster` (already RT-descending,
 * already carrying both fields, year, all 12 attributes, height/weight and every position
 * rating) into that module's shape.
 */
function playerDevFranchiseId() {
  return liveParams().get('franchise_id') || '';
}

function playerDevRows() {
  return (Array.isArray(customFocusRoster) ? customFocusRoster : []).map(function (row) {
    return {
      id: row.player_id,
      _id: row.player_id,
      player_id: row.player_id,
      name: row.name,
      year: row.year,
      height: row.height,
      weight: row.weight,
      attributes: row.attrs || {},
      position_ratings: row.position_ratings || {},
      training_position: row.training_position || null,
      training_focus: row.training_focus || null,
      resolved_training_position: row.resolved_training_position || null,
      resolved_training_focus: row.resolved_training_focus || null,
      image_id: row.image_id || null,
      portrait_source: row.portrait_source || 'player',
      jersey: row.jersey,
      pos: row.pos || null,
      potential_rt_ratcheted: row.potential_rt_ratcheted,
    };
  });
}

function renderPlayerDevelopment() {
  const grid = window.GOBPlayerDevelopmentGrid;
  if (!playerDevSection || !grid) return;
  const rows = playerDevRows();
  if (!rows.length) {
    playerDevSection.hidden = true;
    return;
  }
  playerDevSection.hidden = false;
  const weekly = isWeekly();
  const pointer = byId('training-advance-pointer');
  if (pointer) pointer.hidden = weekly;
  // Both hosts (the weekly page and Prep > Player Training) draw the same cards, four
  // across, in RT order reading left to right; the grid component orders them.
  grid.render(playerDevSection, rows, {
    tallies: (positionTallies && focusTallies)
      ? { positions: positionTallies, focuses: focusTallies }
      : null,
    getFranchiseId: playerDevFranchiseId,
    // Write back to the source array so a later re-render keeps the change.
    onSaved: function (playerId, field, value) {
      const key = field === 'training_focus'
        ? 'resolved_training_focus' : 'resolved_training_position';
      (customFocusRoster || []).forEach(function (r) {
        if (String(r.player_id) === String(playerId)) { r[field] = value; r[key] = value; }
      });
    },
  });
}

/**
 * "Training by Position" leaves the page, so the in-progress allocation is saved as a
 * draft first and a resume context is set — the same pattern the Training Tutorial button
 * uses. A coach who reads the chart comes back to the points he had already spent.
 */
function wirePlayerDevelopmentTutorialButton() {
  const btn = byId('player-dev-tutorial-btn');
  if (!btn) return;
  btn.addEventListener('click', function () {
    playSound('SFX_SELECT');
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
    window.location.href = '/tutorial-advanced-training-by-position.html';
  });
}
wirePlayerDevelopmentTutorialButton();

/** Old drafts stored this umbrella value plus a resolved leaf; the leaf is now the radio. */
const LEGACY_CHOOSE_ATTRIBUTES_VALUE = 'player-maximizer-choose-attributes';
const PM_CUSTOM_VALUE = 'player-maximizer-custom';

/**
 * The four Player Maximizer options. Each is its own Coaching Focus radio, and choosing
 * one opens the attribute modal under that option's name.
 */
const PM_LEAVES = {
  'player-maximizer-top-3': {
    mode: 'top-3',
    title: 'Top 3 Attributes',
    hint: 'Sharpens what each player already does best. Highlighted attributes get the focus.',
  },
  'player-maximizer-attributes-4-6': {
    mode: 'attributes-4-6',
    title: 'Attributes 4\u20136',
    hint: 'Takes each player from good to great in emerging skills. Highlighted attributes get the focus.',
  },
  'player-maximizer-positional-focus': {
    mode: 'positional',
    title: 'Positional Focus',
    hint: 'Builds positional identity around each player\u2019s best position. Highlighted attributes get the focus.',
  },
  'player-maximizer-custom': {
    mode: 'custom',
    title: 'Custom',
    hint: 'Pick three attributes for each player.',
  },
};

/** The assigned Player Maximizer leaf, or null. Kept in the draft for older readers. */
let playerMaximizerResolvedFocus = null;
/** The Coaching Focus value in force: what Cancel in the attribute modal returns to. */
let committedCoachingValue = null;
/** The Player Maximizer leaf the attribute modal is showing. */
let pmModalValue = null;

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
  const leaf = PM_LEAVES[pmModalValue];
  return leaf ? leaf.mode : 'top-3';
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
  // v3 invalidates Week 1 payloads that ranked matchups across the full season.
  return `gob_training_newswire_v3_${franchiseId}_s${season}_w${week}`;
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

/**
 * Player Training is always the settings page. It used to bounce to the training report
 * whenever the week was already submitted, which is what made one sub-tab show two
 * unrelated screens. Now it stays put and says which state the week is in; the report is a
 * drill-in you open deliberately, from here, the Office card or News.
 *
 * Returns true when there is no weekly allocation to make, so the caller can skip the
 * point-budget setup. Player Development is unaffected either way — it saves per change
 * and applies to the next training that runs.
 */
async function applyTrainingWeekState() {
  if (!isWeekly()) return false;
  const urlParams = liveParams();
  const mode = urlParams.get('mode');
  const franchiseId = urlParams.get('franchise_id');
  const teamId = urlParams.get('team_id') || urlParams.get('user_team_id');
  if (mode !== 'franchise' || !franchiseId) return false;

  let data = null;
  try {
    data = await fetchFranchiseCommandCenterData(franchiseId);
  } catch (error) {
    console.warn('⚠️ [TRAINING] Unable to verify committed training state:', error);
    return false;
  }
  if (!data) return false;

  const week = Number(data.week || 1);
  const noTrainingWeek = !!data.training_disabled_for_postseason
    || !!data.training_disabled_for_eos;

  if (noTrainingWeek) {
    // /franchise/training-points now returns 200 with training_unavailable (and the
    // roster) after week 26, so the grid still loads. There is still no weekly budget
    // and nothing to submit.
    showTrainingStateNote({
      head: 'No team training during the tournament',
      body: 'Weekly training runs through week 26. Player development focus below still '
        + 'saves, and applies from next season\u2019s Training Camp.',
    });
    trainingAllocationClosed = true;
    return true;
  }

  if (data.training_completed) {
    showTrainingStateNote({
      head: 'Training submitted for this week',
      body: 'Player development focus below still saves, and applies to next week\u2019s '
        + 'training.',
      linkText: 'View training report \u2192',
      linkHref: trainingReportHref(franchiseId, teamId, week),
    });
    trainingAllocationClosed = true;
    return true;
  }

  trainingAllocationClosed = false;
  return false;
}

function trainingReportHref(franchiseId, teamId, week) {
  const params = emptyParams();
  params.set('mode', 'franchise');
  params.set('franchise_id', franchiseId);
  if (teamId) params.set('team_id', teamId);
  params.set('week', String(week));
  params.set('from', 'training');
  params.set('origin', 'prep');
  return `/training-report.html?${params.toString()}`;
}

/**
 * Swap the weekly allocation for a one-line explanation. Player Development is deliberately
 * left visible — it is the part that still does something on these weeks.
 */
function showTrainingStateNote(opts) {
  const note = byId('training-state-note');
  if (!note) return;
  const head = byId('training-state-note-head');
  const body = byId('training-state-note-body');
  const link = byId('training-state-note-link');
  if (head) head.textContent = opts.head || '';
  if (body) body.textContent = opts.body || '';
  if (link) {
    if (opts.linkHref) {
      link.textContent = opts.linkText || 'Open';
      link.href = opts.linkHref;
      link.hidden = false;
    } else {
      link.hidden = true;
    }
  }
  note.hidden = false;

  ['.main-content-grid', '.coaching-section'].forEach(function (sel) {
    const el = rootQuery(sel);
    if (el) el.hidden = true;
  });
  ['requirements-bar', 'auto-train-btn', 'submit-btn'].forEach(function (id) {
    const el = byId(id);
    if (el) el.hidden = true;
  });
  document.body.classList.add('training-no-allocation');
  // The top-bar Advance must not offer Submit Training for a week that cannot take it.
  if (window.GOBAdvance && window.GOBAdvance.clearOverride) window.GOBAdvance.clearOverride();
}

function primeSliderPrev() {
  allSliders.forEach(slider => {
    slider.dataset.prev = '0';
  });
}

const PS_CLEAR_SVG = '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6"/></svg>';

/**
 * Build the point selector for one drill: a clear control, five boxes and the number.
 *
 * The <input type="range"> stays the model. Everything that reads a drill value — the
 * points counter, the draft save/restore, Auto-Train, collectTrainingData — still reads
 * `slider.value`, so this is visual plus click targets and changes no contract. The
 * input is clipped out of sight but stays focusable: arrow keys change the value, and
 * Home, Backspace, Delete or 0 clear it.
 */
function ensureTrainingSliderVisual(slider) {
  const wrapper = slider?.closest('.slider-container');
  if (!wrapper) return null;
  let row = wrapper.querySelector('.ps');
  if (row) return row;

  row = document.createElement('div');
  row.className = 'ps';
  // The range input carries the accessible name and value; these are pointer shortcuts
  // to it, so they stay out of the accessibility tree rather than repeating it.
  const clear = document.createElement('button');
  clear.type = 'button';
  clear.className = 'ps-clear';
  clear.dataset.value = '0';
  clear.title = 'Clear';
  clear.setAttribute('aria-hidden', 'true');
  clear.tabIndex = -1;
  clear.innerHTML = PS_CLEAR_SVG;
  clear.addEventListener('click', function () {
    setSliderValueFromPip(slider, 0);
  });
  row.appendChild(clear);
  for (let i = 1; i <= 5; i++) {
    const pip = document.createElement('button');
    pip.type = 'button';
    pip.className = 'pip x';
    pip.dataset.value = String(i);
    pip.setAttribute('aria-hidden', 'true');
    pip.tabIndex = -1;
    pip.addEventListener('click', function () {
      setSliderValueFromPip(slider, i);
    });
    row.appendChild(pip);
  }
  const numeral = document.createElement('span');
  numeral.className = 'ps-n z';
  numeral.setAttribute('aria-hidden', 'true');
  numeral.textContent = '0';
  row.appendChild(numeral);
  wrapper.appendChild(row);
  if (!slider.dataset.clearKeys) {
    slider.dataset.clearKeys = '1';
    slider.addEventListener('keydown', function (event) {
      if (event.key === 'Backspace' || event.key === 'Delete' || event.key === '0') {
        event.preventDefault();
        setSliderValueFromPip(slider, 0);
      }
    });
  }
  return row;
}

/**
 * A box click routes through the input's own `input` handler, so over-allocation is
 * refused by the one rule that already guards dragging and keyboard use.
 */
function setSliderValueFromPip(slider, value) {
  if (slider.disabled) return;
  const next = Math.max(0, Math.min(5, Number(value) || 0));
  if (next === (parseInt(slider.value, 10) || 0)) return;
  slider.value = String(next);
  slider.dispatchEvent(new Event('input', { bubbles: true }));
  slider.dispatchEvent(new Event('change', { bubbles: true }));
}

function updateTrainingSliderVisual(slider, rawValue) {
  const row = ensureTrainingSliderVisual(slider);
  if (!row) return;
  const value = Math.max(0, Math.min(5, Number(rawValue) || 0));
  const spent = calculateTotalPoints();
  const headroom = TOTAL_POINTS - spent + value;   // what this drill alone could reach
  row.dataset.value = String(value);
  row.classList.toggle('has-points', value > 0);
  row.querySelectorAll('.pip').forEach((pip) => {
    const n = Number(pip.dataset.value);
    pip.classList.toggle('f', n <= value);
    pip.classList.toggle('x', n > value);
    // Boxes past the remaining budget dim and cannot be clicked.
    pip.disabled = n > headroom;
  });
  const clear = row.querySelector('.ps-clear');
  if (clear) clear.disabled = value === 0;
  const numeral = row.querySelector('.ps-n');
  if (numeral) {
    numeral.textContent = String(value);
    numeral.classList.toggle('z', value === 0);
  }
}

/** Repaint every stepper's reachable range after the budget moves. */
function refreshAllTrainingSliderVisuals() {
  allSliders.forEach(function (slider) {
    updateTrainingSliderVisual(slider, slider.value);
  });
}

/** No-op since the pip swap: there is no range thumb to position a bubble against.
 *  Kept as a seam so the call sites (resize, restore, auto-train) stay one shape. */
function updateTrainingSliderValuePosition(_slider) {}

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
  const selectedFocus = rootQuery('input[name="coaching-focus"]:checked');
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

/** A Player Maximizer option is ready once chosen; Custom also needs three picks per player. */
function isPlayerMaximizerSubmitReady() {
  const sel = rootQuery('input[name="coaching-focus"]:checked');
  if (!sel || !PM_LEAVES[sel.value]) return true;
  if (sel.value === PM_CUSTOM_VALUE) return isCustomFocusComplete();
  return true;
}

function resetCustomFocusCommitted() {
  customFocusCommitted = {};
  customFocusDraft = {};
}

function isCustomFocusModalOpen() {
  return !!(customFocusModal && customFocusModal.classList.contains('is-visible'));
}

/** Open the attribute modal for one Player Maximizer option. Its title is that option. */
function openCustomFocusModal(value) {
  if (!customFocusModal || !customFocusThead || !customFocusTbody) return false;
  const leaf = PM_LEAVES[value];
  if (!leaf) return false;
  const urlParams = liveParams();
  if (urlParams.get('mode') !== 'franchise' || !urlParams.get('franchise_id')) {
    showMessageModal('Player Maximizer is available in franchise mode after roster data loads.');
    return false;
  }
  if (!customFocusRoster.length) {
    showMessageModal('Roster data is still loading. Try again in a moment.');
    return false;
  }
  pmModalValue = value;
  const title = byId('custom-focus-modal-title');
  const hint = byId('custom-focus-modal-hint');
  if (title) title.textContent = leaf.title;
  if (hint) hint.textContent = leaf.hint;

  customFocusDraft = {};
  customFocusRoster.forEach(function (row) {
    const pid = row.player_id;
    const c = leaf.mode === 'custom' ? customFocusCommitted[pid] : null;
    customFocusDraft[pid] = c && c.length === 3 ? [c[0], c[1], c[2]] : [];
  });
  renderCustomFocusTable();
  syncCustomFocusAssignButton();
  customFocusModal.classList.add('is-visible');
  customFocusModal.setAttribute('aria-hidden', 'false');
  if (customFocusAssignBtn && !customFocusAssignBtn.disabled) customFocusAssignBtn.focus({ preventScroll: true });
  else if (customFocusCancelBtn) customFocusCancelBtn.focus({ preventScroll: true });
  return true;
}

function closeCustomFocusModal() {
  if (!customFocusModal) return;
  customFocusModal.classList.remove('is-visible');
  customFocusModal.setAttribute('aria-hidden', 'true');
}

/** Check the radio for `value` (none when null) and repaint the cards. */
function setCoachingFocusRadio(value) {
  qsa('input[name="coaching-focus"]').forEach(function (inp) {
    inp.checked = !!(value && inp.value === value);
  });
  if (value) applyCoachingFocusArchetypeUi(value);
  else qsa('.archetype-block').forEach(function (block) {
    block.classList.remove('active', 'header-selected', 'sub-option-selected');
  });
}

/** Cancel, Escape or the backdrop: the focus goes back to what it was before the modal. */
function cancelCustomFocusModal() {
  if (!isCustomFocusModalOpen()) return;
  closeCustomFocusModal();
  customFocusDraft = {};
  if (committedCoachingValue !== pmModalValue) setCoachingFocusRadio(committedCoachingValue);
  updatePointsRemaining();
  saveTrainingFormDraft();
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
      const raw = window.GOB_AttributeDisplay.rawAttr(row.attrs, code);
      const shown = window.GOB_AttributeDisplay.displayAttr(raw);
      td.textContent = shown == null ? '—' : String(shown);
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
  playSound('SFX_SELECT');
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
  const value = pmModalValue;
  if (!PM_LEAVES[value]) return;
  customFocusCommitted = {};
  if (value === PM_CUSTOM_VALUE) {
    customFocusRoster.forEach(function (row) {
      const pid = row.player_id;
      const picks = customFocusDraft[pid];
      if (isCustomFocusThreeDistinct(picks)) {
        customFocusCommitted[pid] = [picks[0], picks[1], picks[2]];
      }
    });
  }
  customFocusDraft = {};
  playerMaximizerResolvedFocus = value;
  committedCoachingValue = value;
  setCoachingFocusRadio(value);
  closeCustomFocusModal();
  updatePointsRemaining();
  noteTrainingEdit();
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
  syncTrainingAdvance(allPointsAllocated && focusSelected && pmOk);

  updateRequirementsBar();
  // Spending on one drill shrinks every other drill's reachable range, so the disabled
  // pips are repainted across the page, not just on the stepper that moved.
  refreshAllTrainingSliderVisuals();

  return remaining;
}

function syncTrainingAdvance(ready) {
  if (!isWeekly() || trainingAllocationClosed) {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.hidden = true;
    }
    return;
  }
  if (submitBtn) {
    submitBtn.hidden = false;
    submitBtn.disabled = !ready;
    submitBtn.style.opacity = ready ? '1' : '0.4';
  }
}

/**
 * Handle slider input - prevent over-allocation
 */
function wireSliders() {
allSliders.forEach(slider => {
  ensureTrainingSliderVisual(slider);
  updateTrainingSliderVisual(slider, slider.value);
  slider.addEventListener('change', function() {
    playSound('SFX_SELECT');
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
    noteTrainingEdit();
    
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
}

function wireSliderResize() {
_onResizeSliders = function () {
  allSliders.forEach(function (slider) {
    updateTrainingSliderValuePosition(slider);
  });
};
window.addEventListener('resize', _onResizeSliders);
}

/**
 * Auto-Train: assign whole points under the flat budget and pick a random focus
 */
function autoAssignTraining() {
  // Same cue as Autoset Lineup on Set Lineup (Sound_Design_System: chaotic-choice).
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
        value !== PM_CUSTOM_VALUE
      );
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

function wireAutoTrain() {
if (autoTrainBtn) {
  autoTrainBtn.addEventListener('click', autoAssignTraining);
}
if (autoTrainModalClose && autoTrainModal) {
  autoTrainModalClose.addEventListener('click', () => {
    playSound('SFX_SELECT');
    autoTrainModal.classList.remove('is-visible');
  });
}
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
  qsa('.archetype-block').forEach(function (block) {
    block.classList.remove('active', 'header-selected', 'sub-option-selected');
  });
  let archetype = null;
  if (value.startsWith('authoritarian')) archetype = 'authoritarian';
  else if (value.startsWith('systems-coach')) archetype = 'systems-coach';
  else if (value.startsWith('player-maximizer')) archetype = 'player-maximizer';
  else if (value.startsWith('culture-builder')) archetype = 'culture-builder';
  if (!archetype) return;
  const archetypeBlock = rootQuery(`[data-archetype="${archetype}"]`);
  if (!archetypeBlock) return;
  const isHeaderRadio = value === archetype;
  if (isHeaderRadio) archetypeBlock.classList.add('active', 'header-selected');
  else archetypeBlock.classList.add('active', 'sub-option-selected');
}

function restoreTrainingFormDraft() {
  const urlParams = liveParams();
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

  applyTrainingFormState(o);
  trainingDirty = false;
}

/**
 * Handle coaching focus radio button selection
 * All radios in this section are part of ONE global radio group
 */
function wireCoachingRadios() {
coachingRadios.forEach(radio => {
  radio.addEventListener('change', function() {
    if (!this.checked) return;
    trainingDirty = true;
    
    // Skip when Auto-Train triggered this change (one SFX_SELECT already).
    const value = this.value;
    const skipSound = typeof window !== 'undefined' && window.__trainingAutoAssigning;
    if (typeof window !== 'undefined') window.__trainingAutoAssigning = false;
    if (!skipSound) {
      playSound('SFX_SELECT');
    }
    
    applyCoachingFocusArchetypeUi(value);

    if (PM_LEAVES[value]) {
      if (skipSound) {
        // Auto-Train never picks Custom, so the leaf is complete as chosen.
        resetCustomFocusCommitted();
        playerMaximizerResolvedFocus = value;
        committedCoachingValue = value;
      } else if (!openCustomFocusModal(value)) {
        setCoachingFocusRadio(committedCoachingValue);
      }
    } else {
      resetPlayerMaximizerResolvedState();
      committedCoachingValue = value;
    }

    // Update submit button state when focus is selected
    updatePointsRemaining();
    saveTrainingFormDraft();
  });

  // A second click on the assigned option reopens its modal (to review, or to edit
  // Custom picks). A first click is handled by `change` above.
  if (PM_LEAVES[radio.value]) {
    radio.addEventListener('click', function () {
      if (this.checked && committedCoachingValue === this.value && !isCustomFocusModalOpen()) {
        openCustomFocusModal(this.value);
      }
    });
  }
});

if (customFocusAssignBtn) {
  customFocusAssignBtn.addEventListener('click', function () {
    playSound('SFX_COMMIT');
    commitCustomFocusFromModal();
  });
}
if (customFocusCancelBtn) {
  customFocusCancelBtn.addEventListener('click', function () {
    playSound('SFX_SELECT');
    cancelCustomFocusModal();
  });
}
if (customFocusModal) {
  const backdrop = customFocusModal.querySelector('.gob-modal-backdrop');
  if (backdrop) backdrop.addEventListener('click', cancelCustomFocusModal);
}
_onKeyModal = function (event) {
  if (event.key === 'Escape' && isCustomFocusModalOpen()) {
    event.preventDefault();
    cancelCustomFocusModal();
  }
};
document.addEventListener('keydown', _onKeyModal);
}

/**
 * Handle back button click
 */
function wireBackButton() {
if (backBtn) backBtn.addEventListener('click', function() {
  clearTutorialResumeContext();
  // Get URL parameters to determine where to navigate back
  const urlParams = liveParams();
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
    if (window.GOBNav) window.GOBNav.back(finalUrl);
    else window.location.replace(finalUrl);
  } else if (from === 'game-plan') {
    const planUrl = '/game-plan.html?' + urlParams.toString();
    if (window.GOBNav) window.GOBNav.replace(planUrl);
    else window.location.replace(planUrl);
  } else {
    // ✅ PHASE 2: Preserve URL params in fallback (includes game_id if present)
    const planUrl = '/game-plan.html?' + urlParams.toString();
    if (window.GOBNav) window.GOBNav.replace(planUrl);
    else window.location.replace(planUrl);
  }
});
}

/**
 * Collect all training data for submission
 */
function collectTrainingData() {
  const pageParams = liveParams();
  const data = {
    // Player Drills
    player_drills: {
      offense: {
        inside: parseInt(byId('offense-inside').value) || 0,
        outside: parseInt(byId('offense-outside').value) || 0
      },
      defense: {
        inside: parseInt(byId('defense-inside').value) || 0,
        outside: parseInt(byId('defense-outside').value) || 0
      },
      technical: {
        passing: parseInt(byId('technical-passing').value) || 0,
        ball_handling: parseInt(byId('technical-ball-handling').value) || 0,
        rebounding: parseInt(byId('technical-rebounding').value) || 0
      },
      weight_room: {
        strength: parseInt(byId('weight-strength').value) || 0,
        agility: parseInt(byId('weight-agility').value) || 0
      }
    },
    
    // Team Drills
    team_drills: {
      team_offense: {
        install: parseInt(byId('team-offense-install').value) || 0
      },
      team_defense: {
        install: parseInt(byId('team-defense-install').value) || 0
      },
      fast_breaks: {
        offense_install: parseInt(byId('fast-break-offense-install').value) || 0,
        defense_install: parseInt(byId('fast-break-defense-install').value) || 0
      },
      scrimmages: parseInt(byId('team-scrimmages').value) || 0,
      presses_traps: {
        defense_install: parseInt(byId('press-defense-install').value) || 0,
        offense_install: parseInt(byId('press-offense-install').value) || 0
      }
    },
    
    // General
    general: {
      conditioning: parseInt(byId('general-conditioning').value) || 0,
      free_throws: parseInt(byId('general-free-throws').value) || 0,
      film_study: parseInt(byId('general-film-study').value) || 0,
      breaks: parseInt(byId('general-breaks').value) || 0
    },
    
    // Coaching Focus: the checked option's value is the leaf the server reads.
    coaching_focus: rootQuery('input[name="coaching-focus"]:checked')?.value || null,
    
    // Playbook Training Mode (+ optional custom CMD focus for franchise)
    playbook_training_mode: (function () {
      if (pageParams.get('mode') === 'franchise') {
        const sm = sessionStorage.getItem(STORAGE_PLAYBOOK_MODE);
        if (sm === 'custom' && sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS)) {
          return 'custom';
        }
        return 'current-playbooks';
      }
      return rootQuery('input[name="playbook-training-mode"]:checked')?.value || 'current-playbooks';
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
    console.log('🔋 [FRONTEND] Checking element again:', byId('team-scrimmages'));
  }
  
  return data;
}

function playSound(name) {
  import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(name, 0.7); }).catch(function () {});
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

function rewriteReportRedirect(redirectUrl) {
  try {
    const redirect = new URL(redirectUrl, window.location.origin);
    if (redirect.pathname === '/training-report.html' || redirect.pathname === '/static/training-report.html') {
      const bag = franchiseCtx().parseSearch(redirect.search);
      bag.delete('embed');
      bag.delete('tab');
      if (!bag.get('origin')) bag.set('origin', 'prep');
      if (!bag.get('from')) bag.set('from', 'training');
      if (!bag.get('franchise_id')) {
        const fid = franchiseCtx().get('franchise_id');
        if (fid) bag.set('franchise_id', fid);
      }
      if (!bag.get('team_id')) {
        const tid = franchiseCtx().get('team_id');
        if (tid) bag.set('team_id', tid);
      }
      if (!bag.get('week')) {
        const w = franchiseCtx().get('week') || currentWeek;
        if (w) bag.set('week', String(w));
      }
      const qs = bag.toString();
      return '/training-report.html' + (qs ? '?' + qs : '');
    }
  } catch (_err) {}
  return redirectUrl;
}

/**
 * Handle submit button click
 */
async function submitTraining(button) {
  if (button && button.disabled) return;

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

  if (!isPlayerMaximizerSubmitReady()) {
    alert('Player Maximizer Custom: pick three attributes for each player, then Assign Focus Attributes.');
    return;
  }
  
  // Get URL parameters for context
  const urlParams = liveParams();
  const mode = urlParams.get('mode');
  const franchiseId = urlParams.get('franchise_id');
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
  } else {
    // Single game mode or default
    payload = {
      team_id: teamId,
      training_data: trainingData
    };
  }
  
  try {
    if (button) {
      button.disabled = true;
      button.textContent = 'Submitting...';
    }
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
      if (mode === 'franchise' && franchiseId) {
        sessionStorage.setItem('gob_training_return', String(franchiseId));
      }
    } catch (_clearErr) {}

    // Handle success - use redirect URL from backend if provided, otherwise navigate to command center
    if (result.redirect) {
      // ✅ FIX: Strip /static/ prefix from backend redirect URLs for Netlify compatibility
      let redirectUrl = result.redirect.replace(/^\/static\//, '/');
      const headingToReport = /training-report\.html/.test(redirectUrl);
      redirectUrl = rewriteReportRedirect(redirectUrl);
      const returnUrl = urlParams.get('return_url');
      if (mode === 'franchise' && returnUrl) {
        const safeReturnUrl = typeof getSafeReturnUrl === 'function' ? getSafeReturnUrl(returnUrl) : returnUrl;
        if (safeReturnUrl) {
          const redirect = new URL(redirectUrl, window.location.origin);
          const bag = franchiseCtx().parseSearch(redirect.search);
          bag.set('return_url', safeReturnUrl);
          const qs = bag.toString();
          redirectUrl = `${redirect.pathname}${qs ? '?' + qs : ''}${redirect.hash || ''}`;
        }
      }
      trainingDirty = false;
      if (!headingToReport && window.GOBNav && window.GOBNav.exitFlow && window.GOBNav.isHubUrl && window.GOBNav.isHubUrl(redirectUrl)) {
        window.GOBNav.allowNextLeave();
        window.GOBNav.exitFlow(redirectUrl);
      } else if (window.GOBNav) {
        window.GOBNav.allowNextLeave();
        window.GOBNav.replace(redirectUrl);
      } else {
        window.location.replace(redirectUrl);
      }
    } else if (mode === 'franchise' && franchiseId) {
      trainingDirty = false;
      const lockerUrl = (typeof resolveFranchiseLockerRoomUrl === 'function')
        ? resolveFranchiseLockerRoomUrl({
            params: urlParams,
            franchiseId: franchiseId,
            teamId: urlParams.get('team_id')
          })
        : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}`;
      if (window.GOBNav && window.GOBNav.exitFlow) {
        window.GOBNav.allowNextLeave();
        window.GOBNav.exitFlow(lockerUrl);
      } else if (window.GOBNav) {
        window.GOBNav.allowNextLeave();
        window.GOBNav.replace(lockerUrl);
      } else {
        window.location.replace(lockerUrl);
      }
    } else {
      trainingDirty = false;
      if (window.GOBNav) {
        window.GOBNav.allowNextLeave();
        window.GOBNav.replace('/game-plan.html');
      } else {
        window.location.replace('/game-plan.html');
      }
    }
    
  } catch (error) {
    console.error('Failed to submit training:', error);
    trainingNewswireOverlayActive = false;
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) {
      window.PageLoadOverlay.hide();
    }
    showMessageModal(error.message || 'Failed to submit training. Please try again.');
    if (button) {
      button.disabled = false;
      button.textContent = button.id === 'play-now' ? 'Submit Training' : 'Submit Training';
    }
    syncTrainingAdvance(false);
  }
}

function wireSubmit() {
if (submitBtn) {
  submitBtn.addEventListener('click', function () {
    submitTraining(submitBtn);
  });
}
}

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
    trainingDirty = false;
    const next = result.redirect.replace(/^\/static\//, '/');
    if (window.GOBNav && window.GOBNav.exitFlow && window.GOBNav.isHubUrl && window.GOBNav.isHubUrl(next)) {
      window.GOBNav.allowNextLeave();
      window.GOBNav.exitFlow(next);
    } else if (window.GOBNav) {
      window.GOBNav.allowNextLeave();
      window.GOBNav.replace(next);
    } else {
      window.location.replace(next);
    }
  }
}

/**
 * Fetch training points from API for franchise mode
 */
async function initializeTrainingPoints() {
  const urlParams = liveParams();
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
        if (data.position_tallies && typeof data.position_tallies === 'object') {
          positionTallies = data.position_tallies;
        }
        if (data.focus_tallies && typeof data.focus_tallies === 'object') {
          focusTallies = data.focus_tallies;
        }
        if (Array.isArray(data.custom_focus_roster)) {
          customFocusRoster = data.custom_focus_roster;
          // Same 12 rows, already RT-descending, already carrying training_position /
          // training_focus through training_position_projection — no second fetch.
          // After week 26 the payload still carries this roster so the grid stays
          // editable even though there is no weekly allocation to make.
          renderPlayerDevelopment();
        }
        if (data.training_unavailable) {
          updatePointsRemaining();
          return;
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
        if (isWeekly()) captureTrainingFormSnapshot();
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


function wirePageShow() {
_onPageShow = (event) => {
  if (event.persisted) {
    if (window.GOBNav && window.GOBNav.reloadIfStale && window.GOBNav.reloadIfStale(event)) return;
    return;
  }
  if (isWeekly()) applyTrainingWeekState();
};
window.addEventListener('pageshow', _onPageShow);
}

function syncPlaybookModeToggleUi() {
  try {
    if (
      sessionStorage.getItem(STORAGE_PLAYBOOK_MODE) === 'custom' &&
      !sessionStorage.getItem(STORAGE_PLAYBOOK_FOCUS)
    ) {
      sessionStorage.removeItem(STORAGE_PLAYBOOK_MODE);
    }
  } catch (_e) {}
  const banner = byId('custom-playbook-banner');
  const btnCurrent = byId('playbook-mode-current-btn');
  const btnCustom = byId('playbook-mode-custom-btn');
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
  const pageParams = liveParams();
  if (pageParams.get('mode') !== 'franchise') {
    const wrap = rootQuery('.playbook-mode-selection');
    if (wrap) wrap.style.display = 'none';
    return;
  }
  const btnCurrent = byId('playbook-mode-current-btn');
  const btnCustom = byId('playbook-mode-custom-btn');
  if (btnCurrent) {
    btnCurrent.addEventListener('click', function () {
      playSound('SFX_SELECT');
      try {
        sessionStorage.removeItem(STORAGE_PLAYBOOK_FOCUS);
        sessionStorage.removeItem(STORAGE_PLAYBOOK_MODE);
      } catch (_e) {}
      syncPlaybookModeToggleUi();
    });
  }
  if (btnCustom) {
    btnCustom.addEventListener('click', function () {
      playSound('SFX_SELECT');
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
      const p = liveParams();
      const q = emptyParams();
      q.set('mode', p.get('mode') || 'franchise');
      if (p.get('franchise_id')) q.set('franchise_id', p.get('franchise_id'));
      const tid = p.get('team_id') || p.get('user_team_id');
      if (tid) q.set('team_id', tid);
      if (p.get('session_type')) q.set('session_type', p.get('session_type'));
      const playbooksUrl = `/training-playbooks.html?${q.toString()}`;
      // Not a leave: the draft was saved above and Training Playbook returns here, so
      // the unsaved-allocation confirm must not stand in the way once points are spent.
      if (window.GOBNav && typeof window.GOBNav.go === 'function') {
        if (typeof window.GOBNav.allowNextLeave === 'function') window.GOBNav.allowNextLeave();
        window.GOBNav.go(playbooksUrl);
      } else {
        window.location.href = playbooksUrl;
      }
    });
  }
  syncPlaybookModeToggleUi();
}

/* ============================================================
   Training polish: tooltips, attribute chips, requirements bar
   ============================================================ */

const ARCH_NAMES = {
  'authoritarian': 'Authoritarian',
  'systems-coach': 'Systems Coach',
  'player-maximizer': 'Player Maximizer',
  'culture-builder': 'Culture Builder'
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
  'offense-inside':      { code: 'SC', attr: 'Inside Scoring',   desc: "Sharpens scoring around the rim and in the post." },
  'offense-outside':     { code: 'SH', attr: 'Outside Shooting', desc: "Develops perimeter and mid-range shooting touch." },
  'defense-inside':      { code: 'ID', attr: 'Inside Defense',   desc: "Builds post defense, rim protection and interior toughness." },
  'defense-outside':     { code: 'OD', attr: 'Outside Defense',  desc: "Hones on-ball perimeter defense and closeouts." },
  'technical-passing':   { code: 'PS', attr: 'Passing',          desc: "Improves court vision, timing and passing accuracy." },
  'technical-ball-handling': { code: 'BH', attr: 'Ball Handling', desc: "Tightens handle and ball security under pressure." },
  'technical-rebounding':{ code: 'RB', attr: 'Rebounding',       desc: "Drills boxing out and finishing on the glass." },
  'weight-strength':     { code: 'ST', attr: 'Strength',         desc: "Adds physical strength for finishing and holding position." },
  'weight-agility':      { code: 'AG', attr: 'Agility',          desc: "Builds quickness, lateral speed and body control." },
  'general-conditioning':{ code: 'ND', attr: 'Conditioning',     desc: "Builds team-wide stamina so legs stay fresh deep into games." },
  'general-free-throws': { code: 'FT', attr: 'Free Throws',      desc: "Reps from the line to convert when it matters most." },
  'general-film-study':  { code: 'IQ', attr: 'Basketball IQ',    desc: "Film Study gives coaches better insight into upcoming opponents — especially tendencies from their most recent game." },
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
  'player-maximizer-top-3':             { name: 'Top 3 Attributes', desc: "Sharpen what each player already does best." },
  'player-maximizer-attributes-4-6':    { name: 'Attributes 4\u20136',   desc: "Take each player from good to great in emerging skills." },
  'player-maximizer-positional-focus':  { name: 'Positional Focus', desc: "Build positional identity around each player's core strengths." },
  'player-maximizer-custom':            { name: 'Custom',           desc: "Develop each player around the attributes you choose." }
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
function wireTooltipScroll() {
_onScrollTip = hideTrainingTooltip;
window.addEventListener('scroll', _onScrollTip, true);
}
document.addEventListener('click', function (e) {
  if (lastPointerType === 'touch' && trainingTooltipTrigger && !trainingTooltipTrigger.contains(e.target)) {
    hideTrainingTooltip();
  }
}, true);

function buildDrillTooltipHtml(d) {
  let head = '';
  if (d.code) {
    head = '<div class="tt-head"><span class="attr-chip">' + d.code +
      '</span><span class="tt-attr">' + d.attr + '</span></div>';
  }
  return head + '<div class="tt-desc">' + d.desc + '</div>';
}

function buildFocusTooltipHtml(value, f) {
  const archKey = archKeyFromValue(value);
  const archName = ARCH_NAMES[archKey] || '';
  let modes = '';
  if (f.modes) {
    modes = '<ul class="tt-modes">' + f.modes.map(function (m) {
      return '<li class="tt-mode"><b>' + m[0] + '</b> — ' + m[1] + '</li>';
    }).join('') + '</ul>';
  }
  return '<div class="tt-eyebrow">' + archName + '</div>' +
    '<div class="tt-name">' + f.name + '</div>' +
    '<div class="tt-desc">' + f.desc + '</div>' + modes;
}

/* --- Attribute code chips on single-attribute drills ---
   The chip hangs off the drill's NAME, which is the .label-text on a drill that sits
   inside a titled group and the .drill-title on a solo drill. Requiring .label-text alone
   silently dropped the chip from every General drill once they became solo rows. */
function injectAttributeChip(slider, d) {
  if (!d || !d.code) return;
  const label = slider.closest('.slider-label');
  const group = slider.closest('.drill-group');
  const lt = (label && label.querySelector('.label-text'))
    || (group && group.classList.contains('drill-group--solo') && group.querySelector('.drill-title'));
  if (!lt || lt.querySelector('.attr-chip')) return;
  const chip = document.createElement('span');
  chip.className = 'attr-chip';
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
    const slider = byId(id);
    if (!slider) return;
    const d = DRILL_TOOLTIPS[id];
    injectAttributeChip(slider, d);
    const trigger = triggerForSlider(slider);
    if (trigger) registerTrainingTooltip(trigger, buildDrillTooltipHtml(d), slider);
  });

  qsa('.archetype-option').forEach(function (opt) {
    const radio = opt.querySelector('input[name="coaching-focus"]');
    if (!radio) return;
    const f = FOCUS_TOOLTIPS[radio.value];
    if (!f) return;
    registerTrainingTooltip(opt, buildFocusTooltipHtml(radio.value, f), radio);
  });
}

/* --- Requirements bar --- */
function friendlyFocusName(radio) {
  const v = radio.value;
  if (PM_LEAVES[v]) return PM_LEAVES[v].title;
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

  const checked = rootQuery('input[name="coaching-focus"]:checked');
  const focusSelected = !!checked;
  const focusComplete = focusSelected && isPlayerMaximizerSubmitReady();

  if (focusSelected) {
    const archKey = archKeyFromValue(checked.value);
    const archName = ARCH_NAMES[archKey] || '';
    const focusName = friendlyFocusName(checked);
    if (reqFocusValueEl) reqFocusValueEl.textContent = archName ? (focusName + ' · ' + archName) : focusName;
    if (reqFocusChip) reqFocusChip.style.setProperty('--arch', 'var(--text-38)');
  } else {
    if (reqFocusValueEl) reqFocusValueEl.textContent = 'Not selected';
    if (reqFocusChip) reqFocusChip.style.removeProperty('--arch');
  }
  if (reqFocusChip) reqFocusChip.classList.toggle('is-selected', focusComplete);

  const nudge = pointsComplete && !focusSelected;
  if (reqFocusChip) reqFocusChip.classList.toggle('is-nudge', nudge);
  if (reqFocusNudgeBtn) reqFocusNudgeBtn.hidden = !nudge;

  // No "n of 2 ready" tally: the two chips already show their own state, and Submit
  // stays disabled until both are met, which says the same thing in the place a coach
  // is actually looking when he wants to submit.
}

function scrollToCoachingFocus() {
  const sec = rootQuery('.coaching-section');
  if (!sec) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  sec.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  sec.classList.remove('coaching-flash');
  void sec.offsetWidth; // restart animation
  sec.classList.add('coaching-flash');
  window.setTimeout(function () { sec.classList.remove('coaching-flash'); }, 1600);
}

function wireReqNudge() {
if (reqFocusNudgeBtn) {
  reqFocusNudgeBtn.addEventListener('click', function () {
    playSound('SFX_SELECT');
    scrollToCoachingFocus();
  });
}
}

/* Keep the requirements bar docked just below the sticky header. */
function positionRequirementsBar() {
  const header = rootQuery('.training-header');
  if (!reqBarEl || !header) return;
  const headerTop = parseFloat(getComputedStyle(header).top) || 0;
  reqBarEl.style.top = Math.round(headerTop + header.offsetHeight + 8) + 'px';
}

function wireReqBarChrome() {
_onResizeReq = positionRequirementsBar;
window.addEventListener('resize', _onResizeReq);
if (typeof ResizeObserver !== 'undefined') {
  const headerForObserve = rootQuery('.training-header');
  if (headerForObserve) {
    _reqObserver = new ResizeObserver(positionRequirementsBar);
    _reqObserver.observe(headerForObserve);
  }
}
}

function wireTrainingUi() {
  if (root && root.dataset.trainingWired === '1') return;
  if (root) root.dataset.trainingWired = '1';
  primeSliderPrev();
  wireSliders();
  wireSliderResize();
  wireAutoTrain();
  wireCoachingRadios();
  wireBackButton();
  wireSubmit();
  wirePageShow();
  wireTooltipScroll();
  wireReqNudge();
  wireReqBarChrome();
  setupTrainingTooltips();
  positionRequirementsBar();
  updateRequirementsBar();
}

async function startTrainingPage() {
  applySections();
  if (isWeekly() && window.GOBNav) {
    window.GOBNav.warnOnLeave(
      function () { return trainingDirty; },
      { confirm: confirmTrainingLeave }
    );
  }
  const noAllocation = await applyTrainingWeekState();
  wireTrainingTutorialButton();
  await initializeTrainingPoints();
  applySections();
  if (isWeekly() && !noAllocation) wireCustomTrainingPlaybook();
  if (window.GOBNav) window.GOBNav.restoreScroll();
}

function teardown() {
  if (_onPageShow) window.removeEventListener('pageshow', _onPageShow);
  if (_onResizeSliders) window.removeEventListener('resize', _onResizeSliders);
  if (_onResizeReq) window.removeEventListener('resize', _onResizeReq);
  if (_onScrollTip) window.removeEventListener('scroll', _onScrollTip, true);
  if (_tabShown) window.removeEventListener('gob-tab-shown', _tabShown);
  if (_onKeyModal) document.removeEventListener('keydown', _onKeyModal);
  _onPageShow = _onResizeSliders = _onResizeReq = _onScrollTip = _tabShown = _onKeyModal = null;
  if (_reqObserver) { try { _reqObserver.disconnect(); } catch (err) {} _reqObserver = null; }
  if (window.GOBAdvance && window.GOBAdvance.clearOverride) window.GOBAdvance.clearOverride();
  if (window.GOBNav && typeof window.GOBNav.warnOnLeave === 'function') {
    try { window.GOBNav.warnOnLeave(null); } catch (err) {}
  }
  started = false;
}

function revalidate(options) {
  if (options && options.sections) trainingSections = resolveSections(options);
  if (!started) return init(root, { sections: trainingSections });
  bindDom();
  applySections();
  return applyTrainingWeekState().then(function () {
    return initializeTrainingPoints();
  }).then(function () {
    applySections();
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    return { revalidate: revalidate, unmount: teardown };
  });
}

async function init(host, options) {
  root = host || document.body;
  trainingSections = resolveSections(options);
  const hadShell = !!root.querySelector('.training-container');
  if (!hadShell) root.insertAdjacentHTML('beforeend', shellHtml());
  bindDom();
  applySections();
  if (hadShell && started) return revalidate(options);
  wireTrainingUi();
  try {
    await startTrainingPage();
    started = true;
  } catch (error) {
    console.error('Failed to initialize training page:', error);
    throw error;
  } finally {
    liftWeeklyLoading();
  }
  return { revalidate: revalidate, unmount: teardown };
}

/**
 * First paint, weekly page only. training.html holds the page behind the shared loader
 * (html.is-loading); this lifts it once the week's budget, the saved draft and the Player
 * Development grid are in, so a 24-point budget that becomes 30, rows that refill from a
 * draft and a grid that lands late are never shown. A resume that is on its way to the
 * report keeps its own loader up. In the FCC tab the class is never set, so this is a no-op.
 */
function liftWeeklyLoading() {
  const html = document.documentElement;
  if (!html.classList.contains('is-loading') || trainingNewswireOverlayActive) return;
  html.classList.remove('is-loading');
  if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
}

function shellHtml() {
  return TRAINING_SHELL;
}

export { init, teardown, revalidate, shellHtml };
window.initTraining = function (host, options) { return init(host || document.body, options); };

window.GOBTraining = {
  submit: function () { return submitTraining(byId('play-now')); },
  syncAdvance: function () {
    const remaining = TOTAL_POINTS - calculateTotalPoints();
    syncTrainingAdvance(remaining === 0 && isCoachingFocusSelected() && isPlayerMaximizerSubmitReady());
  },
};
