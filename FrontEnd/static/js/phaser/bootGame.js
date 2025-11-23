import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';
import { setCourtOffsets } from './utils/gridToPixels.js';
import { on, emit } from './utils/eventBus.js';
import { finalizeGame } from './finalizeGame.js';
import { DEBUG } from './utils/debug.js';
import gameStore from '../state/gameStore.js';
import { generateBothLineups } from './utils/autosetLineup.js';

const DEBUG_GAME_ID =
  (typeof window !== 'undefined' && window.DEBUG_GAME_ID) ||
  (typeof process !== 'undefined' && process.env.DEBUG_GAME_ID) ||
  false;
const DEBUG_TEAMS =
  (typeof window !== 'undefined' && window.DEBUG_TEAMS) ||
  (typeof process !== 'undefined' && process.env.DEBUG_TEAMS) ||
  false;
const DEBUG_SERIALIZATION =
  (typeof window !== 'undefined' && window.DEBUG_SERIALIZATION) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SERIALIZATION) ||
  false;

if (typeof window !== 'undefined') {
  window.TEXT_SCROLL_ENABLED =
    window.TEXT_SCROLL_ENABLED !== undefined ? window.TEXT_SCROLL_ENABLED : true;
  window.TEXT_SCROLL_CONFIG = {
    autoScroll: true,
    smooth: false,
    lineSpacing: '1em',
    ...(window.TEXT_SCROLL_CONFIG || {}),
  };
  window.animation_config = window.animation_config || {};
}

function updateScoreboardScores({ home, away }) {
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl) homeScoreEl.textContent = home;
  if (awayScoreEl) awayScoreEl.textContent = away;
}

if (typeof on === 'function' && typeof emit === 'function') {
  on('score:update', updateScoreboardScores);
  // Note: Score initialization moved to after variable declarations
} else {
  // Note: Score initialization moved to after variable declarations
}

function getMode({ tournamentId, franchiseId }) {
  if (tournamentId) return 'tournament';
  if (franchiseId) return 'franchise';
  return 'standalone';
}

// Utility function to generate MongoDB ObjectId format game IDs
function generateMongoObjectId() {
  // 8-byte timestamp (seconds since epoch)
  const timestamp = Math.floor(Date.now() / 1000).toString(16).padStart(8, '0');
  
  // 6-byte random value
  const randomPart = Math.floor(Math.random() * 0xffffff).toString(16).padStart(6, '0');
  
  // 4-byte counter (additional randomness)
  const counter = Math.floor(Math.random() * 0xffff).toString(16).padStart(4, '0');
  
  // Additional 6 bytes for full 24-character ObjectId format
  const extraRandom = Math.floor(Math.random() * 0xffffff).toString(16).padStart(6, '0');
  
  return timestamp + randomPart + counter + extraRandom;
}

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.append(key, value);
  });
  const str = search.toString();
  return str ? `?${str}` : '';
}

const urlParams = new URLSearchParams(window.location.search);
const tournamentId = urlParams.get('tournament_id');
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const queryFranchiseId = urlParams.get('franchise_id');
const storedFranchiseId =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem('franchise_id') || localStorage.getItem('franchiseId')
    : null;
const franchiseId = queryFranchiseId || storedFranchiseId;
if (queryFranchiseId && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_id', queryFranchiseId);
}
const weekParam = parseInt(urlParams.get('week'), 10);
if (weekParam && !Number.isNaN(weekParam) && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_week', weekParam);
}
const mode = urlParams.get('mode') || getMode({ tournamentId, franchiseId });
const userTeamSide = urlParams.get('my_team');  // "home" or "away"
let quarter = parseInt(urlParams.get('quarter'), 10) || 1;
let gameId =
  urlParams.get('game_id') ||
  (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);

// Initialize scoreboard scores
// Only reset to 0-0 for fresh Q1 games; for resumed games, loadGameStats.js sets accumulated scores
if (quarter === 1 && !gameId) {
  if (typeof emit === 'function') {
    emit('score:update', { home: 0, away: 0 });
  } else {
    updateScoreboardScores({ home: 0, away: 0 });
  }
}

// Load game plan settings (async function to be called before game starts)
let gamePlanSettings = null;

