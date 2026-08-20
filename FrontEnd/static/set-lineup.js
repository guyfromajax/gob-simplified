const urlParams = new URLSearchParams(window.location.search);
console.log('✅ set-lineup.js loaded at', new Date().toISOString());
// Append cache buster to any dynamic loads if present
(function(){
  const s = document.querySelector('script[src*="set-lineup.js"]');
  if (s && s.src.includes('__BUILD_TS__')) {
    const now = Date.now().toString();
    s.src = s.src.replace('__BUILD_TS__', now);
    // Cache buster updated silently
  }
})();

// ✅ PHASE 1.3: Set telemetry context
if (window.StateTelemetry) {
  window.StateTelemetry.setContext('set-lineup');
}

// ✅ PHASE 1.3: Instrument URL parameter reads
const homeTeam = window.StateTelemetry ? window.StateTelemetry.logUrlRead('home', urlParams.get('home')) : urlParams.get('home');
const awayTeam = window.StateTelemetry ? window.StateTelemetry.logUrlRead('away', urlParams.get('away')) : urlParams.get('away');
const homeId = urlParams.get('home_id');
const awayId = urlParams.get('away_id');
// Chrome labels (Team Builder overlay). Identity for init/sim remains home/away (core).
const homeDisplay = urlParams.get('home_display') || homeTeam;
const awayDisplay = urlParams.get('away_display') || awayTeam;
let myTeamSide = urlParams.get('my_team');

/** Attach structural ObjectIds when present (Team Builder franchise matchup identity). */
function attachMatchupTeamIds(payload) {
  if (homeId) payload.home_id = homeId;
  if (awayId) payload.away_id = awayId;
  return payload;
}
// FT shooter lock: when the first turn out of Set Lineup is a free throw, the
// designated shooter cannot be removed from the active lineup (reorder still ok).
// See Timeout_System.md § Designated Free Throw Shooter Lock.
let ftLockActive = false;
let ftLockShooterId = null;
function isFtLockedPlayer(playerId) {
  return ftLockActive && ftLockShooterId != null && playerId != null
    && String(playerId) === ftLockShooterId;
}
async function loadFtShooterLock() {
  try {
    if (!gameId || urlParams.get('resume_from_timeout') !== 'true') return;
    const res = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}/ft-lock`), { headers: API_CONFIG.getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.next_turn_is_free_throw && data.ft_shooter_id) {
      ftLockShooterId = String(data.ft_shooter_id);
      ftLockActive = true;
    }
  } catch (e) { /* non-fatal: lock is a safeguard, never block lineup screen */ }
}
const userTeamIdParam = window.StateTelemetry ? window.StateTelemetry.logUrlRead('user_team_id', urlParams.get('user_team_id')) : urlParams.get('user_team_id');
const teamIdParam = window.StateTelemetry ? window.StateTelemetry.logUrlRead('team_id', urlParams.get('team_id')) : urlParams.get('team_id');
const franchiseId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('franchise_id', urlParams.get('franchise_id')) : urlParams.get('franchise_id');
const weekParam = urlParams.get('week');
const tournamentId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('tournament_id', urlParams.get('tournament_id')) : urlParams.get('tournament_id');
const modeParam = urlParams.get('mode');
const DEBUG = urlParams.has('debug');
const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
// ✅ PHASE 1.1: Remove localStorage fallback - game_id must come from URL params only
// game_id is optional for new games (will be created by init-game), but if present must be in URL
// Note: This is a snapshot of initial URL state - always read from window.location.search when needed
const gameId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('game_id', urlParams.get('game_id') || null) : (urlParams.get('game_id') || null);
/** game_id from URL (updated by init-game replaceState); falls back to page-load snapshot. */
function getActiveGameId() {
  const fromUrl = new URLSearchParams(window.location.search).get('game_id');
  return fromUrl || gameId || null;
}
let exhaustedUserLineupLocked = urlParams.get('locked_exhausted_user_lineup') === 'true';

/** @returns {boolean} true if response was 401/403 and redirect was triggered — caller must stop. */
function abortIfAccessDenied(response) {
  if (!response) return false;
  if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
    return AccessDenied.checkAccessDenied(response);
  }
  return false;
}

function playSound(filename) {
  try {
    const base = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(() => {});
  } catch (e) {}
}

async function redirectIfFranchiseGameplayAlreadyCommitted() {
  if (modeParam !== 'franchise' || !franchiseId || !weekParam) return false;
  try {
    const response = await fetch(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${encodeURIComponent(franchiseId)}`, {
      headers: API_CONFIG.getAuthHeaders()
    });
    if (abortIfAccessDenied(response)) return false;
    if (!response.ok) return false;
    const data = await response.json();
    // Mid-game resume often lands here before court — hydrate same as FCC.
    if (typeof hydrateTeamBuilderVisualFromFranchisePayload === 'function') {
      hydrateTeamBuilderVisualFromFranchisePayload(data, franchiseId);
    }
    const currentWeek = Number(data.week || 1);
    const pageWeek = Number(weekParam || 0);
    if (pageWeek && currentWeek > pageWeek) {
      window.location.replace(`/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`);
      return true;
    }
  } catch (error) {
    console.warn('⚠️ [SET-LINEUP] Unable to verify franchise gameplay state:', error);
  }
  return false;
}

function buildPlayerDetailUrl(playerId) {
  const qs = new URLSearchParams();
  qs.set('id', playerId);
  if (modeParam) qs.set('mode', modeParam);
  if (franchiseId) qs.set('franchise_id', franchiseId);
  if (tournamentId) qs.set('tournament_id', tournamentId);
  if (gameId) qs.set('game_id', gameId);
  qs.set('return_url', window.location.pathname + window.location.search);
  return `/player-detail.html?${qs.toString()}`;
}

function getPlayerStableId(player) {
  return player?._id || player?.playerId || player?.player_id || null;
}

function getRosterGameFouls(player) {
  const raw = player?.stats || {};
  const game = raw.game || raw;
  return Number(game.F ?? player?.F ?? 0) || 0;
}

function shuffleCopy(items) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function buildExhaustedUserLineupIfNeeded() {
  const nonFouledOut = roster.filter(player => getRosterGameFouls(player) < 5);
  const fouledOut = roster.filter(player => getRosterGameFouls(player) >= 5);
  if (nonFouledOut.length > 4 || fouledOut.length < 8) return false;

  const hasPreservedLockedLineup =
    exhaustedUserLineupLocked
    && ['PG', 'SG', 'SF', 'PF', 'C'].every(pos => lineup[pos]);

  if (!hasPreservedLockedLineup) {
    const shortfall = 5 - nonFouledOut.length;
    const selected = [
      ...nonFouledOut,
      ...shuffleCopy(fouledOut).slice(0, shortfall),
    ];
    const randomizedFive = shuffleCopy(selected);
    ['PG', 'SG', 'SF', 'PF', 'C'].forEach((pos, index) => {
      lineup[pos] = String(getPlayerStableId(randomizedFive[index]));
    });
  }

  exhaustedUserLineupLocked = true;
  const currentParams = new URLSearchParams(window.location.search);
  currentParams.set('locked_exhausted_user_lineup', 'true');
  ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
    currentParams.set(`${myTeamSide}_${pos.toLowerCase()}`, lineup[pos]);
  });
  history.replaceState(null, '', `${window.location.pathname}?${currentParams.toString()}`);
  return true;
}

function lockExhaustedUserLineupControls() {
  if (!exhaustedUserLineupLocked) return;
  document.body.classList.add('exhausted-lineup-locked');
  document.querySelectorAll(
    '#autoset-lineup, #roster-view-game, #roster-view-attributes, #roster-view-stats, .roster-row-remove'
  ).forEach(control => {
    control.disabled = true;
    control.setAttribute('aria-disabled', 'true');
  });
  document.querySelectorAll(
    '#roster-body-game tr, #roster-body tr, #roster-body-stats tr'
  ).forEach(element => {
    element.draggable = false;
    element.setAttribute('draggable', 'false');
  });
}

function showExhaustedUserLineupModal() {
  if (!exhaustedUserLineupLocked) return;
  const modal = document.getElementById('exhausted-lineup-modal');
  const button = document.getElementById('exhausted-lineup-got-it');
  if (!modal || !button) return;
  const seenKey = `exhaustedLineupModalShown_${gameId || 'game'}`;
  try {
    if (sessionStorage.getItem(seenKey) === '1') return;
    sessionStorage.setItem(seenKey, '1');
  } catch (_) {}
  modal.hidden = false;
  button.addEventListener('click', () => {
    modal.hidden = true;
  }, { once: true });
  setTimeout(() => button.focus(), 0);
}

function isGameplayLineupContext() {
  // During active gameplay/timeouts/quarter resumes, game_id is present.
  // Pregame lineup flow typically has no game_id yet.
  return Boolean(gameId);
}

function applyPlayerDetailLinkBehavior(linkEl, playerId) {
  if (!linkEl) return;
  if (isGameplayLineupContext()) {
    linkEl.removeAttribute('href');
    linkEl.style.cursor = 'default';
    linkEl.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    return;
  }
  linkEl.href = buildPlayerDetailUrl(playerId);
}

// ✅ PHASE 2: Validate pointers on page load (if present)
// Note: game_id is optional for new Q1 games, but if present must be valid
// franchise_id and tournament_id are required for their respective modes
async function validatePointersOnLoad() {
  const mode = modeParam || 'single';
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  const resumeFromAnchor = urlParams.get('resume_from_anchor') === 'true' || urlParams.get('consume_resume_anchor') === 'true';
  const currentQuarter = parseInt(urlParams.get('quarter'), 10) || 1;
  
  // For single mode, game_id is required for Q2+ or timeout resume
  const isGameIdRequired = (mode === 'single') && ((currentQuarter > 1) || resumeFromTimeout);
  
  if (isGameIdRequired && !gameId) {
    const errorMsg = `game_id is required but missing from URL. Mode: ${mode}, Quarter: ${currentQuarter}, Resume from timeout: ${resumeFromTimeout}. Please navigate from a valid game state.`;
    console.error(`❌ [SET-LINEUP] ${errorMsg}`);
    if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
      window.ErrorHandler.showMissingPointerError({
        missingPointer: 'game_id',
        message: errorMsg,
        mode: mode,
        recoveryAction: 'redirect_to_mode_select'
      });
    } else {
      alert(`Error: ${errorMsg}\n\nPlease return to the mode select screen and try again.`);
    }
    return false;
  }
  
  // Validate that game_id points to existing document (if present)
  if (gameId && mode === 'single' && window.PointerValidation) {
    try {
      await window.PointerValidation.validateGameId(gameId);
      console.log(`✅ [SET-LINEUP] game_id validated: ${gameId}`);
    } catch (error) {
      console.error(`❌ [SET-LINEUP] Invalid game_id: ${error.message}`);
      // ✅ Phase 4: Use showMissingTruthError for invalid pointer (document not found)
      if (window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
        window.ErrorHandler.showMissingTruthError({
          pointerType: 'game_id',
          pointerValue: gameId,
          message: `Invalid game_id: ${gameId}. ${error.message}`,
          mode: mode,
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
          mode: mode,
          recoveryOptions: {
            redirectTo: 'mode-select',
            redirectLabel: 'Go to Mode Select'
          }
        });
      }
      return false;
    }
  }
  
  // Validate franchise_id if in franchise mode
  if (mode === 'franchise') {
    if (!franchiseId) {
      const errorMsg = `franchise_id is required for franchise mode but missing from URL.`;
      console.error(`❌ [SET-LINEUP] ${errorMsg}`);
      if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
        window.ErrorHandler.showMissingPointerError({
          missingPointer: 'franchise_id',
          message: errorMsg,
          mode: mode,
          recoveryAction: 'redirect_to_franchise_select'
        });
      }
      return false;
    }
    
    if (window.PointerValidation) {
      try {
        await window.PointerValidation.validateFranchiseId(franchiseId);
        console.log(`✅ [SET-LINEUP] franchise_id validated: ${franchiseId}`);
      } catch (error) {
        console.error(`❌ [SET-LINEUP] Invalid franchise_id: ${error.message}`);
        if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
          window.ErrorHandler.showMissingPointerError({
            missingPointer: 'franchise_id',
            message: `Invalid franchise_id: ${franchiseId}. ${error.message}`,
            mode: mode,
            recoveryAction: 'redirect_to_franchise_select'
          });
        }
        return false;
      }
    }
  }
  
  // Validate tournament_id if in tournament mode
  if (mode === 'tournament') {
    if (!tournamentId) {
      const errorMsg = `tournament_id is required for tournament mode but missing from URL.`;
      console.error(`❌ [SET-LINEUP] ${errorMsg}`);
      if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
        window.ErrorHandler.showMissingPointerError({
          missingPointer: 'tournament_id',
          message: errorMsg,
          mode: mode,
          recoveryAction: 'redirect_to_tournament_select'
        });
      }
      return false;
    }
    
    if (window.PointerValidation) {
      try {
        await window.PointerValidation.validateTournamentId(tournamentId);
        console.log(`✅ [SET-LINEUP] tournament_id validated: ${tournamentId}`);
      } catch (error) {
        console.error(`❌ [SET-LINEUP] Invalid tournament_id: ${error.message}`);
        if (window.ErrorHandler && window.ErrorHandler.showMissingPointerError) {
          window.ErrorHandler.showMissingPointerError({
            missingPointer: 'tournament_id',
            message: `Invalid tournament_id: ${tournamentId}. ${error.message}`,
            mode: mode,
            recoveryAction: 'redirect_to_tournament_select'
          });
        }
        return false;
      }
    }
  }
  
  return true;
}

// ✅ FIX: Track if init-game is in progress to prevent duplicate calls
let initGameInProgress = false;

// ✅ PHASE 1.1: Only use localStorage for explicit "Resume Last Game" feature (not implemented yet)
// For now, we only read from URL params - fail loudly if game_id is required but missing
// Note: game_id is optional on lineup screen for new games, but required for Q2+ or timeout resume

// ✅ PHASE 1.1: Clean up URL params if game_id is present but shouldn't be (for new matchups)
// This ensures URL is clean and doesn't carry stale game_id from previous games
if (gameId && quarter === 1 && !urlParams.has('resume_from_timeout')) {
  // If we have a game_id but it's Q1 and not a timeout resume, verify teams match
  // If teams don't match, this is a new matchup and game_id should be cleared
  // (Backend will create new game_id via init-game)
  const storedHome = typeof localStorage !== 'undefined' ? localStorage.getItem('game_home') : null;
  const storedAway = typeof localStorage !== 'undefined' ? localStorage.getItem('game_away') : null;
  const storedHomeId = typeof localStorage !== 'undefined' ? localStorage.getItem('game_home_id') : null;
  const storedAwayId = typeof localStorage !== 'undefined' ? localStorage.getItem('game_away_id') : null;
  // Prefer ObjectId identity when both sides have ids; fall back to display names.
  const isNewMatchup = (homeId && awayId && storedHomeId && storedAwayId)
    ? (storedHomeId !== homeId || storedAwayId !== awayId)
    : (storedHome && storedAway && (storedHome !== homeTeam || storedAway !== awayTeam));
  
  if (isNewMatchup) {
    // Teams changed = definitely a new matchup, clear game_id from URL
    if (typeof history !== 'undefined' && history.replaceState) {
      const clean = new URLSearchParams(urlParams);
      clean.delete('game_id');
      const qs = clean.toString();
      history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
    }
    // Update stored teams for next check
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_home', homeTeam || '');
      localStorage.setItem('game_away', awayTeam || '');
      if (homeId) localStorage.setItem('game_home_id', homeId);
      if (awayId) localStorage.setItem('game_away_id', awayId);
    }
  } else {
    // Teams match, update stored teams
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_home', homeTeam || '');
      localStorage.setItem('game_away', awayTeam || '');
      if (homeId) localStorage.setItem('game_home_id', homeId);
      if (awayId) localStorage.setItem('game_away_id', awayId);
    }
  }
}

// FIXED: Additional check - if we have a gameId but it's Q1, verify it's valid
// If user starts Q1 but saved game is Q2+, backend will handle detection via heuristic
// Frontend just needs to ensure gameId exists for init-game flow to work

// ✅ PHASE 1.1: Log game_id source (should only be URL now)
console.log('[Lineup] gameId check:', {
  fromUrl: urlParams.get('game_id'),
  finalGameId: gameId,
  quarter: quarter,
  homeTeam: homeTeam,
  awayTeam: awayTeam,
  isRequired: quarter > 1 || urlParams.has('resume_from_timeout')
});

