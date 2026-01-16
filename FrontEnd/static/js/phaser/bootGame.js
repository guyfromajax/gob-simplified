import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';
import { setCourtOffsets } from './utils/gridToPixels.js';
import { on, emit } from './utils/eventBus.js';
import { finalizeGame } from './finalizeGame.js';
import { DEBUG } from './utils/debug.js';
import gameStore from '../state/gameStore.js';
import { generateBothLineups } from './utils/autosetLineup.js';

// API_CONFIG is loaded as a global script, access via window
const API_CONFIG = window.API_CONFIG;

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

// ✅ REFACTOR: Removed event system for scores - now using direct DOM updates in gameScene.js
// This matches the pattern used for fouls, timeouts, and clock (consistent approach)

function getMode({ tournamentId, franchiseId }) {
  if (tournamentId) return 'tournament';
  if (franchiseId) return 'franchise';
  return 'single'; // ✅ SS&S: Explicitly return 'single' for Single Game mode
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

// ✅ DEBUG: Log URL params when court.html loads (to see what game-plan passed)
const bootGameParams = {
  fullUrl: window.location.href,
  game_id: urlParams.get('game_id'),
  resume_from_timeout: urlParams.get('resume_from_timeout'),
  quarter: urlParams.get('quarter'),
  allParams: Object.fromEntries(urlParams.entries())
};
console.log('🔍 [BOOTGAME] Court page loaded with URL params:', bootGameParams);
console.warn('⚠️ [BOOTGAME] CRITICAL CHECK - game_id:', bootGameParams.game_id, 'resume_from_timeout:', bootGameParams.resume_from_timeout);

const tournamentId = urlParams.get('tournament_id');
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const queryFranchiseId = urlParams.get('franchise_id');
const storedFranchiseId =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem('franchise_id') || localStorage.getItem('franchiseId')
    : null;
// ✅ FIX: Only use storedFranchiseId if mode is explicitly 'franchise' or queryFranchiseId exists
// This prevents Single Game mode from accidentally using franchise_id from localStorage
const urlMode = urlParams.get('mode');
const franchiseId = queryFranchiseId || (urlMode === 'franchise' ? storedFranchiseId : null);
if (queryFranchiseId && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_id', queryFranchiseId);
}
const weekParam = parseInt(urlParams.get('week'), 10);
if (weekParam && !Number.isNaN(weekParam) && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_week', weekParam);
}
// ✅ SS&S: Explicitly set mode to 'single' if not provided and not tournament/franchise
const mode = urlMode || getMode({ tournamentId, franchiseId });
// Ensure mode is always explicit (never undefined)
if (!mode) {
  console.warn('⚠️ [BOOTGAME] Mode was undefined, defaulting to "single"');
}
const userTeamSide = urlParams.get('my_team');  // "home" or "away"
// ✅ SS&S: Read team_id (ObjectId) from URL params for navigation anchor preservation
const teamId = urlParams.get('team_id') || (userTeamSide === 'home' ? urlParams.get('home_id') : urlParams.get('away_id'));
// ✅ FIX: Default to 0 for pre-game screen (before Q1 starts)
// On pre-game screen, quarter param is missing, so default to 0
// This ensures "Sim Quarter" button simulates Q1 (0 + 1 = 1), not Q2 (1 + 1 = 2)
let quarter = urlParams.has('quarter') ? parseInt(urlParams.get('quarter'), 10) : 0;
console.log('🔍 [Q1 SKIP DEBUG] Quarter initialized:', { 
  urlHasQuarter: urlParams.has('quarter'), 
  urlQuarter: urlParams.get('quarter'), 
  parsedQuarter: quarter,
  url: window.location.href 
});
let gameId =
  urlParams.get('game_id') ||
  (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);

// Initialize scoreboard scores
// Only reset to 0-0 for fresh Q1 games; for resumed games, loadGameStats.js sets accumulated scores
// ✅ REFACTOR: Direct DOM update (same pattern as other scoreboard items)
// ✅ FIX: Use quarter === 0 (pre-game) OR (quarter === 1 && !gameId) for fresh Q1 games
if ((quarter === 0 || quarter === 1) && !gameId) {
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl) homeScoreEl.textContent = 0;
  if (awayScoreEl) awayScoreEl.textContent = 0;
}

// Load game plan settings (async function to be called before game starts)
let gamePlanSettings = null;

