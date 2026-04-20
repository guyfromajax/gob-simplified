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
let myTeamSide = urlParams.get('my_team');
const userTeamIdParam = window.StateTelemetry ? window.StateTelemetry.logUrlRead('user_team_id', urlParams.get('user_team_id')) : urlParams.get('user_team_id');
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
  const isNewMatchup = storedHome && storedAway && (storedHome !== homeTeam || storedAway !== awayTeam);
  
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
    }
  } else {
    // Teams match, update stored teams
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_home', homeTeam || '');
      localStorage.setItem('game_away', awayTeam || '');
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
];

function getRT(player) {
  const ratings = Object.values(player.position_ratings || {});
  return ratings.length ? Math.max(...ratings) : -Infinity;
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
  const numeric = Number(value || 0);
  if (numeric >= 67) return 'is-high';
  if (numeric >= 34) return 'is-mid';
  return 'is-low';
}

function getLineupPlaybookUrl() {
  const params = new URLSearchParams();
  params.set('mode', modeParam || 'single');
  if (userTeamIdParam) params.set('team_id', userTeamIdParam);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (tournamentId) params.set('tournament_id', tournamentId);
  const currentGameId = new URLSearchParams(window.location.search).get('game_id');
  if (currentGameId) params.set('game_id', currentGameId);
  return `${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`;
}

