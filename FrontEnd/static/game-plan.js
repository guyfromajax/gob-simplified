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


function playSound(name) {
  import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(name, 0.7); }).catch(function () {});
}

let root = null;
let slidersWired = false;
let tutorialWired = false;
let controlsWired = false;
let urlParams = null;
let homeTeam = null;
let awayTeam = null;
let homeId = null;
let awayId = null;
let myTeamSide = null;
let userTeamIdParam = null;
let franchiseId = null;
let weekParam = null;
let modeParam = null;
let quarter = 1;
let periodLabel = 'Q1';
let gameId = null;
let resumeFromTimeout = false;
let isGameIdRequired = false;
let DEBUG = false;
let pgId = null;
let sgId = null;
let sfId = null;
let pfId = null;
let cId = null;
let teamName = null;
let teamId = null;

function byId(id) {
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

function inAppShell() {
  return !!(root && (root.id === 'game-plan-view' || (root.closest && root.closest('#game-plan-view'))));
}

function readOptions(options) {
  options = options || {};
  urlParams = liveParams();
  function pick(name, alt) {
    if (options[name] != null && options[name] !== '') return String(options[name]);
    return urlParams.get(name) || (alt ? urlParams.get(alt) : '') || '';
  }
  homeTeam = pick('home');
  awayTeam = pick('away');
  homeId = pick('home_id');
  awayId = pick('away_id');
  myTeamSide = pick('my_team');
  userTeamIdParam = pick('user_team_id');
  franchiseId = window.StateTelemetry
    ? window.StateTelemetry.logUrlRead('franchise_id', pick('franchiseId', 'franchise_id') || null)
    : (pick('franchiseId', 'franchise_id') || null);
  weekParam = pick('week');
  modeParam = pick('mode');
  quarter = parseInt(pick('quarter'), 10) || 1;
  periodLabel = pick('period') || ('Q' + quarter);
  gameId = window.StateTelemetry
    ? window.StateTelemetry.logUrlRead('game_id', pick('game_id') || null)
    : (pick('game_id') || null);
  resumeFromTimeout = pick('resume_from_timeout') === 'true';
  isGameIdRequired = (modeParam === 'single') || (quarter > 1) || resumeFromTimeout;
  DEBUG = urlParams.has('debug');
  pgId = myTeamSide ? urlParams.get(myTeamSide + '_pg') : null;
  sgId = myTeamSide ? urlParams.get(myTeamSide + '_sg') : null;
  sfId = myTeamSide ? urlParams.get(myTeamSide + '_sf') : null;
  pfId = myTeamSide ? urlParams.get(myTeamSide + '_pf') : null;
  cId = myTeamSide ? urlParams.get(myTeamSide + '_c') : null;
  teamName = myTeamSide === 'home' ? homeTeam : awayTeam;
  teamId = myTeamSide === 'home' ? homeId : awayId;
  if (modeParam && (modeParam === 'tournament' || modeParam === 'franchise')) {
    const teamIdParam = pick('teamId', 'team_id');
    if (teamIdParam) {
      teamId = teamIdParam;
      teamName = teamIdParam;
    } else if (userTeamIdParam) {
      teamId = userTeamIdParam;
      teamName = userTeamIdParam;
    }
  }
  if (modeParam === 'single' || modeParam === 'tutorial') {
    const teamIdParam = pick('teamId', 'team_id');
    if (teamIdParam) {
      teamId = teamIdParam;
      teamName = teamIdParam;
    }
  }
}

function maybeMissingGameId() {
  if (!(isGameIdRequired && !gameId)) return;
  const errorMsg = `game_id is required but missing from URL. Mode: ${modeParam}, Quarter: ${quarter}, Resume from timeout: ${resumeFromTimeout}. Please navigate from the lineup screen with a valid game_id (created by init-game).`;
  console.error(`❌ [GAME-PLAN] ${errorMsg}`);
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
          franchise_id: franchiseId || undefined
        },
        redirectLabel: 'Return to Lineup'
      }
    });
  } else {
    alert(`Error: ${errorMsg}\n\nPlease return to the lineup screen and try again.`);
    if (homeTeam && awayTeam) {
      let lineupUrl = `/set-lineup.html?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&home_id=${encodeURIComponent(homeId || '')}&away_id=${encodeURIComponent(awayId || '')}&my_team=${encodeURIComponent(myTeamSide || 'home')}&mode=${encodeURIComponent(modeParam || 'single')}`;
      const homeDisplayParam = urlParams.get('home_display');
      const awayDisplayParam = urlParams.get('away_display');
      if (homeDisplayParam) lineupUrl += `&home_display=${encodeURIComponent(homeDisplayParam)}`;
      if (awayDisplayParam) lineupUrl += `&away_display=${encodeURIComponent(awayDisplayParam)}`;
      if (franchiseId) lineupUrl += `&franchise_id=${encodeURIComponent(franchiseId)}`;
      if (window.GOBNav) window.GOBNav.replace(lineupUrl);
      else window.location.replace(lineupUrl);
    }
  }
}


