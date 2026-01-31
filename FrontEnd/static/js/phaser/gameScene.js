import { animateGameTurns } from './animation/animateGameTurns.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { gridToPixels } from './utils/gridToPixels.js';
import { finalizeGame } from './finalizeGame.js';
import { emit } from './utils/eventBus.js';
import { appendToTextScroll } from './utils/textScroll.js';
import { DEBUG } from './utils/debug.js';
import { createGameStateMachine, States } from './state/gameStateMachine.js';
import { initializePossessionManager } from './utils/possessionManager.js';
import gameStore from '../state/gameStore.js';
import { animateCountdownTransition } from './animation/countdownAnimation.js';
import { ENABLE_TIMEOUT_BUTTON, initTimeoutButton } from './utils/timeoutButtonManager.js';

const DEBUG_SIM_PAYLOAD =
  (typeof window !== 'undefined' && window.DEBUG_SIM_PAYLOAD) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SIM_PAYLOAD) ||
  false;
const DEBUG_TEAMS =
  (typeof window !== 'undefined' && window.DEBUG_TEAMS) ||
  (typeof process !== 'undefined' && process.env.DEBUG_TEAMS) ||
  false;
const DEBUG_SERIALIZATION =
  (typeof window !== 'undefined' && window.DEBUG_SERIALIZATION) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SERIALIZATION) ||
  false;
const DEBUG_FLOW =
  (typeof window !== 'undefined' && window.DEBUG_FLOW) ||
  (typeof process !== 'undefined' && process.env.DEBUG_FLOW) ||
  false;
const DEBUG_SKIP =
  (typeof window !== 'undefined' && window.DEBUG_SKIP) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SKIP) ||
  false;