const periodLabel = urlParams.get('period') || `Q${quarter}`;
let teamName = '';

let roster = [];
/** Team chemistry from /roster (franchise/tournament FTD); single-game default 15. */
let rosterTeamChemistry = 15;
const lineup = {};
/** @type {string|null} Selected Rim Runner player id (single-select); null = use backend default */
let rimRunnerPlayerId = null;
const playerMap = {};
let lineupPlaybooksModalInitialized = false;
let lineupPlaybooksModalCache = null;

const LINEUP_PLAYBOOK_SECTION_ORDER = [
  { key: 'motion', label: 'Motion Plays' },
  { key: 'set_plays', label: 'Set Plays' },
  { key: 'man_defense', label: 'Man Defense' },
  { key: 'zone_defense', label: 'Zone Defense' },
  { key: 'fast_breaks', label: 'Fast Breaks' },
  { key: 'hc_traps', label: 'HC Traps' },
];

function getRT(player) {
  const ratings = Object.values(player.position_ratings || {});
  return ratings.length ? Math.max(...ratings) : -Infinity;
}

// RT color bucket helper.
//
// IMPORTANT: do NOT define a local `function getRtBucketClass()` here.
// set-lineup.js is loaded as a classic (non-module) script, and a top-level
// function declaration of the same name as the shared global on window
// silently clobbers it — then any wrapper that tries to delegate to
// window.getRtBucketClass ends up calling itself recursively until the
// stack overflows. (That bug masked the entire render in tutorial mode.)
//
// Canonical implementation lives at /js/shared/rtBucket.js. The two call
// sites below pick it up via window. with an inline guard for the rare
// case it didn't load.
function rtBucketClassOrEmpty(rt) {
  return typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rt) : '';
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2000);
}

function escapeLineupPlaybookHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getLineupPlaybookEffClass(value) {
  if (typeof getPlaybookCmdClass === 'function') {
    return getPlaybookCmdClass(value);
  }
  const numeric = Number(value || 0);
  if (numeric >= 70) return 'is-good';
  if (numeric >= 40) return 'is-mid';
  return 'is-low';
}

function getLineupPlaybookUrl() {
  const params = new URLSearchParams();
  const qp = new URLSearchParams(window.location.search);
  let resolvedTeamId =
    typeof window.resolvePlaybookTeamIdFromSearch === 'function'
      ? window.resolvePlaybookTeamIdFromSearch(qp)
      : null;
  if (!resolvedTeamId) {
    resolvedTeamId =
      userTeamIdParam ||
      teamIdParam ||
      (myTeamSide === 'home' ? homeId || homeTeam : null) ||
      (myTeamSide === 'away' ? awayId || awayTeam : null);
  }
  params.set('mode', modeParam || 'single');
  if (resolvedTeamId) params.set('team_id', resolvedTeamId);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (tournamentId) params.set('tournament_id', tournamentId);
  const currentGameId = getActiveGameId();
  if (currentGameId) params.set('game_id', currentGameId);
  if (typeof window.isDebugPlaycallSearch === 'function' && window.isDebugPlaycallSearch(qp)) {
    params.set('debug_pc', '1');
  }
  return `${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`;
}

async function fetchLineupPlaybooksData() {
  const apiUrl = getLineupPlaybookUrl();
  const __debugPc =
    typeof window.isDebugPlaycallSearch === 'function' && window.isDebugPlaycallSearch(urlParams);
  const response = await fetch(apiUrl, { headers: API_CONFIG.getAuthHeaders() });
  if (abortIfAccessDenied(response)) return null;
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  const data = await response.json();
  if (__debugPc) {
    const slotAssignments = data.slot_assignments || {};
    const offensePcOrder = (((data || {}).pc_order || {}).offense || []);
    let qsTeamId = null;
    try {
      const u = new URL(apiUrl, typeof window !== 'undefined' ? window.location.origin : 'http://local');
      qsTeamId = u.searchParams.get('team_id');
    } catch (e) {
      qsTeamId = null;
    }
    console.warn('[DEBUG_PC] set-lineup GET /api/playbooks response', {
      page: 'set-lineup',
      apiUrl,
      mode: modeParam || 'single',
      gameId: gameId || null,
      franchiseId: franchiseId || null,
      tournamentId: tournamentId || null,
      myTeamSide: myTeamSide || null,
      teamIdParam: teamIdParam || null,
      userTeamIdParam: userTeamIdParam || null,
      queryTeamId: qsTeamId,
      offensePcOrderLen: Array.isArray(offensePcOrder) ? offensePcOrder.length : 0,
      slotAssignmentKeyCount: Object.keys(slotAssignments).length,
      motionPlays: (data.motion || []).length,
    });
  }
  return data;
}

function renderLineupShotWeights(playbookData) {
  const weightsContainer = document.getElementById('lineup-shot-weights');
  if (!weightsContainer) return;
  const shotWeights = playbookData?.position_shot_weights;
  if (!shotWeights || (!shotWeights.playbooks && !shotWeights.playcall_center)) {
    weightsContainer.innerHTML = '<p class="psw-unavailable">Shot weight data unavailable.</p>';
    return;
  }
  const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
  const colorFn = typeof getPswColor === 'function' ? getPswColor : () => '#34EC27';

  function renderBarGroup(label, data) {
    if (!data) return '';
    const values = POSITIONS.map((pos) => ({ pos, pct: Number(data[pos] ?? 0) || 0 }));
    const maxPct = Math.max(...values.map((value) => value.pct));
    const rows = values.map(({ pos, pct }) => {
      const color = colorFn(pct);
      const hi = pct === maxPct && maxPct > 0 ? ' is-hi' : '';
      return `
        <div class="psw-bar-row${hi}">
          <div class="psw-bar-pos">${pos}</div>
          <div class="psw-bar-track"><i style="width:${pct}%;background:${color}"></i></div>
          <div class="psw-bar-val" style="color:${color}">${pct}%</div>
        </div>`;
    }).join('');
    return `
      <div class="psw-bar-group">
        <div class="psw-bar-label">${label}</div>
        ${rows}
      </div>`;
  }

  weightsContainer.innerHTML = `
    <div class="psw-bar-root">
      ${renderBarGroup('Playbook Shot Weights', shotWeights.playbooks)}
      ${renderBarGroup('Play Call Center Shot Weights', shotWeights.playcall_center)}
    </div>`;
}

function getLineupPlaybookPercentage(percentages, key, id) {
  const category = percentages?.[key] || {};
  const legacyFastBreakCategory = key === 'fast_breaks' ? percentages?.fast_break || {} : {};
  const value = category?.[id] ?? legacyFastBreakCategory?.[id] ?? 0;
  return Number(value || 0);
}

function lineupPlaybookSectionPcSide(key) {
  if (key === 'motion' || key === 'set_plays') return 'offense';
  if (key === 'man_defense' || key === 'zone_defense') return 'defense';
  return null;
}

/** Show weighted plays, plus 0% plays that are still on the call sheet. */
function lineupPlaybookItemVisible(item, key, data) {
  if (Number(item.percentage || 0) > 0) return true;
  const side = lineupPlaybookSectionPcSide(key);
  if (!side) return false;
  const order = ((data?.pc_order || {})[side] || []).map(String);
  return order.includes(String(item.id || ''));
}

function buildLineupPlaybookItems(data, key) {
  const percentages = data?.simple_playbook_percentages || data?.playbook_percentages || {};
  let items = [];
  if (key === 'motion') {
    items = (data?.motion || []).map((play) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: getLineupPlaybookPercentage(percentages, 'motion', play?.play_id),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
    }));
  } else if (key === 'set_plays') {
    items = (data?.set_plays || []).map((play, index) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: getLineupPlaybookPercentage(percentages, 'set_plays', play?.play_id),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
      focus: play?.play_focus || '',
      _apiIndex: index,
    }));
  } else if (key === 'man_defense') {
    items = (data?.man_defense_rows || [])
      .filter((row) => row?.is_active !== false)
      .map((row) => ({
        id: String(row?.id || ''),
        name: row?.name || 'Unknown',
        percentage: getLineupPlaybookPercentage(percentages, 'man_defense', row?.id),
        effectiveness: Number(row?.effectiveness || 0),
        top_scorer: row?.top_scorer || '',
      }));
  } else if (key === 'zone_defense') {
    items = (data?.zone_defense_rows || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: getLineupPlaybookPercentage(percentages, 'zone_defense', row?.id),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || '',
    }));
  } else if (key === 'fast_breaks') {
    items = (data?.fast_breaks || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: getLineupPlaybookPercentage(percentages, 'fast_breaks', row?.id),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || '',
    }));
  } else if (key === 'hc_traps') {
    items = (data?.hc_traps || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: getLineupPlaybookPercentage(percentages, 'hc_traps', row?.id),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || '',
    }));
  }

  return items
    .filter((item) => lineupPlaybookItemVisible(item, key, data))
    .sort(function (a, b) {
      if (key === 'set_plays' && typeof compareSetPlaysForDisplay === 'function') {
        return compareSetPlaysForDisplay(a, b, { percentPrimary: true });
      }
      return (
        Number(b.percentage || 0) - Number(a.percentage || 0) ||
        String(a.name).localeCompare(String(b.name))
      );
    });
}

function renderLineupPlaybooksModal(data) {
  const host = document.getElementById('playbooks-modal-sections');
  if (!host) return;
  host.innerHTML = '';
  LINEUP_PLAYBOOK_SECTION_ORDER.forEach((section) => {
    const items = buildLineupPlaybookItems(data, section.key);
    const sectionEl = document.createElement('section');
    sectionEl.className = 'lineup-playbooks-section';
    sectionEl.innerHTML = `
      <div class="lineup-playbooks-head">${escapeLineupPlaybookHtml(section.label)}</div>
      <div class="lineup-playbooks-items">
        ${items.length ? items.map((item) => `
          <article class="lineup-playbook-card">
            <div class="lineup-playbook-card-top">
              <div class="lineup-playbook-card-name">${escapeLineupPlaybookHtml(item.name)}</div>
              <div class="lineup-playbook-card-pct">${escapeLineupPlaybookHtml(`${Number(item.percentage || 0)}%`)}</div>
            </div>
            <div class="lineup-playbook-card-meta">
              <div class="lineup-playbook-card-eff ${getLineupPlaybookEffClass(item.effectiveness)}">${escapeLineupPlaybookHtml(`CMD: ${Number(item.effectiveness || 0)}`)}</div>
              ${item.top_scorer && item.top_scorer !== 'N/A' ? `<div class="lineup-playbook-card-top-scorer">${escapeLineupPlaybookHtml(`TOP: ${item.top_scorer}`)}</div>` : ''}
            </div>
          </article>
        `).join('') : '<div class="lineup-playbooks-empty">No plays assigned.</div>'}
      </div>
    `;
    host.appendChild(sectionEl);
  });
}

function closeLineupPlaybooksModal() {
  const modal = document.getElementById('playbooks-modal');
  if (!modal) return;
  modal.hidden = true;
  document.body.style.overflow = '';
}

async function openLineupPlaybooksModal() {
  const modal = document.getElementById('playbooks-modal');
  const host = document.getElementById('playbooks-modal-sections');
  if (!modal || !host) return;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
  host.innerHTML = '<div class="lineup-playbooks-empty">Loading playbook settings...</div>';
  try {
    lineupPlaybooksModalCache = await fetchLineupPlaybooksData();
    if (!lineupPlaybooksModalCache) {
      host.innerHTML = '<div class="lineup-playbooks-empty">Failed to load playbook settings.</div>';
      return;
    }
    renderLineupPlaybooksModal(lineupPlaybooksModalCache);
  } catch (error) {
    console.error('[SET-LINEUP] Failed to load playbooks modal:', error);
    host.innerHTML = '<div class="lineup-playbooks-empty">Failed to load playbook settings.</div>';
  }
}

function initLineupPlaybooksModal() {
  if (lineupPlaybooksModalInitialized) return;
  lineupPlaybooksModalInitialized = true;
  const closeBtn = document.getElementById('playbooks-modal-close');
  const backdrop = document.getElementById('playbooks-modal-backdrop');
  closeBtn?.addEventListener('click', closeLineupPlaybooksModal);
  backdrop?.addEventListener('click', closeLineupPlaybooksModal);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeLineupPlaybooksModal();
  });
}

// User team's conference / region (captured from the roster fetch) for the
// tournament tier emblem value — same value as the FCC/court emblems.
let lineupUserConference = null;
let lineupUserRegion = null;

// Surface: tier emblem on the set-lineup context bar (score/time row). Tier from
// the week URL param; value from the roster. Cleared outside a franchise EOS week.
function renderLineupTierEmblem() {
  const slot = document.getElementById('lineup-tier-emblem');
  if (!slot || !window.GOBTierEmblem) return;
  const tier = franchiseId ? window.GOBTierEmblem.tierForWeek(weekParam) : null;
  if (!tier) { slot.innerHTML = ''; return; }
  let value = null;
  if (tier === 'conference') {
    value = (lineupUserConference === 0 || lineupUserConference) ? String(lineupUserConference) : '';
  } else if (tier === 'region') {
    if (lineupUserRegion) {
      value = String(lineupUserRegion).toUpperCase();
    } else {
      const c = Number(lineupUserConference);
      if (Number.isInteger(c) && c >= 1 && c <= 16) value = String.fromCharCode(65 + Math.floor((c - 1) / 2));
    }
  }
  window.GOBTierEmblem.injectCss();
  slot.innerHTML = window.GOBTierEmblem.renderLockup({ tier, value, size: 34, variant: 'stack', l1: 13, l2: 8 });
}