function applyTutorialMode() {
  if (modeParam !== 'tutorial' || tutorialWired) return;
  tutorialWired = true;
  const subhead = byId('tutorial-readonly-subhead');
  if (subhead) subhead.hidden = true;
  const backLink = byId('game-plan-back-link');
  if (backLink) backLink.hidden = true;
  const backToLineup = byId('btn-back-to-lineup');
  if (backToLineup) backToLineup.style.display = 'none';
  const cancelBtn = byId('btn-cancel');
  if (cancelBtn) cancelBtn.style.display = 'none';
  const saveBtn = byId('btn-save-game-plan');
  if (saveBtn) saveBtn.style.display = 'none';
  const btnRow = (root && root.querySelector('.button-container')) || (root && root.querySelector('.button-container')) || document.querySelector('.button-container');
  if (btnRow) {
    btnRow.style.justifyContent = 'center';
    btnRow.style.display = 'flex';
  }
  import('/js/shared/sammyModal.js')
    .then((m) => m.showSammyModal({
      body: 'Set your strategy. Sliders have real tradeoffs.',
      ctaLabel: 'GOT IT',
    }))
    .catch(() => { /* non-fatal */ });
  const actions = saveBtn ? saveBtn.parentElement : (root && root.querySelector('.sliders-container'));
  if (!actions || byId('btn-tutorial-gameplan-continue')) return;
  let tutorialSaveFailures = 0;
  const cta = document.createElement('button');
  cta.id = 'btn-tutorial-gameplan-continue';
  cta.type = 'button';
  cta.className = 'gob-btn gob-btn--neutral gob-btn--lg';
  cta.setAttribute('data-sfx', 'SFX_COMMIT');
  cta.textContent = 'PLAY NOW';
  cta.addEventListener('click', async () => {
    cta.disabled = true;
    let saved = false;
    try {
      saved = await saveSettingsQuietly();
      await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ step: 'situation' }),
      });
    } catch (e) {
      console.warn('[tutorial] game plan save/advance failed:', e);
    }
    if (!saved) {
      tutorialSaveFailures += 1;
      if (tutorialSaveFailures === 1) {
        showModal("Your game plan couldn't be saved. Press PLAY NOW to try again — otherwise this game uses the default plan.");
        cta.disabled = false;
        return;
      }
      console.warn('[tutorial] game plan save failed twice — continuing on the default plan');
    }
    const fwd = liveParams();
    window.location.href = '/tutorial-situation.html?' + fwd.toString();
  });
  actions.appendChild(cta);
}

// State
let currentSettings = {
  strategy_settings: {}
};

// Track unsaved changes
let hasUnsavedChanges = false;
let lastSavedSettings = null;
// True when mounted as the command center's game-plan-view.
let gamePlanHosted = false;
let toastTimer = null;
let toastHideTimer = null;

/** Match `.toast` enter transition in `game-plan.css` (transform + opacity). */
const TOAST_ENTER_TRANSITION_MS = 220;
const TOAST_POST_LAND_BUFFER_MS = 100;

/** True when game-plan was opened from FCC / TCC (not from set-lineup). */
function isGamePlanFromCommandCenter() {
  const p = liveParams();
  const from = p.get('from') || 'lineup';
  return (
    from === 'command_center' ||
    from === 'tournament-command-center' ||
    from === 'franchise-command-center'
  );
}

function navigateAfterSaveGamePlanFromToast() {
  if (isGamePlanFromCommandCenter()) {
    executeNavigateToCommandCenter();
  } else if (resumeFromTimeout) {
    executeNavigateToCourt();
  } else {
    executeNavigateBack();
  }
}

// Slider mappings (note: all go to strategy_settings now for unified backend handling)
const strategySliders = {
  'offense': 'slider-offense',
  'inside': 'slider-inside',
  'attack': 'slider-attack',
  'outside': 'slider-outside',
  'tempo': 'slider-tempo',
  'alterations': 'slider-alterations',
  'defense': 'slider-defense',
  'aggression': 'slider-aggression',
  'hc_trap': 'slider-hc-trap',
  'fc_press': 'slider-fc-press',
  'fast_breaks': 'slider-fast_breaks',
  'rebounding': 'slider-rebounding'
};

const EFFECT_LINES = {
  offense: 'Motion freedom vs designed set plays.',
  inside: 'Your highest-percentage shots.',
  attack: 'Drives and cuts. Draws the most fouls.',
  outside: 'Lowest %, most impact.',
  tempo: 'Work the offense or shoot fast.',
  alterations: 'Follow the script or read and react.',
  defense: 'Man uses talent. Zone uses IQ.',
  aggression: 'Play it safe or take more risks.',
  hc_trap: 'More turnovers. Faster fatigue, more fouls.',
  fc_press: 'Bigger disruption than a trap, bigger cost.',
  fast_breaks: 'How hard you push in transition.',
  rebounding: 'Second chances vs getting back on D.'
};

function applyEffectLines() {
  qsa('[data-effect]').forEach((el) => {
    const key = el.getAttribute('data-effect');
    if (EFFECT_LINES[key]) el.textContent = EFFECT_LINES[key];
  });
}

function clampTrack(raw) {
  const n = parseInt(raw, 10);
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(4, n));
}

function paintTrack(slider, raw) {
  const value = clampTrack(raw);
  const labels = slider.querySelectorAll('.gt-l');
  const names = Array.from(labels).map((el) => el.textContent.trim());
  let text = names[1] || '';
  if (value === 0) text = names[0] || '';
  else if (value === 2) text = names[1] || '';
  else if (value === 4) text = names[2] || '';
  else if (value === 1) text = 'between ' + (names[0] || '') + ' and ' + (names[1] || '');
  else text = 'between ' + (names[1] || '') + ' and ' + (names[2] || '');
  slider.setAttribute('aria-valuenow', String(value));
  slider.setAttribute('aria-valuetext', text);
  const knob = slider.querySelector('.gt-k');
  if (knob) knob.style.left = 'calc(8px + (100% - 16px) * ' + (value / 4) + ')';
  labels.forEach((el, index) => {
    const stop = index * 2;
    const between = value === 1 || value === 3;
    el.classList.toggle('on', !between && value === stop);
    el.classList.toggle('nr', between && Math.abs(stop - value) === 1);
  });
  return value;
}

function valueFromPointer(slider, clientX) {
  const rail = slider.querySelector('.gt-r') || slider;
  const rect = rail.getBoundingClientRect();
  const width = rect.width || 1;
  let t = (clientX - rect.left) / width;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  return Math.round(t * 4);
}