async function fetchLineupPlaybooksData() {
  const response = await fetch(getLineupPlaybookUrl(), { headers: API_CONFIG.getAuthHeaders() });
  if (abortIfAccessDenied(response)) return null;
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function buildLineupPlaybookItems(data, key) {
  const percentages = data?.simple_playbook_percentages || data?.playbook_percentages || {};
  let items = [];
  if (key === 'motion') {
    items = (data?.motion || []).map((play) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: Number(percentages.motion?.[play?.play_id] || 0),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
    }));
  } else if (key === 'set_plays') {
    items = (data?.set_plays || []).map((play) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: Number(percentages.set_plays?.[play?.play_id] || 0),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
    }));
  } else if (key === 'man_defense') {
    items = (data?.man_defense_rows || [])
      .filter((row) => row?.is_active !== false)
      .map((row) => ({
        id: String(row?.id || ''),
        name: row?.name || 'Unknown',
        percentage: Number(percentages.man_defense?.[row?.id] || 0),
        effectiveness: Number(row?.effectiveness || 0),
        top_scorer: row?.top_scorer || '',
      }));
  } else if (key === 'zone_defense') {
    items = (data?.zone_defense_rows || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: Number(percentages.zone_defense?.[row?.id] || 0),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || '',
    }));
  } else if (key === 'fast_breaks') {
    items = (data?.fast_breaks || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: Number(percentages.fast_breaks?.[row?.id] || 0),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || '',
    }));
  }

  return items
    .filter((item) => Number(item.percentage || 0) > 0)
    .sort((a, b) => Number(b.percentage || 0) - Number(a.percentage || 0) || String(a.name).localeCompare(String(b.name)));
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
              <div class="lineup-playbook-card-eff ${getLineupPlaybookEffClass(item.effectiveness)}">${escapeLineupPlaybookHtml(`EFF: ${Number(item.effectiveness || 0)}`)}</div>
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
  const shouldInitGame = !gameId && homeTeam && awayTeam && !resumeFromTimeout && !initGameInProgress;
  
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
  
  // If there's an active game, fetch current player energy levels
  // Pass actual quarter from URL params to ensure correct stats loading (not hardcoded quarter=1)
  // Backend detects new game scenarios when quarter=1 is requested but saved game is Q2+
  if (gameId) {
    console.log("Loading current player energy from game:", gameId);
    try {
        // ✅ HYBRID APPROACH: Use source=db to ensure fresh data from database
        const gameRes = await fetch(`${API_CONFIG.buildUrl(`/api/game/${gameId}`)}?quarter=${quarter}&source=db`, { headers: API_CONFIG.getAuthHeaders() });
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
            
            // Attributes: EM and MO
            if (gp.attributes) {
              rosterPlayer.attributes.EM = gp.attributes.EM ?? rosterPlayer.attributes.EM ?? 50;
              rosterPlayer.attributes.MO = gp.attributes.MO ?? rosterPlayer.attributes.MO ?? 0;
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

// Store roster data for sorting
let rosterDataForSorting = [];
let currentSortColumn = 'RT';
let currentSortDirection = 'desc'; // 'desc' or 'asc'

function renderRoster() {
  const tbody = document.getElementById('roster-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  // Calculate RT for each player and store for sorting
  rosterDataForSorting = roster.map(p => {
    const posRatings = p.position_ratings || {};
    const rtValues = Object.values(posRatings);
    const highestRT = rtValues.length > 0 ? Math.max(...rtValues) : -Infinity;
    return { ...p, highestRT };
  });
  
  // Default sort by RT (descending)
  if (currentSortColumn === 'RT' && currentSortDirection === 'desc') {
    rosterDataForSorting.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));
  }
  
  // ✅ PERFORMANCE FIX: Use DocumentFragment to batch DOM updates (single reflow)
  const fragment = document.createDocumentFragment();

  function getEnergyClass(ngValue) {
    const percent = Math.round((ngValue ?? 1.0) * 100);
    if (percent >= 90) return 'high';
    if (percent >= 80) return 'medium';
    if (percent >= 70) return 'low';
    return 'critical';
  }
  
  rosterDataForSorting.forEach(p => {
    const tr = document.createElement('tr');
    tr.draggable = !p.ineligible;  // Disable drag for ineligible players
    tr.dataset.playerId = p._id;
    if (p.ineligible || p.fouled_out) {
      tr.classList.add('ineligible');  // Add class for styling
      tr.style.backgroundColor = '#d3d3d3';  // Light grey background tint
      tr.style.opacity = '0.7';  // Slight opacity reduction
      tr.style.pointerEvents = 'none';  // Disable interactions
      tr.style.cursor = 'not-allowed';  // Show not-allowed cursor
    }
    tr.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', p._id);
    });

    const posRatings = p.position_ratings || {};
    let bestPos = '--';
    let rt = '--';
    const entries = Object.entries(posRatings);
    if (entries.length) {
      const [pos, rating] = entries.reduce((a, b) => b[1] > a[1] ? b : a);
      bestPos = pos;
      rt = rating;
    }
    // Use anchor attributes (don't show energy-scaled values)
    const anchorAttrs = p.attributes || {};

    const displayPlayerName =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    const ngValue = anchorAttrs.NG ?? 1.0;
    const weightValue = p.weight != null && p.weight !== '' ? p.weight : '--';
    const cells = [
      displayPlayerName,
      bestPos,
      formatHeight(p.height),
      weightValue,
      Math.floor((anchorAttrs.anchor_SC ?? anchorAttrs.SC ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_SH ?? anchorAttrs.SH ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_ID ?? anchorAttrs.ID ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_OD ?? anchorAttrs.OD ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_PS ?? anchorAttrs.PS ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_BH ?? anchorAttrs.BH ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_RB ?? anchorAttrs.RB ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_ST ?? anchorAttrs.ST ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_AG ?? anchorAttrs.AG ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_ND ?? anchorAttrs.ND ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_IQ ?? anchorAttrs.IQ ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_FT ?? anchorAttrs.FT ?? 0) / 10),
      `${Math.round(ngValue * 100)}%`
    ];
    const classes = ['', '', 'ht', 'wt', '', '', '', '', '', '', '', '', '', '', '', '', `ng ${getEnergyClass(ngValue)}`];

    cells.forEach((val, idx) => {
      const td = document.createElement('td');
      if (idx === 0) {
        td.className = 'player-name-cell';
        const wrap = document.createElement('div');
        wrap.className = 'player-name-wrap';
        const link = document.createElement('a');
        applyPlayerDetailLinkBehavior(link, p._id);
        link.textContent = val ?? '--';
        link.className = 'player-name-link';
        link.style.textDecoration = 'none';
        link.addEventListener('mouseenter', () => {
          link.style.textDecoration = 'underline';
        });
        link.addEventListener('mouseleave', () => {
          link.style.textDecoration = 'none';
        });
        const rtSpan = document.createElement('span');
        rtSpan.className = 'inline-rt';
        rtSpan.textContent = rt ?? '--';
        wrap.appendChild(link);
        wrap.appendChild(rtSpan);
        td.appendChild(wrap);
      } else {
        td.textContent = val ?? '--';
      }
      if (classes[idx]) td.className = classes[idx];
      tr.appendChild(td);
    });

    // ✅ PERFORMANCE FIX: Append to fragment instead of tbody (batched update)
    fragment.appendChild(tr);
  });
  
  // ✅ PERFORMANCE FIX: Single DOM update (triggers one reflow instead of N)
  tbody.appendChild(fragment);
  
  // Add click handlers to sortable headers
  const sortableHeaders = document.querySelectorAll('.roster-table thead th');
  sortableHeaders.forEach((header, index) => {
    // Remove existing listeners
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const columnNames = ['Player Name', 'Pos', 'HT', 'WT', 'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG'];
      const columnName = columnNames[index];
      sortRoster(columnName);
    });
  });
  
  // Note: Tooltips for th headers are initialized in DOMContentLoaded
  // We don't need to initialize tooltips for td elements (they contain values, not abbreviations)
}