async function loadGamePlanSettings() {
  if (!userTeamSide) {
    console.log('⚠️ No user team side specified, skipping game plan load');
    return;
  }
  
  const teamName = userTeamSide === 'home' ? homeTeam : awayTeam;
  const teamId = userTeamSide === 'home' ? urlParams.get('home_id') : urlParams.get('away_id');
  
  if (mode === 'single' && typeof localStorage !== 'undefined') {
    // Single game mode: load from localStorage (persist by team, not matchup)
    const storageKey = `gameplan_${teamName}`;
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        gamePlanSettings = JSON.parse(stored);
      } catch (e) {
        console.error('Failed to parse game plan settings:', e);
      }
    }
  } else if (mode === 'franchise' && franchiseId && teamId) {
    // Franchise mode: load from database
    try {
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('franchise_id', franchiseId);
      params.set('team_id', teamId);
      
      const res = await fetch(`/api/gameplan?${params.toString()}`);
      if (res.ok) {
        gamePlanSettings = await res.json();
        console.log('📋 Loaded game plan settings from database (franchise mode):', gamePlanSettings);
      } else {
        console.error('Failed to load franchise game plan settings');
      }
    } catch (e) {
      console.error('Error loading franchise game plan:', e);
    }
  } else if (mode === 'tournament' && tournamentId && teamId) {
    // Tournament mode: load from database
    try {
      const params = new URLSearchParams();
      params.set('mode', 'tournament');
      params.set('tournament_id', tournamentId);
      params.set('team_id', teamId);
      
      const res = await fetch(`/api/gameplan?${params.toString()}`);
      if (res.ok) {
        gamePlanSettings = await res.json();
        console.log('📋 Loaded game plan settings from database (tournament mode):', gamePlanSettings);
      } else {
        console.error('Failed to load tournament game plan settings');
      }
    } catch (e) {
      console.error('Error loading tournament game plan:', e);
    }
  }
}
let periodLabel = urlParams.get('period') || `Q${quarter}`;

const homeLineup = {};
const awayLineup = {};
['pg', 'sg', 'sf', 'pf', 'c'].forEach(pos => {
  const h = urlParams.get(`home_${pos}`);
  const a = urlParams.get(`away_${pos}`);
  if (h) homeLineup[pos.toUpperCase()] = h;
  if (a) awayLineup[pos.toUpperCase()] = a;
});

console.log("🏀 Tournament launch params:", {
  tournamentId,
  franchiseId,
  homeTeam,
  awayTeam,
  mode,
  periodLabel,
});

const GameScene = createGameScene(Phaser);
let game;
let isSimulating = false;

function showStatus(msg) {
  let el = document.getElementById('sim-status');
  if (!el) {
    el = document.createElement('div');
    el.id = 'sim-status';
    el.style.color = '#fff';
    el.style.fontFamily = 'Bebas Neue, sans-serif';
    const container = document.getElementById('phaser-container');
    if (container) container.appendChild(el);
  }
  el.textContent = msg;
}

function updateOffsets() {
  if (typeof document === 'undefined') return;
  const container = document.getElementById('phaser-container');
  if (!container || !container.getBoundingClientRect) return;
  const rect = container.getBoundingClientRect();
  setCourtOffsets(rect.left, rect.top);
}

if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('resize', updateOffsets);
}

function resetGameContext() {
  gameId = null;
  quarter = 1;
  periodLabel = 'Q1';
  isSimulating = false;
  if (typeof localStorage !== 'undefined' && typeof localStorage.removeItem === 'function') {
    localStorage.removeItem('game_id');
  }
  gameStore.reset();
  updateScoreboardScores({ home: 0, away: 0 });
}