function installTrack(slider) {
  if (!slider || slider.dataset.trackReady === '1') return;
  slider.dataset.trackReady = '1';
  let current = paintTrack(slider, slider.getAttribute('aria-valuenow') || '2');
  Object.defineProperty(slider, 'value', {
    configurable: true,
    get() { return String(current); },
    set(v) { current = paintTrack(slider, v); }
  });
  function commit(next, notify) {
    const prev = current;
    current = paintTrack(slider, next);
    if (!notify || current === prev) return;
    slider.dispatchEvent(new Event('input', { bubbles: true }));
  }
  slider.addEventListener('keydown', (event) => {
    if (slider.getAttribute('aria-disabled') === 'true') return;
    let next = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = current + 1;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = current - 1;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 4;
    else return;
    event.preventDefault();
    if (next === current) return;
    commit(next, true);
    slider.dispatchEvent(new Event('change', { bubbles: true }));
  });
  slider.addEventListener('pointerdown', (event) => {
    if (slider.getAttribute('aria-disabled') === 'true') return;
    if (event.button != null && event.button !== 0) return;
    slider.focus();
    try { slider.setPointerCapture(event.pointerId); } catch (err) { /* pointer already gone */ }
    function at(ev) { commit(valueFromPointer(slider, ev.clientX), true); }
    function move(ev) {
      if (ev.pointerId !== event.pointerId) return;
      at(ev);
    }
    function up(ev) {
      if (ev.pointerId !== event.pointerId) return;
      slider.removeEventListener('pointermove', move);
      slider.removeEventListener('pointerup', up);
      slider.removeEventListener('pointercancel', up);
      slider.dispatchEvent(new Event('change', { bubbles: true }));
    }
    at(event);
    slider.addEventListener('pointermove', move);
    slider.addEventListener('pointerup', up);
    slider.addEventListener('pointercancel', up);
  });
}

function placeGamePlanTools() {
  if (document.documentElement.classList.contains('gob-focus')) return;
  const row = (root && root.querySelector('.button-container')) || document.querySelector('.button-container');
  const host = byId('gob-subtabs');
  if (!row || !host) return;
  if (!row.getAttribute('data-tool-home')) row.setAttribute('data-tool-home', '#game-plan-tools-home');
  let tools = host.querySelector('.pg-tools');
  if (!tools) {
    tools = document.createElement('div');
    tools.className = 'pg-tools';
    host.appendChild(tools);
  }
  tools.appendChild(row);
  if (window.GOBSubtabs && typeof window.GOBSubtabs.syncTools === 'function') {
    window.GOBSubtabs.syncTools(host);
  }
}

function dismissToast() {
  const toast = byId('toast');
  if (!toast) return;
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (toastHideTimer) {
    clearTimeout(toastHideTimer);
    toastHideTimer = null;
  }
  toast.classList.remove('visible');
  toastHideTimer = setTimeout(() => {
    toast.hidden = true;
  }, 220);
}

function showToast(title, subtitle = '', options = {}) {
  const toast = byId('toast');
  if (!toast) return;
  const accent = options.accentColor || 'var(--text-60)';
  const subline = subtitle ? `<div class="toast-subline">${subtitle}</div>` : '';
  toast.innerHTML = `
    <div class="toast-icon" style="--toast-accent: ${accent};">
      <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <path d="M5.1 10.4 8.3 13.6 14.9 7" fill="none" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"></path>
      </svg>
    </div>
    <div class="toast-copy">
      <div class="toast-title">${title}</div>
      ${subline}
    </div>
    <button class="toast-dismiss" type="button" aria-label="Dismiss notification">×</button>
  `;
  toast.style.setProperty('--toast-accent', accent);
  toast.hidden = false;
  toast.querySelector('.toast-dismiss')?.addEventListener('click', dismissToast, { once: true });
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (toastHideTimer) {
    clearTimeout(toastHideTimer);
    toastHideTimer = null;
  }
  requestAnimationFrame(() => {
    toast.classList.add('visible');
    if (typeof options.onAfterLand === 'function') {
      const landMs = TOAST_ENTER_TRANSITION_MS + TOAST_POST_LAND_BUFFER_MS;
      setTimeout(() => {
        try {
          options.onAfterLand();
        } catch (e) {
          console.error('[GAME-PLAN] onAfterLand callback failed', e);
        }
      }, landMs);
    }
  });
  const dismissAfterMs = typeof options.autoDismissMs === 'number' ? options.autoDismissMs : 3000;
  if (dismissAfterMs > 0) {
    toastTimer = setTimeout(() => {
      dismissToast();
    }, dismissAfterMs);
  }
}

function showModal(message) {
  const modal = byId('validation-modal');
  const modalMessage = byId('modal-message');
  if (modalMessage) modalMessage.textContent = message;
  if (modal) modal.hidden = false;
}

function hideModal() {
  const modal = byId('validation-modal');
  if (modal) modal.hidden = true;
}

function setHeader() {
  const title = byId('page-title');
  const subtitle = byId('team-subtitle');
  if (title) {
    title.textContent = 'Set Your Game Plan';
  }
  if (subtitle && teamName) {
    subtitle.textContent = teamName;
  }
}

function ensureSliderVisual(slider) {
  const wrapper = slider?.closest('.slider-wrapper');
  if (!wrapper) return null;
  let shell = wrapper.querySelector('.strategy-slider-shell');
  if (shell) return shell;

  shell = document.createElement('div');
  shell.className = 'strategy-slider-shell';
  shell.setAttribute('aria-hidden', 'true');
  shell.innerHTML = `
    <div class="strategy-slider-track"></div>
    <div class="strategy-slider-nodes">
      <span class="strategy-slider-node"></span>
      <span class="strategy-slider-node"></span>
      <span class="strategy-slider-node"></span>
      <span class="strategy-slider-node"></span>
      <span class="strategy-slider-node"></span>
    </div>
  `;
  wrapper.appendChild(shell);
  return shell;
}