export function createGameScene(Phaser) {
  return class GameScene extends Phaser.Scene {
    constructor() {
      super("GameScene");
      this.lastTurnShown = -1;
      this.rebounderId = null;
      this.stateMachine = createGameStateMachine(States.Inbound);
      
      // Initialize centralized possession manager
      this.possessionManager = null; // Will be initialized in create()
    }

    init(data) {
        this.tournamentId = data.tournamentId;
        this.franchiseId = data.franchiseId;
        this.animate = data.animate;
        this.mode = data.mode;
        this.homeLineup = data.homeLineup || {};
        this.awayLineup = data.awayLineup || {};
        this.periodLabel = data.periodLabel;
        this.quarter = data.quarter || 1;
        
        // ✅ REMOVED: Quarter transition debug logging (cluttering console)
        
        this.gameId = gameStore.getGameId();
        // ✅ PHASE 2.4: Removed commented localStorage fallback code
        
        if (!this.gameId && typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
        this.gamePlanSettings = data.gamePlanSettings;
        this.playbookSettings = data.playbookSettings; // ✅ UNIFIED: Store playbook settings (same pattern as gamePlanSettings)
        this.userTeamSide = data.userTeamSide;
        // ✅ SS&S: Store team_id (ObjectId) for navigation anchor preservation
        this.teamId = data.teamId;
        
        // Reset pause state for new game
        this.isPaused = false;

        if (DEBUG_FLOW) {
          const teams = gameStore.getTeams();
          console.log("🧠 Game initialized with:", {
            rosters: gameStore.getRosters(),
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            homeTeam: teams.home,
            awayTeam: teams.away,
            mode: this.mode,
            periodLabel: this.periodLabel,
          });
        }
      }


    shutdown() {
      if (DEBUG_FLOW) console.log("🧹 GameScene shutdown - cleaning up sprites");
      
      // Reset pause state and kill all tweens
      this.isPaused = false;
      if (this.tweens) {
        // Resume all tweens before killing them to prevent stuck state
        this.tweens.resumeAll();
        // Kill all active tweens
        if (typeof this.tweens.killAll === 'function') {
          this.tweens.killAll();
        } else {
          // Fallback: kill all tweens individually
          const allTweens = this.tweens.getAll ? this.tweens.getAll() : [];
          allTweens.forEach(tween => {
            if (tween && typeof tween.stop === 'function') {
              tween.stop();
            }
          });
        }
      }
      
      // Update pause button text if it exists (element may not exist during shutdown)
      const pauseBtnEl = document.getElementById('pause-btn');
      if (pauseBtnEl) {
        pauseBtnEl.textContent = 'Pause';
      }
      
      // Destroy all player sprites
      if (this.playerSprites) {
        Object.values(this.playerSprites).forEach(sprite => {
          if (sprite && sprite.destroy) {
            sprite.destroy();
          }
        });
        this.playerSprites = {};
      }
      
      // Destroy ball sprite if it exists
      if (this.ballSprite && this.ballSprite.destroy) {
        this.ballSprite.destroy();
        this.ballSprite = null;
      }
      
      // Clear other references
      this.nameToId = {};
      this.playerInfo = {};
      this.playerStats = {};
      this.teamPlaysData = {};  // Store team plays data for tooltips
      this.teamStatsData = {};  // Store team stats data for tooltips
      
      console.log("✅ GameScene cleanup complete");
    }

    async preload() {
      if (DEBUG_FLOW) console.log("✅ GameScene preloaded");
      if (this.animate) {
        this.load.image("ball", "/images/ball.png");
        const { home } = gameStore.getTeams();
        const normalizeTeamName = (name) => name.toLowerCase().replace(/[\s\-]/g, '_');
        const teamId = normalizeTeamName(home);
        this.load.image("court-bg", `/images/courts/${teamId}.jpg`);
      }

    }

    async create() {
      if (DEBUG_FLOW) console.log("🎬 GameScene created");
      
      // Expose gameScene globally for Playcall Center tooltips
      window.currentGameScene = this;
      
      // ✅ TIMEOUT: Initialize timeout button
      if (ENABLE_TIMEOUT_BUTTON) {
        initTimeoutButton();
      }
      
      // ✅ DEFENSE MATCHUPS: Store trigger info for after simData loads
      // We'll show the popup after simData is fetched but before animation starts
      const urlParams = new URLSearchParams(window.location.search);
      const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
      const fromLineup = urlParams.get('from') === 'set-lineup';
      const isQ1Start = this.quarter === 1 && !resumeFromTimeout && !fromLineup;
      const isAfterBreak = resumeFromTimeout || fromLineup;
      this.shouldShowMatchupsPopup = (isQ1Start || isAfterBreak) && this.gameId;
      
      // Reset pause state BEFORE killing tweens
      this.isPaused = false;
      if (this.tweens) {
        // Resume all tweens first (if any were paused)
        this.tweens.resumeAll();
        // Kill all active tweens to start fresh
        if (typeof this.tweens.killAll === 'function') {
          this.tweens.killAll();
        } else {
          // Fallback: kill all tweens individually
          const allTweens = this.tweens.getAll ? this.tweens.getAll() : [];
          allTweens.forEach(tween => {
            if (tween && typeof tween.stop === 'function') {
              tween.stop();
            }
          });
        }
        // Ensure tween manager is not paused for new animations
        // Phaser doesn't have a direct "unpause" for the manager, but new tweens should start normally
      }
      
      // Run structure validation for inbound passes
      this.runStructureValidation();

      const homeStatsEl = document.getElementById('home-stats-body');
      const awayStatsEl = document.getElementById('away-stats-body');
      if (homeStatsEl) homeStatsEl.innerHTML = '';
      if (awayStatsEl) awayStatsEl.innerHTML = '';

      // Ensure clean slate - destroy any existing sprites before creating new ones
      if (this.playerSprites) {
        Object.values(this.playerSprites).forEach(sprite => {
          if (sprite && sprite.destroy) {
            sprite.destroy();
          }
        });
      }
      
      this.playerSprites = {};
      this.nameToId = {};
      this.playerInfo = {};
      this.playerStats = {};
      this.teamPlaysData = {};  // Store team plays data for tooltips
      this.teamStatsData = {};  // Store team stats data for tooltips

      const { home: homeTeam, away: awayTeam } = gameStore.getTeams();

      if (DEBUG_TEAMS) {
        console.log("📨 Sending /api/simulate-quarter request for:", homeTeam, "vs", awayTeam);
        console.log("🔢 Quarter:", this.quarter, "Game ID:", this.gameId);
      }

      // ✅ NEW GAME DETECTION: Determine if this is a truly new game
      // New game if: no game_id, OR Q1 with no game_id in URL and not resuming from timeout
      // Reuse urlParams and resumeFromTimeout from above (lines 167-168)
      const urlGameId = urlParams.get('game_id');
      const isNewGameStart = !this.gameId || 
                        (this.quarter === 1 && !urlGameId && !resumeFromTimeout);
      
      if (isNewGameStart) {
        // Clear stale game_id for new game
        // ✅ REMOVED: New game logging (cluttering console)
        this.gameId = null;
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
      }
      
      const payload = { home_team: homeTeam, away_team: awayTeam, quarter: this.quarter };
      // Only pass game_id if we have one AND it's not a new game
      if (this.gameId && !isNewGameStart) {
        payload.game_id = this.gameId;
      }
      
      // ✅ SS&S: Add mode and mode-specific IDs to payload (matches bootGame.js pattern)
      // This ensures backend sets correct mode on game document for finalize_game() processing
      if (this.mode) {
        payload.mode = this.mode;
      }
      if (this.tournamentId) {
        payload.tournament_id = this.tournamentId;
      }
      if (this.franchiseId) {
        payload.franchise_id = this.franchiseId;
      }
      
      // ✅ TIMEOUT: Add resume_from_timeout flag if present in URL
      if (resumeFromTimeout) {
        payload.resume_from_timeout = true;
        // ✅ REMOVED: Timeout resume logging (cluttering console)
      }
      if (DEBUG_FLOW) {
        console.log('[gameScene] request payload', {
          mode: this.mode,
          home: homeTeam,
          away: awayTeam,
          quarter: this.quarter,
          gameId: this.gameId,
        });
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      if (DEBUG_SIM_PAYLOAD) {
        console.debug('Sim payload teams:', homeTeam, awayTeam, 'gameId:', this.gameId);
      }
      if (Object.keys(this.homeLineup).length) payload.home_lineup = this.homeLineup;
      if (Object.keys(this.awayLineup).length) payload.away_lineup = this.awayLineup;
      
      // ✅ UNIFIED: Send both game plan and playbook settings for ALL quarters (not just Q1)
      // This ensures settings are available when resuming games from DB
      // If DB has None/missing settings, backend can use request settings as fallback
      if (this.gamePlanSettings && this.userTeamSide) {
        payload.user_team_side = this.userTeamSide;
        payload.strategy_settings = this.gamePlanSettings.strategy_settings;
        console.log('🎮 [gameScene] Sending game plan settings to backend:', {
          user_team_side: this.userTeamSide,
          aggression: this.gamePlanSettings.strategy_settings?.aggression,
          quarter: this.quarter
        });
      } else if (this.quarter === 1) {
        console.warn('⚠️ [gameScene] Not sending game plan:', { 
          hasSettings: !!this.gamePlanSettings, 
          userTeamSide: this.userTeamSide,
          gamePlanSettings: this.gamePlanSettings
        });
      }
      
      // ✅ UNIFIED: Send playbook settings (same pattern as strategy_settings)
      if (this.playbookSettings && this.userTeamSide) {
        payload.playbook_settings = this.playbookSettings;
        const slotCount = this.playbookSettings.slot_assignments ? Object.keys(this.playbookSettings.slot_assignments).length : 0;
        console.log('🎮 [gameScene] Sending playbook settings to backend:', {
          user_team_side: this.userTeamSide,
          slot_assignments: slotCount,
          quarter: this.quarter
        });
      } else if (this.quarter === 1) {
        console.warn('⚠️ [gameScene] Not sending playbook settings:', { 
          hasSettings: !!this.playbookSettings, 
          userTeamSide: this.userTeamSide,
          playbookSettings: this.playbookSettings
        });
      }
      
      // Note: Q4 possession is handled by backend using opening_tip_winner from Q1
      // No need to pass start_with_inbound for standard Q4 logic
      const url = API_CONFIG.buildUrl('/api/simulate-quarter');
      const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
      });
      if (DEBUG_FLOW) {
        console.log('[gameScene] response status', res.status);
      }
      if (!this.constructor._loggedSimQuarter) {
        console.debug("🛠️ /api/simulate-quarter payload keys:", Object.keys(payload), "response status:", res.status);
        this.constructor._loggedSimQuarter = true;
      }


      if (!res.ok) {
        let errorMessage;
        try {
          const errData = await res.clone().json();
          errorMessage = errData.detail || errData.message || errData.error || JSON.stringify(errData);
        } catch {
          try {
            errorMessage = await res.text();
          } catch {
            errorMessage = res.statusText;
          }
        }
        console.error("❌ Failed to fetch sim data:", errorMessage);
        appendToTextScroll(`❌ ${errorMessage}`);
        return;
      }

      const simData = await res.json();
      // ✅ TIMEOUT: Store simData in scene for timeout button manager access
      this.simData = simData;
      DEBUG && console.log('[gameScene] simData.turns', simData.turns.length, simData.turns[0]);
      if (DEBUG_FLOW) {
        console.log("📦 simData received:", simData);
        const turnsLen = Array.isArray(simData.turns) ? simData.turns.length : 0;
        console.log('🔄 Sim response arrived', { turns: turnsLen });
      }
      DEBUG_FLOW && console.log('[gameScene] quarters', { requested: this.quarter, sim: simData.quarter });
      
      // ✅ UNIFIED STRUCTURE: Prefer unified teams object, fallback to backward-compatible fields
      const homeTeamId = simData.home_team_id;
      const awayTeamId = simData.away_team_id;
      const teamsObj = simData.teams || {};
      
      // Get team data from unified structure first
      let homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : null;
      let awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : null;
      
      // ✅ BACKWARD COMPATIBILITY: Fallback to old structure if unified structure not available
      if (!homeTeamObj) {
        homeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
      }
      if (!awayTeamObj) {
        awayTeamObj = typeof simData.away_team === 'object' ? simData.away_team : null;
      }
      
      // Extract team names (unified structure preferred, fallback to old structure)
      const logHome = homeTeamObj?.name || simData.home_team || simData.homeTeam?.name;
      const logAway = awayTeamObj?.name || simData.away_team || simData.awayTeam?.name;
      
      // Extract team IDs
      const homeId = homeTeamId || homeTeamObj?.team_id || simData.home_team_id || simData.homeTeam?.team_id;
      const awayId = awayTeamId || awayTeamObj?.team_id || simData.away_team_id || simData.awayTeam?.team_id;
      
      // ✅ TIMEOUT: Store team names in scene for timeout button manager
      this.homeTeam = logHome;
      this.awayTeam = logAway;
      
      // Extract team colors (unified structure preferred)
      const homeColors = homeTeamObj?.colors || simData.home_team_colors;
      const awayColors = awayTeamObj?.colors || simData.away_team_colors;
      
      if (DEBUG_TEAMS) {
        console.log('Resolved team IDs:', { home_team_id: homeId, away_team_id: awayId });
        console.log('Team colors from simData:', {
          mode: this.mode,
          home: homeColors,
          away: awayColors,
        });
      }
      // Detect if this is a new game (Q1 with no existing gameId or new gameId)
      const previousGameId = this.gameId;
      this.gameId = simData.game_id || this.gameId;
      const isNewGame = this.quarter === 1 && (!previousGameId || (simData.game_id && simData.game_id !== previousGameId));
      
      // ✅ REMOVED: Quarter transition debug logging (cluttering console)
      
      // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
      gameStore.setGameId(this.gameId);
      
      // Set team IDs on scene for animation systems
      this.homeTeamId = homeId;
      this.awayTeamId = awayId;
      gameStore.setColors({
        home: homeColors,
        away: awayColors,
      });
      this.isFinal = simData.is_final;
      
      // ⏸️ TABLED: Resume Last Game feature - Exact game state restoration
      // TODO: Revisit after Phase 1.3+ and site go-live priorities complete
      // Current implementation resumes at lineup screen (functional but basic)
      // Future enhancement: Resume at exact moment (play step, time remaining, mid-animation, etc.)
      // See: docs/To Do/resume_last_game_exact_state.md
      /*
      // ✅ PHASE 1.2: Save game_id and user_team_side to localStorage when user quits mid-game (only for single mode, only if not final)
      // This enables "Resume Last Game" feature - save only when user explicitly quits (beforeunload)
      if (this.mode === 'single' && this.gameId && !this.isFinal && typeof window !== 'undefined') {
        const saveGameForResume = () => {
          if (this.gameId && !this.isFinal && this.mode === 'single' && typeof localStorage !== 'undefined') {
            localStorage.setItem('last_game_id', this.gameId);
            // Also save user_team_side so we can identify which team the user was playing
            if (this.userTeamSide) {
              localStorage.setItem('last_game_user_team_side', this.userTeamSide);
            }
            console.log('💾 [RESUME] Saved game_id and user_team_side for resume:', {
              game_id: this.gameId,
              user_team_side: this.userTeamSide
            });
          }
        };
        // Save on page unload (user closes tab/browser)
        window.addEventListener('beforeunload', saveGameForResume);
        // Also save on visibility change (user switches tabs - might come back)
        document.addEventListener('visibilitychange', () => {
          if (document.hidden) {
            saveGameForResume();
          }
        });
      }
      */
      
      if (DEBUG_FLOW) {
        console.log(
          `✅ Simulated matchup: ${logHome} vs ${logAway}`
        );
        console.log("📦 First turn:", simData.turns?.[0]);
      }

      const homeLogoEl = document.getElementById('home-logo');
      const awayLogoEl = document.getElementById('away-logo');
      if (homeLogoEl) homeLogoEl.src = `/images/homepage-logos/${encodeURIComponent(homeTeam)}.png`;
      if (awayLogoEl) awayLogoEl.src = `/images/homepage-logos/${encodeURIComponent(awayTeam)}.png`;

      const homeScoreEl = document.getElementById('home-score');
      const awayScoreEl = document.getElementById('away-score');
      const homeFoulsEl = document.getElementById('home-fouls');
      const awayFoulsEl = document.getElementById('away-fouls');
      const homeTolEl = document.getElementById('home-tol');
      const awayTolEl = document.getElementById('away-tol');
      const clockEl = document.getElementById('game-clock');
      const quarterEl = document.getElementById('quarter');
      
      // ✅ FOUL OUT RESUME: Initialize clock early (before DOM usage)
      // When resuming from timeout/foul out, the first turn has the correct clock from backend
      // Note: resumeFromTimeout is already declared earlier in this function (line 222)
      
      // For timeout resumes, use first turn's clock if available (backend source of truth)
      let liveClock = '8:00'; // Default
      if (resumeFromTimeout && simData.turns && simData.turns.length > 0) {
        const firstTurn = simData.turns[0];
        liveClock = firstTurn.clock || firstTurn.game_clock || simData.clock || '8:00';
        console.log(`✅ TIMEOUT RESUME: Using first turn clock: ${liveClock}`);
      } else {
        // For new games or non-timeout resumes, use URL param or simData
        // Reuse urlParams from above (line 167)
        const urlClock = urlParams.get('clock');
        liveClock = urlClock || simData.clock || '8:00';
      }
      
      let liveQuarter = this.quarter;
      let livePeriodLabel = simData.period_label || `Q${this.quarter}`;
      
      // ✅ FOUL OUT RESUME: Set clock immediately on page load (before turn processing)
      // This ensures correct clock display when returning from lineup/game plan screens
      if (clockEl && liveClock) {
        clockEl.textContent = liveClock;
      }
      if (quarterEl && livePeriodLabel) {
        quarterEl.textContent = livePeriodLabel;
      }

      const positions = ["PG","SG","SF","PF","C"];
      // Filter out the ball and inactive players (those without a position)
      const actualPlayers = simData.players.filter(p => {
        const id = p.playerId ?? p.player_id;
        const isBall = id === "ball" || id === "Ball" || p.name === "ball" || p.name === "Ball";
        const hasPosition = p.pos !== null && p.pos !== undefined; // Only include players in current lineup
        
        if (!isBall && !hasPosition) {
        }
        
        return !isBall && hasPosition;
      });
      
      // Filtered active players from roster
      
      this.nameToId = Object.fromEntries(actualPlayers.map(p => [p.name, p.playerId ?? p.player_id]));
      this.playerInfo = Object.fromEntries(actualPlayers.map(p => [p.playerId ?? p.player_id, { name: p.name, team: p.team, pos: p.pos }]));
      
      // Initialize player stats from simData.players (accumulated stats from previous quarters)
      // For Q2+, stats are restored from the database; for Q1, stats start at 0
      this.playerStats = {};
      simData.players.forEach(p => {
        const id = p.playerId ?? p.player_id;
        // Use stats from simData if available (Q2+), otherwise initialize to 0 (Q1)
        const savedStats = p.stats || {};
        // IMPORTANT: Initialize OREB and DREB separately (not just REB)
        // REB is calculated from OREB + DREB, so we need to track all three
        const oreb = savedStats.OREB || 0;
        const dreb = savedStats.DREB || 0;
        const reb = savedStats.REB || (oreb + dreb); // Use saved REB, or calculate from OREB + DREB
        this.playerStats[id] = { 
          PTS: savedStats.PTS || 0,
          F: savedStats.F || 0,
          OREB: oreb,
          DREB: dreb,
          REB: reb,
          AST: savedStats.AST || 0,
          STL: savedStats.STL || 0,
          BLK: savedStats.BLK || 0,
          TO: savedStats.TO || 0,
          DEF_A: savedStats.DEF_A || 0,
          DEF_S: savedStats.DEF_S || 0
        };
      });
      this.rowRefs = { home: {}, away: {} };
      this.currentLineup = { home: {}, away: {} };

      const homeBody = document.getElementById('home-stats-body');
      const awayBody = document.getElementById('away-stats-body');

      const formatName = (name) => {
        if (!name) return '';
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) return parts[0];
        return `${parts[0][0]}. ${parts[parts.length - 1]}`;
      };

      const getEnergyColor = (ng) => {
        if (ng > 0.89) return '#00aa00';      // Green
        if (ng >= 0.8) return '#cccc00';      // Yellow
        if (ng >= 0.7) return '#ff8800';      // Orange
        return '#cc0000';                      // Red
      };

      // Player tooltip functions
      const showPlayerTooltip = (event, playerId, player) => {
        const tooltip = document.getElementById('player-tooltip');
        const image = document.getElementById('tooltip-player-image');
        const energyEl = document.getElementById('tooltip-player-energy');
        const momentumEl = document.getElementById('tooltip-player-momentum');
        const emotionEl = document.getElementById('tooltip-player-emotion');
        
        if (!tooltip) return;
        
        // Set player image
        const playerPhoto = player.photo || `/images/players/${playerId}.png`;
        image.src = playerPhoto;
        image.onerror = () => {
          image.src = '/images/players/default.png'; // Fallback image
        };
        
        // Get current player stats (including current energy)
        const stats = this.playerStats[playerId] || {};
        
        // Get current energy from playerStats (updated each turn from player_energy)
        const ng = stats.NG ?? 1.0;
        const ngPercent = Math.round(ng * 100);
        
        // Get momentum from player attributes
        const momentum = player.attributes?.MO ?? player.MO ?? '--';
        
        // Get emotion score (EM) from player attributes
        const em = player.attributes?.EM ?? player.EM ?? 50;
        
        // Determine emoji based on EM score
        let emoji = '😐'; // Default straight face
        if (em >= 80) emoji = '😎';        // Sunglasses
        else if (em >= 60) emoji = '😊';   // Big smile
        else if (em >= 40) emoji = '😐';   // Straight face
        else if (em >= 20) emoji = '🙁';   // Frown
        else emoji = '🤢';                  // Sick green face
        
        // Update tooltip content
        energyEl.textContent = `${ngPercent}%`;
        energyEl.className = 'tooltip-stat-value';
        if (ng > 0.89) energyEl.classList.add('energy-high');
        else if (ng >= 0.8) energyEl.classList.add('energy-medium');
        else if (ng >= 0.7) energyEl.classList.add('energy-low');
        else energyEl.classList.add('energy-critical');
        
        // Update momentum bar (visual instead of text)
        const leftBar = document.getElementById('tooltip-momentum-left');
        const rightBar = document.getElementById('tooltip-momentum-right');
        
        if (leftBar && rightBar) {
          const moValue = typeof momentum === 'number' ? momentum : 0;
          
          if (moValue < 0) {
            // Negative momentum: fill left side with red
            const fillPercent = Math.abs(moValue) / 10 * 100; // -10 = 100%, -5 = 50%
            leftBar.style.width = `${fillPercent}%`;
            rightBar.style.width = '0%';
          } else if (moValue > 0) {
            // Positive momentum: fill right side with green
            const fillPercent = moValue / 10 * 100; // +10 = 100%, +5 = 50%
            leftBar.style.width = '0%';
            rightBar.style.width = `${fillPercent}%`;
          } else {
            // Zero momentum: no fill, just yellow line
            leftBar.style.width = '0%';
            rightBar.style.width = '0%';
          }
        }
        
        emotionEl.textContent = emoji;
        
        // Position and show tooltip
        updateTooltipPosition(event);
        tooltip.classList.add('visible');
      };

      const updateTooltipPosition = (event) => {
        const tooltip = document.getElementById('player-tooltip');
        if (!tooltip || !tooltip.classList.contains('visible')) return;
        
        // Position tooltip near mouse, offset to avoid cursor overlap
        const offsetX = 15;
        const offsetY = 15;
        tooltip.style.left = `${event.clientX + offsetX}px`;
        tooltip.style.top = `${event.clientY + offsetY}px`;
      };

      const hidePlayerTooltip = () => {
        const tooltip = document.getElementById('player-tooltip');
        if (tooltip) {
          tooltip.classList.remove('visible');
        }
      };

      // Play tooltip functions (for S2 tab play categories)
      const showPlayTooltip = (event, category, teamKey) => {
        const tooltip = document.getElementById('play-tooltip');
        const playNameEl = document.getElementById('tooltip-play-name');
        const effectivenessEl = document.getElementById('tooltip-play-effectiveness');
        
        if (!tooltip || !this.teamPlaysData) return;
        
        // Get team name from simData (handle nested structure)
        const homeTeamField = this.simData?.home_team;
        const awayTeamField = this.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const teamName = teamKey === 'home' ? homeTeamName : awayTeamName;
        if (!teamName) return;
        
        // Get last play run for this category
        const lastPlayByCategory = this.teamStatsData?.[teamName]?.offense?.last_play_by_category || {};
        const lastPlayName = lastPlayByCategory[category];
        
        // Get effectiveness from plays data
        const teamPlays = this.teamPlaysData[teamName] || [];
        const playData = teamPlays.find(p => p.name === lastPlayName);
        const effectiveness = playData?.game_stats?.effectiveness ?? '--';
        
        // Update tooltip content
        playNameEl.textContent = lastPlayName || 'None';
        effectivenessEl.textContent = effectiveness !== '--' ? `${effectiveness}` : '--';
        
        // Position and show tooltip
        updatePlayTooltipPosition(event);
        tooltip.classList.add('visible');
      };
      
      const updatePlayTooltipPosition = (event) => {
        const tooltip = document.getElementById('play-tooltip');
        if (!tooltip) return;
        
        const offset = 15;
        tooltip.style.left = `${event.clientX + offset}px`;
        tooltip.style.top = `${event.clientY + offset}px`;
      };
      
      const hidePlayTooltip = () => {
        const tooltip = document.getElementById('play-tooltip');
        if (tooltip) {
          tooltip.classList.remove('visible');
        }
      };

      const initTeamTable = (teamKey, bodyEl) => {
        positions.forEach(pos => {
          const player = simData.players.find(p => p.team === teamKey && p.pos === pos);
          const playerId = player?.playerId ?? player?.player_id;
          const tr = document.createElement('tr');
          const nameTd = document.createElement('td');
          const ptsTd = document.createElement('td');
          const rebTd = document.createElement('td');
          const astTd = document.createElement('td');
          const foulsTd = document.createElement('td');
          const stlTd = document.createElement('td');
          const blkTd = document.createElement('td');
          const toTd = document.createElement('td');
          const defAttemptsTd = document.createElement('td');
          const defTd = document.createElement('td');
          
          nameTd.textContent = formatName(player?.name) || '';
          nameTd.style.cursor = 'pointer';
          nameTd.dataset.playerId = playerId;
          
          // Add tooltip functionality for player names
          nameTd.addEventListener('mouseenter', (e) => {
            if (playerId && player) {
              showPlayerTooltip(e, playerId, player);
            }
          });
          nameTd.addEventListener('mousemove', (e) => {
            updateTooltipPosition(e);
          });
          nameTd.addEventListener('mouseleave', () => {
            hidePlayerTooltip();
          });
          
          ptsTd.textContent = '0';
          rebTd.textContent = '0';
          astTd.textContent = '0';
          foulsTd.textContent = '0';
          stlTd.textContent = '0';
          blkTd.textContent = '0';
          toTd.textContent = '0';
          defAttemptsTd.textContent = '0';
          defTd.textContent = '0%';
          
          // Initialize energy color (defaults to green for fresh players at 1.0)
          const initialNG = player?.NG ?? 1.0;
          const initialColor = getEnergyColor(initialNG);
          nameTd.style.color = initialColor;
          ptsTd.style.color = initialColor;
          rebTd.style.color = initialColor;
          astTd.style.color = initialColor;
          foulsTd.style.color = initialColor;
          stlTd.style.color = initialColor;
          blkTd.style.color = initialColor;
          toTd.style.color = initialColor;
          defAttemptsTd.style.color = initialColor;
          defTd.style.color = initialColor;
          
          // Hide S2 and S3 columns by default (S1 is visible)
          stlTd.style.display = 'none';
          blkTd.style.display = 'none';
          toTd.style.display = 'none';
          defAttemptsTd.style.display = 'none';
          defTd.style.display = 'none';
          
          tr.append(nameTd, ptsTd, rebTd, astTd, foulsTd, stlTd, blkTd, toTd, defAttemptsTd, defTd);
          bodyEl.appendChild(tr);
          this.rowRefs[teamKey][pos] = { 
            nameCell: nameTd, ptsCell: ptsTd, rebCell: rebTd, astCell: astTd, foulsCell: foulsTd,
            stlCell: stlTd, blkCell: blkTd, toCell: toTd, defAttemptsCell: defAttemptsTd, defCell: defTd
          };
          if (playerId) {
            this.playerStats[playerId].cells = { 
              pts: ptsTd, reb: rebTd, ast: astTd, fouls: foulsTd,
              stl: stlTd, blk: blkTd, to: toTd, defAttempts: defAttemptsTd, def: defTd
            };
            this.playerStats[playerId].nameCell = nameTd; // Store name cell for energy color coding
            this.currentLineup[teamKey][pos] = playerId;
          }
        });
      };

      initTeamTable('home', homeBody);
      initTeamTable('away', awayBody);

      // Add event listeners for play tooltip (S2 tab play categories)
      const playStatRows = document.querySelectorAll('.play-stat-row');
      playStatRows.forEach(row => {
        const category = row.dataset.playCategory;
        const teamKey = row.dataset.team;
        
        row.addEventListener('mouseenter', (e) => {
          if (category && teamKey) {
            showPlayTooltip(e, category, teamKey);
          }
        });
        
        row.addEventListener('mousemove', (e) => {
          updatePlayTooltipPosition(e);
        });
        
        row.addEventListener('mouseleave', () => {
          hidePlayTooltip();
        });
      });

      const updateLineup = (teamKey, lineup) => {
        if (!lineup) return;
        positions.forEach(pos => {
          const playerId = lineup[pos];
          if (!playerId) return;
          this.currentLineup[teamKey][pos] = playerId;
          const info = this.playerInfo[playerId];
          const row = this.rowRefs[teamKey][pos];
          if (info && row) {
            row.nameCell.textContent = formatName(info.name);
            const stats = this.playerStats[playerId] || { 
              PTS: 0, F: 0, REB: 0, AST: 0, STL: 0, BLK: 0, TO: 0, DEF_A: 0, DEF_S: 0 
            };
            this.playerStats[playerId] = stats;
            row.ptsCell.textContent = stats.PTS;
            row.foulsCell.textContent = stats.F;
            row.rebCell.textContent = stats.REB;
            row.astCell.textContent = stats.AST;
            row.stlCell.textContent = stats.STL;
            row.blkCell.textContent = stats.BLK;
            row.toCell.textContent = stats.TO;
            row.defAttemptsCell.textContent = stats.DEF_A;
            
            // Calculate defensive win percentage (no decimals)
            const defRate = stats.DEF_A > 0 ? Math.round((stats.DEF_S / stats.DEF_A) * 100) : 0;
            stats.DEF_PCT = `${defRate}%`;  // Store for S3 tab access
            row.defCell.textContent = stats.DEF_PCT;
            
            stats.cells = { 
              pts: row.ptsCell, fouls: row.foulsCell, reb: row.rebCell, ast: row.astCell,
              stl: row.stlCell, blk: row.blkCell, to: row.toCell, defAttempts: row.defAttemptsCell, def: row.defCell
            };
            stats.nameCell = row.nameCell; // Store name cell for energy color coding
          }
        });
      };

      const hydrateBoxScore = () => {
        // Use the baseline stats captured at the start of the quarter so the
        // table initially reflects pre-tip totals.
        // For new games, force empty box score to ensure stats start at 0
        const box = isNewGame ? {} : (simData.start_box_score || {});
        // Preserve the final (cumulative) box score separately for any
        // consumers that need the completed stats (e.g. post-game summaries).
        this.finalBoxScore = simData.final_box_score || simData.box_score || {};
        ['home', 'away'].forEach(teamKey => {
          const teamName = teamKey === 'home' ? homeTeam : awayTeam;
          const teamBox = box[teamName] || {};
          const lineup = {};
          positions.forEach(pos => {
            const statBlock = teamBox[pos];
            if (!statBlock) return;
            const playerId = this.nameToId[statBlock.name];
            if (!playerId) return;
            const pts = statBlock.PTS ?? 0;
            const reb = statBlock.REB ?? ((statBlock.OREB || 0) + (statBlock.DREB || 0));
            const ast = statBlock.AST ?? 0;
            const fouls = statBlock.F ?? 0;
            const stl = statBlock.STL ?? 0;
            const blk = statBlock.BLK ?? 0;
            const to = statBlock.TO ?? 0;
            const defA = statBlock.DEF_A ?? 0;
            const defS = statBlock.DEF_S ?? 0;
            
            const ps = this.playerStats[playerId] || { 
              PTS: 0, F: 0, REB: 0, AST: 0, STL: 0, BLK: 0, TO: 0, DEF_A: 0, DEF_S: 0 
            };
            ps.PTS = pts;
            ps.F = fouls;
            ps.REB = reb;
            ps.AST = ast;
            ps.STL = stl;
            ps.BLK = blk;
            ps.TO = to;
            ps.DEF_A = defA;
            ps.DEF_S = defS;
            // Calculate defensive win percentage (no decimals)
            const defPct = ps.DEF_A > 0 ? Math.round((ps.DEF_S / ps.DEF_A) * 100) : 0;
            ps.DEF_PCT = `${defPct}%`;
            this.playerStats[playerId] = ps;
            lineup[pos] = playerId;
          });
          updateLineup(teamKey, lineup);
        });
      };

      hydrateBoxScore();

      // Initialize Team Box Score with team attributes (S3 tab) only
      // Stats will be updated in real-time from turn data via applyTeamStats
      if (typeof window.setTeamBoxData === 'function') {
        // Get team attributes from new nested structure or old flat structure
        const homeAttrs = homeTeamObj?.attributes || simData.team_attributes?.[homeTeam] || {};
        const awayAttrs = awayTeamObj?.attributes || simData.team_attributes?.[awayTeam] || {};
        
        // Initialize with empty offense, defense, and empty totals (will be populated from turn data in real-time)
        window.setTeamBoxData({
          home: {
            offense: {},
            defense: {},
            attributes: homeAttrs,
            totals: {} // Start empty - will update from turn.team_totals in real-time
          },
          away: {
            offense: {},
            defense: {},
            attributes: awayAttrs,
            totals: {} // Start empty - will update from turn.team_totals in real-time
          }
        });
      }

      if (this.animate) {
        // Count existing sprites in the scene BEFORE creating new ones
        const existingContainers = this.children.list.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('🔍 PRE-CREATION: Existing containers in scene:', existingContainers.length);
        
        this.playerSprites = loadPhaserPlayers(this, actualPlayers, Phaser);
        
        // Count sprites AFTER creation
        const postCreationContainers = this.children.list.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('🔍 POST-CREATION: Total containers in scene:', postCreationContainers.length);
        // console.log('🔍 POST-CREATION: playerSprites object size:', Object.keys(this.playerSprites).length);
        
        // Clean up any extra sprites that don't have corresponding playerInfo
        const spriteKeys = Object.keys(this.playerSprites);
        const playerInfoKeys = Object.keys(this.playerInfo || {});
        const extraSprites = spriteKeys.filter(id => !this.playerInfo?.[id]);
        
        // console.log('SPRITE CLEANUP DEBUG:', {
        //   totalSprites: spriteKeys.length,
        //   totalPlayerInfo: playerInfoKeys.length,
        //   spriteKeys,
        //   playerInfoKeys,
        //   extraSprites
        // });
        
        if (extraSprites.length > 0) {
          console.warn('EXTRA SPRITES DETECTED at game start (no playerInfo):', extraSprites);
          extraSprites.forEach(id => {
            const sprite = this.playerSprites[id];
            if (sprite) {
              console.log(`Hiding extra sprite at game start: ${id}`, { 
                team: sprite.team, 
                position: { x: sprite.x, y: sprite.y },
                visible: sprite.visible,
                team_id: sprite.team_id,
                playerId: sprite.playerId
              });
              sprite.setVisible(false);
              // Remove from playerSprites object to prevent future issues
              delete this.playerSprites[id];
            }
          });
        }
        
        // Also check for any sprites that might have been created elsewhere
        // console.log('Final playerSprites after cleanup:', Object.keys(this.playerSprites));
        
        // Check all children in the scene to see if there are any extra sprites
        const allChildren = this.children.list;
        const playerSprites = allChildren.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('All container sprites in scene:', playerSprites.map(sprite => ({
        //   id: sprite.playerId,
        //   team: sprite.team,
        //   position: { x: sprite.x, y: sprite.y },
        //   visible: sprite.visible
        // })));
      }

      const applyPlayerStats = (turn = {}) => {
        if (turn.home_lineup) updateLineup('home', turn.home_lineup);
        if (turn.away_lineup) updateLineup('away', turn.away_lineup);

        if (turn.deltas) {
          for (const [playerId, delta] of Object.entries(turn.deltas)) {
            const ps = this.playerStats[playerId];
            if (ps && delta.stats) {
              for (const [stat, value] of Object.entries(delta.stats)) {
                // Skip REB - it's calculated from OREB + DREB to avoid double-counting
                // REB should NOT be in deltas (backend excludes it), but defensive check just in case
                if (stat === 'REB') continue;
                
                ps[stat] = (ps[stat] || 0) + value;
                if (ps.cells) {
                  // Map stat names to cell keys
                  const statToCellKey = {
                    'PTS': 'pts',
                    'REB': 'reb',
                    'OREB': 'reb',  // Both OREB and DREB update reb
                    'DREB': 'reb',
                    'AST': 'ast',
                    'F': 'fouls',   // Fix: F maps to fouls, not f
                    'STL': 'stl',
                    'BLK': 'blk',
                    'TO': 'to',
                    'DEF_A': 'defAttempts',
                    'DEF_S': 'def'
                  };
                  const cellKey = statToCellKey[stat];
                  
                  if (cellKey && ps.cells[cellKey]) {
                    if (stat === 'DEF_A' || stat === 'DEF_S') {
                      // Update defensive attempts and success rate when defensive stats change
                      if (ps.cells.defAttempts) ps.cells.defAttempts.textContent = ps.DEF_A;
                      const defRate = ps.DEF_A > 0 ? Math.round((ps.DEF_S / ps.DEF_A) * 100) : 0;
                      ps.DEF_PCT = `${defRate}%`;  // Store for S3 tab access
                      ps.cells.def.textContent = ps.DEF_PCT;
                    } else if (stat === 'OREB' || stat === 'DREB') {
                      // Update combined rebounds (OREB + DREB)
                      ps.REB = (ps.OREB || 0) + (ps.DREB || 0);
                      ps.cells.reb.textContent = ps.REB;
                    } else {
                      ps.cells[cellKey].textContent = ps[stat];
                    }
                  }
                }
              }
            }
          }
        }
        
        // Apply energy-based color coding to player rows
        if (turn.player_energy) {
          for (const [playerId, energyData] of Object.entries(turn.player_energy)) {
            const ps = this.playerStats[playerId];
            if (ps && ps.cells) {
              const ng = energyData.NG || 1.0;
              
              // Store current NG in playerStats for tooltip access
              ps.NG = ng;
              
              const color = getEnergyColor(ng);
              
              // Apply color to all cells in the player's row
              Object.values(ps.cells).forEach(cell => {
                if (cell) cell.style.color = color;
              });
              
              // Also apply to name cell if we have a reference to it
              if (ps.nameCell) {
                ps.nameCell.style.color = color;
              }
            }
          }
        }
      };

      const applyTeamStats = (turn = {}) => {
        // Simple approach: read team stats directly from turn data (like turn.score)
        // Update if we have team_stats (S2 tab) or team_totals (S1 tab)
        if ((!turn.team_stats && !turn.team_totals) || typeof window.setTeamBoxData !== 'function') {
          return;
        }

        const homeOffense = turn.team_stats?.[homeTeam]?.offense || {};
        const awayOffense = turn.team_stats?.[awayTeam]?.offense || {};
        const homeDefense = turn.team_stats?.[homeTeam]?.defense || {};
        const awayDefense = turn.team_stats?.[awayTeam]?.defense || {};
        
        // ✅ UNIFIED STRUCTURE: Get team attributes from unified teams object
        // Reuse team objects from outer scope if available, otherwise get from simData
        let localHomeTeamObj = homeTeamObj;
        let localAwayTeamObj = awayTeamObj;
        if (!localHomeTeamObj && simData.home_team_id && simData.teams) {
          localHomeTeamObj = simData.teams[simData.home_team_id];
        }
        if (!localHomeTeamObj) {
          localHomeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
        }
        if (!localAwayTeamObj && simData.away_team_id && simData.teams) {
          localAwayTeamObj = simData.teams[simData.away_team_id];
        }
        if (!localAwayTeamObj) {
          localAwayTeamObj = typeof simData.away_team === 'object' ? simData.away_team : null;
        }
        const homeAttrs = localHomeTeamObj?.attributes || simData.team_attributes?.[homeTeam] || {};
        const awayAttrs = localAwayTeamObj?.attributes || simData.team_attributes?.[awayTeam] || {};
        
        // Get cumulative team stats for S1 tab
        const homeTotals = turn.team_totals?.[homeTeam] || {};
        const awayTotals = turn.team_totals?.[awayTeam] || {};
        
        // Store team plays and stats data for tooltips
        if (turn.team_plays) {
          this.teamPlaysData = turn.team_plays;
        }
        if (turn.team_stats) {
          this.teamStatsData = turn.team_stats;
        }

        // Update UI directly from turn data (like scoreboard updates)
        window.setTeamBoxData({
          home: {
            offense: homeOffense,
            defense: homeDefense,
            attributes: homeAttrs,
            totals: homeTotals
          },
          away: {
            offense: awayOffense,
            defense: awayDefense,
            attributes: awayAttrs,
            totals: awayTotals
          }
        });
      };

      const formatTurnText = (turn = {}) => {
        const parts = [];
        
        // Add turn number for debugging
        if (turn.index !== undefined) {
          parts.push(`Turn ${turn.index}:`);
        }
        
        const q =
          turn.period_label ||
          (turn.quarter != null
            ? turn.quarter > 4
              ? `OT${turn.quarter - 4}`
              : `Q${turn.quarter}`
            : null);
        const clk = turn.clock || turn.game_clock;
        if (q || clk) {
          const timePart = [q, clk].filter(Boolean).join(' ');
          parts.push(`[${timePart}]`);
        }
        if (turn.team) {
          const teamName =
            turn.team === 'home'
              ? homeTeam
              : turn.team === 'away'
              ? awayTeam
              : turn.team;
          parts.push(teamName);
        }
        if (turn.text) parts.push(turn.text);
        return parts.join(' ');
      };

      // Live scoreboard state - force to 0 for new games
      // Only use persisted scores if continuing an existing game
      // ✅ TIMEOUT RESUME: Check team objects first (same pattern as timeouts) for consistency
      const homeScoreFromData = homeTeamObj?.score ?? simData.score?.[homeTeam];
      const awayScoreFromData = awayTeamObj?.score ?? simData.score?.[awayTeam];
      const liveScore = {
        [homeTeam]: isNewGame ? 0 : (homeScoreFromData ?? 0),
        [awayTeam]: isNewGame ? 0 : (awayScoreFromData ?? 0),
      };
      
        // Explicitly reset scoreboard UI for new games
        if (isNewGame) {
          // ✅ REFACTOR: Direct DOM updates (same as other scoreboard items)
          if (homeScoreEl) homeScoreEl.textContent = 0;
          if (awayScoreEl) awayScoreEl.textContent = 0;
          // Initialize timeout display for new games (default 4)
          if (homeTolEl) homeTolEl.textContent = 'TOL: 4';
          if (awayTolEl) awayTolEl.textContent = 'TOL: 4';
        }
      // ✅ TIMEOUT RESUME: Check team objects first (same pattern as timeouts) for consistency
      const homeFoulsFromData = homeTeamObj?.team_fouls ?? simData.fouls?.home;
      const awayFoulsFromData = awayTeamObj?.team_fouls ?? simData.fouls?.away;
      let liveHomeFouls = typeof homeFoulsFromData === 'number' ? homeFoulsFromData : 0;
      let liveAwayFouls = typeof awayFoulsFromData === 'number' ? awayFoulsFromData : 0;
      // Extract timeouts from nested team objects or flat structure, default to 5 for new games
      const homeTimeoutsFromData = homeTeamObj?.timeouts ?? simData.timeouts?.home ?? simData.home_team_timeouts;
      const awayTimeoutsFromData = awayTeamObj?.timeouts ?? simData.timeouts?.away ?? simData.away_team_timeouts;
      let liveHomeTimeouts = typeof homeTimeoutsFromData === 'number' ? homeTimeoutsFromData : (isNewGame ? 4 : 4);
      let liveAwayTimeouts = typeof awayTimeoutsFromData === 'number' ? awayTimeoutsFromData : (isNewGame ? 4 : 4);

      const updateScoreboard = (turn = {}) => {
        const prevHome = liveScore[homeTeam];
        const prevAway = liveScore[awayTeam];
        
        // ✅ TIMEOUT: Track if we're updating from initial values (not a turn)
        const isInitialUpdate = turn.score && !turn.index && !turn.result_type;

        // ``turn.score`` is authoritative. ``turn.points`` may appear in the
        // payload for context but must **not** be re-applied here to avoid
        // double counting.
        if (turn.score) {
          if (typeof turn.score[homeTeam] === 'number') liveScore[homeTeam] = turn.score[homeTeam];
          if (typeof turn.score[awayTeam] === 'number') liveScore[awayTeam] = turn.score[awayTeam];
        }

        // ✅ TIMEOUT: Update fouls from turn data (exact same pattern as scores)
        if (turn.homeFouls !== undefined || turn.awayFouls !== undefined) {
          if (typeof turn.homeFouls === 'number') liveHomeFouls = turn.homeFouls;
          if (typeof turn.awayFouls === 'number') liveAwayFouls = turn.awayFouls;
        }
        // Also check alternative keys (for turn data)
        const homeF = turn.home_team_fouls ?? turn.fouls?.home;
        const awayF = turn.away_team_fouls ?? turn.fouls?.away;
        if (typeof homeF === 'number') liveHomeFouls = homeF;
        if (typeof awayF === 'number') liveAwayFouls = awayF;

        // ✅ TIMEOUT: Update timeouts from turn data (exact same pattern as scores and fouls)
        if (turn.homeTimeouts !== undefined || turn.awayTimeouts !== undefined) {
          if (typeof turn.homeTimeouts === 'number') liveHomeTimeouts = turn.homeTimeouts;
          if (typeof turn.awayTimeouts === 'number') liveAwayTimeouts = turn.awayTimeouts;
        }
        // Also check alternative keys (for turn data)
        const homeT = turn.home_team_timeouts ?? turn.timeouts?.home;
        const awayT = turn.away_team_timeouts ?? turn.timeouts?.away;
        if (typeof homeT === 'number') liveHomeTimeouts = homeT;
        if (typeof awayT === 'number') liveAwayTimeouts = awayT;

        if (turn.clock || turn.game_clock) {
          liveClock = turn.clock || turn.game_clock;
          // ✅ TIMEOUT: Update scene.simData.clock so it's accessible for timeout navigation
          if (this.simData) {
            this.simData.clock = liveClock;
          }
        }
        if (turn.quarter != null) liveQuarter = turn.quarter;
        if (turn.period_label) {
          livePeriodLabel = turn.period_label;
        } else if (turn.quarter != null) {
          livePeriodLabel = turn.quarter > 4 ? `OT${turn.quarter - 4}` : `Q${turn.quarter}`;
        }

        // ✅ REFACTOR: Direct DOM updates for all scoreboard items (consistent pattern)
        if (homeScoreEl) homeScoreEl.textContent = liveScore[homeTeam];
        if (awayScoreEl) awayScoreEl.textContent = liveScore[awayTeam];
        if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
        if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
        if (homeTolEl) homeTolEl.textContent = `TOL: ${liveHomeTimeouts}`;
        if (awayTolEl) awayTolEl.textContent = `TOL: ${liveAwayTimeouts}`;
        if (clockEl) clockEl.textContent = liveClock;
        if (quarterEl) quarterEl.textContent = livePeriodLabel;

        applyPlayerStats(turn);
        applyTeamStats(turn);

        // Check for foul out and show popup
        if (turn.fouled_out && turn.foul_out_player) {
          // Dynamically import foul out popup
          import('./utils/foulOutPopup.js').then(({ showFoulOutPopup }) => {
            // Get game context from scene
            const mode = this.mode || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('mode') : null) || 'single';
            const urlParams = new URLSearchParams(window.location.search);
            const tournamentId = urlParams.get('tournament_id') || null;
            const franchiseId = urlParams.get('franchise_id') || null;
            
            // Get team information from gameStore or URL
            const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
            const homeId = this.homeTeamId || urlParams.get('home_id');
            const awayId = this.awayTeamId || urlParams.get('away_id');
            const myTeamSide = urlParams.get('my_team');
            const userTeamId = urlParams.get('user_team_id');
            
            showFoulOutPopup({
              player: turn.foul_out_player,
              gameId: this.gameId,
              mode: mode,
              quarter: liveQuarter,
              clock: liveClock, // ✅ Pass current clock time to preserve it
              tournamentId: tournamentId,
              franchiseId: franchiseId,
              homeTeam: homeTeam,
              awayTeam: awayTeam,
              homeId: homeId,
              awayId: awayId,
              myTeamSide: myTeamSide,
              userTeamId: userTeamId
            });
          }).catch(err => {
            console.error('Failed to load foul out popup:', err);
          });
        }

        // ✅ REFACTOR: Scores now use direct DOM updates (same as fouls/timeouts/clock)
        // No need for event system - scores are updated directly above with other scoreboard items

        if (turn.text && turn.index !== this.lastTurnShown) {
          if (typeof window !== 'undefined' && window.TEXT_SCROLL_ENABLED) {
            // Display debug info first (if available)
            if (turn.debug_turn_start) {
              appendToTextScroll(turn.debug_turn_start);
            }
            
            // Display normal turn text
            appendToTextScroll(formatTurnText(turn));
            
            // Display debug result info (if available)
            if (turn.debug_turn_result) {
              appendToTextScroll(turn.debug_turn_result);
            }
          }
          this.lastTurnShown = turn.index;
        }
      };

      // Show cumulative state immediately
      // ✅ TIMEOUT: updateScoreboard() now handles initial score updates (same system as other items)
      updateScoreboard({
        score: liveScore,  // Pass scores so updateScoreboard can update them
        homeFouls: liveHomeFouls,
        awayFouls: liveAwayFouls,
        homeTimeouts: liveHomeTimeouts,  // ✅ TIMEOUT: Pass timeouts for immediate update
        awayTimeouts: liveAwayTimeouts,
        clock: liveClock,
        quarter: liveQuarter,
        period_label: livePeriodLabel,
      });

      const pauseBtn = document.getElementById('pause-btn');
      const skipBtn = document.getElementById('skip-btn');
      const gameSpeedBtn = document.getElementById('game-speed-btn');
      const speedDropdown = document.getElementById('speed-dropdown');
      this.isPaused = false;
      this.skipToEnd = false;
      this.isSkipping = false;
      this.finalized = false;
      
      // Initialize game speed from localStorage
      const { loadSpeedPreference, setGameSpeed, getSpeedPresets } = await import('./utils/gameSpeedManager.js');
      const initialSpeed = loadSpeedPreference();
      updateSpeedDropdown(initialSpeed);
      
      // Game Speed button handler
      if (gameSpeedBtn && speedDropdown) {
        gameSpeedBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const isVisible = speedDropdown.style.display !== 'none';
          speedDropdown.style.display = isVisible ? 'none' : 'flex';
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
          if (!speedDropdown.contains(e.target) && e.target !== gameSpeedBtn) {
            speedDropdown.style.display = 'none';
          }
        });
        
        // Speed option handlers
        const speedOptions = speedDropdown.querySelectorAll('.speed-option');
        speedOptions.forEach(option => {
          option.addEventListener('click', (e) => {
            e.stopPropagation();
            const speed = parseInt(option.dataset.speed, 10);
            setGameSpeed(speed);
            updateSpeedDropdown(speed);
            speedDropdown.style.display = 'none';
          });
        });
      }
      
      function updateSpeedDropdown(currentSpeed) {
        if (!speedDropdown) return;
        const speedOptions = speedDropdown.querySelectorAll('.speed-option');
        speedOptions.forEach(option => {
          const optionSpeed = parseInt(option.dataset.speed, 10);
          if (optionSpeed === currentSpeed) {
            option.classList.add('active');
          } else {
            option.classList.remove('active');
          }
        });
      }
      
      if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
          this.isPaused = !this.isPaused;
          if (this.isPaused) {
            // Pause all tweens
            if (this.tweens) {
              this.tweens.pauseAll();
              const activeTweens = this.tweens.getAll ? this.tweens.getAll() : [];
              if (DEBUG_FLOW) console.log('⏸️ Game paused', {
                activeTweensCount: activeTweens.length,
                tweenManagerPaused: typeof this.tweens.isPaused === 'function' ? this.tweens.isPaused() : 'N/A',
                tweenManagerTimeScale: this.tweens.timeScale
              });
            }
            pauseBtn.textContent = 'Resume';
          } else {
            // Resume all tweens
            if (this.tweens) {
              // Ensure timeScale is set to 1 (normal speed) - it might have been set to 0
              if (typeof this.tweens.timeScale !== 'undefined') {
                this.tweens.timeScale = 1;
              }
              
              // Resume all existing tweens
              this.tweens.resumeAll();
              
              // Also explicitly resume each tween individually (in case resumeAll() doesn't work)
              const activeTweens = this.tweens.getAll ? this.tweens.getAll() : [];
              activeTweens.forEach(tween => {
                if (tween) {
                  // Try multiple methods to ensure tween resumes
                  if (typeof tween.resume === 'function') {
                    tween.resume();
                  }
                  if (typeof tween.play === 'function' && !tween.isPlaying()) {
                    tween.play();
                  }
                  // If tween has an isPaused check, ensure it's not paused
                  if (typeof tween.isPaused === 'function' && tween.isPaused()) {
                    if (typeof tween.resume === 'function') {
                      tween.resume();
                    }
                  }
                  // Ensure tween's timeScale is set to 1 (normal speed)
                  if (typeof tween.timeScale !== 'undefined') {
                    tween.timeScale = 1;
                  }
                }
              });
              
              if (DEBUG_FLOW) console.log('▶️ Game resumed', {
                activeTweensCount: activeTweens.length,
                tweenManagerPaused: typeof this.tweens.isPaused === 'function' ? this.tweens.isPaused() : 'N/A',
                tweenManagerTimeScale: this.tweens.timeScale,
                resumedTweens: activeTweens.length
              });
            }
            
            pauseBtn.textContent = 'Pause';
          }
        });
      }
      if (skipBtn && DEBUG_SKIP) {
        skipBtn.addEventListener('click', async () => {
          if (this.isSkipping) return;
          this.skipToEnd = true;
          this.isSkipping = true;
          this.isPaused = false;
          skipBtn.disabled = true;
          if (pauseBtn) pauseBtn.textContent = 'Pause';
          this.tweens.resumeAll();
          this.tweens.getAllTweens().forEach(t => t.stop());
          await finalize();
        });
      }

      const finalize = async () => {
        if (this.finalized) return this.finalScore;
        const finalScore = await finalizeGame({
          simData,
          tournamentId: this.tournamentId,
          franchiseId: this.franchiseId,
          game: this.game,
        });
        this.finalScore = finalScore;
        this.finalized = true;
        if (window.GOB_Analytics) {
          if (this.tournamentId) window.GOB_Analytics.tournamentGameCompleted();
          else if (this.franchiseId) window.GOB_Analytics.franchiseGameCompleted();
          else window.GOB_Analytics.singleGameCompleted();
        }
        // Show game completion popup (absolute path for Netlify/module resolution)
        const base = (typeof window !== 'undefined' && window.API_CONFIG) ? window.API_CONFIG.getStaticPath() : '';
        const { showGameCompletionPopup } = await import(`${base}/js/phaser/utils/gameCompletionPopup.js`);
        const mode = this.tournamentId ? 'tournament' : (this.franchiseId ? 'franchise' : 'single');
        showGameCompletionPopup({
          gameId: this.gameId || simData.game_id,
          mode: mode,
          tournamentId: this.tournamentId,
          franchiseId: this.franchiseId,
          finalScore: finalScore
        });
        
        return finalScore;
      };

      // console.log('🚨 GAMESCENE: animate parameter:', this.animate);
      // console.log('🚨 GAMESCENE: typeof animate:', typeof this.animate);
      
      if (this.animate) {
        // console.log('🚨 GAMESCENE: Taking animation path');
        const courtKey = "court-bg";

        const startAnimation = async () => {
          const spriteKeys = Object.keys(this.playerSprites || {});
          if (DEBUG_TEAMS) {
            console.log('playerSprites keys:', spriteKeys);
          }
          const turnIds = Array.from(new Set((simData.turns || []).flatMap(t => {
            const ids = [];
            if (t.playerId) ids.push(t.playerId);
            if (t.player_id) ids.push(t.player_id);
            if (Array.isArray(t.animations)) {
              t.animations.forEach(a => {
                if (a.playerId) ids.push(a.playerId);
                if (a.player_id) ids.push(a.player_id);
              });
            }
            return ids;
          })));
          if (DEBUG_FLOW) console.log('IDs in turns:', turnIds);

          if (DEBUG_TEAMS) {
            simData.players.forEach(p => {
              console.log(`Sprite initialized: ${p.name} -> ${p.team}`);
            });
          }

          // ✅ DEFENSE MATCHUPS: Show popup before animation starts (if needed)
          // Only show popup if animate=true (Play Quarter was pressed), not for Sim Quarter/Sim Full Game
          if (this.shouldShowMatchupsPopup && this.animate) {
            try {
              const { showDefenseMatchupsPopup, resetDontShowAgainFlag } = await import('./utils/defenseMatchupsPopup.js');
              // Reset "Don't show again" flag at start of new game (Q1)
              const urlParams = new URLSearchParams(window.location.search);
              const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
              const fromLineup = urlParams.get('from') === 'set-lineup';
              const isQ1Start = this.quarter === 1 && !resumeFromTimeout && !fromLineup;
              
              if (isQ1Start) {
                resetDontShowAgainFlag();
              }
              
              // Show popup and wait for user to submit before starting animation
              await showDefenseMatchupsPopup(this.gameId, this);
            } catch (error) {
              console.error('❌ DEFENSE MATCHUPS: Failed to show popup:', error);
              // Don't block gameplay if popup fails
            }
          }

          this.ballSprite = this.add.image(0, 0, "ball").setVisible(true).setDepth(1000).setScale(1.5);  // 50% larger

          // Initialize BallController for the new animation system
          try {
            const { initializeBallController } = await import('./animation/BallControllerAdapter.js');
            this.ballController = initializeBallController(this, this.ballSprite);
            if (DEBUG_FLOW) {
              console.log('🎬 GameScene: BallController initialized');
            }
          } catch (error) {
            console.error('🎬 GameScene: Failed to initialize BallController:', error);
          }

          this.tweens.add({
            targets: this.ballSprite,
            scale: { from: 1, to: 1.3 },
            duration: 400,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
          });

          let animStart;
          if (DEBUG_FLOW) {
            animStart = Date.now();
            console.log('🚀 animateGameTurns start', animStart);
          }
          
          // Turn-by-turn simulation loop
          // Initial turns (opening tip for Q1, empty for Q2+) are passed in
          // Turns are generated on-demand via /api/simulate-turn calls
          // ✅ REMOVED: Starting quarter logging (cluttering console)
          const turnResult = await this.simulateTurnByTurn(simData, updateScoreboard);
          
          // ✅ FIX: Skip quarter completion logic if timeout was detected
          // Timeout navigation is handled by timeoutButtonManager, so we should exit here
          if (turnResult?.timeoutDetected) {
            console.log('⏸️ TIMEOUT: simulateTurnByTurn returned timeoutDetected=true - skipping quarter completion logic');
            return; // Exit - timeout navigation is handled elsewhere
          }
          
          console.log('🎬 GameScene: Turn-by-turn simulation completed');
          if (DEBUG_FLOW) {
            const animEnd = Date.now();
            console.log('🏁 animateGameTurns finish', animEnd, 'duration', animEnd - animStart);
          }

          if (DEBUG_FLOW) {
            console.log('🧭 Navigation condition', {
              isFinal: this.isFinal,
              quarter: this.quarter,
              turnCount: quarterTurns.length
            });
          }

          if (DEBUG_FLOW) console.log("✅ GameScene animation complete");
          if (this.isFinal) {
            await finalize();
          } else {
            console.log('✅ Quarter complete - showing locker room popup');
            
            // Show "Go To Locker Room" popup
            const nextQ = this.quarter + 1;
            const params = new URLSearchParams(window.location.search);
            params.set('game_id', this.gameId);
            params.set('quarter', nextQ);
            params.set('period', `Q${nextQ}`);
            // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
            
            // Create locker room popup
            const popup = document.createElement('div');
            popup.className = 'locker-room-popup';
            popup.innerHTML = `
              <div class="locker-room-content">
                <h2>Quarter ${this.quarter} Complete!</h2>
                <button class="locker-room-button">Go To Locker Room</button>
              </div>
            `;
            document.body.appendChild(popup);
            
            // Wire up button
            const button = popup.querySelector('.locker-room-button');
            button.addEventListener('click', () => {
              window.location.href = `/set-lineup.html?${params.toString()}`;
            });
            
            return;
          }
      };

        const logAndStart = () => {
          DEBUG_FLOW && console.log('skipToEnd before startAnimation:', this.skipToEnd);
          startAnimation();
        };

        if (this.textures.exists(courtKey)) {
          this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
          logAndStart();
        } else {
          this.load.once("complete", () => {
              this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
              logAndStart();
          });
          this.load.start();
        }
      } else {
        // console.log('🚨 GAMESCENE: Taking NO animation path - skipping to next quarter');
        if (this.isFinal) {
          await finalize();
        } else {
          // console.log('🚨 GAMESCENE: About to navigate to next quarter - BLOCKING FOR DEBUG');
          // console.log('🚨 GAMESCENE: If you see this, the animation was skipped!');
          
          // TEMPORARY DEBUG: Block navigation to see what's happening
          if (window.DEBUG_BLOCK_NAVIGATION !== false) {
            // console.log('🚨 GAMESCENE: Navigation blocked for debugging. Set window.DEBUG_BLOCK_NAVIGATION = false to allow navigation.');
            return; // Block navigation
          }
          
          // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
          const nextQ = this.quarter + 1;
          const urlParams = new URLSearchParams(window.location.search);
          
          // ✅ REMOVED: Quarter navigation debug logging (cluttering console)
          
          // ✅ SS&S: Use global helper (works in both regular scripts and modules)
          const helper = window.TimeoutNavigationHelper;
          if (!helper) {
            console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
            return;
          }
          
          // ✅ PHASE 2.4: Removed localStorage fallback - game_id must come from URL
          
          // ✅ QUARTER BREAK: Quarter breaks should NOT have resume_from_timeout
          // Helper will automatically exclude it for quarter breaks (resumeFromTimeout=false)
          const params = helper.buildGameNavigationParams({
            sourceParams: urlParams,
            targetQuarter: nextQ,
            gameId: this.gameId,
            resumeFromTimeout: false, // ✅ QUARTER BREAK: Not a timeout resume
            lineup: {}, // Lineup will be set on lineup screen
            myTeamSide: urlParams.get('my_team')
          });
          
          // ✅ REMOVED: Navigation params debug logging (cluttering console)
          
          // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
          DEBUG_FLOW && console.log('➡️ Advancing to lineup', { nextQ, gameId: this.gameId });
          DEBUG_FLOW && console.log('skipToEnd at navigation:', this.skipToEnd);
          window.location.href = `/set-lineup.html?${params.toString()}`;
        }
      }
    }

    /**
     * Run structure validation for inbound pass system
     */
    runStructureValidation() {
      try {
        // Running inbound pass structure validation
        
        // Import and run validation
        import('./animation/validateStructure.js').then(module => {
          const result = module.validateInboundPassStructure();
          
          if (result.isValid) {
            // Inbound pass structure validation passed
          } else {
            console.log('❌ Inbound pass structure validation failed:');
            result.issues.forEach(issue => {
              console.log(`   - ${issue}`);
            });
            console.log('💡 Check the PotentialIssues.md file for solutions');
          }
        }).catch(error => {
          console.log('⚠️ Could not run structure validation:', error.message);
        });
        
      } catch (error) {
        console.log('⚠️ Structure validation error:', error.message);
      }
    }
    
    /**
     * NEW: Turn-by-turn simulation method
     * Replaces the old batch simulation approach
     */
    async simulateTurnByTurn(initialSimData, updateScoreboard) {
      // ✅ REMOVED: Starting turn-by-turn simulation logging (cluttering console)
      
      const gameId = initialSimData.game_id;
      const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
      
      let quarterComplete = false;
      let turnCount = 0;
      let lastHomeScore = initialSimData.home_score || 0;
      let lastAwayScore = initialSimData.away_score || 0;
      let nextQuarterNumber = this.quarter + 1; // Will be updated when quarter completes
      let lastTurnData = null; // Track last turn data to check is_final
      let timeoutTurnDetected = false; // ✅ FIX: Track if timeout turn was detected to prevent quarter completion logic
      
      // Initialize with any turns from the initial simulation (e.g., opening tip, inbound)
      const initialTurns = initialSimData.turns || [];
      
      // Animate initial turns first (opening tip, quarter start inbound, etc.)
      if (initialTurns.length > 0) {
        // ✅ REMOVED: Animating initial turns logging (cluttering console)
        
        // Add indices to initial turns for text scroll
        initialTurns.forEach((turn, idx) => {
          turn.index = idx;
          turnCount++;
        });
        
        await animateGameTurns({
          scene: this,
          simData: { ...initialSimData, turns: initialTurns },
          playerSprites: this.playerSprites,
          ballSprite: this.ballSprite,
          onUpdate: updateScoreboard
        });
      }
      
      // Main turn-by-turn loop
      while (!quarterComplete) {
        try {
          // ✅ SS&S: Overrides are now stored in team.strategy_calls via /api/set-playcall-override
          // No need to pass overrides here - backend checks team.strategy_calls automatically
          // Legacy support: Still check window globals for backward compatibility (will be removed)
          const offenseOverride = window.nextOffenseOverride || null;
          const defenseOverride = window.nextDefenseOverride || null;
          
          // Clear legacy window globals after reading (single-use)
          window.nextOffenseOverride = null;
          window.nextDefenseOverride = null;
          window.nextDefenseTypeOverride = null;
          window.nextDefenseAggressionOverride = null;
          
          // Clear visual selections in Playcall Center (only if override was used)
          // Note: Highlighting will be managed by tracking which turn used the override
          // For now, clear on every turn (will be refined to only clear after override is used)
          if (window.clearPlaycallOverrides && (offenseOverride || defenseOverride)) {
            window.clearPlaycallOverrides();
          }
          
          const response = await fetch(API_CONFIG.buildUrl('/api/simulate-turn'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              game_id: gameId,
              offense_override: offenseOverride,  // Legacy support - will be removed
              defense_override: defenseOverride,   // Legacy support - will be removed
              mode: this.mode || 'single'
            })
          });
          
          if (!response.ok) {
            let errorData;
            try {
              errorData = await response.json();
            } catch {
              errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
            }
            console.error('❌ /api/simulate-turn failed:', errorData);
            // ✅ FIX: Don't assume 404 = quarter complete
            // A 404 could mean: game not found, backend restart, network issue, etc.
            // Only mark quarter complete if backend explicitly says so (quarter_complete=true)
            if (response.status === 404 && errorData.detail && errorData.detail.includes('not found')) {
              console.error('⚠️ Game was cleared from backend memory. This may indicate a backend restart or timeout.');
              
              // ✅ Phase 4: Show missing truth error screen for game not found
              if (window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
                const urlParams = new URLSearchParams(window.location.search);
                const gameId = urlParams.get('game_id');
                const mode = urlParams.get('mode') || 'single';
                
                window.ErrorHandler.showMissingTruthError({
                  pointerType: 'game_id',
                  pointerValue: gameId || 'unknown',
                  message: errorData.detail || 'Game was cleared from backend memory. This may indicate a backend restart or timeout.',
                  mode,
                  recoveryOptions: {
                    redirectTo: 'mode-select',
                    redirectLabel: 'Go to Mode Select'
                  }
                });
              }
              
              // ✅ FIX: Don't break - throw error to be caught by outer catch block
              // This prevents quarter completion logic from running
              throw new Error(`Game not found: ${errorData.detail || 'Game was cleared from backend memory'}`);
            }
            // ✅ FIX: For other errors, throw to prevent quarter completion
            throw new Error(`API error: ${errorData.detail || `HTTP ${response.status}`}`);
          }
          
          const turnData = await response.json();
          
          // ✅ FIX: Only break if there's no turn to animate
          // If quarter_complete is True but turn exists, animate the turn first (it's the final turn of the quarter)
          if (!turnData.turn) {
            console.log('✅ Quarter complete! (no turn returned)', {
              time_remaining: turnData.time_remaining,
              turnCount,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              is_final: turnData.is_final
            });
            quarterComplete = true;
            lastTurnData = turnData; // Store last turn data for game completion check
            
            // Update final scores
            updateScoreboard({
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_fouls: turnData.home_team_fouls,
              away_team_fouls: turnData.away_team_fouls,
              clock: turnData.clock
            });
            
            // Update tracked scores from final turnData
            if (turnData.home_score !== undefined) {
              lastHomeScore = turnData.home_score;
            }
            if (turnData.away_score !== undefined) {
              lastAwayScore = turnData.away_score;
            }
            
            // Track the next quarter number from backend
            if (turnData.quarter !== undefined) {
              nextQuarterNumber = turnData.quarter;
            }
            
            break;
          }
          
          // Animate this single turn (or batch of turns)
          const turn = turnData.turn;
          
          // ✅ FIX: Check if this is the final turn of the quarter AFTER getting the turn
          // This ensures the final turn is animated before handling quarter completion
          if (turnData.quarter_complete) {
            // Mark that this is the final turn - we'll handle quarter completion after animation
            turn.is_final_turn_of_quarter = true;
            console.log('🔍 [FINAL TURN DEBUG] Received turn with quarter_complete=true BEFORE animation', {
              turn_result_type: turn.result_type,
              turn_text: turn.text?.substring(0, 50),
              time_remaining_before_turn: turnData.time_remaining,
              clock_before_turn: turnData.clock,
              turnCount,
              will_animate: true
            });
          }
          let finalTurn = turn; // Track the final turn for Quick Adjust logic
          
          // ✅ TIMEOUT: Check if this is a timeout turn - if so, stop the simulation loop
          if (turn.result_type === "TIMEOUT") {
            console.log('⏸️ TIMEOUT: Timeout turn detected in simulateTurnByTurn - stopping simulation loop');
            // ✅ FIX: Set flag to prevent quarter completion logic
            timeoutTurnDetected = true;
            // ✅ UNIFIED: Store full response data in turn for animation system to access clock/time_remaining
            turn._responseData = {
              clock: turnData.clock,
              time_remaining: turnData.time_remaining,
              quarter: turnData.quarter,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_timeouts: turnData.home_team_timeouts,
              away_team_timeouts: turnData.away_team_timeouts
            };
            // Animate the timeout turn (will handle navigation)
            await animateGameTurns({
              scene: this,
              simData: { 
                ...initialSimData,
                turns: [turn],
                home_team: initialSimData.home_team,
                away_team: initialSimData.away_team
              },
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              onUpdate: updateScoreboard
            });
            // Break out of the while loop - don't make any more API calls
            break;
          }
          
          // Handle BATCH turns (e.g., HCO miss → OREB)
          if (turn.result_type === 'BATCH' && turn.batch_turns) {
            // ✅ REMOVED: Batch turn logging (cluttering console)
            
            // Animate each turn in the batch
            for (const subTurn of turn.batch_turns) {
              turnCount++;
              subTurn.index = turnCount;
              
              console.log(`🎬 Turn ${turnCount}: ${subTurn.result_type} - ${subTurn.text?.substring(0, 50)}...`);
              
              // Display debug info in text scroll
              if (subTurn.debug_turn_start) {
                appendToTextScroll(subTurn.debug_turn_start);
              }
              if (subTurn.text) {
                appendToTextScroll(`Turn ${turnCount}: ${subTurn.text}`);
              }
              if (subTurn.debug_turn_result) {
                appendToTextScroll(subTurn.debug_turn_result);
              }
              
              await animateGameTurns({
                scene: this,
                simData: { 
                  ...initialSimData,
                  turns: [subTurn],
                  home_team: initialSimData.home_team,
                  away_team: initialSimData.away_team
                },
                playerSprites: this.playerSprites,
                ballSprite: this.ballSprite,
                onUpdate: updateScoreboard
              });
              
              // Update finalTurn to be the last sub-turn in the batch
              finalTurn = subTurn;
            }
          } else {
            // Normal single turn
            turnCount++;
            turn.index = turnCount;
            
            console.log(`🎬 Turn ${turnCount}: ${turn.result_type} - ${turn.text?.substring(0, 50)}...`);
            
            // Display debug info in text scroll
            if (turn.debug_turn_start) {
              appendToTextScroll(turn.debug_turn_start);
            }
            if (turn.text) {
              appendToTextScroll(`Turn ${turnCount}: ${turn.text}`);
            }
            if (turn.debug_turn_result) {
              appendToTextScroll(turn.debug_turn_result);
            }
            
            // Wrap single turn in array for animateGameTurns
            if (turn.is_final_turn_of_quarter) {
              console.log('🎬 [FINAL TURN DEBUG] Starting animation of final turn', {
                turn_result_type: turn.result_type,
                turn_text: turn.text?.substring(0, 50)
              });
            }
            await animateGameTurns({
              scene: this,
              simData: { 
                ...initialSimData,
                turns: [turn],
                home_team: initialSimData.home_team,
                away_team: initialSimData.away_team
              },
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              onUpdate: updateScoreboard
            });
            if (turn.is_final_turn_of_quarter) {
              console.log('✅ [FINAL TURN DEBUG] Animation of final turn completed', {
                turn_result_type: turn.result_type,
                turn_text: turn.text?.substring(0, 50)
              });
            }
          }
          
          // Update scores and game state after each turn
          updateScoreboard({
            home_score: turnData.home_score,
            away_score: turnData.away_score,
            home_team_fouls: turnData.home_team_fouls,
            away_team_fouls: turnData.away_team_fouls,
            clock: turnData.clock
          });
          
          // Track latest scores for game completion check
          if (turnData.home_score !== undefined) {
            lastHomeScore = turnData.home_score;
          }
          if (turnData.away_score !== undefined) {
            lastAwayScore = turnData.away_score;
          }
          
          // Check if next turn is HCO (eligible for quick adjust window)
          // Use finalTurn (last sub-turn in batch, or the single turn)
          const nextIsHCO = turnData.next_offensive_state === 'HCO';
          const currentIsFastBreak = finalTurn.fast_break || finalTurn.result_type === 'FAST_BREAK';
          const currentIsFreethrow = finalTurn.result_type === 'FREE_THROW';
          const currentIsFCP = finalTurn.fcp_foul || finalTurn.result_type === 'FCP';
          const currentIsHCT = finalTurn.hct_foul || finalTurn.result_type === 'HCT';
          
          // SIMPLIFIED: turnData.offense_team is ALREADY who has offense next
          // (API returns this AFTER possession flips have been processed)
          const nextOffenseTeam = turnData.offense_team;
          const userTeamName = this.userTeamSide === 'home' ? homeTeam : awayTeam;
          const userHasOffenseNext = nextOffenseTeam === userTeamName;
          
          // Quick Adjust Check
          
          // ==================== CLIPBOARD COUNTDOWN (DISABLED FOR NOW) ====================
          // User can preset calls anytime; no forced decision window
          // Future: Re-enable for "coaching moments" feature
          /*
          // Show clipboard countdown if:
          // 1. Next state is HCO
          // 2. Current turn is NOT Fast Break, Free Throw, FCP, or HCT
          // 3. User's team is on offense next
          if (nextIsHCO && !currentIsFastBreak && !currentIsFreethrow && !currentIsFCP && !currentIsHCT && userHasOffenseNext) {
            console.log('📋 Showing clipboard countdown (5 seconds)');
            
            // Determine transition type for animation
            let transitionType = 'INBOUND_PASS'; // Default
            if (finalTurn.result_type === 'DREB') {
              transitionType = 'DREB';
            } else if (finalTurn.result_type === 'SIDE_INBOUND') {
              transitionType = 'SIDE_INBOUND';
            }
            
            // Start clipboard countdown timer UI and player animation simultaneously
            const countdownPromise = window.showClipboardCountdown ? window.showClipboardCountdown(5000) : Promise.resolve();
            const animationPromise = animateCountdownTransition({
              scene: this,
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              transitionType: transitionType,
              offenseTeamId: nextOffenseTeam,
              homeTeamId: initialSimData.home_team_id,
              duration: 5000
            });
            
            // Wait for both to complete
            await Promise.all([countdownPromise, animationPromise]);
            
            console.log('📋 Countdown complete, using preset overrides:', {
              offense: window.nextOffenseOverride || 'auto',
              defense: window.nextDefenseOverride || 'auto'
            });
          }
          */
          
          // ✅ FIX: Check if quarter is complete AFTER animating the turn
          // This ensures the final turn of the quarter is animated before handling quarter completion
          if (turnData.quarter_complete) {
            console.log('✅ [FINAL TURN DEBUG] Quarter complete! (after final turn animation)', {
              turn_result_type: turn?.result_type,
              turn_text: turn?.text?.substring(0, 50),
              time_remaining_after_turn: turnData.time_remaining,
              clock_after_turn: turnData.clock,
              turnCount,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              is_final: turnData.is_final,
              animation_completed: true
            });
            quarterComplete = true;
            lastTurnData = turnData; // Store last turn data for game completion check
            
            // Update final scores
            updateScoreboard({
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_fouls: turnData.home_team_fouls,
              away_team_fouls: turnData.away_team_fouls,
              clock: turnData.clock
            });
            
            // Update tracked scores from final turnData
            if (turnData.home_score !== undefined) {
              lastHomeScore = turnData.home_score;
            }
            if (turnData.away_score !== undefined) {
              lastAwayScore = turnData.away_score;
            }
            
            // Track the next quarter number from backend
            if (turnData.quarter !== undefined) {
              nextQuarterNumber = turnData.quarter;
            }
            
            break;
          }
          
          // Small delay between turns for readability (optional)
          await new Promise(resolve => setTimeout(resolve, 100));
          
        } catch (error) {
          console.error('❌ Error in turn-by-turn loop:', error);
          // ✅ FIX: Don't end quarter on API errors (404, network issues, etc.)
          // Only end quarter if backend explicitly signals completion (quarter_complete=true)
          // Check if the current or last turn data indicates quarter completion before breaking
          // ✅ FIX: Use lastTurnData (turnData may be undefined if error occurred before assignment)
          const dataToCheck = lastTurnData;
          if (dataToCheck && (dataToCheck.quarter_complete === true || dataToCheck.time_remaining <= 0)) {
            // Backend signaled quarter completion - exit loop normally
            console.log('✅ Quarter complete detected after error, exiting loop');
            quarterComplete = true;
            lastTurnData = dataToCheck;
            break;
          }
          // ✅ FIX: For API errors (404, network issues), don't continue - show error and exit
          // This prevents premature quarter completion
          if (error.message && (error.message.includes('Game not found') || error.message.includes('API error'))) {
            console.error('❌ Critical API error - stopping simulation:', error.message);
            // Don't set quarterComplete - exit loop without triggering quarter completion
            break;
          }
          // For animation errors (like missing showAnnouncement), log and continue
          // The backend will signal quarter completion when time_remaining <= 0
          console.warn('⚠️ Animation error occurred, continuing to next turn');
          continue;
        }
      }
      
      // ✅ FIX: Skip quarter completion logic if timeout turn was detected
      // Timeout turns should exit immediately - navigation is handled by timeoutButtonManager
      if (timeoutTurnDetected) {
        console.log('⏸️ TIMEOUT: Exiting simulateTurnByTurn after timeout turn - preventing quarter completion');
        return { timeoutDetected: true };
      }
      
      // ✅ FIX: Only proceed with quarter completion if backend explicitly signaled it
      // Don't complete quarter on API errors (404, network issues, etc.)
      if (!quarterComplete) {
        console.warn('⚠️ Simulation loop ended but quarter not complete. This may indicate an API error or game state issue.');
        // Don't proceed with quarter completion logic - return early
        return { timeoutDetected: false };
      }
      
      console.log(`🏁 Quarter ${this.quarter} finished! Total turns: ${turnCount}`);
      
      // Check if game should end or go to overtime
      // nextQuarterNumber is the quarter number the backend is ready for next
      // So the quarter we just finished is nextQuarterNumber - 1
      // ✅ FIX: Use this.quarter (the quarter we just finished) instead of nextQuarterNumber - 1
      // This is more reliable since this.quarter is set by the backend
      const quarterThatJustFinished = this.quarter;
      
      // Use scores from lastTurnData if available (most recent/accurate), otherwise fall back to tracked scores
      const finalHomeScore = (lastTurnData && lastTurnData.home_score !== undefined) 
        ? lastTurnData.home_score 
        : lastHomeScore;
      const finalAwayScore = (lastTurnData && lastTurnData.away_score !== undefined)
        ? lastTurnData.away_score
        : lastAwayScore;
      const finalIsTied = finalHomeScore === finalAwayScore;
      
      // Check if backend marked game as final (more reliable than frontend calculation)
      let isFinalFromBackend = false;
      if (lastTurnData && lastTurnData.is_final !== undefined) {
        isFinalFromBackend = lastTurnData.is_final;
      }
      
      console.log('🏁 Game completion check:', {
        quarterJustFinished: quarterThatJustFinished,
        nextQuarter: nextQuarterNumber,
        homeScore: finalHomeScore,
        awayScore: finalAwayScore,
        isTied: finalIsTied,
        isFinalFromBackend: isFinalFromBackend,
        lastTurnDataScores: lastTurnData ? { home: lastTurnData.home_score, away: lastTurnData.away_score } : null
      });
      
      // Game ends if:
      // 1. Backend says is_final = true (Q4+ complete and not tied)
      // 2. Q4 is complete and scores are NOT tied → game over
      // 3. Any OT is complete and scores are NOT tied → game over
      // Game continues if:
      // 1. Q4 is complete and scores ARE tied → go to OT
      // 2. OT is complete and scores ARE tied → go to next OT
      
      // Check tie condition FIRST - if tied, go to OT regardless of isFinalFromBackend
      if (quarterThatJustFinished === 4 && finalIsTied) {
        // Q4 tied - go to OT
        console.log('⏰ Game tied after Q4! Going to overtime...');
        // Show locker room popup for OT
        const nextQ = nextQuarterNumber; // Should be 5 (first OT)
        const params = new URLSearchParams(window.location.search);
        params.set('game_id', this.gameId);
        params.set('quarter', nextQ);
        params.set('period', 'OT1');
        // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
        
        // Create locker room popup
        const popup = document.createElement('div');
        popup.className = 'locker-room-popup';
        popup.innerHTML = `
          <div class="locker-room-content">
            <h2>Overtime!</h2>
            <p>Game tied ${finalHomeScore}-${finalAwayScore}</p>
            <button class="locker-room-button">Start Overtime</button>
          </div>
        `;
        document.body.appendChild(popup);
        
        // Wire up button
        const button = popup.querySelector('.locker-room-button');
        button.addEventListener('click', () => {
          window.location.href = `/set-lineup.html?${params.toString()}`;
        });
        return;
      } else if (quarterThatJustFinished > 4 && finalIsTied) {
        // OT tied - go to next OT
        const currentOTNumber = quarterThatJustFinished - 4;
        const nextOTNumber = currentOTNumber + 1;
        console.log(`⏰ OT${currentOTNumber} tied! Going to OT${nextOTNumber}...`);
        const nextOT = nextQuarterNumber; // Should be the next OT quarter number
        const params = new URLSearchParams(window.location.search);
        params.set('game_id', this.gameId);
        params.set('quarter', nextOT);
        params.set('period', `OT${nextOTNumber}`);
        // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
        
        // Create locker room popup
        const popup = document.createElement('div');
        popup.className = 'locker-room-popup';
        popup.innerHTML = `
          <div class="locker-room-content">
            <h2>Overtime ${currentOTNumber} Complete!</h2>
            <p>Game still tied ${finalHomeScore}-${finalAwayScore}</p>
            <button class="locker-room-button">Start OT${nextOTNumber}</button>
          </div>
        `;
        document.body.appendChild(popup);
        
        // Wire up button
        const button = popup.querySelector('.locker-room-button');
        button.addEventListener('click', () => {
          window.location.href = `/set-lineup.html?${params.toString()}`;
        });
        return;
      } else if (isFinalFromBackend || (quarterThatJustFinished >= 4 && !finalIsTied)) {
        // Game is over - finalize
        console.log('🏆 Game complete! Finalizing...');
        
        // ✅ FIX: Update this.isFinal so the "no animation" path also knows game is final
        this.isFinal = true;
        
        const finalize = async () => {
          const { finalizeGame } = await import('./finalizeGame.js');
          
          // ✅ FIX: Use final_game_document from simulate-quarter response if available
          // This eliminates race condition - backend returns complete document when is_final=True
          // Works for Q4 (not tied) and any OT that ends with a winner
          let finalGameData = initialSimData;
          
          // Check if lastTurnData contains final_game_document (returned from simulate-quarter)
          if (lastTurnData && lastTurnData.final_game_document) {
            console.log('✅ Using final_game_document from simulate-quarter response (no fetch needed)');
            finalGameData = lastTurnData.final_game_document;
            console.log('✅ Final game document details:', {
              game_id: finalGameData.game_id || finalGameData._id,
              quarter: finalGameData.quarter,
              is_final: finalGameData.is_final,
              hasBoxScore: !!finalGameData.box_score,
              boxScoreKeys: finalGameData.box_score ? Object.keys(finalGameData.box_score) : []
            });
          } else if (gameId) {
            // Fallback: Fetch from API if final_game_document not in response
            try {
              console.log('📥 final_game_document not in response, fetching from API...');
              const gameResponse = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`));
              if (gameResponse.ok) {
                finalGameData = await gameResponse.json();
                console.log('✅ Fetched final game data:', {
                  game_id: finalGameData.game_id || finalGameData._id,
                  quarter: finalGameData.quarter,
                  is_final: finalGameData.is_final,
                  hasBoxScore: !!finalGameData.box_score,
                  boxScoreKeys: finalGameData.box_score ? Object.keys(finalGameData.box_score) : []
                });
              } else {
                console.warn('⚠️ Failed to fetch final game data, using initialSimData:', gameResponse.status);
              }
            } catch (err) {
              console.error('❌ Error fetching final game data, using initialSimData:', err);
            }
          }
          
          // ✅ UNIFIED STRUCTURE: Get team names from unified teams object, fallback to old structure
          const { home: homeTeamName, away: awayTeamName } = gameStore.getTeams();
          const finalHomeTeamId = finalGameData.home_team_id;
          const finalAwayTeamId = finalGameData.away_team_id;
          const finalTeamsObj = finalGameData.teams || {};
          const finalHomeTeamObj = finalHomeTeamId && finalTeamsObj[finalHomeTeamId] ? finalTeamsObj[finalHomeTeamId] : null;
          const finalAwayTeamObj = finalAwayTeamId && finalTeamsObj[finalAwayTeamId] ? finalTeamsObj[finalAwayTeamId] : null;
          
          const homeName = homeTeamName || finalHomeTeamObj?.name || finalGameData.home_team?.name || finalGameData.home_team;
          const awayName = awayTeamName || finalAwayTeamObj?.name || finalGameData.away_team?.name || finalGameData.away_team;
          
          // ✅ UNIFIED STRUCTURE: Update team objects with final scores (if unified structure exists)
          // For unified structure, scores are updated in teams object
          // For backward compatibility, maintain old structure if it exists
          let updatedHomeTeam = null;
          let updatedAwayTeam = null;
          if (finalHomeTeamObj) {
            updatedHomeTeam = { ...finalHomeTeamObj, score: finalHomeScore };
          } else if (typeof finalGameData.home_team === 'object') {
            updatedHomeTeam = { ...finalGameData.home_team, score: finalHomeScore };
          } else {
            updatedHomeTeam = finalGameData.home_team;
          }
          if (finalAwayTeamObj) {
            updatedAwayTeam = { ...finalAwayTeamObj, score: finalAwayScore };
          } else if (typeof finalGameData.away_team === 'object') {
            updatedAwayTeam = { ...finalGameData.away_team, score: finalAwayScore };
          } else {
            updatedAwayTeam = finalGameData.away_team;
          }
          
          // Update simData.score with current final scores (finalizeGame prioritizes this)
          // ✅ FIX: Preserve final_game_document if it was in the response (from simulate-quarter)
          // This ensures complete_week() gets the complete document without database lookup
          const updatedSimData = {
            ...finalGameData,
            home_score: finalHomeScore,
            away_score: finalAwayScore,
            game_id: gameId || finalGameData.game_id || finalGameData._id,
            home_team: updatedHomeTeam,
            away_team: updatedAwayTeam,
            score: {
              ...(finalGameData.score || {}),
              [homeName]: finalHomeScore,
              [awayName]: finalAwayScore
            }
          };
          
          // ✅ FIX: Preserve final_game_document if it was in lastTurnData (from simulate-quarter)
          if (lastTurnData && lastTurnData.final_game_document) {
            updatedSimData.final_game_document = lastTurnData.final_game_document;
          }
          
          console.log('🔍 [GAMESCENE] Calling finalizeGame with:', {
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            game_id: updatedSimData.game_id || updatedSimData._id,
            hasFinalGameDocument: !!updatedSimData.final_game_document
          });
          
          const finalScore = await finalizeGame({
            simData: updatedSimData,
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            game: this.game,
          });
          this.finalScore = finalScore;
          this.finalized = true;
          if (window.GOB_Analytics) {
            if (this.tournamentId) window.GOB_Analytics.tournamentGameCompleted();
            else if (this.franchiseId) window.GOB_Analytics.franchiseGameCompleted();
            else window.GOB_Analytics.singleGameCompleted();
          }
          // Show game completion popup (absolute path for Netlify/module resolution)
          const base = (typeof window !== 'undefined' && window.API_CONFIG) ? window.API_CONFIG.getStaticPath() : '';
          const { showGameCompletionPopup } = await import(`${base}/js/phaser/utils/gameCompletionPopup.js`);
          const mode = this.tournamentId ? 'tournament' : (this.franchiseId ? 'franchise' : 'single');
          showGameCompletionPopup({
            gameId: gameId,
            mode: mode,
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            teamId: this.teamId, // ✅ SS&S: Pass team_id (ObjectId) for navigation anchor preservation
            finalScore: finalScore
          });
          
          return finalScore;
        };
        await finalize();
        return; // Exit - game is over
      } else {
        // Regular quarter complete (Q1-Q3) - show locker room popup
        console.log('✅ Quarter complete - showing locker room popup');
        const nextQ = this.quarter + 1;
        
        // ✅ FIX: Use TimeoutNavigationHelper (same as Sim Quarter) to ensure resume_from_timeout=false
        // This matches the working Sim Quarter pattern exactly
        const helper = window.TimeoutNavigationHelper;
        if (!helper) {
          console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
          // Fallback to manual params if helper not available
          const params = new URLSearchParams(window.location.search);
          params.set('game_id', this.gameId);
          params.set('quarter', nextQ);
          params.set('period', `Q${nextQ}`);
          params.set('resume_from_timeout', 'false');
          const finalUrl = `/set-lineup.html?${params.toString()}`;
          window.location.href = finalUrl;
          return;
        }
        
        // Get teams from gameStore (same as Sim Quarter pattern)
        const teams = gameStore.getTeams();
        const sourceParams = new URLSearchParams(window.location.search);
        
        // Build params using helper (exactly like Sim Quarter does)
        const params = helper.buildGameNavigationParams({
          sourceParams: sourceParams,
          targetQuarter: nextQ,
          gameId: this.gameId,
          resumeFromTimeout: false, // ✅ CRITICAL: Not a timeout resume (quarter break)
          lineup: {}, // Lineup will be set on lineup screen
          myTeamSide: this.userTeamSide || 'home',
          overrides: {
            home: teams.home,
            away: teams.away,
            mode: this.mode,
            tournament_id: this.tournamentId,
            franchise_id: this.franchiseId,
            team_id: this.teamId
          }
        });
        
        console.log('🔍 [DEBUG QTR BREAK] gameScene.js - Using TimeoutNavigationHelper (Sim Quarter pattern):', {
          quarter: this.quarter,
          nextQ: nextQ,
          gameId: this.gameId,
          resume_from_timeout: params.get('resume_from_timeout'),
          fullParams: Object.fromEntries(params.entries())
        });
        
        // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
        
        // Create locker room popup
        const popup = document.createElement('div');
        popup.className = 'locker-room-popup';
        popup.innerHTML = `
          <div class="locker-room-content">
            <h2>Quarter ${this.quarter} Complete!</h2>
            <button class="locker-room-button">Go To Locker Room</button>
          </div>
        `;
        document.body.appendChild(popup);
        
        // Wire up button
        const button = popup.querySelector('.locker-room-button');
        button.addEventListener('click', () => {
          const finalUrl = `/set-lineup.html?${params.toString()}`;
          console.log('🔍 [DEBUG QTR BREAK] gameScene.js - Navigating to set-lineup:', finalUrl);
          window.location.href = finalUrl;
        });
        return;
      }
    }
  };
}