async function loadGamePlanSettings() {
  if (!userTeamSide) {
    console.log('⚠️ No user team side specified, skipping game plan load');
    return;
  }
  
  // Try multiple parameter names (different pages use different names)
  const teamId = urlParams.get('team_id') || 
                 urlParams.get('user_team_id') ||
                 (userTeamSide === 'home' ? urlParams.get('home_id') : urlParams.get('away_id'));
  
  // ✅ SS&S: Always load from database (single source of truth for all modes)
  try {
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
    
    const res = await fetch(API_CONFIG.buildUrl(`/api/gameplan?${params.toString()}`));
    if (res.ok) {
      gamePlanSettings = await res.json();
      console.log(`📋 Loaded game plan settings from database (${mode} mode):`, gamePlanSettings);
      console.log('   - Aggression setting:', gamePlanSettings?.strategy_settings?.aggression);
    } else {
      console.error(`❌ Failed to load game plan settings (${mode} mode), status:`, res.status);
    }
  } catch (e) {
    console.error(`❌ Error loading game plan settings (${mode} mode):`, e);
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

/**
 * Show scrolling text popup with shot results during Sim Quarter
 * @param {Object} lastSummary - Game summary from backend with turns array
 * @param {number} quarter - Quarter being simulated
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 */
async function showSimQuarterResults(lastSummary, quarter, homeTeam, awayTeam) {
  console.log('🔍 [SIM QUARTER] showSimQuarterResults called', { quarter, homeTeam, awayTeam });
  
  // Set scoreboard logos (GameScene doesn't start during Sim Quarter, so set them here)
  const homeLogoEl = document.getElementById('home-logo');
  const awayLogoEl = document.getElementById('away-logo');
  if (homeLogoEl && homeTeam) {
    homeLogoEl.src = `/images/homepage-logos/${encodeURIComponent(homeTeam)}.png`;
  }
  if (awayLogoEl && awayTeam) {
    awayLogoEl.src = `/images/homepage-logos/${encodeURIComponent(awayTeam)}.png`;
  }
  
  // Hide pre-game container
  const preGameContainer = document.querySelector('.pre-game-container');
  if (preGameContainer) {
    preGameContainer.classList.add('hidden');
    console.log('🔍 [SIM QUARTER] Pre-game container hidden');
  } else {
    console.log('🔍 [SIM QUARTER] Pre-game container not found (may already be hidden)');
  }
  
  // Show sim quarter popup
  const popup = document.getElementById('sim-quarter-popup');
  const titleEl = document.getElementById('sim-quarter-title');
  const contentEl = document.getElementById('sim-quarter-scroll-content');
  
  // ✅ NEW: Hide game control buttons when Sim Quarter popup is visible
  const gameControlsEl = document.querySelector('.game-controls');
  if (gameControlsEl) {
    gameControlsEl.style.display = 'none';
  }
  
  console.log('🔍 [SIM QUARTER] Popup elements check:', {
    popup: !!popup,
    titleEl: !!titleEl,
    contentEl: !!contentEl
  });
  
  if (!popup || !titleEl || !contentEl) {
    console.error('❌ [SIM QUARTER] Sim quarter popup elements not found - returning early');
    return;
  }
  
  console.log('🔍 [SIM QUARTER] All popup elements found, proceeding...');
  
  // ✅ FIX: Quarter display - show the quarter that just completed (quarter - 1)
  // When we're at Q1 break (quarter=1) and simulating Q2, the title should show Q1 (the quarter that just completed)
  // The quarter parameter passed in is the quarter we're about to simulate (nextQuarter)
  const displayQuarter = quarter - 1;
  const periodLabel = displayQuarter <= 4 ? `Q${displayQuarter}` : `OT${displayQuarter - 4}`;
  titleEl.textContent = `Simulating ${periodLabel}...`;
  
  // ✅ FIX: Don't update scoreboard quarter during Sim Quarter
  // Scoreboard should show the quarter that just completed (quarter - 1), not the quarter we're simulating
  // The scoreboard quarter will be updated after simulation completes via normal game flow
  // This prevents showing Q2 when we're still in Q1
  
  // Get team colors (SS&S: same pattern as gameScene.js - check unified structure first, then fallback)
  // Works across all modes (Single, Tournament, Franchise)
  const homeTeamId = lastSummary.home_team_id;
  const awayTeamId = lastSummary.away_team_id;
  const teamsObj = lastSummary.teams || {};
  
  // Try unified structure first (teams[team_id])
  let homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
  let awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
  
  // Fallback to direct home_team/away_team objects (backward compatibility)
  if (!homeTeamObj) {
    homeTeamObj = typeof lastSummary.home_team === 'object' ? lastSummary.home_team : null;
  }
  if (!awayTeamObj) {
    awayTeamObj = typeof lastSummary.away_team === 'object' ? lastSummary.away_team : null;
  }
  
  // Extract colors (same pattern as gameScene.js line 375-376)
  const homeColors = homeTeamObj?.colors || lastSummary.home_team_colors;
  const awayColors = awayTeamObj?.colors || lastSummary.away_team_colors;
  
  const homeColor = homeColors?.primary_color || '#ff6200';
  const awayColor = awayColors?.primary_color || '#ff6200';
  
  console.log('🔍 [SIM QUARTER] Team colors resolved:', {
    homeTeamId,
    awayTeamId,
    homeTeamObj: !!homeTeamObj,
    awayTeamObj: !!awayTeamObj,
    homeColors,
    awayColors,
    homeColor,
    awayColor
  });
  
  const players = lastSummary.players || [];
  
  // Create player lookup map (playerId -> {name, jersey, team_id})
  // ✅ SIMPLIFIED: Store team_id directly, compare to home/away team IDs when needed
  const playerMap = {};
  const homeTeamIdForComparison = homeTeamObj?.team_id || homeTeamId;
  const awayTeamIdForComparison = awayTeamObj?.team_id || awayTeamId;
  
  players.forEach(player => {
    if (player.playerId) {
      // ✅ FIX: Handle jersey number 0 - use nullish coalescing to preserve 0
      let jersey = '';
      if (typeof player.jersey === 'number') {
        jersey = player.jersey; // Preserve 0
      } else if (player.jersey !== undefined && player.jersey !== null && player.jersey !== '') {
        jersey = player.jersey;
      } else if (typeof player.jerseyNumber === 'number') {
        jersey = player.jerseyNumber; // Preserve 0
      } else if (player.jerseyNumber !== undefined && player.jerseyNumber !== null && player.jerseyNumber !== '') {
        jersey = player.jerseyNumber;
      } else if (typeof player.jersey_number === 'number') {
        jersey = player.jersey_number; // Preserve 0
      } else if (player.jersey_number !== undefined && player.jersey_number !== null && player.jersey_number !== '') {
        jersey = player.jersey_number;
      }
      
      playerMap[player.playerId] = {
        name: player.name || 'Unknown',
        jersey: jersey,
        team_id: player.team_id, // Store team_id directly
        photo: player.photo || null // Store player photo for made shots
      };
    }
  });
  
  // ✅ DIAGNOSTIC: Initialize ALL tracking arrays (before event processing)
  const ENABLE_FT_FG_DIAGNOSTICS = true; // Set to false to disable
  const playerLookupFailures = []; // Track when playerMap lookups fail
  const allPrintedEvents = []; // Track ALL printed events (not just FT/FG)
  const freeThrowEvents = []; // Track free throw events from turns
  const madeFGEvents = []; // Track made FG events from turns
  const printedFTEvents = []; // Track printed free throw events
  const printedMadeFGEvents = []; // Track printed made FG events
  const scoreboardUpdates = []; // ✅ NEW: Track every scoreboard update
  
  // ✅ DIAGNOSTIC: Build playerMap statistics for analysis
  const playerMapStats = {
    totalPlayers: players.length,
    playerMapSize: Object.keys(playerMap).length,
    playerIds: Object.keys(playerMap),
    playerNames: Object.values(playerMap).map(p => p.name)
  };
  
  // Get team names
  const homeTeamName = lastSummary.home_team?.name || homeTeam;
  const awayTeamName = lastSummary.away_team?.name || awayTeam;
  
  // Extract shot results from turns - ONLY from the quarter we just simulated
  // SS&S: Use turn.score (authoritative) just like updateScoreboard in gameScene.js
  // Filter turns to only include the quarter we just simulated (each turn has a quarter field)
  // ⚠️ BUG FIX: Backend sets turn.quarter = gm.quarter BEFORE simulating, so if we're simulating Q2
  // but gm.quarter=1, all turns will have quarter=1. We need to filter by the quarter BEFORE the one
  // that was just completed. If we just simulated Q2, turns have quarter=1 (the quarter before Q2).
  // Actually wait - let me check: if we're at Q1 break (gm.quarter=1) and simulate Q2, turns get quarter=1.
  // But if we're at Q2 break (gm.quarter=2) and simulate Q3, turns get quarter=2.
  // So the turns have the quarter that was ACTIVE when they were created, which is the quarter we just simulated.
  // But the backend increments gm.quarter AFTER simulation, so if we simulate Q2, turns should have quarter=2.
  // Let me check the actual behavior: we're simulating Q2, so turns should have quarter=2.
  // But the log shows 0 turns with quarter=2, which means turns have quarter=1.
  // This suggests gm.quarter=1 when we start simulating Q2.
  // FIX: Filter by quarter-1 (the quarter that was active during simulation)
  const allTurns = lastSummary.turns || [];
  console.log('🔍 [SIM QUARTER] Total turns in summary:', allTurns.length);
  console.log('🔍 [SIM QUARTER] Sample turn quarters:', allTurns.slice(0, 5).map(t => t.quarter));
  
  // Try filtering by the quarter we just simulated (quarter parameter)
  let turns = allTurns.filter(turn => turn.quarter === quarter);
  console.log('🔍 [SIM QUARTER] Turns for quarter', quarter + ':', turns.length);
  
  // If no turns found, try quarter-1 (backend might set quarter before incrementing)
  if (turns.length === 0 && quarter > 1) {
    turns = allTurns.filter(turn => turn.quarter === quarter - 1);
    console.log('🔍 [SIM QUARTER] Trying quarter-1 filter:', turns.length, 'turns found');
  }
  
  const eventResults = [];
  
  // ✅ SIMPLIFIED: Helper function to get player team ('home' or 'away') by comparing team_id
  const getPlayerTeam = (playerId, defaultTeam = 'home') => {
    const playerData = playerMap[playerId];
    if (!playerData || !playerData.team_id) return defaultTeam;
    
    // Simply compare player's team_id to home/away team IDs
    if (playerData.team_id === homeTeamIdForComparison) {
      return 'home';
    } else if (playerData.team_id === awayTeamIdForComparison) {
      return 'away';
    }
    
    // Fallback if team_id doesn't match (shouldn't happen, but safe)
    return defaultTeam;
  };
  
  turns.forEach((turn, index) => {
    const timeRemaining = turn.time_remaining || turn.clock || turn.game_clock || '0:00';
    const turnScore = turn.score || {};
    const homeScore = typeof turnScore[homeTeamName] === 'number' ? turnScore[homeTeamName] : 
                     (typeof turnScore[homeTeam] === 'number' ? turnScore[homeTeam] : 0);
    const awayScore = typeof turnScore[awayTeamName] === 'number' ? turnScore[awayTeamName] : 
                     (typeof turnScore[awayTeam] === 'number' ? turnScore[awayTeam] : 0);
    
    const resultType = turn.result_type;
    
    // Process different event types
    if (resultType === 'MAKE' || resultType === 'MISS') {
      // Regular shots, Fast Break shots, FCP shots, or HCT shots
      // Note: FCP/HCT shots have result_type 'MAKE'/'MISS' with fcp_shot/hct_shot flags, so they're captured here
      const shooterId = turn.shooter_id || turn.shooter?.player_id || turn.shooter;
      const shooterData = playerMap[shooterId];
      const lookupSucceeded = !!shooterData;
      
      // ✅ DIAGNOSTIC: Track lookup failures
      if (ENABLE_FT_FG_DIAGNOSTICS && !lookupSucceeded && shooterId) {
        playerLookupFailures.push({
          eventType: resultType === 'MAKE' ? 'MADE_FG' : 'MISSED_FG',
          turnIndex: index,
          shooterId: shooterId,
          fallbackUsed: turn.shooter || 'Unknown',
          inPlayerMap: false,
          playerMapKeys: Object.keys(playerMap).slice(0, 10) // First 10 for reference
        });
      }
      
      const finalShooterData = shooterData || { name: turn.shooter || 'Unknown', jersey: '', team: 'home', photo: null };
      
      // ✅ FIX: Use turn.offense_team_id to determine team (shooter is on offense)
      const playerTeam = getPlayerTeam(shooterId, finalShooterData.team);
      
      // Determine shot type (2-pt or 3-pt)
      const points = turn.points || 0;
      const shotType = points === 3 ? '3-pt' : '2-pt';
      
      // Check if this is a Fast Break shot (for prefix display)
      const isFastBreak = turn.fast_break === true || turn.offensive_state === 'FAST_BREAK' || 
                         turn.current_turn === 'FAST_BREAK';
      
      eventResults.push({
        timeRemaining,
        playerName: finalShooterData.name,
        playerJersey: finalShooterData.jersey,
        playerTeam: playerTeam,
        resultType: resultType,
        eventType: 'SHOT',
        shotType,
        isFastBreak,
        homeScore,
        awayScore,
        playerId: shooterId, // Store playerId for made shot images
        playerPhoto: finalShooterData.photo || null, // Store player photo for made shot images
        lookupSucceeded: lookupSucceeded // ✅ DIAGNOSTIC: Track lookup success
      });
    } else if (resultType === 'PUTBACK_MAKE' || resultType === 'PUTBACK_MISS') {
      // OREB putback attempts
      const shooterId = turn.shooter_id || turn.shooter?.player_id || turn.shooter || turn.rebounderId;
      let shooterData = playerMap[shooterId];
      
      // ✅ FIX: If not found in playerMap, try to find player in players array or use fallback name
      if (!shooterData && shooterId) {
        // Try to find player in players array (try multiple ID formats)
        const foundPlayer = players.find(p => 
          p.playerId === shooterId || 
          p.player_id === shooterId || 
          String(p.playerId) === String(shooterId) ||
          String(p.player_id) === String(shooterId)
        );
        if (foundPlayer) {
          // ✅ FIX: Handle jersey number 0 - use explicit checks to preserve 0
          let jersey = '';
          if (typeof foundPlayer.jersey === 'number') {
            jersey = foundPlayer.jersey; // Preserve 0
          } else if (foundPlayer.jersey !== undefined && foundPlayer.jersey !== null && foundPlayer.jersey !== '') {
            jersey = foundPlayer.jersey;
          } else if (typeof foundPlayer.jerseyNumber === 'number') {
            jersey = foundPlayer.jerseyNumber; // Preserve 0
          } else if (foundPlayer.jerseyNumber !== undefined && foundPlayer.jerseyNumber !== null && foundPlayer.jerseyNumber !== '') {
            jersey = foundPlayer.jerseyNumber;
          } else if (typeof foundPlayer.jersey_number === 'number') {
            jersey = foundPlayer.jersey_number; // Preserve 0
          } else if (foundPlayer.jersey_number !== undefined && foundPlayer.jersey_number !== null && foundPlayer.jersey_number !== '') {
            jersey = foundPlayer.jersey_number;
          }
          
          shooterData = {
            name: foundPlayer.name || 'Unknown',
            jersey: jersey,
            team_id: foundPlayer.team_id,
            photo: foundPlayer.photo || null
          };
        }
      }
      
      // ✅ FIX: Final fallback - use turn.shooter_name if available, check if turn.shooter is an ID
      if (!shooterData) {
        const fallbackName = turn.shooter_name || turn.shooter || 'Unknown';
        // If turn.shooter looks like an ID (UUID format with dashes and long length), don't use it as name
        const isLikelyId = fallbackName && typeof fallbackName === 'string' && 
                          (fallbackName.includes('-') && fallbackName.length > 20) ||
                          (fallbackName.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i));
        shooterData = {
          name: isLikelyId ? (turn.shooter_name || 'Unknown') : fallbackName,
          jersey: '',
          team_id: null,
          photo: null
        };
      }
      
      // ✅ FIX: Use turn.offense_team_id to determine team (shooter is on offense)
      const playerTeam = getPlayerTeam(shooterId, shooterData.team);
      
      const points = turn.points || 0;
      const shotType = points === 3 ? '3-pt' : '2-pt';
      
      eventResults.push({
        timeRemaining,
        playerName: shooterData.name,
        playerJersey: shooterData.jersey,
        playerTeam: playerTeam,
        resultType: resultType === 'PUTBACK_MAKE' ? 'MAKE' : 'MISS',
        eventType: 'OREB_PUTBACK',
        shotType,
        isFastBreak: false,
        homeScore,
        awayScore,
        playerId: shooterId, // Store playerId for made shot images
        playerPhoto: shooterData.photo || null // Store player photo for made shot images (safe access)
      });
    } else if (resultType === 'FREE_THROW') {
      // Free throws (made or missed based on points)
      const shooterId = turn.shooter_id || turn.shooter?.player_id || turn.shooter;
      const shooterData = playerMap[shooterId] || { name: turn.shooter || 'Unknown', jersey: '', team: 'home', photo: null };
      
      // ✅ FIX: Use turn.offense_team_id to determine team (shooter is on offense)
      const playerTeam = getPlayerTeam(shooterId, shooterData.team);
      
      const turnPoints = turn.points || 0;
      const made = turnPoints > 0;
      
      // ✅ DEBUG: Log free throw processing
      console.log('🏀 [FREE THROW DEBUG] Processing free throw:', {
        turnIndex: index,
        timeRemaining,
        shooterId,
        shooterName: shooterData.name,
        turnPoints,
        made,
        resultType: made ? 'MAKE' : 'MISS',
        homeScore,
        awayScore,
        turn: turn
      });
      
      eventResults.push({
        timeRemaining,
        playerName: shooterData.name,
        playerJersey: shooterData.jersey,
        playerTeam: playerTeam,
        resultType: made ? 'MAKE' : 'MISS',
        eventType: 'FREE_THROW',
        shotType: 'free throw',
        isFastBreak: false,
        homeScore,
        awayScore,
        playerId: shooterId, // Store playerId for made shot images
        playerPhoto: shooterData.photo || null // Store player photo for made shot images (safe access)
      });
    } else if (resultType === 'FOUL') {
      // Fouls
      // ✅ FIX: Backend sends foul_player_id, not fouler_id
      const foulerId = turn.foul_player_id || turn.fouler_id || turn.ball_handler || turn.shooter_id;
      const foulerData = playerMap[foulerId] || { name: turn.fouler || turn.ball_handler || 'Unknown', jersey: '', team: 'home' };
      
      // ✅ FIX: Use turn.offense_team_id if fouler is ball_handler, otherwise use playerData.team
      const playerTeam = getPlayerTeam(foulerId, foulerData.team);
      
      eventResults.push({
        timeRemaining,
        playerName: foulerData.name,
        playerJersey: foulerData.jersey,
        playerTeam: playerTeam,
        resultType: 'FOUL',
        eventType: 'FOUL',
        shotType: null,
        isFastBreak: false,
        homeScore,
        awayScore
      });
    } else if (resultType === 'DEAD BALL' || resultType === 'TURNOVER') {
      // Dead ball turnovers
      const victimId = turn.victim_id || turn.ball_handler || turn.shooter_id;
      const victimData = playerMap[victimId] || { name: turn.victim_name || turn.ball_handler || 'Unknown', jersey: '', team: 'home' };
      
      // ✅ FIX: Use turn.offense_team_id to determine team (victim is on offense)
      const playerTeam = getPlayerTeam(victimId, victimData.team);
      
      eventResults.push({
        timeRemaining,
        playerName: victimData.name,
        playerJersey: victimData.jersey,
        playerTeam: playerTeam,
        resultType: 'TURNOVER',
        eventType: 'DEAD_BALL',
        shotType: null,
        isFastBreak: false,
        homeScore,
        awayScore
      });
    } else if (resultType === 'STEAL') {
      // Steals
      const stealerId = turn.stealer_id || turn.ball_handler;
      // ✅ FIX: Try multiple ID formats and fallback to stealer_name
      // playerMap uses player.playerId as key, but stealer_id might be in different format
      let stealerData = playerMap[stealerId];
      if (!stealerData && stealerId) {
        // Try string conversion (in case of type mismatch)
        stealerData = playerMap[String(stealerId)];
      }
      // If still not found, try to find player by searching players array
      if (!stealerData && stealerId) {
        const foundPlayer = players.find(p => p.playerId === stealerId || p.playerId === String(stealerId) || p.player_id === stealerId);
        if (foundPlayer) {
          // ✅ FIX: Handle jersey number 0 - use explicit checks to preserve 0
          let jersey = '';
          if (typeof foundPlayer.jersey === 'number') {
            jersey = foundPlayer.jersey; // Preserve 0
          } else if (foundPlayer.jersey !== undefined && foundPlayer.jersey !== null && foundPlayer.jersey !== '') {
            jersey = foundPlayer.jersey;
          } else if (typeof foundPlayer.jerseyNumber === 'number') {
            jersey = foundPlayer.jerseyNumber; // Preserve 0
          } else if (foundPlayer.jerseyNumber !== undefined && foundPlayer.jerseyNumber !== null && foundPlayer.jerseyNumber !== '') {
            jersey = foundPlayer.jerseyNumber;
          } else if (typeof foundPlayer.jersey_number === 'number') {
            jersey = foundPlayer.jersey_number; // Preserve 0
          } else if (foundPlayer.jersey_number !== undefined && foundPlayer.jersey_number !== null && foundPlayer.jersey_number !== '') {
            jersey = foundPlayer.jersey_number;
          }
          
          stealerData = {
            name: foundPlayer.name || 'Unknown',
            jersey: jersey,
            team_id: foundPlayer.team_id
          };
        }
      }
      // Final fallback: use turn.stealer_name if available
      if (!stealerData) {
        stealerData = { 
          name: turn.stealer_name || 'Unknown', 
          jersey: '', 
          team_id: null 
        };
      }
      
      // ✅ FIX: Use turn.offense_team_id to determine team (stealer is on defense, opposite of offense)
      const playerTeam = getPlayerTeam(stealerId, stealerData.team_id ? null : 'home');
      
      eventResults.push({
        timeRemaining,
        playerName: stealerData.name,
        playerJersey: stealerData.jersey,
        playerTeam: playerTeam,
        resultType: 'STEAL',
        eventType: 'STEAL',
        shotType: null,
        isFastBreak: false,
        homeScore,
        awayScore
      });
    }
  });
  
  // Show popup before processing events
  popup.classList.remove('hidden');
  console.log('🔍 [SIM QUARTER] Popup shown, processing', eventResults.length, 'events');
  
  // Clear content
  contentEl.innerHTML = '';
  
  // ✅ NEW: Get scoreboard elements for real-time updates (SS&S: same pattern as gameScene.js)
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  
  // Get initial scores (start of quarter) - use start_box_score if available, otherwise use score from first turn
  let displayHomeScore = 0;
  let displayAwayScore = 0;
  
  if (lastSummary.start_box_score) {
    displayHomeScore = lastSummary.start_box_score.home_score || 0;
    displayAwayScore = lastSummary.start_box_score.away_score || 0;
  } else if (turns.length > 0 && turns[0].score) {
    // Fallback: use first turn's score as starting point
    const firstTurnScore = turns[0].score;
    displayHomeScore = typeof firstTurnScore[homeTeamName] === 'number' ? firstTurnScore[homeTeamName] : 
                      (typeof firstTurnScore[homeTeam] === 'number' ? firstTurnScore[homeTeam] : 0);
    displayAwayScore = typeof firstTurnScore[awayTeamName] === 'number' ? firstTurnScore[awayTeamName] : 
                       (typeof firstTurnScore[awayTeam] === 'number' ? firstTurnScore[awayTeam] : 0);
  }
  
  // ✅ NEW: Get clock and quarter elements for real-time updates
  const clockEl = document.getElementById('game-clock');
  const quarterEl = document.getElementById('quarter');
  
  // ✅ NEW: Update scoreboard quarter to show the quarter being simulated
  if (quarterEl) {
    quarterEl.textContent = periodLabel;
  }
  
  // ✅ NEW: Initialize scoreboard with starting scores
  if (homeScoreEl) homeScoreEl.textContent = displayHomeScore;
  if (awayScoreEl) awayScoreEl.textContent = displayAwayScore;
  
  // ✅ DIAGNOSTIC: Track initial scoreboard setup
  if (ENABLE_FT_FG_DIAGNOSTICS) {
    scoreboardUpdates.push({
      type: 'INITIAL',
      turnIndex: null,
      timeRemaining: null,
      homeScore: displayHomeScore,
      awayScore: displayAwayScore,
      homeScoreChange: 0,
      awayScoreChange: 0,
      source: 'initial_setup',
      eventType: null,
      eventResultType: null
    });
  }
  
  // ✅ DIAGNOSTIC: Track score increments and printed events for debugging
  const ENABLE_TEXT_SCROLL_DIAGNOSTICS = false; // Set to true to enable
  const scoreIncrements = [];
  const printedEvents = [];
  let previousHomeScore = displayHomeScore;
  let previousAwayScore = displayAwayScore;
  
  // ✅ FIX: Track matched events to prevent duplicate matches (especially for FTs with same time)
  const matchedEventIndices = new Set();
  
  // Process all turns to update clock in real-time, create entries for all event types
  for (let i = 0; i < turns.length; i++) {
    const turn = turns[i];
    
    // ✅ NEW: Update clock with each turn's time_remaining (all turns)
    if (clockEl && (turn.time_remaining !== undefined || turn.clock || turn.game_clock)) {
      let timeValue = turn.time_remaining || turn.clock || turn.game_clock;
      // Convert seconds to MM:SS format if needed
      if (typeof timeValue === 'number') {
        const minutes = Math.floor(timeValue / 60);
        const seconds = Math.floor(timeValue % 60);
        timeValue = `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      clockEl.textContent = timeValue;
    }
    
    // ✅ DIAGNOSTIC: Track score increments
    if (ENABLE_TEXT_SCROLL_DIAGNOSTICS) {
      const turnScore = turn.score || {};
      const currentHomeScore = typeof turnScore[homeTeamName] === 'number' ? turnScore[homeTeamName] : 
                              (typeof turnScore[homeTeam] === 'number' ? turnScore[homeTeam] : previousHomeScore);
      const currentAwayScore = typeof turnScore[awayTeamName] === 'number' ? turnScore[awayTeamName] : 
                              (typeof turnScore[awayTeam] === 'number' ? turnScore[awayTeam] : previousAwayScore);
      
      const homeScoreChange = currentHomeScore - previousHomeScore;
      const awayScoreChange = currentAwayScore - previousAwayScore;
      
      if (homeScoreChange > 0 || awayScoreChange > 0) {
        scoreIncrements.push({
          turnIndex: i,
          timeRemaining: turn.time_remaining || turn.clock || turn.game_clock,
          homeScoreChange,
          awayScoreChange,
          newHomeScore: currentHomeScore,
          newAwayScore: currentAwayScore,
          resultType: turn.result_type,
          points: turn.points || 0,
          shooterId: turn.shooter_id || turn.shooter?.player_id || turn.shooter,
          turn: turn
        });
        previousHomeScore = currentHomeScore;
        previousAwayScore = currentAwayScore;
      }
    }
    
    // Find corresponding event in eventResults array
    // Match by time and result type, but handle special cases (FREE_THROW, PUTBACK_MAKE/MISS)
    const event = eventResults.find(e => {
      // Handle PUTBACK_MAKE/MISS first - they may not have time_remaining, so be more flexible with matching
      if (turn.result_type === 'PUTBACK_MAKE' || turn.result_type === 'PUTBACK_MISS') {
        const expectedResultType = turn.result_type === 'PUTBACK_MAKE' ? 'MAKE' : 'MISS';
        
        // Match by event type and result type
        if (e.eventType === 'OREB_PUTBACK' && e.resultType === expectedResultType) {
          // If time is available, try to match it. If not, still allow the match (putbacks may not have time)
          const turnTime = turn.time_remaining || turn.clock || turn.game_clock;
          if (turnTime) {
            // Time is available, require match
            return e.timeRemaining === turnTime;
          } else {
            // No time available, match by type only (for putbacks without time_remaining)
            return true;
          }
        }
        return false;
      }
      
      // For other events, require time match
      const timeMatch = e.timeRemaining === (turn.time_remaining || turn.clock || turn.game_clock);
      if (!timeMatch) return false;
      
      // Handle special result type mappings
      if (turn.result_type === 'FREE_THROW') {
        // ✅ FIX: Match free throws more specifically by result type (MAKE/MISS) to handle multiple FTs at same time
        const turnPoints = turn.points || 0;
        const expectedMade = turnPoints > 0;
        const expectedResultType = expectedMade ? 'MAKE' : 'MISS';
        
        // Match by event type AND result type AND time, and ensure not already matched
        const eventIndex = eventResults.indexOf(e);
        const isMatch = e.eventType === 'FREE_THROW' && 
                       e.resultType === expectedResultType && 
                       !matchedEventIndices.has(eventIndex);
        
        // ✅ DEBUG: Log free throw matching
        if (e.eventType === 'FREE_THROW') {
          console.log('🏀 [FREE THROW DEBUG] Matching free throw:', {
            turnIndex: i,
            timeRemaining: turn.time_remaining || turn.clock || turn.game_clock,
            turnPoints,
            expectedResultType: expectedResultType,
            matchedEventResultType: e.resultType,
            matchedEventPlayerName: e.playerName,
            matchedEventTimeRemaining: e.timeRemaining,
            eventIndex: eventIndex,
            alreadyMatched: matchedEventIndices.has(eventIndex),
            match: isMatch ? '✅ CORRECT' : '❌ NO MATCH'
          });
        }
        
        return isMatch;
      } else {
        return e.resultType === turn.result_type || e.eventType === turn.result_type;
      }
    });
    
    if (event) {
      // ✅ FIX: Mark this event as matched to prevent duplicate matches (especially for FTs with same time)
      const eventIndex = eventResults.indexOf(event);
      if (eventIndex !== -1) {
        matchedEventIndices.add(eventIndex);
      }
      
      // Update scores if they changed
      if (event.homeScore !== displayHomeScore || event.awayScore !== displayAwayScore) {
        const homeScoreChange = event.homeScore - displayHomeScore;
        const awayScoreChange = event.awayScore - displayAwayScore;
        
        displayHomeScore = event.homeScore;
        displayAwayScore = event.awayScore;
        
        // ✅ NEW: Update scoreboard in real-time (SS&S: same pattern as gameScene.js updateScoreboard)
        if (homeScoreEl) homeScoreEl.textContent = displayHomeScore;
        if (awayScoreEl) awayScoreEl.textContent = displayAwayScore;
        
        // ✅ DIAGNOSTIC: Track scoreboard update
        if (ENABLE_FT_FG_DIAGNOSTICS) {
          scoreboardUpdates.push({
            type: 'UPDATE',
            turnIndex: i,
            timeRemaining: event.timeRemaining,
            homeScore: displayHomeScore,
            awayScore: displayAwayScore,
            homeScoreChange: homeScoreChange,
            awayScoreChange: awayScoreChange,
            source: 'event_processing',
            eventType: event.eventType,
            eventResultType: event.resultType,
            playerName: event.playerName,
            playerJersey: event.playerJersey,
            shotType: event.shotType,
            pointsScored: event.resultType === 'MAKE' ? (event.shotType === '3-pt' ? 3 : event.shotType === 'free throw' ? 1 : 2) : 0
          });
        }
      }
      
      // Create event entry
      const entry = document.createElement('div');
      
      // Determine team color
      const teamColor = event.playerTeam === 'home' ? homeColor : awayColor;
      
      // Format time (convert seconds to MM:SS if needed)
      let timeDisplay = event.timeRemaining;
      if (typeof event.timeRemaining === 'number') {
        const minutes = Math.floor(event.timeRemaining / 60);
        const seconds = Math.floor(event.timeRemaining % 60);
        timeDisplay = `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      
      // ✅ FIX: Format jersey number - handle 0 as valid jersey number
      // Check for null/undefined/empty string, but allow 0
      const jerseyDisplay = (event.playerJersey !== undefined && event.playerJersey !== null && event.playerJersey !== '') 
        ? ` (#${event.playerJersey})` 
        : '';
      
      // Determine CSS class based on event type (only made shots get background colors)
      let eventClass = 'sim-quarter-shot-entry';
      if (event.resultType === 'MAKE') {
        if (event.eventType === 'FREE_THROW') {
          eventClass += ' event-made-ft'; // Made free throw - yellow
        } else if (event.eventType === 'SHOT' || event.eventType === 'OREB_PUTBACK') {
          if (event.shotType === '3-pt') {
            eventClass += ' event-made-3pt'; // Made 3-point shot - blue
          } else {
            eventClass += ' event-made-2pt'; // Made 2-point shot - green
          }
        }
      }
      // All other events (missed shots, fouls, steals, turnovers) get default grey (no background)
      
      entry.className = eventClass;
      
      // Build event text based on event type
      let eventText = '';
      let prefix = '';
      
      if (event.eventType === 'SHOT') {
        // Regular shot or Fast Break shot (FCP/HCT shots also included but no prefix)
        if (event.isFastBreak) {
          prefix = '[Fast Break] ';
        }
        const resultText = event.resultType === 'MAKE' ? 'makes' : 'misses';
        eventText = `${resultText} the ${event.shotType} shot.`;
      } else if (event.eventType === 'OREB_PUTBACK') {
        // OREB putback
        prefix = '[Off Rebound] ';
        const resultText = event.resultType === 'MAKE' ? 'makes' : 'misses';
        eventText = `${resultText} the ${event.shotType} shot.`;
      } else if (event.eventType === 'FREE_THROW') {
        // Free throw
        const resultText = event.resultType === 'MAKE' ? 'makes' : 'misses';
        eventText = `${resultText} the ${event.shotType}.`;
      } else if (event.eventType === 'FOUL') {
        // Foul
        eventText = 'commits a foul.';
      } else if (event.eventType === 'DEAD_BALL') {
        // Dead ball turnover
        eventText = 'turnover (dead ball).';
      } else if (event.eventType === 'STEAL') {
        // Steal
        eventText = 'steals the ball.';
      }
      
      // Create content div (SS&S: Use DOM element creation like announcement system)
      const contentDiv = document.createElement('div');
      contentDiv.className = 'sim-quarter-entry-content';
      
      // Create time span
      const timeSpan = document.createElement('span');
      timeSpan.style.color = '#374151';
      timeSpan.textContent = `[${timeDisplay}]: `;
      contentDiv.appendChild(timeSpan);
      
      // Create prefix span if needed
      if (prefix) {
        const prefixSpan = document.createElement('span');
        prefixSpan.style.color = '#374151';
        prefixSpan.textContent = prefix;
        contentDiv.appendChild(prefixSpan);
      }
      
      // Create player name span
      const playerNameSpan = document.createElement('span');
      playerNameSpan.style.color = teamColor;
      playerNameSpan.style.fontWeight = 'bold';
      playerNameSpan.textContent = `${event.playerName}${jerseyDisplay}`;
      contentDiv.appendChild(playerNameSpan);
      
      // Create event text span
      const eventTextSpan = document.createElement('span');
      eventTextSpan.style.color = '#111827';
      eventTextSpan.textContent = ` ${eventText}`;
      contentDiv.appendChild(eventTextSpan);
      
      // Append content div to entry
      entry.appendChild(contentDiv);
      
      // Build player image for made shots (SS&S: Use DOM element creation like announcement system)
      if (event.resultType === 'MAKE' && (event.eventType === 'SHOT' || event.eventType === 'OREB_PUTBACK' || event.eventType === 'FREE_THROW')) {
        // SS&S: Use same environment-aware path logic as announcement system
        const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
        
        // Normalize playerPhoto path based on environment
        let playerPhoto = event.playerPhoto;
        if (playerPhoto) {
          // If we have a photo path, normalize it for the current environment
          if (!isLocalhost && playerPhoto.startsWith('/static/')) {
            // Production: remove /static/ prefix
            playerPhoto = playerPhoto.replace('/static', '');
          } else if (isLocalhost && !playerPhoto.startsWith('/static/') && playerPhoto.startsWith('/images/')) {
            // Localhost: add /static/ prefix if missing
            playerPhoto = '/static' + playerPhoto;
          }
        } else if (event.playerId) {
          // Construct path based on environment (fallback if no photo provided)
          const staticPrefix = isLocalhost ? '/static' : '';
          playerPhoto = `${staticPrefix}/images/players/${event.playerId}.png`;
        }
        
        if (playerPhoto) {
          const img = document.createElement('img');
          img.src = playerPhoto;
          img.alt = event.playerName;
          img.className = 'sim-quarter-player-image';
          img.onerror = () => {
            img.style.display = 'none';
          };
          entry.appendChild(img);
        }
      }
      
      contentEl.appendChild(entry);
      
      // ✅ DIAGNOSTIC: Track printed events
      if (ENABLE_TEXT_SCROLL_DIAGNOSTICS) {
        const pointsScored = event.resultType === 'MAKE' ? (event.shotType === '3-pt' ? 3 : event.shotType === 'free throw' ? 1 : 2) : 0;
        printedEvents.push({
          turnIndex: i,
          timeRemaining: event.timeRemaining,
          eventType: event.eventType,
          resultType: event.resultType,
          pointsScored,
          playerName: event.playerName,
          playerJersey: event.playerJersey,
          shotType: event.shotType,
          homeScore: event.homeScore,
          awayScore: event.awayScore,
          isFastBreak: event.isFastBreak
        });
      }
      
      // ✅ DIAGNOSTIC: Track ALL printed events for FT/FG analysis (with player ID lookup info)
      if (ENABLE_FT_FG_DIAGNOSTICS) {
        // Calculate points scored based on result type and shot type
        const pointsScored = event.resultType === 'MAKE' ? 
          (event.shotType === '3-pt' ? 3 : event.shotType === 'free throw' ? 1 : 2) : 0;
        
        const printedEvent = {
          turnIndex: i,
          timeRemaining: event.timeRemaining,
          eventType: event.eventType,
          resultType: event.resultType,
          playerId: event.playerId, // The shooter_id from the turn
          playerName: event.playerName, // The name actually printed
          playerJersey: event.playerJersey,
          shotType: event.shotType,
          pointsScored: pointsScored, // ✅ FIX: Add points scored calculation
          homeScore: event.homeScore,
          awayScore: event.awayScore,
          isFastBreak: event.isFastBreak,
          // Track lookup details
          lookupSucceeded: !!playerMap[event.playerId],
          playerMapHasId: event.playerId ? (event.playerId in playerMap) : false,
          fallbackUsed: !playerMap[event.playerId] ? 'Yes (playerMap lookup failed)' : 'No'
        };
        
        allPrintedEvents.push(printedEvent);
        
        // Also track in specific arrays for matching
        if (event.eventType === 'FREE_THROW') {
          printedFTEvents.push(printedEvent);
        } else if (event.eventType === 'SHOT' && event.resultType === 'MAKE') {
          printedMadeFGEvents.push(printedEvent);
        }
      }
      
      // Scroll to bottom
      const scrollContainer = popup.querySelector('.sim-quarter-scroll-container');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
      
      // 2 second delay for real-time feel (users experience each event)
      await new Promise(resolve => setTimeout(resolve, 2000));
    } else {
      // Not an event we display, just update clock with small delay
      await new Promise(resolve => setTimeout(resolve, 200)); // Small delay for clock updates
    }
  }
  
  // If no events, show message
  if (eventResults.length === 0) {
    const noShotsMsg = document.createElement('div');
    noShotsMsg.className = 'sim-quarter-shot-entry';
    noShotsMsg.style.textAlign = 'center';
    noShotsMsg.style.color = '#111827';
    noShotsMsg.textContent = 'No shots in this quarter.';
    contentEl.appendChild(noShotsMsg);
  }
  
  // Wait a bit before navigating (2 seconds after last shot or message)
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // ✅ FIX: Update scoreboard with final scores from lastSummary (authoritative source)
  // This ensures the scoreboard shows correct final scores before navigation
  // Use lastSummary.score (dict with team names as keys) as single source of truth
  if (lastSummary.score) {
    const finalHomeScore = typeof lastSummary.score[homeTeamName] === 'number' ? lastSummary.score[homeTeamName] : 
                           (typeof lastSummary.score[homeTeam] === 'number' ? lastSummary.score[homeTeam] : displayHomeScore);
    const finalAwayScore = typeof lastSummary.score[awayTeamName] === 'number' ? lastSummary.score[awayTeamName] : 
                           (typeof lastSummary.score[awayTeam] === 'number' ? lastSummary.score[awayTeam] : displayAwayScore);
    
    const finalHomeScoreChange = finalHomeScore - displayHomeScore;
    const finalAwayScoreChange = finalAwayScore - displayAwayScore;
    
    if (homeScoreEl) homeScoreEl.textContent = finalHomeScore;
    if (awayScoreEl) awayScoreEl.textContent = finalAwayScore;
    
    // ✅ DIAGNOSTIC: Track final scoreboard update
    if (ENABLE_FT_FG_DIAGNOSTICS && (finalHomeScoreChange !== 0 || finalAwayScoreChange !== 0)) {
      scoreboardUpdates.push({
        type: 'FINAL',
        turnIndex: null,
        timeRemaining: null,
        homeScore: finalHomeScore,
        awayScore: finalAwayScore,
        homeScoreChange: finalHomeScoreChange,
        awayScoreChange: finalAwayScoreChange,
        source: 'final_update',
        eventType: null,
        eventResultType: null,
        previousHomeScore: displayHomeScore,
        previousAwayScore: displayAwayScore
      });
    }
  }
  
  // Hide popup before navigation
  popup.classList.add('hidden');
  
  // ✅ NEW: Show game control buttons when Sim Quarter popup is hidden
  if (gameControlsEl) {
    gameControlsEl.style.display = '';
  }
  
  // ✅ DIAGNOSTIC: Collect FT/FG events from turns for analysis (arrays already initialized above)
  if (ENABLE_FT_FG_DIAGNOSTICS) {
    // Collect all free throw and made FG events from turns for analysis
    turns.forEach((turn, index) => {
      if (turn.result_type === 'FREE_THROW') {
        const turnPoints = turn.points || 0;
        const made = turnPoints > 0;
        const shooterId = turn.shooter_id || turn.shooter?.player_id || turn.shooter;
        const shooterData = playerMap[shooterId];
        const lookupSucceeded = !!shooterData;
        const fallbackName = turn.shooter || 'Unknown';
        
        // Track lookup failures
        if (!lookupSucceeded) {
          playerLookupFailures.push({
            eventType: 'FREE_THROW',
            turnIndex: index,
            shooterId: shooterId,
            fallbackUsed: fallbackName,
            inPlayerMap: false,
            playerMapKeys: Object.keys(playerMap).slice(0, 10) // First 10 for reference
          });
        }
        
        freeThrowEvents.push({
          turnIndex: index,
          timeRemaining: turn.time_remaining || turn.clock || turn.game_clock,
          shooterId: shooterId,
          shooterName: shooterData?.name || turn.shooter_name || turn.shooter || 'Unknown',
          turnPoints,
          made,
          expectedResultType: made ? 'MAKE' : 'MISS',
          score: turn.score || {},
          lookupSucceeded: lookupSucceeded,
          fallbackUsed: !lookupSucceeded ? fallbackName : null,
          turn: turn
        });
      } else if (turn.result_type === 'MAKE' && turn.points && turn.points > 0) {
        // Only track actual made field goals (not free throws)
        const turnPoints = turn.points || 0;
        const shooterId = turn.shooter_id || turn.shooter?.player_id || turn.shooter;
        const shooterData = playerMap[shooterId];
        const lookupSucceeded = !!shooterData;
        const fallbackName = turn.shooter || 'Unknown';
        
        // Track lookup failures
        if (!lookupSucceeded) {
          playerLookupFailures.push({
            eventType: 'MADE_FG',
            turnIndex: index,
            shooterId: shooterId,
            fallbackUsed: fallbackName,
            inPlayerMap: false,
            playerMapKeys: Object.keys(playerMap).slice(0, 10) // First 10 for reference
          });
        }
        
        madeFGEvents.push({
          turnIndex: index,
          timeRemaining: turn.time_remaining || turn.clock || turn.game_clock,
          shooterId: shooterId,
          shooterName: shooterData?.name || turn.shooter_name || turn.shooter || 'Unknown',
          turnPoints,
          score: turn.score || {},
          lookupSucceeded: lookupSucceeded,
          fallbackUsed: !lookupSucceeded ? fallbackName : null,
          turn: turn
        });
      }
    });
    
    // After processing all events, collect printed free throws and made FGs
    // This happens in the event processing loop below
  }
  
  // ✅ DIAGNOSTIC: Comprehensive made shot tracking - link made shots → prints → scoreboard updates
  if (ENABLE_FT_FG_DIAGNOSTICS) {
    const ftMismatches = [];
    const fgMismatches = [];
    const madeShotVerifications = []; // ✅ NEW: Track every made shot with print + scoreboard verification
    const unmatchedPrints = []; // ✅ NEW: Track prints that don't link to made shots
    
    // ✅ IMPROVED: Match free throws using turnIndex as primary (more explicit than timing)
    for (const ft of freeThrowEvents) {
      // Primary match: turnIndex (most reliable)
      let printedFT = printedFTEvents.find(pft => pft.turnIndex === ft.turnIndex);
      
      // Fallback: time + player name (only if turnIndex didn't match)
      if (!printedFT) {
        printedFT = printedFTEvents.find(pft => 
          pft.timeRemaining === ft.timeRemaining && pft.playerName === ft.shooterName
        );
      }
      
      // Find corresponding scoreboard update
      const scoreboardUpdate = scoreboardUpdates.find(su => 
        su.turnIndex === ft.turnIndex && su.type === 'UPDATE'
      );
      
      if (printedFT) {
        // Check if result types match
        if (printedFT.resultType !== ft.expectedResultType) {
          ftMismatches.push({
            type: 'RESULT_TYPE_MISMATCH',
            turnIndex: ft.turnIndex,
            timeRemaining: ft.timeRemaining,
            shooterName: ft.shooterName,
            expectedResultType: ft.expectedResultType,
            printedResultType: printedFT.resultType,
            turnPoints: ft.turnPoints,
            made: ft.made
          });
        }
        
        // ✅ NEW: Verify made free throw has scoreboard update
        if (ft.made && ft.turnPoints > 0) {
          const hasScoreboardUpdate = !!scoreboardUpdate;
          const expectedScoreChange = 1;
          const actualScoreChange = scoreboardUpdate ? 
            (scoreboardUpdate.homeScoreChange + scoreboardUpdate.awayScoreChange) : 0;
          
          madeShotVerifications.push({
            type: 'FREE_THROW_MAKE',
            turnIndex: ft.turnIndex,
            timeRemaining: ft.timeRemaining,
            shooterName: ft.shooterName,
            shooterId: ft.shooterId,
            turnPoints: ft.turnPoints,
            hasPrint: true,
            printResultType: printedFT.resultType,
            hasScoreboardUpdate: hasScoreboardUpdate,
            expectedScoreChange: expectedScoreChange,
            actualScoreChange: actualScoreChange,
            scoreboardMatches: hasScoreboardUpdate && actualScoreChange === expectedScoreChange,
            scoreboardUpdate: scoreboardUpdate || null
          });
        }
      } else {
        // Free throw not printed at all
        ftMismatches.push({
          type: 'NOT_PRINTED',
          turnIndex: ft.turnIndex,
          timeRemaining: ft.timeRemaining,
          shooterName: ft.shooterName,
          expectedResultType: ft.expectedResultType,
          turnPoints: ft.turnPoints,
          made: ft.made
        });
        
        // ✅ NEW: Track made FT without print
        if (ft.made && ft.turnPoints > 0) {
          madeShotVerifications.push({
            type: 'FREE_THROW_MAKE',
            turnIndex: ft.turnIndex,
            timeRemaining: ft.timeRemaining,
            shooterName: ft.shooterName,
            shooterId: ft.shooterId,
            turnPoints: ft.turnPoints,
            hasPrint: false,
            hasScoreboardUpdate: !!scoreboardUpdate,
            expectedScoreChange: 1,
            actualScoreChange: scoreboardUpdate ? 
              (scoreboardUpdate.homeScoreChange + scoreboardUpdate.awayScoreChange) : 0,
            scoreboardMatches: false,
            scoreboardUpdate: scoreboardUpdate || null
          });
        }
      }
    }
    
    // ✅ IMPROVED: Match made FGs and verify print + scoreboard update
    for (const fg of madeFGEvents) {
      // Primary match: turnIndex (most reliable)
      let printedFG = printedMadeFGEvents.find(pfg => pfg.turnIndex === fg.turnIndex);
      
      // Fallback: time + player name (only if turnIndex didn't match)
      if (!printedFG) {
        printedFG = printedMadeFGEvents.find(pfg => 
          pfg.timeRemaining === fg.timeRemaining && pfg.playerName === fg.shooterName
        );
      }
      
      // Find corresponding scoreboard update
      const scoreboardUpdate = scoreboardUpdates.find(su => 
        su.turnIndex === fg.turnIndex && su.type === 'UPDATE'
      );
      
      const expectedScoreChange = fg.turnPoints; // 2 or 3 points
      const actualScoreChange = scoreboardUpdate ? 
        (scoreboardUpdate.homeScoreChange + scoreboardUpdate.awayScoreChange) : 0;
      
      if (printedFG) {
        // ✅ NEW: Verify made FG has scoreboard update
        madeShotVerifications.push({
          type: 'MADE_FG',
          turnIndex: fg.turnIndex,
          timeRemaining: fg.timeRemaining,
          shooterName: fg.shooterName,
          shooterId: fg.shooterId,
          turnPoints: fg.turnPoints,
          hasPrint: true,
          printResultType: printedFG.resultType,
          printPointsScored: printedFG.pointsScored,
          hasScoreboardUpdate: !!scoreboardUpdate,
          expectedScoreChange: expectedScoreChange,
          actualScoreChange: actualScoreChange,
          scoreboardMatches: !!scoreboardUpdate && actualScoreChange === expectedScoreChange,
          scoreboardUpdate: scoreboardUpdate || null
        });
      } else {
        // Made FG not printed
        fgMismatches.push({
          type: 'NOT_PRINTED',
          turnIndex: fg.turnIndex,
          timeRemaining: fg.timeRemaining,
          shooterName: fg.shooterName,
          turnPoints: fg.turnPoints
        });
        
        // ✅ NEW: Track made FG without print
        madeShotVerifications.push({
          type: 'MADE_FG',
          turnIndex: fg.turnIndex,
          timeRemaining: fg.timeRemaining,
          shooterName: fg.shooterName,
          shooterId: fg.shooterId,
          turnPoints: fg.turnPoints,
          hasPrint: false,
          hasScoreboardUpdate: !!scoreboardUpdate,
          expectedScoreChange: expectedScoreChange,
          actualScoreChange: actualScoreChange,
          scoreboardMatches: false,
          scoreboardUpdate: scoreboardUpdate || null
        });
      }
    }
    
    // ✅ NEW: Find prints that don't link to made shots (unmatched prints)
    // Check all printed made FGs
    for (const printedFG of printedMadeFGEvents) {
      const matchingMadeFG = madeFGEvents.find(fg => 
        fg.turnIndex === printedFG.turnIndex ||
        (fg.timeRemaining === printedFG.timeRemaining && fg.shooterName === printedFG.playerName)
      );
      
      if (!matchingMadeFG) {
        unmatchedPrints.push({
          type: 'MADE_FG_PRINT',
          turnIndex: printedFG.turnIndex,
          timeRemaining: printedFG.timeRemaining,
          playerName: printedFG.playerName,
          playerId: printedFG.playerId,
          resultType: printedFG.resultType,
          pointsScored: printedFG.pointsScored,
          shotType: printedFG.shotType,
          homeScore: printedFG.homeScore,
          awayScore: printedFG.awayScore
        });
      }
    }
    
    // Check all printed made free throws
    for (const printedFT of printedFTEvents) {
      if (printedFT.resultType === 'MAKE') {
        const matchingFT = freeThrowEvents.find(ft => 
          ft.turnIndex === printedFT.turnIndex ||
          (ft.timeRemaining === printedFT.timeRemaining && ft.shooterName === printedFT.playerName)
        );
        
        if (!matchingFT || !matchingFT.made) {
          unmatchedPrints.push({
            type: 'FREE_THROW_MAKE_PRINT',
            turnIndex: printedFT.turnIndex,
            timeRemaining: printedFT.timeRemaining,
            playerName: printedFT.playerName,
            playerId: printedFT.playerId,
            resultType: printedFT.resultType,
            pointsScored: printedFT.pointsScored,
            shotType: printedFT.shotType,
            homeScore: printedFT.homeScore,
            awayScore: printedFT.awayScore
          });
        }
      }
    }
    
    // Get game ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const gameId = urlParams.get('game_id');
    
    // Send diagnostic data to backend
    try {
      const diagnosticData = {
        gameId: gameId || 'unknown',
        quarter,
        homeTeam,
        awayTeam,
        timestamp: new Date().toISOString(),
        freeThrowEvents,
        madeFGEvents,
        printedFTEvents,
        printedMadeFGEvents,
        allPrintedEvents, // ✅ NEW: All printed events (not just FT/FG)
        ftMismatches,
        fgMismatches,
        madeShotVerifications, // ✅ NEW: Track every made shot with print + scoreboard verification
        unmatchedPrints, // ✅ NEW: Track prints that don't link to made shots
        playerLookupFailures, // ✅ NEW: Track when playerMap lookups fail
        playerMapStats, // ✅ NEW: PlayerMap statistics
        scoreboardUpdates, // ✅ NEW: Track every scoreboard update
        totalFreeThrows: freeThrowEvents.length,
        totalMadeFGs: madeFGEvents.length,
        totalPrintedFTs: printedFTEvents.length,
        totalPrintedMadeFGs: printedMadeFGEvents.length,
        totalAllPrintedEvents: allPrintedEvents.length,
        totalLookupFailures: playerLookupFailures.length,
        totalScoreboardUpdates: scoreboardUpdates.length, // ✅ NEW: Total scoreboard updates
        totalMadeShotVerifications: madeShotVerifications.length, // ✅ NEW: Total made shot verifications
        totalUnmatchedPrints: unmatchedPrints.length, // ✅ NEW: Total unmatched prints
        ftMismatchCount: ftMismatches.length,
        fgMismatchCount: fgMismatches.length
      };
      
      const response = await fetch(API_CONFIG.buildUrl('/api/diagnostics/ft-fg-analysis'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(diagnosticData)
      });
      
      if (response.ok) {
        const result = await response.json();
        
        // Download markdown file to user's computer
        if (result.markdownContent) {
          const blob = new Blob([result.markdownContent], { type: 'text/markdown' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = result.filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          
          console.log(`✅ [FT/FG DIAGNOSTIC] Analysis file downloaded: ${result.filename} (${result.ftMismatchCount || 0} FT mismatches, ${result.fgMismatchCount || 0} FG mismatches)`);
        }
      }
    } catch (error) {
      console.error('❌ [FT/FG DIAGNOSTIC] Failed to send diagnostic data:', error);
    }
  }
  
  // ✅ DIAGNOSTIC: Match score increments with printed events and send to backend
  if (ENABLE_TEXT_SCROLL_DIAGNOSTICS) {
    const mismatches = [];
    
    // Match each score increment with a printed event
    for (const scoreInc of scoreIncrements) {
      // Find matching printed event by turn index and points
      const matchingEvent = printedEvents.find(pe => 
        pe.turnIndex === scoreInc.turnIndex && 
        pe.pointsScored === (scoreInc.homeScoreChange + scoreInc.awayScoreChange)
      );
      
      if (!matchingEvent) {
        // No matching printed event found
        mismatches.push({
          type: 'MISSING_PRINT',
          scoreIncrement: {
            turnIndex: scoreInc.turnIndex,
            timeRemaining: scoreInc.timeRemaining,
            homeScoreChange: scoreInc.homeScoreChange,
            awayScoreChange: scoreInc.awayScoreChange,
            totalPoints: scoreInc.homeScoreChange + scoreInc.awayScoreChange,
            resultType: scoreInc.resultType,
            points: scoreInc.points,
            shooterId: scoreInc.shooterId
          }
        });
      }
    }
    
    // Get game ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const gameId = urlParams.get('game_id');
    
    // Send diagnostic data to backend
    try {
      const diagnosticData = {
        gameId: gameId || 'unknown',
        quarter,
        homeTeam,
        awayTeam,
        timestamp: new Date().toISOString(),
        scoreIncrements,
        printedEvents,
        mismatches,
        totalScoreIncrements: scoreIncrements.length,
        totalPrintedEvents: printedEvents.length,
        mismatchCount: mismatches.length
      };
      
      const response = await fetch(API_CONFIG.buildUrl('/api/diagnostics/sim-quarter'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(diagnosticData)
      });
      
      if (response.ok) {
        const result = await response.json();
        
        // Download markdown file to user's computer
        if (result.markdownContent) {
          const blob = new Blob([result.markdownContent], { type: 'text/markdown' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = result.filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          
          console.log(`✅ [DIAGNOSTIC] Diagnostic file downloaded: ${result.filename} (${result.mismatchCount} mismatches found)`);
        }
      }
    } catch (error) {
      console.error('❌ [DIAGNOSTIC] Failed to send diagnostic data:', error);
    }
  }
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
  // ✅ REFACTOR: Direct DOM update (same pattern as other scoreboard items)
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl) homeScoreEl.textContent = 0;
  if (awayScoreEl) awayScoreEl.textContent = 0;
}


async function fetchTeamRoster(teamName) {
  // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
  // Supports tournament_id and franchise_id query parameters
  const params = new URLSearchParams();
  if (mode === 'tournament' && tournamentId) {
    params.append('tournament_id', tournamentId);
  }
  if (mode === 'franchise' && franchiseId) {
    params.append('franchise_id', franchiseId);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const url = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(teamName)}${query}`);
  
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
  
  // ✅ REMOVED: Quarter transition debug logging (cluttering console)
  
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
    teamId, // ✅ SS&S: Pass team_id (ObjectId) for navigation anchor preservation
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
  // ❌ COMMENTED OUT: score.gameId check - not used by "Play Quarter" flow (goes through gameScene.js)
  // if (!popupGameId && score && score.gameId) {
  //   popupGameId = score.gameId;
  // }
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
    // ❌ COMMENTED OUT: score.gameId check - not used by "Play Quarter" flow
    // gameIdFromScore: score?.gameId,
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
    // ✅ FIX: Only reset isSimulating flag - buttons are already removed and game is complete
    // The pre-game container was removed at line 415, and completion popup handles navigation
    isSimulating = false;
  }
}

/**
 * ✅ SS&S: Shared function to handle game completion (finalize and show popup)
 * Used by both handleSimQuarter and handleSimFullGame to avoid code duplication
 */
async function handleGameCompletion({ gameId, lastSummary, tournamentId, franchiseId, teamId, homeTeam, awayTeam }) {
  console.log('✅ Game complete - finalizing game');
  
  // ✅ SS&S FIX: Use lastSummary directly as single source of truth (has correct final scores)
  // Only fetch from API if lastSummary is missing critical fields (box_score, players, etc.)
  let finalGameData = lastSummary;
  
  // Check if lastSummary has all required fields
  const hasBoxScore = !!lastSummary.box_score;
  const hasPlayers = !!lastSummary.players && lastSummary.players.length > 0;
  const hasScore = !!lastSummary.score && Object.keys(lastSummary.score).length > 0;
  
  // Only fetch if missing critical data (shouldn't happen, but safe fallback)
  if (gameId && (!hasBoxScore || !hasPlayers || !hasScore)) {
    try {
      console.log('📥 Fetching final game data from API (lastSummary missing some fields)...', {
        hasBoxScore,
        hasPlayers,
        hasScore
      });
      const gameResponse = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`));
      if (gameResponse.ok) {
        const fetchedData = await gameResponse.json();
        // Merge fetched data with lastSummary (prefer lastSummary scores - they're authoritative)
        finalGameData = {
          ...fetchedData,
          ...lastSummary, // lastSummary takes precedence (has correct final scores)
          score: lastSummary.score || fetchedData.score, // Use lastSummary.score (correct final scores)
          box_score: lastSummary.box_score || fetchedData.box_score // Prefer lastSummary.box_score
        };
        console.log('✅ Merged fetched data with lastSummary (lastSummary scores take precedence)');
      } else {
        console.warn('⚠️ Failed to fetch final game data, using lastSummary:', gameResponse.status);
      }
    } catch (err) {
      console.error('❌ Error fetching final game data, using lastSummary:', err);
    }
  } else {
    console.log('✅ Using lastSummary directly (has all required fields, correct final scores)');
  }

  // Finalize the game and show completion popup
  const finalScore = await finalizeGame({ simData: finalGameData, tournamentId, franchiseId });
  console.log('🏆 Final score object:', finalScore);
  
  const { showGameCompletionPopup } = await import('./utils/gameCompletionPopup.js');
  const popupMode = tournamentId ? 'tournament' : (franchiseId ? 'franchise' : 'single');
  showGameCompletionPopup({
    gameId: gameId,
    mode: popupMode,
    tournamentId: tournamentId,
    franchiseId: franchiseId,
    teamId: teamId, // ✅ SS&S: Include team_id (ObjectId) for navigation anchor preservation
    finalScore: finalScore,
    homeTeam: homeTeam,
    awayTeam: awayTeam
  });
}

async function handleSimQuarter() {
  // ✅ FIX: Calculate next quarter (handle pre-game screen where quarter = 0)
  // On pre-game screen (quarter = 0), nextQuarter = 0 + 1 = 1 (correct)
  // On Q1 break (quarter = 1), nextQuarter = 1 + 1 = 2 (correct)
  const nextQuarter = quarter + 1;
  
  // ✅ DEBUG: Log quarter calculation for debugging (including Q1 skip investigation)
  console.log(`🔍 [Q1 SKIP DEBUG] handleSimQuarter called:`, {
    currentQuarter: quarter,
    nextQuarter: nextQuarter,
    urlQuarter: urlParams.get('quarter'),
    gameId: gameId,
    url: window.location.href
  });
  
  // Validate: Don't simulate if already simulating
  if (isSimulating) return;
  
  // Validate: Don't simulate if game is complete (Q4+ and scores differ, or game is final)
  // Note: We can't easily check if game is final here without fetching game state
  // So we'll rely on button state logic to disable button after game completes
  // This is a safety check - button should already be disabled
  
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
  const simQuarterBtn = document.querySelector('.sim-to-fourth-button');
  [playBtn, simFullBtn, simQuarterBtn].forEach(btn => { if (btn) btn.disabled = true; });

  // Load game plan settings before simulating
  await loadGamePlanSettings();

  // Fetch rosters for auto-set lineup generation (needed for Q2-Q4)
  let homeRoster, awayRoster;
  try {
    const homeRes = await fetch(API_CONFIG.buildUrl(`/roster/${homeTeam}`));
    const awayRes = await fetch(API_CONFIG.buildUrl(`/roster/${awayTeam}`));
    if (homeRes.ok) homeRoster = await homeRes.json();
    if (awayRes.ok) awayRoster = await awayRes.json();
  } catch (err) {
    console.error('Error fetching rosters for auto-set:', err);
  }

  try {
    // ✅ REMOVED: showStatus call - redundant with popup header
    const payload = {
      home_team: homeTeam,
      away_team: awayTeam,
      quarter: nextQuarter,
      game_id: gameId, // Always pass gameId for tournament games
    };
    
    // ✅ SS&S: Add mode and mode-specific IDs to payload (matches gameScene.js pattern)
    // This ensures backend sets correct mode on game document for finalize_game() processing
    if (mode) {
      payload.mode = mode;
    }
    if (tournamentId) {
      payload.tournament_id = tournamentId;
    }
    // ✅ FIX: Only pass franchise_id if mode is explicitly 'franchise'
    // This prevents Single Game mode from accidentally passing franchise_id from localStorage
    if (mode === 'franchise' && franchiseId) {
      payload.franchise_id = franchiseId;
      if (weekParam && !Number.isNaN(weekParam)) {
        payload.week = weekParam;
      }
    }
    
    // Q1: Use user's set lineup (if we're simulating Q1 from pre-game screen)
    // Q2-Q4: Auto-set lineups for both teams
    if (nextQuarter === 1) {
      if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
      if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
      // Add game plan settings (Q1 only)
      if (gamePlanSettings && userTeamSide) {
        payload.user_team_side = userTeamSide;
        payload.strategy_settings = gamePlanSettings.strategy_settings;
        console.log(`🎮 Sending game plan settings to backend (${mode} mode):`, { userTeamSide, strategy: gamePlanSettings.strategy_settings });
      }
    } else {
      // Q2-Q4: Auto-set lineups
      if (homeRoster && awayRoster) {
        const autoLineups = generateBothLineups(homeRoster, awayRoster);
        payload.home_lineup = autoLineups.home_lineup;
        payload.away_lineup = autoLineups.away_lineup;
        console.log(`🤖 Q${nextQuarter}: Auto-set lineups generated for both teams`);
      }
      // Reuse game plan settings from Q1
      if (gamePlanSettings && userTeamSide) {
        payload.user_team_side = userTeamSide;
        payload.strategy_settings = gamePlanSettings.strategy_settings;
      }
      // Q2-Q3: Randomize possession and start with inbound
      // Q4: Use standard possession logic (opening tip winner) - handled by backend
      if (nextQuarter < 4) {
        payload.start_with_inbound = true;
        payload.starting_possession = Math.random() < 0.5 ? 'home' : 'away';
        console.log(`🎲 Q${nextQuarter}: Random possession assigned to ${payload.starting_possession}`);
      }
    }
    if (DEBUG_TEAMS) {
      console.log('/api/simulate-quarter payload teams:', {
        home: payload.home_team,
        away: payload.away_team,
      });
    }
    // ✅ FIX: Add full_sim=true for "simming" operations (fully simulate without animation)
    payload.full_sim = true;
    
    console.log({event:'simulate-quarter:request', mode, homeTeam, awayTeam, quarter: nextQuarter, gameId, full_sim: true});
    const res = await fetch(API_CONFIG.buildUrl('/api/simulate-quarter'), {
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
      console.error(`❌ Q${nextQuarter} simulation failed:`, errorDetail);
      throw new Error(`Q${nextQuarter} simulation failed: ${errorDetail}`);
    }
    const lastSummary = await res.json();
    const gId = lastSummary.game_id;
    
    // Update gameId from response
    gameId = gId;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('game_id', gameId);
    }
    
    // ✅ NEW: Show scrolling text popup with shot results
    console.log('🔍 [SIM QUARTER] About to call showSimQuarterResults');
    try {
      await showSimQuarterResults(lastSummary, nextQuarter, homeTeam, awayTeam);
      console.log('🔍 [SIM QUARTER] showSimQuarterResults completed');
    } catch (error) {
      console.error('❌ [SIM QUARTER] Error in showSimQuarterResults:', error);
      throw error; // Re-throw to prevent continuing if there's an error
    }
    
    // Check if game is complete (Q4+ and not tied)
    const isGameComplete = lastSummary.is_final === true;
    if (isGameComplete) {
      // ✅ FIX: Game is complete - use shared completion handler
      // When Q4 completes via Sim Quarter, finalize the game and show completion popup
      await handleGameCompletion({
        gameId,
        lastSummary,
        tournamentId,
        franchiseId,
        teamId,
        homeTeam,
        awayTeam
      });
      
      // Reset simulation flag and return (don't navigate to lineup screen)
      isSimulating = false;
      if (playBtn) playBtn.disabled = false;
      if (simFullBtn) simFullBtn.disabled = false;
      if (simQuarterBtn) simQuarterBtn.disabled = false;
      return; // Exit - game is complete, popup handles navigation
    }
    
    // ✅ FIX: Calculate next quarter after simulation
    // For full simulations (full_sim=true), backend increments gm.quarter AFTER sim completes
    // summarize_game_state() returns gm.quarter (the NEXT quarter), not the completed quarter
    // Example: Backend simulates Q1, increments to 2, returns 2 (next quarter)
    // So we should use lastSummary.quarter directly (it's already the next quarter)
    const quarterAfterSim = lastSummary.quarter || (nextQuarter + 1);
    const periodLabel = quarterAfterSim <= 4 ? `Q${quarterAfterSim}` : `OT${quarterAfterSim - 4}`;
    
    console.log(`✅ Q${nextQuarter} fully simulated, backend reports next quarter=${lastSummary.quarter}, using quarterAfterSim=${quarterAfterSim}`);
    
    // Build URL parameters for set-lineup screen using TimeoutNavigationHelper for consistency
    const helper = window.TimeoutNavigationHelper;
    if (helper) {
      const params = helper.buildGameNavigationParams({
        sourceParams: urlParams,
        targetQuarter: quarterAfterSim,
        gameId: gameId,
        resumeFromTimeout: false, // Not a timeout resume
        lineup: {}, // Lineup will be set on lineup screen
        myTeamSide: userTeamSide || 'home'
      });
      
      console.log(`🎮 Redirecting to set-lineup for ${periodLabel} after simming Q${nextQuarter}`);
      window.location.href = `/set-lineup.html?${params.toString()}`;
    } else {
      // Fallback: Build params manually if helper not available
      const params = new URLSearchParams();
      params.set('home', homeTeam);
      params.set('away', awayTeam);
      params.set('home_id', urlParams.get('home_id') || homeTeam);
      params.set('away_id', urlParams.get('away_id') || awayTeam);
      params.set('mode', mode);
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (weekParam && !Number.isNaN(weekParam)) params.set('week', weekParam);
      if (teamId) params.set('team_id', teamId);
      params.set('my_team', userTeamSide || 'home');
      params.set('quarter', quarterAfterSim);
      params.set('period', periodLabel);
      params.set('game_id', gameId);
      
      console.log(`🎮 Redirecting to set-lineup for ${periodLabel} after simming Q${nextQuarter}`);
      window.location.href = `/set-lineup.html?${params.toString()}`;
    }
  } catch (err) {
    console.error('Error simming quarter:', err);
    // ✅ FIX: Show actual error message instead of generic message
    const errorMessage = err.message || 'Simulation failed. Please try again.';
    showStatus(errorMessage);
    // Also show in alert for better visibility
    alert(`Simulation Error: ${errorMessage}`);
  } finally {
    isSimulating = false;
    if (playBtn) playBtn.disabled = false;
    if (simFullBtn) simFullBtn.disabled = false;
    if (simQuarterBtn) simQuarterBtn.disabled = false;
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
    const homeRes = await fetch(API_CONFIG.buildUrl(`/roster/${homeTeam}`));
    const awayRes = await fetch(API_CONFIG.buildUrl(`/roster/${awayTeam}`));
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
      // ✅ REMOVED: showStatus call - redundant with popup header
      const payload = {
        home_team: homeTeam,
        away_team: awayTeam,
        quarter: currentQ,
      };
      if (gId) payload.game_id = gId;
      
      // ✅ SS&S: Add mode and mode-specific IDs to payload (matches gameScene.js pattern)
      // This ensures backend sets correct mode on game document for finalize_game() processing
      if (mode) {
        payload.mode = mode;
      }
      if (tournamentId) {
        payload.tournament_id = tournamentId;
      }
      // ✅ FIX: Only pass franchise_id if mode is explicitly 'franchise'
      // This prevents Single Game mode from accidentally passing franchise_id from localStorage
      if (mode === 'franchise' && franchiseId) {
        payload.franchise_id = franchiseId;
        if (weekParam && !Number.isNaN(weekParam)) {
          payload.week = weekParam;
        }
      }
      
      // Q1: Use user's set lineup
      // Q2-Q4: Auto-set lineups for both teams
      if (currentQ === quarter) {
        if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
        if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
        // Add game plan settings (Q1 only, will be reused for all quarters)
        console.log('🔍 Game plan check (sim full):', { currentQ, quarter, hasSettings: !!gamePlanSettings, userTeamSide, mode });
        if (currentQ === 1 && gamePlanSettings && userTeamSide) {
          payload.user_team_side = userTeamSide;
          payload.strategy_settings = gamePlanSettings.strategy_settings;
          console.log(`🎮 Sending game plan settings to backend (${mode} mode, sim full):`, { userTeamSide, strategy: gamePlanSettings.strategy_settings });
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
      const res = await fetch(API_CONFIG.buildUrl('/api/simulate-quarter'), {
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

    // ✅ SS&S: Use shared game completion handler (same as handleSimQuarter)
    await handleGameCompletion({
      gameId,
      lastSummary,
      tournamentId,
      franchiseId,
      teamId,
      homeTeam,
      awayTeam
    });
    
    // ❌ COMMENTED OUT: No longer needed since we call showGameCompletionPopup directly
    // // Add gameId to finalScore so showPopup can access it
    // finalScore.gameId = gameId;
    // 
    // // Ensure gameId is in localStorage before showing popup
    // if (gameId && typeof localStorage !== 'undefined') {
    //   const storedGameId = localStorage.getItem('game_id');
    //   if (storedGameId !== gameId) {
    //     localStorage.setItem('game_id', gameId);
    //     console.log('💾 Re-saved gameId to localStorage in finalize step:', gameId);
    //   }
    // }
    // 
    // showPopup(finalScore);
  } catch (err) {
    console.error('Error simming full game:', err);
    // ✅ FIX: Show actual error message instead of generic message
    const errorMessage = err.message || 'Simulation failed. Please try again.';
    showStatus(errorMessage);
    // Also show in alert for better visibility
    alert(`Simulation Error: ${errorMessage}`);
    // ✅ FIX: Query for buttons again if they exist (defensive check)
    // Buttons may have been removed, so query DOM instead of using out-of-scope variables
    const playBtn = document.querySelector('.play-button');
    const simFullBtn = document.querySelector('.sim-full-game-button');
    const sim4Btn = document.querySelector('.sim-to-fourth-button');
    [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = false; });
  } finally {
    isSimulating = false;
  }
}

async function initGame() {
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  
  console.log('Initializing game buttons:', { playBtn, simFullBtn, sim4Btn });
  
  // ✅ FIX: Show pre-game buttons at start of each quarter (not just Q1)
  // Only hide buttons when resuming from timeout (not quarter breaks)
  const urlResumeFromTimeoutParam = urlParams.get('resume_from_timeout');
  // ✅ CRITICAL FIX: Explicitly check for 'true' string - if param is 'false' or missing, treat as false
  // This ensures quarter breaks (resume_from_timeout=false) are never treated as timeout resumes
  let resumeFromTimeout = urlResumeFromTimeoutParam === 'true';
  
  console.log('🔍 [DEBUG QTR BREAK] bootGame.js initGame() - Reading resume_from_timeout:', {
    urlParam: urlResumeFromTimeoutParam,
    parsedValue: resumeFromTimeout,
    quarter: quarter,
    gameId: gameId,
    allUrlParams: Object.fromEntries(urlParams.entries())
  });
  
  // ✅ RESILIENCE: Check database for timeout state as fallback (ONLY if URL param is missing/null)
  // This makes the system robust - even if URL param is lost, we can still detect timeout resume
  // ✅ CRITICAL: Only check DB if URL param is missing (null) - if it's explicitly 'false', trust it!
  // ✅ CRITICAL: Only check for Q1/pre-game (quarter === 0 || quarter === 1) - quarter breaks (Q2+) should never use DB fallback
  if (urlResumeFromTimeoutParam === null && gameId && (quarter === 0 || quarter === 1)) {
    // Lightweight check: If URL param missing but we have gameId in Q1, check DB for timeout state
    // This is a fallback - URL param is still primary source for navigation
    console.log('🔍 [DEBUG QTR BREAK] bootGame.js - Checking DB fallback (Q1/pre-game only, URL param missing)');
    try {
      const response = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}?quarter=${quarter}`));
      if (response.ok) {
        const gameData = await response.json();
        if (gameData.timeout_next_play_type) {
          console.log('🔍 [DEBUG QTR BREAK] bootGame.js - DB check found timeout state, setting resumeFromTimeout=true');
          resumeFromTimeout = true;
        } else {
          console.log('🔍 [DEBUG QTR BREAK] bootGame.js - DB check found no timeout state');
        }
      }
    } catch (error) {
      console.warn('⚠️ Could not check DB for timeout state (non-critical):', error);
      // Non-critical - user can still click "Play Quarter" button
    }
  } else if (urlResumeFromTimeoutParam === 'false') {
    // ✅ CRITICAL: If URL explicitly says 'false', trust it - don't check DB
    console.log('🔍 [DEBUG QTR BREAK] bootGame.js - URL param explicitly set to false (quarter break), skipping DB check');
  }
  
  console.log('🔍 [DEBUG QTR BREAK] bootGame.js initGame() - Final decision:', {
    resumeFromTimeout: resumeFromTimeout,
    willHideButtons: resumeFromTimeout,
    quarter: quarter
  });
  
  // ✅ FIX: Only hide pre-game buttons when resuming from timeout
  // Show pre-game buttons at start of each quarter (Q1-Q4, OT)
  if (resumeFromTimeout) {
    const preGameContainer = document.querySelector('.pre-game-container');
    if (preGameContainer) {
      console.log(`🎮 Hiding pre-game container (timeout resume)`);
      preGameContainer.classList.add('hidden');
    } else {
      console.log('🔍 [DEBUG QTR BREAK] bootGame.js - resumeFromTimeout=true but pre-game container not found');
    }
  } else {
    console.log('🔍 [DEBUG QTR BREAK] bootGame.js - resumeFromTimeout=false, pre-game buttons should be visible');
    const preGameContainer = document.querySelector('.pre-game-container');
    if (preGameContainer) {
      console.log('🔍 [DEBUG QTR BREAK] bootGame.js - Pre-game container found, should be visible');
    } else {
      console.log('🔍 [DEBUG QTR BREAK] bootGame.js - Pre-game container NOT found in DOM!');
    }
  }
  
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
  
  // ✅ FIX: Only auto-start when resuming from timeout (not quarter breaks)
  // Quarter breaks now show pre-game buttons for user to choose Play/Sim Quarter/Sim Full Game
  if (resumeFromTimeout && gameId && homeTeam && awayTeam) {
    console.log(`⏸️ AUTO-START: Timeout resume - auto-starting game`);
    // Auto-start the game (same as clicking "Play Quarter" button)
    handleButtonClick(true);
  }
  
  if (simFullBtn) {
    // ✅ FIX: Update button text based on quarter
    // Q2-Q3: "Sim Rest Of Game"
    // Q4+: Hide button (only show Play Quarter and Sim Quarter)
    const currentQuarter = Math.max(0, quarter);
    if (currentQuarter >= 4) {
      // Q4+: Hide "Sim Full Game"/"Sim Rest Of Game" button
      simFullBtn.style.display = 'none';
    } else if (currentQuarter >= 2) {
      // Q2-Q3: Change text to "Sim Rest Of Game"
      simFullBtn.textContent = 'Sim Rest Of Game';
      simFullBtn.addEventListener('click', handleSimFullGame);
    } else {
      // Q1: Show "Sim Full Game"
      simFullBtn.textContent = 'Sim Full Game';
      simFullBtn.addEventListener('click', handleSimFullGame);
    }
  }
  if (sim4Btn) {
    // ✅ SIM QUARTER: Button works for Q1-Q4 (before game completes)
    // Disabled when quarter > 4 (game already complete, in OT or finished)
    // Note: Button should be enabled at Q4 start (quarter = 4), only disabled after Q4 completes
    // ✅ FIX: Use Math.max(0, quarter) to handle pre-game screen (quarter = 0)
    const currentQuarter = Math.max(0, quarter);
    if (currentQuarter > 4) {
      // Game is complete (in OT or finished) - disable button
      sim4Btn.disabled = true;
      sim4Btn.title = 'Game complete';
    } else {
      // Q1-Q4: Button enabled (can sim current quarter if at start, or next quarter if at break)
      sim4Btn.disabled = false;
      sim4Btn.title = `Sim Quarter ${currentQuarter + 1}`;
      sim4Btn.addEventListener('click', handleSimQuarter);
    }
  }
}

// console.log('🚨 BOOTGAME: JavaScript is loading and executing!');
initGame().catch(error => {
  console.error('Error initializing game:', error);
});
updateOffsets();
// console.log('🚨 BOOTGAME: Initialization complete!');

// new Phaser.Game(config);