function updateSliderVisual(slider, rawValue) {
  if (slider && slider.classList && slider.classList.contains('gt')) {
    if (slider.dataset.trackReady === '1') slider.value = rawValue;
    else paintTrack(slider, rawValue);
    return;
  }
  const shell = ensureSliderVisual(slider);
  if (!shell) return;
  const value = Math.max(0, Math.min(4, Number(rawValue) || 0));
  shell.querySelectorAll('.strategy-slider-node').forEach((node, index) => {
    node.classList.toggle('is-selected', index === value);
  });
}

function setupSliders() {
  applyEffectLines();
  if (slidersWired) return;
  slidersWired = true;
  // Setup all sliders (all save to strategy_settings)
  for (const [key, sliderId] of Object.entries(strategySliders)) {
    const slider = byId(sliderId);
    const valueDisplay = byId(`value-${sliderId.replace('slider-', '')}`);

    if (slider && slider.classList.contains('gt')) installTrack(slider);
    if (slider && valueDisplay) {
      updateSliderVisual(slider, slider.value);
      slider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value, 10);
        valueDisplay.textContent = value;
        currentSettings.strategy_settings[key] = value;
        updateSliderVisual(slider, value);
        markUnsavedChanges();
      });
      slider.addEventListener('change', () => {
        playSound('SFX_SELECT');
      });
    }
  }
}

function wireShotDietTip() {
  const btn = (root && root.querySelector('#shot-diet-nest .slider-nest__info')) || document.querySelector('#shot-diet-nest .slider-nest__info');
  const copy = byId('shot-diet-tip');
  if (!btn || !copy || btn.dataset.tipReady === '1') return;
  if (typeof addTextTooltip !== 'function') return;
  btn.dataset.tipReady = '1';
  addTextTooltip(btn, copy.textContent.trim());
}

function markUnsavedChanges() {
  hasUnsavedChanges = true;
  syncSaveDirtyState();
}

// Colour law: Save Game Plan is orange only while there is something to save
// (a real edit per gamePlanHasEdits). Neutral at rest and after a save.
function syncSaveDirtyState() {
  const btn = byId('btn-save-game-plan');
  if (btn) btn.classList.toggle('is-dirty', gamePlanHasEdits());
}

function sliderSnapshot(settings) {
  const source = (settings && settings.strategy_settings) || {};
  return Object.keys(strategySliders).map((key) => Number(source[key] ?? 2)).join(',');
}

// Unsaved only while a slider differs from the last load or save; moving one
// away and back is not an edit.
function gamePlanHasEdits() {
  if (!hasUnsavedChanges || !lastSavedSettings) return false;
  return sliderSnapshot(currentSettings) !== sliderSnapshot(lastSavedSettings);
}

function revertGamePlan() {
  if (!lastSavedSettings) return;
  currentSettings = JSON.parse(JSON.stringify(lastSavedSettings));
  for (const [key, sliderId] of Object.entries(strategySliders)) {
    const slider = byId(sliderId);
    const valueDisplay = byId(`value-${sliderId.replace('slider-', '')}`);
    const value = currentSettings.strategy_settings[key] ?? 2;
    if (slider) slider.value = value;
    if (valueDisplay) valueDisplay.textContent = value;
    if (slider) updateSliderVisual(slider, value);
  }
  hasUnsavedChanges = false;
  syncSaveDirtyState();
}

function confirmGamePlanLeave(proceed) {
  if (!window.GOBLeaveConfirm) {
    showUnsavedChangesWarning(proceed);
    return;
  }
  window.GOBLeaveConfirm.open({
    title: 'Unsaved Game Plan',
    copy: 'Save your game plan changes before you leave?',
    saveLabel: 'Save Game Plan',
    onSave: async () => {
      await saveGamePlan();
      return !gamePlanHasEdits();
    },
    onDiscard: revertGamePlan,
    proceed: proceed,
  });
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

// FTE v3 safety net: recover game_id from tutorial_state when the query string
// has lost it. Without a game_id the page 400s on GET /api/gameplan and 500s on
// PUT, and the user's sliders are silently never saved. tutorial_state is the
// durable copy (see TutorialState in auth_routes.py).
const recoverTutorialGameId = async () => {
  if (gameId) return gameId;
  try {
    const res = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() });
    if (!res.ok) return null;
    const me = await res.json();
    const recovered = ((me && me.tutorial_state) || {}).game_id || null;
    if (recovered) {
      gameId = recovered;
      // Repair the URL in place so every later read — including the save on
      // PLAY NOW and anything that forwards the query string — sees it.
      const bag = liveParams();
      bag.set('game_id', recovered);
      // In-place: repair game_id on the current game-plan URL. Do not navigate.
      franchiseCtx().commitParams(bag);
      console.warn('[tutorial] recovered game_id from tutorial_state:', recovered);
    }
    return recovered;
  } catch (e) {
    console.warn('[tutorial] game_id recovery failed:', e);
    return null;
  }
};