async function fetchTeamRoster(teamName) {
  // Use franchise-specific roster endpoint if in franchise mode
  let url;
  if (mode === 'franchise' && franchiseId) {
    url = `/franchise/roster?franchise_id=${franchiseId}&team_name=${encodeURIComponent(teamName)}`;
    console.log(`Loading franchise-specific roster for ${teamName}`);
  } else {
    const query = buildQuery({
      tournament_id: mode === 'tournament' ? tournamentId : null,
      franchise_id: mode === 'franchise' ? franchiseId : null,
    });
    url = `/roster/${encodeURIComponent(teamName)}${query}`;
  }
  
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load roster for ${teamName}`);
  }
  return res.json();
}

async function startGame({ homeRoster, awayRoster, animate = true }) {
  DEBUG && console.log('[bootGame] startGame', { quarter, animate });
  
  // Load game plan settings before starting the game
  await loadGamePlanSettings();
  
  gameStore.reset();
  gameStore.setTeams({ home: homeTeam, away: awayTeam });
  gameStore.setRosters({ home: homeRoster, away: awayRoster });
  gameStore.setColors({
    home: {
      primary_color: homeRoster.primary_color,
      secondary_color: homeRoster.secondary_color,
    },
    away: {
      primary_color: awayRoster.primary_color,
      secondary_color: awayRoster.secondary_color,
    },
  });
  gameStore.setGameId(gameId);
  if (!game) {
    game = new Phaser.Game({
      type: Phaser.AUTO,
      width: 1229,
      height: 768,
      backgroundColor: '#1e1e1e',
      parent: 'phaser-container',
      audio: { noAudio: true },
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_HORIZONTALLY,
        width: 1229,
        height: 768
      },
      scene: [], // prevent auto-start
    });
    game.scene.add('GameScene', GameScene);
  }

  const sceneData = {
    tournamentId,
    franchiseId,
    animate,
    homeLineup,
    awayLineup,
    periodLabel,
    quarter,
    gamePlanSettings,
    userTeamSide,
    mode,
  };

  if (game.scene.isActive('GameScene')) {
    game.scene.restart('GameScene', sceneData);
  } else {
    game.scene.start('GameScene', sceneData);
  }

  return new Promise((resolve) => {
    // Listen on the global event emitter so we don't lose the listener when
    // GameScene is restarted or recreated
    game.events.once('gameComplete', (finalScore) => {
      resolve(finalScore);
    });
  });
}

async function showPopup(score) {
  // Get gameId from multiple sources (module variable, score object, localStorage, URL params)
  let popupGameId = gameId; // Use module-level gameId first
  if (!popupGameId && score && score.gameId) {
    popupGameId = score.gameId;
  }
  if (!popupGameId && typeof localStorage !== 'undefined') {
    popupGameId = localStorage.getItem('game_id');
  }
  if (!popupGameId) {
    const params = new URLSearchParams(window.location.search);
    popupGameId = params.get('game_id');
  }
  
  console.log('📋 showPopup called:', {
    popupGameId,
    moduleGameId: gameId,
    gameIdFromScore: score?.gameId,
    gameIdFromLocalStorage: typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : 'N/A',
    gameIdFromParams: new URLSearchParams(window.location.search).get('game_id'),
    score,
    homeTeam,
    awayTeam,
    mode,
    tournamentId,
    franchiseId
  });
  
  if (!popupGameId) {
    console.error('❌ No game_id found for box score - box score will not have data!');
  }

  // Use the new game completion popup
  const { showGameCompletionPopup } = await import('./utils/gameCompletionPopup.js');
  showGameCompletionPopup({
    gameId: popupGameId || '',
    mode: mode || 'single',
    tournamentId: tournamentId,
    franchiseId: franchiseId,
    finalScore: score,
    homeTeam: homeTeam,
    awayTeam: awayTeam
  });
}

async function handleButtonClick(animate) {
  console.log('handleButtonClick called with animate:', animate);
  console.log('Current state:', { isSimulating, gameId, quarter, homeTeam, awayTeam });
  
  if (isSimulating) {
    console.log('Already simulating, returning early');
    return;
  }
  
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
    console.log('Retrieved gameId from localStorage:', gameId);
  }
  
  const startingFresh = !gameId;
  if (startingFresh) {
    console.log('Starting fresh game, resetting context');
    resetGameContext();
  }
  
  DEBUG && console.log('[handleButtonClick]', { startingFresh, quarter, gameId });
  isSimulating = true;
  
  // Remove the pre-game button container from DOM
  const preGameContainer = document.querySelector('.pre-game-container');
  if (preGameContainer) {
    console.log('🎮 Removing pre-game container (Play Quarter)');
    preGameContainer.remove();
    console.log('🎮 Pre-game container removed from DOM');
  } else {
    console.warn('⚠️ Pre-game container not found');
  }

  try {
    if (DEBUG_TEAMS) {
      console.log('Fetching rosters for teams:', { homeTeam, awayTeam });
    }
    const [homeRoster, awayRoster] = await Promise.all([
      fetchTeamRoster(homeTeam),
      fetchTeamRoster(awayTeam),
    ]);
    const finalScore = await startGame({ homeRoster, awayRoster, animate });
    console.log('Game completed, final score:', finalScore);
    showPopup(finalScore);
  } catch (err) {
    console.error('Error starting game:', err);
    console.error('Error details:', err.message, err.stack);
  } finally {
    if (isSimulating) {
      isSimulating = false;
      if (playBtn) playBtn.style.display = '';
      if (simFullBtn) simFullBtn.style.display = '';
      if (sim4Btn && quarter < 4) sim4Btn.style.display = '';
    }
  }
}

async function handleSimToFourth() {
  if (isSimulating || quarter >= 4) return;
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
  }
  if (!gameId) {
    // Generate a new gameId using standardized MongoDB ObjectId format
    gameId = generateMongoObjectId();
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_id', gameId);
    }
    console.log('🎮 Generated new gameId:', gameId);
  }
  isSimulating = true;
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = true; });

  // Load game plan settings before simulating
  await loadGamePlanSettings();

  // Fetch rosters for auto-set lineup generation
  let homeRoster, awayRoster;
  try {
    const homeRes = await fetch(`/roster/${homeTeam}`);
    const awayRes = await fetch(`/roster/${awayTeam}`);
    if (homeRes.ok) homeRoster = await homeRes.json();
    if (awayRes.ok) awayRoster = await awayRes.json();
  } catch (err) {
    console.error('Error fetching rosters for auto-set:', err);
  }

  try {
    let currentQ = quarter;
    let gId = gameId;
    let lastSummary;
      while (currentQ <= 3) {
        showStatus(`Simulating Q${currentQ}...`);
      const payload = {
        home_team: homeTeam,
        away_team: awayTeam,
        quarter: currentQ,
        game_id: gameId, // Always pass gameId for tournament games
      };
      
      // Q1: Use user's set lineup
      // Q2-Q3: Auto-set lineups for both teams
      if (currentQ === quarter) {
        if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
        if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
        // Add game plan settings (Q1 only, will be reused for Q2-Q3)
        console.log('🔍 Game plan check:', { currentQ, quarter, hasSettings: !!gamePlanSettings, userTeamSide, mode });
        if (currentQ === 1 && gamePlanSettings && userTeamSide) {
          payload.user_team_side = userTeamSide;
          payload.playcall_settings = gamePlanSettings.playcall_settings;
          payload.strategy_settings = gamePlanSettings.strategy_settings;
          console.log(`🎮 Sending game plan settings to backend (${mode} mode):`, { userTeamSide, playcall: gamePlanSettings.playcall_settings });
        } else if (currentQ === 1) {
          console.warn('⚠️ Not sending game plan settings:', { hasSettings: !!gamePlanSettings, userTeamSide });
        }
      } else {
        // Q2-Q3: Auto-set lineups
        if (homeRoster && awayRoster) {
          const autoLineups = generateBothLineups(homeRoster, awayRoster);
          payload.home_lineup = autoLineups.home_lineup;
          payload.away_lineup = autoLineups.away_lineup;
          console.log(`🤖 Q${currentQ}: Auto-set lineups generated for both teams`);
        }
        // Reuse game plan settings from Q1
        if (gamePlanSettings && userTeamSide) {
          payload.user_team_side = userTeamSide;
          payload.playcall_settings = gamePlanSettings.playcall_settings;
          payload.strategy_settings = gamePlanSettings.strategy_settings;
        }
        // Randomize possession and start with inbound for Q2-Q3
        payload.start_with_inbound = true;
        payload.starting_possession = Math.random() < 0.5 ? 'home' : 'away';
        console.log(`🎲 Q${currentQ}: Random possession assigned to ${payload.starting_possession}`);
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      // ✅ FIX: Add full_sim=true for "simming" operations (fully simulate without animation)
      payload.full_sim = true;
      
      console.log({event:'simulate-quarter:request', mode, homeTeam, awayTeam, quarter: currentQ, gameId: gId, full_sim: true});
      const res = await fetch('/api/simulate-quarter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        // ✅ FIX: Extract actual error message from backend for better debugging
        let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
        try {
          const errorData = await res.json();
          errorDetail = errorData.detail || errorData.message || errorDetail;
        } catch (e) {
          try {
            errorDetail = await res.text();
          } catch (e2) {
            // Keep default errorDetail
          }
        }
        console.error(`❌ Q${currentQ} simulation failed:`, errorDetail);
        throw new Error(`Q${currentQ} simulation failed: ${errorDetail}`);
      }
      lastSummary = await res.json();
      gId = lastSummary.game_id;
      // ✅ FIX: After fully simulating a quarter, increment to the next quarter
      // This ensures the loop progresses: Q1 → Q2 → Q3 → exit (4 > 3)
      const simulatedQuarter = currentQ;
      currentQ += 1;
      console.log(`✅ Q${simulatedQuarter} fully simulated, backend reports next quarter=${lastSummary.quarter}, moving to Q${currentQ}`);
      // Safety check: if currentQ didn't increment, break to prevent infinite loop
      if (currentQ === simulatedQuarter) {
        console.error('🚨 Infinite loop detected: currentQ did not increment! Breaking loop.');
        break;
      }
    }

    // After Q1-Q3 simulated, redirect to set-lineup for Q4
    gameId = gId;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_id', gameId);
    }
    
    // Build URL parameters for set-lineup screen
    const params = new URLSearchParams();
    params.set('home', homeTeam);
    params.set('away', awayTeam);
    params.set('home_id', urlParams.get('home_id') || homeTeam);
    params.set('away_id', urlParams.get('away_id') || awayTeam);
    params.set('mode', mode);
    params.set('my_team', userTeamSide || 'home');
    params.set('user_team_id', userTeamSide === 'home' ? homeTeam : awayTeam);
    params.set('quarter', 4);
    params.set('period', 'Q4');
    params.set('game_id', gameId);
    
    // Q4 should NOT use start_with_inbound - let backend handle standard Q4 logic (opening tip winner)
    // The backend will automatically give possession to the opening tip winner for Q4
    console.log(`🏀 Q4 will use standard possession logic (opening tip winner gets ball)`);
    
    console.log('🎮 Redirecting to set-lineup for Q4 after simming Q1-Q3');
    window.location.href = `/static/set-lineup.html?${params.toString()}`;
  } catch (err) {
    console.error('Error simming to 4th quarter:', err);
    // ✅ FIX: Show actual error message instead of generic message
    const errorMessage = err.message || 'Simulation failed. Please try again.';
    showStatus(errorMessage);
    // Also show in alert for better visibility
    alert(`Simulation Error: ${errorMessage}`);
  } finally {
    isSimulating = false;
    if (playBtn) playBtn.disabled = false;
    if (simFullBtn) simFullBtn.disabled = false;
    if (sim4Btn) sim4Btn.disabled = true;
  }
}

async function handleSimFullGame() {
  if (isSimulating) return;
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
  }
  if (!gameId) {
    resetGameContext();
  }
  isSimulating = true;
  
  // Remove the pre-game button container from DOM
  const preGameContainer = document.querySelector('.pre-game-container');
  if (preGameContainer) {
    console.log('🎮 Removing pre-game container (Sim Full Game)');
    preGameContainer.remove();
    console.log('🎮 Pre-game container removed from DOM');
  } else {
    console.warn('⚠️ Pre-game container not found');
  }
  
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = true; });

  // Load game plan settings before simulating
  await loadGamePlanSettings();

  // Fetch rosters for auto-set lineup generation
  let homeRoster, awayRoster;
  try {
    const homeRes = await fetch(`/roster/${homeTeam}`);
    const awayRes = await fetch(`/roster/${awayTeam}`);
    if (homeRes.ok) homeRoster = await homeRes.json();
    if (awayRes.ok) awayRoster = await awayRes.json();
  } catch (err) {
    console.error('Error fetching rosters for auto-set:', err);
  }

  try {
    let currentQ = quarter;
    let gId = gameId;
    let lastSummary;
    while (true) {
      showStatus(`Simulating Q${currentQ}...`);
      const payload = {
        home_team: homeTeam,
        away_team: awayTeam,
        quarter: currentQ,
      };
      if (gId) payload.game_id = gId;
      
      // Q1: Use user's set lineup
      // Q2-Q4: Auto-set lineups for both teams
      if (currentQ === quarter) {
        if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
        if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
        // Add game plan settings (Q1 only, will be reused for all quarters)
        console.log('🔍 Game plan check (sim full):', { currentQ, quarter, hasSettings: !!gamePlanSettings, userTeamSide, mode });
        if (currentQ === 1 && gamePlanSettings && userTeamSide) {
          payload.user_team_side = userTeamSide;
          payload.playcall_settings = gamePlanSettings.playcall_settings;
          payload.strategy_settings = gamePlanSettings.strategy_settings;
          console.log(`🎮 Sending game plan settings to backend (${mode} mode, sim full):`, { userTeamSide, playcall: gamePlanSettings.playcall_settings });
        } else if (currentQ === 1) {
          console.warn('⚠️ Not sending game plan settings (sim full):', { hasSettings: !!gamePlanSettings, userTeamSide });
        }
      } else {
        // Q2-Q4: Auto-set lineups
        if (homeRoster && awayRoster) {
          const autoLineups = generateBothLineups(homeRoster, awayRoster);
          payload.home_lineup = autoLineups.home_lineup;
          payload.away_lineup = autoLineups.away_lineup;
          console.log(`🤖 Q${currentQ}: Auto-set lineups generated for both teams`);
        }
        // Reuse game plan settings from Q1
        if (gamePlanSettings && userTeamSide) {
          payload.user_team_side = userTeamSide;
          payload.playcall_settings = gamePlanSettings.playcall_settings;
          payload.strategy_settings = gamePlanSettings.strategy_settings;
        }
        // Randomize possession and start with inbound for Q2-Q4
        payload.start_with_inbound = true;
        payload.starting_possession = Math.random() < 0.5 ? 'home' : 'away';
        console.log(`🎲 Q${currentQ}: Random possession assigned to ${payload.starting_possession}`);
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      // ✅ FIX: Add full_sim=true for "simming" operations (fully simulate without animation)
      payload.full_sim = true;
      
      console.log({event:'simulate-quarter:request', mode, homeTeam, awayTeam, quarter: currentQ, gameId: gId, full_sim: true});
      const res = await fetch('/api/simulate-quarter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        // ✅ FIX: Extract actual error message from backend for better debugging
        let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
        try {
          const errorData = await res.json();
          errorDetail = errorData.detail || errorData.message || errorDetail;
        } catch (e) {
          try {
            errorDetail = await res.text();
          } catch (e2) {
            // Keep default errorDetail
          }
        }
        console.error(`❌ Q${currentQ} simulation failed:`, errorDetail);
        throw new Error(`Q${currentQ} simulation failed: ${errorDetail}`);
      }
      lastSummary = await res.json();
      // Ensure game_id is a string (backend might return ObjectId)
      gId = lastSummary.game_id ? String(lastSummary.game_id) : lastSummary.game_id;
      console.log('🎮 Quarter simulation response:', {
        quarter: currentQ,
        gameId: gId,
        gameIdType: typeof gId,
        isFinal: lastSummary.is_final,
        hasBoxScore: !!lastSummary.box_score
      });
      if (lastSummary.is_final) break;
      // ✅ FIX: After fully simulating a quarter, increment to the next quarter
      // The backend's quarter in the response is the NEXT quarter (after increment)
      // But we need to manually increment currentQ to move to the next iteration
      currentQ += 1;
      console.log(`✅ Q${currentQ - 1} fully simulated, backend reports next quarter=${lastSummary.quarter}, moving to Q${currentQ}`);
    }

    gameId = gId;
    // Save gameId to localStorage so box score can access it
    if (gameId && typeof localStorage !== 'undefined') {
      localStorage.setItem('game_id', gameId);
      console.log('💾 Saved gameId to localStorage:', gameId);
    } else {
      console.warn('⚠️ Could not save gameId to localStorage:', { gameId, gId, hasLocalStorage: typeof localStorage !== 'undefined' });
    }
    quarter = lastSummary.quarter || currentQ;
    periodLabel = lastSummary.period_label || (quarter > 4 ? `OT${quarter - 4}` : `Q${quarter}`);

    console.log('📊 Final game summary from last quarter response:', {
      gameId,
      quarter,
      hasBoxScore: !!lastSummary.box_score,
      boxScoreKeys: lastSummary.box_score ? Object.keys(lastSummary.box_score) : [],
      score: lastSummary.score,
      isFinal: lastSummary.is_final
    });

    // ✅ FIX: Fetch the complete game data from API to ensure box_score is fully populated
    // This matches what happens when "Sim To 4th Quarter" → play Q4 normally
    let finalGameData = lastSummary;
    if (gameId) {
      try {
        console.log('📥 Fetching final game data from API to ensure box_score is complete...');
        const gameResponse = await fetch(`/api/game/${gameId}`);
        if (gameResponse.ok) {
          finalGameData = await gameResponse.json();
          console.log('✅ Fetched final game data:', {
            hasBoxScore: !!finalGameData.box_score,
            boxScoreKeys: finalGameData.box_score ? Object.keys(finalGameData.box_score) : [],
            hasPlayers: !!finalGameData.players,
            playerCount: finalGameData.players ? finalGameData.players.length : 0
          });
        } else {
          console.warn('⚠️ Failed to fetch final game data, using lastSummary:', gameResponse.status);
        }
      } catch (err) {
        console.error('❌ Error fetching final game data, using lastSummary:', err);
      }
    }

    const finalScore = await finalizeGame({ simData: finalGameData, tournamentId, franchiseId });
    console.log('🏆 Final score object:', finalScore);
    
    // ✅ REPLICATE gameScene.js approach: Pass gameId directly to showGameCompletionPopup
    // This matches exactly what gameScene.js does (line 1916: gameId: gameId)
    const { showGameCompletionPopup } = await import('./utils/gameCompletionPopup.js');
    const popupMode = tournamentId ? 'tournament' : (franchiseId ? 'franchise' : 'single');
    showGameCompletionPopup({
      gameId: gameId, // Use module-level gameId directly, just like gameScene.js
      mode: popupMode,
      tournamentId: tournamentId,
      franchiseId: franchiseId,
      finalScore: finalScore,
      homeTeam: homeTeam,
      awayTeam: awayTeam
    });
  } catch (err) {
    console.error('Error simming full game:', err);
    // ✅ FIX: Show actual error message instead of generic message
    const errorMessage = err.message || 'Simulation failed. Please try again.';
    showStatus(errorMessage);
    // Also show in alert for better visibility
    alert(`Simulation Error: ${errorMessage}`);
    [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = false; });
  } finally {
    isSimulating = false;
  }
}

function initGame() {
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  
  console.log('Initializing game buttons:', { playBtn, simFullBtn, sim4Btn });
  
  if (playBtn) {
    console.log('Adding click listener to Play Quarter button');
    playBtn.addEventListener('click', async () => {
      console.log('🚨 BUTTON CLICKED: Play Quarter button clicked!');
      console.log('🚨 BUTTON CLICKED: About to call handleButtonClick');
      try {
        await handleButtonClick(true);
        console.log('🚨 BUTTON CLICKED: handleButtonClick completed successfully');
      } catch (error) {
        console.error('🚨 BUTTON CLICKED: handleButtonClick failed:', error);
      }
    });
  } else {
    console.error('Play Quarter button not found!');
  }
  
  if (simFullBtn) {
    simFullBtn.addEventListener('click', handleSimFullGame);
  }
  if (sim4Btn) {
    if (quarter >= 4) {
      sim4Btn.disabled = true;
      sim4Btn.title = 'Already in 4th quarter';
    } else {
      sim4Btn.addEventListener('click', handleSimToFourth);
    }
  }
}

// console.log('🚨 BOOTGAME: JavaScript is loading and executing!');
initGame();
updateOffsets();
// console.log('🚨 BOOTGAME: Initialization complete!');

// new Phaser.Game(config);