async function loadRoster() {
  if (!teamName) return;
  
  // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
  // Supports tournament_id and franchise_id query parameters
  let url = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(teamName)}`);
  const params = new URLSearchParams();
  if (tournamentId) {
    params.append('tournament_id', tournamentId);
  }
  if (franchiseId) {
    params.append('franchise_id', franchiseId);
  }
  params.append('profile', '1');
  if (params.toString()) {
    url += `?${params.toString()}`;
  }
  console.log("Loading roster for lineup", franchiseId ? "(franchise mode)" : tournamentId ? "(tournament mode)" : "(single game mode)");
  
  const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
  if (abortIfAccessDenied(res)) return;
  if (!res.ok) return;
  const data = await res.json();
  lineupUserConference = (data.conference === 0 || data.conference) ? data.conference : null;
  lineupUserRegion = data.region || null;
  renderLineupTierEmblem();
  rosterTeamChemistry = data.team_chemistry != null && data.team_chemistry !== ''
    ? Number(data.team_chemistry)
    : 15;
  if (Number.isNaN(rosterTeamChemistry)) rosterTeamChemistry = 15;
  roster = (data.players || []).map((p, idx) => ({ ...p, _idx: idx }));
  
  // If no gameId, initialize a new game (for pre-game lineup screen)
  // This creates a game document with initialized players (Emotion, Momentum)
  // ✅ CRITICAL FIX: Don't init if game_id exists in URL (game already exists) or if resuming from timeout
  // This prevents creating a new game when resuming from timeout, which would reset all game state
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  const resumeFromAnchor = urlParams.get('resume_from_anchor') === 'true'
    || urlParams.get('consume_resume_anchor') === 'true';

  // FTE v2 tutorial: init-game is supposed to run on the tutorial-situation
  // page (NOT here). If tutorial mode lands on set-lineup without a game_id,
  // the situation page failed to navigate properly — bounce back so the user
  // gets a clean retry instead of getting stuck with a half-initialized game
  // whose game_id never reaches the Play click (race condition we hit on the
  // second staging walkthrough).
  if (!gameId && modeParam === 'tutorial' && !resumeFromTimeout) {
    console.error('[SET-LINEUP][tutorial] No game_id on URL — bouncing to /tutorial-situation.html');
    window.location.replace('/tutorial-situation.html');
    return;
  }

  const shouldInitGame = !gameId && homeTeam && awayTeam && !resumeFromTimeout && !resumeFromAnchor && !initGameInProgress;
  
  if (shouldInitGame) {
    console.log("No gameId found - initializing new game for pre-game lineup");
    initGameInProgress = true; // Prevent duplicate calls
    try {
      const mode = modeParam || 'single';
      const initPayload = {
        home_team: homeTeam,
        away_team: awayTeam,
        mode: mode
      };
      attachMatchupTeamIds(initPayload);
      
      // ✅ CRITICAL: Pass user_team_side to init-game so GameManager can set is_user_team flags
      // This ensures user team settings are protected from autoset_strategy_settings()
      if (myTeamSide) {
        initPayload.user_team_side = myTeamSide; // "home" or "away"
      }
      
      // Add mode-specific IDs for playbook settings persistence
      if (mode === 'tournament' && tournamentId) {
        initPayload.tournament_id = tournamentId;
      } else if (mode === 'franchise' && franchiseId) {
        initPayload.franchise_id = franchiseId;
      }
      
      const initRes = await fetch(API_CONFIG.buildUrl('/api/init-game'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(initPayload)
      });
      if (abortIfAccessDenied(initRes)) return;
      if (initRes.ok) {
        const initData = await initRes.json();
        const newGameId = initData.game_id;
        console.log("✅ Initialized new game:", newGameId);
        
        // ✅ PHASE 1.1: Only store game_home/game_away for team matching check (not game_id fallback)
        // game_id is only stored in URL (source of truth)
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('game_home', homeTeam);
          localStorage.setItem('game_away', awayTeam);
          if (homeId) localStorage.setItem('game_home_id', homeId);
          if (awayId) localStorage.setItem('game_away_id', awayId);
        }
        
        // ✅ SS&S: URL is the source of truth - update URL with gameId (without page reload)
        // Button handlers will read from window.location.search, not from module-level variable
        const newParams = new URLSearchParams(window.location.search);
        newParams.set('game_id', newGameId);
        if (typeof history !== 'undefined' && history.replaceState) {
          history.replaceState(null, '', `${window.location.pathname}?${newParams.toString()}`);
        }
      } else {
        console.warn("Failed to initialize game:", initRes.status, initRes.statusText);
      }
    } catch (err) {
      console.warn("Could not initialize game:", err);
    } finally {
      initGameInProgress = false; // Reset flag
    }
  } else if (gameId) {
    console.log("Game ID exists - skipping init-game (game already exists)");
  } else if (resumeFromTimeout) {
    console.log("Resuming from timeout - skipping init-game (game should already exist)");
  }
  
  // If there's an active game, fetch current player energy levels.
  // Use getActiveGameId() — init-game may have just written game_id to the URL while the
  // page-load `gameId` const is still null (franchise pre-game flow).
  // Pass actual quarter from URL params to ensure correct stats loading (not hardcoded quarter=1)
  // Backend detects new game scenarios when quarter=1 is requested but saved game is Q2+
  const mergeGameId = getActiveGameId();
  if (mergeGameId) {
    console.log("Loading current player energy from game:", mergeGameId);
    try {
        // ✅ HYBRID APPROACH: Use source=db to ensure fresh data from database
        const gameRes = await fetch(`${API_CONFIG.buildUrl(`/api/game/${mergeGameId}`)}?quarter=${quarter}&source=db`, { headers: API_CONFIG.getAuthHeaders() });
        if (abortIfAccessDenied(gameRes)) return;
        if (gameRes.ok) {
          const gameData = await gameRes.json();
          const gamePlayers = gameData.players || [];
          
          console.log(`Found ${gamePlayers.length} players with energy data from game`);
          
          // Debug: Log roster player names and IDs
          console.log('[Lineup] Roster players:', roster.map(p => ({
            name: p.name,
            id: p._id || p.playerId || p.player_id
          })));
          
          // Debug: Log game player names and IDs
          console.log('[Lineup] Game players:', gamePlayers.map(gp => ({
            name: gp.name,
            id: gp._id || gp.playerId || gp.player_id,
            hasStats: !!gp.stats
          })));
        
        // Merge game data into roster (same approach as box-score.js)
        // ✅ PERFORMANCE FIX: Build lookup maps once (O(n)) instead of nested find() loops (O(n²))
        const rosterById = new Map();
        const rosterByName = new Map();
        roster.forEach(p => {
          const playerId = p._id || p.playerId || p.player_id;
          if (playerId) {
            rosterById.set(String(playerId), p);
          }
          if (p.name) {
            rosterByName.set(p.name, p);
          }
        });
        
        let updatedCount = 0;
        gamePlayers.forEach(gp => {
          const playerId = gp._id || gp.playerId || gp.player_id;
          if (!playerId) {
            console.warn("Game player missing ID:", gp);
            return;
          }
          
          // ✅ PERFORMANCE FIX: O(1) lookup instead of O(n) find()
          let rosterPlayer = rosterById.get(String(playerId));
          
          // Fallback to name matching if ID doesn't match
          if (!rosterPlayer && gp.name) {
            rosterPlayer = rosterByName.get(gp.name);
            if (rosterPlayer) {
              console.log(`[Lineup] Matched ${gp.name} by name (ID mismatch: game=${playerId}, roster=${rosterPlayer._id || rosterPlayer.playerId || rosterPlayer.player_id})`);
            }
          }
          
          if (rosterPlayer) {
            // Energy (same as before)
            rosterPlayer.attributes = rosterPlayer.attributes || {};
            const energyValue = gp.NG ?? gp.energy ?? gp.attributes?.NG ?? 1.0;
            rosterPlayer.attributes.NG = energyValue;
            rosterPlayer.NG = energyValue;
            
            // Stats: Use EXACT same approach as box-score.js (line 203)
            // Flatten stats to player.stats (not nested under .game)
            rosterPlayer.stats = gp.stats?.game || gp.stats || {};
            
            // Ineligible (fouled out): derive from game foul count each visit – no persisted list
            const fouls = Number(rosterPlayer.stats.F) || 0;
            if (fouls >= 5) {
              rosterPlayer.ineligible = true;
              rosterPlayer.fouled_out = true;
            }
            
            // Attributes: EM and MO from game doc (overrides franchise roster training MO)
            if (gp.attributes) {
              if (gp.attributes.EM != null) {
                rosterPlayer.attributes.EM = gp.attributes.EM;
              } else if (rosterPlayer.attributes.EM == null) {
                rosterPlayer.attributes.EM = 50;
              }
              if (gp.attributes.MO != null) {
                rosterPlayer.attributes.MO = gp.attributes.MO;
              } else if (rosterPlayer.attributes.MO == null) {
                rosterPlayer.attributes.MO = 0;
              }
              rosterPlayer.EM = rosterPlayer.attributes.EM;
              rosterPlayer.MO = rosterPlayer.attributes.MO;
            }
            
            updatedCount++;
          } else {
            // Debug: Show what we tried to match
            const rosterNames = roster.map(p => p.name).join(', ');
            console.warn(`Could not find roster player for game player: ${gp.name || 'Unknown'} (ID: ${playerId})`, {
              triedName: gp.name,
              rosterNames: rosterNames,
              rosterCount: roster.length
            });
          }
        });
        
        console.log(`Successfully updated ${updatedCount} players with game data`);
        
        // Refresh slot displays to show updated stats
        updateAllSlotDisplays();
      } else {
        console.warn(`Failed to fetch game data: ${gameRes.status} ${gameRes.statusText}`);
      }
    } catch (err) {
      console.warn("Could not load player energy from game:", err);
    }
  } else {
    console.log("No gameId found, skipping energy load (players will show default 100%)");
  }
  
  // ✅ PERFORMANCE FIX: Sort first, then build playerMap once (removed duplicate building)
  roster.sort((a, b) => {
    const diff = getRT(b) - getRT(a);
    return diff !== 0 ? diff : a._idx - b._idx;
  });
  console.log("Sorted lineup by RT descending");
  
  // ✅ PERFORMANCE FIX: Build playerMap once after sorting (removed duplicate forEach)
  roster.forEach(p => {
    delete p._idx;
    const playerId = p._id || p.playerId || p.player_id;
    if (playerId) {
      playerMap[playerId] = p;
    }
  });
  
  renderRoster();
}

function getGameStatsForRoster(p) {
  const raw = p.stats || {};
  return raw.game || raw;
}

/** Match box-score.js player stats MIN formatting */
function formatMinutesRosterStats(seconds) {
  if (!seconds) return '0';
  return Math.floor(seconds / 60).toString();
}

const LINEUP_POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const FOUL_TROUBLE_MIN = 3;

const ROSTER_STATS_COLUMN_NAMES = [
  'POS', 'PLAYER', 'ENG', 'RT',
  'PTS', 'FGM/FGA', '3PTM/3PTA', 'FTM/FTA', 'DREB', 'OREB', 'TREB', 'AST', 'STL', 'BLK', 'F', 'TO', 'DEFA', 'DEF%', 'SCRA', 'SCR%', 'MIN'
];
const ROSTER_ATTR_COLUMN_NAMES = [
  'POS', 'PLAYER', 'ENG', 'RT', 'HT', 'WT', 'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'
];
const ROSTER_GAME_COLUMN_NAMES = ['POS', 'PLAYER', 'ENG', 'PTS', 'REB', 'AST', 'DEF%', 'RT', 'F', 'MIN', 'MO'];

let rosterPanelView = 'game'; // game | attributes | stats
let rosterDataForSorting = [];
let attrSortColumn = 'ENG';
let attrSortDirection = 'desc';
let rosterStatsRows = [];
let statsSortColumn = 'ENG';
let statsSortDirection = 'desc';
let gameSortColumn = 'ENG';
let gameSortDirection = 'desc';
let rosterTableEventsBound = false;

function getEnergyPercent(player) {
  const ng = player?.attributes?.NG ?? player?.NG ?? 1.0;
  return Math.round((Number(ng) || 0) * 100);
}

function getEnergyClassFromPercent(percent) {
  if (percent >= 90) return 'high';
  if (percent >= 80) return 'medium';
  if (percent >= 70) return 'low';
  return 'critical';
}

function getEnergyEdgeColor(energyClass) {
  if (energyClass === 'medium') return '#F5C518';
  if (energyClass === 'low') return '#ff9f43';
  if (energyClass === 'critical') return '#ff6d6d';
  return 'transparent';
}

function getAssignedSlotForPlayer(playerId) {
  if (!playerId) return null;
  for (const pos of LINEUP_POSITIONS) {
    if (lineup[pos] != null && String(lineup[pos]) === String(playerId)) return pos;
  }
  return null;
}

function getNaturalPosition(player) {
  const entries = Object.entries(player?.position_ratings || {});
  if (!entries.length) return '--';
  return entries.reduce((a, b) => (b[1] > a[1] ? b : a))[0];
}

function getDisplayRt(player, assignedSlot) {
  const ratings = player?.position_ratings || {};
  if (assignedSlot && ratings[assignedSlot] != null) return ratings[assignedSlot];
  const values = Object.values(ratings);
  return values.length ? Math.max(...values) : '--';
}

function getPlayerFouls(player) {
  const st = getGameStatsForRoster(player);
  return Number(st.F) || 0;
}

function isLineupPregameContext() {
  const scoreboard = document.getElementById('context-scoreboard');
  if (scoreboard) return scoreboard.classList.contains('is-pregame');
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  const currentQuarter = parseInt(urlParams.get('quarter'), 10) || quarter || 1;
  const activeId = typeof getActiveGameId === 'function' ? getActiveGameId() : gameId;
  return !(activeId && (resumeFromTimeout || currentQuarter > 1));
}

function buildEnergyCell(percent) {
  const energyClass = getEnergyClassFromPercent(percent);
  const td = document.createElement('td');
  td.className = 'eng-cell';
  td.innerHTML = `
    <div class="eng">
      <div class="engbar"><i class="${energyClass}" style="width:${Math.max(0, Math.min(100, percent))}%"></i></div>
      <span class="engnum ${energyClass}">${percent}%</span>
    </div>`;
  return td;
}

function buildRtCell(player, assignedSlot) {
  const rt = getDisplayRt(player, assignedSlot);
  const rtTd = document.createElement('td');
  rtTd.className = `rt ${rtBucketClassOrEmpty(rt)}`;
  rtTd.textContent = formatRtDisplay(rt);
  return rtTd;
}

function getRosterDefPct(stats) {
  const defa = Number(stats?.DEF_A) || 0;
  const defs = Number(stats?.DEF_S) || 0;
  return defa > 0 ? Math.round((defs / defa) * 100) : 0;
}

function buildProductionCell(player) {
  const td = document.createElement('td');
  td.className = 'prod-cell';
  if (!player) {
    td.innerHTML = '<div class="prod"></div>';
    return td;
  }
  const stats = getGameStatsForRoster(player);
  const reb = (Number(stats.DREB) || 0) + (Number(stats.OREB) || 0);
  const pts = Number(stats.PTS) || 0;
  const ast = Number(stats.AST) || 0;
  const defPct = getRosterDefPct(stats);
  td.innerHTML = `
    <div class="prod">
      <span><b class="pv">${pts}</b><i class="pk">PTS</i></span>
      <span><b class="pv">${reb}</b><i class="pk">REB</i></span>
      <span><b class="pv">${ast}</b><i class="pk">AST</i></span>
      <span><b class="pv">${defPct}</b><i class="pk">DEF%</i></span>
    </div>`;
  return td;
}

function buildMoPipsCell(moValue) {
  const td = document.createElement('td');
  const mo = Math.max(-5, Math.min(5, Number(moValue) || 0));
  const neg = [];
  const pos = [];
  for (let i = 1; i <= 5; i += 1) {
    const onNeg = mo < 0 && i <= Math.abs(mo);
    const onPos = mo > 0 && i <= mo;
    neg.push(`<s class="${onNeg ? 'on neg' : ''}"></s>`);
    pos.push(`<s class="${onPos ? 'on pos' : ''}"></s>`);
  }
  td.innerHTML = `
    <div class="mo-pips" title="${mo === 0 ? '' : (mo > 0 ? '+' + mo : String(mo))}">
      <div class="side neg">${neg.join('')}</div>
      <div class="ctr"></div>
      <div class="side pos">${pos.join('')}</div>
    </div>`;
  return td;
}

function buildHeadshotCell(playerId, playerName) {
  const td = document.createElement('td');
  td.className = 'hs-cell';
  if (!playerId) {
    td.innerHTML = '<div class="roster-empty-hs" aria-hidden="true"></div>';
    return td;
  }
  const playerImg = (typeof API_CONFIG !== 'undefined' && API_CONFIG.getPlayerImageUrl)
    ? API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' })
    : `/images/players/${playerId}.png`;
  const genericImg = (typeof API_CONFIG !== 'undefined' && API_CONFIG.getGenericHeadshotUrl)
    ? API_CONFIG.getGenericHeadshotUrl({ size: 'card' })
    : '/images/players/generic_headshot.png';
  const img = document.createElement('img');
  img.className = 'roster-headshot';
  img.src = playerImg;
  img.alt = playerName || '';
  img.onerror = () => { img.onerror = null; img.src = genericImg; };
  td.appendChild(img);
  return td;
}

function buildRemoveCell(pos, playerId) {
  const td = document.createElement('td');
  td.className = 'rm-cell';
  if (!pos || !playerId) return td;
  if (isFtLockedPlayer(playerId)) return td;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'roster-row-remove';
  btn.setAttribute('aria-label', `Remove player from ${pos}`);
  btn.dataset.pos = pos;
  btn.textContent = '✕';
  td.appendChild(btn);
  return td;
}

function appendSharedLeadingCells(tr, {
  posLabel,
  player,
  playerId,
  assignedSlot,
  empty = false,
  includeRt = true,
}) {
  const edgeClass = empty ? 'high' : getEnergyClassFromPercent(getEnergyPercent(player || {}));
  const slotTd = document.createElement('td');
  slotTd.className = 'slot-cell';
  slotTd.style.setProperty('--edge', empty ? 'transparent' : getEnergyEdgeColor(edgeClass));
  slotTd.textContent = posLabel || '--';
  tr.appendChild(slotTd);

  if (empty) {
    tr.appendChild(buildHeadshotCell(null));
    const nameTd = document.createElement('td');
    nameTd.className = 'player-name-cell';
    nameTd.innerHTML = '<span class="roster-empty-copy">Empty</span>';
    tr.appendChild(nameTd);
    const emptyEng = document.createElement('td');
    emptyEng.className = 'eng-cell';
    emptyEng.textContent = '—';
    tr.appendChild(emptyEng);
    if (includeRt) {
      const emptyRt = document.createElement('td');
      emptyRt.className = 'rt';
      emptyRt.textContent = '—';
      tr.appendChild(emptyRt);
    }
    return;
  }

  tr.appendChild(buildHeadshotCell(playerId, player?.name));

  const nameTd = document.createElement('td');
  nameTd.className = 'player-name-cell';
  const wrap = document.createElement('div');
  wrap.className = 'player-name-wrap';
  const nameText = document.createElement('span');
  nameText.className = 'player-name-link';
  nameText.textContent = typeof formatNameWithJersey === 'function'
    ? formatNameWithJersey(player.jersey, player.name)
    : (player.name || '—');
  wrap.appendChild(nameText);
  if (isFtLockedPlayer(playerId)) {
    const badge = document.createElement('span');
    badge.className = 'ft-shooter-lock-badge';
    badge.textContent = 'Free Throw Shooter';
    wrap.appendChild(badge);
  }
  nameTd.appendChild(wrap);
  tr.appendChild(nameTd);

  tr.appendChild(buildEnergyCell(getEnergyPercent(player)));

  if (includeRt) {
    tr.appendChild(buildRtCell(player, assignedSlot));
  }
}

function buildGroupHeaderRow(label, count, colSpan, warnText = '') {
  const tr = document.createElement('tr');
  tr.className = 'group-header';
  const td = document.createElement('td');
  td.colSpan = colSpan;
  const warnHtml = warnText
    ? `<span class="roster-group-warn">${warnText}</span>`
    : '';
  td.innerHTML = `<div class="roster-group-label"><span class="lbl">${label}</span><span class="cnt">${count}</span>${warnHtml}</div>`;
  tr.appendChild(td);
  return tr;
}

function comparePlayersForSort(a, b, columnName, direction) {
  const desc = direction === 'desc';
  const slotA = a._assignedSlot || null;
  const slotB = b._assignedSlot || null;

  const energyA = getEnergyPercent(a);
  const energyB = getEnergyPercent(b);
  const foulsA = getPlayerFouls(a);
  const foulsB = getPlayerFouls(b);
  const statsA = getGameStatsForRoster(a);
  const statsB = getGameStatsForRoster(b);
  const moA = Number(a.attributes?.MO ?? a.MO ?? 0) || 0;
  const moB = Number(b.attributes?.MO ?? b.MO ?? 0) || 0;
  const rtA = getDisplayRt(a, slotA);
  const rtB = getDisplayRt(b, slotB);
  const posA = slotA || getNaturalPosition(a);
  const posB = slotB || getNaturalPosition(b);

  let val1;
  let val2;

  if (columnName === 'PLAYER' || columnName === 'Player Name' || columnName === 'Name') {
    val1 = a.name || '';
    val2 = b.name || '';
    return desc ? val2.localeCompare(val1) : val1.localeCompare(val2);
  }
  if (columnName === 'POS' || columnName === 'Pos') {
    val1 = LINEUP_POSITIONS.indexOf(posA);
    val2 = LINEUP_POSITIONS.indexOf(posB);
    if (val1 < 0) val1 = 99;
    if (val2 < 0) val2 = 99;
  } else if (columnName === 'ENG' || columnName === 'NG') {
    val1 = energyA;
    val2 = energyB;
  } else if (columnName === 'RT') {
    val1 = Number(rtA);
    val2 = Number(rtB);
    if (!Number.isFinite(val1)) val1 = -Infinity;
    if (!Number.isFinite(val2)) val2 = -Infinity;
  } else if (columnName === 'F') {
    val1 = foulsA;
    val2 = foulsB;
  } else if (columnName === 'MIN') {
    val1 = Number(statsA.MIN) || 0;
    val2 = Number(statsB.MIN) || 0;
  } else if (columnName === 'MO') {
    val1 = moA;
    val2 = moB;
  } else if (columnName === 'HT') {
    const parseHeight = (h) => {
      if (!h || h === '--') return 0;
      const match = String(h).match(/(\d+)'(\d+)"/);
      return match ? parseInt(match[1], 10) * 12 + parseInt(match[2], 10) : 0;
    };
    val1 = parseHeight(a.height);
    val2 = parseHeight(b.height);
  } else if (columnName === 'WT') {
    val1 = parseInt(a.weight, 10) || 0;
    val2 = parseInt(b.weight, 10) || 0;
  } else if (['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'].includes(columnName)) {
    const attrsA = a.attributes || {};
    const attrsB = b.attributes || {};
    val1 = Math.floor((attrsA[`anchor_${columnName}`] ?? attrsA[columnName] ?? 0) / 10);
    val2 = Math.floor((attrsB[`anchor_${columnName}`] ?? attrsB[columnName] ?? 0) / 10);
  } else if (columnName === 'PTS') {
    val1 = Number(statsA.PTS) || 0;
    val2 = Number(statsB.PTS) || 0;
  } else if (columnName === 'REB') {
    val1 = (Number(statsA.DREB) || 0) + (Number(statsA.OREB) || 0);
    val2 = (Number(statsB.DREB) || 0) + (Number(statsB.OREB) || 0);
  } else if (columnName === 'FGM/FGA') {
    val1 = Number(statsA.FGM) || 0;
    val2 = Number(statsB.FGM) || 0;
    if (val1 === val2) {
      val1 = Number(statsA.FGA) || 0;
      val2 = Number(statsB.FGA) || 0;
    }
  } else if (columnName === '3PTM/3PTA') {
    val1 = Number(statsA['3PTM']) || 0;
    val2 = Number(statsB['3PTM']) || 0;
    if (val1 === val2) {
      val1 = Number(statsA['3PTA']) || 0;
      val2 = Number(statsB['3PTA']) || 0;
    }
  } else if (columnName === 'FTM/FTA') {
    val1 = Number(statsA.FTM) || 0;
    val2 = Number(statsB.FTM) || 0;
    if (val1 === val2) {
      val1 = Number(statsA.FTA) || 0;
      val2 = Number(statsB.FTA) || 0;
    }
  } else if (columnName === 'DREB') {
    val1 = Number(statsA.DREB) || 0;
    val2 = Number(statsB.DREB) || 0;
  } else if (columnName === 'OREB') {
    val1 = Number(statsA.OREB) || 0;
    val2 = Number(statsB.OREB) || 0;
  } else if (columnName === 'TREB') {
    val1 = (Number(statsA.DREB) || 0) + (Number(statsA.OREB) || 0);
    val2 = (Number(statsB.DREB) || 0) + (Number(statsB.OREB) || 0);
  } else if (columnName === 'AST') {
    val1 = Number(statsA.AST) || 0;
    val2 = Number(statsB.AST) || 0;
  } else if (columnName === 'STL') {
    val1 = Number(statsA.STL) || 0;
    val2 = Number(statsB.STL) || 0;
  } else if (columnName === 'BLK') {
    val1 = Number(statsA.BLK) || 0;
    val2 = Number(statsB.BLK) || 0;
  } else if (columnName === 'TO') {
    val1 = Number(statsA.TO) || 0;
    val2 = Number(statsB.TO) || 0;
  } else if (columnName === 'DEFA') {
    val1 = Number(statsA.DEF_A) || 0;
    val2 = Number(statsB.DEF_A) || 0;
  } else if (columnName === 'DEF%') {
    const defaA = Number(statsA.DEF_A) || 0;
    const defaB = Number(statsB.DEF_A) || 0;
    val1 = defaA > 0 ? ((Number(statsA.DEF_S) || 0) / defaA) * 100 : 0;
    val2 = defaB > 0 ? ((Number(statsB.DEF_S) || 0) / defaB) * 100 : 0;
  } else if (columnName === 'SCRA') {
    val1 = Number(statsA.SCR_A) || 0;
    val2 = Number(statsB.SCR_A) || 0;
  } else if (columnName === 'SCR%') {
    const scraA = Number(statsA.SCR_A) || 0;
    const scraB = Number(statsB.SCR_A) || 0;
    val1 = scraA > 0 ? ((Number(statsA.SCR_S) || 0) / scraA) * 100 : 0;
    val2 = scraB > 0 ? ((Number(statsB.SCR_S) || 0) / scraB) * 100 : 0;
  } else {
    val1 = 0;
    val2 = 0;
  }

  if (desc) return val2 - val1;
  return val1 - val2;
}

function sortPlayerList(list, columnName, direction) {
  return [...list].sort((a, b) => comparePlayersForSort(a, b, columnName, direction));
}

function decoratePlayerForRoster(p) {
  const playerId = getPlayerStableId(p);
  const assignedSlot = getAssignedSlotForPlayer(playerId);
  return { ...p, _playerId: playerId, _assignedSlot: assignedSlot };
}

function updateLineupHeaderReads() {
  const host = document.getElementById('lineup-header-reads');
  if (!host) return;
  if (isLineupPregameContext()) {
    host.hidden = true;
    host.innerHTML = '';
    return;
  }
  const onCourt = LINEUP_POSITIONS
    .map((pos) => (lineup[pos] ? playerMap[lineup[pos]] : null))
    .filter(Boolean);
  if (onCourt.length < 5) {
    host.hidden = true;
    host.innerHTML = '';
    return;
  }
  const energies = onCourt.map(getEnergyPercent);
  const avg = Math.round(energies.reduce((s, n) => s + n, 0) / energies.length);
  const under70 = energies.filter((n) => n < 70).length;
  const foulRisk = onCourt.filter((p) => getPlayerFouls(p) >= FOUL_TROUBLE_MIN).length;
  host.hidden = false;
  host.innerHTML = `
    <span class="lineup-header-read"><span class="k">AVG ENG</span><span class="v">${avg}%</span></span>
    <span class="lineup-header-read"><span class="k">BELOW 70%</span><span class="v${under70 ? ' is-alert' : ''}">${under70}</span></span>
    <span class="lineup-header-read"><span class="k">FOUL TROUBLE</span><span class="v${foulRisk ? ' is-warn' : ''}">${foulRisk}</span></span>`;
}

function wireSortableHeaders(selector, _columnNames, onSort) {
  document.querySelectorAll(selector).forEach((header) => {
    const col = header.getAttribute('data-sort');
    if (!col) return;
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => onSort(col));
  });
}

function createPlayerRowShell(player, { onCourt, assignedSlot, emptySlot }) {
  const tr = document.createElement('tr');
  if (emptySlot) {
    tr.className = 'on-court empty-slot';
    tr.dataset.slot = emptySlot;
    tr.draggable = false;
    return tr;
  }
  const playerId = player._playerId || getPlayerStableId(player);
  tr.dataset.playerId = playerId;
  if (assignedSlot) tr.dataset.slot = assignedSlot;
  tr.classList.add(onCourt ? 'on-court' : 'bench');
  if (player.ineligible || player.fouled_out) {
    tr.classList.add('ineligible');
    tr.style.opacity = '0.7';
    tr.style.pointerEvents = 'none';
    tr.style.cursor = 'not-allowed';
    tr.draggable = false;
  } else {
    tr.draggable = !exhaustedUserLineupLocked;
    tr.style.cursor = onCourt ? 'grab' : 'pointer';
  }
  if (isFtLockedPlayer(playerId)) tr.classList.add('ft-shooter-locked');
  return tr;
}

function renderRosterGame() {
  const tbody = document.getElementById('roster-body-game');
  if (!tbody) return;
  tbody.innerHTML = '';
  const colSpan = 10;
  const decorated = roster.map(decoratePlayerForRoster);
  const byId = new Map(decorated.map((p) => [String(p._playerId), p]));
  const bench = sortPlayerList(
    decorated.filter((p) => !p._assignedSlot),
    gameSortColumn,
    gameSortDirection
  );
  const fragment = document.createDocumentFragment();

  function appendGameTail(tr, p) {
    tr.appendChild(buildProductionCell(p));
    tr.appendChild(buildRtCell(p, p._assignedSlot || null));
    const stats = getGameStatsForRoster(p);
    const fouls = Number(stats.F) || 0;
    const foulTd = document.createElement('td');
    foulTd.className = `foul-cell${fouls >= 5 ? ' out' : (fouls >= FOUL_TROUBLE_MIN ? ' warn' : '')}`;
    foulTd.textContent = String(fouls);
    tr.appendChild(foulTd);
    const minTd = document.createElement('td');
    minTd.textContent = formatMinutesRosterStats(Number(stats.MIN) || 0);
    tr.appendChild(minTd);
    tr.appendChild(buildMoPipsCell(p.attributes?.MO ?? p.MO ?? 0));
  }

  LINEUP_POSITIONS.forEach((pos) => {
    const pid = lineup[pos];
    const player = pid ? byId.get(String(pid)) : null;
    if (player) {
      const p = { ...player, _assignedSlot: pos };
      const tr = createPlayerRowShell(p, { onCourt: true, assignedSlot: pos });
      appendSharedLeadingCells(tr, {
        posLabel: pos,
        player: p,
        playerId: p._playerId,
        assignedSlot: pos,
        includeRt: false,
      });
      appendGameTail(tr, p);
      tr.appendChild(buildRemoveCell(pos, p._playerId));
      fragment.appendChild(tr);
      return;
    }
    const tr = createPlayerRowShell(null, { emptySlot: pos });
    appendSharedLeadingCells(tr, { posLabel: pos, empty: true, includeRt: false });
    tr.appendChild(buildProductionCell(null));
    const emptyRt = document.createElement('td');
    emptyRt.className = 'rt';
    emptyRt.textContent = '—';
    tr.appendChild(emptyRt);
    for (let i = 0; i < 3; i += 1) {
      const td = document.createElement('td');
      td.textContent = '—';
      tr.appendChild(td);
    }
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  fragment.appendChild(buildGroupHeaderRow('BENCH', bench.length, colSpan));
  bench.forEach((p) => {
    const tr = createPlayerRowShell(p, { onCourt: false, assignedSlot: null });
    appendSharedLeadingCells(tr, {
      posLabel: getNaturalPosition(p),
      player: p,
      playerId: p._playerId,
      assignedSlot: null,
      includeRt: false,
    });
    appendGameTail(tr, p);
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  tbody.appendChild(fragment);
  wireSortableHeaders('#roster-game-pane .roster-table thead th', ROSTER_GAME_COLUMN_NAMES, sortRosterGame);
}

function renderRosterAttributes() {
  const tbody = document.getElementById('roster-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  const colSpan = 20;
  const decorated = roster.map(decoratePlayerForRoster);
  const byId = new Map(decorated.map((p) => [String(p._playerId), p]));
  const bench = sortPlayerList(
    decorated.filter((p) => !p._assignedSlot),
    attrSortColumn,
    attrSortDirection
  );
  const fragment = document.createDocumentFragment();

  function appendAttrTail(tr, p) {
    const attrs = p.attributes || {};
    const vals = [
      formatHeight(p.height),
      p.weight != null && p.weight !== '' ? p.weight : '--',
      Math.floor((attrs.anchor_SC ?? attrs.SC ?? 0) / 10),
      Math.floor((attrs.anchor_SH ?? attrs.SH ?? 0) / 10),
      Math.floor((attrs.anchor_ID ?? attrs.ID ?? 0) / 10),
      Math.floor((attrs.anchor_OD ?? attrs.OD ?? 0) / 10),
      Math.floor((attrs.anchor_PS ?? attrs.PS ?? 0) / 10),
      Math.floor((attrs.anchor_BH ?? attrs.BH ?? 0) / 10),
      Math.floor((attrs.anchor_RB ?? attrs.RB ?? 0) / 10),
      Math.floor((attrs.anchor_ST ?? attrs.ST ?? 0) / 10),
      Math.floor((attrs.anchor_AG ?? attrs.AG ?? 0) / 10),
      Math.floor((attrs.anchor_ND ?? attrs.ND ?? 0) / 10),
      Math.floor((attrs.anchor_IQ ?? attrs.IQ ?? 0) / 10),
      Math.floor((attrs.anchor_FT ?? attrs.FT ?? 0) / 10),
    ];
    vals.forEach((val) => {
      const td = document.createElement('td');
      td.textContent = val ?? '--';
      tr.appendChild(td);
    });
  }

  LINEUP_POSITIONS.forEach((pos) => {
    const pid = lineup[pos];
    const player = pid ? byId.get(String(pid)) : null;
    if (player) {
      const p = { ...player, _assignedSlot: pos };
      const tr = createPlayerRowShell(p, { onCourt: true, assignedSlot: pos });
      appendSharedLeadingCells(tr, {
        posLabel: pos,
        player: p,
        playerId: p._playerId,
        assignedSlot: pos,
      });
      appendAttrTail(tr, p);
      tr.appendChild(buildRemoveCell(pos, p._playerId));
      fragment.appendChild(tr);
      return;
    }
    const tr = createPlayerRowShell(null, { emptySlot: pos });
    appendSharedLeadingCells(tr, { posLabel: pos, empty: true });
    for (let i = 0; i < 14; i += 1) {
      const td = document.createElement('td');
      td.textContent = '—';
      tr.appendChild(td);
    }
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  fragment.appendChild(buildGroupHeaderRow('BENCH', bench.length, colSpan));
  bench.forEach((p) => {
    const tr = createPlayerRowShell(p, { onCourt: false, assignedSlot: null });
    appendSharedLeadingCells(tr, {
      posLabel: getNaturalPosition(p),
      player: p,
      playerId: p._playerId,
      assignedSlot: null,
    });
    appendAttrTail(tr, p);
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  tbody.appendChild(fragment);
  wireSortableHeaders('#roster-attributes-pane .roster-table thead th', ROSTER_ATTR_COLUMN_NAMES, sortRoster);
  if (typeof initAttributeTooltips !== 'undefined') {
    const thead = document.querySelector('#roster-attributes-pane .roster-table thead');
    if (thead) initAttributeTooltips(thead, ['th', '[data-attr]']);
  }
}

function renderRosterStats() {
  const tbody = document.getElementById('roster-body-stats');
  if (!tbody) return;
  tbody.innerHTML = '';
  const colSpan = 23;
  const decorated = roster.map(decoratePlayerForRoster);
  const byId = new Map(decorated.map((p) => [String(p._playerId), p]));
  const bench = sortPlayerList(
    decorated.filter((p) => !p._assignedSlot),
    statsSortColumn,
    statsSortDirection
  );
  const fragment = document.createDocumentFragment();

  function appendStatsTail(tr, p) {
    const stats = getGameStatsForRoster(p);
    const treb = (Number(stats.DREB) || 0) + (Number(stats.OREB) || 0);
    const defa = Number(stats.DEF_A) || 0;
    const defs = Number(stats.DEF_S) || 0;
    const defPct = defa > 0 ? ((defs / defa) * 100).toFixed(0) : '0';
    const scra = Number(stats.SCR_A) || 0;
    const scrs = Number(stats.SCR_S) || 0;
    const scrPct = scra > 0 ? ((scrs / scra) * 100).toFixed(0) : '0';
    const fouls = Number(stats.F) || 0;
    const vals = [
      String(stats.PTS || 0),
      `${stats.FGM || 0}/${stats.FGA || 0}`,
      `${stats['3PTM'] || 0}/${stats['3PTA'] || 0}`,
      `${stats.FTM || 0}/${stats.FTA || 0}`,
      String(stats.DREB || 0),
      String(stats.OREB || 0),
      String(treb),
      String(stats.AST || 0),
      String(stats.STL || 0),
      String(stats.BLK || 0),
      String(fouls),
      String(stats.TO || 0),
      String(defa),
      `${defPct}%`,
      String(scra),
      `${scrPct}%`,
      formatMinutesRosterStats(Number(stats.MIN) || 0),
    ];
    vals.forEach((text, idx) => {
      const td = document.createElement('td');
      td.textContent = text;
      if (idx === 10) {
        td.className = `foul-cell${fouls >= 5 ? ' out' : (fouls >= FOUL_TROUBLE_MIN ? ' warn' : '')}`;
      }
      tr.appendChild(td);
    });
  }

  LINEUP_POSITIONS.forEach((pos) => {
    const pid = lineup[pos];
    const player = pid ? byId.get(String(pid)) : null;
    if (player) {
      const p = { ...player, _assignedSlot: pos };
      const tr = createPlayerRowShell(p, { onCourt: true, assignedSlot: pos });
      appendSharedLeadingCells(tr, {
        posLabel: pos,
        player: p,
        playerId: p._playerId,
        assignedSlot: pos,
      });
      appendStatsTail(tr, p);
      tr.appendChild(buildRemoveCell(pos, p._playerId));
      fragment.appendChild(tr);
      return;
    }
    const tr = createPlayerRowShell(null, { emptySlot: pos });
    appendSharedLeadingCells(tr, { posLabel: pos, empty: true });
    for (let i = 0; i < 17; i += 1) {
      const td = document.createElement('td');
      td.textContent = '—';
      tr.appendChild(td);
    }
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  fragment.appendChild(buildGroupHeaderRow('BENCH', bench.length, colSpan));
  bench.forEach((p) => {
    const tr = createPlayerRowShell(p, { onCourt: false, assignedSlot: null });
    appendSharedLeadingCells(tr, {
      posLabel: getNaturalPosition(p),
      player: p,
      playerId: p._playerId,
      assignedSlot: null,
    });
    appendStatsTail(tr, p);
    tr.appendChild(document.createElement('td'));
    fragment.appendChild(tr);
  });
  tbody.appendChild(fragment);
  wireSortableHeaders('#roster-stats-pane .roster-stats-table thead th', ROSTER_STATS_COLUMN_NAMES, sortRosterStats);
}

function applySelectionToRosterRows() {
  // Selection and interactions are bound once via bindRosterTableEvents().
}

function renderRoster() {
  renderRosterGame();
  renderRosterAttributes();
  renderRosterStats();
  updateLineupHeaderReads();
  bindRosterTableEvents();
}

function refreshLineupAvailabilityDisplay() {
  renderRoster();
}

function sortRoster(columnName) {
  if (attrSortColumn === columnName) {
    attrSortDirection = attrSortDirection === 'desc' ? 'asc' : 'desc';
  } else {
    attrSortColumn = columnName;
    attrSortDirection = 'desc';
  }
  renderRoster();
}

function sortRosterStats(columnName) {
  if (statsSortColumn === columnName) {
    statsSortDirection = statsSortDirection === 'desc' ? 'asc' : 'desc';
  } else {
    statsSortColumn = columnName;
    statsSortDirection = 'desc';
  }
  renderRoster();
}

function sortRosterGame(columnName) {
  if (gameSortColumn === columnName) {
    gameSortDirection = gameSortDirection === 'desc' ? 'asc' : 'desc';
  } else {
    gameSortColumn = columnName;
    gameSortDirection = 'desc';
  }
  renderRoster();
}

function initRosterPanelToggle() {
  const btnGame = document.getElementById('roster-view-game');
  const btnAttr = document.getElementById('roster-view-attributes');
  const btnStats = document.getElementById('roster-view-stats');
  const paneGame = document.getElementById('roster-game-pane');
  const paneAttr = document.getElementById('roster-attributes-pane');
  const paneStats = document.getElementById('roster-stats-pane');
  if (!btnGame || !btnAttr || !btnStats || !paneGame || !paneAttr || !paneStats) return;

  function apply(view) {
    rosterPanelView = view;
    btnGame.classList.toggle('active', view === 'game');
    btnAttr.classList.toggle('active', view === 'attributes');
    btnStats.classList.toggle('active', view === 'stats');
    paneGame.hidden = view !== 'game';
    paneAttr.hidden = view !== 'attributes';
    paneStats.hidden = view !== 'stats';
  }

  btnGame.addEventListener('click', () => {
    playSound('click-tiny.wav');
    apply('game');
  });
  btnAttr.addEventListener('click', () => {
    playSound('click-tiny.wav');
    apply('attributes');
  });
  btnStats.addEventListener('click', () => {
    playSound('click-tiny.wav');
    apply('stats');
  });
  apply('game');
}

function clearLineupSlot(pos) {
  const removedId = lineup[pos];
  if (isFtLockedPlayer(removedId)) {
    if (typeof showToast === 'function') showToast('Free throw shooter must stay in the lineup');
    return;
  }
  delete lineup[pos];
  if (removedId != null && rimRunnerPlayerId != null && String(rimRunnerPlayerId) === String(removedId)) {
    rimRunnerPlayerId = null;
  }
  updatePlayButton();
  renderRoster();
}

function applyRosterDrop({ draggedPlayerId, sourcePos, dropPos }) {
  if (!draggedPlayerId || !dropPos) return;
  const existingAtDrop = lineup[dropPos] || null;
  if (sourcePos && existingAtDrop) {
    lineup[sourcePos] = existingAtDrop;
  } else if (sourcePos && !existingAtDrop) {
    delete lineup[sourcePos];
  } else if (!sourcePos) {
    for (const p of Object.keys(lineup)) {
      if (String(lineup[p]) === String(draggedPlayerId)) delete lineup[p];
    }
  }
  lineup[dropPos] = draggedPlayerId;
  updatePlayButton();
  playSound('click-soft.mp3');
  renderRoster();
}

function bindRosterTableEvents() {
  const container = document.getElementById('roster-table-container');
  if (!container || rosterTableEventsBound) return;
  rosterTableEventsBound = true;

  container.addEventListener('dragstart', (e) => {
    const tr = e.target.closest('tr[data-player-id]');
    if (!tr || exhaustedUserLineupLocked) {
      e.preventDefault();
      return;
    }
    const playerId = tr.dataset.playerId;
    const sourcePos = tr.dataset.slot || '';
    e.dataTransfer.setData('text/plain', playerId);
    if (sourcePos) e.dataTransfer.setData('application/x-slot-pos', sourcePos);
    e.dataTransfer.effectAllowed = 'move';
  });

  container.addEventListener('dragover', (e) => {
    const tr = e.target.closest('tr[data-slot]');
    if (!tr) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    tr.classList.add('drag-over');
  });

  container.addEventListener('dragleave', (e) => {
    const tr = e.target.closest('tr[data-slot]');
    if (tr) tr.classList.remove('drag-over');
  });

  container.addEventListener('drop', (e) => {
    const tr = e.target.closest('tr[data-slot]');
    if (!tr) return;
    e.preventDefault();
    tr.classList.remove('drag-over');
    const draggedPlayerId = e.dataTransfer.getData('text/plain');
    const dropPos = tr.dataset.slot;
    let sourcePos = e.dataTransfer.getData('application/x-slot-pos') || null;
    if (!sourcePos) {
      for (const [p, id] of Object.entries(lineup)) {
        if (String(id) === String(draggedPlayerId)) {
          sourcePos = p;
          break;
        }
      }
    }
    const player = playerMap[draggedPlayerId];
    if (player && (player.ineligible || player.fouled_out)) {
      showToast(`${player.name} has fouled out and cannot play`);
      return;
    }
    applyRosterDrop({ draggedPlayerId, sourcePos, dropPos });
  });

  container.addEventListener('click', (e) => {
    const removeBtn = e.target.closest('.roster-row-remove');
    if (removeBtn) {
      e.stopPropagation();
      playSound('x-back.mp3');
      clearLineupSlot(removeBtn.dataset.pos);
      return;
    }
    const tr = e.target.closest('tr[data-player-id]');
    if (!tr || tr.classList.contains('on-court') || tr.classList.contains('ineligible')) return;
    const playerId = tr.dataset.playerId;
    if (!playerId || Object.values(lineup).some((id) => String(id) === String(playerId))) return;
    const assigned = fillNextSlot(playerId);
    if (assigned) playSound('click-soft.mp3');
  });
}

function updatePlayButton() {
  const playBtn = document.getElementById('play-now');
  const gameplanBtn = document.getElementById('gameplan-optional');
  
  const filled = ['PG','SG','SF','PF','C'].every(pos => lineup[pos]);
  
  if (filled) {
    // Enable play button when lineup is complete
    if (playBtn) {
      playBtn.classList.remove('disabled');
      playBtn.style.cursor = 'pointer';
    }
  } else {
    // Disable play button when lineup is incomplete
    if (playBtn) {
      playBtn.classList.add('disabled');
      playBtn.style.cursor = 'not-allowed';
    }
  }
  
  // Game Plan button is ALWAYS enabled (user can go to Game Plan anytime)
  if (gameplanBtn) {
    gameplanBtn.classList.remove('disabled');
    gameplanBtn.style.cursor = 'pointer';
    gameplanBtn.removeAttribute('disabled');
  }
}

function clockStringToSecondsForAutoset(clockStr) {
  if (clockStr == null || clockStr === '') return 480;
  const s = String(clockStr);
  if (!s.includes(':')) {
    const n = parseInt(s, 10);
    return Number.isNaN(n) ? 480 : n;
  }
  const parts = s.split(':');
  const m = parseInt(parts[0], 10) || 0;
  const sec = parseInt(parts[1], 10) || 0;
  return m * 60 + sec;
}

/** Match is_player_eligible_for_lineup clock context (quarter break / default quarter clock). */
function buildAutosetGameState() {
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  const q = parseInt(urlParams.get('quarter'), 10) || quarter || 1;
  let clockTime = urlParams.get('clock');
  const isQuarterBreak = !resumeFromTimeout && q > 1;
  if (isQuarterBreak || (!resumeFromTimeout && (!clockTime || clockTime === '0:00'))) {
    clockTime = q > 4 ? '4:00' : '8:00';
  }
  return { quarter: q, time_remaining: clockStringToSecondsForAutoset(clockTime) };
}

function rosterRowsForAutosetApi() {
  return roster.map(p => {
    const playerId = getPlayerStableId(p);
    const rawStats = p.stats || {};
    const gameStats = rawStats.game || rawStats;
    return {
      _id: playerId,
      first_name: p.first_name || '',
      last_name: p.last_name || '',
      name: p.name,
      attributes: p.attributes || {},
      position_ratings: p.position_ratings || {},
      stats: Object.keys(gameStats).length ? { game: gameStats } : {},
    };
  });
}

async function autosetLineup() {
  playSound('chaotic-choice.wav');
  LINEUP_POSITIONS.forEach((pos) => { delete lineup[pos]; });

  if (!roster.length || roster.length < 5) {
    showToast('Roster not loaded yet');
    return;
  }

  try {
    // Shot-weight autoset: pass franchise/team ids so the backend orders the fill by this
    // team's playbook shot-attempt likelihood. Franchise mode only; other modes → backend shuffle.
    const autosetTeamId =
      (typeof window.resolvePlaybookTeamIdFromSearch === 'function'
        ? window.resolvePlaybookTeamIdFromSearch(urlParams)
        : null) || userTeamIdParam || teamIdParam || null;
    const payload = {
      players: rosterRowsForAutosetApi(),
      game_state: buildAutosetGameState(),
      team_chemistry: rosterTeamChemistry,
    };
    if (franchiseId) payload.franchise_id = franchiseId;
    if (autosetTeamId) payload.team_id = autosetTeamId;
    const res = await fetch(API_CONFIG.buildUrl('/api/autoset-lineup'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (abortIfAccessDenied(res)) return;
    if (!res.ok) {
      let msg = `Autoset failed (${res.status})`;
      try {
        const err = await res.json();
        if (err.detail) {
          msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        }
      } catch (_) { /* ignore */ }
      showToast(msg);
      return;
    }
    const data = await res.json();
    const lu = data.lineup || {};
    ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
      if (lu[pos]) lineup[pos] = lu[pos];
    });
    updatePlayButton();
    refreshLineupAvailabilityDisplay();
    showToast('Lineup auto-generated!');
  } catch (e) {
    console.error('[autosetLineup]', e);
    showToast('Autoset failed');
  }
}

function updateSlotDisplay(_slot) {
  // Starting Five cards removed — table rows are the lineup UI.
}

function normalizeRimRunnerSelection() {
  if (rimRunnerPlayerId == null) return;
  const inLineup = Object.values(lineup).some((id) => String(id) === String(rimRunnerPlayerId));
  if (!inLineup) {
    rimRunnerPlayerId = null;
  }
}

function updateAllSlotDisplays() {
  normalizeRimRunnerSelection();
  updatePlayButton();
  renderRoster();
}

function clearSlot(slotOrPos) {
  const pos = typeof slotOrPos === 'string' ? slotOrPos : slotOrPos?.dataset?.pos;
  if (!pos) return;
  clearLineupSlot(pos);
}

function setupSlots() {
  // Cards removed. Table drag/drop is bound in bindRosterTableEvents().
  bindRosterTableEvents();
}

function resolveTeam() {
  if (myTeamSide === 'home' || myTeamSide === 'away') {
    teamName = myTeamSide === 'away' ? awayTeam : homeTeam;
    return !!teamName;
  }
  // ✅ PHASE 2.4: Removed localStorage fallback - user_team_id must come from URL
  // For franchise/tournament mode, user_team_id should be in URL
  // For single game mode, my_team ('home' or 'away') should be in URL
  const storedId = userTeamIdParam || teamIdParam;
  if (storedId) {
    if (homeId && storedId === homeId) {
      myTeamSide = 'home';
      teamName = homeTeam;
      return true;
    }
    if (awayId && storedId === awayId) {
      myTeamSide = 'away';
      teamName = awayTeam;
      return true;
    }
    // Name fallback for legacy URLs without home_id/away_id
    if (storedId === homeTeam) {
      myTeamSide = 'home';
      teamName = homeTeam;
      return true;
    }
    if (storedId === awayTeam) {
      myTeamSide = 'away';
      teamName = awayTeam;
      return true;
    }
  }
  return false;
}

async function setHeader() {
  const banner = document.getElementById('team-banner');
  const bannerFallback = document.getElementById('team-banner-fallback');
  const scoreHomeTeamEl = document.getElementById('score-home-team');
  const scoreAwayTeamEl = document.getElementById('score-away-team');
  const scoreHomeValueEl = document.getElementById('score-home-value');
  const scoreAwayValueEl = document.getElementById('score-away-value');
  const quarterValueEl = document.getElementById('quarter-value');
  const timeValueEl = document.getElementById('time-value');
  const scoreboardEl = document.getElementById('context-scoreboard');
  const playBtn = document.getElementById('play-now');
  if (!quarterValueEl || !timeValueEl) return;

  // Score dict keys = core URL names; chrome labels = display (overlay when present).
  const userTeamName = teamName;
  const opponentTeamName = myTeamSide === 'home' ? awayTeam : homeTeam;
  const userTeamLabel = myTeamSide === 'home' ? homeDisplay : (myTeamSide === 'away' ? awayDisplay : userTeamName);
  const opponentTeamLabel = myTeamSide === 'home' ? awayDisplay : homeDisplay;

  let userTeamScore = 0;
  let opponentTeamScore = 0;
  let scoresFromUrl = false;
  const resumeFromTimeoutForScores = urlParams.get('resume_from_timeout') === 'true';
  const urlHomeScore = urlParams.get('home_score');
  const urlAwayScore = urlParams.get('away_score');
  if (resumeFromTimeoutForScores && urlHomeScore !== null && urlHomeScore !== '' && urlAwayScore !== null && urlAwayScore !== '') {
    const h = parseInt(urlHomeScore, 10);
    const a = parseInt(urlAwayScore, 10);
    if (!isNaN(h) && !isNaN(a)) {
      userTeamScore = myTeamSide === 'home' ? h : a;
      opponentTeamScore = myTeamSide === 'home' ? a : h;
      scoresFromUrl = true;
      console.log('[setHeader] Using scores from URL (timeout):', { userTeamScore, opponentTeamScore });
    }
  }
  let gameData = null;
  if (!scoresFromUrl && gameId) {
    try {
      const gameRes = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}?quarter=${quarter}&source=db`), { headers: API_CONFIG.getAuthHeaders() });
      if (abortIfAccessDenied(gameRes)) return;
      if (gameRes.ok) {
        gameData = await gameRes.json();
        const score = gameData.score || {};
        userTeamScore = score[userTeamName] || 0;
        opponentTeamScore = score[opponentTeamName] || 0;
        console.log('[setHeader] Fetched scores:', { userTeamScore, opponentTeamScore, score });
      } else {
        console.warn('[setHeader] Failed to fetch game data:', gameRes.status);
      }
    } catch (err) {
      console.warn("[setHeader] Could not fetch game scores for header:", err);
    }
  } else if (!gameId && !scoresFromUrl) {
    console.log('[setHeader] No gameId, using default scores (0)');
  }
  
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  let clockTime = urlParams.get('clock');
  const currentQuarter = parseInt(urlParams.get('quarter'), 10) || quarter || 1;
  const isQuarterBreak = !resumeFromTimeout && currentQuarter > 1;
  if (isQuarterBreak) {
    clockTime = currentQuarter > 4 ? '4:00' : '8:00';
  } else if (!resumeFromTimeout && (!clockTime || clockTime === '0:00')) {
    clockTime = currentQuarter > 4 ? '4:00' : '8:00';
  } else if (resumeFromTimeout && (!clockTime || clockTime === '')) {
    if (gameData && gameData.clock) {
      clockTime = gameData.clock;
    }
  }
  // FTE v2 tutorial: prefer the game doc's clock (4:00 set by
  // apply_tutorial_initial_state) over the quarter-break default ('8:00').
  if (modeParam === 'tutorial' && gameData && gameData.clock) {
    clockTime = gameData.clock;
  }
 
  let formattedClock = '--:--';
  if (clockTime) {
    if (!clockTime.includes(':')) {
      const totalSeconds = parseInt(clockTime, 10);
      if (!isNaN(totalSeconds)) {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        formattedClock = `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
    } else {
      formattedClock = clockTime;
    }
  }

  const bannerSrc = typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(userTeamLabel || teamName, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  if (banner && bannerFallback) {
    banner.src = bannerSrc;
    banner.alt = `${userTeamLabel || teamName} banner`;
    banner.hidden = false;
    bannerFallback.hidden = true;
    banner.onerror = () => {
      banner.hidden = true;
      bannerFallback.hidden = false;
    };
  }

  const isPregame = !(gameId && (resumeFromTimeout || currentQuarter > 1 || userTeamScore > 0 || opponentTeamScore > 0));
  scoreboardEl?.classList.toggle('is-pregame', isPregame);
  const displayUserTeamName = String(typeof formatTeamName === 'function' ? formatTeamName(userTeamLabel || 'Home') : (userTeamLabel || 'Home')).toUpperCase();
  const displayOpponentTeamName = String(typeof formatTeamName === 'function' ? formatTeamName(opponentTeamLabel || 'Away') : (opponentTeamLabel || 'Away')).toUpperCase();
  if (scoreHomeTeamEl) scoreHomeTeamEl.textContent = displayUserTeamName;
  if (scoreAwayTeamEl) scoreAwayTeamEl.textContent = displayOpponentTeamName;
  if (scoreHomeValueEl) scoreHomeValueEl.textContent = `${userTeamScore}`;
  if (scoreAwayValueEl) scoreAwayValueEl.textContent = `${opponentTeamScore}`;
  quarterValueEl.textContent = isPregame ? 'Pre-Game' : `Q${currentQuarter}`;
  timeValueEl.textContent = isPregame ? '--:--' : formattedClock;

  if (playBtn) {
    playBtn.textContent = isPregame ? 'Play Game' : 'Return to Game';
  }
}

function restoreLineupFromUrl() {
  // Restore lineup from URL parameters if present
  // Ensure myTeamSide is set (should be set by resolveTeam() before this is called)
  if (!myTeamSide) {
    console.warn('[restoreLineupFromUrl] myTeamSide not set, cannot restore lineup');
    return;
  }
  
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  let restoredCount = 0;
  positions.forEach(pos => {
    const paramKey = `${myTeamSide}_${pos.toLowerCase()}`;
    const playerId = urlParams.get(paramKey);
    if (playerId) {
      lineup[pos] = playerId;
      restoredCount++;
    }
  });
  if (restoredCount > 0) {
    console.log(`[restoreLineupFromUrl] Restored ${restoredCount} players from URL`);
  }
}

/**
 * Remove ineligible (fouled-out) players from the lineup
 * Called after lineup is restored from URL to ensure fouled-out players are removed
 */
function removeIneligiblePlayersFromLineup() {
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  let removedCount = 0;
  
  console.log(`🔍 [FOUL-OUT] Checking lineup for fouled-out players. Current lineup:`, lineup);
  
  positions.forEach(pos => {
    const playerId = lineup[pos];
    if (!playerId) return;
    
    // Find player in roster
    const player = roster.find(p => {
      const pId = p._id || p.playerId || p.player_id;
      return String(pId) === String(playerId);
    });
    
    // If player is ineligible (fouled out), remove from lineup
    if (player && (player.ineligible || player.fouled_out)) {
      console.log(`✅ [FOUL-OUT] Removing ${player.name} (ID: ${playerId}) from ${pos} slot (fouled out)`);
      delete lineup[pos];
      removedCount++;
      console.log(`✅ [FOUL-OUT] Cleared ${pos} from lineup`);
    }
  });
  
  if (removedCount > 0) {
    console.log(`✅ [FOUL-OUT] Removed ${removedCount} fouled-out player(s) from lineup. Updated lineup:`, lineup);
  } else {
    console.log(`✅ [FOUL-OUT] No fouled-out players found in lineup`);
  }
}

function wireLineupNavButtons() {
  const gameplanBtn = document.getElementById('gameplan-optional');
  if (gameplanBtn) {
    gameplanBtn.addEventListener('click', async () => {
      playSound('positive-beep.wav');
      console.log('🎮 GAME PLAN BUTTON CLICKED! Redirecting to game-plan.html');
      const currentUrlParams = new URLSearchParams(window.location.search);
      let currentGameId = currentUrlParams.get('game_id');
      const resumeFromTimeout = currentUrlParams.get('resume_from_timeout') === 'true';
      if (!currentGameId && homeTeam && awayTeam && !resumeFromTimeout && !initGameInProgress) {
        initGameInProgress = true;
        try {
          const mode = modeParam || 'single';
          const initPayload = { home_team: homeTeam, away_team: awayTeam, mode: mode };
          attachMatchupTeamIds(initPayload);
          if (mode === 'tournament' && tournamentId) initPayload.tournament_id = tournamentId;
          else if (mode === 'franchise' && franchiseId) initPayload.franchise_id = franchiseId;
          const initRes = await fetch(API_CONFIG.buildUrl('/api/init-game'), {
            method: 'POST',
            headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(initPayload)
          });
          if (abortIfAccessDenied(initRes)) {
            initGameInProgress = false;
            return;
          }
          if (initRes.ok) {
            const initData = await initRes.json();
            currentGameId = initData.game_id;
            currentUrlParams.set('game_id', currentGameId);
            if (typeof history !== 'undefined' && history.replaceState) {
              history.replaceState(null, '', `${window.location.pathname}?${currentUrlParams.toString()}`);
            }
          }
        } catch (err) {
          console.error('❌ [SET-LINEUP] Error initializing game for Game Plan navigation:', err);
          alert('Failed to initialize game. Please try again.');
          initGameInProgress = false;
          return;
        }
        initGameInProgress = false;
      } else if (initGameInProgress) {
        let waitCount = 0;
        while (initGameInProgress && waitCount < 50) {
          await new Promise(r => setTimeout(r, 100));
          waitCount++;
          currentGameId = new URLSearchParams(window.location.search).get('game_id');
          if (currentGameId) break;
        }
        if (!currentGameId) {
          alert('Game initialization is taking longer than expected. Please try again.');
          return;
        }
      }
      const helper = window.TimeoutNavigationHelper;
      if (!helper) {
        console.error('❌ [SET-LINEUP] TimeoutNavigationHelper not loaded!');
        return;
      }
      const params = helper.buildGameNavigationParams({
        sourceParams: currentUrlParams,
        targetQuarter: quarter,
        gameId: currentGameId,
        resumeFromTimeout: resumeFromTimeout,
        lineup: lineup,
        myTeamSide: myTeamSide
      });
      params.set('from', 'lineup');
      if (DEBUG) params.set('debug', '1');
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }
  const playbooksBtn = document.getElementById('playbooks-button');
  if (playbooksBtn) {
    initLineupPlaybooksModal();
    playbooksBtn.addEventListener('click', async () => {
      playSound('positive-beep.wav');
      await openLineupPlaybooksModal();
    });
  }
  const boxBtn = document.getElementById('box-score-button');
  if (boxBtn) {
    boxBtn.addEventListener('click', () => {
      playSound('positive-slide.wav');
      const helper = window.TimeoutNavigationHelper;
      if (!helper) {
        console.error('❌ [SET-LINEUP] TimeoutNavigationHelper not loaded!');
        return;
      }
      const currentUrlParams = new URLSearchParams(window.location.search);
      const currentGameId = helper.getGameId(currentUrlParams);
      const resumeFromTimeout = helper.getResumeFromTimeout(currentUrlParams);
      const params = helper.buildGameNavigationParams({
        sourceParams: currentUrlParams,
        targetQuarter: quarter,
        gameId: currentGameId,
        resumeFromTimeout: resumeFromTimeout,
        lineup: lineup,
        myTeamSide: myTeamSide
      });
      if (currentGameId) {
        params.set('game_id', currentGameId);
      } else {
        params.set('pregame', '1');
      }
      params.set('from', 'lineup');
      window.location.href = `/box-score.html?${params.toString()}`;
    });
  }
}

async function init() {
  try {
  wireLineupNavButtons();
  // ✅ PHASE 2: Validate pointers on page load
  const validationPassed = await validatePointersOnLoad();
  if (!validationPassed) {
    // Validation failed - error screen already shown, disable functionality
    const btn = document.getElementById('play-now');
    if (btn) btn.classList.add('disabled');
    return;
  }

  if (!resolveTeam()) {
    alert("Can't determine your team for this game. Please return and relaunch.");
    const btn = document.getElementById('play-now');
    if (btn) btn.classList.add('disabled');
    return;
  }

  await loadRoster();
  initRosterPanelToggle();
  await setHeader();
  setupSlots(); // Bind table drag/drop (lineup starts empty until URL restore)
  
  // Restore lineup from URL
  restoreLineupFromUrl();
  
  // ✅ FOUL OUT: Remove ineligible players from lineup AFTER restoring from URL
  // This ensures fouled-out players are removed even if they were in the URL params
  if (!exhaustedUserLineupLocked) {
    removeIneligiblePlayersFromLineup();
  }
  const enteredExhaustedLineupState = buildExhaustedUserLineupIfNeeded();
  
  // ✅ FOUL OUT FIX: Add diagnostic helper function for browser console
  window.checkFoulOutStatus = function() {
    const fouledOutPlayers = roster.filter(p => p.fouled_out || p.ineligible);
    const lineupPositions = ['PG', 'SG', 'SF', 'PF', 'C'];
    const fouledOutInLineup = lineupPositions.filter(pos => {
      const playerId = lineup[pos];
      if (!playerId) return false;
      const player = roster.find(p => {
        const pId = p._id || p.playerId || p.player_id;
        return String(pId) === String(playerId);
      });
      return player && (player.fouled_out || player.ineligible);
    });
    
    console.log('🔍 [FOUL-OUT STATUS CHECK]');
    console.log(`- Fouled-out players in roster: ${fouledOutPlayers.length}`);
    console.log(`- Fouled-out players:`, fouledOutPlayers.map(p => `${p.name} (ID: ${p._id || p.playerId || p.player_id})`));
    console.log(`- Fouled-out players in lineup: ${fouledOutInLineup.length}`);
    console.log(`- Positions with fouled-out players:`, fouledOutInLineup);
    console.log(`- Current lineup state:`, lineup);
    console.log(`- Roster players with fouled_out flag:`, roster.filter(p => p.fouled_out).map(p => p.name));
    console.log(`- Roster players with ineligible flag:`, roster.filter(p => p.ineligible).map(p => p.name));
    
    return {
      fouledOutCount: fouledOutPlayers.length,
      fouledOutPlayers: fouledOutPlayers.map(p => ({ name: p.name, id: p._id || p.playerId || p.player_id })),
      fouledOutInLineup: fouledOutInLineup,
      lineup: { ...lineup }
    };
  };
  
  await loadFtShooterLock(); // FT shooter lock state before table render
  updatePlayButton();
  refreshLineupAvailabilityDisplay();
  lockExhaustedUserLineupControls();
  if (enteredExhaustedLineupState) showExhaustedUserLineupModal();
  try {
    lineupPlaybooksModalCache = await fetchLineupPlaybooksData();
    renderLineupShotWeights(lineupPlaybooksModalCache);
  } catch (error) {
    console.error('[SET-LINEUP] Failed to load shot weights:', error);
  }
  
  // Wire up autoset button
  const autosetBtn = document.getElementById('autoset-lineup');
  if (autosetBtn) {
    autosetBtn.addEventListener('click', autosetLineup);
  }

  // Debug: surface the resolved mode + tour-gate state so we can see
  // immediately why the tutorial chrome (intro modal + attribute tour)
  // does or doesn't fire on this page load. Cheap, fires once per load.
  try {
    const introKeyPreview = gameId
      ? `fteV2TutorialLineupModalShown_${gameId}`
      : 'fteV2TutorialLineupModalShown';
    const tourKeyPreview = gameId
      ? `fteV2TutorialAttrTourShown_${gameId}`
      : 'fteV2TutorialAttrTourShown';
    console.log('[tutorial][gate]', {
      modeParam,
      isTutorial: modeParam === 'tutorial',
      gameId,
      homeTeam,
      introModalShown: (() => { try { return sessionStorage.getItem(introKeyPreview); } catch (_) { return '<denied>'; } })(),
      attrTourShown: (() => { try { return sessionStorage.getItem(tourKeyPreview); } catch (_) { return '<denied>'; } })(),
      url: typeof window !== 'undefined' ? window.location.href : null,
    });
  } catch (_) { /* non-fatal */ }

  // FTE v2 tutorial: the slots load empty (tutorial-situation no longer
  // forwards home_pg/etc.) — the user sets their own lineup as part of
  // the lesson. On first paint, show a centered Functional-modal-style
  // intro that nudges them into the task. The CTA is renamed "Return To
  // Game" here, and clicking it shows a second modal with algorithm-
  // chosen feedback before actual navigation.
  if (modeParam === 'tutorial') {
    const playBtnEl = document.getElementById('play-now');
    if (playBtnEl) playBtnEl.textContent = 'Return To Game';

    const introKey = gameId
      ? `fteV2TutorialLineupModalShown_${gameId}`
      : 'fteV2TutorialLineupModalShown';
    const alreadyShown = (() => {
      try { return sessionStorage.getItem(introKey) === '1'; } catch (_) { return false; }
    })();
    Promise.all([
      import('/js/shared/tutorialProgressThread.js'),
      alreadyShown ? Promise.resolve(null) : import('/js/shared/tutorialLineupModals.js'),
      import('/js/shared/attributeTour.js'),
    ]).then(([{ mountTutorialProgress }, lineupModals, { showAttributeTour }]) => {
      mountTutorialProgress('lineup');
      // After the intro modal dismisses, fire the attribute tour. The tour
      // has its own sessionStorage gate keyed by game_id — matches the
      // intro modal's pattern, so a fresh tutorial game = fresh tour while
      // within-tutorial navigation (set-lineup → game-plan → back) stays
      // quiet. headerRow is the roster attributes table's <thead>.
      const tourKey = gameId
        ? `fteV2TutorialAttrTourShown_${gameId}`
        : 'fteV2TutorialAttrTourShown';
      const launchAttributeTour = () => {
        const headerRow = document.querySelector('#roster-attributes-pane .roster-table thead');
        if (!headerRow) return;
        // Defer a frame so any post-intro-modal layout settles before we
        // measure the header row for Sammy positioning.
        requestAnimationFrame(() => {
          showAttributeTour({
            headerRow,
            teamName: homeTeam,
            persistKey: tourKey,
            // Dim everything around the header row instead of laying a
            // scrim on top — <thead> z-index is unreliable against a
            // full-screen overlay (early build had the header rendering
            // UNDER the dim). These are the siblings that should fade
            // back during the tour; the header row itself is absent.
            dimSelectors: [
              '.lineup-banner-strip',
              '.lineup-context-bar',
              '.lineup-roster-header-row',
              '#roster-body',
              '#roster-pos-note',
              '.roster-panel-actions',
              '.lineup-right-panel',
            ],
          });
        });
      };
      if (!alreadyShown && lineupModals) {
        try { sessionStorage.setItem(introKey, '1'); } catch (_) {}
        lineupModals.showLineupIntroModal({
          teamName: homeTeam,
          onDismiss: launchAttributeTour,
        });
      } else {
        // Re-entry path (back from game-plan, etc.). The intro modal was
        // already dismissed in this session. Try to fire the tour anyway —
        // its localStorage gate will silently no-op if already seen.
        launchAttributeTour();
      }
    }).catch((e) => console.warn('[tutorial] could not init lineup tutorial chrome:', e));
  }

  const btn = document.getElementById('play-now');
  if (btn) {
    btn.addEventListener('click', async () => {
      if (btn.classList.contains('disabled')) return;
      
      // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
      const helper = window.TimeoutNavigationHelper;
      if (!helper) {
        console.error('❌ [SET-LINEUP] TimeoutNavigationHelper not loaded!');
        return;
      }
      
      // ✅ PHASE 1.1: Read from current URL (source of truth), not stale module-level urlParams
      const currentUrlParams = new URLSearchParams(window.location.search);
      let currentGameId = currentUrlParams.get('game_id') || null;
      let resumeFromTimeout = currentUrlParams.get('resume_from_timeout') === 'true';
      const resumeFromAnchor = currentUrlParams.get('resume_from_anchor') === 'true' || currentUrlParams.get('consume_resume_anchor') === 'true';
      const modeParam = currentUrlParams.get('mode') || 'single';
      
      // ✅ CRITICAL FIX: Only force resumeFromTimeout=false for quarter breaks (quarter > 1)
      // BUT: If we're actually resuming from a timeout (URL param says true), preserve it
      if (quarter > 1 && !resumeFromTimeout) {
        resumeFromTimeout = false;
        console.warn('🔍 [DEBUG QTR BREAK] set-lineup.js - Quarter break detected (Q' + quarter + '), forcing resumeFromTimeout=false');
      } else if (quarter > 1 && resumeFromTimeout) {
        console.warn('🔍 [DEBUG TIMEOUT] set-lineup.js - Timeout resume detected (Q' + quarter + '), preserving resumeFromTimeout=true');
      }
      
      // ✅ PHASE 1.1: Ensure game_id exists before navigating (same as Game Plan / Playbooks)
      // PLAY GAME bypasses game plan; if user clicks before init-game completes, we'd navigate without game_id
      // (FTE v2 tutorial mode is NOT here — init-game runs earlier on the
      // situation page so the engine state + roster are available when this
      // page loads. By the time the user hits Play, game_id is already in URL.)
      if (!currentGameId && homeTeam && awayTeam && !resumeFromTimeout && !resumeFromAnchor && modeParam === 'single' && quarter === 1) {
        if (!initGameInProgress) {
          console.log('⏳ [SET-LINEUP] PLAY GAME: game_id not found, calling init-game...');
          initGameInProgress = true;
          try {
            const initPayload = { home_team: homeTeam, away_team: awayTeam, mode: 'single' };
            attachMatchupTeamIds(initPayload);
            if (myTeamSide) initPayload.user_team_side = myTeamSide;
            const initRes = await fetch(API_CONFIG.buildUrl('/api/init-game'), {
              method: 'POST',
              headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
              body: JSON.stringify(initPayload)
            });
            if (abortIfAccessDenied(initRes)) return;
            if (initRes.ok) {
              const initData = await initRes.json();
              currentGameId = initData.game_id;
              currentUrlParams.set('game_id', currentGameId);
              if (typeof history !== 'undefined' && history.replaceState) {
                history.replaceState(null, '', `${window.location.pathname}?${currentUrlParams.toString()}`);
              }
              console.log('✅ [SET-LINEUP] PLAY GAME: Initialized game_id:', currentGameId);
            }
          } catch (e) {
            console.warn('Could not initialize game for PLAY GAME:', e);
          } finally {
            initGameInProgress = false;
          }
        } else {
          let waitCount = 0;
          while (initGameInProgress && waitCount < 50) {
            await new Promise(r => setTimeout(r, 100));
            waitCount++;
            const u = new URLSearchParams(window.location.search);
            currentGameId = u.get('game_id');
            if (currentGameId) break;
          }
          if (!currentGameId) {
            console.error('❌ [SET-LINEUP] PLAY GAME: init-game did not complete in time');
            if (typeof window !== 'undefined' && window.alert) {
              window.alert('Game initialization is taking longer than expected. Please try again.');
            }
            return;
          }
        }
      }
      
      console.log('🔍 [DEBUG QTR BREAK] set-lineup.js - Before building params:', {
        quarter,
        gameId: currentGameId,
        resumeFromTimeout,
        allUrlParams: Object.fromEntries(currentUrlParams.entries())
      });
      
      const params = helper.buildGameNavigationParams({
        sourceParams: currentUrlParams,
        targetQuarter: quarter,
        gameId: currentGameId,
        resumeFromTimeout,
        lineup: lineup,
        myTeamSide: myTeamSide,
        clock: currentUrlParams.get('clock')
      });
      params.set('lineup_checkpoint', 'true');
      // Pass through quarter_break_from for quarter-break navigation context
      const quarterBreakFrom = currentUrlParams.get('quarter_break_from');
      if (quarterBreakFrom) params.set('quarter_break_from', quarterBreakFrom);
      if (quarterBreakFrom === 'mid_game_resume') {
        params.set('consume_resume_anchor', 'true');
        params.set('resume_from_anchor', 'true');
        params.delete('active_resume');
        console.info('[MGR-RESUME-CLIENT] lineup return from resume', {
          game_id: currentGameId,
          quarter,
          clock: currentUrlParams.get('clock'),
          resume_from_timeout: resumeFromTimeout,
          next_play: currentUrlParams.get('timeout_next_play_type'),
        });
      }

      if (rimRunnerPlayerId && myTeamSide) {
        const k = myTeamSide === 'home' ? 'home_rim_runner_player_id' : 'away_rim_runner_player_id';
        params.set(k, String(rimRunnerPlayerId));
      }
      
      console.log('🔍 [DEBUG QTR BREAK] set-lineup.js - After building params:', {
        resume_from_timeout: params.get('resume_from_timeout'),
        game_id: params.get('game_id'),
        quarter: params.get('quarter'),
        fullParams: Object.fromEntries(params.entries())
      });
      
      if (DEBUG) params.set('debug', '1');
      if (DEBUG) {
        console.debug('🔀 Redirecting to court.html (bypassing game plan)', { home: homeTeam, away: awayTeam, gameId: currentGameId });
      }
      DEBUG && console.log('[lineup] launching quarter', quarter);

      // FTE v2 tutorial: advance the server-side step to "in_game" before
      // navigation. Court.html will read resume_from_timeout from URL params
      // (added by buildGameNavigationParams below) so the engine emits the SIP
      // first turn per the timeout-resume path in BackEnd/main.py.
      if (modeParam === 'tutorial') {
        try {
          await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
            method: 'POST',
            headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ step: 'in_game' }),
          });
        } catch (e) {
          console.warn('[tutorial] could not advance to in_game step:', e);
        }
        // Force resume_from_timeout=true so the engine routes through the
        // existing SIP emission path for the first turn (state seeded by
        // apply_tutorial_initial_state in PR 1).
        params.set('resume_from_timeout', 'true');
      }

      const finalUrl = `/court.html?${params.toString()}`;
      console.log('🔍 [DEBUG QTR BREAK] set-lineup.js - Navigating to court.html:', finalUrl);
      playSound('confirm-1-lowervol.wav');
      const navigate = () => setTimeout(() => { window.location.href = finalUrl; }, 200);

      // FTE v2 tutorial: insert a feedback modal between Return To Game and
      // the actual navigation. Algorithm picks a Talent / skill-based /
      // Unconventional message based on the user's chosen starters. The
      // modal's CTA is the real navigation trigger.
      if (modeParam === 'tutorial') {
        try {
          const { showLineupFeedbackModal, pickLineupFeedbackMessage } = await import('/js/shared/tutorialLineupModals.js');
          const starters = ['PG', 'SG', 'SF', 'PF', 'C']
            .map((pos) => lineup[pos])
            .filter(Boolean)
            .map((id) => roster.find((p) => p._id === id))
            .filter(Boolean);
          const message = pickLineupFeedbackMessage(starters, roster);
          showLineupFeedbackModal({
            teamName: homeTeam,
            message,
            onConfirm: navigate,
          });
        } catch (e) {
          // If the feedback modal fails to load, don't block the user from
          // proceeding — fall through to direct navigation.
          console.warn('[tutorial] lineup feedback modal failed; proceeding:', e);
          navigate();
        }
        return;
      }

      // Non-tutorial: navigate directly.
      navigate();
    });
  }
  // Game Plan, Playbooks, Box Score wired in wireLineupNavButtons()
  } finally {
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
  }
}

// ========== PLAYER VIEW IMPLEMENTATION ==========

let currentView = 'grid'; // 'grid' or 'player'
const cardFlipState = {}; // Track flip state per player ID

// Attribute groupings for card back
const ATTR_GROUPS = {
  'OFFENSE': ['SC', 'SH'],
  'DEFENSE': ['ID', 'OD'],
  'SKILLS': ['PS', 'BH'],
  'DIRTY WORK': ['RB', 'ST'],
  'PHYSICAL': ['AG', 'ND'],
  'MIND': ['IQ', 'FT']
};

function initViewToggle() {
  // Restore saved view from sessionStorage
  const savedView = sessionStorage.getItem('lineupView');
  if (savedView === 'player') {
    currentView = 'player';
  }
  
  const toggleBtns = document.querySelectorAll('.view-toggle-btn');
  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      playSound('click-tiny.wav');
      const view = btn.dataset.view;
      switchView(view);
    });
    
    // Set active state based on current view
    if (btn.dataset.view === currentView) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Initialize view
  switchView(currentView);
}

function switchView(view) {
  currentView = view;
  sessionStorage.setItem('lineupView', view);
  
  // Update toggle buttons
  document.querySelectorAll('.view-toggle-btn').forEach(btn => {
    if (btn.dataset.view === view) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Show/hide view containers
  const gridContainer = document.getElementById('roster-table-container');
  const playerContainer = document.getElementById('player-view-container');
  
  if (view === 'grid') {
    gridContainer?.classList.add('active');
    playerContainer?.classList.remove('active');
  } else {
    gridContainer?.classList.remove('active');
    playerContainer?.classList.add('active');
    renderPlayerView();
  }
}

function renderPlayerView() {
  const container = document.querySelector('.players-grid');
  if (!container) return;
  
  container.innerHTML = '';
  
  // Sort players by their HIGHEST position rating
  const sortedPlayers = roster
    .map(p => {
      const posRatings = p.position_ratings || {};
      const entries = Object.entries(posRatings);
      
      let highestPos = null;
      let highestRating = -1;
      
      if (entries.length > 0) {
        const sorted = entries.sort((a, b) => b[1] - a[1]);
        highestPos = sorted[0][0];
        highestRating = sorted[0][1];
      }
      
      return { 
        ...p, 
        highestPos,
        highestRating 
      };
    })
    .sort((a, b) => {
      // Sort by highest rating desc
      if (b.highestRating !== a.highestRating) return b.highestRating - a.highestRating;
      // Then by name asc
      return (a.name || '').localeCompare(b.name || '');
    });
  
  sortedPlayers.forEach(player => {
    const card = createPlayerCard(player);
    container.appendChild(card);
  });
  
  // Initialize tooltips for player cards
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(container, ['.attr-label']);
  }
}

function createPlayerCard(player) {
  const playerId = getPlayerStableId(player);
  const card = document.createElement('div');
  card.className = 'player-card';
  
  // Add ineligible styling for fouled-out players
  if (player.ineligible || player.fouled_out) {
    card.classList.add('ineligible');
    card.style.backgroundColor = '#d3d3d3';  // Light grey background tint
    card.style.opacity = '0.7';
    card.style.pointerEvents = 'none';
    card.style.cursor = 'not-allowed';
  }
  if (playerId) card.dataset.playerId = playerId;
  
  // Check if selected
  const isSelected = playerId != null && Object.values(lineup).some(id => String(id) === String(playerId));
  if (isSelected) {
    card.classList.add('selected');
  }
  
  // Make draggable (only if not ineligible)
  card.draggable = !isSelected && !player.ineligible && !player.fouled_out;
  if (card.draggable) {
    card.addEventListener('dragstart', (e) => {
      if (playerId) e.dataTransfer.setData('text/plain', playerId);
    });
  }
  
  // Click to fill next slot (only if not ineligible)
  if (!player.ineligible && !player.fouled_out) {
    card.addEventListener('click', (e) => {
      // Don't trigger on flip button, position rating circle, or headshot clicks
      if (e.target.closest('.flip-btn') || 
          e.target.closest('.position-rating-circle') || 
          e.target.closest('.player-headshot-container')) {
        return;
      }
      if (!isSelected) {
        fillNextSlot(playerId);
      }
    });
  }
  
  const inner = document.createElement('div');
  inner.className = 'player-card-inner';
  
  // Front side
  const front = createCardFront(player);
  inner.appendChild(front);
  
  // Back side
  const back = createCardBack(player);
  inner.appendChild(back);
  
  card.appendChild(inner);
  
  return card;
}

function createCardFront(player) {
  const front = document.createElement('div');
  front.className = 'player-card-front';
  
  // Headshot container (clickable link to player detail)
  const headshotLink = document.createElement('a');
  applyPlayerDetailLinkBehavior(headshotLink, getPlayerStableId(player));
  headshotLink.style.display = 'block';
  headshotLink.style.textDecoration = 'none';
  
  const headshotContainer = document.createElement('div');
  headshotContainer.className = 'player-headshot-container';
  
  // Set team background image
  const teamNameNormalized = teamName.toLowerCase().replace(/\s+/g, '-');
  // Use environment-aware path
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const staticPrefix = isLocalhost ? '/static' : '';
  headshotContainer.style.backgroundImage = `url(${(typeof getTeamAssetPath === 'function' ? getTeamAssetPath(teamName, 'background') : staticPrefix + '/images/teams/general/general_background.png')})`;
  headshotContainer.style.backgroundSize = 'cover';
  headshotContainer.style.backgroundPosition = 'center';
  
  // Add energy-based border
  const ng = player.attributes?.NG ?? 1.0;
  let borderColor;
  if (ng > 0.89) borderColor = '#00aa00';      // Green
  else if (ng >= 0.8) borderColor = '#cccc00'; // Yellow
  else if (ng >= 0.7) borderColor = '#ff8800'; // Orange
  else borderColor = '#cc0000';                // Red
  
  headshotContainer.style.border = `4px solid ${borderColor}`;
  headshotContainer.style.cursor = 'pointer';
  headshotContainer.style.transition = 'transform 0.2s ease';
  
  // Add hover effect
  headshotContainer.addEventListener('mouseenter', () => {
    headshotContainer.style.transform = 'scale(1.05)';
  });
  headshotContainer.addEventListener('mouseleave', () => {
    headshotContainer.style.transform = 'scale(1)';
  });
  
  // Player image
  const img = document.createElement('img');
  img.className = 'player-headshot';
  img.src = (typeof API_CONFIG !== 'undefined' && API_CONFIG.getPlayerImageUrl)
    ? API_CONFIG.getPlayerImageUrl(getPlayerStableId(player), { size: 'card' })
    : `${staticPrefix}/images/players/${getPlayerStableId(player)}.png`;
  img.alt = player.name;
  img.onerror = () => {
    img.onerror = null;
    img.src = (typeof API_CONFIG !== 'undefined' && API_CONFIG.getGenericHeadshotUrl)
      ? API_CONFIG.getGenericHeadshotUrl({ size: 'card' })
      : `${staticPrefix}/images/players/generic_headshot.png`;
  };
  headshotContainer.appendChild(img);
  
  // Year display (top center)
  if (player.year) {
    const yearDisplay = document.createElement('div');
    yearDisplay.className = 'player-year-display';
    const yearFormatted = (typeof GOB_PlayerYear !== 'undefined' && GOB_PlayerYear.formatDisplay)
      ? GOB_PlayerYear.formatDisplay(player.year)
      : (typeof yearMap !== 'undefined' && yearMap[String(player.year).toLowerCase()]
        ? yearMap[String(player.year).toLowerCase()]
        : String(player.year).toUpperCase());
    yearDisplay.textContent = yearFormatted;
    
    // Custom colors by year
    let yearColor;
    if (yearText === 'senior') {
      yearColor = '#FFD700'; // Bright gold
    } else if (yearText === 'junior') {
      yearColor = '#c1c1c1'; // Bright silver
    } else if (yearText === 'sophomore') {
      yearColor = '#32CD32'; // Bright lime green
    } else if (yearText === 'freshman') {
      yearColor = '#FF69B4'; // Bright pink
    } else {
      yearColor = '#c1c1c1'; // Default to silver
    }
    
    yearDisplay.style.cssText = `
      position: absolute;
      top: 8px;
      left: 50%;
      transform: translateX(-50%);
      color: ${yearColor};
      opacity: 1.0;
      font-weight: 600;
      font-size: 14px;
      text-transform: capitalize;
      z-index: 10;
      pointer-events: none;
      text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    `;
    headshotContainer.appendChild(yearDisplay);
  }
  
  // Add ineligible overlay/shade for fouled-out players
  if (player.ineligible || player.fouled_out) {
    headshotContainer.style.position = 'relative';
    
    // Add overlay shade
    const overlay = document.createElement('div');
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.bottom = '0';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
    overlay.style.zIndex = '10';
    overlay.style.pointerEvents = 'none';
    headshotContainer.appendChild(overlay);
    
    // Add "FOULED OUT" label
    const label = document.createElement('div');
    label.textContent = 'FOULED OUT';
    label.style.position = 'absolute';
    label.style.top = '50%';
    label.style.left = '50%';
    label.style.transform = 'translate(-50%, -50%)';
    label.style.color = '#e74c3c';
    label.style.fontWeight = 'bold';
    label.style.fontSize = '14px';
    label.style.zIndex = '11';
    label.style.pointerEvents = 'none';
    label.style.textShadow = '0 0 4px rgba(0,0,0,0.8)';
    headshotContainer.appendChild(label);
  }
  
  headshotLink.appendChild(headshotContainer);
  front.appendChild(headshotLink);
  
  // Flip button (outside the link so it doesn't navigate)
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(getPlayerStableId(player));
  });
  front.appendChild(flipBtn);
  
  // Position rating circle (top-left, opposite flip button)
  const ratingCircle = createPositionRatingCircle(player);
  front.appendChild(ratingCircle);
  
  // Info bar
  const infoBar = document.createElement('div');
  infoBar.className = 'player-info-bar';
  
  // Left side: name and physical stats
  const leftInfo = document.createElement('div');
  leftInfo.className = 'player-info-left';
  
  const name = document.createElement('div');
  name.className = 'player-name';
  name.textContent =
    typeof formatNameWithJersey === 'function' ? formatNameWithJersey(player.jersey, player.name) : player.name;
  leftInfo.appendChild(name);
  
  const physical = document.createElement('div');
  physical.className = 'player-physical';
  physical.textContent = `${formatHeight(player.height)} ${player.weight || '--'} lbs`;
  leftInfo.appendChild(physical);
  
  infoBar.appendChild(leftInfo);
  
  // Right side: energy percentage
  const energyDisplay = document.createElement('div');
  energyDisplay.className = 'player-energy-display';
  const ngPercent = Math.round(ng * 100);
  energyDisplay.textContent = `${ngPercent}%`;
  energyDisplay.style.color = borderColor;  // Match border color
  energyDisplay.style.fontWeight = 'bold';
  energyDisplay.style.fontSize = '18px';
  infoBar.appendChild(energyDisplay);
  
  front.appendChild(infoBar);
  
  return front;
}

function createPositionRatingCircle(player) {
  const circle = document.createElement('div');
  circle.className = 'position-rating-circle';
  
  const posRatings = player.position_ratings || {};
  const entries = Object.entries(posRatings)
    .sort((a, b) => b[1] - a[1]); // Sort by rating desc
  
  if (entries.length === 0) {
    circle.style.display = 'none';
    return circle;
  }
  
  // Use player's highest position rating (already calculated in renderPlayerView)
  const topRating = player.highestRating ?? entries[0][1];
  
  // Display only the highest rating integer value
  circle.textContent = formatRtDisplay(topRating);
  circle.setAttribute('aria-label', 'Position rating');
  
  // Create tooltip content with all 5 position ratings in descending order
  const tooltipContent = entries
    .map(([pos, rating]) => `${pos}: ${formatRtDisplay(rating)}`)
    .join('\n');
  
  // Setup tooltip on hover
  setupPositionRatingTooltip(circle, tooltipContent);
  
  return circle;
}

function setupPositionRatingTooltip(element, tooltipText) {
  let tooltip = null;
  
  element.addEventListener('mouseenter', (e) => {
    // Create tooltip element
    tooltip = document.createElement('div');
    tooltip.className = 'position-rating-tooltip';
    tooltip.style.cssText = `
      position: absolute;
      padding: 8px 12px;
      background: rgba(0, 0, 0, 0.95);
      color: #fff;
      font-size: 12px;
      white-space: pre-line;
      border-radius: 6px;
      pointer-events: none;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.2s, visibility 0.2s;
      z-index: 10000;
      font-family: 'Inter', sans-serif;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
      line-height: 1.6;
      text-align: left;
    `;
    tooltip.textContent = tooltipText;
    document.body.appendChild(tooltip);
    
    // Position tooltip near the circle
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    // Position to the right of the circle
    tooltip.style.left = `${rect.right + 8}px`;
    tooltip.style.top = `${rect.top + rect.height / 2 - tooltipRect.height / 2}px`;
    tooltip.style.opacity = '0';
    tooltip.style.visibility = 'visible';
    
    // Force reflow, then show
    tooltip.offsetHeight;
    tooltip.style.opacity = '1';
  });
  
  element.addEventListener('mouseleave', () => {
    if (tooltip) {
      tooltip.style.opacity = '0';
      tooltip.style.visibility = 'hidden';
      // Remove tooltip after transition
      setTimeout(() => {
        if (tooltip && tooltip.parentNode) {
          tooltip.parentNode.removeChild(tooltip);
        }
        tooltip = null;
      }, 200);
    }
  });
  
  element.addEventListener('mousemove', (e) => {
    if (tooltip && tooltip.style.visibility === 'visible') {
      const rect = element.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      
      // Update position to stay near circle
      tooltip.style.left = `${rect.right + 8}px`;
      tooltip.style.top = `${rect.top + rect.height / 2 - tooltipRect.height / 2}px`;
    }
  });
}

function createCardBack(player) {
  const back = document.createElement('div');
  back.className = 'player-card-back';
  
  // Flip button (on back) - exactly like front button
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card back');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(getPlayerStableId(player));
  });
  back.appendChild(flipBtn);
  
  // Two-column container
  const columnsContainer = document.createElement('div');
  columnsContainer.className = 'attr-columns-container';
  
  // Column 1
  const column1 = document.createElement('div');
  column1.className = 'attr-column';
  
  // Column 2
  const column2 = document.createElement('div');
  column2.className = 'attr-column';
  
  // Attribute sections - use anchor attributes (not energy-scaled)
  const attrs = player.attributes || {};
  
  // Helper function to create an attribute pill
  function createAttrPill(key, attrs) {
    const pill = document.createElement('div');
    pill.className = 'attr-pill';
    
    const label = document.createElement('span');
    label.className = 'attr-label';
    label.textContent = key;
    // Add tooltip for attribute abbreviation
    if (typeof addTooltip !== 'undefined') {
      addTooltip(label, key);
    }
    pill.appendChild(label);
    
    const value = document.createElement('span');
    value.className = 'attr-value';
    // Use anchor attribute (base value, not energy-scaled)
    const rawVal = attrs[`anchor_${key}`] ?? attrs[key];
    const displayVal = rawVal != null ? Math.floor(rawVal / 10) : '--';
    value.textContent = displayVal;
    
    // Set gold bar fill percentage (0-10 scale, max at 100%)
    if (displayVal !== '--' && typeof getAttrColor === 'function') {
      const fillPercentage = Math.min(displayVal * 10, 100);
      pill.style.setProperty('--attr-fill', `${fillPercentage}%`);
      pill.style.setProperty('--attr-bar-color', getAttrColor(Math.ceil(Number(rawVal) / 10)));
    }
    
    pill.appendChild(value);
    return pill;
  }
  
  // Helper function to create a section with header and pills
  function createSection(headerText, attrKeys) {
    const section = document.createElement('div');
    section.className = 'attr-section';
    
    const title = document.createElement('div');
    title.className = 'attr-section-title';
    title.textContent = headerText;
    section.appendChild(title);
    
    attrKeys.forEach(key => {
      const pill = createAttrPill(key, attrs);
      section.appendChild(pill);
    });
    
    return section;
  }
  
  // Column 1: Offense, Skills, Physical
  column1.appendChild(createSection('Offense', ['SC', 'SH']));
  column1.appendChild(createSection('Skills', ['PS', 'BH']));
  column1.appendChild(createSection('Physical', ['AG', 'ND']));
  
  // Column 2: Defense, Dirty Work, Mind
  column2.appendChild(createSection('Defense', ['ID', 'OD']));
  column2.appendChild(createSection('Dirty Work', ['RB', 'ST']));
  column2.appendChild(createSection('Mind', ['IQ', 'FT']));
  
  columnsContainer.appendChild(column1);
  columnsContainer.appendChild(column2);
  back.appendChild(columnsContainer);
  
  return back;
}

function toggleCardFlip(playerId) {
  const card = document.querySelector(`.player-card[data-player-id="${playerId}"]`);
  if (!card) return;
  
  card.classList.toggle('flipped');
  cardFlipState[playerId] = card.classList.contains('flipped');
}

function assignToSlot(pos, playerId) {
  playerId = String(playerId);
  // Check if slot is already filled
  if (lineup[pos]) {
    showToast('Slot already filled');
    return false;
  }
  
  // Check if player is already in lineup
  if (Object.values(lineup).some(id => String(id) === String(playerId))) {
    showToast('Player already in lineup');
    return false;
  }
  
  const player = playerMap[playerId];
  if (!player) return false;
  
  // Check if player is ineligible (fouled out)
  if (player.ineligible || player.fouled_out) {
    showToast(`${player.name} has fouled out and cannot play`);
    return false;
  }
  
  // Update lineup data
  lineup[pos] = playerId;
  updateAllSlotDisplays();
  return true;
}

function getHighestOpenSlotPosition() {
  return LINEUP_POSITIONS.find(pos => !lineup[pos]) || null;
}

function fillNextSlot(playerId) {
  const player = playerMap[playerId];
  
  // Check if player is ineligible (fouled out)
  if (player && (player.ineligible || player.fouled_out)) {
    showToast(`${player.name} has fouled out and cannot play`);
    return false;
  }

  const openPos = getHighestOpenSlotPosition();
  if (openPos) {
    return assignToSlot(openPos, playerId);
  }

  showToast('All positions filled');
  return false;
}

function setupSlotDragAndDrop() {
  // Cards removed; table DnD is bound in bindRosterTableEvents().
}

function updateAllSlots() {
  updateAllSlotDisplays();
}

// D&D on-screen debug overlay
const DND_DEBUG = false;
function ensureDndOverlay() {
  if (!DND_DEBUG) return null;
  let box = document.getElementById('dnd-overlay');
  if (!box) {
    box = document.createElement('div');
    box.id = 'dnd-overlay';
    box.style.position = 'fixed';
    box.style.right = '8px';
    box.style.bottom = '8px';
    box.style.width = '360px';
    box.style.maxHeight = '40vh';
    box.style.overflowY = 'auto';
    box.style.background = 'rgba(0,0,0,0.75)';
    box.style.color = '#fff';
    box.style.font = '12px/1.4 Inter, system-ui, sans-serif';
    box.style.padding = '8px';
    box.style.borderRadius = '6px';
    box.style.zIndex = '99999';
    box.style.boxShadow = '0 2px 10px rgba(0,0,0,0.4)';
    const title = document.createElement('div');
    title.textContent = 'D&D Debug';
    title.style.fontWeight = '700';
    title.style.marginBottom = '6px';
    box.appendChild(title);
    const list = document.createElement('div');
    list.id = 'dnd-overlay-list';
    box.appendChild(list);
    document.body.appendChild(box);
  }
  return box;
}
function dndLog(label, data) {
  if (!DND_DEBUG) return;
  const box = ensureDndOverlay();
  if (!box) return;
  const list = document.getElementById('dnd-overlay-list');
  if (!list) return;
  const row = document.createElement('div');
  row.style.whiteSpace = 'pre-wrap';
  row.style.margin = '2px 0';
  const payload = data ? ` ${JSON.stringify(data)}` : '';
  row.textContent = `${label}:${payload}`;
  list.appendChild(row);
  // Keep last 20 entries
  while (list.childNodes.length > 20) list.removeChild(list.firstChild);
}

window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    window.location.reload();
  }
});

document.addEventListener('DOMContentLoaded', async () => {
  // Resume often lands here before court. Hydrate once via FCC payload when possible.
  let redirected = false;
  if (franchiseId && weekParam) {
    redirected = await redirectIfFranchiseGameplayAlreadyCommitted(); // hydrates from FCC fetch
  } else if (franchiseId && typeof ensureTeamBuilderVisualHydratedFromFranchise === 'function') {
    try {
      await ensureTeamBuilderVisualHydratedFromFranchise(franchiseId);
    } catch (e) { /* non-fatal */ }
  }
  if (redirected) return;
  init();
  
  // Initialize tooltips for table headers (th elements only)
  // Use a small delay to ensure thead is fully rendered
  setTimeout(() => {
    if (typeof initAttributeTooltips !== 'undefined') {
      const thead = document.querySelector('#roster-attributes-pane .roster-table thead');
      if (thead) {
        // Include [data-attr] for explicitly keyed attribute headers such as RT.
        initAttributeTooltips(thead, ['th', '[data-attr]']);
      } else {
        console.warn('[TOOLTIP] thead element not found');
      }
    }
  }, 100);
  
  setupSlotDragAndDrop();
});