async function loadSettings() {
  // FTE v3: recover a missing game_id BEFORE the request is built. The previous
  // version kicked recovery off without awaiting it, so the fetch still went out
  // with no game_id, 400'd, and alerted the user — recovery then repaired the URL
  // too late to matter.
  if (modeParam === 'tutorial' && !gameId && typeof recoverTutorialGameId === 'function') {
    await recoverTutorialGameId();
  }

  try {
    // ✅ PHASE 2: Validate game_id before loading settings
    if (gameId && modeParam === 'single' && window.PointerValidation) {
      try {
        await window.PointerValidation.validateGameId(gameId);
        console.log(`✅ [GAME-PLAN] game_id validated: ${gameId}`);
      } catch (error) {
        console.error(`❌ [GAME-PLAN] Invalid game_id: ${error.message}`);
        // ✅ Phase 4: Use showMissingTruthError for invalid pointer (document not found)
        if (window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
          window.ErrorHandler.showMissingTruthError({
            pointerType: 'game_id',
            pointerValue: gameId,
            message: `Invalid game_id: ${gameId}. ${error.message}`,
            mode: modeParam || 'single',
            recoveryOptions: {
              redirectTo: 'mode-select',
              redirectLabel: 'Go to Mode Select'
            }
          });
        } else if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
          // Fallback to missing pointer error if missing truth error not available
          window.ErrorHandler.showMissingPointerError({
            missingPointer: 'game_id',
            message: `Invalid game_id: ${gameId}. ${error.message}`,
            mode: modeParam || 'single',
            recoveryOptions: {
              redirectTo: 'mode-select',
              redirectLabel: 'Go to Mode Select'
            }
          });
        }
        return; // Don't proceed with loading
      }
    }
    
    let mode = modeParam || 'single';
    
    // ✅ SS&S: Always load from database (single source of truth for all modes)
    const params = emptyParams();
    params.set('mode', mode);
    params.set('team_id', teamId);
    
    if (mode === 'franchise' && franchiseId) {
      params.set('franchise_id', franchiseId);
      if (gameId) params.set('game_id', gameId);
    } else if ((mode === 'single' || mode === 'tutorial') && gameId) {
      // Tutorial games are stored in games_collection like single mode; the
      // backend aliases mode=tutorial → single and requires game_id.
      params.set('game_id', gameId);
    }
    
    // ✅ PHASE 1.3: Check cache first (optional, disposable)
    // Wait for gameStore to be available (handles async module loading)
    let data = null;
    if (window.gameStore) {
      data = window.gameStore.getStrategySettings();
      if (data) {
        console.log('✅ [GAME-PLAN] Cache hit - using cached strategy settings');
      }
    } else {
      // gameStore not loaded yet - log for debugging
      console.log('🔍 [GAME-PLAN] gameStore not available yet (module may still be loading)');
    }
    
    // If cache miss, load from backend
    if (!data) {
      console.log('🔍 [GAME-PLAN] Loading settings from database:', params.toString());
      const res = await fetch(`${API_CONFIG.buildUrl('/api/gameplan')}?${params.toString()}`);
      if (!res.ok) {
        let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
        let errorData = {};
        try {
          errorData = await res.json();
          errorDetail = errorData.detail || errorData.message || errorDetail;
        } catch (e) {
          try {
            errorDetail = await res.text();
          } catch (e2) {
            // Keep default errorDetail
          }
        }
        console.error('❌ [GAME-PLAN] Failed to load game plan settings:', errorDetail);
        
        // ✅ Phase 4: Remove silent default - show error screen for API failures
        if (res.status === 404 && errorDetail.includes('not found')) {
          // Document not found - show missing truth error
          if (window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
            const pointerType = mode === 'franchise' ? 'franchise_id' : 'game_id';
            const pointerValue = mode === 'franchise' ? franchiseId : gameId;
            window.ErrorHandler.showMissingTruthError({
              pointerType,
              pointerValue: pointerValue || 'unknown',
              message: errorDetail,
              mode: mode,
              recoveryOptions: {
                redirectTo: mode === 'franchise' ? 'franchise-select' : 'mode-select',
                redirectLabel: mode === 'franchise' ? 'Go to Franchise Select' : 'Go to Mode Select'
              }
            });
          }
        } else {
          // Other API errors - show generic error
          console.error('❌ [GAME-PLAN] API error loading settings - cannot proceed without settings');
          alert(`Error: Failed to load game plan settings. ${errorDetail}\n\nPlease try refreshing the page or return to the lineup screen.`);
        }
        // ✅ Phase 4: Don't use silent defaults - fail explicitly
        return;
      }
      
      data = await res.json();
      // ✅ PHASE 1.3: Log backend read
      if (window.StateTelemetry) {
        window.StateTelemetry.logBackendRead('strategy_settings', data, '/api/gameplan');
      }
      
      // ✅ PHASE 1.3: Update cache after successful backend load
      if (window.gameStore) {
        window.gameStore.setStrategySettings(data);
        console.log('✅ [GAME-PLAN] Updated cache with backend data');
      }
    }
    currentSettings = data;
    console.log('✅ [GAME-PLAN] Loaded settings from database:', currentSettings);
    
    // Update UI with loaded values AND ensure currentSettings is fully populated
    for (const [key, sliderId] of Object.entries(strategySliders)) {
      const slider = byId(sliderId);
      const valueDisplay = byId(`value-${sliderId.replace('slider-', '')}`);
      // ✅ FIX: Use nullish coalescing to preserve 0 values (|| treats 0 as falsy)
      const value = currentSettings.strategy_settings[key] ?? 2;
      
      // Ensure value is in currentSettings (in case it wasn't loaded)
      currentSettings.strategy_settings[key] = value;
      
      if (slider) slider.value = value;
      if (valueDisplay) valueDisplay.textContent = value;
      if (slider) updateSliderVisual(slider, value);
    }
    
    // Store last saved settings for comparison
    lastSavedSettings = JSON.parse(JSON.stringify(currentSettings));
    hasUnsavedChanges = false;
    syncSaveDirtyState();
    
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
    // ✅ PHASE 5.1: Send team_id (backend will normalize to canonical format if needed)
    const payload = {
      mode,
      team_id: teamId, // Can be team name, ObjectId, or canonical format - backend normalizes
      strategy_settings: currentSettings.strategy_settings
    };
    
    // ✅ PHASE 5.7: Include game_id when available (for all modes)
    // Backend will determine if game is active and save to game doc or master doc accordingly
    if (gameId) {
      payload.game_id = gameId;
    }
    
    if (mode === 'franchise' && franchiseId) {
      payload.franchise_id = franchiseId;
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
    
    // ✅ PHASE 1.3: Invalidate cache after successful save (cache must be rebuilt from truth)
    if (window.gameStore) {
      window.gameStore.invalidateStrategySettings('settings saved to backend');
      console.log('✅ [GAME-PLAN] Invalidated cache after save');
    }
    
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
    syncSaveDirtyState();

    if (resumeFromTimeout) {
      executeNavigateToCourt();
      return;
    }
    if (gamePlanHosted && window.GOBToast) {
      window.GOBToast.show('Game plan saved');
      return;
    }

    showToast('Game Plan Saved', 'Changes applied successfully', {
      onAfterLand: navigateAfterSaveGamePlanFromToast,
      autoDismissMs: 0,
    });

    const saveBtn = byId('btn-save-game-plan');
    if (saveBtn) saveBtn.disabled = true;
  } catch (err) {
    console.error('Error saving settings:', err);
    showModal('An error occurred while saving. Please try again.');
  }
}