function sortRoster(columnName) {
  // Toggle sort direction if clicking the same column
  if (currentSortColumn === columnName) {
    currentSortDirection = currentSortDirection === 'desc' ? 'asc' : 'desc';
  } else {
    currentSortColumn = columnName;
    currentSortDirection = 'desc'; // Default to descending
  }
  
  const columnMap = {
    'Player Name': 'name',
    'Pos': 'pos',
    'HT': 'height',
    'WT': 'weight',
    'SC': 'SC',
    'SH': 'SH',
    'ID': 'ID',
    'OD': 'OD',
    'PS': 'PS',
    'BH': 'BH',
    'RB': 'RB',
    'ST': 'ST',
    'AG': 'AG',
    'ND': 'ND',
    'IQ': 'IQ',
    'FT': 'FT',
    'NG': 'NG',
    'RT': 'RT'
  };
  
  const dataKey = columnMap[columnName] || columnName;
  
  rosterDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (dataKey === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return currentSortDirection === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (dataKey === 'RT') {
      val1 = a.highestRT ?? -Infinity;
      val2 = b.highestRT ?? -Infinity;
    } else if (dataKey === 'pos') {
      const posOrder = ['PG', 'SG', 'SF', 'PF', 'C'];
      const posRatingsA = a.position_ratings || {};
      const posRatingsB = b.position_ratings || {};
      const entriesA = Object.entries(posRatingsA);
      const entriesB = Object.entries(posRatingsB);
      const bestA = entriesA.length ? entriesA.reduce((a, b) => b[1] > a[1] ? b : a)[0] : '';
      const bestB = entriesB.length ? entriesB.reduce((a, b) => b[1] > a[1] ? b : a)[0] : '';
      val1 = posOrder.indexOf(bestA);
      val2 = posOrder.indexOf(bestB);
    } else if (dataKey === 'height') {
      // Parse height (e.g., "6'8\"")
      const parseHeight = (h) => {
        if (!h || h === '--') return 0;
        const match = h.match(/(\d+)'(\d+)"/);
        return match ? parseInt(match[1]) * 12 + parseInt(match[2]) : 0;
      };
      val1 = parseHeight(a.height);
      val2 = parseHeight(b.height);
    } else if (dataKey === 'weight') {
      val1 = parseInt(a.weight) || 0;
      val2 = parseInt(b.weight) || 0;
    } else if (dataKey === 'NG') {
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      val1 = attrsA.NG ?? 1.0;
      val2 = attrsB.NG ?? 1.0;
    } else {
      // Attribute columns (SC, SH, ID, etc.)
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      const rawValA = attrsA[`anchor_${dataKey}`] ?? attrsA[dataKey] ?? 0;
      const rawValB = attrsB[`anchor_${dataKey}`] ?? attrsB[dataKey] ?? 0;
      val1 = Math.floor(rawValA / 10);
      val2 = Math.floor(rawValB / 10);
    }
    
    if (currentSortDirection === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  renderRoster();
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
    const rawStats = p.stats || {};
    const gameStats = rawStats.game || rawStats;
    return {
      _id: p._id,
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
  document.querySelectorAll('.slot').forEach(slot => clearSlot(slot));

  if (!roster.length || roster.length < 5) {
    showToast('Roster not loaded yet');
    return;
  }

  try {
    const payload = {
      players: rosterRowsForAutosetApi(),
      game_state: buildAutosetGameState(),
      team_chemistry: rosterTeamChemistry,
    };
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
    updateAllSlotDisplays();
    updatePlayButton();
    setupSlotDragAndDrop();
    showToast('Lineup auto-generated!');
  } catch (e) {
    console.error('[autosetLineup]', e);
    showToast('Autoset failed');
  }
}

function updateSlotDisplay(slot) {
  const pos = slot.dataset.pos;
  const playerId = lineup[pos];
  const remove = slot.querySelector('.remove');
  const slotContent = slot.querySelector('.slot-content');
  
  if (playerId && playerMap[playerId]) {
    const player = playerMap[playerId];
    const rating = player.position_ratings?.[pos] ?? '--';
    
    // Get energy (same pattern as energy - check attributes first, then fallback)
    const energy = player.attributes?.NG ?? player.NG ?? 1.0;
    const energyPercent = Math.round(energy * 100);
    
    // Get stats - handle both flat (game stats) and nested (season stats) structures
    // Game stats are already flattened at loadRoster line 211: rosterPlayer.stats = gp.stats?.game || gp.stats || {}
    // Initial roster stats are nested: stats.season.PTS (from API line 1317)
    const rawStats = player.stats || {};
    const stats = rawStats.game || rawStats.season || rawStats || {};
    
    // Get all stats with fallbacks (same pattern as energy)
    const points = stats.PTS || 0;
    // REB (TREB) is the total rebounds - use it if available, otherwise calculate from OREB + DREB
    const rebounds = stats.REB || ((stats.OREB || 0) + (stats.DREB || 0));
    const assists = stats.AST || 0;
    const defA = stats.DEF_A || 0;
    const defS = stats.DEF_S || 0;
    const defPct = defA > 0 ? Math.round((defS / defA) * 100) : 0;
    const fouls = stats.F || 0;
    
    // Get emotion (EM) - same pattern as energy: check attributes first, then fallback
    const em = player.attributes?.EM ?? player.EM ?? 50;
    let emoji = '😐'; // Default straight face
    if (em >= 80) emoji = '😎';        // Sunglasses
    else if (em >= 60) emoji = '😊';   // Big smile
    else if (em >= 40) emoji = '😐';   // Straight face
    else if (em >= 20) emoji = '😕';   // Slight frown
    else emoji = '😡';                 // Angry face
    
    // Get momentum (MO) - same pattern as energy: check attributes first, then fallback
    const momentum = player.attributes?.MO ?? player.MO ?? 0;
    const moValue = typeof momentum === 'number' ? momentum : 0;
    
    // ✅ UNIFIED: Use same thresholds as Player Grid (70/80/90%) — green from 90%, yellow 80–89%
    // Determine energy color class
    let energyClass = 'high';
    if (energyPercent < 70) energyClass = 'critical';
    else if (energyPercent < 80) energyClass = 'low';
    else if (energyPercent < 90) energyClass = 'medium';
    
    // Calculate momentum bar widths
    let leftWidth = '0%';
    let rightWidth = '0%';
    if (moValue < 0) {
      // Negative momentum: fill left side with red
      const fillPercent = Math.min(100, Math.abs(moValue) / 10 * 100); // -10 = 100%, -5 = 50%
      leftWidth = `${fillPercent}%`;
    } else if (moValue > 0) {
      // Positive momentum: fill right side with green
      const fillPercent = Math.min(100, moValue / 10 * 100); // +10 = 100%, +5 = 50%
      rightWidth = `${fillPercent}%`;
    }
    
    const imgBase = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/images/players/') : ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? '/static/images/players/' : '/images/players/');
    const genericImg = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/images/players/generic_headshot.png') : ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? '/static/images/players/generic_headshot.png' : '/images/players/generic_headshot.png');
    const slotDisplayName =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(player.jersey, player.name) : player.name;
    // Build slot content HTML
    slotContent.innerHTML = `
      <div class="player-image-container">
        <img class="player-image" src="${imgBase}${playerId}.png" 
             onerror="this.src='${genericImg}'" alt="${player.name}">
      </div>
      <div class="slot-info">
        <div class="slot-row-1">
          <div class="player-name">${slotDisplayName}</div>
          <div class="player-rating">RT: ${rating}</div>
        </div>
        <div class="slot-row-2">
          <div class="slot-stat"><span class="slot-stat-label">PTS</span><span class="player-points">${points}</span></div>
          <div class="slot-stat"><span class="slot-stat-label">REB</span><span class="player-rebounds">${rebounds}</span></div>
          <div class="slot-stat"><span class="slot-stat-label">AST</span><span class="player-assists">${assists}</span></div>
          <div class="slot-stat"><span class="slot-stat-label">DEF%</span><span class="player-def-pct">${defPct}%</span></div>
          <div class="slot-stat slot-stat-momentum">
            <span class="slot-stat-label">MO</span>
            <div class="player-momentum">
              <div class="momentum-bar-container">
                <div class="momentum-bar-left" style="width: ${leftWidth}"></div>
                <div class="momentum-bar-center"></div>
                <div class="momentum-bar-right" style="width: ${rightWidth}"></div>
              </div>
            </div>
          </div>
          <div class="slot-stat"><span class="slot-stat-label">F</span><span class="player-fouls${fouls >= 3 ? ' danger' : ''}">${fouls}</span></div>
          <div class="slot-stat"><span class="slot-stat-label">ENG</span><span class="player-energy ${energyClass}">${energyPercent}%</span></div>
        </div>
      </div>
    `;
    
    slotContent.classList.remove('empty');
    
    // Show remove button
    if (remove) {
      remove.hidden = false;
    }
    
    slot.classList.add('filled');
    slot.draggable = true;
    slot.setAttribute('draggable', 'true');
  } else {
    // Empty slot
    slotContent.innerHTML = '<span class="slot-empty-copy">Drag a player here</span>';
    slotContent.classList.add('empty');
    
    if (remove) {
      remove.hidden = true;
    }
    
    slot.classList.remove('filled');
    slot.draggable = false;
    slot.setAttribute('draggable', 'false');
  }
}

/** Clear Rim Runner if that player is no longer in the lineup */
function normalizeRimRunnerSelection() {
  if (rimRunnerPlayerId == null) return;
  const inLineup = Object.values(lineup).some((id) => String(id) === String(rimRunnerPlayerId));
  if (!inLineup) {
    rimRunnerPlayerId = null;
  }
}

function updateAllSlotDisplays() {
  normalizeRimRunnerSelection();
  document.querySelectorAll('.slot').forEach(slot => {
    updateSlotDisplay(slot);
  });
}

function clearSlot(slot) {
  const pos = slot.dataset.pos;
  const removedId = lineup[pos];
  delete lineup[pos];
  if (removedId != null && rimRunnerPlayerId != null && String(rimRunnerPlayerId) === String(removedId)) {
    rimRunnerPlayerId = null;
  }
  updateSlotDisplay(slot);
  updatePlayButton();
  
  // Re-render views to update selection state
  if (currentView === 'player') {
    renderPlayerView();
  } else {
    renderRoster();
  }
}

function setupSlots() {
  document.querySelectorAll('.slot').forEach(slot => {
    clearSlot(slot);
  });
  
  const slotsContainer = document.getElementById('slots');
  if (!slotsContainer) return;

  // Delegated dragstart on container
  slotsContainer.addEventListener('dragstart', (e) => {
    const slot = e.target.closest('.slot');
    if (!slot) return;
    const pos = slot.dataset.pos;
    const playerId = lineup[pos];
    if (playerId) {
      console.log('[DND] dragstart', { pos, playerId });
      dndLog('[DND] dragstart', { pos, playerId });
      e.dataTransfer.setData('text/plain', playerId);
      e.dataTransfer.setData('application/x-slot-pos', pos);
      e.dataTransfer.effectAllowed = 'move';
    } else {
      e.preventDefault();
    }
  });

  // Allow drops on slots
  slotsContainer.addEventListener('dragover', (e) => {
    if (e.target.closest('.slot')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }
  });

  slotsContainer.addEventListener('drop', (e) => {
    const slot = e.target.closest('.slot');
    if (!slot) return;
    e.preventDefault();

    const draggedPlayerId = e.dataTransfer.getData('text/plain');
    const dropPos = slot.dataset.pos;
    console.log('[DND] drop start', { draggedPlayerId, dropPos, lineup: { ...lineup } });
    dndLog('[DND] drop start', { draggedPlayerId, dropPos, lineup: { ...lineup } });
    if (!draggedPlayerId) return;

    // Infer source slot from lineup
    let sourcePos = null;
    for (const [p, id] of Object.entries(lineup)) {
      if (id === draggedPlayerId) { sourcePos = p; break; }
    }

    const existingAtDrop = lineup[dropPos] || null;
    console.log('[DND] resolved', { sourcePos, existingAtDrop });
    dndLog('[DND] resolved', { sourcePos, existingAtDrop });

    // Swap/move logic
    if (sourcePos && existingAtDrop) {
      lineup[sourcePos] = existingAtDrop;
    } else if (sourcePos && !existingAtDrop) {
      delete lineup[sourcePos];
    } else if (!sourcePos) {
      // Ensure uniqueness if dragged from roster
      for (const p of Object.keys(lineup)) {
        if (lineup[p] === draggedPlayerId) delete lineup[p];
      }
    }

    lineup[dropPos] = draggedPlayerId;
    console.log('[DND] drop end', { lineup: { ...lineup } });
    dndLog('[DND] drop end', { lineup: { ...lineup } });

    updateAllSlotDisplays();
    updatePlayButton();
    playSound('click-soft.mp3');

    if (currentView === 'player') {
      renderPlayerView();
    } else {
      renderRoster();
    }
  });
}

function resolveTeam() {
  if (myTeamSide === 'home' || myTeamSide === 'away') {
    teamName = myTeamSide === 'away' ? awayTeam : homeTeam;
    return !!teamName;
  }
  // ✅ PHASE 2.4: Removed localStorage fallback - user_team_id must come from URL
  // For franchise/tournament mode, user_team_id should be in URL
  // For single game mode, my_team ('home' or 'away') should be in URL
  const storedId = userTeamIdParam;
  if (storedId) {
    if (storedId === homeId || storedId === homeTeam) {
      myTeamSide = 'home';
      teamName = homeTeam;
      return true;
    }
    if (storedId === awayId || storedId === awayTeam) {
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

  const userTeamName = teamName;
  const opponentTeamName = myTeamSide === 'home' ? awayTeam : homeTeam;

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
    ? getTeamAssetPath(teamName, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  if (banner && bannerFallback) {
    banner.src = bannerSrc;
    banner.alt = `${teamName} banner`;
    banner.hidden = false;
    bannerFallback.hidden = true;
    banner.onerror = () => {
      banner.hidden = true;
      bannerFallback.hidden = false;
    };
  }

  const isPregame = !(gameId && (resumeFromTimeout || currentQuarter > 1 || userTeamScore > 0 || opponentTeamScore > 0));
  scoreboardEl?.classList.toggle('is-pregame', isPregame);
  const displayUserTeamName = String(typeof formatTeamName === 'function' ? formatTeamName(userTeamName || 'Home') : (userTeamName || 'Home')).toUpperCase();
  const displayOpponentTeamName = String(typeof formatTeamName === 'function' ? formatTeamName(opponentTeamName || 'Away') : (opponentTeamName || 'Away')).toUpperCase();
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
      lineup[pos] = null;
      removedCount++;
      
      // Clear the slot display
      const slot = document.querySelector(`.slot[data-pos="${pos}"]`);
      if (slot) {
        const slotContent = slot.querySelector('.slot-content');
        if (slotContent) {
          slotContent.innerHTML = '';
          slotContent.classList.add('empty');
          slot.classList.remove('filled');
          slot.draggable = false;
          const removeBtn = slot.querySelector('.remove');
          if (removeBtn) removeBtn.hidden = true;
        }
        console.log(`✅ [FOUL-OUT] Cleared ${pos} slot display`);
      } else {
        console.warn(`⚠️ [FOUL-OUT] Slot element not found for position ${pos}`);
      }
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
  await setHeader();
  setupSlots(); // Setup slot event handlers (this clears slots/lineup)
  
  // Restore lineup from URL AFTER setupSlots (which clears the lineup)
  restoreLineupFromUrl();
  
  // ✅ FOUL OUT: Remove ineligible players from lineup AFTER restoring from URL
  // This ensures fouled-out players are removed even if they were in the URL params
  removeIneligiblePlayersFromLineup();
  
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
  
  updateAllSlotDisplays(); // Display restored lineup in slots
  updatePlayButton(); // Update play button state based on restored lineup
  
  // Wire up autoset button
  const autosetBtn = document.getElementById('autoset-lineup');
  if (autosetBtn) {
    autosetBtn.addEventListener('click', autosetLineup);
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
      if (!currentGameId && homeTeam && awayTeam && !resumeFromTimeout && modeParam === 'single' && quarter === 1) {
        if (!initGameInProgress) {
          console.log('⏳ [SET-LINEUP] PLAY GAME: game_id not found, calling init-game...');
          initGameInProgress = true;
          try {
            const initPayload = { home_team: homeTeam, away_team: awayTeam, mode: 'single' };
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
      // Pass through quarter_break_from so court knows whether to play airhorn (play_quarter only)
      const quarterBreakFrom = currentUrlParams.get('quarter_break_from');
      if (quarterBreakFrom) params.set('quarter_break_from', quarterBreakFrom);

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
      const finalUrl = `/court.html?${params.toString()}`;
      console.log('🔍 [DEBUG QTR BREAK] set-lineup.js - Navigating to court.html:', finalUrl);
      playSound('confirm-1.mp3');
      // Delay navigation so the sound can start before the page unloads
      setTimeout(() => { window.location.href = finalUrl; }, 200);
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
  card.dataset.playerId = player._id;
  
  // Check if selected
  const isSelected = Object.values(lineup).includes(player._id);
  if (isSelected) {
    card.classList.add('selected');
  }
  
  // Make draggable (only if not ineligible)
  card.draggable = !isSelected && !player.ineligible && !player.fouled_out;
  if (card.draggable) {
    card.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', player._id);
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
        fillNextSlot(player._id);
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
  applyPlayerDetailLinkBehavior(headshotLink, player._id);
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
  
  // Player image (use static prefix for localhost)
  const playerImgBase = staticPrefix + '/images/players/';
  const img = document.createElement('img');
  img.className = 'player-headshot';
  img.src = player.photo || `${playerImgBase}${player._id}.png`;
  img.alt = player.name;
  img.onerror = () => {
    img.src = staticPrefix + '/images/players/generic_headshot.png';
  };
  headshotContainer.appendChild(img);
  
  // Year display (top center)
  if (player.year) {
    const yearDisplay = document.createElement('div');
    yearDisplay.className = 'player-year-display';
    // Format: capitalize first letter, rest lowercase
    const yearText = player.year.toLowerCase();
    const yearFormatted = yearText.charAt(0).toUpperCase() + yearText.slice(1);
    yearDisplay.textContent = yearFormatted;
    
    // Custom colors by year
    let yearColor;
    if (yearText === 'senior') {
      yearColor = '#FFD700'; // Bright gold
    } else if (yearText === 'junior') {
      yearColor = '#C0C0C0'; // Bright silver
    } else if (yearText === 'sophomore') {
      yearColor = '#32CD32'; // Bright lime green
    } else if (yearText === 'freshman') {
      yearColor = '#FF69B4'; // Bright pink
    } else {
      yearColor = '#C0C0C0'; // Default to silver
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
    toggleCardFlip(player._id);
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
  circle.textContent = topRating;
  circle.setAttribute('aria-label', 'Position rating');
  
  // Create tooltip content with all 5 position ratings in descending order
  const tooltipContent = entries
    .map(([pos, rating]) => `${pos}: ${rating}`)
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
    toggleCardFlip(player._id);
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
    if (displayVal !== '--') {
      const fillPercentage = Math.min(displayVal * 10, 100);
      pill.style.setProperty('--attr-fill', `${fillPercentage}%`);
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
  // Check if slot is already filled
  if (lineup[pos]) {
    showToast('Slot already filled');
    return false;
  }
  
  // Check if player is already in lineup
  if (Object.values(lineup).includes(playerId)) {
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
  
  // Update all slot displays to ensure position ratings are shown correctly
  updateAllSlotDisplays();
  
  updatePlayButton();
  
  // Re-attach event listeners after DOM update
  setupSlotDragAndDrop();
  
  // Re-render views to update selection state
  if (currentView === 'player') {
    renderPlayerView();
  } else {
    renderRoster();
  }
  
  return true;
}

function getHighestOpenSlotPosition() {
  const renderedSlots = Array.from(document.querySelectorAll('#slots .slot[data-pos]'));
  for (const slot of renderedSlots) {
    const pos = slot.dataset.pos;
    if (pos && !lineup[pos]) {
      return pos;
    }
  }

  const fallbackPositions = ['PG', 'SG', 'SF', 'PF', 'C'];
  return fallbackPositions.find(pos => !lineup[pos]) || null;
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

// Update renderRoster to mark selected rows
const originalRenderRoster = renderRoster;
renderRoster = function() {
  originalRenderRoster();
  
  // Mark selected rows
  const selectedIds = Object.values(lineup);
  roster.forEach(p => {
    const row = document.querySelector(`tr[data-player-id="${p._id}"]`);
    if (row) {
      if (selectedIds.includes(p._id)) {
        row.classList.add('selected');
      } else {
        row.classList.remove('selected');
      }
      
      // Add click handler to fill next slot (only if not ineligible)
      if (!p.ineligible && !p.fouled_out) {
        row.addEventListener('click', (e) => {
          if (!selectedIds.includes(p._id)) {
            const assigned = fillNextSlot(p._id);
            if (assigned) {
              playSound('click-tiny.wav');
            }
          }
        });
      } else if (p.ineligible || p.fouled_out) {
        // Mark ineligible rows with grey tint
        row.classList.add('ineligible');
        row.style.backgroundColor = '#d3d3d3';  // Light grey background tint
        row.style.opacity = '0.7';
        row.style.pointerEvents = 'none';
        row.style.cursor = 'not-allowed';
      }
    }
  });
};

// Make slots draggable for swapping
function setupSlotDragAndDrop() {
  const slots = document.querySelectorAll('.slot');
  
  slots.forEach(slot => {
    const pos = slot.dataset.pos;
    // Ensure draggable state reflects whether slot is filled
    const filled = !!lineup[pos];
    slot.draggable = filled;
    slot.setAttribute('draggable', filled ? 'true' : 'false');

    // Wire up remove button click event
    const removeBtn = slot.querySelector('.remove');
    if (removeBtn) {
      // Remove any existing listeners to prevent duplicates
      const newRemoveBtn = removeBtn.cloneNode(true);
      removeBtn.parentNode.replaceChild(newRemoveBtn, removeBtn);
      
      newRemoveBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent slot click from firing
        playSound('x-back.mp3');
        clearSlot(slot);
      });
    }

    // Provide drag data when dragging a filled slot
    slot.addEventListener('dragstart', (e) => {
      const playerId = lineup[pos];
      if (!playerId) { e.preventDefault(); return; }
      e.dataTransfer.setData('text/plain', playerId);
      e.dataTransfer.effectAllowed = 'move';
    });
    
    slot.addEventListener('dragover', (e) => {
      e.preventDefault();
      slot.classList.add('drag-over');
    });
    
    slot.addEventListener('dragleave', () => {
      slot.classList.remove('drag-over');
    });
    
    slot.addEventListener('drop', (e) => {
      e.preventDefault();
      slot.classList.remove('drag-over');
      
      const draggedId = e.dataTransfer.getData('text/plain');
      const targetPos = pos;
      if (!draggedId) return;
      
      // If slot is filled, swap; else assign
      if (lineup[targetPos]) {
        const currentId = lineup[targetPos];
        const draggedPos = Object.keys(lineup).find(p => lineup[p] === draggedId);
        if (draggedPos) {
          lineup[draggedPos] = currentId;
          lineup[targetPos] = draggedId;
          updateAllSlots();
        } else {
          assignToSlot(targetPos, draggedId);
        }
      } else {
        assignToSlot(targetPos, draggedId);
      }
      playSound('click-soft.mp3');
    });
  });
}

function updateAllSlots() {
  // Use the new updateAllSlotDisplays() function which handles the new HTML structure
  updateAllSlotDisplays();
  updatePlayButton();
  // Re-attach event listeners after DOM update
  setupSlotDragAndDrop();
  if (currentView === 'player') renderPlayerView();
  if (currentView === 'grid') renderRoster();
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
  const redirected = await redirectIfFranchiseGameplayAlreadyCommitted();
  if (redirected) return;
  init();
  
  // Initialize tooltips for table headers (th elements only)
  // Use a small delay to ensure thead is fully rendered
  setTimeout(() => {
    if (typeof initAttributeTooltips !== 'undefined') {
      const thead = document.querySelector('.roster-table thead');
      if (thead) {
        initAttributeTooltips(thead, ['th']);
        
        // Tooltips initialized (verification logs removed for cleaner console)
      } else {
        console.warn('[TOOLTIP] thead element not found');
      }
    }
  }, 100);
  
  setupSlotDragAndDrop();
});