function navigateToCourt() {
  // Check for unsaved changes before navigating
  if (gamePlanHasEdits()) {
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
  
  // ✅ CRITICAL FIX: Read URL params directly from currentSearch()
  // Don't rely on module-level urlParams which might be stale
  const currentUrlParams = liveParams();
  const currentParamsObj = Object.fromEntries(currentUrlParams.entries());
  console.log('🚀 [GAME-PLAN] Current URL params:', currentParamsObj);
  console.error('🚀🚀🚀 [GAME-PLAN] executeNavigateToCourt() - game_id:', currentUrlParams.get('game_id'), 'resume_from_timeout:', currentUrlParams.get('resume_from_timeout'));
  
  // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
  const helper = window.TimeoutNavigationHelper;
  if (!helper) {
    const fallback = '/court.html?' + currentUrlParams.toString();
    if (window.GOBNav) {
      window.GOBNav.allowNextLeave();
      window.GOBNav.replace(fallback);
    } else {
      window.location.replace(fallback);
    }
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
  if (window.GOBNav) {
    window.GOBNav.allowNextLeave();
    window.GOBNav.replace(finalUrl);
  } else {
    window.location.replace(finalUrl);
  }
}

function navigateBack() {
  // Check for unsaved changes before navigating
  if (gamePlanHasEdits()) {
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
  
  // ✅ CRITICAL FIX: Read URL params directly from currentSearch()
  // Don't rely on module-level urlParams which might be stale
  const currentUrlParams = liveParams();
  
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
  
  const lineupUrl = `/set-lineup.html?${params.toString()}`;
  if (window.GOBNav) {
    window.GOBNav.allowNextLeave();
    window.GOBNav.replace(lineupUrl);
  } else {
    window.location.replace(lineupUrl);
  }
}

function navigateToCommandCenter() {
  // Check for unsaved changes before navigating
  if (gamePlanHasEdits()) {
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
  
  const mode = modeParam || 'single';
  
  if (mode === 'franchise' && franchiseId) {
    const teamIdParam = teamId || userTeamIdParam || teamName;
    const finalUrl = typeof resolveFranchiseLockerRoomUrl === 'function'
      ? resolveFranchiseLockerRoomUrl({
          params: urlParams,
          franchiseId: franchiseId,
          teamId: teamIdParam
        })
      : buildFranchiseLockerRoomUrl(franchiseId, teamIdParam);
    if (window.GOBNav) {
      window.GOBNav.allowNextLeave();
      window.GOBNav.replace(finalUrl);
    } else {
      window.location.replace(finalUrl);
    }
  } else {
    if (window.GOBNav) {
      window.GOBNav.allowNextLeave();
      window.GOBNav.replace('/mode-select.html');
    } else {
      window.location.replace('/mode-select.html');
    }
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

  const modal = document.createElement('div');
  modal.className = 'gameplan-warning-modal';

  const message = document.createElement('p');
  message.textContent = "You haven't saved game plan changes.";

  const checkboxContainer = document.createElement('div');
  checkboxContainer.style.marginBottom = '20px';

  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = 'gameplan-suppress-warning';
  checkbox.style.marginRight = '8px';

  const checkboxLabel = document.createElement('label');
  checkboxLabel.htmlFor = 'gameplan-suppress-warning';
  checkboxLabel.textContent = "Don't show this message again";

  checkboxContainer.appendChild(checkbox);
  checkboxContainer.appendChild(checkboxLabel);

  const buttonsContainer = document.createElement('div');
  buttonsContainer.className = 'gameplan-warning-actions';

  const saveBtn = document.createElement('button');
  saveBtn.textContent = 'Save Game Plan';
  saveBtn.className = 'gameplan-warning-save';
  saveBtn.addEventListener('click', async () => {
    if (checkbox.checked) {
      sessionStorage.setItem('gameplan_suppress_warning', 'true');
    }
    overlay.remove();
    playSound('SFX_COMMIT');
    await saveGamePlan();
    // After successful save, continue with navigation
    if (!gamePlanHasEdits()) {
      onContinue();
    }
  });
  
  // Leave Without Saving button
  const leaveBtn = document.createElement('button');
  leaveBtn.textContent = 'Leave Without Saving';
  leaveBtn.className = 'gameplan-warning-leave';
  leaveBtn.addEventListener('click', () => {
    if (checkbox.checked) {
      sessionStorage.setItem('gameplan_suppress_warning', 'true');
    }
    overlay.remove();
    hasUnsavedChanges = false;
    syncSaveDirtyState();
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


function teardown() {
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (toastHideTimer) {
    clearTimeout(toastHideTimer);
    toastHideTimer = null;
  }
  if (window.GOBNav && typeof window.GOBNav.warnOnLeave === 'function') {
    try { window.GOBNav.warnOnLeave(null); } catch (err) { /* leave hook optional */ }
  }
}

function revalidate(options) {
  readOptions(options);
  return loadSettings().then(function () {
    placeGamePlanTools();
    return { revalidate: revalidate, unmount: teardown };
  });
}

async function init(host, options) {
  root = host || document.body;
  readOptions(options);
  if (window.StateTelemetry) window.StateTelemetry.setContext('game-plan');
  maybeMissingGameId();
  const hadShell = !!root.querySelector('.gpc');
  if (!hadShell) {
    root.insertAdjacentHTML('beforeend', shellHtml());
    slidersWired = false;
    tutorialWired = false;
    controlsWired = false;
  }
  if (hadShell && slidersWired) return revalidate(options);
  gamePlanHosted = inAppShell();
  if (window.GOBNav) {
    window.GOBNav.warnOnLeave(gamePlanHasEdits, gamePlanHosted
      ? { view: 'game-plan-view', confirm: confirmGamePlanLeave }
      : null);
  }
  setHeader();
  setupSliders();
  wireShotDietTip();
  applyTutorialMode();

  const from = (urlParams && urlParams.get('from')) || 'lineup';
  const btnSaveGamePlan = byId('btn-save-game-plan');
  const btnCancel = byId('btn-cancel');
  const btnBackToLineup = byId('btn-back-to-lineup');
  const pageBackLink = byId('game-plan-back-link');
  const modalClose = byId('modal-close');
  const isFromCommandCenter = from === 'command_center' ||
                               from === 'tournament-command-center' ||
                               from === 'franchise-command-center';

  if (!controlsWired) {
    controlsWired = true;
    if (gamePlanHosted) {
      if (pageBackLink) pageBackLink.hidden = true;
      if (btnBackToLineup) btnBackToLineup.style.display = 'none';
      if (btnCancel) btnCancel.style.display = 'none';
    } else if (isFromCommandCenter) {
      if (pageBackLink) {
        pageBackLink.hidden = false;
        pageBackLink.addEventListener('click', (event) => {
          event.preventDefault();
          playSound('SFX_SELECT');
          navigateToCommandCenter();
        });
      }
      if (btnBackToLineup) btnBackToLineup.style.display = 'none';
      if (btnCancel) btnCancel.style.display = 'none';
    } else {
      if (pageBackLink) pageBackLink.hidden = true;
      if (btnBackToLineup) {
        btnBackToLineup.style.display = 'inline-block';
        btnBackToLineup.addEventListener('click', () => {
          navigateBack();
        });
      }
      if (btnCancel) btnCancel.style.display = 'none';
    }

    if (modeParam === 'tutorial') {
      if (pageBackLink) {
        pageBackLink.hidden = true;
        pageBackLink.style.display = 'none';
      }
      if (btnBackToLineup) btnBackToLineup.style.display = 'none';
      if (btnCancel) btnCancel.style.display = 'none';
      if (btnSaveGamePlan) btnSaveGamePlan.style.display = 'none';
      const btnRow = (root && root.querySelector('.button-container')) || document.querySelector('.button-container');
      if (btnRow) {
        btnRow.style.display = 'flex';
        btnRow.style.justifyContent = 'center';
      }
    }

    if (btnSaveGamePlan) {
      btnSaveGamePlan.addEventListener('click', () => {
        playSound('SFX_COMMIT');
        saveGamePlan();
      });
      btnSaveGamePlan.setAttribute('data-wired', '1');
    }
    if (btnCancel) {
      btnCancel.addEventListener('click', navigateToCommandCenter);
    }
    if (modalClose) {
      modalClose.addEventListener('click', hideModal);
    }
  }

  placeGamePlanTools();
  await loadSettings();
  return { revalidate: revalidate, unmount: teardown };
}

function shellHtml() {
  return (
    '<div class="resource-page-container fcc-brand-page-shell">\n    <div class="game-plan-page-header-wrap">\n      <a id="game-plan-back-link" class="back-to-locker-room brand-back-link game-plan-back-link" href="#" hidden>Back to Locker Room</a>\n    </div>\n\n    <section class="fcc-data-card game-plan-card">\n      <div class="fcc-data-card-body game-plan-card-body">\n        <header class="game-plan-page-header">\n          <h1 id="page-title">Set Your Game Plan</h1>\n          <p id="tutorial-readonly-subhead" class="tutorial-readonly-subhead" hidden>Read-only for onboarding game.</p>\n        </header>\n        <div class="button-container">\n          <button type="button" id="btn-back-to-lineup" class="btn btn-secondary" style="display: none;">Back To Lineup</button>\n          <button type="button" id="btn-cancel" class="btn btn-secondary" style="display: none;">Cancel</button>\n          <button type="button" id="btn-save-game-plan" class="btn btn-o btn-save-game-plan">Save Game Plan</button>\n        </div>\n        <div class="gpc cols2">\n          <section aria-label="Offense">\n            <div class="gpr">\n              <div class="gpr-n"><b>Offense</b><span data-effect="offense"></span></div>\n              <div class="gt strategy-slider" id="slider-offense" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="50/50" aria-label="Offense">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">100% Motion</span>\n                <span class="gt-l b on">50/50</span>\n                <span class="gt-l c">100% Set Plays</span>\n                <span class="slider-value" id="value-offense" hidden>2</span>\n              </div>\n            </div>\n            <!-- Shot Diet: Inside / Attack / Outside share touches. A section like\n                 Execution and Transition; the tip and the offense-not-all-Never modal\n                 are unchanged. -->\n            <div class="grp" id="shot-diet-nest">\n              <div class="grp-hd">\n                <span class="eb grp-h">Shot Diet</span>\n                <button type="button" class="slider-nest__info"\n                        aria-label="About the shot diet sliders"\n                        aria-describedby="shot-diet-tip">i</button>\n                <span id="shot-diet-tip" hidden>These three share touches — raise one, the others compete.</span>\n              </div>\n              <div class="gpr">\n                <div class="gpr-n"><b>Inside Offense</b><span data-effect="inside"></span></div>\n                <div class="gt strategy-slider" id="slider-inside" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Inside Offense">\n                  <i class="gt-r"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                  <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <span class="gt-l a">Never</span>\n                  <span class="gt-l b on">Normal</span>\n                  <span class="gt-l c">Most</span>\n                  <span class="slider-value" id="value-inside" hidden>2</span>\n                </div>\n              </div>\n              <div class="gpr">\n                <div class="gpr-n"><b>Attack Offense</b><span data-effect="attack"></span></div>\n                <div class="gt strategy-slider" id="slider-attack" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Attack Offense">\n                  <i class="gt-r"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                  <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <span class="gt-l a">Never</span>\n                  <span class="gt-l b on">Normal</span>\n                  <span class="gt-l c">Most</span>\n                  <span class="slider-value" id="value-attack" hidden>2</span>\n                </div>\n              </div>\n              <div class="gpr">\n                <div class="gpr-n"><b>Outside Offense</b><span data-effect="outside"></span></div>\n                <div class="gt strategy-slider" id="slider-outside" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Outside Offense">\n                  <i class="gt-r"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                  <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                  <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                  <span class="gt-l a">Never</span>\n                  <span class="gt-l b on">Normal</span>\n                  <span class="gt-l c">Most</span>\n                  <span class="slider-value" id="value-outside" hidden>2</span>\n                </div>\n              </div>\n            </div>\n            <span class="eb grp-h">Execution</span>\n            <div class="gpr">\n              <div class="gpr-n"><b>Offense Tempo</b><span data-effect="tempo"></span></div>\n              <div class="gt strategy-slider" id="slider-tempo" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Offense Tempo">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">Slow</span>\n                <span class="gt-l b on">Normal</span>\n                <span class="gt-l c">Fast</span>\n                <span class="slider-value" id="value-tempo" hidden>2</span>\n              </div>\n            </div>\n            <div class="gpr">\n              <div class="gpr-n"><b>Play Alteration</b><span data-effect="alterations"></span></div>\n              <div class="gt strategy-slider" id="slider-alterations" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Play Alteration">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">Least</span>\n                <span class="gt-l b on">Normal</span>\n                <span class="gt-l c">Most</span>\n                <span class="slider-value" id="value-alterations" hidden>2</span>\n              </div>\n            </div>\n          </section>\n          <section aria-label="Defense">\n            <div class="gpr">\n              <div class="gpr-n"><b>Defense</b><span data-effect="defense"></span></div>\n              <div class="gt strategy-slider" id="slider-defense" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="50/50" aria-label="Defense">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">100% Man</span>\n                <span class="gt-l b on">50/50</span>\n                <span class="gt-l c">100% Zone</span>\n                <span class="slider-value" id="value-defense" hidden>2</span>\n              </div>\n            </div>\n            <span class="eb grp-h">Disruption</span>\n            <div class="gpr">\n              <div class="gpr-n"><b>Aggression</b><span data-effect="aggression"></span></div>\n              <div class="gt strategy-slider" id="slider-aggression" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Aggression">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">Passive</span>\n                <span class="gt-l b on">Normal</span>\n                <span class="gt-l c">Aggressive</span>\n                <span class="slider-value" id="value-aggression" hidden>2</span>\n              </div>\n            </div>\n            <div class="gpr">\n              <div class="gpr-n"><b>Half-Court Trap</b><span data-effect="hc_trap"></span></div>\n              <div class="gt strategy-slider" id="slider-hc-trap" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Half-Court Trap">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">Never</span>\n                <span class="gt-l b on">Normal</span>\n                <span class="gt-l c">Most</span>\n                <span class="slider-value" id="value-hc-trap" hidden>2</span>\n              </div>\n            </div>\n            <div class="gpr">\n              <div class="gpr-n"><b>Full-Court Press</b><span data-effect="fc_press"></span></div>\n              <div class="gt strategy-slider" id="slider-fc-press" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="Normal" aria-label="Full-Court Press">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">Never</span>\n                <span class="gt-l b on">Normal</span>\n                <span class="gt-l c">Most</span>\n                <span class="slider-value" id="value-fc-press" hidden>2</span>\n              </div>\n            </div>\n            <span class="eb grp-h">Transition</span>\n            <div class="gpr">\n              <div class="gpr-n"><b>Fast Break</b><span data-effect="fast_breaks"></span></div>\n              <div class="gt strategy-slider" id="slider-fast_breaks" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="50/50" aria-label="Fast Break">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">100% Half-Court Sets</span>\n                <span class="gt-l b on">50/50</span>\n                <span class="gt-l c">100% Fast Breaks</span>\n                <span class="slider-value" id="value-fast_breaks" hidden>2</span>\n              </div>\n            </div>\n            <div class="gpr">\n              <div class="gpr-n"><b>Offensive Rebounding</b><span data-effect="rebounding"></span></div>\n              <div class="gt strategy-slider" id="slider-rebounding" role="slider" tabindex="0" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="4" aria-valuenow="2" aria-valuetext="50/50" aria-label="Offensive Rebounding">\n                <i class="gt-r"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.25)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <i class="gt-s n" style="left:calc(8px + (100% - 16px) * 0.75)"></i>\n                <i class="gt-s" style="left:calc(8px + (100% - 16px) * 1)"></i>\n                <i class="gt-k" style="left:calc(8px + (100% - 16px) * 0.5)"></i>\n                <span class="gt-l a">100% Crash the Boards</span>\n                <span class="gt-l b on">50/50</span>\n                <span class="gt-l c">100% Get Back on D</span>\n                <span class="slider-value" id="value-rebounding" hidden>2</span>\n              </div>\n            </div>\n          </section>\n        </div>\n      </div>\n    </section>\n  </div>\n\n  <!-- Validation Modal -->\n  <div id="validation-modal" class="modal" hidden>\n    <div class="modal-content">\n      <h2>Invalid Game Plan</h2>\n      <p id="modal-message">At least one Offense setting must be above \'Never\'. Please increase any Offense slider.</p>\n      <button id="modal-close" class="btn btn-primary">OK</button>\n    </div>\n  </div>'
  );
}

export { init, teardown, revalidate, shellHtml };
window.initGamePlan = function (host, options) { return init(host || document.body, options); };
